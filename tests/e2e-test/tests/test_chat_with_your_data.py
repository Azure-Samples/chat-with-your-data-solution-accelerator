import logging
import time
import pytest
import io

from config.constants import *
from pages.adminPage import AdminPage
from pages.webUserPage import WebUserPage

logger = logging.getLogger(__name__)

# === Step 1: Golden Path Step Functions ===

def validate_admin_page_loaded(page, admin_page, home_page):
    page.goto(ADMIN_URL)
    actual_title = page.locator(admin_page.ADMIN_PAGE_TITLE).text_content()
    assert actual_title == "Chat with your data Solution Accelerator", "Admin page title mismatch"

def validate_files_are_uploaded(page, admin_page, home_page):
    admin_page.click_delete_data_tab()
    checkbox_count = page.locator(admin_page.DELETE_CHECK_BOXES).count()
    assert checkbox_count >= 1, "No files available to delete"

def execute_golden_path_prompts(page, home_page, step_number=""):
    failed_questions = []

    def ask_question_and_check(question, attempt):
        start_time = time.time()
        logger.info(f"[{step_number}] [{question}] Attempt {attempt} - START")

        home_page.wait_for_load(4000)
        home_page.enter_a_question(question)
        home_page.click_send_button()
        home_page.validate_response_status(question)

        response_text = page.locator(home_page.ANSWER_TEXT)
        response_count = response_text.count()

        if home_page.has_reference_link():
            logger.info(f"[{step_number}] [{question}] Reference link found. Opening citation.")
            home_page.click_reference_link_in_response()
            logger.info(f"[{step_number}] [{question}] Closing citation.")
            home_page.close_citation()

        if response_count == 0:
            logger.warning(f"[{step_number}] [{question}] No response returned.")
            logger.info(f"[{step_number}] [{question}] Execution Time: {time.time() - start_time:.2f}s")
            return False

        response_text_content = response_text.nth(response_count - 1).text_content()
        if response_text_content == invalid_response:
            logger.warning(f"[{step_number}] [{question}] Invalid response: {response_text_content}")
            logger.info(f"[{step_number}] [{question}] Execution Time: {time.time() - start_time:.2f}s")
            return False

        logger.info(f"[{step_number}] [{question}] Valid response received.")
        logger.info(f"[{step_number}] [{question}] Execution Time: {time.time() - start_time:.2f}s")
        return True

    for question in questions:
        if not ask_question_and_check(question, attempt=1):
            failed_questions.append(question)

    if failed_questions:
        logger.info(f"[{step_number}] Retrying failed questions.")
        for question in failed_questions:
            if not ask_question_and_check(question, attempt=2):
                home_page.soft_assert(False, f"Failed after retry: {question}")

# === Step 2: Functions and Descriptions ===

golden_path_functions = [
    validate_admin_page_loaded,
    validate_files_are_uploaded,
    lambda page, admin_page, home_page: page.goto(WEB_URL),
    lambda page, admin_page, home_page: home_page.delete_chat_history(),
    lambda page, admin_page, home_page: execute_golden_path_prompts(page, home_page, step_number="05"),
    lambda page, admin_page, home_page: home_page.show_chat_history(),
    lambda page, admin_page, home_page: (home_page.close_chat_history(), home_page.assert_all()),
]

step_descriptions = [
    "Validate Admin page is loaded",
    "Validate files are uploaded",
    "Validate Web page is loaded",
    "Delete chat history",
    "Validate Golden Path prompts response",
    "Validate chat history shown",
    "Validate chat history closed",
]

golden_path_steps = [
    (f"{i+1:02d}. {desc}", func) for i, (desc, func) in enumerate(zip(step_descriptions, golden_path_functions))
]

step_ids = [desc for desc, _ in golden_path_steps]

# === Step 3: Pytest Test Function ===

@pytest.mark.parametrize("step_desc, action", golden_path_steps, ids=step_ids)
def test_golden_path_steps(login_logout, step_desc, action, request):
    request.node._nodeid = step_desc

    page = login_logout
    admin_page = AdminPage(page)
    home_page = WebUserPage(page)

    step_number = step_desc.split('.')[0]

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    logger.info(f"[{step_number}] 🟢 START: {step_desc}")
    start = time.time()

    try:
        action_result = action(page, admin_page, home_page)
        if isinstance(action_result, tuple):
            for func in action_result:
                if callable(func):
                    func()
    except AssertionError as e:
        logger.error(f"[{step_number}] ❌ FAILED: {step_desc} - {str(e)}")
        raise
    finally:
        duration = time.time() - start
        logger.info(f"[{step_number}] ✅ END: {step_desc} | Execution Time: {duration:.2f}s")
        logger.removeHandler(handler)

        log_output = log_capture.getvalue()
        setattr(request.node, "_captured_log", log_output)
