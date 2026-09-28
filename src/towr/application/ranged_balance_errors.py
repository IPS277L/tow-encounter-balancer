"""Request-bound failures; diagnostics remain in the Python cause chain."""


class RangedBalanceGenerationError(RuntimeError):
    def __init__(self, request_id: str, candidate_id: str | None = None,
                 counts: tuple[int, ...] | None = None) -> None:
        super().__init__("Balance candidate generation failed")
        self.request_id = request_id
        self.candidate_id = candidate_id
        self.counts = tuple(counts) if counts is not None else None


class RangedBalanceExecutionError(RuntimeError):
    def __init__(self, request_id: str, stage_index: int | None = None,
                 candidate_id: str | None = None) -> None:
        super().__init__("Balance evaluation failed")
        self.request_id = request_id
        self.stage_index = stage_index
        self.candidate_id = candidate_id
