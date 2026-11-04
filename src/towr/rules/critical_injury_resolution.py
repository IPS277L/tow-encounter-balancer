"""Pure PG123 Critically Injured Endurance consequence, without another roll."""
from towr.domain.critical_injury_models import (
    CriticalInjuryTestRequest, CriticalInjuryTestResult,
    critical_injury_state_after_test,
)
from towr.domain.test_models import TestResult


def resolve_critical_injury_test(
    request: CriticalInjuryTestRequest,
    test: TestResult,
) -> CriticalInjuryTestResult:
    return CriticalInjuryTestResult(request,test,critical_injury_state_after_test(request,test))
