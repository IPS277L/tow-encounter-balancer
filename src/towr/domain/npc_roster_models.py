from __future__ import annotations

from dataclasses import dataclass

from towr.domain.attack_models import ResilienceProfile
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile, NpcAttackSelectionSnapshot
from towr.domain.protection_models import PROTECTION_SKILLS, ProtectionTestOption
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.turn_models import CombatSide, CombatTurnParticipant


@dataclass(frozen=True, slots=True)
class NpcProtectionProfile:
    source_rule_id: str
    skill: Skill
    test_profile: InlineProfile

    def __post_init__(self) -> None:
        _identifier(self.source_rule_id, "Protection source rule")
        if not isinstance(self.skill, Skill):
            raise TypeError("Protection skill must be a Skill")
        if self.skill not in PROTECTION_SKILLS:
            raise ValueError("unsupported Protection skill")
        if not isinstance(self.test_profile, InlineProfile):
            raise TypeError("NPC Protection requires an InlineProfile")


@dataclass(frozen=True, slots=True)
class NpcDefinition:
    """Supplied numeric profile, not a complete NPC catalogue entry."""

    id: str
    source_rule_id: str
    injury_policy: TargetInjuryPolicy
    wound_limit: int | None
    resilience: ResilienceProfile
    attacks: tuple[NpcAttackProfile, ...]
    protection: tuple[NpcProtectionProfile, ...]

    def __post_init__(self) -> None:
        _identifier(self.id, "NPC definition id")
        _identifier(self.source_rule_id, "NPC source rule")
        if not isinstance(self.injury_policy, TargetInjuryPolicy):
            raise TypeError("NPC injury_policy must be a TargetInjuryPolicy")
        if self.injury_policy not in (
            TargetInjuryPolicy.MINION, TargetInjuryPolicy.BRUTE, TargetInjuryPolicy.CHAMPION,
        ):
            raise ValueError("NPC roster supports Minion, Brute and Champion only")
        if self.injury_policy is TargetInjuryPolicy.CHAMPION:
            if self.wound_limit is not None:
                raise ValueError("Champion has no profile wound limit")
        else:
            if not isinstance(self.wound_limit, int) or isinstance(self.wound_limit, bool):
                raise TypeError("profile wound_limit must be an integer")
            if self.wound_limit < 1:
                raise ValueError("profile wound_limit must be positive")
            if self.injury_policy is TargetInjuryPolicy.MINION and self.wound_limit != 1:
                raise ValueError("Minion requires wound_limit 1")
        if not isinstance(self.resilience, ResilienceProfile):
            raise TypeError("NPC resilience must be a ResilienceProfile")
        attacks = tuple(self.attacks)
        if not all(isinstance(item, NpcAttackProfile) for item in attacks):
            raise TypeError("attacks must contain NpcAttackProfile values")
        if len({item.id for item in attacks}) != len(attacks):
            raise ValueError("NPC attack IDs must be unique")
        protection = tuple(self.protection)
        if not all(isinstance(item, NpcProtectionProfile) for item in protection):
            raise TypeError("protection must contain NpcProtectionProfile values")
        if len({item.skill for item in protection}) != len(protection):
            raise ValueError("NPC Protection skills must be unique")
        object.__setattr__(self, "attacks", attacks)
        object.__setattr__(self, "protection", protection)


@dataclass(frozen=True, slots=True)
class NpcParticipantState:
    actor_id: str
    definition_id: str
    side: CombatSide
    injury: CharacterInjuryState | ProfileInjuryState
    available_attack_ids: tuple[str, ...]
    current_resilience: ResilienceProfile
    wields_weapon: bool
    holds_shield: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "NPC actor id")
        _identifier(self.definition_id, "NPC definition id")
        if not isinstance(self.side, CombatSide):
            raise TypeError("NPC side must be a CombatSide")
        if not isinstance(self.injury, (CharacterInjuryState, ProfileInjuryState)):
            raise TypeError("NPC injury must be a typed injury state")
        if not isinstance(self.current_resilience, ResilienceProfile):
            raise TypeError("current_resilience must be a ResilienceProfile")
        if not isinstance(self.wields_weapon, bool) or not isinstance(self.holds_shield, bool):
            raise TypeError("NPC equipment facts must be explicit booleans")
        available = tuple(self.available_attack_ids)
        for identifier in available:
            _identifier(identifier, "available attack id")
        if len(set(available)) != len(available):
            raise ValueError("available attack IDs must be unique")
        object.__setattr__(self, "available_attack_ids", available)


