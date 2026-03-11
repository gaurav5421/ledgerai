"""Entity context — per-company knowledge the agent needs.

Includes business segments, reporting quirks, major events,
and comparable companies.
"""

from dataclasses import dataclass


@dataclass
class Segment:
    name: str
    description: str


@dataclass
class MajorEvent:
    date: str  # YYYY-MM or YYYY-QN
    description: str
    impact: str  # How it affects financial analysis


@dataclass
class CompanyContext:
    ticker: str
    name: str
    industry: str
    description: str
    segments: list[Segment]
    major_events: list[MajorEvent]
    reporting_quirks: list[str]
    comparable_companies: list[str]  # tickers


COMPANY_CONTEXTS: dict[str, CompanyContext] = {}


def _register(ctx: CompanyContext) -> None:
    COMPANY_CONTEXTS[ctx.ticker] = ctx


# ============================================================
# Apple
# ============================================================

_register(
    CompanyContext(
        ticker="AAPL",
        name="Apple Inc.",
        industry="tech_hardware",
        description=(
            "Consumer electronics and services company. Hardware"
            " (iPhone, Mac, iPad, Wearables) drives the majority"
            " of revenue, but Services (App Store, iCloud, Apple"
            " Music, Apple TV+) is the highest-margin and"
            " fastest-growing segment."
        ),
        segments=[
            Segment("Products", "iPhone, Mac, iPad, Wearables/Home/Accessories"),
            Segment("Services", "App Store, iCloud, Apple Music, Apple TV+, AppleCare, licensing"),
        ],
        major_events=[
            MajorEvent(
                "2024-Q1",
                "Apple Vision Pro launched — minimal revenue impact in first year",
                "Increased R&D expense; negligible revenue contribution",
            ),
            MajorEvent(
                "2023",
                "iPhone 15 introduced USB-C — supply chain implications",
                "Minimal financial impact, but unit ASPs remained stable",
            ),
            MajorEvent(
                "2022-Q4",
                "China COVID lockdowns disrupted iPhone 14 Pro production",
                "Q1 FY2023 revenue missed estimates due to supply constraints",
            ),
        ],
        reporting_quirks=[
            "Fiscal year ends in late September (last Saturday). FY2024 ended Sep 28, 2024.",
            "Q1 is the holiday quarter (Oct-Dec) — always the strongest revenue quarter.",
            "Apple does NOT break out unit sales since 2019. Revenue by product line is available.",
            "Services revenue has different seasonality than Products.",
            "Gross margin is heavily influenced by product mix"
            " (Services margin ~70% vs Products ~36%).",
        ],
        comparable_companies=["MSFT", "GOOGL", "AMZN"],
    )
)

# ============================================================
# Microsoft
# ============================================================

_register(
    CompanyContext(
        ticker="MSFT",
        name="Microsoft Corporation",
        industry="tech_software",
        description=(
            "Enterprise software, cloud computing (Azure), and"
            " gaming company. Three reporting segments:"
            " Intelligent Cloud, Productivity & Business"
            " Processes, and More Personal Computing."
        ),
        segments=[
            Segment("Intelligent Cloud", "Azure, SQL Server, GitHub, Enterprise Services"),
            Segment("Productivity & Business Processes", "Office 365, LinkedIn, Dynamics"),
            Segment("More Personal Computing", "Windows, Xbox, Surface, Search/advertising"),
        ],
        major_events=[
            MajorEvent(
                "2023-Q1",
                "Activision Blizzard acquisition closed (Oct 2023, $69B)",
                "Significant revenue and cost boost to Gaming"
                " segment. Makes YoY comparisons misleading"
                " for 4 quarters.",
            ),
            MajorEvent(
                "2023",
                "Major AI investment — Copilot integrated across products",
                "Increased capex for AI infrastructure; emerging revenue from AI services",
            ),
            MajorEvent(
                "2022",
                "LinkedIn hiring slowdown and impairment charges",
                "One-time charges affected operating income",
            ),
        ],
        reporting_quirks=[
            "Fiscal year ends June 30. 'FY2025' runs Jul 2024 - Jun 2025.",
            "Q2 (Oct-Dec) is the holiday quarter — strong for"
            " Xbox/Surface but enterprise drives most revenue.",
            "Azure revenue growth is reported in constant currency — watch for FX impact.",
            "Microsoft reports 'revenue growth in constant currency' which strips out FX effects.",
            "Activision acquisition makes FY2024 gaming comparisons vs FY2023 unreliable.",
        ],
        comparable_companies=["AAPL", "GOOGL", "AMZN"],
    )
)

