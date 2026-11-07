from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackRequest
from towr.domain.test_models import Skill, TestRequest

if TYPE_CHECKING:
    from towr.domain.npc_roster_models import NpcDefinition


PROTECTION_PREPARATION_RULE_ID = "RULE-NPC-008:protection-preparation"
PROTECTION_ELIGIBILITY_RULE_ID = "RULE-COMBAT-005:protection-eligibility"
CLOSE_RANGED_MELEE_RULE_ID = "RULE-EQUIPMENT-004:close-ranged-melee-opposition"
ATTACK_SKILLS = (Skill.MELEE, Skill.BRAWN, Skill.SHOOTING, Skill.THROWING)
PROTECTION_SKILLS = (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE, Skill.STEALTH, Skill.ENDURANCE)
NOW_YOU_SEE_ME_RULE_ID = 'RULE-PROFILE-PEOPLES-002:now-you-see-me'


@dataclass(frozen=True, slots=True)
class HalflingStealthProtectionPermission:
    """The complete book source granting one defender Stealth opposition."""

    defender_id: str
    definition: NpcDefinition

    def __post_init__(self) -> None:
        from towr.domain.npc_roster_models import NpcDefinition
        from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
        if type(self.defender_id) is not str or not self.defender_id.strip():
            raise TypeError('Stealth permission requires an exact defender ID')
        if type(self.definition) is not NpcDefinition:
            raise TypeError('Stealth permission requires a complete NPC definition')
        validate_pc_book_npc_definition(self.definition)
        if self.definition.id != 'pc-book-npc:halfling_thief_dagger':
            raise ValueError('Now You See Me requires the canonical Halfling Thief')


class UnopposedReason(str, Enum):
    UNAWARE = "unaware"
    DEFENCELESS = "defenceless"


@dataclass(frozen=True, slots=True)
class ProtectionTestOption:
    """An explicitly supplied, already modified Test for one defender and Skill."""

    defender_id: str
    skill: Skill
    test: TestRequest

    def __post_init__(self) -> None:
        _non_empty(self.defender_id, "defender_id")
        if not isinstance(self.skill, Skill):
            raise TypeError("protection skill must be a Skill")
        if self.skill not in PROTECTION_SKILLS:
            raise ValueError("unsupported Protection Skill")
        if not isinstance(self.test, TestRequest):
            raise TypeError("protection test must be a TestRequest")


@dataclass(frozen=True, slots=True)
class ProtectionPreparationRequest:
    id: str
    defender_id: str
    attack: AttackRequest
    attack_skill: Skill
    defender_is_aware: bool
    defender_is_defenceless: bool
    defender_wields_weapon: bool
    defender_holds_shield: bool
    selected_skill: Skill | None
    options: tuple[ProtectionTestOption, ...]
    rule_id: str = PROTECTION_PREPARATION_RULE_ID
    halfling_stealth_permission: HalflingStealthProtectionPermission | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _non_empty(self.id, "protection preparation id")
        _non_empty(self.defender_id, "defender_id")
        if not isinstance(self.attack, AttackRequest):
            raise TypeError("attack must be an AttackRequest")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill not in ATTACK_SKILLS:
            raise ValueError("unsupported incoming attack skill")
        for value in (self.defender_is_aware, self.defender_is_defenceless,
                      self.defender_wields_weapon, self.defender_holds_shield):
            if not isinstance(value, bool):
                raise TypeError("protection facts must be explicit booleans")
        if self.selected_skill is not None and not isinstance(self.selected_skill, Skill):
            raise TypeError("selected_skill must be a Skill or None")
        options = tuple(self.options)
        if not all(isinstance(option, ProtectionTestOption) for option in options):
            raise TypeError("options must contain ProtectionTestOption values")
        if any(option.defender_id != self.defender_id for option in options):
            raise ValueError("protection option belongs to another defender")
        if len({option.skill for option in options}) != len(options):
            raise ValueError("protection options must have unique skills")
        if len({option.test.id for option in options}) != len(options):
            raise ValueError("protection options must have unique Test IDs")
        if any(option.test.id == self.attack.attacker_test.id for option in options):
            raise ValueError("protection Test ID must differ from attacker Test ID")
        if self.rule_id != PROTECTION_PREPARATION_RULE_ID:
            raise ValueError("unknown protection preparation rule")
        object.__setattr__(self, "options", options)
        _expected_protection(self)


