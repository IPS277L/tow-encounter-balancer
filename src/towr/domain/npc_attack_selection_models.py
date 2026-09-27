from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import (
    NPC_OUTSIDE_OPTIMUM_RULE_ID, NpcAttackPreparationRequest, NpcAttackPreparationResult,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest, NpcRosterAttackState
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionTestOption
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import FollowUpRequest
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import CombatRoundState


class NpcAttackSelectionBlock(str, Enum):
    PENDING_FOLLOW_UPS = "pending_follow_ups"
    NO_ACTIVE_TURN = "no_active_turn"
    ANOTHER_ACTIVE_ACTOR = "another_active_actor"
    UNSUPPORTED_ACTOR = "unsupported_actor"
    ACTOR_DEFEATED = "actor_defeated"
    SLOT_UNAVAILABLE = "slot_unavailable"
    SLOT_EXECUTED = "slot_executed"
    EXECUTION_CONSUMED = "execution_consumed"
    NO_CANDIDATE = "no_candidate"


class NpcAttackCandidateRejection(str, Enum):
    ATTACK_UNAVAILABLE = "attack_unavailable"
    SELF_TARGET = "self_target"
    UNSUPPORTED_TARGET = "unsupported_target"
    TARGET_DEFEATED = "target_defeated"
    TARGET_NOT_IN_ROUND = "target_not_in_round"
    UNSUPPORTED_EFFECTS = "unsupported_effects"
    ATTACK_CONTEXT = "attack_context"
    PROTECTION_CONTEXT = "protection_context"


@dataclass(frozen=True, slots=True)
class NpcAttackCandidate:
    id: str
    attack_profile_id: str
    target_id: str
    target_range: RangedWeaponRange
    has_enemy_in_close_range: bool
    range_approved_by_gm: bool
    defender_is_aware: bool
    protection_skill: Skill | None
    protection_options: tuple[ProtectionTestOption, ...]
    can_target_leave_zone: bool
    target_has_given_ground_this_round: bool
    dice_modifiers: tuple[DiceModifier, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.id, self.attack_profile_id, self.target_id):
            _identifier(value)
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError("candidate range must be a RangedWeaponRange")
        for value in (self.has_enemy_in_close_range, self.range_approved_by_gm, self.defender_is_aware,
                      self.can_target_leave_zone, self.target_has_given_ground_this_round):
            if not isinstance(value, bool):
                raise TypeError("candidate context requires explicit booleans")
        if self.protection_skill is not None and not isinstance(self.protection_skill, Skill):
            raise TypeError("candidate protection_skill must be a Skill or None")
        options = tuple(self.protection_options)
        if not all(isinstance(item, ProtectionTestOption) for item in options):
            raise TypeError("candidate protection options must be typed")
        if any(item.defender_id != self.target_id for item in options):
            raise ValueError("candidate Protection belongs to another target")
        if len({item.skill for item in options}) != len(options) or len({item.test.id for item in options}) != len(options):
            raise ValueError("candidate Protection skills and Test IDs must be unique")
        modifiers = tuple(self.dice_modifiers)
        if not all(isinstance(item, DiceModifier) for item in modifiers):
            raise TypeError("candidate dice modifiers must be typed")
        if any(item.rule_id == NPC_OUTSIDE_OPTIMUM_RULE_ID for item in modifiers):
            raise ValueError("NPC range modifier is owned by preparation")
        object.__setattr__(self, "protection_options", options)
        object.__setattr__(self, "dice_modifiers", modifiers)

    def attack_preparation_request(self, source: NpcAttackSelectionRequest) -> NpcAttackPreparationRequest:
        actor = source.state.roster.participant(source.actor_id)
        target = source.state.roster.participant(self.target_id)
        return NpcAttackPreparationRequest(
            id=source.id + ":prepare", attack_id=source.id + ":attack", attacker_test_id=source.id + ":attack-test",
            snapshot=actor.attack_snapshot(source.id + ":availability"), selected_attack_id=self.attack_profile_id,
            target_id=self.target_id, target_range=self.target_range, target_resilience=target.state.current_resilience,
            has_enemy_in_close_range=self.has_enemy_in_close_range,
            attacker_is_staggered=actor.state.injury.conditions.has(Condition.STAGGERED),
            range_approved_by_gm=self.range_approved_by_gm, dice_modifiers=self.dice_modifiers,
        )

    def protection_preparation_request(
        self, source: NpcAttackSelectionRequest, npc: NpcAttackPreparationResult,
    ) -> ProtectionPreparationRequest:
        target = source.state.roster.participant(self.target_id)
        return ProtectionPreparationRequest(
            id=source.id + ":protect", defender_id=self.target_id, attack=npc.attack,
            attack_skill=npc.selected_profile.skill, defender_is_aware=self.defender_is_aware,
            defender_is_defenceless=target.state.injury.conditions.has(Condition.DEFENCELESS),
            defender_wields_weapon=target.state.wields_weapon, defender_holds_shield=target.state.holds_shield,
            selected_skill=self.protection_skill, options=self.protection_options,
        )


@dataclass(frozen=True, slots=True)
class NpcAttackSelectionRequest:
    id: str
    state: NpcRosterAttackState
    round_state: CombatRoundState
    actor_id: str
    slot_index: int
    candidates: tuple[NpcAttackCandidate, ...]
    pending_follow_ups: tuple[FollowUpRequest, ...]

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        if not isinstance(self.state, NpcRosterAttackState) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError("selection requires typed roster and round snapshots")
        if not isinstance(self.slot_index, int) or isinstance(self.slot_index, bool):
            raise TypeError("slot_index must be an integer")
        if self.slot_index not in (1, 2):
            raise ValueError("slot_index must be 1 or 2")
        candidates = tuple(self.candidates)
        if not all(isinstance(item, NpcAttackCandidate) for item in candidates):
            raise TypeError("candidates must contain NpcAttackCandidate values")
        if len({item.id for item in candidates}) != len(candidates):
            raise ValueError("candidate IDs must be unique")
        pending = tuple(self.pending_follow_ups)
        if not all(isinstance(item, FollowUpRequest) for item in pending):
            raise TypeError("pending follow-ups must be typed")
        actor = self.state.roster.participant(self.actor_id)
        if actor.turn_participant not in self.round_state.participants:
            raise ValueError("selection actor/side does not match the round")
        profiles = {profile.id for profile in actor.definition.attacks}
        # Malformed source data is an error even after a valid first candidate.
        for candidate in candidates:
            if candidate.attack_profile_id not in profiles:
                raise ValueError("candidate names an unknown attack profile")
            target = self.state.roster.participant(candidate.target_id)
            protection = {profile.skill: profile.test_profile for profile in target.definition.protection}
            if any(option.test.profile != protection.get(option.skill) for option in candidate.protection_options):
                raise ValueError("candidate Protection profile does not match current roster")
            if any(option.test.id == self.id + ":attack-test" for option in candidate.protection_options):
                raise ValueError("candidate Protection Test ID collides with attack Test ID")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "pending_follow_ups", pending)

    @property
    def execution_id(self) -> str:
        return self.id + ":execution"


