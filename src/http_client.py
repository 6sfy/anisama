"""Shared httpx.Client singleton with HTTP/2 support.

Thread-safe, lazily initialized. Use ``get_client()`` everywhere
instead of creating ad-hoc ``httpx.Client`` instances.
"""

import threading

import httpx

from .config import REQUEST_TIMEOUT

_client: httpx.Client | None = None
_lock = threading.Lock()


def get_client() -> httpx.Client:
    """Return a shared, lazily-initialized ``httpx.Client``.

    The client is created once with HTTP/2 support and connection
    pooling.  It is thread-safe: concurrent calls will only create
    one instance.
    """
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = httpx.Client(
                    follow_redirects=True,
                    timeout=REQUEST_TIMEOUT,
                    http2=True,
                )
    return _client


def close_client() -> None:
    """Explicitly close the shared client (e.g. at process shutdown)."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
            _client = None
