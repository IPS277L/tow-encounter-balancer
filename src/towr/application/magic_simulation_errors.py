class MagicSimulationExecutionError(RuntimeError):
    """Execution failed; the original exception and notes remain in __cause__."""

    def __init__(self, request_id: str, *, schema_version: str = "1") -> None:
        if not isinstance(schema_version, str):
            raise TypeError("magic schema version must be a string")
        if schema_version not in ("1", "2"):
            raise ValueError("unsupported magic schema version")
        super().__init__("Magic simulation execution failed")
        self.request_id = request_id
        self.schema_version = schema_version
