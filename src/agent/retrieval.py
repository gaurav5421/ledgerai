"""Retrieval Layer — fetches data from SQLite for the agent.

Handles structured data queries, metric calculations, and trend retrieval.
"""

import sqlite3
from pathlib import Path

from src.guardrails.provenance import ProvenanceRecord, build_fiscal_label
from src.ingestion.data_store import DEFAULT_DB_PATH, get_connection


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    return get_connection(db_path or DEFAULT_DB_PATH)


def fetch_metric(
    conn: sqlite3.Connection,
    ticker: str,
    metric: str,
    fiscal_year: int | None = None,
    fiscal_quarter: int | None = None,
    limit: int = 1,
) -> list[dict]:
    """Fetch metric values for a company."""
    query = """
        SELECT li.*, c.ticker, c.name as company_name
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE c.ticker = ? AND li.metric = ?
    """
    params: list = [ticker, metric]

    if fiscal_year is not None:
        query += " AND li.fiscal_year = ?"
        params.append(fiscal_year)
    if fiscal_quarter is not None:
        query += " AND li.fiscal_quarter = ?"
        params.append(fiscal_quarter)

    query += " ORDER BY li.period_end DESC"
    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def fetch_metric_trend(
    conn: sqlite3.Connection,
    ticker: str,
    metric: str,
    quarters: int = 8,
    quarterly: bool = True,
) -> list[dict]:
    """Fetch metric values over multiple periods for trend analysis."""
    query = """
        SELECT li.*, c.ticker, c.name as company_name
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE c.ticker = ? AND li.metric = ? AND li.is_quarterly = ?
        ORDER BY li.period_end DESC
        LIMIT ?
    """
    rows = conn.execute(query, (ticker, metric, 1 if quarterly else 0, quarters)).fetchall()
    return [dict(row) for row in rows]


def fetch_latest_metric(
    conn: sqlite3.Connection,
    ticker: str,
    metric: str,
    quarterly: bool = True,
) -> dict | None:
    """Fetch the most recent value of a metric."""
    results = fetch_metric_trend(conn, ticker, metric, quarters=1, quarterly=quarterly)
    return results[0] if results else None


def fetch_comparison_data(
    conn: sqlite3.Connection,
    tickers: list[str],
    metric: str,
    quarters: int = 4,
    quarterly: bool = True,
) -> dict[str, list[dict]]:
    """Fetch metric data for multiple companies for comparison."""
    result = {}
    for ticker in tickers:
        result[ticker] = fetch_metric_trend(conn, ticker, metric, quarters, quarterly)
    return result


