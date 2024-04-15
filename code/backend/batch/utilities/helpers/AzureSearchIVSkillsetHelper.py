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


class AzureSearchIVSkillsetHelper:
    def __init__(self):
        pass

    def create_skillset(self):
        env_helper: EnvHelper = EnvHelper()
        skillset_name = f"{env_helper.AZURE_SEARCH_INDEX}-skillset"

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
            resource_uri=env_helper.AZURE_OPENAI_ENDPOINT,
            deployment_id=env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
            api_key=env_helper.OPENAI_API_KEY,
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/pages/*"),
            ],
            outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
        )

        index_projections = SearchIndexerIndexProjections(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=env_helper.AZURE_SEARCH_INDEX,
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

        client = SearchIndexerClient(
            env_helper.AZURE_SEARCH_SERVICE,
            (
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.AZURE_AUTH_TYPE == "keys"
                else DefaultAzureCredential()
            ),
        )
        client.create_or_update_skillset(skillset)
        print(f"{skillset.name} created")
        return skillset.name
