"""Shared trained mounts and forced dismounts (PG1.4 V124, GM1.1 VII135/175–176).

The rider and trained Horse are one combat entity while mounted. The scene's
explicit GM policy sends the Horse away after a forced dismount; no independent
mount turn is manufactured. Physical worn armour remains a separate source fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import ProneBeforeGiveGroundSpec, ConditionAfterGiveGroundSpec, SecondaryEffectSpec
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.movement_models import MovementSpeed
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.brawn_impact_models import BrawnDisplacementRequest, BrawnAttackEffect

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeScenario
    from towr.domain.pc_melee_result_models import PcMeleeState


HORSE_NOBLE_STEED_RULE_ID = 'RULE-MOUNT-002:noble-steed'
PEGASUS_KNIGHTS_RULE_ID = 'BOOK-GM-GUIDE:1.1:p176:pegasus-knights'
ELVEN_STEED_RULE_ID = 'RULE-MOUNT-002:elven-steed'
DEMIGRYPH_FEARSOME_RULE_ID = 'BOOK-GM-GUIDE:1.1:p175:demigryph-knights:fearsome'
SKELETAL_STEED_FRIGHTENING_RULE_ID = 'BOOK-GM-GUIDE:1.1:p135:skeletal-steed:frightening'


class CombatMount(str, Enum):
    HORSE = 'horse'
    BRETONNIAN_WARHORSE = 'bretonnian_warhorse'
    ELVEN_STEED = 'elven_steed'
    SKELETAL_STEED = 'skeletal_steed'
    DEMIGRYPH = 'demigryph'
    PEGASUS = 'pegasus'


class RiderKind(str, Enum):
    HUMAN = 'human'
    ELF = 'elf'
    OTHER = 'other'


def validate_mount_rider(mount: CombatMount | None, rider_kind: RiderKind | None) -> None:
    """Admit the explicit book eligibility, without an implicit Human default.

    Ordinary horses do not have a rider-kind requirement, so their source omits
    this conditional fact. The beastly rider benefits are restricted by GM175–176.
    """
    if mount is not None and type(mount) is not CombatMount:
        raise TypeError('mount requires its exact supported typed component or None')
    if rider_kind is not None and type(rider_kind) is not RiderKind:
        raise TypeError('rider kind requires its exact typed fact or None')
    if mount not in (CombatMount.DEMIGRYPH, CombatMount.PEGASUS):
        if rider_kind is not None:
            raise ValueError('rider kind belongs to the Demigryph/Pegasus source')
        return
    if mount is CombatMount.DEMIGRYPH and rider_kind is not RiderKind.HUMAN:
        raise ValueError('Demigryph rider benefits require an explicit Human rider')
    if mount is CombatMount.PEGASUS and rider_kind not in (RiderKind.HUMAN, RiderKind.ELF):
        raise ValueError('Pegasus rider benefits require an explicit Human or Elf rider')


def mount_source_resilience_bonus(mount: CombatMount | None) -> int:
    """Base printed rider bonus; source admission separately checks rider kind.

    Barding is a distinct equipment source and is not implied by the mount.
    """
    if mount is not None and type(mount) is not CombatMount:
        raise TypeError('mount requires its exact supported typed component or None')
    return 0 if mount is None else 2 if mount is CombatMount.DEMIGRYPH else 1


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
    brawn_drag: BrawnDisplacementRequest | None = field(default=None, kw_only=True)

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
        if self.brawn_drag is not None:
            if type(self.brawn_drag) is not BrawnDisplacementRequest:
                raise TypeError('dragged dismount requires its exact actual Brawn consequence')
            replace(self.brawn_drag)
            if self.brawn_drag.kind is not BrawnAttackEffect.DISMOUNT or self.brawn_drag.target_id != self.actor_id:
                raise ValueError('dragged dismount belongs to another actual target or alternative')
        elif not self.source_injury.conditions.has(Condition.PRONE):
            raise ValueError('forced dismount requires actual Prone after injury resolution')


def initial_pc_mounts(source: PcMeleeScenario) -> tuple[PcMountedState, ...]:
    """Only explicit source components create mounts; names never select rules."""
    mounted = []
    for member in source.party:
        mount = getattr(member, 'mount', None)
        validate_mount_rider(mount, getattr(member, 'rider_kind', None))
        if mount is not None:
            mounted.append(PcMountedState(member.actor_id, mount, True))
    for enemy in source.enemies:
        components = enemy.definition.generated_components
        mount = getattr(components, 'mount', None) if components is not None else None
        validate_mount_rider(mount, getattr(components, 'rider_kind', None))
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


def _rider_source(state, actor):
    _known_actor(state.source, actor)
    return (state.source.participant(actor) if actor in state.source.pc_activation_order
        else state.enemy(actor).definition.generated_components)


def _active_mount(state, actor):
    member = _mounted_entry(state, actor)
    source = _rider_source(state, actor)
    mount = getattr(source, 'mount', None)
    validate_mount_rider(mount, getattr(source, 'rider_kind', None))
    if member is None:
        if mount is not None:
            raise ValueError('mounted source must retain its actual mount state')
        return None
    replace(member)
    if member.mount is not mount:
        raise ValueError('mount state differs from the rider source component')
    return member.mount if member.mounted else None


def pc_is_mounted(state: PcMeleeState, actor: str) -> bool:
    return _active_mount(state, actor) is not None


def mount_resilience_bonus(state: PcMeleeState, actor: str) -> int:
    """PG97: this bonus counts as armoured, but is not physically worn armour."""
    mount = _active_mount(state, actor)
    if mount is None:
        return 0
    from towr.domain.armour_models import ArmourLoadout
    armour = getattr(_rider_source(state, actor), 'armour', None)
    if armour is not None:
        if type(armour) is not ArmourLoadout:
            raise TypeError('mounted armour requires its exact typed equipment source')
        replace(armour)
    return mount_source_resilience_bonus(mount) + int(armour is not None and armour.barding)


def mounted_armour_test_exemptions(state: PcMeleeState, actor: str, skill: Skill,
        *, oppose_attack: bool = False, control_mount: bool = False) -> dict[str, bool]:
    """Return only printed exemptions; they neither change Agility nor its cap."""
    if type(skill) is not Skill:
        raise TypeError('mounted Test requires its exact typed Skill')
    if type(oppose_attack) is not bool or type(control_mount) is not bool:
        raise TypeError('mounted Test context requires exact bool facts')
    mount = _active_mount(state, actor)
    bretonnian = (mount is CombatMount.BRETONNIAN_WARHORSE
        and (oppose_attack or control_mount))
    demigryph = mount is CombatMount.DEMIGRYPH
    return dict(ignore_heavy=bretonnian or demigryph,
        ignore_full_plate=demigryph, ignore_barding=bretonnian,
        mounted=mount is not None)


def mounted_test_modifiers(state: PcMeleeState, actor: str, skill: Skill,
        *, oppose_attack: bool = False, control_mount: bool = False) -> tuple[DiceModifier, ...]:
    """PG124: an Elven Steed helps only Athletics control/opposition Tests."""
    if type(skill) is not Skill:
        raise TypeError('mounted Test requires its exact typed Skill')
    if type(oppose_attack) is not bool or type(control_mount) is not bool:
        raise TypeError('mounted Test context requires exact bool facts')
    mount = _active_mount(state, actor)
    return ((DiceModifier(ELVEN_STEED_RULE_ID, 1),)
        if mount is CombatMount.ELVEN_STEED and skill is Skill.ATHLETICS
            and (oppose_attack or control_mount) else ())


def mounted_can_fly(state: PcMeleeState, actor: str) -> bool:
    """Actual current Fly capability, distinct from permission for a move."""
    return _active_mount(state, actor) is CombatMount.PEGASUS


def mounted_give_ground_broken(state: PcMeleeState, actor: str, attack_skill: Skill) -> bool:
    """GM175 Fearsome; GM135 Skeletal Steed grants Frightening, not all attacks."""
    if type(attack_skill) is not Skill:
        raise TypeError('mounted attack requires its exact typed Skill')
    mount = _active_mount(state, actor)
    return mount is CombatMount.DEMIGRYPH or (mount is CombatMount.SKELETAL_STEED
        and attack_skill in (Skill.MELEE, Skill.BRAWN))


def pc_mount_speed(state: PcMeleeState, actor: str, base_speed: MovementSpeed) -> MovementSpeed:
    if type(base_speed) is not MovementSpeed:
        raise TypeError('mount speed needs the exact current base speed')
    mounted = pc_is_mounted(state, actor)
    # A current Slow restriction (for example an actual Wound) still applies.
    return MovementSpeed.FAST if mounted and base_speed is not MovementSpeed.SLOW else base_speed


def pc_mounted_attack_effects(state: PcMeleeState, actor: str, target: str,
        *, is_charge: bool, attack_skill: Skill = Skill.MELEE) -> tuple[SecondaryEffectSpec, ...]:
    """The action owner supplies actual Charge, never a voluntary modifier flag."""
    _known_actor(state.source, target)
    if actor == target:
        raise ValueError('mounted attack target must differ from its actor')
    if type(is_charge) is not bool:
        raise TypeError('mounted attack needs an exact actual-Charge bool')
    if type(attack_skill) is not Skill:
        raise TypeError('mounted attack needs its exact actual Skill')
    mount = _active_mount(state, actor)
    if mount is None:
        return ()
    after_ground = ()
    if mounted_give_ground_broken(state, actor, attack_skill):
        # PG76: Frightening does not affect an enemy that is Fearsome. The
        # current generated source grants Fearsome through a real Demigryph.
        immune = mount is CombatMount.SKELETAL_STEED and _active_mount(state, target) is CombatMount.DEMIGRYPH
        if not immune:
            after_ground = (ConditionAfterGiveGroundSpec(Condition.BROKEN,
                DEMIGRYPH_FEARSOME_RULE_ID if mount is CombatMount.DEMIGRYPH else SKELETAL_STEED_FRIGHTENING_RULE_ID),)
    if mount is CombatMount.DEMIGRYPH or not is_charge:
        return after_ground
    pegasus = mount is CombatMount.PEGASUS
    if (not pegasus and target in state.source.enemy_activation_order
            and state.enemy(target).definition.injury_policy is TargetInjuryPolicy.MONSTROSITY):
        return after_ground
    return (ProneBeforeGiveGroundSpec(
        PEGASUS_KNIGHTS_RULE_ID if pegasus else HORSE_NOBLE_STEED_RULE_ID,
        affects_monstrosities=pegasus), *after_ground)


def _source_id(source, actor, history_index):
    return f'{source.id}:dismount:{history_index}:{actor}'


def _injury(state, actor):
    return (state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)


def expected_pc_dismount(state: PcMeleeState) -> PcDismountProof | None:
    # Near Miss and queued injury consequences must settle first. A pending
    # spell, however, must not let an already-Prone rider retain Horse bonuses.
    if state.pending_wound is not None:
        return None
    from towr.domain.pc_brawn_displacement_models import _pending, _bound_displacement
    drag = _pending(state)
    if drag is not None and drag.kind is BrawnAttackEffect.DISMOUNT:
        _bound_displacement(state, drag)
        member = next((member for member in state.mounts if member.actor_id == drag.target_id), None)
        if member is None or not member.mounted:
            raise ValueError('actual Brawn drag requires its still-mounted target')
        index = len(state.history)
        return PcDismountProof(member.actor_id, _source_id(state.source, member.actor_id, index),
            index, member, replace(member, mounted=False), _injury(state, member.actor_id), brawn_drag=drag)
    if state.pending:
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
        raise ValueError('dismount differs from its actual current Prone/drag source prefix')
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
        if proof.brawn_drag is not None:
            from towr.domain.pc_melee_result_models import PcAttackProof
            from towr.domain.pc_demigryph_models import pc_kernel_resolution
            request = proof.brawn_drag
            source = next((candidate for candidate in state.history[:index]
                if type(candidate) is PcAttackProof
                and candidate.request.kernel_request.id == request.resolution_id), None)
            if (source is None or source.request.actor_id != request.actor_id
                    or source.request.target_id != request.target_id
                    or request not in pc_kernel_resolution(source).follow_ups
                    or getattr(source.weapon_intent, 'brawn_effect', None) is not BrawnAttackEffect.DISMOUNT):
                raise ValueError('dragged mount history lacks its actual frozen successful Brawn Attack')
        bank = tuple(proof.state if member.actor_id == proof.actor_id else member for member in bank)
    if state.mounts != bank:
        raise ValueError('mount bank differs from the initial source and actual dismount history')
