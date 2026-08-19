from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.injury_models import (
    AdditionalProfileWound,
    CharacterInjuryState,
    CharacterWoundResult,
    DecisionOwner,
    FixedCharacterWoundResult,
    ProfileInjuryState,
    ProfileWoundResult,
    WoundDiceModifier,
    WoundEffectResult,
    WoundNegationOption,
)
from towr.domain.condition_models import (
    ConditionApplicationResult,
    EffectApplicationResult,
    EffectImmunity,
)
from towr.domain.magic_models import (
    MiscastTableEffectRequest,
    MiscastTableEntryId,
    WizardMagicState,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest,
    StaggerImpactRequest,
    StaggerImpactResult,
    TargetInjuryPolicy,
    TargetInjuryState,
    GiveGroundRequest,
    ZoneHazardRequest,
)
from towr.domain.test_models import (
    Characteristic,
    DiceModifier,
    QualityModifier,
    TestRequest,
    TestResult,
    TestQuality,
)


class MiscastHideousStenchChoice(str, Enum):
    GIVE_GROUND = "give_ground"
    SUFFER_NEXT_TEST_PENALTY = "suffer_next_test_penalty"


class MiscastHideousStenchOutcome(str, Enum):
    GIVE_GROUND_REQUESTED = "give_ground_requested"
    NEXT_TEST_PENALTY_APPLIED = "next_test_penalty_applied"


class MiscastArcaneSightTestContext(str, Enum):
    AFFECTED_NORMAL_AWARENESS = "affected_normal_awareness"
    DETECT_MAGICAL_PHENOMENA = "detect_magical_phenomena"


class MiscastFearedFoeIllusionDuration(str, Enum):
    UNTIL_BATTLE_END = "until_battle_end"
    MINUTES = "minutes"


class MiscastIlluminationKind(str, Enum):
    SUNLIGHT = "sunlight"
    OTHER_NATURAL_LIGHT = "other_natural_light"
    TORCHLIGHT = "torchlight"
    OTHER_ARTIFICIAL_LIGHT = "other_artificial_light"
    ARCANE_ILLUMINATION = "arcane_illumination"


class MiscastRandomTransportRange(str, Enum):
    MEDIUM = "medium"


class MiscastDaemonHostilePurpose(str, Enum):
    BEGUILE = "beguile"
    CORRUPT = "corrupt"
    DESTROY = "destroy"


class MiscastDaemonInitialCourse(str, Enum):
    ACT_IMMEDIATELY = "act_immediately"
    FLEE_AND_PLOT = "flee_and_plot"


class MiscastDaemonReturnTrigger(str, Enum):
    DAEMON_DESTROYED = "daemon_destroyed"
    CASTER_DESTROYED = "caster_destroyed"


class MiscastFascinatingRiftRangeLimit(str, Enum):
    LONG = "long"


class MiscastFascinatingRiftCloseTrigger(str, Enum):
    SOMEONE_ENTERED = "someone_entered"
    SOMETHING_EMERGED = "something_emerged"


class MiscastFascinatingRiftWitnessOutcome(str, Enum):
    IMMUNE = "immune"
    RESISTED = "resisted"
    COMPELLED_TO_ENTER = "compelled_to_enter"


@dataclass(frozen=True, slots=True)
class MiscastEffectTarget:
    target_id: str
    policy: TargetInjuryPolicy
    state: TargetInjuryState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.policy, TargetInjuryPolicy):
            raise TypeError("policy must be a TargetInjuryPolicy")
        _validate_policy_state(self.policy, self.state)


@dataclass(frozen=True, slots=True)
class MiscastMinorLoreEffectRequest:
    resolution_id: str
    caster_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastHideousStenchTarget:
    target_id: str
    can_give_ground: bool

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.can_give_ground, bool):
            raise TypeError("can_give_ground must be a boolean")


@dataclass(frozen=True, slots=True)
class MiscastNextTestPenaltyRequest:
    resolution_id: str
    target_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_non_empty_string(self.rule_id, "rule_id")

    @property
    def modifier(self) -> DiceModifier:
        return DiceModifier(rule_id=self.rule_id, amount=-1)


