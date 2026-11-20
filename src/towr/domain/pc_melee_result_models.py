"""Source-bound journal for the bounded PC melee encounter (ADR-0065)."""
from __future__ import annotations

from towr.domain.pc_demigryph_models import pc_kernel_attack_types
from towr.domain.pc_combat_equipment_models import validate_pc_weapon_inventory
from towr.domain.weapon_inventory_models import WeaponInventoryState, WeaponItemLocation, WeaponGrip
from towr.domain.tool_inventory_models import ToolInventoryState, ToolInventoryTransition, initial_tool_inventory
from towr.domain.pc_musician_effect_models import PcMusicianActionProof, PcMusicianSignalProof
from towr.domain.pc_musician_tactics import PcMusicianIntentProof
from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
from towr.domain.pc_oath_models import (
    PcOathActor, PcLadyPrayerProof, PcOathNegationAckProof, initial_pc_oaths, lady_prayer_selected,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof,initial_pc_weapon_inventory
from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent, build_pc_attack_weapon_intent, weapon_use_hand
from towr.domain.weapon_use_models import WeaponUse, WeaponProtectionUse
from towr.domain.talent_armour_bane_models import ArmourBaneApplication
from towr.domain.talent_allies_in_arms_models import AlliesInArmsApplication
from towr.domain.pc_immediate_attack_models import PcBashDecisionProof,PcImmediateStrikeProof

from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.potion_recover_models import HealingPotionRecoverSource
from towr.domain.pc_potion_models import (PcPotionRecoverProof, ENHANCEMENT_CHARACTERISTICS,
    pc_effective_definition, selected_pc_potion)
from towr.domain.pc_magic_models import (PcMagicPending,PcMagicModifier,PcMagicTask,
    PcCastingProof,PcMagicInterruptionProof,PcMiscastRollProof,PcMagicEffectProof,PcMagicCleanupProof,
    PcMagicUnsupported,pc_magic_unsupported,expected_magic_interruption,magic_test_modifiers)
from towr.domain.pc_generated_talents import (PcWildAttackProof,PcDefensiveStanceProof,
    expected_wild_attack,pending_wild_attack,generated_attack_quality)

from dataclasses import dataclass, field, fields, is_dataclass, replace
from towr.domain.pc_companion_models import PcMountCompanionState
from towr.domain.pc_mount_retention_models import PcMountRetentionProof
from towr.domain.pc_companion_turn_models import PcCompanionWaitProof
from towr.domain.pc_companion_departure_models import PcCompanionDepartureProof
from towr.domain.pc_companion_landing_models import PcCompanionLandingProof
from towr.domain.pc_back_in_saddle_models import PcBackInSaddleMoveProof,PcBackInSaddleRecoverProof
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.domain.pc_weighted_net_models import PcNetDrop,PcNetThrowLanding

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import AttackRequest, AttackOutcome, DamageImpactSpec, ImpactOutcome, MissConsequence, NearbyTargetsStaggerSpec
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_weapon_models import (pc_weapon_damage, pc_weapon_test_modifiers,
    pc_weapon_attack_modifiers, pc_weapon_damage_modifiers,pc_weapon_requires_two_hands)
from towr.domain.pc_npc_ability_models import (pc_npc_outnumbering_modifier,pc_npc_allows_give_ground,
    pc_npc_allows_enemy_higher_ground,
    pc_npc_attack_modifiers,pc_npc_damage_modifiers,pc_npc_damage_profile,pc_npc_stagger_defeat_spec,
    pc_npc_wound_dice_modifiers)
from towr.domain.pc_npc_wound_models import PcNpcBrokenTurnUnsupported, PcNpcBrokenWaveTurnUnsupported, pc_npc_broken_turn_unsupported
from towr.domain.pc_npc_exit_models import PcNpcExitProof
from towr.domain.pc_minion_defeat_models import validate_pc_minion_defeat_equipment
from towr.domain.pc_npc_distraction_models import (PcNpcDistractionSource,PcNpcWaveDistractionSource,PcNpcCleavingDistractionSource,PcNpcDistractionExpiredProof,
    validate_pc_npc_distractions,expected_pc_npc_distraction_expiry,pc_npc_distraction_test_modifiers)
from towr.domain.pc_npc_grudge_models import (PcNpcGrudgeDistractionSource,PcNpcGrudgeEncounterProof,
    pc_npc_grudge_melee_modifiers,expected_pc_npc_grudge_encounter)
from towr.domain.pc_bestigor_models import (PcNpcBloodRageProof, PcBestigorGloriousSource, PcBestigorWaveGloriousSource,
    expected_pc_npc_blood_rage, pc_bestigor_attack_quality)
from towr.domain.pc_warped_form_models import (PcWarpedFormActivationProof, PcWarpedFormTargetProof,
    PcWarpedFormProfileProof, PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof,
    current_warped_form, expected_pc_warped_form_activation)
from towr.domain.pc_flagellant_models import (PcNpcRecoverProof, PcFlagellantMissWoundProof,
    validate_pc_flagellant_conditions, flagellant_conditions, pc_flagellant_recover_selected,
    pc_flagellant_first_stagger_spec)
from towr.domain.pc_ranged_models import (PcRangedShotProof,PcRangedReloadProof,PcRangedHelpUseProof,initial_pc_ranged,
    pc_ranged_unsupported,ranged_reload_declaration,prepare_pc_ranged_shot,pc_repeater_attack_modifiers,
    pc_ranged_profile_modifiers, pc_conditioned_ranged_attack)
from towr.domain.reload_models import FreeReloadWeaponState, ReloadableWeaponState
from towr.domain.pc_short_opening_models import (PcNpcApproachProof, PcRangedCloseUnsupported,
    pc_enemy_range, pc_has_close_enemy, expected_pc_npc_approach, validate_pc_approaches)
from towr.domain.pc_battlefield_models import PcBattlefieldState, build_pc_battlefield
from towr.domain.pc_mount_models import (PcMountedState,PcDismountProof,initial_pc_mounts,
    validate_pc_mounts,expected_pc_dismount,pc_is_mounted,pc_mounted_attack_effects)
from towr.domain.pc_npc_shield_models import (PcNpcShieldState,PcNpcShieldDropProof,PcNpcShieldRecoverProof,
    initial_npc_shields,validate_npc_shields,build_npc_shield_pickup)
from towr.domain.pc_briarroot_models import (PcBriarrootBinding,PcBriarrootProof,PcBriarrootReleaseProof,
    validate_briarroot_bindings)
from towr.domain.pc_demigryph_models import (PcDemigryphIntentProof,PcDemigryphStrikeProof,
    pc_kernel_resolution)
from towr.domain.pc_falling_models import (PcFallingProof,PcFallingAcknowledgementProof,
    expected_pc_falling_request,falling_acknowledgement_source)
from towr.domain.pc_throwing_inventory_models import PcThrowingInventoryReceipt
from towr.domain.pc_weapon_area_models import (
    PcWeaponAreaSnapshot,PcWeaponAreaConditionProof,PcWeaponAreaEndProof,
    PcWeaponHazardProof,PcWeaponHazardCompletionProof,current_weapon_area,
    expected_ablaze_hazard,weapon_hazard_completion)
from towr.domain.pc_extinguish_models import PcExtinguishProof,pc_extinguish_selected
from towr.domain.pc_magic_weapon_models import PcMagicWeaponAttackReceipt,PcScarabChargeProof
from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
from towr.domain.pc_terrain_models import PcTerrainTraversalProof,expected_pc_terrain_traversal
from towr.domain.pc_hammer_recover_models import PcHammerRetrievalProof
from towr.domain.pc_give_ground_models import PcGiveGroundProof,PcAfterGiveGroundProof
from towr.domain.pc_brawn_displacement_models import PcBrawnShoveProof
from towr.domain.brawn_impact_models import BrawnDisplacementRequest
from towr.domain.pc_broken_battlefield_models import (PcBrokenMoveProof,PcBrokenRunProof,PcBrokenBlockedProof,
    expected_pc_broken_battlefield_step)
from towr.domain.pc_mount_attack_models import (PcMountedAttackIntent,pc_uses_mount_attack,
    build_pc_mounted_attack_intent,prepare_pc_mounted_attack)
from towr.domain.pc_briarroot_weapon_models import (PcBriarrootDroppedWeapon,
    PcBriarrootWeaponDropProof,PcBriarrootWeaponPickupProof,PcBriarrootWeaponApproachProof,
    PcBriarrootWeaponPickup,validate_briarroot_dropped_weapons,
    briarroot_weapon_on_ground,can_pickup_briarroot_weapon,build_briarroot_weapon_drop)
from towr.domain.pc_weighted_net_models import (PcWeightedNetState,PcNetThrowLanding,PcNetDrop,
    PcNetReleaseProof,PcNetPickupProof,PcNetApproachProof,PcNetIncidentalPickupProof,
    initial_weighted_nets,validate_weighted_net_bank,weighted_net_condition_sources,
    weighted_net_recovery_options,selected_weighted_net_recovery)
from towr.domain.pc_battlefield_manoeuvre_models import (PcBattlefieldChargeProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof,
    current_pc_charge,pc_charge_attack_modifiers,proposed_pc_battlefield_manoeuvre)
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldMoveProof, PcBattlefieldRecoverProof, validate_pc_battlefield_history,
    pc_battlefield_attack_available, pc_battlefield_npc_recover_selected,
    pc_battlefield_allows_outnumbering,
)
from towr.domain.pc_npc_ranged_models import (
    PcNpcRangedShotProof, PcNpcRangedReloadProof, initial_pc_npc_weapon_inventories,
    validate_pc_npc_ranged_weapons, pc_npc_ranged_weapon, npc_ranged_reload_declaration,
    prepare_pc_npc_ranged_shot,
)
from towr.domain.pc_shield_models import (PcShieldState, PcShieldLocation, PcShieldReleaseProof,
    initial_pc_shield, pc_has_working_shield, pc_shield_recover_hand, pc_shield_recover_needed,
    pc_shield_resilience, expected_pc_shield_release,
    PcShieldDropProof, PcShieldApproachProof, PcShieldPickup, validate_pc_shields)
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
from towr.domain.pc_aim_models import (PcAimProof, PcAimSecondActionProof, PcAimConsumptionProof,
    validate_pc_aim_history, expected_pc_aim_consumption, pc_hochland_needs_aim, pc_aim_attack_modifiers)
from towr.domain.pc_npc_aim_models import (PcNpcAimProof,PcNpcAimConsumptionProof,
    validate_pc_npc_aim_history,expected_npc_aim_consumption,npc_needs_aim)
from towr.domain.pc_blunderbuss_models import (PcBlunderbussNearbyProof, PcBlunderbussSnapshot,
    PcBlunderbussTargetProof,PcBlunderbussProfileProof,PcBlunderbussEndProof,PcBlunderbussMinionDefeatProof,
    current_pc_blunderbuss_wave,pc_blunderbuss_pending_npc_target,validate_pc_blunderbuss_history)
from towr.domain.pc_net_models import (PcNetConditionSource, PcNpcNetDrawProof,
    net_condition_sources_from_attack, selected_pc_npc_net_attack, expected_pc_npc_net_draw)
from towr.domain.pc_hit_condition_models import (PcHitConditionSource,hit_condition_sources_from_attack,
    retain_pc_hit_conditions)
from towr.domain.pc_backup_weapon_models import (pc_active_weapon, pc_preferred_weapon_hand,
    pc_active_weapon_item_id)
from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
from towr.domain.fate_models import FateSessionState, FateNearMissBurnRequest, FateGloriousSpendResult, FATE_NEAR_MISS_RULE_ID
from towr.domain.infection_models import DailyWoundState
from towr.domain.help_models import HelpActionExecutionRequest, HelpActionExecutionResult, HelpBonusApplicationResult
from towr.domain.automatic_help_models import (AutomaticHelpActionRequest,AutomaticHelpActionResult,
    AutomaticHelpBonusApplicationResult)
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundType, ProfileInjuryState, ProfileNpcType,
    ProfileStateChangeRequest, WoundConditionEffect, WoundConsequence, WoundConsequenceRequest,
    WoundEffectDuration, WoundEnduranceFailure, WoundEnduranceTestRequest, WoundEnduranceTestResult,
    WoundRestriction, WoundRestrictionEffect, WoundChoiceRequest, WoundChoiceResult, WoundChoice, WoundEntryId,
    MinionStaggerDefeatCause,
)
from towr.domain.pc_heavy_wound_models import (PcBodyFact, PcBodyFactKind, available_sides, usable_hands, injured_hands, usable_weapon_hand, has_ongoing_condition, critical_for_hand)
from towr.domain.critical_injury_models import CriticalInjuryTestResult
from towr.domain.magic_models import WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.pc_melee_models import (
    PcMeleeWeapon,PcMeleePolicy,
    PcFatePolicy, PcMeleeScenario, PcWeaponHand, PcTwoHandedGrip, validate_pc_melee_scenario_admission,
)
from towr.domain.protection_models import (
    ProtectionPreparationRequest, ProtectionPreparationResult, ProtectionTestOption,
)
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionTarget,
    RecoverMode, RecoverObjectInteractionFollowUp, RecoverStandardChoice,
)
from towr.domain.resolution_models import (AttackerStaggerRequest, KernelAttackRequest, TargetInjuryPolicy,
    ConsumeWoundNegationRequest, NearbyTargetsStaggerRequest,HazardExposureRequest,
    GiveGroundRequest,ConditionAfterGiveGroundRequest)
from towr.domain.pc_cleaving_blow_models import (
    PcCleavingStartProof,PcCleavingTargetProof,PcCleavingProfileProof,
    PcCleavingMinionDefeatProof,PcCleavingEndProof,validate_cleaving_history,
    current_cleaving_wave,expected_cleaving_start,cleaving_pending_npc_target,
)
from towr.domain.pc_npc_champion_models import (NpcChampionMetadata,NpcChampionShieldDrop,PcNpcChampionRecoverProof,
    initial_npc_champions,validate_npc_champions,npc_champion_pending_owner,is_npc_champion)
from towr.domain.injury_models import injury_is_defeated
from towr.domain.test_models import (
    DiceModifier, QualityModifier, RerollTrace, RollTrace, Skill, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatRoundAdvanceResult,
    CombatRoundState, CombatSide, CombatTurnEndResult, CombatTurnParticipant, CombatTurnStartResult,
    CombatTurnState, CombatActionSlotResult, CombatActionSlot,ManoeuvreKind,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest, CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleRollResult,
)


class PcMeleeOutcome(str, Enum):
    OBJECTIVE_ACHIEVED = "objective_achieved"
    PARTY_DEFEATED = "party_defeated"
    ROUND_LIMIT = "round_limit"
    UNSUPPORTED_PATH = "unsupported_path"


PcMeleePending = WoundEnduranceTestRequest | WoundConsequenceRequest | WoundChoiceRequest | AttackerStaggerRequest | ProfileStateChangeRequest | HazardExposureRequest | GiveGroundRequest | ConditionAfterGiveGroundRequest | BrawnDisplacementRequest


