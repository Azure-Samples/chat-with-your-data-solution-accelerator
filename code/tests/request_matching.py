from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Request


class RequestMatcher:
    path: str
    method: str
    json: dict
    headers: dict
    query_string: dict
    times: int

    def __init__(
        self,
        path: str,
        method: str,
        json: dict = None,
        headers: dict = None,
        query_string: str = None,
        times: int = 1,
    ):
        self.path = path
        self.method = method
        self.json = json
        self.headers = headers
        self.query_string = query_string
        self.times = times

    def __str__(self):
        return f"Path: {self.path}, Method: {self.method}, JSON: {self.json}, Headers: {self.headers}, Query String: {self.query_string}, Times: {self.times}"


def verify_request_made(
    mock_httpserver: HTTPServer, request_matcher: RequestMatcher
) -> list[Request]:
    requests_log = mock_httpserver.log

    similar_requests = []
    matching_requests = []
    for request_log in requests_log:
        request = request_log[0]

        if request.path == request_matcher.path:
            similar_requests.append(request)

            if request.method != request_matcher.method:
                continue

            if (
                request_matcher.json is not None
                and request.json != request_matcher.json
            ):
                continue

            if request_matcher.headers is not None and not contains_all_headers(
                request_matcher, request
            ):
                continue

            if (
                request_matcher.query_string is not None
                and request.query_string.decode("utf-8") != request_matcher.query_string
            ):
                continue

            matching_requests.append(request)

    error_message = f"Matching request found {len(matching_requests)} times but expected {request_matcher.times} times. \n Expected request: {request_matcher}\n Found similar requests:"
    if len(matching_requests) != request_matcher.times:
        for request in similar_requests:
            error_message += "\n--- Similar Request Start"
            error_message += f"\nPath: {request.path}, Method: {request.method}, Body: {request.get_data()}, Headers: {request.headers} Query String: {request.query_string.decode('utf-8')}"
            error_message += "\n--- Similar Request End"

    assert len(matching_requests) == request_matcher.times, error_message
    return matching_requests


def contains_all_headers(request_matcher: RequestMatcher, request: Request):
    for key, value in request_matcher.headers.items():
        if request.headers.get(key) != value:
            return False

    return True
