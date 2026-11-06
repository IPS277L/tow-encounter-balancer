"""Fresh explicit Bear scenes; no battle execution or expected-result logic."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc


def bear_scene(*, pcs=2, rounds=1, enabled=True):
    source = make_pc_melee_party_scenario(pc_count=pcs, enemy_count=1, max_rounds=rounds)
    bear = create_pc_book_npc(PcBookNpcProfile.BEAR_SWEEPING_CLAWS, 'bear1')
    party = tuple(replace(member, target_priority=('bear1',),
        defeat_decisions=(replace(member.defeat_decisions[0], target_id='bear1'),))
        for member in source.party)
    return replace(source, party=party, enemies=(bear,), enemy_activation_order=('bear1',),
        facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_extra_attack_actor_ids=('bear1',) if enabled else ())
