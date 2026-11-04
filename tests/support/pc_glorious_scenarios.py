"""Independent authored Glorious and Near Miss strategies for a small party."""
from dataclasses import replace

from tests.support.pc_near_miss_scenarios import active_near_miss_source
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy
from towr.domain.test_models import Skill


def active_glorious_source(*, maximum_initial_successes=1, minimum_remaining_spends=1,
                           include_near_miss=True):
    source = active_near_miss_source()
    return replace(source,party=tuple(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
        near_miss_policy=member.near_miss_policy if include_near_miss else None,
        glorious_policy=PcGloriousPolicy((Skill.MELEE,Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE),
            maximum_initial_successes,minimum_remaining_spends)) for member in source.party))
