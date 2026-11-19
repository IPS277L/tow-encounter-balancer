"""Explicit line-arena GM features and pure PG115 queries, ADR-0140D.

Cover/concealment confirms impeded fire at occupants, not hidden status.
Visibility facts are directed; neither those facts nor a weapon erases Blinded.
Consumers only describe real geometry. Tests, movement and Conditions retain
their existing action owners.
"""
from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import DiceModifier,Skill


SCENE_COVER_RULE_ID='RULE-COMBAT-013:cover-and-concealment'


def _id(value):
    if type(value) is not str or not value.strip():
        raise TypeError('scene visibility needs exact nonempty actor identifiers')


@dataclass(frozen=True,slots=True)
class PcZoneFeatures:
    index: int
    difficult_terrain: bool = False
    cover: bool = False
    concealment: bool = False

    def __post_init__(self):
        if type(self.index) is not int:
            raise TypeError('scene Zone index must be an exact integer')
        for name in ('difficult_terrain','cover','concealment'):
            if type(getattr(self,name)) is not bool:
                raise TypeError('scene Zone features require exact booleans')


@dataclass(frozen=True,slots=True)
class PcVisibilityFact:
    observer_id: str
    target_id: str
    visible: bool

    def __post_init__(self):
        _id(self.observer_id);_id(self.target_id)
        if self.observer_id==self.target_id:
            raise ValueError('scene visibility must refer to two distinct actors')
        if type(self.visible) is not bool:
            raise TypeError('scene visibility requires an exact bool')


def validate_scene_feature_source(features,visibility,darkness,initial_range):
    for values,cls in ((features,PcZoneFeatures),(visibility,PcVisibilityFact)):
        if type(values) is not tuple or any(type(value) is not cls for value in values):
            raise TypeError('scene features require exact ordered tuples of typed facts')
        for value in values:replace(value)
    if type(darkness) is not bool:
        raise TypeError('scene darkness requires an exact bool')
    from towr.domain.pc_battlefield_models import _INITIAL_ZONE_OFFSETS
    offset=_INITIAL_ZONE_OFFSETS[initial_range]
    if any(not -3<=feature.index<=offset+3 for feature in features):
        raise ValueError('scene feature Zone must exist in the actual configured line')
    if len({feature.index for feature in features})!=len(features):
        raise ValueError('scene feature Zones must be unique')
    if len({(fact.observer_id,fact.target_id) for fact in visibility})!=len(visibility):
        raise ValueError('directed scene visibility facts must be unique')


def validate_scene_visibility_actors(spec,actor_ids):
    if spec is None:return
    from towr.domain.pc_battlefield_models import PcBattlefieldSpec
    if type(spec) is not PcBattlefieldSpec:
        raise TypeError('scene visibility needs the exact battlefield source')
    replace(spec)
    known=set(actor_ids)
    if any(fact.observer_id not in known or fact.target_id not in known for fact in spec.visibility):
        raise ValueError('scene visibility requires actual actors at every admitted NPC count')


def scene_zone_features(state,zone_id):
    """Only the source's explicitly indexed ground Zone owns these features."""
    _id(zone_id)
    spec=state.source.battlefield
    if spec is None:return None
    return next((feature for feature in spec.zone_features
        if f'{state.source.facts.zone_id}:zone:{feature.index}'==zone_id),None)


@dataclass(frozen=True,slots=True)
class PcSceneAttackVisibility:
    actor_id: str
    target_id: str
    target_zone_id: str | None
    visible: bool
    cover: bool
    concealment: bool
    modifiers: tuple[DiceModifier,...]


