"""Source-bound journal for the bounded PC melee encounter (ADR-0065)."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import AttackRequest, AttackOutcome, DamageImpactSpec, ImpactOutcome, MissConsequence
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_weapon_models import (pc_weapon_damage, pc_weapon_test_modifiers,
    pc_weapon_attack_modifiers, pc_weapon_damage_modifiers)
from towr.domain.pc_npc_ability_models import (pc_npc_outnumbering_modifier,pc_npc_allows_give_ground,
    pc_npc_allows_enemy_higher_ground,
    pc_npc_attack_modifiers,pc_npc_damage_modifiers,pc_npc_damage_profile,pc_npc_stagger_defeat_spec,
    pc_npc_wound_dice_modifiers)
from towr.domain.pc_npc_wound_models import PcNpcBrokenTurnUnsupported, PcNpcBrokenWaveTurnUnsupported, pc_npc_broken_turn_unsupported
from towr.domain.pc_npc_exit_models import PcNpcExitProof
from towr.domain.pc_minion_defeat_models import validate_pc_minion_defeat_equipment
from towr.domain.pc_npc_distraction_models import (PcNpcDistractionSource,PcNpcWaveDistractionSource,PcNpcDistractionExpiredProof,
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
from towr.domain.pc_pistol_models import (PcPistolShotProof,PcPistolReloadProof,initial_pc_pistol,
    pc_pistol_unsupported,pistol_reload_declaration,prepare_pc_pistol_shot)
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.pc_shield_models import (PcShieldState, PcShieldLocation, PcShieldReleaseProof,
    initial_pc_shield, pc_has_working_shield, pc_shield_recover_hand, pc_shield_recover_needed,
    pc_shield_resilience, pc_defence_hand, expected_pc_shield_release)
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
    PcFatePolicy, PcMeleeScenario, PcWeaponHand, PcTwoHandedGrip, validate_pc_melee_scenario_admission,
)
from towr.domain.protection_models import (
    ProtectionPreparationRequest, ProtectionPreparationResult, ProtectionTestOption,
)
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionTarget,
    RecoverMode, RecoverObjectInteractionFollowUp, RecoverStandardChoice,
)
from towr.domain.resolution_models import AttackerStaggerRequest, KernelAttackRequest, TargetInjuryPolicy, ConsumeWoundNegationRequest
from towr.domain.test_models import (
    DiceModifier, QualityModifier, RerollTrace, RollTrace, Skill, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatRoundAdvanceResult,
    CombatRoundState, CombatSide, CombatTurnEndResult, CombatTurnParticipant, CombatTurnStartResult,
    CombatTurnState, CombatActionSlotResult, CombatActionSlot,
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


PcMeleePending = WoundEnduranceTestRequest | WoundConsequenceRequest | WoundChoiceRequest | AttackerStaggerRequest | ProfileStateChangeRequest


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
                'pistol_grip_unavailable','pistol_reload_hands_unavailable')
                or type(self.source_id) is not str or not self.source_id):
            raise ValueError('unsupported PC result requires an exact Wound source')
        for value in (self.wound_sequence, self.table_total):
            if type(value) is not int or value < 1:
                raise ValueError('unsupported Wound values must be positive integers')
        if not 11 <= self.table_total <= 23:
            raise ValueError('anatomical stop requires a heavy Wound source')
        if self.reason in ('two_handed_grip_unavailable','pistol_grip_unavailable',
                'pistol_reload_hands_unavailable') and self.table_total not in (16,18,20):
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
    weapon_hand: PcWeaponHand | PcTwoHandedGrip | None
    fate: FateSessionState
    daily_wounds: DailyWoundState
    timed_wounds: tuple[PcTimedWound, ...] = ()
    body_facts: tuple[PcBodyFact, ...] = ()
    using_backup_weapon: bool = False
    hit_condition_sources: tuple[PcHitConditionSource,...] = ()
    net_condition_sources: tuple[PcNetConditionSource,...] = ()
    shield: PcShieldState | None = field(default=None,kw_only=True)
    pistol: ReloadableWeaponState | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC state requires its actor ID')
        if not isinstance(self.injury, CharacterInjuryState) or not isinstance(self.fate, FateSessionState):
            raise TypeError('PC state requires PLAYER injury and actual Fate session')
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError('PC state requires typed daily Wound history')
        if self.fate.actor_id != self.actor_id or self.daily_wounds.target_id != self.actor_id:
            raise ValueError('PC Fate/daily histories belong to another actor')
        if self.weapon_hand is not None and type(self.weapon_hand) not in (PcWeaponHand,PcTwoHandedGrip):
            raise TypeError('held PC weapon requires its typed hand')
        if self.pistol is not None:
            if type(self.pistol) is not ReloadableWeaponState:
                raise TypeError('PC Pistol requires its exact reload state')
            replace(self.pistol)
            if self.pistol.weapon_instance_id!=self.actor_id+':weapon':
                raise ValueError('Pistol instance belongs to another actor')
        if self.shield is not None:
            if type(self.shield) is not PcShieldState:
                raise TypeError('PC shield must retain its exact runtime state')
            replace(self.shield)
        if type(self.using_backup_weapon) is not bool:
            raise TypeError('backup weapon activation must be an exact bool')
        if type(self.hit_condition_sources) is not tuple:
            raise TypeError('hit Condition sources must be a canonical tuple')
        for source in self.hit_condition_sources:
            if type(source) is not PcHitConditionSource:
                raise TypeError('hit Condition bank requires exact typed sources')
            replace(source)
            if source.target_id!=self.actor_id:
                raise ValueError('hit Condition source belongs to another target')
        if (len({s.application_id for s in self.hit_condition_sources})!=len(self.hit_condition_sources)
                or len({s.attack_id for s in self.hit_condition_sources})!=len(self.hit_condition_sources)):
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
    npc_distractions: tuple[PcNpcDistractionSource | PcNpcGrudgeDistractionSource | PcNpcWaveDistractionSource, ...] = ()

    def __post_init__(self):
        if not isinstance(self.source, PcMeleeScenario) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError('PC owner requires source scenario and combat clock')
        for name in ('party', 'enemies', 'pending', 'history'):
            if not isinstance(getattr(self, name), (tuple, list)):
                raise TypeError('PC owner collections must be ordered')
            object.__setattr__(self, name, tuple(getattr(self, name)))
        exits = tuple(proof for proof in self.history if type(proof) is PcNpcExitProof)
        actors = tuple(proof.request.actor_id for proof in exits)
        if (len(set(actors))!=len(actors) or any(actor not in self.source.enemy_activation_order for actor in actors)
                or exits and self.source.npc_broken_exit_policy is None):
            raise ValueError('NPC exits must preserve their one actual source-bound movement each')
        for proof in exits:
            replace(proof)
        if (not all(isinstance(m, PcMeleeParticipantState) for m in self.party)
                or tuple(m.actor_id for m in self.party) != tuple(m.actor_id for m in self.source.party)):
            raise ValueError('PC owner must preserve its complete ordered party')
        has_hit_effects = any(attack.secondary_effects for enemy in self.source.enemies
            for attack in enemy.definition.attacks)
        hit_causes = (tuple(cause for proof in self.history
            if type(proof) is PcAttackProof and proof.request.target_id in self.source.pc_activation_order
            for cause in hit_condition_sources_from_attack(proof.request,proof.execution.resolution))
            if has_hit_effects else ())
        net_causes = tuple(cause for proof in self.history if type(proof) is PcAttackProof
            for cause in net_condition_sources_from_attack(proof.request,proof.execution.resolution)) if self.source.npc_net_policies else ()
        for member, source in zip(self.party, self.source.party):
            replace(member)
            if (member.shield is None)!=(source.shield is None):
                raise ValueError('PC shield runtime must preserve its source loadout membership')
            if (member.pistol is None)!=(source.pc.pistol is None):
                raise ValueError('Pistol runtime must retain its source membership')
            expected_hit_sources = tuple(cause for cause in hit_causes if cause.target_id==member.actor_id)
            if member.hit_condition_sources!=expected_hit_sources:
                raise ValueError('hit Condition bank must preserve its actual successful Attack history')
            validate_pc_melee_source_types(member.hit_condition_sources,expected_hit_sources)
            expected_net_sources = tuple(cause for cause in net_causes if cause.target_id==member.actor_id)
            if member.net_condition_sources!=expected_net_sources:
                raise ValueError('Net bank differs from actual successful throws')
            validate_pc_melee_source_types(member.net_condition_sources,expected_net_sources)
            draws = tuple(p for p in self.history if isinstance(p,PcBackupWeaponDrawProof) and p.actor_id==member.actor_id)
            if (len(draws)>1 or member.using_backup_weapon != bool(draws)
                    or member.using_backup_weapon and source.backup_weapon_policy is None):
                raise ValueError('backup activation must preserve its single actual draw receipt')
            grip_type = PcWeaponHand if member.using_backup_weapon else type(source.initial_weapon_hand)
            if member.weapon_hand is not None and type(member.weapon_hand) is not grip_type:
                raise ValueError('held weapon grip must preserve its one/two-handed source')
            expected_fate = source.fate
            for proof in self.history:
                glorious = (proof.glorious if isinstance(proof,(PcAttackProof,PcEnduranceProof,PcHelpProof,PcPistolReloadProof)) else
                    proof.critical.glorious if isinstance(proof,(PcTurnEndProof,PcIncapacitatedTurnEndProof))
                    and proof.critical is not None else None)
                if glorious is not None and glorious.previous_state.actor_id == member.actor_id:
                    if glorious.previous_state != expected_fate:
                        raise ValueError('PC Fate spends must extend the actual resource history')
                    expected_fate = glorious.state
                if isinstance(proof, PcWoundCompletionProof) and proof.completion.fate_burn is not None:
                    burn = proof.completion.fate_burn
                    if burn.previous_state.actor_id == member.actor_id:
                        if burn.previous_state != expected_fate:
                            raise ValueError('PC Fate burns must extend the actual resource history')
                        expected_fate = burn.state
            if member.fate != expected_fate or member.daily_wounds.day_id != self.source.day_id:
                raise ValueError('PC owner cannot replace Fate or daily source')
        if (not all(isinstance(e, NpcParticipantSnapshot) for e in self.enemies)
                or tuple(e.state.actor_id for e in self.enemies) != tuple(e.state.actor_id for e in self.source.enemies)
                or any(e.definition != old.definition for e, old in zip(self.enemies, self.source.enemies))):
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
                if (wave is None or target is None or target.activation_id != wave.activation_id
                        or target.request.target_id != self.pending_actor_id
                        or self.pending_actor_id not in self.source.enemy_activation_order
                        or self.pending_wound is not None
                        or self.pending != target.result.follow_ups):
                    raise ValueError('NPC pending owner requires its actual wave target queue')
            if self.pending_wound is not None and self.pending_wound.source_request.target_id != self.pending_actor_id:
                raise ValueError('pending Wound belongs to another PC')
        elif self.pending_actor_id is not None:
            raise ValueError('a completed queue cannot retain a pending PC owner')
        validate_pc_npc_distractions(self)
        validate_pc_flagellant_conditions(self)

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
        return tuple(e for e in self.enemies if not e.state.injury.defeated and e.state.actor_id not in exited)

    @property
    def exited_npc_ids(self) -> tuple[str, ...]:
        if self.source.npc_broken_exit_policy is None:
            return ()
        observed = {proof.request.actor_id for proof in self.history if type(proof) is PcNpcExitProof}
        return tuple(enemy.state.actor_id for enemy in self.source.enemies if enemy.state.actor_id in observed)


def pc_melee_round_participants(state: PcMeleeState) -> tuple[CombatTurnParticipant, ...]:
    return (*(CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES)
              for actor in state.source.pc_activation_order if not state.participant(actor).injury.dead),
            *(CombatTurnParticipant(actor, CombatSide.OPPOSITION)
              for actor in state.source.enemy_activation_order
              if not state.enemy(actor).state.injury.defeated and actor not in state.exited_npc_ids))


def initial_pc_melee_state(source: PcMeleeScenario) -> PcMeleeState:
    validate_pc_melee_scenario_admission(source)
    participants = (*(CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES) for actor in source.pc_activation_order),
        *(CombatTurnParticipant(actor, CombatSide.OPPOSITION) for actor in source.enemy_activation_order))
    party = tuple(PcMeleeParticipantState(member.actor_id, CharacterInjuryState(), member.initial_weapon_hand,
        member.fate, DailyWoundState(source.day_id, member.actor_id),shield=initial_pc_shield(member.shield),pistol=initial_pc_pistol(member)) for member in source.party)
    return PcMeleeState(source, CombatRoundState(1, participants), party, source.enemies)


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
    pistol_shot: PcPistolShotProof | None = field(default=None,kw_only=True)


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


@dataclass(frozen=True, slots=True)
class PcBodyConsequenceProof:
    source: WoundConsequenceRequest
    die: int | None
    side: PcWeaponHand | None
    count: int = 1


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
    previous_hand: PcTwoHandedGrip | None
    hand: PcWeaponHand

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('backup draw requires its actual actor ID')
        if self.previous_hand is not None and type(self.previous_hand) is not PcTwoHandedGrip:
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


@dataclass(frozen=True, slots=True)
class PcRecoverProof:
    result: RecoverActionExecutionResult


@dataclass(frozen=True, slots=True)
class PcTurnEndProof:
    result: CombatTurnEndResult
    fate_decline: PcFateDecline | None
    critical: PcCriticalProof | None = None


PcMeleeProof = (
    CombatTurnStartResult | CombatActionSlotResult | PcAttackProof | PcWoundCompletionProof | PcNpcBloodRageProof
    | PcNpcRecoverProof | PcFlagellantMissWoundProof
    | PcWarpedFormActivationProof | PcWarpedFormTargetProof | PcWarpedFormProfileProof
    | PcWarpedFormMinionDefeatProof | PcWarpedFormEndProof
    | PcEnduranceProof | PcHandDropProof | PcAttackerStaggerProof | PcProfileWoundProof
    | PcRecoverProof | PcTurnEndProof | PcIncapacitatedTurnEndProof | PcBodyConsequenceProof | PcMinionStaggerDefeatProof | PcNpcHelpProof
    | PcWoundChoiceProof | PcHandSwapProof | PcBackupWeaponDrawProof | PcHelpProof | PcNpcExitProof | CombatRoundAdvanceResult
    | PcNpcDistractionExpiredProof
    | PcNpcGrudgeEncounterProof | PcNpcNetDrawProof | PcShieldReleaseProof | PcPistolReloadProof
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
    unsupported: PcMeleeUnsupported | PcNpcBrokenTurnUnsupported | PcNpcBrokenWaveTurnUnsupported | None = None

    def __post_init__(self):
        validate_pc_melee_scenario_admission(self.source)
        if not isinstance(self.outcome, PcMeleeOutcome) or not isinstance(self.steps, (tuple, list)):
            raise TypeError('PC result needs typed outcome and ordered steps')
        if self.unsupported is not None:
            if not isinstance(self.unsupported,(PcMeleeUnsupported,PcNpcBrokenTurnUnsupported,PcNpcBrokenWaveTurnUnsupported)):
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
        if actual_stop is None and (current_warped_form(current) is not None
                or expected_pc_warped_form_activation(current) is not None):
            raise ValueError('terminal result skipped its Warped Form end phase')
        if (actual_stop is None and current.round_state.active_turn is not None
                and current.round_state.active_turn.actor_id in {p.actor_id for p in self.source.npc_warped_form_policies}
                and current.round_state.active_turn.action_slots
                and all(s.executed for s in current.round_state.active_turn.action_slots)):
            raise ValueError('terminal result skipped Skin Wolf TurnEnd')
        if expected_pc_npc_grudge_encounter(current) is not None:
            raise ValueError('PC result skipped its initial grudge encounters')
        if expected_pc_npc_blood_rage(current) is not None:
            raise ValueError('PC result skipped its selected pre-Attack Blood Rage')
        if actual_stop is None and expected_pc_npc_distraction_expiry(current) is not None:
            raise ValueError('PC result skipped mandatory focus-death distraction expiry')
        if self.unsupported != actual_stop:
            raise ValueError('PC unsupported result must preserve its actual pending source')
        active = current.round_state.active_turn
        if (actual_stop is None and active is not None and active.actor_id in self.source.enemy_activation_order
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
        return sum(isinstance(step.proof, (PcAttackProof, PcRecoverProof, PcHelpProof, PcNpcHelpProof, PcNpcRecoverProof, PcPistolReloadProof)) for step in self.steps)

    @property
    def started_rounds(self) -> int:
        return self.state.round_state.round_number

    @property
    def completed_rounds(self) -> int:
        return self.started_rounds - 1 + int(self.state.round_state.round_complete)


def _pc_wound_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | None:
    # Finish the entire actual Wound lifecycle and immediate consequence queue
    # before reporting the caller-selected boundary; never infer this from a roll.
    if not state.pending and state.pending_wound is None:
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        for member, source in zip(state.party,state.source.party):
            if (member.injury.dead or member.using_backup_weapon
                    or not pc_weapon_requires_two_hands(source.pc.weapon) or len(usable_hands(member)) == 2):
                continue
            if source.backup_weapon_policy is not None and len(usable_hands(member)) == 1:
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
    member = state.participant(state.pending_actor_id)
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


def pc_melee_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | PcNpcBrokenTurnUnsupported | PcNpcBrokenWaveTurnUnsupported | None:
    return _pc_wound_unsupported(state) or pc_npc_broken_turn_unsupported(state) or pc_pistol_unsupported(state)


def pc_melee_action_id(state: PcMeleeState, actor_id: str) -> str:
    return f'{state.source.id}:r{state.round_state.round_number}:{actor_id}'


def pc_melee_selected_action(state: PcMeleeState) -> CombatActionKind:
    actor_id = state.round_state.active_turn.actor_id
    if actor_id in state.source.pc_activation_order:
        member = state.participant(actor_id)
        if _pc_recover_needed(member):
            return CombatActionKind.RECOVER
        from towr.domain.pc_ally_recover_models import pc_ally_recover_beneficiary
        if pc_ally_recover_beneficiary(state) is not None:
            return CombatActionKind.RECOVER
        from towr.domain.pc_help_models import pc_help_beneficiary
        if pc_help_beneficiary(state) is not None:
            return CombatActionKind.HELP
        if member.pistol is not None and not member.pistol.loaded:
            return CombatActionKind.IMPROVISE
    else:
        if pc_flagellant_recover_selected(state, actor_id):
            return CombatActionKind.RECOVER
        from towr.domain.pc_npc_help_models import pc_npc_help_beneficiary
        if pc_npc_help_beneficiary(state) is not None:
            return CombatActionKind.HELP
    return CombatActionKind.ATTACK


def pc_melee_action_declaration(state):
    actor = state.round_state.active_turn.actor_id
    kind = pc_melee_selected_action(state)
    return pistol_reload_declaration(state,actor) if kind is CombatActionKind.IMPROVISE else CombatActionDeclaration(kind)


def pc_attack_skill(state,actor):
    return Skill.SHOOTING if state.source.participant(actor).pc.pistol is not None else Skill.MELEE


def _pc_recover_needed(member):
    return pc_shield_recover_needed(member) or usable_weapon_hand(member) is None or (member.injury.conditions.has(Condition.PRONE)
        and not has_ongoing_condition(member.injury,Condition.PRONE))


def pc_melee_next_actor(state: PcMeleeState) -> str:
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    if state.round_state.next_side is CombatSide.PLAYERS_AND_ALLIES:
        return next(actor for actor in state.source.pc_activation_order
            if not state.participant(actor).injury.dead and actor not in unavailable)
    return next(actor for actor in state.source.enemy_activation_order
        if not state.enemy(actor).state.injury.defeated and actor not in state.exited_npc_ids and actor not in unavailable)


def _pc_test(state: PcMeleeState, actor_id: str, test_id: str, skill: Skill,
             dice_modifiers: tuple[DiceModifier, ...] = ()) -> TestRequest:
    member = state.participant(actor_id)
    pc = state.source.participant(actor_id).pc
    if skill in (Skill.SHOOTING,Skill.DEXTERITY):
        if pc.pistol is None:
            raise ValueError('this PC has no authored Shooting/Dexterity profile')
        profile = pc.pistol.shooting_profile if skill is Skill.SHOOTING else pc.pistol.dexterity_profile
    else:
        profile = {Skill.MELEE: pc.melee_profile, Skill.DEFENCE: pc.defence_profile,
            Skill.ATHLETICS: pc.athletics_profile, Skill.ENDURANCE: pc.endurance_profile}[skill]
    drained = member.injury.conditions.has(Condition.DRAINED)
    weapon_modifiers = (pc_weapon_test_modifiers(pc_active_weapon(state,actor_id),skill,member.injury.conditions)
        if usable_weapon_hand(member) is not None else ())
    modifiers = (*dice_modifiers,*weapon_modifiers)
    if drained:
        modifiers = tuple(m for m in modifiers if m.amount <= 0)
    qualities = []
    if skill is not Skill.ENDURANCE and member.injury.conditions.has(Condition.BLINDED):
        qualities.append(QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    qualities.extend(QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)
        for e in member.injury.active_wound_effects
        if isinstance(e, WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM)
    return TestRequest(test_id, profile, modifiers, tuple(qualities))


def pc_after_test(state: PcMeleeState, actor_id: str, injury=None) -> CharacterInjuryState:
    injury = state.participant(actor_id).injury if injury is None else injury
    return replace(injury, active_wound_effects=tuple(e for e in injury.active_wound_effects
        if not isinstance(e, WoundRestrictionEffect) or e.restriction is not WoundRestriction.NEXT_TEST_IS_GRIM))


def pc_selected_npc_attack_profile(state,actor):
    enemy = state.enemy(actor)
    turn = state.round_state.active_turn
    crown = (turn.action_slots[-1].crown_of_antlers if turn is not None and turn.actor_id==actor
        and turn.action_slots else None)
    selected = crown.attack_id if crown is not None else selected_pc_npc_net_attack(state,actor)
    return next((profile for profile in enemy.definition.attacks if profile.id==selected),enemy.definition.attacks[0])


def pc_protection_skill(member,attack_skill):
    if attack_skill is Skill.BRAWN:
        return Skill.ENDURANCE
    if attack_skill in (Skill.SHOOTING,Skill.THROWING):
        return Skill.DEFENCE if pc_has_working_shield(member) else Skill.ATHLETICS
    return Skill.DEFENCE if usable_weapon_hand(member) is not None or pc_has_working_shield(member) else Skill.ATHLETICS


def build_pc_melee_attack(state: PcMeleeState) -> tuple[AttackActionExecutionRequest, ProtectionPreparationRequest]:
    if current_warped_form(state) is not None or expected_pc_warped_form_activation(state) is not None:
        raise ValueError('Warped Form end phase must finish before another Attack preparation')
    if expected_pc_npc_blood_rage(state) is not None:
        raise ValueError('Attack must follow its selected Blood Rage proof')
    if expected_pc_npc_net_draw(state) is not None:
        raise ValueError('Attack must follow its actual carried weapon draw')
    if expected_pc_shield_release(state) is not None:
        raise ValueError('Attack must follow its actual weapon-first shield release')
    turn = state.round_state.active_turn
    actor = turn.actor_id
    # Preparation can precede reservation; actual execution still requires a slot.
    slot_index = len(turn.action_slots) or 1
    grant = (turn.action_slots[-1].enduring_strength or turn.action_slots[-1].crown_of_antlers) if turn.action_slots else None
    crown = turn.action_slots[-1].crown_of_antlers if turn.action_slots else None
    pc_attacks = actor in state.source.pc_activation_order
    target = (next(a for a in state.source.participant(actor).target_priority
        if not state.enemy(a).state.injury.defeated and a not in state.exited_npc_ids)
        if pc_attacks else (grant.target_id if grant is not None
            else next(a for a in state.source.enemy_target_priority if not state.participant(a).injury.dead)))
    action_id = pc_melee_action_id(state, actor) + (':attack2' if slot_index == 2 else '')
    pc_count = sum(not m.injury.conditions.has(Condition.DEFENCELESS) for m in state.live_party)
    enemy_count = sum(not e.state.injury.conditions.has(Condition.DEFENCELESS) for e in state.live_enemies)
    modifiers = []
    damage_modifiers = ()
    wound_dice_modifiers = ()
    if state.source.facts.outnumbering_bonus_approved and (pc_count > enemy_count if pc_attacks else enemy_count > pc_count):
        modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1) if pc_attacks else
            pc_npc_outnumbering_modifier(state.enemy(actor).definition))
    if pc_attacks:
        pc = state.source.participant(actor).pc
        weapon = pc_active_weapon(state,actor)
        member = state.participant(actor)
        target_snapshot = state.enemy(target)
        shooting = pc.pistol is not None
        if shooting:
            modifiers = []
            if target_snapshot.state.injury.conditions.has(Condition.PRONE):
                modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
        if (not shooting and target_snapshot.state.injury.conditions.has(Condition.PRONE)
                and pc_npc_allows_enemy_higher_ground(target_snapshot.definition)):
            modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        modifiers.extend(pc_weapon_attack_modifiers(weapon, target_snapshot.state.injury.conditions))
        attacker = _pc_test(state, actor, action_id + ':attack', pc_attack_skill(state,actor), tuple(modifiers))
        from towr.domain.pc_help_models import build_pc_attack_help
        if not shooting:
            attacker,_ = build_pc_attack_help(state,attacker)
        protection_profile = target_snapshot.definition.protection[0]
        if shooting:
            policy = next((policy for policy in
                (state.source.npc_close_shooting_protection_policies or ())
                if policy.actor_id == target), None)
            if policy is not None:
                from towr.domain.pc_npc_close_shooting_models import pc_close_shooting_protection_profile
                protection_profile = pc_close_shooting_protection_profile(target_snapshot.definition,policy.skill)
        defender = TestRequest(action_id + ':protection', protection_profile.test_profile,
            pc_npc_distraction_test_modifiers(state,target,actor))
        skill = protection_profile.skill
        damage, resilience = pc_weapon_damage(weapon, pc.strength), target_snapshot.state.current_resilience
        damage_modifiers = pc_weapon_damage_modifiers(weapon, resilience)
        attacker_conditions = member.injury.conditions
        target_injury = target_snapshot.state.injury
        target_armed = target_snapshot.state.wields_weapon
    else:
        enemy = state.enemy(actor)
        profile = pc_selected_npc_attack_profile(state,actor)
        if crown is not None and (enemy.definition.id!='pc-book-npc:great_stag'
                or not state.participant(target).injury.conditions.has(Condition.PRONE)
                or state.participant(target).injury.dead):
            raise ValueError('Trample requires the granted same living Prone target')
        member = state.participant(target)
        if profile.skill is Skill.THROWING:
            modifiers = []  # Melee/Brawn outnumbering does not apply to a thrown Net.
        if member.injury.conditions.has(Condition.PRONE) and profile.skill is not Skill.THROWING:
            modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        modifiers.extend(pc_npc_attack_modifiers(enemy.definition,enemy.state.injury.conditions,
            target_conditions=member.injury.conditions,attacker_wounds=enemy.state.injury.wounds))
        modifiers.extend(pc_npc_grudge_melee_modifiers(state,actor,target))
        modifiers.extend(pc_npc_distraction_test_modifiers(state,actor,target))
        if enemy.state.injury.conditions.has(Condition.DRAINED):
            modifiers = [m for m in modifiers if m.amount <= 0]
        attacker = TestRequest(action_id + ':attack', profile.test_profile, tuple(modifiers),
            pc_bestigor_attack_quality(state, actor))
        from towr.domain.pc_npc_help_models import build_pc_npc_attack_help
        if profile.skill is not Skill.THROWING:
            attacker,_ = build_pc_npc_attack_help(state,actor,attacker)
        skill = pc_protection_skill(member,profile.skill)
        defender = _pc_test(state, target, action_id + ':protection', skill)
        if not member.injury.conditions.has(Condition.DEFENCELESS):
            from towr.domain.pc_help_models import build_pc_test_help
            defender,_ = build_pc_test_help(state,target,skill,defender)
        resilience = pc_shield_resilience(state,target)
        damage_modifiers = pc_npc_damage_modifiers(enemy.definition)
        wound_dice_modifiers = pc_npc_wound_dice_modifiers(enemy.definition,member.injury)
        attacker_conditions = enemy.state.injury.conditions
        target_injury = member.injury if member.injury.conditions.has(Condition.DEFENCELESS) else pc_after_test(state, target,critical_for_hand(member,
            pc_defence_hand(member,profile.skill) if skill is Skill.DEFENCE else None))
        damage = (profile.damage if crown is not None else pc_npc_damage_profile(enemy.definition,
            unopposed=target_injury.conditions.has(Condition.DEFENCELESS)))
        target_armed = usable_weapon_hand(member) is not None
    impact = (profile.condition_impact if not pc_attacks and profile.condition_impact is not None
        else DamageImpactSpec(damage,resilience,ignores_armour=pc_attacks and shooting,damage_modifiers=damage_modifiers))
    attack = AttackRequest(action_id + ':attack-request', attacker, None,impact,
        True, attacker_conditions.has(Condition.STAGGERED),
        secondary_effects=() if pc_attacks else profile.secondary_effects)
    defenceless = target_injury.conditions.has(Condition.DEFENCELESS)
    from towr.domain.protection_models import HalflingStealthProtectionPermission
    stealth_permission = (HalflingStealthProtectionPermission(target,target_snapshot.definition)
        if pc_attacks and skill is Skill.STEALTH else None)
    protection = ProtectionPreparationRequest(action_id + ':prepare-protection', target, attack,
        pc_attack_skill(state,actor) if pc_attacks else profile.skill,
        True, defenceless, target_armed, target_snapshot.state.holds_shield if pc_attacks else pc_has_working_shield(member),
        None if defenceless else skill,
        () if defenceless else (ProtectionTestOption(target,skill,defender),),
        halfling_stealth_permission=stealth_permission)
    from towr.domain.protection_models import _expected_protection
    prepared_attack = _expected_protection(protection)[0]
    kernel = KernelAttackRequest(action_id + ':kernel',target,prepared_attack,
        target_snapshot.definition.injury_policy if pc_attacks else TargetInjuryPolicy.PLAYER, target_injury,
        state.source.facts.can_leave_zone and (pc_attacks or pc_npc_allows_give_ground(enemy.definition)),
        False,physical_attack=True,wound_dice_modifiers=wound_dice_modifiers,minion_stagger_defeat=(
            pc_npc_stagger_defeat_spec(target_snapshot.definition) if pc_attacks else None),
        first_stagger_wound=(pc_flagellant_first_stagger_spec(state,target) if pc_attacks else None))
    request = AttackActionExecutionRequest(action_id + ':execute',state.round_state,actor,target,slot_index,kernel)
    if pc_attacks and shooting:
        preparation = prepare_pc_pistol_shot(state,request)
        if preparation.profile_attack!=request:
            raise ValueError('PC Pistol preparation changed its complete canonical profile')
    return request, protection


def build_pc_melee_recover(state: PcMeleeState) -> RecoverActionExecutionRequest:
    actor = state.round_state.active_turn.actor_id
    member = state.participant(actor)
    action_id = pc_melee_action_id(state, actor)
    from towr.domain.pc_ally_recover_models import pc_recover_targets
    staggered_target,prone_target = pc_recover_targets(state)
    choice = RecoverStandardChoice(WizardMagicState(),
        staggered_target=staggered_target,
        prone_target=prone_target,
        object_interaction=(RecoverObjectInteractionFollowUp(action_id + ':pickup',actor,
            pc_active_weapon_item_id(state,actor),True) if member.weapon_hand is None
            and pc_preferred_weapon_hand(state,actor) is not None else
            RecoverObjectInteractionFollowUp(action_id+':pickup-shield',actor,actor+':shield',True)
            if pc_shield_recover_hand(member) is not None else None))
    return RecoverActionExecutionRequest(action_id + ':execute',state.round_state,actor,member.injury.conditions,
        bool(state.live_enemies),1,RecoverMode.STANDARD,choice)


def build_pc_wound_completion(state: PcMeleeState) -> CharacterWoundLifecycleCompletionRequest:
    """Bind the explicit strategy to this actual rolled Wound and resource prefix."""
    pending = state.pending_wound
    if pending is None:
        raise ValueError('no actual PC Wound awaits its Fate decision')
    member = state.participant(state.pending_actor_id)
    participant = state.source.participant(member.actor_id)
    completions = tuple(p.completion for p in state.history if isinstance(p, PcWoundCompletionProof))
    consumed = tuple(c.source_request.roll.request_id for c in completions)
    effects = completions[-1].consumed_near_miss_effect_ids if completions else ()
    near_miss = None
    strategy = participant.near_miss_policy
    if (participant.fate_policy is PcFatePolicy.CONFIGURED and strategy is not None
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
        daily_registration_id=pending.request_id+':daily' if near_miss is None else None,
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
    return tuple(replace(m, **changes) if m.actor_id == actor_id else m for m in state.party)


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
    indices = tuple(i for i,v in enumerate(trace.initial_values) if
        (v <= parameters[6] if quality is TestQuality.GRIM else v > parameters[6])) if quality is not TestQuality.NORMAL else ()
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


def _enemy_update(state: PcMeleeState, actor_id: str, injury: ProfileInjuryState):
    injury = replace(injury,conditions=flagellant_conditions(state.enemy(actor_id).definition,injury.conditions))
    return tuple(replace(e,state=replace(e.state,injury=injury)) if e.state.actor_id == actor_id else e for e in state.enemies)


def _ready(state: PcMeleeState):
    if (state.pending or state.pending_wound is not None or pc_melee_unsupported(state) is not None
            or current_warped_form(state) is not None or expected_pc_warped_form_activation(state) is not None):
        raise ValueError('mandatory PC continuation blocks the next ordinary phase')
    if not state.live_party or not state.live_enemies:
        raise ValueError('terminal PC encounter cannot continue')


def project_pc_melee_step(state: PcMeleeState, proof: PcMeleeProof) -> PcMeleeState:
    """Pure projection from one exact source and explicit typed K1 evidence."""
    from towr.domain._pc_melee_projection import project_pc_step
    return project_pc_step(state,proof)


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
                or type(enemy.state.injury.wounds) is not int or type(enemy.state.injury.wound_limit) is not int
                or type(enemy.state.injury.defeated) is not bool
                or any(type(value) is not str for value in enemy.state.available_attack_ids)):
            raise TypeError('Minion owner scalar/ID fields must retain canonical types')
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
        if isinstance(pending,(WoundEnduranceTestRequest,WoundConsequenceRequest,WoundChoiceRequest)):
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
        else:
            raise TypeError('unsupported pending PC continuation type')
