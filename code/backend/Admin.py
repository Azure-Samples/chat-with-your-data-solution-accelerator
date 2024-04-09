import streamlit as st
import os
import logging
import sys
from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor


load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# We cannot use EnvHelper here as Application Insights needs to be configured first
# for instrumentation to work correctly
if os.getenv("APPINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)


st.set_page_config(
    page_title="Admin",
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
