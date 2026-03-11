"""Metric Registry — structured definitions for financial metrics.

Each metric includes its formula, components, caveats, comparability rules,
and typical ranges. The agent looks up definitions here rather than improvising.
"""

from dataclasses import dataclass


@dataclass
class MetricDefinition:
    id: str
    name: str
    formula: str
    unit: str  # "USD", "percentage", "ratio", "USD/share"
    components: list[str]  # metric IDs needed to calculate this
    caveats: list[str]
    related_metrics: list[str]
    typical_ranges: dict[str, tuple[float | None, float | None]]  # industry -> (low, high)
    category: str  # "revenue", "profitability", "cash_flow", "balance_sheet", "per_share"
    description: str
    requires_normalization_for_comparison: bool = False
    preferred_comparison: str = "yoy"  # "yoy", "qoq", "ttm"
    seasonal_sensitivity: bool = False
    applicable_to_banks: bool = True


# --- Metric Definitions ---

METRICS: dict[str, MetricDefinition] = {}


def _register(m: MetricDefinition) -> None:
    METRICS[m.id] = m


# ============================================================
# Revenue Metrics
# ============================================================

_register(
    MetricDefinition(
        id="revenue",
        name="Revenue",
        formula="Direct from filing (top-line revenue)",
        unit="USD",
        components=[],
        caveats=[
            "Revenue recognition policies vary by company (ASC 606)",
            "Banks report 'net interest income' + 'noninterest income'"
            " instead of a single revenue line",
            "Some companies include excise taxes in revenue, others exclude them",
            "Acquisitions and divestitures can make period-over-period comparison misleading",
        ],
        related_metrics=["revenue_growth_yoy", "revenue_growth_qoq", "gross_margin"],
        typical_ranges={"tech": (1e9, 150e9), "banking": (10e9, 50e9)},
        category="revenue",
        description="Total revenue or net sales for the period.",
        seasonal_sensitivity=True,
    )
)

_register(
    MetricDefinition(
        id="revenue_growth_yoy",
        name="Revenue Growth (YoY)",
        formula=(
            "(current_quarter_revenue - same_quarter_prior_year_revenue)"
            " / same_quarter_prior_year_revenue"
        ),
        unit="percentage",
        components=["revenue"],
        caveats=[
            "YoY comparison removes seasonality effects",
            "Acquisitions can inflate growth rates — check for organic vs. inorganic growth",
            "Currency fluctuations affect growth rates for companies with international revenue",
            "One-time items (licensing deals, settlements) can distort single-quarter growth",
        ],
        related_metrics=["revenue", "revenue_growth_qoq"],
        typical_ranges={"tech": (-0.05, 0.40), "banking": (-0.10, 0.20)},
        category="revenue",
        description="Year-over-year revenue growth rate, comparing the same quarter.",
        preferred_comparison="yoy",
        seasonal_sensitivity=False,
    )
)

_register(
    MetricDefinition(
        id="revenue_growth_qoq",
        name="Revenue Growth (QoQ)",
        formula="(current_quarter_revenue - prior_quarter_revenue) / prior_quarter_revenue",
        unit="percentage",
        components=["revenue"],
        caveats=[
            "QoQ growth is heavily affected by seasonality — use with caution",
            "Holiday quarters (Q4 for retail, Q1 for Apple) will naturally show higher revenue",
            "Better to compare QoQ within the same industry and similar fiscal calendars",
            "YoY comparison is generally more meaningful for seasonal businesses",
        ],
        related_metrics=["revenue", "revenue_growth_yoy"],
        typical_ranges={"tech": (-0.15, 0.30), "banking": (-0.10, 0.15)},
        category="revenue",
        description="Quarter-over-quarter sequential revenue growth rate.",
        preferred_comparison="qoq",
        seasonal_sensitivity=True,
    )
)

# ============================================================
# Profitability Metrics
# ============================================================

_register(
    MetricDefinition(
        id="gross_profit",
        name="Gross Profit",
        formula="revenue - cost_of_revenue",
        unit="USD",
        components=["revenue", "cost_of_revenue"],
        caveats=[
            "Definition of cost of revenue varies significantly by industry",
            "Banks typically do not report a 'gross profit' line",
            "Software companies may include hosting costs in COGS, others may not",
        ],
        related_metrics=["gross_margin", "revenue", "cost_of_revenue"],
        typical_ranges={"tech": (1e9, 100e9), "banking": (None, None)},
        category="profitability",
        description="Revenue minus cost of goods sold / cost of revenue.",
        applicable_to_banks=False,
    )
)

