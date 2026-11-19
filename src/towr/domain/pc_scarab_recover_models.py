"""The Scarab Knife's paid standard-Recover healing interaction, GM84."""
from __future__ import annotations

from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation
from towr.domain.weapon_magic_lifecycle import WeaponScarabHealingResources,prepare_scarab_healing_resources
from towr.domain.recover_models import RecoverActionExecutionRequest,RecoverActionExecutionResult


@dataclass(frozen=True,slots=True)
class PcScarabHealingSelection:
    item_id: str
    wound_sequence: int | None


@dataclass(frozen=True,slots=True)
class PcScarabHealingProof:
    selection: PcScarabHealingSelection
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    resources: WeaponScarabHealingResources


def scarab_healing_options(state,actor):
    from towr.domain.pc_magic_weapon_models import actor_inventory,actor_injury
    inventory=actor_inventory(state,actor)
    injury=actor_injury(state,actor)
    if inventory is None or getattr(injury,'dead',False) or getattr(injury,'defeated',False):
        return ()
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_hands
        hands={WeaponGrip(hand.value) for hand in usable_hands(state.participant(actor))}
        wounds=[w.sequence for w in sorted(injury.wounds,key=lambda w:(-w.table_total,w.sequence))
            if not w.healed and w.effect_resolved and w.table_total<24]
    else:
        hands={WeaponGrip.LEFT,WeaponGrip.RIGHT}
        wounds=[None] if injury.wounds else []
    return tuple(PcScarabHealingSelection(item.id,wound) for item in inventory.items
        if item.kind is WeaponKind.SCARAB_KNIFE and item.location is WeaponItemLocation.HELD
        and item.grip in hands and item.charges>=3 for wound in wounds)


def selected_scarab_healing(state):
    actor=state.round_state.active_turn.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            return None
        from towr.domain.pc_tactical_models import select_pc_tactic
        return select_pc_tactic(state).scarab_heal
    return next(iter(scarab_healing_options(state,actor)),None)


def _resources(state,actor,selection):
    from towr.domain.pc_magic_weapon_models import actor_inventory
    from towr.domain.weapon_use_models import build_weapon_use
    inventory=actor_inventory(state,actor)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_hands
        hands=tuple(WeaponGrip(hand.value) for hand in usable_hands(state.participant(actor)))
    else:
        hands=(WeaponGrip.LEFT,WeaponGrip.RIGHT)
    use=build_weapon_use(actor,inventory,selection.item_id,usable_hands=hands)
    return prepare_scarab_healing_resources(use,selection.item_id)


def build_scarab_healing(state):
    from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
    from towr.domain.pc_melee_result_models import build_pc_melee_recover,pc_melee_action_id
    from towr.domain.recover_models import (RecoverMode,RecoverStandardChoice,RecoverObjectInteractionFollowUp,
        RecoverConditionTarget)
    from towr.domain.magic_models import WizardMagicState
    from towr.domain.pc_short_opening_models import pc_has_close_enemy
    actor=state.round_state.active_turn.actor_id
    selection=selected_scarab_healing(state)
    if selection is None or selection not in scarab_healing_options(state,actor):
        raise ValueError('Scarab healing requires a held charged item and an actual eligible Wound')
    if actor in state.source.pc_activation_order:
        request=build_pc_melee_recover(state)
    else:
        conditions=state.enemy(actor).state.injury.conditions
        target=lambda condition: RecoverConditionTarget(actor,conditions,None) if conditions.has(condition) else None
        identifier=pc_melee_action_id(state,actor)+':scarab-recover'
        choice=RecoverStandardChoice(WizardMagicState(),staggered_target=target(Condition.STAGGERED),
            prone_target=target(Condition.PRONE),object_interaction=RecoverObjectInteractionFollowUp(
                pc_melee_action_id(state,actor)+':scarab-heal',actor,selection.item_id,True))
        request=RecoverActionExecutionRequest(identifier,state.round_state,actor,conditions,
            pc_has_close_enemy(state,actor),1,RecoverMode.STANDARD,choice)
    return PcScarabHealingProof(selection,request,expected_pc_standard_recover(request),_resources(state,actor,selection))


def project_scarab_healing(state,proof):
    expected=build_scarab_healing(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if proof!=expected:
        raise ValueError('Scarab healing changed its full actual Recover/Wound/charge source')
    validate_pc_melee_source_types(proof,expected)
    actor=proof.request.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_ally_recover_models import pc_after_standard_recover
        from towr.domain.pc_potion_models import heal_pc_member
        before=state.participant(actor)
        party=pc_after_standard_recover(state,proof.request,proof.result)
        after=next(member for member in party if member.actor_id==actor)
        after=heal_pc_member(state,actor,before,after,proof.selection.wound_sequence)
        after=replace(after,weapon_inventory=proof.resources.after_inventory)
        return dict(round_state=proof.result.round_state,
            party=tuple(after if member.actor_id==actor else member for member in party))
    from towr.domain.pc_battlefield_movement_models import battlefield_recovered_injury
    enemy=state.enemy(actor)
    injury=battlefield_recovered_injury(enemy.state.injury,proof.result)
    injury=replace(injury,wounds=injury.wounds-1)
    return dict(round_state=proof.result.round_state,enemies=tuple(replace(row,
        state=replace(row.state,injury=injury,weapon_inventory=proof.resources.after_inventory))
        if row.state.actor_id==actor else row for row in state.enemies))
