from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Characteristic(str, Enum):
    STRENGTH = "strength"
    TOUGHNESS = "toughness"
    INITIATIVE = "initiative"
    AGILITY = "agility"
    REASON = "reason"
    FELLOWSHIP = "fellowship"


class Skill(str, Enum):
    MELEE = "melee"
    DEFENCE = "defence"
    SHOOTING = "shooting"
    THROWING = "throwing"
    BRAWN = "brawn"
    TOIL = "toil"
    SURVIVAL = "survival"
    ENDURANCE = "endurance"
    AWARENESS = "awareness"
    DEXTERITY = "dexterity"
    ATHLETICS = "athletics"
    STEALTH = "stealth"
    WILLPOWER = "willpower"
    RECALL = "recall"
    LEADERSHIP = "leadership"
    CHARM = "charm"


class TestQuality(str, Enum):
    NORMAL = "normal"
    GRIM = "grim"
    GLORIOUS = "glorious"


class QualityModifierSource(str, Enum):
    RULE = "rule"
    FATE = "fate"


FATE_GLORIOUS_RULE_ID = "RULE-FATE-001:glorious-test"


class BasicOutcome(str, Enum):
    FAILURE = "failure"
    MARGINAL_SUCCESS = "marginal_success"
    SUCCESS = "success"
    TOTAL_SUCCESS = "total_success"


class OpposedSide(str, Enum):
    INITIATOR = "initiator"
    OPPONENT = "opponent"


class OpposedOutcome(str, Enum):
    INITIATOR_WINS = "initiator_wins"
    OPPONENT_WINS = "opponent_wins"
    BOTH_FAIL = "both_fail"


@dataclass(frozen=True, slots=True)
class TestProfile:
    """A book profile: Characteristic supplies dice and Skill supplies threshold."""

    characteristic: int
    skill: int

    def __post_init__(self) -> None:
        _validate_positive_int(self.characteristic, "characteristic")
        _validate_threshold(self.skill)

    @property
    def base_dice(self) -> int:
        return self.characteristic

    @property
    def threshold(self) -> int:
        return self.skill

    @property
    def maximum_dice(self) -> int:
        return self.characteristic * 2


@dataclass(frozen=True, slots=True)
class InlineProfile:
    """A ready profile, primarily for NPCs whose sheets already contain Xd/Y."""

    dice: int
    threshold: int
    pool_cap: int | None = None

    def __post_init__(self) -> None:
        _validate_positive_int(self.dice, "dice")
        _validate_threshold(self.threshold)
        if self.pool_cap is not None:
            _validate_positive_int(self.pool_cap, "pool_cap")

    @property
    def base_dice(self) -> int:
        return self.dice

    @property
    def maximum_dice(self) -> int:
        return self.pool_cap if self.pool_cap is not None else self.dice * 2


RollProfile = TestProfile | InlineProfile


@dataclass(frozen=True, slots=True)
class DiceModifier:
    rule_id: str
    amount: int
    bypasses_pool_cap: bool = False

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_int(self.amount, "dice modifier amount")
        if self.amount == 0:
            raise ValueError("dice modifier amount must not be zero")
        if self.bypasses_pool_cap and self.amount < 1:
            raise ValueError("only bonus dice can bypass the pool cap")


@dataclass(frozen=True, slots=True)
class QualityModifier:
    rule_id: str
    quality: TestQuality
    source: QualityModifierSource = QualityModifierSource.RULE
    source_id: str | None = None

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        if not isinstance(self.quality, TestQuality):
            raise TypeError("quality must be a TestQuality")
        if self.quality is TestQuality.NORMAL:
            raise ValueError("a quality modifier must be Grim or Glorious")
        if not isinstance(self.source, QualityModifierSource):
            raise TypeError("source must be a QualityModifierSource")
        if self.source is QualityModifierSource.FATE:
            if self.quality is not TestQuality.GLORIOUS:
                raise ValueError("Fate can only make a Test Glorious")
            if self.rule_id != FATE_GLORIOUS_RULE_ID:
                raise ValueError("Fate Glorious requires its canonical rule")
            _validate_source_id(self.source_id, "Fate source_id")
        elif self.source_id is not None:
            raise ValueError("rule-sourced quality cannot name a source_id")


@dataclass(frozen=True, slots=True)
class FateGloriousProof:
    id: str
    actor_id: str
    test_id: str
    rule_id: str = FATE_GLORIOUS_RULE_ID

    def __post_init__(self) -> None:
        _validate_source_id(self.id, "Fate proof id")
        _validate_source_id(self.actor_id, "Fate proof actor_id")
        _validate_source_id(self.test_id, "Fate proof test_id")
        _validate_rule_id(self.rule_id)
        if self.rule_id != FATE_GLORIOUS_RULE_ID:
            raise ValueError("Fate Glorious proof requires its canonical rule")


@dataclass(frozen=True, slots=True)
class SuccessModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_int(self.amount, "success modifier amount")
        if self.amount == 0:
            raise ValueError("success modifier amount must not be zero")


