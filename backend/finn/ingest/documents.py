"""Download PDFs once (cached on disk by URL hash) and return page text with page numbers."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

from .. import config, net

_last_fetch = 0.0


def local_path(url: str, folder: str = "_filings") -> Path:
    return config.DOCS_DIR / folder / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".pdf")


def fetch_pdf(url: str, folder: str = "_filings", min_interval: float = 0.5) -> Path | None:
    """Returns the cached file path, downloading if needed. None on failure (caller degrades)."""
    global _last_fetch
    if not url or not url.startswith("http"):
        return None                     # links need not end in .pdf (company IR sites); we check the bytes instead
    path = local_path(url, folder)
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    wait = min_interval - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        r = net.client().get(url)
        _last_fetch = time.time()
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            return None
        path.write_bytes(r.content)
        return path
    except httpx.HTTPError:
        return None


def page_texts(path: Path, max_pages: int | None = None) -> list[str]:
    import pymupdf
    with pymupdf.open(path) as doc:
        n = doc.page_count if max_pages is None else min(max_pages, doc.page_count)
        return [doc[i].get_text() for i in range(n)]


def snippet(url: str, chars: int = 1500) -> str:
    """First ~1500 characters of a filing's text ('' if unavailable or scanned)."""
    path = fetch_pdf(url)
    if not path:
        return ""
    try:
        text = " ".join(" ".join(page_texts(path, 2)).split())
    except Exception:  # noqa: BLE001
        return ""
    return text[:chars]
