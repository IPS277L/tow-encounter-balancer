"""Typed errors for the sole current PC melee JSON contract."""
from towr.adapters.ranged_json_errors import RangedInputError


class PcMeleeInputError(RangedInputError):
    def __init__(self, *args, schema_version: str = "1", **kwargs):
        if type(schema_version) is not str or schema_version != "1":
            raise ValueError("unsupported PC melee schema version")
        super().__init__(*args, **kwargs)
        self.schema_version = schema_version


class PcMeleeSimulationInputError(PcMeleeInputError):
    pass


class PcMeleeBalanceInputError(PcMeleeInputError):
    pass
