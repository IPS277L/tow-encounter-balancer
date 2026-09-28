from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from towr.domain.npc_ranged_scenario_models import NpcRangedScenario
from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome


SEED_SCHEME = "towr:npc-ranged-trial:v1"
_UINT64_LIMIT = 1 << 64


def _uint64(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value < _UINT64_LIMIT:
        raise ValueError(f"{name} must be in [0, 2**64)")


def npc_ranged_trial_seed(master_seed: int, trial_index: int) -> int:
    """Stable v1 SHA-256 derivation, independent of batch size and scheduling."""
    _uint64(master_seed, "master_seed")
    _uint64(trial_index, "trial_index")
    payload = SEED_SCHEME.encode("ascii") + b"\0" + master_seed.to_bytes(8, "big") + trial_index.to_bytes(8, "big")
    return int.from_bytes(sha256(payload).digest(), "big")


@dataclass(frozen=True, slots=True)
class NpcRangedSimulationRequest:
    scenario: NpcRangedScenario
    master_seed: int
    trials: int

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, NpcRangedScenario):
            raise TypeError("simulation requires an admitted NpcRangedScenario")
        _uint64(self.master_seed, "master_seed")
        _uint64(self.trials, "trials")
        if self.trials == 0:
            raise ValueError("simulation requires at least one trial")

    def seed_for(self, trial_index: int) -> int:
        _uint64(trial_index, "trial_index")
        if trial_index >= self.trials:
            raise ValueError("trial index is outside the requested batch")
        return npc_ranged_trial_seed(self.master_seed, trial_index)


@dataclass(frozen=True, slots=True)
class NpcRangedTrialSummary:
    """Compact observation; not a replacement for the full source journal."""

    trial_index: int
    seed: int
    outcome: NpcRangedScenarioOutcome
    executed_attack_count: int
    visited_round_count: int

    def __post_init__(self) -> None:
        _uint64(self.trial_index, "trial_index")
        if type(self.seed) is not int or not 0 <= self.seed < 1 << 256:
            raise ValueError("trial seed must be a 256-bit non-negative integer")
        if not isinstance(self.outcome, NpcRangedScenarioOutcome):
            raise TypeError("trial outcome must be typed")
        for value in (self.executed_attack_count, self.visited_round_count):
            if type(value) is not int or value < 0:
                raise ValueError("trial counters must be non-negative integers")
        if self.visited_round_count == 0:
            raise ValueError("a completed trial must have visited a round")
        if (self.outcome in (NpcRangedScenarioOutcome.OBJECTIVE_ACHIEVED, NpcRangedScenarioOutcome.SIDE_DEFEATED)
                and self.executed_attack_count == 0):
            raise ValueError("terminal defeat requires at least one Attack")


@dataclass(frozen=True, slots=True)
class NpcRangedOutcomeCounts:
    objective_achieved: int
    side_defeated: int
    round_limit: int
    unsupported_path: int

    def __post_init__(self) -> None:
        for count in (self.objective_achieved, self.side_defeated, self.round_limit, self.unsupported_path):
            if type(count) is not int or count < 0:
                raise ValueError("outcome counts must be non-negative integers")


@dataclass(frozen=True, slots=True)
class NpcRangedSimulationResult:
    source_request: NpcRangedSimulationRequest
    trials: tuple[NpcRangedTrialSummary, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRangedSimulationRequest):
            raise TypeError("simulation result requires its typed source request")
        trials = tuple(self.trials)
        if not all(isinstance(item, NpcRangedTrialSummary) for item in trials):
            raise TypeError("simulation trials must be typed summaries")
        if len(trials) != self.source_request.trials:
            raise ValueError("simulation result must contain every requested trial")
        trials = tuple(sorted(trials, key=lambda item: item.trial_index))
        budget = self.source_request.scenario.initial.max_rounds
        actors = len(self.source_request.scenario.initial.current.actor_order)
        for index, trial in enumerate(trials):
            if trial.trial_index != index or trial.seed != self.source_request.seed_for(index):
                raise ValueError("simulation trial has a missing/duplicate index or foreign seed")
            if (trial.visited_round_count > budget
                    or trial.executed_attack_count > actors * trial.visited_round_count):
                raise ValueError("trial counters exceed the scenario budget")
            if trial.outcome is NpcRangedScenarioOutcome.ROUND_LIMIT and trial.visited_round_count != budget:
                raise ValueError("ROUND_LIMIT must reach the global scenario budget")
        object.__setattr__(self, "trials", trials)

    @property
    def outcome_counts(self) -> NpcRangedOutcomeCounts:
        counts = Counter(item.outcome for item in self.trials)
        return NpcRangedOutcomeCounts(
            counts[NpcRangedScenarioOutcome.OBJECTIVE_ACHIEVED], counts[NpcRangedScenarioOutcome.SIDE_DEFEATED],
            counts[NpcRangedScenarioOutcome.ROUND_LIMIT], counts[NpcRangedScenarioOutcome.UNSUPPORTED_PATH],
        )

    @property
    def total_attack_count(self) -> int:
        return sum(item.executed_attack_count for item in self.trials)

    @property
    def total_visited_round_count(self) -> int:
        return sum(item.visited_round_count for item in self.trials)

    @property
    def mean_attack_count(self) -> float:
        return self.total_attack_count / len(self.trials)

    @property
    def mean_visited_round_count(self) -> float:
        return self.total_visited_round_count / len(self.trials)
