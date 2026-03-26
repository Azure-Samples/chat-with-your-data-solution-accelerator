import pytest
import os
import io
import logging
import atexit
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from config.constants import *
from datetime import datetime
from pytest_html import extras
import glob
log_streams = {}

# ---------- FIXTURE: Login and Logout Setup ----------
@pytest.fixture(scope="session")
def login_logout():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        context.set_default_timeout(80000)
        page = context.new_page()

        # Load URL and wait
        page.goto(WEB_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Uncomment if authentication is needed
        # load_dotenv()
        # login_page = LoginPage(page)
        # login_page.authenticate(os.getenv('user_name'), os.getenv('pass_word'))

        yield page
        browser.close()
# Create screenshots directory if it doesn't exist
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Configuration for screenshot behavior
CAPTURE_ALL_SCREENSHOTS = os.getenv('CAPTURE_ALL_SCREENSHOTS', 'false').lower() == 'true'

def clean_screenshot_filename(test_name):
    """Clean test name to create valid filename for screenshots"""
    # Replace invalid characters for Windows filenames
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '[', ']']
    clean_name = test_name
    for char in invalid_chars:
        clean_name = clean_name.replace(char, "_")
    # Replace spaces with underscores
    clean_name = clean_name.replace(" ", "_")
    # Remove duplicate underscores
    clean_name = "_".join(filter(None, clean_name.split("_")))
    # Truncate if too long (Windows has 255 char limit)
    if len(clean_name) > 100:
        clean_name = clean_name[:100]
    return clean_name
# ---------- HTML Report Title ----------
@pytest.hookimpl(tryfirst=True)
def pytest_html_report_title(report):
    report.title = "Test_Automation_Chat_with_your_Data"

# ---------- Logging Setup per Test ----------
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    logger = logging.getLogger()
    logger.addHandler(handler)
    log_streams[item.nodeid] = (handler, stream)