@dataclass(frozen=True, slots=True)
class MiscastFellowshipGrimUntilBatheRequest:
    resolution_id: str
    target_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_non_empty_string(self.rule_id, "rule_id")

    @property
    def characteristic(self) -> Characteristic:
        return Characteristic.FELLOWSHIP

    @property
    def modifier(self) -> QualityModifier:
        return QualityModifier(
            rule_id=self.rule_id,
            quality=TestQuality.GRIM,
        )


MiscastHideousStenchFollowUp = (
    GiveGroundRequest | MiscastNextTestPenaltyRequest
)


@dataclass(frozen=True, slots=True)
class MiscastHideousStenchRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    targets: tuple[MiscastHideousStenchTarget, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Hideous Stench request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.HIDEOUS_STENCH,
        )
        targets = tuple(self.targets)
        if not all(
            isinstance(item, MiscastHideousStenchTarget)
            for item in targets
        ):
            raise TypeError(
                "targets must contain MiscastHideousStenchTarget values"
            )
        target_ids = tuple(item.target_id for item in targets)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Hideous Stench target ids must be unique")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class MiscastHideousStenchTargetResult:
    target_id: str
    outcome: MiscastHideousStenchOutcome
    decision_owner: DecisionOwner | None
    allowed_choices: tuple[MiscastHideousStenchChoice, ...]
    selected_choice: MiscastHideousStenchChoice
    follow_ups: tuple[MiscastHideousStenchFollowUp, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastHideousStenchResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    targets: tuple[MiscastHideousStenchTargetResult, ...]
    fellowship_penalty: MiscastFellowshipGrimUntilBatheRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastRecentSpellOption:
    option_id: str
    spell_rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.option_id, "recent spell option_id")
        _validate_non_empty_string(
            self.spell_rule_id,
            "recent spell rule_id",
        )


@dataclass(frozen=True, slots=True)
class MiscastSpellRecastRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    recent_spell_options: tuple[MiscastRecentSpellOption, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Spell Recast request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.SPELL_RECAST,
        )
        options = tuple(self.recent_spell_options)
        if not options:
            raise ValueError("Spell Recast requires a recent spell snapshot")
        if not all(
            isinstance(item, MiscastRecentSpellOption) for item in options
        ):
            raise TypeError(
                "recent_spell_options must contain "
                "MiscastRecentSpellOption values"
            )
        option_ids = tuple(item.option_id for item in options)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("recent spell option ids must be unique")
        object.__setattr__(self, "recent_spell_options", options)


@dataclass(frozen=True, slots=True)
class MiscastSpellRecastApplicationRequest:
    resolution_id: str
    caster_id: str
    source_option_id: str
    spell_rule_id: str
    potency: int
    target_choice_owner: DecisionOwner
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.source_option_id, "source_option_id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        if self.potency != 1:
            raise ValueError("a Spell Recast must have Potency 1")
        if self.target_choice_owner is not DecisionOwner.GM:
            raise ValueError("a Spell Recast target must be chosen by the GM")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastSpellRecastResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    selected_index: int
    selected_option: MiscastRecentSpellOption
    recast_request: MiscastSpellRecastApplicationRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastTruthboundRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Truthbound request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.TRUTHBOUND,
        )


@dataclass(frozen=True, slots=True)
class MiscastTruthboundUntilDowntimeRequest:
    resolution_id: str
    caster_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastTruthboundResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    truthbound: MiscastTruthboundUntilDowntimeRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastArcaneSightRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Arcane Sight request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.ARCANE_SIGHT,
        )


@dataclass(frozen=True, slots=True)
class MiscastArcaneSightUntilMorrsliebFullRequest:
    resolution_id: str
    caster_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastArcaneSightResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    arcane_sight: MiscastArcaneSightUntilMorrsliebFullRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastFearedFoeIllusionRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    feared_foe_reference_id: str
    battle_active: bool
    outside_battle_duration_minutes: int | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Feared Foe Illusion request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.FEARED_FOE_ILLUSION,
        )
        _validate_non_empty_string(
            self.feared_foe_reference_id,
            "feared_foe_reference_id",
        )
        if not isinstance(self.battle_active, bool):
            raise TypeError("battle_active must be a boolean")
        minutes = self.outside_battle_duration_minutes
        if self.battle_active and minutes is not None:
            raise ValueError(
                "an in-battle illusion lasts until battle end, not minutes"
            )
        if not self.battle_active and (
            not isinstance(minutes, int)
            or isinstance(minutes, bool)
            or minutes < 1
        ):
            raise ValueError(
                "an out-of-battle illusion requires positive duration minutes"
            )


