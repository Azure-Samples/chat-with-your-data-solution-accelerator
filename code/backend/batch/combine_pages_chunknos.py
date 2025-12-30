import logging
import azure.functions as func
import json

bp_combine_pages_and_chunknos = func.Blueprint()


@bp_combine_pages_and_chunknos.route(route="combine_pages_and_chunknos", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def combine_pages_and_chunknos(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function is designed to be called by an Azure Cognitive Search WebApiSkill.
    It expects a JSON payload with two arrays ("pages" and "chunk_nos") and
    combines them into a single array of objects.
    """
    logging.info("Combine pages and chunk numbers function processed a request.")

    try:
        req_body = req.get_json()
        values = req_body.get("values", [])

        response_values = []

        for value in values:
            record_id = value.get("recordId")
            data = value.get("data", {})

            pages = data.get("pages", [])
            chunk_nos = data.get("chunk_nos", [])

            # Zip the two arrays together
            zipped_data = [
                {"page_text": page, "chunk_no": chunk}
                for page, chunk in zip(pages, chunk_nos)
            ]

            response_values.append(
                {
                    "recordId": record_id,
                    "data": {"pages_with_chunks": zipped_data},
                    "errors": None,
                    "warnings": None,
                }
            )

        # Return the response in the format expected by the WebApiSkill
        return func.HttpResponse(
            body=json.dumps({"values": response_values}),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        logging.error(f"Error in combine_pages_and_chunknos function: {e}")
        return func.HttpResponse(
            body=json.dumps({"values": [{"recordId": "error", "data": {}, "errors": [{"message": str(e)}], "warnings": []}]}),
            mimetype="application/json",
            status_code=500,
        )
