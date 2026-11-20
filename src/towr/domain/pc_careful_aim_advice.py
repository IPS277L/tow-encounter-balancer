"""Finite Aim/Attack/Recover comparisons, never prospective random rolls."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import CombatActionKind


def _eligible(state, actor):
    from towr.domain.pc_aim_source_models import actor_can_aim
    from towr.domain.pc_generated_talents import actor_stagger_removable
    from towr.domain.talent_actor_models import actor_has_talent
    return (actor_has_talent(state, actor, TalentId.CAREFUL_AIM)
        and actor_stagger_removable(state, actor) and actor_can_aim(state, actor))


def player_careful_aim_value(state, actor):
    if not _eligible(state, actor):
        return None
    from towr.domain.pc_aim_models import pc_aim_target
    from towr.domain.pc_melee_result_models import _pc_test
    from towr.domain.pc_tactical_models import _distribution
    from towr.domain.pc_ranged_advice import pc_attack_value
    from towr.domain.test_models import Skill
    target = pc_aim_target(state, actor)
    if target is None:
        return None
    test = _pc_test(state, actor, 'tactics:careful-aim', Skill.AWARENESS)
    values = _distribution(test)
    member = state.participant(actor)
    cleared = replace(member, injury=replace(member.injury,
        conditions=member.injury.conditions.without_condition(Condition.STAGGERED)))
    after = replace(state, party=tuple(cleared if row.actor_id == actor else row for row in state.party))
    has_next = state.round_state.round_number < state.source.max_rounds
    value = sum(chance*((.5 if successes else 0.) + (pc_attack_value(
        after if successes else state, actor, extra=successes, target_id=target,
        ignore_aim=True)[0] if has_next else 0.)) for successes, chance in enumerate(values))
    return target, value/(2 if has_next else 1)


def npc_careful_aim_action(state, actor):
    if not _eligible(state, actor):
        return None
    from towr.domain.pc_npc_aim_models import _target, _awareness_test
    from towr.domain.pc_npc_weapon_inventory import _utility
    from towr.domain.pc_tactical_models import _distribution
    target = _target(state, actor)
    if target is None:
        return None
    values = _distribution(_awareness_test(state, actor, target, 'tactics:npc-careful-aim'))
    enemy = state.enemy(actor)
    cleared = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
        conditions=enemy.state.injury.conditions.without_condition(Condition.STAGGERED))))
    after = replace(state, enemies=tuple(cleared if row.state.actor_id == actor else row for row in state.enemies))
    has_next = state.round_state.round_number < state.source.max_rounds
    aim = sum(chance*((.5 if successes else 0.) + (_utility(after if successes else state,
        actor, aim_bonus=successes, ignore_aim=True) if has_next else 0.))
        for successes, chance in enumerate(values))/(2 if has_next else 1)
    recover = (.5 + (_utility(after, actor, ignore_aim=True) if has_next else 0.))/(2 if has_next else 1)
    attack = _utility(state, actor)
    # Exact tie keeps a genuine Recover over a potentially failed removal.
    if aim > max(recover, attack)+1e-12:
        return CombatActionKind.AIM
    return CombatActionKind.RECOVER if recover > attack+1e-12 else CombatActionKind.ATTACK
