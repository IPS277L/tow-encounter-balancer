"""The two strikes of one Demigryph rider Attack action (GM1.1 VII175).

The rider commits the Grim leg before the first roll. The mount strike uses K1
after every first-strike consequence; it never reserves or executes another
action slot. The native owner validates and projects the complete journal.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_mount_models import CombatMount, PcMountedState, RiderKind
from towr.domain.protection_models import ProtectionPreparationResult
from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult
from towr.domain.test_models import QualityModifier, Skill, TestQuality
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind, CombatRoundState

if TYPE_CHECKING:
    from towr.domain.fate_models import FateGloriousSpendResult
    from towr.domain.pc_melee_result_models import PcFateDecline, PcMeleeState
    from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent


DEMIGRYPH_KNIGHTS_RULE_ID = 'BOOK-GM-GUIDE:1.1:p175:demigryph-knights'
DEMIGRYPH_GRIM_RULE_ID = DEMIGRYPH_KNIGHTS_RULE_ID + ':grim-strike'


class DemigryphGrimLeg(str, Enum):
    RIDER = 'rider'
    CLAWS = 'claws'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(f'{label} requires an exact nonempty identifier')


@dataclass(frozen=True, slots=True)
class PcDemigryphIntentProof:
    id: str
    actor_id: str
    source_round: CombatRoundState
    source_mount: PcMountedState
    primary_action_id: str
    grim_leg: DemigryphGrimLeg = DemigryphGrimLeg.CLAWS

    def __post_init__(self):
        for value, label in ((self.id, 'Demigryph intent'), (self.actor_id, 'rider'),
                (self.primary_action_id, 'primary action')):
            _identifier(value, label)
        if type(self.source_round) is not CombatRoundState or type(self.source_mount) is not PcMountedState:
            raise TypeError('Demigryph intent requires its actual combat clock and mount')
        replace(self.source_round); replace(self.source_mount)
        if type(self.grim_leg) is not DemigryphGrimLeg:
            raise TypeError('Demigryph requires a committed typed Grim leg')
        turn = self.source_round.active_turn
        if (turn is None or turn.actor_id != self.actor_id or not turn.action_slots
                or turn.action_slots[-1].executed
                or turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK):
            raise ValueError('Demigryph intent must precede its actual unused Attack action')
        if (self.source_mount.actor_id != self.actor_id
                or self.source_mount.mount is not CombatMount.DEMIGRYPH or not self.source_mount.mounted):
            raise ValueError('Demigryph intent requires this same actual mounted rider')

    @property
    def slot_index(self):
        return self.source_round.active_turn.action_slots[-1].index


@dataclass(frozen=True, slots=True)
class PcDemigryphStrikeRequest:
    id: str
    intent: PcDemigryphIntentProof
    parent_receipt: ActionExecutionReceipt
    source_round: CombatRoundState
    target_id: str
    kernel_request: KernelAttackRequest

    def __post_init__(self):
        _identifier(self.id, 'Demigryph strike')
        _identifier(self.target_id, 'Demigryph strike target')
        if (type(self.intent) is not PcDemigryphIntentProof
                or type(self.parent_receipt) is not ActionExecutionReceipt
                or type(self.source_round) is not CombatRoundState
                or type(self.kernel_request) is not KernelAttackRequest):
            raise TypeError('mount strike requires its exact intent, primary receipt, clock and K1 request')
        for value in (self.intent, self.parent_receipt, self.source_round, self.kernel_request):
            replace(value)
        receipt = self.parent_receipt
        primary_kernel_id = self.intent.primary_action_id.removesuffix(':execute') + ':kernel'
        turn = self.source_round.active_turn
        if (turn is None or turn.actor_id != self.actor_id
                or self.source_round.round_number != self.intent.source_round.round_number
                or self.slot_index > len(turn.action_slots)
                or turn.action_slots[self.slot_index-1].execution != receipt
                or len(turn.action_slots) != self.slot_index):
            raise ValueError('mount strike must retain the current actual executed primary action')
        if (receipt.id != self.intent.primary_action_id or receipt.actor_id != self.actor_id
                or receipt.round_number != self.source_round.round_number or receipt.slot_index != self.slot_index
                or receipt.declaration != self.intent.source_round.active_turn.action_slots[-1].declaration
                or receipt.executor_rule_id != 'RULE-COMBAT-004:attack-action-execution'
                or receipt.source_request_id != primary_kernel_id or receipt.result_request_id != primary_kernel_id):
            raise ValueError('mount strike is detached from its original primary Attack receipt')
        if self.kernel_request.target_id != self.target_id or self.target_id == self.actor_id:
            raise ValueError('mount strike requires its actual distinct K1 target')

    @property
    def actor_id(self):
        return self.intent.actor_id

    @property
    def slot_index(self):
        return self.intent.slot_index

    @property
    def state(self):
        """The existing clock, never a new action-slot reservation."""
        return self.source_round

    @property
    def weapon_instance_id(self):
        """The actual mount's natural weapon, never its rider's held item."""
        return self.actor_id + ':mount:demigryph:wicked-claws'


@dataclass(frozen=True, slots=True)
class PcDemigryphStrikeProof:
    request: PcDemigryphStrikeRequest
    protection: ProtectionPreparationResult
    resolution: ResolutionResult
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None
    weapon_intent: PcAttackWeaponIntent = field(kw_only=True)

    def __post_init__(self):
        if (type(self.request) is not PcDemigryphStrikeRequest
                or type(self.protection) is not ProtectionPreparationResult
                or type(self.resolution) is not ResolutionResult):
            raise TypeError('mount strike proof requires its exact request, Protection and K1 result')
        replace(self.request); replace(self.protection); replace(self.resolution)
        from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
        if type(self.weapon_intent) is not PcAttackWeaponIntent:
            raise TypeError('mount strike requires its exact frozen weapon intent')
        replace(self.weapon_intent)
        if (self.weapon_intent.action_id != self.request.id
                or self.weapon_intent.actor_id != self.request.actor_id
                or self.weapon_intent.target_id != self.request.target_id
                or not self.weapon_intent.mount_attack
                or self.weapon_intent.attack_skill is not Skill.MELEE
                or self.weapon_intent.attack_use is not None):
            raise ValueError('mount strike changed its committed natural Attack source')
        if self.fate_decline is not None:
            from towr.domain.pc_melee_result_models import PcFateDecline
            if type(self.fate_decline) is not PcFateDecline:
                raise TypeError('mount strike Fate decline requires its exact typed PC window')
            replace(self.fate_decline)
        if self.glorious is not None:
            from towr.domain.fate_models import FateGloriousSpendResult
            if type(self.glorious) is not FateGloriousSpendResult:
                raise TypeError('mount strike Glorious requires its actual PC spend result')
            replace(self.glorious)
        if self.fate_decline is not None and self.glorious is not None:
            raise ValueError('mount strike cannot both decline and spend Fate for the same Test')
        if self.resolution.request_id != self.request.kernel_request.id:
            raise ValueError('mount strike resolution belongs to another K1 request')
        if (self.protection.defender_id != self.request.target_id
                or self.protection.source_request.attack_skill is not Skill.MELEE):
            raise ValueError('Wicked Claws requires its own actual Melee Protection')


def _mount(state, actor):
    entry = next((item for item in state.mounts if item.actor_id == actor), None)
    if entry is None or entry.mount is not CombatMount.DEMIGRYPH or not entry.mounted:
        return None
    source = (state.source.participant(actor) if actor in state.source.pc_activation_order
        else state.enemy(actor).definition.generated_components)
    if source is None or source.mount is not CombatMount.DEMIGRYPH or source.rider_kind is not RiderKind.HUMAN:
        raise ValueError('Demigryph rider benefits require their complete actual Human source')
    return entry


def _able(state, actor):
    is_pc = actor in state.source.pc_activation_order
    injury = state.participant(actor).injury if is_pc else state.enemy(actor).state.injury
    return not (injury.dead if is_pc else injury.defeated) and not any(
        injury.conditions.has(condition) for condition in (Condition.DEFENCELESS, Condition.PRONE))


def _targets(state, actor):
    from towr.domain.pc_short_opening_models import pc_enemy_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    if actor in state.source.pc_activation_order:
        priority = state.source.participant(actor).target_priority
        alive = {enemy.state.actor_id for enemy in state.live_enemies}
    else:
        priority = state.source.enemy_target_priority
        alive = {member.actor_id for member in state.live_party}
    return tuple(target for target in priority if target in alive
        and pc_enemy_range(state, actor, target) is RangedWeaponRange.CLOSE)


def expected_pc_demigryph_intent(state: PcMeleeState) -> PcDemigryphIntentProof | None:
    """The fixed tactic makes Claws Grim, committed before either Test is rolled."""
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    turn = state.round_state.active_turn
    if (turn is None or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK):
        return None
    actor = turn.actor_id
    from towr.domain.pc_oath_models import oath_allows_attack
    if not oath_allows_attack(state,actor,Skill.MELEE):
        return None
    from towr.domain.pc_mount_attack_models import pc_uses_mount_attack
    if pc_uses_mount_attack(state,actor):
        return None
    mount = _mount(state, actor)
    if mount is None or not _able(state, actor) or not _targets(state, actor):
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action_id = pc_melee_action_id(state, actor) + (':attack2' if turn.action_slots[-1].index == 2 else '')
    identifier = action_id + ':demigryph:intent'
    if any(type(item) is PcDemigryphIntentProof and item.id == identifier for item in state.history):
        return None
    return PcDemigryphIntentProof(identifier, actor, state.round_state, mount, action_id+':execute')


def current_pc_demigryph_intent(state: PcMeleeState) -> PcDemigryphIntentProof | None:
    turn = state.round_state.active_turn
    if turn is None or not turn.action_slots:
        return None
    return next((item for item in reversed(state.history) if type(item) is PcDemigryphIntentProof
        and item.actor_id == turn.actor_id and item.source_round.round_number == state.round_state.round_number
        and item.slot_index == turn.action_slots[-1].index), None)


def demigryph_primary_qualities(intent: PcDemigryphIntentProof) -> tuple[QualityModifier, ...]:
    if type(intent) is not PcDemigryphIntentProof:
        raise TypeError('primary preparation requires its exact committed Demigryph intent')
    replace(intent)
    return ((QualityModifier(DEMIGRYPH_GRIM_RULE_ID, TestQuality.GRIM),)
        if intent.grim_leg is DemigryphGrimLeg.RIDER else ())


def pc_kernel_attack_types():
    """The explicit ordinary, paired mount and immediate strike families."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    return (PcAttackProof,PcDemigryphStrikeProof,PcImmediateStrikeProof)