_register(
    MetricDefinition(
        id="gross_margin",
        name="Gross Margin",
        formula="gross_profit / revenue",
        unit="percentage",
        components=["gross_profit", "revenue"],
        caveats=[
            "Definition of COGS varies by industry — tech companies may"
            " exclude different items than manufacturers",
            "One-time charges can distort single-quarter margins",
            "Compare within industry, not across industries",
            "Banks do not have a traditional gross margin — use net interest margin instead",
            "Hardware vs. software mix significantly affects tech company margins",
        ],
        related_metrics=["operating_margin", "net_margin", "gross_profit"],
        typical_ranges={
            "tech_software": (0.60, 0.90),
            "tech_hardware": (0.30, 0.50),
            "tech_mixed": (0.40, 0.70),
            "banking": (None, None),
            "retail": (0.20, 0.45),
        },
        category="profitability",
        description="Gross profit as a percentage of revenue. Measures production efficiency.",
        requires_normalization_for_comparison=True,
        applicable_to_banks=False,
    )
)

_register(
    MetricDefinition(
        id="operating_income",
        name="Operating Income",
        formula="gross_profit - operating_expenses (or direct from filing)",
        unit="USD",
        components=["gross_profit", "rd_expense", "sga_expense"],
        caveats=[
            "May include or exclude restructuring charges depending on the company",
            "Stock-based compensation treatment varies (included in GAAP, excluded in non-GAAP)",
            "Amortization of acquired intangibles can significantly depress"
            " operating income for acquisitive companies",
        ],
        related_metrics=["operating_margin", "gross_profit", "net_income"],
        typical_ranges={"tech": (1e9, 50e9), "banking": (5e9, 20e9)},
        category="profitability",
        description="Income from core business operations, before interest and taxes.",
    )
)

_register(
    MetricDefinition(
        id="operating_margin",
        name="Operating Margin",
        formula="operating_income / revenue",
        unit="percentage",
        components=["operating_income", "revenue"],
        caveats=[
            "Highly sensitive to R&D and SGA spending levels",
            "Stock-based compensation (SBC) is a real cost — GAAP operating"
            " margin includes it, non-GAAP often excludes it",
            "Restructuring charges can temporarily depress margins",
            "For banks, 'efficiency ratio' is a more relevant metric than operating margin",
        ],
        related_metrics=["gross_margin", "net_margin", "operating_income"],
        typical_ranges={
            "tech_software": (0.20, 0.50),
            "tech_hardware": (0.10, 0.35),
            "banking": (None, None),
        },
        category="profitability",
        description="Operating income as a percentage of revenue. Measures operational efficiency.",
        requires_normalization_for_comparison=True,
    )
)

_register(
    MetricDefinition(
        id="net_income",
        name="Net Income",
        formula="Direct from filing (bottom-line earnings)",
        unit="USD",
        components=[],
        caveats=[
            "Includes non-operating items: interest expense, tax provisions, one-time gains/losses",
            "Tax rate changes (e.g., TCJA in 2017) can cause large swings unrelated to operations",
            "Investment gains/losses (e.g., equity portfolio mark-to-market)"
            " can dominate for some companies",
            "Compare operating income for a cleaner view of business performance",
        ],
        related_metrics=["net_margin", "eps_basic", "eps_diluted", "operating_income"],
        typical_ranges={"tech": (1e9, 40e9), "banking": (5e9, 15e9)},
        category="profitability",
        description="Bottom-line profit after all expenses, interest, and taxes.",
    )
)

_register(
    MetricDefinition(
        id="net_margin",
        name="Net Margin",
        formula="net_income / revenue",
        unit="percentage",
        components=["net_income", "revenue"],
        caveats=[
            "Affected by tax rates, interest expense, and one-time items",
            "Not ideal for cross-company comparison due to capital structure differences",
            "Negative net margin doesn't necessarily mean the business"
            " is unhealthy — check operating margin",
        ],
        related_metrics=["gross_margin", "operating_margin", "net_income"],
        typical_ranges={
            "tech": (0.15, 0.40),
            "banking": (0.20, 0.40),
            "retail": (0.02, 0.10),
        },
        category="profitability",
        description="Net income as a percentage of revenue.",
        requires_normalization_for_comparison=True,
    )
)

# ============================================================
# Per-Share Metrics
# ============================================================

_register(
    MetricDefinition(
        id="eps_basic",
        name="EPS (Basic)",
        formula="net_income / weighted_average_shares_basic",
        unit="USD/share",
        components=["net_income"],
        caveats=[
            "Does not account for dilution from stock options and convertible securities",
            "Share buybacks reduce share count, inflating EPS even if net income is flat",
            "Stock splits change the per-share value — historical EPS is retroactively adjusted",
        ],
        related_metrics=["eps_diluted", "net_income", "shares_outstanding"],
        typical_ranges={"tech": (1.0, 25.0), "banking": (2.0, 20.0)},
        category="per_share",
        description="Net income divided by weighted average basic shares outstanding.",
    )
)

