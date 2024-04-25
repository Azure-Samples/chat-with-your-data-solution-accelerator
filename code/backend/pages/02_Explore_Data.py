import streamlit as st
import os
import traceback
import sys
import pandas as pd
from batch.utilities.helpers.EnvHelper import EnvHelper
from batch.utilities.search.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)
from batch.utilities.search.AzureSearchHandler import AzureSearchHandler

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()

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

try:
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        search_handler = IntegratedVectorizationSearchHandler(env_helper)
    else:
        search_handler = AzureSearchHandler(env_helper)

    results = search_handler.search_client.search("*", facets=["title"])
    unique_files = [filename["value"] for filename in results.get_facets()["title"]]
    filename = st.selectbox("Select your file:", unique_files)
    st.write("Showing chunks for:", filename)

    results = search_handler.perform_search(filename)
    data = search_handler.process_results(results)
    df = pd.DataFrame(data, columns=("Chunk", "Content")).sort_values(by=["Chunk"])
    st.table(df)


except Exception:
    st.error(traceback.format_exc())
