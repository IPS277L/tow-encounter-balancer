"""Candidate context for failures of a bounded magic evaluation."""


class MagicBalanceEvaluationError(RuntimeError):
    """A candidate failed; __cause__ preserves the original error and notes."""

    candidate_id: str

    def __init__(self, candidate_id: str) -> None:
        super().__init__(f"Magic balance evaluation failed for candidate {candidate_id}")
        self.candidate_id = candidate_id
