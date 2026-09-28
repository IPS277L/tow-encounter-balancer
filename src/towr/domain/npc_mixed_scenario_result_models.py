from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.injury_models import ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementResult
from towr.domain.npc_attack_selection_models import NpcAttackCandidate, NpcAttackSelectionRequest, NpcAttackSelectionResult
from towr.domain.npc_mixed_scenario_models import NpcMixedScenario
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceResult
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.domain.npc_rounds_models import NpcRoundsOutcome, NpcRoundsResult
from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import CombatSide


class NpcMixedScenarioOutcome(str, Enum):
    OBJECTIVE_ACHIEVED = "objective_achieved"
    SIDE_DEFEATED = "side_defeated"
    ROUND_LIMIT = "round_limit"
    UNSUPPORTED_PATH = "unsupported_path"


def mixed_scenario_candidates(
    scenario: NpcMixedScenario, context: NpcAttackSelectionRequest, spatial: SpatialBattleState,
) -> tuple[NpcAttackCandidate, ...]:
    """Project ordered reachable targets and current Zone-local outnumbering.

    PG1.4 Equipment / Ranged Weapons p94; Rules / Attack Modifiers pp118-119.
    Distances, awareness and GM approval remain explicit supplied facts.
    """
    if not isinstance(scenario, NpcMixedScenario) or not isinstance(context, NpcAttackSelectionRequest):
        raise TypeError("mixed candidates require typed scenario and selection context")
    if not isinstance(spatial, SpatialBattleState):
        raise TypeError("mixed candidates require typed spatial state")
    expected_spatial = replace(scenario.initial.spatial_state, round_number=context.round_state.round_number)
    if spatial != expected_spatial:
        raise ValueError("mixed candidates require the scenario's stationary spatial state")
    facts, roster = scenario.facts, context.state.roster
    actor = roster.participant(context.actor_id)
    policy = scenario.policy_for(context.actor_id)
    attack = actor.definition.attacks[0]
    living_targets = tuple(target for target in policy.target_actor_ids
                           if not roster.participant(target).state.injury.defeated)
    close_enemy = any(scenario.range_for(context.actor_id, target) is RangedWeaponRange.CLOSE
                      for target in living_targets)
    zone_id = spatial.placement_for(context.actor_id).zone_id
    counted = tuple(p for p in roster.participants if not p.state.injury.defeated
                    and not p.state.injury.conditions.has(Condition.DEFENCELESS)
                    and spatial.placement_for(p.state.actor_id).zone_id == zone_id)
    allies = sum(p.state.side is actor.state.side for p in counted)
    enemies = len(counted) - allies
    modifiers = ((DiceModifier("RULE-COMBAT-009:outnumbering", 1),)
                 if attack.skill is Skill.MELEE and allies > enemies and policy.outnumbering_bonus_approved else ())
    candidates = []
    for target_id in living_targets:
        target = roster.participant(target_id)
        distance = scenario.range_for(context.actor_id, target_id)
        if attack.skill is Skill.MELEE and distance is not RangedWeaponRange.CLOSE:
            continue
        if attack.skill is Skill.SHOOTING and (close_enemy or distance is not RangedWeaponRange.MEDIUM):
            continue
        candidates.append(NpcAttackCandidate(
            context.id + ":target:" + target_id, attack.id, target_id,
            distance, close_enemy, False, facts.targets_aware, target.definition.protection[0].skill,
            target.protection_options(context.id), scenario.policy_for(target_id).can_leave_zone, False, modifiers,
        ))
    return tuple(candidates)


def mixed_scenario_terminal_side(current: NpcRoundRequest) -> CombatSide | None:
    """Surviving side, if only one remains; no inference about disposition."""
    sides = {p.state.side for p in current.state.roster.participants if not p.state.injury.defeated}
    return next(iter(sides)) if len(sides) == 1 else None


