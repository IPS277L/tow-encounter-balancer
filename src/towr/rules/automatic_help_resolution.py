"""Execute and apply either closed no-Test Help effect without an RNG."""
from towr.domain.automatic_help_models import (
    AutomaticHelpActionRequest,AutomaticHelpActionResult,
    AutomaticHelpBonusApplicationRequest,AutomaticHelpBonusApplicationResult,
    expected_automatic_help_action,_expected_automatic_help_application,
)


def execute_automatic_help_action(request:AutomaticHelpActionRequest)->AutomaticHelpActionResult:
    return expected_automatic_help_action(request)


def apply_automatic_help_bonus(request:AutomaticHelpBonusApplicationRequest)->AutomaticHelpBonusApplicationResult:
    test,modifier=_expected_automatic_help_application(request)
    return AutomaticHelpBonusApplicationResult(request.id,request,test,modifier,
        (request.help.source_request.rule_id,request.help.bonus.rule_id))
