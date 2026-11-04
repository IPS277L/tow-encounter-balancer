"""Source-bound journal for the bounded PC melee encounter (ADR-0065)."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import AttackRequest, AttackOutcome, DamageImpactSpec, DamageProfile, ImpactOutcome, MissConsequence
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
from towr.domain.fate_models import FateSessionState
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundType, ProfileInjuryState, ProfileNpcType,
    ProfileStateChangeRequest, WoundConditionEffect, WoundConsequence, WoundConsequenceRequest,
    WoundEffectDuration, WoundEnduranceFailure, WoundEnduranceTestRequest, WoundEnduranceTestResult,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleeScenario, PcMeleeWeapon, PcWeaponHand, validate_pc_melee_scenario_admission,
)
from towr.domain.protection_models import (
    ProtectionPreparationRequest, ProtectionPreparationResult, ProtectionTestOption,
)
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionTarget,
    RecoverMode, RecoverObjectInteractionFollowUp, RecoverStandardChoice,
)
from towr.domain.resolution_models import AttackerStaggerRequest, KernelAttackRequest, TargetInjuryPolicy
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


PcMeleePending = WoundEnduranceTestRequest | WoundConsequenceRequest | AttackerStaggerRequest | ProfileStateChangeRequest


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
        if type(self.reason) is not str or self.reason != 'unsupported_wound_effect' or type(self.source_id) is not str or not self.source_id:
            raise ValueError('unsupported PC result requires an exact Wound source')
        for value in (self.wound_sequence, self.table_total):
            if type(value) is not int or value < 1:
                raise ValueError('unsupported Wound values must be positive integers')
        if not 11 <= self.table_total <= 23:
            raise ValueError('only Wounds11-23 are unsupported by this PC slice')


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
        if self.policy is not PcFatePolicy.DECLINE_OPTIONAL_FATE:
            raise ValueError('PC Fate decision requires the selected decline strategy')
        if any(type(v) is not str or not v for v in (self.actor_id, self.source_id)):
            raise ValueError('PC Fate decline requires actor and source')


@dataclass(frozen=True, slots=True)
class PcMeleeParticipantState:
    actor_id: str
    injury: CharacterInjuryState
    weapon_hand: PcWeaponHand | None
    fate: FateSessionState
    daily_wounds: DailyWoundState
    timed_wounds: tuple[PcTimedWound, ...] = ()

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC state requires its actor ID')
        if not isinstance(self.injury, CharacterInjuryState) or not isinstance(self.fate, FateSessionState):
            raise TypeError('PC state requires PLAYER injury and actual Fate session')
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError('PC state requires typed daily Wound history')
        if self.fate.actor_id != self.actor_id or self.daily_wounds.target_id != self.actor_id:
            raise ValueError('PC Fate/daily histories belong to another actor')
        if self.weapon_hand is not None and not isinstance(self.weapon_hand, PcWeaponHand):
            raise TypeError('held PC weapon requires its typed hand')
        if not isinstance(self.timed_wounds, (tuple, list)):
            raise TypeError('PC expiry sources must be ordered')
        object.__setattr__(self, 'timed_wounds', tuple(self.timed_wounds))
        if any(not isinstance(e, PcTimedWound) or e.effect not in self.injury.active_wound_effects for e in self.timed_wounds):
            raise ValueError('PC expiry must refer to a current actual effect')
        if len({e.effect for e in self.timed_wounds}) != len(self.timed_wounds):
            raise ValueError('PC expiry sources must not repeat')


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

    def __post_init__(self):
        if not isinstance(self.source, PcMeleeScenario) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError('PC owner requires source scenario and combat clock')
        for name in ('party', 'enemies', 'pending', 'history'):
            if not isinstance(getattr(self, name), (tuple, list)):
                raise TypeError('PC owner collections must be ordered')
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if (not all(isinstance(m, PcMeleeParticipantState) for m in self.party)
                or tuple(m.actor_id for m in self.party) != tuple(m.actor_id for m in self.source.party)):
            raise ValueError('PC owner must preserve its complete ordered party')
        for member, source in zip(self.party, self.source.party):
            replace(member)
            if member.fate != source.fate or member.daily_wounds.day_id != self.source.day_id:
                raise ValueError('PC owner cannot replace Fate or daily source')
        if (not all(isinstance(e, NpcParticipantSnapshot) for e in self.enemies)
                or tuple(e.state.actor_id for e in self.enemies) != tuple(e.state.actor_id for e in self.source.enemies)
                or any(e.definition != old.definition for e, old in zip(self.enemies, self.source.enemies))):
            raise ValueError('PC owner must preserve its exact ordered Minion definitions')
        if any(replace(e.state,injury=old.state.injury) != old.state for e,old in zip(self.enemies,self.source.enemies)):
            raise ValueError('PC owner cannot change Minion equipment or available attacks')
        if self.pending_wound is not None and not isinstance(self.pending_wound, CharacterWoundLifecycleRollResult):
            raise TypeError('pending PC Wound must retain its lifecycle roll')
        has_pending = bool(self.pending) or self.pending_wound is not None
        if has_pending:
            if type(self.pending_actor_id) is not str or self.pending_actor_id not in self.source.pc_activation_order:
                raise ValueError('mandatory queue must retain its exact PC owner')
            if self.pending_wound is not None and self.pending_wound.source_request.target_id != self.pending_actor_id:
                raise ValueError('pending Wound belongs to another PC')
        elif self.pending_actor_id is not None:
            raise ValueError('a completed queue cannot retain a pending PC owner')

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
        return tuple(e for e in self.enemies if not e.state.injury.defeated)


def pc_melee_round_participants(state: PcMeleeState) -> tuple[CombatTurnParticipant, ...]:
    return (*(CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES)
              for actor in state.source.pc_activation_order if not state.participant(actor).injury.dead),
            *(CombatTurnParticipant(actor, CombatSide.OPPOSITION)
              for actor in state.source.enemy_activation_order if not state.enemy(actor).state.injury.defeated))


def initial_pc_melee_state(source: PcMeleeScenario) -> PcMeleeState:
    validate_pc_melee_scenario_admission(source)
    participants = (*(CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES) for actor in source.pc_activation_order),
        *(CombatTurnParticipant(actor, CombatSide.OPPOSITION) for actor in source.enemy_activation_order))
    party = tuple(PcMeleeParticipantState(member.actor_id, CharacterInjuryState(), member.initial_weapon_hand,
        member.fate, DailyWoundState(source.day_id, member.actor_id)) for member in source.party)
    return PcMeleeState(source, CombatRoundState(1, participants), party, source.enemies)


@dataclass(frozen=True, slots=True)
class PcAttackProof:
    request: AttackActionExecutionRequest
    protection: ProtectionPreparationResult
    execution: AttackActionExecutionResult
    fate_decline: PcFateDecline


@dataclass(frozen=True, slots=True)
class PcWoundCompletionProof:
    completion: CharacterWoundLifecycleCompletionResult
    fate_decline: PcFateDecline


@dataclass(frozen=True, slots=True)
class PcEnduranceProof:
    request: WoundEnduranceTestRequest
    test_request: TestRequest
    test: TestResult
    result: WoundEnduranceTestResult
    fate_decline: PcFateDecline


@dataclass(frozen=True, slots=True)
class PcHandDropProof:
    source: WoundConsequenceRequest
    die: int
    hand: PcWeaponHand


@dataclass(frozen=True, slots=True)
class PcAttackerStaggerProof:
    source: AttackerStaggerRequest


@dataclass(frozen=True, slots=True)
class PcMinionDefeatProof:
    source: ProfileStateChangeRequest
    decision: MinionDefeatDecision


@dataclass(frozen=True, slots=True)
class PcRecoverProof:
    result: RecoverActionExecutionResult


@dataclass(frozen=True, slots=True)
class PcTurnEndProof:
    result: CombatTurnEndResult
    fate_decline: PcFateDecline | None


PcMeleeProof = (
    CombatTurnStartResult | CombatActionSlotResult | PcAttackProof | PcWoundCompletionProof
    | PcEnduranceProof | PcHandDropProof | PcAttackerStaggerProof | PcMinionDefeatProof
    | PcRecoverProof | PcTurnEndProof | CombatRoundAdvanceResult
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
    unsupported: PcMeleeUnsupported | None = None

    def __post_init__(self):
        validate_pc_melee_scenario_admission(self.source)
        if not isinstance(self.outcome, PcMeleeOutcome) or not isinstance(self.steps, (tuple, list)):
            raise TypeError('PC result needs typed outcome and ordered steps')
        if self.unsupported is not None:
            if not isinstance(self.unsupported,PcMeleeUnsupported):
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
        if self.unsupported != actual_stop:
            raise ValueError('PC unsupported result must preserve its actual pending source')
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
    def executed_actions(self) -> int:
        return sum(isinstance(step.proof, (PcAttackProof, PcRecoverProof)) for step in self.steps)

    @property
    def started_rounds(self) -> int:
        return self.state.round_state.round_number

    @property
    def completed_rounds(self) -> int:
        return self.started_rounds - 1 + int(self.state.round_state.round_complete)


def pc_melee_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | None:
    if state.pending_wound is not None:
        wound = state.pending_wound.wound_result.state.wounds[-1]
        return (PcMeleeUnsupported(state.pending_actor_id, state.pending_wound.request_id,
            'unsupported_wound_effect', wound.sequence, wound.table_total) if 11 <= wound.table_total <= 23 else None)
    for member in state.party:
        unsupported = next((w for w in member.injury.wounds if 11 <= w.table_total <= 23), None)
        if unsupported is not None:
            raise ValueError('unsupported PC injury must preserve its unresolved lifecycle')
    return None


def pc_melee_action_id(state: PcMeleeState, actor_id: str) -> str:
    return f'{state.source.id}:r{state.round_state.round_number}:{actor_id}'


def pc_melee_selected_action(state: PcMeleeState) -> CombatActionKind:
    actor_id = state.round_state.active_turn.actor_id
    if actor_id in state.source.pc_activation_order:
        member = state.participant(actor_id)
        if member.weapon_hand is None or member.injury.conditions.has(Condition.PRONE):
            return CombatActionKind.RECOVER
    return CombatActionKind.ATTACK


def pc_melee_next_actor(state: PcMeleeState) -> str:
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    if state.round_state.next_side is CombatSide.PLAYERS_AND_ALLIES:
        return next(actor for actor in state.source.pc_activation_order
            if not state.participant(actor).injury.dead and actor not in unavailable)
    return next(actor for actor in state.source.enemy_activation_order
        if not state.enemy(actor).state.injury.defeated and actor not in unavailable)


def _pc_test(state: PcMeleeState, actor_id: str, test_id: str, skill: Skill,
             dice_modifiers: tuple[DiceModifier, ...] = ()) -> TestRequest:
    member = state.participant(actor_id)
    pc = state.source.participant(actor_id).pc
    profile = {Skill.MELEE: pc.melee_profile, Skill.DEFENCE: pc.defence_profile,
        Skill.ATHLETICS: pc.athletics_profile, Skill.ENDURANCE: pc.endurance_profile}[skill]
    drained = member.injury.conditions.has(Condition.DRAINED)
    modifiers = tuple(m for m in dice_modifiers if m.amount <= 0) if drained else dice_modifiers
    if (skill is Skill.DEFENCE and pc.weapon is PcMeleeWeapon.SWORD
            and not member.injury.conditions.has(Condition.STAGGERED) and not drained):
        modifiers = (*modifiers, DiceModifier('RULE-EQUIPMENT-003:sword-defence', 1))
    qualities = []
    if skill is not Skill.ENDURANCE and member.injury.conditions.has(Condition.BLINDED):
        qualities.append(QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    qualities.extend(QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)
        for e in member.injury.active_wound_effects
        if isinstance(e, WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM)
    return TestRequest(test_id, profile, modifiers, tuple(qualities))


def pc_after_test(state: PcMeleeState, actor_id: str) -> CharacterInjuryState:
    injury = state.participant(actor_id).injury
    return replace(injury, active_wound_effects=tuple(e for e in injury.active_wound_effects
        if not isinstance(e, WoundRestrictionEffect) or e.restriction is not WoundRestriction.NEXT_TEST_IS_GRIM))


def build_pc_melee_attack(state: PcMeleeState) -> tuple[AttackActionExecutionRequest, ProtectionPreparationRequest]:
    actor = state.round_state.active_turn.actor_id
    pc_attacks = actor in state.source.pc_activation_order
    target = (next(a for a in state.source.participant(actor).target_priority if not state.enemy(a).state.injury.defeated)
        if pc_attacks else next(a for a in state.source.enemy_target_priority if not state.participant(a).injury.dead))
    action_id = pc_melee_action_id(state, actor)
    pc_count = sum(not m.injury.conditions.has(Condition.DEFENCELESS) for m in state.live_party)
    enemy_count = sum(not e.state.injury.conditions.has(Condition.DEFENCELESS) for e in state.live_enemies)
    modifiers = []
    if state.source.facts.outnumbering_bonus_approved and (pc_count > enemy_count if pc_attacks else enemy_count > pc_count):
        modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering', 1))
    if pc_attacks:
        pc = state.source.participant(actor).pc
        member = state.participant(actor)
        target_snapshot = state.enemy(target)
        if target_snapshot.state.injury.conditions.has(Condition.PRONE):
            modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        attacker = _pc_test(state, actor, action_id + ':attack', Skill.MELEE, tuple(modifiers))
        protection_profile = target_snapshot.definition.protection[0]
        defender = TestRequest(action_id + ':protection', protection_profile.test_profile)
        skill = Skill.DEFENCE
        damage, resilience = DamageProfile(pc.strength), target_snapshot.state.current_resilience
        attacker_conditions = member.injury.conditions
        target_injury = target_snapshot.state.injury
        target_armed = True
    else:
        enemy = state.enemy(actor)
        profile = enemy.definition.attacks[0]
        member = state.participant(target)
        if member.injury.conditions.has(Condition.PRONE):
            modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
        if enemy.state.injury.conditions.has(Condition.DRAINED):
            modifiers = [m for m in modifiers if m.amount <= 0]
        attacker = TestRequest(action_id + ':attack', profile.test_profile, tuple(modifiers))
        skill = Skill.DEFENCE if member.weapon_hand is not None else Skill.ATHLETICS
        defender = _pc_test(state, target, action_id + ':protection', skill)
        damage, resilience = profile.damage, state.source.participant(target).pc.resilience
        attacker_conditions = enemy.state.injury.conditions
        target_injury = pc_after_test(state, target)
        target_armed = member.weapon_hand is not None
    attack = AttackRequest(action_id + ':attack-request', attacker, None, DamageImpactSpec(damage,resilience),
        True, attacker_conditions.has(Condition.STAGGERED))
    protection = ProtectionPreparationRequest(action_id + ':prepare-protection', target, attack, Skill.MELEE,
        True, False, target_armed, False, skill, (ProtectionTestOption(target,skill,defender),))
    from towr.domain.protection_models import _expected_protection
    prepared_attack = _expected_protection(protection)[0]
    kernel = KernelAttackRequest(action_id + ':kernel',target,prepared_attack,
        TargetInjuryPolicy.MINION if pc_attacks else TargetInjuryPolicy.PLAYER, target_injury,
        state.source.facts.can_leave_zone,False)
    return AttackActionExecutionRequest(action_id + ':execute',state.round_state,actor,target,1,kernel), protection


def build_pc_melee_recover(state: PcMeleeState) -> RecoverActionExecutionRequest:
    actor = state.round_state.active_turn.actor_id
    member = state.participant(actor)
    action_id = pc_melee_action_id(state, actor)
    target = RecoverConditionTarget(actor,member.injury.conditions,None)
    choice = RecoverStandardChoice(WizardMagicState(),
        staggered_target=target if member.injury.conditions.has(Condition.STAGGERED) else None,
        prone_target=target if member.injury.conditions.has(Condition.PRONE) else None,
        object_interaction=(RecoverObjectInteractionFollowUp(action_id + ':pickup',actor,
            actor + ':weapon',True) if member.weapon_hand is None else None))
    return RecoverActionExecutionRequest(action_id + ':execute',state.round_state,actor,member.injury.conditions,
        bool(state.live_enemies),1,RecoverMode.STANDARD,choice)


def _decline(state: PcMeleeState, actual: PcFateDecline, actor_id: str, source_id: str, window: str):
    if not isinstance(actual,PcFateDecline):
        raise TypeError('PC Fate decision must be typed')
    replace(actual)
    member = state.source.participant(actor_id)
    if actual != PcFateDecline(actor_id,source_id,window,member.fate_policy):
        raise ValueError('Fate decline differs from the actor, window or selected source policy')


def _party_update(state: PcMeleeState, actor_id: str, **changes):
    state.participant(actor_id)
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
    if not isinstance(trace.rerolls,tuple) or not isinstance(trace.applied_rule_ids,tuple):
        raise TypeError('PC Test trace collections must be canonical tuples')
    if any(type(v) is not str or not v for v in trace.applied_rule_ids):
        raise TypeError('PC Test rule IDs must be strings')
    if any(not isinstance(r,RerollTrace) for r in trace.rerolls):
        raise TypeError('PC reroll traces must be typed')
    parameters = _expected_initial_roll_parameters(request)
    for values in (trace.initial_values,trace.final_values):
        if not isinstance(values,tuple) or len(values) != parameters[5] or any(type(v) is not int or not 1 <= v <= 10 for v in values):
            raise ValueError('PC Test has malformed d10 values')
    quality = TestQuality.GRIM if request.quality_modifiers else TestQuality.NORMAL
    indices = tuple(i for i,v in enumerate(trace.initial_values) if v <= parameters[6]) if quality is TestQuality.GRIM else ()
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
    rules = tuple(m.rule_id for mods in (request.dice_modifiers,request.quality_modifiers,
        request.success_modifiers,request.reroll_locks) for m in mods)
    expected = RollTrace(request.id,*parameters[:6],parameters[6],parameters[7],quality,
        trace.initial_values,trace.rerolls,tuple(final),successes,0,successes,rules)
    if trace != expected:
        raise ValueError('PC Test trace is not canonical for its bound request')


def _enemy_update(state: PcMeleeState, actor_id: str, injury: ProfileInjuryState):
    return tuple(replace(e,state=replace(e.state,injury=injury)) if e.state.actor_id == actor_id else e for e in state.enemies)


def _ready(state: PcMeleeState):
    if state.pending or state.pending_wound is not None or pc_melee_unsupported(state) is not None:
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


def validate_pc_melee_source_types(recorded: PcMeleeState, canonical: PcMeleeState) -> None:
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
        if isinstance(pending,(WoundEnduranceTestRequest,WoundConsequenceRequest)):
            replace(pending)
        elif isinstance(pending,AttackerStaggerRequest):
            if type(pending.attack_id) is not str or type(pending.rule_id) is not str:
                raise TypeError('miss follow-up IDs must be strings')
        elif isinstance(pending,ProfileStateChangeRequest):
            if (not isinstance(pending.npc_type,ProfileNpcType)
                    or type(pending.previous_wounds) is not int or type(pending.current_wounds) is not int
                    or type(pending.defeated) is not bool):
                raise TypeError('profile change requires typed integer/bool values')
        else:
            raise TypeError('unsupported pending PC continuation type')
