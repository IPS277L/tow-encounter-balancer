"""Wild Attack for the committed immediate Bash Melee Test (PG73/81).

The optional price neither reserves an action nor selects another weapon or
target. PC advice compares finite prepared Tests and a small current exposure
penalty; it does not predict future wins or execute hypothetical combat.
"""
from towr.domain.attack_models import DamageImpactSpec, effective_damage_modifiers, effective_ignores_armour
from towr.domain.condition_models import Condition
from towr.domain.pc_musician_effect_models import musician_defends_ties
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionKind


def expected_bash_wild_attack(state):
    from towr.domain.pc_bash_attack_models import pending_bash_decision, build_pc_bash_strike
    from towr.domain.pc_generated_talents import (
        PcWildAttackProof, actor_conditions, actor_has_combat_talent, pending_wild_attack,
    )
    turn = state.round_state.active_turn
    if (turn is None or not actor_has_combat_talent(state, turn.actor_id, TalentId.WILD_ATTACK)
            or not actor_has_combat_talent(state, turn.actor_id, TalentId.BASH_ATTACK)):
        return None
    decision = pending_bash_decision(state)
    if (decision is None or state.pending or state.pending_wound is not None
            or state.magic_pending is not None):
        return None
    actor = decision.grant.actor_id
    conditions = actor_conditions(state, actor)
    if (conditions.has(Condition.STAGGERED) or conditions.has(Condition.DRAINED)
            or pending_wild_attack(state) is not None):
        return None
    ready = build_pc_bash_strike(state)
    if ready is None:
        return None  # The actual Shield/equipment owners must complete first.
    request, _ = ready
    intent = request.weapon_intent
    if intent.attack_skill is not Skill.MELEE or intent.attack_use is None:
        return None
    utility = decision.selection.utility
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_talent_advice import pc_test_distribution, pc_wild_test_variant
        from towr.domain.pc_tactical_models import _distribution, _impact_value
        source = state.source.participant(actor)
        attack = request.kernel_request.attack
        impact = attack.impact_spec
        if type(impact) is not DamageImpactSpec:
            return None
        normal = pc_test_distribution(state, actor, Skill.MELEE, attack.attacker_test)
        wild_test = pc_wild_test_variant(attack.attacker_test, intent.attack_use.kind, conditions,
            weapon_use=intent.attack_use, talents=source.talents)
        wild = pc_test_distribution(state, actor, Skill.MELEE, wild_test)
        protection = (1.0,) if attack.defender_test is None else _distribution(attack.defender_test)
        damage = impact.damage.base + sum(modifier.amount for modifier in effective_damage_modifiers(impact))
        resilience = (impact.resilience.toughness if effective_ignores_armour(impact)
            else impact.resilience.total) + sum(modifier.amount for modifier in impact.resilience_modifiers)
        injury = request.kernel_request.target_state

        def value(distribution):
            return _impact_value(distribution, protection, damage, resilience,
                impact.damage.success_multiplier, injury.conditions.has(Condition.STAGGERED),
                injury.conditions.has(Condition.DEFENCELESS),
                defender_wins_ties=musician_defends_ties(state,request.target_id))

        before, after = value(normal), value(wild)
        combat = state.round_state
        exposed = any(enemy.state.actor_id not in (*combat.completed_turn_entity_ids,
            *combat.excluded_turn_entity_ids) for enemy in state.live_enemies)
        current_wounds = sum(not wound.healed for wound in state.participant(actor).injury.wounds)
        risk = (.1 if exposed else .025) + .05 * min(2, current_wounds)
        if after - before <= risk + 1e-12:
            return None
        utility = after - risk
    from towr.domain.pc_tactical_models import PcTacticalChoice
    tactic = PcTacticalChoice(actor, CombatActionKind.ATTACK, request.target_id, None,
        float(utility), 'bash_wild_attack', wild_attack=True,
        weapon_item_id=intent.attack_use.primary_item_id)
    return PcWildAttackProof(actor, decision.grant.id, intent=tactic,
        attack_weapon_intent=intent)
