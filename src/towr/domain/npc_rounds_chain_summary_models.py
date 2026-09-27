from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TypeAlias

from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementResult
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_give_ground_models import NpcGiveGroundConsumptionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceResult
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome, NpcRoundsResult
from towr.domain.npc_rounds_summary_models import NpcRoundsParticipantSummary, NpcRoundsSummary
from towr.domain.spatial_models import SpatialBattleState


NpcRoundsChainStep: TypeAlias = (
    NpcRoundsResult | NpcGiveGroundConsumptionResult | MinionDefeatAcknowledgementResult
    | NpcRoundExclusionResult | NpcRoundAdvanceResult
)


@dataclass(frozen=True, slots=True)
class NpcRoundsChainSummary:
    """Projection of a continuous journal, beginning and ending with a runner call."""

    source_steps: tuple[NpcRoundsChainStep, ...]

    def __post_init__(self) -> None:
        steps = tuple(self.source_steps)
        if not all(isinstance(step, (NpcRoundsResult, NpcGiveGroundConsumptionResult,
                                    MinionDefeatAcknowledgementResult, NpcRoundExclusionResult,
                                    NpcRoundAdvanceResult)) for step in steps):
            raise TypeError("NPC rounds chain requires typed completed results")
        if not steps or not isinstance(steps[0], NpcRoundsResult) or not isinstance(steps[-1], NpcRoundsResult):
            raise ValueError("NPC rounds chain must begin and end with a runner result")
        current, spatial = steps[0].source_request.current, steps[0].source_request.spatial_state
        for index, step in enumerate(steps):
            source = step.source_request
            expected_current = source.source if isinstance(step, NpcRoundExclusionResult) else source.current
            if current != expected_current:
                raise ValueError(f"NPC rounds chain step {index} source differs from current snapshot")
            if isinstance(step, (NpcRoundsResult, NpcGiveGroundConsumptionResult, NpcRoundAdvanceResult)):
                if spatial != source.spatial_state:
                    raise ValueError(f"NPC rounds chain step {index} source differs from spatial snapshot")
                spatial = step.spatial_state
            if isinstance(step, NpcRoundsResult):
                current = step.current
            elif isinstance(step, NpcRoundExclusionResult):
                current = replace(current, round_state=step.round_state)
            else:
                current = step.continuation
        object.__setattr__(self, "source_steps", steps)

    @property
    def call_summaries(self) -> tuple[NpcRoundsSummary, ...]:
        return tuple(NpcRoundsSummary(step) for step in self.source_steps if isinstance(step, NpcRoundsResult))

    @property
    def final_summary(self) -> NpcRoundsSummary:
        return NpcRoundsSummary(self.source_steps[-1])

    @property
    def current(self) -> NpcRoundRequest:
        return self.final_summary.source_result.current

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.final_summary.source_result.spatial_state

    @property
    def outcome(self) -> NpcRoundsOutcome:
        return self.final_summary.outcome

    @property
    def blocked_reason(self) -> NpcAttackSelectionBlock | None:
        return self.final_summary.blocked_reason

    @property
    def pending_follow_up_count(self) -> int:
        return self.final_summary.pending_follow_up_count

    @property
    def initial_round_number(self) -> int:
        return self.call_summaries[0].initial_round_number

    @property
    def final_round_number(self) -> int:
        return self.final_summary.final_round_number

    @property
    def visited_round_count(self) -> int:
        """Distinct rounds observed by runner calls, including complete input."""
        return len({result.round_state.round_number for step in self.source_steps
                    if isinstance(step, NpcRoundsResult) for result in step.rounds})

    @property
    def newly_completed_round_count(self) -> int:
        """Completions performed by the runner calls, excluding external transitions."""
        return sum(summary.newly_completed_round_count for summary in self.call_summaries)

    @property
    def executed_attack_count(self) -> int:
        return sum(summary.executed_attack_count for summary in self.call_summaries)

    @property
    def defeat_acknowledgements(self) -> tuple[MinionDefeatAcknowledgementResult, ...]:
        """Explicit decisions with their full sources; never inferred from history IDs."""
        return tuple(step for step in self.source_steps if isinstance(step, MinionDefeatAcknowledgementResult))

    @property
    def participants(self) -> tuple[NpcRoundsParticipantSummary, ...]:
        actor_ids = dict.fromkeys(record.actor_id for summary in self.call_summaries for record in summary.participants)
        roster = self.current.state.roster
        records = []
        for actor_id in actor_ids:
            state = roster.participant(actor_id).state
            records.append(NpcRoundsParticipantSummary(actor_id, state.side, state.injury.wounds,
                                                       state.injury.defeated, state.injury.conditions))
        return tuple(records)
