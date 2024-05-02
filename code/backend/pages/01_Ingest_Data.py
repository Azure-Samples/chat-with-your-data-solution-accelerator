import io
from os import path
from bs4 import BeautifulSoup
import streamlit as st
import traceback
import requests
import urllib.parse
import sys
import logging
from batch.utilities.helpers.config.ConfigHelper import ConfigHelper
from batch.utilities.helpers.EnvHelper import EnvHelper
from batch.utilities.helpers.AzureBlobStorageClient import AzureBlobStorageClient

sys.path.append(path.join(path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Ingest Data",
    page_icon=path.join("images", "favicon.ico"),
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


def remote_convert_files_and_add_embeddings(process_all=False):
    backend_url = urllib.parse.urljoin(
        env_helper.BACKEND_URL, "/api/BatchStartProcessing"
    )
    params = {}
    if env_helper.FUNCTION_KEY is not None:
        params["code"] = env_helper.FUNCTION_KEY
        params["clientId"] = "clientKey"
    if process_all:
        params["process_all"] = "true"
    try:
        response = requests.post(backend_url, params=params)
        if response.status_code == 200:
            st.success(
                f"{response.text}\nPlease note this is an asynchronous process and may take a few minutes to complete."
            )
        else:
            st.error(f"Error: {response.text}")
    except Exception:
        st.error(traceback.format_exc())


def add_urls(blob_client: AzureBlobStorageClient):
    urls = st.session_state["urls"].split("\n")
    if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
        download_url_and_upload_to_blob(blob_client, urls)
    else:
        add_url_embeddings(urls)


def download_url_and_upload_to_blob(
    blob_client: AzureBlobStorageClient, urls: list[str]
):
    for url in urls:
        try:
            response = requests.get(url)
            parsed_data = BeautifulSoup(response.content, "html.parser")
            with io.BytesIO(parsed_data.get_text().encode("utf-8")) as stream:
                st.session_state["filename"] = url
                st.session_state["file_url"] = blob_client.upload_file(
                    stream, url, metadata={"title": url}
                )
            st.success(f"Url {url} added to knowledge base")
        except Exception:
            logger.error(traceback.format_exc())
            st.error(f"Exception occurred while adding {url} to the knowledge base.")


def add_url_embeddings(urls: list[str]):
    params = {}
    if env_helper.FUNCTION_KEY is not None:
        params["code"] = env_helper.FUNCTION_KEY
        params["clientId"] = "clientKey"
    for url in urls:
        body = {"url": url}
        backend_url = urllib.parse.urljoin(
            env_helper.BACKEND_URL, "/api/AddURLEmbeddings"
        )
        r = requests.post(url=backend_url, params=params, json=body)
        if not r.ok:
            raise ValueError(f"Error {r.status_code}: {r.text}")
        else:
            st.success(f"Embeddings added successfully for {url}")


try:
    with st.expander("Add documents in Batch", expanded=True):
        config = ConfigHelper.get_active_config_or_default()
        file_type = [
            processor.document_type for processor in config.document_processors
        ]
        uploaded_files = st.file_uploader(
            "Upload a document to add it to the Azure Storage Account, compute embeddings and add them to the Azure AI Search index. Check your configuration for available document processors.",
            type=file_type,
            accept_multiple_files=True,
        )
        blob_client = AzureBlobStorageClient()
        if uploaded_files is not None:
            for up in uploaded_files:
                # To read file as bytes:
                bytes_data = up.getvalue()
                if st.session_state.get("filename", "") != up.name:
                    # Upload a new file
                    st.session_state["filename"] = up.name
                    st.session_state["file_url"] = blob_client.upload_file(
                        bytes_data, up.name, metadata={"title": up.name}
                    )
            if len(uploaded_files) > 0:
                st.success(
                    f"{len(uploaded_files)} documents uploaded. Embeddings computation in progress. \nPlease note this is an asynchronous process and may take a few minutes to complete.\nYou can check for further details in the Azure Function logs."
                )

        col1, col2, col3 = st.columns([2, 1, 2])
        # with col1:
        #     st.button("Process and ingest new files", on_click=remote_convert_files_and_add_embeddings)
        with col3:
            st.button(
                "Reprocess all documents in the Azure Storage account",
                on_click=remote_convert_files_and_add_embeddings,
                args=(True,),
            )

    with st.expander("Add URLs to the knowledge base", expanded=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_area(
                "Add a URLs and than click on 'Compute Embeddings'",
                placeholder="PLACE YOUR URLS HERE SEPARATED BY A NEW LINE",
                height=100,
                key="urls",
            )

        with col2:
            st.selectbox(
                "Embeddings models",
                [env_helper.AZURE_OPENAI_EMBEDDING_MODEL],
                disabled=True,
            )
            st.button(
                "Process and ingest web pages",
                on_click=lambda: add_urls(blob_client),
                key="add_url",
            )

except Exception:
    st.error(traceback.format_exc())
