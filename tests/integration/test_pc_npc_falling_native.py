"""A real NPC takeoff, airborne Charge and forced-fall native journal."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedRangedFacts,GeneratedWeapon
from towr.domain.injury_models import WoundEntryId
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec,PcBattlefieldSpec,battlefield_is_midair,battlefield_ground_below,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponItem
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.pc_heavy_wound_models import usable_hands
from towr.domain.pc_melee_models import PcMeleeWeapon,PcRangedProfile,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,PcMeleeOutcome,initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount,RiderKind,PcDismountProof
from towr.domain.pc_npc_distraction_models import _confirmed_death_source
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def npc_falling_source(disposition=NpcDefeatDisposition.KNOCKED_OUT):
    source=automatic_source(pc_count=1,enemy_count=2,rounds=2)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SHORTBOW,
        ranged=PcRangedProfile(1,2,ammunition_supply_confirmed=True),
        weapon_skill=1,melee=2,strength=1,agility=1,athletics=2),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('bow',PcMeleeWeapon.SHORTBOW,
            PcItemLocation.HELD,PcTwoHandedGrip.BOTH),),
        mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN,
        defeat_decisions=tuple(replace(decision,disposition=disposition) for decision in member.defeat_decisions))
    npc=GeneratedNpc(1,1,20,1,2,2,initial_generated_weapons(GeneratedWeapon.PISTOL),ArmourLoadout(),defence=2,
        ranged=GeneratedRangedFacts(6,6,3,4,True,True,True,awareness=2),
        mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
    ground_gunner=replace(npc,weapons=initial_generated_weapons(GeneratedWeapon.HANDGUN),mount=None,rider_kind=None)
    actors=source.enemy_activation_order
    return replace(source,party=(member,),enemies=(npc.participant(actors[0]),ground_gunner.participant(actors[1])),
        npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(profile,actor)
            for profile,actor in zip((npc,ground_gunner),actors)),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True,unmounted=False),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG,
            airspace=PcAirspaceSpec(2,True)))


class NativeNpcFallingTests(unittest.TestCase):
    def test_npc_falls_after_actual_airborne_mount_charge_and_keeps_native_replay(self):
        # R1: bow misses; two actual gunshots cause Wounds1 and16, with
        # one unusable arm. R2: the rider cannot use that bow, so the real
        # Pegasus Charge hits without breaching the NPC's high Resilience.
        values=[10,10]+[1]*6+[10,1]+[1]*6+[10,10,6,1]+[1]*4+[10]*8
        for disposition in (NpcDefeatDisposition.KNOCKED_OUT,NpcDefeatDisposition.KILLED):
            with self.subTest(disposition=disposition):
                source=npc_falling_source(disposition)
                rng=ScriptedD10(values)
                result=run_pc_melee_scenario(source,rng)
                rng.assert_exhausted()
                self.assertIsNone(result.unsupported)
                falls=[step for step in result.steps if type(step.proof) is PcFallingProof]
                self.assertEqual(len(falls),1)
                fall=falls[0]
                self.assertEqual(fall.proof.actor_id,'minion1')
                self.assertFalse(battlefield_is_midair(initial_pc_melee_state(source).battlefield,'minion1'))
                self.assertTrue(battlefield_is_midair(fall.source.battlefield,'minion1'))
                self.assertFalse(battlefield_is_midair(fall.state.battlefield,'minion1'))
                air=fall.source.battlefield.spatial.placement_for('minion1').zone_id
                self.assertEqual(fall.state.battlefield.spatial.placement_for('minion1').zone_id,
                    battlefield_ground_below(fall.source.battlefield,air))
                self.assertEqual(fall.source.battlefield.air_to_ground,fall.state.battlefield.air_to_ground)
                dismount=result.steps[fall.proof.request.dismount_history_index]
                self.assertIs(type(dismount.proof),PcDismountProof)
                self.assertTrue(dismount.proof.source_injury.conditions.has(Condition.PRONE))
                self.assertEqual(dismount.proof.source_injury.wounds,0)
                charged=next(step for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
                self.assertIsNotNone(charged.proof.mount_attack)
                self.assertIsNotNone(charged.proof.request.charge_movement)
                self.assertEqual(charged.proof.mount_attack.weapon_instance_id,'pc1:mount:pegasus:hooves')
                self.assertEqual(len(usable_hands(charged.source.participant('pc1'))),1)
                self.assertEqual(charged.source.participant('pc1').injury.wounds[-1].entry_id,
                    WoundEntryId.SLASHED_FOREARMS)
                self.assertEqual(fall.proof.test.trace.initial_values,(10,))
                self.assertEqual((fall.proof.result.rating,fall.proof.result.shortfall),(2,2))
                self.assertIsNotNone(fall.proof.result.profile_wound)
                self.assertIs(fall.proof.npc_disposition,disposition)
                self.assertIsNone(fall.proof.fate_decline)
                self.assertIsNone(fall.proof.glorious)
                self.assertTrue(fall.state.enemy('minion1').state.injury.defeated)
                self.assertIn('minion1',fall.state.round_state.excluded_turn_entity_ids)
                self.assertEqual(fall.source.round_state.active_turn,fall.state.round_state.active_turn)
                self.assertEqual(fall.state.round_state.active_turn.actor_id,'pc1')
                self.assertEqual(result.executed_actions,5)
                self.assertEqual(result.completed_rounds,2)
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                self.assertFalse(result.state.enemy('minion2').state.injury.defeated)
                expected_death=(fall.proof.request.id+':defeat'
                    if disposition is NpcDefeatDisposition.KILLED else None)
                self.assertEqual(_confirmed_death_source(result.state.history,'minion1'),expected_death)
                replay=initial_pc_melee_state(source)
                for step in result.steps:
                    replay=apply_pc_melee_step(replay,step)
                self.assertEqual(replay,result.state)
                with self.assertRaises(ValueError):
                    PcMeleeStep(fall.state,fall.proof)
                with self.assertRaises(ValueError):
                    PcMeleeStep(fall.source,replace(fall.proof,npc_disposition=None))

                # A fresh deterministic trial passes the public observation
                # aggregation path; falling adds no fabricated Attack/Reload.
                trial_rng=ScriptedD10(values)
                request=PcMeleeSimulationRequest(source,42,1)
                trial=run_pc_melee_trial(request,0,rng_factory=lambda _:trial_rng)
                trial_rng.assert_exhausted()
                batch=PcMeleeSimulationResult(request,(trial,))
                self.assertEqual(batch.total_action_count,5)
                self.assertEqual(batch.total_started_round_count,2)
                self.assertEqual(batch.total_completed_round_count,2)
                self.assertEqual(batch.outcome_counts.round_limit,1)
                self.assertEqual(batch.outcome_counts.unsupported_path,0)
                self.assertEqual([(row.actor_id,row.shots,row.reload_actions)
                    for row in trial.npc_ranged_counts],[('minion1',1,0),('minion2',1,1)])
                self.assertEqual(trial.pc_ranged_counts[0].shots,1)


if __name__=='__main__':
    unittest.main()
