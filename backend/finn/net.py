"""One HTTP client for everything we fetch. Forces IPv4 and short connect timeouts: on some home networks
IPv6 routes silently hang, which looked like 'push is stuck' (1 Nov). Set FINN_FORCE_IPV4=0 to disable."""
from __future__ import annotations

import os
from functools import lru_cache

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _transport() -> httpx.HTTPTransport:
    if os.environ.get("FINN_FORCE_IPV4", "1") == "1":
        return httpx.HTTPTransport(local_address="0.0.0.0", retries=2)
    return httpx.HTTPTransport(retries=2)


@lru_cache
def client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=TIMEOUT, follow_redirects=True, transport=_transport())


def llm_client() -> httpx.Client:
    """For the Gemini SDK (no browser User-Agent; longer read timeout for big prompts)."""
    return httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0), transport=_transport())
