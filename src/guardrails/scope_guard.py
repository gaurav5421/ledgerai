"""Scope Guard — determines if a query is in-scope for LedgerAI.

Classifies queries as in-scope, partially in-scope, or out-of-scope,
and provides graceful refusal responses.
"""

import re
from dataclasses import dataclass
from enum import Enum

from src.context.entity_context import get_all_tickers


class ScopeLevel(Enum):
    IN_SCOPE = "in_scope"
    PARTIAL = "partial"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class ScopeResult:
    level: ScopeLevel
    reason: str
    suggestion: str | None = None  # What we CAN help with
    detected_tickers: list[str] = None
    detected_intent: str | None = None

    def __post_init__(self):
        if self.detected_tickers is None:
            self.detected_tickers = []


# --- Out-of-scope patterns ---

INVESTMENT_ADVICE_PATTERNS = [
    r"\bshould\s+i\s+(buy|sell|invest|hold)\b",
    r"\b(buy|sell)\s+(signal|recommendation|rating)\b",
    r"\bis\s+\w+\s+(a\s+good|a\s+bad)\s+(buy|investment|stock)\b",
    r"\b(stock|price)\s+(prediction|forecast|target)\b",
    r"\bwill\s+\w+\s+(stock|share|price)\s+(go\s+up|go\s+down|rise|fall|increase|decrease)\b",
    r"\b(invest|put\s+money)\s+(in|into)\b",
    r"\bportfolio\s+(advice|recommendation|allocation)\b",
]

NON_FINANCIAL_PATTERNS = [
    r"\b(weather|recipe|sports|movie|music|game|travel)\b",
    r"\b(who\s+is\s+the\s+CEO|management\s+team|board\s+of\s+directors)\b",
    r"\b(news|rumor|tweet|social\s+media)\b",
    r"\b(write|code|program|debug|translate)\b",
]

FUTURE_PROJECTION_PATTERNS = [
    r"\b(predict|forecast|project|estimate)\s+.*(revenue|income|earnings|margin|growth)\b",
    r"\bwhat\s+will\s+.*(revenue|income|earnings)\s+be\b",
    r"\b(next\s+quarter|next\s+year|future|upcoming)\s+.*(revenue|earnings|results)\b",
    r"\bnext\s+(quarter|year).*(?:revenue|earnings|income|margin)\b",
]

# --- In-scope intent patterns ---

FINANCIAL_METRIC_PATTERNS = [
    r"\b(revenue|sales|income|earnings|profit|margin|eps|cash\s*flow|fcf|debt|equity|assets|liabilities|roe|roa)\b",
    r"\b(gross\s+margin|operating\s+margin|net\s+margin|profit\s+margin)\b",
    r"\b(growth|trend|change|increase|decrease|decline|drop|rise|improve)\b",
    r"\b(compare|comparison|versus|vs\.?|relative\s+to)\b",
    r"\b(quarter|quarterly|annual|year|yoy|qoq|ttm)\b",
    r"\b(balance\s+sheet|income\s+statement|cash\s+flow\s+statement)\b",
    r"\b(capex|capital\s+expenditure|r&d|research\s+and\s+development|sga)\b",
    r"\b(current\s+ratio|debt.to.equity|free\s+cash\s+flow)\b",
]

# Ticker/company name recognition
TICKER_ALIASES: dict[str, str] = {
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    "goog": "GOOGL",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "jpm": "JPM",
    "chase": "JPM",
}


def extract_tickers(query: str) -> list[str]:
    """Extract recognized company tickers from a query."""
    query_lower = query.lower()
    found = set()
    for alias, ticker in TICKER_ALIASES.items():
        if alias in query_lower:
            found.add(ticker)
    return sorted(found)


def _matches_any(query: str, patterns: list[str]) -> bool:
    query_lower = query.lower()
    return any(re.search(p, query_lower) for p in patterns)


