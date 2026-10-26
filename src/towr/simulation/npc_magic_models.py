"""Independent magic trial inputs and compact observations (ADR-0038)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome


SEED_SCHEME = "towr:npc-magic-trial:v1"
_UINT64_LIMIT = 1 << 64


def _nonnegative_integer(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _uint64(value: int, name: str) -> None:
    _nonnegative_integer(value, name)
    if value >= _UINT64_LIMIT:
        raise ValueError(f"{name} must be in [0, 2**64)")


def npc_magic_trial_seed(master_seed: int, trial_index: int) -> int:
    """Derive a v1 seed independently of scenario IDs, batch size and order."""
    _uint64(master_seed, "master_seed")
    _uint64(trial_index, "trial_index")
    payload = (SEED_SCHEME.encode("ascii") + b"\0"
               + master_seed.to_bytes(8, "big") + trial_index.to_bytes(8, "big"))
    return int.from_bytes(sha256(payload).digest(), "big")


@dataclass(frozen=True, slots=True)
class NpcMagicSimulationRequest:
    scenario: NpcMagicScenario
    master_seed: int
    trials: int

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, NpcMagicScenario):
            raise TypeError("magic simulation requires an admitted NpcMagicScenario")
        _uint64(self.master_seed, "master_seed")
        _uint64(self.trials, "trials")
        if self.trials == 0:
            raise ValueError("magic simulation requires at least one trial")

    def seed_for(self, trial_index: int) -> int:
        _uint64(trial_index, "trial_index")
        if trial_index >= self.trials:
            raise ValueError("trial index is outside the requested magic batch")
        return npc_magic_trial_seed(self.master_seed, trial_index)


@dataclass(frozen=True, slots=True)
class NpcMagicTrialRecord:
    """Full immutable input and scalars, without a battle result or journal."""

    source_scenario: NpcMagicScenario
    trial_index: int
    seed: int
    outcome: NpcMagicScenarioOutcome
    executed_action_count: int
    started_round_count: int
    completed_round_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_scenario, NpcMagicScenario):
            raise TypeError("magic record requires its full typed source scenario")
        _uint64(self.trial_index, "trial_index")
        _nonnegative_integer(self.seed, "seed")
        if self.seed >= 1 << 256:
            raise ValueError("trial seed must be in [0, 2**256)")
        if not isinstance(self.outcome, NpcMagicScenarioOutcome):
            raise TypeError("magic record requires a magic outcome enum")
        for name in ("executed_action_count", "started_round_count", "completed_round_count"):
            _nonnegative_integer(getattr(self, name), name)
        started, completed = self.started_round_count, self.completed_round_count
        actions = self.executed_action_count
        budget = self.source_scenario.max_rounds
        actors = len(self.source_scenario.activation_order)
        if not 1 <= started <= budget:
            raise ValueError("started rounds must fit the magic scenario budget")
        if not 0 <= completed <= started or started - completed > 1:
            raise ValueError("completed rounds contradict started rounds")
        if not completed <= actions <= actors * started:
            raise ValueError("actions contradict completed rounds or available slots")
        if (self.outcome in (NpcMagicScenarioOutcome.OBJECTIVE_ACHIEVED,
                             NpcMagicScenarioOutcome.PERSPECTIVE_DEFEATED) and actions == 0):
            raise ValueError("terminal defeat requires an executed action")
        if (self.outcome is NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
                and (started != budget or completed != budget)):
            raise ValueError("ROUND_LIMIT_REACHED requires the full completed budget")


@dataclass(frozen=True, slots=True)
class NpcMagicOutcomeCounts:
    objective_achieved: int
    perspective_defeated: int
    round_limit_reached: int
    unsupported_path: int

    def __post_init__(self) -> None:
        for name in ("objective_achieved", "perspective_defeated", "round_limit_reached", "unsupported_path"):
            _nonnegative_integer(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class NpcMagicSimulationResult:
    source_request: NpcMagicSimulationRequest
    trials: tuple[NpcMagicTrialRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcMagicSimulationRequest):
            raise TypeError("magic result requires its typed source request")
        if not isinstance(self.trials, (tuple, list)):
            raise TypeError("magic trials must be an ordered tuple or list")
        trials = tuple(self.trials)
        if not all(isinstance(item, NpcMagicTrialRecord) for item in trials):
            raise TypeError("magic trials must contain only typed magic records")
        if len(trials) != self.source_request.trials:
            raise ValueError("magic result must contain every requested trial")
        trials = tuple(sorted(trials, key=lambda item: item.trial_index))
        for index, trial in enumerate(trials):
            if trial.trial_index != index:
                raise ValueError("magic result has a missing, duplicate or foreign index")
            if trial.seed != self.source_request.seed_for(index):
                raise ValueError("magic record seed does not match its parent request")
            if trial.source_scenario != self.source_request.scenario:
                raise ValueError("magic record belongs to a different full scenario")
        object.__setattr__(self, "trials", trials)

    @property
    def outcome_counts(self) -> NpcMagicOutcomeCounts:
        counts = Counter(item.outcome for item in self.trials)
        return NpcMagicOutcomeCounts(
            counts[NpcMagicScenarioOutcome.OBJECTIVE_ACHIEVED],
            counts[NpcMagicScenarioOutcome.PERSPECTIVE_DEFEATED],
            counts[NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED],
            counts[NpcMagicScenarioOutcome.UNSUPPORTED_PATH],
        )

    @property
    def total_action_count(self) -> int:
        return sum(item.executed_action_count for item in self.trials)

    @property
    def total_started_round_count(self) -> int:
        return sum(item.started_round_count for item in self.trials)

    @property
    def total_completed_round_count(self) -> int:
        return sum(item.completed_round_count for item in self.trials)