@dataclass(frozen=True, slots=True)
class PcMeleeUnsupported:
    actor_id: str
    source_id: str
    reason: str
    wound_sequence: int
    table_total: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise ValueError('unsupported PC result requires its owner')
        if (type(self.reason) is not str or self.reason not in ('unavailable_anatomical_target','two_handed_grip_unavailable',
                'ranged_grip_unavailable','ranged_reload_hands_unavailable')
                or type(self.source_id) is not str or not self.source_id):
            raise ValueError('unsupported PC result requires an exact Wound source')
        for value in (self.wound_sequence, self.table_total):
            if type(value) is not int or value < 1:
                raise ValueError('unsupported Wound values must be positive integers')
        if not 11 <= self.table_total <= 23:
            raise ValueError('anatomical stop requires a heavy Wound source')
        if self.reason in ('two_handed_grip_unavailable','ranged_grip_unavailable',
                'ranged_reload_hands_unavailable') and self.table_total not in (16,18,20):
            raise ValueError('two-handed grip stop requires its actual arm/clutch Wound')


@dataclass(frozen=True, slots=True)
class PcTimedWound:
    effect: WoundConditionEffect
    source_id: str
    deadline_round: int

    def __post_init__(self):
        if (not isinstance(self.effect, WoundConditionEffect)
                or self.effect.duration is not WoundEffectDuration.END_OF_NEXT_TURN
                or self.effect.condition not in (Condition.DRAINED, Condition.BLINDED)):
            raise ValueError('PC expiry supports its bound Drained/Blinded effect only')
        if type(self.source_id) is not str or not self.source_id or type(self.deadline_round) is not int or self.deadline_round < 1:
            raise ValueError('PC expiry requires its source and deadline')


@dataclass(frozen=True, slots=True)
class PcFateDecline:
    actor_id: str
    source_id: str
    window: str
    policy: PcFatePolicy

    def __post_init__(self):
        if type(self.window) is not str or self.window not in ('test', 'wound', 'action'):
            raise ValueError('unknown PC Fate decision window')
        if type(self.policy) is not PcFatePolicy:
            raise TypeError('PC Fate decision requires its typed strategy')
        if any(type(v) is not str or not v for v in (self.actor_id, self.source_id)):
            raise ValueError('PC Fate decline requires actor and source')


@dataclass(frozen=True, slots=True)
class PcMeleeParticipantState:
    actor_id: str
    injury: CharacterInjuryState
    weapon_inventory: WeaponInventoryState
    fate: FateSessionState
    daily_wounds: DailyWoundState
    timed_wounds: tuple[PcTimedWound, ...] = ()
    body_facts: tuple[PcBodyFact, ...] = ()
    hit_condition_sources: tuple[PcHitConditionSource,...] = ()
    net_condition_sources: tuple[PcNetConditionSource,...] = ()
    shield: PcShieldState | None = field(default=None,kw_only=True)
    potions: tuple[ConsumableItem, ...] = field(default=(), kw_only=True)
    enhancements: tuple[str, ...] = field(default=(), kw_only=True)
    magic: WizardMagicState | None = field(default=None, kw_only=True)
    tool_inventory: ToolInventoryState = field(default_factory=ToolInventoryState, kw_only=True)

    def __post_init__(self):
        if type(self.tool_inventory) is not ToolInventoryState:
            raise TypeError('PC tools require their actual typed physical inventory')
        replace(self.tool_inventory)
        if self.magic is not None:
            if type(self.magic) is not WizardMagicState:
                raise TypeError('PC magic must retain its typed runtime')
            replace(self.magic)
        if type(self.weapon_inventory) is not WeaponInventoryState:
            raise TypeError('PC weapon inventory requires its exact shared runtime state')
        replace(self.weapon_inventory)
        if type(self.potions) is not tuple or any(type(item) is not ConsumableItem for item in self.potions):
            raise TypeError('PC potion state requires typed supplies')
        for item in self.potions:
            replace(item)
        if len({item.id for item in self.potions}) != len(self.potions):
            raise ValueError('PC potion supplies must have unique instance IDs')
        if (type(self.enhancements) is not tuple or len(set(self.enhancements)) != len(self.enhancements)
                or any(name not in ENHANCEMENT_CHARACTERISTICS for name in self.enhancements)):
            raise ValueError('PC enhancements require unique supported Characteristics')
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC state requires its actor ID')
        if not isinstance(self.injury, CharacterInjuryState) or not isinstance(self.fate, FateSessionState):
            raise TypeError('PC state requires PLAYER injury and actual Fate session')
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError('PC state requires typed daily Wound history')
        if self.fate.actor_id != self.actor_id or self.daily_wounds.target_id != self.actor_id:
            raise ValueError('PC Fate/daily histories belong to another actor')
        if self.shield is not None:
            if type(self.shield) is not PcShieldState:
                raise TypeError('PC shield must retain its exact runtime state')
            replace(self.shield)
        if type(self.hit_condition_sources) is not tuple:
            raise TypeError('hit Condition sources must be a canonical tuple')
        for source in self.hit_condition_sources:
            if type(source) is not PcHitConditionSource:
                raise TypeError('hit Condition bank requires exact typed sources')
            replace(source)
            if source.target_id!=self.actor_id:
                raise ValueError('hit Condition source belongs to another target')
        if len({s.application_id for s in self.hit_condition_sources})!=len(self.hit_condition_sources):
            raise ValueError('a successful hit may register its Condition source only once')
        if self.hit_condition_sources and not self.injury.conditions.has(Condition.DRAINED):
            raise ValueError('active hit Condition source cannot lose its Drained flag')
        if type(self.net_condition_sources) is not tuple:
            raise TypeError('Net causes must retain their canonical tuple')
        for source in self.net_condition_sources:
            if type(source) is not PcNetConditionSource:
                raise TypeError('Net bank requires its exact typed causes')
            replace(source)
            if source.target_id!=self.actor_id:
                raise ValueError('Net cause belongs to another PC')
        if len({s.application_id for s in self.net_condition_sources})!=len(self.net_condition_sources):
            raise ValueError('Net cause cannot be registered twice')
        if self.net_condition_sources and not self.injury.conditions.has(Condition.BURDENED):
            raise ValueError('Net cause cannot lose its Burdened flag')
        if not isinstance(self.timed_wounds, (tuple, list)):
            raise TypeError('PC expiry sources must be ordered')
        object.__setattr__(self, 'timed_wounds', tuple(self.timed_wounds))
        if any(not isinstance(e, PcTimedWound) or e.effect not in self.injury.active_wound_effects for e in self.timed_wounds):
            raise ValueError('PC expiry must refer to a current actual effect')
        if len({e.effect for e in self.timed_wounds}) != len(self.timed_wounds):
            raise ValueError('PC expiry sources must not repeat')
        if type(self.body_facts) is not tuple:
            raise TypeError('body facts require a canonical ordered tuple')
        for fact in self.body_facts:
            if type(fact) is not PcBodyFact:
                raise TypeError('body facts must be typed')
            replace(fact)
            if fact.wound_sequence > len(self.injury.wounds):
                raise ValueError('body fact lacks its actual Wound')
            rows = {PcBodyFactKind.INJURED_HAND:(12,),PcBodyFactKind.UNUSABLE_ARM:(16,),
                PcBodyFactKind.LOST_ARM:(20,),PcBodyFactKind.LOST_LEG:(21,),PcBodyFactKind.LOST_EYE:(19,),
                PcBodyFactKind.LOST_FINGER:(12,),PcBodyFactKind.LOST_TEETH:(11,),PcBodyFactKind.CLUTCH_STOMACH:(18,)}
            if self.injury.wounds[fact.wound_sequence-1].table_total not in rows[fact.kind]:
                raise ValueError('body fact differs from its actual Wounds Table source')
        if len(set(self.body_facts)) != len(self.body_facts):
            raise ValueError('body fact cannot be applied twice')


    @property
    def weapon_hand(self):
        from towr.domain.pc_weapon_inventory import pc_hand
        item=self.weapon_inventory.active
        return pc_hand(item.grip) if item is not None and item.location is WeaponItemLocation.HELD else None

    @property
    def using_backup_weapon(self):
        # Read-only strategy view. It cannot change the selected physical unit.
        inventory=self.weapon_inventory
        primary=next((item for item in inventory.items
            if item.source.initial_location is WeaponItemLocation.HELD),None)
        return primary is not None and inventory.active_item_id is not None and inventory.active_item_id!=primary.id

    @property
    def ranged(self):
        from towr.domain.pc_weapon_inventory import pc_member_ranged
        return pc_member_ranged(self)


@dataclass(frozen=True, slots=True)
class PcMeleeState:
    source: PcMeleeScenario
    round_state: CombatRoundState
    party: tuple[PcMeleeParticipantState, ...]
    enemies: tuple[NpcParticipantSnapshot, ...]
    pending: tuple[PcMeleePending, ...] = ()
    pending_wound: CharacterWoundLifecycleRollResult | None = None
    pending_actor_id: str | None = None
    history: tuple[PcMeleeProof, ...] = field(default=(), repr=False)
    oaths: tuple[PcOathActor, ...] = field(default=(), kw_only=True)
    magic_pending: PcMagicPending | None = field(default=None,kw_only=True)
    magic_modifiers: tuple[PcMagicModifier, ...] = field(default=(),kw_only=True)
    magic_notes: tuple[PcMagicTask, ...] = field(default=(),kw_only=True)
    npc_distractions: tuple[PcNpcDistractionSource | PcNpcGrudgeDistractionSource | PcNpcWaveDistractionSource | PcNpcCleavingDistractionSource, ...] = ()
    approached_npc_ids: tuple[str, ...] = field(default=(),kw_only=True)
    battlefield: PcBattlefieldState | None = field(default=None,kw_only=True)
    mounts: tuple[PcMountedState, ...] = field(default=(),kw_only=True)
    companions: tuple[PcMountCompanionState, ...] = field(default=(),kw_only=True)
    weighted_nets: tuple[PcWeightedNetState, ...] = field(default=(),kw_only=True)
    npc_shields: tuple[PcNpcShieldState, ...] = field(default=(),kw_only=True)
    briarroot_bindings: tuple[PcBriarrootBinding, ...] = field(default=(),kw_only=True)
    briarroot_dropped_weapons: tuple[PcBriarrootDroppedWeapon, ...] = field(default=(),kw_only=True)
    npc_champions: tuple[NpcChampionMetadata,...] = field(default=(),kw_only=True)

    def __post_init__(self):
        if not isinstance(self.source, PcMeleeScenario) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError('PC owner requires source scenario and combat clock')
        if type(self.oaths) is not tuple or any(type(row) is not PcOathActor for row in self.oaths):
            raise TypeError('native oath owners require their exact immutable actor bank')
        for row in self.oaths:
            replace(row)
        if len({row.actor_id for row in self.oaths}) != len(self.oaths):
            raise ValueError('native oath actor cannot repeat its resource bank')
        if self.magic_pending is not None:
            if type(self.magic_pending) is not PcMagicPending:
                raise TypeError('PC pending magic must be typed')
            replace(self.magic_pending)
            if self.source.participant(self.magic_pending.caster_id).wizard is None:
                raise ValueError('pending magic must belong to an actual source Wizard')
        for bank,cls in ((self.magic_modifiers,PcMagicModifier),(self.magic_notes,PcMagicTask)):
            if type(bank) is not tuple or any(type(value) is not cls for value in bank):
                raise TypeError('PC magic banks require exact ordered tuples')
            for value in bank:
                replace(value)
        for name in ('party', 'enemies', 'pending', 'history'):
            if not isinstance(getattr(self, name), (tuple, list)):
                raise TypeError('PC owner collections must be ordered')
            object.__setattr__(self, name, tuple(getattr(self, name)))
        validate_pc_approaches(self)
        validate_pc_battlefield_history(self)
        validate_pc_mounts(self)
        from towr.domain.pc_mount_companion_owner import validate_pc_companions
        validate_pc_companions(self)
        validate_weighted_net_bank(self)
        validate_npc_shields(self)
        validate_pc_shields(self)
        validate_npc_champions(self)
        from towr.domain.pc_tool_models import validate_native_tools
        validate_native_tools(self)
        validate_briarroot_bindings(self)
        validate_briarroot_dropped_weapons(self)
        exits = tuple(proof for proof in self.history if type(proof) is PcNpcExitProof)
        actors = tuple(proof.request.actor_id for proof in exits)
        if (len(set(actors))!=len(actors) or any(actor not in self.source.npc_activation_order for actor in actors)
                or exits and self.source.npc_broken_exit_policy is None):
            raise ValueError('NPC exits must preserve their one actual source-bound movement each')
        for proof in exits:
            replace(proof)
        if (not all(isinstance(m, PcMeleeParticipantState) for m in self.party)
                or tuple(m.actor_id for m in self.party) != tuple(m.actor_id for m in self.source.party)):
            raise ValueError('PC owner must preserve its complete ordered party')
        has_hit_effects = any(attack.secondary_effects for enemy in self.source.npc_sources
            for attack in enemy.definition.attacks)
        if not has_hit_effects:
            from towr.domain.weapon_catalog import WeaponKind
            has_hit_effects=any(enemy.definition.generated_components is not None
                and any(item.kind is WeaponKind.SCARAB_KNIFE
                    for item in enemy.definition.generated_components.weapons) for enemy in self.source.npc_sources)
        hit_causes = (tuple(cause for proof in self.history
            if type(proof) in pc_kernel_attack_types() and proof.request.target_id in self.source.pc_activation_order
            for cause in hit_condition_sources_from_attack(proof.request,pc_kernel_resolution(proof)))
            if has_hit_effects else ())
        for member, source in zip(self.party, self.source.party):
            replace(member)
            from towr.domain.pc_armour_models import external_armour_conditions
            if not external_armour_conditions(self,member.actor_id) <= member.injury.conditions.conditions:
                raise ValueError('PC Conditions must retain the independent current armour burden')
            if (member.shield is None)!=(source.shield is None):
                raise ValueError('PC shield runtime must preserve its source loadout membership')
            if (member.magic is None)!=(source.wizard is None):
                raise ValueError('PC magic runtime must retain its Wizard source membership')
            if (member.ranged is None)!=(source.pc.ranged is None):
                raise ValueError('Shooting facts must match actual source item membership')
            from towr.domain.pc_inventory_conditions import external_inventory_conditions
            if not external_inventory_conditions(self,member.actor_id)<=member.injury.conditions.conditions:
                raise ValueError('PC Conditions lost an independent carrying source')
            expected_hit_sources = tuple(cause for cause in hit_causes if cause.target_id==member.actor_id)
            if member.hit_condition_sources!=expected_hit_sources:
                raise ValueError('hit Condition bank must preserve its actual successful Attack history')
            validate_pc_melee_source_types(member.hit_condition_sources,expected_hit_sources)
            expected_net_sources = weighted_net_condition_sources(self,member.actor_id)
            if member.net_condition_sources!=expected_net_sources:
                raise ValueError('Net bank differs from actual successful throws')
            validate_pc_melee_source_types(member.net_condition_sources,expected_net_sources)
            draws = tuple(p for p in self.history if isinstance(p,PcBackupWeaponDrawProof) and p.actor_id==member.actor_id)
            from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
            bash_swaps=tuple(p for p in self.history if type(p) is PcWeaponSwapProof
                and p.actor_id==member.actor_id and p.intent.reason=='bash_immediate')
            # A granted strike can genuinely draw another physical weapon even
            # under a fixed ordinary policy. Its typed equip receipt owns that
            # transition; the legacy single-backup path still requires its draw.
            if not bash_swaps and (source.combat_equipment is None or source.policy is not PcMeleePolicy.AUTOMATIC_COMBAT) and (len(draws)>1 or member.using_backup_weapon != bool(draws)
                    or member.using_backup_weapon and source.backup_weapon_policy is None):
                raise ValueError('backup activation must preserve its single actual draw receipt')
            active_weapon = pc_active_weapon(self,member.actor_id)
            allowed_grips = ((PcWeaponHand,PcTwoHandedGrip) if active_weapon in
                (PcMeleeWeapon.FOOT_SPEAR,PcMeleeWeapon.POLEARM) else
                (PcTwoHandedGrip,) if pc_weapon_requires_two_hands(active_weapon) else (PcWeaponHand,))
            if member.weapon_hand is not None and type(member.weapon_hand) not in allowed_grips:
                raise ValueError('held weapon grip must preserve its one/two-handed source')
            expected_fate = source.fate
            for proof in self.history:
                glorious = (proof.glorious if isinstance(proof,(PcMedicalTreatmentProof,PcMedicalSuppressionProof,PcMedicalSurgeryProof,PcMusicianActionProof,PcAttackProof,PcDemigryphStrikeProof,PcImmediateStrikeProof,PcFallingProof,PcWeaponHazardProof,PcExtinguishProof,PcTerrainTraversalProof,PcHammerRetrievalProof,PcEnduranceProof,PcHelpProof,PcRangedReloadProof,PcAimProof,PcCastingProof,PcBattlefieldChargeProof,PcBattlefieldRunProof,PcNetReleaseProof,PcBriarrootReleaseProof)) else
                    proof.critical.glorious if isinstance(proof,(PcTurnEndProof,PcIncapacitatedTurnEndProof))
                    and proof.critical is not None else None)
                if glorious is not None and glorious.previous_state.actor_id == member.actor_id:
                    if glorious.previous_state != expected_fate:
                        raise ValueError('PC Fate spends must extend the actual resource history')
                    expected_fate = glorious.state
                if type(proof) is PcAimSecondActionProof and proof.result.previous_state.actor_id == member.actor_id:
                    if proof.result.previous_state != expected_fate:
                        raise ValueError('second action must extend its actual PC Fate resource history')
                    expected_fate = proof.result.state
                if isinstance(proof, PcWoundCompletionProof) and proof.completion.fate_burn is not None:
                    burn = proof.completion.fate_burn
                    if burn.previous_state.actor_id == member.actor_id:
                        if burn.previous_state != expected_fate:
                            raise ValueError('PC Fate burns must extend the actual resource history')
                        expected_fate = burn.state
                if self.oaths:
                    from towr.domain.pc_oath_models import honour_fate_after_proof
                    expected_fate = honour_fate_after_proof(self, member.actor_id, expected_fate, proof)
            if member.fate != expected_fate or member.daily_wounds.day_id != self.source.day_id:
                raise ValueError('PC owner cannot replace Fate or daily source')
        if (not all(isinstance(e, NpcParticipantSnapshot) for e in self.enemies)
                or tuple(e.state.actor_id for e in self.enemies) != tuple(e.state.actor_id for e in self.source.npc_sources)
                or any(e.definition != old.definition for e, old in zip(self.enemies, self.source.npc_sources))):
            raise ValueError('PC owner must preserve its exact ordered Minion definitions')
        validate_pc_minion_defeat_equipment(self)
        if self.pending_wound is not None and not isinstance(self.pending_wound, CharacterWoundLifecycleRollResult):
            raise TypeError('pending PC Wound must retain its lifecycle roll')
        has_pending = bool(self.pending) or self.pending_wound is not None
        if has_pending:
            if type(self.pending_actor_id) is not str:
                raise ValueError('mandatory queue must retain its exact target owner')
            if self.pending_actor_id not in self.source.pc_activation_order:
                wave = current_warped_form(self)
                target = next((p for p in reversed(self.history) if type(p) is PcWarpedFormTargetProof), None)
                from towr.domain.pc_actor_models import pc_companion
                warped = not (wave is None or target is None or target.activation_id != wave.activation_id
                        or target.request.target_id != self.pending_actor_id
                        or (self.pending_actor_id not in self.source.npc_activation_order
                            and pc_companion(self,self.pending_actor_id) is None)
                        or self.pending_wound is not None
                        or self.pending != target.result.follow_ups)
                from towr.domain.pc_companion_attack_models import companion_attack_pending_owner
                if (not warped and npc_champion_pending_owner(self) is None and pc_blunderbuss_pending_npc_target(self) is None
                        and cleaving_pending_npc_target(self) is None
                        and companion_attack_pending_owner(self) != self.pending_actor_id):
                    from towr.domain.pc_give_ground_models import pc_give_ground_pending_actor
                    from towr.domain.pc_brawn_displacement_models import brawn_displacement_pending_actor
                    if (pc_give_ground_pending_actor(self)!=self.pending_actor_id
                            and brawn_displacement_pending_actor(self)!=self.pending_actor_id):
                        raise ValueError('NPC pending owner requires its actual wave or Give Ground queue')
            if self.pending_wound is not None and self.pending_wound.source_request.target_id != self.pending_actor_id:
                raise ValueError('pending Wound belongs to another PC')
        elif self.pending_actor_id is not None:
            raise ValueError('a completed queue cannot retain a pending PC owner')
        validate_pc_npc_distractions(self)
        validate_pc_flagellant_conditions(self)
        validate_pc_npc_ranged_weapons(self)
        validate_pc_blunderbuss_history(self)
        validate_pc_aim_history(self)
        validate_pc_npc_aim_history(self)
        validate_cleaving_history(self)
        for member in self.party:
            validate_pc_weapon_inventory(member,self.source.participant(member.actor_id))

    def participant(self, actor_id: str) -> PcMeleeParticipantState:
        for member in self.party:
            if member.actor_id == actor_id:
                return member
        raise ValueError('unknown PC melee participant')

    def enemy(self, actor_id: str) -> NpcParticipantSnapshot:
        return next(e for e in self.enemies if e.state.actor_id == actor_id)

    @property
    def live_party(self) -> tuple[PcMeleeParticipantState, ...]:
        return tuple(m for m in self.party if not m.injury.dead)

    @property
    def live_enemies(self) -> tuple[NpcParticipantSnapshot, ...]:
        exited = self.exited_npc_ids
        return tuple(e for e in self.enemies if e.state.side is CombatSide.OPPOSITION
            and not injury_is_defeated(e.state.injury) and e.state.actor_id not in exited)

    @property
    def exited_npc_ids(self) -> tuple[str, ...]:
        if self.source.npc_broken_exit_policy is None:
            return ()
        observed = {proof.request.actor_id for proof in self.history if type(proof) is PcNpcExitProof}
        return tuple(enemy.state.actor_id for enemy in self.source.npc_sources if enemy.state.actor_id in observed)


