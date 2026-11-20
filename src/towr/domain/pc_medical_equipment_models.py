"""Actual medical hand preparation and paid retrieval of a physical kit.

Weapon resources never change here. A released Shield has a real ground
position; later restoration belongs to the ordinary Equip/Recover owners.
"""
from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState,WoundConditionEffect,WoundEffectDuration
from towr.domain.pc_musician_equipment_models import (
    PcMusicianEquipmentProof,_participant,_body,_tool_sources,_touched,_hands,
)
from towr.domain.pc_medical_tactics import MedicalActionChoice,committed_medical_intent
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation
from towr.domain.recover_models import RecoverActionExecutionResult


@dataclass(frozen=True,slots=True)
class PcMedicalEquipmentProof:
    choice:MedicalActionChoice
    equipment:PcMusicianEquipmentProof

    def __post_init__(self):
        if type(self.choice) is not MedicalActionChoice or type(self.equipment) is not PcMusicianEquipmentProof:
            raise TypeError('medical preparation retains its exact commitment and physical receipt')
        replace(self.choice);replace(self.equipment)
        if self.equipment.pickup:raise ValueError('unpaid medical preparation cannot retrieve a dropped tool')

    @property
    def actor_id(self):return self.equipment.actor_id
    @property
    def action_id(self):return self.equipment.action_id
    @property
    def round_number(self):return self.equipment.round_state.round_number
    @property
    def changes_equipment(self):return self.equipment.changes_equipment


@dataclass(frozen=True,slots=True)
class PcMedicalToolRecoverProof:
    choice:MedicalActionChoice
    result:RecoverActionExecutionResult
    equipment:PcMusicianEquipmentProof

    def __post_init__(self):
        if (type(self.choice) is not MedicalActionChoice or type(self.result) is not RecoverActionExecutionResult
                or type(self.equipment) is not PcMusicianEquipmentProof):
            raise TypeError('medical pickup retains its exact choice, paid Recover and physical receipt')
        replace(self.choice);replace(self.result);replace(self.equipment)
        if not self.choice.pickup_tool or not self.equipment.pickup or self.choice.kit_id!=self.equipment.item_id:
            raise ValueError('medical Recover must retrieve its one actual selected dropped kit')

    @property
    def actor_id(self):return self.equipment.actor_id


def _intent(state):
    intent=committed_medical_intent(state)
    if intent is None:raise ValueError('medical equipment requires a committed actual action and patient')
    return intent


def _body_injury(state,actor,touched,*,recover=False):
    from towr.domain.pc_medical_models import medical_action_injury,medical_raw_body,MedicalHandUse
    from towr.domain.turn_models import CombatActionKind
    raw=medical_raw_body(state,actor).injury
    if not touched or type(raw) is not CharacterInjuryState:return raw
    # Incidental preparation remains a real hand action; pickup is inside the
    # actual Recover and therefore preserves its different W14 consequence.
    return medical_action_injury(state,actor,MedicalHandUse(actor,tuple(sorted(touched,key=lambda h:h.value)),None),
        CombatActionKind.RECOVER if recover else None)


def _proof(state,actor,choice,weapons,tools,*,pickup=False):
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState,pc_melee_action_id
    value=_body(state,actor);before=_participant(value)
    touched=_touched(before.tool_inventory,tools,before.weapon_inventory,weapons)
    injury=_body_injury(state,actor,touched,recover=pickup)
    previous_npc_shield=npc_shield=None;battlefield=state.battlefield
    if type(value) is PcMeleeParticipantState:
        shield=value.shield
        if before.weapon_inventory.shield_hand is not weapons.shield_hand:
            from towr.domain.pc_shield_models import (PcShieldState,PcShieldLocation,PcShieldGroundPosition,
                _add_shield_marker,_shield_ground,_shield_actors)
            ground=(_shield_ground(state,actor) if battlefield is not None else
                PcShieldGroundPosition(state.source.facts.zone_id,_shield_actors(state)))
            shield=PcShieldState(PcShieldLocation.DROPPED,None,ground=ground)
            battlefield=_add_shield_marker(battlefield,actor,shield)
        from towr.domain.pc_weapon_inventory import replace_pc_member
        after=replace_pc_member(value,weapon_inventory=weapons,tool_inventory=tools,shield=shield,injury=injury)
    else:
        from towr.domain.pc_npc_shield_models import (npc_shield_item,NpcShieldLocation,_drop_position,
            _add_marker,_with_shield,_resilience_witness)
        previous_npc_shield=npc_shield=npc_shield_item(state,actor)
        after=value
        if before.weapon_inventory.shield_hand is not weapons.shield_hand:
            if npc_shield is None or npc_shield.location is not NpcShieldLocation.HELD:
                raise ValueError('medical preparation cannot release a source-less NPC Shield')
            npc_shield=replace(npc_shield,location=NpcShieldLocation.DROPPED,ground=_drop_position(state,actor))
            battlefield=_add_marker(battlefield,npc_shield)
            after=_with_shield(value,False,**_resilience_witness(state,actor))
        from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
        after=replace(after,state=replace(after.state,injury=injury,weapon_inventory=weapons,tool_inventory=tools,
            wields_weapon=any(item.location is WeaponItemLocation.HELD for item in weapons.items),
            available_attack_ids=npc_inventory_attack_ids(after.definition,weapons)))
    return PcMusicianEquipmentProof(actor,pc_melee_action_id(state,actor),state.round_state,len(state.history),
        choice.kit_id,pickup,value,after,previous_npc_shield,npc_shield,state.battlefield,battlefield)


