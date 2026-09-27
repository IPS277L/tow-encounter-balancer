from __future__ import annotations

from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainStep, NpcRoundsChainSummary
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.domain.npc_rounds_summary_models import NpcRoundsSummary


def summarize_npc_rounds(result: NpcRoundsResult) -> NpcRoundsSummary:
    """Summarize this call's journal and final participants without executing rules."""
    return NpcRoundsSummary(result)


def summarize_npc_rounds_chain(steps: tuple[NpcRoundsChainStep, ...]) -> NpcRoundsChainSummary:
    """Validate continuity and summarize completed calls and external transitions."""
    return NpcRoundsChainSummary(steps)