_register(
    MetricDefinition(
        id="eps_diluted",
        name="EPS (Diluted)",
        formula="net_income / weighted_average_shares_diluted",
        unit="USD/share",
        components=["net_income"],
        caveats=[
            "Includes effect of stock options, RSUs, convertible securities",
            "More conservative and widely-used than basic EPS",
            "The difference between basic and diluted EPS indicates dilution risk",
        ],
        related_metrics=["eps_basic", "net_income"],
        typical_ranges={"tech": (1.0, 25.0), "banking": (2.0, 20.0)},
        category="per_share",
        description=(
            "Net income divided by diluted shares outstanding." " Accounts for potential dilution."
        ),
    )
)

# ============================================================
# Cash Flow Metrics
# ============================================================

_register(
    MetricDefinition(
        id="operating_cash_flow",
        name="Operating Cash Flow",
        formula="Direct from cash flow statement",
        unit="USD",
        components=[],
        caveats=[
            "More reliable than net income as it's harder to manipulate",
            "Working capital changes can cause large swings quarter to quarter",
            "Banks have different cash flow dynamics than operating companies",
        ],
        related_metrics=["free_cash_flow", "net_income", "capex"],
        typical_ranges={"tech": (5e9, 50e9), "banking": (-50e9, 50e9)},
        category="cash_flow",
        description="Cash generated from core business operations.",
    )
)

_register(
    MetricDefinition(
        id="capex",
        name="Capital Expenditures",
        formula="Direct from cash flow statement (payments for PP&E)",
        unit="USD",
        components=[],
        caveats=[
            "Reported as a negative number in cash flow statement (cash outflow)",
            "High capex can indicate growth investment or maintenance spending — context matters",
            "Cloud companies may capitalize significant software development costs",
            "Leased assets may not appear in capex (check right-of-use assets)",
        ],
        related_metrics=["free_cash_flow", "operating_cash_flow"],
        typical_ranges={"tech": (1e9, 30e9), "banking": (1e9, 5e9)},
        category="cash_flow",
        description="Capital expenditures — investment in property, plant, and equipment.",
    )
)

_register(
    MetricDefinition(
        id="free_cash_flow",
        name="Free Cash Flow",
        formula="operating_cash_flow - capex",
        unit="USD",
        components=["operating_cash_flow", "capex"],
        caveats=[
            "FCF = Operating Cash Flow - CapEx. This is the 'simple' definition",
            "Some analysts use a more conservative definition that also"
            " subtracts stock-based compensation",
            "Negative FCF isn't always bad — fast-growing companies often invest heavily",
            "For banks, free cash flow is less meaningful; focus on"
            " net interest income and provisions",
        ],
        related_metrics=["fcf_margin", "operating_cash_flow", "capex"],
        typical_ranges={"tech": (5e9, 40e9), "banking": (None, None)},
        category="cash_flow",
        description="Cash available after capital expenditures. Measures cash generation ability.",
        applicable_to_banks=False,
    )
)

_register(
    MetricDefinition(
        id="fcf_margin",
        name="FCF Margin",
        formula="free_cash_flow / revenue",
        unit="percentage",
        components=["free_cash_flow", "revenue"],
        caveats=[
            "Combines profitability and capital efficiency into one metric",
            "Can be volatile quarter to quarter due to capex timing",
            "Best evaluated on a trailing twelve months (TTM) basis",
        ],
        related_metrics=["free_cash_flow", "operating_margin", "net_margin"],
        typical_ranges={"tech": (0.10, 0.40), "banking": (None, None)},
        category="cash_flow",
        description="Free cash flow as a percentage of revenue.",
        preferred_comparison="ttm",
        applicable_to_banks=False,
    )
)

# ============================================================
# Balance Sheet Metrics
# ============================================================

_register(
    MetricDefinition(
        id="total_assets",
        name="Total Assets",
        formula="Direct from balance sheet",
        unit="USD",
        components=[],
        caveats=[
            "Point-in-time value (balance sheet date), not a flow metric",
            "Intangible assets and goodwill can significantly inflate"
            " total assets for acquisitive companies",
            "Banks have much larger balance sheets relative to revenue than operating companies",
        ],
        related_metrics=["total_liabilities", "total_equity", "roa"],
        typical_ranges={"tech": (50e9, 500e9), "banking": (1e12, 5e12)},
        category="balance_sheet",
        description="Total assets on the balance sheet.",
    )
)