@dataclass(frozen=True, slots=True)
class MiscastFearedFoeIllusionEffectRequest:
    resolution_id: str
    caster_id: str
    feared_foe_reference_id: str
    duration: MiscastFearedFoeIllusionDuration
    duration_minutes: int | None
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(
            self.feared_foe_reference_id,
            "feared_foe_reference_id",
        )
        if not isinstance(self.duration, MiscastFearedFoeIllusionDuration):
            raise TypeError(
                "duration must be a MiscastFearedFoeIllusionDuration"
            )
        if self.duration is MiscastFearedFoeIllusionDuration.UNTIL_BATTLE_END:
            if self.duration_minutes is not None:
                raise ValueError("battle duration must not include minutes")
        elif (
            not isinstance(self.duration_minutes, int)
            or isinstance(self.duration_minutes, bool)
            or self.duration_minutes < 1
        ):
            raise ValueError("minute duration must be positive")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastFearedFoeIllusionResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    illusion: MiscastFearedFoeIllusionEffectRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastArcaneSpillRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    stagger_impact: StaggerImpactRequest

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Arcane Spill request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.ARCANE_SPILL,
        )
        if not isinstance(self.stagger_impact, StaggerImpactRequest):
            raise TypeError("stagger_impact must be a StaggerImpactRequest")


@dataclass(frozen=True, slots=True)
class MiscastArcaneSpillResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    state: TargetInjuryState
    stagger_impact: StaggerImpactResult
    lore_effect_request: MiscastMinorLoreEffectRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastInternalDamageRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    caster: MiscastEffectTarget
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    additional_profile_wounds: tuple[AdditionalProfileWound, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Internal Damage request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.INTERNAL_DAMAGE,
        )
        if not isinstance(self.caster, MiscastEffectTarget):
            raise TypeError("caster must be a MiscastEffectTarget")
        if self.caster.target_id != self.source.target_id:
            raise ValueError("Internal Damage target must be the caster")
        wound_dice_modifiers = tuple(self.wound_dice_modifiers)
        wound_negation_options = tuple(self.wound_negation_options)
        additional_profile_wounds = tuple(self.additional_profile_wounds)
        if not all(
            isinstance(item, WoundDiceModifier)
            for item in wound_dice_modifiers
        ):
            raise TypeError(
                "wound_dice_modifiers must contain WoundDiceModifier values"
            )
        if not all(
            isinstance(item, WoundNegationOption)
            for item in wound_negation_options
        ):
            raise TypeError(
                "wound_negation_options must contain WoundNegationOption values"
            )
        if not all(
            isinstance(item, AdditionalProfileWound)
            for item in additional_profile_wounds
        ):
            raise TypeError(
                "additional_profile_wounds must contain "
                "AdditionalProfileWound values"
            )
        character_policy = self.caster.policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }
        if character_policy and additional_profile_wounds:
            raise ValueError(
                "a character cannot receive additional profile Wounds"
            )
        if not character_policy and (
            wound_dice_modifiers or wound_negation_options
        ):
            raise ValueError(
                "a profile NPC cannot use Wounds Table modifiers or negation"
            )
        object.__setattr__(
            self,
            "wound_dice_modifiers",
            wound_dice_modifiers,
        )
        object.__setattr__(
            self,
            "wound_negation_options",
            wound_negation_options,
        )
        object.__setattr__(
            self,
            "additional_profile_wounds",
            additional_profile_wounds,
        )


