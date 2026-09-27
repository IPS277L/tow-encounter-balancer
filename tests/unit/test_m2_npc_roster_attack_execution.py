from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_m2_npc_roster_preparation import attack_request, protection_request, roster
from tests.unit.test_k1_kernel import FixedKernelDecisions
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import ConditionOnHitSpec, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState, ProfileStateChangeRequest
from towr.domain.npc_roster_attack_models import (
    NpcRosterAttackExecutionRequest, NpcRosterAttackState,
)
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.resolution_models import GiveGroundRequest, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, InlineProfile
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatRoundState, CombatSide,
    CombatTurnStartRequest,
)
from towr.rules import attack_action_execution as attack_executor
from towr.rules import npc_roster_attack_execution as execution
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def request(*, selected="axe", aware=True, actor_staggered=False, target_staggered=False, source=None):
    source = source or roster()
    participants = list(source.participants)
    for index, staggered in ((0, actor_staggered), (2, target_staggered)):
        if staggered:
            participant = participants[index]
            injury = participant.state.injury
            participants[index] = replace(participant, state=replace(participant.state, injury=replace(
                injury, conditions=injury.conditions.with_condition(Condition.STAGGERED))))
    source = NpcRoster(tuple(participants))
    round_state = CombatRoundState(round_number=1, participants=source.turn_participants)
    round_state = start_combat_turn(CombatTurnStartRequest("turn:start", round_state, "brigand:0")).state
    round_state = reserve_combat_action_slot(CombatActionSlotRequest(
        id="slot:attack", state=round_state, actor_id="brigand:0",
        declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
        grant=ActionSlotGrant.STANDARD,
    )).state
    npc = prepare_npc_attack(attack_request(source, selected))
    prepared = prepare_npc_attack_protection(npc, protection_request(source, npc, aware))
    target = source.participant("brigand:2")
    kernel = KernelAttackRequest(
        id="kernel:roster", target_id=target.state.actor_id, attack=prepared.attack,
        target_policy=TargetInjuryPolicy.MINION, target_state=target.state.injury,
        can_target_leave_zone=True, target_has_given_ground_this_round=False,
    )
    return NpcRosterAttackExecutionRequest(NpcRosterAttackState(source), prepared,
        AttackActionExecutionRequest("execute:roster", round_state, "brigand:0", "brigand:2", 1, kernel))


def change_participant(source, index, **changes):
    participants = list(source.roster.participants)
    participant = participants[index]
    participants[index] = replace(participant, state=replace(participant.state, **changes))
    return replace(source, roster=NpcRoster(tuple(participants)))


