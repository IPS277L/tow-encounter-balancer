"""Real PC grip transitions preserve the same spear/polearm and Wound sources."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, heavy_prefix
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_heavy_wound_models import PcBodyFactKind, usable_hands
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcMeleeWeapon, PcShieldHandConflictPolicy, PcShieldLoadout,
    PcShieldRecoveryPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBodyConsequenceProof, PcHandSwapProof,
    PcIncapacitatedTurnEndProof, PcMeleeOutcome, PcMeleeStep, PcRecoverProof,
    initial_pc_melee_state,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


VARIABLE_WEAPONS = (PcMeleeWeapon.FOOT_SPEAR, PcMeleeWeapon.POLEARM)


class LiteralPrefixThenMisses:
    """Execute a literal Wound prefix; subsequent ordinary rolls always fail.

    Injury scenarios explicitly give Endurance10, so later Critical Tests are
    survived with these same literal10s. No future state or RNG is inspected.
    """
    def __init__(self, prefix):
        self.prefix = tuple(prefix)
        self.index = 0

    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('this scripted encounter uses only d10')
        value = self.prefix[self.index] if self.index < len(self.prefix) else 10
        self.index += 1
        return value


def scenario(weapon, hand, *, shield=False, enemies=1, rounds=1, injury_test=False):
    source = make_pc_melee_scenario(enemy_count=enemies, max_rounds=rounds)
    member = source.party[0]
    shield_source = (PcShieldLoadout(PcWeaponHand.RIGHT,
        PcShieldHandConflictPolicy.WEAPON_FIRST, PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
        if shield else None)
    member = replace(member, pc=replace(member.pc, weapon=weapon,
        strength=10 if injury_test else 3, endurance=10 if injury_test else 4),
        initial_weapon_hand=hand, policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        shield=shield_source, combat_equipment=(
            PcWeaponItem('pole:owned', weapon, PcItemLocation.HELD, hand),))
    opponents = source.enemies
    if injury_test:
        # The literal prefix misses its own Attack and then receives real
        # Wounds irrespective of weapon bonus. Later failed enemy Tests cause
        # no additional Wounds. These are authored numeric opponents.
        opponents = tuple(replace(enemy,
            definition=replace(enemy.definition, resilience=ResilienceProfile(1, 10),
                attacks=(replace(enemy.definition.attacks[0], damage=DamageProfile(30)),)),
            state=replace(enemy.state, current_resilience=ResilienceProfile(1, 10)))
            for enemy in opponents)
    return replace(source, party=(member,), enemies=opponents)


def pc_attacks(result, *, after_round=0):
    return tuple(step for step in result.steps if type(step.proof) is PcAttackProof
        and step.proof.request.actor_id == 'pc'
        and step.source.round_state.round_number > after_round)


def critical_sources(member):
    return tuple(effect.wound_sequence for effect in member.injury.active_wound_effects
        if type(effect) is WoundConditionEffect
        and effect.condition is Condition.CRITICALLY_INJURED)


class PcVariableGripIntegrationTests(unittest.TestCase):
    def execute(self, source, values, *, tail_misses=False):
        original = deepcopy(source)
        rng = LiteralPrefixThenMisses(values) if tail_misses else ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        if tail_misses:
            self.assertGreaterEqual(rng.index, len(values))
        else:
            rng.assert_exhausted()
        self.assertEqual(source, original)
        self.assertIsNone(result.unsupported)
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        return result

    def assert_same_physical_weapon(self, result, weapon):
        self.assertEqual(result.source.party[0].combat_equipment[0].id, 'pole:owned')
        for member in (initial_pc_melee_state(result.source).party[0],
                *(step.state.party[0] for step in result.steps)):
            inventory = member.weapon_inventory
            self.assertEqual(tuple((item.id, item.weapon) for item in inventory.items),
                (('pole:owned', weapon),))
            self.assertEqual(inventory.active_item_id, 'pole:owned')
            self.assertFalse(member.using_backup_weapon)

    def test_literal_one_hand_and_two_hand_damage_for_both_weapons(self):
        for weapon, two_hand_damage in ((PcMeleeWeapon.FOOT_SPEAR, 4),
                (PcMeleeWeapon.POLEARM, 5)):
            for grip, shield, expected_damage in ((PcWeaponHand.LEFT, True, 3),
                    (PcTwoHandedGrip.BOTH, False, two_hand_damage)):
                with self.subTest(weapon=weapon, grip=grip):
                    result = self.execute(scenario(weapon, grip, shield=shield), [1, 1, 1, 10, 10])
                    attack, = pc_attacks(result)
                    self.assertEqual(attack.proof.execution.resolution.attack.impact_spec.damage.base,
                        expected_damage)
                    self.assertEqual(attack.proof.execution.resolution.attack.damage, expected_damage + 3)
                    self.assertIs(attack.source.participant('pc').weapon_hand, grip)
                    self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                    self.assert_same_physical_weapon(result, weapon)

    def test_one_hand_shield_is_legal_but_two_hand_shield_is_rejected(self):
        for weapon in VARIABLE_WEAPONS:
            with self.subTest(weapon=weapon):
                source = scenario(weapon, PcWeaponHand.LEFT, shield=True)
                initial = initial_pc_melee_state(source).party[0]
                self.assertIs(initial.weapon_hand, PcWeaponHand.LEFT)
                self.assertIs(initial.shield.hand, PcWeaponHand.RIGHT)
                self.assertEqual(initial.weapon_inventory.active.id, 'pole:owned')
                with self.assertRaises(ValueError):
                    scenario(weapon, PcTwoHandedGrip.BOTH, shield=True)

    def test_healthy_own_turn_changes_grip_by_real_proof_without_creating_an_item(self):
        for weapon, expected_damage in ((PcMeleeWeapon.FOOT_SPEAR, 4),
                (PcMeleeWeapon.POLEARM, 5)):
            with self.subTest(weapon=weapon):
                source = scenario(weapon, PcWeaponHand.LEFT)
                self.assertIs(initial_pc_melee_state(source).party[0].weapon_hand, PcWeaponHand.LEFT)
                result = self.execute(source, [1, 1, 1, 10, 10])
                swap, = tuple(step for step in result.steps if type(step.proof) is PcHandSwapProof)
                self.assertIs(swap.proof.previous_hand, PcWeaponHand.LEFT)
                self.assertIs(swap.proof.hand, PcTwoHandedGrip.BOTH)
                self.assertEqual(swap.source.round_state.active_turn.actor_id, 'pc')
                self.assertEqual(swap.source.round_state.active_turn.action_slots, ())
                self.assertEqual(swap.state.round_state, swap.source.round_state)
                self.assertIs(swap.state.party[0].weapon_inventory.active.hand, PcTwoHandedGrip.BOTH)
                attack, = pc_attacks(result)
                self.assertEqual(attack.proof.execution.resolution.attack.impact_spec.damage.base,
                    expected_damage)
                self.assert_same_physical_weapon(result, weapon)
                with self.assertRaises(ValueError):
                    PcMeleeStep(swap.source, replace(swap.proof, previous_hand=PcWeaponHand.RIGHT))
                with self.assertRaises(ValueError):
                    apply_pc_melee_step(swap.state, swap)
                with self.assertRaises(ValueError):
                    replace(result, steps=tuple(step for step in result.steps if step is not swap))

    def test_actual_unusable_arm_changes_both_to_other_hand_and_removes_damage_bonus(self):
        for weapon in VARIABLE_WEAPONS:
            for side, healthy in ((1, PcWeaponHand.RIGHT), (10, PcWeaponHand.LEFT)):
                with self.subTest(weapon=weapon, side=side):
                    source = scenario(weapon, PcTwoHandedGrip.BOTH,
                        enemies=3, rounds=3, injury_test=True)
                    result = self.execute(source, heavy_prefix(16, side=side), tail_misses=True)
                    self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds],
                        [1, 2, 16])
                    swap, = tuple(step for step in result.steps if type(step.proof) is PcHandSwapProof)
                    self.assertIs(swap.proof.previous_hand, PcTwoHandedGrip.BOTH)
                    self.assertIs(swap.proof.hand, healthy)
                    self.assertEqual(swap.source.round_state.round_number, 2)
                    self.assertEqual(swap.source.round_state.active_turn.actor_id, 'pc')
                    self.assertEqual(swap.state.party[0].body_facts, swap.source.party[0].body_facts)
                    self.assertEqual(swap.state.party[0].injury.wounds, swap.source.party[0].injury.wounds)
                    self.assertEqual(usable_hands(swap.state.party[0]), (healthy,))
                    self.assertEqual(swap.state.party[0].weapon_inventory.active.id, 'pole:owned')
                    later = pc_attacks(result, after_round=1)
                    self.assertTrue(later)
                    self.assertTrue(all(step.source.party[0].weapon_hand is healthy for step in later))
                    self.assertTrue(all(step.proof.execution.resolution.attack.impact_spec.damage.base == 10
                        for step in later))
                    self.assert_same_physical_weapon(result, weapon)

    def test_actual_arm_loss_keeps_defenceless_turns_without_illegal_attack_or_swap(self):
        for weapon in VARIABLE_WEAPONS:
            with self.subTest(weapon=weapon):
                result = self.execute(scenario(weapon, PcTwoHandedGrip.BOTH,
                    enemies=3, rounds=3, injury_test=True), heavy_prefix(20), tail_misses=True)
                member = result.state.party[0]
                self.assertEqual([w.table_total for w in member.injury.wounds], [1, 2, 20])
                self.assertIn(PcBodyFactKind.LOST_ARM, tuple(fact.kind for fact in member.body_facts))
                self.assertTrue(member.injury.conditions.has(Condition.DEFENCELESS))
                self.assertEqual(len(usable_hands(member)), 1)
                self.assertFalse(pc_attacks(result, after_round=1))
                self.assertFalse(any(type(step.proof) is PcHandSwapProof for step in result.steps))
                self.assertFalse(any(type(step.proof) is PcRecoverProof for step in result.steps))
                ends = tuple(step for step in result.steps
                    if type(step.proof) is PcIncapacitatedTurnEndProof)
                self.assertEqual([step.source.round_state.round_number for step in ends], [2, 3])
                self.assertTrue(all(step.proof.critical is not None for step in ends))
                self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
                self.assert_same_physical_weapon(result, weapon)

    def test_actual_smashed_hand_drop_recovers_same_item_with_healthy_single_hand(self):
        for weapon in VARIABLE_WEAPONS:
            for side, healthy in ((1, PcWeaponHand.RIGHT), (10, PcWeaponHand.LEFT)):
                with self.subTest(weapon=weapon, side=side):
                    result = self.execute(scenario(weapon, PcTwoHandedGrip.BOTH,
                        enemies=3, rounds=2, injury_test=True),
                        heavy_prefix(12, side=side, endurance_success=True), tail_misses=True)
                    recover, = tuple(step for step in result.steps if type(step.proof) is PcRecoverProof)
                    self.assertIsNone(recover.source.party[0].weapon_hand)
                    self.assertIs(recover.source.party[0].weapon_inventory.active.location, PcItemLocation.DROPPED)
                    self.assertIs(recover.state.party[0].weapon_hand, healthy)
                    self.assertIs(recover.state.party[0].weapon_inventory.active.location, PcItemLocation.HELD)
                    self.assertIs(recover.state.party[0].weapon_inventory.active.hand, healthy)
                    self.assertEqual(recover.state.party[0].body_facts, recover.source.party[0].body_facts)
                    self.assertEqual(recover.state.party[0].injury.wounds, recover.source.party[0].injury.wounds)
                    self.assertNotIn(3, critical_sources(recover.source.party[0]))
                    self.assertNotIn(3, critical_sources(recover.state.party[0]))
                    self.assertFalse(recover.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
                    self.assert_same_physical_weapon(result, weapon)

    def test_real_injured_hand_pickup_keeps_wound12_critical_source_when_other_arm_is_unusable(self):
        # Wounds1,2,12 injure/drop the left hand's item. A fourth real Wound16
        # disables the right arm. Recover must use the injured remaining left
        # hand and apply W12's own Critical source, independent of W16's.
        values = heavy_prefix(12, side=1, endurance_success=True)
        values += [1, 1, 1, 10, 10, 10, 10, 4, 1, 1, 10]
        for weapon in VARIABLE_WEAPONS:
            with self.subTest(weapon=weapon):
                result = self.execute(scenario(weapon, PcTwoHandedGrip.BOTH,
                    enemies=4, rounds=2, injury_test=True), values, tail_misses=True)
                recover, = tuple(step for step in result.steps if type(step.proof) is PcRecoverProof)
                self.assertEqual([w.table_total for w in recover.source.party[0].injury.wounds],
                    [1, 2, 12, 16])
                self.assertEqual(usable_hands(recover.source.party[0]), (PcWeaponHand.LEFT,))
                self.assertNotIn(3, critical_sources(recover.source.party[0]))
                self.assertIn(4, critical_sources(recover.source.party[0]))
                self.assertIs(recover.state.party[0].weapon_hand, PcWeaponHand.LEFT)
                self.assertIn(3, critical_sources(recover.state.party[0]))
                self.assertIn(4, critical_sources(recover.state.party[0]))
                self.assertTrue(recover.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
                self.assert_same_physical_weapon(result, weapon)


if __name__ == '__main__':
    unittest.main()
