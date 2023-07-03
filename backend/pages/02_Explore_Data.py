import streamlit as st
import os
import math
import traceback
import logging
from utilities import azuresearch
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

try:
    search_client = azuresearch.get_search_client(endpoint=os.getenv("AZURE_SEARCH_SERVICE"),
                                      key=os.getenv("AZURE_SEARCH_KEY"),
                                      index_name=os.getenv("AZURE_SEARCH_INDEX"))

    count = search_client.get_document_count()
    
    page_size = 10
    num_pages = math.ceil(count / page_size)
    page = st.slider("Page", min_value=1, max_value=num_pages, value=1)
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, count)
    
    results = search_client.search("*", select="title, metadata", top=page_size, skip=start_index)
    print(results)
    
    st.write(f"Showing chunks {start_index + 1} to {end_index} (of total {count})")
    with st.container():
        for i, result in enumerate(results):
            st.write(f"{result['title']}\n\n```{result['metadata']}```")
            st.divider()

except Exception as e:
    st.error(traceback.format_exc())
