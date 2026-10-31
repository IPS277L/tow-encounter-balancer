"""Magic input failures keep their own boundary family (ADR-0043)."""
from towr.adapters.ranged_json_errors import RangedInputErrorCode


class MagicInputError(ValueError):
    def __init__(self, code: RangedInputErrorCode, message: str, *, path: str | None = None,
                 request_id: str | None = None, schema_version: str = "1") -> None:
        if not isinstance(schema_version, str):
            raise TypeError("magic schema version must be a string")
        if schema_version not in ("1", "2"):
            raise ValueError("unsupported magic schema version")
        super().__init__(message)
        self.code = code
        self.path = path
        self.request_id = request_id
        self.schema_version = schema_version


class MagicSimulationInputError(MagicInputError):
    pass


class MagicBalanceInputError(MagicInputError):
    pass