def pc_melee_round_participants(state: PcMeleeState) -> tuple[CombatTurnParticipant, ...]:
    from towr.domain.pc_actor_models import pc_active_actor_ids, pc_actor_side
    return tuple(CombatTurnParticipant(actor, pc_actor_side(state, actor))
        for actor in pc_active_actor_ids(state))


def initial_pc_melee_state(source: PcMeleeScenario) -> PcMeleeState:
    from towr.domain.pc_mount_companion_owner import initial_pc_companions
    validate_pc_melee_scenario_admission(source)
    participants = (*(CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES) for actor in source.player_activation_order),
        *(CombatTurnParticipant(actor, CombatSide.OPPOSITION) for actor in source.enemy_activation_order))
    from towr.domain.pc_armour_models import initial_pc_armour_injury
    from towr.domain.pc_inventory_conditions import initial_pc_inventory_injury
    party = tuple(PcMeleeParticipantState(member.actor_id, initial_pc_inventory_injury(member,initial_pc_weapon_inventory(member),
        initial_pc_armour_injury(member)), initial_pc_weapon_inventory(member),
        member.fate, DailyWoundState(source.day_id, member.actor_id),shield=initial_pc_shield(member.shield),
        potions=member.consumables, tool_inventory=initial_tool_inventory(member.actor_id,member.pc.tools),
        magic=WizardMagicState() if member.wizard is not None else None) for member in source.party)
    return PcMeleeState(source, CombatRoundState(1, participants), party, initial_pc_npc_weapon_inventories(source),
        oaths=initial_pc_oaths(source),
        mounts=initial_pc_mounts(source),
        companions=initial_pc_companions(source),
        weighted_nets=initial_weighted_nets(source),
        npc_shields=initial_npc_shields(source),
        npc_champions=initial_npc_champions(source),
        battlefield=(build_pc_battlefield(source.battlefield, source.player_activation_order,
            source.enemy_activation_order, source.facts.zone_id) if source.battlefield is not None else None))


@dataclass(frozen=True, slots=True)
class PcAttackProof:
    request: AttackActionExecutionRequest
    protection: ProtectionPreparationResult
    execution: AttackActionExecutionResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None
    help_applications: tuple[HelpBonusApplicationResult, ...] = ()
    npc_help_applications: tuple[AutomaticHelpBonusApplicationResult, ...] = ()
    npc_glorious_source: PcBestigorGloriousSource | PcBestigorWaveGloriousSource | None = None
    ranged_shot: PcRangedShotProof | None = field(default=None,kw_only=True)
    npc_ranged_shot: PcNpcRangedShotProof | None = field(default=None,kw_only=True)
    weighted_net_landing: PcNetThrowLanding | None = field(default=None,kw_only=True)
    nearby_snapshot: PcBlunderbussSnapshot | None = field(default=None,kw_only=True)
    mount_attack: PcMountedAttackIntent | None = field(default=None,kw_only=True)
    weapon_intent: PcAttackWeaponIntent = field(kw_only=True)
    throwing_inventory: PcThrowingInventoryReceipt | None = field(default=None,kw_only=True)
    weapon_area: PcWeaponAreaSnapshot | None = field(default=None,kw_only=True)
    magic_weapon: PcMagicWeaponAttackReceipt | None = field(default=None,kw_only=True)
    armour_bane: ArmourBaneApplication | None = field(default=None,kw_only=True)


@dataclass(frozen=True, slots=True)
class PcNpcHelpProof:
    request: AutomaticHelpActionRequest
    execution: AutomaticHelpActionResult


@dataclass(frozen=True, slots=True)
class PcHelpProof:
    request: HelpActionExecutionRequest
    execution: HelpActionExecutionResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None
    beneficiary_weapon_item_id: str | None = field(default=None,kw_only=True)
    ranged_use: PcRangedHelpUseProof | None = field(default=None,kw_only=True)
    weapon_use: WeaponUse | WeaponProtectionUse | None = field(kw_only=True)
    allies_in_arms: AlliesInArmsApplication | None = field(default=None,kw_only=True)


@dataclass(frozen=True, slots=True)
class PcWoundCompletionProof:
    completion: CharacterWoundLifecycleCompletionResult
    fate_decline: PcFateDecline | None


@dataclass(frozen=True, slots=True)
class PcEnduranceProof:
    request: WoundEnduranceTestRequest
    test_request: TestRequest
    test: TestResult
    result: WoundEnduranceTestResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None


@dataclass(frozen=True, slots=True)
class PcHandDropProof:
    source: WoundConsequenceRequest
    die: int
    hand: PcWeaponHand
    weighted_net_drops: tuple[PcNetDrop, ...] = field(default=(),kw_only=True)
    tool_drops: tuple[ToolInventoryTransition, ...] = field(default=(),kw_only=True)
    npc_shield_drop: NpcChampionShieldDrop | None = field(default=None,kw_only=True)


@dataclass(frozen=True, slots=True)
class PcBodyConsequenceProof:
    source: WoundConsequenceRequest
    die: int | None
    side: PcWeaponHand | None
    count: int = 1
    weighted_net_drops: tuple[PcNetDrop, ...] = field(default=(),kw_only=True)
    tool_drops: tuple[ToolInventoryTransition, ...] = field(default=(),kw_only=True)
    npc_shield_drop: NpcChampionShieldDrop | None = field(default=None,kw_only=True)


@dataclass(frozen=True, slots=True)
class PcWoundChoiceProof:
    result: WoundChoiceResult


@dataclass(frozen=True, slots=True)
class PcHandSwapProof:
    previous_hand: PcWeaponHand | PcTwoHandedGrip
    hand: PcWeaponHand | PcTwoHandedGrip


@dataclass(frozen=True, slots=True)
class PcBackupWeaponDrawProof:
    actor_id: str
    previous_hand: PcWeaponHand | PcTwoHandedGrip | None
    hand: PcWeaponHand

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('backup draw requires its actual actor ID')
        if self.previous_hand is not None and type(self.previous_hand) not in (PcTwoHandedGrip,PcWeaponHand):
            raise TypeError('backup draw must abandon its actual primary grip')
        if type(self.hand) is not PcWeaponHand:
            raise TypeError('backup draw requires one actual typed hand')


@dataclass(frozen=True, slots=True)
class PcCriticalProof:
    test_request: TestRequest
    result: CriticalInjuryTestResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None


@dataclass(frozen=True, slots=True)
class PcIncapacitatedTurnEndProof:
    result: CombatTurnEndResult
    critical: PcCriticalProof | None


@dataclass(frozen=True, slots=True)
class PcAttackerStaggerProof:
    source: AttackerStaggerRequest


@dataclass(frozen=True, slots=True)
class PcProfileWoundProof:
    source: ProfileStateChangeRequest
    decision: MinionDefeatDecision | None


@dataclass(frozen=True, slots=True)
class PcMinionStaggerDefeatProof:
    source: MinionStaggerDefeatCause
    weighted_net_drops: tuple[PcNetDrop, ...] = field(default=(),kw_only=True)


@dataclass(frozen=True, slots=True)
class PcRecoverProof:
    result: RecoverActionExecutionResult
    briarroot_weapon_pickup: PcBriarrootWeaponPickup | None = field(default=None,kw_only=True)
    pc_shield_pickup: PcShieldPickup | None = field(default=None,kw_only=True)


@dataclass(frozen=True, slots=True)
class PcTurnEndProof:
    result: CombatTurnEndResult
    fate_decline: PcFateDecline | None
    critical: PcCriticalProof | None = None


from towr.domain.pc_medical_models import (PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,
    PcMedicalSuppressionProof,PcMedicalSurgeryProof,PcMedicalRiskProof,pending_medical_work)
from towr.domain.pc_medical_tactics import PcMedicalIntentProof
from towr.domain.pc_medical_equipment_models import PcMedicalEquipmentProof,PcMedicalToolRecoverProof