@dataclass(frozen=True, slots=True)
class RerollLock:
    rule_id: str
    value: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_int(self.value, "locked reroll value")
        if not 1 <= self.value <= 10:
            raise ValueError("locked reroll value must be between 1 and 10")


@dataclass(frozen=True, slots=True)
class TestRequest:
    id: str
    profile: RollProfile
    dice_modifiers: tuple[DiceModifier, ...] = field(default_factory=tuple)
    quality_modifiers: tuple[QualityModifier, ...] = field(default_factory=tuple)
    success_modifiers: tuple[SuccessModifier, ...] = field(default_factory=tuple)
    reroll_locks: tuple[RerollLock, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("test request id must be a string")
        if not self.id.strip():
            raise ValueError("test request id must not be empty")
        object.__setattr__(self, "dice_modifiers", tuple(self.dice_modifiers))
        object.__setattr__(self, "quality_modifiers", tuple(self.quality_modifiers))
        object.__setattr__(self, "success_modifiers", tuple(self.success_modifiers))
        object.__setattr__(self, "reroll_locks", tuple(self.reroll_locks))
        if not isinstance(self.profile, (TestProfile, InlineProfile)):
            raise TypeError("profile must be a TestProfile or InlineProfile")
        if not all(isinstance(item, DiceModifier) for item in self.dice_modifiers):
            raise TypeError("dice_modifiers must contain DiceModifier values")
        if not all(
            isinstance(item, QualityModifier) for item in self.quality_modifiers
        ):
            raise TypeError("quality_modifiers must contain QualityModifier values")
        fate_modifiers = tuple(
            item
            for item in self.quality_modifiers
            if item.source is QualityModifierSource.FATE
        )
        if len(fate_modifiers) > 1:
            raise ValueError("a Test cannot spend Fate on Glorious twice")
        if fate_modifiers and sum(
            item.quality is TestQuality.GLORIOUS
            for item in self.quality_modifiers
        ) > 1:
            raise ValueError("Fate cannot be spent on an already Glorious Test")
        if not all(
            isinstance(item, SuccessModifier) for item in self.success_modifiers
        ):
            raise TypeError("success_modifiers must contain SuccessModifier values")
        if not all(isinstance(item, RerollLock) for item in self.reroll_locks):
            raise TypeError("reroll_locks must contain RerollLock values")
        lock_rule_ids = tuple(item.rule_id for item in self.reroll_locks)
        if len(set(lock_rule_ids)) != len(lock_rule_ids):
            raise ValueError("reroll lock rule IDs must be unique")
        lock_values = tuple(item.value for item in self.reroll_locks)
        if len(set(lock_values)) != len(lock_values):
            raise ValueError("reroll lock values must be unique")


@dataclass(frozen=True, slots=True)
class RerollTrace:
    index: int
    original: int
    replacement: int


@dataclass(frozen=True, slots=True)
class RollTrace:
    request_id: str
    base_dice: int
    pool_cap: int
    regular_dice_delta: int
    cap_bypassing_dice: int
    dice_before_minimum: int
    rolled_dice: int
    threshold: int
    minimum_die_rule_applied: bool
    quality: TestQuality
    initial_values: tuple[int, ...]
    rerolls: tuple[RerollTrace, ...]
    final_values: tuple[int, ...]
    rolled_successes: int
    success_delta: int
    successes: int
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TestResult:
    trace: RollTrace

    @property
    def successes(self) -> int:
        return self.trace.successes

    @property
    def succeeded(self) -> bool:
        return self.successes > 0


@dataclass(frozen=True, slots=True)
class BasicTestResult:
    test: TestResult
    outcome: BasicOutcome


@dataclass(frozen=True, slots=True)
class TieBreak:
    rule_id: str
    winner: OpposedSide

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        if not isinstance(self.winner, OpposedSide):
            raise TypeError("winner must be an OpposedSide")


@dataclass(frozen=True, slots=True)
class OpposedTestRequest:
    id: str
    initiator: TestRequest
    opponent: TestRequest
    tie_break: TieBreak

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("opposed test request id must be a string")
        if not self.id.strip():
            raise ValueError("opposed test request id must not be empty")


@dataclass(frozen=True, slots=True)
class OpposedTestResult:
    request_id: str
    initiator: TestResult
    opponent: TestResult
    outcome: OpposedOutcome
    winner: OpposedSide | None
    success_margin: int
    consequence: BasicOutcome | None
    tie_break_applied: bool
    tie_break_rule_id: str | None


def _validate_threshold(value: int) -> None:
    _validate_int(value, "skill/threshold")
    if not 1 <= value <= 10:
        raise ValueError("skill/threshold must be between 1 and 10")


def _validate_rule_id(rule_id: str) -> None:
    if not isinstance(rule_id, str):
        raise TypeError("rule_id must be a string")
    if not rule_id.strip():
        raise ValueError("rule_id must not be empty")


def _validate_source_id(value: str | None, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