_register(
    MetricDefinition(
        id="total_equity",
        name="Total Stockholders' Equity",
        formula="total_assets - total_liabilities",
        unit="USD",
        components=["total_assets", "total_liabilities"],
        caveats=[
            "Can be negative if company has large accumulated deficits and share buybacks",
            "Apple has had periods of near-zero or negative equity due to massive buybacks",
            "Book equity is very different from market equity (market cap)",
        ],
        related_metrics=["total_assets", "debt_to_equity", "roe"],
        typical_ranges={"tech": (10e9, 300e9), "banking": (200e9, 400e9)},
        category="balance_sheet",
        description="Total stockholders' equity (book value).",
    )
)

_register(
    MetricDefinition(
        id="debt_to_equity",
        name="Debt-to-Equity Ratio",
        formula="(long_term_debt + short_term_debt) / total_equity",
        unit="ratio",
        components=["long_term_debt", "short_term_debt", "total_equity"],
        caveats=[
            "Meaningless if equity is negative (e.g., Apple at times)",
            "Banks are inherently highly leveraged — don't compare D/E across industries",
            "Operating leases (ASC 842) added significant liabilities for some companies",
            "Low D/E isn't always good — might indicate underutilized capital structure",
        ],
        related_metrics=["total_equity", "long_term_debt", "current_ratio"],
        typical_ranges={
            "tech": (0.0, 1.5),
            "banking": (5.0, 15.0),
        },
        category="balance_sheet",
        description="Total debt divided by stockholders' equity. Measures financial leverage.",
        requires_normalization_for_comparison=True,
    )
)

_register(
    MetricDefinition(
        id="current_ratio",
        name="Current Ratio",
        formula="current_assets / current_liabilities",
        unit="ratio",
        components=["current_assets", "current_liabilities"],
        caveats=[
            "Measures short-term liquidity — ability to pay obligations within one year",
            "Too high may indicate inefficient use of assets",
            "Industry norms vary significantly — tech companies often have higher ratios",
            "Does not account for quality of current assets (e.g., aging receivables)",
        ],
        related_metrics=["current_assets", "current_liabilities"],
        typical_ranges={
            "tech": (1.0, 4.0),
            "banking": (None, None),  # Not meaningful for banks
        },
        category="balance_sheet",
        description="Current assets divided by current liabilities. Measures short-term liquidity.",
        applicable_to_banks=False,
    )
)

_register(
    MetricDefinition(
        id="roe",
        name="Return on Equity",
        formula="net_income_annual / average_total_equity",
        unit="percentage",
        components=["net_income", "total_equity"],
        caveats=[
            "Use trailing twelve months net income with average equity for accuracy",
            "High ROE can result from high leverage, not just operational excellence",
            "Meaningless if equity is negative",
            "For banks, ROE is a key performance metric — target is typically 10-15%",
        ],
        related_metrics=["roa", "net_income", "total_equity"],
        typical_ranges={
            "tech": (0.15, 0.60),
            "banking": (0.08, 0.18),
        },
        category="balance_sheet",
        description="Annual net income divided by average stockholders' equity.",
        preferred_comparison="ttm",
    )
)

_register(
    MetricDefinition(
        id="roa",
        name="Return on Assets",
        formula="net_income_annual / average_total_assets",
        unit="percentage",
        components=["net_income", "total_assets"],
        caveats=[
            "Asset-light companies (software) naturally have higher ROA than asset-heavy ones",
            "Banks have very low ROA (1-2%) because of enormous balance sheets — this is normal",
            "Use trailing twelve months for consistency",
        ],
        related_metrics=["roe", "net_income", "total_assets"],
        typical_ranges={
            "tech": (0.05, 0.30),
            "banking": (0.005, 0.02),
        },
        category="balance_sheet",
        description="Annual net income divided by average total assets.",
        preferred_comparison="ttm",
    )
)

# ============================================================
# Expense Metrics
# ============================================================

_register(
    MetricDefinition(
        id="rd_expense",
        name="Research & Development Expense",
        formula="Direct from income statement",
        unit="USD",
        components=[],
        caveats=[
            "R&D intensity (R&D/Revenue) is more comparable across companies than absolute R&D",
            "Some companies capitalize a portion of R&D (e.g., software development costs)",
            "Banks typically have minimal R&D — they invest in technology differently",
        ],
        related_metrics=["revenue", "operating_income", "sga_expense"],
        typical_ranges={"tech": (5e9, 40e9), "banking": (None, None)},
        category="profitability",
        description="Research and development expenses.",
        applicable_to_banks=False,
    )
)