def check_scope(query: str) -> ScopeResult:
    """Classify a query as in-scope, partial, or out-of-scope."""
    tickers = extract_tickers(query)

    # Check out-of-scope patterns first
    if _matches_any(query, INVESTMENT_ADVICE_PATTERNS):
        company_str = f" {', '.join(tickers)}'s" if tickers else ""
        return ScopeResult(
            level=ScopeLevel.OUT_OF_SCOPE,
            reason="This appears to be a request for investment advice or stock recommendations.",
            suggestion=(
                f"I can't provide investment advice or stock recommendations. "
                f"What I can do is help you analyze{company_str} financial fundamentals — "
                f"revenue trends, margin analysis, cash flow health — so you have "
                f"better data for your own decision. Want to start there?"
            ),
            detected_tickers=tickers,
            detected_intent="investment_advice",
        )

    if _matches_any(query, NON_FINANCIAL_PATTERNS) and not _matches_any(
        query, FINANCIAL_METRIC_PATTERNS
    ):
        return ScopeResult(
            level=ScopeLevel.OUT_OF_SCOPE,
            reason="This question is outside the financial analysis domain.",
            suggestion=(
                "I specialize in analyzing public company financials from SEC filings. "
                "I can help with revenue trends, margin analysis, earnings comparisons, "
                "and cash flow analysis for AAPL, MSFT, GOOGL, AMZN, and JPM."
            ),
            detected_tickers=tickers,
            detected_intent="non_financial",
        )

    if _matches_any(query, FUTURE_PROJECTION_PATTERNS):
        return ScopeResult(
            level=ScopeLevel.OUT_OF_SCOPE,
            reason="This asks for future projections or forecasts, which I cannot provide.",
            suggestion=(
                "I can't predict future financial results. However, I can show you "
                "historical trends that may be useful for your own analysis — "
                "for example, revenue growth trends, margin trajectories, or "
                "seasonal patterns over the last 8 quarters."
            ),
            detected_tickers=tickers,
            detected_intent="future_projection",
        )

    # Check for recognized companies
    has_financial_intent = _matches_any(query, FINANCIAL_METRIC_PATTERNS)
    all_known_tickers = set(get_all_tickers())

    if not tickers and has_financial_intent:
        return ScopeResult(
            level=ScopeLevel.PARTIAL,
            reason="Financial question detected but no recognized company specified.",
            suggestion=(
                "I can analyze financials for these companies: "
                f"{', '.join(sorted(all_known_tickers))}. "
                "Which company would you like to look at?"
            ),
            detected_tickers=[],
            detected_intent="financial_no_company",
        )

    unknown_tickers = [t for t in tickers if t not in all_known_tickers]
    if unknown_tickers:
        return ScopeResult(
            level=ScopeLevel.PARTIAL,
            reason=f"Company not in dataset: {', '.join(unknown_tickers)}.",
            suggestion=(
                f"I don't have data for {', '.join(unknown_tickers)}. "
                f"I currently cover: {', '.join(sorted(all_known_tickers))}. "
                f"Would you like to analyze one of these instead?"
            ),
            detected_tickers=[t for t in tickers if t in all_known_tickers],
            detected_intent="unknown_company",
        )

    if tickers and has_financial_intent:
        return ScopeResult(
            level=ScopeLevel.IN_SCOPE,
            reason="Financial question about covered company.",
            detected_tickers=tickers,
            detected_intent="financial_query",
        )

    # If we have tickers but unclear intent, it's partially in scope
    if tickers:
        return ScopeResult(
            level=ScopeLevel.PARTIAL,
            reason="Company recognized but question intent is unclear.",
            suggestion=(
                f"I can help analyze {', '.join(tickers)}'s financials. "
                f"For example: revenue trends, margin analysis, EPS, cash flow, "
                f"or comparisons with peers. What would you like to know?"
            ),
            detected_tickers=tickers,
            detected_intent="unclear",
        )

    # Generic fallback
    return ScopeResult(
        level=ScopeLevel.OUT_OF_SCOPE,
        reason="Question doesn't appear to be about company financials.",
        suggestion=(
            "I specialize in analyzing public company financials from SEC filings. "
            "Try asking about revenue, margins, earnings, or cash flow for "
            f"{', '.join(sorted(all_known_tickers))}."
        ),
        detected_tickers=[],
        detected_intent="unknown",
    )
