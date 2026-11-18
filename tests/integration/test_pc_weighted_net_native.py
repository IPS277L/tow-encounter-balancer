"""Physical Net identities, paid/free pickup and one-binding Brawn recovery."""
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.pc_magic_scenarios import magic_scenario
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedRangedFacts
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_melee_models import (
    PcMeleeWeapon,PcTwoHandedGrip,PcRangedProfile,PcFatePolicy,PcGloriousPolicy,
)
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state,PcMeleeStep,PcHandDropProof
from towr.domain.pc_mount_models import CombatMount,PcDismountProof,HORSE_NOBLE_STEED_RULE_ID
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_weighted_net_models import (
    PcNetLocation,PcNetReleaseProof,PcNetPickupProof,PcNetIncidentalPickupProof,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R,RangedWeaponHands
from towr.domain.recover_models import RecoverMode
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class Dice:
    def __init__(self,values=(),*,default=1):
        self.values=tuple(values);self.default=default;self.index=0
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('literal Net battle uses d10 only')
        value=self.values[self.index] if self.index<len(self.values) else self.default
        self.index+=1
        return value


def npc(weapon=GeneratedWeapon.STAFF,*,mount=None):
    if weapon is GeneratedWeapon.WEIGHTED_NET:
        return GeneratedNpc(3,3,20,2,3,3,weapon,False,defence=3,shield=False,
            brawn=3,ballistic_skill=3,throwing=4,mount=mount)
    ranged=(GeneratedRangedFacts(4,5,2,4,True,True,None,None,awareness=4)
        if weapon is GeneratedWeapon.LONGBOW else None)
    return GeneratedNpc(2,2,4,2,3,3,weapon,False,defence=3,shield=False,
        brawn=3,ranged=ranged,mount=mount,
        weapon_grip=RangedWeaponHands.TWO_HANDED if weapon is GeneratedWeapon.FOOT_SPEAR else None)


def pc_net_scene(*,rounds=3,enemy_weapon=GeneratedWeapon.STAFF,mounted=False):
    source=automatic_source(pc_count=1,rounds=rounds)
    mount=CombatMount.HORSE if mounted else None
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.WEIGHTED_NET,
        ballistic_skill=3,throwing=4,brawn=4),initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('net',PcMeleeWeapon.WEIGHTED_NET,
            PcItemLocation.HELD,PcTwoHandedGrip.BOTH),),mount=mount)
    enemy=npc(enemy_weapon,mount=mount)
    if mounted:
        enemy=replace(enemy,toughness=20)
    distance=R.MEDIUM if mounted else R.SHORT
    return replace(source,party=(member,),enemies=(enemy.participant('minion1'),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(enemy,'minion1'),) if enemy.ranged else (),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True,unmounted=not mounted),
        battlefield=PcBattlefieldSpec(distance,R.LONG))


def two_bindings_scene():
    source=automatic_source(pc_count=1,enemy_count=3,rounds=2)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SHORTBOW,
        weapon_skill=1,agility=1,athletics=2,toughness=20,brawn=4,
        ranged=PcRangedProfile(1,2,initiative=2,awareness=3,ammunition_supply_confirmed=True)),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('bow',PcMeleeWeapon.SHORTBOW,PcItemLocation.HELD,PcTwoHandedGrip.BOTH),),
        fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.BRAWN,),0,0))
    weak=GeneratedNpc(1,30,20,1,3,3,GeneratedWeapon.STAFF,False,defence=3,shield=False,brawn=3)
    enemies=(npc(GeneratedWeapon.WEIGHTED_NET),npc(GeneratedWeapon.WEIGHTED_NET),weak)
    return replace(source,party=(member,),enemies=tuple(item.participant(actor)
        for item,actor in zip(enemies,source.enemy_activation_order)),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(R.SHORT,R.LONG))


