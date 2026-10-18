"""Polite HTTP fetching.

Adapted from ``~/Projects/unified-job-portal-automation/discovery/http.py``:
timeouts, bounded retries with exponential backoff + jitter, URL redaction for
sensitive query parameters, and **fully injectable** network calls so unit tests
never touch the network.

Also provides a small :class:`RateLimiter` (minimum interval between requests)
and a :class:`RobotsGate` that honours ``robots.txt`` (respecting the
``respect_robots`` setting).
"""

from __future__ import annotations

import http.client
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

DEFAULT_USER_AGENT = (
    "india-road-safety-intelligence/0.1 (local research; contact: research@localhost)"
)

# Query-string keys whose values must never appear in error messages or logs.
_SENSITIVE_QUERY_KEYS = frozenset({
    "app_id", "app_key", "api_key", "apikey", "token", "access_token",
    "password", "secret", "key", "auth",
})


class HttpError(RuntimeError):
    """Raised when a request does not produce a usable response."""

    def __init__(self, message: str, url: str, status: Optional[int] = None):
        super().__init__(message)
        self.url = url
        self.status = status


class RobotsDisallowed(RuntimeError):
    """Raised when robots.txt (or site policy) disallows fetching a URL."""


def redact_url(url: str) -> str:
    """Mask sensitive query-parameter values for safe logging."""
    try:
        parts = urllib.parse.urlsplit(url)
        if not parts.query:
            return url
        qs = [
            (k, "<redacted>" if k.lower() in _SENSITIVE_QUERY_KEYS else v)
            for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(qs), parts.fragment)
        )
    except Exception:  # noqa: BLE001 — redaction must never itself raise
        return url


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text())


class RateLimiter:
    """Enforce a minimum interval between requests (politeness)."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.min_interval = max(0.0, float(min_interval))
        self._clock = clock
        self._sleep = sleep
        self._last: Optional[float] = None

    def wait(self) -> float:
        """Sleep as needed so at least ``min_interval`` separates calls."""
        if self.min_interval <= 0:
            return 0.0
        now = self._clock()
        slept = 0.0
        if self._last is not None:
            delta = now - self._last
            remaining = self.min_interval - delta
            if remaining > 0:
                self._sleep(remaining)
                slept = remaining
                now = self._clock()
        self._last = now
        return slept


class HttpFetcher:
    """GET helper with bounded retry + backoff and optional rate limiting."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 15.0,
        rate_limiter: Optional[RateLimiter] = None,
        urlopen: Optional[Callable[..., Any]] = None,
        sleep: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.rate_limiter = rate_limiter
        self._urlopen = urlopen or urllib.request.urlopen
        self._sleep = sleep
        self._random_uniform = random_uniform

    # -- internals --------------------------------------------------------- #
    def _backoff(self, attempt: int) -> float:
        delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        jitter = self._random_uniform(0, delay / 2) if delay > 0 else 0.0
        return delay + jitter

    def _request(self, url: str, headers: dict[str, str]) -> Response:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with self._urlopen(req, timeout=self.timeout) as resp:
            body = resp.read()
            status = getattr(resp, "status", None) or getattr(resp, "code", 200)
            hdrs = {k: v for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
            final_url = getattr(resp, "url", url)
        return Response(status=int(status), body=body, headers=hdrs, url=final_url)

    # -- public API -------------------------------------------------------- #
    def fetch(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> Response:
        """GET ``url`` returning a :class:`Response`, retrying transient errors."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        }
        if extra_headers:
            headers.update(extra_headers)

        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            if self.rate_limiter is not None:
                self.rate_limiter.wait()
            try:
                return self._request(url, headers)
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}"
                retryable = e.code == 429 or 500 <= e.code < 600
                if not retryable or attempt == self.max_attempts:
                    raise HttpError(
                        f"HTTP {e.code} for {redact_url(url)}", url, status=e.code
                    ) from e
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.IncompleteRead) as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt == self.max_attempts:
                    raise HttpError(
                        f"request failed for {redact_url(url)}: {last_error}", url
                    ) from e

            self._sleep(self._backoff(attempt))

        raise HttpError(f"request failed for {redact_url(url)}: {last_error}", url)

    def fetch_json(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> Any:
        resp = self.fetch(url, {**(extra_headers or {}), "Accept": "application/json"})
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise HttpError(f"invalid JSON from {redact_url(url)}: {e}", url, resp.status) from e

    def fetch_text(
        self, url: str, encoding: str = "utf-8", extra_headers: Optional[dict[str, str]] = None
    ) -> str:
        return self.fetch(url, extra_headers).text(encoding)

    def fetch_bytes(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> bytes:
        return self.fetch(url, extra_headers).body


class RobotsGate:
    """Honour ``robots.txt`` before fetching a URL.

    Parsing uses :class:`urllib.robotparser.RobotFileParser`, fed by the injected
    fetcher so this stays testable and never touches the network in tests. A host
    whose ``robots.txt`` is missing/unreachable is treated as *allowed* (the
    conservative default used by ``robotparser``), but that decision is logged by
    the caller-side via the returned boolean; callers should still respect site
    terms independently.
    """

    def __init__(self, fetcher: HttpFetcher, user_agent: str = DEFAULT_USER_AGENT):
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._cache: dict[str, Any] = {}

    def _parser_for(self, url: str):  # -> RobotFileParser-like
        from urllib import robotparser

        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._cache:
            rp = robotparser.RobotFileParser()
            robots_url = f"{origin}/robots.txt"
            try:
                text = self._fetcher.fetch_text(robots_url)
                rp.parse(text.splitlines())
            except Exception:  # noqa: BLE001 — unreachable robots => default allow
                rp = robotparser.RobotFileParser()
                rp.allow_all = True
            self._cache[origin] = rp
        return self._cache[origin]

    def can_fetch(self, url: str) -> bool:
        try:
            return bool(self._parser_for(url).can_fetch(self._user_agent, url))
        except Exception:  # noqa: BLE001
            return True

    def require(self, url: str) -> None:
        """Raise :class:`RobotsDisallowed` if fetching ``url`` is disallowed."""
        if not self.can_fetch(url):
            raise RobotsDisallowed(f"robots.txt disallows {redact_url(url)}")
