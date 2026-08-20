from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.test_models import OpposedTestResult, TestRequest, TestResult


class NpcWizardCastingOppositionOutcome(str, Enum):
    RESOLVED = "resolved"
    UNAVAILABLE_OUT_OF_RANGE = "unavailable_out_of_range"
    UNAVAILABLE_ALREADY_USED = "unavailable_already_used"


class MiscastPoolOutcome(str, Enum):
    ACCUMULATED = "accumulated"
    MISCAST_TRIGGERED = "miscast_triggered"


class MiscastPoolIncreaseSourceKind(str, Enum):
    TEST = "test"
    ACTION = "action"


class CastingChoice(str, Enum):
    CAST = "cast"
    WAIT = "wait"


class SpellTargetKind(str, Enum):
    SELF = "self"
    CREATURE = "creature"
    ZONE = "zone"
    OBJECT = "object"
    OTHER = "other"


class SpellRange(str, Enum):
    SELF = "self"
    CLOSE = "close"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    EXTREME = "extreme"


class SpellDuration(str, Enum):
    INSTANT = "instant"
    POTENCY_TURNS = "potency_turns"
    BATTLE = "battle"
    PERMANENT = "permanent"
    OTHER = "other"


class SpellTargetPreflightOutcome(str, Enum):
    READY = "ready"
    INVALID_TARGET_KIND = "invalid_target_kind"
    OUT_OF_RANGE = "out_of_range"


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
    casting_lore_id: str | None = None
    latest_casting_roll_successes: int = 0

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.miscast_dice, "miscast_dice")
        _validate_non_negative_int(
            self.casting_successes,
            "casting_successes",
        )
        _validate_non_negative_int(
            self.latest_casting_roll_successes,
            "latest_casting_roll_successes",
        )
        if self.casting_lore_id is not None:
            _validate_non_empty_string(self.casting_lore_id, "casting_lore_id")
        elif self.casting_successes or self.latest_casting_roll_successes:
            raise ValueError(
                "Casting successes require an active casting_lore_id"
            )
        if self.latest_casting_roll_successes > self.casting_successes:
            raise ValueError(
                "latest Casting roll successes cannot exceed accumulated "
                "Casting successes"
            )


