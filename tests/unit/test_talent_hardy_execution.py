"""Target-owned Hardy at real PC/Champion Wound boundaries.

Native attack/fall journals are replayed in full. Hazard and Miscast cases
explicitly prepare a pending boundary; they are not invented native histories.
"""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.talent_sources import paid_talent,free_talent
from tests.integration.test_pc_falling_native import falling_source
from tests.unit.test_m8_npc_champion_attack import request as champion_attack
from towr.domain.condition_models import Condition
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.pc_magic_models import PcMagicPending,build_magic_effect,project_pc_magic_step
from towr.domain.pc_magic_miscast_plan import PcMagicTask,PcMagicTaskKind
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeStep,initial_pc_melee_state,
)
from towr.domain.pc_weapon_area_models import (
    _hazard_request,_canonical_hazard,weapon_hazard_resolution_request,
    ABLAZE_HAZARD_RULE_ID,BLAST_IMPACT_RULE_ID,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_injury_models import HARDY_RULE_ID,hardy_wound_dice_modifiers
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.test_resolution import resolve_test


def hardy_source():
    source=make_pc_melee_scenario(max_rounds=1)
    member=source.party[0]
    return replace(source,party=(replace(member,pc=replace(member.pc,toughness=4),
        talents=(paid_talent(TalentId.HARDY),)),))


class HardyExecutionTests(unittest.TestCase):
    def assert_replay(self,result):
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_native_pc_attack_wound_has_one_target_modifier_and_one_die(self):
        source=hardy_source()
        rng=ScriptedD10([10]*5+[1]*2+[10]*3+[1])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        attack,=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id=='pc')
        wound=attack.proof.execution.resolution.pending_character_wound
        self.assertEqual(wound.source_request.wound.dice_modifiers,
            hardy_wound_dice_modifiers(source.party[0].talents))
        self.assertEqual(wound.wound_result.table_roll.values,(1,))
        self.assertEqual(tuple(w.table_total for w in result.state.participant('pc').injury.wounds),(1,))
        self.assertEqual(result.state.participant('pc').daily_wounds.wound_count,1)
        self.assertEqual(result.executed_actions,2)
        self.assert_replay(result)
        # Removing or doubling a target-owned modifier cannot legitimise a
        # cached receipt, even when the minimum leaves the same dice outcome.
        for modifiers in ((),wound.source_request.wound.dice_modifiers*2):
            forged=deepcopy(attack.proof)
            object.__setattr__(forged.request.kernel_request,'wound_dice_modifiers',modifiers)
            with self.assertRaises(ValueError):
                PcMeleeStep(attack.source,forged)

    def test_native_forced_fall_preserves_shortfall_and_existing_wound(self):
        source=falling_source()
        source=replace(source,party=(replace(source.party[0],talents=(free_talent(TalentId.HARDY),)),))
        rng=ScriptedD10([10,10]+[1]*6+[10,9,1,1])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        fall,=tuple(step for step in result.steps if type(step.proof) is PcFallingProof)
        wound=fall.proof.result.pending_character_wound
        self.assertEqual((fall.proof.result.rating,fall.proof.result.shortfall),(2,1))
        self.assertEqual(wound.source_request.wound.base_dice,1)
        self.assertEqual(wound.source_request.wound.dice_modifiers[0].rule_id,HARDY_RULE_ID)
        self.assertEqual(wound.wound_result.table_roll.values,(1,))
        self.assertEqual(tuple(w.table_total for w in result.state.participant('pc1').injury.wounds),(9,1))
        self.assertEqual(result.state.participant('pc1').daily_wounds.wound_count,2)
        self.assert_replay(result)
        with self.assertRaises(ValueError):
            PcMeleeStep(fall.source,replace(fall.proof,request=replace(fall.proof.request,
                wound_dice_modifiers=())))

    def test_fire_and_direct_blast_keep_their_actual_hazard_rating(self):
        state=initial_pc_melee_state(hardy_source())
        for rule,rating in ((ABLAZE_HAZARD_RULE_ID,2),(BLAST_IMPACT_RULE_ID,3)):
            with self.subTest(rule=rule):
                request=_hazard_request(state,'pc','prepared:'+rule,rating,rule)
                # The base Endurance Test has four dice; zero successes
                # produce the full, unchanged Hazard shortfall.
                rng=ScriptedD10([10]*4+[1]*(rating-1))
                test=resolve_test(request.avoidance_test,rng)
                result=resolve_hazard(weapon_hazard_resolution_request(request,test),rng)
                rng.assert_exhausted()
                self.assertEqual((result.rating,result.shortfall),(rating,rating))
                self.assertEqual(result.pending_character_wound.wound_result.table_roll.values,(1,)*(rating-1))
                _canonical_hazard(request,test,result)
                with self.assertRaises(ValueError):
                    _canonical_hazard(replace(request,wound_dice_modifiers=()),test,result)

    def test_internal_miscast_and_repeated_stagger_use_target_owned_source(self):
        for kind,staggered in ((PcMagicTaskKind.RANDOM_WOUND,False),(PcMagicTaskKind.STAGGER,True)):
            with self.subTest(kind=kind):
                source=magic_scenario(enemies=1)
                member=source.party[0]
                source=replace(source,party=(replace(member,
                    talents=(*member.talents,paid_talent(TalentId.HARDY))),))
                actor=member.actor_id
                state=initial_pc_melee_state(source)
                if staggered:
                    body=state.party[0]
                    state=replace(state,party=(replace(body,injury=replace(body.injury,
                        conditions=body.injury.conditions.with_condition(Condition.STAGGERED))),))
                task=PcMagicTask('prepared:miscast',kind,actor)
                state=replace(state,magic_pending=PcMagicPending(actor,'prepared:roll',(task,)))
                rng=ScriptedD10([1])
                proof=build_magic_effect(state,rng)
                rng.assert_exhausted()
                wound=proof.result if not staggered else proof.result.pending_character_wound
                self.assertEqual(wound.source_request.wound.dice_modifiers[0].rule_id,HARDY_RULE_ID)
                self.assertEqual(wound.wound_result.table_roll.values,(1,))
                # Exact projection rebuilds the effect using retained random
                # dice; the prepared boundary makes no prior Cast claim.
                updates=project_pc_magic_step(state,proof)
                self.assertIsNotNone(updates.pending_wound)

    def test_champion_bridge_requires_actual_target_source_before_rng(self):
        from towr.domain.npc_roster_models import NpcRoster
        base=champion_attack(staggered=True)
        target=base.state.roster.participant(base.execution.target_id)
        target=replace(target,definition=replace(target.definition,
            talents=(free_talent(TalentId.HARDY),)))
        roster=NpcRoster(tuple(target if p.state.actor_id==target.state.actor_id else p
            for p in base.state.roster.participants))
        state=replace(base.state,roster=roster)
        with self.assertRaisesRegex(ValueError,'kernel differs'):
            replace(base,state=state)
        modifiers=hardy_wound_dice_modifiers(target.definition.talents)
        request=replace(base,state=state,execution=replace(base.execution,
            kernel_request=replace(base.execution.kernel_request,wound_dice_modifiers=modifiers)))
        rng=ScriptedD10([1,2,10,10,10,10,6])
        result=execute_npc_champion_attack(request,rng)
        rng.assert_exhausted()
        injury=result.state.roster.participant(target.state.actor_id).state.injury
        self.assertEqual(injury.wounds[0].table_total,6)
        self.assertEqual(result.state.daily_wounds.wound_count,1)
        self.assertEqual(result.execution.resolution.pending_character_wound.source_request.wound.dice_modifiers,modifiers)
        with self.assertRaises(ValueError):
            replace(request,execution=replace(request.execution,kernel_request=replace(
                request.execution.kernel_request,wound_dice_modifiers=modifiers*2)))


if __name__=='__main__':
    unittest.main()