@dataclass(frozen=True, slots=True)
class ProtectionPreparationResult:
    request_id: str
    rule_id: str
    source_request: ProtectionPreparationRequest
    defender_id: str
    attack: AttackRequest
    eligible_skills: tuple[Skill, ...]
    unopposed_reasons: tuple[UnopposedReason, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, ProtectionPreparationRequest):
            raise TypeError("source_request must be a ProtectionPreparationRequest")
        if not isinstance(self.attack, AttackRequest):
            raise TypeError("prepared attack must be an AttackRequest")
        source = self.source_request
        expected = _expected_protection(source)
        if (self.request_id != source.id or self.rule_id != source.rule_id
                or self.defender_id != source.defender_id
                or (self.attack, tuple(self.eligible_skills), tuple(self.unopposed_reasons),
                    tuple(self.applied_rule_ids)) != expected):
            raise ValueError("protection result has stale source, selection or trace")
        object.__setattr__(self, "eligible_skills", expected[1])
        object.__setattr__(self, "unopposed_reasons", expected[2])
        object.__setattr__(self, "applied_rule_ids", expected[3])


def _expected_protection(request: ProtectionPreparationRequest) -> tuple[
    AttackRequest, tuple[Skill, ...], tuple[UnopposedReason, ...], tuple[str, ...],
]:
    permission = request.halfling_stealth_permission
    if permission is not None:
        if type(permission) is not HalflingStealthProtectionPermission:
            raise TypeError('Stealth permission must retain its exact source type')
        replace(permission)
        if permission.defender_id != request.defender_id:
            raise ValueError('Stealth permission belongs to another defender')
    reasons = (
        *((UnopposedReason.UNAWARE,) if not request.defender_is_aware else ()),
        *((UnopposedReason.DEFENCELESS,) if request.defender_is_defenceless else ()),
    )
    rules = (request.rule_id, PROTECTION_ELIGIBILITY_RULE_ID)
    if reasons:
        if request.selected_skill is not None:
            raise ValueError("unaware or Defenceless target cannot select opposition")
        return replace(request.attack, defender_test=None), (), reasons, rules

    # Close combat describes the incoming Skill, not a restriction to Close Range:
    # e.g. a spear can make a Melee attack at Short Range.
    ranged = request.attack_skill in (Skill.SHOOTING, Skill.THROWING)
    eligible = [Skill.ATHLETICS]
    if request.attack_skill is Skill.BRAWN:
        eligible.append(Skill.ENDURANCE)
    elif request.defender_holds_shield or (not ranged and request.defender_wields_weapon):
        eligible.append(Skill.DEFENCE)
    if ranged and request.attack.is_close_range:
        eligible.append(Skill.MELEE)
    if permission is not None:
        eligible.append(Skill.STEALTH)
    if request.selected_skill not in eligible:
        raise ValueError("selected protection skill is not eligible in this context")
    option = next((item for item in request.options if item.skill is request.selected_skill), None)
    if option is None:
        raise ValueError("selected protection skill requires a supplied Test")
    if request.selected_skill is Skill.MELEE:
        rules = (*rules, CLOSE_RANGED_MELEE_RULE_ID)
    if request.selected_skill is Skill.STEALTH:
        from towr.domain.test_models import InlineProfile
        profile = option.test.profile
        if type(profile) is not InlineProfile:
            raise TypeError('Halfling Stealth requires its printed InlineProfile')
        replace(profile)
        if profile != permission.definition.protection[0].test_profile:
            raise ValueError('Stealth Test changed its canonical numeric source')
        rules = (*rules, NOW_YOU_SEE_ME_RULE_ID)
    return replace(request.attack, defender_test=option.test), tuple(eligible), (), rules


def _non_empty(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
