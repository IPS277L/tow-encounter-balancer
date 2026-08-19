from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.test_models import OpposedTestResult


class NpcWizardCastingOppositionOutcome(str, Enum):
    RESOLVED = "resolved"
    UNAVAILABLE_OUT_OF_RANGE = "unavailable_out_of_range"
    UNAVAILABLE_ALREADY_USED = "unavailable_already_used"


class MiscastPoolOutcome(str, Enum):
    ACCUMULATED = "accumulated"
    MISCAST_TRIGGERED = "miscast_triggered"


class MiscastTableEntryId(str, Enum):
    SENSE_OF_LOSS = "sense_of_loss"
    NAUSEATING_WAVE = "nauseating_wave"
    OBJECTS_TRANSFIGURED = "objects_transfigured"
    SHADOW_CHITTERING = "shadow_chittering"
    FOOD_SPOILED = "food_spoiled"
    ARCANE_SPILL = "arcane_spill"
    HIDEOUS_STENCH = "hideous_stench"
    UNNATURAL_WEATHER = "unnatural_weather"
    RANDOM_TRANSPORT = "random_transport"
    SUNLIGHT_BLINDNESS = "sunlight_blindness"
    UNNATURAL_WIND = "unnatural_wind"
    SPELL_RECAST = "spell_recast"
    TRUTHBOUND = "truthbound"
    ARCANE_SIGHT = "arcane_sight"
    FEARED_FOE_ILLUSION = "feared_foe_illusion"
    INTERNAL_DAMAGE = "internal_damage"
    ZONE_HAZARD = "zone_hazard"
    EAR_DAMAGE = "ear_damage"
    DAEMON_RIFT = "daemon_rift"
    FASCINATING_RIFT = "fascinating_rift"
    CATASTROPHIC_DEATH = "catastrophic_death"


@dataclass(frozen=True, slots=True)
class WizardMagicState:
    miscast_dice: int = 0
    casting_successes: int = 0

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.miscast_dice, "miscast_dice")
        _validate_non_negative_int(
            self.casting_successes,
            "casting_successes",
        )


