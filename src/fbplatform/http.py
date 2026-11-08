"""Rate-limited, retrying HTTP client that records provenance for every fetch.

Every response body is cached under data/raw/<source>/ and one line is appended to
data/raw/manifest.jsonl (url, status, sha256, retrieved_at). Re-running reuses the
cache, which makes ingestion resumable and keeps us polite to the sources.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import RAW, USER_AGENT


class HttpClient:
    def __init__(self, source: str, min_interval: float = 0.2, headers: dict | None = None,
                 use_cache: bool = True):
        self.source = source
        self.min_interval = min_interval
        self.use_cache = use_cache
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, **(headers or {})})
        retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.dir = RAW / source
        self.dir.mkdir(parents=True, exist_ok=True)

    def _wait(self):
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()

    def _log(self, url, status, body: bytes | None, cached: bool):
        rec = {"source": self.source, "url": url, "status": status, "cached": cached,
               "sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
               "bytes": len(body) if body is not None else None,
               "retrieved_at": datetime.now(timezone.utc).isoformat()}
        with open(RAW / "manifest.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def get(self, url: str, cache: bool = True) -> requests.Response | None:
        """GET with cache. Returns a Response (or a cached stand-in); None on 404."""
        key = hashlib.sha1(url.encode()).hexdigest()
        path = self.dir / key
        if cache and self.use_cache and path.exists():
            r = requests.Response()
            r.status_code, r._content, r.url = 200, path.read_bytes(), url
            self._log(url, 200, r._content, cached=True)
            return r
        self._wait()
        r = self.session.get(url, timeout=60)
        self._log(url, r.status_code, r.content, cached=False)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        if cache:
            path.write_bytes(r.content)
        return r

    def exists(self, url: str) -> bool:
        """HEAD request; True if 200. Not cached (cheap, and existence can change)."""
        self._wait()
        r = self.session.head(url, timeout=60, allow_redirects=True)
        self._log(url, r.status_code, None, cached=False)
        return r.status_code == 200
