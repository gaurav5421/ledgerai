"""SQLite storage layer for LedgerAI financial data."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/ledgerai.db")


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    cik         TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    sic_code    TEXT,
    industry    TEXT,
    fiscal_year_end TEXT,  -- MM-DD format, e.g. '09-30' for Apple
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS filings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cik             TEXT NOT NULL REFERENCES companies(cik),
    accession_number TEXT NOT NULL UNIQUE,
    form_type       TEXT NOT NULL,  -- '10-K' or '10-Q'
    filing_date     TEXT NOT NULL,  -- YYYY-MM-DD
    period_end_date TEXT NOT NULL,  -- YYYY-MM-DD
    fiscal_year     INTEGER,
    fiscal_quarter  INTEGER,       -- 1-4 for 10-Q, NULL for 10-K
    url             TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS financial_line_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cik             TEXT NOT NULL REFERENCES companies(cik),
    filing_id       INTEGER REFERENCES filings(id),
    metric          TEXT NOT NULL,  -- normalized name: 'revenue', 'net_income', etc.
    xbrl_tag        TEXT,          -- original XBRL tag: 'us-gaap:Revenues'
    value           REAL NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'USD',
    period_start    TEXT,          -- YYYY-MM-DD
    period_end      TEXT NOT NULL,  -- YYYY-MM-DD
    fiscal_year     INTEGER NOT NULL,
    fiscal_quarter  INTEGER,       -- NULL for annual
    is_quarterly    INTEGER NOT NULL DEFAULT 1,  -- 1=quarterly, 0=annual
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS filing_sections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id       INTEGER NOT NULL REFERENCES filings(id),
    section_type    TEXT NOT NULL,  -- 'mda', 'risk_factors', 'notes', etc.
    content         TEXT NOT NULL,
    chunk_index     INTEGER DEFAULT 0,  -- for splitting long sections
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_line_items_lookup
    ON financial_line_items(cik, metric, fiscal_year, fiscal_quarter);

CREATE INDEX IF NOT EXISTS idx_line_items_period
    ON financial_line_items(cik, metric, period_end);

CREATE INDEX IF NOT EXISTS idx_filings_company
    ON filings(cik, form_type, period_end_date);

CREATE INDEX IF NOT EXISTS idx_sections_filing
    ON filing_sections(filing_id, section_type);
"""


# --- Query helpers ---


def insert_company(conn: sqlite3.Connection, **kwargs) -> None:
    """Insert or update a company record."""
    conn.execute(
        """INSERT OR REPLACE INTO companies (cik, ticker, name, sic_code, industry, fiscal_year_end)
           VALUES (:cik, :ticker, :name, :sic_code, :industry, :fiscal_year_end)""",
        kwargs,
    )


def insert_filing(conn: sqlite3.Connection, **kwargs) -> int:
    """Insert a filing record, return its id."""
    cursor = conn.execute(
        """INSERT OR IGNORE INTO filings
           (cik, accession_number, form_type, filing_date, period_end_date,
            fiscal_year, fiscal_quarter, url)
           VALUES (:cik, :accession_number, :form_type, :filing_date, :period_end_date,
                   :fiscal_year, :fiscal_quarter, :url)""",
        kwargs,
    )
    if cursor.lastrowid:
        return cursor.lastrowid
    # If IGNORE triggered, fetch existing id
    row = conn.execute(
        "SELECT id FROM filings WHERE accession_number = :accession_number", kwargs
    ).fetchone()
    return row["id"]


def insert_line_item(conn: sqlite3.Connection, **kwargs) -> None:
    """Insert a financial line item."""
    conn.execute(
        """INSERT INTO financial_line_items
           (cik, filing_id, metric, xbrl_tag, value, unit,
            period_start, period_end, fiscal_year, fiscal_quarter, is_quarterly)
           VALUES (:cik, :filing_id, :metric, :xbrl_tag, :value, :unit,
                   :period_start, :period_end, :fiscal_year, :fiscal_quarter, :is_quarterly)""",
        kwargs,
    )


def insert_filing_section(conn: sqlite3.Connection, **kwargs) -> None:
    """Insert a filing text section."""
    conn.execute(
        """INSERT INTO filing_sections (filing_id, section_type, content, chunk_index)
           VALUES (:filing_id, :section_type, :content, :chunk_index)""",
        kwargs,
    )


def get_metric(
    conn: sqlite3.Connection,
    ticker: str,
    metric: str,
    fiscal_year: int | None = None,
    fiscal_quarter: int | None = None,
) -> list[dict]:
    """Retrieve metric values for a company, optionally filtered by period."""
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
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_available_metrics(conn: sqlite3.Connection, ticker: str) -> list[str]:
    """List all available metrics for a company."""
    rows = conn.execute(
        """SELECT DISTINCT li.metric
           FROM financial_line_items li
           JOIN companies c ON li.cik = c.cik
           WHERE c.ticker = ?
           ORDER BY li.metric""",
        (ticker,),
    ).fetchall()
    return [row["metric"] for row in rows]


def get_available_periods(conn: sqlite3.Connection, ticker: str) -> list[dict]:
    """List all available periods for a company."""
    rows = conn.execute(
        """SELECT DISTINCT fiscal_year, fiscal_quarter, period_end, is_quarterly
           FROM financial_line_items li
           JOIN companies c ON li.cik = c.cik
           WHERE c.ticker = ?
           ORDER BY period_end DESC""",
        (ticker,),
    ).fetchall()
    return [dict(row) for row in rows]


def summary_report(conn: sqlite3.Connection) -> dict:
    """Generate a data summary: companies, periods, metrics available."""
    companies = conn.execute("SELECT ticker, name FROM companies ORDER BY ticker").fetchall()

    report = {}
    for company in companies:
        ticker = company["ticker"]
        metrics = get_available_metrics(conn, ticker)
        periods = get_available_periods(conn, ticker)
        report[ticker] = {
            "name": company["name"],
            "metrics_count": len(metrics),
            "periods_count": len(periods),
            "metrics": metrics,
            "periods": periods[:8],  # last 8 for brevity
        }
    return report
