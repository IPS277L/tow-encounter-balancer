"""Pure admission for one Curse of Cowardly Flight action (ADR-0035).

PG1.4: Combat Actions pp116-117; Casting/Miscasts pp156-157;
Formal Spells p160; Battle Magic / Curse of Cowardly Flight p162.
These scope checks do not execute a Test, choose targets or advance a turn.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum

from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatRoundState, ImproviseKind,
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
    """One healthy Minion enemy, factually unable to Give Ground."""

    actor_id: str
    willpower_profile: InlineProfile
    injury: ProfileInjuryState
    can_give_ground: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "target actor id")
        _normal_profile(self.willpower_profile, "willpower_profile")
        if not isinstance(self.injury, ProfileInjuryState):
            raise TypeError("target injury must be a ProfileInjuryState")
        if self.injury != ProfileInjuryState(0, 1):
            raise ValueError("Casting boundary requires healthy Minions without Conditions")
        if not isinstance(self.can_give_ground, bool):
            raise TypeError("can_give_ground must be an explicit boolean")
        if self.can_give_ground:
            raise ValueError("Casting boundary does not yet support Give Ground")


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
        object.__setattr__(self, "targets", targets)


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