# ============================================================
# Alphabet (Google)
# ============================================================

_register(
    CompanyContext(
        ticker="GOOGL",
        name="Alphabet Inc.",
        industry="tech_software",
        description=(
            "Digital advertising (Google Search, YouTube),"
            " cloud computing (Google Cloud), and Other Bets"
            " (Waymo, Verily, etc.). Advertising remains"
            " ~75% of revenue."
        ),
        segments=[
            Segment(
                "Google Services", "Search, YouTube, Android, Chrome, Play, hardware, subscriptions"
            ),
            Segment("Google Cloud", "GCP, Workspace (formerly G Suite)"),
            Segment("Other Bets", "Waymo, Verily, Calico, X, and other moonshots"),
        ],
        major_events=[
            MajorEvent(
                "2024",
                "First-ever dividend declared ($0.20/share) and $70B buyback authorized",
                "New capital return program — meaningful for per-share metrics going forward",
            ),
            MajorEvent(
                "2024-Q1",
                "Major layoffs (12,000+ employees in late 2023, effects in 2024)",
                "Severance charges in Q4 2023 / Q1 2024; lower headcount improves margins",
            ),
            MajorEvent(
                "2023",
                "Google Cloud turned profitable for the first time",
                "Margin expansion story — Cloud segment now contributing positive operating income",
            ),
        ],
        reporting_quirks=[
            "Calendar fiscal year (Jan-Dec).",
            "Other Bets segment consistently loses money — it dilutes overall margins.",
            "YouTube advertising revenue is broken out separately since Q4 2019.",
            "Traffic Acquisition Costs (TAC) are a major cost item — reported separately.",
            "Stock-based compensation is very high relative to"
            " revenue — GAAP vs non-GAAP gap is significant.",
        ],
        comparable_companies=["MSFT", "AMZN"],
    )
)

# ============================================================
# Amazon
# ============================================================

_register(
    CompanyContext(
        ticker="AMZN",
        name="Amazon.com, Inc.",
        industry="tech_mixed",
        description=(
            "E-commerce, cloud computing (AWS), advertising,"
            " and subscription services. AWS is the primary"
            " profit driver despite being ~17% of revenue."
        ),
        segments=[
            Segment("North America", "E-commerce, advertising, and subscription in NA"),
            Segment("International", "E-commerce and subscriptions outside NA"),
            Segment("AWS", "Amazon Web Services — cloud infrastructure and platform services"),
        ],
        major_events=[
            MajorEvent(
                "2024",
                "Massive AI/cloud infrastructure investment — capex surge",
                "Capex increased significantly for AI data"
                " centers; affects FCF and D&A going forward",
            ),
            MajorEvent(
                "2023",
                "Cost optimization program — layoffs and fulfillment network restructuring",
                "Improved margins across segments after 2022 over-investment",
            ),
            MajorEvent(
                "2022",
                "Rivian investment write-down and over-expansion of fulfillment",
                "Large investment losses and margin compression in North America segment",
            ),
        ],
        reporting_quirks=[
            "Calendar fiscal year (Jan-Dec).",
            "AWS margin is much higher than e-commerce — segment mix drives overall profitability.",
            "International segment has historically been"
            " unprofitable — recently turning profitable.",
            "Advertising revenue is not a separate segment"
            " but is broken out in supplementary data.",
            "Free cash flow calculation should subtract finance"
            " lease principal payments for a truer picture.",
            "Amazon capitalizes significant software development costs.",
        ],
        comparable_companies=["MSFT", "GOOGL"],
    )
)

# ============================================================
# JPMorgan Chase
# ============================================================

