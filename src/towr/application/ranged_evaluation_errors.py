class RangedBalanceEvaluationError(RuntimeError):
    """A candidate failed; __cause__ retains the original exception and notes."""

    def __init__(self, candidate_id: str) -> None:
        super().__init__(f"Balance evaluation failed for candidate {candidate_id}")
        self.candidate_id = candidate_id