@dataclass(frozen=True, slots=True)
class RejectedNpcAttackCandidate:
    candidate_id: str
    reason: NpcAttackCandidateRejection
    detail: str = ""

    def __post_init__(self) -> None:
        _identifier(self.candidate_id)
        if not isinstance(self.reason, NpcAttackCandidateRejection) or not isinstance(self.detail, str):
            raise TypeError("candidate rejection requires typed reason and string detail")


@dataclass(frozen=True, slots=True)
class NpcAttackSelectionResult:
    source_request: NpcAttackSelectionRequest
    selected_candidate: NpcAttackCandidate | None
    execution_request: NpcRosterAttackExecutionRequest | None
    rejected: tuple[RejectedNpcAttackCandidate, ...]
    blocked_reason: NpcAttackSelectionBlock | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcAttackSelectionRequest):
            raise TypeError("selection result requires its source request")
        rejected = tuple(self.rejected)
        if not all(isinstance(item, RejectedNpcAttackCandidate) for item in rejected):
            raise TypeError("selection rejections must be typed")
        source = self.source_request
        if tuple(item.candidate_id for item in rejected) != tuple(c.id for c in source.candidates[:len(rejected)]):
            raise ValueError("rejections must preserve candidate preference order")
        if self.selected_candidate is None:
            if self.execution_request is not None or not isinstance(self.blocked_reason, NpcAttackSelectionBlock):
                raise ValueError("no selection requires a reason and no executable request")
            expected_count = len(source.candidates) if self.blocked_reason is NpcAttackSelectionBlock.NO_CANDIDATE else 0
            if len(rejected) != expected_count:
                raise ValueError("blocked selection has inconsistent candidate rejections")
        else:
            if self.blocked_reason is not None or not isinstance(self.execution_request, NpcRosterAttackExecutionRequest):
                raise ValueError("selected candidate requires an executable request and no block")
            if len(rejected) >= len(source.candidates) or self.selected_candidate != source.candidates[len(rejected)]:
                raise ValueError("selected candidate must follow rejected preference prefix")
            selected, prepared = self.selected_candidate, self.execution_request.preparation
            execution = self.execution_request.execution
            if (source.pending_follow_ups or self.execution_request.state != source.state
                    or execution.state != source.round_state or execution.actor_id != source.actor_id
                    or execution.slot_index != source.slot_index or execution.id != source.execution_id
                    or execution.target_id != selected.target_id
                    or execution.kernel_request.id != source.id + ":kernel"
                    or execution.kernel_request.can_target_leave_zone != selected.can_target_leave_zone
                    or execution.kernel_request.target_has_given_ground_this_round != selected.target_has_given_ground_this_round
                    or prepared.npc_attack.source_request != selected.attack_preparation_request(source)
                    or prepared.protection.source_request != selected.protection_preparation_request(source, prepared.npc_attack)):
                raise ValueError("selected execution does not match exact source/candidate context")
        object.__setattr__(self, "rejected", rejected)

    @property
    def pending_follow_ups(self) -> tuple[FollowUpRequest, ...]:
        return self.source_request.pending_follow_ups


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("selection identifiers must be strings")
    if not value.strip():
        raise ValueError("selection identifiers must not be empty")
