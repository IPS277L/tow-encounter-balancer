"""Pure admission for one Curse of Cowardly Flight action (ADR-0035).

PG1.4: Combat Actions pp116-117; Casting/Miscasts pp156-157;
Formal Spells p160; Battle Magic / Curse of Cowardly Flight p162.
These scope checks do not execute a Test, choose targets or advance a turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.crushed_rib_test_models import (
    CrushedRibCastingPreparationResult, _integer, _magic, _ordered, _test, _typed,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import CastingTestRequest, WizardMagicState
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatRoundState, CombatSide, ImproviseKind,
)


BATTLE_MAGIC_LORE_ID = "lore:battle-magic"


class CowardlyFlightCastingPolicy(str, Enum):
    CAST_WHEN_READY = "cast_when_ready"


@dataclass(frozen=True, slots=True)
class CastingCasterDefinition:
    """Reusable numeric Wizard definition; id is not a battle actor ID."""

    id: str
    source_rule_id: str
    wizard_level: int
    casting_profile: InlineProfile

    def __post_init__(self) -> None:
        _identifier(self.id, "caster definition id")
        _identifier(self.source_rule_id, "caster source rule id")
        if not isinstance(self.wizard_level, int) or isinstance(self.wizard_level, bool):
            raise TypeError("wizard_level must be an integer")
        if not 1 <= self.wizard_level <= 4:
            raise ValueError("Casting boundary supports Wizard Level 1 through 4")
        _normal_profile(self.casting_profile, "casting_profile")


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingTarget:
    """One living Minion enemy with explicit Give Ground availability.

    ADR-0036/0046 permit Staggered, Drained, Broken and standalone Prone
    under the unchanged normal Willpower profile (PG1.4 pp122-123, 162).
    can_give_ground is effective availability, not an authored route fact.
    """

    actor_id: str
    willpower_profile: InlineProfile
    injury: ProfileInjuryState
    can_give_ground: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "target actor id")
        _normal_profile(self.willpower_profile, "willpower_profile")
        if not isinstance(self.injury, ProfileInjuryState):
            raise TypeError("target injury must be a ProfileInjuryState")
        if self.injury.wound_limit != 1 or self.injury.defeated:
            raise ValueError("Casting boundary requires living Minions")
        if not self.injury.conditions.conditions <= {
                Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN, Condition.PRONE}:
            raise ValueError("Casting target has unsupported Conditions for normal Willpower")
        if not isinstance(self.can_give_ground, bool):
            raise TypeError("can_give_ground must be an explicit boolean")
        if self.injury.conditions.has(Condition.PRONE) and self.can_give_ground:
            raise ValueError('a Prone Curse target cannot Give Ground')


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingFacts:
    """Explicit caller assertions for this action, including target Willpower.

    Range, eligibility, knowledge and effect immunities are not inferred from
    numeric profiles/Zone names. No field silently supplies a GM decision.
    """

    caster_can_cast: bool
    knows_battle_magic: bool
    spell_memorised: bool
    caster_unarmoured: bool
    no_bulky_items: bool
    no_casting_opposition: bool
    no_mixing_winds: bool
    no_other_test_modifiers: bool
    no_potency_modifiers: bool
    no_effect_immunities: bool
    all_zone_enemies_included: bool
    target_zone_within_long_range: bool

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, bool):
                raise TypeError(f"Casting fact {item.name} must be an explicit boolean")
            if not value:
                raise ValueError(f"unsupported Casting fact: {item.name}")


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingRequest:
    """Admitted action input, without RNG or generated K1 execution requests.

    Caller owns the current magic snapshot for actor_id. WizardMagicState is
    actor-agnostic; this model cannot authenticate its historical ownership.
    Spatial placements must cover exactly the supplied round participants.
    Completed/excluded turns do not remove enemies from the target selection.
    """

    id: str
    caster: CastingCasterDefinition
    actor_id: str
    round_state: CombatRoundState
    slot_index: int
    magic_state: WizardMagicState
    spatial_state: SpatialBattleState
    selected_zone_id: str
    targets: tuple[CowardlyFlightCastingTarget, ...]
    facts: CowardlyFlightCastingFacts
    policy: CowardlyFlightCastingPolicy
    crushed_rib_preparation: CrushedRibCastingPreparationResult | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.id, "Casting request id")
        _identifier(self.actor_id, "casting actor id")
        _identifier(self.selected_zone_id, "selected Zone id")
        for value, expected, name in (
            (self.caster, CastingCasterDefinition, "caster"),
            (self.round_state, CombatRoundState, "round_state"),
            (self.magic_state, WizardMagicState, "magic_state"),
            (self.spatial_state, SpatialBattleState, "spatial_state"),
            (self.facts, CowardlyFlightCastingFacts, "facts"),
            (self.policy, CowardlyFlightCastingPolicy, "policy"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be a {expected.__name__}")
        if self.crushed_rib_preparation is not None:
            # Preserve original transported containers/facts before any existing
            # source normalization or equal-valued comparison can hide damage.
            validate_crushed_rib_casting_source(self)
        if not isinstance(self.slot_index, int) or isinstance(self.slot_index, bool):
            raise TypeError("slot_index must be an integer")
        if self.slot_index != 1:
            raise ValueError("Casting boundary supports only the standard first slot")
        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("casting actor must own the active turn")
        if len(turn.action_slots) != 1:
            raise ValueError("Casting boundary requires exactly one reserved action slot")
        slot = turn.action_slots[0]
        if slot.grant is not ActionSlotGrant.STANDARD or slot.executed:
            raise ValueError("Casting requires an unexecuted standard slot")
        expected_declaration = CombatActionDeclaration(
            CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
            improvise_approach_id=BATTLE_MAGIC_LORE_ID,
        )
        if slot.declaration != expected_declaration:
            raise ValueError("Casting requires a Battle Magic spell Improvise without an attack")
        if self.magic_state.miscast_dice > self.caster.wizard_level:
            raise ValueError("mandatory Miscast must be resolved before normal Casting")
        if self.magic_state.casting_lore_id not in (None, BATTLE_MAGIC_LORE_ID):
            raise ValueError("active Casting Lore must be Battle Magic")

        spatial = self.spatial_state
        if spatial.round_number != self.round_state.round_number:
            raise ValueError("spatial state belongs to another round")
        if not spatial.graph.contains(self.selected_zone_id):
            raise ValueError("selected Zone must exist in the spatial graph")
        placements = {p.entity_id: p for p in spatial.placements}
        if set(placements) != {p.entity_id for p in self.round_state.participants}:
            raise ValueError("spatial placements must match round participants exactly")
        for participant in self.round_state.participants:
            if placements[participant.entity_id].side_id != participant.side.value:
                raise ValueError("spatial side must match round participant side")
        if not isinstance(self.targets, (tuple, list)):
            raise TypeError("targets must be an ordered tuple or list")
        targets = tuple(self.targets)
        if not all(isinstance(t, CowardlyFlightCastingTarget) for t in targets):
            raise TypeError("targets must contain CowardlyFlightCastingTarget values")
        expected_targets = tuple(
            p.entity_id for p in self.round_state.participants
            if p.side is not turn.side
            and placements[p.entity_id].zone_id == self.selected_zone_id
        )
        if tuple(t.actor_id for t in targets) != expected_targets:
            raise ValueError("targets must match all selected Zone enemies in round participant order")
        if any(t.can_give_ground and t.actor_id in spatial.gave_ground_entity_ids for t in targets):
            raise ValueError("a target that already gave ground this round cannot Give Ground again")
        object.__setattr__(self, "targets", targets)
        preparation = self.crushed_rib_preparation
        if preparation is not None:
            if not isinstance(preparation, CrushedRibCastingPreparationResult):
                raise TypeError('Casting requires typed Crushed Rib preparation')
            # Re-admit the original witness before equality (bool/int and enum
            # aliases in frozen/unpickled nested objects must not be laundered).
            replace(preparation)
            original = preparation.source_request
            if original.actor_id != self.actor_id or original.casting != self.casting_test_request:
                raise ValueError('Crushed Rib preparation differs from the exact Casting action source')

    @property
    def casting_test_request(self) -> CastingTestRequest:
        """Original unmodified Test owned by this action, before injury effects."""
        return CastingTestRequest(self.id + ':casting', self.actor_id, BATTLE_MAGIC_LORE_ID,
            TestRequest(self.id + ':willpower', self.caster.casting_profile), self.magic_state)


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _normal_profile(value: InlineProfile, name: str) -> None:
    if not isinstance(value, InlineProfile):
        raise TypeError(f"{name} must be an InlineProfile")
    if value.pool_cap is not None:
        raise ValueError(f"{name} does not support a custom pool cap")


def strict_casting_round(combat: CombatRoundState) -> None:
    """Original round/receipt primitives on the explicit Crushed Rib edge."""
    _typed(combat, CombatRoundState)
    _integer(combat.round_number)
    for values in (combat.participants, combat.side_order, combat.completed_turn_entity_ids,
                   combat.excluded_turn_entity_ids):
        _ordered(values)
    for side in combat.side_order:
        _typed(side, CombatSide)
    for participant in combat.participants:
        replace(participant)
    turn = combat.active_turn
    if turn is not None:
        _typed(turn.side, CombatSide)
        _ordered(turn.action_slots)
        for slot in turn.action_slots:
            _integer(slot.index)
            _typed(slot.grant, ActionSlotGrant)
            replace(slot.declaration)
            if slot.execution is not None:
                replace(slot.execution.declaration)
                replace(slot.execution)
            replace(slot)
        replace(turn)
    replace(combat)


def validate_crushed_rib_casting_source(source: CowardlyFlightCastingRequest) -> None:
    """Readmit original explicit56 source facts before Test RNG; no mutation.

    Also used by the upper consumed branch, whose lower request is normal and
    therefore has no new preparation marker of its own.
    """
    _typed(source, CowardlyFlightCastingRequest)
    replace(source.facts)
    replace(source.caster)
    _test(source.casting_test_request.test)
    _magic(source.magic_state)
    strict_casting_round(source.round_state)
    _ordered(source.targets)
    for target in source.targets:
        replace(target)
        _test(TestRequest('crushed-rib:target-profile', target.willpower_profile))
        _integer(target.injury.wounds)
        _integer(target.injury.wound_limit)
        if type(target.injury.conditions.conditions) is not frozenset:
            raise TypeError('Crushed Rib Casting target Conditions must be an original frozenset')
        for condition in target.injury.conditions.conditions:
            _typed(condition, Condition)
        replace(target.injury)
    spatial = source.spatial_state
    _integer(spatial.round_number)
    for values in (spatial.placements, spatial.gave_ground_entity_ids, spatial.free_move_used_entity_ids,
                   spatial.difficult_terrain_tested_entity_ids, spatial.graph.zone_ids, spatial.graph.connections):
        _ordered(values)
    for placement in spatial.placements:
        replace(placement)
    for connection in spatial.graph.connections:
        replace(connection)
    replace(spatial.graph)
    replace(spatial)
