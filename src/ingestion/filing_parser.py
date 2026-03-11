"""Parse XBRL company facts into normalized financial line items."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping from XBRL tags to our normalized metric names
# us-gaap taxonomy tags -> normalized names
XBRL_TAG_MAP = {
    # Revenue
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "SalesRevenueNet": "revenue",
    "RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    "InterestIncomeExpenseNet": "net_interest_income",
    "NoninterestIncome": "noninterest_income",
    # Cost of revenue
    "CostOfRevenue": "cost_of_revenue",
    "CostOfGoodsAndServicesSold": "cost_of_revenue",
    "CostOfGoodsSold": "cost_of_revenue",
    # Gross profit
    "GrossProfit": "gross_profit",
    # Operating income
    "OperatingIncomeLoss": "operating_income",
    # Net income
    "NetIncomeLoss": "net_income",
    "NetIncomeLossAvailableToCommonStockholdersBasic": "net_income",
    "ProfitLoss": "net_income",
    # EPS
    "EarningsPerShareBasic": "eps_basic",
    "EarningsPerShareDiluted": "eps_diluted",
    # Cash flow
    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "CapitalExpendituresIncurredButNotYetPaid": "capex",
    # Balance sheet
    "Assets": "total_assets",
    "Liabilities": "total_liabilities",
    "StockholdersEquity": "total_equity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "total_equity",
    "LongTermDebt": "long_term_debt",
    "LongTermDebtNoncurrent": "long_term_debt",
    "ShortTermBorrowings": "short_term_debt",
    "AssetsCurrent": "current_assets",
    "LiabilitiesCurrent": "current_liabilities",
    # Shares
    "CommonStockSharesOutstanding": "shares_outstanding",
    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted": "weighted_avg_shares_diluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding": "weighted_avg_shares_diluted",
    # Research and development
    "ResearchAndDevelopmentExpense": "rd_expense",
    # SGA
    "SellingGeneralAndAdministrativeExpense": "sga_expense",
    # Depreciation
    "DepreciationDepletionAndAmortization": "depreciation_amortization",
    "DepreciationAndAmortization": "depreciation_amortization",
}

# Company fiscal year end months (month number)
FISCAL_YEAR_ENDS = {
    "AAPL": 9,  # September
    "MSFT": 6,  # June
    "GOOGL": 12,  # December
    "AMZN": 12,  # December
    "JPM": 12,  # December
}


def determine_fiscal_period(
    period_end: str,
    ticker: str,
    is_instant: bool = False,
) -> tuple[int, int | None, bool]:
    """Determine fiscal year and quarter from period end date.

    Returns (fiscal_year, fiscal_quarter, is_quarterly).
    fiscal_quarter is None for annual periods.
    """
    date = datetime.strptime(period_end, "%Y-%m-%d")
    fy_end_month = FISCAL_YEAR_ENDS.get(ticker, 12)

    # Determine fiscal year
    if date.month <= fy_end_month:
        fiscal_year = date.year
    else:
        fiscal_year = date.year + 1

    # Determine fiscal quarter based on month relative to FY end
    months_from_fy_start = (date.month - fy_end_month - 1) % 12
    fiscal_quarter = (months_from_fy_start // 3) + 1

    return fiscal_year, fiscal_quarter, True


def is_quarterly_period(start: str | None, end: str) -> bool:
    """Check if a period is roughly quarterly (80-100 days) vs annual."""
    if start is None:
        return True  # Assume quarterly for instant values
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")
    days = (end_date - start_date).days
    return days < 120  # Quarterly is ~90 days


def parse_company_facts(
    facts_data: dict,
    ticker: str,
    cik: str,
) -> list[dict]:
    """Parse XBRL company facts JSON into normalized line items.

    Returns a list of dicts ready for insert_line_item().
    """
    line_items = []
    entity_name = facts_data.get("entityName", ticker)

    us_gaap = facts_data.get("facts", {}).get("us-gaap", {})

    for xbrl_tag, tag_data in us_gaap.items():
        metric = XBRL_TAG_MAP.get(xbrl_tag)
        if metric is None:
            continue  # Skip tags we don't care about

        units = tag_data.get("units", {})

        # Determine the right unit key
        for unit_key, entries in units.items():
            # We want USD for dollar amounts, USD/shares for per-share, shares for counts
            if unit_key not in ("USD", "USD/shares", "shares", "pure"):
                continue

            unit_label = unit_key
            if unit_key == "USD/shares":
                unit_label = "USD/share"
            elif unit_key == "pure":
                unit_label = "ratio"

            for entry in entries:
                form_type = entry.get("form", "")
                if form_type not in ("10-K", "10-Q"):
                    continue

                period_end = entry.get("end")
                period_start = entry.get("start")
                if period_end is None:
                    continue

                # Determine if quarterly or annual
                if period_start:
                    quarterly = is_quarterly_period(period_start, period_end)
                else:
                    # Instant values (balance sheet) — use the form type
                    quarterly = form_type == "10-Q"

                # For 10-K, we want annual figures (not quarterly)
                if form_type == "10-K" and quarterly:
                    continue
                # For 10-Q, we want quarterly figures
                if form_type == "10-Q" and not quarterly:
                    continue

                fiscal_year, fiscal_quarter, _ = determine_fiscal_period(period_end, ticker)

                value = entry.get("val")
                if value is None:
                    continue

                line_items.append(
                    {
                        "cik": cik,
                        "filing_id": None,  # Will link later if needed
                        "metric": metric,
                        "xbrl_tag": f"us-gaap:{xbrl_tag}",
                        "value": float(value),
                        "unit": unit_label,
                        "period_start": period_start,
                        "period_end": period_end,
                        "fiscal_year": fiscal_year,
                        "fiscal_quarter": fiscal_quarter if quarterly else None,
                        "is_quarterly": 1 if quarterly else 0,
                    }
                )

    logger.info(f"Parsed {len(line_items)} line items for {ticker} ({entity_name})")
    return line_items


def parse_submissions(
    submissions_data: dict,
    ticker: str,
    cik: str,
) -> tuple[dict, list[dict]]:
    """Parse submissions JSON into company info and filing records.

    Returns (company_info, filings_list).
    """
    company_info = {
        "cik": cik,
        "ticker": ticker,
        "name": submissions_data.get("name", ticker),
        "sic_code": submissions_data.get("sic", None),
        "industry": submissions_data.get("sicDescription", None),
        "fiscal_year_end": submissions_data.get("fiscalYearEnd", None),
    }

    filings = []
    recent = submissions_data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    acc_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])

    for i in range(len(forms)):
        form_type = forms[i]
        if form_type not in ("10-K", "10-Q"):
            continue

        period_end = report_dates[i] if i < len(report_dates) else None
        if not period_end:
            continue

        fiscal_year, fiscal_quarter, _ = determine_fiscal_period(period_end, ticker)

        # Build filing URL
        acc = acc_numbers[i] if i < len(acc_numbers) else ""
        acc_clean = acc.replace("-", "")
        doc = primary_docs[i] if i < len(primary_docs) else ""
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{doc}" if doc else None

        filings.append(
            {
                "cik": cik,
                "accession_number": acc,
                "form_type": form_type,
                "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                "period_end_date": period_end,
                "fiscal_year": fiscal_year,
                "fiscal_quarter": fiscal_quarter if form_type == "10-Q" else None,
                "url": url,
            }
        )

    logger.info(f"Parsed {len(filings)} filings for {ticker}")
    return company_info, filings
