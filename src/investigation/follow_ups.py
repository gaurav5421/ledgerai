"""Contextual Follow-ups — data-driven suggestions based on what the numbers show.

Follow-ups are NOT generic. They look at the actual data retrieved and suggest
next steps based on what's interesting: large changes, outliers, decomposition
opportunities, or cross-company comparisons.
"""

import sqlite3

from src.agent.retrieval import fetch_metric_trend
from src.context.entity_context import get_company_context
from src.context.metric_registry import get_metric
from src.investigation.decomposition import has_decomposition


def generate_contextual_follow_ups(
    conn: sqlite3.Connection,
    tickers: list[str],
    metrics: list[str],
    query: str,
) -> list[str]:
    """Generate 2-3 follow-up suggestions based on what the data actually shows.

    Looks at the retrieved data to find interesting patterns worth exploring.
    """
    follow_ups: list[str] = []
    query_lower = query.lower()
    is_trend = any(kw in query_lower for kw in ["trend", "over time", "quarters", "history"])
    is_comparison = len(tickers) > 1

    for ticker in tickers:
        for metric_id in metrics:
            # Strategy 1: Offer decomposition if metric changed significantly
            if has_decomposition(metric_id) and len(follow_ups) < 3:
                rows = fetch_metric_trend(conn, ticker, metric_id, quarters=5)
                if len(rows) >= 2:
                    latest = rows[0]["value"]
                    prior = rows[1]["value"]
                    if prior != 0:
                        change = (latest - prior) / abs(prior)
                        if abs(change) >= 0.05:  # 5%+ change
                            m = get_metric(metric_id)
                            name = m.name if m else metric_id
                            direction = "increased" if change > 0 else "decreased"
                            follow_ups.append(
                                f"Why did {ticker}'s {name.lower()} {direction} "
                                f"{abs(change) * 100:.1f}% last quarter? [decompose]"
                            )

                    # Strategy 2: YoY divergence from QoQ
                    if len(rows) >= 5 and rows[4]["value"] != 0:
                        yoy = (latest - rows[4]["value"]) / abs(rows[4]["value"])
                        qoq = change if prior != 0 else None
                        if qoq is not None and _signs_differ(yoy, qoq):
                            m = get_metric(metric_id)
                            name = m.name if m else metric_id
                            follow_ups.append(
                                f"{ticker}'s {name.lower()} moved differently QoQ vs YoY "
                                f"— is this seasonal? [analyze]"
                            )

            # Strategy 3: If single lookup, suggest trend
            if not is_trend and len(follow_ups) < 3:
                m = get_metric(metric_id)
                name = m.name if m else metric_id
                follow_ups.append(
                    f"How has {ticker}'s {name.lower()} trended over the last 8 quarters?"
                )

            # Strategy 4: Related metrics
            if len(follow_ups) < 3:
                m = get_metric(metric_id)
                if m and m.related_metrics:
                    for related_id in m.related_metrics[:2]:
                        rm = get_metric(related_id)
                        if rm and len(follow_ups) < 3:
                            follow_ups.append(f"What's {ticker}'s {rm.name.lower()}?")
                            break

    # Strategy 5: Cross-company comparison if single ticker
    if not is_comparison and len(tickers) == 1 and len(follow_ups) < 3:
        ctx = get_company_context(tickers[0])
        if ctx and ctx.comparable_companies:
            peers = ", ".join(ctx.comparable_companies[:2])
            m = get_metric(metrics[0]) if metrics else None
            if m:
                follow_ups.append(f"Compare {tickers[0]}'s {m.name.lower()} with {peers}")

    # Deduplicate and limit
    seen = set()
    unique = []
    for f in follow_ups:
        key = f.lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique[:3]


def _signs_differ(a: float, b: float) -> bool:
    """Check if two values have different signs (one positive, one negative)."""
    return (a > 0.02 and b < -0.02) or (a < -0.02 and b > 0.02)
