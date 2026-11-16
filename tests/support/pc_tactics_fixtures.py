"""Small numeric sources and pure preparation snapshots for automatic tactics."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatTurnStartRequest
from towr.rules.turn_resolution import start_combat_turn


def automatic_source(*, pc_count=2, enemy_count=1, rounds=1):
    source = make_pc_melee_party_scenario(pc_count=pc_count, enemy_count=enemy_count, max_rounds=rounds)
    return replace(source, party=tuple(replace(member, policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        for member in source.party))


def weak_helper_source():
    source = automatic_source()
    party = tuple(replace(member, pc=replace(member.pc, weapon_skill=1 if index==0 else 6,
        melee=6, strength=1 if index==0 else 9)) for index, member in enumerate(source.party))
    enemy = source.enemies[0]
    resilience = ResilienceProfile(10)
    definition = replace(enemy.definition, resilience=resilience,
        protection=(replace(enemy.definition.protection[0], test_profile=InlineProfile(6,6)),))
    enemy = replace(enemy, definition=definition, state=replace(enemy.state, current_resilience=resilience))
    return replace(source, party=party, enemies=(enemy,))


def tactical_snapshot(source, actor='pc1'):
    """Preparation-only snapshot; not an invented native journal prefix."""
    state = initial_pc_melee_state(source)
    clock = start_combat_turn(CombatTurnStartRequest('pure:start', state.round_state, actor)).state
    return replace(state, round_state=clock)
