import logging
from azure.search.documents.indexes.models import (
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerIndexProjections,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset,
)
from azure.search.documents.indexes import SearchIndexerClient
from .EnvHelper import EnvHelper
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


class AzureSearchIVSkillsetHelper:
    def __init__(self, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.indexer_client = SearchIndexerClient(
            self.env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )

    def create_skillset(self):
        skillset_name = f"{self.env_helper.AZURE_SEARCH_INDEX}-skillset"

        split_skill = SplitSkill(
            description="Split skill to chunk documents",
            text_split_mode="pages",
            context="/document",
            maximum_page_length=2000,
            page_overlap_length=500,
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/content"),
            ],
            outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
        )

        embedding_skill = AzureOpenAIEmbeddingSkill(
            description="Skill to generate embeddings via Azure OpenAI",
            context="/document/pages/*",
            resource_uri=self.env_helper.AZURE_OPENAI_ENDPOINT,
            deployment_id=self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
            api_key=(
                self.env_helper.OPENAI_API_KEY
                if self.env_helper.AZURE_AUTH_TYPE == "keys"
                else None
            ),
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/pages/*"),
            ],
            outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
        )

        index_projections = SearchIndexerIndexProjections(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.env_helper.AZURE_SEARCH_INDEX,
                    parent_key_field_name="parent_id",
                    source_context="/document/pages/*",
                    mappings=[
                        InputFieldMappingEntry(
                            name="chunk", source="/document/pages/*"
                        ),
                        InputFieldMappingEntry(
                            name="vector", source="/document/pages/*/vector"
                        ),
                        InputFieldMappingEntry(
                            name="title", source="/document/metadata_storage_name"
                        ),
                        InputFieldMappingEntry(
                            name="source", source="/document/metadata_storage_path"
                        ),
                        InputFieldMappingEntry(
                            name="content", source="/document/pages/*"
                        ),
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
            skills=[split_skill, embedding_skill],
            index_projections=index_projections,
        )

        self.indexer_client.create_or_update_skillset(skillset)
        logger.info(f"{skillset.name} created")
        return skillset.name
