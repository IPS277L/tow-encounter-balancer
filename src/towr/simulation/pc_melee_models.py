"""Indexed, source-bound observations for the bounded PC encounter (ADR-0065)."""
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256

from towr.domain.pc_melee_models import PcMeleeScenario, validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import PcMeleeOutcome


SEED_SCHEME = 'towr:pc-melee-trial:v1'


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
    from towr.domain.pc_melee_models import PcFatePolicy
    if member.fate_policy is PcFatePolicy.DECLINE_OPTIONAL_FATE:
        return 0
    return max(0, member.fate.rating - member.near_miss_policy.minimum_rating_to_keep)


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
        actors = len(self.source_scenario.party) + len(self.source_scenario.enemies)
        if not self.completed_rounds <= self.executed_actions <= actors*self.started_rounds:
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
        if len(self.defeated_pc_ids) > self.executed_actions:
            raise ValueError('confirmed deaths cannot exceed executed ordinary attacks')
        validate_near_miss_counts(self.near_miss_burn_counts, self.source_scenario,
            trials=1, burn_trials=None,
            actions=self.executed_actions)


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