PcMeleeProof = (
    PcMedicalIntentProof | PcMedicalEquipmentProof | PcMedicalToolRecoverProof |
    PcMedicalTreatmentProof | PcMedicalTreatmentApplicationProof | PcMedicalSuppressionProof | PcMedicalSurgeryProof | PcMedicalRiskProof |
    PcScarabChargeProof | PcScarabHealingProof | PcTerrainTraversalProof | PcHammerRetrievalProof | PcGiveGroundProof | PcAfterGiveGroundProof | PcBrokenMoveProof | PcBrokenRunProof | PcBrokenBlockedProof | PcBrawnShoveProof |
    PcWeaponAreaConditionProof | PcWeaponAreaEndProof | PcWeaponHazardProof | PcWeaponHazardCompletionProof | PcExtinguishProof |
    CombatTurnStartResult | CombatActionSlotResult | PcAttackProof | PcDemigryphIntentProof | PcDemigryphStrikeProof | PcBashDecisionProof | PcImmediateStrikeProof | PcFallingProof | PcFallingAcknowledgementProof | PcWoundCompletionProof | PcNpcBloodRageProof
    | PcNpcRecoverProof | PcFlagellantMissWoundProof | PcWildAttackProof | PcDefensiveStanceProof
    | PcCleavingStartProof | PcCleavingTargetProof | PcCleavingProfileProof
    | PcCleavingMinionDefeatProof | PcCleavingEndProof
    | PcWarpedFormActivationProof | PcWarpedFormTargetProof | PcWarpedFormProfileProof
    | PcWarpedFormMinionDefeatProof | PcWarpedFormEndProof
    | PcEnduranceProof | PcHandDropProof | PcAttackerStaggerProof | PcProfileWoundProof
    | PcRecoverProof | PcPotionRecoverProof | PcCastingProof | PcMagicInterruptionProof | PcMiscastRollProof | PcWeaponSwapProof | PcNpcWeaponEquipProof
    | PcMagicEffectProof | PcMagicCleanupProof | PcMusicianActionProof | PcMusicianSignalProof | PcMusicianIntentProof | PcMusicianEquipmentProof | PcMusicianRecoverProof
    | PcTurnEndProof | PcIncapacitatedTurnEndProof | PcBodyConsequenceProof | PcMinionStaggerDefeatProof | PcNpcHelpProof
    | PcWoundChoiceProof | PcHandSwapProof | PcBackupWeaponDrawProof | PcHelpProof | PcNpcExitProof | CombatRoundAdvanceResult
    | PcNpcDistractionExpiredProof
    | PcAimProof | PcAimSecondActionProof | PcAimConsumptionProof
    | PcNpcAimProof | PcNpcAimConsumptionProof
    | PcBlunderbussNearbyProof | PcNpcGrudgeEncounterProof | PcNpcNetDrawProof | PcShieldReleaseProof | PcRangedReloadProof | PcNpcRangedReloadProof | PcNpcApproachProof
    | PcNpcShieldDropProof | PcNpcShieldRecoverProof | PcBriarrootProof | PcBriarrootReleaseProof
    | PcShieldDropProof | PcShieldApproachProof
    | PcBriarrootWeaponDropProof | PcBriarrootWeaponPickupProof | PcBriarrootWeaponApproachProof
    | PcBattlefieldMoveProof | PcBattlefieldRecoverProof | PcNpcChampionRecoverProof
    | PcBattlefieldChargeProof | PcBattlefieldRunProof | PcBattlefieldCarefulProof
    | PcBlunderbussTargetProof | PcBlunderbussProfileProof | PcBlunderbussEndProof | PcBlunderbussMinionDefeatProof
    | PcDismountProof | PcMountRetentionProof | PcCompanionWaitProof | PcCompanionDepartureProof | PcCompanionLandingProof | PcBackInSaddleMoveProof | PcBackInSaddleRecoverProof
    | PcNetReleaseProof | PcNetPickupProof | PcNetApproachProof | PcNetIncidentalPickupProof | PcLadyPrayerProof | PcOathNegationAckProof
)


@dataclass(frozen=True, slots=True)
class PcMeleeStep:
    source: PcMeleeState
    proof: PcMeleeProof
    state: PcMeleeState = field(init=False)

    def __post_init__(self):
        if not isinstance(self.source, PcMeleeState):
            raise TypeError('PC transition requires its complete source owner')
        object.__setattr__(self, 'state', project_pc_melee_step(self.source, self.proof))


@dataclass(frozen=True, slots=True)
class PcMeleeScenarioResult:
    source: PcMeleeScenario
    steps: tuple[PcMeleeStep, ...]
    outcome: PcMeleeOutcome
    unsupported: PcMeleeUnsupported | PcNpcBrokenTurnUnsupported | PcNpcBrokenWaveTurnUnsupported | PcRangedCloseUnsupported | None = None

    def __post_init__(self):
        validate_pc_melee_scenario_admission(self.source)
        if not isinstance(self.outcome, PcMeleeOutcome) or not isinstance(self.steps, (tuple, list)):
            raise TypeError('PC result needs typed outcome and ordered steps')
        if self.unsupported is not None:
            if not isinstance(self.unsupported,(PcMeleeUnsupported,PcNpcBrokenTurnUnsupported,PcNpcBrokenWaveTurnUnsupported,PcRangedCloseUnsupported,PcMagicUnsupported)):
                raise TypeError('PC unsupported result must be typed')
            replace(self.unsupported)
        steps = tuple(self.steps)
        current = initial_pc_melee_state(self.source)
        for step in steps:
            if not isinstance(step, PcMeleeStep):
                raise TypeError('PC journal requires typed steps')
            validate_pc_melee_state_shape(step.source)
            if step.source != current:
                raise ValueError('PC journal is detached, reordered or has a missing prefix')
            validate_pc_melee_source_types(step.source,current)
            actual = project_pc_melee_step(current, step.proof)
            validate_pc_melee_state_shape(step.state)
            if actual != step.state:
                raise ValueError('PC journal has a forged transition result')
            validate_pc_melee_source_types(step.state,actual)
            current = actual
        if not steps:
            raise ValueError('PC encounter cannot finish without an executed action')
        actual_stop = pc_melee_unsupported(current)
        from towr.domain.pc_companion_departure_models import expected_companion_departure
        if expected_companion_departure(current) is not None:
            raise ValueError('terminal result skipped its confirmed rider-source companion departure')
        from towr.domain.pc_companion_landing_models import expected_companion_landing
        if expected_companion_landing(current) is not None:
            raise ValueError('terminal result skipped its source-bound wounded Pegasus landing')
        from towr.domain.pc_magic_weapon_models import expected_scarab_charge
        if expected_scarab_charge(current) is not None:
            raise ValueError('terminal result skipped its actual Scarab Wound resource completion')
        if expected_pc_terrain_traversal(current) is not None:
            raise ValueError('terminal result skipped its actual Difficult Terrain crossing Test')
        if expected_pc_broken_battlefield_step(current) is not None:
            raise ValueError('terminal result skipped its actual mandatory Broken movement')
        if actual_stop is None and (current.magic_pending is not None or expected_magic_interruption(current) is not None):
            raise ValueError('terminal result skipped mandatory magic or Casting interruption')
        if actual_stop is None and current_pc_blunderbuss_wave(current) is not None:
            raise ValueError('terminal result skipped its actual nearby targets or consequences')
        if actual_stop is None and (current_cleaving_wave(current) is not None or expected_cleaving_start(current) is not None):
            raise ValueError('terminal result skipped an actual Cleaving Blow weapon Wound or wave')
        if current_weapon_area(current) is not None or weapon_hazard_completion(current) is not None or expected_ablaze_hazard(current) is not None:
            raise ValueError('terminal result skipped its actual weapon area or Ablaze end phase')
        if actual_stop is None and (current_warped_form(current) is not None
                or expected_pc_warped_form_activation(current) is not None):
            raise ValueError('terminal result skipped its Warped Form end phase')
        if (actual_stop is None and current.round_state.active_turn is not None
                and current.round_state.active_turn.actor_id in {p.actor_id for p in self.source.npc_warped_form_policies}
                and current.round_state.active_turn.action_slots
                and all(s.executed for s in current.round_state.active_turn.action_slots)):
            raise ValueError('terminal result skipped Skin Wolf TurnEnd')
        if expected_pc_aim_consumption(current) is not None:
            raise ValueError('terminal result skipped actual Aim consumption')
        if expected_npc_aim_consumption(current) is not None:
            raise ValueError('terminal result skipped actual NPC Aim consumption')
        if pending_medical_work(current) is not None:
            raise ValueError('terminal result skipped actual treatment, surgeon Recall or surgical risk')
        from towr.domain.pc_briarroot_weapon_models import expected_briarroot_weapon_loss
        if expected_briarroot_weapon_loss(current) is not None:
            raise ValueError('terminal result skipped actual physical Wound weapon loss')
        if expected_pc_dismount(current) is not None:
            raise ValueError('terminal result skipped the actual forced dismount')
        if (expected_pc_falling_request(current) is not None
                or falling_acknowledgement_source(current) is not None):
            raise ValueError('terminal result skipped actual falling or its completed Wound acknowledgement')
        from towr.domain.pc_demigryph_models import build_pc_demigryph_strike
        if actual_stop is None and build_pc_demigryph_strike(current) is not None:
            raise ValueError('terminal result skipped the committed same-action Demigryph strike')
        if expected_pc_npc_grudge_encounter(current) is not None:
            raise ValueError('PC result skipped its initial grudge encounters')
        if expected_pc_npc_blood_rage(current) is not None:
            raise ValueError('PC result skipped its selected pre-Attack Blood Rage')
        from towr.domain.pc_weapon_inventory import pending_pc_weapon_swap
        if (expected_wild_attack(current) is not None or pending_wild_attack(current) is not None
                or pending_pc_weapon_swap(current) is not None):
            raise ValueError('terminal result skipped the selected Wild Attack price or next Melee Test')
        if actual_stop is None and expected_pc_npc_distraction_expiry(current) is not None:
            raise ValueError('PC result skipped mandatory focus-death distraction expiry')
        if self.unsupported != actual_stop:
            raise ValueError('PC unsupported result must preserve its actual pending source')
        active = current.round_state.active_turn
        if (actual_stop is None and active is not None and active.actor_id in self.source.pc_activation_order
                and current.participant(active.actor_id).injury.dead):
            raise ValueError('terminal result skipped the active dead PC real turn end phase')
        if (actual_stop is None and active is not None and active.actor_id in self.source.npc_activation_order
                and current.enemy(active.actor_id).definition.id=='pc-book-npc:great_stag'
                and active.action_slots and all(slot.executed for slot in active.action_slots)):
            raise ValueError('terminal result skipped the Great Stag completed turn or Crown opportunity')
        if (actual_stop is None and active is not None and active.actor_id in self.source.pc_activation_order
                and current.participant(active.actor_id).injury.conditions.has(Condition.CRITICALLY_INJURED)
                and active.action_slots and active.action_slots[0].executed):
            raise ValueError('terminal result skipped the active PC mandatory Critical end phase')
        expected = (PcMeleeOutcome.UNSUPPORTED_PATH if actual_stop else
            PcMeleeOutcome.PARTY_DEFEATED if not current.live_party else
            PcMeleeOutcome.OBJECTIVE_ACHIEVED if not current.live_enemies else
            PcMeleeOutcome.ROUND_LIMIT if current.round_state.round_complete
                and current.round_state.round_number == self.source.max_rounds else None)
        if (current.pending_wound is not None and actual_stop is None) or (current.pending and actual_stop is None) or self.outcome is not expected:
            raise ValueError('PC outcome skipped mandatory work or misclassified the battle')
        object.__setattr__(self, 'steps', steps)

    @property
    def state(self) -> PcMeleeState:
        return self.steps[-1].state

    @property
    def defeated_pc_ids(self) -> tuple[str, ...]:
        pending_actor = self.state.pending_actor_id if self.state.pending_wound is not None else None
        return tuple(member.actor_id for member in self.state.party
            if member.injury.dead and member.actor_id != pending_actor)

    @property
    def exited_npc_ids(self) -> tuple[str, ...]:
        return self.state.exited_npc_ids

    @property
    def executed_actions(self) -> int:
        return sum(isinstance(step.proof, (PcMedicalTreatmentProof,PcMedicalSurgeryProof,PcMedicalToolRecoverProof,PcLadyPrayerProof, PcMusicianActionProof, PcMusicianRecoverProof, PcAimProof, PcNpcAimProof, PcAttackProof, PcCastingProof, PcRecoverProof, PcExtinguishProof, PcPotionRecoverProof, PcScarabHealingProof, PcHammerRetrievalProof, PcHelpProof, PcNpcHelpProof, PcNpcRecoverProof, PcRangedReloadProof, PcNpcRangedReloadProof, PcBattlefieldRecoverProof,PcNpcChampionRecoverProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof,PcBrokenRunProof,PcNetReleaseProof,PcNetPickupProof,PcNpcShieldRecoverProof,PcBriarrootReleaseProof,PcBriarrootWeaponPickupProof))
            or type(step.proof) is PcBattlefieldChargeProof and not step.proof.result.attack_allowed
            for step in self.steps)

    @property
    def started_rounds(self) -> int:
        return self.state.round_state.round_number

    @property
    def completed_rounds(self) -> int:
        return self.started_rounds - 1 + int(self.state.round_state.round_complete)

    @property
    def tactical_decisions(self):
        """Explain automatic choices from their exact pre-reservation snapshots."""
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.pc_tactical_models import select_pc_tactic
        from towr.domain.turn_models import CombatActionSlotResult
        return tuple(select_pc_tactic(step.source) for step in self.steps
            if isinstance(step.proof, CombatActionSlotResult)
            and step.source.round_state.active_turn.actor_id in self.source.pc_activation_order
            and self.source.participant(step.source.round_state.active_turn.actor_id).policy
                is PcMeleePolicy.AUTOMATIC_COMBAT)


def _pc_wound_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | None:
    # Finish the entire actual Wound lifecycle and immediate consequence queue
    # before reporting the caller-selected boundary; never infer this from a roll.
    if not state.pending and state.pending_wound is None:
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        for member, source in zip(state.party,state.source.party):
            from towr.domain.pc_melee_models import PC_TWO_HANDED_RANGED_WEAPONS
            if source.pc.weapon in PC_TWO_HANDED_RANGED_WEAPONS:
                continue  # Two-handed ranged grip stops belong to its actual next own Shoot/draw boundary.
            if (member.injury.dead or member.using_backup_weapon
                    or not pc_weapon_requires_two_hands(source.pc.weapon) or len(usable_hands(member)) == 2):
                continue
            if source.backup_weapon_policy is not None and len(usable_hands(member)) == 1:
                continue
            if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
                # Keep the actual body/equipment state. The automatic selector
                # chooses standard Recover when this melee grip is unusable;
                # it grants no hand, pickup or healing, and still owes the
                # ordinary action and mandatory end-phase consequences.
                continue
            if source.wizard is not None:
                from towr.domain.pc_magic_models import magic_hand
                if magic_hand(state,member.actor_id) is not None:
                    continue  # A one-hand Casting action does not need its primary weapon grip.
            turn = state.round_state.active_turn
            if (turn is not None and turn.actor_id == member.actor_id
                    and turn.action_slots and all(slot.executed for slot in turn.action_slots)
                    and any(type(proof) is PcPotionRecoverProof and proof.actor_id == member.actor_id
                        and proof.result.round_state.round_number == state.round_state.round_number
                        for proof in reversed(state.history))):
                # An actual potion action still owes its mandatory Critical
                # end phase, even if it healed a different Wound and grip is
                # still unavailable. Report that boundary after TurnEnd.
                continue
            # Keep the native prefix alive until its own healing Recover. The
            # potion must be physically usable; absent stock/hands keeps the
            # previous precise unsupported boundary.
            from towr.domain.pc_potion_models import potion_options
            if any(option.wound_sequence is not None for option in potion_options(member)):
                continue
            facts = tuple(f for f in member.body_facts if f.kind in (
                PcBodyFactKind.UNUSABLE_ARM,PcBodyFactKind.LOST_ARM,PcBodyFactKind.CLUTCH_STOMACH))
            fact = max(facts,key=lambda f:f.wound_sequence) if source.backup_weapon_policy is not None else facts[0]
            wound = member.injury.wounds[fact.wound_sequence-1]
            return PcMeleeUnsupported(member.actor_id,
                f'RULE-EQUIPMENT-002:{member.actor_id}:w{wound.sequence}:two-handed-grip',
                'two_handed_grip_unavailable',wound.sequence,wound.table_total)
    if not state.pending or state.pending_wound is not None:
        return None
    pending = state.pending[0]
    if not isinstance(pending,WoundConsequenceRequest):
        return None
    from towr.domain.pc_actor_models import pc_actor_character_body
    member = pc_actor_character_body(state,state.pending_actor_id)
    kinds = {WoundConsequence.RANDOMISE_SEVERED_ARM:(PcBodyFactKind.LOST_ARM,),
        WoundConsequence.RANDOMISE_SEVERED_LEG:(PcBodyFactKind.LOST_LEG,),
        WoundConsequence.LOSE_RANDOM_EYE:(PcBodyFactKind.LOST_EYE,),
        WoundConsequence.RANDOMISE_INJURED_ARM:(PcBodyFactKind.LOST_ARM,)}
    if pending.consequence is WoundConsequence.DROP_RANDOM_HAND_ITEM and member.injury.wounds[pending.wound_sequence-1].table_total == 12:
        kinds[pending.consequence] = (PcBodyFactKind.LOST_ARM,)
    if pending.consequence not in kinds or available_sides(member,kinds[pending.consequence]):
        return None
    wound = member.injury.wounds[pending.wound_sequence-1]
    return PcMeleeUnsupported(member.actor_id,
        f'{pending.rule_id}:{member.actor_id}:w{pending.wound_sequence}:{pending.consequence.value}',
        'unavailable_anatomical_target',pending.wound_sequence,wound.table_total)


