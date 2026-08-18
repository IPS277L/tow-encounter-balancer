from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.condition_models import Condition, ConditionState


class WoundEntryId(str, Enum):
    SUPERFICIAL_INJURY = "superficial_injury"
    NICKED_ARM = "nicked_arm"
    BATTERED_LEG = "battered_leg"
    STOMACH_BLOW = "stomach_blow"
    GASHED_BROW = "gashed_brow"
    SHAKING_GRIP = "shaking_grip"
    LEG_SPASM = "leg_spasm"
    CRUSHED_RIB = "crushed_rib"
    EARS_RINGING = "ears_ringing"
    SMASHED_HAND = "smashed_hand"
    TORN_LEG = "torn_leg"
    INTERNAL_INJURY = "internal_injury"
    SCARRING_STRIKE = "scarring_strike"
    SLASHED_FOREARMS = "slashed_forearms"
    SHATTERED_KNEE = "shattered_knee"
    SPILLING_GUTS = "spilling_guts"
    BLACKING_OUT = "blacking_out"
    SEVERED_ARM = "severed_arm"
    SEVERED_LEG = "severed_leg"
    RUPTURED_ORGANS = "ruptured_organs"
    RUINED_EYES = "ruined_eyes"
    APPALLING_STRIKE = "appalling_strike"
    BISECTION = "bisection"
    PIERCED_HEART = "pierced_heart"
    DECAPITATION = "decapitation"


class HealingRequirement(str, Enum):
    CATCH_YOUR_BREATH = "catch_your_breath"
    NIGHTS_REST = "nights_rest"
    REST_AND_RECOVERY = "rest_and_recovery"
    SURGERY_AND_RECOVERY = "surgery_and_recovery"
    NOT_APPLICABLE = "not_applicable"


class ProfileNpcType(str, Enum):
    MINION = "minion"
    BRUTE = "brute"
    MONSTROSITY = "monstrosity"


class CharacterWoundType(str, Enum):
    PLAYER = "player"
    CHAMPION = "champion"


class MonstrosityImpactChoice(str, Enum):
    SUFFER_WOUND = "suffer_wound"
    TRIGGER_REACTION = "trigger_reaction"


class DecisionOwner(str, Enum):
    ATTACKER = "attacker"
    MONSTROSITY = "monstrosity"


class WoundEffectDuration(str, Enum):
    END_OF_NEXT_TURN = "end_of_next_turn"
    UNTIL_REMOVED = "until_removed"
    UNTIL_TREATED = "until_treated"
    UNTIL_HEALED = "until_healed"
    NEXT_TEST = "next_test"
    PERMANENT = "permanent"


class WoundRestriction(str, Enum):
    CANNOT_AIM = "cannot_aim"
    MOVEMENT_IS_DIFFICULT_TERRAIN = "movement_is_difficult_terrain"
    NEXT_TEST_IS_GRIM = "next_test_is_grim"
    USING_INJURED_HAND_CAUSES_CRITICAL = (
        "using_injured_hand_causes_critical"
    )
    REMOVING_PRONE_CAUSES_CRITICAL = "removing_prone_causes_critical"
    NON_RECOVER_ACTION_CAUSES_CRITICAL = (
        "non_recover_action_causes_critical"
    )
    NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL = (
        "non_face_protection_action_causes_critical"
    )
    INJURED_ARM_UNUSABLE = "injured_arm_unusable"
    ARM_LOST = "arm_lost"
    LEG_LOST = "leg_lost"
    SPEED_IS_SLOW = "speed_is_slow"
    PHYSICAL_STAGGER_BECOMES_WOUND = (
        "physical_stagger_becomes_wound"
    )


class WoundEnduranceFailure(str, Enum):
    DROP_RANDOM_HAND_ITEM = "drop_random_hand_item"
    FALL_PRONE = "fall_prone"
    BLINDED_UNTIL_END_OF_NEXT_TURN = (
        "blinded_until_end_of_next_turn"
    )
    LOSE_D10_TEETH = "lose_d10_teeth"
    LOSE_RANDOM_FINGER = "lose_random_finger"
    LOSE_RANDOM_EYE = "lose_random_eye"


class WoundConsequence(str, Enum):
    DROP_RANDOM_HAND_ITEM = "drop_random_hand_item"
    LOSE_D10_TEETH = "lose_d10_teeth"
    LOSE_RANDOM_FINGER = "lose_random_finger"
    LOSE_RANDOM_EYE = "lose_random_eye"
    RANDOMISE_INJURED_ARM = "randomise_injured_arm"
    RANDOMISE_SEVERED_ARM = "randomise_severed_arm"
    RANDOMISE_SEVERED_LEG = "randomise_severed_leg"
    DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH = (
        "drop_one_hand_item_and_clutch_stomach"
    )


