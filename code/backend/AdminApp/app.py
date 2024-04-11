import logging
import os
import streamlit as st
from dotenv import load_dotenv
from batch.utilities.helpers.EnvHelper import EnvHelper
from components.login import isAdmin, isLoggedIn, logout
import streamlit as st
from streamlit_msal import Msal
load_dotenv()

st.set_page_config(
        page_title="Sign In",
        page_icon=os.path.join("images", "favicon.ico"),
        layout="wide",
        menu_items=None,
    )

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
st.write("# Solution Accelerator Admin Panel")
if not isLoggedIn():
    if st.button("Sign In"):
        login()
else:
    if isAdmin():
        pages_path = os.path.join(os.path.dirname(__file__), "pages")
        st.switch_page(os.path.join(pages_path, "home.py"))
    else:
        st.write("Access denied")
        if st.button("Sign Out"):
            logout()