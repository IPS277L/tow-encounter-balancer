from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TypeAlias

from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementResult
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_give_ground_models import NpcGiveGroundConsumptionResult
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_blunderbuss_defeat_models import NpcBlunderbussDefeatAcknowledgementResult
from towr.domain.npc_blunderbuss_give_ground_models import NpcBlunderbussGiveGroundConsumptionResult
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionResult
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementResult
from towr.domain.npc_nearby_give_ground_models import NpcNearbyGiveGroundConsumptionResult
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionResult
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_round_advance_models import NpcRoundAdvanceResult
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome, NpcRoundsResult
from towr.domain.npc_rounds_summary_models import NpcRoundsParticipantSummary, NpcRoundsSummary
from towr.domain.spatial_models import SpatialBattleState


NpcRoundsChainStep: TypeAlias = (
    NpcRoundsResult | NpcGiveGroundConsumptionResult | MinionDefeatAcknowledgementResult
    | NpcRoundExclusionResult | NpcRoundAdvanceResult
    | NpcNearbyStaggerExecutionResult | NpcNearbyDefeatAcknowledgementResult | NpcNearbyGiveGroundConsumptionResult
    | NpcNearbyCompletionResult | NpcBlunderbussDefeatAcknowledgementResult | NpcBlunderbussGiveGroundConsumptionResult
)

NpcRoundsDefeatAcknowledgement: TypeAlias = (
    MinionDefeatAcknowledgementResult | NpcNearbyDefeatAcknowledgementResult | NpcBlunderbussDefeatAcknowledgementResult
)


@dataclass(frozen=True, slots=True)
class NpcRoundsChainSummary:
    """Projection of a continuous journal, beginning and ending with a runner call."""

    source_steps: tuple[NpcRoundsChainStep, ...]

    def __post_init__(self) -> None:
        steps = tuple(self.source_steps)
        if not all(isinstance(step, NpcRoundsChainStep) for step in steps):
            raise TypeError("NPC rounds chain requires typed completed results")
        if not steps or not isinstance(steps[0], NpcRoundsResult) or not isinstance(steps[-1], NpcRoundsResult):
            raise ValueError("NPC rounds chain must begin and end with a runner result")
        current, spatial = steps[0].source_request.current, steps[0].source_request.spatial_state
        attacks: dict[str, NpcBlunderbussAttackExecutionResult] = {}
        nearby: NpcNearbyConsequenceChain | None = None
        completed: NpcNearbyCompletionResult | None = None
        for index, step in enumerate(steps):
            source = step.source_request
            if isinstance(step, NpcNearbyStaggerExecutionResult):
                primary = source.primary_attack
                attack = attacks.get(primary.attack.request_id) if primary is not None else None
                if (nearby is not None or attack is None or primary != attack.primary_attack
                        or source.state != current.state or current != attack.continuation):
                    raise ValueError("nearby batch source differs from the journal's primary Attack/current snapshot")
                nearby = NpcNearbyConsequenceChain(step, spatial)
                completed = None
                current = replace(current, state=nearby.state)
                continue
            if isinstance(step, (NpcNearbyDefeatAcknowledgementResult, NpcNearbyGiveGroundConsumptionResult)):
                if nearby is None:
                    raise ValueError("secondary consequence requires its batch in the journal")
                nearby = replace(nearby, steps=(*nearby.steps, step))
                current, spatial = replace(current, state=nearby.state), nearby.spatial_state
                continue
            if isinstance(step, NpcNearbyCompletionResult):
                if nearby is None or source.chain != nearby:
                    raise ValueError("nearby completion differs from the full journal consequence prefix")
            elif isinstance(step, (NpcBlunderbussDefeatAcknowledgementResult, NpcBlunderbussGiveGroundConsumptionResult)):
                primary_id = source.attack.primary_attack.attack.request_id
                if nearby is not None or source.completion != completed or source.attack != attacks.get(primary_id):
                    raise ValueError("primary consequence differs from the journal Attack/completion/decisions")
            elif nearby is not None and not isinstance(step, NpcRoundsResult):
                raise ValueError("unfinished nearby chain permits only its consequences or runner observations")
            expected_current = source.source if isinstance(step, NpcRoundExclusionResult) else source.current
            if current != expected_current:
                raise ValueError(f"NPC rounds chain step {index} source differs from current snapshot")
            if isinstance(step, (NpcRoundsResult, NpcGiveGroundConsumptionResult, NpcRoundAdvanceResult,
                                 NpcNearbyCompletionResult, NpcBlunderbussDefeatAcknowledgementResult,
                                 NpcBlunderbussGiveGroundConsumptionResult)):
                if spatial != source.spatial_state:
                    raise ValueError(f"NPC rounds chain step {index} source differs from spatial snapshot")
                spatial = step.spatial_state
            if isinstance(step, NpcRoundsResult):
                for combat_round in step.rounds:
                    for action in combat_round.steps:
                        if isinstance(action, NpcBlunderbussAttackExecutionResult):
                            identifier = action.primary_attack.attack.request_id
                            if identifier in attacks:
                                raise ValueError("Blunderbuss Attack is repeated in the journal")
                            attacks[identifier] = action
                current = step.current
            elif isinstance(step, NpcRoundExclusionResult):
                current = replace(current, round_state=step.round_state)
            else:
                current = step.continuation
            if isinstance(step, NpcNearbyCompletionResult):
                completed, nearby = step, None
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
    def defeat_acknowledgements(self) -> tuple[NpcRoundsDefeatAcknowledgement, ...]:
        """Explicit decisions with their full sources; never inferred from history IDs."""
        return tuple(step for step in self.source_steps if isinstance(step, NpcRoundsDefeatAcknowledgement))

    @property
    def participants(self) -> tuple[NpcRoundsParticipantSummary, ...]:
        actor_ids = {}
        for step in self.source_steps:
            if isinstance(step, NpcRoundsResult):
                actor_ids.update((record.actor_id, None) for record in NpcRoundsSummary(step).participants)
            elif isinstance(step, NpcNearbyStaggerExecutionResult):
                actor_ids.update((target.target_id, None) for target in step.resolution.targets)
        roster = self.current.state.roster
        records = []
        for actor_id in actor_ids:
            state = roster.participant(actor_id).state
            records.append(NpcRoundsParticipantSummary(actor_id, state.side, state.injury.wounds,
                                                       state.injury.defeated, state.injury.conditions))
        return tuple(records)
