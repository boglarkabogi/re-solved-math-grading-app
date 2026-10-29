"""No test may reach a model endpoint.

Both doors are shut by the autouse `no_network` fixture: the grading engine
goes through llm.chat, the recognition goes straight out through requests.
"""

import pytest
import requests

from motor import grading


def test_the_grading_engine_cannot_reach_the_network():
    with pytest.raises(RuntimeError, match="tried to call a model"):
        grading.grade("Mennyi lnko(12, 18)?", "6", "12 = 2*6")


def test_an_http_call_cannot_reach_the_network():
    """The recognition uses requests directly, so llm.chat alone is not enough."""
    with pytest.raises(RuntimeError, match="tried to make an HTTP request"):
        requests.post("https://integrate.api.nvidia.com/v1/chat/completions", json={})


def test_a_get_cannot_slip_through_either():
    with pytest.raises(RuntimeError, match="tried to make an HTTP request"):
        requests.get("https://integrate.api.nvidia.com/v1/models")


def test_a_test_may_still_stub_its_own_http_call(monkeypatch):
    """The guard must not stop a test from serving a canned response."""
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: "canned")

    assert requests.post("https://example.invalid") == "canned"
