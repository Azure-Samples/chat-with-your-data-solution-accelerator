from backend.pages.utilities.SearchHandlerBase import SearchHandlerBase
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
import pandas as pd
import streamlit as st


class IntegratedVectorizationSearchHandler(SearchHandlerBase):
    def create_search_client(self):
        return SearchClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            index_name=self.env_helper.AZURE_SEARCH_INDEX,
            credential=(
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.is_auth_type_keys()
                else DefaultAzureCredential()
            ),
        )

    def perform_search(self, filename):
        return self.search_client.search(
            search_text="*",
            select=["id", "chunk_id", "content"],
            filter=f"title eq '{filename}'",
        )

    def process_results(self, results):
        data = [[result["chunk_id"], result["content"]] for result in results]
        return pd.DataFrame(data, columns=("Chunk", "Content")).sort_values(
            by=["Chunk"]
        )

    def get_files(self):
        return self.search_client.search(
            "*", select="id, chunk_id, title", include_total_count=True
        )

    def output_results(self, results):
        files = {}
        if results.get_count() == 0:
            st.info("No files to delete")
            st.stop()
        else:
            st.write("Select files to delete:")

        for result in results:
            id = result["chunk_id"]
            filename = result["title"]
            if filename in files:
                files[filename].append(id)
            else:
                files[filename] = [id]
                st.checkbox(filename, False, key=filename)

        return files

    def delete_files(self, files):
        ids_to_delete = []
        files_to_delete = []

        for filename, ids in files.items():
            if st.session_state[filename]:
                files_to_delete.append(filename)
                ids_to_delete += [{"chunk_id": id} for id in ids]

        if len(ids_to_delete) == 0:
            st.info("No files selected")
            st.stop()

        self.search_client.delete_documents(ids_to_delete)

        st.success("Deleted files: " + str(files_to_delete))
