"""Investigation Workflows — metric decomposition, follow-ups, and multi-turn state."""

from src.investigation.decomposition import (
    ComponentChange,
    DecompositionResult,
    decompose_metric_change,
    get_decomposition_paths,
    has_decomposition,
)
from src.investigation.follow_ups import generate_contextual_follow_ups
from src.investigation.session import InvestigationDepth, InvestigationSession, TurnRecord

__all__ = [
    "ComponentChange",
    "DecompositionResult",
    "decompose_metric_change",
    "generate_contextual_follow_ups",
    "get_decomposition_paths",
    "has_decomposition",
    "InvestigationDepth",
    "InvestigationSession",
    "TurnRecord",
]
