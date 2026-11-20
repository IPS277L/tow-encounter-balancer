"""Native treatment, temporary suppression and surgical work, PG74/121–122.

The journal owns medical receipts. Physical preparation and true Character
injury remain separate; neither a Talent tag nor a profile HP loss is a patient.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (CharacterInjuryState,WoundConditionEffect,
    WoundRestrictionEffect,WoundEffectDuration,WoundRestriction,WoundConditionSourceSnapshot,
    HealingRequirement)
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.recover_models import (
    RecoverActionExecutionRequest,RecoverActionExecutionResult,RecoverMode,RecoverTreatWoundChoice,
    RecoverConditionTarget,RecoverTreatWoundResult,RecoverWoundTreatmentApplicationRequest,
    RecoverWoundTreatmentResolutionRequest,RecoverWoundTreatmentResolutionResult,_expected_recover_execution,
)
from towr.domain.combat_surgeon_models import (
    COMBAT_SURGEON_RULE_ID,CombatSurgeonTreatmentRequest,CombatSurgeonTreatmentResult,_expected_suppression,
)
from towr.domain.combat_surgeon_surgery_models import (
    CombatSurgeonBattleSurgeryActionRequest,CombatSurgeonBattleSurgeryActionResult,
    _source_progress,_exacting_request,_expected_proof,_expected_failure_risk,
)
from towr.domain.combat_surgeon_suppression_models import (
    CombatSurgeonSuppressionAggregate,CombatSurgeonEffectiveEffectsRequest,
)
from towr.domain.surgery_failure_resolution_models import (
    SurgeryFailureResolutionRequest,SurgeryFailureResolutionResult,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_test_source import validate_completed_talent_test
from towr.domain.test_models import TestRequest,TestResult,Skill,DiceModifier,QualityModifier,TestQuality
from towr.domain.tool_inventory_models import ToolKind
from towr.domain.turn_models import CombatActionKind,ActionExecutionReceipt
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation


def _id(value):
    if type(value) is not str or not value.strip(): raise TypeError('medical source IDs must be exact nonempty strings')


@dataclass(frozen=True,slots=True)
class MedicalHandUse:
    actor_id: str
    hands: tuple[WeaponGrip,...]
    kit_id: str|None

    def __post_init__(self):
        _id(self.actor_id)
        if (type(self.hands) is not tuple or len(self.hands) not in (1,2)
                or any(type(h) is not WeaponGrip or h is WeaponGrip.BOTH for h in self.hands)
                or len(set(self.hands))!=len(self.hands)):
            raise TypeError('medical use requires one or two distinct actual hands')
        if self.kit_id is not None: _id(self.kit_id)


@dataclass(frozen=True,slots=True)
class PcMedicalTreatmentRequest:
    recover: RecoverActionExecutionRequest
    hand_use: MedicalHandUse

    @property
    def actor_id(self): return self.recover.actor_id
    @property
    def target_id(self): return self.recover.choice.target.entity_id
    @property
    def id(self): return self.recover.id
    @property
    def test(self): return self.recover.choice.recall_test

    def __post_init__(self):
        if type(self.recover) is not RecoverActionExecutionRequest or type(self.hand_use) is not MedicalHandUse:
            raise TypeError('medical treatment requires its exact Recover and physical hand use')
        replace(self.recover);replace(self.hand_use)
        if self.recover.mode is not RecoverMode.TREAT_WOUND or self.actor_id!=self.hand_use.actor_id:
            raise ValueError('medical treatment cannot become another action or use another actor hands')


@dataclass(frozen=True,slots=True)
class PcMedicalTreatmentProof:
    request: PcMedicalTreatmentRequest
    execution: RecoverActionExecutionResult
    decline: object|None = None
    glorious: object|None = None


@dataclass(frozen=True,slots=True)
class PcMedicalTreatmentApplicationProof:
    result: RecoverWoundTreatmentResolutionResult


@dataclass(frozen=True,slots=True)
class PcMedicalSuppressionProof:
    request: CombatSurgeonTreatmentRequest
    result: CombatSurgeonTreatmentResult
    decline: object|None = None
    glorious: object|None = None


@dataclass(frozen=True,slots=True)
class PcMedicalSurgeryProof:
    request: CombatSurgeonBattleSurgeryActionRequest
    hand_use: MedicalHandUse
    result: CombatSurgeonBattleSurgeryActionResult
    decline: object|None = None
    glorious: object|None = None


@dataclass(frozen=True,slots=True)
class PcMedicalRiskProof:
    request: SurgeryFailureResolutionRequest
    result: SurgeryFailureResolutionResult


MEDICAL_PROOFS=(PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,PcMedicalSuppressionProof,
    PcMedicalSurgeryProof,PcMedicalRiskProof)


def medical_description(state,actor):
    if actor in state.source.pc_activation_order: return state.source.participant(actor).pc
    if actor in state.source.npc_activation_order: return state.enemy(actor).definition.generated_components
    return None


def medical_facts(state,actor):
    description=medical_description(state,actor)
    facts=None if description is None else description.medical
    if facts is not None:
        if type(facts) is not MedicalPreparationFacts: raise TypeError('medical actor needs its complete typed facts')
        replace(facts)
    return facts


def medical_raw_body(state,actor):
    if actor in state.source.pc_activation_order: return state.participant(actor)
    from towr.domain.pc_npc_champion_models import is_npc_champion,npc_champion_body
    if is_npc_champion(state,actor): return npc_champion_body(state,actor)
    enemy=state.enemy(actor)
    return SimpleNamespace(actor_id=actor,injury=enemy.state.injury,weapon_inventory=enemy.state.weapon_inventory,
        tool_inventory=enemy.state.tool_inventory,body_facts=(),shield=None)


def medical_suppressions(state):
    return CombatSurgeonSuppressionAggregate(state.source.id,tuple(p.result.suppression for p in state.history
        if type(p) is PcMedicalSuppressionProof and p.result.suppression is not None))


def medical_condition_snapshots(state,actor,injury,removed):
    from towr.domain.pc_medical_condition_sources import medical_external_conditions
    external=medical_external_conditions(state,actor)
    remaining=tuple(effect for effect in injury.active_wound_effects if effect not in removed)
    conditions=tuple(dict.fromkeys(effect.condition for effect in removed if type(effect) is WoundConditionEffect
        and injury.conditions.has(effect.condition)))
    return tuple(WoundConditionSourceSnapshot(condition,condition in external or any(
        type(effect) is WoundConditionEffect and effect.condition is condition for effect in remaining))
        for condition in conditions)


def effective_medical_injury(state,actor):
    """Read a prepared effective view without changing Wound records.

    A native suppression transition already suspends its active effects; its
    completed receipt retains the originals, so the normal live query is an
    identity. This also prepares that same transition before it is committed.
    """
    from towr.domain.pc_actor_models import pc_actor_injury
    raw=pc_actor_injury(state,actor)
    if type(raw) is not CharacterInjuryState: return raw
    aggregate=medical_suppressions(state)
    matching=tuple(s for s in aggregate.suppressions if s.target_id==actor
        and any(effect in raw.active_wound_effects for effect in s.suppressed_effects))
    if not matching: return raw
    aggregate=replace(aggregate,suppressions=matching)
    suppressed=tuple(effect for suppression in matching
        if not raw.wounds[suppression.wound_sequence-1].healed for effect in suppression.suppressed_effects
        if effect in raw.active_wound_effects)
    request=CombatSurgeonEffectiveEffectsRequest('medical:effective:'+actor,state.source.id,aggregate,
        actor,raw,medical_condition_snapshots(state,actor,raw,suppressed))
    from towr.rules.combat_surgeon_suppression_resolution import resolve_combat_surgeon_effective_effects
    result=resolve_combat_surgeon_effective_effects(request)
    return replace(raw,conditions=result.effective_conditions,active_wound_effects=result.effective_wound_effects)


def medical_effective_body(state,actor):
    body=medical_raw_body(state,actor)
    if type(body.injury) is not CharacterInjuryState: return body
    injury=effective_medical_injury(state,actor)
    from towr.domain.pc_heavy_wound_models import PcBodyFactKind
    raw=body.injury
    suppressed_sequences={effect.wound_sequence for effect in raw.active_wound_effects
        if effect not in injury.active_wound_effects}
    facts=tuple(fact for fact in body.body_facts if not (
        fact.wound_sequence in suppressed_sequences and fact.kind in
            (PcBodyFactKind.UNUSABLE_ARM,PcBodyFactKind.CLUTCH_STOMACH)))
    return replace(body,injury=injury,body_facts=facts)


def available_medical_kit(state,actor):
    from towr.domain.pc_tool_models import actor_tools
    return next((item for item in actor_tools(state,actor).items
        if item.kind is ToolKind.PHYSICKERS_KIT and item.location in
            (WeaponItemLocation.CARRIED,WeaponItemLocation.HELD)),None)


def medical_tool_penalty(state,actor):
    """PG98–99: the right kit circumvents difficulty with its required Lore.

    Without that knowledge, or without the kit, only the already explicit GM
    makeshift permission supplies a difficulty. Never invent its magnitude.
    """
    facts=medical_facts(state,actor)
    if facts is None:raise ValueError('medical tools require actual preparation')
    if available_medical_kit(state,actor) is not None and facts.anatomy_lore:return 0
    if facts.makeshift_modifier is None:
        raise ValueError('medical work requires its kit and Anatomy Lore or explicit GM improvised difficulty')
    return facts.makeshift_modifier


def medical_hand_use(state,actor,*,surgery=False):
    """Use only hands already available; preparation has its own physical owner."""
    from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands
    body=medical_effective_body(state,actor)
    kit=available_medical_kit(state,actor)
    used=set()
    inventory=body.weapon_inventory
    if inventory is None: return None
    for item in inventory.items:
        if item.location is WeaponItemLocation.HELD:
            used.update((WeaponGrip.LEFT,WeaponGrip.RIGHT) if item.grip is WeaponGrip.BOTH else (item.grip,))
    if inventory.shield_hand is not None: used.add(inventory.shield_hand)
    for item in body.tool_inventory.items:
        if kit is None or item.id!=kit.id: used.update(item.occupied_hands)
    if type(body.injury) is CharacterInjuryState:
        hands=tuple(WeaponGrip(hand.value) for hand in usable_hands(body))
        injured={WeaponGrip(hand.value) for hand in injured_hands(body)}
    else: hands=(WeaponGrip.LEFT,WeaponGrip.RIGHT);injured=set()
    free=tuple(sorted((hand for hand in hands if hand not in used),key=lambda hand:hand in injured))
    count=2 if surgery else 1
    return None if len(free)<count else MedicalHandUse(actor,free[:count],None if kit is None else kit.id)


def medical_action_injury(state,actor,hand_use,kind,*,consume_test=False):
    """Preserve raw effects while adding consequences of actual selected hand use."""
    body=medical_effective_body(state,actor)
    raw=medical_raw_body(state,actor).injury
    if type(raw) is not CharacterInjuryState: return raw
    from towr.domain.pc_heavy_wound_models import critical_for_action,critical_for_hand
    from towr.domain.pc_melee_models import PcWeaponHand
    after=critical_for_action(body,kind)
    for hand in hand_use.hands:
        after=critical_for_hand(replace(body,injury=after),PcWeaponHand(hand.value))
    added=tuple(effect for effect in after.active_wound_effects if effect not in body.injury.active_wound_effects)
    effects=tuple(dict.fromkeys((*raw.active_wound_effects,*added)))
    if consume_test:
        effects=tuple(effect for effect in effects if not (type(effect) is WoundRestrictionEffect
            and effect.restriction is WoundRestriction.NEXT_TEST_IS_GRIM))
    return replace(raw,active_wound_effects=effects,
        conditions=raw.conditions.with_condition(Condition.CRITICALLY_INJURED) if added else raw.conditions)


def medical_test(state,actor,identifier,skill,*,target=None):
    facts=medical_facts(state,actor)
    if facts is None: raise ValueError('medical Test needs the actual actor preparation')
    modifiers=tuple(DiceModifier(rule,amount) for rule,amount in (
        ('RULE-HEALTH-005:self-treatment',facts.self_treatment_modifier if target==actor else 0),
        ('RULE-EQUIPMENT-TOOLS:makeshift-medical',medical_tool_penalty(state,actor))) if amount)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        return _pc_test(state,actor,identifier,skill,modifiers,weapon_use=None)
    description=medical_description(state,actor)
    profile=description.recall_profile if skill is Skill.RECALL else description.dexterity_profile
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    md,mq=magic_test_modifiers(state,actor,skill)
    dice=(*md,*modifiers,*actor_armour_test_modifiers(state,actor,skill),
        *pc_npc_distraction_test_modifiers(state,actor,None))
    injury=effective_medical_injury(state,actor)
    if injury.conditions.has(Condition.BLINDED): mq=(*mq,QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM))
    if type(injury) is CharacterInjuryState and any(type(effect) is WoundRestrictionEffect
            and effect.restriction is WoundRestriction.NEXT_TEST_IS_GRIM for effect in injury.active_wound_effects):
        mq=(*mq,QualityModifier('RULE-HEALTH-005:crushed-rib-next-test',TestQuality.GRIM))
    if injury.conditions.has(Condition.DRAINED):
        dice=tuple(m for m in dice if m.amount<=0);mq=tuple(q for q in mq if q.quality is not TestQuality.GLORIOUS)
    from towr.domain.pc_oath_models import filter_honour_test
    return filter_honour_test(TestRequest(identifier,profile,dice,mq))


def _patient(state,actor,target,sequence):
    from towr.domain.pc_actor_models import pc_actor_side,pc_actor_injury
    if pc_actor_side(state,actor) is not pc_actor_side(state,target): raise ValueError('a medical patient must be self or ally')
    injury=pc_actor_injury(state,target)
    if type(injury) is not CharacterInjuryState or injury.dead: raise ValueError('medical patient needs a living actual table-Wound body')
    if type(sequence) is not int or not 1<=sequence<=len(injury.wounds): raise ValueError('medical patient requires an actual Wound number')
    wound=injury.wounds[sequence-1]
    if wound.healed or not wound.effect_resolved: raise ValueError('medical patient Wound must remain active and resolved')
    if actor!=target:
        from towr.domain.pc_battlefield_models import battlefield_range
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        close=(state.source.facts.all_opponents_close if state.battlefield is None else
            battlefield_range(state.battlefield,actor,target) is RangedWeaponRange.CLOSE)
        if not close: raise ValueError('medical ally must actually be in Close')
    return injury,wound


def build_medical_treatment(state,target,sequence):
    turn=state.round_state.active_turn
    if turn is None or not turn.action_slots: raise ValueError('medical treatment needs an actual reserved own action')
    actor=turn.actor_id;facts=medical_facts(state,actor)
    injury,wound=_patient(state,actor,target,sequence)
    if facts is None or not facts.treatment_supplies or wound.treated:
        raise ValueError('treatment requires real supplies and an untreated Wound')
    medical_tool_penalty(state,actor)
    hand=medical_hand_use(state,actor)
    if hand is None or hand.kit_id is None and facts.makeshift_modifier is None:
        raise ValueError('treatment needs its actual medical hand and tools or explicit makeshift supplies')
    after=medical_action_injury(state,actor,hand,CombatActionKind.RECOVER,consume_test=not facts.anatomy_lore)
    if actor==target: injury=after
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    identifier=pc_melee_action_id(state,actor)+':medical-treatment'
    test=None if facts.anatomy_lore else medical_test(state,actor,identifier+':recall',Skill.RECALL,target=target)
    choice=RecoverTreatWoundChoice(RecoverConditionTarget(target,injury.conditions,None if actor==target else True),
        injury,sequence,True,test,'anatomy' if facts.anatomy_lore else None)
    from towr.domain.pc_extinguish_models import _enemy_in_zone
    request=RecoverActionExecutionRequest(identifier,state.round_state,actor,after.conditions,
        _enemy_in_zone(state,actor),turn.action_slots[-1].index,RecoverMode.TREAT_WOUND,choice)
    return PcMedicalTreatmentRequest(request,hand)


def complete_medical_treatment(prepared,test=None):
    request=prepared.recover;choice=request.choice;automatic=choice.automatic_lore_id is not None
    if automatic and test is not None: raise ValueError('Anatomy treatment cannot invent a Recall roll')
    if not automatic: validate_completed_talent_test(choice.recall_test,test)
    success=automatic or test.succeeded
    app=(RecoverWoundTreatmentApplicationRequest(request.id+':treatment',request.id,request.actor_id,
        choice.target.entity_id,choice.injury_state,choice.wound_sequence,
        automatic_lore_id=choice.automatic_lore_id,source_test_id=None if automatic else test.trace.request_id) if success else None)
    return _expected_recover_execution(request,RecoverTreatWoundResult(choice,test,automatic,app))


def expected_medical_treatment_application(state):
    done={p.result.source_request.recover.request_id for p in state.history if type(p) is PcMedicalTreatmentApplicationProof}
    for proof in state.history:
        if type(proof) is not PcMedicalTreatmentProof or proof.execution.request_id in done: continue
        result=proof.execution
        if result.resolution.treatment is None: continue
        target=proof.request.target_id;injury=medical_raw_body(state,target).injury
        selected=result.resolution.treatment.wound_sequence
        removed=tuple(effect for effect in injury.active_wound_effects if effect.wound_sequence==selected
            and effect.duration is WoundEffectDuration.UNTIL_TREATED)
        return RecoverWoundTreatmentResolutionRequest(result.request_id+':apply',result,target,injury,
            medical_condition_snapshots(state,target,injury,removed),tuple(p.result.source_request.recover.resolution.treatment.id
                for p in state.history if type(p) is PcMedicalTreatmentApplicationProof))
    return None


def expected_medical_suppression(state):
    from towr.domain.talent_actor_models import actor_has_talent
    consumed=tuple(p.request.treatment.request_id for p in state.history if type(p) is PcMedicalSuppressionProof)
    for proof in state.history:
        if type(proof) is not PcMedicalTreatmentApplicationProof or proof.result.request_id in consumed: continue
        treatment=proof.result;actor=treatment.source_request.recover.source_request.actor_id
        if not actor_has_talent(state,actor,TalentId.COMBAT_SURGEON): continue
        target=treatment.target_id;injury=medical_raw_body(state,target).injury
        if injury.dead or not any(e.wound_sequence==treatment.wound_sequence and e.duration is WoundEffectDuration.UNTIL_HEALED
                for e in injury.active_wound_effects): continue
        test=medical_test(state,actor,treatment.request_id+':surgeon-recall',Skill.RECALL,target=target)
        return CombatSurgeonTreatmentRequest(treatment.request_id+':surgeon',state.source.id,treatment,
            actor,target,injury,test,True,consumed)
    return None


def complete_medical_suppression(request,test):
    validate_completed_talent_test(request.recall_test,test)
    return CombatSurgeonTreatmentResult(request.id,request.rule_id,request,test,_expected_suppression(request,test),
        request.injury_state,request.injury_state,request.consumed_treatment_result_ids,
        (*request.consumed_treatment_result_ids,request.treatment.request_id),
        tuple(dict.fromkeys((request.rule_id,request.treatment.rule_id,*test.trace.applied_rule_ids))))


def _wound_identity(wound):
    return wound.sequence,wound.entry_id,wound.table_total,wound.roll_values,wound.origin


def medical_surgery_progress(state,actor,target,sequence,injury):
    last=next((p.result.progress for p in reversed(state.history) if type(p) is PcMedicalSurgeryProof
        and p.request.surgeon_id==actor and p.request.target_id==target and p.request.wound_sequence==sequence),None)
    if last is None: return None
    if _wound_identity(last.injury_state.wounds[sequence-1])!=_wound_identity(injury.wounds[sequence-1]):
        raise ValueError('surgical progress cannot be transferred to a replaced Wound')
    return replace(last,injury_state=injury)


def build_medical_surgery(state,target,sequence):
    from towr.domain.talent_actor_models import actor_has_talent
    turn=state.round_state.active_turn
    if turn is None or not turn.action_slots: raise ValueError('surgery needs an actual reserved own action')
    actor=turn.actor_id;facts=medical_facts(state,actor)
    injury,wound=_patient(state,actor,target,sequence)
    from towr.rules.wound_table import lookup_wound
    if lookup_wound(wound.table_total).healing is not HealingRequirement.SURGERY_AND_RECOVERY:
        raise ValueError('surgery requires the actual surgery-and-recovery Wound')
    if not actor_has_talent(state,actor,TalentId.COMBAT_SURGEON) or facts is None or not facts.surgery_supplies:
        raise ValueError('surgery requires the acquired Talent and actual medical supplies')
    if wound.entry_id not in facts.recovery_supports or state.source.surgery_risk is None:
        raise ValueError('surgery needs actual recovery supports and an explicit GM risk policy')
    hand=medical_hand_use(state,actor,surgery=True)
    if hand is None or hand.kit_id is None: raise ValueError('surgery requires two free usable hands and its actual specialist tools')
    after=medical_action_injury(state,actor,hand,CombatActionKind.IMPROVISE,consume_test=True)
    if actor==target: injury=after
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    identifier=pc_melee_action_id(state,actor)+':medical-surgery'
    progress=medical_surgery_progress(state,actor,target,sequence,injury)
    surgery_id=(progress.id if progress is not None else state.source.id+':surgery:'+actor+':'+target+':'+str(sequence))
    request=CombatSurgeonBattleSurgeryActionRequest(identifier,surgery_id,state.source.id,state.round_state,actor,
        after.conditions,(COMBAT_SURGEON_RULE_ID,),turn.action_slots[-1].index,target,None if actor==target else True,
        injury,sequence,medical_test(state,actor,identifier+':dexterity',Skill.DEXTERITY,target=target),True,True,progress)
    return request,hand


def complete_medical_surgery(request,test):
    """Finish a real final Test after the optional PC Fate window, without RNG."""
    validate_completed_talent_test(request.dexterity_test,test)
    from towr.rules.exacting_test_resolution import complete_exacting_test_contribution
    previous=_source_progress(request)
    exacting=complete_exacting_test_contribution(_exacting_request(request,previous),test)
    progress=replace(previous,exacting=exacting.progress)
    proof=_expected_proof(request,progress);risk=_expected_failure_risk(request,exacting)
    turn=request.round_state.active_turn;slot=turn.action_slots[request.slot_index-1]
    receipt=ActionExecutionReceipt(request.id,request.rule_id,request.id,exacting.request_id,request.surgeon_id,
        request.round_state.round_number,slot.index,slot.declaration)
    executed=replace(slot,execution=receipt)
    clock=replace(request.round_state,active_turn=replace(turn,action_slots=tuple(executed if s.index==slot.index else s for s in turn.action_slots)))
    return CombatSurgeonBattleSurgeryActionResult(request.id,request.rule_id,request,exacting,previous,progress,
        proof,risk,request.injury_state,request.injury_state,request.round_state,clock,executed,
        tuple(dict.fromkeys((request.rule_id,COMBAT_SURGEON_RULE_ID,*exacting.applied_rule_ids,
            *((risk.rule_id,) if risk is not None else ())))))


def expected_medical_risk(state):
    done=tuple(p.request.surgery.failure_risk.id for p in state.history if type(p) is PcMedicalRiskProof)
    for proof in state.history:
        if type(proof) is not PcMedicalSurgeryProof or proof.result.failure_risk is None or proof.result.failure_risk.id in done: continue
        if state.source.surgery_risk is None: raise ValueError('actual surgery cannot invent missing GM risk weights')
        return SurgeryFailureResolutionRequest(proof.request.id+':risk',proof.result,state.source.surgery_risk,
            medical_raw_body(state,proof.request.target_id).injury,done)
    return None


def pending_medical_work(state):
    return expected_medical_treatment_application(state) or expected_medical_suppression(state) or expected_medical_risk(state)
