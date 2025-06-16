from base.base import BasePage
from playwright.sync_api import expect


class WebUserPage(BasePage):
    WEB_PAGE_TITLE = "//h3[text()='Azure AI']"
    TYPE_QUESTION_TEXT_AREA = "//textarea[contains(@placeholder,'Type a new question')]"
    SEND_BUTTON = "div[role='button'][aria-label='Ask question button']"
    CLEAR_CHAT_ICON = "svg[aria-label='Clear session']"
    USER_CHAT_MESSAGE = "(//div[contains(@class,'chatMessageUserMessage')])[1]"
    STOP_GENERATING_LABEL = "//span[text()='Stop generating']"
    ANSWER_TEXT = "._answerContainer_onnz5_1"
    REFERENCE_LINK_IN_RESPONSE = "(//span[@class='_citationContainer_onnz5_62'])[1]"
    REFERENCE_LINKS_IN_RESPONSE = "//span[@class='_citationContainer_onnz5_62']"
    RESPONSE_REFERENCE_EXPAND_ICON = "//div[@aria-label='References']"
    CLOSE_CITATIONS = "svg[role='button']"
    SHOW_CHAT_HISTORY = "//span//i"
    CHAT_HISTORY_NAME = "div[aria-label='chat history list']"
    CHAT_CLOSE_ICON = "button[title='Hide']"
    CHAT_HISTORY_OPTIONS = "//button[@id='moreButton']"
    CHAT_HISTORY_DELETE = "//button[@role='menuitem']"
    TOGGLE_CITATIONS_LIST = "[data-testid='toggle-citations-list']"
    CITATIONS_CONTAINER = "[data-testid='citations-container']"
    CITATION_BLOCK = "[data-testid='citation-block']"

    def __init__(self, page):
        self.page = page
        self.soft_assert_errors = []

    def enter_a_question(self, text):
        # Type a question in the text area
        self.page.locator(self.TYPE_QUESTION_TEXT_AREA).fill(text)
        self.page.wait_for_timeout(2000)

    def click_send_button(self):
        # Click on send button in question area
        self.page.locator(self.SEND_BUTTON).click()
        self.page.locator(self.STOP_GENERATING_LABEL).wait_for(state="hidden")

    def soft_assert(self, condition, message):
        if not condition:
            self.soft_assert_errors.append(message)

    def assert_all(self):
        if self.soft_assert_errors:
            raise AssertionError(
                "Soft assertion failures:\n" + "\n".join(self.soft_assert_errors)
            )

    def click_clear_chat_icon(self):
        # Click on clear chat icon in question area
        if self.page.locator(self.USER_CHAT_MESSAGE).is_visible():
            self.page.locator(self.CLEAR_CHAT_ICON).click()

    def show_chat_history(self):
        self.page.locator(self.SHOW_CHAT_HISTORY).click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)
        expect(self.page.locator(self.CHAT_HISTORY_NAME)).to_be_visible()

    def close_chat_history(self):
        self.page.locator(self.CHAT_CLOSE_ICON).click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def delete_chat_history(self):
        self.page.locator(self.SHOW_CHAT_HISTORY).click()
        self.page.wait_for_timeout(2000)
        chat_history = self.page.locator("//span[contains(text(),'No chat history.')]")
        if chat_history.is_visible():
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(2000)
            self.page.get_by_label("hide button").click()

        else:
            self.page.locator(self.CHAT_HISTORY_OPTIONS).click()
            self.page.locator(self.CHAT_HISTORY_DELETE).click()
            self.page.get_by_role("button", name="Clear All").click()
            self.page.get_by_label("hide button").click()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(2000)

    def click_reference_link_in_response(self):
        response_blocks = self.page.locator(self.ANSWER_TEXT)
        last_response = response_blocks.nth(response_blocks.count() - 1)
        toggle_button = last_response.locator(self.TOGGLE_CITATIONS_LIST)
        citations_container = last_response.locator(self.CITATIONS_CONTAINER)


        if not citations_container.is_visible():
            toggle_button.click()
            self.page.wait_for_timeout(1000)

        citation = citations_container.locator(self.CITATION_BLOCK).first


        citation.click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

    def close_citation(self):
        self.page.wait_for_timeout(3000)
        close_btn = self.page.locator(self.CLOSE_CITATIONS)
        close_btn.wait_for(state="attached", timeout=5000)
        close_btn.scroll_into_view_if_needed()
        close_btn.click(force=True)
        self.page.wait_for_timeout(5000)

    def has_reference_link(self):
        response_blocks = self.page.locator(self.ANSWER_TEXT)

        count = response_blocks.count()
        if count == 0:
            return False
        last_response = response_blocks.nth(count - 1)
        toggle_button = last_response.locator(self.TOGGLE_CITATIONS_LIST)
        if toggle_button.count() > 0:
            toggle_button.click()


        citations_container = last_response.locator(self.CITATIONS_CONTAINER)
        citation_blocks = citations_container.locator(self.CITATION_BLOCK)
        citation_count = citation_blocks.count()

        return citation_count > 0