def pc_melee_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | PcNpcBrokenTurnUnsupported | PcNpcBrokenWaveTurnUnsupported | PcRangedCloseUnsupported | None:
    magic_stop = pc_magic_unsupported(state)
    wound_stop = _pc_wound_unsupported(state)
    if magic_stop is not None:
        return magic_stop
    if wound_stop is not None and wound_stop.reason == 'unavailable_anatomical_target':
        return wound_stop
    if state.magic_pending is not None or expected_magic_interruption(state) is not None:
        return None
    return wound_stop or pc_npc_broken_turn_unsupported(state) or pc_ranged_unsupported(state)


def pc_melee_action_id(state: PcMeleeState, actor_id: str,*,round_number=None) -> str:
    number=state.round_state.round_number if round_number is None else round_number
    if type(number) is not int or number<1:
        raise ValueError('an upcoming action needs its exact positive round number')
    return f'{state.source.id}:r{number}:{actor_id}'


def pc_melee_net_recovery(state):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    turn=state.round_state.active_turn
    if turn is None:
        return None
    actor=turn.actor_id
    if actor in state.source.npc_activation_order:
        return selected_weighted_net_recovery(state,actor)
    if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
        return None
    from towr.domain.pc_tactical_models import select_pc_tactic
    choice=select_pc_tactic(state,actor)
    if choice.net_item_id is None:
        return None
    return next((option for option in weighted_net_recovery_options(state,actor)
        if option.item_id==choice.net_item_id and option.target_id==choice.net_release_target_id),None)


def pc_melee_briarroot_recovery(state):
    """Break a selected restraint when the held ranged weapon needs separation."""
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    from towr.domain.pc_musician_tactics import committed_musician_intent
    if committed_musician_intent(state) is not None:
        return None
    turn=state.round_state.active_turn
    if turn is None or turn.action_slots and turn.action_slots[-1].executed:
        return None
    actor=turn.actor_id
    from towr.domain.pc_briarroot_models import briarroot_recovery_options
    options=briarroot_recovery_options(state,actor)
    own=next((item for item in state.briarroot_bindings if item.attacker_id==actor and item.id in options),None)
    if own is None:
        return None
    brawn=(state.source.participant(actor).pc.brawn if actor in state.source.pc_activation_order else
        getattr(state.enemy(actor).definition.generated_components,'brawn',None))
    if brawn is None:
        return None
    from towr.domain.pc_battlefield_movement_models import _ranges
    return own if _ranges(state,actor)[0] is not RangedWeaponRange.CLOSE else None


def pc_melee_briarroot_weapon_drop(state):
    """Abandon one held restraint when separation is needed and Brawn is absent."""
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    turn=state.round_state.active_turn
    if turn is None or turn.action_slots:
        return None
    actor=turn.actor_id
    from towr.domain.pc_briarroot_models import BriarrootWeaponKind
    binding=next((item for item in state.briarroot_bindings if item.attacker_id==actor
        and item.kind is BriarrootWeaponKind.HELD),None)
    if binding is None:
        return None
    from towr.domain.pc_battlefield_movement_models import _ranges
    if _ranges(state,actor)[0] is RangedWeaponRange.CLOSE:
        return None
    brawn=(state.source.participant(actor).pc.brawn if actor in state.source.pc_activation_order else
        getattr(state.enemy(actor).definition.generated_components,'brawn',None))
    if brawn is not None:
        return None
    injury=(state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)
    if injury.conditions.has(Condition.DEFENCELESS) or injury_is_defeated(injury):
        return None
    return build_briarroot_weapon_drop(state,actor,binding.weapon_id)


def pc_melee_briarroot_weapon_recovery(state):
    """Only a recoverable actual owned ground item can drive pickup positioning."""
    from towr.domain.pc_musician_tactics import committed_musician_intent
    if committed_musician_intent(state) is not None:
        return None
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    turn=state.round_state.active_turn
    if turn is None or turn.action_slots and turn.action_slots[-1].executed:
        return None
    actor=turn.actor_id
    if actor in state.source.pc_activation_order:
        member=state.participant(actor)
        if (state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT
                or member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)
                or usable_weapon_hand(member) is not None or pc_preferred_weapon_hand(state,actor) is None):
            return None
        return briarroot_weapon_on_ground(state,actor,pc_active_weapon_item_id(state,actor))
    enemy=state.enemy(actor)
    if enemy.state.wields_weapon or injury_is_defeated(enemy.state.injury) or enemy.state.injury.conditions.has(Condition.DEFENCELESS):
        return None
    return briarroot_weapon_on_ground(state,actor)


def pc_melee_selected_action(state: PcMeleeState) -> CombatActionKind:
    from towr.domain.pc_broken_battlefield_models import pc_broken_run_selected,pc_broken_standard_recover_selected
    if pc_broken_run_selected(state):
        return CombatActionKind.MANOEUVRE
    if pc_broken_standard_recover_selected(state):
        return CombatActionKind.RECOVER
    from towr.domain.pc_actor_models import pc_companion
    if (state.round_state.active_turn is not None
            and pc_companion(state, state.round_state.active_turn.actor_id) is not None):
        return CombatActionKind.RECOVER
    if lady_prayer_selected(state):
        return CombatActionKind.IMPROVISE
    from towr.domain.pc_medical_tactics import current_medical_choice,MedicalActionKind
    medical=current_medical_choice(state)
    if medical is not None:
        return (CombatActionKind.IMPROVISE if medical.kind is MedicalActionKind.SURGERY
            and not medical.pickup_tool else CombatActionKind.RECOVER)
    from towr.domain.pc_musician_tactics import committed_musician_intent
    committed_music=committed_musician_intent(state)
    if committed_music is not None:
        return committed_music.choice.action
    from towr.domain.pc_magic_weapon_models import pc_hammer_retrieval_selected
    if pc_hammer_retrieval_selected(state):
        return CombatActionKind.RECOVER
    if pc_melee_briarroot_recovery(state) is not None or pc_melee_briarroot_weapon_recovery(state) is not None:
        return CombatActionKind.RECOVER
    turn = state.round_state.active_turn
    actor_id = turn.actor_id
    if turn.action_slots and not turn.action_slots[-1].executed:
        return turn.action_slots[-1].declaration.kind
    from towr.domain.pc_back_in_saddle_models import available_remount
    if available_remount(state, actor_id) is not None:
        return CombatActionKind.RECOVER
    from towr.domain.pc_musician_tactics import committed_musician_intent,npc_music_choice
    music_intent=committed_musician_intent(state,actor_id)
    if music_intent is not None:
        return music_intent.choice.action
    if actor_id in state.source.npc_activation_order:
        music=npc_music_choice(state,actor_id)
        if music is not None:
            return music.action
    if actor_id in state.source.pc_activation_order:
        member = state.participant(actor_id)
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(actor_id).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            from towr.domain.pc_tactical_models import select_pc_tactic
            return select_pc_tactic(state).action
        if _pc_recover_needed(member,unarmed_available=state.source.participant(actor_id).pc.weapon is PcMeleeWeapon.UNARMED):
            return CombatActionKind.RECOVER
        from towr.domain.pc_ally_recover_models import pc_ally_recover_beneficiary
        if pc_ally_recover_beneficiary(state) is not None:
            return CombatActionKind.RECOVER
        from towr.domain.pc_help_models import pc_help_beneficiary
        if pc_help_beneficiary(state) is not None:
            return CombatActionKind.HELP
        from towr.domain.pc_backup_weapon_models import pc_active_weapon
        from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
        if (pc_active_weapon(state,actor_id) in PC_RANGED_WEAPONS
                and type(member.ranged) is ReloadableWeaponState
                and not member.using_backup_weapon and not member.ranged.loaded):
            return CombatActionKind.IMPROVISE
        if pc_hochland_needs_aim(state,actor_id):
            return CombatActionKind.AIM
    else:
        from towr.domain.pc_scarab_recover_models import selected_scarab_healing
        if is_npc_champion(state,actor_id):
            from towr.domain.pc_npc_champion_models import npc_champion_body
            body=npc_champion_body(state,actor_id)
            if body.injury.conditions.has(Condition.PRONE) and not has_ongoing_condition(body.injury,Condition.PRONE):
                return CombatActionKind.RECOVER
            from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
            if npc_attack_weapon_use(state,actor_id) is None:
                return CombatActionKind.RECOVER
        from towr.domain.pc_oath_models import npc_oath_attack_blocked
        if npc_oath_attack_blocked(state, actor_id):
            return CombatActionKind.RECOVER
        if selected_scarab_healing(state) is not None:
            return CombatActionKind.RECOVER
        if pc_extinguish_selected(state):
            return CombatActionKind.RECOVER
        if pc_uses_mount_attack(state,actor_id):
            return CombatActionKind.ATTACK
        if build_npc_shield_pickup(state) is not None:
            return CombatActionKind.RECOVER
        if pc_flagellant_recover_selected(state, actor_id):
            return CombatActionKind.RECOVER
        recovery=pc_melee_net_recovery(state)
        if recovery is not None and not recovery.requires_approach:
            return CombatActionKind.RECOVER
        from towr.domain.pc_npc_help_models import pc_npc_help_beneficiary
        if pc_npc_help_beneficiary(state) is not None:
            return CombatActionKind.HELP
        from towr.domain.pc_npc_normal_help_models import npc_normal_help_choice
        if npc_normal_help_choice(state) is not None:
            return CombatActionKind.HELP
        if pc_battlefield_npc_recover_selected(state):
            return CombatActionKind.RECOVER
        from towr.domain.reload_models import ranged_weapon_is_loaded
        weapon = pc_npc_ranged_weapon(state,actor_id)
        if weapon is not None and not ranged_weapon_is_loaded(weapon):
            from towr.domain.pc_npc_ranged_models import npc_ranged_hands_available
            if not npc_ranged_hands_available(state,actor_id,reload=True):
                return CombatActionKind.RECOVER
            return CombatActionKind.IMPROVISE
        if npc_needs_aim(state,actor_id):
            from towr.domain.pc_npc_aim_models import npc_can_aim
            if not npc_can_aim(state,actor_id):
                return CombatActionKind.RECOVER
            return CombatActionKind.AIM
        if proposed_pc_battlefield_manoeuvre(state) is not None:
            return CombatActionKind.MANOEUVRE
    return CombatActionKind.ATTACK


def pc_melee_action_declaration(state):
    actor = state.round_state.active_turn.actor_id
    kind = pc_melee_selected_action(state)
    if lady_prayer_selected(state):
        from towr.domain.talent_lady_prayer_models import lady_prayer_declaration
        return lady_prayer_declaration()
    from towr.domain.pc_medical_tactics import current_medical_choice,MedicalActionKind
    medical=current_medical_choice(state)
    if medical is not None and medical.kind is MedicalActionKind.SURGERY and not medical.pickup_tool:
        from towr.domain.turn_models import ImproviseKind
        from towr.domain.combat_surgeon_models import COMBAT_SURGEON_RULE_ID
        return CombatActionDeclaration(kind,improvise_kind=ImproviseKind.ABILITY,
            improvise_approach_id=COMBAT_SURGEON_RULE_ID)
    if kind is CombatActionKind.MANOEUVRE:
        from towr.domain.pc_broken_battlefield_models import pc_broken_run_selected
        if pc_broken_run_selected(state):
            return CombatActionDeclaration(kind,manoeuvre=ManoeuvreKind.RUN)
        if actor in state.source.pc_activation_order:
            from towr.domain.pc_tactical_models import select_pc_tactic
            manoeuvre=select_pc_tactic(state,actor).manoeuvre
        else:
            manoeuvre=proposed_pc_battlefield_manoeuvre(state).kind
        return CombatActionDeclaration(kind,manoeuvre=manoeuvre)
    if kind is CombatActionKind.IMPROVISE:
        from towr.domain.pc_musician_tactics import current_music_choice
        music=current_music_choice(state)
        if music is not None and not music.music_pickup:
            from towr.domain.talent_battlefield_musician_models import BATTLEFIELD_MUSICIAN_RULE_ID
            from towr.domain.turn_models import ImproviseKind
            return CombatActionDeclaration(kind,improvise_kind=ImproviseKind.ABILITY,
                improvise_approach_id=BATTLEFIELD_MUSICIAN_RULE_ID)
        if pc_is_casting_action(state):
            from towr.domain.turn_models import ImproviseKind
            from towr.domain.pc_magic_source_models import ELEMENTALISM_LORE_ID
            return CombatActionDeclaration(kind,improvise_kind=ImproviseKind.SPELL,
                improvise_approach_id=ELEMENTALISM_LORE_ID)
        return (ranged_reload_declaration(state,actor) if actor in state.source.pc_activation_order
            else npc_ranged_reload_declaration(state,actor))
    return CombatActionDeclaration(kind)


def pc_is_casting_action(state):
    turn=state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.pc_activation_order:
        return False
    from towr.domain.pc_medical_tactics import current_medical_choice
    if current_medical_choice(state) is not None:
        return False
    source=state.source.participant(turn.actor_id)
    if source.wizard is None or pc_melee_selected_action(state) is not CombatActionKind.IMPROVISE:
        return False
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        from towr.domain.pc_tactical_models import select_pc_tactic
        choice=select_pc_tactic(state)
        return not choice.ranged_reload and choice.music_item_id is None
    return True


def pc_attack_skill(state,actor):
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
    use=pc_attack_weapon_use(state,actor)
    if use is not None:
        return use.skill
    weapon=pc_active_weapon(state,actor)
    from towr.domain.weapon_catalog import weapon_profile
    return weapon_profile(weapon).skill


def _pc_recover_needed(member, *, unarmed_available=False):
    return pc_shield_recover_needed(member) or (usable_weapon_hand(member) is None and not unarmed_available) or (member.injury.conditions.has(Condition.PRONE)
        and not has_ongoing_condition(member.injury,Condition.PRONE))


def pc_melee_next_actor(state: PcMeleeState) -> str:
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    from towr.domain.pc_actor_models import pc_active_actor_ids
    active = pc_active_actor_ids(state, state.round_state.next_side)
    admitted = {row.entity_id for row in state.round_state.participants}
    return next(actor for actor in active if actor in admitted and actor not in unavailable)


_SELECT_WEAPON_USE = object()


