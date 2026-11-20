"""Finite medical alternatives from actual patients, never hypothetical HP."""
from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState,WoundEffectDuration,WoundConditionEffect,HealingRequirement,injury_is_defeated
from towr.domain.pc_medical_models import medical_facts,medical_hand_use,available_medical_kit,_patient
from towr.domain.talent_catalog import TalentId


class MedicalActionKind(str,Enum):
    TREATMENT='treatment'
    SURGERY='surgery'


@dataclass(frozen=True,slots=True)
class MedicalActionChoice:
    kind:MedicalActionKind
    target_id:str
    wound_sequence:int
    required_hands:int
    requires_preparation:bool
    utility:int
    kit_id:str|None=None
    pickup_tool:bool=False

    def __post_init__(self):
        if type(self.kind) is not MedicalActionKind or type(self.target_id) is not str or not self.target_id.strip():
            raise TypeError('medical choice requires its actual kind and patient')
        if type(self.wound_sequence) is not int or self.wound_sequence<1:
            raise TypeError('medical choice requires an actual positive Wound sequence')
        if type(self.required_hands) is not int or self.required_hands!=(2 if self.kind is MedicalActionKind.SURGERY else 1):
            raise ValueError('medical hand requirement differs from its action')
        if type(self.requires_preparation) is not bool or type(self.utility) is not int or self.utility<0:
            raise TypeError('medical choice preserves its actual preparation and finite utility')
        if self.kit_id is not None and (type(self.kit_id) is not str or not self.kit_id.strip()):
            raise TypeError('medical kit selection requires its actual physical identifier')
        if type(self.pickup_tool) is not bool or self.pickup_tool and self.kit_id is None:
            raise ValueError('medical pickup must name its one actual dropped kit')


@dataclass(frozen=True,slots=True)
class PcMedicalIntentProof:
    actor_id:str
    action_id:str
    choice:MedicalActionChoice

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.action_id)):
            raise TypeError('medical intent requires its actual actor and action identifiers')
        if type(self.choice) is not MedicalActionChoice:
            raise TypeError('medical intent retains the exact selected action/patient/Wound')


def committed_medical_intent(state,actor=None):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_medical_models import PcMedicalTreatmentProof,PcMedicalSurgeryProof
    from towr.domain.pc_medical_equipment_models import PcMedicalToolRecoverProof
    turn=state.round_state.active_turn
    if turn is None or actor is not None and actor!=turn.actor_id:return None
    actor=turn.actor_id;action=pc_melee_action_id(state,actor)
    for proof in reversed(state.history):
        if type(proof) is PcMedicalTreatmentProof and proof.request.actor_id==actor:return None
        if type(proof) is PcMedicalSurgeryProof and proof.request.surgeon_id==actor:return None
        if type(proof) is PcMedicalToolRecoverProof and proof.result.source_request.actor_id==actor:return None
        if type(proof) is PcMedicalIntentProof and proof.actor_id==actor and proof.action_id==action:return proof
    return None


def medical_actions(state,actor):
    """Enumerate attainable medical work before equipment preparation.

    Surgery is a genuine alternative but has zero immediate combat utility:
    completing it does not heal a Wound before postoperative recovery.
    """
    from towr.domain.pc_actor_models import pc_actor_injury
    from towr.domain.pc_heavy_wound_models import usable_hands
    from towr.domain.pc_medical_models import medical_effective_body,medical_surgery_progress
    from towr.domain.talent_actor_models import actor_has_talent
    facts=medical_facts(state,actor)
    if facts is None:return ()
    if not facts.anatomy_lore and facts.makeshift_modifier is None:return ()
    own=pc_actor_injury(state,actor)
    if injury_is_defeated(own) or any(own.conditions.has(condition) for condition in
            (Condition.DEFENCELESS,Condition.BROKEN)):return ()
    body=medical_effective_body(state,actor)
    usable=usable_hands(body) if type(own) is CharacterInjuryState else (1,2)
    kit=available_medical_kit(state,actor)
    pickup=False
    if kit is None:
        from towr.domain.pc_tool_models import actor_tools,actor_tool_zone
        from towr.domain.tool_inventory_models import ToolKind
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        kit=next((item for item in actor_tools(state,actor).items
            if item.kind is ToolKind.PHYSICKERS_KIT and item.location is WeaponItemLocation.DROPPED
                and item.dropped_zone_id==actor_tool_zone(state,actor)),None)
        pickup=kit is not None
    if not usable or kit is None and facts.makeshift_modifier is None:return ()
    has_talent=actor_has_talent(state,actor,TalentId.COMBAT_SURGEON)
    targets=(*state.source.pc_activation_order,*state.source.npc_activation_order,
        *(row.snapshot.state.actor_id for row in state.companions))
    choices=[]
    for target in targets:
        injury=pc_actor_injury(state,target)
        if type(injury) is not CharacterInjuryState or injury.dead:continue
        for wound in injury.wounds:
            try:_patient(state,actor,target,wound.sequence)
            except ValueError:continue
            effects=tuple(e for e in injury.active_wound_effects if e.wound_sequence==wound.sequence)
            if not wound.treated and facts.treatment_supplies:
                removable=tuple(e for e in effects if e.duration is WoundEffectDuration.UNTIL_TREATED)
                suppressed=tuple(e for e in effects if e.duration is WoundEffectDuration.UNTIL_HEALED) if has_talent else ()
                critical=any(type(e) is WoundConditionEffect and e.condition is Condition.CRITICALLY_INJURED for e in removable)
                utility=(100 if critical else 0)+20*len(removable)+10*len(suppressed)
                if utility:
                    choices.append(MedicalActionChoice(MedicalActionKind.TREATMENT,target,wound.sequence,1,
                        pickup or medical_hand_use(state,actor) is None,utility,
                        None if kit is None else kit.id,pickup))
            from towr.rules.wound_table import lookup_wound
            if (has_talent and kit is not None and not pickup and len(usable)>=2 and facts.surgery_supplies
                    and wound.entry_id in facts.recovery_supports and state.source.surgery_risk is not None
                    and lookup_wound(wound.table_total).healing is HealingRequirement.SURGERY_AND_RECOVERY):
                progress=medical_surgery_progress(state,actor,target,wound.sequence,injury)
                if progress is None or not progress.exacting.completed:
                    choices.append(MedicalActionChoice(MedicalActionKind.SURGERY,target,wound.sequence,2,
                        medical_hand_use(state,actor,surgery=True) is None,0,kit.id))
    return tuple(choices)


def choose_medical_action(state,actor):
    """Use finite action advice; a Wound alone does not force treatment."""
    from towr.domain.pc_medical_advice import choose_compared_medical_action
    advice=choose_compared_medical_action(state,actor)
    return None if advice is None else advice.choice


def current_medical_choice(state):
    if getattr(state,'medical_advice_disabled',False):return None
    turn=state.round_state.active_turn
    if turn is None:return None
    intent=committed_medical_intent(state,turn.actor_id)
    if intent is not None:return intent.choice
    if turn.action_slots:return None
    actor=turn.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:return None
    elif actor not in state.source.npc_activation_order:return None
    return choose_medical_action(state,actor)


def expected_medical_intent(state):
    turn=state.round_state.active_turn
    if (turn is None or turn.action_slots or state.pending or state.pending_wound is not None
            or state.magic_pending is not None or committed_medical_intent(state) is not None):return None
    choice=current_medical_choice(state)
    if choice is None:return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    return PcMedicalIntentProof(turn.actor_id,pc_melee_action_id(state,turn.actor_id),choice)
