"""SEC EDGAR API client for fetching filings and structured financial data."""

import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov"
EFTS_URL = "https://efts.sec.gov/LATEST"

# Target companies: ticker -> CIK (zero-padded 10 digits)
COMPANY_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "JPM": "0000019617",
}

# Rate limit: SEC allows 10 req/s, we'll be conservative
MIN_REQUEST_INTERVAL = 0.15  # seconds between requests


class EdgarClient:
    """Client for SEC EDGAR APIs with rate limiting."""

    def __init__(self, user_agent: str):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC EDGAR requires a User-Agent with contact email. "
                "Example: 'LedgerAI gaurav@example.com'"
            )
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        self._last_request_time = 0.0
        self._client = httpx.Client(headers=self.headers, timeout=30.0)

    def _rate_limit(self) -> None:
        """Enforce minimum interval between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> dict:
        """Make a rate-limited GET request."""
        self._rate_limit()
        logger.debug(f"GET {url}")
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    def _get_raw(self, url: str) -> str:
        """Make a rate-limited GET request, return raw text."""
        self._rate_limit()
        logger.debug(f"GET {url}")
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.text

    def get_company_facts(self, cik: str) -> dict:
        """Fetch all XBRL facts for a company.

        Returns structured financial data across all filings.
        Endpoint: data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
        """
        url = f"{BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        return self._get(url)

    def get_submissions(self, cik: str) -> dict:
        """Fetch filing metadata for a company.

        Returns filing dates, accession numbers, form types.
        Endpoint: data.sec.gov/submissions/CIK{cik}.json
        """
        url = f"{BASE_URL}/submissions/CIK{cik}.json"
        return self._get(url)

    def get_filing_document(self, accession_number: str, cik: str) -> str:
        """Fetch the primary document of a filing (HTML).

        First gets the filing index to find the primary document,
        then fetches the document content.
        """
        # Clean accession number: remove dashes for URL path
        acc_clean = accession_number.replace("-", "")
        index_url = (
            f"{BASE_URL}/Archives/edgar/data/{cik}/{acc_clean}/{accession_number}-index.json"
        )

        try:
            index_data = self._get(index_url)
        except httpx.HTTPStatusError:
            # Try alternate index format
            index_url = f"{BASE_URL}/Archives/edgar/data/{cik}/{acc_clean}/index.json"
            index_data = self._get(index_url)

        # Find the primary document (usually the 10-K or 10-Q HTML file)
        primary_doc = None
        for item in index_data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".htm") or name.endswith(".html"):
                # Prefer the largest HTML file (usually the full filing)
                if primary_doc is None or item.get("size", 0) > primary_doc.get("size", 0):
                    primary_doc = item

        if not primary_doc:
            raise ValueError(f"No primary document found for {accession_number}")

        doc_url = f"{BASE_URL}/Archives/edgar/data/{cik}/{acc_clean}/{primary_doc['name']}"
        return self._get_raw(doc_url)

    def get_company_tickers(self) -> dict:
        """Fetch the full company tickers mapping from EDGAR."""
        url = f"{BASE_URL}/files/company_tickers.json"
        return self._get(url)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def download_company_facts(
    user_agent: str,
    tickers: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, dict]:
    """Download XBRL company facts for target companies.

    Returns dict of ticker -> company_facts data.
    Also saves raw JSON to output_dir if provided.
    """
    import json

    tickers = tickers or list(COMPANY_CIKS.keys())
    output_dir = output_dir or Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    with EdgarClient(user_agent) as client:
        for ticker in tickers:
            cik = COMPANY_CIKS.get(ticker)
            if not cik:
                logger.warning(f"Unknown ticker: {ticker}")
                continue

            logger.info(f"Fetching company facts for {ticker} (CIK: {cik})...")
            try:
                facts = client.get_company_facts(cik)
                results[ticker] = facts

                # Save raw JSON
                out_path = output_dir / f"{ticker}_facts.json"
                with open(out_path, "w") as f:
                    json.dump(facts, f, indent=2)
                logger.info(f"  Saved {out_path}")

            except httpx.HTTPStatusError as e:
                logger.error(f"  Failed to fetch {ticker}: {e}")

    return results


def download_submissions(
    user_agent: str,
    tickers: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, dict]:
    """Download filing submissions metadata for target companies."""
    import json

    tickers = tickers or list(COMPANY_CIKS.keys())
    output_dir = output_dir or Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    with EdgarClient(user_agent) as client:
        for ticker in tickers:
            cik = COMPANY_CIKS.get(ticker)
            if not cik:
                continue

            logger.info(f"Fetching submissions for {ticker} (CIK: {cik})...")
            try:
                subs = client.get_submissions(cik)
                results[ticker] = subs

                out_path = output_dir / f"{ticker}_submissions.json"
                with open(out_path, "w") as f:
                    json.dump(subs, f, indent=2)
                logger.info(f"  Saved {out_path}")

            except httpx.HTTPStatusError as e:
                logger.error(f"  Failed to fetch {ticker}: {e}")

    return results