@dataclass(frozen=True, slots=True)
class CastingTestRequest:
    id: str
    caster_id: str
    lore_id: str
    test: TestRequest
    state: WizardMagicState
    rule_id: str = "RULE-MAGIC-004:casting-test"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Casting Test request id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.lore_id, "lore_id")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        if any(lock.value == 9 for lock in self.test.reroll_locks):
            raise ValueError(
                "Casting Test owns the Rule of Nine reroll lock"
            )
        if (
            self.state.casting_lore_id is not None
            and self.state.casting_lore_id != self.lore_id
        ):
            raise ValueError(
                "an active Casting Test cannot switch Magic Lore"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastPoolIncreaseRequest:
    resolution_id: str
    target_id: str
    amount: int
    source_kind: MiscastPoolIncreaseSourceKind
    source_id: str
    trigger_rule_id: str
    rule_id: str = "RULE-MAGIC-003:rule-of-nine"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_positive_int(self.amount, "Miscast Pool increase")
        if not isinstance(self.source_kind, MiscastPoolIncreaseSourceKind):
            raise TypeError(
                "source_kind must be a MiscastPoolIncreaseSourceKind"
            )
        _validate_non_empty_string(self.source_id, "source_id")
        _validate_non_empty_string(self.trigger_rule_id, "trigger_rule_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class CastingTestResult:
    request_id: str
    caster_id: str
    lore_id: str
    test: TestResult
    state: WizardMagicState
    previous_casting_successes: int
    latest_roll_successes: int
    miscast_dice_added: int
    follow_ups: tuple[MiscastPoolIncreaseRequest, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CastingSpellSelection:
    spell_rule_id: str
    lore_id: str
    casting_value: int

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_non_empty_string(self.lore_id, "lore_id")
        _validate_positive_int(self.casting_value, "casting_value")


@dataclass(frozen=True, slots=True)
class SpellCastRequest:
    resolution_id: str
    caster_id: str
    spell_rule_id: str
    lore_id: str
    casting_value: int
    base_potency: int
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_non_empty_string(self.lore_id, "lore_id")
        _validate_positive_int(self.casting_value, "casting_value")
        _validate_non_negative_int(self.base_potency, "base_potency")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class CastingDecisionRequest:
    id: str
    caster_id: str
    state: WizardMagicState
    wizard_level: int
    choice: CastingChoice
    selected_spell: CastingSpellSelection | None = None
    rule_id: str = "RULE-MAGIC-004:cast-or-wait"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Casting decision request id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        _validate_positive_int(self.wizard_level, "wizard_level")
        if not isinstance(self.choice, CastingChoice):
            raise TypeError("choice must be a CastingChoice")
        if self.state.casting_lore_id is None:
            raise ValueError("Casting decision requires an active Casting Test")
        if self.state.miscast_dice > self.wizard_level:
            raise ValueError(
                "a triggered Miscast must be resolved before CAST or WAIT"
            )
        if self.selected_spell is not None and not isinstance(
            self.selected_spell,
            CastingSpellSelection,
        ):
            raise TypeError("selected_spell must be a CastingSpellSelection")
        if self.choice is CastingChoice.WAIT:
            if self.selected_spell is not None:
                raise ValueError("WAIT must not select a spell")
        elif self.selected_spell is None:
            raise ValueError("CAST requires a selected spell")
        else:
            if self.selected_spell.lore_id != self.state.casting_lore_id:
                raise ValueError(
                    "selected spell must belong to the active Magic Lore"
                )
            if (
                self.selected_spell.casting_value
                > self.state.casting_successes
            ):
                raise ValueError(
                    "selected spell requires more accumulated Casting successes"
                )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class CastingDecisionResult:
    request_id: str
    caster_id: str
    choice: CastingChoice
    state: WizardMagicState
    previous_casting_successes: int
    base_potency: int | None
    follow_ups: tuple[SpellCastRequest, ...]
    applied_rule_ids: tuple[str, ...]


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
class MiscastPreparationRequest:
    id: str
    source: MiscastRollRequest
    state: WizardMagicState
    spell_to_cast: CastingSpellSelection | None = None
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
            CastingSpellSelection,
        ):
            raise TypeError("spell_to_cast must be a CastingSpellSelection")
        if (
            self.spell_to_cast is not None
            and self.state.casting_successes
            < self.spell_to_cast.casting_value
        ):
            raise ValueError(
                "the selected spell requires more accumulated Casting "
                "successes"
            )
        if (
            self.spell_to_cast is not None
            and self.spell_to_cast.lore_id != self.state.casting_lore_id
        ):
            raise ValueError(
                "the selected spell must belong to the active Magic Lore"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


MiscastPreparationFollowUp = SpellCastRequest | MiscastRollRequest


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
        if self.base_potency < 0:
            raise ValueError("base_potency must not be negative")
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


@dataclass(frozen=True, slots=True)
class FormalSpellDefinition:
    rule_id: str
    lore_id: str
    casting_value: int
    target_kind: SpellTargetKind
    range: SpellRange
    duration: SpellDuration

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.rule_id, "formal spell rule_id")
        _validate_non_empty_string(self.lore_id, "formal spell lore_id")
        _validate_positive_int(self.casting_value, "formal spell casting_value")
        if not isinstance(self.target_kind, SpellTargetKind):
            raise TypeError("target_kind must be a SpellTargetKind")
        if not isinstance(self.range, SpellRange):
            raise TypeError("range must be a SpellRange")
        if not isinstance(self.duration, SpellDuration):
            raise TypeError("duration must be a SpellDuration")


@dataclass(frozen=True, slots=True)
class IdentifiedSpellTarget:
    target_id: str
    potency_modifiers: tuple[SpellPotencyModifier, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "spell target_id")
        modifiers = tuple(self.potency_modifiers)
        if not all(isinstance(item, SpellPotencyModifier) for item in modifiers):
            raise TypeError(
                "potency_modifiers must contain SpellPotencyModifier values"
            )
        rule_ids = tuple(item.rule_id for item in modifiers)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("target Potency modifier rule IDs must be unique")
        object.__setattr__(self, "potency_modifiers", modifiers)


@dataclass(frozen=True, slots=True)
class SpellTargetPreflightRequest:
    id: str
    source: SpellCastRequest
    definition: FormalSpellDefinition
    selected_target_id: str
    selected_target_kind: SpellTargetKind
    target_within_range: bool
    affected_targets: tuple[IdentifiedSpellTarget, ...] = field(
        default_factory=tuple
    )
    rule_id: str = "RULE-MAGIC-005:spell-schema"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Spell target preflight request id")
        if not isinstance(self.source, SpellCastRequest):
            raise TypeError("source must be a SpellCastRequest")
        if not isinstance(self.definition, FormalSpellDefinition):
            raise TypeError("definition must be a FormalSpellDefinition")
        _validate_non_empty_string(self.selected_target_id, "selected_target_id")
        if not isinstance(self.selected_target_kind, SpellTargetKind):
            raise TypeError("selected_target_kind must be a SpellTargetKind")
        _validate_bool(self.target_within_range, "target_within_range")
        targets = tuple(self.affected_targets)
        if not all(isinstance(item, IdentifiedSpellTarget) for item in targets):
            raise TypeError(
                "affected_targets must contain IdentifiedSpellTarget values"
            )
        target_ids = tuple(item.target_id for item in targets)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("affected spell target IDs must be unique")
        object.__setattr__(self, "affected_targets", targets)
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class SpellCastExecutionRequest:
    id: str
    source: SpellCastRequest
    selected_target_id: str
    targets: tuple[IdentifiedSpellTarget, ...]
    rule_id: str = "RULE-MAGIC-002:target-scoped-potency"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Spell execution request id")
        if not isinstance(self.source, SpellCastRequest):
            raise TypeError("source must be a SpellCastRequest")
        _validate_non_empty_string(self.selected_target_id, "selected_target_id")
        targets = tuple(self.targets)
        if not all(isinstance(item, IdentifiedSpellTarget) for item in targets):
            raise TypeError("targets must contain IdentifiedSpellTarget values")
        target_ids = tuple(item.target_id for item in targets)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Spell execution target IDs must be unique")
        object.__setattr__(self, "targets", targets)
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class SpellTargetPreflightResult:
    request_id: str
    source_cast_id: str
    selected_target_id: str
    outcome: SpellTargetPreflightOutcome
    definition: FormalSpellDefinition
    execution_request: SpellCastExecutionRequest | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SpellEffectApplicationRequest:
    resolution_id: str
    source_cast_id: str
    caster_id: str
    spell_rule_id: str
    lore_id: str
    target_id: str
    potency: int
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.source_cast_id, "source_cast_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_non_empty_string(self.lore_id, "lore_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_positive_int(self.potency, "spell effect potency")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class SpellCastTargetResult:
    target_id: str
    potency: SpellPotencyResult
    effect_request: SpellEffectApplicationRequest | None


@dataclass(frozen=True, slots=True)
class SpellCastExecutionResult:
    request_id: str
    source_cast_id: str
    caster_id: str
    spell_rule_id: str
    lore_id: str
    selected_target_id: str
    targets: tuple[SpellCastTargetResult, ...]
    follow_ups: tuple[SpellEffectApplicationRequest, ...]
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
