import json
import time
from datetime import datetime
from uuid import uuid4

import requests


class CWYDConversationClient:
    def __init__(
        self, client_id: str, client_secret: str, tenant_id: str, base_url: str
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.base_url = base_url
        self.token = None

    def get_access_token(self):
        """Obtain OAuth2 access token"""
        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": f"api://{self.client_id}/.default",
        }
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Failed to get token: {response.text}")

    def get_conversation_response(self, question: str):
        """Call CWYD /conversation API and return response and latency"""
        if not self.token:
            self.token = self.get_access_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Accept": "*/*",
        }

        payload = {
            "conversation_id": str(uuid4()),
            "messages": [
                {
                    "role": "user",
                    "content": question,
                    "id": str(uuid4()),
                    "date": datetime.utcnow().isoformat() + "Z",
                }
            ],
        }

        start_time = time.time()
        response = requests.post(
            f"{self.base_url}/conversation", headers=headers, json=payload
        )
        latency = time.time() - start_time

        if response.status_code == 200:
            response_lines = response.text.splitlines()
            final_response_line = response_lines[-1]
            return json.loads(final_response_line), latency
        else:
            raise Exception(f"API request failed: {response.text}")
