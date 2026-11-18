"""Shared Horse facts and forced dismounts (PG1.4 V, Mounted Combat124).

The rider and trained Horse are one combat entity while mounted. The scene's
explicit GM policy sends the Horse away after a forced dismount; no independent
mount turn is manufactured. Physical worn armour remains a separate source fact.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.movement_models import MovementSpeed
from towr.domain.resolution_models import TargetInjuryPolicy

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeScenario
    from towr.domain.pc_melee_result_models import PcMeleeState


HORSE_NOBLE_STEED_RULE_ID = 'RULE-MOUNT-002:noble-steed'


class CombatMount(str, Enum):
    HORSE = 'horse'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(f'{label} requires an exact nonempty identifier')


@dataclass(frozen=True, slots=True)
class PcMountedState:
    actor_id: str
    mount: CombatMount
    mounted: bool

    def __post_init__(self):
        _identifier(self.actor_id, 'mounted actor')
        if type(self.mount) is not CombatMount:
            raise TypeError('mount requires its exact supported typed component')
        if type(self.mounted) is not bool:
            raise TypeError('mounted requires an exact bool')


@dataclass(frozen=True, slots=True)
class PcDismountProof:
    actor_id: str
    source_id: str
    history_index: int
    previous: PcMountedState
    state: PcMountedState
    source_injury: CharacterInjuryState | ProfileInjuryState

    def __post_init__(self):
        _identifier(self.actor_id, 'dismounted actor')
        _identifier(self.source_id, 'dismount source')
        if type(self.history_index) is not int or self.history_index < 0:
            raise ValueError('dismount history index must be an exact nonnegative integer')
        for bank in (self.previous, self.state):
            if type(bank) is not PcMountedState:
                raise TypeError('dismount requires exact typed mount states')
            replace(bank)
        if (self.previous.actor_id != self.actor_id or self.state.actor_id != self.actor_id
                or self.previous.mount is not self.state.mount
                or not self.previous.mounted or self.state.mounted):
            raise ValueError('forced dismount must change this same mount from true to false')
        if type(self.source_injury) not in (CharacterInjuryState, ProfileInjuryState):
            raise TypeError('dismount requires its exact actual typed injury witness')
        replace(self.source_injury)
        if not self.source_injury.conditions.has(Condition.PRONE):
            raise ValueError('forced dismount requires actual Prone after injury resolution')


def initial_pc_mounts(source: PcMeleeScenario) -> tuple[PcMountedState, ...]:
    """Only explicit source components create mounts; names never select rules."""
    mounted = []
    for member in source.party:
        mount = getattr(member, 'mount', None)
        if mount is not None:
            mounted.append(PcMountedState(member.actor_id, mount, True))
    for enemy in source.enemies:
        components = enemy.definition.generated_components
        mount = getattr(components, 'mount', None) if components is not None else None
        if mount is not None:
            mounted.append(PcMountedState(enemy.state.actor_id, mount, True))
    if len({member.actor_id for member in mounted}) != len(mounted):
        raise ValueError('mounted source actor IDs must be unique')
    if mounted and source.battlefield is None:
        raise ValueError('a mounted encounter requires its explicit battlefield')
    return tuple(mounted)


def _known_actor(source, actor):
    _identifier(actor, 'mount query actor')
    if actor not in (*source.pc_activation_order, *source.enemy_activation_order):
        raise ValueError('mount query actor must belong to the encounter source')


def _mounted_entry(state, actor):
    _known_actor(state.source, actor)
    return next((member for member in state.mounts if member.actor_id == actor), None)


def pc_is_mounted(state: PcMeleeState, actor: str) -> bool:
    member = _mounted_entry(state, actor)
    return member is not None and member.mounted


def mount_resilience_bonus(state: PcMeleeState, actor: str) -> int:
    """PG97: this bonus counts as armoured, but is not physically worn armour."""
    return int(pc_is_mounted(state, actor))


def pc_mount_speed(state: PcMeleeState, actor: str, base_speed: MovementSpeed) -> MovementSpeed:
    if type(base_speed) is not MovementSpeed:
        raise TypeError('mount speed needs the exact current base speed')
    mounted = pc_is_mounted(state, actor)
    # A current Slow restriction (for example an actual Wound) still applies.
    return MovementSpeed.FAST if mounted and base_speed is not MovementSpeed.SLOW else base_speed


def pc_mounted_attack_effects(state: PcMeleeState, actor: str, target: str,
        *, is_charge: bool) -> tuple[ProneBeforeGiveGroundSpec, ...]:
    """The action owner supplies actual Charge, never a voluntary modifier flag."""
    _known_actor(state.source, target)
    if actor == target:
        raise ValueError('mounted attack target must differ from its actor')
    if type(is_charge) is not bool:
        raise TypeError('mounted attack needs an exact actual-Charge bool')
    mounted = pc_is_mounted(state, actor)
    if (not mounted or not is_charge or target in state.source.enemy_activation_order
            and state.enemy(target).definition.injury_policy is TargetInjuryPolicy.MONSTROSITY):
        return ()
    return (ProneBeforeGiveGroundSpec(HORSE_NOBLE_STEED_RULE_ID,
        affects_monstrosities=False),)


def _source_id(source, actor, history_index):
    return f'{source.id}:dismount:{history_index}:{actor}'


def _injury(state, actor):
    return (state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)


def expected_pc_dismount(state: PcMeleeState) -> PcDismountProof | None:
    # Near Miss and queued injury consequences must settle first. A pending
    # spell, however, must not let an already-Prone rider retain Horse bonuses.
    if state.pending_wound is not None or state.pending:
        return None
    for member in state.mounts:
        injury = _injury(state, member.actor_id)
        if member.mounted and injury.conditions.has(Condition.PRONE):
            index = len(state.history)
            return PcDismountProof(member.actor_id, _source_id(state.source, member.actor_id, index),
                index, member, replace(member, mounted=False), injury)
    return None


def updated_pc_mounts(state: PcMeleeState, proof: PcDismountProof) -> tuple[PcMountedState, ...]:
    if type(proof) is not PcDismountProof:
        raise TypeError('mount transition requires its exact forced-dismount proof')
    replace(proof)
    if proof != expected_pc_dismount(state):
        raise ValueError('dismount differs from the actual current Prone injury and source prefix')
    return tuple(proof.state if member.actor_id == proof.actor_id else member
        for member in state.mounts)


def validate_pc_mounts(state: PcMeleeState) -> None:
    """Replay the source-bound bank; the owner also checks actual injury prefixes."""
    if type(state.mounts) is not tuple or any(type(member) is not PcMountedState
            for member in state.mounts):
        raise TypeError('mount bank requires an exact ordered tuple of typed states')
    for member in state.mounts:
        replace(member)
    bank = initial_pc_mounts(state.source)
    for index, proof in enumerate(state.history):
        if type(proof) is not PcDismountProof:
            continue
        replace(proof)
        if (proof.history_index != index
                or proof.source_id != _source_id(state.source, proof.actor_id, index)):
            raise ValueError('dismount proof must retain its exact source history position')
        previous = next((member for member in bank if member.actor_id == proof.actor_id), None)
        if previous != proof.previous:
            raise ValueError('dismount proof changes an unavailable or already-departed mount')
        expected_injury_type = (CharacterInjuryState
            if proof.actor_id in state.source.pc_activation_order else ProfileInjuryState)
        if type(proof.source_injury) is not expected_injury_type:
            raise TypeError('dismount injury witness differs from the actual rider kind')
        bank = tuple(proof.state if member.actor_id == proof.actor_id else member for member in bank)
    if state.mounts != bank:
        raise ValueError('mount bank differs from the initial source and actual dismount history')
