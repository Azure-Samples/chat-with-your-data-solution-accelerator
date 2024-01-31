import streamlit as st
import os
import json
import traceback
import logging
import pandas as pd
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utilities.helpers.AzureSearchHelper import AzureSearchHelper
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
st.set_page_config(page_title="Explore Data", page_icon=os.path.join('images','favicon.ico'), layout="wide", menu_items=None)
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
    vector_store_helper : AzureSearchHelper = AzureSearchHelper()
    search_client = vector_store_helper.get_vector_store().client
    # get unique document names by getting facets for title field
    results = search_client.search("*", facets=["title"])
    unique_files = [filename['value'] for filename in results.get_facets()["title"]]
    filename = st.selectbox('Select your file:', unique_files)
    st.write('Showing chunks for:', filename)
    
    results = search_client.search("*", select="title, content, metadata", filter=f"title eq '{filename}'")
    
    data = [[json.loads(result['metadata'])['chunk'], result['content']] for result in results]
    df = pd.DataFrame(data, columns=('Chunk', 'Content')).sort_values(by=['Chunk'])           
    st.table(df)
    

except Exception as e:
    st.error(traceback.format_exc())
