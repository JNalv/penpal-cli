"""Tests for builder.py"""
from penpal.builder import build_single_request, resolve_model


def test_resolve_alias():
    assert resolve_model("haiku") == "claude-haiku-4-5-20251001"
    assert resolve_model("sonnet") == "claude-sonnet-4-20250514"
    assert resolve_model("opus") == "claude-opus-4-20250514"


def test_resolve_passthrough():
    full = "claude-some-future-model"
    assert resolve_model(full) == full


def test_build_single_request_basic():
    req = build_single_request("Hello", "claude-sonnet-4-20250514", 1000)
    assert req["params"]["model"] == "claude-sonnet-4-20250514"
    assert req["params"]["max_tokens"] == 1000
    assert req["params"]["messages"][0]["content"] == "Hello"
    assert "custom_id" in req
    assert "system" not in req["params"]


def test_build_single_request_with_system():
    req = build_single_request("Q", "model", 100, system_prompt="Be helpful.")
    assert req["params"]["system"] == "Be helpful."


def test_build_single_request_custom_id():
    req = build_single_request("Q", "model", 100, custom_id="my-id")
    assert req["custom_id"] == "my-id"
