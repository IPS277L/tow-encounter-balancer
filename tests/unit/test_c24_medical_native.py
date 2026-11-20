"""Native medical receipts; boundary surgical patients are explicitly prepared.

The Champion treatment case runs and replays the entire original encounter.
Surgery cases isolate real reserved actions and never claim an invented battle
prefix or manufacture a Test/progress result.
"""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import paid_talent
from tests.unit.test_c24_champion_native import champion_scenario
from tests.unit.test_k1_combat_surgeon_battle_surgery import surgical_state
from towr.domain.combat_surgeon_models import COMBAT_SURGEON_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcMeleeStep,PcFateDecline
from towr.domain.pc_medical_models import (PcMedicalTreatmentProof,PcMedicalSuppressionProof,
    PcMedicalSurgeryProof,PcMedicalRiskProof,build_medical_surgery,complete_medical_surgery,
    expected_medical_risk,effective_medical_injury)
from towr.domain.surgery_failure_resolution_models import SurgeryRiskPolicy,SurgeryFailureOutcome
from towr.domain.talent_catalog import TalentId
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.turn_models import (CombatActionDeclaration,CombatActionKind,ImproviseKind,
    CombatActionSlotRequest,ActionSlotGrant,CombatTurnStartRequest,CombatRoundState)
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.test_resolution import resolve_test
from towr.rules.surgery_failure_resolution import resolve_surgery_failure
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def kit(location=WeaponItemLocation.CARRIED):
    return ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,2,location,
        WeaponGrip.BOTH if location is WeaponItemLocation.HELD else None)


def treatment_source(*,rounds):
    from towr.domain.generated_npc_models import GeneratedWeapon
    source=champion_scenario(party_size=2,rounds=rounds,weapon=GeneratedWeapon.AXE,shield=True)
    npc=replace(source.enemies[0].definition.generated_components,toughness=1,endurance=2,
        reason=3,recall=5,initiative=3,
        dexterity=5,medical=MedicalPreparationFacts(True,True,False),
        talents=(paid_talent(TalentId.COMBAT_SURGEON),),tools=(kit(),))
    return replace(source,enemies=(npc.participant('minion1'),))


def treatment_rng():
    return SequenceRandom([1]*4+[10]*2+[1]+[1]*4+[10]*2+[7,7]+[1]*400)


def reserve_surgery(state,actor,round_number=1):
    clock=CombatRoundState(round_number,state.round_state.participants)
    if actor in state.source.enemy_activation_order:
        clock=replace(clock,completed_turn_entity_ids=state.source.pc_activation_order)
    clock=start_combat_turn(CombatTurnStartRequest(f'boundary:r{round_number}:start',clock,actor)).state
    state=replace(state,round_state=clock)
    from towr.domain.pc_medical_tactics import PcMedicalIntentProof,MedicalActionKind,medical_actions
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    choice=next(choice for choice in medical_actions(state,actor) if choice.kind is MedicalActionKind.SURGERY)
    state=PcMeleeStep(state,PcMedicalIntentProof(actor,pc_melee_action_id(state,actor),choice)).state
    declaration=CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.ABILITY,improvise_approach_id=COMBAT_SURGEON_RULE_ID)
    reserved=reserve_combat_action_slot(CombatActionSlotRequest(pc_melee_action_id(state,actor)+':reserve',state.round_state,
        actor,declaration,ActionSlotGrant.STANDARD))
    return PcMeleeStep(state,reserved).state


def boundary_pc_surgery(*,glorious=False):
    source=champion_scenario(party_size=2,rounds=5)
    surgeon=source.party[0]
    facts=MedicalPreparationFacts(True,True,True,(WoundEntryId.SEVERED_ARM,))
    surgeon=replace(surgeon,pc=replace(surgeon.pc,weapon=PcMeleeWeapon.UNARMED,brawn=5,
        reason=3,recall=5,initiative=3,dexterity=5,
        medical=facts,tools=(kit(WeaponItemLocation.HELD),)),talents=(paid_talent(TalentId.COMBAT_SURGEON),),
        initial_weapon_hand=None,combat_equipment=())
    if glorious:
        from towr.domain.pc_melee_models import PcFatePolicy,PcGloriousPolicy
        from towr.domain.test_models import Skill
        surgeon=replace(surgeon,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.DEXTERITY,),0,0))
    source=replace(source,party=(surgeon,source.party[1]),
        surgery_risk=SurgeryRiskPolicy('gm:explicit-risk',1,1,1,'Permanent surgical scarring'))
    state=initial_pc_melee_state(source)
    # A previously sustained surgical Wound is an explicit patient boundary.
    state=replace(state,party=(state.party[0],replace(state.party[1],injury=surgical_state())))
    return reserve_surgery(state,'pc1')