def _pc_test(state: PcMeleeState, actor_id: str, test_id: str, skill: Skill,
             dice_modifiers: tuple[DiceModifier, ...] = (), *, oppose_attack: bool = False,
             control_mount: bool = False, weapon_use=_SELECT_WEAPON_USE, incoming_attack_skill=None,
             casting: bool = False) -> TestRequest:
    from towr.domain.pc_medical_models import medical_effective_body
    member = medical_effective_body(state,actor_id)
    pc = pc_effective_definition(state, actor_id)
    if skill is Skill.WILLPOWER:
        wizard = state.source.participant(actor_id).wizard
        if wizard is None:
            raise ValueError('Willpower Casting requires its explicit Wizard facts')
        profile = state.source.participant(actor_id).willpower_profile
    elif skill is Skill.RECALL:
        profile = pc.recall_profile
    elif skill is Skill.DEXTERITY:
        profile = pc.dexterity_profile
    elif skill is Skill.LEADERSHIP:
        profile=pc.leadership_profile
    elif skill in (Skill.THROWING,Skill.BRAWN):
        profile=pc.throwing_profile if skill is Skill.THROWING else pc.brawn_profile
    elif skill is Skill.AWARENESS:
        profile = pc.awareness_profile
    elif skill is Skill.SHOOTING:
        if pc.ranged is None:
            raise ValueError('this PC has no authored Shooting/Dexterity profile')
        profile = pc.ranged.shooting_profile
    else:
        profile = {Skill.MELEE: pc.melee_profile, Skill.DEFENCE: pc.defence_profile,
            Skill.ATHLETICS: pc.athletics_profile, Skill.ENDURANCE: pc.endurance_profile}[skill]
    drained = member.injury.conditions.has(Condition.DRAINED)
    turn=state.round_state.active_turn
    charge=current_pc_charge(state,turn.actor_id) if turn is not None else None
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use,pc_protection_weapon_use
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers
    if weapon_use is _SELECT_WEAPON_USE:
        weapon_use = None
        if skill is Skill.DEFENCE or skill is Skill.MELEE and oppose_attack:
            weapon_use=pc_protection_weapon_use(member,skill,incoming_attack_skill,
                talents=state.source.participant(actor_id).talents)
        elif skill is pc_attack_skill(state,actor_id):
            weapon_use=pc_attack_weapon_use(state,actor_id)
    weapon_modifiers=(() if weapon_use is None else weapon_test_modifiers(weapon_use,
        member.injury.conditions,against_charge=charge is not None and charge.target_id==actor_id,
        actor_mounted=pc_is_mounted(state,actor_id),
        charging=charge is not None and charge.actor_id==actor_id and not oppose_attack,
        talents=state.source.participant(actor_id).talents).modifiers)
    magic_dice,magic_qualities = magic_test_modifiers(state,actor_id,skill)
    from towr.domain.pc_armour_models import actor_armour_test_modifiers,actor_armour_quality_modifiers
    modifiers = (*dice_modifiers,*weapon_modifiers,*magic_dice,
        *actor_armour_test_modifiers(state,actor_id,skill,oppose_attack=oppose_attack,control_mount=control_mount))
    if oppose_attack and turn is not None:
        from towr.domain.pc_deep_formation_models import deep_formation_modifiers
        modifiers=(*modifiers,*deep_formation_modifiers(state,actor_id,turn.actor_id,incoming_attack_skill))
    if drained:
        modifiers = tuple(m for m in modifiers if m.amount <= 0)
    qualities = list(magic_qualities)
    if skill is Skill.MELEE:
        qualities.extend(generated_attack_quality(state,actor_id))
    if skill in (Skill.MELEE,Skill.SHOOTING,Skill.THROWING,Skill.BRAWN):
        qualities.extend(actor_armour_quality_modifiers(state,actor_id,
            charge_attack=charge is not None and charge.actor_id==actor_id))
    if skill not in (Skill.ENDURANCE,Skill.WILLPOWER) and member.injury.conditions.has(Condition.BLINDED):
        qualities.append(QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    if skill is Skill.WILLPOWER:
        wizard = state.source.participant(actor_id).wizard
        equipment=state.source.participant(actor_id).armour
        from towr.domain.armour_models import armour_casting_grim
        grim=(armour_casting_grim(equipment,working_shield=pc_has_working_shield(member))
            if equipment is not None else state.source.participant(actor_id).armour_worn is True
                or pc.armour_bonus>0 or pc_has_working_shield(member))
        if grim:
            qualities.append(QualityModifier('RULE-MAGIC-004:armoured-casting',TestQuality.GRIM))
    qualities.extend(QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)
        for e in member.injury.active_wound_effects
        if isinstance(e, WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM)
    from towr.domain.pc_oath_models import filter_honour_test, prepare_pc_honour_test
    from towr.domain.weapon_catalog import WeaponKind
    from towr.domain.weapon_use_models import WeaponUse
    area_weapon = (not oppose_attack and type(weapon_use) is WeaponUse
        and weapon_use.kind in (WeaponKind.BLASTING_CHARGE, WeaponKind.OIL_FLASK, WeaponKind.BLUNDERBUSS))
    return prepare_pc_honour_test(state, actor_id,
        filter_honour_test(TestRequest(test_id, profile, modifiers, tuple(qualities))),
        rule_of_nine=casting, area_weapon=area_weapon)


def pc_after_test(state: PcMeleeState, actor_id: str, injury=None) -> CharacterInjuryState:
    injury = state.participant(actor_id).injury if injury is None else injury
    return replace(injury, active_wound_effects=tuple(e for e in injury.active_wound_effects
        if not isinstance(e, WoundRestrictionEffect) or e.restriction is not WoundRestriction.NEXT_TEST_IS_GRIM))


def pc_selected_npc_attack_profile(state,actor):
    enemy = state.enemy(actor)
    if enemy.definition.generated_components is not None:
        from towr.domain.pc_npc_weapon_inventory import npc_selected_weapon_profile
        actual=npc_selected_weapon_profile(state,actor)
        if actual is not None:return actual
    turn = state.round_state.active_turn
    crown = (turn.action_slots[-1].crown_of_antlers if turn is not None and turn.actor_id==actor
        and turn.action_slots else None)
    selected = crown.attack_id if crown is not None else selected_pc_npc_net_attack(state,actor)
    return next((profile for profile in enemy.definition.attacks if profile.id==selected),enemy.definition.attacks[0])


def pc_protection_skill(member,attack_skill,choice=None):
    if attack_skill is Skill.BRAWN:
        return Skill.ENDURANCE
    if attack_skill in (Skill.SHOOTING,Skill.THROWING) and choice is not None:
        return choice
    if attack_skill in (Skill.SHOOTING,Skill.THROWING):
        return Skill.DEFENCE if pc_has_working_shield(member) else Skill.ATHLETICS
    from towr.domain.pc_weapon_inventory import pc_protection_weapon_use
    return Skill.DEFENCE if pc_protection_weapon_use(member,Skill.DEFENCE,attack_skill) is not None else Skill.ATHLETICS


def build_pc_melee_attack(state: PcMeleeState, *, weapon_intent=None) -> tuple[AttackActionExecutionRequest, ProtectionPreparationRequest]:
    if expected_pc_npc_approach(state) is not None:
        raise ValueError('NPC must approach before its actual Melee Attack')
    if current_warped_form(state) is not None or expected_pc_warped_form_activation(state) is not None:
        raise ValueError('Warped Form end phase must finish before another Attack preparation')
    if expected_pc_npc_blood_rage(state) is not None:
        raise ValueError('Attack must follow its selected Blood Rage proof')
    if expected_wild_attack(state) is not None:
        raise ValueError('selected Wild Attack must pay Staggered before its Melee Test')
    if expected_pc_npc_net_draw(state) is not None:
        raise ValueError('Attack must follow its actual carried weapon draw')
    if expected_pc_shield_release(state) is not None:
        raise ValueError('Attack must follow its actual weapon-first shield release')
    turn = state.round_state.active_turn
    actor = turn.actor_id
    intent = build_pc_attack_weapon_intent(state) if weapon_intent is None else weapon_intent
    if type(intent) is not PcAttackWeaponIntent or intent.actor_id != actor:
        raise ValueError('Attack requires its exact actor-owned weapon intent')
    target = intent.target_id
    # Preparation can precede reservation; actual execution still requires a slot.
    charge=current_pc_charge(state,actor)
    slot_index = len(turn.action_slots) or 1
    if intent.mount_attack:
        build_pc_mounted_attack_intent(state,actor,target)
        action_id=pc_melee_action_id(state,actor)+(':attack2' if slot_index==2 else '')
        kernel,protection=prepare_pc_mounted_attack(state,actor,target,action_id,is_charge=charge is not None,
            weapon_intent=intent)
        return AttackActionExecutionRequest(action_id+':execute',state.round_state,actor,target,slot_index,
            kernel,charge_movement=charge),protection
    crown = turn.action_slots[-1].crown_of_antlers if turn.action_slots else None
    action_id = pc_melee_action_id(state, actor) + (':attack2' if slot_index == 2 else '')
    kernel,protection=prepare_pc_weapon_kernel(state,intent,action_id,charge=charge,crown=crown)
    request = AttackActionExecutionRequest(action_id + ':execute',state.round_state,actor,target,slot_index,kernel,
        charge_movement=charge)
    if actor in state.source.pc_activation_order and intent.attack_skill is Skill.SHOOTING:
        preparation = prepare_pc_ranged_shot(state,request)
        if pc_conditioned_ranged_attack(state,actor,preparation)!=request:
            raise ValueError('PC ranged preparation changed its complete canonical profile')
    elif actor in state.source.npc_activation_order and intent.attack_skill is Skill.SHOOTING:
        from towr.domain.pc_npc_ranged_models import pc_conditioned_npc_ranged_attack
        preparation = prepare_pc_npc_ranged_shot(state,request)
        # Let K1 derive the printed Damage/Aim/range/nearby/Wound traits from
        # their complete source. The Protection source must witness precisely
        # the resulting Attack too; re-preparation then checks single use.
        request = pc_conditioned_npc_ranged_attack(state,actor,preparation)
        protection = replace(protection,attack=replace(request.kernel_request.attack,
            defender_test=None))
        if pc_conditioned_npc_ranged_attack(state,actor,
                prepare_pc_npc_ranged_shot(state,request)) != request:
            raise ValueError('NPC ranged preparation changed its full canonical printed profile')
    return request, protection

def prepare_pc_weapon_kernel(state: PcMeleeState,weapon_intent,action_id: str,*,charge=None,crown=None):
    """Prepare a real physical strike without reserving/executing any action.

    Ordinary Attack supplies its actual action/Charge source. An immediate
    Talent strike supplies its own identifier and explicit physical implements.
    No clock or inventory is changed by this preparation.
    """
    if type(weapon_intent) is not PcAttackWeaponIntent:
        raise TypeError('physical strike requires its exact committed weapon intent')
    intent=weapon_intent
    replace(intent)
    actor,target=intent.actor_id,intent.target_id
    if type(action_id) is not str or not action_id.strip() or intent.action_id!=action_id:
        raise ValueError('physical strike changed its committed action identifier')
    if intent.mount_attack:
        raise ValueError('natural mount strikes use their own preparation')
    if charge is not None and charge!=current_pc_charge(state,actor):
        raise ValueError('physical strike cannot inherit a completed or foreign Charge')
    from towr.domain.pc_magic_weapon_models import actor_inventory
    for use,owner in ((intent.attack_use,actor),(intent.protection_use,target)):
        if use is not None and use.inventory!=actor_inventory(state,owner):
            raise ValueError('physical strike changed its actual Attack/Protection inventory')
    from towr.domain.pc_scene_feature_models import scene_attack_visibility
    visibility=scene_attack_visibility(state,actor,target,intent.attack_skill)
    if (intent.attack_use is not None and intent.attack_use.kind.value=='dragon_bow'
            and not visibility.visible):
        raise ValueError('Dragon Bow requires an actually visible target')
    pc_attacks = actor in state.source.pc_activation_order
    target_is_pc = target in state.source.pc_activation_order
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot, pc_actor_side
    if pc_actor_side(state, actor) is pc_actor_side(state, target):
        raise ValueError('physical Attack requires actual opposing sides')
    if ((state.battlefield is not None or intent.attack_skill is Skill.THROWING)
            and not pc_battlefield_attack_available(state, actor, target)):
        raise ValueError('Attack target is outside the actual battlefield weapon Range')
    modifiers = []
    if charge is not None:
        modifiers.extend(pc_charge_attack_modifiers(state,actor,target))
    damage_modifiers = ()
    wound_dice_modifiers = ()
    if state.source.facts.outnumbering_bonus_approved and pc_battlefield_allows_outnumbering(state,actor):
        modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1) if pc_attacks else
            pc_npc_outnumbering_modifier(state.enemy(actor).definition))
    if pc_attacks:
        pc = pc_effective_definition(state, actor)
        from towr.domain.pc_weapon_inventory import pc_weapon_target_modifiers
        weapon_use=intent.attack_use
        if weapon_use is None:
            raise ValueError("Attack requires actual held weapons and usable hands")
        weapon = weapon_use.kind
        member = state.participant(actor)
        target_snapshot = pc_actor_npc_snapshot(state, target)
        shooting = intent.attack_skill is Skill.SHOOTING
        throwing = intent.attack_skill is Skill.THROWING
        if shooting or throwing:
            modifiers = []
        if shooting:
            modifiers.extend(pc_repeater_attack_modifiers(state, actor))
            modifiers.extend(pc_ranged_profile_modifiers(state, actor, target))
            if target_snapshot.state.injury.conditions.has(Condition.PRONE):
                modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
        if (not shooting and not throwing and target_snapshot.state.injury.conditions.has(Condition.PRONE)
                and pc_npc_allows_enemy_higher_ground(target_snapshot.definition)):
            modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        modifiers.extend(pc_weapon_target_modifiers(weapon_use,target_snapshot.state.injury.conditions,
            target_mounted=pc_is_mounted(state,target)))
        if shooting or throwing:
            modifiers.extend(pc_aim_attack_modifiers(state,actor,target))
        attacker = _pc_test(state, actor, action_id + ':attack', intent.attack_skill, tuple(modifiers),weapon_use=weapon_use)
        from towr.domain.pc_help_models import build_pc_test_help
        attacker,_ = build_pc_test_help(state,actor,intent.attack_skill,attacker)
        from towr.domain.pc_generated_equipment import npc_protection_test
        protection_profile,defender = npc_protection_test(state,target,actor,
            action_id+':protection',intent.npc_protection,attack_skill=intent.attack_skill,
            weapon_use=intent.protection_use)
        skill = protection_profile.skill
        from towr.domain.pc_melee_models import PcTwoHandedGrip
        damage = (None if weapon in (PcMeleeWeapon.UNARMED,PcMeleeWeapon.WEIGHTED_NET,
            PcMeleeWeapon.ROCK,PcMeleeWeapon.OIL_FLASK,PcMeleeWeapon.BLASTING_CHARGE) else pc_weapon_damage(weapon, pc.strength,
            two_handed=weapon_use.primary is not None and weapon_use.primary.grip is WeaponGrip.BOTH))
        resilience = target_snapshot.state.current_resilience
        from towr.domain.weapon_effect_preparation import weapon_damage_preparation
        damage_modifiers = weapon_damage_preparation(weapon_use,pc.strength,resilience).modifiers
        attacker_conditions = member.injury.conditions
        target_injury = target_snapshot.state.injury
        target_armed = target_snapshot.state.wields_weapon
    else:
        enemy = state.enemy(actor)
        profile = pc_selected_npc_attack_profile(state,actor)
        if enemy.definition.generated_components is not None and intent.attack_use is not None:
            from towr.domain.generated_npc_models import generated_weapon_attack_profile,generated_unarmed_attack_profile
            use=intent.attack_use
            profile=(generated_unarmed_attack_profile(enemy.definition.generated_components)
                if use.primary is None else generated_weapon_attack_profile(enemy.definition.generated_components,
                    use.primary.source_item_id,use.primary.grip))
        from towr.domain.pc_actor_models import pc_actor_injury
        if crown is not None and (enemy.definition.id!='pc-book-npc:great_stag'
                or not pc_actor_injury(state,target).conditions.has(Condition.PRONE)
                or injury_is_defeated(pc_actor_injury(state,target))):
            raise ValueError('Trample requires the granted same living Prone target')
        member = state.participant(target) if target_is_pc else None
        target_snapshot = None if target_is_pc else pc_actor_npc_snapshot(state, target)
        target_body = member.injury if target_is_pc else target_snapshot.state.injury
        if profile.skill in (Skill.THROWING,Skill.SHOOTING):
            modifiers = []  # Ranged attacks receive no Melee/Brawn outnumbering.
        if target_body.conditions.has(Condition.PRONE):
            if profile.skill is Skill.SHOOTING:
                modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting', -1))
            elif profile.skill is not Skill.THROWING:
                modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        from towr.domain.injury_models import injury_wound_count
        modifiers.extend(pc_npc_attack_modifiers(enemy.definition,enemy.state.injury.conditions,
            target_conditions=target_body.conditions,attacker_wounds=injury_wound_count(enemy.state.injury)))
        from towr.domain.pc_generated_equipment import generated_attack_modifiers,generated_damage_modifiers
        npc_use=intent.attack_use
        if enemy.definition.generated_components is not None and npc_use is None:
            raise ValueError('generated NPC Attack requires its actual held physical implements')
        modifiers.extend(generated_attack_modifiers(enemy.definition,enemy.state.injury.conditions,
            target_body.conditions,target_mounted=pc_is_mounted(state,target),weapon_use=npc_use,
            actor_mounted=pc_is_mounted(state,actor),charging=charge is not None))
        if profile.skill is Skill.SHOOTING:
            from towr.domain.pc_npc_ranged_models import pc_npc_ranged_profile_modifiers
            modifiers.extend(pc_npc_ranged_profile_modifiers(state,actor,target))
        if profile.skill in (Skill.SHOOTING, Skill.THROWING):
            from towr.domain.pc_npc_aim_models import npc_aim_attack_modifiers
            modifiers.extend(npc_aim_attack_modifiers(state,actor,target))
        if profile.skill is Skill.MELEE:
            modifiers.extend(pc_npc_grudge_melee_modifiers(state,actor,target))
        modifiers.extend(pc_npc_distraction_test_modifiers(state,actor,target))
        if enemy.state.injury.conditions.has(Condition.DRAINED):
            modifiers = [m for m in modifiers if m.amount <= 0]
        attacker = TestRequest(action_id + ':attack', profile.test_profile,
            (*modifiers,*magic_test_modifiers(state,actor,profile.skill)[0]),
            (*pc_bestigor_attack_quality(state, actor),*generated_attack_quality(state,actor),
                *magic_test_modifiers(state,actor,profile.skill)[1]))
        from towr.domain.pc_npc_help_models import build_pc_npc_attack_help
        from towr.domain.pc_armour_models import actor_armour_quality_modifiers
        attacker=replace(attacker,quality_modifiers=(*attacker.quality_modifiers,
            *actor_armour_quality_modifiers(state,actor,charge_attack=charge is not None)))
        from towr.domain.pc_npc_champion_models import npc_champion_test_modifiers
        _,body_qualities=npc_champion_test_modifiers(state,actor,profile.skill)
        attacker=replace(attacker,quality_modifiers=tuple(dict.fromkeys((*attacker.quality_modifiers,*body_qualities))))
        if profile.skill is not Skill.THROWING:
            attacker,_ = build_pc_npc_attack_help(state,actor,attacker)
        from towr.domain.pc_help_models import build_pc_test_help
        attacker,_=build_pc_test_help(state,actor,profile.skill,attacker)
        skill = intent.protection_skill
        if target_is_pc:
            defender = None if skill is None else _pc_test(state, target, action_id + ':protection', skill,
                oppose_attack=True,incoming_attack_skill=profile.skill,weapon_use=intent.protection_use)
        else:
            from towr.domain.pc_generated_equipment import npc_protection_test
            protection_profile, defender = npc_protection_test(state, target, actor, action_id+':protection',
                intent.npc_protection, attack_skill=profile.skill, weapon_use=intent.protection_use)
            skill = protection_profile.skill
        if defender is not None and target_is_pc:
            from towr.domain.pc_help_models import build_pc_test_help
            defender,_ = build_pc_test_help(state,target,skill,defender)
        if enemy.definition.generated_components is not None and profile.skill is Skill.SHOOTING:
            from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus
            from towr.domain.ranged_weapon_profiles import ranged_weapon_reload_profile,RangedWeaponId
            if npc_repeater_bonus(state,actor,attacker,
                    None if target_body.conditions.has(Condition.DEFENCELESS) else defender,target,
                    defender_skill=skill):
                bonus=ranged_weapon_reload_profile(RangedWeaponId(
                    npc_use.primary.kind.value)).optional_bonus_modifier()
                attacker=replace(attacker,dice_modifiers=(*attacker.dice_modifiers,bonus))
        resilience = pc_shield_resilience(state,target) if target_is_pc else target_snapshot.state.current_resilience
        damage_modifiers = (pc_npc_damage_modifiers(enemy.definition)
            + generated_damage_modifiers(enemy.definition,resilience,weapon_use=npc_use))
        from towr.domain.talent_injury_models import hardy_wound_dice_modifiers
        wound_dice_modifiers = ((*pc_npc_wound_dice_modifiers(enemy.definition,target_body),
            *hardy_wound_dice_modifiers(state.source.participant(target).talents)) if target_is_pc else ())
        attacker_conditions = enemy.state.injury.conditions
        target_injury = (target_body if not target_is_pc or target_body.conditions.has(Condition.DEFENCELESS)
            else pc_after_test(state, target,critical_for_hand(member,weapon_use_hand(intent.protection_use))))
        damage = (profile.damage if crown is not None or enemy.definition.generated_components is not None else pc_npc_damage_profile(enemy.definition,
            unopposed=target_injury.conditions.has(Condition.DEFENCELESS)))
        from towr.domain.pc_weapon_inventory import pc_protection_weapon_use
        defence_use=pc_protection_weapon_use(member,Skill.DEFENCE,Skill.MELEE) if target_is_pc else None
        target_armed = (defence_use is not None and bool(defence_use.item_ids)) if target_is_pc else target_snapshot.state.wields_weapon
    if pc_attacks and shooting:
        from towr.domain.ranged_weapon_profiles import RangedWeaponId, ranged_weapon_combat_profile
        ignores_armour = ranged_weapon_combat_profile(RangedWeaponId(weapon.value)).ignores_armour
    else:
        ignores_armour = False if pc_attacks else profile.ignores_armour
    from towr.domain.attack_models import ConditionImpactSpec
    from towr.domain.pc_oath_models import oath_allows_attack
    if not oath_allows_attack(state, actor, intent.attack_skill if pc_attacks else profile.skill):
        raise ValueError('automatic Attack cannot skip the actual GM-confirmed oath restriction')
    from towr.domain.pc_npc_net_policy_models import NET_RULE_ID
    from towr.domain.weapon_impact_preparation import UNARMED_IMPACT_RULE_ID
    if is_npc_champion(state,target) and not target_injury.conditions.has(Condition.DEFENCELESS):
        from towr.domain.pc_npc_champion_models import npc_champion_body,npc_champion_after_test
        target_injury=npc_champion_after_test(state,target,
            critical_for_hand(npc_champion_body(state,target),weapon_use_hand(intent.protection_use)))
    actual_use = weapon_use if pc_attacks else npc_use
    if actual_use is not None:
        from towr.domain.weapon_impact_preparation import prepare_weapon_impact
        preparation=prepare_weapon_impact(actual_use,pc.strength if pc_attacks else enemy.definition.generated_components.strength,
            resilience,actor_mounted=pc_is_mounted(state,actor),charging=charge is not None,
            dragon_fire=intent.dragon_fire)
        impact=preparation.impact_spec
        if not pc_attacks or target_snapshot.definition.injury_policy in (TargetInjuryPolicy.PLAYER,TargetInjuryPolicy.CHAMPION):
            wound_dice_modifiers=(*wound_dice_modifiers,*(m for m in preparation.wound_dice_modifiers
                if actual_use.skill is not Skill.SHOOTING or m.rule_id!='RULE-EQUIPMENT-004:wounds-table-bonus'))
    else:
        impact=(profile.condition_impact if not pc_attacks and profile.condition_impact is not None
            else profile.hazard_impact if not pc_attacks and profile.hazard_impact is not None
            else DamageImpactSpec(damage,resilience,ignores_armour=ignores_armour,damage_modifiers=damage_modifiers))
    from towr.domain.brawn_impact_models import BrawnAttackEffect,prepare_brawn_displacement_impact
    if intent.brawn_effect is not BrawnAttackEffect.STAGGER:
        impact=prepare_brawn_displacement_impact(actual_use,intent.brawn_effect)
    from towr.domain.pc_magic_weapon_models import magic_weapon_attack_test
    attacker=replace(attacker,dice_modifiers=(*attacker.dice_modifiers,*visibility.modifiers))
    if not visibility.visible and intent.attack_skill in (Skill.SHOOTING,Skill.THROWING):
        attacker=replace(attacker,quality_modifiers=tuple(dict.fromkeys((*attacker.quality_modifiers,
            QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM)))))
    attacker=magic_weapon_attack_test(intent,attacker)
    from towr.domain.pc_oath_models import filter_honour_test
    attacker=filter_honour_test(attacker)
    weapon_effects=(() if actual_use is None else preparation.secondary_effects)
    from towr.domain.pc_musician_effect_models import pc_attack_tie_break
    attack = AttackRequest(action_id + ':attack-request', attacker, None,impact,
        pc_enemy_range(state,actor,target).value == 'close', attacker_conditions.has(Condition.STAGGERED),
        tie_break=pc_attack_tie_break(state,actor,target),
        secondary_effects=tuple(dict.fromkeys((*((NearbyTargetsStaggerSpec(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID),)
            if pc_attacks and shooting and weapon is PcMeleeWeapon.BLUNDERBUSS else () if pc_attacks else profile.secondary_effects),
            *pc_mounted_attack_effects(state,actor,target,is_charge=charge is not None,
                attack_skill=intent.attack_skill if pc_attacks else profile.skill),
            *weapon_effects))))
    defenceless = target_injury.conditions.has(Condition.DEFENCELESS)
    from towr.domain.protection_models import HalflingStealthProtectionPermission
    stealth_permission = (HalflingStealthProtectionPermission(target,target_snapshot.definition)
        if not target_is_pc and skill is Skill.STEALTH else None)
    protection = ProtectionPreparationRequest(action_id + ':prepare-protection', target, attack,
        intent.attack_skill if pc_attacks else profile.skill,
        True, defenceless, target_armed, pc_has_working_shield(member) if target_is_pc else target_snapshot.state.holds_shield,
        None if defenceless else skill,
        () if defenceless else (ProtectionTestOption(target,skill,defender),),
        halfling_stealth_permission=stealth_permission)
    from towr.domain.protection_models import _expected_protection
    prepared_attack = _expected_protection(protection)[0]
    from towr.domain.pc_briarroot_models import briarroot_allows_give_ground
    from towr.domain.pc_give_ground_models import pc_give_ground_context
    give_ground=pc_give_ground_context(state,target,actor)
    kernel = KernelAttackRequest(action_id + ':kernel',target,prepared_attack,
        TargetInjuryPolicy.PLAYER if target_is_pc else target_snapshot.definition.injury_policy, target_injury,
        give_ground.can_leave and (pc_attacks or pc_npc_allows_give_ground(enemy.definition))
            and briarroot_allows_give_ground(state,target)
            and (actual_use is None or not preparation.forbids_give_ground),
        give_ground.given_this_round,physical_attack=True,wound_dice_modifiers=wound_dice_modifiers,minion_stagger_defeat=(
            pc_npc_stagger_defeat_spec(target_snapshot.definition) if not target_is_pc else None),
        first_stagger_wound=(pc_flagellant_first_stagger_spec(state,target) if not target_is_pc else None))
    from towr.domain.pc_undead_minion_models import pc_undead_minion_source
    undead = pc_undead_minion_source(state, target)
    if undead is not None:
        from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec, undead_minion_effect_immunities
        kernel = replace(kernel, minion_stagger_defeat=undead_minion_stagger_defeat_spec(undead,target),
            target_effect_immunities=undead_minion_effect_immunities(undead,target))
    if intent.magic_context is not None and intent.magic_context.headsman_execution:
        from towr.domain.injury_models import FixedWoundSelection
        from towr.domain.weapon_quality_preparation import HEADSMAN_EXECUTION_RULE_ID
        kernel=replace(kernel,fixed_character_wound=FixedWoundSelection(
            WoundEntryId.DECAPITATION,27,HEADSMAN_EXECUTION_RULE_ID))
    from towr.domain.pc_oath_models import pc_oath_wound_options
    kernel = replace(kernel, wound_negation_options=pc_oath_wound_options(state, target))
    return kernel,protection



