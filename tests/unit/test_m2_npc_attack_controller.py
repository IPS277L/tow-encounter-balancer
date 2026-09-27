from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_roster_attack_execution import request as execution_request, change_participant
from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_selection_models import (
    NpcAttackCandidate, NpcAttackCandidateRejection as Rejection, NpcAttackSelectionBlock as Block,
    NpcAttackSelectionRequest,
)
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundRequest, TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, InlineProfile, QualityModifier, Skill, TestQuality
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine import npc_attack_controller as controller


def candidate(state, identifier="first", *, target_id="brigand:2", attack="axe", aware=True):
    return NpcAttackCandidate(
        identifier, attack, target_id, Range.CLOSE if attack == "axe" else Range.MEDIUM,
        attack == "axe", False, aware, Skill.ATHLETICS if aware else None,
        state.roster.participant(target_id).protection_options("test:" + identifier), True, False,
    )


def request():
    base = execution_request()
    return NpcAttackSelectionRequest("select", base.state, base.execution.state, base.execution.actor_id, 1,
        (candidate(base.state), candidate(base.state, "second", target_id="brigand:3", attack="warbow")), ())


class M2NpcAttackControllerTests(unittest.TestCase):
    def test_preference_order_selects_first_without_damage_ranking_or_rng(self):
        source = request()
        # Same source ID may be reused only with identical definitions across the roster.
        profile = source.state.roster.participants[0].definition
        high_damage = replace(profile.attacks[1], damage=DamageProfile(20))
        profile = replace(profile, attacks=(profile.attacks[0], high_damage))
        source = replace(source, state=replace(source.state,
            roster=NpcRoster(tuple(replace(p, definition=profile) for p in source.state.roster.participants))))
        before = deepcopy(source)
        with patch.object(controller, "prepare_npc_attack", wraps=controller.prepare_npc_attack) as prepare:
            selected = controller.select_npc_attack(source)
        prepare.assert_called_once()
        self.assertIs(selected.source_request, source)
        self.assertIs(selected.selected_candidate, source.candidates[0])
        self.assertEqual(selected.execution_request.preparation.npc_attack.selected_profile.damage.base, 3)
        self.assertIs(selected.execution_request.state, source.state)
        self.assertIs(selected.execution_request.execution.state, source.round_state)
        self.assertFalse(source.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(source, before)
        reversed_result = controller.select_npc_attack(replace(source, candidates=source.candidates[::-1]))
        self.assertEqual(reversed_result.selected_candidate.id, "second")
        self.assertEqual(reversed_result.execution_request.execution.target_id, "brigand:3")
        self.assertEqual(reversed_result.rejected, ())
        with self.assertRaises(FrozenInstanceError):
            selected.selected_candidate = None

    def test_unavailable_and_defeated_candidates_are_skipped_in_order(self):
        source = request()
        state = change_participant(source.state, 0, available_attack_ids=("warbow",))
        state = change_participant(state, 2, injury=ProfileInjuryState(1, 1, defeated=True))
        candidates = (candidate(state, "unavailable"), candidate(state, "defeated", attack="warbow"),
                      candidate(state, "valid", target_id="brigand:3", attack="warbow"))
        result = controller.select_npc_attack(replace(source, state=state, candidates=candidates))
        self.assertEqual(result.selected_candidate.id, "valid")
        self.assertEqual(tuple(r.reason for r in result.rejected),
                         (Rejection.ATTACK_UNAVAILABLE, Rejection.TARGET_DEFEATED))
        self.assertEqual(tuple(r.candidate_id for r in result.rejected), ("unavailable", "defeated"))

    def test_range_and_protection_rejections_use_existing_preparations(self):
        source = request()
        candidates = (
            replace(source.candidates[0], id="far-axe", target_range=Range.MEDIUM),
            replace(source.candidates[1], id="close-enemy", has_enemy_in_close_range=True),
            replace(source.candidates[1], id="no-shield", protection_skill=Skill.DEFENCE),
            source.candidates[1],
        )
        result = controller.select_npc_attack(replace(source, candidates=candidates))
        self.assertEqual(result.selected_candidate.id, "second")
        self.assertEqual(tuple(r.reason for r in result.rejected),
                         (Rejection.ATTACK_CONTEXT, Rejection.ATTACK_CONTEXT, Rejection.PROTECTION_CONTEXT))
        self.assertTrue(all(r.detail for r in result.rejected))

    def test_empty_and_fully_rejected_candidates_have_explicit_no_candidate_result(self):
        source = request()
        for candidates in ((), (replace(source.candidates[0], target_range=Range.LONG),)):
            with self.subTest(candidates=candidates):
                result = controller.select_npc_attack(replace(source, candidates=candidates))
                self.assertIs(result.blocked_reason, Block.NO_CANDIDATE)
                self.assertIsNone(result.selected_candidate)
                self.assertIsNone(result.execution_request)
                self.assertEqual(len(result.rejected), len(candidates))

    def test_global_turn_slot_history_and_pending_guards_do_not_prepare(self):
        source = request()
        turn = source.round_state.active_turn
        cases = (
            (replace(source, pending_follow_ups=(GiveGroundRequest("pending"),)), Block.PENDING_FOLLOW_UPS),
            (replace(source, round_state=replace(source.round_state, active_turn=None)), Block.NO_ACTIVE_TURN),
            (replace(source, actor_id="brigand:1"), Block.ANOTHER_ACTIVE_ACTOR),
            (replace(source, slot_index=2), Block.SLOT_UNAVAILABLE),
            (replace(source, state=replace(source.state, consumed_execution_ids=(source.execution_id,))), Block.EXECUTION_CONSUMED),
            (replace(source, round_state=replace(source.round_state, active_turn=replace(turn, action_slots=(replace(
                turn.action_slots[0], declaration=CombatActionDeclaration(CombatActionKind.RECOVER)),)))), Block.SLOT_UNAVAILABLE),
            (replace(source, state=change_participant(source.state, 0,
                injury=ProfileInjuryState(1, 1, defeated=True))), Block.ACTOR_DEFEATED),
        )
        for value, expected in cases:
            with self.subTest(expected=expected), patch.object(controller, "prepare_npc_attack") as prepare:
                result = controller.select_npc_attack(value)
                self.assertIs(result.blocked_reason, expected)
                self.assertEqual(result.pending_follow_ups, value.pending_follow_ups)
                self.assertEqual(result.rejected, ())
                prepare.assert_not_called()

    def test_unsupported_actor_and_targets_and_self_are_explicit(self):
        source = request()
        for index in (0, 2):
            participants = list(source.state.roster.participants)
            participant = participants[index]
            participants[index] = replace(participant,
                definition=replace(participant.definition, id="brute", injury_policy=TargetInjuryPolicy.BRUTE, wound_limit=2),
                state=replace(participant.state, definition_id="brute", injury=ProfileInjuryState(0, 2)))
            state = replace(source.state, roster=NpcRoster(tuple(participants)))
            result = controller.select_npc_attack(replace(source, state=state))
            if index == 0:
                self.assertIs(result.blocked_reason, Block.UNSUPPORTED_ACTOR)
            else:
                self.assertIs(result.rejected[0].reason, Rejection.UNSUPPORTED_TARGET)
                self.assertEqual(result.selected_candidate.id, "second")
        own = candidate(source.state, "self", target_id="brigand:0")
        result = controller.select_npc_attack(replace(source, candidates=(own, source.candidates[1])))
        self.assertIs(result.rejected[0].reason, Rejection.SELF_TARGET)

    def test_target_absent_from_round_is_skipped_without_inventing_eligibility(self):
        source = request()
        round_state = replace(source.round_state, participants=tuple(
            p for p in source.round_state.participants if p.entity_id != "brigand:2"))
        result = controller.select_npc_attack(replace(source, round_state=round_state))
        self.assertIs(result.rejected[0].reason, Rejection.TARGET_NOT_IN_ROUND)
        self.assertEqual(result.selected_candidate.target_id, "brigand:3")

    def test_extra_attack_effects_are_skipped_instead_of_silently_dropped(self):
        source = request()
        profile = source.state.roster.participants[0].definition
        axe = replace(profile.attacks[0], secondary_effects=(ConditionOnHitSpec(
            condition=Condition.PRONE, rule_id="scenario:prone"),))
        profile = replace(profile, attacks=(axe, profile.attacks[1]))
        state = replace(source.state, roster=NpcRoster(tuple(replace(p, definition=profile) for p in source.state.roster.participants)))
        result = controller.select_npc_attack(replace(source, state=state))
        self.assertIs(result.rejected[0].reason, Rejection.UNSUPPORTED_EFFECTS)
        self.assertEqual(result.selected_candidate.id, "second")

    def test_explicit_modifiers_quality_and_unopposed_facts_survive_selection(self):
        source = request()
        option = source.candidates[0].protection_options[0]
        option = replace(option, test=replace(option.test, quality_modifiers=(QualityModifier("scenario:grim", TestQuality.GRIM),),
            dice_modifiers=(DiceModifier("scenario:protection", -1),)))
        modified = replace(source.candidates[0], protection_options=(option,),
                           dice_modifiers=(DiceModifier("scenario:attack", 1),))
        result = controller.select_npc_attack(replace(source, candidates=(modified,)))
        attack = result.execution_request.preparation.attack
        self.assertIs(attack.defender_test, option.test)
        self.assertEqual(attack.attacker_test.dice_modifiers, modified.dice_modifiers)
        for defenceless in (False, True):
            state = source.state
            if defenceless:
                injury = state.roster.participants[2].state.injury
                state = change_participant(state, 2, injury=replace(injury,
                    conditions=injury.conditions.with_condition(Condition.DEFENCELESS)))
            proposed = replace(source.candidates[0], defender_is_aware=defenceless, protection_skill=None)
            selected = controller.select_npc_attack(replace(source, state=state, candidates=(proposed,)))
            self.assertIsNone(selected.execution_request.preparation.attack.defender_test)

    def test_malformed_sources_do_not_become_silent_candidate_skips(self):
        source = request()
        for candidate in (replace(source.candidates[1], attack_profile_id="absent"),
                          replace(source.candidates[1], target_id="unknown", protection_options=())):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                replace(source, candidates=(source.candidates[0], candidate))
        option = source.candidates[1].protection_options[0]
        option = replace(option, test=replace(option.test, profile=InlineProfile(9, 9)))
        with self.assertRaisesRegex(ValueError, "current roster"):
            replace(source, candidates=(source.candidates[0], replace(source.candidates[1], protection_options=(option,))))
        with self.assertRaisesRegex(ValueError, "another target"):
            replace(source.candidates[0], protection_options=source.candidates[1].protection_options)
        with self.assertRaisesRegex(ValueError, "unique"):
            replace(source, candidates=source.candidates * 2)
        with self.assertRaises(TypeError):
            replace(source, slot_index=True)
        with self.assertRaises(TypeError):
            replace(source, pending_follow_ups=(object(),))

    def test_handoff_requires_exact_current_roster_round_and_pending_queue(self):
        source = request()
        selected = controller.select_npc_attack(source)
        self.assertIs(controller.require_current_npc_attack_selection(selected, source.state, source.round_state,
            pending_follow_ups=()), selected.execution_request)
        for state, round_state, pending in (
            (change_participant(source.state, 3, available_attack_ids=()), source.round_state, ()),
            (source.state, replace(source.round_state, active_turn=None), ()),
            (source.state, source.round_state, (GiveGroundRequest("pending"),)),
            (replace(source.state, consumed_execution_ids=("earlier",)), source.round_state, ()),
        ):
            with self.subTest(state=state, pending=pending), self.assertRaisesRegex(ValueError, "stale"):
                controller.require_current_npc_attack_selection(selected, state, round_state, pending_follow_ups=pending)
        blocked = controller.select_npc_attack(replace(source, candidates=()))
        with self.assertRaisesRegex(ValueError, "no executable"):
            controller.require_current_npc_attack_selection(blocked, source.state, source.round_state, pending_follow_ups=())

    def test_result_guards_order_and_source_even_when_ids_are_unchanged(self):
        source = request()
        selected = controller.select_npc_attack(source)
        with self.assertRaisesRegex(ValueError, "preference prefix"):
            replace(selected, selected_candidate=source.candidates[1])
        with self.assertRaisesRegex(ValueError, "exact source"):
            replace(selected, source_request=replace(source, state=change_participant(source.state, 3, available_attack_ids=())))
        altered = replace(source.candidates[0], can_target_leave_zone=False)
        with self.assertRaisesRegex(ValueError, "exact source"):
            replace(selected, selected_candidate=altered, source_request=replace(source, candidates=(altered,)))

    def test_unexpected_preparation_failure_propagates_instead_of_trying_next_candidate(self):
        source = request()
        with patch.object(controller, "prepare_npc_attack", side_effect=ValueError("unexpected regression")):
            with self.assertRaisesRegex(ValueError, "unexpected regression"):
                controller.select_npc_attack(source)
