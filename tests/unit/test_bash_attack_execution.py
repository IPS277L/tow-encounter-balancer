"""Real PC/generated NPC Bash strikes, physical readiness and complete replay."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.npc_roster_models import NpcProtectionProfile
from towr.domain.pc_bash_attack_models import expected_bash_decision, pending_bash_decision
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof, current_pc_charge
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_immediate_attack_models import PcBashDecisionProof, PcImmediateStrikeProof
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcShieldHandConflictPolicy, PcShieldLoadout, PcShieldRecoveryPolicy, PcWeaponHand,
)
from towr.domain.pc_mount_models import CombatMount, pc_is_mounted
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_npc_shield_models import PcNpcShieldDropProof
from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
from towr.domain.pc_shield_models import PcShieldReleaseProof
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.domain.talent_catalog import TalentId
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def pc_source(*, carried=False, melee=True, rounds=1):
    source = make_pc_melee_scenario(max_rounds=rounds)
    row = source.party[0]
    items = (PcWeaponItem('knuckles', W.KNUCKLEDUSTERS, L.HELD, PcWeaponHand.LEFT),)
    if melee:
        items += (PcWeaponItem('melee', W.HALBERD if carried else W.SWORD,
            L.CARRIED if carried else L.HELD, None if carried else PcWeaponHand.RIGHT),)
    shield = (PcShieldLoadout(PcWeaponHand.RIGHT, PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if carried else None)
    row = replace(row, pc=replace(row.pc, weapon=W.KNUCKLEDUSTERS, strength=5, toughness=20,
        brawn=6), initial_weapon_hand=PcWeaponHand.LEFT, combat_equipment=items,
        talents=(paid_talent(TalentId.BASH_ATTACK),), shield=shield)
    enemy = source.enemies[0]
    resilience = replace(enemy.definition.resilience, toughness=20)
    definition = replace(enemy.definition, resilience=resilience, protection=(
        NpcProtectionProfile('authored:minion:athletics', Skill.ATHLETICS, InlineProfile(2,4)),))
    enemy = replace(enemy, definition=definition, state=replace(enemy.state, current_resilience=resilience))
    return replace(source, party=(row,), enemies=(enemy,),
        facts=replace(source.facts, outnumbering_bonus_approved=False))


def npc_source(*, carried=False):
    source = make_pc_melee_scenario(max_rounds=1)
    row = source.party[0]
    row = replace(row, pc=replace(row.pc, weapon_skill=1, strength=1, toughness=20,
        melee=1, defence=1, endurance=1))
    items = (WeaponItemSource('knuckles', W.KNUCKLEDUSTERS, L.HELD, G.LEFT),
        WeaponItemSource('melee', W.HALBERD if carried else W.SWORD,
            L.CARRIED if carried else L.HELD, None if carried else G.RIGHT))
    components = GeneratedNpc(1, 5, 20, 1, 2, 2, items,
        ArmourLoadout(shield=ShieldKind.SHIELD if carried else None), defence=2, brawn=6,
        talents=(paid_talent(TalentId.BASH_ATTACK),))
    return replace(source, party=(row,), enemies=(components.participant('minion1'),),
        facts=replace(source.facts, outnumbering_bonus_approved=False))


class BashAttackExecutionTests(unittest.TestCase):
    def execute(self, source, values):
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        state = initial_pc_melee_state(source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)
        return result

    def assert_immediate(self, result, actor, *, carried=False):
        decision, = tuple(step for step in result.steps if type(step.proof) is PcBashDecisionProof)
        strike, = tuple(step for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        primary = result.steps[decision.proof.source_index]
        self.assertIs(type(primary.proof), PcAttackProof)
        self.assertEqual(primary.proof.request.actor_id, actor)
        self.assertIs(primary.proof.weapon_intent.attack_use.skill, Skill.BRAWN)
        self.assertEqual(decision.proof.grant.source_request, primary.proof.request)
        self.assertEqual(decision.proof.grant.source_execution, primary.proof.execution)
        self.assertEqual(strike.proof.request.decision, decision.proof)
        self.assertIs(strike.proof.weapon_intent.attack_skill, Skill.MELEE)
        self.assertEqual(strike.proof.request.target_id, primary.proof.request.target_id)
        self.assertEqual(strike.source.round_state, primary.proof.execution.state)
        self.assertEqual(strike.state.round_state, strike.source.round_state)
        self.assertEqual(len(strike.state.round_state.active_turn.action_slots), 1)
        self.assertIsNone(current_pc_charge(strike.source, actor))
        self.assertIsNone(pending_bash_decision(strike.state))
        self.assertIsNone(expected_bash_decision(strike.state))
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(strike.state, strike.proof)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(decision.state, decision.proof)
        if not carried:
            self.assertIsNone(decision.proof.selection.equip)
            self.assertIs(strike.proof.weapon_intent.attack_use.inventory,
                decision.proof.selection.use.inventory)
            self.assertNotEqual(strike.proof.weapon_intent.attack_use.primary_item_id,
                strike.proof.weapon_intent.attack_use.inventory.active_item_id)
        return decision, strike

    def test_pc_held_melee_strikes_from_an_actual_brawn_primary_without_an_extra_action(self):
        result = self.execute(pc_source(), [1]*5 + [10]*2 + [1]*3 + [10]*2)
        self.assert_immediate(result, 'pc')
        self.assertEqual(result.executed_actions, 1)
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)

    def test_pc_carried_two_handed_weapon_uses_real_shield_release_and_incidental_equip(self):
        result = self.execute(pc_source(carried=True), [1]*5 + [10]*2 + [1]*3 + [10]*2)
        decision, strike = self.assert_immediate(result, 'pc', carried=True)
        release, = tuple(step for step in result.steps if type(step.proof) is PcShieldReleaseProof)
        equip, = tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertTrue(decision.proof.selection.release_shield)
        self.assertEqual(equip.proof.previous, release.state.participant('pc').weapon_inventory)
        self.assertEqual(strike.proof.weapon_intent.attack_use.inventory, equip.proof.state)
        self.assertIs(strike.proof.weapon_intent.attack_use.primary_grip, G.BOTH)
        self.assertEqual(result.executed_actions, 1)

    def test_npc_held_melee_strikes_from_an_actual_brawn_primary_and_preserves_parent_budget(self):
        values = [1,10,10] + [1]*5 + [10]*20 + [1,10,1]
        result = self.execute(npc_source(), values)
        self.assert_immediate(result, 'minion1')
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(len(result.state.participant('pc').injury.wounds), 1)

    def test_npc_carried_two_handed_weapon_drops_shield_before_the_actual_equip(self):
        # Unlike the held-Sword fixture, the Shield has no +1d Sword Trait.
        values = [1,10] + [1]*5 + [10]*20 + [1,10,1]
        result = self.execute(npc_source(carried=True), values)
        decision, strike = self.assert_immediate(result, 'minion1', carried=True)
        drop, = tuple(step for step in result.steps if type(step.proof) is PcNpcShieldDropProof)
        equip, = tuple(step for step in result.steps if type(step.proof) is PcNpcWeaponEquipProof)
        self.assertTrue(decision.proof.selection.release_shield)
        self.assertEqual(equip.proof.transition.before, drop.state.enemy('minion1').state.weapon_inventory)
        self.assertEqual(strike.proof.weapon_intent.attack_use.inventory, equip.proof.transition.after)
        self.assertIsNone(equip.proof.transition.after.shield_hand)
        self.assertEqual(result.executed_actions, 2)

    def test_no_melee_weapon_settles_permission_once_and_repeated_stagger_is_not_a_new_trigger(self):
        values = [1]*5 + [10]*2 + [10]*2 + [10]*3 + [1]*5 + [10]*2
        result = self.execute(pc_source(melee=False, rounds=2), values)
        decisions = tuple(step for step in result.steps if type(step.proof) is PcBashDecisionProof)
        self.assertEqual(len(decisions), 1)
        self.assertIsNone(decisions[0].proof.selection)
        self.assertFalse(any(type(step.proof) is PcImmediateStrikeProof for step in result.steps))
        attacks = tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc')
        self.assertEqual(len(attacks), 2)
        self.assertTrue(attacks[1].source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)

    def test_actual_mounted_brawn_charge_does_not_lend_charge_traits_to_the_immediate_lance(self):
        source = pc_source()
        row = source.party[0]
        items = (row.combat_equipment[0], replace(row.combat_equipment[1], weapon=W.LANCE))
        row = replace(row, pc=replace(row.pc, weapon_skill=1, melee=2),
            combat_equipment=items, policy=PcMeleePolicy.AUTOMATIC_COMBAT, mount=CombatMount.HORSE)
        source = replace(source, party=(row,),
            facts=replace(source.facts, all_opponents_close=False, unmounted=False, can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG))
        result = self.execute(source, [1]*11)
        charge, = tuple(step for step in result.steps if type(step.proof) is PcBattlefieldChargeProof)
        self.assertTrue(charge.proof.result.attack_allowed)
        _, strike = self.assert_immediate(result, 'pc')
        self.assertTrue(pc_is_mounted(strike.source, 'pc'))
        self.assertIs(strike.proof.weapon_intent.attack_use.kind, W.LANCE)
        attack = strike.proof.request.kernel_request.attack
        # Horse's actual Charge already knocked the target Prone. Its ordinary
        # higher-ground bonus remains, while Charge-only Lance Traits do not.
        self.assertTrue(strike.source.enemy('minion1').state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(strike.proof.resolution.attack.attacker_test.trace.rolled_dice, 2)
        self.assertEqual(tuple((modifier.rule_id,modifier.amount)
            for modifier in attack.attacker_test.dice_modifiers), (('RULE-COMBAT-007:higher-ground',1),))
        self.assertEqual(attack.impact_spec.damage.base, 6)
        self.assertFalse(any('charge' in modifier.rule_id for modifier in attack.attacker_test.dice_modifiers))
        self.assertFalse(any('charge' in modifier.rule_id for modifier in attack.impact_spec.damage_modifiers))


if __name__ == '__main__':
    unittest.main()