def boundary_npc_surgery():
    """Stable treated Champion leg loss with a genuine registered Wound receipt."""
    from towr.domain.weapon_inventory_models import WeaponItemSource
    from towr.domain.weapon_catalog import WeaponKind
    from towr.domain.injury_models import (CharacterWoundRequest,CharacterWoundType,FixedWoundSelection,
        WoundEffectDuration)
    from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleRollRequest,CharacterWoundLifecycleCompletionRequest
    from towr.rules.wound_lifecycle_resolution import roll_character_wound_lifecycle,complete_character_wound_lifecycle
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
    from towr.domain.pc_melee_models import PcWeaponHand
    source=champion_scenario(rounds=4)
    npc=replace(source.enemies[0].definition.generated_components,reason=3,recall=5,initiative=3,dexterity=5,
        brawn=4,weapons=(WeaponItemSource('staff',WeaponKind.STAFF,WeaponItemLocation.CARRIED,None),),
        medical=MedicalPreparationFacts(True,False,True,(WoundEntryId.SEVERED_LEG,)),
        talents=(paid_talent(TalentId.COMBAT_SURGEON),),tools=(kit(WeaponItemLocation.HELD),))
    source=replace(source,enemies=(npc.participant('minion1'),),
        surgery_risk=SurgeryRiskPolicy('gm:explicit-risk',1,1,1,'Permanent surgical scarring'))
    state=initial_pc_melee_state(source);enemy=state.enemy('minion1')
    roll=roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest('boundary:wound','minion1',
        CharacterWoundRequest('boundary:wound:roll',enemy.state.injury,CharacterWoundType.CHAMPION,
            fixed_entry=FixedWoundSelection(WoundEntryId.SEVERED_LEG,21,'gm:boundary-patient'))),SequenceRandom([]))
    completed=complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest('boundary:wound:complete',
        roll,roll.wound_result.state,state.npc_champions[0].daily_wounds,daily_registration_id='boundary:wound:daily'))
    # The operation boundary follows treatment; it preserves permanent leg loss.
    injury=replace(completed.state,wounds=tuple(replace(w,treated=True) for w in completed.state.wounds),
        conditions=completed.state.conditions.without_condition(Condition.DEFENCELESS).without_condition(Condition.CRITICALLY_INJURED),
        active_wound_effects=tuple(e for e in completed.state.active_wound_effects if e.duration is not WoundEffectDuration.UNTIL_TREATED))
    row=replace(state.npc_champions[0],daily_wounds=completed.daily_wounds,
        body_facts=(PcBodyFact(PcBodyFactKind.LOST_LEG,1,PcWeaponHand.LEFT),))
    state=replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=injury)),),
        npc_champions=(row,),history=(PcWoundCompletionProof(completed,None),))
    return reserve_surgery(state,'minion1')


