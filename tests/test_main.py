"""Unit tests for main.py (Keepa bot)."""

from __future__ import annotations

import json
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import (
    parse_product_catalog,
    parse_bool,
    pick_latest_price,
    extract_current_price,
    calculate_profit,
    build_webhook_payload,
    ProductConfig,
    ProfitResult,
)


class TestParseBool:
    def test_true_values(self):
        assert parse_bool("1") is True
        assert parse_bool("true") is True
        assert parse_bool("True") is True
        assert parse_bool("TRUE") is True
        assert parse_bool("yes") is True
        assert parse_bool("on") is True

    def test_false_values(self):
        assert parse_bool("0") is False
        assert parse_bool("false") is False
        assert parse_bool("no") is False
        assert parse_bool("off") is False
        assert parse_bool("") is False

    def test_none_returns_default(self):
        assert parse_bool(None) is False
        assert parse_bool(None, default=True) is True


class TestParseProductCatalog:
    def test_valid_catalog(self):
        raw = json.dumps([
            {"asin": "B001", "cost_price": 1000},
            {"asin": "B002", "cost_price": 2000, "min_profit": 100, "min_margin": 0.1},
        ])
        configs = parse_product_catalog(raw)
        assert len(configs) == 2
        assert configs[0].asin == "B001"
        assert configs[0].cost_price == 1000
        assert configs[1].min_profit == 100
        assert configs[1].min_margin == 0.1

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="JSON"):
            parse_product_catalog("not valid json")

    def test_empty_array(self):
        with pytest.raises(ValueError, match="1件以上"):
            parse_product_catalog("[]")

    def test_missing_required_fields(self):
        with pytest.raises(ValueError, match="必須"):
            parse_product_catalog('[{"asin": "B001"}]')


class TestPickLatestPrice:
    def test_returns_last_positive_value(self):
        assert pick_latest_price([100, 200, 300]) == 300
        assert pick_latest_price([100, -1, 200]) == 200

    def test_returns_none_for_empty(self):
        assert pick_latest_price([]) is None
        assert pick_latest_price(None) is None

    def test_returns_none_for_all_invalid(self):
        assert pick_latest_price([-1, -1, 0]) is None


class TestExtractCurrentPrice:
    def test_extracts_from_buybox(self):
        product = {"stats": {"current": {"buyBox": 12345}}}
        assert extract_current_price(product) == 123.45

    def test_fallback_to_new(self):
        product = {"stats": {"current": {"new": 5000}}}
        assert extract_current_price(product) == 50.0

    def test_fallback_to_history(self):
        product = {"stats": {"current": {}}, "buyBoxPriceHistory": [1000, 2000]}
        assert extract_current_price(product) == 20.0

    def test_returns_none_when_no_price(self):
        product = {"stats": {"current": {}}}
        assert extract_current_price(product) is None


class TestCalculateProfit:
    def test_basic_calculation(self):
        profit, margin = calculate_profit(
            current_price=10000,
            cost_price=5000,
            fee_rate=0.15,
            fba_fee=440,
        )
        expected_profit = 10000 * 0.85 - 440 - 5000
        assert profit == pytest.approx(expected_profit)
        assert margin == pytest.approx(expected_profit / 10000)


class TestBuildWebhookPayload:
    def test_builds_correct_payload(self):
        config = ProductConfig(
            asin="B001",
            cost_price=1000,
            min_profit=0,
            min_margin=0,
            min_sale_price=None,
            title="Test Product",
        )
        result = ProfitResult(
            asin="B001",
            current_price=2000,
            profit=500,
            margin=0.25,
            config=config,
            product_title="Test Product",
        )
        payload = build_webhook_payload([result])
        assert "text" in payload
        assert "B001" in payload["text"]
        assert "Test Product" in payload["text"]
