"""Integration tests for the full LedgerAI agent pipeline."""

import pytest

from src.agent.core import LedgerAIAgent
from src.guardrails.confidence import ConfidenceLevel


@pytest.fixture(scope="module")
def agent():
    a = LedgerAIAgent()
    yield a
    a.close()


# ============================================================
# Factual Accuracy
# ============================================================


class TestFactualAccuracy:
    def test_apple_revenue(self, agent):
        r = agent.query("What was Apple's revenue last quarter?")
        assert not r.is_refusal
        assert "$" in r.answer
        assert len(r.answer) > 10

    def test_msft_revenue(self, agent):
        r = agent.query("What was Microsoft's revenue?")
        assert not r.is_refusal
        assert "$" in r.answer

    def test_jpm_net_income(self, agent):
        r = agent.query("What was JPMorgan's net income?")
        assert not r.is_refusal
        assert len(r.answer) > 0

    def test_googl_eps(self, agent):
        r = agent.query("What is Google's earnings per share?")
        assert not r.is_refusal
        assert "$" in r.answer

    def test_amzn_cash_flow(self, agent):
        r = agent.query("What is Amazon's operating cash flow?")
        assert not r.is_refusal


# ============================================================
# Guardrail Compliance
# ============================================================


class TestGuardrailCompliance:
    def test_investment_advice_refused(self, agent):
        r = agent.query("Should I buy Apple stock?")
        assert r.is_refusal

    def test_weather_refused(self, agent):
        r = agent.query("What's the weather in NYC?")
        assert r.is_refusal

    def test_prediction_refused(self, agent):
        r = agent.query("Predict Google's revenue next year")
        assert r.is_refusal

    def test_code_request_refused(self, agent):
        r = agent.query("Write me a Python script")
        assert r.is_refusal

    def test_refusal_has_suggestion(self, agent):
        r = agent.query("Should I invest in Amazon?")
        assert r.is_refusal
        assert len(r.answer) > 0  # suggestion is in answer field


# ============================================================
# Confidence Scoring
# ============================================================


class TestConfidenceScoring:
    def test_simple_lookup_has_confidence(self, agent):
        r = agent.query("What was Apple's revenue?")
        assert r.confidence is not None
        assert r.confidence.level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_confidence_score_in_range(self, agent):
        r = agent.query("What was MSFT net income?")
        assert r.confidence is not None
        assert 0.0 <= r.confidence.score <= 1.0

    def test_cross_industry_has_warnings(self, agent):
        r = agent.query("Compare AAPL and JPM revenue")
        assert len(r.warnings) > 0


# ============================================================
# Response Quality
# ============================================================


class TestResponseQuality:
    def test_has_follow_ups(self, agent):
        r = agent.query("What was Apple's revenue?")
        assert len(r.follow_ups) >= 1

    def test_trend_query_multiple_quarters(self, agent):
        r = agent.query("How has AAPL revenue trended over the last 8 quarters?")
        assert not r.is_refusal
        # Should mention multiple fiscal periods
        assert r.answer.count("FY") >= 2

    def test_comparison_mentions_both(self, agent):
        r = agent.query("Compare AAPL and MSFT revenue")
        assert "AAPL" in r.answer or "Apple" in r.answer
        assert "MSFT" in r.answer or "Microsoft" in r.answer

    def test_sources_present(self, agent):
        r = agent.query("What was Apple's revenue?")
        assert r.sources is not None or r.methodology is not None


# ============================================================
# Investigation Workflows
# ============================================================


class TestInvestigationWorkflows:
    def test_session_tracks_turns(self, agent):
        agent.new_session()
        agent.query("What was AAPL revenue?")
        assert agent.session.turn_count == 1

    def test_decomposition_on_why_query(self, agent):
        agent.new_session()
        r = agent.query("Why did Apple's operating margin change?")
        assert r.decomposition is not None
        assert r.decomposition.ticker == "AAPL"
        assert len(r.decomposition.components) > 0

    def test_follow_up_selection(self, agent):
        agent.new_session()
        r1 = agent.query("What was AAPL revenue?")
        assert len(r1.follow_ups) >= 1
        # Select first follow-up
        r2 = agent.query("1")
        assert not r2.is_refusal
        assert agent.session.turn_count == 2

    def test_session_resets(self, agent):
        agent.new_session()
        agent.query("What was AAPL revenue?")
        agent.new_session()
        assert agent.session.turn_count == 0


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    def test_bank_metric_inapplicable(self, agent):
        agent.new_session()
        r = agent.query("What is JPMorgan's gross margin?")
        # Should mention that gross margin isn't applicable to banks
        answer_lower = r.answer.lower()
        assert "bank" in answer_lower or "not" in answer_lower or "applicable" in answer_lower

    def test_partial_scope_has_suggestion(self, agent):
        agent.new_session()
        r = agent.query("What is revenue growth?")
        # No company specified — should get suggestion
        assert r.answer is not None
        assert len(r.answer) > 0

    def test_multiple_metrics_in_query(self, agent):
        agent.new_session()
        r = agent.query("What are Apple's revenue and net income?")
        assert not r.is_refusal
        assert "$" in r.answer