class WoundChoice(str, Enum):
    DROP_AND_CLUTCH_STOMACH = "drop_and_clutch_stomach"
    BECOME_DEFENCELESS = "become_defenceless"


@dataclass(frozen=True, slots=True)
class WoundTableEntry:
    id: WoundEntryId
    minimum: int
    maximum: int | None
    healing: HealingRequirement
    lethal: bool

    def __post_init__(self) -> None:
        _validate_positive_int(self.minimum, "minimum")
        if self.maximum is not None:
            _validate_positive_int(self.maximum, "maximum")
            if self.maximum < self.minimum:
                raise ValueError("maximum must not be lower than minimum")
        if not isinstance(self.id, WoundEntryId):
            raise TypeError("id must be a WoundEntryId")
        if not isinstance(self.healing, HealingRequirement):
            raise TypeError("healing must be a HealingRequirement")
        _validate_bool(self.lethal, "lethal")

    def includes(self, total: int) -> bool:
        return total >= self.minimum and (
            self.maximum is None or total <= self.maximum
        )


@dataclass(frozen=True, slots=True)
class WoundDiceModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_non_zero_int(self.amount, "wound dice modifier amount")


@dataclass(frozen=True, slots=True)
class WoundNegationOption:
    rule_id: str

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class WoundRecord:
    sequence: int
    entry_id: WoundEntryId
    table_total: int
    roll_values: tuple[int, ...]
    treated: bool = False
    effect_resolved: bool = False

    def __post_init__(self) -> None:
        _validate_positive_int(self.sequence, "wound sequence")
        if not isinstance(self.entry_id, WoundEntryId):
            raise TypeError("entry_id must be a WoundEntryId")
        _validate_positive_int(self.table_total, "table_total")
        values = tuple(self.roll_values)
        if not values:
            raise ValueError("roll_values must not be empty")
        if any(not isinstance(value, int) or not 1 <= value <= 10 for value in values):
            raise ValueError("roll_values must contain d10 results")
        if sum(values) != self.table_total:
            raise ValueError("table_total must equal the sum of roll_values")
        object.__setattr__(self, "roll_values", values)
        _validate_bool(self.treated, "treated")
        _validate_bool(self.effect_resolved, "effect_resolved")


@dataclass(frozen=True, slots=True)
class WoundConditionEffect:
    wound_sequence: int
    condition: Condition
    duration: WoundEffectDuration

    def __post_init__(self) -> None:
        _validate_positive_int(self.wound_sequence, "wound sequence")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if not isinstance(self.duration, WoundEffectDuration):
            raise TypeError("duration must be a WoundEffectDuration")


@dataclass(frozen=True, slots=True)
class WoundRestrictionEffect:
    wound_sequence: int
    restriction: WoundRestriction
    duration: WoundEffectDuration

    def __post_init__(self) -> None:
        _validate_positive_int(self.wound_sequence, "wound sequence")
        if not isinstance(self.restriction, WoundRestriction):
            raise TypeError("restriction must be a WoundRestriction")
        if not isinstance(self.duration, WoundEffectDuration):
            raise TypeError("duration must be a WoundEffectDuration")


ActiveWoundEffect = WoundConditionEffect | WoundRestrictionEffect


@dataclass(frozen=True, slots=True)
class CharacterInjuryState:
    wounds: tuple[WoundRecord, ...] = field(default_factory=tuple)
    conditions: ConditionState = field(default_factory=ConditionState)
    active_wound_effects: tuple[ActiveWoundEffect, ...] = field(
        default_factory=tuple
    )
    dead: bool = False

    def __post_init__(self) -> None:
        wounds = tuple(self.wounds)
        if not all(isinstance(item, WoundRecord) for item in wounds):
            raise TypeError("wounds must contain WoundRecord values")
        if tuple(item.sequence for item in wounds) != tuple(range(1, len(wounds) + 1)):
            raise ValueError("wound sequences must be contiguous and start at 1")
        object.__setattr__(self, "wounds", wounds)
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        effects = tuple(self.active_wound_effects)
        if not all(
            isinstance(item, (WoundConditionEffect, WoundRestrictionEffect))
            for item in effects
        ):
            raise TypeError(
                "active_wound_effects must contain active Wound effects"
            )
        wound_sequences = {wound.sequence for wound in wounds}
        if any(item.wound_sequence not in wound_sequences for item in effects):
            raise ValueError("active Wound effects must refer to an existing Wound")
        object.__setattr__(self, "active_wound_effects", effects)
        _validate_bool(self.dead, "dead")

    @property
    def untreated_wounds(self) -> int:
        return sum(not wound.treated for wound in self.wounds)


