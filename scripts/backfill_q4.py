"""Backfill Q4 quarterly data from annual 10-K filings.

Many companies only file 10-Q for Q1-Q3, with Q4 data embedded in the
annual 10-K. This script derives Q4 values by subtracting Q1+Q2+Q3
from the annual figure for flow metrics (revenue, expenses, etc.).

Balance sheet metrics (assets, liabilities, equity) use the annual value
directly since they're point-in-time.
"""

from pathlib import Path

from src.ingestion.data_store import get_connection

# Flow metrics: Q4 = Annual - (Q1 + Q2 + Q3)
FLOW_METRICS = {
    "revenue",
    "net_income",
    "gross_profit",
    "operating_income",
    "cost_of_revenue",
    "rd_expense",
    "sga_expense",
    "operating_cash_flow",
    "capex",
    "depreciation_amortization",
    "net_interest_income",
    "noninterest_income",
}

# Per-share metrics: also flow-like, Q4 ≈ Annual - (Q1+Q2+Q3)
PER_SHARE_METRICS = {"eps_basic", "eps_diluted"}

# Balance sheet metrics: point-in-time, Q4 value = annual value
BALANCE_SHEET_METRICS = {
    "total_assets",
    "total_equity",
    "total_liabilities",
    "current_assets",
    "current_liabilities",
    "long_term_debt",
    "short_term_debt",
    "shares_outstanding",
    "weighted_avg_shares_diluted",
}


def backfill_q4(db_path: Path | None = None, dry_run: bool = False) -> int:
    """Backfill Q4 quarterly rows from annual data.

    Returns the number of rows inserted.
    """
    conn = get_connection(db_path)
    inserted = 0

    # Find all company/fiscal_year combos with annual data
    annuals = conn.execute("""
        SELECT DISTINCT cik, fiscal_year
        FROM financial_line_items
        WHERE is_quarterly = 0 AND fiscal_year IS NOT NULL
        ORDER BY cik, fiscal_year
    """).fetchall()

    for row in annuals:
        cik, fy = row["cik"], row["fiscal_year"]

        # Check which metrics have annual but no Q4
        annual_metrics = conn.execute(
            """
            SELECT metric, value, unit, period_start, period_end, filing_id
            FROM financial_line_items
            WHERE cik = ? AND fiscal_year = ? AND is_quarterly = 0
        """,
            (cik, fy),
        ).fetchall()

        for am in annual_metrics:
            metric = am["metric"]

            # Check if Q4 already exists
            existing = conn.execute(
                """
                SELECT id FROM financial_line_items
                WHERE cik = ? AND fiscal_year = ? AND fiscal_quarter = 4
                AND metric = ? AND is_quarterly = 1
            """,
                (cik, fy, metric),
            ).fetchone()

            if existing:
                continue

            if metric in BALANCE_SHEET_METRICS:
                # Point-in-time: Q4 = annual value
                q4_value = am["value"]
            elif metric in FLOW_METRICS or metric in PER_SHARE_METRICS:
                # Flow: Q4 = Annual - (Q1 + Q2 + Q3)
                quarters = conn.execute(
                    """
                    SELECT fiscal_quarter, value
                    FROM financial_line_items
                    WHERE cik = ? AND fiscal_year = ? AND metric = ?
                    AND is_quarterly = 1 AND fiscal_quarter IN (1, 2, 3)
                """,
                    (cik, fy, metric),
                ).fetchall()

                if len(quarters) != 3:
                    continue  # Can't derive Q4 without all 3 quarters

                q123_sum = sum(q["value"] for q in quarters)
                q4_value = am["value"] - q123_sum
            else:
                continue

            if dry_run:
                ticker = conn.execute(
                    "SELECT ticker FROM companies WHERE cik = ?", (cik,)
                ).fetchone()["ticker"]
                print(
                    f"  Would insert: {ticker} FY{fy} Q4 "
                    f"{metric} = {q4_value:,.0f} {am['unit']}"
                )
            else:
                conn.execute(
                    """
                    INSERT INTO financial_line_items
                    (cik, filing_id, metric, xbrl_tag, value, unit,
                     period_start, period_end, fiscal_year, fiscal_quarter,
                     is_quarterly)
                    VALUES (?, ?, ?, 'derived_q4', ?, ?, ?, ?, ?, 4, 1)
                """,
                    (
                        cik,
                        am["filing_id"],
                        metric,
                        q4_value,
                        am["unit"],
                        am["period_start"],
                        am["period_end"],
                        fy,
                    ),
                )

            inserted += 1

    if not dry_run:
        conn.commit()
        print(f"Inserted {inserted} Q4 rows.")
    else:
        print(f"\nDry run: would insert {inserted} Q4 rows.")

    conn.close()
    return inserted


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv
    backfill_q4(dry_run=dry)
