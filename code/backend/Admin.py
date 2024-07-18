"""
This module contains the code for the Admin app of the Chat with your data Solution Accelerator.
"""

import os
import logging
import sys
import streamlit as st
from azure.monitor.opentelemetry import configure_azure_monitor

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logging.captureWarnings(True)
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
# Raising the azure log level to WARN as it is too verbose
# https://github.com/Azure/azure-sdk-for-python/issues/9422
logging.getLogger("azure").setLevel(os.environ.get("LOGLEVEL_AZURE", "WARN").upper())
# We cannot use EnvHelper here as Application Insights needs to be configured first
# for instrumentation to work correctly
if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

logger = logging.getLogger(__name__)
logger.debug("Starting admin app")


st.set_page_config(
    page_title="Admin",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)


def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Load the common CSS
load_css("pages/common.css")


col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.image(os.path.join("images", "logo.png"))

st.write("# Chat with your data Solution Accelerator")

st.write(
    """
         * If you want to ingest data (pdf, websites, etc.), then use the `Ingest Data` tab
         * If you want to explore how your data was chunked, check the `Explore Data` tab
         * If you want to adapt the underlying prompts, logging settings and others, use the `Configuration` tab
         """
)