def calculate_derived_metric(
    conn: sqlite3.Connection,
    ticker: str,
    metric_id: str,
    fiscal_year: int | None = None,
    fiscal_quarter: int | None = None,
) -> tuple[float, ProvenanceRecord] | None:
    """Calculate a derived metric from its components.

    Returns (value, provenance) or None if data is missing.
    """
    provenance = ProvenanceRecord()

    def _get(component_metric: str) -> float | None:
        rows = fetch_metric(conn, ticker, component_metric, fiscal_year, fiscal_quarter, limit=1)
        if not rows:
            return None
        row = rows[0]
        provenance.add_source(
            ticker=ticker,
            filing_type="10-Q" if row["is_quarterly"] else "10-K",
            period_end=row["period_end"],
            fiscal_label=build_fiscal_label(
                row["fiscal_year"], row.get("fiscal_quarter"), bool(row["is_quarterly"])
            ),
            metric=component_metric,
            value=row["value"],
            unit=row["unit"],
        )
        return row["value"]

    # Derived metric calculations
    if metric_id == "gross_margin":
        gp = _get("gross_profit")
        rev = _get("revenue")
        if gp is not None and rev is not None and rev != 0:
            result = gp / rev
            provenance.add_calculation(
                "Gross Margin",
                "gross_profit / revenue",
                {"gross_profit": gp, "revenue": rev},
                result,
            )
            return result, provenance

    elif metric_id == "operating_margin":
        oi = _get("operating_income")
        rev = _get("revenue")
        if oi is not None and rev is not None and rev != 0:
            result = oi / rev
            provenance.add_calculation(
                "Operating Margin",
                "operating_income / revenue",
                {"operating_income": oi, "revenue": rev},
                result,
            )
            return result, provenance

    elif metric_id == "net_margin":
        ni = _get("net_income")
        rev = _get("revenue")
        if ni is not None and rev is not None and rev != 0:
            result = ni / rev
            provenance.add_calculation(
                "Net Margin", "net_income / revenue", {"net_income": ni, "revenue": rev}, result
            )
            return result, provenance

    elif metric_id == "free_cash_flow":
        ocf = _get("operating_cash_flow")
        cx = _get("capex")
        if ocf is not None and cx is not None:
            result = ocf - cx
            provenance.add_calculation(
                "Free Cash Flow",
                "operating_cash_flow - capex",
                {"operating_cash_flow": ocf, "capex": cx},
                result,
            )
            return result, provenance

    elif metric_id == "fcf_margin":
        ocf = _get("operating_cash_flow")
        cx = _get("capex")
        rev = _get("revenue")
        if ocf is not None and cx is not None and rev is not None and rev != 0:
            fcf = ocf - cx
            result = fcf / rev
            provenance.add_calculation(
                "FCF Margin",
                "(operating_cash_flow - capex) / revenue",
                {"operating_cash_flow": ocf, "capex": cx, "revenue": rev},
                result,
            )
            return result, provenance

    elif metric_id == "debt_to_equity":
        ltd = _get("long_term_debt")
        std = _get("short_term_debt")
        eq = _get("total_equity")
        if ltd is not None and eq is not None and eq != 0:
            total_debt = ltd + (std or 0)
            result = total_debt / eq
            provenance.add_calculation(
                "Debt-to-Equity",
                "(long_term_debt + short_term_debt) / total_equity",
                {"long_term_debt": ltd, "short_term_debt": std or 0, "total_equity": eq},
                result,
            )
            return result, provenance

    elif metric_id == "current_ratio":
        ca = _get("current_assets")
        cl = _get("current_liabilities")
        if ca is not None and cl is not None and cl != 0:
            result = ca / cl
            provenance.add_calculation(
                "Current Ratio",
                "current_assets / current_liabilities",
                {"current_assets": ca, "current_liabilities": cl},
                result,
            )
            return result, provenance

    elif metric_id in ("revenue_growth_yoy", "revenue_growth_qoq"):
        # Need current and prior period revenue
        current = fetch_metric(conn, ticker, "revenue", fiscal_year, fiscal_quarter, limit=1)
        if not current:
            return None

        row = current[0]
        provenance.add_source(
            ticker=ticker,
            filing_type="10-Q" if row["is_quarterly"] else "10-K",
            period_end=row["period_end"],
            fiscal_label=build_fiscal_label(row["fiscal_year"], row.get("fiscal_quarter"), True),
            metric="revenue",
            value=row["value"],
            unit=row["unit"],
        )

        if metric_id == "revenue_growth_yoy":
            prior_fy = (fiscal_year or row["fiscal_year"]) - 1
            prior_fq = fiscal_quarter or row.get("fiscal_quarter")
        else:
            prior_fy = fiscal_year or row["fiscal_year"]
            prior_fq = (fiscal_quarter or row.get("fiscal_quarter", 1)) - 1
            if prior_fq == 0:
                prior_fq = 4
                prior_fy -= 1

        prior = fetch_metric(conn, ticker, "revenue", prior_fy, prior_fq, limit=1)
        if prior:
            p = prior[0]
            provenance.add_source(
                ticker=ticker,
                filing_type="10-Q" if p["is_quarterly"] else "10-K",
                period_end=p["period_end"],
                fiscal_label=build_fiscal_label(p["fiscal_year"], p.get("fiscal_quarter"), True),
                metric="revenue",
                value=p["value"],
                unit=p["unit"],
            )
            if p["value"] != 0:
                result = (row["value"] - p["value"]) / p["value"]
                provenance.add_calculation(
                    metric_id,
                    "(current - prior) / prior",
                    {"current": row["value"], "prior": p["value"]},
                    result,
                )
                return result, provenance

    return None


def get_available_metrics_for_company(conn: sqlite3.Connection, ticker: str) -> list[str]:
    """List all available metrics for a company."""
    rows = conn.execute(
        """
        SELECT DISTINCT li.metric
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE c.ticker = ?
        ORDER BY li.metric
    """,
        (ticker,),
    ).fetchall()
    return [row["metric"] for row in rows]


def get_latest_period(conn: sqlite3.Connection, ticker: str) -> str | None:
    """Get the most recent period_end for a company."""
    row = conn.execute(
        """
        SELECT MAX(period_end) as latest
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE c.ticker = ?
    """,
        (ticker,),
    ).fetchone()
    return row["latest"] if row else None
