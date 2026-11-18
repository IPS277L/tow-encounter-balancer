"""Actual Close discovery and complete ordered Blunderbuss friendly fire."""
from dataclasses import replace
import unittest

from tests.support.pc_blunderbuss_scenarios import blunderbuss_profile
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedRangedFacts,GeneratedWeapon
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_blunderbuss_models import (
    PcBattlefieldNearbySource,PcBlunderbussTargetProof,PcBlunderbussProfileProof,PcBlunderbussEndProof,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy,PcMeleeWeapon,PcNearMissPolicy,PcTwoHandedGrip,
    PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeStep,PcWoundCompletionProof,initial_pc_melee_state,
)
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


class FirstMissesThenOnes:
    def __init__(self,count=0):
        self.count=count
        self.index=0
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('literal combat uses d10 only')
        self.index+=1
        return 10 if self.index<=self.count else 1


def component(weapon):
    ranged=(GeneratedRangedFacts(4,5,2,4,True,True,True,True,awareness=4)
        if weapon is GeneratedWeapon.BLUNDERBUSS else None)
    return GeneratedNpc(1 if weapon is GeneratedWeapon.FLAIL else 3,3,4,2,4,3,weapon,False,
        defence=4,shield=False,ranged=ranged)


def scene(*,npc_weapons=(GeneratedWeapon.BLUNDERBUSS,GeneratedWeapon.BLUNDERBUSS),
          pc_shooters=False,near_miss=False):
    source=automatic_source(pc_count=2,enemy_count=len(npc_weapons),rounds=1)
    party=tuple(replace(member,pc=replace(member.pc,
        weapon=PcMeleeWeapon.BLUNDERBUSS if pc_shooters else PcMeleeWeapon.FOOT_SPEAR,
        ranged=blunderbuss_profile(ballistic_skill=4,shooting=5) if pc_shooters else None),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem(member.actor_id+':held',PcMeleeWeapon.BLUNDERBUSS,
            PcItemLocation.HELD,PcTwoHandedGrip.BOTH),) if pc_shooters else None) for member in source.party)
    if near_miss:
        party=(party[0],replace(party[1],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1,0)))
    npcs=tuple(component(weapon) for weapon in npc_weapons)
    return replace(source,party=party,
        enemies=tuple(npc.participant(actor) for npc,actor in zip(npcs,source.enemy_activation_order)),
        npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
            for npc,actor in zip(npcs,source.enemy_activation_order) if npc.ranged is not None),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG))


