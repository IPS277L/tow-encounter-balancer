"""Pure continuation policy for refinement of magic candidates (ADR-0041)."""
from towr.balance.magic_assessment_models import MagicAssessmentStatus
from towr.balance.magic_evaluation_models import MagicBalanceEvaluationResult


def magic_continuation_candidate_ids(report: MagicBalanceEvaluationResult) -> tuple[str, ...]:
    """Keep eligible candidates, including outside-window rows, in input order."""
    if not isinstance(report, MagicBalanceEvaluationResult):
        raise TypeError("magic continuation requires a typed evaluation report")
    eligible = (row for row in report.candidates if row.assessment.status is MagicAssessmentStatus.ELIGIBLE)
    ranked = sorted(eligible, key=lambda row: abs(
        row.assessment.objective_achieved_rate - report.source_request.window.target))
    kept = {row.candidate_id for row in ranked[:report.source_request.top_k]}
    return tuple(row.candidate_id for row in report.candidates if row.candidate_id in kept)
