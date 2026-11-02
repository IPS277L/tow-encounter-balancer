"""Immutable magic balance boundary inputs and aggregate source chain (ADR-0043)."""
from dataclasses import dataclass, replace

from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest, MagicCandidateGenerationResult,
    _validate_generation_policy_types, _validate_generation_source,
)
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationRequest, MagicStagedEvaluationResult
from towr.domain.npc_magic_scenario_models import NpcMagicScenario


@dataclass(frozen=True, slots=True)
class MagicBalanceCommand:
    request_id: str
    generation_request: MagicCandidateGenerationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]
    schema_version: str = '1'

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str):
            raise TypeError('magic schema version must be a string')
        if self.schema_version not in ('1', '2', '3', '4', '5'):
            raise ValueError('unsupported magic schema version')
        if not isinstance(self.request_id, str):
            raise TypeError('magic balance request ID must be a string')
        if not self.request_id.strip():
            raise ValueError('magic balance request ID must not be blank')
        if not isinstance(self.generation_request, MagicCandidateGenerationRequest):
            raise TypeError('balance command requires a typed magic generation request')
        _validate_generation_source(self.generation_request)
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError('balance command requires typed execution options')
        if not isinstance(self.definition_order, (tuple, list)):
            raise TypeError('definition order requires an ordered tuple or list')
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError('definition order requires non-empty IDs')
        roster = self.generation_request.template_scenario.initial.roster
        if len(set(order)) != len(order) or set(order) != {p.definition.id for p in roster.participants}:
            raise ValueError('definition order must contain every used definition exactly once')
        object.__setattr__(self, 'definition_order', order)


@dataclass(frozen=True, slots=True)
class MagicBalanceResult:
    generation_result: MagicCandidateGenerationResult
    evaluation_result: MagicStagedEvaluationResult

    def __post_init__(self) -> None:
        if not isinstance(self.generation_result, MagicCandidateGenerationResult):
            raise TypeError('balance result requires a typed magic generation result')
        if not isinstance(self.evaluation_result, MagicStagedEvaluationResult):
            raise TypeError('balance result requires a typed magic staged evaluation result')
        _validate_generation_result_source(self.generation_result)
        _validate_staged_result_source(self.evaluation_result)
        if self.evaluation_result.source_request != self.generation_result.evaluation_request:
            raise ValueError('balance evaluation must belong to the exact generated request')


def _validate_scenario_source(scenario: NpcMagicScenario) -> None:
    replace(scenario)
    replace(scenario.facts)
    _validate_generation_policy_types(scenario, scenario.miscast_continuation,
                                      scenario.stationary_wound_continuation,
                                      scenario.repeated_leg_spasm_continuation,
                                      scenario.crushed_rib_continuation)


def _validate_staged_request_source(source: MagicStagedEvaluationRequest) -> None:
    if not isinstance(source, MagicStagedEvaluationRequest):
        raise TypeError('balance requires a typed staged source')
    for candidate in source.candidates:
        _validate_scenario_source(candidate.scenario)
        replace(candidate)
    for stage in source.stages:
        replace(stage)
    replace(source.window)
    if replace(source) != source:
        raise ValueError('balance staged source must retain its admitted form')


def _validate_generation_result_source(result: MagicCandidateGenerationResult) -> None:
    if not isinstance(result, MagicCandidateGenerationResult):
        raise TypeError('generator must return a typed magic generation result')
    _validate_generation_source(result.source_request)
    _validate_staged_request_source(result.evaluation_request)
    replace(result)


def _validate_staged_result_source(result: MagicStagedEvaluationResult) -> None:
    """Check the explicit report/source edges, without replaying any trials."""
    if not isinstance(result, MagicStagedEvaluationResult):
        raise TypeError('evaluator must return a typed magic staged result')
    _validate_staged_request_source(result.source_request)
    for report in result.stage_reports:
        for candidate in report.source_request.candidates:
            _validate_scenario_source(candidate.scenario)
            replace(candidate)
        for request in report.source_request.simulation_requests:
            replace(request)
            _validate_scenario_source(request.scenario)
        replace(report.source_request.window)
        admitted_source = replace(report.source_request)
        if report.source_request.simulation_requests != admitted_source.simulation_requests:
            raise ValueError('balance report has foreign derived simulation requests')
        for row in report.candidates:
            assessment = row.assessment
            for request in (assessment.source_request, assessment.summary.source_request):
                replace(request)
                _validate_scenario_source(request.scenario)
            replace(assessment.summary.outcome_counts)
            replace(assessment.summary)
            replace(assessment.window)
            replace(assessment)
            replace(row)
        replace(report, source_request=admitted_source)
    replace(result)
