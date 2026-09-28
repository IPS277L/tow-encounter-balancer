from dataclasses import dataclass, field

from towr.balance.ranged_assessment_models import ObjectiveRateWindow, RangedCandidateAssessment
from towr.domain.npc_ranged_scenario_models import NpcRangedScenario
from towr.simulation.npc_ranged_models import SEED_SCHEME, NpcRangedSimulationRequest


@dataclass(frozen=True, slots=True)
class RangedBalanceCandidate:
    candidate_id: str
    scenario: NpcRangedScenario

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("balance candidate requires a non-empty ID")
        if not isinstance(self.scenario, NpcRangedScenario):
            raise TypeError("balance candidate requires an admitted simulator scenario")


@dataclass(frozen=True, slots=True)
class RangedBalanceEvaluationRequest:
    candidates: tuple[RangedBalanceCandidate, ...]
    master_seed: int
    trials_per_candidate: int
    max_total_trials: int
    window: ObjectiveRateWindow
    top_k: int
    simulation_requests: tuple[NpcRangedSimulationRequest, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        if not candidates:
            raise ValueError("balance evaluation requires at least one candidate")
        if not all(isinstance(item, RangedBalanceCandidate) for item in candidates):
            raise TypeError("balance evaluation requires typed candidates")
        if len({item.candidate_id for item in candidates}) != len(candidates):
            raise ValueError("balance candidate IDs must be unique")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("balance evaluation requires a typed objective window")
        for name, value in (("max_total_trials", self.max_total_trials), ("top_k", self.top_k)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        first = candidates[0].scenario
        if any(item.scenario.perspective_side is not first.perspective_side
               or item.scenario.initial.max_rounds != first.initial.max_rounds for item in candidates):
            raise ValueError("candidates must share perspective side and round budget")
        # Existing constructors validate the common seed/trials before any execution.
        requests = tuple(NpcRangedSimulationRequest(item.scenario, self.master_seed, self.trials_per_candidate)
                         for item in candidates)
        if len(candidates) * self.trials_per_candidate > self.max_total_trials:
            raise ValueError("candidate evaluation exceeds max_total_trials")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "simulation_requests", requests)

    @property
    def planned_trials(self) -> int:
        return len(self.candidates) * self.trials_per_candidate


@dataclass(frozen=True, slots=True)
class RangedBalanceCandidateResult:
    candidate_id: str
    assessment: RangedCandidateAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("candidate result requires a non-empty ID")
        if not isinstance(self.assessment, RangedCandidateAssessment):
            raise TypeError("candidate result requires a typed assessment")


@dataclass(frozen=True, slots=True)
class RangedBalanceEvaluationResult:
    source_request: RangedBalanceEvaluationRequest
    candidates: tuple[RangedBalanceCandidateResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RangedBalanceEvaluationRequest):
            raise TypeError("evaluation result requires its typed request")
        candidates = tuple(self.candidates)
        if not all(isinstance(item, RangedBalanceCandidateResult) for item in candidates):
            raise TypeError("evaluation result requires typed candidate results")
        source = self.source_request
        if len(candidates) != len(source.candidates):
            raise ValueError("evaluation result must contain every candidate")
        for item, candidate, simulation in zip(candidates, source.candidates, source.simulation_requests):
            if (item.candidate_id != candidate.candidate_id
                    or item.assessment.source_request != simulation
                    or item.assessment.window != source.window):
                raise ValueError("candidate result has a foreign source/window or incorrect order")
        object.__setattr__(self, "candidates", candidates)

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        eligible = (item for item in self.candidates if item.assessment.window_match is True)
        # Python's stable sort preserves the input order for exact ties.
        ordered = sorted(eligible, key=lambda item: abs(
            item.assessment.objective_achieved_rate - self.source_request.window.target))
        return tuple(item.candidate_id for item in ordered[:self.source_request.top_k])

    @property
    def total_trials(self) -> int:
        return sum(item.assessment.summary.trials for item in self.candidates)

    @property
    def seed_scheme(self) -> str:
        return SEED_SCHEME
