"""Candidate context for an interrupted magic family construction."""


class MagicCandidateGenerationError(RuntimeError):
    """The original admission error and notes remain in the __cause__ chain."""

    candidate_id: str
    counts: tuple[int, ...]

    def __init__(self, candidate_id: str, counts: tuple[int, ...]) -> None:
        super().__init__(f"Magic candidate generation failed for {candidate_id}")
        self.candidate_id = candidate_id
        self.counts = counts
