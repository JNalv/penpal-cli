"""Tests for cost.py"""
import pytest
from penpal.cost import estimate_cost, format_cost


def test_estimate_sonnet():
    # 1M input + 1M output for sonnet = $1.50 + $7.50 = $9.00
    cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert cost == pytest.approx(9.0)


def test_estimate_haiku():
    cost = estimate_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert cost == pytest.approx(2.40)


def test_estimate_unknown_model():
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


def test_format_cost_zero():
    assert format_cost(0.0) == "—"


def test_format_cost_small():
    result = format_cost(0.001)
    assert result.startswith("$")


def test_format_cost_normal():
    assert format_cost(1.23) == "$1.23"
