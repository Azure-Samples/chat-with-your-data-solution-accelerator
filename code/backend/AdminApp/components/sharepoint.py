import streamlit as st
from bs4 import BeautifulSoup
import requests
from batch.utilities.helpers.EnvHelper import EnvHelper

env_helper: EnvHelper = EnvHelper()


class SitePageHeader:
    def __init__(self, id, title, name):
        self.id = id
        self.title = title
        self.name = name


class SitePage:
    def __init__(self, header):
        self.header = header
        self.text_content = None
        self.tags = None

    def set_text_content(self, text_content):
        self.text_content = text_content

    def set_tags(self, tags):
        self.tags = tags


def get_site_id(site_hostname):
    if not site_hostname:
        raise ValueError("'site_hostname' can not be empty")

    endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}"
    access_token = st.session_state.access_data["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        site_data = response.json()
        site_id = site_data["id"]
        return site_id
    else:
        st.error("Failed to retrieve site information from Microsoft Graph API")


def get_page_headers(site_id):
    if not site_id:
        raise ValueError("'site_id' can not be empty")

    endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
    access_token = st.session_state.access_data["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        pages = []
        pages_data = response.json()["value"]
        for page in pages_data:
            if (
                "@odata.type" not in page
                or page["@odata.type"] != "#microsoft.graph.sitePage"
            ):
                continue

            id = page["id"]
            title = page["title"]
            name = page["name"]

            pages.append(SitePageHeader(id, title, name))

        return pages
    else:
        st.error("Failed to retrieve pages information from Microsoft Graph API")


def extract_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(" ", strip=True)


def get_site_page(site_id, page_header):
    if not page_header:
        raise ValueError("'page_header' can not be empty")

    endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages/{page_header.id}/microsoft.graph.sitepage/webparts"
    access_token = st.session_state.access_data["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        page_data = response.json()["value"]
        site_page = SitePage(header=page_header)
        for index, item in reversed(list(enumerate(page_data))):
            if (
                "@odata.type" not in item
                or item["@odata.type"] != "#microsoft.graph.textWebPart"
                or "innerHtml" not in item
            ):
                continue

            inner_html = item["innerHtml"]
            if "Project Overview" in inner_html:
                del page_data[index]
                text_content = extract_text(html_content=inner_html)
                site_page.set_text_content(text_content)

            elif "Tags" in inner_html:
                del page_data[index]
                text_content = extract_text(html_content=inner_html)
                site_page.set_tags(tags=text_content)

        return site_page

    else:
        st.error("Failed to retrieve pages information from Microsoft Graph API")


def filter_by_name(items, skip_names):
    return [item for item in items if item.name not in skip_names]


def scrap_sharepoint_data():
    pages_to_skip = env_helper.SHAREPOINT_FILES_TO_SKIP
    site_hostname = env_helper.SHAREPOINT_SITE_HOSTNAME
    site_id = get_site_id(site_hostname)
    site_page_headers = filter_by_name(get_page_headers(site_id), pages_to_skip)

    pages_list = []
    for site_page in [
        get_site_page(site_id, page_header) for page_header in site_page_headers
    ]:
        page_dict = {
            "title": site_page.header.title,
            "content": site_page.text_content,
            "keys": site_page.tags,
        }
        pages_list.append(page_dict)
    json_data = {"pages": pages_list}

    return json_data
