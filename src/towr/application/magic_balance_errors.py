"""Request-bound magic failures; original diagnostics stay in the cause chain."""


class MagicBalanceGenerationError(RuntimeError):
    def __init__(self, request_id: str, candidate_id: str | None = None,
                 counts: tuple[int, ...] | None = None) -> None:
        super().__init__('Magic balance candidate generation failed')
        self.request_id = request_id
        self.candidate_id = candidate_id
        self.counts = tuple(counts) if counts is not None else None


class MagicBalanceExecutionError(RuntimeError):
    def __init__(self, request_id: str, stage_index: int | None = None,
                 candidate_id: str | None = None) -> None:
        super().__init__('Magic balance evaluation failed')
        self.request_id = request_id
        self.stage_index = stage_index
        self.candidate_id = candidate_id
