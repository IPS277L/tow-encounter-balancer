"""Prepared mount-body facts with genuine natural Attack and Test executions.

No native retention/remount journal or passive-companion Attack is claimed.
"""
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_companion_attack_wrappers import PreparedAttackView, prepared
from tests.unit.test_pc_demigryph import reserved
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition, ConditionState, EffectClassification
from towr.domain.injury_models import MinionStaggerDefeatOutcome
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_magic_models import PcMagicModifier, PcMagicTaskKind, consume_magic_modifiers
from towr.domain.pc_melee_result_models import PcAttackProof, pc_melee_action_id
from towr.domain.pc_battlefield_models import _close_key
from towr.domain.pc_mount_attack_models import (
    available_pc_attack_mount, build_pc_mounted_attack_intent, pc_mounted_attack_test,
    prepare_pc_mounted_attack, pc_best_mount_attack,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.test_models import InlineProfile, Skill, TestQuality
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection


def view_of(state):
    return PreparedAttackView(_base=state, **{name: getattr(state, name) for name in state.__dataclass_fields__})


def body_injury(view, actor, *, conditions=(), wounds=0, defeated=False):
    view.companions = tuple(replace(row, snapshot=replace(row.snapshot, state=replace(row.snapshot.state,
        injury=replace(row.snapshot.state.injury, wounds=wounds, defeated=defeated,
            conditions=ConditionState(frozenset(conditions)))))) if row.rider_id == actor else row
        for row in view.companions)


def rider_conditions(view, actor, *conditions):
    if actor in view.source.pc_activation_order:
        view.party = tuple(replace(row, injury=replace(row.injury,
            conditions=ConditionState(frozenset(conditions)))) if row.actor_id == actor else row for row in view.party)
    else:
        view.enemies = tuple(replace(row, state=replace(row.state, injury=replace(row.state.injury,
            conditions=ConditionState(frozenset(conditions))))) if row.state.actor_id == actor else row
            for row in view.enemies)


class CompanionMountedAttackTests(unittest.TestCase):
    def test_both_rider_sides_can_target_actual_opposing_companions_with_one_paid_natural_attack(self):
        for npc_actor in (False, True):
            view, actor, target = prepared(npc_actor=npc_actor)
            with self.subTest(npc_actor=npc_actor):
                mount_intent = build_pc_mounted_attack_intent(view, actor, target)
                action_id = pc_melee_action_id(view, actor)
                weapon_intent = build_pc_explicit_attack_weapon_intent(view, actor, target, action_id, mount_attack=True)
                kernel, protection = prepare_pc_mounted_attack(view, actor, target, action_id, weapon_intent=weapon_intent)
                self.assertIs(kernel.target_policy, TargetInjuryPolicy.MINION)
                self.assertIs(protection.selected_skill, Skill.ATHLETICS)
                self.assertEqual(kernel.target_state, pc_actor_injury(view, target))
                self.assertEqual(kernel.attack.attacker_test.profile, InlineProfile(3, 3, 6))
                request = AttackActionExecutionRequest(action_id+':execute', view.round_state, actor, target, 1, kernel)
                rng = ScriptedD10([1]*6)
                execution = execute_attack_action(request, rng)
                rng.assert_exhausted()
                self.assertEqual(execution.actor_id, actor)
                self.assertTrue(execution.resolution.target_state.conditions.has(Condition.STAGGERED))
                self.assertEqual(len(execution.state.active_turn.action_slots), 1)
                self.assertEqual(mount_intent.source_round, view.round_state)
                self.assertIsNone(weapon_intent.attack_use)
                self.assertFalse(hasattr(execution.resolution.target_state, 'fate'))
                with self.assertRaises(ValueError):
                    available_pc_attack_mount(view, target)

    def test_body_drained_blinded_and_staggered_control_own_test_for_both_rider_sides(self):
        for actor, target in (('pc1', 'minion1'), ('minion1', 'pc1')):
            view = view_of(reserved(actor=actor))
            body_injury(view, actor, conditions=(Condition.DRAINED, Condition.BLINDED, Condition.STAGGERED), wounds=1)
            rider_conditions(view, target, Condition.PRONE)
            with self.subTest(actor=actor):
                test = pc_mounted_attack_test(view, actor, target, 'own-body:test')
                self.assertEqual(test.profile, InlineProfile(4, 4, 8))
                self.assertFalse(any(row.amount > 0 for row in test.dice_modifiers))
                self.assertEqual(tuple(row.rule_id for row in test.quality_modifiers if row.quality is TestQuality.GRIM),
                    ('RULE-HEALTH-008:blinded',))
                kernel, _ = prepare_pc_mounted_attack(view, actor, target, 'own-body')
                self.assertTrue(kernel.attack.attacker_is_staggered)
                self.assertFalse(pc_actor_injury(view, actor).conditions.has(Condition.STAGGERED))
                self.assertEqual(next(row for row in view.companions if row.rider_id == actor).snapshot.state.injury.wounds, 1)

    def test_natural_attack_keeps_the_skeletal_targets_real_undead_source(self):
        view = view_of(reserved(actor='minion1', mount=CombatMount.SKELETAL_STEED))
        target = 'pc1:mount'
        view.companions = tuple(replace(row, retained_since_round=1) if row.rider_id == 'pc1' else row
            for row in view.companions)
        view.mounts = tuple(replace(row, mounted=False) if row.actor_id == 'pc1' else row for row in view.mounts)
        origin = view.battlefield.spatial.placement_for('pc1')
        view.battlefield = replace(view.battlefield, spatial=replace(view.battlefield.spatial,
            placements=(*view.battlefield.spatial.placements,
                SpatialEntityPlacement(target, origin.side_id, origin.zone_id))),
            close_pairs=(*view.battlefield.close_pairs, _close_key(target, 'pc1'), _close_key(target, 'minion1')))
        intent = build_pc_mounted_attack_intent(view, 'minion1', target)
        kernel, _ = prepare_pc_mounted_attack(view, 'minion1', target, 'skeletal:natural')
        self.assertEqual(intent.target_id, target)
        self.assertIs(kernel.target_policy, TargetInjuryPolicy.MINION)
        self.assertIs(kernel.minion_stagger_defeat.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual(tuple(row.classification for row in kernel.target_effect_immunities),
            (EffectClassification.PSYCHOLOGICAL,))
        self.assertFalse(kernel.can_target_leave_zone)

    def test_rider_conditions_and_magic_penalty_do_not_become_mount_facts(self):
        view = view_of(reserved())
        rider_conditions(view, 'pc1', Condition.DRAINED, Condition.BLINDED, Condition.STAGGERED)
        rider_conditions(view, 'minion1', Condition.PRONE)
        view.magic_modifiers = (PcMagicModifier('actual:rider:next', 'pc1', PcMagicTaskKind.NEXT_TEST_PENALTY),)
        test = pc_mounted_attack_test(view, 'pc1', 'minion1', 'healthy-body:test')
        self.assertEqual(test.profile, InlineProfile(4, 4, 8))
        self.assertIn(('RULE-COMBAT-007:higher-ground', 1), tuple((row.rule_id, row.amount) for row in test.dice_modifiers))
        self.assertFalse(any(row.rule_id == 'actual:rider:next' for row in test.dice_modifiers))
        self.assertEqual(test.quality_modifiers, ())
        kernel, _ = prepare_pc_mounted_attack(view, 'pc1', 'minion1', 'healthy-body')
        self.assertFalse(kernel.attack.attacker_is_staggered)

    def test_same_blinded_condition_on_rider_and_body_has_one_body_source(self):
        view = view_of(reserved())
        rider_conditions(view, 'pc1', Condition.BLINDED)
        body_injury(view, 'pc1', conditions=(Condition.BLINDED,))
        test = pc_mounted_attack_test(view, 'pc1', 'minion1', 'one-source')
        self.assertEqual(len(test.quality_modifiers), 1)
        self.assertIs(test.quality_modifiers[0].quality, TestQuality.GRIM)

    def test_unusable_or_foreign_body_cannot_supply_a_natural_attack(self):
        for conditions, wounds, defeated in (((Condition.PRONE,), 0, False),
                ((Condition.DEFENCELESS,), 0, False), ((), 3, True)):
            view = view_of(reserved())
            body_injury(view, 'pc1', conditions=conditions, wounds=wounds, defeated=defeated)
            with self.subTest(conditions=conditions, defeated=defeated):
                self.assertIsNone(available_pc_attack_mount(view, 'pc1'))
                with self.assertRaises(ValueError):
                    prepare_pc_mounted_attack(view, 'pc1', 'minion1', 'unavailable')
        view = view_of(reserved())
        row, = tuple(row for row in view.companions if row.rider_id == 'pc1')
        forged = replace(row, snapshot=replace(row.snapshot,
            definition=replace(row.snapshot.definition, source_rule_id='foreign:animal')))
        view.companions = tuple(forged if body.rider_id == 'pc1' else body for body in view.companions)
        with self.assertRaises(ValueError):
            available_pc_attack_mount(view, 'pc1')

    def test_used_body_magic_penalty_consumes_from_actual_attack_trace_only(self):
        view, actor, target = prepared()
        body_id = actor+':mount'
        body = PcMagicModifier('actual:body:next', body_id, PcMagicTaskKind.NEXT_TEST_PENALTY)
        rider = PcMagicModifier('actual:rider:next', actor, PcMagicTaskKind.NEXT_TEST_PENALTY)
        view.magic_modifiers = (body, rider)
        action_id = pc_melee_action_id(view, actor)
        intent = build_pc_mounted_attack_intent(view, actor, target)
        weapon_intent = build_pc_explicit_attack_weapon_intent(view, actor, target, action_id, mount_attack=True)
        kernel, protection = prepare_pc_mounted_attack(view, actor, target, action_id, weapon_intent=weapon_intent)
        self.assertEqual(tuple(row.rule_id for row in kernel.attack.attacker_test.dice_modifiers), ('actual:body:next',))
        request = AttackActionExecutionRequest(action_id+':execute', view.round_state, actor, target, 1, kernel)
        rng = ScriptedD10([1]*5)
        execution = execute_attack_action(request, rng)
        rng.assert_exhausted()
        proof = PcAttackProof(request, prepare_protection(protection), execution, None,
            weapon_intent=weapon_intent, mount_attack=intent)
        self.assertIn(body.source_id, execution.resolution.attack.attacker_test.trace.applied_rule_ids)
        self.assertEqual(consume_magic_modifiers(view.magic_modifiers, proof), (rider,))


if __name__ == '__main__':
    unittest.main()
