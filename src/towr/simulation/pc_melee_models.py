"""Indexed, source-bound observations for the bounded PC encounter (ADR-0065)."""
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256

from towr.domain.pc_melee_models import PcMeleeScenario, validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import PcMeleeOutcome


SEED_SCHEME = 'towr:pc-melee-trial:v1'


@dataclass(frozen=True, slots=True)
class PcNpcExitCount:
    """Actual exits observed for one source NPC, distinct from lethal defeat."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC exit count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('NPC exit count must be an integer')
        if self.count < 0:
            raise ValueError('NPC exit count must be nonnegative')


@dataclass(frozen=True, slots=True)
class PcNpcHelpActionCount:
    """Executed Help actions for one source NPC, including explicit zero counts."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC Help count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('NPC Help count must be an integer')
        if self.count < 0:
            raise ValueError('NPC Help count must be nonnegative')


@dataclass(frozen=True, slots=True)
class PcNpcRecoverActionCount:
    """Executed Recover actions for one source NPC, including explicit zero counts."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC Recover count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('NPC Recover count must be an integer')
        if self.count < 0:
            raise ValueError('NPC Recover count must be nonnegative')


@dataclass(frozen=True, slots=True)
class PcNpcWarpedFormCount:
    """Committed end-phase cost/heal activations, independent of actions."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC Warped Form count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('NPC Warped Form count must be an integer')
        if self.count < 0:
            raise ValueError('NPC Warped Form count must be nonnegative')


