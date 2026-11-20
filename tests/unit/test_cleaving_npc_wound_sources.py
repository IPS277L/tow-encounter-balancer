"""Prepared real Cleaving W1 receipts feed existing book NPC consumers.

These isolate profile source consumers, not a complete triggering Attack or
native battle. The wave's Stagger/Wound result is executed by the real rule.
"""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_cleaving_companion_sources import prepared_start
from tests.unit.test_companion_attack_wrappers import PreparedAttackView, attack_request
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_bestigor_models import pc_bestigor_glorious_source, PcBestigorWaveGloriousSource
from towr.domain.pc_blunderbuss_models import PcNearbyDecisions
from towr.domain.pc_cleaving_blow_models import (
    PcCleavingTargetProof, PcCleavingProfileProof, PcCleavingEndProof,
)
from towr.domain.pc_melee_models import PcAdjacentNpcExitPolicy
from towr.domain.pc_melee_result_models import initial_pc_melee_state, PcAttackProof
from towr.domain.pc_npc_wound_models import (
    official_profile_wound_state, pc_npc_broken_turn_unsupported, PcNpcBrokenWaveTurnUnsupported,
)
from towr.domain.resolution_models import StaggerImpactRequest, TargetInjuryPolicy
from towr.domain.turn_models import (
    CombatTurnStartRequest, CombatActionSlotRequest, CombatActionDeclaration,
    CombatActionKind, ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot
from towr.rules.test_resolution import RerollAllFailures


def prepared_view(*, official=False, exit_supported=False):
    source=book_pc_scenario(bestigors=int(not official),officials=int(official),
        footpads=0,townsfolk=0,pc_count=1)
    if exit_supported:
        source=replace(source,npc_broken_exit_policy=PcAdjacentNpcExitPolicy('outside',True,True),
            facts=replace(source.facts,can_leave_zone=True))
    base=initial_pc_melee_state(source)
    current=PreparedAttackView(_base=base,**{name:getattr(base,name) for name in base.__dataclass_fields__})
    actor='official1' if official else 'bestigor1'
    wave=prepared_start('pc1',actor)
    enemy=base.enemy(actor)
    before=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED))
    request=StaggerImpactRequest(wave.wave_id+':target:'+actor,actor,TargetInjuryPolicy.BRUTE,before,False,False)
    result=resolve_stagger_impact(request,SequenceRandom(()),decisions=PcNearbyDecisions())
    target=PcCleavingTargetProof(wave.wave_id,request,result)
    ack=PcCleavingProfileProof(wave.wave_id,actor,result.profile_wound.state_change,None)
    injury=(official_profile_wound_state(enemy.definition,result.state,ack.source) if official else result.state)
    current.enemies=(replace(enemy,state=replace(enemy.state,injury=injury)),)
    current.history=(wave,target,ack,PcCleavingEndProof(wave.wave_id))
    current.round_state=replace(base.round_state,completed_turn_entity_ids=('pc1',))
    return current,actor,wave,target,ack


class CleavingNpcWoundSourceTests(TestCase):
    def test_bestigor_first_wave_wound_grants_the_actual_wave_entitlement(self):
        current,actor,wave,_,ack=prepared_view()
        grant=pc_bestigor_glorious_source(current,actor)
        self.assertEqual(grant,PcBestigorWaveGloriousSource(actor,wave.wave_id,ack.source))
        self.assertFalse(hasattr(grant,'wound_attack_id'))

    def test_bestigor_next_actual_attack_consumes_the_wave_entitlement(self):
        current,actor,_,_,_=prepared_view()
        grant=pc_bestigor_glorious_source(current,actor)
        clock=start_combat_turn(CombatTurnStartRequest('prepared:turn',current.round_state,actor)).state
        current.round_state=reserve_combat_action_slot(CombatActionSlotRequest('prepared:slot',clock,actor,
            CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD)).state
        request,protection,intent=attack_request(current,actor,'pc1')
        execution=execute_attack_action(request,SequenceRandom([1]*100),decisions=RerollAllFailures())
        proof=PcAttackProof(request,prepare_protection(protection),execution,None,
            npc_glorious_source=grant,weapon_intent=intent)
        current.history=(*current.history,proof)
        self.assertIsNone(pc_bestigor_glorious_source(current,actor))

    def test_bestigor_rejects_missing_target_wrong_wave_and_illegal_disposition(self):
        for changed in ('missing','wrong-wave','closed','disposition'):
            with self.subTest(changed=changed):
                current,actor,wave,target,ack=prepared_view()
                if changed=='missing': current.history=(wave,ack)
                elif changed=='wrong-wave': current.history=(wave,replace(target,wave_id='foreign'),ack)
                elif changed=='closed': current.history=(wave,target,PcCleavingEndProof(wave.wave_id),ack)
                else:
                    decision=MinionDefeatDecision('pc1',actor,NpcDefeatDisposition.KILLED,True)
                    current.history=(wave,target,replace(ack,decision=decision))
                with self.assertRaises(ValueError): pc_bestigor_glorious_source(current,actor)

    def test_bestigor_wound_count_without_ack_does_not_invent_entitlement(self):
        current,actor,wave,target,_=prepared_view()
        current.history=(wave,target)
        self.assertIsNone(pc_bestigor_glorious_source(current,actor))
        current,actor,_,_,_=prepared_view()
        enemy=current.enemy(actor)
        current.enemies=(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,wounds=2,defeated=True))),)
        self.assertIsNone(pc_bestigor_glorious_source(current,actor))

    def test_official_next_own_turn_retains_the_cleaving_wound_source(self):
        current,actor,wave,_,ack=prepared_view(official=True)
        stop=pc_npc_broken_turn_unsupported(current)
        self.assertIs(type(stop),PcNpcBrokenWaveTurnUnsupported)
        self.assertEqual((stop.actor_id,stop.wave_id,stop.profile_change),(actor,wave.wave_id,ack.source))
        self.assertFalse(hasattr(stop,'attack_id'))

    def test_official_with_supported_exit_continues_without_unsupported_or_fake_attack(self):
        current,_,_,_,_=prepared_view(official=True,exit_supported=True)
        self.assertIsNone(pc_npc_broken_turn_unsupported(current))

    def test_official_rejects_detached_repeated_and_retargeted_acknowledgements(self):
        for changed in ('missing','repeat','wrong-wave','disposition'):
            with self.subTest(changed=changed):
                current,actor,wave,target,ack=prepared_view(official=True)
                if changed=='missing': current.history=(wave,ack)
                elif changed=='repeat': current.history=(wave,target,ack,ack)
                elif changed=='wrong-wave': current.history=(wave,replace(target,wave_id='foreign'),ack)
                else:
                    decision=MinionDefeatDecision('pc1',actor,NpcDefeatDisposition.KILLED,True)
                    current.history=(wave,target,replace(ack,decision=decision))
                with self.assertRaises(ValueError): pc_npc_broken_turn_unsupported(current)
