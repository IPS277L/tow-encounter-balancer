class MeleeCandidateGenerationError(RuntimeError):
    """A composition failed admission; __cause__ retains the original diagnosis."""

    def __init__(self, candidate_id: str, counts: tuple[int, ...]) -> None:
        super().__init__(f"Candidate generation failed for {candidate_id}")
        self.candidate_id = candidate_id
        self.counts = counts
