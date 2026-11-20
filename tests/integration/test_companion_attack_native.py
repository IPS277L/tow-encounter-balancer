"""Genuine range fallback targets an allied NPC body, without PC Fate.

Only Talent admission is widened for this unfinished feature's fixture. The
flight, charge, Wound, retained body, fall, next round and attacks are native.
"""
from dataclasses import replace
from unittest import TestCase, main
from unittest.mock import patch

from tests.integration.test_pc_falling_native import falling_source
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent
from towr.domain import talent_actor_models
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_battlefield_models import battlefield_is_midair
from towr.domain.pc_melee_result_models import PcAttackProof, PcProfileWoundProof, PcAttackerStaggerProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.condition_models import Condition
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def airborne_companion_source():
    source = falling_source()
    pc = replace(source.party[0], talents=(free_talent(TalentId.ACROBATIC),
        free_talent(TalentId.BACK_IN_THE_SADDLE)))
    npc = GeneratedNpc(5,5,20,3,6,2,initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(),defence=2,mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
    return replace(source,party=(pc,),enemies=(npc.participant(source.enemy_activation_order[0]),),
        npc_ranged_policies=(), max_rounds=2,
        battlefield=replace(source.battlefield,
            airspace=replace(source.battlefield.airspace,fall_hazard_rating=1)))


class NativeCompanionAttackTests(TestCase):
    def setUp(self):
        self.enterContext(patch.object(talent_actor_models,'PC_EXECUTABLE_TALENTS',
            talent_actor_models.PC_EXECUTABLE_TALENTS | {TalentId.BACK_IN_THE_SADDLE}))

    def test_wounded_airborne_body_lands_on_its_next_real_turn_without_falling_damage(self):
        from tests.integration.test_pc_two_handed_recover import LiteralPrefixThenMisses
        from towr.domain.pc_companion_landing_models import PcCompanionLandingProof
        from towr.domain.pc_falling_models import PcFallingProof
        source=replace(airborne_companion_source(),max_rounds=3)
        rng=LiteralPrefixThenMisses([10]*4+[1]*6+[10]*3+[9,10]+[1]*6+[10]*4)
        result=run_pc_melee_scenario(source,rng)
        self.assertIsNone(result.unsupported)
        landing,=tuple(step for step in result.steps if type(step.proof) is PcCompanionLandingProof)
        self.assertEqual(landing.proof.body_id,'pc1:mount')
        self.assertEqual(landing.proof.actor_id,'pc1:mount')
        self.assertEqual(landing.source.round_state.round_number,3)
        self.assertEqual(landing.proof.turn_start.turn.actor_id,'pc1:mount')
        self.assertTrue(battlefield_is_midair(landing.source.battlefield,'pc1:mount'))
        self.assertFalse(battlefield_is_midair(landing.state.battlefield,'pc1:mount'))
        self.assertIn('pc1:mount',landing.state.battlefield.spatial.free_move_used_entity_ids)
        self.assertEqual(landing.state.round_state,landing.source.round_state)
        self.assertEqual(landing.state.companions,landing.source.companions)
        self.assertEqual(landing.state.companions[0].snapshot.state.injury.wounds,1)
        self.assertFalse(any(type(step.proof) is PcFallingProof and step.proof.actor_id=='pc1:mount'
            for step in result.steps))
        with self.assertRaises(ValueError): PcMeleeStep(landing.state,landing.proof)
        state=initial_pc_melee_state(source)
        for step in result.steps: state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_melee_npc_targets_retained_airborne_pegasus_after_rider_falls_out_of_range(self):
        source = airborne_companion_source()
        # C14 excludes the passive body from the fighter count; in round2 the
        # isolated NPC has the scene-approved Outnumbering die against it.
        values = [10]*4 + [1]*6 + [10]*3 + [9,10] + [1]*6 + [10]*4
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        attacked, = tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id == 'pc1:mount')
        proof = attacked.proof
        self.assertEqual(proof.request.actor_id,source.enemy_activation_order[0])
        self.assertTrue(battlefield_is_midair(attacked.source.battlefield,'pc1:mount'))
        self.assertFalse(battlefield_is_midair(attacked.source.battlefield,'pc1'))
        self.assertIsNotNone(proof.execution.resolution.profile_wound)
        self.assertIsNone(proof.execution.resolution.pending_character_wound)
        self.assertIsNone(proof.fate_decline)
        self.assertIsNone(proof.glorious)
        self.assertEqual(attacked.source.party,attacked.state.party)
        self.assertEqual(attacked.source.enemies,attacked.state.enemies)
        self.assertEqual(attacked.state.companions[0].snapshot.state.injury.wounds,1)
        self.assertEqual(tuple(member.actor_id for member in result.state.party),('pc1',))
        self.assertEqual(len(result.state.enemies),1)
        acknowledgement, = tuple(step for step in result.steps if type(step.proof) is PcProfileWoundProof
            and step.source.pending_actor_id == 'pc1:mount')
        self.assertIsNone(acknowledgement.proof.decision)
        self.assertFalse(acknowledgement.state.pending)
        state = initial_pc_melee_state(source)
        for step in result.steps: state = apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        with self.assertRaises(ValueError): PcMeleeStep(attacked.state,proof)
        with self.assertRaises(ValueError): PcMeleeStep(acknowledgement.state,acknowledgement.proof)

    def test_missed_attack_staggers_the_npc_without_spending_the_ground_riders_fate(self):
        source=airborne_companion_source()
        rng=ScriptedD10([10]*4+[1]*6+[10]*3+[9,10]+[10]*6+[1]*4)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        attacked,=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id=='pc1:mount')
        self.assertEqual(attacked.state.pending_actor_id,source.enemy_activation_order[0])
        self.assertEqual(attacked.source.companions,attacked.state.companions)
        self.assertEqual(attacked.source.party,attacked.state.party)
        acknowledgement,=tuple(step for step in result.steps if type(step.proof) is PcAttackerStaggerProof
            and step.source.pending_actor_id==source.enemy_activation_order[0])
        self.assertTrue(acknowledgement.state.enemy(source.enemy_activation_order[0]).state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(acknowledgement.state.pending)
        self.assertEqual(result.state.participant('pc1').fate,source.party[0].fate)
        self.assertEqual(result.state.companions[0].snapshot.state.injury.wounds,0)
        state=initial_pc_melee_state(source)
        for step in result.steps: state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        with self.assertRaises(ValueError): PcMeleeStep(acknowledgement.state,acknowledgement.proof)


if __name__ == '__main__': main()