@dataclass(frozen=True, slots=True)
class MiscastInternalDamageResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    state: TargetInjuryState
    character_wound: CharacterWoundResult | None
    wound_effect: WoundEffectResult | None
    profile_wound: ProfileWoundResult | None
    consume_wound_negation: ConsumeWoundNegationRequest | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastEarsRingingRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    targets: tuple[MiscastEffectTarget, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Ears ringing request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.EAR_DAMAGE,
        )
        targets = tuple(self.targets)
        if not targets:
            raise ValueError("Ears ringing targets must not be empty")
        if not all(isinstance(item, MiscastEffectTarget) for item in targets):
            raise TypeError("targets must contain MiscastEffectTarget values")
        target_ids = tuple(item.target_id for item in targets)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Ears ringing target ids must be unique")
        if target_ids[0] != self.source.target_id:
            raise ValueError("the caster must be the first Ears ringing target")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class MiscastEarsRingingTargetResult:
    target_id: str
    state: TargetInjuryState
    fixed_character_wound: FixedCharacterWoundResult | None
    wound_effect: WoundEffectResult | None
    profile_wound: ProfileWoundResult | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastEarsRingingResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    targets: tuple[MiscastEarsRingingTargetResult, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastRandomTransportRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    origin_zone_id: str
    eligible_destination_zone_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Random Transport request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.RANDOM_TRANSPORT,
        )
        _validate_non_empty_string(self.origin_zone_id, "origin_zone_id")
        destinations = tuple(self.eligible_destination_zone_ids)
        if not destinations:
            raise ValueError(
                "Random Transport requires an eligible destination snapshot"
            )
        for destination in destinations:
            _validate_non_empty_string(destination, "destination zone id")
        if len(set(destinations)) != len(destinations):
            raise ValueError(
                "Random Transport destination zone ids must be unique"
            )
        if self.origin_zone_id in destinations:
            raise ValueError(
                "the current Zone is not a Medium Range destination"
            )
        object.__setattr__(
            self,
            "eligible_destination_zone_ids",
            destinations,
        )


@dataclass(frozen=True, slots=True)
class MiscastRandomTransportRelocationRequest:
    resolution_id: str
    caster_id: str
    origin_zone_id: str
    destination_zone_id: str
    rule_id: str
    destination_range: MiscastRandomTransportRange = field(
        init=False,
        default=MiscastRandomTransportRange.MEDIUM,
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.origin_zone_id, "origin_zone_id")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if self.destination_zone_id == self.origin_zone_id:
            raise ValueError("Random Transport must change the caster's Zone")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastRandomTransportResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    selected_index: int
    selected_destination_zone_id: str
    relocation: MiscastRandomTransportRelocationRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastSunlightBlindnessRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Sunlight Blindness request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.SUNLIGHT_BLINDNESS,
        )


@dataclass(frozen=True, slots=True)
class MiscastSunlightBlindnessUntilDowntimeRequest:
    resolution_id: str
    caster_id: str
    rule_id: str
    unusable_illumination: tuple[MiscastIlluminationKind, ...] = field(
        init=False,
        default=(
            MiscastIlluminationKind.SUNLIGHT,
            MiscastIlluminationKind.OTHER_NATURAL_LIGHT,
        ),
    )
    usable_illumination: tuple[MiscastIlluminationKind, ...] = field(
        init=False,
        default=(
            MiscastIlluminationKind.TORCHLIGHT,
            MiscastIlluminationKind.OTHER_ARTIFICIAL_LIGHT,
            MiscastIlluminationKind.ARCANE_ILLUMINATION,
        ),
    )
    otherwise_treat_as_dead_of_night: bool = field(
        init=False,
        default=True,
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastSunlightBlindnessResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    blindness: MiscastSunlightBlindnessUntilDowntimeRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastUnnaturalWindRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    targets: tuple[MiscastEffectTarget, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Unnatural Wind request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.UNNATURAL_WIND,
        )
        targets = tuple(self.targets)
        if not targets:
            raise ValueError("Unnatural Wind targets must not be empty")
        if not all(isinstance(item, MiscastEffectTarget) for item in targets):
            raise TypeError("targets must contain MiscastEffectTarget values")
        target_ids = tuple(item.target_id for item in targets)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Unnatural Wind target ids must be unique")
        if target_ids[0] != self.source.target_id:
            raise ValueError("the caster must be the first Unnatural Wind target")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class MiscastUnnaturalWindTargetResult:
    target_id: str
    state: TargetInjuryState
    excluded_as_monstrosity: bool
    condition_application: ConditionApplicationResult | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastUnnaturalWindResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    targets: tuple[MiscastUnnaturalWindTargetResult, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastZoneHazardRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Zone Hazard Miscast request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.ZONE_HAZARD,
        )


@dataclass(frozen=True, slots=True)
class MiscastZoneHazardResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    zone_hazard: ZoneHazardRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastDaemonRiftRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Daemon Rift request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.DAEMON_RIFT,
        )


