import streamlit as st
import os
import traceback
import sys
import logging
from batch.utilities.helpers.env_helper import EnvHelper
from batch.utilities.search.search import Search
from batch.utilities.helpers.config.database_type import DatabaseType
from batch.utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Delete Data",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)


def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Load the common CSS
load_css("pages/common.css")


# CSS to inject contained in a string
hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """

# Inject CSS with Markdown
st.markdown(hide_table_row_index, unsafe_allow_html=True)

try:
    # Initialize session state for selected files
    if "selected_files" not in st.session_state:
        st.session_state.selected_files = {}

    search_handler = Search.get_search_handler(env_helper)
    results = search_handler.get_files()
    if (
        env_helper.DATABASE_TYPE == DatabaseType.COSMOSDB.value
        and (results is None or results.get_count() == 0)
    ) or (env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value and len(results) == 0):
        st.info("No files to delete")
        st.stop()
    else:
        st.write("Select files to delete:")

    files = search_handler.output_results(results)
    # Format filenames with container path for display
    container_name = env_helper.AZURE_BLOB_CONTAINER_NAME
    display_files = {f"/{container_name}/{fname}": fname for fname in files.keys()}

    with st.form("delete_form", clear_on_submit=True, border=False):
        selections = {
            display_name: st.checkbox(display_name, False, key=display_name)
            for display_name in display_files.keys()
        }
        # Map display names back to actual filenames
        selected_files = {
            display_files[display_name]: files[display_files[display_name]]
            for display_name in display_files.keys()
            if selections[display_name]
        }

        if st.form_submit_button("Delete"):
            with st.spinner("Deleting files..."):
                if len(selected_files) == 0:
                    st.info("No files selected")
                    st.stop()
                else:
                    files_to_delete = search_handler.delete_files(
                        selected_files,
                    )
                    blob_client = AzureBlobStorageClient()
                    blob_client.delete_files(
                        selected_files,
                        env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION,
                    )
                    if len(files_to_delete) > 0:
                        # Format deleted files with container path for display
                        # Use original selected_files keys instead of parsing the returned string
                        deleted_list = [f"/{container_name}/{fname}" for fname in selected_files.keys()]
                        st.success("Deleted files: " + ", ".join(deleted_list))
                        st.rerun()
except Exception:
    logger.error(traceback.format_exc())
    st.error("Exception occurred deleting files.")