@dataclass(frozen=True, slots=True)
class NpcMixedScenarioResult:
    """Completed scenario or explicit technical stop, with full result sources.

    The runner report ends at a genuine runner stop. A terminal defeat may
    require one final acknowledgement/exclusion without another runner call.
    Those results remain explicit; no dummy turn or observation is fabricated.
    """

    source_scenario: NpcMixedScenario
    runner_report: NpcRoundsChainSummary
    terminal_acknowledgement: MinionDefeatAcknowledgementResult | None = None
    terminal_exclusion: NpcRoundExclusionResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_scenario, NpcMixedScenario):
            raise TypeError("scenario result requires its typed source")
        if not isinstance(self.runner_report, NpcRoundsChainSummary):
            raise TypeError("scenario result requires a typed runner report")
        scenario, report = self.source_scenario, self.runner_report
        if report.source_steps[0].source_request != replace(scenario.initial, max_rounds=1):
            raise ValueError("scenario report starts from a different initial source")
        if report.final_round_number > scenario.initial.max_rounds:
            raise ValueError("scenario report exceeds the global round budget")
        attacks = {}
        for step in report.source_steps:
            if isinstance(step, NpcRoundsResult):
                if mixed_scenario_terminal_side(step.source_request.current) is not None:
                    raise ValueError("scenario cannot call the runner after terminal defeat")
                if step.source_request.max_rounds != 1 or step.advances:
                    raise ValueError("scenario runner calls must visit one round at a time")
                expected_selected = None
                for action in step.rounds[0].steps:
                    if isinstance(action, NpcAttackSelectionResult):
                        expected = mixed_scenario_candidates(scenario, action.source_request, step.source_request.spatial_state)
                        if (action.source_request.candidates != expected
                                or (action.selected_candidate is not None
                                    and (not expected or action.selected_candidate != expected[0]))):
                            raise ValueError("candidate/target priority differs from scenario policy")
                        expected_selected = expected[0] if expected else None
                    if isinstance(action, NpcRosterAttackExecutionResult):
                        execution = action.execution
                        if expected_selected is None or execution.target_id != expected_selected.target_id:
                            raise ValueError("scenario Attack differs from available target priority")
                        expected_selected = None
                        stagger = execution.resolution.stagger
                        if (stagger is not None and stagger.selected_choice is not None
                                and stagger.selected_choice is not scenario.repeated_stagger_choice):
                            raise ValueError("scenario Attack differs from repeated Staggered policy")
                        attacks[execution.request_id] = action
            elif isinstance(step, MinionDefeatAcknowledgementResult):
                self._require_decision(step, attacks)
            elif isinstance(step, NpcRoundAdvanceResult):
                source = step.source_request
                if mixed_scenario_terminal_side(source.current) is not None:
                    raise ValueError("scenario cannot advance after terminal defeat")
                alive = tuple(p.turn_participant for p in source.current.state.roster.participants
                              if not p.state.injury.defeated)
                ids = {p.entity_id for p in alive}
                order = tuple(actor for actor in scenario.initial.current.actor_order if actor in ids)
                if source.next_round_participants != alive or source.next_actor_order != order:
                    raise ValueError("scenario advance differs from surviving composition/order")
            elif not isinstance(step, NpcRoundExclusionResult):
                raise ValueError("unsupported external transition in mixed scenario report")

        ack, exclusion = self.terminal_acknowledgement, self.terminal_exclusion
        if ack is not None:
            if not isinstance(ack, MinionDefeatAcknowledgementResult):
                raise TypeError("terminal acknowledgement must be typed")
            if ack.source_request.current != report.current:
                raise ValueError("terminal acknowledgement differs from report snapshot")
            self._require_decision(ack, attacks)
            if mixed_scenario_terminal_side(ack.continuation) is None or ack.continuation.pending_follow_ups:
                raise ValueError("terminal acknowledgement must finish a terminal defeat")
            target = ack.source_request.decision.target_id
            completed = target in ack.continuation.round_state.completed_turn_entity_ids
            if completed != (exclusion is None):
                raise ValueError("terminal exclusion is required only for an unfinished defeated turn")
        elif exclusion is not None:
            raise ValueError("terminal exclusion requires its acknowledgement")
        elif (len(report.current.pending_follow_ups) == 1
              and isinstance(report.current.pending_follow_ups[0], ProfileStateChangeRequest)):
            raise ValueError("scenario result omits a supported defeat acknowledgement")
        if exclusion is not None:
            if not isinstance(exclusion, NpcRoundExclusionResult):
                raise TypeError("terminal exclusion must be typed")
            if (exclusion.source_request.source != ack.continuation
                    or exclusion.source_request.actor_id != ack.source_request.decision.target_id):
                raise ValueError("terminal exclusion differs from acknowledged defeat")
        if self.outcome is NpcMixedScenarioOutcome.UNSUPPORTED_PATH:
            if report.outcome is NpcRoundsOutcome.ROUND_LIMIT:
                raise ValueError("scenario stopped before terminal outcome or global budget")

    def _require_decision(self, ack: MinionDefeatAcknowledgementResult,
                         attacks: dict[str, NpcRosterAttackExecutionResult]) -> None:
        source = ack.source_request
        if attacks.get(source.attack.execution.request_id) != source.attack:
            raise ValueError("scenario acknowledgement requires its full Attack in the report")
        policy = self.source_scenario.policy_for(source.decision.attacker_id)
        expected = next((item for item in policy.defeat_decisions
                         if item.target_id == source.decision.target_id), None)
        if source.decision != expected:
            raise ValueError("scenario acknowledgement differs from supplied GM decision")

    @property
    def current(self) -> NpcRoundRequest:
        current = (self.terminal_acknowledgement.continuation if self.terminal_acknowledgement is not None
                   else self.runner_report.current)
        return replace(current, round_state=self.terminal_exclusion.round_state) if self.terminal_exclusion else current

    @property
    def outcome(self) -> NpcMixedScenarioOutcome:
        current = self.current
        if current.pending_follow_ups:
            return NpcMixedScenarioOutcome.UNSUPPORTED_PATH
        side = mixed_scenario_terminal_side(current)
        if side is not None:
            return (NpcMixedScenarioOutcome.OBJECTIVE_ACHIEVED if side is self.source_scenario.perspective_side
                    else NpcMixedScenarioOutcome.SIDE_DEFEATED)
        if (self.runner_report.outcome is NpcRoundsOutcome.ROUND_LIMIT
                and current.round_state.round_number == self.source_scenario.initial.max_rounds):
            return NpcMixedScenarioOutcome.ROUND_LIMIT
        return NpcMixedScenarioOutcome.UNSUPPORTED_PATH

    @property
    def defeat_acknowledgements(self) -> tuple[MinionDefeatAcknowledgementResult, ...]:
        suffix = (self.terminal_acknowledgement,) if self.terminal_acknowledgement is not None else ()
        return (*self.runner_report.defeat_acknowledgements, *suffix)
