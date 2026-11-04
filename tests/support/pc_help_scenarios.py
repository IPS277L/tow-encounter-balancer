"""Explicit physical Melee assistance for a later ordinary ally."""
from dataclasses import replace

from tests.support.pc_glorious_scenarios import active_glorious_source
from towr.domain.pc_melee_models import PcHelpPolicy,PcMeleePolicy


def active_help_source():
    source = active_glorious_source()
    helper,beneficiary = source.party
    helper = replace(helper,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        help_policy=PcHelpPolicy(beneficiary.actor_id))
    return replace(source,party=(helper,beneficiary))
