from backend.pages.utilities.SearchHandlerBase import SearchHandlerBase
from backend.batch.utilities.helpers.AzureSearchHelper import AzureSearchHelper
import json
import pandas as pd
import streamlit as st


class AzureSearchHandler(SearchHandlerBase):
    def create_search_client(self):
        vector_store_helper = AzureSearchHelper()
        return vector_store_helper.get_vector_store().client

    def perform_search(self, filename):
        return self.search_client.search(
            "*", select="title, content, metadata", filter=f"title eq '{filename}'"
        )

    def process_results(self, results):
        data = [
            [json.loads(result["metadata"])["chunk"], result["content"]]
            for result in results
        ]
        return pd.DataFrame(data, columns=("Chunk", "Content")).sort_values(
            by=["Chunk"]
        )

    def get_files(self):
        return self.search_client.search(
            "*", select="id, title", include_total_count=True
        )

    def output_results(self, results):
        files = {}
        if results.get_count() == 0:
            st.info("No files to delete")
            st.stop()
        else:
            st.write("Select files to delete:")

        for result in results:
            id = result["id"]
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
                ids_to_delete += [{"id": id} for id in ids]

        if len(ids_to_delete) == 0:
            st.info("No files selected")
            st.stop()

        self.search_client.delete_documents(ids_to_delete)

        st.success("Deleted files: " + str(files_to_delete))
