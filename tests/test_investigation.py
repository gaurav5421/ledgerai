"""Tests for Investigation Workflows — decomposition, follow-ups, and session."""

import pytest

from src.agent.retrieval import get_db
from src.investigation.decomposition import (
    DecompositionResult,
    decompose_metric_change,
    get_decomposition_paths,
    has_decomposition,
)
from src.investigation.follow_ups import generate_contextual_follow_ups
from src.investigation.session import InvestigationDepth, InvestigationSession

# ============================================================
# Decomposition Paths
# ============================================================


class TestDecompositionPaths:
    @pytest.mark.parametrize(
        "metric_id",
        [
            "gross_margin",
            "operating_margin",
            "net_margin",
            "net_income",
            "eps_diluted",
            "free_cash_flow",
        ],
    )
    def test_has_decomposition(self, metric_id):
        assert has_decomposition(metric_id) is True

    @pytest.mark.parametrize(
        "metric_id",
        [
            "total_assets",
            "current_ratio",
            "shares_outstanding",
        ],
    )
    def test_no_decomposition(self, metric_id):
        assert has_decomposition(metric_id) is False

    def test_gross_margin_path(self):
        paths = get_decomposition_paths("gross_margin")
        assert len(paths) >= 1
        label, desc, components = paths[0]
        assert label == "Margin Bridge"
        assert "revenue" in components

    def test_operating_margin_path(self):
        paths = get_decomposition_paths("operating_margin")
        assert len(paths) >= 1
        assert paths[0][0] == "Expense Decomposition"

    def test_eps_path(self):
        paths = get_decomposition_paths("eps_diluted")
        assert len(paths) >= 1
        _, _, components = paths[0]
        assert "net_income" in components

    def test_no_paths_for_unknown(self):
        assert get_decomposition_paths("fake_metric") == []


# ============================================================
# Decomposition Execution (with real DB)
# ============================================================


@pytest.fixture(scope="module")
def conn():
    c = get_db()
    yield c
    c.close()


class TestDecomposeMetricChange:
    def test_decompose_gross_margin(self, conn):
        result = decompose_metric_change(conn, "AAPL", "gross_margin")
        assert result is not None
        assert isinstance(result, DecompositionResult)
        assert result.ticker == "AAPL"
        assert result.metric_id == "gross_margin"
        assert len(result.components) > 0

    def test_decompose_operating_margin(self, conn):
        result = decompose_metric_change(conn, "MSFT", "operating_margin")
        assert result is not None
        assert len(result.components) > 0
        assert result.driver  # driver string is not empty

    def test_decompose_net_income(self, conn):
        result = decompose_metric_change(conn, "GOOGL", "net_income")
        assert result is not None

    def test_decompose_nonexistent_returns_none(self, conn):
        result = decompose_metric_change(conn, "AAPL", "total_assets")
        assert result is None

    def test_format_text(self, conn):
        result = decompose_metric_change(conn, "AAPL", "operating_margin")
        assert result is not None
        text = result.format_text()
        assert "Decomposition:" in text
        assert "Primary driver:" in text or "driver" in text.lower()

    def test_component_change_has_values(self, conn):
        result = decompose_metric_change(conn, "AAPL", "gross_margin")
        if result and result.components:
            comp = result.components[0]
            assert comp.latest_value != 0 or comp.prior_value != 0
            assert comp.unit is not None
            assert comp.latest_period is not None


# ============================================================
# Investigation Session
# ============================================================