class PhysicalNetNativeTests(unittest.TestCase):
    def execute(self,source,dice=None):
        result=run_pc_melee_scenario(source,dice or Dice())
        self.assertIsNone(result.unsupported)
        state=initial_pc_melee_state(source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        return result

    def test_same_uid_is_released_picked_up_with_recover_then_thrown_again(self):
        result=self.execute(pc_net_scene())
        shots=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.weighted_net_landing is not None]
        self.assertEqual(len(shots),2)
        self.assertEqual({step.proof.weighted_net_landing.item_id for step in shots},{'pc1:weapon:net'})
        release,=[step for step in result.steps if type(step.proof) is PcNetReleaseProof]
        pickup,=[step for step in result.steps if type(step.proof) is PcNetPickupProof]
        self.assertEqual(release.proof.request.mode,RecoverMode.REMOVE_CONDITION)
        self.assertEqual(release.proof.item.location,PcNetLocation.FREE)
        self.assertTrue(pickup.proof.request.actor_has_enemy_in_zone)
        self.assertEqual(pickup.proof.item.location,PcNetLocation.HELD)
        self.assertTrue(pickup.proof.result.slot.executed)
        self.assertEqual(result.executed_actions,6)
        self.assertEqual(len(result.state.weighted_nets),1)
        self.assertEqual(result.state.weighted_nets[0].location,PcNetLocation.BOUND)
        with self.assertRaises(ValueError):
            PcMeleeStep(pickup.state,pickup.proof)

    def test_missed_net_stays_on_ground_and_nearby_enemy_requires_paid_pickup(self):
        result=self.execute(pc_net_scene(rounds=2,enemy_weapon=GeneratedWeapon.FOOT_SPEAR),Dice(default=10))
        shot=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.weighted_net_landing is not None)
        landing=shot.proof.weighted_net_landing
        self.assertEqual(landing.item.location,PcNetLocation.FREE)
        self.assertEqual(landing.item.ground.zone_id,
            shot.source.battlefield.spatial.placement_for('minion1').zone_id)
        pickup,=[step for step in result.steps if type(step.proof) is PcNetPickupProof]
        self.assertTrue(pickup.proof.request.actor_has_enemy_in_zone)
        self.assertFalse(any(type(step.proof) is PcNetIncidentalPickupProof for step in result.steps))
        self.assertEqual(result.state.weighted_nets[0].location,PcNetLocation.HELD)
        self.assertEqual(result.executed_actions,4)
        self.assertFalse(any(placement.entity_id==landing.item.marker_id
            for placement in result.state.battlefield.spatial.placements))

    def test_enemy_movement_leaves_marker_static_and_allows_incidental_pickup(self):
        result=self.execute(pc_net_scene(rounds=2,enemy_weapon=GeneratedWeapon.LONGBOW),Dice(default=10))
        pickup,=[step for step in result.steps if type(step.proof) is PcNetIncidentalPickupProof]
        self.assertNotEqual(pickup.source.battlefield.spatial.placement_for('minion1').zone_id,
            pickup.proof.previous_item.ground.zone_id)
        self.assertEqual(pickup.source.round_state,pickup.state.round_state)
        self.assertEqual(pickup.proof.item_id,'pc1:weapon:net')
        self.assertEqual(result.executed_actions,4)

    def test_one_successful_brawn_recover_releases_one_binding_and_preserves_other(self):
        # The real first Wound8 drops the bow before turn2. With no held
        # weapon, retreat cannot invent a shot; this is a legal Brawn choice.
        result=self.execute(two_bindings_scene(),Dice([1]*14+[8,1]+[10]*3+[1]*3))
        release,=[step for step in result.steps if type(step.proof) is PcNetReleaseProof
            and step.proof.request.actor_id=='pc1']
        self.assertIsNotNone(release.proof.glorious)
        self.assertEqual(release.proof.result.resolution.test_result.successes,3)
        self.assertEqual(len(release.source.participant('pc1').net_condition_sources),2)
        self.assertEqual(len(release.state.participant('pc1').net_condition_sources),1)
        self.assertTrue(release.state.participant('pc1').injury.conditions.has(Condition.BURDENED))
        self.assertEqual(release.state.participant('pc1').injury.wounds,
            release.source.participant('pc1').injury.wounds)
        self.assertEqual(sum(item.location is PcNetLocation.BOUND for item in release.state.weighted_nets),1)
        self.assertEqual(len(release.state.participant('pc1').fate.spends),1)

    def test_real_wound_drop_keeps_same_net_uid_and_requires_typed_spatial_receipt(self):
        source=magic_scenario(reason=3,willpower=4,level=1,rounds=1,enemies=1)
        member=source.party[0]
        member=replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.WEIGHTED_NET,
            ballistic_skill=1,throwing=2,brawn=4),initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=(PcWeaponItem('net',PcMeleeWeapon.WEIGHTED_NET,
                PcItemLocation.HELD,PcTwoHandedGrip.BOTH),))
        opponent=GeneratedNpc(1,30,100,1,3,3,GeneratedWeapon.STAFF,False,
            defence=3,shield=False,brawn=3)
        source=replace(source,party=(member,),enemies=(opponent.participant('minion1'),),
            facts=replace(source.facts,can_leave_zone=True),battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG))
        dice=Dice([1]*5+[8,1])
        result=self.execute(source,dice)
        self.assertEqual(dice.index,7)
        drop,=[step for step in result.steps if type(step.proof) is PcHandDropProof]
        receipt,=drop.proof.weighted_net_drops
        self.assertEqual(receipt.item_id,'pc1:weapon:net')
        self.assertEqual(receipt.previous_item.location,PcNetLocation.HELD)
        self.assertEqual(receipt.item.location,PcNetLocation.FREE)
        self.assertEqual(receipt.previous,drop.source.battlefield)
        self.assertEqual(receipt.state,drop.state.battlefield)
        self.assertIsNone(drop.state.participant('pc1').weapon_hand)
        self.assertEqual(drop.state.participant('pc1').weapon_inventory.items[0].location,PcItemLocation.DEPLOYED)
        with self.assertRaises(ValueError):
            PcMeleeStep(drop.source,replace(drop.proof,weighted_net_drops=()))

    def test_none_scene_unarmed_npc_waits_without_restoring_a_bound_net(self):
        source=automatic_source(pc_count=1,rounds=2)
        member=replace(source.party[0],pc=replace(source.party[0].pc,weapon_skill=1,melee=2,brawn=4))
        source=replace(source,party=(member,),enemies=(npc(GeneratedWeapon.WEIGHTED_NET).participant('minion1'),))
        result=self.execute(source)
        self.assertEqual(result.state.weighted_nets[0].location,PcNetLocation.BOUND)
        self.assertFalse(result.state.enemy('minion1').state.wields_weapon)
        self.assertEqual(result.executed_actions,4)
        trial=run_pc_melee_trial(PcMeleeSimulationRequest(source,42,1),0,rng_factory=lambda _:Dice())
        self.assertEqual(trial.npc_recover_action_counts[0].count,1)

    def test_horse_net_charge_applies_prone_then_burdened_without_damage(self):
        result=self.execute(pc_net_scene(rounds=1,mounted=True))
        shot=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.weighted_net_landing is not None)
        outcome=shot.proof.execution.resolution
        self.assertIsNone(outcome.attack.damage)
        self.assertIsNone(outcome.stagger)
        self.assertEqual(outcome.applied_secondary_rule_ids,(HORSE_NOBLE_STEED_RULE_ID,))
        self.assertTrue(outcome.target_state.conditions.has(Condition.PRONE))
        self.assertTrue(outcome.target_state.conditions.has(Condition.BURDENED))
        dismount,=[step for step in result.steps if type(step.proof) is PcDismountProof]
        self.assertEqual(dismount.proof.actor_id,'minion1')
        self.assertEqual(result.state.weighted_nets[0].location,PcNetLocation.BOUND)


if __name__=='__main__':
    unittest.main()