_register(
    CompanyContext(
        ticker="JPM",
        name="JPMorgan Chase & Co.",
        industry="banking",
        description=(
            "Largest US bank by assets. Four major business"
            " lines: Consumer & Community Banking (CCB),"
            " Corporate & Investment Bank (CIB), Commercial"
            " Banking (CB), and Asset & Wealth Management"
            " (AWM)."
        ),
        segments=[
            Segment(
                "CCB", "Consumer & Community Banking — retail banking, cards, auto, home lending"
            ),
            Segment(
                "CIB",
                "Corporate & Investment Bank — investment banking, markets, securities services",
            ),
            Segment("CB", "Commercial Banking — middle market, commercial real estate"),
            Segment("AWM", "Asset & Wealth Management — private banking, asset management"),
        ],
        major_events=[
            MajorEvent(
                "2023-Q2",
                "First Republic Bank acquisition (May 2023)",
                "Added ~$200B in assets. Bargain purchase gain"
                " in Q2 2023 inflated net income. Makes YoY"
                " comparisons tricky for several quarters.",
            ),
            MajorEvent(
                "2024",
                "FDIC special assessment charge for bank failures",
                "One-time charge affected Q4 2023 / Q1 2024 results",
            ),
            MajorEvent(
                "2023",
                "Interest rate environment — rates peaked",
                "Net interest income expanded significantly"
                " as rates rose; NII may compress as rates"
                " decline",
            ),
        ],
        reporting_quirks=[
            "Calendar fiscal year (Jan-Dec).",
            "Banks do NOT report gross profit or gross margin — use net interest margin instead.",
            "Provision for credit losses is a major income statement item unique to banks.",
            "Trading revenue (in CIB) can be very volatile quarter to quarter.",
            "ROE and ROTCE (return on tangible common equity)"
            " are the key profitability metrics for banks.",
            "CET1 capital ratio is a critical regulatory"
            " metric — minimum ~4.5% but JPM targets ~13%.",
            "Revenue for banks = Net Interest Income +"
            " Noninterest Income (not directly comparable"
            " to tech revenue).",
            "Free cash flow is not a meaningful metric for banks.",
        ],
        comparable_companies=[],  # No other banks in our dataset currently
    )
)


# ============================================================
# Lookup Functions
# ============================================================


def get_company_context(ticker: str) -> CompanyContext | None:
    return COMPANY_CONTEXTS.get(ticker)


def get_comparable_companies(ticker: str) -> list[str]:
    ctx = COMPANY_CONTEXTS.get(ticker)
    return ctx.comparable_companies if ctx else []


def get_segments(ticker: str) -> list[Segment]:
    ctx = COMPANY_CONTEXTS.get(ticker)
    return ctx.segments if ctx else []


def get_reporting_quirks(ticker: str) -> list[str]:
    ctx = COMPANY_CONTEXTS.get(ticker)
    return ctx.reporting_quirks if ctx else []


def get_major_events(ticker: str) -> list[MajorEvent]:
    ctx = COMPANY_CONTEXTS.get(ticker)
    return ctx.major_events if ctx else []


def format_company_context(ticker: str) -> str:
    """Format company context as text for the LLM prompt."""
    ctx = COMPANY_CONTEXTS.get(ticker)
    if not ctx:
        return f"No context available for {ticker}."

    lines = [
        f"**{ctx.name}** ({ctx.ticker}) — {ctx.industry}",
        ctx.description,
        "",
        "Segments:",
    ]
    for seg in ctx.segments:
        lines.append(f"  - {seg.name}: {seg.description}")

    if ctx.reporting_quirks:
        lines.append("")
        lines.append("Reporting notes:")
        for q in ctx.reporting_quirks:
            lines.append(f"  - {q}")

    if ctx.major_events:
        lines.append("")
        lines.append("Recent events affecting analysis:")
        for e in ctx.major_events:
            lines.append(f"  - [{e.date}] {e.description} — {e.impact}")

    return "\n".join(lines)


def get_all_tickers() -> list[str]:
    return list(COMPANY_CONTEXTS.keys())
