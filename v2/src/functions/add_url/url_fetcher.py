"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

URL fetcher for the ``add_url`` blueprint.

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

import logging

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0


async def fetch_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Fetch ``url`` via httpx async GET and return the raw response body.

    Caller may inject an ``httpx.AsyncClient`` (mirrors the DI
    contract of :func:`functions.batch_push.blob_fetcher.download_blob`
    — the trigger owns the client lifecycle when it wants connection
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
    try:
        if client is None:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
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
