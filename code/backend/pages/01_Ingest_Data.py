from os import path
import streamlit as st
from typing import Optional
import mimetypes
import traceback
import chardet
from datetime import datetime, timedelta
import logging
import requests
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    ContentSettings,
    UserDelegationKey,
)
import urllib.parse
import sys
from batch.utilities.helpers.ConfigHelper import ConfigHelper
from batch.utilities.helpers.EnvHelper import EnvHelper

sys.path.append(path.join(path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
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


def request_user_delegation_key(
    blob_service_client: BlobServiceClient,
) -> UserDelegationKey:
    # Get a user delegation key that's valid for 1 day
    delegation_key_start_time = datetime.utcnow()
    delegation_key_expiry_time = delegation_key_start_time + timedelta(days=1)

    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=delegation_key_start_time,
        key_expiry_time=delegation_key_expiry_time,
    )

    return user_delegation_key


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


def add_urls():
    params = {}
    if env_helper.FUNCTION_KEY is not None:
        params["code"] = env_helper.FUNCTION_KEY
        params["clientId"] = "clientKey"
    urls = st.session_state["urls"].split("\n")
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


def upload_file(bytes_data: bytes, file_name: str, content_type: Optional[str] = None):
    # Upload a new file
    st.session_state["filename"] = file_name
    if content_type is None:
        content_type = mimetypes.MimeTypes().guess_type(file_name)[0]
        charset = (
            f"; charset={chardet.detect(bytes_data)['encoding']}"
            if content_type == "text/plain"
            else ""
        )
        content_type = content_type if content_type is not None else "text/plain"
    account_name = env_helper.AZURE_BLOB_ACCOUNT_NAME
    if env_helper.AZURE_AUTH_TYPE == "rbac":
        credential = DefaultAzureCredential()
        account_url = f"https://{account_name}.blob.core.windows.net/"
        blob_service_client = BlobServiceClient(
            account_url=account_url, credential=credential
        )
        user_delegation_key = request_user_delegation_key(
            blob_service_client=blob_service_client
        )
        container_name = env_helper.AZURE_BLOB_CONTAINER_NAME
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=file_name
        )
        blob_client.upload_blob(
            bytes_data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type + charset),
        )
        st.session_state["file_url"] = (
            blob_client.url
            + "?"
            + generate_blob_sas(
                account_name,
                container_name,
                file_name,
                user_delegation_key=user_delegation_key,
                permission="r",
                expiry=datetime.utcnow() + timedelta(hours=3),
            )
        )
    else:
        account_key = env_helper.AZURE_BLOB_ACCOUNT_KEY
        container_name = env_helper.AZURE_BLOB_CONTAINER_NAME
        if account_name is None or account_key is None or container_name is None:
            raise ValueError(
                "Please provide values for AZURE_BLOB_ACCOUNT_NAME, AZURE_BLOB_ACCOUNT_KEY and AZURE_BLOB_CONTAINER_NAME"
            )
        connect_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
        blob_service_client: BlobServiceClient = (
            BlobServiceClient.from_connection_string(connect_str)
        )
        # Create a blob client using the local file name as the name for the blob
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=file_name
        )
        # Upload the created file
        blob_client.upload_blob(
            bytes_data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type + charset),
        )
        # Generate a SAS URL to the blob and return it
        st.session_state["file_url"] = (
            blob_client.url
            + "?"
            + generate_blob_sas(
                account_name,
                container_name,
                file_name,
                account_key=account_key,
                permission="r",
                expiry=datetime.utcnow() + timedelta(hours=3),
            )
        )


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
        if uploaded_files is not None:
            for up in uploaded_files:
                # To read file as bytes:
                bytes_data = up.getvalue()
                if st.session_state.get("filename", "") != up.name:
                    # Upload a new file
                    upload_file(bytes_data, up.name)
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
            st.button("Process and ingest web pages", on_click=add_urls, key="add_url")

except Exception:
    st.error(traceback.format_exc())
