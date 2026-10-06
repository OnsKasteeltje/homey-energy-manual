#!/usr/bin/env python3
"""Bounded Open-Meteo HTTP transport for forecast builders."""

import json
import socket
import ssl
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT_SEC = 20
MAX_ATTEMPTS = 2
RETRY_DELAY_SEC = 2.0


def _is_retryable_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code <= 599

    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc

    if isinstance(reason, ssl.SSLCertVerificationError):
        return False

    return isinstance(
        reason,
        (
            TimeoutError,
            socket.timeout,
            ssl.SSLError,
            ConnectionError,
            OSError,
        ),
    )


def fetch_json_with_retry(
    request,
    *,
    label,
    opener=urllib.request.urlopen,
    sleeper=time.sleep,
    timeout_sec=DEFAULT_TIMEOUT_SEC,
    retry_delay_sec=RETRY_DELAY_SEC,
):
    """Fetch JSON with exactly one bounded retry for transient transport faults."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener(request, timeout=timeout_sec) as response:
                return json.load(response)
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            if not retryable or attempt >= MAX_ATTEMPTS:
                raise

            print(
                "WARN: "
                f"{label} transient fetch failure "
                f"attempt={attempt}/{MAX_ATTEMPTS} "
                f"error={type(exc).__name__}: {exc}; "
                f"retrying in {retry_delay_sec:.0f}s",
                flush=True,
            )
            sleeper(retry_delay_sec)

    raise RuntimeError("unreachable")
