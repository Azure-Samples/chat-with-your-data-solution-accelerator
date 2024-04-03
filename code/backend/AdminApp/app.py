import logging
import os
import streamlit as st
import msal
from dotenv import load_dotenv
from batch.utilities.helpers.ConfigHelper import ConfigHelper
from batch.utilities.helpers.EnvHelper import EnvHelper
from components.login import isLoggedIn
load_dotenv()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
env_helper: EnvHelper = EnvHelper()
scopes= ["User.Read"]
app = msal.PublicClientApplication(
    env_helper.CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{env_helper.TENANT_ID}",
    verify=True
)

def get_token_from_cache():
    accounts = app.get_accounts()
    if not accounts:
        return None
    
    result = app.acquire_token_silent(scopes, account=accounts[0])
    if "access_token" in result:
        return result["access_token"]
    else:
        return None

#def login():
#    
#    auth_data = Msal.initialize(
#        client_id=env_helper.CLIENT_ID,
#        authority=f"https://login.microsoftonline.com/{env_helper.TENANT_ID}",
#        scopes=scopes,
#    )
#
#    if st.button("Sign in"):
#        Msal.sign_in() # Show popup to select account
#
#    if st.button("Sign out"):
#        Msal.sign_out() # Clears auth_data
#
#    if st.button("Revalidate"):
#        Msal.revalidate() # Usefull to refresh "accessToken"
    
    #flow = app.initiate_auth_code_flow(
    #    scopes=scopes)
#
    #if "auth_uri" not in flow:
    #    return st.write("Failed with token")
#
    #auth_uri = flow["auth_uri"]
#
    #browser = webdriver.Chrome()
    #browser.get(auth_uri)
#
    #redirect_uri = "localhost"
    #WebDriverWait(browser, 200).until(
    #    EC.url_contains(redirect_uri))
    #
    #redirected_url = browser.current_url
    #url = urllib.parse.urlparse(redirected_url)
    ## parse the query string to get a dictionary of {key: value}
#
    #query_params = dict(urllib.parse.parse_qsl(url.query))
    #
#
    ##code = query_params.get('code')[0]
    #
    #result = app.acquire_token_by_auth_code_flow(flow,query_params, scopes=scopes)
    #
    #browser.quit()
#    return auth_data

# Initialize st.session_state.role to None
if "role" not in st.session_state:
    st.session_state.role = None

# Retrieve the role from Session State to initialize the widget
st.session_state._role = st.session_state.role

def set_role():
    # Callback function to save the role selection to Session State
    st.session_state.role = st.session_state._role

import streamlit as st
from streamlit_msal import Msal
auth_data = Msal.initialize(
        client_id=env_helper.CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{env_helper.TENANT_ID}",
        scopes=scopes,
    )
#with st.sidebar:
#    auth_data = Msal.initialize_ui(
#        client_id=env_helper.CLIENT_ID,
#        authority=f"https://login.microsoftonline.com/{env_helper.TENANT_ID}",
#        scopes=scopes,
#        # Customize (Default values):
#        connecting_label="Connecting",
#        disconnected_label="Disconnected",
#        sign_in_label="Sign in",
#        sign_out_label="Sign out"
#    )
#
#if not auth_data:
#    st.write("Authenticate to access protected content")
#    st.stop()
#
#st.write("Protected content available")


def login():
    Msal.sign_in()
     
def logout():
    Msal.sign_out()
    
def refresh():
    Msal.revalidate()
    

st.session_state.access_data = auth_data

if not isLoggedIn():
    if st.button("Sign in"):
        login()
else:
    pages_path = os.path.join(os.path.dirname(__file__), "pages")
    st.switch_page(os.path.join(pages_path, "home.py"))
    
    #if st.button("Sign out"):
    #    Msal.sign_out() # Clears auth_data
#
    #if st.button("Revalidate"):
    #    Msal.revalidate() # Usefull to refresh "accessToken"
        
    # Getting usefull information
    #access_token = auth_data["accessToken"]
#
    #account = auth_data["account"]
    #name = account["name"]
    #username = account["username"]
    #account_id = account["localAccountId"]
#
#
    ## Display information
    #st.write(f"Hello {name}!")
    #st.write(f"Your username is: {username}")
    #st.write(f"Your account id is: {account_id}")
    #st.write("Your access token is:")
    #st.code(access_token)
#
    #st.write("Auth data:")
    #st.json(auth_data)
    #st.title("Login")
    #if st.button("Login"):
    #    get_token_from_cache()
    #    token = login()
    #
    #    st.write(st.query_params)
    #    if token:
    #        st.write("Logged in successfully!")
    #        st.write(token)
    #    else:
    #        st.write("Failed to login")
        # Perform authentication logic here
        #st.session_state.role = "admin"
        #pages_path = os.path.join(os.path.dirname(__file__), "pages")
        #st.switch_page(os.path.join(pages_path, "home.py"))