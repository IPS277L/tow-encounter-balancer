"""Resolve one real failed surgical Test using explicit GM-supplied weights."""
from dataclasses import replace

from towr.domain.surgery_failure_resolution_models import (
    SurgeryFailureResolutionRequest,SurgeryFailureResolutionResult,_expected_surgery_failure,
)
from towr.rules.dice import RandomSource


def resolve_surgery_failure(request:SurgeryFailureResolutionRequest,rng:RandomSource)->SurgeryFailureResolutionResult:
    if type(request) is not SurgeryFailureResolutionRequest:
        raise TypeError('surgery failure resolution requires its exact source-bound request')
    replace(request)
    draw=rng.randint(1,request.policy.total)
    outcome,state,disfigurement,consumed=_expected_surgery_failure(request,draw)
    return SurgeryFailureResolutionResult(request,draw,outcome,state,disfigurement,consumed)