def expected_medical_preparation(state):
    """Stow only conflicts with the chosen one/two usable medical hands."""
    intent=_intent(state);actor=intent.actor_id;choice=intent.choice
    turn=state.round_state.active_turn
    if turn.action_slots or state.pending or state.pending_wound is not None or state.magic_pending is not None:return None
    if any(type(proof) is PcMedicalEquipmentProof and proof.action_id==intent.action_id for proof in state.history):return None
    value=_body(state,actor)
    if value is None:return None
    before=_participant(value);_tool_sources(state,actor,value)
    from towr.domain.pc_medical_models import medical_effective_body
    from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands
    effective=medical_effective_body(state,actor)
    if type(effective.injury) is CharacterInjuryState:
        usable=tuple(WeaponGrip(hand.value) for hand in usable_hands(effective))
        injured={WeaponGrip(hand.value) for hand in injured_hands(effective)}
    else:usable=(WeaponGrip.LEFT,WeaponGrip.RIGHT);injured=set()
    count=1 if choice.pickup_tool else choice.required_hands
    if len(usable)<count:return None
    def cost(hand):
        return (hand in injured,hand is before.weapon_inventory.shield_hand,
            sum(hand in _hands(item.grip) for item in before.weapon_inventory.items
                if item.location is WeaponItemLocation.HELD),hand is WeaponGrip.RIGHT)
    selected=set(sorted(usable,key=cost)[:count])
    trapped={binding.weapon_id for binding in state.briarroot_bindings if binding.attacker_id==actor}
    if any(item.id in trapped and item.location is WeaponItemLocation.HELD and selected.intersection(_hands(item.grip))
            for item in before.weapon_inventory.items):return None
    weapons=replace(before.weapon_inventory,items=tuple(
        replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        if item.location is WeaponItemLocation.HELD and selected.intersection(_hands(item.grip)) else item
        for item in before.weapon_inventory.items),
        shield_hand=None if before.weapon_inventory.shield_hand in selected else before.weapon_inventory.shield_hand)
    tools=replace(before.tool_inventory,items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        if item.location is WeaponItemLocation.HELD and item.id!=choice.kit_id
            and selected.intersection(item.occupied_hands) else item for item in before.tool_inventory.items))
    if weapons==before.weapon_inventory and tools==before.tool_inventory:return None
    return PcMedicalEquipmentProof(choice,_proof(state,actor,choice,weapons,tools))


def _equipment_updates(state,equipment):
    actor=equipment.actor_id
    if actor in state.source.pc_activation_order:
        return dict(party=tuple(equipment.state if member.actor_id==actor else member for member in state.party),
            battlefield=equipment.battlefield)
    return dict(enemies=tuple(equipment.state if enemy.state.actor_id==actor else enemy for enemy in state.enemies),
        battlefield=equipment.battlefield,npc_shields=tuple(equipment.npc_shield if row.actor_id==actor else row
            for row in state.npc_shields))


