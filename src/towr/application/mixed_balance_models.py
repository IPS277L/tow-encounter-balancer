"""Immutable external command and aggregate result; no JSON or execution."""
from dataclasses import dataclass

from towr.application.mixed_candidate_generation_models import (
    MixedCandidateGenerationRequest, MixedCandidateGenerationResult,
)
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.balance.mixed_staged_evaluation_models import MixedStagedEvaluationResult


@dataclass(frozen=True, slots=True)
class MixedBalanceCommand:
    request_id: str
    generation_request: MixedCandidateGenerationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("balance command requires a non-empty request ID")
        if not isinstance(self.generation_request, MixedCandidateGenerationRequest):
            raise TypeError("balance command requires a typed generation request")
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError("balance command requires typed execution options")
        if not isinstance(self.definition_order, (tuple, list)):
            raise TypeError("definition order requires an ordered sequence")
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError("definition order requires non-empty IDs")
        roster = self.generation_request.template_scenario.initial.current.state.roster
        if len(set(order)) != len(order) or set(order) != {p.definition.id for p in roster.participants}:
            raise ValueError("definition order must contain every used definition exactly once")
        object.__setattr__(self, "definition_order", order)


@dataclass(frozen=True, slots=True)
class MixedBalanceResult:
    generation_result: MixedCandidateGenerationResult
    evaluation_result: MixedStagedEvaluationResult

    def __post_init__(self) -> None:
        if not isinstance(self.generation_result, MixedCandidateGenerationResult):
            raise TypeError("balance result requires a typed generation result")
        if not isinstance(self.evaluation_result, MixedStagedEvaluationResult):
            raise TypeError("balance result requires a typed staged evaluation result")
        if self.evaluation_result.source_request != self.generation_result.evaluation_request:
            raise ValueError("balance evaluation must belong to the exact generated request")
