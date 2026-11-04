"""Small mixed encounter with explicit, finite Near Miss choices."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_mixed_scenario
from towr.domain.attack_models import DamageProfile
from towr.domain.pc_melee_models import PcFatePolicy, PcNearMissPolicy
from towr.domain.test_models import InlineProfile


def active_near_miss_source(*, minimum_table_total=1, minimum_rating_to_keep=1):
    source = make_pc_melee_mixed_scenario(pc_count=2, minion_count=1,
        brute_count=1, brute_wound_limit=2, max_rounds=3)
    party = tuple(replace(member,
        fate_policy=PcFatePolicy.CONFIGURED,
        near_miss_policy=PcNearMissPolicy(minimum_table_total,minimum_rating_to_keep))
        for member in source.party)
    enemies = []
    for enemy in source.enemies:
        attack = replace(enemy.definition.attacks[0],test_profile=InlineProfile(3,7),
            damage=DamageProfile(7))
        definition = replace(enemy.definition,attacks=(attack,))
        enemies.append(replace(enemy,definition=definition))
    return replace(source,party=party,enemies=tuple(enemies))
