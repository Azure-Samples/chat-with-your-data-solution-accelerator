import logging
import os
import streamlit as st
import msal
from dotenv import load_dotenv
from batch.utilities.helpers.EnvHelper import EnvHelper
from components.login import isLoggedIn
import streamlit as st
from streamlit_msal import Msal
load_dotenv()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)


def login():
    Msal.sign_in()
    
def refresh():
    Msal.revalidate()
    
env_helper: EnvHelper = EnvHelper()
scopes= ["User.Read"]

auth_data = Msal.initialize(
        client_id=env_helper.CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{env_helper.TENANT_ID}",
        scopes=scopes,
    )
    

st.session_state.access_data = auth_data

if not isLoggedIn():
    if st.button("Sign in"):
        login()
else:
    pages_path = os.path.join(os.path.dirname(__file__), "pages")
    st.switch_page(os.path.join(pages_path, "home.py"))