class MedicalNativeTests(unittest.TestCase):
    def test_actual_champion_treatment_physical_preparation_and_suppression_replay(self):
        result=run_pc_melee_scenario(treatment_source(rounds=2),treatment_rng())
        self.assertIsNone(result.unsupported)
        self.assertEqual(replace(result),result)
        treatments=[s for s in result.steps if type(s.proof) is PcMedicalTreatmentProof]
        suppressions=[s for s in result.steps if type(s.proof) is PcMedicalSuppressionProof]
        self.assertTrue(treatments);self.assertTrue(suppressions)
        self.assertTrue(all(p.proof.decline is None and p.proof.glorious is None for p in (*treatments,*suppressions)))
        self.assertIsNotNone(suppressions[0].proof.result.suppression)
        self.assertFalse(effective_medical_injury(suppressions[0].state,'minion1').conditions.has(Condition.DRAINED))
        from towr.domain.pc_medical_equipment_models import PcMedicalEquipmentProof
        equips=[s.proof for s in result.steps if type(s.proof) is PcMedicalEquipmentProof]
        self.assertTrue(equips)
        self.assertTrue(equips[0].equipment.changes_equipment)
        from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
        first_suppression=result.steps.index(suppressions[0])
        self.assertTrue(any(type(s.proof) is PcNpcWeaponEquipProof and s.proof.actor_id=='minion1'
            for s in result.steps[first_suppression+1:]))

    def test_medical_npc_recover_is_observed_in_trial_and_summary(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult
        from towr.simulation.pc_melee_simulation import run_pc_melee_trial
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        request=PcMeleeSimulationRequest(treatment_source(rounds=2),42,1)
        record=run_pc_melee_trial(request,0,rng_factory=lambda seed:treatment_rng())
        self.assertEqual([(row.actor_id,row.count) for row in record.npc_recover_action_counts],[('minion1',1)])
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,(record,)))
        self.assertEqual(summary.npc_recover_action_counts,record.npc_recover_action_counts)

    def surgical_step(self,state,values):
        request,hands=build_medical_surgery(state,'pc2',1)
        test=resolve_test(request.dexterity_test,SequenceRandom(values))
        result=complete_medical_surgery(request,test)
        decline=PcFateDecline('pc1',request.dexterity_test.id,'test',state.source.participant('pc1').fate_policy)
        proof=PcMedicalSurgeryProof(request,hands,result,decline)
        return PcMeleeStep(state,proof)

    def test_real_surgery_accumulates_eight_from_final_test_receipts(self):
        state=boundary_pc_surgery()
        contributions=[]
        for round_number,values in ((1,[1,1,1]),(2,[1,1,1]),(3,[1,1,10])):
            if round_number>1:state=reserve_surgery(state,'pc1',round_number)
            step=self.surgical_step(state,values)
            contributions.append(step.proof.result.exacting.test_result.effective_successes)
            state=step.state
            self.assertTrue(state.round_state.active_turn.action_slots[-1].executed)
        final=step.proof.result
        self.assertEqual(contributions,[3,3,2])
        self.assertEqual(final.progress.exacting.accumulated_successes,8)
        self.assertIsNotNone(final.proof)
        self.assertEqual(len(final.progress.exacting.contributions),3)
        self.assertFalse(state.participant('pc2').injury.wounds[0].healed)

    def test_failed_native_surgery_requires_gm_draw_and_rejects_replay(self):
        for draw,outcome in ((2,SurgeryFailureOutcome.PERMANENT_DISFIGUREMENT),(3,SurgeryFailureOutcome.DEATH)):
            with self.subTest(draw=draw):
                step=self.surgical_step(boundary_pc_surgery(),[10,10,10])
                self.assertEqual(step.proof.result.progress.exacting.accumulated_successes,0)
                request=expected_medical_risk(step.state)
                self.assertIsNotNone(request)
                result=resolve_surgery_failure(request,SequenceRandom([draw]))
                risk_step=PcMeleeStep(step.state,PcMedicalRiskProof(request,result))
                self.assertIs(result.outcome,outcome)
                self.assertEqual(risk_step.state.participant('pc2').injury.dead,outcome is SurgeryFailureOutcome.DEATH)
                self.assertEqual(risk_step.state.participant('pc2').injury.wounds,step.state.participant('pc2').injury.wounds)
                with self.assertRaises((TypeError,ValueError)):PcMeleeStep(risk_step.state,risk_step.proof)

    def test_npc_surgery_uses_real_champion_patient_and_rejects_pc_fate(self):
        state=boundary_npc_surgery()
        request,hands=build_medical_surgery(state,'minion1',1)
        result=complete_medical_surgery(request,resolve_test(request.dexterity_test,SequenceRandom([1,1,1])))
        proof=PcMedicalSurgeryProof(request,hands,result)
        projected=PcMeleeStep(state,proof)
        self.assertEqual(result.progress.exacting.accumulated_successes,3)
        self.assertEqual(projected.state.party,state.party)
        self.assertIsNone(proof.decline);self.assertIsNone(proof.glorious)
        with self.assertRaises(ValueError):
            PcMeleeStep(state,replace(proof,decline=PcFateDecline('pc',request.dexterity_test.id,'test',state.source.party[0].fate_policy)))

    def test_pc_surgery_glorious_uses_final_reroll_and_spends_fate_once(self):
        from towr.engine.pc_melee_runner import _resolve_pc_test
        from towr.domain.test_models import Skill
        state=boundary_pc_surgery(glorious=True)
        request,hands=build_medical_surgery(state,'pc2',1)
        test,decline,glorious,effective=_resolve_pc_test(state,'pc1',Skill.DEXTERITY,
            request.dexterity_test,SequenceRandom([10,10,10,1,1,1]),None)
        result=complete_medical_surgery(replace(request,dexterity_test=effective),test)
        proof=PcMedicalSurgeryProof(request,hands,result,decline,glorious)
        step=PcMeleeStep(state,proof)
        self.assertEqual(test.trace.initial_values,(10,10,10))
        self.assertEqual(result.progress.exacting.accumulated_successes,3)
        self.assertIsNone(result.failure_risk)
        self.assertIsNotNone(glorious);self.assertIsNone(decline)
        self.assertEqual(step.state.participant('pc1').fate.remaining_spends,
            state.participant('pc1').fate.remaining_spends-1)
        with self.assertRaises((TypeError,ValueError)):PcMeleeStep(state,replace(proof,glorious=None))
        with self.assertRaises((TypeError,ValueError)):PcMeleeStep(step.state,proof)


if __name__=='__main__':unittest.main()
