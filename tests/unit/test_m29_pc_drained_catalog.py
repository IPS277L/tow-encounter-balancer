"""GM136–137: on-hit Drained versus the White Wolf's own first-Wound Drained."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import ConditionOnHitSpec,DamageProfile,ResilienceProfile
from towr.domain.condition_models import Condition,EffectClassification
from towr.domain.pc_melee_result_models import PcAttackProof,PcProfileWoundProof
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,PcBookNpcWoundBand,create_pc_book_npc,get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


SPIDER=PcBookNpcProfile.GIANT_SPIDER
WOLF=PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS
SPIDER_RULE='RULE-PROFILE-CREATURE-007:poisonous-fangs-drained'


class PcDrainedCatalogTests(unittest.TestCase):
    def test_two_distinct_drained_sources_keep_printed_profiles_and_injury_types(self):
        for profile,page,attack_id,threshold,damage,pthreshold,toughness,limit in (
                (SPIDER,137,'poisonous_fangs',3,3,3,3,1),
                (WOLF,136,'clamping_jaws',4,5,4,5,2)):
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,
                     TargetInjuryPolicy.MINION if limit==1 else TargetInjuryPolicy.BRUTE,
                     limit,ResilienceProfile(toughness)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands),(attack_id,source+':'+attack_id,Skill.MELEE,
                    InlineProfile(3,threshold),DamageProfile(damage),None))
                self.assertEqual((definition.protection[0].skill,definition.protection[0].test_profile),
                    (Skill.ATHLETICS,InlineProfile(4,pthreshold)))
                self.assertEqual(attack.secondary_effects,
                    (ConditionOnHitSpec(Condition.DRAINED,SPIDER_RULE,EffectClassification.UNCLASSIFIED),)
                    if profile is SPIDER else ())
                actor=create_pc_book_npc(profile,'creature')
                self.assertEqual((actor.state.wields_weapon,actor.state.holds_shield),(False,False))
                validate_pc_book_npc_definition(definition)

    def test_whole_card_metadata_preserves_unselected_and_unreachable_actions(self):
        spider=get_pc_book_npc_entry(SPIDER)
        wolf=get_pc_book_npc_entry(WOLF)
        self.assertEqual(tuple(a.name for a in spider.inactive_abilities),
            ('Scitter-Scatter','Goblin Wolf Rider'))
        self.assertIn('Giant Spider',spider.inactive_abilities[1].scope)
        self.assertIn('ruins',spider.inactive_abilities[0].scope)
        self.assertEqual(spider.active_abilities[0].name,'Poisonous Fangs')
        self.assertEqual(wolf.unselected_attack_names,('Rending Claws',))
        self.assertEqual(tuple(a.name for a in wolf.inactive_abilities),('Pin and Tear','Fearsome'))
        self.assertIn('Charge',wolf.inactive_abilities[0].scope)
        self.assertIn('Gives Ground',wolf.inactive_abilities[1].scope)
        self.assertEqual(wolf.active_abilities[0].effect,'Target cannot Give Ground')
        self.assertEqual(wolf.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Drained'),PcBookNpcWoundBand(2,'Defeated')))

    def test_canonical_card_cannot_lose_or_swap_its_effect(self):
        spider=get_pc_book_npc_entry(SPIDER).definition
        attack,=spider.attacks
        wolf=get_pc_book_npc_entry(WOLF).definition
        invalid=(replace(spider,attacks=(replace(attack,secondary_effects=()),)),
            replace(spider,attacks=(replace(attack,secondary_effects=(ConditionOnHitSpec(
                Condition.DRAINED,'RULE-AUTHORED:other-drained'),)),)),
            replace(wolf,attacks=(replace(wolf.attacks[0],secondary_effects=attack.secondary_effects),)),
            replace(spider,id='authored:renamed',source_rule_id='authored:source'),
            replace(wolf,resilience=ResilienceProfile(3)))
        for candidate in invalid:
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_effect_and_snapshot_graphs_are_fresh_and_cache_aliases_fail(self):
        for profile in (SPIDER,WOLF):
            first=create_pc_book_npc(profile,'first')
            second=create_pc_book_npc(profile,'second')
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.state.injury,second.state.injury)
            object.__setattr__(first.definition.attacks[0].damage,'base',99)
            self.assertEqual(second.definition,get_pc_book_npc_entry(profile).definition)
            with self.assertRaises(ValueError):
                validate_pc_book_npc_definition(first.definition)
        forged=deepcopy(get_pc_book_npc_entry(SPIDER).definition)
        object.__setattr__(forged.attacks[0].secondary_effects[0],'condition','drained')
        self.assertEqual(forged,get_pc_book_npc_entry(SPIDER).definition)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(forged)

    def test_white_wolf_first_wound_suppresses_bonus_dice_before_its_ordinary_turn(self):
        source=book_pc_scenario(white_wolves=2,footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
        source=replace(source,facts=replace(source.facts,can_leave_zone=True))
        rng=ScriptedD10([1]*3+[10]*4+[10]*3+[1]*3+[10]*4+[1]*3)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        ack=next(step for step in result.steps if type(step.proof) is PcProfileWoundProof)
        self.assertFalse(ack.source.enemy('white_wolf1').state.injury.conditions.has(Condition.DRAINED))
        self.assertTrue(ack.state.enemy('white_wolf1').state.injury.conditions.has(Condition.DRAINED))
        incoming=tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id in ('white_wolf1','white_wolf2'))
        self.assertEqual(tuple(p.execution.resolution.attack.attacker_test.trace.rolled_dice for p in incoming),(3,4))
        self.assertEqual(tuple(p.execution.resolution.attack.impact_spec.damage.base for p in incoming),(5,5))
        self.assertFalse(any(p.request.kernel_request.can_target_leave_zone for p in incoming))
        pc_attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertTrue(pc_attack.request.kernel_request.can_target_leave_zone)
        self.assertEqual(result.unsupported,None)

    def test_white_wolf_second_wound_defeats_without_reapplying_profile_effect(self):
        source=book_pc_scenario(white_wolves=1,footpads=0,townsfolk=0,pc_count=2,max_rounds=1)
        rng=ScriptedD10([1]*4+[10]*4+[1]*4+[10]*4)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        acks=tuple(step for step in result.steps if type(step.proof) is PcProfileWoundProof)
        self.assertEqual(len(acks),2)
        self.assertEqual(acks[0].state.enemy('white_wolf1').state.injury.wounds,1)
        self.assertTrue(acks[0].state.enemy('white_wolf1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual((acks[1].state.enemy('white_wolf1').state.injury.wounds,
            acks[1].state.enemy('white_wolf1').state.injury.defeated),(2,True))
        self.assertFalse(any(type(step.proof) is PcAttackProof and
            step.proof.request.actor_id=='white_wolf1' for step in result.steps))


if __name__=='__main__':
    unittest.main()
