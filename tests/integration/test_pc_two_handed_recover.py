"""Automatic melee2H Recover preserves real Wounds, hands and turn consequences."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10, heavy_prefix
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_heavy_wound_models import PcBodyFactKind, usable_hands
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcFatePolicy, PcMeleePolicy, PcMeleeWeapon,
    PcNearMissPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcBodyConsequenceProof,
    PcIncapacitatedTurnEndProof, PcMeleeOutcome, PcRecoverProof, PcTurnEndProof,
    initial_pc_melee_state,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class LiteralPrefixThenMisses:
    """A literal injury prefix followed only by failed ordinary dice rolls."""
    def __init__(self, prefix):
        self.prefix = tuple(prefix)
        self.index = 0

    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('this deterministic combat uses only d10')
        result = self.prefix[self.index] if self.index < len(self.prefix) else 10
        self.index += 1
        return result


def scene(*, enemies=3, party=1, rounds=3, automatic=True, backup=False, endurance=10):
    source = make_pc_melee_party_scenario(pc_count=party, enemy_count=enemies,
        max_rounds=rounds)
    member = source.party[0]
    policy = (PcMeleePolicy.AUTOMATIC_COMBAT if automatic
        else PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
    backup_policy = (PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, PcWeaponHand.RIGHT)
        if backup else None)
    equipment = ((PcWeaponItem('pole:owned', PcMeleeWeapon.PICKAXE,
        PcItemLocation.HELD, PcTwoHandedGrip.BOTH),
        *((PcWeaponItem('sword:owned', PcMeleeWeapon.SWORD,
            PcItemLocation.CARRIED, None),) if backup else ())) if automatic else None)
    member = replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.PICKAXE,
        strength=10, endurance=endurance), initial_weapon_hand=PcTwoHandedGrip.BOTH,
        policy=policy, backup_weapon_policy=backup_policy, combat_equipment=equipment)
    others = tuple(replace(ally, pc=replace(ally.pc, weapon_skill=1,
        melee=1, strength=1, toughness=20)) for ally in source.party[1:])
    # Ordinary high-Damage Minions make the scripted actual Wounds independent
    # of the starting melee weapon. Later all-miss dice cannot inflict new ones.
    opponents = []
    for enemy in source.enemies:
        resilience = ResilienceProfile(1, 10)
        attack = replace(enemy.definition.attacks[0], damage=DamageProfile(30))
        opponents.append(replace(enemy,
            definition=replace(enemy.definition, resilience=resilience, attacks=(attack,)),
            state=replace(enemy.state, current_resilience=resilience)))
    return replace(source, party=(member, *others), enemies=tuple(opponents))


def zero_hand_prefix(*, party=1):
    # Three real hits cause Wounds1,2,16(right unusable). The fourth causes
    # Wound18 and the actual left-hand clutch, leaving no usable hands.
    values = heavy_prefix(16, side=10)
    if party == 2:
        values = values[:5] + [10, 10, 10] + values[5:]  # Weak ally also misses.
    return values + [1, 1, 1] + [10, 10, 10] + [10, 6, 1, 1]


def recovers(result):
    return tuple(step for step in result.steps if type(step.proof) is PcRecoverProof
        and step.source.round_state.active_turn.actor_id == 'pc1')


class AutomaticTwoHandedRecoverTests(unittest.TestCase):
    def execute(self, source, prefix):
        rng = LiteralPrefixThenMisses(prefix)
        result = run_pc_melee_scenario(source, rng)
        self.assertGreaterEqual(rng.index, len(prefix))
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        self.assertIsNone(result.unsupported)
        return result

    def assert_no_free_restoration(self, steps, usable_count):
        self.assertTrue(steps)
        for step in steps:
            before = step.source.participant('pc1')
            after = step.state.participant('pc1')
            self.assertEqual(len(usable_hands(before)), usable_count)
            self.assertEqual(usable_hands(after), usable_hands(before))
            self.assertEqual(after.body_facts, before.body_facts)
            self.assertEqual(after.injury.wounds, before.injury.wounds)
            self.assertEqual(after.weapon_inventory, before.weapon_inventory)
            self.assertEqual(after.weapon_hand, before.weapon_hand)
            self.assertIsNone(step.proof.result.source_request.choice.object_interaction)
            self.assertTrue(step.state.round_state.active_turn.action_slots[-1].executed)

    def test_one_usable_hand_recovers_after_arm_loss_or_clutch_without_fake_pickup(self):
        for total, kind in ((16, PcBodyFactKind.UNUSABLE_ARM),
                (18, PcBodyFactKind.CLUTCH_STOMACH)):
            with self.subTest(wound=total):
                result = self.execute(scene(), heavy_prefix(total))
                self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
                self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds],
                    [1, 2, total])
                self.assertIn(kind, tuple(f.kind for f in result.state.party[0].body_facts))
                steps = recovers(result)
                self.assertEqual([step.source.round_state.round_number for step in steps], [2, 3])
                self.assert_no_free_restoration(steps, 1)
                self.assertFalse(any(type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id == 'pc1'
                    and step.source.round_state.round_number > 1 for step in result.steps))

    def test_defenceless_arm_loss_keeps_empty_turns_and_mandatory_critical_end_phase(self):
        result = self.execute(scene(), heavy_prefix(20))
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds], [1, 2, 20])
        self.assertIn(PcBodyFactKind.LOST_ARM,
            tuple(f.kind for f in result.state.party[0].body_facts))
        self.assertEqual(len(usable_hands(result.state.party[0])), 1)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(recovers(result))
        ends = tuple(step for step in result.steps if type(step.proof) is PcIncapacitatedTurnEndProof)
        self.assertEqual([step.source.round_state.round_number for step in ends], [2, 3])
        self.assertTrue(all(step.proof.critical is not None for step in ends))
        self.assertFalse(result.state.party[0].injury.dead)

    def test_no_usable_hands_recovers_then_still_owes_critical_death(self):
        result = self.execute(scene(enemies=4, endurance=4), zero_hand_prefix())
        recover, = recovers(result)
        self.assert_no_free_restoration((recover,), 0)
        self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds],
            [1, 2, 16, 18])
        self.assertTrue(result.state.party[0].injury.dead)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
        end, = tuple(step for step in result.steps if type(step.proof) is PcTurnEndProof
            and step.proof.critical is not None)
        self.assertGreater(result.steps.index(end), result.steps.index(recover))
        self.assertEqual(end.source.round_state.round_number, 2)

    def test_no_usable_hands_can_survive_recover_until_round_limit(self):
        result = self.execute(scene(enemies=4), zero_hand_prefix())
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        self.assertFalse(result.state.party[0].injury.dead)
        self.assert_no_free_restoration(recovers(result), 0)
        self.assertEqual([step.source.round_state.round_number for step in recovers(result)], [2, 3])
        self.assertFalse(any(type(step.proof) is PcBackupWeaponDrawProof for step in result.steps))

    def test_ally_and_npcs_continue_after_handless_recover_and_critical_death(self):
        result = self.execute(scene(enemies=4, party=2, endurance=4), zero_hand_prefix(party=2))
        recover, = recovers(result)
        self.assert_no_free_restoration((recover,), 0)
        self.assertTrue(result.state.participant('pc1').injury.dead)
        self.assertFalse(result.state.participant('pc2').injury.dead)
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        later = result.steps[result.steps.index(recover)+1:]
        self.assertTrue(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc2' for step in later))
        self.assertTrue(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id.startswith('minion') for step in later))

    def test_one_hand_uses_the_existing_backup_instead_of_getting_stuck_recovering(self):
        result = self.execute(scene(backup=True), heavy_prefix(16))
        draws = tuple(step for step in result.steps if type(step.proof) is PcBackupWeaponDrawProof)
        self.assertEqual(len(draws), 1)
        draw, = draws
        self.assertTrue(draw.state.participant('pc1').using_backup_weapon)
        self.assertIs(draw.state.participant('pc1').weapon_hand, PcWeaponHand.RIGHT)
        self.assertEqual(draw.state.participant('pc1').weapon_inventory.active_item_id, 'sword:owned')
        later_attacks = tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc1'
            and step.source.round_state.round_number > 1)
        self.assertTrue(later_attacks)
        self.assertTrue(all(step.source.participant('pc1').using_backup_weapon for step in later_attacks))
        self.assertFalse(recovers(result))

    def test_no_hand_does_not_draw_the_carried_backup(self):
        result = self.execute(scene(enemies=4, backup=True), zero_hand_prefix())
        self.assert_no_free_restoration(recovers(result), 0)
        self.assertFalse(any(type(step.proof) is PcBackupWeaponDrawProof for step in result.steps))
        self.assertFalse(result.state.participant('pc1').using_backup_weapon)
        inventory = result.state.participant('pc1').weapon_inventory
        self.assertIs(next(item for item in inventory.items if item.id == 'sword:owned').location,
            PcItemLocation.CARRIED)

    def test_near_miss_negates_the_actual_hand_loss_without_creating_recover_fallback(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(16, 0)),))
        result = self.execute(source, heavy_prefix(16)[:-1])
        self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds], [1, 2])
        self.assertEqual(result.state.party[0].body_facts, ())
        self.assertEqual(len(usable_hands(result.state.party[0])), 2)
        self.assertEqual(result.state.party[0].fate.rating, 2)
        self.assertFalse(recovers(result))
        self.assertTrue(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc1'
            and step.source.round_state.round_number > 1 for step in result.steps))

    def test_explicit_attack_policy_retains_its_precise_post_consequence_stop(self):
        source = scene(automatic=False)
        rng = ScriptedD10(heavy_prefix(16))
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual((result.unsupported.reason, result.unsupported.table_total),
            ('two_handed_grip_unavailable', 16))
        self.assertIsInstance(result.steps[-1].proof, PcBodyConsequenceProof)
        self.assertEqual(result.state.pending, ())
        self.assertIsNone(result.state.pending_wound)
        self.assertFalse(recovers(result))


if __name__ == '__main__':
    unittest.main()
