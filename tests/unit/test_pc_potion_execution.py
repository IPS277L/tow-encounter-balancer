"""Actual potion Recover actions following literal, continuous Wound prefixes."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, heavy_prefix
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.attack_models import ConditionOnHitSpec
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.pc_melee_models import PcMeleePolicy, PcWeaponHand, PcMeleeWeapon, PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcMeleeStep, PcMeleeOutcome, PcTurnEndProof, PcRecoverProof
from towr.domain.pc_potion_models import PcPotionRecoverProof, potion_options
from towr.domain.pc_heavy_wound_models import PcBodyFactKind
from towr.domain.pc_shield_models import PcShieldLocation
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.turn_models import CombatActionSlotResult, CombatActionKind, CombatActionDeclaration
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest, PcPotionUseCount
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def healing_source(*, enemies=3):
    source = make_pc_melee_scenario(enemy_count=enemies, max_rounds=2)
    # Healing the ringing ears must compete with genuinely difficult enemies,
    # rather than asserting that cosmetic injury always outranks a good Attack.
    enemies = []
    for enemy in source.enemies:
        resilience = replace(enemy.definition.resilience, toughness=10)
        enemies.append(replace(enemy, definition=replace(enemy.definition, resilience=resilience),
            state=replace(enemy.state, current_resilience=resilience)))
    return replace(source, party=(replace(source.party[0], policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        consumables=(ConsumableItem('healing', ConsumableKind.HEALING, 1, None),)),), enemies=tuple(enemies))


def healing_run(total):
    source = healing_source()
    rng = ScriptedD10(heavy_prefix(total)+[10]*18)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


class PcPotionExecutionTests(unittest.TestCase):
    def test_all_heavy_wounds_heal_the_exact_source_and_continue_actual_combat(self):
        for total in range(11, 24):
            with self.subTest(total=total):
                result = healing_run(total)
                steps = tuple(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
                self.assertEqual(len(steps), 1)
                step = steps[0]
                proof = step.proof
                self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
                self.assertEqual(proof.selection.wound_sequence, 3)
                self.assertEqual(proof.before.injury.wounds[2].table_total, total)
                self.assertTrue(proof.after.injury.wounds[2].healed)
                self.assertTrue(proof.after.injury.wounds[2].treated)
                self.assertEqual(proof.after.injury.wounds[:2], proof.before.injury.wounds[:2])
                self.assertEqual(proof.after.potions, ())
                self.assertFalse(any(fact.wound_sequence == 3 for fact in proof.after.body_facts))
                self.assertFalse(any(effect.wound_sequence == 3
                    for effect in proof.after.injury.active_wound_effects))
                self.assertEqual(proof.result.source_request.slot_index, 1)
                self.assertTrue(step.state.round_state.active_turn.action_slots[-1].executed)
                self.assertEqual(result.executed_actions, 8)
                self.assertEqual(result.source.party[0].consumables[0].quantity, 1)

    def test_native_proof_requires_current_source_and_one_application(self):
        result = healing_run(20)
        step = next(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertEqual(apply_pc_melee_step(step.source, step), step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state, step)
        for proof in (
            replace(step.proof, selection=replace(step.proof.selection, item_id='other')),
            replace(step.proof, selection=replace(step.proof.selection, wound_sequence=1)),
            replace(step.proof, after=step.proof.before),
        ):
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                PcMeleeStep(step.source, proof)
        proof = deepcopy(step.proof)
        object.__setattr__(proof.selection, 'wound_sequence', True)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(step.source, proof)
        proof = deepcopy(step.proof)
        object.__setattr__(proof.before.potions[0], 'quantity', True)
        self.assertEqual(proof.before.potions[0].quantity, 1)
        with self.assertRaises(TypeError):
            PcMeleeStep(step.source, proof)

    def test_actual_trial_counts_the_potion_separately_from_ally_recover(self):
        request = PcMeleeSimulationRequest(healing_source(), 42, 1)
        record = run_pc_melee_trial(request, 0,
            rng_factory=lambda _: ScriptedD10(heavy_prefix(22)+[10]*18))
        self.assertEqual(record.potion_use_counts, (PcPotionUseCount('pc', 'healing', 1),))
        self.assertEqual(tuple(row.count for row in record.ally_recover_action_counts), (0,))

    def test_defenceless_can_only_reserve_healing_and_cannot_get_an_extra_action(self):
        result = healing_run(20)
        step = next(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertTrue(step.proof.before.injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(step.proof.after.injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNotNone(step.proof.result.source_request.healing_potion)
        reservation = next(step for step in result.steps if type(step.proof) is CombatActionSlotResult
            and step.source.round_state.round_number == 2
            and step.source.round_state.active_turn.actor_id == 'pc')
        wrong = replace(reservation.proof, slot=replace(reservation.proof.slot,
            declaration=CombatActionDeclaration(CombatActionKind.ATTACK)))
        with self.assertRaises(ValueError):
            PcMeleeStep(reservation.source, wrong)
        extra = replace(reservation.proof, request_id='forged:second-potion')
        with self.assertRaises(ValueError):
            PcMeleeStep(step.state, extra)

    def test_held_shield_and_weapon_are_not_dropped_to_drink(self):
        source = healing_source()
        source = replace(source, party=(replace(source.party[0], shield=shield_loadout(PcWeaponHand.RIGHT)),))
        rng = ScriptedD10(heavy_prefix(14)+[10]*18)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertIs(proof.selection.hand, PcWeaponHand.LEFT)
        self.assertIs(proof.before.weapon_hand, PcWeaponHand.LEFT)
        self.assertIs(proof.after.weapon_hand, proof.before.weapon_hand)
        self.assertEqual(proof.after.shield, proof.before.shield)
        self.assertIs(proof.after.shield.hand, PcWeaponHand.RIGHT)

    def test_restored_arm_does_not_teleport_the_dropped_weapon(self):
        result = healing_run(20)
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertTrue(any(fact.kind is PcBodyFactKind.LOST_ARM for fact in proof.before.body_facts))
        self.assertFalse(any(fact.kind is PcBodyFactKind.LOST_ARM for fact in proof.after.body_facts))
        self.assertIsNone(proof.before.weapon_hand)
        self.assertIsNone(proof.after.weapon_hand)
        self.assertIsNone(result.state.party[0].weapon_hand)

    def test_independent_on_hit_drained_survives_healing_its_wound_namesake(self):
        source = healing_source()
        enemy = source.enemies[0]
        attack = replace(enemy.definition.attacks[0], secondary_effects=(
            ConditionOnHitSpec(Condition.DRAINED, 'authored:drained-on-hit'),))
        enemy = replace(enemy, definition=replace(enemy.definition, id='poisonous-minion-profile', attacks=(attack,)),
            state=replace(enemy.state, definition_id='poisonous-minion-profile'))
        source = replace(source, enemies=(enemy, *source.enemies[1:]))
        rng = ScriptedD10(heavy_prefix(14)+[10]*18)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertTrue(proof.after.injury.wounds[2].healed)
        self.assertEqual(proof.after.hit_condition_sources, proof.before.hit_condition_sources)
        self.assertTrue(proof.after.hit_condition_sources)
        self.assertTrue(proof.after.injury.conditions.has(Condition.DRAINED))
        self.assertFalse(any(isinstance(effect, WoundConditionEffect)
            and effect.condition is Condition.DRAINED for effect in proof.after.injury.active_wound_effects))

    def test_only_usable_injured_hand_causes_critical_even_while_other_wound_is_healed(self):
        source = healing_source(enemies=4)
        # Third Wound injures left hand12; fourth disables the right arm16.
        # Potion heals16 but its left-hand use leaves a real Critical source12.
        values = heavy_prefix(12) + [1]*3+[10]*3+[4]*4+[10]+[1]*3+[10]*24
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertIs(proof.selection.hand, PcWeaponHand.LEFT)
        self.assertEqual(proof.selection.wound_sequence, 4)
        self.assertFalse(proof.after.injury.wounds[2].healed)
        self.assertTrue(proof.after.injury.wounds[3].healed)
        self.assertTrue(any(isinstance(effect, WoundConditionEffect)
            and effect.wound_sequence == 3 and effect.condition is Condition.CRITICALLY_INJURED
            for effect in proof.after.injury.active_wound_effects))
        self.assertTrue(any(type(step.proof) is PcTurnEndProof and step.proof.critical is not None
            for step in result.steps))

    def test_no_usable_hand_keeps_inventory_and_does_not_create_potion_action(self):
        source = healing_source(enemies=4)
        # Two genuine severed arms; Defenceless makes the fourth hit unopposed.
        values = heavy_prefix(20)+[1]*3+[5]*4+[1]*3+[10]*12
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        self.assertFalse(any(type(step.proof) is PcPotionRecoverProof for step in result.steps))
        member = result.state.party[0]
        self.assertEqual(member.potions, source.party[0].consumables)
        self.assertEqual(potion_options(member), ())
        self.assertEqual(tuple(fact.kind for fact in member.body_facts),
            (PcBodyFactKind.LOST_ARM, PcBodyFactKind.LOST_ARM))

    def test_static_roles_do_not_silently_acquire_potion_tactics(self):
        with self.assertRaises(ValueError):
            replace(healing_source().party[0], policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)

    def test_generic_defenceless_permission_requires_the_actual_potion_interaction(self):
        result = healing_run(20)
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        request = proof.result.source_request
        self.assertTrue(request.actor_conditions.has(Condition.DEFENCELESS))
        for interaction in (None, replace(request.choice.object_interaction, object_id='other-item')):
            with self.subTest(interaction=interaction), self.assertRaises(ValueError):
                replace(request, choice=replace(request.choice, object_interaction=interaction))

    def test_inventory_ids_cannot_disguise_weapon_or_shield_pickup_as_drinking(self):
        for item_id, side in (('pc:weapon', 1), ('pc:shield', 10)):
            with self.subTest(item_id=item_id):
                source = healing_source()
                source = replace(source, max_rounds=5, party=(replace(source.party[0],
                    shield=shield_loadout(PcWeaponHand.RIGHT), consumables=(
                        ConsumableItem(item_id, ConsumableKind.HEALING, 4, None),)),))
                # Three genuine Wounds heal in r2–r4; one potion remains when
                # r5 finally picks up the dropped item bearing that internal ID.
                rng = ScriptedD10(heavy_prefix(12, side=side)+[10]*72)
                result = run_pc_melee_scenario(source, rng)
                rng.assert_exhausted()
                self.assertEqual(sum(type(step.proof) is PcPotionRecoverProof for step in result.steps), 3)
                pickups = tuple(step.proof for step in result.steps if type(step.proof) is PcRecoverProof)
                self.assertEqual(len(pickups), 1)
                self.assertEqual(pickups[0].result.source_request.choice.object_interaction.object_id, item_id)
                self.assertEqual(result.state.party[0].potions[0].quantity, 1)
                self.assertIs(result.state.party[0].weapon_hand, PcWeaponHand.LEFT)
                self.assertIs(result.state.party[0].shield.location, PcShieldLocation.HELD)

    def test_healing_disabled_shield_arm_restores_the_still_attached_shield(self):
        source = healing_source()
        source = replace(source, party=(replace(source.party[0], shield=shield_loadout(PcWeaponHand.RIGHT)),))
        rng = ScriptedD10(heavy_prefix(16, side=10)+[10]*18)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertIs(proof.before.shield.location, PcShieldLocation.UNAVAILABLE)
        self.assertIs(proof.after.shield.location, PcShieldLocation.HELD)
        self.assertIs(proof.after.shield.hand, PcWeaponHand.RIGHT)
        self.assertTrue(proof.after.injury.wounds[2].healed)

    def test_healing_another_wound_cannot_skip_critical_end_before_remaining_grip_stop(self):
        source = healing_source(enemies=4)
        source = replace(source, party=(replace(source.party[0],
            pc=replace(source.party[0].pc, weapon=PcMeleeWeapon.HALBERD),
            initial_weapon_hand=PcTwoHandedGrip.BOTH),))
        # Wound20 severs the left arm; the fourth unopposed hit causes22.
        # Healing22 leaves20/Defenceless/Critical and the unavailable2H grip.
        # The executed Recover still requires its Critical end test; failure
        # kills the Defenceless PC before the deferred grip boundary can stop.
        values = heavy_prefix(20)+[1]*3+[10,10,1,1]+[10]*3
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        potion = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertEqual(potion.selection.wound_sequence, 4)
        self.assertFalse(potion.after.injury.wounds[2].healed)
        self.assertTrue(potion.after.injury.wounds[3].healed)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
        self.assertIsNone(result.unsupported)
        self.assertIsInstance(result.steps[-1].proof, PcTurnEndProof)
        self.assertIsNotNone(result.steps[-1].proof.critical)
        self.assertTrue(result.state.party[0].injury.dead)


if __name__ == '__main__':
    unittest.main()
