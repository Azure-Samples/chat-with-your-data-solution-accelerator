import streamlit as st
from batch.utilities.helpers.EnvHelper import EnvHelper
import logging
from streamlit_msal import Msal

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
env_helper: EnvHelper = EnvHelper()

def isLoggedIn()->bool:
    if "access_data" not in st.session_state:
        return False
    if not st.session_state.access_data:
        return False
    if not st.session_state.access_data["accessToken"]:
        return False
    accessToken = st.session_state.access_data["accessToken"]
    #account = auth_data["account"]
    #name = account["name"]
    #username = account["username"]
    #account_id = account["localAccountId"]
    return True
     
def logout():
    st.session_state.access_data = None
    Msal.sign_out()