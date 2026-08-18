from __future__ import annotations

from towr.domain.attack_models import (
    AttackOutcome,
    AttackRequest,
    AttackResult,
    ImpactOutcome,
    MissConsequence,
)
from towr.domain.test_models import (
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    TieBreak,
)
from towr.rules.dice import RandomSource
from towr.rules.opposed_test import resolve_opposed_test
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


ATTACK_TIE_RULE_ID = "RULE-COMBAT-006:attack-tie"


def resolve_attack(
    request: AttackRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> AttackResult:
    if request.defender_test is None:
        attacker_test = resolve_test(request.attacker_test, rng, decisions=decisions)
        defender_test = None
        hit = attacker_test.successes > 0
        success_margin = attacker_test.successes if hit else 0
        tie_break_applied = False
    else:
        opposed = resolve_opposed_test(
            OpposedTestRequest(
                id=f"{request.id}:opposed",
                initiator=request.attacker_test,
                opponent=request.defender_test,
                tie_break=TieBreak(ATTACK_TIE_RULE_ID, OpposedSide.INITIATOR),
            ),
            rng,
            decisions=decisions,
        )
        attacker_test = opposed.initiator
        defender_test = opposed.opponent
        hit = opposed.outcome is OpposedOutcome.INITIATOR_WINS
        tie_break_applied = opposed.tie_break_applied
        success_margin = (
            attacker_test.successes - defender_test.successes if hit else 0
        )

    if not hit:
        miss_consequence = _resolve_miss_consequence(request)
        return AttackResult(
            request_id=request.id,
            attacker_test=attacker_test,
            defender_test=defender_test,
            outcome=AttackOutcome.MISS,
            success_margin=0,
            damage=None,
            effective_resilience=None,
            impact=None,
            miss_consequence=miss_consequence,
            tie_break_applied=False,
            applied_rule_ids=(),
        )

    damage_delta = sum(modifier.amount for modifier in request.damage_modifiers)
    total_damage = (
        request.damage.base
        + success_margin * request.damage.success_multiplier
        + damage_delta
    )
    if total_damage < 0:
        raise ValueError("resolved damage must not be negative")

    base_resilience = (
        request.resilience.toughness
        if request.ignores_armour
        else request.resilience.total
    )
    resilience_delta = sum(
        modifier.amount for modifier in request.resilience_modifiers
    )
    effective_resilience = base_resilience + resilience_delta
    if effective_resilience < 0:
        raise ValueError("effective resilience must not be negative")

    impact = (
        ImpactOutcome.WOUND
        if total_damage > effective_resilience
        else ImpactOutcome.STAGGERED
    )
    applied_rule_ids = tuple(
        modifier.rule_id
        for modifiers in (
            request.damage_modifiers,
            request.resilience_modifiers,
        )
        for modifier in modifiers
    )
    if tie_break_applied:
        applied_rule_ids = (*applied_rule_ids, ATTACK_TIE_RULE_ID)
    return AttackResult(
        request_id=request.id,
        attacker_test=attacker_test,
        defender_test=defender_test,
        outcome=AttackOutcome.HIT,
        success_margin=success_margin,
        damage=total_damage,
        effective_resilience=effective_resilience,
        impact=impact,
        miss_consequence=MissConsequence.NONE,
        tie_break_applied=tie_break_applied,
        applied_rule_ids=applied_rule_ids,
    )


def _resolve_miss_consequence(request: AttackRequest) -> MissConsequence:
    if request.is_close_range and not request.attacker_is_staggered:
        return MissConsequence.STAGGER_ATTACKER
    return MissConsequence.NONE