_register(
    MetricDefinition(
        id="sga_expense",
        name="Selling, General & Administrative Expense",
        formula="Direct from income statement",
        unit="USD",
        components=[],
        caveats=[
            "Includes sales commissions, marketing, executive compensation, and corporate overhead",
            "SGA as percentage of revenue indicates overhead efficiency",
            "Can include significant stock-based compensation",
        ],
        related_metrics=["revenue", "operating_income", "rd_expense"],
        typical_ranges={"tech": (5e9, 30e9), "banking": (10e9, 40e9)},
        category="profitability",
        description="Selling, general, and administrative expenses.",
    )
)

# ============================================================
# Bank-Specific Metrics
# ============================================================

_register(
    MetricDefinition(
        id="net_interest_income",
        name="Net Interest Income",
        formula="interest_income - interest_expense",
        unit="USD",
        components=[],
        caveats=[
            "Primary revenue source for banks — equivalent to 'revenue' for operating companies",
            "Highly sensitive to interest rate environment (Fed funds rate)",
            "Rising rates generally help banks (wider net interest margin)",
            "Compare using net interest margin (NII / earning assets) not absolute NII",
        ],
        related_metrics=["noninterest_income", "revenue"],
        typical_ranges={"banking": (10e9, 30e9), "tech": (None, None)},
        category="revenue",
        description="Interest income minus interest expense. Primary revenue driver for banks.",
        applicable_to_banks=True,
    )
)

_register(
    MetricDefinition(
        id="noninterest_income",
        name="Noninterest Income",
        formula="Direct from filing (fees, trading, investment banking, etc.)",
        unit="USD",
        components=[],
        caveats=[
            "Includes diverse sources: advisory fees, trading revenue, asset management fees",
            "More volatile than net interest income",
            "Investment banking revenue is cyclical (tied to M&A and IPO markets)",
        ],
        related_metrics=["net_interest_income", "revenue"],
        typical_ranges={"banking": (5e9, 25e9), "tech": (None, None)},
        category="revenue",
        description="Non-interest revenue for banks: fees, commissions, trading, etc.",
        applicable_to_banks=True,
    )
)


# ============================================================
# Lookup Functions
# ============================================================


def get_metric(metric_id: str) -> MetricDefinition | None:
    """Look up a metric definition by ID."""
    return METRICS.get(metric_id)


def get_metrics_by_category(category: str) -> list[MetricDefinition]:
    """Get all metrics in a category."""
    return [m for m in METRICS.values() if m.category == category]


def get_all_metric_ids() -> list[str]:
    """Get all registered metric IDs."""
    return list(METRICS.keys())


def get_caveats_for_metrics(metric_ids: list[str]) -> dict[str, list[str]]:
    """Get caveats for a list of metrics."""
    return {mid: METRICS[mid].caveats for mid in metric_ids if mid in METRICS}


def get_components(metric_id: str) -> list[str]:
    """Get the component metrics needed to calculate a derived metric."""
    m = METRICS.get(metric_id)
    return m.components if m else []


def is_applicable_to_company(metric_id: str, industry: str) -> bool:
    """Check if a metric is meaningful for a given industry."""
    m = METRICS.get(metric_id)
    if not m:
        return False
    if industry.lower() in ("banking", "financial", "bank"):
        return m.applicable_to_banks
    return True


def format_metric_context(metric_id: str) -> str:
    """Format a metric definition as context text for the LLM prompt."""
    m = METRICS.get(metric_id)
    if not m:
        return f"Unknown metric: {metric_id}"

    lines = [
        f"**{m.name}** ({m.id})",
        f"Formula: {m.formula}",
        f"Unit: {m.unit}",
        f"Category: {m.category}",
    ]
    if m.components:
        lines.append(f"Components: {', '.join(m.components)}")
    if m.caveats:
        lines.append("Caveats:")
        for c in m.caveats:
            lines.append(f"  - {c}")
    if m.typical_ranges:
        ranges = []
        for industry, (lo, hi) in m.typical_ranges.items():
            if lo is not None and hi is not None:
                if m.unit == "percentage":
                    ranges.append(f"{industry}: {lo*100:.0f}%-{hi*100:.0f}%")
                elif m.unit == "ratio":
                    ranges.append(f"{industry}: {lo:.1f}-{hi:.1f}")
                else:
                    ranges.append(f"{industry}: {lo/1e9:.0f}B-{hi/1e9:.0f}B")
        if ranges:
            lines.append(f"Typical ranges: {'; '.join(ranges)}")

    return "\n".join(lines)
