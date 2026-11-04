"""Physical protection assistance with an explicit skill and enemy priority."""
from dataclasses import replace

from tests.support.pc_help_scenarios import active_help_source
from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget
from towr.domain.test_models import Skill


def active_protection_help_source():
    source = active_help_source()
    helper,beneficiary = source.party
    helper = replace(helper,help_policy=PcHelpPolicy(beneficiary.actor_id,
        PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE))
    party = []
    for member in (helper,beneficiary):
        priority = tuple(reversed(member.target_priority))
        party.append(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)))
    return replace(source,party=tuple(party),
        enemy_target_priority=(beneficiary.actor_id,helper.actor_id))
