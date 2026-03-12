"""Tests for the Metric Registry — financial metric definitions and lookups."""

import pytest

from src.context.metric_registry import (
    METRICS,
    format_metric_context,
    get_all_metric_ids,
    get_caveats_for_metrics,
    get_components,
    get_metric,
    get_metrics_by_category,
    is_applicable_to_company,
)


class TestMetricCount:
    def test_has_expected_number_of_metrics(self):
        assert len(METRICS) >= 20  # At least 20 metrics registered

    def test_all_metric_ids_matches_dict(self):
        assert set(get_all_metric_ids()) == set(METRICS.keys())


class TestKnownMetrics:
    @pytest.mark.parametrize(
        "metric_id",
        [
            "revenue",
            "gross_margin",
            "operating_margin",
            "net_income",
            "eps_diluted",
            "free_cash_flow",
            "net_interest_income",
            "operating_income",
            "net_margin",
            "capex",
        ],
    )
    def test_known_metric_exists(self, metric_id):
        assert get_metric(metric_id) is not None

    def test_unknown_metric_returns_none(self):
        assert get_metric("nonexistent_metric") is None


class TestMetricProperties:
    def test_revenue_properties(self):
        m = get_metric("revenue")
        assert m.unit == "USD"
        assert m.category == "revenue"
        assert m.components == []

    def test_gross_margin_properties(self):
        m = get_metric("gross_margin")
        assert m.unit == "percentage"
        assert "gross_profit" in m.components
        assert "revenue" in m.components

    def test_free_cash_flow_components(self):
        m = get_metric("free_cash_flow")
        assert "operating_cash_flow" in m.components
        assert "capex" in m.components

    def test_eps_diluted_unit(self):
        m = get_metric("eps_diluted")
        assert m.unit == "USD/share"

    def test_debt_to_equity_unit(self):
        m = get_metric("debt_to_equity")
        assert m.unit == "ratio"


class TestCategories:
    def test_revenue_category(self):
        metrics = get_metrics_by_category("revenue")
        ids = [m.id for m in metrics]
        assert "revenue" in ids

    def test_per_share_category(self):
        metrics = get_metrics_by_category("per_share")
        ids = [m.id for m in metrics]
        assert "eps_basic" in ids
        assert "eps_diluted" in ids

    def test_cash_flow_category(self):
        metrics = get_metrics_by_category("cash_flow")
        ids = [m.id for m in metrics]
        assert "free_cash_flow" in ids
        assert "operating_cash_flow" in ids

    def test_empty_category(self):
        metrics = get_metrics_by_category("nonexistent")
        assert metrics == []


class TestBankApplicability:
    def test_gross_margin_not_for_banks(self):
        assert is_applicable_to_company("gross_margin", "banking") is False

    def test_gross_profit_not_for_banks(self):
        assert is_applicable_to_company("gross_profit", "banking") is False

    def test_free_cash_flow_not_for_banks(self):
        assert is_applicable_to_company("free_cash_flow", "banking") is False

    def test_current_ratio_not_for_banks(self):
        assert is_applicable_to_company("current_ratio", "banking") is False

    def test_net_interest_income_for_banks(self):
        assert is_applicable_to_company("net_interest_income", "banking") is True

    def test_revenue_for_all(self):
        assert is_applicable_to_company("revenue", "banking") is True
        assert is_applicable_to_company("revenue", "tech_software") is True

    def test_unknown_metric_not_applicable(self):
        assert is_applicable_to_company("fake_metric", "banking") is False


class TestComponents:
    def test_revenue_no_components(self):
        assert get_components("revenue") == []

    def test_derived_metric_has_components(self):
        comps = get_components("free_cash_flow")
        assert len(comps) >= 2

    def test_unknown_metric_no_components(self):
        assert get_components("nonexistent") == []


class TestCaveats:
    def test_every_metric_has_caveats(self):
        for metric_id, m in METRICS.items():
            assert len(m.caveats) >= 1, f"{metric_id} has no caveats"

    def test_get_caveats_returns_dict(self):
        caveats = get_caveats_for_metrics(["revenue", "net_income"])
        assert "revenue" in caveats
        assert "net_income" in caveats
        assert isinstance(caveats["revenue"], list)

    def test_get_caveats_ignores_unknown(self):
        caveats = get_caveats_for_metrics(["revenue", "fake"])
        assert "revenue" in caveats
        assert "fake" not in caveats


class TestFormatMetricContext:
    def test_format_includes_name(self):
        text = format_metric_context("revenue")
        assert "Revenue" in text

    def test_format_includes_formula(self):
        text = format_metric_context("gross_margin")
        assert "gross_profit" in text.lower()

    def test_format_unknown_metric(self):
        text = format_metric_context("nonexistent")
        assert "Unknown" in text

    def test_format_includes_caveats(self):
        text = format_metric_context("revenue")
        assert "Caveats" in text
