from towr.balance.mixed_assessment_models import MixedAssessmentStatus
from towr.balance.mixed_evaluation_models import MixedBalanceEvaluationResult


def mixed_continuation_candidate_ids(report: MixedBalanceEvaluationResult) -> tuple[str, ...]:
    """Choose eligible candidates for refinement, returning their original order."""
    if not isinstance(report, MixedBalanceEvaluationResult):
        raise TypeError("continuation requires a typed evaluation report")
    eligible = (row for row in report.candidates if row.assessment.status is MixedAssessmentStatus.ELIGIBLE)
    ranked = sorted(eligible, key=lambda row: abs(
        row.assessment.objective_achieved_rate - report.source_request.window.target))
    kept = {row.candidate_id for row in ranked[:report.source_request.top_k]}
    return tuple(row.candidate_id for row in report.candidates if row.candidate_id in kept)
