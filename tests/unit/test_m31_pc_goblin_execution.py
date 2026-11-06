"""Actual Goblin defeat without Wounds, shield witnesses and unopposed Backstabba."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.attack_models import MissConsequence
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcAttackerStaggerProof,PcMinionStaggerDefeatProof,PcProfileWoundProof,
    PcMeleeStep,PcMeleeOutcome,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry
from towr.domain.pc_npc_ability_models import pc_npc_damage_profile
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def scene(*,goblins=0,night_goblins=0,skulkers=0,pcs=2,rounds=1):
    return book_pc_scenario(goblins=goblins,night_goblins=night_goblins,skulkers=skulkers,
        footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds)


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def fleeing_goblin():
    return execute(scene(goblins=1),([1,1,10,10]+[10]*3)*2)


class PcGoblinExecutionTests(unittest.TestCase):
    def test_authored_shield_and_short_maximum_remain_explicit_and_require_one_hand(self):
        source=make_pc_melee_scenario(max_rounds=1)
        enemy=source.enemies[0]
        attack=replace(enemy.definition.attacks[0],range_max=RangedWeaponRange.SHORT)
        resilience=ResilienceProfile(3,1)
        definition=replace(enemy.definition,attacks=(attack,),resilience=resilience)
        state=replace(enemy.state,current_resilience=resilience,holds_shield=True)
        source=replace(source,enemies=(replace(enemy,definition=definition,state=state),))
        result=execute(source,[1]*3+[10]*2)
        proof=next(s.proof for s in result.steps if type(s.proof) is PcAttackProof)
        self.assertTrue(proof.protection.source_request.defender_holds_shield)
        self.assertEqual(proof.execution.resolution.attack.effective_resilience,4)
        for hands in (RangedWeaponHands.TWO_HANDED,None):
            protection=replace(definition.protection[0],skill=Skill.ATHLETICS)
            malformed=replace(definition,attacks=(replace(attack,hands=hands),),protection=(protection,))
            with self.subTest(hands=hands),self.assertRaises(ValueError):
                replace(source,enemies=(replace(enemy,definition=malformed,
                    state=replace(state,wields_weapon=hands is not None)),))

    def test_repeated_stagger_defeats_both_goblin_loadouts_without_wound_or_gm_disposition(self):
        for keyword,actor,roll in (('goblins','goblin1',[1,1,10,10]),
                ('night_goblins','night_goblin1',[1,10,10,10])):
            with self.subTest(profile=keyword):
                result=execute(scene(**{keyword:1}),(roll+[10]*3)*2)
                ack,=tuple(s for s in result.steps if type(s.proof) is PcMinionStaggerDefeatProof)
                injury=result.state.enemy(actor).state.injury
                self.assertEqual((injury.wounds,injury.wound_limit,injury.defeated),(0,1,True))
                self.assertEqual(injury.defeat_cause,ack.proof.source)
                self.assertTrue(injury.conditions.has(Condition.STAGGERED))
                self.assertFalse(any(type(s.proof) is PcProfileWoundProof for s in result.steps))
                self.assertFalse(result.state.enemy(actor).state.wields_weapon)
                self.assertTrue(result.state.enemy(actor).state.holds_shield)
                self.assertEqual(result.state.enemy(actor).state.available_attack_ids,())
                self.assertIn(actor,result.state.round_state.excluded_turn_entity_ids)
                self.assertEqual(result.state.live_enemies,())
                self.assertEqual(result.exited_npc_ids,())
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                self.assertIsNone(result.unsupported)
                for s in result.steps:
                    if type(s.proof) is PcAttackProof:
                        self.assertTrue(s.proof.protection.source_request.defender_holds_shield)
                attack=next(s.proof for s in reversed(result.steps) if type(s.proof) is PcAttackProof)
                self.assertIsNone(attack.execution.resolution.stagger)
                self.assertIsNone(attack.execution.resolution.profile_wound)
                self.assertEqual(attack.execution.resolution.follow_ups,(injury.defeat_cause,))

    def test_direct_wound_keeps_normal_disposition_and_does_not_invent_fleeing(self):
        for keyword,actor in (('goblins','goblin1'),('night_goblins','night_goblin1')):
            with self.subTest(profile=keyword):
                result=execute(scene(**{keyword:1},pcs=1),[1]*3+[10]*3)
                injury=result.state.enemy(actor).state.injury
                self.assertEqual((injury.wounds,injury.defeated,injury.defeat_cause),(1,True,None))
                ack,=tuple(s.proof for s in result.steps if type(s.proof) is PcProfileWoundProof)
                self.assertIsNotNone(ack.decision)
                self.assertFalse(any(type(s.proof) is PcMinionStaggerDefeatProof for s in result.steps))

    def test_skulker_does_not_inherit_dirty_coward(self):
        result=execute(scene(skulkers=1),([1,10,10,10]+[10]*4)*2)
        injury=result.state.enemy('skulker1').state.injury
        self.assertEqual((injury.wounds,injury.defeated,injury.defeat_cause),(1,True,None))
        self.assertTrue(any(type(s.proof) is PcProfileWoundProof for s in result.steps))

    def test_already_staggered_attacker_miss_does_not_trigger_dirty_coward(self):
        result=execute(scene(goblins=1,pcs=1,rounds=2),
            ([10]*3+[1]*3+[10]*2+[1]*3)*2)
        injury=result.state.enemy('goblin1').state.injury
        self.assertEqual((injury.wounds,injury.defeated,injury.defeat_cause),(0,False,None))
        attacks=tuple(s.proof for s in result.steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='goblin1')
        self.assertEqual(tuple(a.execution.resolution.attack.miss_consequence for a in attacks),
            (MissConsequence.STAGGER_ATTACKER,MissConsequence.NONE))
        self.assertEqual(sum(type(s.proof) is PcAttackerStaggerProof and
            s.source.round_state.active_turn.actor_id=='goblin1' for s in result.steps),1)
        self.assertFalse(any(type(s.proof) is PcMinionStaggerDefeatProof for s in result.steps))

    def test_cause_and_weapon_drop_cannot_be_replayed_swapped_or_removed_from_cached_state(self):
        result=fleeing_goblin()
        ack=next(s for s in result.steps if type(s.proof) is PcMinionStaggerDefeatProof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)
        for field,value in (('target_id','another-goblin'),('source_id','another-attack'),('rule_id','another-rule')):
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(ack.source,replace(ack.proof,source=replace(ack.proof.source,**{field:value})))
        attack=next(s for s in reversed(result.steps) if type(s.proof) is PcAttackProof)
        forged=deepcopy(attack.proof)
        object.__setattr__(forged.execution.resolution,'minion_stagger_defeat',None)
        with self.assertRaises(ValueError):
            PcMeleeStep(attack.source,forged)
        # A forged ordinary Wound/flag cannot replace the actual zero-Wound cause.
        forged=deepcopy(result)
        enemy=forged.steps[-1].state.enemy('goblin1')
        object.__setattr__(enemy.state.injury,'defeat_cause',None)
        with self.assertRaises(ValueError):
            replace(forged)
        with self.assertRaises(ValueError):
            replace(ack.state,enemies=(replace(ack.state.enemy('goblin1'),state=replace(
                ack.state.enemy('goblin1').state,wields_weapon=True)),))

    def test_multiple_fleeing_causes_keep_their_own_attack_and_target(self):
        source=scene(goblins=2,pcs=4)
        priorities=('goblin2','goblin1')
        source=replace(source,party=tuple(member if index<2 else replace(member,target_priority=priorities,
            defeat_decisions=tuple(member.defeat_decision(target) for target in priorities))
            for index,member in enumerate(source.party)))
        result=execute(source,([1,1,10,10]+[10]*3)*4)
        acks=tuple(s for s in result.steps if type(s.proof) is PcMinionStaggerDefeatProof)
        self.assertEqual(tuple(s.proof.source.target_id for s in acks),('goblin1','goblin2'))
        self.assertNotEqual(acks[0].proof.source.source_id,acks[1].proof.source.source_id)
        self.assertTrue(all(e.state.injury.wounds==0 and e.state.injury.defeated for e in result.state.enemies))
        with self.assertRaises(ValueError):
            PcMeleeStep(acks[1].source,acks[0].proof)

    def test_backstabba_opposed_zero_successes_remains_ordinary_damage(self):
        result=execute(scene(skulkers=1,pcs=1),[10]*3+[1]*4+[1]*4+[10]*3+[1])
        attack=next(s.proof.execution.resolution.attack for s in result.steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='skulker1')
        self.assertIsNotNone(attack.defender_test)
        self.assertEqual(attack.defender_test.successes,0)
        self.assertEqual((attack.impact_spec.damage.base,attack.impact_spec.damage.success_multiplier,attack.damage),(3,1,7))

    def test_actual_defenceless_pc_enables_backstabba_but_receives_only_one_wound(self):
        source=make_pc_melee_scenario(enemy_count=4,max_rounds=1)
        source=replace(source,enemies=(*source.enemies[:3],create_pc_book_npc(PcBookNpcProfile.NASTY_SKULKER,'minion4')))
        result=execute(source,heavy_prefix(22)+[1]*5+[10]*4)
        step=next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id=='minion4')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(step.proof.execution.resolution.attack.defender_test)
        self.assertIsNone(step.proof.protection.source_request.selected_skill)
        damage=step.proof.execution.resolution.attack.impact_spec.damage
        self.assertEqual((damage.base,damage.success_multiplier,step.proof.execution.resolution.attack.damage),(3,2,13))
        self.assertEqual(len(result.state.party[0].injury.wounds),len(step.source.party[0].injury.wounds)+1)
        self.assertEqual(result.state.party[0].injury.wounds[-1].table_total,40)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertIsNone(result.unsupported)

    def test_backstabba_profile_change_is_bound_to_actual_skulker_not_other_npcs(self):
        skulker=get_pc_book_npc_entry(PcBookNpcProfile.NASTY_SKULKER).definition
        goblin=get_pc_book_npc_entry(PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR).definition
        self.assertEqual(pc_npc_damage_profile(skulker,unopposed=True).success_multiplier,2)
        self.assertEqual(pc_npc_damage_profile(skulker,unopposed=False).success_multiplier,1)
        self.assertEqual(pc_npc_damage_profile(goblin,unopposed=True).success_multiplier,1)
        with self.assertRaises(TypeError):
            pc_npc_damage_profile(skulker,unopposed=1)


if __name__=='__main__':
    unittest.main()
