"""Falling preparation/outcome snapshots; native journal coverage is separate."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.armour_models import ArmourLoadout,BodyArmour,body_resilience_bonus
from towr.domain.armour_models import ITHILMAR_ENVIRONMENT_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_battlefield_models import PcAirspaceSpec,PcBattlefieldSpec,with_actor_placement,battlefield_is_midair
from towr.domain.pc_falling_models import (
    expected_pc_falling_request,falling_hazard_request,project_pc_falling_step,
    PcFallingProof,prepare_hazard_avoidance,falling_npc_disposition,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcFateDecline
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_mount_models import CombatMount,RiderKind,PcDismountProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import HazardExposureRequest
from towr.domain.test_models import Skill
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.test_resolution import resolve_test


def view(*,npc=False,body=BodyArmour.HEAVY):
    source=make_pc_melee_scenario()
    loadout=ArmourLoadout((body,),body)
    member=source.party[0]
    member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN,
        armour=loadout,armour_worn=True,pc=replace(member.pc,armour_bonus=body_resilience_bonus(loadout)))
    enemies=source.enemies
    if npc:
        enemy=GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),loadout,defence=4,
            mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN).participant('minion1')
        enemies=(enemy,)
    source=replace(source,party=(member,),enemies=enemies,
        facts=replace(source.facts,unmounted=False,all_opponents_close=False,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG,airspace=PcAirspaceSpec()))
    base=initial_pc_melee_state(source)
    actor='minion1' if npc else 'pc'
    parties={item.actor_id:item for item in base.party}
    opposition={item.state.actor_id:item for item in base.enemies}
    injury=opposition[actor].state.injury if npc else parties[actor].injury
    injury=replace(injury,conditions=injury.conditions.with_condition(Condition.PRONE))
    if npc:opposition[actor]=replace(opposition[actor],state=replace(opposition[actor].state,injury=injury))
    else:parties[actor]=replace(parties[actor],injury=injury)
    before=next(item for item in base.mounts if item.actor_id==actor)
    after=replace(before,mounted=False)
    dismount=PcDismountProof(actor,source.id+':dismount:0:'+actor,0,before,after,injury)
    spatial=with_actor_placement(base.battlefield,actor,base.battlefield.air_to_ground[3][0])
    return SimpleNamespace(source=source,party=tuple(parties.values()),enemies=tuple(opposition.values()),
        participant=parties.__getitem__,enemy=opposition.__getitem__,history=(dismount,),
        battlefield=spatial,mounts=tuple(after if item.actor_id==actor else item for item in base.mounts),
        companions=base.companions,oaths=base.oaths,
        pending=(),pending_wound=None,magic_pending=None,magic_modifiers=(),round_state=base.round_state)


class FallingTests(unittest.TestCase):
    def test_actual_athletics_uses_armour_and_lands_directly_below(self):
        state=view()
        request=expected_pc_falling_request(state)
        self.assertEqual(sum(item.amount for item in request.avoidance_test.dice_modifiers),-1)
        self.assertTrue(battlefield_is_midair(state.battlefield,'pc'))
        self.assertFalse(battlefield_is_midair(request.battlefield,'pc'))
        rng=ScriptedD10([1,1])
        test=resolve_test(request.avoidance_test,rng)
        result=resolve_hazard(falling_hazard_request(request,test),rng)
        rng.assert_exhausted()
        decline=PcFateDecline('pc',request.avoidance_test.id,'test',state.source.party[0].fate_policy)
        updates=project_pc_falling_step(state,PcFallingProof(request,test,result,decline))
        self.assertEqual(updates['battlefield'],request.battlefield)
        self.assertTrue(result.avoided)
        self.assertIsNone(updates['pending_wound'])
        self.assertEqual(updates['party'][0].injury.wounds,())

    def test_failed_pc_hazard_keeps_real_shortfall_and_wound_lifecycle(self):
        state=view()
        request=expected_pc_falling_request(state)
        rng=ScriptedD10([10,10,1,1])
        test=resolve_test(request.avoidance_test,rng)
        result=resolve_hazard(falling_hazard_request(request,test),rng)
        rng.assert_exhausted()
        decline=PcFateDecline('pc',request.avoidance_test.id,'test',state.source.party[0].fate_policy)
        updates=project_pc_falling_step(state,PcFallingProof(request,test,result,decline))
        self.assertEqual(result.shortfall,2)
        self.assertEqual(updates['pending_wound'].source_request.wound.base_dice,2)
        self.assertEqual(updates['pending_actor_id'],'pc')
        forged=replace(result,rating=1)
        with self.assertRaises(ValueError):
            project_pc_falling_step(state,PcFallingProof(request,test,forged,decline))

    def test_npc_falling_has_no_fate_and_keeps_gm_defeat_disposition(self):
        state=view(npc=True)
        request=expected_pc_falling_request(state)
        rng=ScriptedD10([10,10])
        test=resolve_test(request.avoidance_test,rng)
        result=resolve_hazard(falling_hazard_request(request,test),rng)
        rng.assert_exhausted()
        disposition=falling_npc_disposition(state.source,'minion1')
        proof=PcFallingProof(request,test,result,npc_disposition=disposition)
        updates=project_pc_falling_step(state,proof)
        self.assertTrue(updates['enemies'][0].state.injury.defeated)
        self.assertNotIn('party',updates)
        with self.assertRaises(ValueError):
            project_pc_falling_step(state,replace(proof,npc_disposition=None))

    def test_environmental_context_applies_ithilmar_once_for_both_sides(self):
        state=view(npc=True,body=BodyArmour.ITHILMAR)
        for actor in ('pc','minion1'):
            exposure=HazardExposureRequest('environment:'+actor,'environment:'+actor+':test',
                1,Skill.ATHLETICS,'authored:environment',False,(Condition.DRAINED,))
            ordinary=prepare_hazard_avoidance(state,actor,exposure)
            environmental=prepare_hazard_avoidance(state,actor,exposure,environmental=True)
            self.assertEqual(sum(item.amount for item in environmental.dice_modifiers)
                -sum(item.amount for item in ordinary.dice_modifiers),1)
            rng=ScriptedD10([1,1,1,1])
            result=resolve_test(environmental,rng)
            rng.assert_exhausted()
            self.assertEqual(result.trace.rolled_dice,4)

    def test_actual_falling_mantle_bonus_is_suppressed_by_drained_for_both_sides(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                state=view(npc=npc,body=BodyArmour.ITHILMAR)
                actor='minion1' if npc else 'pc'
                ready=expected_pc_falling_request(state)
                self.assertEqual(tuple(mod.amount for mod in ready.avoidance_test.dice_modifiers
                    if mod.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID),(1,))
                if npc:
                    enemy=state.enemy(actor)
                    changed=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                        conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
                    state.enemies=tuple(changed if item.state.actor_id==actor else item for item in state.enemies)
                    state.enemy=lambda identifier:next(item for item in state.enemies if item.state.actor_id==identifier)
                else:
                    member=state.participant(actor)
                    changed=replace(member,injury=replace(member.injury,
                        conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
                    state.party=tuple(changed if item.actor_id==actor else item for item in state.party)
                    state.participant=lambda identifier:next(item for item in state.party if item.actor_id==identifier)
                request=expected_pc_falling_request(state)
                self.assertFalse(any(mod.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID
                    for mod in request.avoidance_test.dice_modifiers))


if __name__=='__main__':unittest.main()
