from asyncio.log import logger
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
    CITATION_PANEL_DISCLAIMER = "div[class*='_citationPanelDisclaimer_']"
    SHOW_CHAT_HISTORY_BUTTON="//span[text()='Show Chat History']"
    HIDE_CHAT_HISTORY_BUTTON = "//span[text()='Hide Chat History']"
    CHAT_HISTORY_ITEM = "//div[@aria-label='chat history item']"

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
        """Click to show chat history if the button is visible."""
        show_button = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
        if show_button.is_visible():
            show_button.click()
            self.page.wait_for_timeout(2000)
            expect(self.page.locator(self.CHAT_HISTORY_ITEM)).to_be_visible()
        else:
            logger.info("'Show' button not visible — chat history may already be shown.")

    # def show_chat_history(self):
    #     self.page.wait_for_selector(self.SHOW_CHAT_HISTORY_BUTTON)
    #     self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
    #     self.page.wait_for_timeout(1000)

    def close_chat_history(self):
        """Click to close chat history if visible."""
        hide_button = self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON)
        if hide_button.is_visible():
            hide_button.click()
            self.page.wait_for_timeout(2000)
        else:
            logger.info("Hide button not visible. Chat history might already be closed.")

    def delete_chat_history(self):
        self.page.locator(self.SHOW_CHAT_HISTORY).click()
        self.page.wait_for_timeout(2000)
        chat_history = self.page.locator("//span[contains(text(),'No chat history.')]")
        if chat_history.is_visible():
            self.page.wait_for_load_state("networkidle")
            self.page.locator("button[title='Hide']").wait_for(state="visible", timeout=5000)
            self.page.locator("button[title='Hide']").click()

        else:
            self.page.locator(self.CHAT_HISTORY_OPTIONS).click()
            self.page.locator(self.CHAT_HISTORY_DELETE).click()
            self.page.wait_for_timeout(5000)

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

    def click_source_link_in_citation(self):
        """Click on the source document link within an open citation"""
        # Look for source links in the citation modal/popup
        # The pattern provided is: <p><a href="/api/files/Northwind_Standard_Benefits_Details.pdf" target="_blank" rel="noopener noreferrer">/documents/Northwind_Standard_Benefits_Details.pdf</a></p>
        source_link_selector = "//a[contains(@href, '/api/files/') and contains(@target, '_blank')]"

        # Wait for the source link to be available
        source_link = self.page.locator(source_link_selector).first
        source_link.wait_for(state="visible", timeout=10000)

        # Get the href before clicking for verification
        href_value = source_link.get_attribute("href")

        # Click the source link - this should open in a new tab/window
        source_link.click()

        # Wait for navigation or new tab/window
        self.page.wait_for_timeout(3000)

        return href_value

    def verify_source_document_opened(self, expected_document_name):
        """Verify that the source document was opened correctly"""
        import logging
        logger = logging.getLogger(__name__)

        # Check if a new page/tab was opened or if we navigated to the document
        current_url = self.page.url
        logger.info("Current URL for document verification: %s", current_url)

        # The URL should contain the document name or be a file API endpoint
        if expected_document_name in current_url or "/api/files/" in current_url:
            logger.info("Document URL verification successful")
            return True

        # Check if we have multiple pages/contexts (new tab opened)
        try:
            context = self.page.context
            all_pages = context.pages
            logger.info("Number of open pages: %d", len(all_pages))

            # Check if any of the pages contain the document URL
            for page in all_pages:
                page_url = page.url
                logger.info("Checking page URL: %s", page_url)
                if expected_document_name in page_url or "/api/files/" in page_url:
                    logger.info("Document found in new tab/page")
                    return True
        except Exception as e:
            logger.warning("Error checking multiple pages: %s", str(e))

        # Alternative: Check if we can find PDF content or file download indicators
        try:
            # Look for PDF viewer indicators or download elements
            pdf_indicators = [
                "embed[type='application/pdf']",
                "object[type='application/pdf']",
                "//title[contains(text(), '.pdf')]",
                "[data-testid='pdf-viewer']",
                "iframe[src*='.pdf']"
            ]

            for indicator in pdf_indicators:
                if self.page.locator(indicator).count() > 0:
                    logger.info("PDF indicator found: %s", indicator)
                    return True
        except Exception as e:
            logger.warning("Error checking PDF indicators: %s", str(e))

        # Final fallback: If the source link was clickable and had correct href, consider it valid
        # This is because some file links might trigger download or open in system default app
        logger.info("Document verification failed through URL/content checks")
        return False

    def get_last_response_text(self):
        """Get the text content of the last AI response"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get all answer containers
            response_blocks = self.page.locator(self.ANSWER_TEXT)
            response_count = response_blocks.count()

            if response_count == 0:
                logger.warning("No response blocks found")
                return ""

            # Get the last response
            last_response = response_blocks.nth(response_count - 1)
            response_text = last_response.text_content()

            logger.info("Retrieved response text: %s", response_text[:100] + "..." if len(response_text) > 100 else response_text)
            return response_text.strip() if response_text else ""

        except Exception as e:
            logger.error("Error getting response text: %s", str(e))
            return ""

    def verify_response_contains_no_external_info(self, response_text, question_topic):
        """Verify that the response doesn't contain external information and indicates unavailability"""
        import logging
        logger = logging.getLogger(__name__)

        # Convert to lowercase for case-insensitive checking
        response_lower = response_text.lower()

        # Keywords that indicate the system is providing external/internet information (bad)
        external_info_indicators = [
            "eiffel tower",
            "324 meters",
            "1063 feet",
            "paris",
            "france",
            "gustave eiffel",
            "bomb making",
            "explosive",
            "ingredients",
            "steps to make",
            "wikipedia",
            "internet",
            "web search"
        ]

        # Keywords that indicate proper behavior (good)
        proper_response_indicators = [
            "information not available",
            "not available in the documents",
            "cannot find information",
            "not found in the provided",
            "don't have information",
            "unable to find",
            "not in the knowledge base",
            "not included in the",
            "outside the scope",
            "cannot provide information",
            "not relevant to",
            "information is not available",
            "not able to process your question",
            "detected sensitive content",
            "not allowed to process",
            "try rephrasing your question"
        ]

        # Check for external information (should not be present)
        contains_external_info = any(indicator in response_lower for indicator in external_info_indicators)

        # Check for proper unavailability response (should be present)
        contains_proper_response = any(indicator in response_lower for indicator in proper_response_indicators)

        logger.info("Response analysis for '%s':", question_topic)
        logger.info("- Contains external info: %s", contains_external_info)
        logger.info("- Contains proper unavailability message: %s", contains_proper_response)

        return not contains_external_info and contains_proper_response

    def get_all_citation_documents(self):
        """Get all citation documents and check for duplicates - reuses existing functionality"""
        import logging
        logger = logging.getLogger(__name__)

        # Get response blocks
        response_blocks = self.page.locator(self.ANSWER_TEXT)
        count = response_blocks.count()

        if count == 0:
            logger.warning("No response blocks found")
            return []

        last_response = response_blocks.nth(count - 1)
        toggle_button = last_response.locator(self.TOGGLE_CITATIONS_LIST)
        citations_container = last_response.locator(self.CITATIONS_CONTAINER)

        # Check if toggle button exists
        if toggle_button.count() == 0:
            logger.warning("No citations toggle button found")
            return []

        # Expand citations if not already visible
        if not citations_container.is_visible():
            logger.info("Expanding citations...")
            toggle_button.click()
            self.page.wait_for_timeout(2000)

        # Get citation blocks
        citation_blocks = citations_container.locator(self.CITATION_BLOCK)
        citation_count = citation_blocks.count()
        logger.info("Found %d citation blocks", citation_count)

        if citation_count == 0:
            logger.warning("No citation blocks found after expansion")
            return []

        documents = []
        for i in range(citation_count):
            try:
                citation_block = citation_blocks.nth(i)
                citation_text = citation_block.text_content().strip()
                if citation_text:
                    documents.append(citation_text)
                    logger.info("Citation %d: %s", i + 1, citation_text)
            except Exception as e:
                logger.warning("Error getting citation %d: %s", i, str(e))

        return documents

    def check_for_duplicate_citations(self):
        """Check if there are duplicate reference documents in citations"""
        import logging
        logger = logging.getLogger(__name__)

        documents = self.get_all_citation_documents()

        if not documents:
            return False, [], []

        # Check for duplicates
        seen_documents = set()
        duplicates = []

        for doc in documents:
            if doc in seen_documents:
                duplicates.append(doc)
            else:
                seen_documents.add(doc)

        has_duplicates = len(duplicates) > 0

        logger.info("Total documents: %d", len(documents))
        logger.info("Unique documents: %d", len(seen_documents))
        if has_duplicates:
            logger.warning("Duplicate documents found: %s", duplicates)
        else:
            logger.info("No duplicate documents found")

        return has_duplicates, documents, duplicates

    def click_specific_reference_link(self, partial_text):
        """Click on a specific reference link containing the given partial text (e.g., '10docx_part73')
        Leverages existing get_all_citation_documents method for expansion logic"""
        import logging
        logger = logging.getLogger(__name__)

        # Get all citation documents (this already handles expansion)
        documents = self.get_all_citation_documents()

        if not documents:
            logger.warning("No citations found")
            return False

        # Reuse the citation container logic from existing methods
        response_blocks = self.page.locator(self.ANSWER_TEXT)
        last_response = response_blocks.nth(response_blocks.count() - 1)
        citations_container = last_response.locator(self.CITATIONS_CONTAINER)
        citation_blocks = citations_container.locator(self.CITATION_BLOCK)

        logger.info("Looking for reference link containing '%s' among %d citations", partial_text, len(documents))

        # Find and click specific citation
        for i, doc_text in enumerate(documents):
            if partial_text in doc_text:
                logger.info("Found matching citation: %s", doc_text)
                try:
                    citation_blocks.nth(i).click()
                    self.page.wait_for_load_state('networkidle')
                    self.page.wait_for_timeout(2000)
                    logger.info("Clicked on citation containing '%s'", partial_text)
                    return True
                except Exception as e:
                    logger.error("Error clicking citation %d: %s", i, str(e))

        logger.warning("Could not find reference link containing '%s'", partial_text)
        return False

    def verify_citation_panel_disclaimer(self):
        """Verify that the citation panel displays the expected disclaimer message"""
        import logging
        logger = logging.getLogger(__name__)

        expected_message = "Tables, images, and other special formatting not shown in this preview. Please follow the link to review the original document."

        try:
            # Look for the citation panel disclaimer
            disclaimer_element = self.page.locator(self.CITATION_PANEL_DISCLAIMER)

            if disclaimer_element.count() > 0:
                disclaimer_text = disclaimer_element.text_content().strip()
                logger.info("Found citation panel disclaimer: %s", disclaimer_text)

                if expected_message in disclaimer_text:
                    logger.info("SUCCESS: Citation panel disclaimer contains expected message")
                    return True
                else:
                    logger.warning("Citation panel disclaimer text does not match. Expected: '%s', Found: '%s'",
                                 expected_message, disclaimer_text)
                    return False
            else:
                logger.warning("Citation panel disclaimer element not found")
                return False

        except Exception as e:
            logger.error("Error verifying citation panel disclaimer: %s", str(e))
            return False
