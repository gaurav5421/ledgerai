"""Tests for the Confidence Scoring system."""

from src.guardrails.confidence import (
    ConfidenceFactor,
    ConfidenceLevel,
    classify_level,
    compute_confidence,
    score_ambiguity,
    score_calculation_complexity,
    score_comparability,
    score_data_availability,
    score_temporal_relevance,
)

# ============================================================
# Level Classification
# ============================================================


class TestClassifyLevel:
    def test_high(self):
        assert classify_level(0.8) == ConfidenceLevel.HIGH
        assert classify_level(1.0) == ConfidenceLevel.HIGH
        assert classify_level(0.95) == ConfidenceLevel.HIGH

    def test_medium(self):
        assert classify_level(0.5) == ConfidenceLevel.MEDIUM
        assert classify_level(0.79) == ConfidenceLevel.MEDIUM

    def test_low(self):
        assert classify_level(0.2) == ConfidenceLevel.LOW
        assert classify_level(0.49) == ConfidenceLevel.LOW

    def test_refuse(self):
        assert classify_level(0.0) == ConfidenceLevel.REFUSE
        assert classify_level(0.19) == ConfidenceLevel.REFUSE


# ============================================================
# Data Availability
# ============================================================


class TestDataAvailability:
    def test_all_metrics_available(self):
        factor = score_data_availability(["revenue"], ["revenue", "net_income"])
        assert factor.score >= 0.9

    def test_no_metrics_available(self):
        factor = score_data_availability(["revenue"], ["net_income", "eps_diluted"])
        assert factor.score < 0.5

    def test_partial_metrics(self):
        factor = score_data_availability(["revenue", "net_income"], ["revenue", "eps_diluted"])
        assert 0.3 < factor.score < 0.9

    def test_empty_requested(self):
        factor = score_data_availability([], ["revenue"])
        assert factor.score == 0.5

    def test_reason_includes_metric_names(self):
        factor = score_data_availability(["revenue"], ["revenue"])
        assert "revenue" in factor.reason


# ============================================================
# Calculation Complexity
# ============================================================


class TestCalculationComplexity:
    def test_direct_lookup(self):
        factor = score_calculation_complexity(is_direct_lookup=True)
        assert factor.score == 1.0

    def test_derived_with_components(self):
        factor = score_calculation_complexity(num_components=3)
        assert factor.score < 1.0

    def test_cross_period(self):
        factor = score_calculation_complexity(requires_cross_period=True)
        assert factor.score < 0.9

    def test_cross_company(self):
        factor = score_calculation_complexity(requires_cross_company=True)
        assert factor.score < 0.9

    def test_complex_combination(self):
        factor = score_calculation_complexity(
            num_components=4, requires_cross_period=True, requires_cross_company=True
        )
        assert factor.score < 0.7

    def test_minimum_score(self):
        factor = score_calculation_complexity(num_components=20)
        assert factor.score >= 0.3


# ============================================================
# Temporal Relevance
# ============================================================


class TestTemporalRelevance:
    def test_latest_data(self):
        factor = score_temporal_relevance("2024-12-31", "2024-12-31")
        assert factor.score == 1.0

    def test_stale_data(self):
        factor = score_temporal_relevance("2024-06-30", "2024-12-31")
        assert factor.score == 0.8

    def test_no_period(self):
        factor = score_temporal_relevance(None, "2024-12-31")
        assert factor.score == 0.5


# ============================================================
# Comparability
# ============================================================


class TestComparability:
    def test_single_company(self):
        factor = score_comparability(["AAPL"], [])
        assert factor.score == 1.0

    def test_multiple_no_warnings(self):
        factor = score_comparability(["AAPL", "MSFT"], [])
        assert factor.score == 0.9

    def test_multiple_with_warnings(self):
        factor = score_comparability(["AAPL", "JPM"], ["Cross-industry comparison warning"])
        assert factor.score < 0.9

    def test_many_warnings(self):
        factor = score_comparability(["AAPL", "JPM"], ["warn1", "warn2", "warn3"])
        assert factor.score < 0.6


# ============================================================
# Ambiguity
# ============================================================


class TestAmbiguity:
    def test_clear_question(self):
        factor = score_ambiguity(has_single_interpretation=True, metric_count=1)
        assert factor.score == 1.0

    def test_ambiguous(self):
        factor = score_ambiguity(has_single_interpretation=False)
        assert factor.score == 0.5

    def test_many_metrics(self):
        factor = score_ambiguity(has_single_interpretation=True, metric_count=5)
        assert factor.score < 1.0


# ============================================================
# Compute Confidence (Integration)
# ============================================================


class TestComputeConfidence:
    def test_empty_factors(self):
        result = compute_confidence([])
        assert result.level == ConfidenceLevel.LOW

    def test_all_high_factors(self):
        factors = [
            ConfidenceFactor("data_availability", 1.0, "All data available"),
            ConfidenceFactor("calculation_complexity", 1.0, "Direct lookup"),
            ConfidenceFactor("temporal_relevance", 1.0, "Latest data"),
            ConfidenceFactor("comparability", 1.0, "Single company"),
            ConfidenceFactor("ambiguity", 1.0, "Clear question"),
        ]
        result = compute_confidence(factors)
        assert result.level == ConfidenceLevel.HIGH
        assert result.score == 1.0

    def test_all_low_factors(self):
        factors = [
            ConfidenceFactor("data_availability", 0.1, "No data"),
            ConfidenceFactor("calculation_complexity", 0.1, "Complex"),
            ConfidenceFactor("temporal_relevance", 0.1, "Old data"),
            ConfidenceFactor("comparability", 0.1, "Invalid comparison"),
            ConfidenceFactor("ambiguity", 0.1, "Ambiguous"),
        ]
        result = compute_confidence(factors)
        assert result.level in (ConfidenceLevel.REFUSE, ConfidenceLevel.LOW)

    def test_mixed_factors(self):
        factors = [
            ConfidenceFactor("data_availability", 0.8, "Most data available"),
            ConfidenceFactor("calculation_complexity", 0.6, "Derived metric"),
            ConfidenceFactor("temporal_relevance", 1.0, "Latest data"),
            ConfidenceFactor("comparability", 1.0, "Single company"),
            ConfidenceFactor("ambiguity", 0.8, "Mostly clear"),
        ]
        result = compute_confidence(factors)
        assert result.level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_result_has_summary(self):
        factors = [ConfidenceFactor("data_availability", 1.0, "All data")]
        result = compute_confidence(factors)
        assert len(result.summary) > 0

    def test_should_answer_property(self):
        factors = [ConfidenceFactor("data_availability", 1.0, "All data")]
        result = compute_confidence(factors)
        assert result.should_answer is True

    def test_data_availability_weighted_highest(self):
        # When only data_availability is low, overall should drop significantly
        high = compute_confidence(
            [
                ConfidenceFactor("data_availability", 1.0, ""),
                ConfidenceFactor("calculation_complexity", 1.0, ""),
            ]
        )
        low_data = compute_confidence(
            [
                ConfidenceFactor("data_availability", 0.2, ""),
                ConfidenceFactor("calculation_complexity", 1.0, ""),
            ]
        )
        assert high.score > low_data.score