class TestInvestigationSession:
    def test_new_session(self):
        s = InvestigationSession()
        assert s.is_new is True
        assert s.turn_count == 0
        assert s.active_tickers == []

    def test_record_turn(self):
        s = InvestigationSession()
        s.record_turn("What was AAPL revenue?", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY)
        assert s.is_new is False
        assert s.turn_count == 1
        assert "AAPL" in s.active_tickers

    def test_discussed_metrics(self):
        s = InvestigationSession()
        s.record_turn("test", ["AAPL"], ["revenue", "net_income"], InvestigationDepth.SUMMARY)
        discussed = s.get_discussed_metrics("AAPL")
        assert "revenue" in discussed
        assert "net_income" in discussed

    def test_discussed_metrics_empty_ticker(self):
        s = InvestigationSession()
        assert s.get_discussed_metrics("AAPL") == set()

    def test_multiple_turns_accumulate(self):
        s = InvestigationSession()
        s.record_turn("q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY)
        s.record_turn("q2", ["MSFT"], ["net_income"], InvestigationDepth.DETAIL)
        assert s.turn_count == 2
        assert "AAPL" in s.active_tickers
        assert "MSFT" in s.active_tickers

    def test_follow_ups_stored(self):
        s = InvestigationSession()
        s.record_turn(
            "q1",
            ["AAPL"],
            ["revenue"],
            InvestigationDepth.SUMMARY,
            follow_ups=["Follow-up 1", "Follow-up 2"],
        )
        assert s.get_last_follow_ups() == ["Follow-up 1", "Follow-up 2"]

    def test_no_follow_ups_when_empty(self):
        s = InvestigationSession()
        assert s.get_last_follow_ups() == []


# ============================================================
# Follow-up Selection
# ============================================================


class TestFollowUpSelection:
    def test_select_first(self):
        s = InvestigationSession()
        s.record_turn(
            "q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY, follow_ups=["F1", "F2", "F3"]
        )
        assert s.is_follow_up_selection("1") == 0

    def test_select_second(self):
        s = InvestigationSession()
        s.record_turn(
            "q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY, follow_ups=["F1", "F2"]
        )
        assert s.is_follow_up_selection("2") == 1

    def test_text_not_selection(self):
        s = InvestigationSession()
        s.record_turn("q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY, follow_ups=["F1"])
        assert s.is_follow_up_selection("hello") is None

    def test_no_follow_ups_no_selection(self):
        s = InvestigationSession()
        assert s.is_follow_up_selection("1") is None


# ============================================================
# Depth Classification
# ============================================================


class TestDepthClassification:
    def test_decomposition_why(self):
        s = InvestigationSession()
        depth = s.classify_depth("Why did margin change?", ["AAPL"], ["gross_margin"])
        assert depth == InvestigationDepth.DECOMPOSITION

    def test_decomposition_what_drove(self):
        s = InvestigationSession()
        depth = s.classify_depth("What drove the EPS change?", ["AAPL"], ["eps_diluted"])
        assert depth == InvestigationDepth.DECOMPOSITION

    def test_comparison_multiple_tickers(self):
        s = InvestigationSession()
        depth = s.classify_depth("Revenue comparison", ["AAPL", "MSFT"], ["revenue"])
        assert depth == InvestigationDepth.COMPARISON

    def test_comparison_keyword(self):
        s = InvestigationSession()
        depth = s.classify_depth("Compare AAPL vs MSFT", ["AAPL", "MSFT"], ["revenue"])
        assert depth == InvestigationDepth.COMPARISON

    def test_detail_trend(self):
        s = InvestigationSession()
        depth = s.classify_depth("How has revenue trended?", ["AAPL"], ["revenue"])
        assert depth == InvestigationDepth.DETAIL

    def test_summary_default(self):
        s = InvestigationSession()
        depth = s.classify_depth("What was revenue?", ["AAPL"], ["revenue"])
        assert depth == InvestigationDepth.SUMMARY

    def test_detail_when_already_discussed(self):
        s = InvestigationSession()
        s.record_turn("q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY)
        depth = s.classify_depth("What was revenue?", ["AAPL"], ["revenue"])
        assert depth == InvestigationDepth.DETAIL


# ============================================================
# Context Summary
# ============================================================


class TestContextSummary:
    def test_none_when_empty(self):
        s = InvestigationSession()
        assert s.build_context_summary() is None

    def test_has_content_after_turn(self):
        s = InvestigationSession()
        s.record_turn("q1", ["AAPL"], ["revenue"], InvestigationDepth.SUMMARY)
        summary = s.build_context_summary()
        assert summary is not None
        assert "AAPL" in summary
        assert "Turn" in summary


# ============================================================
# Contextual Follow-ups
# ============================================================


class TestContextualFollowUps:
    def test_generates_follow_ups(self, conn):
        follow_ups = generate_contextual_follow_ups(
            conn, ["AAPL"], ["revenue"], "What was Apple's revenue?"
        )
        assert len(follow_ups) >= 1
        assert len(follow_ups) <= 3

    def test_follow_ups_are_strings(self, conn):
        follow_ups = generate_contextual_follow_ups(
            conn, ["AAPL"], ["gross_margin"], "What was AAPL gross margin?"
        )
        for f in follow_ups:
            assert isinstance(f, str)
            assert len(f) > 0

    def test_follow_ups_no_duplicates(self, conn):
        follow_ups = generate_contextual_follow_ups(
            conn, ["AAPL"], ["revenue", "net_income"], "AAPL financials"
        )
        assert len(follow_ups) == len(set(f.lower() for f in follow_ups))
