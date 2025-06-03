import logging

from config.constants import *
from pages.adminPage import AdminPage
from pages.webUserPage import WebUserPage

logger = logging.getLogger(__name__)


def test_golden_path_web_page_demo_script(login_logout):
    """Validate Golden path test case for Chat with your Data"""
    page = login_logout
    page.goto(ADMIN_URL)
    logger.info("Step 1: Validate Admin page is loaded.")
    admin_page = AdminPage(page)
    assert (
        admin_page_title == page.locator(admin_page.ADMIN_PAGE_TITLE).text_content()
    ), "page title not found"
    logger.info("Step 2: Validate Files are uploaded or not")
    admin_page.click_delete_data_tab()
    assert (
        page.locator(admin_page.DELETE_CHECK_BOXES).count() >= 1
    ), "Files are not uploaded."
    logger.info("Step 3: Validate Web page is loaded.")
    page.goto(WEB_URL)
    home_page = WebUserPage(page)
    logger.info("Step 5: Validate Chat history has been deleted.")
    home_page.delete_chat_history()

    failed_questions = []
    logger.info("Step 6: Validate Golden Path prompts response")

    def ask_question_and_check(question, attempt):
        home_page.wait_for_load(4000)
        home_page.enter_a_question(question)
        home_page.click_send_button()
        home_page.validate_response_status(question)

        response_text = page.locator(home_page.ANSWER_TEXT)
        response_count = response_text.count()

        if response_count == 0:
            return False  # no response found

        response_text_content = response_text.nth(response_count - 1).text_content()

        if response_text_content == invalid_response:
            print(f"[Attempt {attempt}] Invalid response for prompt: {question}")
            return False
        return True

    # First run through all questions
    for question in questions:
        if not ask_question_and_check(question, attempt=1):
            failed_questions.append(question)

    # Retry failed questions once more
    if failed_questions:
        logger.info("Step 7: Retry failed question one more time.")
        for question in failed_questions:
            if not ask_question_and_check(question, attempt=2):
                home_page.soft_assert(
                    False,
                    f"Failed after retry- Invalid response for prompt: {question}",
                )

    logger.info("Step 8: Validate chat history.")
    home_page.show_chat_history()
    logger.info("Step 9: Validate chat history closed.")
    home_page.close_chat_history()
    home_page.assert_all()
