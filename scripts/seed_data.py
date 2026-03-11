#!/usr/bin/env python3
"""Process downloaded EDGAR data and seed the SQLite database.

Reads raw JSON from data/raw/ and populates the database with:
- Company records
- Filing metadata
- Normalized financial line items

Run download_filings.py first.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.data_store import (
    get_connection,
    init_db,
    insert_company,
    insert_filing,
    insert_line_item,
    summary_report,
)
from src.ingestion.edgar_client import COMPANY_CIKS
from src.ingestion.filing_parser import parse_company_facts, parse_submissions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/ledgerai.db")


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def seed_company(conn, ticker: str, cik: str) -> None:
    """Seed a single company's data from raw files."""
    # Parse submissions for company info and filing metadata
    subs_path = RAW_DIR / f"{ticker}_submissions.json"
    if subs_path.exists():
        subs_data = load_json(subs_path)
        company_info, filings = parse_submissions(subs_data, ticker, cik)
        insert_company(conn, **company_info)
        for filing in filings:
            insert_filing(conn, **filing)
        logger.info(f"  {ticker}: {len(filings)} filings inserted")
    else:
        # Minimal company record
        insert_company(
            conn,
            cik=cik,
            ticker=ticker,
            name=ticker,
            sic_code=None,
            industry=None,
            fiscal_year_end=None,
        )

    # Parse XBRL facts for financial line items
    facts_path = RAW_DIR / f"{ticker}_facts.json"
    if facts_path.exists():
        facts_data = load_json(facts_path)
        line_items = parse_company_facts(facts_data, ticker, cik)

        # Deduplicate: keep the latest entry for each (metric, period_end, is_quarterly)
        seen = {}
        for item in line_items:
            key = (item["metric"], item["period_end"], item["is_quarterly"])
            seen[key] = item  # Last one wins (usually most recent filing)

        deduped = list(seen.values())
        for item in deduped:
            insert_line_item(conn, **item)
        logger.info(f"  {ticker}: {len(deduped)} line items inserted (from {len(line_items)} raw)")
    else:
        logger.warning(f"  {ticker}: No facts file found at {facts_path}")


def run_quality_checks(conn) -> None:
    """Run basic data quality checks."""
    print("\n=== Data Quality Checks ===")

    # Check for companies with no line items
    rows = conn.execute("""
        SELECT c.ticker, COUNT(li.id) as item_count
        FROM companies c
        LEFT JOIN financial_line_items li ON c.cik = li.cik
        GROUP BY c.ticker
    """).fetchall()

    for row in rows:
        status = "OK" if row["item_count"] > 0 else "WARNING: no data"
        print(f"  {row['ticker']}: {row['item_count']} line items - {status}")

    # Check revenue exists for each company
    print("\n  Revenue coverage:")
    rows = conn.execute("""
        SELECT c.ticker, COUNT(*) as periods,
               MIN(li.period_end) as earliest,
               MAX(li.period_end) as latest
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE li.metric = 'revenue'
        GROUP BY c.ticker
    """).fetchall()

    for row in rows:
        print(
            f"    {row['ticker']}: {row['periods']} periods "
            f"({row['earliest']} to {row['latest']})"
        )

    # Check for basic balance sheet equation: Assets ≈ Liabilities + Equity
    print("\n  Balance sheet checks (latest period per company):")
    rows = conn.execute("""
        SELECT c.ticker, li.metric, li.value, li.period_end
        FROM financial_line_items li
        JOIN companies c ON li.cik = c.cik
        WHERE li.metric IN ('total_assets', 'total_liabilities', 'total_equity')
        AND li.period_end = (
            SELECT MAX(li2.period_end)
            FROM financial_line_items li2
            JOIN companies c2 ON li2.cik = c2.cik
            WHERE c2.ticker = c.ticker AND li2.metric = 'total_assets'
        )
        ORDER BY c.ticker, li.metric
    """).fetchall()

    by_company: dict[str, dict] = {}
    for row in rows:
        ticker = row["ticker"]
        if ticker not in by_company:
            by_company[ticker] = {}
        by_company[ticker][row["metric"]] = row["value"]

    for ticker, vals in by_company.items():
        assets = vals.get("total_assets")
        liabilities = vals.get("total_liabilities")
        equity = vals.get("total_equity")
        if assets and liabilities and equity:
            expected = liabilities + equity
            diff_pct = abs(assets - expected) / assets * 100 if assets else 0
            status = "OK" if diff_pct < 5 else f"WARNING: {diff_pct:.1f}% off"
            print(f"    {ticker}: A={assets/1e9:.1f}B, L+E={expected/1e9:.1f}B - {status}")
        else:
            missing = [
                k for k in ("total_assets", "total_liabilities", "total_equity") if k not in vals
            ]
            print(f"    {ticker}: Missing {', '.join(missing)}")


def main():
    # Delete existing DB for clean seed
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info(f"Removed existing database: {DB_PATH}")

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)

    try:
        print("=== Seeding Database ===")
        for ticker, cik in COMPANY_CIKS.items():
            print(f"\nProcessing {ticker}...")
            seed_company(conn, ticker, cik)
            conn.commit()

        run_quality_checks(conn)

        # Print summary
        print("\n=== Data Summary ===")
        report = summary_report(conn)
        for ticker, info in report.items():
            print(f"\n{ticker} ({info['name']}):")
            print(f"  Metrics: {info['metrics_count']}")
            print(f"  Periods: {info['periods_count']}")
            if info["metrics"]:
                print(f"  Available: {', '.join(info['metrics'][:10])}")

        print("\nDone! Database saved to", DB_PATH)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
