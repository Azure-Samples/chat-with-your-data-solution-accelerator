"""URL fetcher for the ``add_url`` blueprint.

``add_url`` is the HTTP-triggered counterpart to ``batch_push``:
operators POST a URL, the blueprint downloads the page bytes, and
the same parse / chunk / embed / push pipeline runs against the
fetched payload. This module owns only the download call; the
HTTP trigger (``blueprint.py``) and the orchestrating handler
(``handler.py``) compose the pipeline around it.

Why bytes (not a stream): matches the
:func:`functions.batch_push.blob_fetcher.download_blob` contract so
``add_url_handler`` and ``batch_push_handler`` can share the same
parser / embedder wiring without conditional buffering. Pages
ingested through ``add_url`` are HTML / PDF / text in the same
size class as blob ingestion (tens of MB at most); full
materialization keeps the pipeline composition simple.

Hard Rule #14 (SDK boundary resilience) -- the httpx call is
wrapped in a narrow ``except httpx.HTTPError`` (umbrella for
``ConnectError``, ``TimeoutException``, ``HTTPStatusError``,
``ReadError``, etc.) with structured ``logger.exception`` extras
(``operation``, ``provider``, ``url``) then re-raised so the
HTTP trigger's ``@map_function_exceptions("add_url")`` decorator
can translate the failure into the right ``HttpResponse``
status (502 for SDK errors per the policy in
[v2/docs/exception_handling_policy.md] §"Functions blueprints").
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_public_http_url(url: str) -> None:
    """Raise ``httpx.InvalidURL`` if *url* is not a safe public http/https URL.

    Guards against SSRF by rejecting non-http(s) schemes, URLs without a
    hostname, and URLs whose hostname resolves to a private, loopback,
    link-local, multicast, reserved, or unspecified IP address (including
    Azure IMDS 169.254.169.254 and the Azure WireServer 168.63.129.16).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise httpx.InvalidURL("Only http/https URLs are allowed.")
    if not parsed.hostname:
        raise httpx.InvalidURL("URL must include a hostname.")
    host = parsed.hostname
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise httpx.InvalidURL("URL host resolves to a non-public IP.")
        return
    except ValueError:
        logger.debug(
            "Host %r is not an IP address literal; proceeding to DNS resolution.",
            host,
        )
    try:
        infos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise httpx.InvalidURL("Hostname could not be resolved.") from exc
    if not infos:
        raise httpx.InvalidURL("Hostname could not be resolved.")
    for info in infos:
        resolved_ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(resolved_ip):
            raise httpx.InvalidURL("URL host resolves to a non-public IP.")


async def fetch_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Fetch ``url`` via httpx async GET and return the raw response body.

    Caller may inject an ``httpx.AsyncClient`` (mirrors the DI
    contract of :func:`functions.batch_push.blob_fetcher.download_blob`,
    the trigger owns the client lifecycle when it wants connection
    reuse across multiple URLs). When ``client`` is ``None`` the
    helper constructs a per-call client with ``follow_redirects=True``
    and the documented default timeout, then closes it on exit.

    ``timeout_seconds`` is ignored when ``client`` is supplied;
    timeout configuration belongs to the injected client's own
    construction in that case.

    Raises:
        httpx.HTTPError: any httpx-family error (``ConnectError``,
            ``TimeoutException``, ``HTTPStatusError`` from
            ``raise_for_status``, etc.). Logged at ERROR with
            ``operation="fetch_url"`` then re-raised so the
            ``add_url`` HTTP trigger's
            ``@map_function_exceptions("add_url")`` decorator can
            translate it into a 502 response.
    """
    _validate_public_http_url(url)
    # A descriptive User-Agent is required by many sites (e.g. Wikipedia
    # blocks the default python-httpx UA with 403). The string follows the
    # convention used by other Azure SA bots.
    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CWYD-Bot/1.0; "
            "+https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)"
        )
    }
    try:
        if client is None:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
                headers=_headers,
            ) as owned_client:
                response = await owned_client.get(url)
        else:
            response = await client.get(url)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError:
        logger.exception(
            "url fetch failed",
            extra={
                "operation": "fetch_url",
                "provider": "httpx",
                "url": url,
            },
        )
        raise
