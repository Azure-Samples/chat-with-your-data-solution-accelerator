import streamlit as st
import os
import traceback
import logging
import sys

from utilities.helpers.AzureSearchHelper import AzureSearchHelper
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
st.set_page_config(
    page_title="Delete Data",
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


def get_files():
    return search_client.search("*", select="id, title", include_total_count=True)


def output_results(results):
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


def delete_files(files):
    ids_to_delete = []
    files_to_delete = []

    for filename, ids in files.items():
        if st.session_state[filename]:
            files_to_delete.append(filename)
            ids_to_delete += [{"id": id} for id in ids]

    if len(ids_to_delete) == 0:
        st.info("No files selected")
        st.stop()

    search_client.delete_documents(ids_to_delete)

    st.success("Deleted files: " + str(files_to_delete))


try:
    vector_store_helper: AzureSearchHelper = AzureSearchHelper()
    search_client = vector_store_helper.get_vector_store().client

    results = get_files()
    files = output_results(results)

    if st.button("Delete"):
        with st.spinner("Deleting files..."):
            delete_files(files)

except Exception:
    st.error(traceback.format_exc())
