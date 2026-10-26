"""Pure bounded magic candidate list and aggregate report (ADR-0040)."""
from dataclasses import dataclass, field

from towr.balance.magic_assessment_models import MagicCandidateAssessment, ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.simulation.npc_magic_models import SEED_SCHEME, NpcMagicSimulationRequest


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("magic candidate ID must be a string")
    if not value.strip():
        raise ValueError("magic candidate ID must be non-empty")


@dataclass(frozen=True, slots=True)
class MagicBalanceCandidate:
    candidate_id: str
    scenario: NpcMagicScenario

    def __post_init__(self) -> None:
        _identifier(self.candidate_id)
        if not isinstance(self.scenario, NpcMagicScenario):
            raise TypeError("magic candidate requires an admitted magic scenario")


@dataclass(frozen=True, slots=True)
class MagicBalanceEvaluationRequest:
    candidates: tuple[MagicBalanceCandidate, ...]
    master_seed: int
    trials_per_candidate: int
    max_total_trials: int
    window: ObjectiveRateWindow
    top_k: int
    simulation_requests: tuple[NpcMagicSimulationRequest, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, (tuple, list)):
            raise TypeError("magic candidates must be an ordered tuple or list")
        candidates = tuple(self.candidates)
        if not candidates:
            raise ValueError("magic evaluation requires at least one candidate")
        if not all(isinstance(item, MagicBalanceCandidate) for item in candidates):
            raise TypeError("magic evaluation requires typed magic candidates")
        if len({item.candidate_id for item in candidates}) != len(candidates):
            raise ValueError("magic candidate IDs must be unique")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("magic evaluation requires a typed objective window")
        for name in ("max_total_trials", "top_k"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
            if value < 1:
                raise ValueError(f"{name} must be positive")
        first = candidates[0].scenario
        if any(item.scenario.perspective_side is not first.perspective_side
               or item.scenario.max_rounds != first.max_rounds for item in candidates):
            raise ValueError("magic candidates must share perspective side and round budget")
        # Existing constructors validate the common seed/N, without executing trials.
        requests = tuple(NpcMagicSimulationRequest(item.scenario, self.master_seed, self.trials_per_candidate)
                         for item in candidates)
        if len(candidates) * self.trials_per_candidate > self.max_total_trials:
            raise ValueError("magic candidate evaluation exceeds max_total_trials")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "simulation_requests", requests)

    @property
    def planned_trials(self) -> int:
        return len(self.candidates) * self.trials_per_candidate


@dataclass(frozen=True, slots=True)
class MagicBalanceCandidateResult:
    candidate_id: str
    assessment: MagicCandidateAssessment

    def __post_init__(self) -> None:
        _identifier(self.candidate_id)
        if not isinstance(self.assessment, MagicCandidateAssessment):
            raise TypeError("magic candidate result requires a typed magic assessment")


@dataclass(frozen=True, slots=True)
class MagicBalanceEvaluationResult:
    source_request: MagicBalanceEvaluationRequest
    candidates: tuple[MagicBalanceCandidateResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MagicBalanceEvaluationRequest):
            raise TypeError("magic evaluation result requires its typed source request")
        if not isinstance(self.candidates, (tuple, list)):
            raise TypeError("magic candidate rows must be an ordered tuple or list")
        candidates = tuple(self.candidates)
        if not all(isinstance(item, MagicBalanceCandidateResult) for item in candidates):
            raise TypeError("magic evaluation result requires typed magic candidate rows")
        source = self.source_request
        if len(candidates) != len(source.candidates):
            raise ValueError("magic evaluation result must contain every candidate")
        for item, candidate, simulation in zip(candidates, source.candidates, source.simulation_requests):
            if (item.candidate_id != candidate.candidate_id
                    or item.assessment.source_request != simulation
                    or item.assessment.window != source.window):
                raise ValueError("magic candidate row has a foreign source/window or incorrect order")
        object.__setattr__(self, "candidates", candidates)

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        matching = (item for item in self.candidates if item.assessment.window_match is True)
        # Stable sort retains the original input order for exact Fraction ties.
        ordered = sorted(matching, key=lambda item: abs(
            item.assessment.objective_achieved_rate - self.source_request.window.target))
        return tuple(item.candidate_id for item in ordered[:self.source_request.top_k])

    @property
    def total_trials(self) -> int:
        return sum(item.assessment.summary.trials for item in self.candidates)

    @property
    def seed_scheme(self) -> str:
        return SEED_SCHEME
