from functools import wraps
import jwt
import streamlit as st
import os
import logging
import sys
from dotenv import load_dotenv

from auth.token_validator import TokenValidator
from batch.utilities.helpers.EnvHelper import EnvHelper
from streamlit.web.server.websocket_headers import _get_websocket_headers

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)

env_helper: EnvHelper = EnvHelper()
token_validator = TokenValidator(env_helper.TENANT_ID, env_helper.CLIENT_ID)

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        headers = _get_websocket_headers()
        if not headers or "Authorization" not in headers:
            return st.error("Forbidden")
        token = headers["Authorization"]
        if not token:
            return st.error("Forbidden")
        
        try:
            token_validator.validate(token)
        except jwt.ExpiredSignatureError:
            st.error("Token expired")
        except jwt.InvalidTokenError:
            st.error("Forbidden")
        except Exception as e:
            errorMessage = str(e)
            logging.exception(f"Exception occured while access token validation | {errorMessage}")
            st.error("An error occured")
        return f(*args, **kwargs)

    return decorated_function

@auth_required
def main():
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

main()