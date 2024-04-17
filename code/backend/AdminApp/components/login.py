import traceback
import requests
import streamlit as st
from batch.utilities.helpers.EnvHelper import EnvHelper
import logging
from streamlit_msal import Msal

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
env_helper: EnvHelper = EnvHelper()


def isLoggedIn() -> bool:
    if "access_data" not in st.session_state:
        return False
    if not st.session_state.access_data:
        return False
    if not st.session_state.access_data["accessToken"]:
        return False
    # account = auth_data["account"]
    # name = account["name"]
    # username = account["username"]
    # account_id = account["localAccountId"]
    return True


def isAdmin() -> bool:
    try:
        url = "https://graph.microsoft.com/v1.0/me/memberOf"
        access_token = st.session_state.access_data["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers)

        if response.ok:
            groups = response.json()["value"]
            for group in groups:
                if group.get("id") == env_helper.ADMIN_GROUP_ID:
                    return True

        return False
    except Exception:
        st.error(traceback.format_exc())


def logout():
    st.session_state.access_data = None
    Msal.sign_out()