@dataclass(frozen=True, slots=True)
class CharacterWoundRequest:
    id: str
    state: CharacterInjuryState
    subject_type: CharacterWoundType = CharacterWoundType.PLAYER
    dice_modifiers: tuple[WoundDiceModifier, ...] = field(default_factory=tuple)
    negation_options: tuple[WoundNegationOption, ...] = field(default_factory=tuple)
    base_dice: int = 1

    def __post_init__(self) -> None:
        _validate_request_id(self.id, "character wound request")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        _validate_positive_int(self.base_dice, "base_dice")
        if not isinstance(self.subject_type, CharacterWoundType):
            raise TypeError("subject_type must be a CharacterWoundType")
        object.__setattr__(self, "dice_modifiers", tuple(self.dice_modifiers))
        object.__setattr__(self, "negation_options", tuple(self.negation_options))
        if not all(
            isinstance(item, WoundDiceModifier) for item in self.dice_modifiers
        ):
            raise TypeError("dice_modifiers must contain WoundDiceModifier values")
        if not all(
            isinstance(item, WoundNegationOption) for item in self.negation_options
        ):
            raise TypeError(
                "negation_options must contain WoundNegationOption values"
            )
        option_ids = tuple(item.rule_id for item in self.negation_options)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("negation option rule IDs must be unique")


@dataclass(frozen=True, slots=True)
class WoundTableRoll:
    dice: int
    values: tuple[int, ...]
    total: int
    entry: WoundTableEntry

    def __post_init__(self) -> None:
        _validate_positive_int(self.dice, "wound table dice")
        _validate_positive_int(self.total, "wound table total")
        values = tuple(self.values)
        if len(values) != self.dice:
            raise ValueError("wound table values must match dice count")
        if any(not isinstance(value, int) or not 1 <= value <= 10 for value in values):
            raise ValueError("wound table values must contain d10 results")
        object.__setattr__(self, "values", values)
        if sum(values) != self.total:
            raise ValueError("wound table total must equal the sum of values")
        if not isinstance(self.entry, WoundTableEntry):
            raise TypeError("entry must be a WoundTableEntry")
        if not self.entry.includes(self.total):
            raise ValueError("entry must include the wound table total")


@dataclass(frozen=True, slots=True)
class WoundEffectRequest:
    id: str
    wound_sequence: int
    entry_id: WoundEntryId
    rule_id: str

    def __post_init__(self) -> None:
        _validate_request_id(self.id, "Wound effect request")
        _validate_positive_int(self.wound_sequence, "wound sequence")
        if not isinstance(self.entry_id, WoundEntryId):
            raise TypeError("entry_id must be a WoundEntryId")
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class WoundEnduranceTestRequest:
    test_id: str
    wound_sequence: int
    entry_id: WoundEntryId
    failure: WoundEnduranceFailure
    rule_id: str

    def __post_init__(self) -> None:
        _validate_request_id(self.test_id, "Wound Endurance Test request")
        _validate_positive_int(self.wound_sequence, "wound sequence")
        if not isinstance(self.entry_id, WoundEntryId):
            raise TypeError("entry_id must be a WoundEntryId")
        if not isinstance(self.failure, WoundEnduranceFailure):
            raise TypeError("failure must be a WoundEnduranceFailure")
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class WoundConsequenceRequest:
    wound_sequence: int
    consequence: WoundConsequence
    rule_id: str

    def __post_init__(self) -> None:
        _validate_positive_int(self.wound_sequence, "wound sequence")
        if not isinstance(self.consequence, WoundConsequence):
            raise TypeError("consequence must be a WoundConsequence")
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class WoundChoiceRequest:
    wound_sequence: int
    options: tuple[WoundChoice, ...]
    rule_id: str

    def __post_init__(self) -> None:
        _validate_positive_int(self.wound_sequence, "wound sequence")
        options = tuple(self.options)
        if not options:
            raise ValueError("Wound choice options must not be empty")
        if not all(isinstance(item, WoundChoice) for item in options):
            raise TypeError("options must contain WoundChoice values")
        if len(set(options)) != len(options):
            raise ValueError("Wound choice options must be unique")
        object.__setattr__(self, "options", options)
        _validate_rule_id(self.rule_id)