@dataclass(frozen=True, slots=True)
class NpcParticipantSnapshot:
    definition: NpcDefinition
    state: NpcParticipantState

    def __post_init__(self) -> None:
        if not isinstance(self.definition, NpcDefinition):
            raise TypeError("definition must be an NpcDefinition")
        if not isinstance(self.state, NpcParticipantState):
            raise TypeError("state must be an NpcParticipantState")
        if self.state.definition_id != self.definition.id:
            raise ValueError("participant state belongs to another definition")
        if not set(self.state.available_attack_ids) <= {p.id for p in self.definition.attacks}:
            raise ValueError("participant has unknown available attacks")
        injury = self.state.injury
        if self.definition.injury_policy is TargetInjuryPolicy.CHAMPION:
            if not isinstance(injury, CharacterInjuryState):
                raise TypeError("Champion requires CharacterInjuryState")
        else:
            if not isinstance(injury, ProfileInjuryState):
                raise TypeError("Minion/Brute requires ProfileInjuryState")
            if injury.wound_limit != self.definition.wound_limit:
                raise ValueError("participant wound limit differs from definition")

    @property
    def turn_participant(self) -> CombatTurnParticipant:
        return CombatTurnParticipant(self.state.actor_id, self.state.side)

    def attack_snapshot(self, snapshot_id: str) -> NpcAttackSelectionSnapshot:
        """Export availability; this does not authorize an action or spend a slot."""
        return NpcAttackSelectionSnapshot(
            snapshot_id, self.state.actor_id, self.definition.attacks,
            self.state.available_attack_ids,
        )

    def protection_options(self, test_id_prefix: str) -> tuple[ProtectionTestOption, ...]:
        """Export base Tests; contextual modifiers and eligibility remain external."""
        _identifier(test_id_prefix, "Protection Test id prefix")
        return tuple(
            ProtectionTestOption(
                self.state.actor_id, profile.skill,
                TestRequest(f"{test_id_prefix}:{self.state.actor_id}:{profile.skill.value}",
                            profile.test_profile),
            )
            for profile in self.definition.protection
        )


@dataclass(frozen=True, slots=True)
class NpcRoster:
    """A supplied participant snapshot, not the owner of battle transitions."""

    participants: tuple[NpcParticipantSnapshot, ...]

    def __post_init__(self) -> None:
        participants = tuple(self.participants)
        if not all(isinstance(item, NpcParticipantSnapshot) for item in participants):
            raise TypeError("roster must contain NpcParticipantSnapshot values")
        if len({item.state.actor_id for item in participants}) != len(participants):
            raise ValueError("roster actor IDs must be unique")
        definitions: dict[str, NpcDefinition] = {}
        for participant in participants:
            definition = participant.definition
            if definition.id in definitions and definitions[definition.id] != definition:
                raise ValueError("roster has conflicting definitions with the same ID")
            definitions[definition.id] = definition
        object.__setattr__(self, "participants", participants)

    def participant(self, actor_id: str) -> NpcParticipantSnapshot:
        _identifier(actor_id, "NPC actor id")
        for participant in self.participants:
            if participant.state.actor_id == actor_id:
                return participant
        raise ValueError("unknown roster actor")

    @property
    def turn_participants(self) -> tuple[CombatTurnParticipant, ...]:
        # Keep the supplied order, including injured/defeated actors. The caller
        # selects eligibility before handing participants to the round contract.
        return tuple(item.turn_participant for item in self.participants)


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
