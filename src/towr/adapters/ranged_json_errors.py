from enum import Enum


class RangedInputErrorCode(str, Enum):
    INVALID_JSON = "invalid_json"
    UNSUPPORTED_VERSION = "unsupported_version"
    INVALID_INPUT = "invalid_input"


class RangedSimulationInputError(ValueError):
    def __init__(self, code: RangedInputErrorCode, message: str, *, path: str | None = None,
                 request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.request_id = request_id