def build_pc_melee_recover(state: PcMeleeState) -> RecoverActionExecutionRequest:
    actor = state.round_state.active_turn.actor_id
    member = state.participant(actor)
    action_id = pc_melee_action_id(state, actor)
    from towr.domain.pc_ally_recover_models import pc_recover_targets
    from towr.domain.pc_weapon_inventory import pc_weapon_pickup_member
    staggered_target,prone_target = pc_recover_targets(state)
    active_item=pc_active_weapon_item_id(state,actor)
    from towr.domain.pc_briarroot_weapon_models import can_pickup_pc_weapon
    weapon_pickup = (member.weapon_hand is None and pc_preferred_weapon_hand(state,actor) is not None
        and can_pickup_pc_weapon(state,actor,active_item)
        and (member.weapon_inventory is None
            or pc_weapon_pickup_member(state,actor,pc_active_weapon_item_id(state,actor)) is not None))
    choice = RecoverStandardChoice(member.magic if member.magic is not None else WizardMagicState(),
        staggered_target=staggered_target,
        prone_target=prone_target,
        object_interaction=(RecoverObjectInteractionFollowUp(action_id + ':pickup',actor,
            pc_active_weapon_item_id(state,actor),True) if weapon_pickup else
            RecoverObjectInteractionFollowUp(action_id+':pickup-shield',actor,actor+':shield',True)
            if pc_shield_recover_hand(member, state=state) is not None else None))
    if state.source.participant(actor).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        from towr.domain.pc_tactical_models import select_pc_tactic
        pickup=select_pc_tactic(state,actor).pickup_item_id
        if pickup is not None:
            if pc_weapon_pickup_member(state,actor,pickup) is None:
                raise ValueError('selected dropped weapon requires its actual available pickup hand')
            choice=replace(choice,object_interaction=RecoverObjectInteractionFollowUp(
                action_id+':pickup-item',actor,pickup,True))
    potion = selected_pc_potion(state)
    from towr.domain.pc_scarab_recover_models import selected_scarab_healing
    scarab=selected_scarab_healing(state)
    healing = None
    if potion is not None:
        choice = replace(choice, object_interaction=RecoverObjectInteractionFollowUp(
            action_id+':drink', actor, potion.item_id, True))
        item = next(item for item in member.potions if item.id == potion.item_id)
        if item.kind is ConsumableKind.HEALING:
            healing = HealingPotionRecoverSource(actor, item, member.injury, potion.wound_sequence)
    elif scarab is not None:
        choice=replace(choice,object_interaction=RecoverObjectInteractionFollowUp(
            action_id+':scarab-heal',actor,scarab.item_id,True))
    from towr.domain.pc_back_in_saddle_models import configure_back_in_saddle_recover
    choice = configure_back_in_saddle_recover(state, actor, action_id, choice)
    return RecoverActionExecutionRequest(action_id + ':execute',state.round_state,actor,member.injury.conditions,
        pc_has_close_enemy(state,actor) if state.battlefield is not None else bool(state.live_enemies),
        1,RecoverMode.STANDARD,choice,healing_potion=healing)


