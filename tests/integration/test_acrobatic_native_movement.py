"""Actual PC/NPC Give Ground paths under the explicit narrow-passage scene."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_give_ground_models import PcGiveGroundProof
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import PcMeleeStep,initial_pc_melee_state
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.spatial_resolution import resolve_give_ground


class Ones:
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('native movement uses d10 only')
        return 1


def source(*,pc_target=False,acrobatic=True,blocked=True):
    battle=make_pc_melee_scenario(max_rounds=1 if pc_target else 2)
    row=battle.party[0]
    row=replace(row,pc=replace(row.pc,weapon_skill=1 if pc_target else 6,
        strength=3,toughness=20,agility=4,melee=2,defence=2),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        talents=(paid_talent(TalentId.ACROBATIC),) if pc_target and acrobatic else ())
    npc=GeneratedNpc(6 if pc_target else 1,3,20,4,6 if pc_target else 2,4,
        initial_generated_weapons(GeneratedWeapon.STAFF),ArmourLoadout(),defence=4,
        talents=(paid_talent(TalentId.ACROBATIC),) if not pc_target and acrobatic else ())
    return replace(battle,party=(row,),enemies=(npc.participant('minion1'),),
        battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG,enemy_zone_blocking=blocked),
        facts=replace(battle.facts,outnumbering_bonus_approved=False,can_leave_zone=True))


def execute(battle):
    result=run_pc_melee_scenario(battle,Ones())
    replay=initial_pc_melee_state(battle)
    for step in result.steps:replay=apply_pc_melee_step(replay,step)
    if replay!=result.state:raise AssertionError('native movement replay changed')
    return result


class AcrobaticNativeMovementTests(unittest.TestCase):
    def test_pc_give_ground_crosses_actual_enemy_without_erasing_the_snapshot(self):
        result=execute(source(pc_target=True))
        step,=tuple(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        self.assertEqual(step.proof.request.mover_id,'pc')
        self.assertEqual(step.proof.request.path_entity_ids,('minion1',))
        self.assertEqual(step.proof.request.acrobatic.actor_id,'pc')
        self.assertIn('minion1',tuple(p.entity_id for p in step.proof.request.state.placements))
        with self.assertRaises(ValueError):resolve_give_ground(replace(step.proof.request,acrobatic=None))
        forged=replace(step.proof.request,path_entity_ids=())
        proof=replace(step.proof,request=forged,result=resolve_give_ground(forged))
        with self.assertRaises(ValueError):PcMeleeStep(step.source,proof)

    def test_generated_npc_uses_its_own_talent_and_the_real_attacking_pc_path(self):
        result=execute(source())
        step,=tuple(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        self.assertEqual(step.proof.request.mover_id,'minion1')
        self.assertEqual(step.proof.request.path_entity_ids,('pc',))
        self.assertEqual(step.proof.request.acrobatic.actor_id,'minion1')
        self.assertTrue(step.proof.result.state.gave_ground_entity_ids)

    def test_same_live_blocker_prevents_npc_give_ground_without_acrobatic(self):
        result=execute(source(acrobatic=False))
        self.assertFalse(any(type(step.proof) is PcGiveGroundProof for step in result.steps))

    def test_pc_can_really_give_ground_into_midair_from_a_ground_enemy_close(self):
        from towr.domain.pc_battlefield_models import PcAirspaceSpec,battlefield_is_midair
        from towr.domain.pc_mount_models import CombatMount,RiderKind
        battle=source(pc_target=True)
        row=replace(battle.party[0],mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
        battle=replace(battle,party=(row,),facts=replace(battle.facts,unmounted=False),
            battlefield=replace(battle.battlefield,airspace=PcAirspaceSpec()))
        result=execute(battle)
        step,=tuple(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        self.assertTrue(battlefield_is_midair(step.state.battlefield,'pc'))
        self.assertEqual(step.proof.request.path_entity_ids,('minion1',))
        self.assertEqual(step.proof.request.acrobatic.actor_id,'pc')

    def test_npc_can_really_give_ground_into_midair_with_its_own_source(self):
        from towr.domain.pc_battlefield_models import PcAirspaceSpec,battlefield_is_midair
        from towr.domain.pc_mount_models import CombatMount,RiderKind
        battle=source()
        npc=replace(battle.enemies[0].definition.generated_components,
            mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN)
        battle=replace(battle,enemies=(npc.participant('minion1'),),
            facts=replace(battle.facts,unmounted=False),
            battlefield=replace(battle.battlefield,airspace=PcAirspaceSpec()))
        result=execute(battle)
        step,=tuple(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        self.assertTrue(battlefield_is_midair(step.state.battlefield,'minion1'))
        self.assertEqual(step.proof.request.path_entity_ids,('pc',))
        self.assertEqual(step.proof.request.acrobatic.actor_id,'minion1')

    def test_default_scene_does_not_invent_blockers_from_close_alone(self):
        result=execute(source(acrobatic=False,blocked=False))
        step,=tuple(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        self.assertEqual(step.proof.request.path_entity_ids,())
        self.assertIsNone(step.proof.request.acrobatic)


if __name__=='__main__':unittest.main()