def pc_kernel_resolution(proof):
    from towr.domain.pc_melee_result_models import PcAttackProof
    if type(proof) is PcAttackProof:
        return proof.execution.resolution
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    if type(proof) in (PcDemigryphStrikeProof,PcImmediateStrikeProof):
        return proof.resolution
    raise TypeError('expected an actual ordinary, paired mount or immediate K1 strike proof')


def latest_pc_kernel_attack(state, *, kernel_request_id=None):
    """An explicit strike-family lookup for Wound/ACK consumers, without fake receipts."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    for proof in reversed(state.history):
        if type(proof) in pc_kernel_attack_types() and (
                kernel_request_id is None or proof.request.kernel_request.id == kernel_request_id):
            return proof
    raise ValueError('no actual journaled K1 strike matches this follow-up source')


def build_pc_demigryph_strike(state: PcMeleeState):
    """Prepare the one optional mount strike from the real completed primary."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    intent = current_pc_demigryph_intent(state)
    if intent is None or _mount(state, intent.actor_id) is None or not _able(state, intent.actor_id):
        return None
    if any(type(item) is PcDemigryphStrikeProof and item.request.intent == intent for item in state.history):
        return None
    turn = state.round_state.active_turn
    receipt = turn.action_slots[intent.slot_index-1].execution
    if receipt is None:
        return None
    primary = next((item for item in reversed(state.history) if type(item) is PcAttackProof
        and item.execution.slot.execution == receipt), None)
    if (primary is None or primary.request.id != intent.primary_action_id
            or primary.request.state != intent.source_round):
        raise ValueError('Demigryph follow-up lacks its actual committed first Attack in this journal')
    if state.history.index(intent) >= state.history.index(primary):
        raise ValueError('Demigryph Grim decision must precede the first Attack')
    targets = _targets(state, intent.actor_id)
    if not targets:
        return None
    target = primary.request.target_id if primary.request.target_id in targets else targets[0]
    identifier = intent.id.removesuffix(':intent') + ':claws'
    from towr.domain.pc_mount_attack_models import prepare_pc_mounted_attack
    qualities = ((QualityModifier(DEMIGRYPH_GRIM_RULE_ID, TestQuality.GRIM),)
        if intent.grim_leg is DemigryphGrimLeg.CLAWS else ())
    from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
    weapon_intent = build_pc_explicit_attack_weapon_intent(state, intent.actor_id, target,
        identifier, mount_attack=True)
    kernel, protection = prepare_pc_mounted_attack(state, intent.actor_id, target, identifier,
        extra_qualities=qualities, weapon_intent=weapon_intent)
    return PcDemigryphStrikeRequest(identifier, intent, receipt, state.round_state, target, kernel), protection
