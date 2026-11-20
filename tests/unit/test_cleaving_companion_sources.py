"""Prepared Cleaving wave receipts bind companion obligations and defeat.

These isolate source consumers with real Stagger/Wound results. They do not
claim a complete triggering Attack, native battle or automatic talent choice.
"""
from dataclasses import replace
from unittest import TestCase

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.unit.test_companion_landing import context, append, started
from tests.unit.test_companion_departure import view as departure_view
from tests.unit.test_companion_attack_wrappers import PreparedAttackView
from tests.unit.test_m31_pc_goblin_execution import scene as goblin_scene
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
from towr.domain.pc_cleaving_blow_models import (
    CleavingBlowTrigger, PcCleavingStartProof, PcCleavingTargetProof,
    PcCleavingProfileProof, PcCleavingMinionDefeatProof, PcCleavingEndProof,
)
from towr.domain.pc_companion_landing_models import expected_companion_landing, _bound_wound
from towr.domain.pc_companion_departure_models import expected_companion_departure, project_companion_departure
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_minion_defeat_models import validate_pc_minion_defeat_equipment
from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_undead_minion_models import pc_undead_minion_source
from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec
from towr.domain.pc_blunderbuss_models import PcNearbyDecisions
from towr.domain.resolution_models import StaggerImpactRequest, TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    WeaponItemSource, WeaponItemLocation, WeaponGrip, initial_weapon_inventory,
)
from towr.domain.weapon_use_models import WeaponUse
from towr.rules.stagger_impact_resolution import resolve_stagger_impact


def prepared_start(actor, target):
    inventory=initial_weapon_inventory(actor,(WeaponItemSource('axe',WeaponKind.GREATAXE,
        WeaponItemLocation.HELD,WeaponGrip.BOTH),))
    use=WeaponUse(actor,inventory,inventory.items[0].id)
    trigger=CleavingBlowTrigger(0,0,'prepared:weapon-wound',0,actor,'prepared:primary',
        use,paid_talent(TalentId.CLEAVING_BLOW))
    return PcCleavingStartProof(trigger,(target,))


def target_wound(state, target, wave_id, *, policy=TargetInjuryPolicy.BRUTE, minion_defeat=None):
    before=pc_actor_injury(state,target)
    before=replace(before,conditions=before.conditions.with_condition(Condition.STAGGERED))
    request=StaggerImpactRequest(wave_id+':target:'+target,target,policy,before,False,False,
        minion_stagger_defeat=minion_defeat)
    result=resolve_stagger_impact(request,ScriptedD10([]),decisions=PcNearbyDecisions())
    return PcCleavingTargetProof(wave_id,request,result)


