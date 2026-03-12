"""Response formatting — structures agent output with answer, methodology, sources, confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.guardrails.confidence import ConfidenceLevel, ConfidenceScore

if TYPE_CHECKING:
    from src.investigation.decomposition import DecompositionResult


@dataclass
class AgentResponse:
    answer: str
    methodology: str | None = None
    sources: str | None = None
    confidence: ConfidenceScore | None = None
    follow_ups: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_refusal: bool = False
    raw_data: dict | None = None  # For API consumers
    decomposition: DecompositionResult | None = None

    def format_text(self) -> str:
        """Format as readable text for CLI / chat display."""
        parts = []

        # Answer
        parts.append(self.answer)

        # Methodology
        if self.methodology:
            parts.append(f"\n**Methodology**\n{self.methodology}")

        # Sources
        if self.sources:
            parts.append(f"\n**Sources**\n{self.sources}")

        # Confidence
        if self.confidence:
            level = self.confidence.level.value
            score = self.confidence.score
            emoji = _confidence_indicator(self.confidence.level)
            parts.append(
                f"\n**Confidence: {level} ({score:.2f})** {emoji}\n{self.confidence.summary}"
            )

        # Warnings
        if self.warnings:
            parts.append("\n**Warnings**")
            for w in self.warnings:
                parts.append(f"- {w}")

        # Decomposition
        if self.decomposition:
            parts.append(f"\n{self.decomposition.format_text()}")

        # Follow-ups
        if self.follow_ups:
            parts.append("\n**Explore Further**")
            for i, f in enumerate(self.follow_ups, 1):
                parts.append(f"  {i}. {f}")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "answer": self.answer,
            "methodology": self.methodology,
            "sources": self.sources,
            "confidence": {
                "level": self.confidence.level.value,
                "score": self.confidence.score,
                "summary": self.confidence.summary,
            }
            if self.confidence
            else None,
            "follow_ups": self.follow_ups,
            "warnings": self.warnings,
            "is_refusal": self.is_refusal,
            "decomposition": self.decomposition.format_text() if self.decomposition else None,
        }


def _confidence_indicator(level: ConfidenceLevel) -> str:
    return {
        ConfidenceLevel.HIGH: "[OK]",
        ConfidenceLevel.MEDIUM: "[~]",
        ConfidenceLevel.LOW: "[!]",
        ConfidenceLevel.REFUSE: "[X]",
    }.get(level, "")


def build_refusal_response(reason: str, suggestion: str) -> AgentResponse:
    """Build a graceful refusal response."""
    return AgentResponse(
        answer=suggestion,
        is_refusal=True,
        confidence=ConfidenceScore(
            level=ConfidenceLevel.REFUSE,
            score=0.0,
            factors=[],
            summary=reason,
        ),
    )
