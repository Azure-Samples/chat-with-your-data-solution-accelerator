import streamlit as st
import os
import traceback
import sys
import logging
from batch.utilities.helpers.env_helper import EnvHelper
from batch.utilities.search.Search import Search

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()
logger = logging.getLogger(__name__)

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

try:
    search_handler = Search.get_search_handler(env_helper)

    results = search_handler.get_files()
    if results is None or results.get_count() == 0:
        st.info("No files to delete")
        st.stop()
    else:
        st.write("Select files to delete:")

    files = search_handler.output_results(results)
    selections = {
        filename: st.checkbox(filename, False, key=filename)
        for filename in files.keys()
    }
    selected_files = {
        filename: ids for filename, ids in files.items() if selections[filename]
    }

    if st.button("Delete"):
        with st.spinner("Deleting files..."):
            if len(selected_files) == 0:
                st.info("No files selected")
                st.stop()
            else:
                files_to_delete = search_handler.delete_files(
                    selected_files,
                )
                if len(files_to_delete) > 0:
                    st.success("Deleted files: " + str(files_to_delete))

except Exception:
    logger.error(traceback.format_exc())
    st.error("Exception occurred deleting files.")
