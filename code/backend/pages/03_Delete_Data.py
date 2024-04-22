import streamlit as st
import os
import traceback
import sys
from dotenv import load_dotenv
from batch.utilities.helpers.EnvHelper import EnvHelper
from backend.pages.utilities.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)
from backend.pages.utilities.AzureSearchHandler import AzureSearchHandler

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()

load_dotenv()

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
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        search_handler: IntegratedVectorizationSearchHandler = (
            IntegratedVectorizationSearchHandler(env_helper)
        )
        search_client = search_handler.search_client
    else:
        search_handler: AzureSearchHandler = AzureSearchHandler(env_helper)
        search_client = search_handler.search_client

    results = search_handler.get_files()
    files = search_handler.output_results(results)
    if st.button("Delete"):
        with st.spinner("Deleting files..."):
            search_handler.delete_files(
                files,
            )

except Exception:
    st.error(traceback.format_exc())
