import json
import urllib.error

import pytest

from india_road_safety.http import (
    HttpError,
    HttpFetcher,
    RateLimiter,
    RobotsDisallowed,
    RobotsGate,
    redact_url,
)


class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None, url=""):
        self._body = body
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self.url = url

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    """Returns queued responses/raises; records every call."""

    def __init__(self, behaviors):
        self.behaviors = list(behaviors)
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(req.full_url)
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


def no_sleep(_):
    pass


def test_fetch_json_success():
    body = json.dumps({"ok": True, "n": 5}).encode()
    fu = FakeUrlopen([FakeResponse(body=body, url="https://x/y")])
    fetcher = HttpFetcher(urlopen=fu, sleep=no_sleep)
    assert fetcher.fetch_json("https://x/y") == {"ok": True, "n": 5}


def test_fetch_retries_then_succeeds():
    sleeps = []
    fu = FakeUrlopen([
        urllib.error.URLError("boom"),
        urllib.error.URLError("boom"),
        FakeResponse(body=b"hi"),
    ])
    fetcher = HttpFetcher(
        urlopen=fu, sleep=sleeps.append, random_uniform=lambda a, b: 0.0,
        base_delay=1.0,
    )
    resp = fetcher.fetch("https://x/y")
    assert resp.text() == "hi"
    assert len(fu.calls) == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff, no jitter


def test_fetch_raises_after_max_attempts():
    fu = FakeUrlopen([urllib.error.URLError("boom")] * 3)
    fetcher = HttpFetcher(urlopen=fu, sleep=no_sleep, random_uniform=lambda a, b: 0.0)
    with pytest.raises(HttpError):
        fetcher.fetch("https://x/y")
    assert len(fu.calls) == 3


def test_http_404_not_retried():
    err = urllib.error.HTTPError("https://x/y", 404, "Not Found", {}, None)
    fu = FakeUrlopen([err])
    fetcher = HttpFetcher(urlopen=fu, sleep=no_sleep)
    with pytest.raises(HttpError) as exc:
        fetcher.fetch("https://x/y")
    assert exc.value.status == 404
    assert len(fu.calls) == 1  # no retry on 4xx


def test_http_503_is_retried():
    err = urllib.error.HTTPError("https://x/y", 503, "Unavailable", {}, None)
    fu = FakeUrlopen([err, FakeResponse(body=b"ok")])
    fetcher = HttpFetcher(urlopen=fu, sleep=no_sleep, random_uniform=lambda a, b: 0.0)
    assert fetcher.fetch("https://x/y").text() == "ok"
    assert len(fu.calls) == 2


def test_http_error_message_is_redacted():
    err = urllib.error.HTTPError("https://x/y", 403, "Forbidden", {}, None)
    fu = FakeUrlopen([err])
    fetcher = HttpFetcher(urlopen=fu, sleep=no_sleep)
    with pytest.raises(HttpError) as exc:
        fetcher.fetch("https://api.example/endpoint?app_key=SECRETVALUE&q=1")
    assert "SECRETVALUE" not in str(exc.value)
    assert "redacted" in str(exc.value)


def test_redact_url():
    out = redact_url("https://api.example/data?app_id=abc&app_key=def&page=2")
    assert "abc" not in out and "def" not in out
    assert "page=2" in out


def test_rate_limiter_enforces_interval():
    clock = [0.0]
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        clock[0] += seconds

    rl = RateLimiter(min_interval=2.0, clock=lambda: clock[0], sleep=fake_sleep)
    rl.wait()            # first: no wait
    assert slept == []
    clock[0] += 0.5      # only 0.5s elapsed
    rl.wait()            # must wait remaining 1.5s
    assert slept == [1.5]


class _FakeTextFetcher:
    def __init__(self, text):
        self.text = text

    def fetch_text(self, url, encoding="utf-8", extra_headers=None):
        return self.text


def test_robots_gate_allow_and_deny():
    robots = "User-agent: *\nDisallow: /private/\n"
    gate = RobotsGate(_FakeTextFetcher(robots), user_agent="test-agent")
    assert gate.can_fetch("https://site.example/public/page") is True
    assert gate.can_fetch("https://site.example/private/secret") is False
    with pytest.raises(RobotsDisallowed):
        gate.require("https://site.example/private/secret")


def test_robots_gate_unreachable_defaults_allow():
    class Boom:
        def fetch_text(self, *a, **k):
            raise RuntimeError("no robots")

    gate = RobotsGate(Boom())
    assert gate.can_fetch("https://site.example/anything") is True
