# Metrics Dictionary

This document lists all financial metrics that LedgerAI understands, along with their definitions, formulas, and caveats.

## Revenue Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| Revenue | Direct from filing | USD |
| Revenue Growth (YoY) | (Current - Prior Year) / Prior Year | % |
| Revenue Growth (QoQ) | (Current - Prior Quarter) / Prior Quarter | % |

## Profitability Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| Gross Margin | (Revenue - COGS) / Revenue | % |
| Operating Margin | Operating Income / Revenue | % |
| Net Margin | Net Income / Revenue | % |
| EBITDA Margin | EBITDA / Revenue | % |

## Per-Share Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| EPS (Basic) | Net Income / Weighted Avg Shares | USD |
| EPS (Diluted) | Net Income / Diluted Shares | USD |

## Cash Flow Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| Free Cash Flow | Operating Cash Flow - CapEx | USD |
| FCF Margin | Free Cash Flow / Revenue | % |

## Balance Sheet Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| Debt-to-Equity | Total Debt / Total Equity | Ratio |
| Current Ratio | Current Assets / Current Liabilities | Ratio |
| ROE | Net Income / Avg Shareholder Equity | % |
| ROA | Net Income / Avg Total Assets | % |

---

*Full structured definitions with caveats, comparability rules, and typical ranges are in `src/context/metric_registry.py`.*
