"""Tests of the learning story (teacher dashboard data)."""

import logging

import httpx

import learning_story


def test_etherpad_api_key_is_not_logged(caplog, monkeypatch):
    """The request URL of the Etherpad API contains the API key. The key must not go into the logs."""
    caplog.set_level(logging.INFO)
    secret = "secret-etherpad-key"
    monkeypatch.setattr(learning_story, "ETHERPAD_ENABLED", True)
    monkeypatch.setattr(learning_story, "ETHERPAD_API_KEY", secret)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"code": 0, "data": {"text": "My pad"}}))
    real_get = httpx.get

    def fake_get(url, **kwargs):
        with httpx.Client(transport=transport) as client:
            return client.get(url, params=kwargs.get("params"))

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        text = learning_story.get_etherpad_text("student-1")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert text == "My pad"
    assert secret not in caplog.text