WoundEffectFollowUp = (
    WoundEnduranceTestRequest | WoundConsequenceRequest | WoundChoiceRequest
)


@dataclass(frozen=True, slots=True)
class WoundEffectResult:
    request: WoundEffectRequest
    state: CharacterInjuryState
    follow_ups: tuple[WoundEffectFollowUp, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WoundEnduranceTestResult:
    request: WoundEnduranceTestRequest
    state: CharacterInjuryState
    succeeded: bool
    follow_ups: tuple[WoundConsequenceRequest, ...]


@dataclass(frozen=True, slots=True)
class WoundChoiceResult:
    request: WoundChoiceRequest
    state: CharacterInjuryState
    selected_choice: WoundChoice
    follow_ups: tuple[WoundConsequenceRequest, ...]


@dataclass(frozen=True, slots=True)
class CharacterWoundResult:
    request_id: str
    subject_type: CharacterWoundType
    state: CharacterInjuryState
    table_roll: WoundTableRoll
    wound_accepted: bool
    negated_by_rule_id: str | None
    effect_request: WoundEffectRequest | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileInjuryState:
    wounds: int
    wound_limit: int
    conditions: ConditionState = field(default_factory=ConditionState)
    defeated: bool = False

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.wounds, "wounds")
        _validate_positive_int(self.wound_limit, "wound_limit")
        if self.wounds > self.wound_limit:
            raise ValueError("wounds must not exceed wound_limit")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        _validate_bool(self.defeated, "defeated")
        if self.defeated != (self.wounds >= self.wound_limit):
            raise ValueError("defeated must match whether wound_limit was reached")


@dataclass(frozen=True, slots=True)
class AdditionalProfileWound:
    rule_id: str
    count: int = 1

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_positive_int(self.count, "additional wound count")


@dataclass(frozen=True, slots=True)
class ProfileWoundRequest:
    id: str
    npc_type: ProfileNpcType
    state: ProfileInjuryState
    additional_wounds: tuple[AdditionalProfileWound, ...] = field(
        default_factory=tuple
    )
    base_wounds: int = 1

    def __post_init__(self) -> None:
        _validate_request_id(self.id, "profile wound request")
        if not isinstance(self.npc_type, ProfileNpcType):
            raise TypeError("npc_type must be a ProfileNpcType")
        if not isinstance(self.state, ProfileInjuryState):
            raise TypeError("state must be a ProfileInjuryState")
        _validate_positive_int(self.base_wounds, "base_wounds")
        if self.npc_type is ProfileNpcType.MINION and self.state.wound_limit != 1:
            raise ValueError("a Minion must have a wound_limit of 1")
        object.__setattr__(self, "additional_wounds", tuple(self.additional_wounds))
        if not all(
            isinstance(item, AdditionalProfileWound)
            for item in self.additional_wounds
        ):
            raise TypeError(
                "additional_wounds must contain AdditionalProfileWound values"
            )


@dataclass(frozen=True, slots=True)
class ProfileStateChangeRequest:
    npc_type: ProfileNpcType
    previous_wounds: int
    current_wounds: int
    defeated: bool


@dataclass(frozen=True, slots=True)
class ProfileWoundResult:
    request_id: str
    state: ProfileInjuryState
    wounds_requested: int
    wounds_inflicted: int
    state_change: ProfileStateChangeRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MonstrosityImpactRequest:
    id: str
    state: ProfileInjuryState
    damage: int
    resilience: int

    def __post_init__(self) -> None:
        _validate_request_id(self.id, "Monstrosity impact request")
        if not isinstance(self.state, ProfileInjuryState):
            raise TypeError("state must be a ProfileInjuryState")
        _validate_non_negative_int(self.damage, "damage")
        _validate_non_negative_int(self.resilience, "resilience")


@dataclass(frozen=True, slots=True)
class MonstrosityImpactResult:
    request_id: str
    state: ProfileInjuryState
    decision_owner: DecisionOwner | None
    selected_choice: MonstrosityImpactChoice | None
    wound_requested: bool
    reaction_requested: bool
    staggered_applied: bool


def _validate_request_id(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} id must be a string")
    if not value.strip():
        raise ValueError(f"{name} id must not be empty")


def _validate_rule_id(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("rule_id must be a string")
    if not value.strip():
        raise ValueError("rule_id must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_non_zero_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value == 0:
        raise ValueError(f"{name} must not be zero")


def _validate_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