def build_pc_wound_completion(state: PcMeleeState) -> CharacterWoundLifecycleCompletionRequest:
    """Bind the explicit strategy to this actual rolled Wound and resource prefix."""
    pending = state.pending_wound
    if pending is None:
        raise ValueError('no actual PC Wound awaits its Fate decision')
    if is_npc_champion(state,state.pending_actor_id):
        from towr.domain.pc_npc_champion_models import npc_champion_wound_completion
        return npc_champion_wound_completion(state)
    member = state.participant(state.pending_actor_id)
    participant = state.source.participant(member.actor_id)
    completions = tuple(p.completion for p in state.history if isinstance(p, PcWoundCompletionProof))
    consumed = tuple(c.source_request.roll.request_id for c in completions)
    effects = completions[-1].consumed_near_miss_effect_ids if completions else ()
    near_miss = None
    strategy = participant.near_miss_policy
    from towr.domain.pc_armour_models import actor_armour_allows_near_miss
    if (participant.fate_policy is PcFatePolicy.CONFIGURED and strategy is not None
            and actor_armour_allows_near_miss(state,member.actor_id)
            and pending.near_miss_eligible
            and pending.wound_result.table_roll.total >= strategy.minimum_table_total
            and member.fate.rating > strategy.minimum_rating_to_keep):
        base_id = pending.request_id+':near-miss-burn'
        used_ids = {*member.fate.resource_event_ids, *(spend.id for spend in member.fate.spends)}
        burn_id, suffix = base_id, 0
        while burn_id in used_ids:
            suffix += 1
            burn_id = f'{base_id}:{suffix}'
        near_miss = FateNearMissBurnRequest(burn_id, member.fate,
            ConsumeWoundNegationRequest(pending.source_request.wound.id, FATE_NEAR_MISS_RULE_ID))
    return CharacterWoundLifecycleCompletionRequest(pending.request_id+':complete', pending,
        member.injury, member.daily_wounds,
        daily_registration_id=pending.request_id+':daily' if near_miss is None and pending.wound_result.wound_accepted else None,
        near_miss=near_miss, consumed_roll_ids=consumed, consumed_near_miss_effect_ids=effects)


def _decline(state: PcMeleeState, actual: PcFateDecline, actor_id: str, source_id: str, window: str):
    if not isinstance(actual,PcFateDecline):
        raise TypeError('PC Fate decision must be typed')
    replace(actual)
    member = state.source.participant(actor_id)
    if actual != PcFateDecline(actor_id,source_id,window,member.fate_policy):
        raise ValueError('Fate decline differs from the actor, window or selected source policy')


def _party_update(state: PcMeleeState, actor_id: str, **changes):
    member = state.participant(actor_id)
    sources = changes.get('hit_condition_sources',member.hit_condition_sources)
    if sources:
        changes['injury'] = retain_pc_hit_conditions(changes.get('injury',member.injury),sources)
    net_sources = changes.get('net_condition_sources',member.net_condition_sources)
    if net_sources:
        injury = changes.get('injury',member.injury)
        changes['injury'] = replace(injury,conditions=injury.conditions.with_condition(Condition.BURDENED))
    from towr.domain.pc_weapon_inventory import replace_pc_member
    return tuple(replace_pc_member(m,**changes)
        if m.actor_id==actor_id else m for m in state.party)


def _test_result(request: TestRequest, actual: TestResult):
    if not isinstance(actual,TestResult) or not isinstance(actual.trace,RollTrace):
        raise TypeError('PC Test requires its actual trace')
    trace = actual.trace
    if type(trace.request_id) is not str:
        raise TypeError('PC Test trace request ID must be a string')
    for name in ('base_dice','pool_cap','regular_dice_delta','cap_bypassing_dice','dice_before_minimum',
            'rolled_dice','threshold','rolled_successes','success_delta','successes'):
        if type(getattr(trace,name)) is not int:
            raise TypeError('PC Test trace counters must be exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or not isinstance(trace.quality,TestQuality):
        raise TypeError('PC Test trace requires a bool minimum flag and typed quality')
    if type(trace.rerolls) is not tuple or type(trace.applied_rule_ids) is not tuple:
        raise TypeError('PC Test trace collections must be canonical tuples')
    if any(type(v) is not str or not v for v in trace.applied_rule_ids):
        raise TypeError('PC Test rule IDs must be strings')
    if any(type(r) is not RerollTrace for r in trace.rerolls):
        raise TypeError('PC reroll traces must be typed')
    parameters = _expected_initial_roll_parameters(request)
    for values in (trace.initial_values,trace.final_values):
        if type(values) is not tuple:
            raise TypeError('PC Test dice require canonical tuples')
        if len(values) != parameters[5] or any(type(v) is not int or not 1 <= v <= 10 for v in values):
            raise ValueError('PC Test has malformed d10 values')
    grim = any(m.quality is TestQuality.GRIM for m in request.quality_modifiers)
    glorious = any(m.quality is TestQuality.GLORIOUS for m in request.quality_modifiers)
    quality = TestQuality.NORMAL if grim == glorious else TestQuality.GRIM if grim else TestQuality.GLORIOUS
    locked = {modifier.value for modifier in request.reroll_locks}
    indices = tuple(i for i,v in enumerate(trace.initial_values) if
        v not in locked and (v <= parameters[6] if quality is TestQuality.GRIM else v > parameters[6])) if quality is not TestQuality.NORMAL else ()
    if tuple(r.index for r in trace.rerolls) != indices:
        raise ValueError('PC Test has a missing or extra Grim reroll')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if any(type(getattr(reroll,name)) is not int for name in ('index','original','replacement')):
            raise TypeError('PC reroll coordinates and values must be exact integers')
        if reroll.original != final[reroll.index] or type(reroll.replacement) is not int or not 1 <= reroll.replacement <= 10:
            raise ValueError('PC Test reroll has a stale original or invalid replacement')
        final[reroll.index] = reroll.replacement
    successes = sum(v <= parameters[6] for v in final)
    success_delta = sum(m.amount for m in request.success_modifiers)
    rules = tuple(m.rule_id for mods in (request.dice_modifiers,request.quality_modifiers,
        request.success_modifiers,request.reroll_locks) for m in mods)
    expected = RollTrace(request.id,*parameters[:6],parameters[6],parameters[7],quality,
        trace.initial_values,trace.rerolls,tuple(final),successes,success_delta,max(0,successes+success_delta),rules)
    if trace != expected:
        raise ValueError('PC Test trace is not canonical for its bound request')
    if actual.honour_bound is not None:
        replace(actual)
        grant = actual.honour_bound
        if grant.activation.source_request.test != request or grant.raw_test.trace != trace:
            raise ValueError('exceptional Test outcome changed its actual prepared source or dice')


def _enemy_update(state: PcMeleeState, actor_id: str, injury: ProfileInjuryState):
    injury = replace(injury,conditions=flagellant_conditions(state.enemy(actor_id).definition,injury.conditions))
    return tuple(replace(e,state=replace(e.state,injury=injury)) if e.state.actor_id == actor_id else e for e in state.enemies)


def _ready(state: PcMeleeState):
    if (state.pending or state.pending_wound is not None or state.magic_pending is not None
            or pending_medical_work(state) is not None
            or expected_magic_interruption(state) is not None or expected_pc_aim_consumption(state) is not None
            or pc_melee_unsupported(state) is not None
            or current_warped_form(state) is not None or expected_pc_warped_form_activation(state) is not None):
        raise ValueError('mandatory PC continuation blocks the next ordinary phase')
    if not state.live_party or not state.live_enemies:
        raise ValueError('terminal PC encounter cannot continue')


def project_pc_melee_step(state: PcMeleeState, proof: PcMeleeProof) -> PcMeleeState:
    """Pure projection from one exact source and explicit typed K1 evidence."""
    from towr.domain._pc_melee_projection import project_pc_step
    from towr.domain.pc_oath_models import project_pc_oath_step, project_oath_aftermath, validate_oath_proof_access
    validate_oath_proof_access(state, proof)
    from towr.domain.pc_oath_models import expected_oath_negation_ack
    acknowledgement = expected_oath_negation_ack(state)
    settling_aim = type(proof) in (PcAimConsumptionProof, PcNpcAimConsumptionProof)
    if (acknowledgement is not None and not settling_aim) or type(proof) in (PcLadyPrayerProof, PcOathNegationAckProof):
        if acknowledgement is not None and proof != acknowledgement:
            raise ValueError('actual Wound resource consumption must settle before continuation')
        validate_pc_melee_state_shape(state)
        return project_pc_oath_step(state, proof)
    from towr.domain.pc_npc_champion_models import npc_champion_aftermath
    projected=npc_champion_aftermath(state,project_pc_step(state,proof),proof)
    after = project_oath_aftermath(state,projected,proof)
    from towr.domain.pc_oath_models import validate_native_oath_resources
    validate_native_oath_resources(after)
    return after


def validate_pc_melee_combat_shape(combat: CombatRoundState) -> None:
    if not isinstance(combat,CombatRoundState):
        raise TypeError('PC clock must be a CombatRoundState')
    replace(combat)
    for participant in combat.participants:
        replace(participant)
    if combat.active_turn is not None:
        replace(combat.active_turn)
        for slot in combat.active_turn.action_slots:
            replace(slot)
            if slot.execution is not None:
                replace(slot.execution)


def validate_pc_melee_source_types(recorded: object, canonical: object) -> None:
    """Equal source snapshots must retain canonical nested value types.

    The canonical prefix has already checked the rules. This data walk catches
    bool/int or Enum/string substitutions in copied historical proofs without
    replaying every prefix again. Shared immutable nodes are visited once.
    """
    visited = set()

    def check(actual, expected):
        if type(actual) is not type(expected):
            raise TypeError('recorded PC source changed a canonical value type')
        pair = (id(actual),id(expected))
        if actual is expected or pair in visited:
            return
        visited.add(pair)
        if is_dataclass(expected):
            for item in fields(expected):
                if item.compare:
                    check(getattr(actual,item.name),getattr(expected,item.name))
        elif isinstance(expected,tuple):
            for left,right in zip(actual,expected):
                check(left,right)
        elif isinstance(expected,frozenset):
            if {(type(item),item) for item in actual} != {(type(item),item) for item in expected}:
                raise TypeError('recorded PC source changed a canonical set value type')

    check(recorded,canonical)


def validate_pc_melee_state_shape(state: PcMeleeState) -> None:
    if not isinstance(state,PcMeleeState):
        raise TypeError('PC owner must be typed')
    replace(state)
    validate_pc_melee_scenario_admission(state.source)
    from towr.domain.pc_oath_models import validate_native_oath_resources
    validate_native_oath_resources(state)
    from towr.domain.pc_oath_models import oath_context_for
    expected_oath_actors = tuple(actor for actor in (*state.source.pc_activation_order, *state.source.npc_activation_order)
        if oath_context_for(state.source, actor) is not None)
    if tuple(row.actor_id for row in state.oaths) != expected_oath_actors:
        raise ValueError('native oath resource bank must match actual complete source owners')
    for row in state.oaths:
        if row.context != oath_context_for(state.source, row.actor_id):
            raise ValueError('native oath GM context replaced its actual original source')
    validate_pc_melee_combat_shape(state.round_state)
    for member in state.party:
        replace(member)
        from towr.domain.pc_melee_models import _readmit_fate
        _readmit_fate(member.fate, member.actor_id)
        replace(member.injury)
        ConditionState(member.injury.conditions.conditions)
        if type(member.injury.dead) is not bool:
            raise TypeError('PC death flag must be a bool')
        for wound in member.injury.wounds:
            replace(wound)
            if any(type(value) is not int for value in wound.roll_values):
                raise TypeError('Wound d10 values must be exact integers')
        for effect in member.injury.active_wound_effects:
            replace(effect)
        replace(member.daily_wounds)
        for receipt in member.daily_wounds.receipts:
            replace(receipt)
            replace(receipt.wound)
        for expiry in member.timed_wounds:
            replace(expiry)
            replace(expiry.effect)
    for enemy in state.enemies:
        replace(enemy)
        replace(enemy.state)
        replace(enemy.state.injury)
        replace(enemy.state.current_resilience)
        if (type(enemy.state.actor_id) is not str or type(enemy.state.definition_id) is not str
                or type(enemy.state.injury) not in (CharacterInjuryState,ProfileInjuryState)
                or any(type(value) is not str for value in enemy.state.available_attack_ids)):
            raise TypeError('Minion owner scalar/ID fields must retain canonical types')
        if type(enemy.state.injury) is ProfileInjuryState:
            if (type(enemy.state.injury.wounds) is not int or type(enemy.state.injury.wound_limit) is not int
                    or type(enemy.state.injury.defeated) is not bool):
                raise TypeError('profile NPC health must retain canonical counter/flag types')
        elif type(enemy.state.injury.dead) is not bool:
            raise TypeError('Champion death must retain its exact flag')
        ConditionState(enemy.state.injury.conditions.conditions)
    if any(type(proof) not in PcMeleeProof.__args__ for proof in state.history):
        raise TypeError('PC owner history requires the explicit M9 proof variants')
    if state.pending_wound is not None:
        replace(state.pending_wound)
        replace(state.pending_wound.source_request)
        replace(state.pending_wound.source_request.wound)
        table = state.pending_wound.wound_result.table_roll
        replace(table)
        replace(table.entry)
        if any(type(value) is not int for value in table.values):
            raise TypeError('pending Wound d10 values must be exact integers')
    for pending in state.pending:
        if isinstance(pending,(WoundEnduranceTestRequest,WoundConsequenceRequest,WoundChoiceRequest)) or type(pending) in (HazardExposureRequest,GiveGroundRequest,ConditionAfterGiveGroundRequest,BrawnDisplacementRequest):
            replace(pending)
        elif isinstance(pending,AttackerStaggerRequest):
            if type(pending.attack_id) is not str or type(pending.rule_id) is not str:
                raise TypeError('miss follow-up IDs must be strings')
        elif isinstance(pending,ProfileStateChangeRequest):
            if (not isinstance(pending.npc_type,ProfileNpcType)
                    or type(pending.previous_wounds) is not int or type(pending.current_wounds) is not int
                    or type(pending.defeated) is not bool):
                raise TypeError('profile change requires typed integer/bool values')
        elif type(pending) is MinionStaggerDefeatCause:
            replace(pending)
        elif type(pending) is ConsumeWoundNegationRequest:
            replace(pending)
        elif type(pending) is NearbyTargetsStaggerRequest:
            replace(pending)
            if type(pending.resolution_id) is not str or type(pending.rule_id) is not str:
                raise TypeError('nearby trigger requires exact resolution/rule IDs')
        else:
            raise TypeError('unsupported pending PC continuation type')
