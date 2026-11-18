"""Actual free movement keeps two-handed shooting/reload available after Close."""
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source,tactical_snapshot
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedRangedFacts
from towr.domain.pc_battlefield_models import PcBattlefieldSpec,battlefield_range
from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof,expected_pc_battlefield_move
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_melee_models import PcMeleeWeapon,PcRangedProfile,PcRangedReloadHandPolicy,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class Ones:
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('literal retreat battle uses d10 only')
        return 1


def player_source():
    source=automatic_source(pc_count=1,rounds=3)
    ranged=PcRangedProfile(3,4,initiative=3,dexterity=4,ammunition_supply_confirmed=True,
        initially_loaded=True,reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS,awareness=4)
    member=replace(source.party[0],pc=replace(source.party[0].pc,
        weapon=PcMeleeWeapon.CROSSBOW,ranged=ranged,toughness=20),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('bow',PcMeleeWeapon.CROSSBOW,PcItemLocation.HELD,PcTwoHandedGrip.BOTH),))
    npc=GeneratedNpc(1,1,20,1,2,2,GeneratedWeapon.STAFF,False,defence=2,shield=False,brawn=3)
    return replace(source,party=(member,),enemies=(npc.participant('minion1'),),
        facts=replace(source.facts,can_leave_zone=True),battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG))


class TwoHandedRetreatTests(unittest.TestCase):
    def execute(self,source):
        result=run_pc_melee_scenario(source,Ones())
        self.assertIsNone(result.unsupported)
        current=initial_pc_melee_state(source)
        for step in result.steps:
            current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def assert_actual_retreats(self,result,actor):
        moves=[step for step in result.steps if type(step.proof) is PcBattlefieldMoveProof
            and step.proof.actor_id==actor]
        self.assertGreaterEqual(len(moves),2)
        self.assertEqual(len({step.proof.source_round.round_number for step in moves}),len(moves))
        for step in moves:
            self.assertIsNotNone(step.proof.movement_request)
            self.assertEqual(battlefield_range(step.proof.previous,actor,step.proof.target_id),R.CLOSE)
            self.assertEqual(battlefield_range(step.proof.state,actor,step.proof.target_id),R.MEDIUM)
            self.assertIn(actor,step.proof.state.spatial.free_move_used_entity_ids)

    def test_pc_retreats_shoots_reloads_and_shoots_again_after_being_charged(self):
        result=self.execute(player_source())
        shots=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1' and step.proof.ranged_shot is not None]
        self.assertEqual(len(shots),2)
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcRangedReloadProof]),1)
        self.assert_actual_retreats(result,'pc1')

    def test_npc_retreats_shoots_reloads_and_shoots_again_after_being_charged(self):
        source=automatic_source(pc_count=1,rounds=3)
        pc=replace(source.party[0],pc=replace(source.party[0].pc,
            weapon=PcMeleeWeapon.FOOT_SPEAR,weapon_skill=1,melee=2,toughness=20),
            initial_weapon_hand=PcTwoHandedGrip.BOTH)
        npc=GeneratedNpc(3,3,20,2,3,3,GeneratedWeapon.CROSSBOW,False,defence=3,shield=False,
            ranged=GeneratedRangedFacts(3,4,3,4,True,True,None,None,awareness=4),brawn=3)
        source=replace(source,party=(pc,),enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),),
            facts=replace(source.facts,can_leave_zone=True),battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG))
        result=self.execute(source)
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.npc_ranged_shot is not None]),2)
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcNpcRangedReloadProof]),1)
        self.assert_actual_retreats(result,'minion1')

    def test_prone_defenceless_and_unheld_weapon_do_not_gain_free_retreat(self):
        state=tactical_snapshot(player_source())
        member=state.participant('pc1')
        for condition in (Condition.PRONE,Condition.DEFENCELESS):
            snapshot=replace(state,party=(replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(condition))),))
            self.assertIsNone(expected_pc_battlefield_move(snapshot))
        dropped=replace(member.weapon_inventory.items[0],location=PcItemLocation.DROPPED,hand=None)
        snapshot=replace(state,party=(replace(member,weapon_hand=None,
            weapon_inventory=replace(member.weapon_inventory,items=(dropped,))),))
        self.assertIsNone(expected_pc_battlefield_move(snapshot))
        burdened=replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.BURDENED))),))
        self.assertIsNotNone(expected_pc_battlefield_move(burdened))

    def test_explicit_short_maximum_uses_real_within_zone_separation(self):
        source=player_source()
        source=replace(source,battlefield=PcBattlefieldSpec(R.CLOSE,R.SHORT))
        proof=expected_pc_battlefield_move(tactical_snapshot(source))
        self.assertIsNone(proof.movement_request)
        self.assertIsNone(proof.movement_result)
        self.assertEqual(proof.state.spatial,proof.previous.spatial)
        self.assertEqual(battlefield_range(proof.state,'pc1','minion1'),R.SHORT)


if __name__=='__main__':
    unittest.main()
