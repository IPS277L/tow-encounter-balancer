"""Magic input failures keep their own boundary family (ADR-0043)."""
from towr.adapters.ranged_json_errors import RangedInputErrorCode


class MagicInputError(ValueError):
    def __init__(self, code: RangedInputErrorCode, message: str, *, path: str | None = None,
                 request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.request_id = request_id


class MagicSimulationInputError(MagicInputError):
    pass


class MagicBalanceInputError(MagicInputError):
    pass