class CleavingCompanionSourcesTests(TestCase):
    def test_actual_detached_enemy_body_is_a_close_target_but_same_zone_is_not_enough(self):
        from towr.domain.pc_cleaving_blow_models import cleaving_target_ids
        from towr.domain.pc_battlefield_models import with_actor_placement
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,rider,body=context(npc=npc,detached=True)
                owner='pc1' if npc else 'minion1'
                ground=state.battlefield.spatial.placement_for(rider).zone_id
                for actor in (owner,body):
                    state.battlefield=with_actor_placement(state.battlefield,actor,ground)
                pair=tuple(sorted((owner,body)))
                state.battlefield=replace(state.battlefield,close_pairs=(*state.battlefield.close_pairs,pair))
                trigger=replace(prepared_start(owner,body).trigger,wounded_target_id=rider)
                self.assertEqual(cleaving_target_ids(state,trigger),(body,))
                state.battlefield=replace(state.battlefield,close_pairs=tuple(
                    p for p in state.battlefield.close_pairs if p!=pair))
                self.assertEqual(cleaving_target_ids(state,trigger),())

    def test_actual_wave_w1_retains_pegasus_body_and_next_own_turn(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,rider,body=context(npc=npc,detached=True)
                wave_id='prepared:cleaving'
                producer=target_wound(state,body,wave_id)
                receipt=PcCleavingProfileProof(wave_id,body,producer.result.profile_wound.state_change,None)
                append(state,producer,**pc_actor_npc_update(state,body,injury=producer.result.state))
                append(state,receipt)
                turn=started(state,body,completed=('pc1',rider) if npc else (rider,))
                landing=expected_companion_landing(state)
                self.assertEqual(landing.wound_producer,producer)
                self.assertEqual(landing.wound_receipt,receipt)
                self.assertEqual(landing.turn_start,turn)
                self.assertEqual(landing.actor_id,body)
                self.assertEqual(landing.battlefield.spatial.free_move_used_entity_ids,(body,))
                self.assertIsNone(_bound_wound(replace(receipt,wave_id='other'),producer,body))
                self.assertIsNone(_bound_wound(receipt,replace(producer,wave_id='other'),body))
                self.assertIsNone(_bound_wound(receipt,producer,rider))

    def test_confirmed_cleaving_rider_death_sends_the_living_mount_away_once(self):
        state=departure_view(npc=True)
        rider='minion1'
        start=prepared_start('pc1',rider)
        producer=target_wound(state,rider,start.wave_id,policy=TargetInjuryPolicy.MINION)
        decision=state.source.participant('pc1').defeat_decision(rider)
        receipt=PcCleavingProfileProof(start.wave_id,rider,producer.result.profile_wound.state_change,decision)
        body_before=next(row for row in state.companions if row.rider_id==rider)
        state.history=(*state.history,start,producer,receipt)
        state.enemies=pc_actor_npc_update(state,rider,injury=producer.result.state)['enemies']
        departure=expected_companion_departure(state)
        self.assertEqual(departure.source_proof,receipt)
        self.assertEqual(departure.source_id,start.wave_id+':'+rider+':defeat')
        self.assertEqual(departure.previous,body_before)
        self.assertEqual(departure.state.snapshot.state.injury,body_before.snapshot.state.injury)
        updates=project_companion_departure(state,departure)
        for name,value in updates.items(): setattr(state,name,value)
        state.history=(*state.history,departure)
        self.assertIsNone(expected_companion_departure(state))

    def test_closed_or_mismatched_wave_cannot_confirm_rider_death(self):
        for changed in ('closed','wrong-wave','wrong-target'):
            with self.subTest(changed=changed):
                state=departure_view(npc=True)
                start=prepared_start('pc1','minion1')
                producer=target_wound(state,'minion1',start.wave_id,policy=TargetInjuryPolicy.MINION)
                receipt=PcCleavingProfileProof(start.wave_id,'minion1',producer.result.profile_wound.state_change,
                    state.source.participant('pc1').defeat_decision('minion1'))
                if changed=='wrong-wave': producer=replace(producer,wave_id='other')
                if changed=='wrong-target': producer=replace(producer,request=replace(producer.request,target_id='pc1'))
                prefix=(*state.history,start,producer)
                if changed=='closed': prefix=(*prefix,PcCleavingEndProof(start.wave_id))
                state.history=(*prefix,receipt)
                state.enemies=pc_actor_npc_update(state,'minion1',injury=producer.result.state)['enemies']
                with self.assertRaises(ValueError): expected_companion_departure(state)

    def test_goblin_fleeing_keeps_its_actual_non_wound_cause_and_one_ack(self):
        base=initial_pc_melee_state(goblin_scene(goblins=1,pcs=1))
        state=PreparedAttackView(_base=base,**{name:getattr(base,name) for name in base.__dataclass_fields__})
        target='goblin1'
        producer=target_wound(state,target,'prepared:cleaving',policy=TargetInjuryPolicy.MINION,
            minion_defeat=pc_npc_stagger_defeat_spec(base.enemy(target).definition))
        cause=producer.result.minion_stagger_defeat.cause
        state.history=(producer,)
        state.pending=(cause,)
        state.pending_actor_id=target
        state.enemies=pc_actor_npc_update(state,target,injury=producer.result.state)['enemies']
        validate_pc_minion_defeat_equipment(state)
        acknowledgement=PcCleavingMinionDefeatProof(producer.wave_id,target,cause)
        state.history=(*state.history,acknowledgement)
        state.pending=()
        state.pending_actor_id=None
        state.enemies=tuple(replace(row,state=replace(row.state,wields_weapon=False,available_attack_ids=()))
            if row.state.actor_id==target else row for row in state.enemies)
        validate_pc_minion_defeat_equipment(state)
        for malformed in ((replace(acknowledgement,wave_id='other'),),
                (acknowledgement,acknowledgement)):
            state.history=(producer,*malformed)
            with self.assertRaises(ValueError): validate_pc_minion_defeat_equipment(state)

    def test_actual_undead_companion_packet_keeps_destruction_separate_from_wound(self):
        for target in ('pc1:mount','minion1:mount'):
            with self.subTest(target=target):
                base=initial_pc_melee_state(mount_source(CombatMount.SKELETAL_STEED))
                state=PreparedAttackView(_base=base,
                    **{name:getattr(base,name) for name in base.__dataclass_fields__})
                undead=pc_undead_minion_source(state,target)
                producer=target_wound(state,target,'prepared:cleaving',policy=TargetInjuryPolicy.MINION,
                    minion_defeat=undead_minion_stagger_defeat_spec(undead,target))
                self.assertIsNone(producer.result.profile_wound)
                cause=producer.result.minion_stagger_defeat.cause
                state.history=(producer,)
                state.pending=producer.result.follow_ups
                state.pending_actor_id=target
                state.companions=pc_actor_npc_update(state,target,injury=producer.result.state)['companions']
                validate_pc_minion_defeat_equipment(state)
                acknowledgement=PcCleavingMinionDefeatProof(producer.wave_id,target,cause)
                state.history=(*state.history,acknowledgement)
                state.pending=()
                state.pending_actor_id=None
                validate_pc_minion_defeat_equipment(state)
                state.history=(*state.history,acknowledgement)
                with self.assertRaises(ValueError): validate_pc_minion_defeat_equipment(state)