@dataclass(frozen=True, slots=True)
class MiscastDaemonManifestationRequest:
    resolution_id: str
    caster_id: str
    rift_anchor_target_id: str
    rule_id: str
    nature_choice_owner: DecisionOwner = field(
        init=False,
        default=DecisionOwner.GM,
    )
    stat_block_choice_owner: DecisionOwner = field(
        init=False,
        default=DecisionOwner.GM,
    )
    placement_choice_owner: DecisionOwner = field(
        init=False,
        default=DecisionOwner.GM,
    )
    initial_course_choice_owner: DecisionOwner = field(
        init=False,
        default=DecisionOwner.GM,
    )
    hostile_to_caster_and_allies: bool = field(init=False, default=True)
    hostile_purpose_options: tuple[MiscastDaemonHostilePurpose, ...] = field(
        init=False,
        default=(
            MiscastDaemonHostilePurpose.BEGUILE,
            MiscastDaemonHostilePurpose.CORRUPT,
            MiscastDaemonHostilePurpose.DESTROY,
        ),
    )
    initial_course_options: tuple[MiscastDaemonInitialCourse, ...] = field(
        init=False,
        default=(
            MiscastDaemonInitialCourse.ACT_IMMEDIATELY,
            MiscastDaemonInitialCourse.FLEE_AND_PLOT,
        ),
    )
    return_to_chaos_triggers: tuple[MiscastDaemonReturnTrigger, ...] = field(
        init=False,
        default=(
            MiscastDaemonReturnTrigger.DAEMON_DESTROYED,
            MiscastDaemonReturnTrigger.CASTER_DESTROYED,
        ),
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(
            self.rift_anchor_target_id,
            "rift_anchor_target_id",
        )
        if self.rift_anchor_target_id != self.caster_id:
            raise ValueError("Daemon Rift must be anchored to the caster")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastDaemonRiftResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    daemon_manifestation: MiscastDaemonManifestationRequest
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftWitness:
    target_id: str
    willpower_test: TestRequest
    effect_immunities: tuple[EffectImmunity, ...] = field(
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.willpower_test, TestRequest):
            raise TypeError("willpower_test must be a TestRequest")
        immunities = tuple(self.effect_immunities)
        if not all(isinstance(item, EffectImmunity) for item in immunities):
            raise TypeError(
                "effect_immunities must contain EffectImmunity values"
            )
        classifications = tuple(item.classification for item in immunities)
        if len(set(classifications)) != len(classifications):
            raise ValueError("effect immunity classifications must be unique")
        object.__setattr__(self, "effect_immunities", immunities)


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    selected_zone_id: str
    witnesses: tuple[MiscastFascinatingRiftWitness, ...] = field(
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fascinating Rift request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.FASCINATING_RIFT,
        )
        _validate_non_empty_string(self.selected_zone_id, "selected_zone_id")
        witnesses = tuple(self.witnesses)
        if not all(
            isinstance(item, MiscastFascinatingRiftWitness)
            for item in witnesses
        ):
            raise TypeError(
                "witnesses must contain MiscastFascinatingRiftWitness values"
            )
        target_ids = tuple(item.target_id for item in witnesses)
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("Fascinating Rift witness ids must be unique")
        test_ids = tuple(item.willpower_test.id for item in witnesses)
        if len(set(test_ids)) != len(test_ids):
            raise ValueError(
                "Fascinating Rift Willpower Test ids must be unique"
            )
        for witness in witnesses:
            if any(
                modifier.rule_id == self.source.rule_id
                for modifier in witness.willpower_test.dice_modifiers
            ):
                raise ValueError(
                    "base Willpower Test must not include the Rift penalty"
                )
        object.__setattr__(self, "witnesses", witnesses)


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftPortal:
    resolution_id: str
    caster_id: str
    zone_id: str
    rule_id: str
    zone_choice_owner: DecisionOwner = field(
        init=False,
        default=DecisionOwner.GM,
    )
    range_limit: MiscastFascinatingRiftRangeLimit = field(
        init=False,
        default=MiscastFascinatingRiftRangeLimit.LONG,
    )
    close_triggers: tuple[MiscastFascinatingRiftCloseTrigger, ...] = field(
        init=False,
        default=(
            MiscastFascinatingRiftCloseTrigger.SOMEONE_ENTERED,
            MiscastFascinatingRiftCloseTrigger.SOMETHING_EMERGED,
        ),
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        _validate_non_empty_string(self.zone_id, "zone_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftCompulsionRequest:
    resolution_id: str
    target_id: str
    portal_id: str
    rule_id: str
    must_attempt_to_enter: bool = field(init=False, default=True)
    restraint_prevents_entry: bool = field(init=False, default=True)
    restraint_ends_compulsion: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_non_empty_string(self.portal_id, "portal_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftWitnessResult:
    target_id: str
    outcome: MiscastFascinatingRiftWitnessOutcome
    source_application: EffectApplicationResult
    willpower_test: TestResult | None
    compulsion: MiscastFascinatingRiftCompulsionRequest | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastFascinatingRiftResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    portal: MiscastFascinatingRiftPortal
    witnesses: tuple[MiscastFascinatingRiftWitnessResult, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MiscastCatastrophicDeathRequest:
    id: str
    source: MiscastTableEffectRequest
    magic_state: WizardMagicState
    caster: MiscastEffectTarget

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Catastrophic Death request id")
        _validate_effect_source(
            self.source,
            self.magic_state,
            MiscastTableEntryId.CATASTROPHIC_DEATH,
        )
        if not isinstance(self.caster, MiscastEffectTarget):
            raise TypeError("caster must be a MiscastEffectTarget")
        if self.caster.target_id != self.source.target_id:
            raise ValueError("Catastrophic Death target must be the caster")


@dataclass(frozen=True, slots=True)
class MiscastCatastrophicDeathResult:
    request_id: str
    caster_id: str
    magic_state: WizardMagicState
    state: TargetInjuryState
    dead: bool
    body_destroyed: bool
    can_be_reanimated: bool
    applied_rule_ids: tuple[str, ...]


def _validate_effect_source(
    source: MiscastTableEffectRequest,
    magic_state: WizardMagicState,
    expected_entry: MiscastTableEntryId,
) -> None:
    if not isinstance(source, MiscastTableEffectRequest):
        raise TypeError("source must be a MiscastTableEffectRequest")
    if source.entry_id is not expected_entry:
        raise ValueError(
            f"Miscast effect requires {expected_entry.value}, "
            f"got {source.entry_id.value}"
        )
    if not isinstance(magic_state, WizardMagicState):
        raise TypeError("magic_state must be a WizardMagicState")
    if magic_state.miscast_dice != source.pool_dice_count:
        raise ValueError("Miscast Pool state must match the table effect")
    if magic_state.casting_successes:
        raise ValueError(
            "Casting successes must be cleared before a Miscast effect"
        )


def _validate_policy_state(
    policy: TargetInjuryPolicy,
    state: TargetInjuryState,
) -> None:
    if policy in {TargetInjuryPolicy.PLAYER, TargetInjuryPolicy.CHAMPION}:
        if not isinstance(state, CharacterInjuryState):
            raise TypeError("Player/Champion requires CharacterInjuryState")
        return
    if not isinstance(state, ProfileInjuryState):
        raise TypeError("profile NPC requires ProfileInjuryState")
    if policy is TargetInjuryPolicy.MINION and state.wound_limit != 1:
        raise ValueError("Minion requires a wound_limit of 1")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
