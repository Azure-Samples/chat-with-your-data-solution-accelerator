import pytest
import os
import io
import logging
import atexit
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from config.constants import *

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
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        question_logs = getattr(item, "_question_logs", None)
        if question_logs:
            for i, (question, logs) in enumerate(question_logs.items(), start=1):
                report.sections.append((f"Q{i:02d}: {question}", logs))
        else:
            log = getattr(item, "_captured_log", None)
            if log:
                report.sections.append(("Captured Log", log))

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
