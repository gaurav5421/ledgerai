"""Provenance Tracking — source attribution for every claim.

Tags answers with source filings, calculation chains, and data freshness.
"""

from dataclasses import dataclass, field


@dataclass
class SourceReference:
    ticker: str
    filing_type: str  # "10-K" or "10-Q"
    period_end: str  # "2024-09-28"
    fiscal_label: str  # "FY2024 Q4" or "FY2024"
    metric: str
    value: float
    unit: str
    xbrl_tag: str | None = None


@dataclass
class CalculationStep:
    description: str
    formula: str
    inputs: dict[str, float]
    result: float


@dataclass
class ProvenanceRecord:
    sources: list[SourceReference] = field(default_factory=list)
    calculations: list[CalculationStep] = field(default_factory=list)
    data_freshness: str | None = None  # Latest period_end in sources

    def add_source(self, **kwargs) -> None:
        self.sources.append(SourceReference(**kwargs))
        # Update freshness
        period = kwargs.get("period_end")
        if period and (self.data_freshness is None or period > self.data_freshness):
            self.data_freshness = period

    def add_calculation(self, description: str, formula: str, inputs: dict, result: float) -> None:
        self.calculations.append(
            CalculationStep(
                description=description,
                formula=formula,
                inputs=inputs,
                result=result,
            )
        )

    def format_sources(self) -> str:
        """Format sources for display."""
        if not self.sources:
            return "No sources available."
        lines = []
        for s in self.sources:
            lines.append(
                f"- {s.ticker} {s.filing_type}, {s.fiscal_label} "
                f"(period ending {s.period_end}): "
                f"{s.metric} = {_format_value(s.value, s.unit)}"
            )
        return "\n".join(lines)

    def format_calculations(self) -> str:
        """Format calculation chain for display."""
        if not self.calculations:
            return ""
        lines = ["Calculation:"]
        for c in self.calculations:
            input_str = ", ".join(f"{k}={v}" for k, v in c.inputs.items())
            lines.append(f"  {c.description}: {c.formula}")
            lines.append(f"    Inputs: {input_str}")
            lines.append(f"    Result: {c.result}")
        return "\n".join(lines)

    def format_full(self) -> str:
        """Full provenance display."""
        parts = [self.format_sources()]
        calc = self.format_calculations()
        if calc:
            parts.append(calc)
        if self.data_freshness:
            parts.append(f"Data freshness: most recent period ending {self.data_freshness}")
        return "\n".join(parts)


def _format_value(value: float, unit: str) -> str:
    if unit == "USD":
        if abs(value) >= 1e12:
            return f"${value / 1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"${value / 1e9:.1f}B"
        elif abs(value) >= 1e6:
            return f"${value / 1e6:.1f}M"
        else:
            return f"${value:,.0f}"
    elif unit == "percentage":
        return f"{value * 100:.1f}%"
    elif unit == "USD/share":
        return f"${value:.2f}"
    elif unit == "ratio":
        return f"{value:.2f}"
    else:
        return f"{value:,.0f} {unit}"


def build_fiscal_label(fiscal_year: int, fiscal_quarter: int | None, is_quarterly: bool) -> str:
    """Build a human-readable fiscal period label."""
    if is_quarterly and fiscal_quarter:
        return f"FY{fiscal_year} Q{fiscal_quarter}"
    else:
        return f"FY{fiscal_year}"
