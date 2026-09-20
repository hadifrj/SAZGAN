from __future__ import annotations

import requests

from native_client.api_client import ApiError, SazganClient


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class RetrySession:
    def __init__(self, failures, response):
        self.failures = failures
        self.response = response
        self.calls = 0

    def request(self, method, url, timeout=None, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise requests.exceptions.ConnectionError("temporary network failure")
        return self.response


class HttpSession:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def request(self, method, url, timeout=None, **kwargs):
        self.calls += 1
        return self.response


def client_with_session(session):
    client = SazganClient("http://127.0.0.1:5000")
    client.session = session
    return client


def test_get_json_retries_network_failure_twice(monkeypatch):
    monkeypatch.setattr("native_client.api_client.time.sleep", lambda _: None)
    session = RetrySession(2, Response(200, {"ok": True}))
    client = client_with_session(session)

    assert client.get_json("/health") == {"ok": True}
    assert session.calls == 3


def test_get_json_does_not_retry_http_403(monkeypatch):
    monkeypatch.setattr("native_client.api_client.time.sleep", lambda _: None)
    session = HttpSession(Response(403))
    client = client_with_session(session)

    try:
        client.get_json("/forbidden")
    except ApiError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("ApiError was not raised")
    assert session.calls == 1


class CsrfRetrySession:
    """A stale CSRF token: first POST -> 400, token-refresh GET -> new
    token, retried POST -> success."""

    def __init__(self):
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append((method, url))
        if method == "GET" and url.endswith("/api/native/csrf-token"):
            return Response(200, {"csrf_token": "new-token"})
        if method == "POST":
            posts = [c for c in self.calls if c[0] == "POST"]
            if len(posts) == 1:
                return Response(400, {"error": "bad csrf"})
            return Response(200, {"ok": True})
        return Response(200, {})


def test_post_form_retries_once_after_csrf_token_refresh(monkeypatch):
    monkeypatch.setattr("native_client.api_client.time.sleep", lambda _: None)
    session = CsrfRetrySession()
    client = client_with_session(session)
    client.csrf_token = "stale-token"

    response = client._post_form("/bad", data={"x": "1"})
    assert response.status_code == 200
    assert client.csrf_token == "new-token"
    assert len([c for c in session.calls if c[0] == "POST"]) == 2


def test_post_form_stops_after_one_csrf_retry_if_still_400(monkeypatch):
    monkeypatch.setattr("native_client.api_client.time.sleep", lambda _: None)
    session = HttpSession(Response(400, {"error": "bad request"}))
    client = client_with_session(session)
    client.csrf_token = "test-token"

    response = client._post_form("/bad", data={"x": "1"})
    assert response.status_code == 400
    # one POST attempt + one refresh GET attempt, then stop - no infinite loop
    assert session.calls == 2
