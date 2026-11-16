"""Numeric encounters with a real trade-off between attacking and enhancement."""
from dataclasses import replace

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.test_models import InlineProfile


def enhancement_source(characteristic='weapon_skill', *, rounds=4):
    source = automatic_source(pc_count=1, enemy_count=3, rounds=rounds)
    pc = replace(source.party[0], pc=replace(source.party[0].pc, weapon_skill=1, melee=1),
        consumables=(ConsumableItem('enhancement', ConsumableKind.ENHANCEMENT, 2, characteristic),))
    enemies = []
    for enemy in source.enemies:
        definition = replace(enemy.definition, resilience=ResilienceProfile(4),
            attacks=(replace(enemy.definition.attacks[0], damage=DamageProfile(3),
                test_profile=InlineProfile(2,5)),),
            protection=(replace(enemy.definition.protection[0], test_profile=InlineProfile(1,1)),))
        enemies.append(replace(enemy, definition=definition,
            state=replace(enemy.state, current_resilience=definition.resilience)))
    return replace(source, party=(pc,), enemies=tuple(enemies))
