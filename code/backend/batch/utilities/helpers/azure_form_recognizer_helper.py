import logging
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.identity import DefaultAzureCredential
import html
import traceback
from .env_helper import EnvHelper

logger = logging.getLogger(__name__)


class AzureFormRecognizerClient:
    def __init__(self) -> None:
        env_helper: EnvHelper = EnvHelper()

        self.AZURE_FORM_RECOGNIZER_ENDPOINT: str = (
            env_helper.AZURE_FORM_RECOGNIZER_ENDPOINT
        )
        if env_helper.AZURE_AUTH_TYPE == "rbac":
            self.document_analysis_client = DocumentAnalysisClient(
                endpoint=self.AZURE_FORM_RECOGNIZER_ENDPOINT,
                credential=DefaultAzureCredential(),
                headers={
                    "x-ms-useragent": "chat-with-your-data-solution-accelerator/1.0.0"
                },
            )
        else:
            self.AZURE_FORM_RECOGNIZER_KEY: str = env_helper.AZURE_FORM_RECOGNIZER_KEY

            self.document_analysis_client = DocumentAnalysisClient(
                endpoint=self.AZURE_FORM_RECOGNIZER_ENDPOINT,
                credential=AzureKeyCredential(self.AZURE_FORM_RECOGNIZER_KEY),
                headers={
                    "x-ms-useragent": "chat-with-your-data-solution-accelerator/1.0.0"
                },
            )

    form_recognizer_role_to_html = {
        "title": "h1",
        "sectionHeading": "h2",
        "pageHeader": None,
        "pageFooter": None,
        "paragraph": "p",
    }

    def _table_to_html(self, table):
        table_html = "<table>"
        rows = [
            sorted(
                [cell for cell in table.cells if cell.row_index == i],
                key=lambda cell: cell.column_index,
            )
            for i in range(table.row_count)
        ]
        for row_cells in rows:
            table_html += "<tr>"
            for cell in row_cells:
                tag = (
                    "th"
                    if (cell.kind == "columnHeader" or cell.kind == "rowHeader")
                    else "td"
                )
                cell_spans = ""
                if cell.column_span > 1:
                    cell_spans += f" colSpan={cell.column_span}"
                if cell.row_span > 1:
                    cell_spans += f" rowSpan={cell.row_span}"
                table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
            table_html += "</tr>"
        table_html += "</table>"
        return table_html

    def begin_analyze_document_from_url(
        self, source_url: str, use_layout: bool = True, paragraph_separator: str = ""
    ):
        offset = 0
        page_map = []
        model_id = "prebuilt-layout" if use_layout else "prebuilt-read"

        try:
            logger.info("Method begin_analyze_document_from_url started")
            logger.info(f"Model ID selected: {model_id}")
            poller = self.document_analysis_client.begin_analyze_document_from_url(
                model_id, document_url=source_url
            )
            form_recognizer_results = poller.result()

            # (if using layout) mark all the positions of headers
            roles_start = {}
            roles_end = {}
            for paragraph in form_recognizer_results.paragraphs:
                # if paragraph.role!=None:
                para_start = paragraph.spans[0].offset
                para_end = paragraph.spans[0].offset + paragraph.spans[0].length
                roles_start[para_start] = (
                    paragraph.role if paragraph.role is not None else "paragraph"
                )
                roles_end[para_end] = (
                    paragraph.role if paragraph.role is not None else "paragraph"
                )

            for page_num, page in enumerate(form_recognizer_results.pages):
                tables_on_page = [
                    table
                    for table in form_recognizer_results.tables
                    if table.bounding_regions[0].page_number == page_num + 1
                ]

                # (if using layout) mark all positions of the table spans in the page
                page_offset = page.spans[0].offset
                page_length = page.spans[0].length
                table_chars = [-1] * page_length
                for table_id, table in enumerate(tables_on_page):
                    for span in table.spans:
                        # replace all table spans with "table_id" in table_chars array
                        for i in range(span.length):
                            idx = span.offset - page_offset + i
                            if idx >= 0 and idx < page_length:
                                table_chars[idx] = table_id

                # build page text by replacing charcters in table spans with table html and replace the characters corresponding to headers with html headers, if using layout
                page_text = ""
                added_tables = set()
                for idx, table_id in enumerate(table_chars):
                    if table_id == -1:
                        position = page_offset + idx
                        if position in roles_start.keys():
                            role = roles_start[position]
                            html_role = self.form_recognizer_role_to_html.get(role)
                            if html_role is not None:
                                page_text += f"<{html_role}>"
                        if position in roles_end.keys():
                            role = roles_end[position]
                            html_role = self.form_recognizer_role_to_html.get(role)
                            if html_role is not None:
                                page_text += f"</{html_role}>"

                        page_text += form_recognizer_results.content[page_offset + idx]

                    elif table_id not in added_tables:
                        page_text += self._table_to_html(tables_on_page[table_id])
                        added_tables.add(table_id)

                page_text += " "
                page_map.append(
                    {"page_number": page_num, "offset": offset, "page_text": page_text}
                )
                offset += len(page_text)

            return page_map
        except Exception as e:
            logger.exception(f"Exception in begin_analyze_document_from_url: {e}")
            raise ValueError(f"Error: {traceback.format_exc()}. Error: {e}")
        finally:
            logger.info("Method begin_analyze_document_from_url ended")
