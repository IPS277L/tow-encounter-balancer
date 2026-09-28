from towr.adapters.ranged_json_errors import RangedInputError


class RangedBalanceInputError(RangedInputError):
    """Strict parsing/admission failure; execution errors belong to a later slice."""
