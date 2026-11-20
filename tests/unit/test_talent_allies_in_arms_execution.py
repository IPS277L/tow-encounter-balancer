"""Actual PC Help/C7 receipts, plus explicitly local Wound-preparation boundaries."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import weak_helper_source
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.talent_sources import paid_talent,free_talent
from tests.unit.test_pc_combat_talent_execution import help_source
from towr.domain.condition_models import Condition
from towr.domain.pc_allies_in_arms_models import build_allies_in_arms_application
from towr.domain.pc_generated_talents import PcWildAttackProof,actor_stagger_removable
from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip,PcWeaponHand
from towr.domain.pc_melee_result_models import PcHelpProof,PcMeleeStep,initial_pc_melee_state
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.test_models import TestQuality
from towr.domain.weapon_effect_preparation import MORNING_STAR_STAGGERED_RULE_ID,FLAIL_STAGGERED_RULE_ID
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


def with_allies(member):
    return replace(member,talents=(*member.talents,paid_talent(TalentId.ALLIES_IN_ARMS)),
        talent_facts=TalentOwnerFacts(fellowship=4))


def wild_source():
    source=help_source()
    return replace(source,party=(with_allies(source.party[0]),source.party[1]),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def penalty_source(weapon):
    source=weak_helper_source()
    helper,ally=source.party
    hand=PcTwoHandedGrip.BOTH if weapon is PcMeleeWeapon.FLAIL else PcWeaponHand.LEFT
    helper=with_allies(replace(helper,pc=replace(helper.pc,weapon=weapon,toughness=20),
        initial_weapon_hand=hand,combat_equipment=initial_weapon_items(weapon,hand)))
    return replace(source,party=(helper,ally),max_rounds=2,
        enemy_target_priority=('pc1','pc2'),facts=replace(source.facts,outnumbering_bonus_approved=False))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def help_steps(result):
    return tuple(step for step in result.steps if type(step.proof) is PcHelpProof)


class AlliesInArmsExecutionTests(unittest.TestCase):
    def assert_replays(self,result):
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_actual_wild_help_pays_stagger_before_zero_success_test_then_removes_it_once(self):
        source=wild_source()
        result=execute(source,[10,10]+[1]*6+[10]*6)
        price,=tuple(step for step in result.steps if type(step.proof) is PcWildAttackProof)
        help,=help_steps(result)
        self.assertFalse(price.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(price.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(help.proof.request.actor_conditions.has(Condition.STAGGERED))
        self.assertIs(help.proof.execution.help_test_result.trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(help.proof.execution.help_test_result.trace.initial_values,(10,))
        self.assertEqual(help.proof.execution.help_test_result.trace.final_values,(10,))
        self.assertEqual(help.proof.execution.help_test_result.successes,0)
        self.assertEqual(help.proof.allies_in_arms.target_id,'pc1')
        self.assertEqual(help.proof.allies_in_arms.execution,help.proof.execution)
        self.assertFalse(help.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(help.state.participant('pc1').fate,source.party[0].fate)
        self.assertEqual(len(help.state.round_state.active_turn.action_slots),1)
        self.assertEqual(result.executed_actions,2)
        self.assert_replays(result)
        application=help.proof.allies_in_arms
        for changed in (replace(help.proof,allies_in_arms=None),
                replace(help.proof,allies_in_arms=replace(application,target_id='pc2')),
                replace(help.proof,allies_in_arms=replace(application,talent=free_talent(TalentId.ALLIES_IN_ARMS)))):
            with self.subTest(changed=changed),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(help.source,changed)
        with self.assertRaises(ValueError):
            PcMeleeStep(help.state,help.proof)

    def test_actual_staggered_weapon_help_keeps_penalty_then_removes_one_selected_condition(self):
        cases=((PcMeleeWeapon.MORNING_STAR,MORNING_STAR_STAGGERED_RULE_ID,-1,True),
            (PcMeleeWeapon.FLAIL,FLAIL_STAGGERED_RULE_ID,-2,False))
        for weapon,rule,amount,both in cases:
            with self.subTest(weapon=weapon):
                source=penalty_source(weapon)
                # Round1: failed Help; ally misses (or hits for exactly R10),
                # then the real NPC hit Staggers the high-T helper.
                ally_rolls=[10]*6 if both else [1]+[10]*5
                values=[10]+ally_rolls+[10]*6+[1,1,10]+[10]+[1]*6+[10]*6
                result=execute(source,values)
                first,second=help_steps(result)
                self.assertIsNone(first.proof.allies_in_arms)
                self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
                test=second.proof.execution.help_test_result
                self.assertIn((rule,amount),tuple((m.rule_id,m.amount) for m in second.proof.request.help_test.dice_modifiers))
                self.assertEqual(test.trace.regular_dice_delta,amount)
                self.assertEqual(test.trace.threshold,1)
                self.assertEqual(test.successes,0)
                target='pc2' if both else 'pc1'
                self.assertEqual(second.proof.allies_in_arms.target_id,target)
                self.assertFalse(second.state.participant(target).injury.conditions.has(Condition.STAGGERED))
                if both:
                    self.assertTrue(second.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
                self.assert_replays(result)

    def test_prepared_wound15_source_cannot_be_removed_by_the_real_help_receipt(self):
        from towr.domain.injury_models import WoundRecord,WoundEntryId,WoundConditionEffect,WoundEffectDuration
        result=execute(wild_source(),[10,10]+[1]*6+[10]*6)
        actual,=help_steps(result)
        member=actual.source.participant('pc1')
        member=replace(member,injury=replace(member.injury,
            wounds=(WoundRecord(1,WoundEntryId.SCARRING_STRIKE,15,(7,8),effect_resolved=True),),
            active_wound_effects=(WoundConditionEffect(1,Condition.STAGGERED,WoundEffectDuration.UNTIL_HEALED),)))
        # Local source/consumer boundary only. The W15 is not presented as an
        # invented earlier sequence of native Wound rolls or surgery receipts.
        prepared=replace(actual.source,party=(member,actual.source.party[1]))
        self.assertFalse(actor_stagger_removable(prepared,'pc1'))
        self.assertIsNone(build_allies_in_arms_application(prepared,actual.proof.execution))
        with self.assertRaises(ValueError):
            PcMeleeStep(prepared,actual.proof)

    def test_prepared_injured_hand_preserves_critical_created_by_actual_help_after_removal(self):
        from towr.domain.injury_models import (
            WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration,
        )
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        result=execute(wild_source(),[10,10]+[1]*6+[10]*6)
        actual,=help_steps(result)
        member=actual.source.participant('pc1')
        member=replace(member,injury=replace(member.injury,
            wounds=(WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),
                WoundRecord(2,WoundEntryId.SMASHED_HAND,12,(3,9),effect_resolved=True)),
            active_wound_effects=tuple(WoundRestrictionEffect(sequence,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED)
                for sequence in (1,2))),
            body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),
                PcBodyFact(PcBodyFactKind.INJURED_HAND,2,PcWeaponHand.RIGHT)))
        # Prepared injury boundary, then the real existing Help execution.
        # No complete history of the two hand injuries is claimed.
        prepared=replace(actual.source,party=(member,actual.source.party[1]))
        self.assertFalse(prepared.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        after=PcMeleeStep(prepared,actual.proof).state
        self.assertTrue(after.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertFalse(after.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(after.participant('pc1').body_facts,member.body_facts)

    def test_only_the_helper_ownership_can_authorize_its_actual_help_application(self):
        result=execute(wild_source(),[10,10]+[1]*6+[10]*6)
        actual,=help_steps(result)
        helper,ally=actual.source.source.party
        helper=replace(helper,talents=tuple(t for t in helper.talents if t.id is not TalentId.ALLIES_IN_ARMS))
        changed=replace(actual.source.source,party=(helper,with_allies(ally)))
        prepared=replace(actual.source,source=changed)
        self.assertIsNone(build_allies_in_arms_application(prepared,actual.proof.execution))
        with self.assertRaises(ValueError):
            PcMeleeStep(prepared,actual.proof)


if __name__=='__main__':
    unittest.main()
