"""Pure PG159 Miscast task plans for the accepted single-Zone PC scene.

No effects, rolls or pool cleanup happen here. The native owner applies each
task against the current source and completes its mandatory consequences before
moving to the next one. Unknown spatial/GM-dependent continuations remain None.
"""
from dataclasses import dataclass
from enum import Enum

from towr.domain.magic_models import MiscastTableEntryId


class PcMagicTaskKind(str, Enum):
    DAMAGE = 'damage'
    STAGGER = 'stagger'
    PRONE = 'prone'
    NEXT_TEST_PENALTY = 'next_test_penalty'
    BLINDED = 'blinded'
    RANDOM_WOUND = 'random_wound'
    FIXED_EARS = 'fixed_ears'
    DEATH = 'death'
    FELLOWSHIP_GRIM = 'fellowship_grim'
    AWARENESS_GRIM = 'awareness_grim'
    NOTE = 'note'


def _identifier(value: str, name: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f'{name} requires a nonempty exact string')


@dataclass(frozen=True, slots=True)
class PcMagicTask:
    id: str
    kind: PcMagicTaskKind
    target_id: str
    value: int = 0
    note: MiscastTableEntryId | None = None
    affected_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.id, 'magic task ID')
        _identifier(self.target_id, 'magic task target')
        if type(self.kind) is not PcMagicTaskKind:
            raise TypeError('magic task needs its typed closed effect kind')
        if type(self.value) is not int:
            raise TypeError('magic task value must be an exact integer')
        if self.kind is PcMagicTaskKind.DAMAGE:
            if self.value < 1:
                raise ValueError('direct magical Damage must be positive')
        elif self.kind is PcMagicTaskKind.NEXT_TEST_PENALTY:
            if self.value != -1:
                raise ValueError('Hideous Stench changes its next Test by exactly -1d')
        elif self.kind is PcMagicTaskKind.FIXED_EARS:
            if self.value != 11:
                raise ValueError('Ear Damage must retain fixed Wounds Table result11')
        elif self.value != 0:
            raise ValueError('this magic task does not carry a numeric amount')
        if self.note is not None and type(self.note) is not MiscastTableEntryId:
            raise TypeError('magic task note must preserve its typed Miscast entry')
        if self.kind is PcMagicTaskKind.NOTE and self.note is None:
            raise ValueError('a nonnumeric Miscast note must identify its actual entry')
        _ordered_ids(self.affected_ids, 'magic task affected IDs')


def _ordered_ids(values: tuple[str, ...], name: str) -> None:
    if type(values) is not tuple:
        raise TypeError(f'{name} must be an ordered tuple')
    for value in values:
        _identifier(value, name)
    if len(set(values)) != len(values):
        raise ValueError(f'{name} cannot repeat a target')


_UNSUPPORTED = frozenset((
    MiscastTableEntryId.OBJECTS_TRANSFIGURED,
    MiscastTableEntryId.RANDOM_TRANSPORT,
    MiscastTableEntryId.SPELL_RECAST,
    MiscastTableEntryId.ZONE_HAZARD,
    MiscastTableEntryId.DAEMON_RIFT,
    MiscastTableEntryId.FASCINATING_RIFT,
))
_SCENE_NOTES = frozenset((
    MiscastTableEntryId.SENSE_OF_LOSS,
    MiscastTableEntryId.NAUSEATING_WAVE,
    MiscastTableEntryId.FOOD_SPOILED,
    MiscastTableEntryId.UNNATURAL_WEATHER,
))
_CASTER_NOTES = frozenset((
    MiscastTableEntryId.SHADOW_CHITTERING,
    MiscastTableEntryId.TRUTHBOUND,
    MiscastTableEntryId.FEARED_FOE_ILLUSION,
))


def pc_miscast_tasks(
    entry: MiscastTableEntryId,
    source_id: str,
    caster_id: str,
    party_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
) -> tuple[PcMagicTask, ...] | None:
    """Snapshot ordered affected actors; do not select replacement GM effects.

    Scene premises are explicit in ADR-0120: daylight, all actors in the same
    Close scene, no Give Ground route, Minions rather than Monstrosities, and a
    harmless minor Elementalism manifestation for Arcane Spill.
    """
    if type(entry) is not MiscastTableEntryId:
        raise TypeError('Miscast task planning requires its actual typed table entry')
    _identifier(source_id, 'Miscast source ID')
    _identifier(caster_id, 'Miscast caster ID')
    _ordered_ids(party_ids, 'Miscast party IDs')
    _ordered_ids(enemy_ids, 'Miscast enemy IDs')
    actors = (*party_ids, *enemy_ids)
    if caster_id not in party_ids:
        raise ValueError('this PC Miscast must retain its living party caster')
    if len(set(actors)) != len(actors):
        raise ValueError('Miscast party and enemy IDs must be distinct')
    if entry in _UNSUPPORTED:
        return None
    tasks: list[PcMagicTask] = []

    def add(kind: PcMagicTaskKind, target: str, value: int = 0,
            affected: tuple[str, ...] = ()) -> None:
        tasks.append(PcMagicTask(f'{source_id}:{len(tasks)}:{kind.value}:{target}',
            kind, target, value, entry, affected))

    if entry in _SCENE_NOTES:
        add(PcMagicTaskKind.NOTE, caster_id, affected=actors)
    elif entry in _CASTER_NOTES:
        add(PcMagicTaskKind.NOTE, caster_id, affected=(caster_id,))
    elif entry is MiscastTableEntryId.ARCANE_SPILL:
        add(PcMagicTaskKind.STAGGER, caster_id)
        add(PcMagicTaskKind.NOTE, caster_id, affected=actors)
    elif entry is MiscastTableEntryId.HIDEOUS_STENCH:
        for actor in actors:
            add(PcMagicTaskKind.NEXT_TEST_PENALTY, actor, -1)
        add(PcMagicTaskKind.FELLOWSHIP_GRIM, caster_id)
    elif entry is MiscastTableEntryId.SUNLIGHT_BLINDNESS:
        add(PcMagicTaskKind.BLINDED, caster_id)
    elif entry is MiscastTableEntryId.UNNATURAL_WIND:
        for actor in actors:
            add(PcMagicTaskKind.PRONE, actor)
    elif entry is MiscastTableEntryId.ARCANE_SIGHT:
        add(PcMagicTaskKind.AWARENESS_GRIM, caster_id)
        # The same typed entry retains Glorious magical-phenomena detection;
        # do not turn that context-specific benefit into general Glorious Tests.
        add(PcMagicTaskKind.NOTE, caster_id, affected=(caster_id,))
    elif entry is MiscastTableEntryId.INTERNAL_DAMAGE:
        add(PcMagicTaskKind.RANDOM_WOUND, caster_id)
    elif entry is MiscastTableEntryId.EAR_DAMAGE:
        for actor in actors:
            add(PcMagicTaskKind.FIXED_EARS, actor, 11)
    elif entry is MiscastTableEntryId.CATASTROPHIC_DEATH:
        add(PcMagicTaskKind.DEATH, caster_id)
    else:
        raise ValueError('Miscast entry has no agreed PC task plan')
    return tuple(tasks)
