"""Source-bound potion Recover for a fresh, pre-sunset PC melee encounter."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import usable_hands, injured_hands
from towr.domain.pc_melee_models import PcWeaponHand, PcMeleeDefinition
from towr.domain.potion_models import (ConsumableKind, heal_potion_wound,
    HEALING_POTION_RULE_ID, ENHANCEMENT_POTION_RULE_ID)
from towr.domain.recover_models import RecoverActionExecutionResult

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState, PcMeleeParticipantState


ENHANCEMENT_CHARACTERISTICS = ('weapon_skill', 'strength', 'toughness', 'agility')


@dataclass(frozen=True, slots=True)
class PcPotionSelection:
    item_id: str
    wound_sequence: int | None
    hand: PcWeaponHand


@dataclass(frozen=True, slots=True)
class PcPotionRecoverProof:
    selection: PcPotionSelection
    result: RecoverActionExecutionResult
    before: PcMeleeParticipantState
    after: PcMeleeParticipantState

    @property
    def actor_id(self) -> str:
        return self.before.actor_id

    @property
    def item_id(self) -> str:
        return self.selection.item_id

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        rule = HEALING_POTION_RULE_ID if self.selection.wound_sequence is not None else ENHANCEMENT_POTION_RULE_ID
        return tuple(dict.fromkeys((*self.result.applied_rule_ids, rule)))


def pc_potion_hand(member: PcMeleeParticipantState) -> PcWeaponHand | None:
    hands = usable_hands(member)
    return next((hand for hand in hands if hand not in injured_hands(member)), next(iter(hands), None))


def pc_effective_definition(state: PcMeleeState, actor: str) -> PcMeleeDefinition:
    pc = state.source.participant(actor).pc
    return (replace(pc, **{name: getattr(pc, name)+1 for name in state.participant(actor).enhancements})
        if state.participant(actor).enhancements else pc)


def potion_options(member: PcMeleeParticipantState) -> tuple[PcPotionSelection, ...]:
    hand = pc_potion_hand(member)
    if hand is None or member.injury.dead:
        return ()
    options = []
    for item in member.potions:
        if item.kind is ConsumableKind.HEALING:
            wounds = sorted((w for w in member.injury.wounds
                if not w.healed and w.effect_resolved and w.table_total < 24),
                key=lambda w: (-w.table_total, w.sequence))
            options.extend(PcPotionSelection(item.id, w.sequence, hand) for w in wounds)
        elif (not member.injury.conditions.has(Condition.DEFENCELESS)
                and item.characteristic not in member.enhancements):
            options.append(PcPotionSelection(item.id, None, hand))
    return tuple(options)


def selected_pc_potion(state: PcMeleeState) -> PcPotionSelection | None:
    from towr.domain.pc_melee_models import PcMeleePolicy
    from towr.domain.pc_tactical_models import select_pc_tactic
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order:
        return None
    if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_MELEE:
        return None
    if not state.participant(actor).potions:
        return None
    return select_pc_tactic(state).potion


def build_pc_potion_recover(state: PcMeleeState) -> PcPotionRecoverProof:
    """Resolve a deterministic Recover and its one actual consumable, no RNG."""
    from towr.domain.pc_melee_result_models import build_pc_melee_recover
    from towr.domain.pc_ally_recover_models import expected_pc_standard_recover, pc_after_standard_recover
    selection = selected_pc_potion(state)
    if selection is None:
        raise ValueError('this source did not select potion Recover')
    actor = state.round_state.active_turn.actor_id
    before = state.participant(actor)
    if selection not in potion_options(before):
        raise ValueError('potion use has no current supply, hand or eligible effect')
    item = next(item for item in before.potions if item.id == selection.item_id)
    request = build_pc_melee_recover(state)
    result = expected_pc_standard_recover(request)
    after = next(member for member in pc_after_standard_recover(state, request, result)
        if member.actor_id == actor)
    if item.kind is ConsumableKind.HEALING:
        other_sources = frozenset((Condition.DRAINED,) if after.hit_condition_sources else ())
        if after.net_condition_sources:
            other_sources |= frozenset((Condition.BURDENED,))
        injury = heal_potion_wound(after.injury, selection.wound_sequence, other_sources)
        after = replace(after, injury=injury,
            timed_wounds=tuple(t for t in after.timed_wounds if t.effect.wound_sequence != selection.wound_sequence),
            body_facts=tuple(f for f in after.body_facts if f.wound_sequence != selection.wound_sequence))
        # UNAVAILABLE is the existing attached-shield state from an injured or
        # severed arm. Healing removes that cause; an actually DROPPED shield
        # remains on the ground and needs its own later pickup.
        from towr.domain.pc_shield_models import PcShieldLocation, PcShieldState
        if (after.shield is not None and after.shield.location is PcShieldLocation.UNAVAILABLE
                and after.shield.hand in usable_hands(after)
                and any(f.wound_sequence == selection.wound_sequence and f.side is after.shield.hand
                    for f in before.body_facts)):
            after = replace(after, shield=PcShieldState(PcShieldLocation.HELD, after.shield.hand))
    else:
        after = replace(after, enhancements=(*after.enhancements, item.characteristic))
    after = replace(after, potions=tuple(replace(current, quantity=current.quantity-1)
        if current.id == item.id else current for current in after.potions
        if current.id != item.id or current.quantity > 1))
    return PcPotionRecoverProof(selection, result, before, after)
