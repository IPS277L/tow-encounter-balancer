from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import StaggerChoice, StaggerRequest
from towr.domain.injury_models import (
    CharacterWoundRequest, DecisionOwner, MonstrosityImpactChoice, MonstrosityImpactRequest,
    ProfileStateChangeRequest, WoundNegationOption, WoundTableRoll,
)
from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementRequest
from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest
from towr.domain.npc_ranged_scenario_models import NpcRangedScenario
from towr.domain.npc_ranged_scenario_result_models import (
    NpcRangedScenarioResult, ranged_scenario_candidates, ranged_scenario_terminal_side,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainStep, NpcRoundsChainSummary
from towr.domain.npc_rounds_models import NpcRoundsOutcome, NpcRoundsRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.rules.dice import RandomSource
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement
from towr.rules.npc_round_advance import advance_npc_round, apply_npc_round_advance
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion
from towr.rules.test_resolution import KeepAllFailures


@dataclass(frozen=True, slots=True)
class _Candidates:
    scenario: NpcRangedScenario

    def get_candidates(self, context: NpcAttackSelectionRequest, spatial: SpatialBattleState) -> NpcAttackSelectionRequest:
        return replace(context, candidates=ranged_scenario_candidates(self.scenario, context))

    def get_next_round(self, current: NpcRoundRequest, spatial_state: SpatialBattleState) -> NpcRoundAdvanceRequest:
        raise AssertionError("scenario owns round advance and checks terminal outcome first")


@dataclass(frozen=True, slots=True)
class _Decisions(KeepAllFailures):
    choice: StaggerChoice

    def choose_repeated_stagger(self, *, request: StaggerRequest,
                               allowed_choices: tuple[StaggerChoice, ...]) -> StaggerChoice:
        if self.choice not in allowed_choices:
            raise ValueError("scenario Staggered policy is unavailable")
        return self.choice

    def choose_wound_negation(self, *, request: CharacterWoundRequest, table_roll: WoundTableRoll,
                             options: tuple[WoundNegationOption, ...]) -> str | None:
        raise ValueError("character Wound decisions are outside the Minion scenario")

    def choose_monstrosity_impact(self, *, request: MonstrosityImpactRequest, owner: DecisionOwner,
                                 choices: tuple[MonstrosityImpactChoice, ...]) -> MonstrosityImpactChoice:
        raise ValueError("Monstrosity decisions are outside the Minion scenario")


def run_npc_ranged_scenario(scenario: NpcRangedScenario, rng: RandomSource) -> NpcRangedScenarioResult:
    """Execute the admitted fixed policy until defeat, budget, or an explicit unsupported stop."""
    if not isinstance(scenario, NpcRangedScenario):
        raise TypeError("ranged scenario runner requires a validated NpcRangedScenario")
    current, spatial = scenario.initial.current, scenario.initial.spatial_state
    candidates, decisions = _Candidates(scenario), _Decisions(scenario.repeated_stagger_choice)
    steps: list[NpcRoundsChainStep] = []
    # Every nonterminal resume consumes a distinct Minion defeat. Every other
    # iteration advances one round or returns. No budget reset on resume.
    while True:
        result = run_npc_rounds(NpcRoundsRequest(current, spatial, 1), candidates, candidates, rng, decisions=decisions)
        steps.append(result)
        current, spatial = result.current, result.spatial_state
        if result.outcome is NpcRoundsOutcome.PENDING_FOLLOW_UPS:
            attacks = tuple(step for step in result.rounds[0].steps if isinstance(step, NpcRosterAttackExecutionResult))
            if (len(current.pending_follow_ups) != 1
                    or not isinstance(current.pending_follow_ups[0], ProfileStateChangeRequest) or not attacks):
                return NpcRangedScenarioResult(scenario, NpcRoundsChainSummary(tuple(steps)))
            attack = attacks[-1]
            execution = attack.execution
            decision = next(item for item in scenario.policy_for(execution.actor_id).defeat_decisions
                            if item.target_id == execution.target_id)
            ack = acknowledge_minion_defeat(MinionDefeatAcknowledgementRequest(
                execution.request_id + ":defeat", current, attack, decision))
            current = apply_minion_defeat_acknowledgement(current, ack)
            exclusion = None
            if execution.target_id not in current.round_state.completed_turn_entity_ids:
                exclusion = exclude_defeated_npc(NpcRoundExclusionRequest(
                    execution.request_id + ":exclude", current, execution.target_id))
                current = apply_npc_round_exclusion(current, exclusion)
            if ranged_scenario_terminal_side(current) is not None:
                return NpcRangedScenarioResult(scenario, NpcRoundsChainSummary(tuple(steps)), ack, exclusion)
            steps.append(ack)
            if exclusion is not None:
                steps.append(exclusion)
            continue
        if result.outcome is not NpcRoundsOutcome.ROUND_LIMIT:
            return NpcRangedScenarioResult(scenario, NpcRoundsChainSummary(tuple(steps)))
        if current.round_state.round_number == scenario.initial.max_rounds:
            return NpcRangedScenarioResult(scenario, NpcRoundsChainSummary(tuple(steps)))
        alive = tuple(p.turn_participant for p in current.state.roster.participants if not p.state.injury.defeated)
        ids = {p.entity_id for p in alive}
        order = tuple(actor for actor in scenario.initial.current.actor_order if actor in ids)
        advanced = advance_npc_round(NpcRoundAdvanceRequest(
            f"{scenario.initial.current.id}:advance:{current.round_state.round_number}", current, spatial, alive, order))
        current, spatial = apply_npc_round_advance(current, spatial, advanced)
        steps.append(advanced)
