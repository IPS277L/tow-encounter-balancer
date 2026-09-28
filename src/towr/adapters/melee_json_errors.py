"""Melee input failures are distinct from ranged boundary failures."""
from towr.adapters.ranged_json_errors import RangedInputErrorCode


class MeleeInputError(ValueError):
    def __init__(self, code: RangedInputErrorCode, message: str, *, path: str | None = None,
                 request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.request_id = request_id


class MeleeSimulationInputError(MeleeInputError):
    pass


class MeleeBalanceInputError(MeleeInputError):
    pass
