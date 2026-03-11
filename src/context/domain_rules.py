"""Domain rules — business logic and constraints for financial analysis.

Encodes knowledge about fiscal calendars, seasonality, comparison validity,
and industry-specific rules that the agent needs for reliable answers.
"""

from dataclasses import dataclass

# ============================================================
# Fiscal Year Mapping
# ============================================================

# Company fiscal year end: (month, day) of fiscal year end
FISCAL_YEAR_ENDS: dict[str, tuple[int, int]] = {
    "AAPL": (9, 30),  # Apple: fiscal year ends late September
    "MSFT": (6, 30),  # Microsoft: fiscal year ends June 30
    "GOOGL": (12, 31),  # Alphabet: calendar year
    "AMZN": (12, 31),  # Amazon: calendar year
    "JPM": (12, 31),  # JPMorgan: calendar year
}

# Fiscal quarter mapping: maps fiscal quarter number to calendar description
FISCAL_QUARTER_DESCRIPTIONS: dict[str, dict[int, str]] = {
    "AAPL": {
        1: "Oct-Dec (holiday quarter)",
        2: "Jan-Mar",
        3: "Apr-Jun (iPhone announcement quarter)",
        4: "Jul-Sep (new iPhone launch quarter)",
    },
    "MSFT": {
        1: "Jul-Sep",
        2: "Oct-Dec (holiday quarter)",
        3: "Jan-Mar",
        4: "Apr-Jun",
    },
    "GOOGL": {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"},
    "AMZN": {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec (holiday quarter)"},
    "JPM": {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"},
}


def get_fiscal_year_end(ticker: str) -> tuple[int, int] | None:
    return FISCAL_YEAR_ENDS.get(ticker)


def get_quarter_description(ticker: str, quarter: int) -> str:
    descs = FISCAL_QUARTER_DESCRIPTIONS.get(ticker, {})
    return descs.get(quarter, f"Q{quarter}")


def is_calendar_year_company(ticker: str) -> bool:
    fy = FISCAL_YEAR_ENDS.get(ticker)
    return fy is not None and fy == (12, 31)


# ============================================================
# Seasonality Rules
# ============================================================


@dataclass
class SeasonalityNote:
    ticker: str
    quarter: int
    effect: str  # "strong", "weak", "neutral"
    description: str


SEASONALITY: list[SeasonalityNote] = [
    SeasonalityNote(
        "AAPL", 1, "strong", "Holiday quarter — highest revenue due to iPhone/holiday sales"
    ),
    SeasonalityNote("AAPL", 3, "weak", "Typically weakest quarter; pre-announcement lull"),
    SeasonalityNote(
        "AMZN",
        4,
        "strong",
        "Holiday quarter — Prime Day was in Q3, but Q4 has "
        "Black Friday/Cyber Monday/holiday shipping",
    ),
    SeasonalityNote("AMZN", 1, "weak", "Post-holiday slowdown"),
    SeasonalityNote("MSFT", 2, "strong", "Holiday quarter for consumer products (Xbox, Surface)"),
    SeasonalityNote("MSFT", 4, "strong", "Enterprise fiscal year-end buying (June quarter)"),
    SeasonalityNote(
        "GOOGL", 4, "strong", "Holiday advertising spending boosts search and YouTube revenue"
    ),
    SeasonalityNote(
        "JPM", 4, "neutral", "Year-end provisions and reserve adjustments can affect results"
    ),
]


def get_seasonality_notes(ticker: str, quarter: int | None = None) -> list[SeasonalityNote]:
    """Get seasonality notes for a company, optionally filtered by quarter."""
    notes = [s for s in SEASONALITY if s.ticker == ticker]
    if quarter is not None:
        notes = [s for s in notes if s.quarter == quarter]
    return notes


# ============================================================
# Comparison Validity Rules
# ============================================================


@dataclass
class ComparisonRule:
    rule_id: str
    description: str
    check_fn_name: str  # Name of the check function


def check_cross_industry_comparison(ticker1: str, ticker2: str) -> str | None:
    """Check if comparing two companies across industries is valid."""
    industry = get_company_industry(ticker1)
    industry2 = get_company_industry(ticker2)

    if industry != industry2:
        return (
            f"Caution: {ticker1} ({industry}) and {ticker2} ({industry2}) "
            f"are in different industries. Cross-industry comparison of margins, "
            f"leverage ratios, and revenue levels may be misleading. "
            f"Compare relative trends rather than absolute values."
        )
    return None


def check_fiscal_year_alignment(ticker1: str, ticker2: str) -> str | None:
    """Check if two companies have aligned fiscal years."""
    fy1 = FISCAL_YEAR_ENDS.get(ticker1)
    fy2 = FISCAL_YEAR_ENDS.get(ticker2)

    if fy1 and fy2 and fy1 != fy2:
        return (
            f"Note: {ticker1} and {ticker2} have different fiscal year ends "
            f"({ticker1}: month {fy1[0]}, {ticker2}: month {fy2[0]}). "
            f"'Q1' for each company covers different calendar months. "
            f"Compare by calendar period (e.g., 'quarter ending Dec 2024') "
            f"rather than fiscal quarter labels."
        )
    return None


def check_comparison_period(comparison_type: str, metric_id: str) -> str | None:
    """Advise on appropriate comparison period for a metric."""
    from src.context.metric_registry import get_metric

    m = get_metric(metric_id)
    if not m:
        return None

    if comparison_type == "qoq" and m.seasonal_sensitivity:
        return (
            f"Warning: {m.name} is seasonally sensitive. Quarter-over-quarter "
            f"comparison may be misleading. Year-over-year (same quarter prior year) "
            f"is more appropriate for this metric."
        )
    return None


def get_comparison_warnings(
    tickers: list[str],
    metric_ids: list[str],
    comparison_type: str = "yoy",
) -> list[str]:
    """Collect all relevant comparison warnings."""
    warnings = []

    # Cross-company checks
    for i, t1 in enumerate(tickers):
        for t2 in tickers[i + 1 :]:
            w = check_cross_industry_comparison(t1, t2)
            if w:
                warnings.append(w)
            w = check_fiscal_year_alignment(t1, t2)
            if w:
                warnings.append(w)

    # Metric-period checks
    for mid in metric_ids:
        w = check_comparison_period(comparison_type, mid)
        if w:
            warnings.append(w)

    return warnings


# ============================================================
# Industry Classification
# ============================================================

COMPANY_INDUSTRIES: dict[str, str] = {
    "AAPL": "tech_hardware",
    "MSFT": "tech_software",
    "GOOGL": "tech_software",
    "AMZN": "tech_mixed",  # e-commerce + cloud
    "JPM": "banking",
}


def get_company_industry(ticker: str) -> str:
    return COMPANY_INDUSTRIES.get(ticker, "unknown")


def are_comparable(ticker1: str, ticker2: str) -> tuple[bool, str]:
    """Determine if two companies are reasonably comparable."""
    ind1 = get_company_industry(ticker1)
    ind2 = get_company_industry(ticker2)

    if ind1 == ind2:
        return True, f"Both {ticker1} and {ticker2} are in {ind1}."

    # Tech sub-industries are partially comparable
    if ind1.startswith("tech") and ind2.startswith("tech"):
        return True, (
            f"{ticker1} ({ind1}) and {ticker2} ({ind2}) are both in tech "
            f"but with different business models. Margin comparisons should "
            f"account for hardware vs. software vs. mixed revenue."
        )

    return False, (
        f"{ticker1} ({ind1}) and {ticker2} ({ind2}) are in different industries. "
        f"Direct comparison of most financial metrics is not meaningful."
    )


# ============================================================
# Period Recommendation
# ============================================================


def recommend_comparison_type(metric_id: str, ticker: str | None = None) -> str:
    """Recommend the best comparison type for a metric."""
    from src.context.metric_registry import get_metric

    m = get_metric(metric_id)
    if not m:
        return "yoy"

    if m.preferred_comparison:
        return m.preferred_comparison

    if m.seasonal_sensitivity:
        return "yoy"

    return "yoy"  # Default to YoY as most robust
