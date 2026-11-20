"""Deterministic medical receipts, actual hands and independent Wound sources."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.unit.test_k1_combat_surgeon_treatment import untreated_state,completed_treatment,combat_surgeon_request
from tests.unit.test_k1_combat_surgeon_battle_surgery import surgery_request,surgical_state
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.pc_medical_models import (
    MedicalHandUse,PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,PcMedicalSuppressionProof,
    PcMedicalSurgeryProof,build_medical_treatment,complete_medical_treatment,
    complete_medical_suppression,complete_medical_surgery,medical_hand_use,
    medical_condition_snapshots,medical_action_injury,medical_surgery_progress,
    expected_medical_treatment_application,effective_medical_injury,
)
from towr.domain._pc_medical_projection import project_medical_step
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcFateDecline
from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand
from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import (CharacterInjuryState,WoundConditionEffect,WoundEffectDuration,
    WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction)
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.weapon_inventory_models import WeaponItemLocation,WeaponGrip
from towr.domain.turn_models import (CombatActionKind,CombatTurnStartRequest,CombatActionSlotRequest,
    CombatActionDeclaration,ActionSlotGrant)
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot
from towr.rules.test_resolution import resolve_test


def medical_state(*,anatomy=True,injury=None,body_facts=()):
    source=make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD)
    member=source.party[0]
    definition=replace(member.pc,reason=3,recall=5,initiative=3,dexterity=5,
        medical=MedicalPreparationFacts(anatomy,True,True,(WoundEntryId.SEVERED_ARM,),makeshift_modifier=None if anatomy else -1),
        tools=(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,1,WeaponItemLocation.CARRIED,None),))
    source=replace(source,party=(replace(member,pc=definition),))
    state=initial_pc_melee_state(source)
    if injury is not None:state=replace(state,party=(replace(state.party[0],injury=injury,body_facts=body_facts),))
    clock=start_combat_turn(CombatTurnStartRequest('turn',state.round_state,'pc')).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('reserve',clock,'pc',
        CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock)


def append_updates(state,proof):
    return replace(state,**project_medical_step(state,proof),history=(*state.history,proof))


class MedicalModelsTests(unittest.TestCase):
    def test_physickers_kit_without_required_lore_does_not_remove_gm_difficulty(self):
        from towr.domain.pc_medical_tactics import medical_actions
        state=medical_state(anatomy=False,injury=untreated_state())
        request=build_medical_treatment(state,'pc',1)
        self.assertIn(('RULE-EQUIPMENT-TOOLS:makeshift-medical',-1),
            tuple((m.rule_id,m.amount) for m in request.test.dice_modifiers))
        source=state.source.party[0]
        facts=replace(source.pc.medical,makeshift_modifier=None)
        source=replace(state.source,party=(replace(source,pc=replace(source.pc,medical=facts)),))
        state=replace(state,source=source)
        with self.assertRaises(ValueError):build_medical_treatment(state,'pc',1)
        self.assertEqual(medical_actions(state,'pc'),())

    def test_actual_anatomy_and_kit_circumvent_improvised_penalty_without_bonus(self):
        from towr.domain.pc_medical_models import medical_test
        from towr.domain.test_models import Skill
        state=medical_state(injury=untreated_state())
        test=medical_test(state,'pc','advice:kit:recall',Skill.RECALL)
        self.assertFalse(any(m.rule_id=='RULE-EQUIPMENT-TOOLS:makeshift-medical' for m in test.dice_modifiers))

    def test_preparation_is_not_derived_from_lore_or_talent_and_validates_exact_fields(self):
        for changes in (dict(anatomy_lore=1),dict(self_treatment_modifier=True),
                dict(makeshift_modifier=0),dict(recovery_supports=(WoundEntryId.SEVERED_ARM,)*2)):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(MedicalPreparationFacts(False,True,False),**changes)

    def test_real_anatomy_treatment_spends_action_then_applies_once_without_healing(self):
        state=medical_state(injury=untreated_state())
        request=build_medical_treatment(state,'pc',1)
        self.assertIsNone(request.test)
        self.assertEqual(request.hand_use.hands,(WeaponGrip.RIGHT,))
        execution=complete_medical_treatment(request)
        after=append_updates(state,PcMedicalTreatmentProof(request,execution))
        self.assertIsNotNone(after.round_state.active_turn.action_slots[0].execution)
        self.assertFalse(after.party[0].injury.wounds[0].treated)
        pending=expected_medical_treatment_application(after)
        from towr.rules.recover_resolution import apply_recover_wound_treatment
        applied=PcMedicalTreatmentApplicationProof(apply_recover_wound_treatment(pending))
        final=append_updates(after,applied)
        self.assertTrue(final.party[0].injury.wounds[0].treated)
        self.assertFalse(final.party[0].injury.wounds[0].healed)
        self.assertFalse(final.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(final.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertIsNone(expected_medical_treatment_application(final))
        with self.assertRaises(ValueError):project_medical_step(final,applied)

    def test_ordinary_recall_failed_treatment_still_spends_action_without_application(self):
        state=medical_state(anatomy=False,injury=untreated_state())
        request=build_medical_treatment(state,'pc',1)
        test=resolve_test(request.test,SequenceRandom([10]*3))
        execution=complete_medical_treatment(request,test)
        self.assertIsNone(execution.resolution.treatment)
        self.assertIsNotNone(execution.slot.execution)
        self.assertFalse(execution.resolution.automatically_succeeded)

    def test_real_recall_consumes_next_test_grim_before_its_self_treatment_application(self):
        original=untreated_state()
        injury=replace(original,wounds=(*original.wounds,
            WoundRecord(3,WoundEntryId.CRUSHED_RIB,10,(10,),effect_resolved=True)),
            active_wound_effects=(*original.active_wound_effects,
                WoundRestrictionEffect(3,WoundRestriction.NEXT_TEST_IS_GRIM,WoundEffectDuration.NEXT_TEST)))
        state=medical_state(anatomy=False,injury=injury)
        request=build_medical_treatment(state,'pc',1)
        self.assertNotIn(injury.active_wound_effects[-1],request.recover.choice.injury_state.active_wound_effects)
        test=resolve_test(request.test,SequenceRandom([1]*6))
        decline=PcFateDecline('pc',request.test.id,'test',state.source.participant('pc').fate_policy)
        proof=PcMedicalTreatmentProof(request,complete_medical_treatment(request,test),decline)
        after=append_updates(state,proof)
        self.assertEqual(expected_medical_treatment_application(after).injury_state,
            after.participant('pc').injury)

    def test_anatomy_auto_treatment_does_not_consume_next_test_restriction(self):
        original=untreated_state()
        effect=WoundRestrictionEffect(3,WoundRestriction.NEXT_TEST_IS_GRIM,WoundEffectDuration.NEXT_TEST)
        injury=replace(original,wounds=(*original.wounds,
            WoundRecord(3,WoundEntryId.CRUSHED_RIB,10,(10,),effect_resolved=True)),
            active_wound_effects=(*original.active_wound_effects,effect))
        state=medical_state(injury=injury)
        request=build_medical_treatment(state,'pc',1)
        after=append_updates(state,PcMedicalTreatmentProof(request,complete_medical_treatment(request)))
        self.assertIn(effect,after.participant('pc').injury.active_wound_effects)

    def test_medical_tactics_use_actual_wounds_not_profile_hp(self):
        from towr.domain.pc_medical_tactics import medical_actions,MedicalActionKind
        state=medical_state(injury=untreated_state())
        choice=medical_actions(state,'pc')[0]
        self.assertEqual((choice.kind,choice.target_id,choice.wound_sequence,choice.required_hands),
            (MedicalActionKind.TREATMENT,'pc',1,1))
        self.assertFalse(choice.requires_preparation)
        self.assertEqual(medical_actions(medical_state(),'pc'),())

    def test_dropped_kit_is_unavailable_and_makeshift_does_not_teleport_it(self):
        state=medical_state(injury=untreated_state())
        member=state.party[0];item=member.tool_inventory.items[0]
        tools=replace(member.tool_inventory,items=(replace(item,location=WeaponItemLocation.DROPPED,dropped_zone_id='arena'),))
        # A read-only decision view of a true physical drop, without fabricating its journal receipt.
        view=SimpleNamespace(**{name:getattr(state,name) for name in state.__dataclass_fields__})
        view.party=(replace(member,tool_inventory=tools),)
        view.participant=lambda actor:view.party[0] if actor=='pc' else state.participant(actor)
        view.enemy=state.enemy
        with self.assertRaises(ValueError):build_medical_treatment(view,'pc',1)

    def test_actual_injured_hand_critical_is_independent_of_other_selected_wound(self):
        injury=CharacterInjuryState((
            WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(10,2),effect_resolved=True),
            WoundRecord(2,WoundEntryId.SLASHED_FOREARMS,16,(10,6),effect_resolved=True)),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_HEALED),))
        facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.RIGHT),
            PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,2,PcWeaponHand.LEFT))
        state=medical_state(injury=injury,body_facts=facts)
        hand=medical_hand_use(state,'pc')
        self.assertEqual(hand.hands,(WeaponGrip.RIGHT,))
        actual=medical_action_injury(state,'pc',hand,CombatActionKind.RECOVER)
        self.assertIn(WoundConditionEffect(1,Condition.CRITICALLY_INJURED,WoundEffectDuration.UNTIL_TREATED),
            actual.active_wound_effects)
        second=replace(actual,active_wound_effects=(*actual.active_wound_effects,
            WoundConditionEffect(2,Condition.CRITICALLY_INJURED,WoundEffectDuration.UNTIL_TREATED)))
        state=replace(state,party=(replace(state.party[0],injury=second),))
        removed=tuple(e for e in second.active_wound_effects if e.wound_sequence==2)
        self.assertEqual(medical_condition_snapshots(state,'pc',second,removed)[0].has_other_active_source,True)

    def test_additional_recall_is_real_and_failure_consumes_single_treatment(self):
        request=combat_surgeon_request(completed_treatment(untreated_state()))
        success=complete_medical_suppression(request,resolve_test(request.recall_test,SequenceRandom([1,10])))
        self.assertIsNotNone(success.suppression)
        self.assertEqual(success.state,request.injury_state)
        failure=complete_medical_suppression(request,resolve_test(request.recall_test,SequenceRandom([10,10])))
        self.assertIsNone(failure.suppression)
        self.assertIn(request.treatment.request_id,failure.consumed_treatment_result_ids)

    def test_surgery_progress_rebases_only_same_wound_and_zero_success_preserves_work(self):
        source=surgical_state()
        first=surgery_request(1,source)
        result=complete_medical_surgery(first,resolve_test(first.dexterity_test,SequenceRandom([1,1,10])))
        self.assertEqual(result.progress.exacting.accumulated_successes,2)
        hand=MedicalHandUse('surgeon',(WeaponGrip.LEFT,WeaponGrip.RIGHT),'kit')
        history=(PcMedicalSurgeryProof(first,hand,result),)
        additional=replace(source,wounds=(*source.wounds,WoundRecord(2,WoundEntryId.SUPERFICIAL_INJURY,1,(1,),effect_resolved=True)))
        rebased=medical_surgery_progress(SimpleNamespace(history=history),'surgeon','surgeon',1,additional)
        self.assertEqual(rebased.exacting.accumulated_successes,2)
        self.assertEqual(rebased.injury_state,additional)
        second=surgery_request(2,additional,progress=rebased)
        failed=complete_medical_surgery(second,resolve_test(second.dexterity_test,SequenceRandom([10,10,10])))
        self.assertEqual(failed.progress.exacting.accumulated_successes,2)
        self.assertIsNotNone(failed.failure_risk)
        replaced=replace(additional,wounds=(replace(additional.wounds[0],entry_id=WoundEntryId.SEVERED_LEG,table_total=21,
            roll_values=(10,10,1)),additional.wounds[1]))
        with self.assertRaises(ValueError):medical_surgery_progress(SimpleNamespace(history=history),'surgeon','surgeon',1,replaced)


if __name__=='__main__':unittest.main()
