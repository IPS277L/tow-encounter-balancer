from towr.domain.protection_models import (
    ProtectionPreparationRequest,
    ProtectionPreparationResult,
    _expected_protection,
)


def prepare_protection(request: ProtectionPreparationRequest) -> ProtectionPreparationResult:
    """Validate an explicit defence choice without rolling or selecting a policy.

    Caller supplies current equipment/awareness facts and keeps this preparation
    alongside the later Attack result to retain both traces.
    """
    if not isinstance(request, ProtectionPreparationRequest):
        raise TypeError("request must be a ProtectionPreparationRequest")
    attack, eligible, reasons, rules = _expected_protection(request)
    return ProtectionPreparationResult(
        request.id, request.rule_id, request, request.defender_id,
        attack, eligible, reasons, rules,
    )
