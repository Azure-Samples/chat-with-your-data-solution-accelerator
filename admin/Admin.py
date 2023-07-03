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


def check_variables_in_prompt():
    # Check if "summaries" is present in the string custom_prompt
    if "{summaries}" not in st.session_state.custom_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{summaries}".  
        This variable is used to add the content of the documents retrieved from the VectorStore to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.
        """)
        st.session_state.custom_prompt = ""
    if "{question}" not in st.session_state.custom_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{question}".  
        This variable is used to add the user's question to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.  
        """)
        st.session_state.custom_prompt = ""

def remote_convert_files_and_add_embeddings(process_all=False):
    backend_url = urllib.parse.urljoin(os.getenv('BACKEND_URL','http://localhost:7071'), "/api/BatchStartProcessing")
    if process_all:
        url = f"{backend_url}?process_all=true"
    try:
        response = requests.post(backend_url)
        if response.status_code == 200:
            st.success(f"{response.text}\nPlease note this is an asynchronous process and may take a few minutes to complete.")
        else:
            st.error(f"Error: {response.text}")
    except Exception as e:
        st.error(traceback.format_exc())

def add_urls():
    urls = st.session_state['urls'].split('\n')
    for url in urls:
        body = {
            "url": url
        }
        backend_url = urllib.parse.urljoin(os.getenv('BACKEND_URL','http://localhost:7071'), "/api/AddURLEmbeddings")
        r = requests.post(url=backend_url, json=body)
        if not r.ok:
            raise ValueError(f'Error adding embeddings for {url}. Status_code:{r.status_code} Response:{r.text} Backend: {backend_url}')
        else:
            st.success(f'Embeddings added successfully for {url}')


def upload_file(bytes_data: bytes, file_name: str, content_type: Optional[str] = None):    
    # Upload a new file
    st.session_state['filename'] = file_name
    if content_type == None:
        content_type = mimetypes.MimeTypes().guess_type(file_name)[0]
        charset = f"; charset={chardet.detect(bytes_data)['encoding']}" if content_type == 'text/plain' else ''
    account_name = os.getenv('BLOB_ACCOUNT_NAME')
    account_key =  os.getenv('BLOB_ACCOUNT_KEY')
    container_name = os.getenv('BLOB_CONTAINER_NAME')
    if account_name == None or account_key == None or container_name == None:
        raise ValueError("Please provide values for BLOB_ACCOUNT_NAME, BLOB_ACCOUNT_KEY and BLOB_CONTAINER_NAME")
    connect_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    blob_service_client : BlobServiceClient = BlobServiceClient.from_connection_string(connect_str)
    # Create a blob client using the local file name as the name for the blob
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
    # Upload the created file
    blob_client.upload_blob(bytes_data, overwrite=True, content_settings=ContentSettings(content_type=content_type+charset))
    # Generate a SAS URL to the blob and return it
    st.session_state['file_url'] =  blob_client.url + '?' + generate_blob_sas(account_name, container_name, file_name,account_key=account_key,  permission="r", expiry=datetime.utcnow() + timedelta(hours=3))
    

try:
    # Prompt initialisation 
    if 'pre_prompt' not in st.session_state:
        st.session_state['pre_prompt'] = ""
    if 'custom_prompt' not in st.session_state:
        st.session_state['custom_prompt'] = ""
    if 'post_prompt' not in st.session_state:
        st.session_state['post_prompt'] = ""    

    custom_prompt_placeholder = """{summaries}  
    Please reply to the question using only the text above.  
    Question: {question}  
    Answer:"""
    pre_prompt_placeholder = """"""
    post_prompt_placeholder = """"""

    pre_prompt_help = """You can configure a pre prompt by defining how the documents retrieved from the VectorStore will be combined and sent to LLM.
        """
    custom_prompt_help = """You can configure a custom prompt by adding the variables {summaries} and {question} to the prompt.  
    {summaries} will be replaced with the content of the documents retrieved from the VectorStore.  
    {question} will be replaced with the user's question.
        """
    post_prompt_help = """You can configure a post prompt by defining how the user's answer will be processed for fact checking or conflict resolution.
        """

    st.set_page_config(page_title="Admin", page_icon=os.path.join('images','favicon.ico'), layout="wide", menu_items=None)
        
    mod_page_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(mod_page_style, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        st.image(os.path.join('images','logo.png'))


    with st.expander("Add documents in Batch", expanded=True):
        uploaded_files = st.file_uploader("Upload a document to add it to the Azure Storage Account", type=['pdf','jpeg','jpg','png', 'txt'], accept_multiple_files=True)
        if uploaded_files is not None:
            for up in uploaded_files:
                # To read file as bytes:
                bytes_data = up.getvalue()
                if st.session_state.get('filename', '') != up.name:
                    # Upload a new file
                    upload_file(bytes_data, up.name)

        col1, col2, col3 = st.columns([2,2,2])
        with col1:
            st.button("Process new files and add embeddings", on_click=remote_convert_files_and_add_embeddings)
        with col3:
            st.button("Reprocess all documents in the Azure Storage account", on_click=remote_convert_files_and_add_embeddings, args=(True,))

    with st.expander("Add URLs to the knowledge base", expanded=True):
        col1, col2 = st.columns([3,1])
        with col1: 
            st.session_state['urls'] = st.text_area("Add a URLs and than click on 'Compute Embeddings'", placeholder="PLACE YOUR URLS HERE SEPARATED BY A NEW LINE", height=100)

        with col2:
            st.selectbox('Embeddings models', [os.getenv('AZURE_OPENAI_EMBEDDING_MODEL')], disabled=True)
            st.button("Compute Embeddings", on_click=add_urls, key="add_url")

    with st.expander("Define your prompt (check help icon for details on each field)", expanded=True):
        # Custom prompt
        st.text_area("Pre Prompt", key='pre_prompt', on_change=check_variables_in_prompt, placeholder= pre_prompt_placeholder,help=pre_prompt_help, height=50)
        st.text_area("Custom Prompt", key='custom_prompt', on_change=check_variables_in_prompt, placeholder= custom_prompt_placeholder,help=custom_prompt_help, height=50)
        st.text_area("Post Prompt", key='post_prompt', on_change=check_variables_in_prompt, placeholder= post_prompt_placeholder,help=post_prompt_help, height=50)

    with st.expander("Chunking config placeholder", expanded=True):
        # Chunking config input
        ch_size=st.text_input("Chunk size (in tokens)", key='chunking_size', placeholder="500")
        ch_overlap=st.text_input("Chunk overlap (in tokens)", key='chunking_overlap', placeholder="100")
        # Placeholder for future chunking strategies like dynamic layout
        ch_selection=st.selectbox('Chunking strategy', ['Fixed size + Overlap', 'Layout based'], key="chunking_strategy")

    with st.expander("Logging placeholder", expanded=True):
        # Logging placeholder
        st.write("Placeholder for future log configuration")

# Pending: write a file called logging.config.txt into blob storage with log_level inside
    json_config = {"ch_size": ch_size, "ch_overlap": ch_overlap, "ch_strategy": ch_selection, "pre_prompt": st.session_state['pre_prompt'], "custom_prompt": st.session_state['custom_prompt'],"post_prompt": st.session_state['post_prompt']}
    #convert json_config to bytes
    json_config = json.dumps(json_config).encode('utf-8')
    upload_file(json_config, f"settings.json", content_type='text/plain; charset=utf-8')

except Exception as e:
    st.error(traceback.format_exc())
