import streamlit as st
from components.login import isLoggedIn, logout
import os
from backend.batch.utilities.helpers.EnvHelper import EnvHelper

env_helper: EnvHelper = EnvHelper()


def authenticated_menu():
    pages_path = os.path.join(os.path.dirname(__file__), "..", "pages")
    st.sidebar.page_link(os.path.join(pages_path, "home.py"), label="Home")
    st.sidebar.page_link(
        os.path.join(pages_path, "ingest_data.py"), label="Ingest data"
    )
    st.sidebar.page_link(
        os.path.join(pages_path, "explore_data.py"), label="Explore data"
    )
    st.sidebar.page_link(
        os.path.join(pages_path, "delete_data.py"), label="Delete data"
    )
    st.sidebar.page_link(
        os.path.join(pages_path, "configuration.py"), label="Configuration"
    )

    if not env_helper.ADMIN_AUTH_DISABLED:
        st.sidebar.button(
            "Sign Out", key="logout_button", help="Sign Out", on_click=logout
        )

    st.sidebar.button("Sign Out", key="logout_button", help="Sign Out", on_click=logout)


def menu():
    if isLoggedIn():
        authenticated_menu()
        return