def scene_attack_visibility(state,actor,target,skill):
    """Read actual placements and source facts without changing awareness."""
    _id(actor);_id(target)
    if type(skill) is not Skill:
        raise TypeError('scene attack visibility requires the actual typed Skill')
    known=(*state.source.pc_activation_order,*state.source.enemy_activation_order)
    if actor not in known or target not in known or actor==target:
        raise ValueError('scene attack visibility requires two actual encounter actors')
    ranged=skill in (Skill.SHOOTING,Skill.THROWING)
    conditions=(state.participant(actor).injury.conditions if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury.conditions)
    visible=not (ranged and conditions.has(Condition.BLINDED))
    zone=None;cover=concealment=False
    spec=state.source.battlefield
    if spec is not None:
        from towr.domain.pc_battlefield_models import battlefield_range
        battlefield=state.battlefield
        zone=battlefield.spatial.placement_for(target).zone_id
        feature=scene_zone_features(state,zone)
        cover=feature.cover if feature else False
        concealment=feature.concealment if feature else False
        fact=next((fact for fact in spec.visibility
            if fact.observer_id==actor and fact.target_id==target),None)
        visible=visible and (fact is None or fact.visible)
        if spec.darkness and battlefield_range(battlefield,actor,target) in (
                RangedWeaponRange.LONG,RangedWeaponRange.EXTREME):
            visible=False
    modifiers=(DiceModifier(SCENE_COVER_RULE_ID,-1),) if ranged and (cover or concealment) else ()
    return PcSceneAttackVisibility(actor,target,zone,visible,cover,concealment,modifiers)


def difficult_terrain_crossed(state,actor,before,path,*,moved,move_carefully=False,flying=False):
    """Describe the real frozen route; no bypass can be invented by a flag.

    ``moved`` also covers actual repositioning inside one Zone, whose route is
    empty. Ground features at departure and arrival both belong to that move.
    The caller owns its movement proof and the ensuing K1 Athletics Test.
    """
    from towr.domain.pc_battlefield_models import PcBattlefieldState,battlefield_is_midair
    from towr.domain.pc_mount_models import mounted_can_fly
    from towr.domain.turn_models import CombatActionKind,ManoeuvreKind
    _id(actor)
    if type(before) is not PcBattlefieldState:
        raise TypeError('terrain crossing requires the frozen actual battlefield')
    replace(before)
    if actor not in (*state.source.pc_activation_order,*state.source.enemy_activation_order):
        raise ValueError('terrain crossing requires an actual actor')
    for flag in (moved,move_carefully,flying):
        if type(flag) is not bool:
            raise TypeError('terrain crossing uses exact movement facts')
    if type(path) is not tuple or any(type(zone) is not str or not zone.strip() for zone in path):
        raise TypeError('terrain crossing requires its actual ordered Zone path')
    if state.battlefield is None or (before.spatial.graph,before.air_to_ground)!=(
            state.battlefield.spatial.graph,state.battlefield.air_to_ground):
        raise ValueError('terrain crossing cannot replace the configured geometry')
    origin=before.spatial.placement_for(actor).zone_id
    previous=origin
    for zone in path:
        if not before.spatial.graph.contains(zone) or not before.spatial.graph.are_adjacent(previous,zone):
            raise ValueError('terrain crossing requires a connected actual movement route')
        previous=zone
    if path and not moved:
        raise ValueError('a route cannot claim no movement')
    if move_carefully:
        turn=state.round_state.active_turn
        if turn is None or turn.actor_id!=actor or not turn.action_slots or (
                turn.action_slots[-1].declaration.kind is not CombatActionKind.MANOEUVRE
                or turn.action_slots[-1].declaration.manoeuvre is not ManoeuvreKind.MOVE_CAREFULLY):
            raise ValueError('terrain bypass requires the real Move Carefully action')
    if flying and (not mounted_can_fly(state,actor) or not any(
            battlefield_is_midair(before,zone,zone=True) for zone in (origin,*path))):
        raise ValueError('terrain flight bypass requires the actual aerial movement')
    if not moved or move_carefully or flying:return ()
    return tuple(dict.fromkeys(zone for zone in (origin,*path)
        if not battlefield_is_midair(before,zone,zone=True)
        and (feature:=scene_zone_features(state,zone)) is not None and feature.difficult_terrain))
