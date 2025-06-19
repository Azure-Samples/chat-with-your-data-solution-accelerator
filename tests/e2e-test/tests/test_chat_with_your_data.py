import logging
import time
import pytest
import io

from config.constants import *
from pages.adminPage import AdminPage
from pages.webUserPage import WebUserPage

logger = logging.getLogger(__name__)

# === Step Functions ===

def validate_admin_page_loaded(page, admin_page, home_page):
    page.goto(ADMIN_URL)
    actual_title = page.locator(admin_page.ADMIN_PAGE_TITLE).text_content()
    assert actual_title == "Chat with your data Solution Accelerator", "Admin page title mismatch"

def validate_files_are_uploaded(page, admin_page, home_page):
    admin_page.click_delete_data_tab()
    checkbox_count = page.locator(admin_page.DELETE_CHECK_BOXES).count()
    assert checkbox_count >= 1, "No files available to delete"

def goto_web_page(page, admin_page, home_page):
    page.goto(WEB_URL)

def delete_chat_history(page, admin_page, home_page):
    home_page.delete_chat_history()

# === Golden Path Step Definitions ===

golden_path_functions = [
    validate_admin_page_loaded,
    validate_files_are_uploaded,
    goto_web_page,
    delete_chat_history,
]

step_descriptions = [
    "Validate Admin page is loaded",
    "Validate files are uploaded",
    "Validate Web page is loaded",
    "Delete chat history"
]

golden_path_steps = list(zip(step_descriptions, golden_path_functions))

# === Golden Path Test Execution ===

@pytest.mark.parametrize("step_desc, action", golden_path_steps, ids=[desc for desc, _ in golden_path_steps])
def test_golden_path_steps(login_logout, step_desc, action, request):
    request.node._nodeid = step_desc
    page = login_logout
    admin_page = AdminPage(page)
    home_page = WebUserPage(page)

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    logger.info(f"🟢 START: {step_desc}")
    start = time.time()

    try:
        result = action(page, admin_page, home_page)
        if isinstance(result, tuple):
            for func in result:
                if callable(func):
                    func()
    except AssertionError as e:
        logger.error(f"❌ FAILED: {step_desc} - {str(e)}")
        raise
    finally:
        duration = time.time() - start
        logger.info(f"✅ END: {step_desc} | Execution Time: {duration:.2f}s")
        logger.removeHandler(handler)
        setattr(request.node, "_captured_log", log_capture.getvalue())


# === Each Question as a Separate Test Case ===

@pytest.mark.parametrize("question", questions, ids=[f"Validate response for prompt : {q}" for q in questions])
def test_gp_question(login_logout, question, request):
    page = login_logout
    home_page = WebUserPage(page)
    request.node._nodeid = f"Validate response for prompt : {question}"

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    success = False
    start_time = time.time()

    try:
        for attempt in range(1, 3):
            logger.info(f"[GP] [{question}] Attempt {attempt} - START")

            try:
                home_page.wait_for_load(4000)
                home_page.enter_a_question(question)
                home_page.click_send_button()
                home_page.validate_response_status(question)

                response_text = page.locator(home_page.ANSWER_TEXT)
                response_count = response_text.count()

                if response_count == 0:
                    logger.warning(f"[GP] [{question}] No response returned.")
                    continue

                if home_page.has_reference_link():
                    logger.info(f"[GP] [{question}] Reference link found. Opening citation.")
                    home_page.click_reference_link_in_response()
                    logger.info(f"[GP] [{question}] Closing citation.")
                    home_page.close_citation()

                response_content = response_text.nth(response_count - 1).text_content().strip()

                if response_content == invalid_response:
                    logger.warning(f"[GP] [{question}] Invalid response: {response_content}")
                    continue

                logger.info(f"[GP] [{question}] Valid response received.")
                success = True
                break

            except Exception as e:
                logger.error(f"[GP] [{question}] Exception: {str(e)}")

        if not success:
            pytest.fail(f"[GP] [{question}] Failed after 2 attempts.")

    finally:
        duration = time.time() - start_time
        logger.info(f"[GP] [{question}] Execution Time: {duration:.2f}s")
        logger.removeHandler(handler)
        setattr(request.node, "_captured_log", log_capture.getvalue())


# === Chat History Test ===

def test_validate_chat_history(login_logout, request):
    request.node._nodeid = "Validate chat history shown and closed"
    page = login_logout
    home_page = WebUserPage(page)

    logger.info("[FINAL] Showing chat history after all questions executed.")
    home_page.show_chat_history()

    logger.info("[FINAL] Closing chat history.")
    home_page.close_chat_history()
