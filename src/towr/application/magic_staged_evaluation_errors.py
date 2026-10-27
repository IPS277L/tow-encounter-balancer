"""Stage and optional candidate context for magic evaluation failures."""


class MagicStagedEvaluationError(RuntimeError):
    """Keep the complete __cause__ chain to the candidate/runner diagnostics."""

    stage_index: int
    candidate_id: str | None

    def __init__(self, stage_index: int, candidate_id: str | None) -> None:
        detail = f" for candidate {candidate_id}" if candidate_id is not None else ""
        super().__init__(f"Magic evaluation failed at stage {stage_index}{detail}")
        self.stage_index = stage_index
        self.candidate_id = candidate_id
