import streamlit as st
import os, json, re, io
from os import path
import requests
import mimetypes
import traceback
import chardet
from utilities.helper import LLMHelper
import uuid
from redis.exceptions import ResponseError 
from urllib import parse
import logging
from utilities.azureblobstorage import AzureBlobStorageClient
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

def check_deployment():
    # Check if the deployment is working
    #\ 1. Check if the llm is working
    try:
        llm_helper = LLMHelper()
        llm_helper.get_completion("Generate a joke!")
        st.success("LLM is working!")
    except Exception as e:
        st.error(f"""LLM is not working.  
            Please check you have a deployment name {llm_helper.deployment_name} in your Azure OpenAI resource {llm_helper.api_base}.  
            If you are using an Instructions based deployment (text-davinci-003), please check you have an environment variable OPENAI_DEPLOYMENT_TYPE=Text or delete the environment variable OPENAI_DEPLOYMENT_TYPE.  
            If you are using a Chat based deployment (gpt-35-turbo or gpt-4-32k or gpt-4), please check you have an environment variable OPENAI_DEPLOYMENT_TYPE=Chat.  
            Then restart your application.
            """)
        st.error(traceback.format_exc())
    #\ 2. Check if the embedding is working
    try:
        llm_helper = LLMHelper()
        llm_helper.embeddings.embed_documents(texts=["This is a test"])
        st.success("Embedding is working!")
    except Exception as e:
        st.error(f"""Embedding model is not working.  
            Please check you have a deployment named "text-embedding-ada-002" for "text-embedding-ada-002" model in your Azure OpenAI resource {llm_helper.api_base}.  
            Then restart your application.
            """)
        st.error(traceback.format_exc())
    #\ 3. Check if the VectorDB is working 
    llm_helper = LLMHelper()
    try:
        llm_helper.vector_store.index_exists()
        st.success("Azure Cognitive Search is working!")
    except Exception as e:
        st.error("""Azure Cognitive Search is not working.  
                    Please check your Azure Cognitive Search service name and service key in the App Settings.  
                    Then restart your application.  
                    """)
        st.error(traceback.format_exc())

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

def upload_text_and_embeddings():
    file_name = f"{uuid.uuid4()}.txt"
    source_url = llm_helper.blob_client.upload_file(st.session_state['doc_text'], file_name=file_name, content_type='text/plain; charset=utf-8')
    llm_helper.add_embeddings_lc(source_url) 
    st.success("Embeddings added successfully.")

def remote_convert_files_and_add_embeddings(process_all=False):
    url = os.getenv('CONVERT_ADD_EMBEDDINGS_URL')
    if process_all:
        url = f"{url}?process_all=true"
    try:
        response = requests.post(url)
        if response.status_code == 200:
            st.success(f"{response.text}\nPlease note this is an asynchronous process and may take a few minutes to complete.")
        else:
            st.error(f"Error: {response.text}")
    except Exception as e:
        st.error(traceback.format_exc())

def add_urls():
    urls = st.session_state['urls'].split('\n')
    for url in urls:
        if url:
            llm_helper.add_embeddings_lc(url)
            st.success(f"Embeddings added successfully for {url}")

def upload_file(bytes_data: bytes, file_name: str):
    # Upload a new file
    st.session_state['filename'] = file_name
    content_type = mimetypes.MimeTypes().guess_type(file_name)[0]
    charset = f"; charset={chardet.detect(bytes_data)['encoding']}" if content_type == 'text/plain' else ''
    st.session_state['file_url'] = llm_helper.blob_client.upload_file(bytes_data, st.session_state['filename'], content_type=content_type+charset)

def upload_config_file(bytes_data: bytes):
    blob_client = AzureBlobStorageClient('aoainachostr', 'fAojSZskTaowJGcrh+lhLAyHqzv25pwyw3AhwN1GBvCEzGKAwjLXHUutooFph20AdGAQDknodl3S+AStR1XuOg==',
'documents')
    blob_client.upload_file(bytes_data, f"settings.json", content_type='text/plain; charset=utf-8')
    # blob_client.upload_file(bytes_data, f"config/{file_name}.txt", content_type='text/plain; charset=utf-8')

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

    menu_items = {
	'Get help': None,
	'Report a bug': None,
	'About': '''
	 ## Embeddings App
	 Embedding testing application.
	'''
    }
    st.set_page_config(layout="wide", menu_items=menu_items)

    llm_helper = LLMHelper()

    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        st.image(os.path.join('images','logo.png'))

    with st.expander("Check deployment integration", expanded=True):
        # Check deployment
        st.button("Check deployment", on_click=check_deployment, key="check_deployment")

    with st.expander("Add documents in Batch", expanded=True):
        uploaded_files = st.file_uploader("Upload a document to add it to the Azure Storage Account", type=['pdf','jpeg','jpg','png', 'txt'], accept_multiple_files=True)
        if uploaded_files is not None:
            for up in uploaded_files:
                # To read file as bytes:
                bytes_data = up.getvalue()

                if st.session_state.get('filename', '') != up.name:
                    # Upload a new file
                    upload_file(bytes_data, up.name)
                    if up.name.endswith('.txt'):
                        # Add the text to the embeddings
                        llm_helper.blob_client.upsert_blob_metadata(up.name, {'converted': "true"})

        col1, col2, col3 = st.columns([2,2,2])
        with col1:
            st.button("Process new files and add embeddings", on_click=remote_convert_files_and_add_embeddings)
        with col3:
            st.button("Process all files and add embeddings", on_click=remote_convert_files_and_add_embeddings, args=(True,))

    with st.expander("Add URLs to the knowledge base", expanded=True):
        col1, col2 = st.columns([3,1])
        with col1: 
            st.session_state['urls'] = st.text_area("Add a URLs and than click on 'Compute Embeddings'", placeholder="PLACE YOUR URLS HERE SEPARATED BY A NEW LINE", height=100)

        with col2:
            st.selectbox('Embeddings models', [llm_helper.get_embeddings_model()['doc']], disabled=True, key="embeddings_model_url")
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
    upload_config_file(json_config)

except Exception as e:
    st.error(traceback.format_exc())