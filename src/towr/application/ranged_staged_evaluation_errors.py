class RangedStagedEvaluationError(RuntimeError):
    """An evaluation stage failed; __cause__ retains candidate/runner diagnostics."""

    def __init__(self, stage_index: int, candidate_id: str | None) -> None:
        detail = f" for candidate {candidate_id}" if candidate_id is not None else ""
        super().__init__(f"Balance evaluation failed at stage {stage_index}{detail}")
        self.stage_index = stage_index
        self.candidate_id = candidate_id