@dataclass(frozen=True, slots=True)
class MiscastPoolIncreaseRequest:
    resolution_id: str
    target_id: str
    amount: int
    source_test_id: str
    trigger_rule_id: str
    rule_id: str = "RULE-MAGIC-003:rule-of-nine"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_positive_int(self.amount, "Miscast Pool increase")
        _validate_non_empty_string(self.source_test_id, "source_test_id")
        _validate_non_empty_string(self.trigger_rule_id, "trigger_rule_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastPoolResolutionRequest:
    id: str
    source: MiscastPoolIncreaseRequest
    state: WizardMagicState
    wizard_level: int
    rule_id: str = "RULE-MAGIC-004:miscast-pool"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Miscast Pool request id")
        if not isinstance(self.source, MiscastPoolIncreaseRequest):
            raise TypeError("source must be a MiscastPoolIncreaseRequest")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        _validate_positive_int(self.wizard_level, "wizard_level")
        if self.state.miscast_dice > self.wizard_level:
            raise ValueError(
                "an already-triggered Miscast must be resolved before "
                "adding more dice"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastRollRequest:
    resolution_id: str
    source_resolution_id: str
    target_id: str
    pool_dice_count: int
    bonus_dice: int = 0
    rule_id: str = "RULE-MAGIC-004:miscast-pool"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(
            self.source_resolution_id,
            "source_resolution_id",
        )
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_positive_int(
            self.pool_dice_count,
            "Miscast roll pool_dice_count",
        )
        _validate_non_negative_int(
            self.bonus_dice,
            "Miscast roll bonus_dice",
        )
        if self.bonus_dice > 1:
            raise ValueError("Miscast roll bonus_dice must not exceed one")
        _validate_non_empty_string(self.rule_id, "rule_id")

    @property
    def dice_count(self) -> int:
        return self.pool_dice_count + self.bonus_dice


@dataclass(frozen=True, slots=True)
class MiscastSpellSelection:
    spell_rule_id: str
    casting_value: int

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_positive_int(self.casting_value, "casting_value")


@dataclass(frozen=True, slots=True)
class MiscastPreparationRequest:
    id: str
    source: MiscastRollRequest
    state: WizardMagicState
    spell_to_cast: MiscastSpellSelection | None = None
    rule_id: str = "RULE-MAGIC-004:miscast-pool"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Miscast preparation request id")
        if not isinstance(self.source, MiscastRollRequest):
            raise TypeError("source must be a MiscastRollRequest")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        if self.source.bonus_dice:
            raise ValueError("source Miscast roll must not already be prepared")
        if self.state.miscast_dice != self.source.pool_dice_count:
            raise ValueError(
                "Miscast Pool state must match the source roll request"
            )
        if self.spell_to_cast is not None and not isinstance(
            self.spell_to_cast,
            MiscastSpellSelection,
        ):
            raise TypeError("spell_to_cast must be a MiscastSpellSelection")
        if (
            self.spell_to_cast is not None
            and self.state.casting_successes
            < self.spell_to_cast.casting_value
        ):
            raise ValueError(
                "the selected spell requires more accumulated Casting "
                "successes"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastSpellCastRequest:
    resolution_id: str
    target_id: str
    spell_rule_id: str
    casting_value: int
    rule_id: str = "RULE-MAGIC-004:miscast-pool"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_positive_int(self.casting_value, "casting_value")
        _validate_non_empty_string(self.rule_id, "rule_id")


MiscastPreparationFollowUp = MiscastSpellCastRequest | MiscastRollRequest


@dataclass(frozen=True, slots=True)
class MiscastPreparationResult:
    request_id: str
    target_id: str
    state: WizardMagicState
    previous_casting_successes: int
    follow_ups: tuple[MiscastPreparationFollowUp, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastTableEntry:
    id: MiscastTableEntryId
    minimum: int
    maximum: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.id, MiscastTableEntryId):
            raise TypeError("id must be a MiscastTableEntryId")
        _validate_positive_int(self.minimum, "minimum")
        if self.maximum is not None:
            _validate_positive_int(self.maximum, "maximum")
            if self.maximum < self.minimum:
                raise ValueError("maximum must not be lower than minimum")

    def includes(self, total: int) -> bool:
        return total >= self.minimum and (
            self.maximum is None or total <= self.maximum
        )


@dataclass(frozen=True, slots=True)
class MiscastTableEffectRequest:
    resolution_id: str
    source_roll_id: str
    target_id: str
    entry: MiscastTableEntry
    roll_values: tuple[int, ...]
    total: int
    pool_dice_count: int
    bonus_dice: int
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.source_roll_id, "source_roll_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.entry, MiscastTableEntry):
            raise TypeError("entry must be a MiscastTableEntry")
        values = tuple(self.roll_values)
        if not values:
            raise ValueError("roll_values must not be empty")
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= 10
            for value in values
        ):
            raise ValueError("roll_values must contain d10 results")
        object.__setattr__(self, "roll_values", values)
        _validate_positive_int(self.total, "Miscast table total")
        if sum(values) != self.total:
            raise ValueError("total must equal the sum of roll_values")
        if not self.entry.includes(self.total):
            raise ValueError("entry must include the Miscast table total")
        _validate_positive_int(self.pool_dice_count, "pool_dice_count")
        _validate_non_negative_int(self.bonus_dice, "bonus_dice")
        if self.bonus_dice > 1:
            raise ValueError("bonus_dice must not exceed one")
        if len(values) != self.pool_dice_count + self.bonus_dice:
            raise ValueError("roll_values must match pool and bonus dice")
        _validate_non_empty_string(self.rule_id, "rule_id")

    @property
    def entry_id(self) -> MiscastTableEntryId:
        return self.entry.id


@dataclass(frozen=True, slots=True)
class MiscastRollResult:
    request_id: str
    target_id: str
    state: WizardMagicState
    roll_values: tuple[int, ...]
    total: int
    entry: MiscastTableEntry
    effect_request: MiscastTableEffectRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastPoolResolutionResult:
    request_id: str
    target_id: str
    state: WizardMagicState
    previous_miscast_dice: int
    dice_added: int
    outcome: MiscastPoolOutcome
    roll_request: MiscastRollRequest | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NpcWizardCastingOppositionRequest:
    id: str
    caster_id: str
    reactor_id: str
    opposed_test_id: str
    casting_test_id: str
    reactor_willpower_test_id: str
    caster_in_long_range: bool
    has_opposed_casting_this_round: bool
    opposition: OpposedTestResult | None
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "NPC Wizard Casting opposition request id",
        )
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.reactor_id, "reactor_id")
        if self.caster_id == self.reactor_id:
            raise ValueError("caster and reacting Wizard must be different")
        _validate_non_empty_string(self.opposed_test_id, "opposed_test_id")
        _validate_non_empty_string(self.casting_test_id, "casting_test_id")
        _validate_non_empty_string(
            self.reactor_willpower_test_id,
            "reactor_willpower_test_id",
        )
        if self.casting_test_id == self.reactor_willpower_test_id:
            raise ValueError("Casting and Willpower Test ids must be different")
        _validate_bool(self.caster_in_long_range, "caster_in_long_range")
        _validate_bool(
            self.has_opposed_casting_this_round,
            "has_opposed_casting_this_round",
        )
        if self.opposition is not None and not isinstance(
            self.opposition,
            OpposedTestResult,
        ):
            raise TypeError("opposition must be an OpposedTestResult")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class NpcWizardCastingOppositionResult:
    request_id: str
    caster_id: str
    reactor_id: str
    outcome: NpcWizardCastingOppositionOutcome
    opposition: OpposedTestResult | None
    opposition_used_this_round: bool
    miscast_dice_added: int
    follow_ups: tuple[MiscastPoolIncreaseRequest, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SpellPotencyModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.rule_id, "Potency modifier rule_id")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise TypeError("Potency modifier amount must be an integer")
        if self.amount == 0:
            raise ValueError("Potency modifier amount must not be zero")


@dataclass(frozen=True, slots=True)
class SpellPotencyRequest:
    id: str
    spell_rule_id: str
    target_id: str
    base_potency: int
    modifiers: tuple[SpellPotencyModifier, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Spell Potency request id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.base_potency, int) or isinstance(
            self.base_potency,
            bool,
        ):
            raise TypeError("base_potency must be an integer")
        if self.base_potency < 1:
            raise ValueError("base_potency must be positive")
        modifiers = tuple(self.modifiers)
        if not all(isinstance(item, SpellPotencyModifier) for item in modifiers):
            raise TypeError(
                "modifiers must contain SpellPotencyModifier values"
            )
        rule_ids = tuple(item.rule_id for item in modifiers)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("Potency modifier rule IDs must be unique")
        object.__setattr__(self, "modifiers", modifiers)


@dataclass(frozen=True, slots=True)
class SpellPotencyResult:
    request_id: str
    spell_rule_id: str
    target_id: str
    base_potency: int
    potency_delta: int
    effective_potency: int
    has_effect: bool
    applied_rule_ids: tuple[str, ...]


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
