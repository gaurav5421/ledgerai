"""Tests for Output Validation — faithfulness checks and plausibility checks."""

from src.guardrails.provenance import ProvenanceRecord, SourceReference
from src.guardrails.validation import (
    validate_consistency,
    validate_faithfulness,
    validate_metric_value,
)

# ============================================================
# Faithfulness Validation
# ============================================================


class TestValidateFaithfulness:
    def _make_provenance(self, sources=None):
        prov = ProvenanceRecord()
        if sources:
            for s in sources:
                prov.sources.append(s)
        return prov

    def test_no_sources_returns_valid(self):
        result = validate_faithfulness("Revenue was $100B", ProvenanceRecord())
        assert result.is_valid
        assert result.warnings == []
        assert result.errors == []

    def test_matching_dollar_amount(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=94.93e9,
                    unit="USD",
                ),
            ]
        )
        result = validate_faithfulness("Apple's revenue was $94.9B", prov)
        assert result.is_valid
        assert result.errors == []

    def test_mismatched_dollar_amount_warning(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=94.93e9,
                    unit="USD",
                ),
            ]
        )
        # 10% off — should warn but not error
        result = validate_faithfulness("Apple's revenue was $85.0B", prov)
        assert result.is_valid  # warnings only, not errors
        assert len(result.warnings) > 0

    def test_grossly_wrong_dollar_amount_error(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=94.93e9,
                    unit="USD",
                ),
            ]
        )
        # Way off — should error
        result = validate_faithfulness("Apple's revenue was $200.0B", prov)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_matching_percentage(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="gross_margin",
                    value=0.462,
                    unit="percentage",
                ),
            ]
        )
        result = validate_faithfulness("Gross margin was 46.2%", prov)
        assert result.is_valid

    def test_mismatched_percentage_error(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="gross_margin",
                    value=0.462,
                    unit="percentage",
                ),
            ]
        )
        # Claimed 60% but source says 46.2%
        result = validate_faithfulness("Gross margin was 60.0%", prov)
        assert not result.is_valid

    def test_no_numbers_in_response(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=94.93e9,
                    unit="USD",
                ),
            ]
        )
        result = validate_faithfulness("Revenue has been growing steadily.", prov)
        assert result.is_valid

    def test_multiple_claims_mixed(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=94.93e9,
                    unit="USD",
                ),
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="net_income",
                    value=14.73e9,
                    unit="USD",
                ),
            ]
        )
        result = validate_faithfulness("Revenue was $94.9B and net income was $14.7B", prov)
        assert result.is_valid

    def test_tolerance_parameter(self):
        prov = self._make_provenance(
            [
                SourceReference(
                    ticker="AAPL",
                    filing_type="10-Q",
                    period_end="2024-09-28",
                    fiscal_label="FY2024 Q4",
                    metric="revenue",
                    value=100e9,
                    unit="USD",
                ),
            ]
        )
        # 8% off with 5% tolerance — should flag
        result = validate_faithfulness("Revenue was $92B", prov, tolerance=0.05)
        assert len(result.warnings) > 0 or len(result.errors) > 0

        # 8% off with 10% tolerance — should pass
        result = validate_faithfulness("Revenue was $92B", prov, tolerance=0.10)
        assert result.is_valid
        assert result.warnings == []


# ============================================================
# Metric Value Validation
# ============================================================


class TestValidateMetricValue:
    def test_normal_percentage(self):
        result = validate_metric_value("gross_margin", 0.45)
        assert result.is_valid

    def test_implausibly_high_percentage(self):
        result = validate_metric_value("gross_margin", 3.0)
        assert not result.is_valid

    def test_negative_revenue(self):
        result = validate_metric_value("revenue", -1e9)
        assert not result.is_valid

    def test_zero_value_warning(self):
        result = validate_metric_value("revenue", 0)
        assert result.is_valid  # warning, not error
        assert len(result.warnings) > 0

    def test_unknown_metric(self):
        result = validate_metric_value("nonexistent_metric", 42.0)
        assert result.is_valid


# ============================================================
# Consistency Validation
# ============================================================


class TestValidateConsistency:
    def test_consistent_gross_profit(self):
        result = validate_consistency(
            {
                "revenue": 100e9,
                "cost_of_revenue": 55e9,
                "gross_profit": 45e9,
            }
        )
        assert result.is_valid
        assert result.warnings == []

    def test_inconsistent_gross_profit(self):
        result = validate_consistency(
            {
                "revenue": 100e9,
                "cost_of_revenue": 55e9,
                "gross_profit": 50e9,  # Should be 45e9
            }
        )
        assert len(result.warnings) > 0

    def test_consistent_gross_margin(self):
        result = validate_consistency(
            {
                "gross_profit": 45e9,
                "revenue": 100e9,
                "gross_margin": 0.45,
            }
        )
        assert result.warnings == []

    def test_balance_sheet_imbalance(self):
        result = validate_consistency(
            {
                "total_assets": 100e9,
                "total_liabilities": 60e9,
                "total_equity": 30e9,  # Should be 40e9
            }
        )
        assert len(result.warnings) > 0

    def test_empty_values(self):
        result = validate_consistency({})
        assert result.is_valid