# ---------- Attach Logs to HTML Report ----------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Generate test report with logs, subtest details, and screenshots for failures"""
    outcome = yield
    report = outcome.get_result()

    # Screenshot logic for failures
    if report.when == "call" and report.failed:
        # Take screenshot for FAILED tests
        if "login_logout" in item.fixturenames:
            page = item.funcargs.get("login_logout")
            if page:
                try:
                    # Generate meaningful screenshot filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_test_name = clean_screenshot_filename(item.name)
                    screenshot_name = f"FAILED_{clean_test_name}_{timestamp}.png"
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_name)

                    # Ensure the path is valid before taking screenshot
                    if not os.path.exists(SCREENSHOTS_DIR):
                        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

                    # Take screenshot with error handling
                    page.screenshot(path=screenshot_path, full_page=True)

                    # Verify screenshot was created successfully
                    if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                        # Add screenshot to HTML report
                        if not hasattr(report, 'extra'):
                            report.extra = []

                        # Use relative path for HTML report
                        relative_screenshot_path = f"../screenshots/{screenshot_name}"

                        # Add both image and link to report
                        report.extra.append(extras.image(relative_screenshot_path, name="Failure Screenshot"))
                        report.extra.append(extras.url(relative_screenshot_path, name="Open Screenshot"))

                        logging.info("Screenshot captured for FAILED test: %s", screenshot_path)
                    else:
                        logging.error("Screenshot file was not created or is empty: %s", screenshot_path)
                except Exception as exc:
                    logging.error("Failed to capture screenshot for failed test: %s", str(exc))
            else:
                logging.warning("Page fixture not available for screenshot in failed test: %s", item.name)
        else:
            logging.warning("login_logout fixture not available for screenshot in failed test: %s", item.name)

    # Optional: Take screenshot for all test completion (both pass and fail) if requested
    elif report.when == "call" and CAPTURE_ALL_SCREENSHOTS:
        # Take screenshot for ALL tests (success and failure) for debugging
        if "login_logout" in item.fixturenames:
            page = item.funcargs.get("login_logout")
            if page:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    status = "PASSED" if report.passed else "FAILED"
                    clean_test_name = clean_screenshot_filename(item.name)
                    screenshot_name = f"{status}_{clean_test_name}_{timestamp}.png"
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_name)

                    # Ensure the path is valid before taking screenshot
                    if not os.path.exists(SCREENSHOTS_DIR):
                        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

                    page.screenshot(path=screenshot_path, full_page=True)

                    # Verify screenshot was created successfully
                    if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                        # Add screenshot to report for all tests when enabled
                        if not hasattr(report, 'extra'):
                            report.extra = []

                        relative_screenshot_path = f"../screenshots/{screenshot_name}"
                        report.extra.append(extras.image(relative_screenshot_path, name=f"{status} Screenshot"))
                        report.extra.append(extras.url(relative_screenshot_path, name="Open Screenshot"))

                        logging.info("Screenshot captured for %s test: %s", status, screenshot_path)
                    else:
                        logging.error("Screenshot file was not created or is empty: %s", screenshot_path)
                except Exception as exc:
                    logging.error("Failed to capture screenshot: %s", str(exc))

    # Check for any debug screenshots that might have been created and attach them to the report
    if report.when == "call" and report.failed:
        # Look for debug screenshots that match the test
        debug_screenshot_patterns = [
            f"debug_*.png",
            f"debug_{item.name.lower()}.png",
            f"debug_*_{item.name.lower()}.png"
        ]

        for pattern in debug_screenshot_patterns:
            debug_screenshots = glob.glob(os.path.join(SCREENSHOTS_DIR, pattern))
            for debug_screenshot_path in debug_screenshots:
                if os.path.exists(debug_screenshot_path):
                    # Check if this screenshot was created recently (within the last minute)
                    screenshot_time = os.path.getmtime(debug_screenshot_path)
                    current_time = datetime.now().timestamp()

                    if current_time - screenshot_time < 60:  # Within the last minute
                        if not hasattr(report, 'extra'):
                            report.extra = []

                        screenshot_filename = os.path.basename(debug_screenshot_path)
                        relative_debug_path = f"../screenshots/{screenshot_filename}"

                        # Add debug screenshot to report
                        report.extra.append(extras.image(relative_debug_path, name=f"Debug Screenshot: {screenshot_filename}"))
                        report.extra.append(extras.url(relative_debug_path, name=f"Open {screenshot_filename}"))

                        logging.info("Debug screenshot attached to report: %s", debug_screenshot_path)

    handler, stream = log_streams.get(item.nodeid, (None, None))

    if handler and stream:
        # Make sure logs are flushed
        handler.flush()
        log_output = stream.getvalue()

        # Only remove the handler, don't close the stream yet
        logger = logging.getLogger()
        logger.removeHandler(handler)

        # Check if there are subtests
        subtests_html = ""
        if hasattr(item, 'user_properties'):
            item_subtests = [
                prop[1] for prop in item.user_properties if prop[0] == "subtest"
            ]
            if item_subtests:
                subtests_html = (
                    "<div style='margin-top: 10px;'>"
                    "<strong>Step-by-Step Details:</strong>"
                    "<ul style='list-style: none; padding-left: 0;'>"
                )
                for idx, subtest in enumerate(item_subtests, 1):
                    status = "✅ PASSED" if subtest.get('passed') else "❌ FAILED"
                    status_color = "green" if subtest.get('passed') else "red"
                    subtests_html += (
                        f"<li style='margin: 10px 0; padding: 10px; "
                        f"border-left: 3px solid {status_color}; "
                        f"background-color: #f9f9f9;'>"
                    )
                    subtests_html += (
                        f"<div style='font-weight: bold; color: {status_color};'>"
                        f"{status} - {subtest.get('msg', f'Step {idx}')}</div>"
                    )
                    if subtest.get('logs'):
                        subtests_html += (
                            f"<pre style='margin: 5px 0; padding: 5px; "
                            f"background-color: #fff; border: 1px solid #ddd; "
                            f"font-size: 11px;'>{subtest.get('logs').strip()}</pre>"
                        )
                    subtests_html += "</li>"
                subtests_html += "</ul></div>"

        # Combine main log output with subtests
        if subtests_html:
            report.description = f"<pre>{log_output.strip()}</pre>{subtests_html}"
        else:
            report.description = f"<pre>{log_output.strip()}</pre>"

        # Clean up references
        log_streams.pop(item.nodeid, None)
    else:
        report.description = ""


log_streams = {}


# ---------- Optional: Clean Up Node IDs for Parametrized Prompts ----------
def pytest_collection_modifyitems(items):
    for item in items:
        if hasattr(item, 'callspec') and "prompt" in item.callspec.params:
            item._nodeid = item.callspec.params["prompt"]

# ---------- Rename Duration Column in HTML Report ----------
def rename_duration_column():
    report_path = os.path.abspath("report.html")
    if not os.path.exists(report_path):
        print("Report file not found, skipping column rename.")
        return

    with open(report_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    headers = soup.select('table#results-table thead th')
    for th in headers:
        if th.text.strip() == 'Duration':
            th.string = 'Execution Time'
            break
    else:
        print("'Duration' column not found in report.")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

atexit.register(rename_duration_column)