def validate_npc_warped_form_counts(counts,scenario,*,trials:int,activation_trials:int|None,
                                   actions:int,started_rounds:int) -> None:
    if type(counts) is not tuple:
        raise TypeError('NPC Warped Form counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNpcWarpedFormCount:
            raise TypeError('NPC Warped Form counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts)!=tuple(enemy.state.actor_id for enemy in scenario.enemies):
        raise ValueError('NPC Warped Form counts must cover every source NPC in order')
    total=sum(item.count for item in counts)
    if activation_trials is None:
        activation_trials=int(total>0)
    if type(activation_trials) is not int:
        raise TypeError('NPC Warped Form trial count must be an integer')
    if (not 0<=activation_trials<=trials or not activation_trials<=total<=actions
            or (total>0)!=(activation_trials>0)):
        raise ValueError('NPC Warped Form counts contradict trials/own completed actions')
    actors={policy.actor_id for policy in scenario.npc_warped_form_policies}
    budget=min(started_rounds-(trials-activation_trials),activation_trials*scenario.max_rounds)
    for item in counts:
        if (item.count and item.actor_id not in actors) or item.count>budget:
            raise ValueError('NPC Warped Form count exceeds its selected actor/end-phase budget')


def warped_form_target_budget(scenario,counts,*,pc_targets:bool) -> int:
    """Additional injury opportunities from actual source-bound wave activations."""
    by_actor={item.actor_id:item.count for item in counts}
    pc_ids=set(scenario.pc_activation_order)
    return sum(by_actor[policy.actor_id]*sum((actor in pc_ids)==pc_targets
        for actor in policy.close_actor_ids) for policy in scenario.npc_warped_form_policies)


@dataclass(frozen=True, slots=True)
class PcNpcExtraAttackCount:
    """Executed second-slot Attacks for one source NPC."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC extra Attack count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('NPC extra Attack count must be an integer')
        if self.count < 0:
            raise ValueError('NPC extra Attack count must be nonnegative')


def validate_npc_extra_attack_counts(counts,scenario,*,trials:int,extra_trials:int|None,
                                     actions:int,started_rounds:int) -> None:
    if type(counts) is not tuple:
        raise TypeError('NPC extra Attack counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNpcExtraAttackCount:
            raise TypeError('NPC extra Attack counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts)!=tuple(enemy.state.actor_id for enemy in scenario.enemies):
        raise ValueError('NPC extra Attack counts must cover every source NPC in order')
    total=sum(item.count for item in counts)
    if extra_trials is None:
        extra_trials=int(total>0)
    if type(extra_trials) is not int:
        raise TypeError('NPC extra Attack trial count must be an integer')
    if (not 0<=extra_trials<=trials or not extra_trials<=total or 2*total>actions
            or (total>0)!=(extra_trials>0)):
        raise ValueError('NPC extra Attack counts contradict trials/primary and extra actions')
    budget=min(started_rounds-(trials-extra_trials),extra_trials*scenario.max_rounds)
    for item in counts:
        if (item.count and item.actor_id not in scenario.npc_extra_attack_actor_ids) or item.count>budget:
            raise ValueError('NPC extra Attack count exceeds its selected actor/round budget')


def validate_npc_help_counts(counts,scenario,*,trials:int,help_trials:int|None,
                             actions:int,started_rounds:int) -> None:
    if type(counts) is not tuple:
        raise TypeError('NPC Help counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNpcHelpActionCount:
            raise TypeError('NPC Help counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts)!=tuple(enemy.state.actor_id for enemy in scenario.enemies):
        raise ValueError('NPC Help counts must cover every source NPC in order')
    total=sum(item.count for item in counts)
    if help_trials is None:
        help_trials=int(total>0)
    if type(help_trials) is not int:
        raise TypeError('NPC Help trial count must be an integer')
    if not 0<=help_trials<=trials or not help_trials<=total<=actions or (total>0)!=(help_trials>0):
        raise ValueError('NPC Help counts contradict trials/actions')
    helpers={policy.helper_id for policy in scenario.npc_help_policies}
    # Every non-Help trial still starts at least one round. Each configured NPC
    # can execute at most one ordinary action per started round in this family.
    budget=min(started_rounds-(trials-help_trials),help_trials*scenario.max_rounds)
    for item in counts:
        if (item.count and item.actor_id not in helpers) or item.count>budget:
            raise ValueError('NPC Help count exceeds its configured role/round budget')


def validate_npc_recover_counts(counts,scenario,*,trials:int,recover_trials:int|None,
                             actions:int,started_rounds:int,warped_form_counts) -> None:
    if type(counts) is not tuple:
        raise TypeError('NPC Recover counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNpcRecoverActionCount:
            raise TypeError('NPC Recover counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts)!=tuple(enemy.state.actor_id for enemy in scenario.enemies):
        raise ValueError('NPC Recover counts must cover every source NPC in order')
    total=sum(item.count for item in counts)
    if recover_trials is None:
        recover_trials=int(total>0)
    if type(recover_trials) is not int:
        raise TypeError('NPC Recover trial count must be an integer')
    wave_wound_budget=warped_form_target_budget(scenario,warped_form_counts,pc_targets=False)
    if (not 0<=recover_trials<=trials or not recover_trials<=total<=actions
            or 2*total>actions+wave_wound_budget or (total>0)!=(recover_trials>0)):
        raise ValueError('NPC Recover counts contradict trials/actions')
    actors={policy.actor_id for policy in scenario.npc_flagellant_policies if policy.recover_when_wounded}
    # Every non-Recover trial still starts at least one round. Each configured NPC
    # can execute at most one ordinary action per started round in this family.
    budget=min(started_rounds-(trials-recover_trials),recover_trials*scenario.max_rounds)
    for item in counts:
        if (item.count and item.actor_id not in actors) or item.count>budget:
            raise ValueError('NPC Recover count exceeds its configured role/round budget')


def validate_npc_exit_counts(counts,scenario,*,trials:int,exit_trials:int|None) -> None:
    if type(counts) is not tuple:
        raise TypeError('NPC exit counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNpcExitCount:
            raise TypeError('NPC exit counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts) != tuple(enemy.state.actor_id for enemy in scenario.enemies):
        raise ValueError('NPC exit counts must cover every source NPC in order')
    total=sum(item.count for item in counts)
    if exit_trials is None:
        exit_trials=int(total>0)
    if type(exit_trials) is not int:
        raise TypeError('NPC exit trial count must be an integer')
    if not 0<=exit_trials<=trials:
        raise ValueError('NPC exit trial count contradicts the batch denominator')
    eligible=0
    for enemy,item in zip(scenario.enemies,counts,strict=True):
        allowed=(scenario.npc_broken_exit_policy is not None
            and enemy.definition.id=='pc-book-npc:empire_official_dagger')
        eligible+=int(allowed)
        if item.count>exit_trials or (item.count and not allowed):
            raise ValueError('NPC exit count contradicts the selected source/batch')
    if not exit_trials<=total<=eligible*exit_trials:
        raise ValueError('NPC exit totals contradict the number of trials with an exit')


@dataclass(frozen=True, slots=True)
class PcNearMissBurnCount:
    """New Near Miss burns during this battle, excluding supplied history."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Near Miss count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('Near Miss count must be an integer')
        if self.count < 0:
            raise ValueError('Near Miss count must be nonnegative')


def near_miss_burn_budget(member) -> int:
    if member.near_miss_policy is None:
        return 0
    return max(0, member.fate.rating - member.near_miss_policy.minimum_rating_to_keep)


@dataclass(frozen=True, slots=True)
class PcGloriousSpendCount:
    """New Glorious session spends during this battle, excluding supplied history."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Glorious count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('Glorious count must be an integer')
        if self.count < 0:
            raise ValueError('Glorious count must be nonnegative')


def glorious_spend_budget(member) -> int:
    if member.glorious_policy is None:
        return 0
    return max(0,member.fate.remaining_spends-member.glorious_policy.minimum_remaining_spends)


def validate_glorious_counts(counts, scenario, *, trials: int, spend_trials: int | None) -> None:
    if type(counts) is not tuple:
        raise TypeError('Glorious counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcGloriousSpendCount:
            raise TypeError('Glorious counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts) != tuple(m.actor_id for m in scenario.party):
        raise ValueError('Glorious counts must cover the full source-ordered party')
    total = sum(item.count for item in counts)
    if spend_trials is None:
        spend_trials = int(total > 0)
    if type(spend_trials) is not int:
        raise TypeError('Glorious trial count must be an integer')
    if not 0 <= spend_trials <= trials or spend_trials > total or (total > 0) != (spend_trials > 0):
        raise ValueError('Glorious counts contradict the batch denominator')
    for member,item in zip(scenario.party,counts,strict=True):
        if item.count > spend_trials*glorious_spend_budget(member):
            raise ValueError('Glorious count exceeds the selected session resource budget')


@dataclass(frozen=True, slots=True)
class PcHelpActionCount:
    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Help count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('Help count must be an integer')
        if self.count < 0:
            raise ValueError('Help count must be nonnegative')


def validate_help_counts(counts,scenario,*,trials:int,help_trials:int|None,
                         actions:int,started_rounds:int) -> None:
    from towr.domain.pc_melee_models import PcMeleePolicy
    if type(counts) is not tuple:
        raise TypeError('Help counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcHelpActionCount:
            raise TypeError('Help counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts) != tuple(member.actor_id for member in scenario.party):
        raise ValueError('Help counts must cover the full source-ordered party')
    total = sum(item.count for item in counts)
    if help_trials is None:
        help_trials = int(total>0)
    if type(help_trials) is not int:
        raise TypeError('Help trial count must be an integer')
    if not 0 <= help_trials <= trials or not help_trials <= total <= actions or (total>0)!=(help_trials>0):
        raise ValueError('Help counts contradict trials/actions')
    for member,item in zip(scenario.party,counts,strict=True):
        budget = min(started_rounds-(trials-help_trials),help_trials*scenario.max_rounds) if (
            member.policy is PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF) else 0
        if item.count>budget:
            raise ValueError('Help count exceeds the selected role/turn budget')


@dataclass(frozen=True, slots=True)
class PcAllyRecoverActionCount:
    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('ally Recover count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('ally Recover count must be an integer')
        if self.count < 0:
            raise ValueError('ally Recover count must be nonnegative')


def validate_ally_recover_counts(counts,scenario,*,trials:int,recover_trials:int|None,
                                 actions:int,started_rounds:int) -> None:
    from towr.domain.pc_melee_models import PcMeleePolicy
    if type(counts) is not tuple:
        raise TypeError('ally Recover counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcAllyRecoverActionCount:
            raise TypeError('ally Recover counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts)!=tuple(member.actor_id for member in scenario.party):
        raise ValueError('ally Recover counts must cover the full source-ordered party')
    total=sum(item.count for item in counts)
    if recover_trials is None:
        recover_trials=int(total>0)
    if type(recover_trials) is not int:
        raise TypeError('ally Recover trial count must be an integer')
    if not 0<=recover_trials<=trials or not recover_trials<=total<=actions or (total>0)!=(recover_trials>0):
        raise ValueError('ally Recover counts contradict trials/actions')
    for member,item in zip(scenario.party,counts,strict=True):
        budget=0
        if member.policy is PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF:
            # Fresh PCs start healthy; before the ally's first turn no removable
            # condition can exist (all PC turns precede the NPC side).
            before_ally=scenario.pc_activation_order.index(member.actor_id)<scenario.pc_activation_order.index(
                member.ally_recover_policy.beneficiary_id)
            unavailable_rounds=trials if before_ally else trials-recover_trials
            budget=min(started_rounds-unavailable_rounds,
                recover_trials*(scenario.max_rounds-int(before_ally)))
        if item.count>budget:
            raise ValueError('ally Recover count exceeds the selected role/turn budget')


def validate_near_miss_counts(counts, scenario, *, trials: int,
                              burn_trials: int | None, actions: int) -> None:
    if type(counts) is not tuple:
        raise TypeError('Near Miss counts require a source-ordered tuple')
    for item in counts:
        if type(item) is not PcNearMissBurnCount:
            raise TypeError('Near Miss counts require typed observations')
        replace(item)
    if tuple(item.actor_id for item in counts) != tuple(m.actor_id for m in scenario.party):
        raise ValueError('Near Miss counts must cover the full source-ordered party')
    total = sum(item.count for item in counts)
    if burn_trials is None:
        burn_trials = int(total > 0)
    if type(burn_trials) is not int:
        raise TypeError('Near Miss trial count must be an integer')
    if not 0 <= burn_trials <= trials:
        raise ValueError('Near Miss trial count exceeds the batch')
    if not burn_trials <= total <= actions or (total > 0) != (burn_trials > 0):
        raise ValueError('Near Miss counts contradict trials/actions')
    for member, item in zip(scenario.party, counts, strict=True):
        if item.count > burn_trials * near_miss_burn_budget(member):
            raise ValueError('Near Miss count exceeds the selected resource budget')


def _uint64(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f'{name} must be an integer')
    if not 0 <= value < 1 << 64:
        raise ValueError(f'{name} must be in [0, 2**64)')


def pc_melee_trial_seed(master_seed: int, trial_index: int) -> int:
    _uint64(master_seed, 'master_seed')
    _uint64(trial_index, 'trial_index')
    payload = SEED_SCHEME.encode('ascii') + b'\0' + master_seed.to_bytes(8, 'big') + trial_index.to_bytes(8, 'big')
    return int.from_bytes(sha256(payload).digest(), 'big')


@dataclass(frozen=True, slots=True)
class PcMeleeSimulationRequest:
    scenario: PcMeleeScenario
    master_seed: int
    trials: int

    def __post_init__(self) -> None:
        validate_pc_melee_scenario_admission(self.scenario)
        _uint64(self.master_seed, 'master_seed')
        _uint64(self.trials, 'trials')
        if self.trials == 0:
            raise ValueError('a simulation needs at least one trial')

    def seed_for(self, trial_index: int) -> int:
        _uint64(trial_index, 'trial_index')
        if trial_index >= self.trials:
            raise ValueError('trial index is outside the requested batch')
        return pc_melee_trial_seed(self.master_seed, trial_index)


@dataclass(frozen=True, slots=True)
class PcMeleeTrialRecord:
    """Compact observation; no final owner or journal is retained."""

    source_scenario: PcMeleeScenario
    trial_index: int
    seed: int
    outcome: PcMeleeOutcome
    executed_actions: int
    started_rounds: int
    completed_rounds: int
    defeated_pc_ids: tuple[str, ...]
    near_miss_burn_counts: tuple[PcNearMissBurnCount, ...]
    glorious_spend_counts: tuple[PcGloriousSpendCount, ...]
    help_action_counts: tuple[PcHelpActionCount, ...]
    ally_recover_action_counts: tuple[PcAllyRecoverActionCount, ...]
    npc_exit_counts: tuple[PcNpcExitCount, ...]
    npc_help_action_counts: tuple[PcNpcHelpActionCount, ...]
    npc_extra_attack_counts: tuple[PcNpcExtraAttackCount, ...]
    npc_recover_action_counts: tuple[PcNpcRecoverActionCount, ...]
    npc_warped_form_counts: tuple[PcNpcWarpedFormCount, ...]

    def __post_init__(self) -> None:
        validate_pc_melee_scenario_admission(self.source_scenario)
        _uint64(self.trial_index, 'trial_index')
        if type(self.seed) is not int:
            raise TypeError('trial seed must be an integer')
        if not 0 <= self.seed < 1 << 256:
            raise ValueError('trial seed must be a nonnegative 256-bit integer')
        if not isinstance(self.outcome, PcMeleeOutcome):
            raise TypeError('trial outcome must be a PcMeleeOutcome')
        for name in ('executed_actions', 'started_rounds', 'completed_rounds'):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f'{name} must be an integer')
            if value < 0:
                raise ValueError(f'{name} must be nonnegative')
        if not 1 <= self.started_rounds <= self.source_scenario.max_rounds:
            raise ValueError('started rounds must fit the source budget')
        if not 0 <= self.completed_rounds <= self.started_rounds or self.started_rounds-self.completed_rounds > 1:
            raise ValueError('completed rounds contradict started rounds')
        validate_npc_extra_attack_counts(self.npc_extra_attack_counts,self.source_scenario,trials=1,
            extra_trials=None,actions=self.executed_actions,started_rounds=self.started_rounds)
        extras=sum(item.count for item in self.npc_extra_attack_counts)
        actors = len(self.source_scenario.party) + len(self.source_scenario.enemies)
        if not self.completed_rounds <= self.executed_actions <= actors*self.started_rounds+extras:
            raise ValueError('actions contradict the round/actor budget')
        if self.outcome is PcMeleeOutcome.ROUND_LIMIT and self.completed_rounds != self.source_scenario.max_rounds:
            raise ValueError('round limit must complete the full source budget')
        if self.outcome in (PcMeleeOutcome.OBJECTIVE_ACHIEVED, PcMeleeOutcome.PARTY_DEFEATED) and not self.executed_actions:
            raise ValueError('terminal defeat requires an executed action')
        if type(self.defeated_pc_ids) is not tuple or any(type(actor) is not str for actor in self.defeated_pc_ids):
            raise TypeError('confirmed PC deaths require an ordered tuple of actor IDs')
        ids = tuple(member.actor_id for member in self.source_scenario.party)
        if tuple(actor for actor in ids if actor in self.defeated_pc_ids) != self.defeated_pc_ids:
            raise ValueError('confirmed PC deaths must be a unique source-ordered party subset')
        if (self.defeated_pc_ids == ids) != (self.outcome is PcMeleeOutcome.PARTY_DEFEATED):
            raise ValueError('all PC deaths must agree with the party-defeated outcome')
        validate_npc_warped_form_counts(self.npc_warped_form_counts,self.source_scenario,trials=1,
            activation_trials=None,actions=self.executed_actions,started_rounds=self.started_rounds)
        pc_injury_budget=self.executed_actions+warped_form_target_budget(
            self.source_scenario,self.npc_warped_form_counts,pc_targets=True)
        npc_injury_budget=self.executed_actions+warped_form_target_budget(
            self.source_scenario,self.npc_warped_form_counts,pc_targets=False)
        if len(self.defeated_pc_ids) > pc_injury_budget:
            raise ValueError('confirmed deaths cannot exceed actual source injury opportunities')
        validate_near_miss_counts(self.near_miss_burn_counts, self.source_scenario,
            trials=1, burn_trials=None,
            actions=pc_injury_budget)
        validate_glorious_counts(self.glorious_spend_counts,self.source_scenario,
            trials=1,spend_trials=None)
        validate_help_counts(self.help_action_counts,self.source_scenario,trials=1,help_trials=None,
            actions=self.executed_actions,started_rounds=self.started_rounds)
        validate_ally_recover_counts(self.ally_recover_action_counts,self.source_scenario,trials=1,
            recover_trials=None,actions=self.executed_actions,started_rounds=self.started_rounds)
        validate_npc_help_counts(self.npc_help_action_counts,self.source_scenario,trials=1,
            help_trials=None,actions=self.executed_actions,started_rounds=self.started_rounds)
        validate_npc_recover_counts(self.npc_recover_action_counts,self.source_scenario,trials=1,
            recover_trials=None,actions=self.executed_actions,started_rounds=self.started_rounds,
            warped_form_counts=self.npc_warped_form_counts)
        if sum(item.count for item in (*self.help_action_counts,*self.ally_recover_action_counts,
                *self.npc_help_action_counts,*self.npc_recover_action_counts))+2*extras>self.executed_actions:
            raise ValueError('Help, ally Recover and primary/extra Attacks cannot consume the same action')
        validate_npc_exit_counts(self.npc_exit_counts,self.source_scenario,trials=1,exit_trials=None)
        if sum(item.count for item in self.npc_exit_counts)>npc_injury_budget:
            raise ValueError('NPC exits exceed actual source injury opportunities')


@dataclass(frozen=True, slots=True)
class PcMeleeOutcomeCounts:
    objective_achieved: int
    party_defeated: int
    round_limit: int
    unsupported_path: int

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError('outcome counts must be integers')
            if value < 0:
                raise ValueError('outcome counts must be nonnegative')


@dataclass(frozen=True, slots=True)
class PcMeleeSimulationResult:
    source_request: PcMeleeSimulationRequest
    records: tuple[PcMeleeTrialRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, PcMeleeSimulationRequest):
            raise TypeError('simulation result requires its typed source request')
        replace(self.source_request)
        if not isinstance(self.records, (tuple, list)):
            raise TypeError('records require an ordered tuple or list')
        if not all(isinstance(record, PcMeleeTrialRecord) for record in self.records):
            raise TypeError('records must contain PcMeleeTrialRecord values')
        records = tuple(sorted(self.records, key=lambda record: record.trial_index))
        if len(records) != self.source_request.trials:
            raise ValueError('simulation must account for every requested trial')
        for index, record in enumerate(records):
            replace(record)
            if record.trial_index != index or record.seed != self.source_request.seed_for(index):
                raise ValueError('missing/duplicate trial index or foreign seed')
            if record.source_scenario != self.source_request.scenario:
                raise ValueError('trial belongs to another complete scenario')
        object.__setattr__(self, 'records', records)

    @property
    def outcome_counts(self) -> PcMeleeOutcomeCounts:
        counts = Counter(record.outcome for record in self.records)
        return PcMeleeOutcomeCounts(*(counts[outcome] for outcome in (
            PcMeleeOutcome.OBJECTIVE_ACHIEVED, PcMeleeOutcome.PARTY_DEFEATED,
            PcMeleeOutcome.ROUND_LIMIT, PcMeleeOutcome.UNSUPPORTED_PATH)))

    @property
    def total_action_count(self) -> int:
        return sum(record.executed_actions for record in self.records)

    @property
    def total_started_round_count(self) -> int:
        return sum(record.started_rounds for record in self.records)

    @property
    def total_completed_round_count(self) -> int:
        return sum(record.completed_rounds for record in self.records)
