from base.base import BasePage


class AdminPage(BasePage):
    ADMIN_PAGE_TITLE = "//h1[text()='Chat with your data Solution Accelerator']"
    INGEST_DATA_TAB = "//span[text()='Ingest Data']"
    EXPLORE_DATA_TAB = "//span[text()='Explore Data']"
    DELETE_DATA_TAB = "//span[text()='Delete Data']"
    CONFIGURATION_TAB = "//span[text()='Configuration']"
    BROWSE_FILES_BUTTON = "//button[normalize-space()='Browse files']"
    UPLOAD_SUCCESS_MESSAGE = "//div[@data-testid='stAlertContentSuccess']//p"
    REPROCESS_ALL_DOCUMENTS_BUTTON = "//p[contains(text(),'Reprocess all documents')]"
    ADD_URLS_TEXT_AREA = "//textarea[contains(@aria-label,'Add URLs ')]"
    PROCESS_INGEST_WEB_PAGES_BUTTON = "//p[text()='Process and ingest web pages']"
    SELECT_YOUR_FILE_DROP_DOWN = "//div[@data-baseweb='select']"
    DROP_DOWN_OPTION = "//div[@data-testid='stTooltipHoverTarget']/div/div"
    DELETE_CHECK_BOXES = "//label[@data-baseweb='checkbox']/span"
    DELETE_BUTTON = "//p[text()='Delete']"
    UNSUPPORTED_FILE_ERROR_MESSAGE = (
        "//span[@data-testid='stFileUploaderFileErrorMessage']"
    )
    REMOVE_ICON = "//button[@data-testid='stBaseButton-minimal']"
    NO_FILES_TO_DELETE_MESSAGE = "//div[@data-testid='stAlertContentInfo']//p"

    def __init__(self, page):
        self.page = page

    def click_delete_data_tab(self):
        self.page.locator(self.DELETE_DATA_TAB).click()
        self.page.wait_for_timeout(5000)
