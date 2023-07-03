import streamlit as st
import os, json
from typing import Optional
import mimetypes
import traceback
import chardet
from datetime import datetime, timedelta
import logging
import requests
from azure.storage.blob import BlobServiceClient, generate_blob_sas, ContentSettings
import urllib.parse
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
    st.write("TODO: Implement functionality")
    from utilities import azuresearch

    search_client = azuresearch.get_search_client(endpoint=os.getenv("AZURE_SEARCH_SERVICE"),
                                      key=os.getenv("AZURE_SEARCH_KEY"),
                                      index_name=os.getenv("AZURE_SEARCH_INDEX"))

    count = search_client.get_document_count()
    st.write(f'The index contains {count} documents.')
    

except Exception as e:
    st.error(traceback.format_exc())
