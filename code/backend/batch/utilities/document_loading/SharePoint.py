from urllib.parse import urlparse
from typing import List
from bs4 import BeautifulSoup
import requests
from .DocumentLoadingBase import DocumentLoadingBase
from ..common.SourceDocument import SourceDocument
from batch.utilities.helpers.EnvHelper import EnvHelper

env_helper: EnvHelper = EnvHelper()


class SitePageHeader:
    def __init__(self, id, title, name, source_url):
        self.id = id
        self.title = title
        self.name = name
        self.source_url = source_url


class SitePage:
    def __init__(self, header):
        self.header = header
        self.text_content = None
        self.tags = None

    def set_text_content(self, text_content):
        self.text_content = text_content

    def set_tags(self, tags):
        self.tags = tags


class SharePointLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()

    def get_site_id(self, site_url, access_token):
        if not site_url:
            raise ValueError("'site_url' can not be empty")

        parsed_url = urlparse(site_url)
        host_name = parsed_url.hostname
        relative_path = parsed_url.path

        endpoint = (
            f"https://graph.microsoft.com/v1.0/sites/{host_name}:/{relative_path}"
        )
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            site_data = response.json()
            site_id = site_data["id"]
            return site_id
        else:
            raise ConnectionError(
                "Failed to retrieve site information from Microsoft Graph API"
            )

    def get_page_headers(self, site_id, access_token):
        if not site_id:
            raise ValueError("'site_id' can not be empty")

        endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
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
                source_url = page["webUrl"]
                pages.append(SitePageHeader(id, title, name, source_url))

            return pages
        else:
            raise ConnectionError(
                "Failed to retrieve pages information from Microsoft Graph API"
            )

    def extract_text(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(" ", strip=True)

    def get_site_page(self, site_id, page_header, access_token):
        if not page_header:
            raise ValueError("'page_header' can not be empty")

        endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages/{page_header.id}/microsoft.graph.sitepage/webparts"
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
                    text_content = self.extract_text(html_content=inner_html)
                    site_page.set_text_content(text_content)

                elif "Tags" in inner_html:
                    del page_data[index]
                    text_content = self.extract_text(html_content=inner_html)
                    site_page.set_tags(tags=text_content)

            return site_page

        else:
            raise ConnectionError(
                "Failed to retrieve pages information from Microsoft Graph API"
            )

    def load(self, document_url: str) -> List[SourceDocument]:

        access_token = env_helper.AZURE_MS_GRAPH_TOKEN_PROVIDER()
        site_id = self.get_site_id(document_url, access_token)
        site_page_headers = self.get_page_headers(site_id, access_token)

        pages = []
        for site_page in [
            self.get_site_page(site_id, page_header, access_token)
            for page_header in site_page_headers
        ]:
            pages.append(
                {
                    "title": site_page.header.title,
                    "content": site_page.text_content,
                    "keys": site_page.tags,
                }
            )

        return SourceDocument(content={"pages": pages}, source=document_url)
