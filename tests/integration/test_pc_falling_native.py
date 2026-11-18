"""Actual airborne forced dismounts retain their native Hazard/Wound owners."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.armour_models import ArmourLoadout,BodyArmour,ITHILMAR_ENVIRONMENT_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.injury_models import WoundEntryId
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec, PcBattlefieldSpec, battlefield_ground_below, battlefield_is_midair,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_falling_models import PcFallingAcknowledgementProof, PcFallingProof
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleeWeapon, PcNearMissPolicy, PcRangedProfile, PcTwoHandedGrip,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeStep, PcWoundCompletionProof, initial_pc_melee_state,
)
from towr.domain.pc_mount_models import CombatMount, PcDismountProof, RiderKind
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatActionSlotResult
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def falling_source(*, near_miss=False):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=1)
    member = source.party[0]
    member = replace(member,
        pc=replace(member.pc, weapon=PcMeleeWeapon.SHORTBOW,
            ranged=PcRangedProfile(1, 2, ammunition_supply_confirmed=True),
            agility=1, athletics=2, toughness=3),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('bow', PcMeleeWeapon.SHORTBOW,
            PcItemLocation.HELD, PcTwoHandedGrip.BOTH),),
        mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN,
        fate=replace(member.fate, rating=1, session_spend_limit=1),
        fate_policy=PcFatePolicy.CONFIGURED if near_miss else PcFatePolicy.DECLINE_OPTIONAL_FATE,
        near_miss_policy=PcNearMissPolicy(11, 0) if near_miss else None, glorious_policy=None)
    npc = GeneratedNpc(1, 1, 20, 1, 2, 2, initial_generated_weapons(GeneratedWeapon.HANDGUN),
        ArmourLoadout(), defence=2,
        ranged=GeneratedRangedFacts(6, 6, 3, 4,  True, True, True, awareness=2))
    actor = source.enemy_activation_order[0]
    return replace(source, party=(member,), enemies=(npc.participant(actor),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc, actor),),
        facts=replace(source.facts, all_opponents_close=False, can_leave_zone=True, unmounted=False),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG,
            airspace=PcAirspaceSpec(2, True)))


class NativeFallingIntegrationTests(unittest.TestCase):
    def test_pc_mantle_avoids_actual_environmental_fall_after_lawful_leg_spasm(self):
        source=falling_source()
        member=source.party[0]
        member=replace(member,armour=ArmourLoadout((BodyArmour.ITHILMAR,),BodyArmour.ITHILMAR),
            armour_worn=True,pc=replace(member.pc,armour_bonus=3))
        source=replace(source,party=(member,))
        rng=ScriptedD10([10,10]+[1]*6+[10,9,1,1])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        fall,=(step for step in result.steps if type(step.proof) is PcFallingProof)
        self.assertEqual(fall.proof.actor_id,'pc1')
        self.assertEqual(tuple(mod.amount for mod in fall.proof.request.avoidance_test.dice_modifiers
            if mod.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID),(1,))
        self.assertEqual((fall.proof.test.trace.rolled_dice,fall.proof.test.successes),(2,2))
        self.assertTrue(fall.proof.result.avoided)
        self.assertIsNone(fall.proof.result.pending_character_wound)
        self.assertIsNone(fall.state.pending_wound)
        self.assertEqual(tuple(w.table_total for w in result.state.participant('pc1').injury.wounds),(9,))
        self.assertEqual(len(result.state.participant('pc1').daily_wounds.receipts),1)
        self.assertEqual(fall.source.round_state,fall.state.round_state)
        self.assertEqual(result.executed_actions,2)
        replay=initial_pc_melee_state(source)
        for step in result.steps:replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)

    def test_npc_mantle_avoids_actual_environmental_fall_after_airborne_mount_charge(self):
        from tests.integration.test_pc_weighted_net_native import pc_net_scene
        # Net's first action leaves the NPC alive and free to take off. On the
        # following turn the PC makes a real aerial Hooves Charge, inflicting
        # Prone before Staggered without defeating this high-Toughness Minion.
        source=pc_net_scene(rounds=2)
        member=replace(source.party[0],mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
        npc=falling_source().enemies[0].definition.generated_components
        npc=replace(npc,armour=ArmourLoadout((BodyArmour.ITHILMAR,),BodyArmour.ITHILMAR),
            mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
        source=replace(source,party=(member,),enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),),
            facts=replace(source.facts,unmounted=False),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG,
                airspace=PcAirspaceSpec(2,True)))
        rng=ScriptedD10([1]*21)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        fall,=(step for step in result.steps if type(step.proof) is PcFallingProof)
        self.assertEqual(fall.proof.actor_id,'minion1')
        self.assertTrue(battlefield_is_midair(fall.source.battlefield,'minion1'))
        self.assertFalse(battlefield_is_midair(fall.state.battlefield,'minion1'))
        self.assertEqual(tuple(mod.amount for mod in fall.proof.request.avoidance_test.dice_modifiers
            if mod.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID),(1,))
        self.assertEqual((fall.proof.test.trace.rolled_dice,fall.proof.test.successes),(2,2))
        self.assertTrue(fall.proof.result.avoided)
        self.assertIsNone(fall.proof.npc_disposition)
        self.assertFalse(fall.state.enemy('minion1').state.injury.defeated)
        self.assertEqual(fall.state.enemy('minion1').state.injury.wounds,0)
        self.assertEqual(fall.source.round_state,fall.state.round_state)
        self.assertTrue(all(getattr(step.proof,'glorious',None) is None for step in result.steps))
        replay=initial_pc_melee_state(source)
        for step in result.steps:replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)

    def assert_falling_sequence(self, result):
        actor = result.source.pc_activation_order[0]
        falls = [(index, step) for index, step in enumerate(result.steps)
            if type(step.proof) is PcFallingProof]
        self.assertEqual(len(falls), 1)
        fall_index, fall = falls[0]
        request = fall.proof.request
        original = result.steps[request.dismount_history_index]
        self.assertIs(type(original.proof), PcDismountProof)
        self.assertEqual(request.source_dismount, original.proof)
        self.assertLess(request.dismount_history_index, fall_index)
        self.assertTrue(battlefield_is_midair(fall.source.battlefield, actor))
        self.assertFalse(battlefield_is_midair(fall.state.battlefield, actor))
        air_zone = fall.source.battlefield.spatial.placement_for(actor).zone_id
        self.assertEqual(fall.state.battlefield.spatial.placement_for(actor).zone_id,
            battlefield_ground_below(fall.source.battlefield, air_zone))
        self.assertEqual(fall.source.battlefield.air_to_ground, fall.state.battlefield.air_to_ground)
        self.assertEqual(fall.proof.test.successes, 1)
        self.assertEqual((fall.proof.result.rating, fall.proof.result.shortfall), (2, 1))
        self.assertEqual(request.previous_injury.wounds[0].entry_id, WoundEntryId.LEG_SPASM)
        self.assertTrue(request.previous_injury.conditions.has(Condition.PRONE))
        self.assertEqual(fall.state.pending_wound, fall.proof.result.pending_character_wound)
        self.assertIsNotNone(fall.state.pending_wound)
        self.assertEqual(fall.source.round_state, fall.state.round_state)
        self.assertEqual(len(fall.state.round_state.active_turn.action_slots), 1)
        attacks = [step.proof for step in result.steps[:fall_index] if type(step.proof) is PcAttackProof]
        self.assertEqual(tuple(proof.request.actor_id for proof in attacks),
            (actor, result.source.enemy_activation_order[0]))
        # Consequences retain the executed attack receipt; no new paid slot buys the fall.
        self.assertEqual(fall.state.round_state.active_turn.action_slots[0], attacks[-1].execution.slot)
        self.assertEqual(sum(type(step.proof) is CombatActionSlotResult for step in result.steps), 2)
        completions = [(index, step) for index, step in enumerate(result.steps)
            if type(step.proof) is PcWoundCompletionProof
            and step.proof.completion.source_request.roll == fall.state.pending_wound]
        self.assertEqual(len(completions), 1)
        completion_index, completion = completions[0]
        acknowledgements = [(index, step) for index, step in enumerate(result.steps)
            if type(step.proof) is PcFallingAcknowledgementProof]
        self.assertEqual(len(acknowledgements), 1)
        ack_index, ack = acknowledgements[0]
        self.assertLess(fall_index, completion_index)
        self.assertLess(completion_index, ack_index)
        self.assertEqual(ack.proof.source_id, request.id)
        self.assertEqual(ack.proof.completion, completion.proof.completion)
        self.assertEqual(ack.proof.result.character_wound_completion, completion.proof.completion)
        self.assertIsNone(ack.state.pending_wound)
        self.assertIsNone(ack.proof.result.pending_character_wound)
        self.assertTrue(ack.state.participant(actor).injury.conditions.has(Condition.PRONE))
        self.assertEqual(ack.source.round_state, ack.state.round_state)
        self.assertIsNone(result.state.pending_wound)
        self.assertTrue(all(not mount.mounted for mount in result.state.mounts))
        return fall, completion, ack

    def test_forced_pc_dismount_completes_falling_wound_without_another_action(self):
        source = falling_source()
        rng = ScriptedD10([10, 10] + [1]*6 + [10, 9, 1, 1, 1])
        result = run_pc_melee_scenario(source, rng)
        self.assertIsNone(result.unsupported)
        rng.assert_exhausted()
        fall, completion, ack = self.assert_falling_sequence(result)
        self.assertIs(completion.proof.completion.outcome, CharacterWoundLifecycleOutcome.ACCEPTED)
        self.assertEqual(tuple(wound.table_total for wound in result.state.participant('pc1').injury.wounds), (9, 2))
        self.assertEqual(len(result.state.participant('pc1').daily_wounds.receipts), 2)
        self.assertEqual(result.state.participant('pc1').fate, source.party[0].fate)
        # Each independent optional Fate window is acknowledged exactly once.
        declines = [step.proof.fate_decline for step in result.steps
            if getattr(step.proof, 'fate_decline', None) is not None]
        self.assertEqual(len({(decline.source_id, decline.window) for decline in declines}), len(declines))
        self.assertEqual(fall.proof.fate_decline.source_id, fall.proof.request.exposure.test_id)
        self.assertEqual(completion.proof.fate_decline.source_id, fall.state.pending_wound.request_id)
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        with self.assertRaises(ValueError):
            PcMeleeStep(fall.state, fall.proof)
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.state, ack.proof)

    def test_falling_wound_can_burn_near_miss_without_cancelling_original_wound(self):
        source = falling_source(near_miss=True)
        rng = ScriptedD10([10, 10] + [1]*6 + [10, 9, 1, 9, 9])
        result = run_pc_melee_scenario(source, rng)
        self.assertIsNone(result.unsupported)
        rng.assert_exhausted()
        fall, completion, ack = self.assert_falling_sequence(result)
        completed = completion.proof.completion
        self.assertIs(completed.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(completed.wound_result.table_roll.values, (9, 9))
        self.assertEqual(completed.near_miss_application.cancelled_wound.table_total, 18)
        member = result.state.participant('pc1')
        self.assertEqual(tuple(wound.table_total for wound in member.injury.wounds), (9,))
        self.assertEqual(member.injury.active_wound_effects, fall.proof.request.previous_injury.active_wound_effects)
        self.assertEqual(len(member.daily_wounds.receipts), 1)
        self.assertEqual(member.fate.rating, 0)
        self.assertEqual(len(member.fate.burns), 1)
        self.assertEqual(member.fate.resource_event_ids, (completed.fate_burn.burn.id,))
        self.assertEqual(member.fate.burns[0].subject_id, fall.state.pending_wound.wound_result.request_id)
        self.assertEqual(len(completed.consumed_near_miss_effect_ids), 1)


if __name__ == '__main__':
    unittest.main()
