"""Output Validation — sanity checks on agent responses.

Checks calculated values are within plausible ranges, cross-references
with the database, and verifies internal consistency.
"""

from dataclasses import dataclass

from src.context.metric_registry import get_metric


@dataclass
class ValidationResult:
    is_valid: bool
    warnings: list[str]
    errors: list[str]


def validate_metric_value(metric_id: str, value: float, ticker: str = "") -> ValidationResult:
    """Check if a calculated metric value is within plausible range."""
    warnings = []
    errors = []

    m = get_metric(metric_id)
    if not m:
        return ValidationResult(True, [], [])

    # Check for obviously wrong values
    if m.unit == "percentage":
        if value > 2.0:  # Over 200%
            errors.append(
                f"{m.name} = {value*100:.1f}% seems implausibly high. "
                f"Check if the value should be a decimal (e.g., 0.45 not 45)."
            )
        if value < -2.0:
            errors.append(f"{m.name} = {value*100:.1f}% seems implausibly negative.")

    if m.unit == "ratio":
        if abs(value) > 100:
            warnings.append(f"{m.name} = {value:.1f} is an extreme ratio. Verify the calculation.")

    if m.unit == "USD":
        if value == 0:
            warnings.append(f"{m.name} is exactly zero — verify this is correct.")
        # Revenue shouldn't be negative (though net income can be)
        if metric_id == "revenue" and value < 0:
            errors.append(f"Revenue cannot be negative (got ${value/1e9:.1f}B).")

    # Check against typical ranges if available
    if m.typical_ranges:
        for industry, (lo, hi) in m.typical_ranges.items():
            if lo is not None and hi is not None:
                if ticker and _industry_matches(ticker, industry):
                    if m.unit == "USD" and (value < lo * 0.1 or value > hi * 10):
                        warnings.append(
                            f"{m.name} = {_fmt(value, m.unit)} is outside "
                            f"typical range for {industry} "
                            f"({_fmt(lo, m.unit)} - {_fmt(hi, m.unit)}). "
                            f"This may be correct but warrants attention."
                        )

    is_valid = len(errors) == 0
    return ValidationResult(is_valid, warnings, errors)


def validate_consistency(values: dict[str, float]) -> ValidationResult:
    """Check internal consistency of multiple values in a response."""
    warnings = []
    errors = []

    # Gross profit = revenue - cost_of_revenue
    if all(k in values for k in ("revenue", "cost_of_revenue", "gross_profit")):
        expected = values["revenue"] - values["cost_of_revenue"]
        actual = values["gross_profit"]
        if abs(expected - actual) > abs(expected) * 0.01:  # 1% tolerance
            warnings.append(
                f"Gross profit inconsistency: revenue ({values['revenue']/1e9:.1f}B) - "
                f"COGS ({values['cost_of_revenue']/1e9:.1f}B) = "
                f"{expected/1e9:.1f}B, but gross_profit = {actual/1e9:.1f}B"
            )

    # Gross margin = gross_profit / revenue
    if all(k in values for k in ("gross_profit", "revenue", "gross_margin")):
        if values["revenue"] != 0:
            expected = values["gross_profit"] / values["revenue"]
            actual = values["gross_margin"]
            if abs(expected - actual) > 0.01:
                warnings.append(
                    f"Gross margin inconsistency: {actual*100:.1f}% reported "
                    f"but {expected*100:.1f}% calculated from components"
                )

    # Operating margin check
    if all(k in values for k in ("operating_income", "revenue", "operating_margin")):
        if values["revenue"] != 0:
            expected = values["operating_income"] / values["revenue"]
            actual = values["operating_margin"]
            if abs(expected - actual) > 0.01:
                warnings.append(
                    f"Operating margin inconsistency: {actual*100:.1f}% reported "
                    f"but {expected*100:.1f}% calculated"
                )

    # Net margin check
    if all(k in values for k in ("net_income", "revenue", "net_margin")):
        if values["revenue"] != 0:
            expected = values["net_income"] / values["revenue"]
            actual = values["net_margin"]
            if abs(expected - actual) > 0.01:
                warnings.append("Net margin inconsistency")

    # Balance sheet: assets ≈ liabilities + equity
    if all(k in values for k in ("total_assets", "total_liabilities", "total_equity")):
        expected = values["total_liabilities"] + values["total_equity"]
        actual = values["total_assets"]
        if actual != 0 and abs(expected - actual) / abs(actual) > 0.02:
            warnings.append(
                f"Balance sheet doesn't balance: A={actual/1e9:.1f}B vs " f"L+E={expected/1e9:.1f}B"
            )

    is_valid = len(errors) == 0
    return ValidationResult(is_valid, warnings, errors)


def _fmt(value: float, unit: str) -> str:
    if unit == "USD":
        return f"${value/1e9:.1f}B"
    elif unit == "percentage":
        return f"{value*100:.1f}%"
    return f"{value:.2f}"


def _industry_matches(ticker: str, industry_key: str) -> bool:
    from src.context.domain_rules import get_company_industry

    company_industry = get_company_industry(ticker)
    return industry_key in company_industry or company_industry in industry_key
