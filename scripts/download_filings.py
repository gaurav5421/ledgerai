#!/usr/bin/env python3
"""Download SEC EDGAR filings data for target companies.

Downloads:
1. XBRL company facts (structured financial data)
2. Filing submissions metadata

Raw JSON is saved to data/raw/ for reprocessing.
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.edgar_client import (
    COMPANY_CIKS,
    download_company_facts,
    download_submissions,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    user_agent = os.getenv("EDGAR_USER_AGENT")
    if not user_agent:
        print("ERROR: Set EDGAR_USER_AGENT in .env")
        print('Example: EDGAR_USER_AGENT="LedgerAI your.email@example.com"')
        sys.exit(1)

    tickers = list(COMPANY_CIKS.keys())
    print(f"Downloading data for: {', '.join(tickers)}")
    print()

    print("=== Downloading XBRL Company Facts ===")
    facts = download_company_facts(user_agent, tickers)
    print(f"Downloaded facts for {len(facts)} companies")
    print()

    print("=== Downloading Filing Submissions ===")
    subs = download_submissions(user_agent, tickers)
    print(f"Downloaded submissions for {len(subs)} companies")
    print()

    print("Done! Raw data saved to data/raw/")
    print("Next step: python scripts/seed_data.py")


if __name__ == "__main__":
    main()
