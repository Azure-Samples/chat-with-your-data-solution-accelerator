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

    # New locators for file upload test based on provided HTML
    FILE_INPUT = "input[type='file']"
    BROWSE_FILES_BUTTON_SPECIFIC = "//button[@data-testid='stBaseButton-secondary' and contains(@class, 'st-emotion-cache') and contains(text(), 'Browse files')]"
    DROPDOWN_ARROW = "svg[data-baseweb='icon'][title='open']"
    DROPDOWN_OPTIONS = "li[role='option']"
    UPLOADED_FILE_OPTION = "//li[contains(@class, 'st-emotion-cache') and contains(., '/documents/architecture_pg.png')]"
    FILE_DROPDOWN_CONTAINER = "div[data-baseweb='select']"

    # New locators for file deletion test based on provided HTML
    SPECIFIC_FILE_CHECKBOX = "//div[@class='stElementContainer element-container st-key--documents-architecture_pg-png st-emotion-cache-zh2fnc e196pkbe0']//input[@type='checkbox']"
    ARCHITECTURE_FILE_CHECKBOX = "//input[@aria-label='/documents/architecture_pg.png' and @type='checkbox']"
    DELETE_FORM_BUTTON = "//button[@data-testid='stBaseButton-secondaryFormSubmit' and contains(., 'Delete')]"
    FILE_LABELS_IN_DELETE = "//div[@data-testid='stMarkdownContainer']//p[contains(text(), '/documents/')]"

    # Locators for invalid file upload testing
    FILE_ERROR_MESSAGE = "//span[@data-testid='stFileUploaderFileErrorMessage']"
    FILE_UPLOADER_FILE = "//div[@data-testid='stFileUploaderFile']"
    FILE_UPLOADER_FILE_NAME = "//div[@data-testid='stFileUploaderFileName']"
    FILE_UPLOADER_DELETE_BTN = "//div[@data-testid='stFileUploaderDeleteBtn']//button"
    INVALID_FILE_ERROR_TEXT = "audio/x-m4a files are not allowed."

    def __init__(self, page):
        self.page = page

    def click_delete_data_tab(self):
        self.page.locator(self.DELETE_DATA_TAB).click()
        self.page.wait_for_timeout(5000)

    def assert_admin_page_title(self, admin_page):
        actual_title = self.page.locator(admin_page.ADMIN_PAGE_TITLE).text_content()
        expected_title = admin_page.ADMIN_PAGE_TITLE
        assert expected_title == actual_title, f"Expected title: {expected_title}, Found: {actual_title}"

    def click_ingest_data_tab(self):
        """Click on the Ingest Data tab"""
        self.page.locator(self.INGEST_DATA_TAB).click()
        self.page.wait_for_timeout(2000)

    def upload_file(self, file_path):
        """Upload a file using the Browse files button"""
        import logging
        import os

        logger = logging.getLogger(__name__)

        # Start listening for file chooser before clicking the button
        logger.info("Setting up file chooser listener...")
        with self.page.expect_file_chooser() as fc_info:
            logger.info("Clicking Browse Files button...")
            # Try the specific locator first, fallback to the original if needed
            browse_button = self.page.locator(self.BROWSE_FILES_BUTTON_SPECIFIC)
            if not browse_button.is_visible():
                browse_button = self.page.locator(self.BROWSE_FILES_BUTTON)

            browse_button.click()
            logger.info("✓ Browse Files button clicked")

            self.page.wait_for_timeout(5000)

        # Get the file chooser and set the file
        file_chooser = fc_info.value

        # Verify file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Test file not found at: {file_path}")

        logger.info(f"Uploading file: {file_path}")
        file_chooser.set_files(file_path)
        logger.info("✓ File uploaded successfully")

        self.page.wait_for_timeout(2000)

    def click_explore_data_tab(self):
        """Click on the Explore Data tab"""
        self.page.locator(self.EXPLORE_DATA_TAB).click()
        # Wait longer for the Explore Data tab to fully load
        self.page.wait_for_timeout(5000)
        # Wait for network activity to settle
        self.page.wait_for_load_state("networkidle")

    def open_file_dropdown(self):
        """Open the file selection dropdown"""
        import logging
        logger = logging.getLogger(__name__)

        # Wait a bit more for the page to be ready
        logger.info("Waiting for dropdown container to be ready...")
        self.page.wait_for_timeout(3000)

        # Try multiple locator strategies for the dropdown
        dropdown_locators = [
            self.FILE_DROPDOWN_CONTAINER,  # div[data-baseweb='select']
            self.SELECT_YOUR_FILE_DROP_DOWN,  # //div[@data-baseweb='select']
            "select",  # generic select element
            "[data-testid*='select']",  # any element with select in testid
            "div[class*='select']",  # any div with select in class
            "div[role='combobox']",  # dropdown role
        ]

        dropdown_clicked = False
        for i, locator in enumerate(dropdown_locators):
            try:
                logger.info("Trying locator %d: %s", i + 1, locator)
                element = self.page.locator(locator).first
                if element.is_visible(timeout=5000):
                    logger.info("✓ Found visible dropdown with locator %d, clicking...", i + 1)
                    element.click(timeout=10000)
                    dropdown_clicked = True
                    break
                else:
                    logger.info("Locator %d not visible", i + 1)
            except Exception as e:
                logger.warning("Locator %d failed: %s", i + 1, str(e))
                continue

        if not dropdown_clicked:
            # Try to find any clickable dropdown element
            logger.info("All specific locators failed, trying generic approach...")
            all_selects = self.page.locator("div").all()
            for element in all_selects[:10]:  # Check first 10 elements
                try:
                    if "select" in element.get_attribute("data-baseweb", timeout=1000):
                        logger.info("Found element with data-baseweb containing 'select'")
                        element.click()
                        dropdown_clicked = True
                        break
                except:
                    continue

        if not dropdown_clicked:
            raise Exception("Could not find or click dropdown element")

        # Wait for dropdown to open
        logger.info("Waiting for dropdown to open...")
        self.page.wait_for_timeout(2000)

    def is_file_visible_in_dropdown(self, filename):
        """Check if a specific file is visible in the dropdown options"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Wait for dropdown to load
            self.page.wait_for_selector(self.DROPDOWN_OPTIONS, timeout=10000)
            logger.info("Dropdown options loaded, searching for file: %s", filename)

            # Get all dropdown options and check their text content
            options = self.page.locator(self.DROPDOWN_OPTIONS).all()
            logger.info("Found %d dropdown options", len(options))

            for i, option in enumerate(options):
                option_text = option.text_content()
                logger.info("Option %d: %s", i, option_text)
                if filename in option_text:
                    logger.info("✓ Found matching file: %s", option_text)
                    return True

            logger.warning("File not found in dropdown options")
            return False

        except Exception as e:
            logger.error("Error checking dropdown visibility: %s", str(e))
            return False

    def select_file_from_dropdown(self, filename):
        """Find and click on a specific file in the dropdown options"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Wait for dropdown to load
            self.page.wait_for_selector(self.DROPDOWN_OPTIONS, timeout=10000)
            logger.info("Dropdown options loaded, searching for file to select: %s", filename)

            # Get all dropdown options and check their text content
            options = self.page.locator(self.DROPDOWN_OPTIONS).all()
            logger.info("Found %d dropdown options", len(options))

            for i, option in enumerate(options):
                option_text = option.text_content()
                logger.info("Option %d: %s", i, option_text)
                if filename in option_text:
                    logger.info("✓ Found matching file, clicking on: %s", option_text)
                    option.click()
                    self.page.wait_for_timeout(2000)  # Wait for selection to process
                    logger.info("✓ File selected successfully")
                    return True

            logger.warning("File not found in dropdown options for selection")
            return False

        except Exception as e:
            logger.error("Error selecting file from dropdown: %s", str(e))
            return False

    def is_file_visible_in_dropdown_with_scroll(self, filename):
        """
        Check if a file is visible in dropdown by scrolling through all options.
        Handles virtualized dropdowns that require scrolling to see all items.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Checking for file '%s' in dropdown with scrolling...", filename)

            # First try to find the file in currently visible options
            if self.is_file_visible_in_dropdown(filename):
                return True

            # Try different dropdown container selectors
            container_selectors = [
                "div[role='listbox']",
                "div[data-baseweb='menu']",
                "ul[role='listbox']",
                ".st-emotion-cache-1gulkj5",  # Streamlit specific class
                "div[data-testid='stSelectbox'] div",
                "[data-baseweb='select'] div[style*='overflow']"
            ]

            dropdown_container = None
            for selector in container_selectors:
                container = self.page.locator(selector).first
                if container.is_visible():
                    dropdown_container = container
                    logger.info("Found dropdown container with selector: %s", selector)
                    break

            if not dropdown_container:
                logger.warning("Could not find dropdown container for scrolling")
                return False

            # Get the dropdown container bounding box for scrolling
            box = dropdown_container.bounding_box()
            if not box:
                logger.warning("Could not get dropdown container bounding box")
                return False

            # Scroll through the dropdown by using mouse wheel
            scroll_attempts = 0
            max_scrolls = 10  # Reduce attempts but make them more effective
            scroll_distance = 100  # Pixels to scroll each time

            last_visible_options = []

            while scroll_attempts < max_scrolls:
                # Check current visible options
                current_visible_options = []
                options = self.page.locator("li[role='option'], div[role='option']").all()

                for option in options:
                    if option.is_visible():
                        text = option.text_content() or ""
                        current_visible_options.append(text.strip())

                logger.info("Scroll attempt %d: Found %d visible options", scroll_attempts + 1, len(current_visible_options))

                # Check if our target file is now visible
                for option_text in current_visible_options:
                    if filename in option_text or option_text.endswith(filename):
                        logger.info("✓ Found file '%s' in option: %s", filename, option_text)
                        return True

                # If we haven't found new options, we've reached the end
                if current_visible_options == last_visible_options and scroll_attempts > 0:
                    logger.info("No new options appeared after scrolling, likely reached end")
                    break

                last_visible_options = current_visible_options.copy()

                # Scroll down using mouse wheel in the dropdown container
                center_x = box['x'] + box['width'] / 2
                center_y = box['y'] + box['height'] / 2

                # Use wheel event to scroll down in the dropdown
                self.page.mouse.wheel(0, scroll_distance)
                self.page.wait_for_timeout(800)  # Wait longer for virtual scrolling

                # Alternative: try scrolling within the container
                try:
                    dropdown_container.evaluate("element => element.scrollTop += 200")
                    self.page.wait_for_timeout(500)
                except:
                    logger.debug("Direct scroll evaluation failed, continuing with wheel scroll")

                scroll_attempts += 1

            logger.warning("File '%s' not found after scrolling through dropdown", filename)
            return False

        except Exception as e:
            logger.error("Error checking file in dropdown with scroll: %s", str(e))
            return False

    def click_delete_data_tab_with_wait(self):
        """Click on the Delete Data tab and wait for it to load"""
        import logging
        logger = logging.getLogger(__name__)

        logger.info("Clicking Delete Data tab...")
        self.page.locator(self.DELETE_DATA_TAB).click()
        self.page.wait_for_timeout(5000)  # Wait for tab content to load
        logger.info("✓ Delete Data tab loaded")

    def get_all_visible_files_in_delete(self):
        """Get list of all visible files in the Delete Data tab"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Wait for file list to load with retries
            max_attempts = 10
            attempt = 0
            files = []

            while attempt < max_attempts and len(files) == 0:
                attempt += 1
                logger.info("Attempt %d: Waiting for files to load...", attempt)

                # Wait progressively longer
                wait_time = 3000 + (attempt * 1000)  # 4s, 5s, 6s, etc.
                self.page.wait_for_timeout(wait_time)

                # Try to get file elements
                file_elements = self.page.locator(self.FILE_LABELS_IN_DELETE).all()
                files = []

                for element in file_elements:
                    try:
                        file_text = element.text_content().strip()
                        if file_text and file_text.startswith('/documents/'):
                            files.append(file_text)
                            logger.info("Found file: %s", file_text)
                    except Exception as elem_e:
                        logger.warning("Error reading file element: %s", str(elem_e))
                        continue

                logger.info("Attempt %d: Total files found: %d", attempt, len(files))

                # If we found files, break out of the loop
                if len(files) > 0:
                    break

                # Try alternative selectors if first attempts fail
                if attempt >= 3:
                    logger.info("Trying alternative file selectors...")

                    # Try broader markdown container selector
                    alt_file_elements = self.page.locator("//div[@data-testid='stMarkdownContainer']//p").all()
                    for element in alt_file_elements:
                        try:
                            file_text = element.text_content().strip()
                            if file_text and '/documents/' in file_text:
                                files.append(file_text)
                                logger.info("Found file (alt1): %s", file_text)
                        except Exception as elem_e:
                            continue

                    # Try even broader selector looking for any text containing documents
                    if len(files) == 0 and attempt >= 5:
                        broad_elements = self.page.locator("//p[contains(text(), '/documents/')]").all()
                        for element in broad_elements:
                            try:
                                file_text = element.text_content().strip()
                                if file_text and '/documents/' in file_text:
                                    files.append(file_text)
                                    logger.info("Found file (alt2): %s", file_text)
                            except Exception as elem_e:
                                continue

                # Debug information
                if attempt % 2 == 0:
                    logger.info("Debug attempt %d: Current URL: %s", attempt, self.page.url)

            if len(files) == 0:
                logger.warning("No files found after %d attempts", max_attempts)
            else:
                logger.info("Final: Total files found: %d", len(files))

            return files

        except Exception as e:
            logger.error("Error getting visible files: %s", str(e))
            return []

    def select_file_for_deletion(self, filename):
        """Select a specific file checkbox for deletion"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Attempting to select checkbox for file: %s", filename)

            # Method 1: Try using data-testid approach
            testid_selector = f"//div[@data-testid='stCheckbox']//input[@aria-label='{filename}' and @type='checkbox']"
            checkbox = self.page.locator(testid_selector)
            if checkbox.count() > 0 and checkbox.is_visible():
                logger.info("Found checkbox using testid selector: %s", filename)
                checkbox.click()
                self.page.wait_for_timeout(1000)
                logger.info("✓ Checkbox selected")
                return True

            # Method 2: Try generic aria-label approach
            generic_checkbox = f"//input[@aria-label='{filename}' and @type='checkbox']"
            checkbox = self.page.locator(generic_checkbox)
            if checkbox.count() > 0 and checkbox.is_visible():
                logger.info("Found checkbox using generic selector: %s", filename)
                checkbox.click()
                self.page.wait_for_timeout(1000)
                logger.info("✓ Checkbox selected")
                return True

            # Method 3: Try clicking on the label containing the filename
            label_selector = f"//label[contains(@data-baseweb, 'checkbox')]//div[contains(text(), '{filename}')]/../.."
            label = self.page.locator(label_selector)
            if label.count() > 0 and label.is_visible():
                logger.info("Found checkbox via label selector: %s", filename)
                label.click()
                self.page.wait_for_timeout(1000)
                logger.info("✓ Checkbox selected via label")
                return True

            # Method 4: Click on the label instead of the hidden input
            all_checkboxes = self.page.locator("//input[@type='checkbox']")
            checkbox_count = all_checkboxes.count()
            logger.info("Total checkboxes found: %d", checkbox_count)

            for i in range(checkbox_count):
                try:
                    checkbox = all_checkboxes.nth(i)
                    aria_label = checkbox.get_attribute("aria-label")
                    logger.info("Checkbox %d: aria-label = '%s'", i, aria_label)
                    if aria_label and filename in aria_label:
                        logger.info("Found matching checkbox by iterating: %s", filename)

                        # Try clicking the label instead of the hidden input
                        label_selector = f"//label[.//input[@aria-label='{filename}' and @type='checkbox']]"
                        label = self.page.locator(label_selector)
                        if label.count() > 0 and label.is_visible():
                            logger.info("Clicking on label for checkbox: %s", filename)
                            label.click()
                            self.page.wait_for_timeout(1000)
                            logger.info("✓ Checkbox selected via label click")
                            return True

                        # Try clicking the container div with data-testid="stCheckbox"
                        container_selector = f"//div[@data-testid='stCheckbox'][.//input[@aria-label='{filename}']]"
                        container = self.page.locator(container_selector)
                        if container.count() > 0 and container.is_visible():
                            logger.info("Clicking on container for checkbox: %s", filename)
                            container.click()
                            self.page.wait_for_timeout(1000)
                            logger.info("✓ Checkbox selected via container click")
                            return True

                        # Try force click on the input if nothing else works
                        logger.info("Attempting force click on hidden input: %s", filename)
                        checkbox.click(force=True)
                        self.page.wait_for_timeout(1000)
                        logger.info("✓ Checkbox selected via force click")
                        return True

                except Exception as iter_e:
                    logger.warning("Error checking checkbox %d: %s", i, str(iter_e))
                    continue

            logger.warning("Checkbox not found for file: %s", filename)
            return False

        except Exception as e:
            logger.error("Error selecting file checkbox: %s", str(e))
            return False

    def click_delete_button(self):
        """Click the Delete button to delete selected files"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Clicking Delete button...")
            delete_button = self.page.locator(self.DELETE_FORM_BUTTON)
            delete_button.click()

            # Wait for deletion to process and page to refresh
            self.page.wait_for_timeout(3000)
            logger.info("✓ Delete button clicked, waiting for page refresh...")

            # Wait for any loading/refresh to complete
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Page refresh completed")

            return True

        except Exception as e:
            logger.error("Error clicking delete button: %s", str(e))
            return False

    def is_file_still_visible_after_deletion(self, filename):
        """Check if a file is still visible after deletion (should not be)"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get current list of visible files
            current_files = self.get_all_visible_files_in_delete()

            # Check if the deleted file is still in the list
            for file in current_files:
                if filename in file:
                    logger.warning("File still visible after deletion: %s", file)
                    return True

            logger.info("✓ File successfully removed from view: %s", filename)
            return False

        except Exception as e:
            logger.error("Error checking file visibility: %s", str(e))
            return True  # Assume visible if we can't check

    def wait_for_upload_processing(self, timeout_minutes=3):
        """Wait for file upload processing to complete"""
        timeout_ms = timeout_minutes * 60 * 1000
        self.page.wait_for_timeout(timeout_ms)

    def upload_invalid_file(self, file_path):
        """Upload an invalid file and handle the file chooser"""
        import logging
        import os
        logger = logging.getLogger(__name__)

        try:
            logger.info("Uploading invalid file: %s", file_path)

            # Verify file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Test file not found at: {file_path}")

            # Start listening for file chooser before clicking the button
            with self.page.expect_file_chooser() as fc_info:
                logger.info("Clicking Browse Files button for invalid file...")
                # Try the specific locator first, fallback to the original if needed
                browse_button = self.page.locator(self.BROWSE_FILES_BUTTON_SPECIFIC)
                if not browse_button.is_visible():
                    browse_button = self.page.locator(self.BROWSE_FILES_BUTTON)

                browse_button.click()
                logger.info("✓ Browse Files button clicked")
                self.page.wait_for_timeout(2000)

            file_chooser = fc_info.value
            file_chooser.set_files(file_path)

            # Wait for file to be processed and error to appear
            self.page.wait_for_timeout(3000)
            logger.info("✓ Invalid file uploaded, waiting for error message")
            return True

        except Exception as e:
            logger.error("Error uploading invalid file: %s", str(e))
            return False

    def verify_file_error_message(self, expected_filename, expected_error):
        """Verify that the file error message appears for invalid file"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Wait for error message to appear
            logger.info("Waiting for error message to appear...")
            self.page.wait_for_timeout(3000)

            # SIMPLEST APPROACH: Look directly for the error message using data-testid
            logger.info("Looking for error message with data-testid...")

            # Method 1: Direct error message locator
            error_locator = "//span[@data-testid='stFileUploaderFileErrorMessage']"
            error_elements = self.page.locator(error_locator).all()
            logger.info("Found %d error message elements", len(error_elements))

            for i, element in enumerate(error_elements):
                try:
                    if element.is_visible():
                        error_text = element.text_content().strip()
                        logger.info("Error element %d (visible): '%s'", i, error_text)
                        if expected_error in error_text:
                            logger.info("✓ Error message matches expected: %s", expected_error)
                            return True
                    else:
                        logger.info("Error element %d: not visible", i)
                except Exception as e:
                    logger.warning("Error checking element %d: %s", i, str(e))

            # Method 2: Look for file name element to confirm file was uploaded
            logger.info("Looking for uploaded file name...")
            file_name_elements = self.page.locator("//div[@data-testid='stFileUploaderFileName']").all()
            logger.info("Found %d file name elements", len(file_name_elements))

            for i, element in enumerate(file_name_elements):
                try:
                    if element.is_visible():
                        text = element.text_content().strip()
                        title = element.get_attribute('title')
                        logger.info("File element %d: text='%s', title='%s'", i, text, title)
                        if expected_filename in str(text) or expected_filename in str(title):
                            logger.info("✓ File name found: %s", expected_filename)
                except Exception as e:
                    logger.warning("Error checking file element %d: %s", i, str(e))

            # Method 3: Broader search for any error text containing the expected message
            logger.info("Trying broader error message search...")
            all_spans = self.page.locator("//span[contains(text(), 'files are not allowed')]").all()
            logger.info("Found %d spans containing 'files are not allowed'", len(all_spans))

            for i, element in enumerate(all_spans):
                try:
                    if element.is_visible():
                        error_text = element.text_content().strip()
                        logger.info("Span element %d: '%s'", i, error_text)
                        if expected_error in error_text:
                            logger.info("✓ Error message found via broad search: %s", expected_error)
                            return True
                except Exception as e:
                    logger.warning("Error checking span element %d: %s", i, str(e))

            logger.warning("Expected error message not found: %s", expected_error)
            return False

        except Exception as e:
            logger.error("Error verifying file error message: %s", str(e))
            return False

    def click_file_remove_button(self, filename):
        """Click the remove button for a specific file in the uploader"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Looking for remove button for file: %s", filename)

            # Look for the delete button with aria-label containing the filename
            delete_btn_selector = f"//button[@aria-label='Remove {filename}']"
            delete_btn = self.page.locator(delete_btn_selector)

            if delete_btn.is_visible():
                logger.info("Clicking remove button for: %s", filename)
                delete_btn.click()
                self.page.wait_for_timeout(1000)
                logger.info("✓ Remove button clicked")
                return True
            else:
                # Try alternative selector using data-testid
                alt_selector = f"{self.FILE_UPLOADER_DELETE_BTN}[@aria-label='Remove {filename}']"
                alt_btn = self.page.locator(alt_selector)
                if alt_btn.is_visible():
                    logger.info("Clicking remove button (alt selector) for: %s", filename)
                    alt_btn.click()
                    self.page.wait_for_timeout(1000)
                    logger.info("✓ Remove button clicked (alt)")
                    return True
                else:
                    logger.warning("Remove button not found for file: %s", filename)
                    return False

        except Exception as e:
            logger.error("Error clicking file remove button: %s", str(e))
            return False

    def verify_file_removed_from_uploader(self, filename):
        """Verify that the file has been removed from the file uploader"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Wait for removal to complete
            self.page.wait_for_timeout(2000)

            # Check if file name is no longer present
            file_name_element = self.page.locator(f"{self.FILE_UPLOADER_FILE_NAME}[title='{filename}']")

            if not file_name_element.is_visible():
                logger.info("✓ File successfully removed from uploader: %s", filename)
                return True
            else:
                logger.warning("File still visible in uploader: %s", filename)
                return False

        except Exception as e:
            logger.error("Error verifying file removal: %s", str(e))
            return False

    def add_web_url(self, url):
        """Add a web URL to the text area for ingestion"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Adding web URL: %s", url)

            # Find and fill the URL text area
            url_textarea = self.page.locator(self.ADD_URLS_TEXT_AREA)
            url_textarea.click()
            url_textarea.fill(url)

            logger.info("✓ URL added to text area: %s", url)
            return True

        except Exception as e:
            logger.error("Error adding web URL: %s", str(e))
            return False

    def click_process_ingest_web_pages(self):
        """Click the 'Process and ingest web pages' button"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Clicking 'Process and ingest web pages' button")

            # Click the process button
            process_button = self.page.locator(self.PROCESS_INGEST_WEB_PAGES_BUTTON)
            process_button.click()

            # Wait for processing to start
            self.page.wait_for_timeout(3000)

            logger.info("✓ 'Process and ingest web pages' button clicked")
            return True

        except Exception as e:
            logger.error("Error clicking process web pages button: %s", str(e))
            return False

    def wait_for_web_url_processing(self, timeout_minutes=3):
        """Wait for web URL processing to complete"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Waiting for web URL processing to complete (timeout: %d minutes)", timeout_minutes)

            # Wait for processing - this can take time for web pages
            processing_time_seconds = timeout_minutes * 60
            chunk_size = 30  # 30 second chunks
            chunks = int(processing_time_seconds // chunk_size)

            for i in range(chunks):
                self.page.wait_for_timeout(chunk_size * 1000)  # Convert to milliseconds
                elapsed_minutes = ((i + 1) * chunk_size) / 60
                remaining_minutes = timeout_minutes - elapsed_minutes
                logger.info("Web URL processing... %.1f minutes elapsed, %.1f minutes remaining",
                           elapsed_minutes, remaining_minutes)

            logger.info("✓ Web URL processing wait completed")
            return True

        except Exception as e:
            logger.error("Error during web URL processing wait: %s", str(e))
            return False

    def click_configuration_tab(self):
        """Click on the Configuration tab"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Clicking Configuration tab...")
            self.page.locator(self.CONFIGURATION_TAB).click()
            self.page.wait_for_timeout(3000)  # Wait for tab to load
            logger.info("✓ Configuration tab loaded")
            return True
        except Exception as e:
            logger.error("Error clicking Configuration tab: %s", str(e))
            return False

    def get_chat_history_toggle_state(self):
        """Get the current state of the chat history toggle (enabled/disabled)"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # First scroll down to make sure the toggle is visible
            logger.info("Scrolling down to find chat history toggle...")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(2000)

            # Try multiple selectors for the chat history checkbox
            selectors = [
                "//input[@aria-label='Enable chat history' and @type='checkbox']",
                "//div[@data-testid='stCheckbox']//input[contains(@aria-label, 'Enable chat history')]",
                "//div[contains(@class, 'stCheckbox')]//input[@type='checkbox' and contains(@aria-label, 'chat history')]",
                "//input[@type='checkbox'][following-sibling::*//text()[contains(., 'Enable chat history')]]"
            ]

            chat_history_checkbox = None
            for selector in selectors:
                try:
                    checkbox = self.page.locator(selector)
                    if checkbox.count() > 0:
                        chat_history_checkbox = checkbox
                        logger.info("Found chat history checkbox using selector: %s", selector)
                        break
                except:
                    continue

            if chat_history_checkbox and chat_history_checkbox.count() > 0:
                # Scroll the element into view
                chat_history_checkbox.scroll_into_view_if_needed()
                self.page.wait_for_timeout(1000)

                is_checked = chat_history_checkbox.is_checked()
                logger.info("Chat history toggle state: %s", "enabled" if is_checked else "disabled")
                return is_checked
            else:
                logger.error("Chat history toggle not found")
                return None
        except Exception as e:
            logger.error("Error getting chat history toggle state: %s", str(e))
            return None

    def debug_configuration_page_structure(self):
        """Debug method to understand what's on the Configuration page"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("=== DEBUGGING Configuration Page Structure ===")

            # Scroll through the page to make sure we see everything
            logger.info("Scrolling to top first...")
            self.page.evaluate("window.scrollTo(0, 0)")
            self.page.wait_for_timeout(1000)

            # Get all checkboxes on the page
            checkboxes = self.page.locator("//input[@type='checkbox']")
            checkbox_count = checkboxes.count()
            logger.info("Total checkboxes found: %d", checkbox_count)

            for i in range(checkbox_count):
                try:
                    checkbox = checkboxes.nth(i)
                    aria_label = checkbox.get_attribute("aria-label") or "No aria-label"
                    is_visible = checkbox.is_visible()
                    logger.info("Checkbox %d: aria-label='%s', visible=%s", i, aria_label, is_visible)
                except:
                    logger.info("Checkbox %d: Could not get attributes", i)

            # Look for any text containing "chat history" or "Enable chat history"
            logger.info("Searching for 'chat history' text...")
            chat_text_elements = self.page.locator("//*[contains(text(), 'chat history') or contains(text(), 'Chat history') or contains(text(), 'Enable chat history')]")
            chat_text_count = chat_text_elements.count()
            logger.info("Elements containing 'chat history': %d", chat_text_count)

            for i in range(chat_text_count):
                try:
                    element = chat_text_elements.nth(i)
                    text_content = element.text_content() or "No text content"
                    tag_name = element.evaluate("el => el.tagName")
                    is_visible = element.is_visible()
                    logger.info("Chat text element %d: tag='%s', text='%s', visible=%s", i, tag_name, text_content, is_visible)
                except:
                    logger.info("Chat text element %d: Could not get attributes", i)

            # Look for all Streamlit elements that might contain the toggle
            logger.info("Searching for Streamlit checkbox elements...")
            st_checkboxes = self.page.locator("//div[@data-testid='stCheckbox']")
            st_checkbox_count = st_checkboxes.count()
            logger.info("Streamlit checkbox elements: %d", st_checkbox_count)

            for i in range(st_checkbox_count):
                try:
                    element = st_checkboxes.nth(i)
                    is_visible = element.is_visible()
                    inner_text = element.text_content() or "No text content"
                    logger.info("Streamlit checkbox %d: visible=%s, text='%s'", i, is_visible, inner_text)
                except:
                    logger.info("Streamlit checkbox %d: Could not get attributes", i)

            # Scroll down and check again
            logger.info("Scrolling down to bottom...")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(2000)

            # Check for expandable sections
            logger.info("Searching for expandable sections...")
            expander_elements = self.page.locator("//div[@data-testid='stExpanderDetails']")
            expander_count = expander_elements.count()
            logger.info("Expandable sections found: %d", expander_count)

            for i in range(expander_count):
                try:
                    element = expander_elements.nth(i)
                    is_visible = element.is_visible()
                    inner_text = element.text_content() or "No text content"
                    logger.info("Expandable section %d: visible=%s, text_snippet='%s'", i, is_visible, inner_text[:100])

                    # Try to expand it if it's not visible
                    if is_visible:
                        # Look for checkboxes inside this expander
                        inner_checkboxes = element.locator(".//input[@type='checkbox']")
                        inner_count = inner_checkboxes.count()
                        logger.info("  - Checkboxes inside expander %d: %d", i, inner_count)

                        for j in range(inner_count):
                            try:
                                inner_checkbox = inner_checkboxes.nth(j)
                                inner_aria_label = inner_checkbox.get_attribute("aria-label") or "No aria-label"
                                logger.info("    - Inner checkbox %d: aria-label='%s'", j, inner_aria_label)
                            except:
                                logger.info("    - Inner checkbox %d: Could not get attributes", j)
                except:
                    logger.info("Expandable section %d: Could not get attributes", i)

            logger.info("=== END DEBUG Configuration Page Structure ===")

        except Exception as e:
            logger.error("Error debugging configuration page structure: %s", str(e))

    def set_chat_history_toggle(self, enable=True):
        """Set the chat history toggle to enabled or disabled"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # First scroll down to make sure the toggle is visible
            logger.info("Scrolling down to find chat history toggle...")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(2000)

            # Try multiple selectors for the chat history checkbox
            selectors = [
                "//input[@aria-label='Enable chat history' and @type='checkbox']",
                "//div[@data-testid='stCheckbox']//input[contains(@aria-label, 'Enable chat history')]",
                "//div[contains(@class, 'stCheckbox')]//input[@type='checkbox' and contains(@aria-label, 'chat history')]"
            ]

            chat_history_checkbox = None
            for selector in selectors:
                try:
                    checkbox = self.page.locator(selector)
                    if checkbox.count() > 0:
                        chat_history_checkbox = checkbox
                        logger.info("Found chat history checkbox using selector: %s", selector)
                        break
                except:
                    continue

            if not chat_history_checkbox or chat_history_checkbox.count() == 0:
                logger.error("Chat history toggle not found")
                return False

            # Scroll the element into view
            chat_history_checkbox.scroll_into_view_if_needed()
            self.page.wait_for_timeout(1000)

            current_state = chat_history_checkbox.is_checked()
            logger.info("Current chat history toggle state: %s", "enabled" if current_state else "disabled")

            # Only click if we need to change the state
            if (enable and not current_state) or (not enable and current_state):
                # Click on the label instead of checkbox since checkbox might be disabled
                label_selectors = [
                    "//label[@data-baseweb='checkbox' and .//input[@aria-label='Enable chat history']]",
                    "//div[@data-testid='stCheckbox']//label[.//input[contains(@aria-label, 'Enable chat history')]]",
                    "//label[.//input[@type='checkbox' and contains(@aria-label, 'chat history')]]"
                ]

                clicked = False
                for label_selector in label_selectors:
                    try:
                        chat_history_label = self.page.locator(label_selector)
                        if chat_history_label.count() > 0:
                            chat_history_label.scroll_into_view_if_needed()
                            self.page.wait_for_timeout(500)
                            chat_history_label.click()
                            self.page.wait_for_timeout(1000)
                            logger.info("✓ Chat history toggle %s", "enabled" if enable else "disabled")
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    logger.error("Could not click chat history label")
                    return False

                return True
            else:
                logger.info("Chat history toggle already in desired state: %s", "enabled" if enable else "disabled")
                return True

        except Exception as e:
            logger.error("Error setting chat history toggle: %s", str(e))
            return False

    def click_save_configuration_button(self):
        """Click the Save configuration button"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Scroll down to make sure the button is visible
            logger.info("Scrolling down to find Save configuration button...")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(2000)

            # Try multiple selectors for the Save configuration button
            selectors = [
                "//button[@data-testid='stBaseButton-secondaryFormSubmit' and .//p[text()='Save configuration']]",
                "//button[contains(@class, 'stFormSubmitButton') and .//p[contains(text(), 'Save configuration')]]",
                "//div[@data-testid='stFormSubmitButton']//button[.//p[contains(text(), 'Save configuration')]]",
                "//button[.//p[text()='Save configuration']]"
            ]

            save_button = None
            for selector in selectors:
                try:
                    button = self.page.locator(selector)
                    if button.count() > 0:
                        save_button = button
                        logger.info("Found Save configuration button using selector: %s", selector)
                        break
                except:
                    continue

            if save_button and save_button.count() > 0:
                # Scroll the button into view
                save_button.scroll_into_view_if_needed()
                self.page.wait_for_timeout(1000)

                save_button.click()
                self.page.wait_for_timeout(3000)  # Wait for configuration to be saved
                logger.info("✓ Save configuration button clicked")
                return True
            else:
                logger.error("Save configuration button not found")
                return False

        except Exception as e:
            logger.error("Error clicking Save configuration button: %s", str(e))
            return False

    def scroll_to_document_processing_section(self):
        """Scroll to the Document processing configuration section"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Scrolling to Document processing configuration section...")

            # Look for the section heading or the data grid
            selectors = [
                "//div[contains(text(), 'Document processing configuration')]",
                "[data-testid='stDataFrame']",
                "//div[contains(@class, 'stDataFrame')]"
            ]

            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        element.scroll_into_view_if_needed()
                        self.page.wait_for_timeout(1000)  # Wait for scrolling
                        logger.info("✓ Scrolled to Document processing configuration section")
                        return True
                except Exception:
                    continue

            logger.warning("Document processing section not found, trying page down")
            self.page.keyboard.press("PageDown")
            self.page.wait_for_timeout(1000)
            return True

        except Exception as e:
            logger.error("Error scrolling to document processing section: %s", str(e))
            return False

    def click_advanced_image_processing_checkbox(self, document_type, max_attempts=3):
        """
        Click the advanced image processing checkbox for a specific document type using direct canvas click

        Args:
            document_type (str): The document type (jpeg, jpg, png, etc.)
            max_attempts (int): Maximum number of click attempts (default: 3, set to 1 for quick testing)
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Attempting to CLICK checkbox for %s using direct canvas approach", document_type)

            # First scroll to make sure the data grid is visible
            self.scroll_to_document_processing_section()

            # Get the row index for this document type based on the actual HTML structure
            row_index = self._get_row_index_for_document_type(document_type)
            if row_index == -1:
                logger.error("Document type %s not found in the expected row positions", document_type)
                return False

            logger.info("Found %s at row index %d", document_type, row_index)

            # Use direct canvas clicking approach (based on working coordinates from previous test)
            try:
                # Look for the Streamlit data frame container
                data_frame_container = self.page.locator(".stDataFrameGlideDataEditor").first

                if not data_frame_container.is_visible():
                    logger.error("Data frame container not visible for %s", document_type)
                    return False

                container_box = data_frame_container.bounding_box()
                logger.info("Canvas dimensions: %dx%d at (%d,%d)",
                           int(container_box['width']), int(container_box['height']),
                           int(container_box['x']), int(container_box['y']))

                if container_box:
                    # Calculate precise checkbox coordinates using same logic as working test
                    # From terminal output: checkbox column is at right edge of grid
                    checkbox_column_x = container_box['x'] + container_box['width'] - 39  # Fine-tuned offset

                    # Row calculation: header + (row_index * row_height) + row_center_offset
                    header_height = 40
                    row_height = 36
                    checkbox_row_y = container_box['y'] + header_height + (row_index * row_height) + (row_height / 2)

                    logger.info("Calculated click position for %s: (%.0f, %.0f)", document_type, checkbox_column_x, checkbox_row_y)

                    # Perform the canvas click to select the cell
                    logger.info("Attempting canvas click for %s...", document_type)
                    self.page.mouse.click(checkbox_column_x, checkbox_row_y)
                    self.page.wait_for_timeout(500)

                    logger.info("Canvas click completed for %s, now pressing spacebar to toggle checkbox", document_type)

                    # Press spacebar to toggle the checkbox after selecting the cell
                    logger.info("Pressing spacebar to toggle checkbox for %s", document_type)
                    self.page.keyboard.press("Space")
                    self.page.wait_for_timeout(800)

                    logger.info("✅ SUCCESS: Canvas click + spacebar completed for %s", document_type)
                    return True
                else:
                    logger.error("Could not get container bounding box for %s", document_type)
                    return False

            except Exception as e:
                logger.error("Canvas clicking failed for %s: %s", document_type, str(e))

            logger.error("Canvas approach failed for %s", document_type)
            return False

        except Exception as e:
            logger.error("Error toggling advanced image processing checkbox for %s: %s", document_type, str(e))
            return False

    def _get_row_index_for_document_type(self, document_type):
        """Helper method to get the row index for a document type based on the actual HTML structure"""
        # Based on the HTML structure provided, these are the actual row indices (0-based)
        type_to_index = {
            'pdf': 0, 'txt': 1, 'url': 2, 'md': 3, 'html': 4, 'htm': 5,
            'docx': 6, 'json': 7, 'jpg': 8, 'jpeg': 9, 'png': 10
        }
        return type_to_index.get(document_type, -1)

    def verify_advanced_image_processing_checkbox_state(self, document_type, expected_state="true"):
        """
        Verify the state of advanced image processing checkbox for a document type

        Args:
            document_type (str): The document type
            expected_state (str): Expected state - "true" or "false"
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Verifying advanced image processing checkbox state for %s (expected: %s)", document_type, expected_state)

            # Get the row index
            row_index = self._get_row_index_for_document_type(document_type)
            if row_index == -1:
                logger.error("Document type %s not found in expected row positions", document_type)
                return False

            # Find the cell containing the checkbox state using Glide Data Editor selectors
            state_selectors = [
                f"[data-testid='glide-cell-6-{row_index}']",  # Direct testid
                f"#glide-cell-6-{row_index}",  # ID approach
                f"//td[@data-testid='glide-cell-6-{row_index}']",  # XPath approach
                f"//table//tr[{row_index + 2}]//td[6]"  # Row-based approach
            ]

            for selector in state_selectors:
                try:
                    state_cell = self.page.locator(selector).first
                    if state_cell.count() > 0:
                        actual_state = state_cell.text_content().strip().lower()
                        logger.info("Checkbox state for %s: %s (using selector: %s)", document_type, actual_state, selector)
                        return actual_state == expected_state.lower()
                except Exception as e:
                    logger.debug("Selector %s failed for state verification: %s", selector, str(e))
                    continue

            logger.error("Could not verify checkbox state for %s", document_type)
            return False

        except Exception as e:
            logger.error("Error verifying advanced image processing checkbox state for %s: %s", document_type, str(e))
            return False

    def debug_data_grid_structure(self):
        """Debug method to understand the data grid structure"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("=== DEBUGGING Data Grid Structure ===")

            # Check if the data grid canvas is present
            canvas = self.page.locator("[data-testid='data-grid-canvas']")
            logger.info("Canvas elements found: %d", canvas.count())

            # Check for glide cells
            glide_cells = self.page.locator("[data-testid*='glide-cell-6']")
            logger.info("Glide cell column 6 elements found: %d", glide_cells.count())

            # List all glide cell 6 elements
            for i in range(min(glide_cells.count(), 15)):  # Limit to first 15
                cell = glide_cells.nth(i)
                cell_id = cell.get_attribute("data-testid")
                cell_text = cell.text_content() if cell.text_content() else "empty"
                logger.info("Glide cell %d: %s = '%s'", i, cell_id, cell_text)

            # Check for table structure
            table_rows = self.page.locator("table tbody tr")
            logger.info("Table rows found: %d", table_rows.count())

            # List first few rows with their content
            for i in range(min(table_rows.count(), 12)):  # Limit to first 12 rows
                row = table_rows.nth(i)
                cells = row.locator("td")
                if cells.count() >= 6:
                    doc_type = cells.nth(0).text_content()
                    checkbox_state = cells.nth(5).text_content()
                    logger.info("Row %d: %s -> checkbox: %s", i, doc_type, checkbox_state)

            logger.info("=== END DEBUG Data Grid Structure ===")

        except Exception as e:
            logger.error("Error debugging data grid structure: %s", str(e))

    def verify_configuration_save_success(self):
        """Verify that configuration was saved successfully"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Verifying configuration save success...")

            # Look for success message
            success_selectors = [
                "//div[@data-testid='stAlertContentSuccess']",
                "//div[contains(@class, 'stAlert')]//div[contains(text(), 'Configuration saved successfully')]",
                "//div[contains(text(), 'saved successfully')]",
                "//div[contains(text(), 'Configuration saved')]"
            ]

            for selector in success_selectors:
                try:
                    success_message = self.page.locator(selector).first
                    if success_message.is_visible():
                        message_text = success_message.text_content()
                        logger.info("✓ Found success message: %s", message_text)
                        return True
                except Exception:
                    continue

            logger.warning("No success message found after saving configuration")
            return False

        except Exception as e:
            logger.error("Error verifying configuration save success: %s", str(e))
            return False

    def verify_page_not_refreshed_during_checkbox_selection(self, document_types):
        """
        Verify that the page doesn't refresh automatically while selecting checkboxes

        Args:
            document_types (list): List of document types to test
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info("Verifying page stability during checkbox selection...")

            # Get initial page state
            initial_url = self.page.url
            initial_title = self.page.title()

            # Click checkboxes and verify page doesn't refresh
            for doc_type in document_types:
                logger.info("Testing checkbox stability for %s", doc_type)

                # Click the checkbox
                success = self.click_advanced_image_processing_checkbox(doc_type)
                if not success:
                    logger.warning("Failed to click checkbox for %s", doc_type)
                    continue

                # Verify page hasn't refreshed
                current_url = self.page.url
                current_title = self.page.title()

                if current_url != initial_url or current_title != initial_title:
                    logger.error("Page refreshed unexpectedly after clicking checkbox for %s", doc_type)
                    logger.error("Initial URL: %s, Current URL: %s", initial_url, current_url)
                    logger.error("Initial Title: %s, Current Title: %s", initial_title, current_title)
                    return False

                logger.info("✓ Page remained stable after clicking checkbox for %s", doc_type)

            logger.info("✓ Page remained stable throughout all checkbox selections")
            return True

        except Exception as e:
            logger.error("Error verifying page stability: %s", str(e))
            return False