class BattlefieldBlunderbussTests(unittest.TestCase):
    def execute(self,source,misses=0):
        result=run_pc_melee_scenario(source,FirstMissesThenOnes(misses))
        self.assertIsNone(result.unsupported)
        state=initial_pc_melee_state(source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        return result

    def test_npc_shots_stagger_then_wound_other_pc_with_full_lifecycle(self):
        result=self.execute(scene(),misses=12)
        targets=[step for step in result.steps if type(step.proof) is PcBlunderbussTargetProof]
        self.assertEqual([step.proof.request.target_id for step in targets],['pc2','pc2'])
        first,second=targets
        self.assertTrue(first.state.participant('pc2').injury.conditions.has(Condition.STAGGERED))
        self.assertIsNotNone(second.state.pending_wound)
        completion=next(step for step in result.steps[result.steps.index(second)+1:]
            if type(step.proof) is PcWoundCompletionProof)
        self.assertEqual(completion.source.pending_actor_id,'pc2')
        self.assertEqual(len(completion.state.participant('pc2').injury.wounds),1)
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcBlunderbussEndProof]),2)
        shots=[step for step in result.steps if type(step.proof) is PcAttackProof and step.proof.npc_ranged_shot]
        self.assertEqual([step.proof.request.actor_id for step in shots],['minion1','minion2'])
        self.assertTrue(all(type(step.proof.nearby_snapshot.cluster) is PcBattlefieldNearbySource for step in shots))
        with self.assertRaises(ValueError):
            PcMeleeStep(second.state,first.proof)

    def test_explicit_scene_maximum_and_printed_medium_maximum_are_both_binding(self):
        source=scene(npc_weapons=(GeneratedWeapon.BLUNDERBUSS,))
        source=replace(source,battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.SHORT))
        self.assertFalse(pc_battlefield_attack_available(initial_pc_melee_state(source),'minion1','pc1'))
        source=replace(source,battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))
        self.assertTrue(pc_battlefield_attack_available(initial_pc_melee_state(source),'minion1','pc1'))
        source=replace(source,battlefield=PcBattlefieldSpec(RangedWeaponRange.LONG,RangedWeaponRange.LONG))
        self.assertFalse(pc_battlefield_attack_available(initial_pc_melee_state(source),'minion1','pc1'))

    def test_npc_friendly_profile_defeat_does_not_invent_gm_disposition(self):
        source=scene(npc_weapons=(GeneratedWeapon.FLAIL,GeneratedWeapon.BLUNDERBUSS))
        result=self.execute(source,misses=10)
        ack,=[step for step in result.steps if type(step.proof) is PcBlunderbussProfileProof]
        self.assertEqual(ack.proof.target_id,'minion1')
        self.assertIsNone(ack.proof.decision)
        self.assertTrue(ack.proof.source.defeated)
        self.assertTrue(ack.state.enemy('minion1').state.injury.defeated)
        self.assertEqual(ack.state.enemy('minion1').state.injury.wounds,1)

    def test_near_miss_finishes_before_next_wave_target_or_end(self):
        result=self.execute(scene(near_miss=True),misses=12)
        target=next(step for step in result.steps if type(step.proof) is PcBlunderbussTargetProof
            and step.state.pending_wound is not None)
        completion=next(step for step in result.steps[result.steps.index(target)+1:]
            if type(step.proof) is PcWoundCompletionProof)
        self.assertIsNotNone(completion.proof.completion.fate_burn)
        self.assertEqual(len(result.state.participant('pc2').injury.wounds),0)
        self.assertEqual(result.state.participant('pc2').fate.rating,2)
        end=next(step for step in result.steps[result.steps.index(completion)+1:]
            if type(step.proof) is PcBlunderbussEndProof)
        with self.assertRaises(ValueError):
            PcMeleeStep(target.state,end.proof)

    def test_pc_source_keeps_typed_gm_disposition_for_nearby_defeat(self):
        source=scene(npc_weapons=(GeneratedWeapon.STAFF,)*3,pc_shooters=True)
        result=self.execute(source)
        ack,=[step for step in result.steps if type(step.proof) is PcBlunderbussProfileProof]
        self.assertEqual(ack.proof.target_id,'minion3')
        self.assertEqual(ack.proof.decision,source.participant('pc2').defeat_decision('minion3'))
        self.assertTrue(result.state.enemy('minion3').state.injury.defeated)

    def test_pc_shot_includes_an_allied_pc_actually_close_to_primary(self):
        source=scene(npc_weapons=(GeneratedWeapon.STAFF,)*3,pc_shooters=True)
        first=replace(source.party[0],pc=replace(source.party[0].pc,
            weapon=PcMeleeWeapon.SWORD,ranged=None),initial_weapon_hand=PcWeaponHand.LEFT,
            combat_equipment=None)
        source=replace(source,party=(first,source.party[1]))
        result=self.execute(source,misses=7)
        target=next(step for step in result.steps if type(step.proof) is PcBlunderbussTargetProof
            and step.proof.request.target_id=='pc1')
        self.assertIsNotNone(target.state.pending_wound)
        completion=next(step for step in result.steps[result.steps.index(target)+1:]
            if type(step.proof) is PcWoundCompletionProof)
        self.assertEqual(completion.source.pending_actor_id,'pc1')
        self.assertEqual(len(completion.state.participant('pc1').injury.wounds),1)


if __name__=='__main__':
    unittest.main()
