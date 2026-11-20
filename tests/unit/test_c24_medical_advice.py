"""Deterministic medical forecasts, separate from native execution receipts."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.unit.test_c24_champion_native import champion_scenario
from tests.unit.test_c24_medical_native import kit
from tests.support.talent_sources import paid_talent
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import (CharacterInjuryState,WoundRecord,WoundEntryId,
    WoundConditionEffect,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration)
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.pc_medical_advice import (MedicalAdviceView,choose_compared_medical_action,
    _treated_view,_turns,_success,_after_medical_test)
from towr.domain.pc_medical_tactics import medical_actions
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatTurnStartRequest
from towr.rules.turn_resolution import start_combat_turn


def prepared(*,urgent=False,strong=False,anatomy=True,rounds=3):
    source=champion_scenario(party_size=2,rounds=rounds)
    surgeon=source.party[0]
    surgeon=replace(surgeon,pc=replace(surgeon.pc,reason=3,recall=5,
        medical=MedicalPreparationFacts(anatomy,True,False,makeshift_modifier=None if anatomy else -1),
        tools=(kit(),),weapon_skill=5 if strong else 1,melee=10 if strong else 2,
        strength=10 if strong else 1),policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        talents=(paid_talent(TalentId.COMBAT_SURGEON),) if anatomy else ())
    patient=replace(source.party[1],policy=PcMeleePolicy.AUTOMATIC_COMBAT)
    source=replace(source,party=(surgeon,patient))
    state=initial_pc_melee_state(source)
    durations=WoundEffectDuration
    effects=(WoundConditionEffect(1,Condition.DRAINED,durations.UNTIL_HEALED),
        WoundRestrictionEffect(1,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,durations.UNTIL_HEALED))
    conditions=ConditionState(frozenset((Condition.DRAINED,)))
    if urgent:
        effects=(*effects,WoundConditionEffect(1,Condition.CRITICALLY_INJURED,durations.UNTIL_TREATED),
            WoundConditionEffect(1,Condition.DEFENCELESS,durations.UNTIL_TREATED))
        conditions=conditions.with_condition(Condition.CRITICALLY_INJURED).with_condition(Condition.DEFENCELESS)
    injury=CharacterInjuryState((WoundRecord(1,WoundEntryId.INTERNAL_INJURY,14,(7,7),effect_resolved=True),),
        conditions=conditions,active_wound_effects=effects)
    state=replace(state,party=(state.party[0],replace(state.party[1],injury=injury)))
    clock=start_combat_turn(CombatTurnStartRequest('boundary:doctor:start',state.round_state,'pc1')).state
    return replace(state,round_state=clock)


class MedicalAdviceTests(unittest.TestCase):
    def test_highly_effective_attack_beats_nonurgent_treatment(self):
        state=prepared(strong=True,urgent=False,rounds=1)
        before=deepcopy(state)
        self.assertIsNone(choose_compared_medical_action(state,'pc1'))
        self.assertEqual(state,before)

    def test_urgent_treatment_wins_without_inventing_a_healed_wound(self):
        state=prepared(urgent=True)
        advice=choose_compared_medical_action(state,'pc1')
        self.assertIsNotNone(advice)
        self.assertEqual(advice.choice.target_id,'pc2')
        self.assertGreater(advice.utility,advice.ordinary_utility)
        view=_treated_view(MedicalAdviceView(state),'pc2',1,suppress=True)
        injury=view.participant('pc2').injury
        self.assertFalse(injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(injury.conditions.has(Condition.DRAINED))
        self.assertTrue(injury.wounds[0].treated)
        self.assertFalse(injury.wounds[0].healed)
        self.assertEqual(injury.wounds[0].roll_values,(7,7))
        self.assertFalse(state.participant('pc2').injury.wounds[0].treated)

    def test_probabilities_use_actual_recall_pool_and_makeshift_penalty(self):
        state=prepared(anatomy=False)
        chance=_success(MedicalAdviceView(state),'pc1',Skill.RECALL,'probe:recall',target='pc2')
        self.assertAlmostEqual(chance,1.-.5**2)

    def test_forecast_consumes_only_actual_first_test_modifiers(self):
        from towr.domain.pc_magic_models import PcMagicModifier
        from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
        from towr.domain.pc_medical_models import medical_test
        state=prepared(anatomy=False)
        penalty=PcMagicModifier('miscast:next','pc1',PcMagicTaskKind.NEXT_TEST_PENALTY)
        other=PcMagicModifier('miscast:other','pc2',PcMagicTaskKind.NEXT_TEST_PENALTY)
        state=replace(state,magic_modifiers=(penalty,other))
        view=MedicalAdviceView(state)
        request=medical_test(view,'pc1','first',Skill.RECALL,target='pc2')
        self.assertIn(penalty.source_id,{modifier.rule_id for modifier in request.dice_modifiers})
        advanced=_after_medical_test(view,'pc1',request)
        second=medical_test(advanced,'pc1','second',Skill.RECALL,target='pc2')
        self.assertNotIn(penalty.source_id,{modifier.rule_id for modifier in second.dice_modifiers})
        self.assertEqual(advanced.magic_modifiers,(other,))
        self.assertEqual(state.magic_modifiers,(penalty,other))

    def test_missing_supplies_and_recursion_disable_medical_advice(self):
        state=prepared(urgent=True)
        source=state.source
        member=source.party[0]
        member=replace(member,pc=replace(member.pc,medical=replace(member.pc.medical,treatment_supplies=False)))
        without=replace(state,source=replace(source,party=(member,source.party[1])))
        self.assertIsNone(choose_compared_medical_action(without,'pc1'))
        self.assertIsNone(choose_compared_medical_action(MedicalAdviceView(state),'pc1'))

    def test_permanent_and_independent_condition_sources_survive(self):
        state=prepared(urgent=True)
        body=state.participant('pc2')
        permanent=WoundConditionEffect(3,Condition.BLINDED,WoundEffectDuration.PERMANENT)
        other_drained=WoundConditionEffect(2,Condition.DRAINED,WoundEffectDuration.UNTIL_HEALED)
        injury=replace(body.injury,wounds=(*body.injury.wounds,
            WoundRecord(2,WoundEntryId.INTERNAL_INJURY,14,(7,7),effect_resolved=True),
            WoundRecord(3,WoundEntryId.RUINED_EYES,23,(7,8,8),treated=True,effect_resolved=True)),
            active_wound_effects=(*body.injury.active_wound_effects,other_drained,permanent),
            conditions=body.injury.conditions.with_condition(Condition.BLINDED).with_condition(Condition.BURDENED))
        state=replace(state,party=(state.party[0],replace(body,injury=injury)))
        view=_treated_view(MedicalAdviceView(state),'pc2',1,suppress=True)
        self.assertIn(permanent,view.participant('pc2').injury.active_wound_effects)
        self.assertTrue(view.participant('pc2').injury.conditions.has(Condition.BLINDED))
        self.assertTrue(view.participant('pc2').injury.conditions.has(Condition.BURDENED))
        self.assertTrue(view.participant('pc2').injury.conditions.has(Condition.DRAINED))
        permanent_view=_treated_view(view,'pc2',3,suppress=True)
        self.assertIn(permanent,permanent_view.participant('pc2').injury.active_wound_effects)

    def test_horizon_does_not_offer_already_elapsed_turns(self):
        state=prepared(rounds=1)
        self.assertEqual(_turns(state,'pc1','pc1'),0)
        self.assertEqual(_turns(state,'pc2','pc1'),1)
        clock=replace(state.round_state,completed_turn_entity_ids=('pc2',))
        self.assertEqual(_turns(replace(state,round_state=clock),'pc2','pc1'),0)

    def test_numeric_npc_surgeon_compares_same_side_pc_patient(self):
        from towr.domain.turn_models import CombatSide
        from towr.domain.resolution_models import TargetInjuryPolicy
        from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
        from towr.domain.generated_npc_models import GeneratedWeapon
        from tests.support.generated_weapon_sources import initial_generated_weapons
        state=prepared(urgent=True)
        npc=replace(state.source.enemies[0].definition.generated_components,
            injury_policy=TargetInjuryPolicy.MINION,reason=3,recall=5,initiative=3,dexterity=5,
            weapon_skill=1,strength=2,melee=2,weapons=initial_generated_weapons(GeneratedWeapon.GREATAXE),
            medical=MedicalPreparationFacts(True,True,False),
            talents=(paid_talent(TalentId.COMBAT_SURGEON),),tools=(kit(),))
        source=replace(state.source,npc_allies=(npc.participant('surgeon',side=CombatSide.PLAYERS_AND_ALLIES),),
            enemy_target_priority=('pc1','pc2','surgeon'),npc_defeat_decisions=(
                MinionDefeatDecision('minion1','surgeon',NpcDefeatDisposition.KILLED,True),))
        fresh=initial_pc_melee_state(source)
        fresh=replace(fresh,party=(fresh.party[0],replace(fresh.party[1],injury=state.party[1].injury)))
        clock=replace(fresh.round_state,completed_turn_entity_ids=('pc1','pc2'))
        clock=start_combat_turn(CombatTurnStartRequest('boundary:npc-doctor:start',clock,'surgeon')).state
        fresh=replace(fresh,round_state=clock)
        advice=choose_compared_medical_action(fresh,'surgeon')
        self.assertIsNotNone(advice)
        self.assertEqual(advice.choice.target_id,'pc2')
        self.assertGreater(advice.utility,advice.ordinary_utility)
        from towr.domain.pc_medical_advice import _prepare,_ordinary
        changed,_=_prepare(MedicalAdviceView(fresh),'surgeon',advice.choice)
        self.assertFalse(changed.enemy('surgeon').state.wields_weapon)
        self.assertGreater(_ordinary(changed,'surgeon')[0],0.)

    def test_recovered_arm_restores_only_an_actually_held_shield(self):
        from towr.domain.pc_melee_models import (PcShieldLoadout,PcWeaponHand,
            PcShieldHandConflictPolicy,PcShieldRecoveryPolicy)
        from towr.domain.pc_shield_models import PcShieldState,PcShieldLocation
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.pc_weapon_inventory import replace_pc_member
        state=prepared()
        patient=replace(state.source.party[1],pc=replace(state.source.party[1].pc,weapon=PcMeleeWeapon.SWORD),
            initial_weapon_hand=PcWeaponHand.LEFT,shield=PcShieldLoadout(PcWeaponHand.RIGHT,
                PcShieldHandConflictPolicy.WEAPON_FIRST,PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK))
        source=replace(state.source,party=(state.source.party[0],patient))
        fresh=initial_pc_melee_state(source)
        injury=CharacterInjuryState((WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(8,8),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.INJURED_ARM_UNUSABLE,WoundEffectDuration.UNTIL_HEALED),))
        body=replace(fresh.party[1],injury=injury,body_facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),),
            shield=PcShieldState(PcShieldLocation.UNAVAILABLE,PcWeaponHand.RIGHT))
        fresh=replace(fresh,party=(fresh.party[0],body))
        recovered=_treated_view(MedicalAdviceView(fresh),'pc2',1,suppress=True)
        self.assertIs(recovered.participant('pc2').shield.location,PcShieldLocation.HELD)
        dropped=replace_pc_member(body,shield=PcShieldState(PcShieldLocation.DROPPED,None))
        missing=MedicalAdviceView(fresh,party=(fresh.party[0],dropped))
        self.assertIs(_treated_view(missing,'pc2',1,suppress=True).participant('pc2').shield.location,PcShieldLocation.DROPPED)

    def test_advice_does_not_draw_random_values_or_mutate_patient(self):
        from unittest.mock import patch
        state=prepared(urgent=True);before=deepcopy(state)
        with (patch('random.Random.randint',side_effect=AssertionError('advice drew RNG')),
                patch('random.randint',side_effect=AssertionError('advice drew global RNG'))):
            self.assertIsNotNone(choose_compared_medical_action(state,'pc1'))
        self.assertEqual(state,before)

    def test_critical_end_test_failure_probability_increases_urgency(self):
        state=prepared(urgent=True)
        def with_endurance(rating):
            member=replace(state.source.party[1],pc=replace(state.source.party[1].pc,endurance=rating))
            return replace(state,source=replace(state.source,party=(state.source.party[0],member)))
        weak=choose_compared_medical_action(with_endurance(1),'pc1')
        strong=choose_compared_medical_action(with_endurance(10),'pc1')
        self.assertIsNotNone(weak);self.assertIsNotNone(strong)
        self.assertGreater(weak.utility,strong.utility)

    def test_surgery_remains_available_without_instant_combat_healing_value(self):
        from tests.unit.test_c24_medical_native import boundary_pc_surgery
        state=boundary_pc_surgery()
        self.assertTrue(medical_actions(state,'pc1'))
        self.assertIsNone(choose_compared_medical_action(state,'pc1'))


if __name__=='__main__':unittest.main()
