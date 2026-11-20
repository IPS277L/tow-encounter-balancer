"""Source-bound native medical transitions; the caller appends the proof once."""
from dataclasses import replace

from towr.domain.pc_medical_models import (
    MEDICAL_PROOFS,PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,
    PcMedicalSuppressionProof,PcMedicalSurgeryProof,PcMedicalRiskProof,
    build_medical_treatment,complete_medical_treatment,expected_medical_treatment_application,
    expected_medical_suppression,complete_medical_suppression,build_medical_surgery,
    complete_medical_surgery,expected_medical_risk,medical_action_injury,medical_raw_body,
    medical_hand_use,pending_medical_work,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionKind
from towr.domain.injury_models import CharacterInjuryState,WoundRestrictionEffect,WoundRestriction


def _same(actual,expected):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual!=expected:
        raise ValueError('medical proof changed its actual patient, source, Test, supplies, hands or clock')
    validate_pc_melee_source_types(actual,expected)


def _test(state,actor,skill,request,result,decline,glorious):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        return validate_pc_test_fate(state,actor,skill,request,result,decline,glorious)
    if decline is not None or glorious is not None:
        raise ValueError('an NPC medical Test cannot spend PC Fate')
    from towr.domain.pc_melee_result_models import _test_result
    _test_result(request,result)
    return request,None


def medical_injury_updates(state,actor,injury,*,fate=None):
    """Apply one raw body update without erasing independent source banks."""
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _party_update
        return dict(party=_party_update(state,actor,injury=injury,**({} if fate is None else dict(fate=fate))))
    from towr.domain.pc_npc_champion_models import is_npc_champion,npc_champion_updates
    if is_npc_champion(state,actor):
        return npc_champion_updates(state,actor,injury=injury)
    from towr.domain.pc_actor_models import pc_actor_npc_update
    return pc_actor_npc_update(state,actor,injury=injury)


def _after_test(state,actor):
    injury=medical_raw_body(state,actor).injury
    if type(injury) is not CharacterInjuryState:return injury
    return replace(injury,active_wound_effects=tuple(effect for effect in injury.active_wound_effects
        if not (type(effect) is WoundRestrictionEffect and effect.restriction is WoundRestriction.NEXT_TEST_IS_GRIM)))


class _MedicalView:
    """Uncommitted canonical updates, used only while building one transition."""
    def __init__(self,state,updates): self.base=state;self.updates=updates
    def __getattr__(self,name): return self.updates.get(name,getattr(self.base,name))
    def participant(self,actor): return next(row for row in self.party if row.actor_id==actor)
    def enemy(self,actor): return next(row for row in self.enemies if row.state.actor_id==actor)


def _apply_suppression(state,proof,updates):
    """Suspend active effects, retaining the Wound and original effects receipt.

    The live injury owns effective effects. The completed suppression owns the
    original suspended effects until this battle ends; no second health owner
    or instantaneous healing is introduced.
    """
    if proof.result.suppression is None:return updates
    from towr.domain.pc_medical_models import medical_effective_body
    view=_MedicalView(state,dict(updates,history=(*state.history,proof)))
    target=proof.request.target_id
    body=medical_effective_body(view,target)
    timed=tuple(row for row in body.timed_wounds if row.effect in body.injury.active_wound_effects)
    if target in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _party_update
        from towr.domain.pc_shield_models import PcShieldLocation
        from towr.domain.pc_heavy_wound_models import usable_hands
        body=replace(body,timed_wounds=timed)
        if (body.shield is not None and body.shield.location is PcShieldLocation.UNAVAILABLE
                and body.shield.hand in usable_hands(body)
                and body.weapon_inventory.shield_hand is not None):
            body=replace(body,shield=replace(body.shield,location=PcShieldLocation.HELD))
        updates['party']=_party_update(view,target,injury=body.injury,body_facts=body.body_facts,
            timed_wounds=timed,shield=body.shield)
    else:
        from towr.domain.pc_npc_champion_models import npc_champion_updates
        updates.update(npc_champion_updates(view,target,body=replace(body,timed_wounds=timed)))
    return updates


def project_medical_step(state,proof):
    """Return canonical field updates only; PcMeleeStep owns journal append."""
    if type(proof) not in MEDICAL_PROOFS:raise TypeError('unknown medical proof variant')
    replace(proof)
    pending=pending_medical_work(state)
    if type(proof) is PcMedicalTreatmentApplicationProof:
        from towr.rules.recover_resolution import apply_recover_wound_treatment
        expected=expected_medical_treatment_application(state)
        if expected is None or pending!=expected:raise ValueError('no immediate actual treatment awaits application')
        canonical=apply_recover_wound_treatment(expected)
        _same(proof.result,canonical)
        return medical_injury_updates(state,canonical.target_id,canonical.state)
    if type(proof) is PcMedicalSuppressionProof:
        expected=expected_medical_suppression(state)
        if expected is None or pending!=expected:raise ValueError('no unused successful treatment permits surgeon Recall')
        _same(proof.request,expected)
        effective,fate=_test(state,expected.surgeon_id,Skill.RECALL,expected.recall_test,
            proof.result.recall_test_result,proof.decline,proof.glorious)
        canonical=complete_medical_suppression(replace(expected,recall_test=effective),proof.result.recall_test_result)
        _same(proof.result,canonical)
        updates=medical_injury_updates(state,expected.surgeon_id,_after_test(state,expected.surgeon_id),fate=fate)
        return _apply_suppression(state,proof,updates)
    if type(proof) is PcMedicalRiskProof:
        from towr.domain.surgery_failure_resolution_models import SurgeryFailureResolutionResult,_expected_surgery_failure
        expected=expected_medical_risk(state)
        if expected is None or pending!=expected:raise ValueError('no unused failed surgical Test permits a risk outcome')
        _same(proof.request,expected)
        outcome,injury,disfigurement,consumed=_expected_surgery_failure(expected,proof.result.draw)
        canonical=SurgeryFailureResolutionResult(expected,proof.result.draw,outcome,injury,disfigurement,consumed)
        _same(proof.result,canonical)
        target=expected.surgery.source_request.target_id
        updates=medical_injury_updates(state,target,injury)
        turn=state.round_state.active_turn
        if injury.dead and (turn is None or turn.actor_id!=target):
            from towr.domain._pc_warped_form_projection import _exclude
            updates['round_state']=_exclude(state.round_state,target)
        return updates
    if pending is not None:raise ValueError('medical continuation must finish before a new action')
    if type(proof) is PcMedicalTreatmentProof:
        expected=build_medical_treatment(state,proof.request.target_id,proof.request.recover.choice.wound_sequence)
        _same(proof.request,expected)
        actor=expected.actor_id;test=proof.execution.resolution.test_result;fate=None
        effective=expected
        if expected.test is not None:
            selected,fate=_test(state,actor,Skill.RECALL,expected.test,test,proof.decline,proof.glorious)
            effective=replace(expected,recover=replace(expected.recover,choice=replace(expected.recover.choice,recall_test=selected)))
        elif proof.decline is not None or proof.glorious is not None:
            raise ValueError('automatic Anatomy treatment has no Fate Test window')
        canonical=complete_medical_treatment(effective,test)
        _same(proof.execution,canonical)
        injury=medical_action_injury(state,actor,expected.hand_use,CombatActionKind.RECOVER,
            consume_test=expected.test is not None)
        return dict(**medical_injury_updates(state,actor,injury,fate=fate),round_state=canonical.round_state)
    expected,hand=build_medical_surgery(state,proof.request.target_id,proof.request.wound_sequence)
    _same(proof.request,expected);_same(proof.hand_use,hand)
    actor=expected.surgeon_id;test=proof.result.exacting.test_result
    effective,fate=_test(state,actor,Skill.DEXTERITY,expected.dexterity_test,test,proof.decline,proof.glorious)
    canonical=complete_medical_surgery(replace(expected,dexterity_test=effective),test)
    _same(proof.result,canonical)
    injury=medical_action_injury(state,actor,hand,CombatActionKind.IMPROVISE,consume_test=True)
    return dict(**medical_injury_updates(state,actor,injury,fate=fate),round_state=canonical.round_state)