class M2NpcRosterAttackExecutionTests(unittest.TestCase):
    def test_one_reserved_attack_updates_only_actor_and_target_for_48_outcomes(self):
        for selected, aware, outcome, actor_staggered, target_staggered in product(
            ("axe", "warbow"), (False, True), ("miss", "stagger", "wound"), (False, True), (False, True),
        ):
            with self.subTest(selected=selected, aware=aware, outcome=outcome,
                              actor_staggered=actor_staggered, target_staggered=target_staggered):
                source = request(selected=selected, aware=aware, actor_staggered=actor_staggered,
                                 target_staggered=target_staggered)
                before = deepcopy(source)
                values = {"miss": [10, 10, 10], "stagger": [1, 10, 10], "wound": [1, 2, 10]}[outcome]
                values += [10, 10, 10] if aware else []
                rng = Mock(wraps=SequenceRandom([*values, 7]))
                decisions = FixedKernelDecisions()
                with patch.object(attack_executor, "resolve_kernel_attack",
                                  wraps=attack_executor.resolve_kernel_attack) as kernel:
                    result = execution.execute_npc_roster_attack(source, rng, decisions=decisions)
                kernel.assert_called_once_with(source.execution.kernel_request, rng, decisions=decisions)
                self.assertEqual(rng.randint.call_count, len(values))
                current = execution.apply_npc_roster_attack_result(source.state, result)
                self.assertEqual(current, result.state)
                self.assertEqual(current.consumed_execution_ids, (source.execution.id,))
                self.assertEqual(source, before)
                self.assertTrue(result.execution.slot.executed)
                self.assertEqual(result.execution.slot.execution.id, source.execution.id)
                self.assertEqual(len(result.execution.state.active_turn.action_slots), 1)
                self.assertFalse(source.execution.state.active_turn.action_slots[0].executed)
                wounded = outcome == "wound" or (outcome == "stagger" and target_staggered)
                target = current.roster.participant("brigand:2").state.injury
                actor = current.roster.participant("brigand:0").state.injury
                self.assertEqual(target.defeated, wounded)
                self.assertEqual(target.wounds, int(wounded))
                self.assertEqual(target.conditions.has(Condition.STAGGERED),
                                 not wounded and (target_staggered or outcome == "stagger"))
                close_miss = selected == "axe" and outcome == "miss"
                self.assertEqual(actor.conditions.has(Condition.STAGGERED), actor_staggered or close_miss)
                self.assertEqual(actor.wounds, 0)
                self.assertEqual(len(result.handled_follow_ups), int(close_miss and not actor_staggered))
                self.assertEqual(len(result.pending_follow_ups), int(wounded))
                if wounded:
                    self.assertIsInstance(result.pending_follow_ups[0], ProfileStateChangeRequest)
                for index in (1, 3):
                    self.assertIs(current.roster.participants[index], source.state.roster.participants[index])
                self.assertTrue(set(source.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(rng.randint(1, 10), 7)

    def test_repeated_stagger_preserves_give_ground_and_prone_choices(self):
        for choice in (StaggerChoice.GIVE_GROUND, StaggerChoice.FALL_PRONE):
            with self.subTest(choice=choice):
                source = request(target_staggered=True)
                result = execution.execute_npc_roster_attack(source, SequenceRandom([1, 10, 10, 10, 10, 10]),
                    decisions=FixedKernelDecisions(stagger=choice))
                target = result.state.roster.participant("brigand:2").state.injury
                self.assertEqual(target.wounds, 0)
                self.assertEqual(target.conditions.has(Condition.PRONE), choice is StaggerChoice.FALL_PRONE)
                self.assertEqual(len(result.pending_follow_ups), int(choice is StaggerChoice.GIVE_GROUND))
                if choice is StaggerChoice.GIVE_GROUND:
                    self.assertIsInstance(result.pending_follow_ups[0], GiveGroundRequest)

    def test_replay_uses_returned_history_even_when_ranged_miss_changed_no_injury(self):
        source = request(selected="warbow", aware=False)
        result = execution.execute_npc_roster_attack(source, SequenceRandom([10, 10, 10]))
        current = execution.apply_npc_roster_attack_result(source.state, result)
        self.assertEqual(current.roster, source.state.roster)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            execution.apply_npc_roster_attack_result(current, result)
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            execution.execute_npc_roster_attack(replace(source, state=current), rng)
        rng.randint.assert_not_called()

    def test_executed_or_unreserved_or_non_attack_slot_fails_before_rng(self):
        source = request()
        result = execution.execute_npc_roster_attack(source, SequenceRandom([10] * 6))
        turn = source.execution.state.active_turn
        rounds = (
            result.execution.state,
            replace(source.execution.state, active_turn=replace(turn, action_slots=())),
            replace(source.execution.state, active_turn=replace(turn, action_slots=(replace(
                turn.action_slots[0], declaration=CombatActionDeclaration(CombatActionKind.RECOVER)),))),
            replace(source.execution.state, active_turn=None),
        )
        for state in rounds:
            with self.subTest(state=state):
                rng = Mock()
                with self.assertRaises(ValueError):
                    execution.execute_npc_roster_attack(replace(source,
                        execution=replace(source.execution, state=state)), rng)
                rng.randint.assert_not_called()

    def test_wrong_active_actor_fails_before_rng(self):
        source = request()
        turn = replace(source.execution.state.active_turn, actor_id="brigand:1")
        wrong = replace(source.execution.state, active_turn=turn)
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "own the active turn"):
            execution.execute_npc_roster_attack(replace(source, execution=replace(source.execution, state=wrong)), rng)
        rng.randint.assert_not_called()

    def test_stale_availability_resilience_equipment_and_injury_are_rejected(self):
        source = request()
        for index, changes in (
            (0, {"available_attack_ids": ("warbow",)}),
            (0, {"side": CombatSide.OPPOSITION}),
            (0, {"injury": replace(source.state.roster.participants[0].state.injury,
                                  conditions=source.state.roster.participants[0].state.injury.conditions.with_condition(Condition.STAGGERED))}),
            (2, {"current_resilience": ResilienceProfile(8)}),
            (2, {"holds_shield": True}),
            (2, {"injury": replace(source.state.roster.participants[2].state.injury,
                                  conditions=source.state.roster.participants[2].state.injury.conditions.with_condition(Condition.PRONE))}),
        ):
            with self.subTest(index=index, changes=changes), self.assertRaises(ValueError):
                replace(source, state=change_participant(source.state, index, **changes))

    def test_defeated_or_non_minion_participants_are_excluded(self):
        source = request()
        for index in (0, 2):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "defeated"):
                    replace(source, state=change_participant(source.state, index,
                        injury=ProfileInjuryState(1, 1, defeated=True)))
                participants = list(source.state.roster.participants)
                participant = participants[index]
                participants[index] = replace(participant,
                    definition=replace(participant.definition, id="brute", injury_policy=TargetInjuryPolicy.BRUTE, wound_limit=2),
                    state=replace(participant.state, definition_id="brute", injury=ProfileInjuryState(0, 2)))
                with self.assertRaisesRegex(ValueError, "Minion versus Minion"):
                    replace(source, state=replace(source.state, roster=NpcRoster(tuple(participants))))

    def test_stale_consumer_snapshot_or_history_is_rejected(self):
        source = request()
        result = execution.execute_npc_roster_attack(source, SequenceRandom([10] * 6))
        for state in (change_participant(source.state, 3, available_attack_ids=()),
                      replace(source.state, consumed_execution_ids=("earlier",))):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "stale source"):
                execution.apply_npc_roster_attack_result(state, result)

    def test_result_cannot_be_bound_to_another_execution_or_attack(self):
        source = request()
        result = execution.execute_npc_roster_attack(source, SequenceRandom([10] * 6))
        with self.assertRaisesRegex(ValueError, "does not match"):
            replace(result, source_request=replace(source, execution=replace(source.execution, id="other")))
        with self.assertRaisesRegex(ValueError, "does not match preparation"):
            replace(result, source_request=request(selected="warbow"))

    def test_protection_profile_and_additional_effects_are_not_silently_accepted(self):
        source = request()
        npc = source.preparation.npc_attack
        protection = source.preparation.protection.source_request
        option = protection.options[0]
        changed = replace(option, test=replace(option.test, profile=InlineProfile(9, 9)))
        prepared = prepare_npc_attack_protection(npc, replace(protection, options=(changed,)))
        with self.assertRaisesRegex(ValueError, "Test profile"):
            replace(source, preparation=prepared)
        attack = npc.selected_profile
        enhanced = replace(attack, secondary_effects=(ConditionOnHitSpec(rule_id="RULE-TEST:extra", condition=Condition.PRONE),))
        snapshot = replace(npc.snapshot, profiles=(enhanced, npc.snapshot.profiles[1]))
        # A legal preparation for a different snapshot cannot silently reuse this roster.
        new_npc = prepare_npc_attack(replace(npc.source_request, snapshot=snapshot))
        prepared = prepare_npc_attack_protection(new_npc, replace(protection, attack=new_npc.attack))
        with self.assertRaisesRegex(ValueError, "stale roster"):
            replace(source, preparation=prepared)
        enhanced_roster = NpcRoster(tuple(replace(p, definition=replace(p.definition, attacks=snapshot.profiles))
                                          for p in source.state.roster.participants))
        with self.assertRaisesRegex(ValueError, "additional attack effects"):
            request(source=enhanced_roster)

    def test_explicit_attack_and_protection_modifiers_reach_the_single_test(self):
        source = request()
        npc = prepare_npc_attack(replace(source.preparation.npc_attack.source_request,
            dice_modifiers=(DiceModifier("scenario:attack", -1),)))
        protection = source.preparation.protection.source_request
        option = protection.options[0]
        option = replace(option, test=replace(option.test, dice_modifiers=(DiceModifier("scenario:defence", -1),)))
        prepared = prepare_npc_attack_protection(npc, replace(protection, attack=npc.attack, options=(option,)))
        source = replace(source, preparation=prepared, execution=replace(source.execution,
            kernel_request=replace(source.execution.kernel_request, attack=prepared.attack)))
        rng = SequenceRandom([1, 10, 10, 10, 7])
        result = execution.execute_npc_roster_attack(source, rng)
        self.assertEqual(result.execution.resolution.attack.attacker_test.trace.rolled_dice, 2)
        self.assertEqual(result.execution.resolution.attack.defender_test.trace.rolled_dice, 2)
        self.assertEqual(rng.randint(1, 10), 7)

    def test_kernel_cannot_substitute_target_state_or_prepared_attack(self):
        source = request()
        kernel = source.execution.kernel_request
        changed_attack = replace(kernel.attack, attacker_is_staggered=True)
        with self.assertRaisesRegex(ValueError, "kernel request differs"):
            replace(source, execution=replace(source.execution, kernel_request=replace(kernel, attack=changed_attack)))

    def test_history_requires_distinct_nonempty_ids(self):
        source = request()
        for consumed in (("same", "same"), ("",), (1,)):
            with self.subTest(consumed=consumed), self.assertRaises(ValueError):
                replace(source.state, consumed_execution_ids=consumed)