def project_medical_equipment(state,proof):
    if type(proof) is not PcMedicalEquipmentProof:raise TypeError('medical preparation needs its exact physical proof')
    expected=expected_medical_preparation(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if expected is None or proof!=expected:raise ValueError('medical preparation differs from its committed real hands/inventory')
    validate_pc_melee_source_types(proof,expected)
    return _equipment_updates(state,proof.equipment)


def build_medical_tool_recover(state):
    intent=_intent(state);choice=intent.choice;actor=intent.actor_id
    if not choice.pickup_tool:raise ValueError('medical tool Recover needs an actual dropped-kit commitment')
    from towr.domain.pc_musician_equipment_models import plan_musician_equipment
    if plan_musician_equipment(state,actor,choice.kit_id,pickup=True) is None:
        raise ValueError('medical kit is not actually retrievable here with usable hands')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_medical_models import effective_medical_injury,medical_raw_body
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    from towr.domain.recover_models import (RecoverStandardChoice,RecoverConditionTarget,
        RecoverObjectInteractionFollowUp,RecoverActionExecutionRequest,RecoverMode)
    from towr.domain.magic_models import WizardMagicState
    from towr.domain.pc_extinguish_models import _enemy_in_zone
    body=medical_raw_body(state,actor);injury=effective_medical_injury(state,actor)
    def target(condition):
        ongoing=type(injury) is CharacterInjuryState and has_ongoing_condition(injury,condition)
        return RecoverConditionTarget(actor,body.injury.conditions,None) if injury.conditions.has(condition) and not ongoing else None
    identifier=pc_melee_action_id(state,actor)
    magic=body.magic if actor in state.source.pc_activation_order and body.magic is not None else WizardMagicState()
    selected=RecoverStandardChoice(magic,staggered_target=target(Condition.STAGGERED),prone_target=target(Condition.PRONE),
        object_interaction=RecoverObjectInteractionFollowUp(identifier+':pickup-tool',actor,choice.kit_id,True))
    return RecoverActionExecutionRequest(identifier,state.round_state,actor,body.injury.conditions,
        _enemy_in_zone(state,actor),len(state.round_state.active_turn.action_slots),RecoverMode.STANDARD,selected)


def complete_medical_tool_recover(state,result):
    intent=_intent(state);request=build_medical_tool_recover(state)
    from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
    from towr.domain.pc_musician_equipment_models import plan_musician_equipment
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    canonical=expected_pc_standard_recover(request)
    if result!=canonical:raise ValueError('medical kit pickup changed its actual paid standard Recover')
    validate_pc_melee_source_types(result,canonical)
    planned=plan_musician_equipment(state,intent.actor_id,intent.choice.kit_id,pickup=True)
    # Reuse the physical tool owner, with the medical body owner applying the
    # actual Champion/PC hand consequences rather than a role-based shortcut.
    before=_participant(planned.previous);after=_participant(planned.state)
    equipment=_proof(state,intent.actor_id,intent.choice,after.weapon_inventory,after.tool_inventory,pickup=True)
    return PcMedicalToolRecoverProof(intent.choice,result,equipment)


def project_medical_tool_recover(state,proof):
    if type(proof) is not PcMedicalToolRecoverProof:raise TypeError('medical pickup needs its exact paid proof')
    expected=complete_medical_tool_recover(state,proof.result)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if proof!=expected:raise ValueError('medical pickup changed its physical source, patient commitment or paid result')
    validate_pc_melee_source_types(proof,expected)
    equipment=proof.equipment;actor=equipment.actor_id;updates=_equipment_updates(state,equipment)
    body=_participant(equipment.state);injury=body.injury
    for change in proof.result.resolution.condition_changes:
        effects=(tuple(effect for effect in injury.active_wound_effects if not (type(effect) is WoundConditionEffect
            and effect.condition in change.removed_conditions and effect.duration is WoundEffectDuration.UNTIL_REMOVED))
            if type(injury) is CharacterInjuryState else None)
        injury=replace(injury,conditions=change.conditions,**({} if effects is None else dict(active_wound_effects=effects)))
    if type(injury) is CharacterInjuryState and any(Condition.PRONE in change.removed_conditions
            for change in proof.result.resolution.condition_changes):
        from towr.domain.pc_medical_models import medical_effective_body
        from towr.domain.pc_heavy_wound_models import critical_for_action
        from towr.domain.turn_models import CombatActionKind
        effective=medical_effective_body(state,actor)
        critical=critical_for_action(effective,CombatActionKind.RECOVER,removes_prone=True)
        added=tuple(effect for effect in critical.active_wound_effects if effect not in effective.injury.active_wound_effects)
        injury=replace(injury,active_wound_effects=tuple(dict.fromkeys((*injury.active_wound_effects,*added))),
            conditions=injury.conditions.with_condition(Condition.CRITICALLY_INJURED) if added else injury.conditions)
    if type(injury) is CharacterInjuryState and body.injury.conditions.has(Condition.CRITICALLY_INJURED):
        injury=replace(injury,conditions=injury.conditions.with_condition(Condition.CRITICALLY_INJURED))
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_weapon_inventory import replace_pc_member
        member=replace_pc_member(equipment.state,injury=injury,
            **({} if equipment.state.magic is None else dict(magic=proof.result.resolution.magic_state)))
        updates['party']=tuple(member if row.actor_id==actor else row for row in state.party)
    else:
        enemy=replace(equipment.state,state=replace(equipment.state.state,injury=injury))
        updates['enemies']=tuple(enemy if row.state.actor_id==actor else row for row in state.enemies)
    updates['round_state']=proof.result.round_state
    return updates
