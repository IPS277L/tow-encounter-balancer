from towr.adapters.ranged_json_errors import RangedInputError


class RangedBalanceInputError(RangedInputError):
    """Strict parsing/admission failure, distinct from application phase failures."""
