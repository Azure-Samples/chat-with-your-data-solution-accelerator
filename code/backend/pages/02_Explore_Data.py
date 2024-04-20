import streamlit as st
import os
import json
import traceback
import pandas as pd
import sys
from batch.utilities.helpers.AzureSearchHelper import AzureSearchHelper
from dotenv import load_dotenv
from batch.utilities.helpers.EnvHelper import EnvHelper
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()

load_dotenv()

st.set_page_config(
    page_title="Explore Data",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)
mod_page_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(mod_page_style, unsafe_allow_html=True)

# CSS to inject contained in a string
hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """

# Inject CSS with Markdown
st.markdown(hide_table_row_index, unsafe_allow_html=True)


def get_search_client(env_helper):
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        return SearchClient(
            endpoint=env_helper.AZURE_SEARCH_SERVICE,
            index_name=env_helper.AZURE_SEARCH_INDEX,
            credential=(
                AzureKeyCredential(env_helper.AZURE_SEARCH_KEY)
                if env_helper.is_auth_type_keys()
                else DefaultAzureCredential()
            ),
        )
    else:
        vector_store_helper: AzureSearchHelper = AzureSearchHelper()
        return vector_store_helper.get_vector_store().client


def perform_search(search_client, filename, env_helper):
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        return search_client.search(
            search_text="*",
            select=["id", "chunk_id", "content"],
            filter=f"title eq '{filename}'",
        )
    else:
        return search_client.search(
            "*", select="title, content, metadata", filter=f"title eq '{filename}'"
        )


def process_results(results, env_helper):
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        data = [[result["chunk_id"], result["content"]] for result in results]
    else:
        data = [
            [json.loads(result["metadata"])["chunk"], result["content"]]
            for result in results
        ]
    return pd.DataFrame(data, columns=("Chunk", "Content")).sort_values(by=["Chunk"])


try:
    search_client = get_search_client(env_helper)
    results = search_client.search("*", facets=["title"])
    unique_files = [filename["value"] for filename in results.get_facets()["title"]]
    filename = st.selectbox("Select your file:", unique_files)
    st.write("Showing chunks for:", filename)

    results = perform_search(search_client, filename, env_helper)
    df = process_results(results, env_helper)
    st.table(df)


except Exception:
    st.error(traceback.format_exc())
