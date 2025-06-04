import json
import os
import uuid

from dotenv import load_dotenv


class BasePage:

    def __init__(self, page):
        self.page = page

    def scroll_into_view(self, locator):
        reference_list = locator
        locator.nth(reference_list.count() - 1).scroll_into_view_if_needed()

    def select_an_element(self, locator, text):
        elements = locator.all()
        for element in elements:
            clientele = element.text_content()
            if clientele == text:
                element.click()
                break

    def is_visible(self, locator):
        locator.is_visible()

    def validate_response_status(self, questions):
        load_dotenv()
        WEB_URL = os.getenv("web_url")

        url = f"{WEB_URL}/api/conversation"

        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())

        payload = {
            "messages": [{"role": "user", "content": questions, "id": user_message_id}],
            "conversation_id": conversation_id,
        }
        # Serialize the payload to JSON
        payload_json = json.dumps(payload)
        headers = {"Content-Type": "application/json", "Accept": "*/*"}
        response = self.page.request.post(url, headers=headers, data=payload_json)
        # Check the response status code
        assert response.status == 200, (
            "response code is " + str(response.status) + " " + str(response.json())
        )

    def wait_for_load(self, wait_time):
        self.page.wait_for_timeout(wait_time)
