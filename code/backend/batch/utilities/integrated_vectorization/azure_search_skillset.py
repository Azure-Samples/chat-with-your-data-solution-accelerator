import logging
from azure.search.documents.indexes.models import (
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    AzureOpenAIEmbeddingSkill,
    OcrSkill,
    MergeSkill,
    ShaperSkill,
    WebApiSkill,
    SearchIndexerIndexProjections,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset,
    SearchIndexerDataUserAssignedIdentity,
)
from azure.search.documents.indexes import SearchIndexerClient
from ..helpers.config.config_helper import IntegratedVectorizationConfig
from ..helpers.env_helper import EnvHelper
from ..helpers.azure_credential_utils import get_azure_credential
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class AzureSearchSkillset:
    def __init__(
        self,
        env_helper: EnvHelper,
        integrated_vectorization_config: IntegratedVectorizationConfig,
    ):
        self.env_helper = env_helper
        self.indexer_client = SearchIndexerClient(
            self.env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.is_auth_type_keys()
                else get_azure_credential(self.env_helper.MANAGED_IDENTITY_CLIENT_ID)
            ),
        )
        self.integrated_vectorization_config = integrated_vectorization_config

    def create_skillset(self):
        skillset_name = f"{self.env_helper.AZURE_SEARCH_INDEX}-skillset"

        ocr_skill = OcrSkill(
            description="Extract text (plain and structured) from image",
            context="/document/normalized_images/*",
            inputs=[
                InputFieldMappingEntry(
                    name="image",
                    source="/document/normalized_images/*",
                )
            ],
            outputs=[
                OutputFieldMappingEntry(name="text", target_name="text"),
                OutputFieldMappingEntry(name="layoutText", target_name="layoutText"),
            ],
        )

        merge_skill = MergeSkill(
            description="Merge text from OCR and text from document",
            context="/document",
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/content"),
                InputFieldMappingEntry(
                    name="itemsToInsert", source="/document/normalized_images/*/text"
                ),
                InputFieldMappingEntry(
                    name="offsets", source="/document/normalized_images/*/contentOffset"
                ),
            ],
            outputs=[
                OutputFieldMappingEntry(name="mergedText", target_name="merged_content")
            ],
        )

        split_skill = SplitSkill(
            description="Split skill to chunk documents",
            text_split_mode="pages",
            context="/document",
            maximum_page_length=self.integrated_vectorization_config.max_page_length,
            page_overlap_length=self.integrated_vectorization_config.page_overlap_length,
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/merged_content"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="textItems", target_name="pages"),
                OutputFieldMappingEntry(name="ordinalPositions", target_name="chunk_nos"),
            ],
        )

        # Custom WebApi skill to combine pages and chunk numbers into a single structure
        combine_pages_and_chunk_nos_skill = WebApiSkill(
            description="Combine pages and chunk numbers together",
            context="/document",
            uri=f"{self.env_helper.BACKEND_URL}/api/combine_pages_and_chunknos",
            http_method="POST",
            inputs=[
                InputFieldMappingEntry(name="pages", source="/document/pages"),
                InputFieldMappingEntry(name="chunk_nos", source="/document/chunk_nos"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="pages_with_chunks", target_name="pages_with_chunks")
            ]
        )

        embedding_skill = AzureOpenAIEmbeddingSkill(
            description="Skill to generate embeddings via Azure OpenAI",
            context="/document/pages_with_chunks/*",
            resource_uri=self.env_helper.AZURE_OPENAI_ENDPOINT,
            deployment_id=self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
            api_key=(
                self.env_helper.OPENAI_API_KEY
                if self.env_helper.is_auth_type_keys()
                else None
            ),
            auth_identity=(
                None
                if getattr(self.env_helper, "APP_ENV", "").lower() == "dev"
                else SearchIndexerDataUserAssignedIdentity(
                    user_assigned_identity=self.env_helper.MANAGED_IDENTITY_RESOURCE_ID
                )
            ),
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/pages_with_chunks/*/page_text"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="embedding", target_name="content_vector")
            ],
        )

        metadata_shaper = ShaperSkill(
            description="Structure metadata fields into a complex object",
            context="/document/pages_with_chunks/*",
            inputs=[
                InputFieldMappingEntry(name="id", source="/document/id"),
                InputFieldMappingEntry(name="source", source="/document/metadata_storage_path"),
                InputFieldMappingEntry(name="title", source="/document/title"),
                InputFieldMappingEntry(name="chunk", source="/document/pages_with_chunks/*/chunk_no"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="output", target_name="metadata_object")
            ]
        )

        index_projections = SearchIndexerIndexProjections(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.env_helper.AZURE_SEARCH_INDEX,
                    parent_key_field_name="id",
                    source_context="/document/pages_with_chunks/*",
                    mappings=[
                        InputFieldMappingEntry(
                            name="content", source="/document/pages_with_chunks/*/page_text"
                        ),
                        InputFieldMappingEntry(
                            name="content_vector",
                            source="/document/pages_with_chunks/*/content_vector",
                        ),
                        InputFieldMappingEntry(name="title", source="/document/title"),
                        InputFieldMappingEntry(
                            name="source", source="/document/metadata_storage_path"
                        ),
                        InputFieldMappingEntry(
                            name="metadata",
                            source="/document/pages_with_chunks/*/metadata_object",
                        )
                    ],
                ),
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            ),
        )

        skillset = SearchIndexerSkillset(
            name=skillset_name,
            description="Skillset to chunk documents and generating embeddings",
            skills=[ocr_skill, merge_skill, split_skill, combine_pages_and_chunk_nos_skill, embedding_skill, metadata_shaper],
            index_projections=index_projections,
        )

        skillset_result = self.indexer_client.create_or_update_skillset(skillset)
        logger.info(f"{skillset.name} created")
        return skillset_result
