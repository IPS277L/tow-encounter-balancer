class MeleeSimulationExecutionError(RuntimeError):
    """Execution failed; the original exception and its notes remain in __cause__."""

    def __init__(self, request_id: str) -> None:
        super().__init__("Simulation execution failed")
        self.request_id = request_id
