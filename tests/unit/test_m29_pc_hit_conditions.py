"""Actual post-hit Drained sources remain independent of Wounds, Fate and expiry."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import ConditionOnHitSpec
from towr.domain.condition_models import Condition,ConditionState,EffectClassification
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.pc_hit_condition_models import PcHitConditionSource
from towr.domain.pc_melee_models import (PcMeleeWeapon,PcFatePolicy,PcNearMissPolicy,PcGloriousPolicy,
    validate_pc_melee_scenario_admission)
from towr.domain.pc_melee_result_models import (PcAttackProof,PcEnduranceProof,PcRecoverProof,
    PcWoundCompletionProof,PcTurnEndProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,initial_pc_melee_state)
from towr.domain.recover_models import RecoverMode
from towr.domain.test_models import DiceModifier,Skill,TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


HIT_RULE = 'RULE-PROFILE-CREATURE-007:poisonous-fangs-drained'


class ForeignRule(str,Enum):
    HIT = 'RULE-PROFILE-CREATURE-007:poisonous-fangs-drained'
    AUTHORED = 'authored:hit-drained'


def scene(*,pcs=1,rounds=1,**kwargs):
    return book_pc_scenario(footpads=0,townsfolk=0,spiders=1,pc_count=pcs,max_rounds=rounds,**kwargs)


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def first_wound_values(total):
    return [10]*3+[1]*4+[1]*3+[10]*3+[total]


def spider_attacks(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof)
        and step.proof.request.actor_id=='spider1')


class HitConditionTests(unittest.TestCase):
    def test_hit_with_no_wound_registers_actual_condition_application_after_protection(self):
        source = scene()
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,strength=1,toughness=4,armour_bonus=2,
            weapon=PcMeleeWeapon.SWORD)),))
        result = execute(source,[1,10,10]+[10]*4+[1,10,10]+[10]*4)
        hit, = spider_attacks(result)
        app, = hit.proof.execution.resolution.condition_applications
        self.assertFalse(hit.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(hit.proof.request.kernel_request.attack.defender_test.dice_modifiers,
            (DiceModifier('RULE-EQUIPMENT-003:sword-defence',1),))
        self.assertEqual(hit.proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)
        self.assertEqual(result.state.party[0].injury.wounds,())
        self.assertEqual(result.state.party[0].daily_wounds.wound_count,0)
        self.assertEqual(result.state.party[0].injury.conditions.conditions,frozenset({Condition.STAGGERED,Condition.DRAINED}))
        self.assertFalse(app.was_already_present)
        self.assertFalse(app.blocked)
        self.assertEqual(app.applied_rule_ids,(HIT_RULE,))
        self.assertEqual(result.state.party[0].hit_condition_sources,(PcHitConditionSource(hit.proof.request.id,
            'spider1','pc1',app.request_id,HIT_RULE,Condition.DRAINED),))

    def test_miss_adds_neither_application_nor_hit_source(self):
        result = execute(scene(),[10]*3+[1]*4+[10]*3+[1]*3)
        attack, = spider_attacks(result)
        self.assertEqual(attack.proof.execution.resolution.condition_applications,())
        self.assertEqual(attack.proof.execution.resolution.applied_secondary_rule_ids,())
        self.assertEqual(result.state.party[0].hit_condition_sources,())
        self.assertFalse(result.state.party[0].injury.conditions.has(Condition.DRAINED))

    def test_repeated_hits_keep_one_flag_and_register_each_real_already_present_application(self):
        result = execute(scene(rounds=2),first_wound_values(1)+[10]*3+[1]*4+[1]*3+[10]*3+[1,1])
        first,second = spider_attacks(result)
        self.assertFalse(first.proof.execution.resolution.condition_applications[0].was_already_present)
        self.assertTrue(second.proof.execution.resolution.condition_applications[0].was_already_present)
        sources = result.state.party[0].hit_condition_sources
        self.assertEqual(tuple(s.attack_id for s in sources),(first.proof.request.id,second.proof.request.id))
        self.assertEqual(len({s.application_id for s in sources}),2)
        self.assertEqual(result.state.party[0].injury.conditions.conditions,frozenset({Condition.DRAINED}))

    def test_near_miss_negates_wound_but_retains_post_hit_drained_and_resource_source(self):
        source = scene()
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1,0)),))
        result = execute(source,first_wound_values(6))
        self.assertEqual(result.state.party[0].injury.wounds,())
        self.assertEqual(result.state.party[0].daily_wounds.wound_count,0)
        self.assertEqual(result.state.party[0].timed_wounds,())
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(result.state.party[0].hit_condition_sources),1)
        self.assertEqual(result.state.party[0].fate.rating,2)
        completion, = tuple(step for step in result.steps if isinstance(step.proof,PcWoundCompletionProof))
        self.assertTrue(completion.proof.completion.source_request.current_state.conditions.has(Condition.DRAINED))
        self.assertFalse(completion.proof.completion.source_request.roll.wound_result.state.conditions.has(Condition.DRAINED))

    def test_wound_six_expiry_removes_only_its_own_cause_and_keeps_drained_sword_filter(self):
        source = scene(rounds=2)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,strength=1,weapon=PcMeleeWeapon.SWORD)),))
        result = execute(source,first_wound_values(6)+[1,10,10]+[10]*4+[10]*3+[1]*3)
        first,second = spider_attacks(result)
        self.assertFalse(first.proof.execution.resolution.condition_applications[0].was_already_present)
        self.assertTrue(second.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertFalse(second.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.request.kernel_request.attack.defender_test.dice_modifiers,())
        self.assertEqual(second.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        member = result.state.party[0]
        self.assertEqual(member.timed_wounds,())
        self.assertFalse(any(isinstance(effect,WoundConditionEffect) and effect.condition is Condition.DRAINED
            for effect in member.injury.active_wound_effects))
        self.assertTrue(member.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(member.hit_condition_sources),1)

    def test_hit_on_existing_wound_drained_still_registers_source_and_survives_old_cause_expiry(self):
        source = book_pc_scenario(footpads=1,townsfolk=0,spiders=1,pc_count=1,max_rounds=2)
        member = source.party[0]
        priority = ('footpad1','spider1')
        source = replace(source,party=(replace(member,pc=replace(member.pc,strength=1,weapon=PcMeleeWeapon.SWORD),
            target_priority=priority,defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
            enemy_activation_order=priority)
        result = execute(source,[10]*3+[1]*3+[1]*4+[10]*3+[6]+[1]*4+[10]*3+[1,1]
            +[1,10,10]+[10]*3+[10]*4+[1]*3+[10]*4+[1]*3)
        first,second = spider_attacks(result)
        self.assertTrue(first.proof.execution.resolution.condition_applications[0].was_already_present)
        self.assertEqual(len(result.state.party[0].hit_condition_sources),1)
        self.assertEqual(result.state.party[0].timed_wounds,())
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(second.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)

    def test_standard_recover_pickup_keeps_hit_drained_without_alternative_endurance(self):
        result = execute(scene(rounds=2),first_wound_values(8)+[1]+[10]*3+[1]*3)
        recover, = tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
        self.assertIs(recover.proof.result.source_request.mode,RecoverMode.STANDARD)
        self.assertTrue(recover.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertTrue(recover.state.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(recover.source.party[0].hit_condition_sources,recover.state.party[0].hit_condition_sources)
        self.assertFalse(any(isinstance(step.proof,PcEnduranceProof) for step in result.steps))

    def test_wound_followup_endurance_sees_post_hit_drained(self):
        result = execute(scene(),first_wound_values(4)+[1,10,10])
        endurance, = tuple(step for step in result.steps if isinstance(step.proof,PcEnduranceProof))
        self.assertTrue(endurance.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(endurance.source.party[0].hit_condition_sources),1)

    def test_next_attack_loses_outnumbering_bonus_but_glorious_spending_remains_allowed(self):
        result = execute(scene(pcs=2,rounds=2),[10]*4+[1]*4+[10]*4+[1]*4+[1]*3+[10]*3+[1]
            +[1]*3+[10]*4)
        own = next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertTrue(own.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(own.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(own.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        source = scene(rounds=2)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)),))
        spent = execute(source,[10]*6+[1]*4+[1]*3+[10]*3+[1]+[10]*3+[1]*3+[10]*4)
        attack = next(step for step in spent.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertTrue(attack.source.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertIsNotNone(attack.proof.glorious)
        self.assertIs(attack.proof.execution.resolution.attack.attacker_test.trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(spent.state.party[0].fate.remaining_spends,1)

    def test_white_wolf_first_profile_wound_adds_drained_without_a_pc_hit_source(self):
        source = book_pc_scenario(footpads=0,townsfolk=0,white_wolves=1,pc_count=1,max_rounds=1)
        result = execute(source,[1]*3+[10]*4+[10]*3+[1]*3)
        ack, = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertFalse(ack.source.enemy('white_wolf1').state.injury.conditions.has(Condition.DRAINED))
        self.assertTrue(ack.state.enemy('white_wolf1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(result.state.party[0].hit_condition_sources,())

    def test_authored_secondary_effect_admission_requires_exact_single_unclassified_drained(self):
        source = make_pc_melee_scenario()
        enemy = source.enemies[0]
        effect = ConditionOnHitSpec(Condition.DRAINED,'authored:hit-drained',EffectClassification.UNCLASSIFIED)
        enemy = replace(enemy,definition=replace(enemy.definition,
            attacks=(replace(enemy.definition.attacks[0],secondary_effects=(effect,)),)))
        source = replace(source,enemies=(enemy,))
        validate_pc_melee_scenario_admission(source)
        for effects in ((replace(effect,condition=Condition.PRONE),),
                (replace(effect,classification=EffectClassification.PSYCHOLOGICAL),),
                (effect,replace(effect,rule_id='authored:second'))):
            candidate = replace(enemy,definition=replace(enemy.definition,
                attacks=(replace(enemy.definition.attacks[0],secondary_effects=effects),)))
            with self.subTest(effects=effects),self.assertRaises((TypeError,ValueError)):
                replace(source,enemies=(candidate,))
        forged = deepcopy(source)
        object.__setattr__(forged.enemies[0].definition.attacks[0].secondary_effects[0],'rule_id',ForeignRule.AUTHORED)
        with self.assertRaises(TypeError):
            validate_pc_melee_scenario_admission(forged)

    def test_condition_receipts_bank_types_and_full_source_replay_reject_forgery(self):
        result = execute(scene(),first_wound_values(1))
        hit, = spider_attacks(result)
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(hit.state,hit)
        for name,value in (('was_already_present',0),('blocked',0),('source_rule_id',ForeignRule.HIT),
                ('request_id','foreign:application'),('was_already_present',True)):
            proof = deepcopy(hit.proof)
            object.__setattr__(proof.execution.resolution.condition_applications[0],name,value)
            with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(hit.source,proof)
        proof = deepcopy(hit.proof)
        resolution = proof.execution.resolution
        object.__setattr__(resolution,'condition_applications',(*resolution.condition_applications,*resolution.condition_applications))
        with self.assertRaises(ValueError):
            PcMeleeStep(hit.source,proof)
        member = hit.state.party[0]
        with self.assertRaises(ValueError):
            replace(member,injury=replace(member.injury,conditions=member.injury.conditions.without_condition(Condition.DRAINED)))
        with self.assertRaises(ValueError):
            replace(hit.state,party=(replace(member,hit_condition_sources=()),))
        with self.assertRaises(TypeError):
            replace(member,hit_condition_sources=list(member.hit_condition_sources))
        with self.assertRaises(ValueError):
            replace(member,hit_condition_sources=member.hit_condition_sources*2)
        with self.assertRaises(ValueError):
            replace(hit.state,party=(replace(member,hit_condition_sources=(replace(member.hit_condition_sources[0],
                attack_id='foreign:execute'),)),))
        with self.assertRaises(TypeError):
            replace(member.hit_condition_sources[0],condition='drained')

    def test_sources_are_rejected_when_no_source_npc_can_apply_hit_conditions(self):
        state = initial_pc_melee_state(make_pc_melee_scenario())
        member = state.party[0]
        cause = PcHitConditionSource('foreign:execute','minion1','pc','foreign:application',HIT_RULE,Condition.DRAINED)
        changed = replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED)),hit_condition_sources=(cause,))
        with self.assertRaises(ValueError):
            replace(state,party=(changed,))


if __name__ == '__main__':
    unittest.main()
