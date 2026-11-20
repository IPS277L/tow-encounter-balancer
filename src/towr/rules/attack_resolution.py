from __future__ import annotations

from dataclasses import replace

from towr.domain.attack_models import (
    AttackOutcome,
    AttackRequest,
    AttackResult,
    DamageImpactSpec,
    ImpactOutcome,
    MissConsequence,
    effective_damage_modifiers,
    effective_ignores_armour,
    armour_ward_cancels_effects,
)
from towr.domain.armour_models import METEORIC_PROTECTION_RULE_ID
from towr.domain.talent_tie_models import compose_talent_tie_break
from towr.domain.test_models import (
    OpposedSide,
    RollTrace,
    TestRequest,
    TestResult,
    TieBreak,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


ATTACK_TIE_RULE_ID = "RULE-COMBAT-006:attack-tie"


def resolve_attack(
    request: AttackRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> AttackResult:
    _attack_tie_break(request)
    attacker_test = resolve_test(request.attacker_test, rng, decisions=decisions)
    defender_test = (
        resolve_test(request.defender_test, rng, decisions=decisions)
        if request.defender_test is not None else None
    )
    return _resolve_attack_after_tests(request, attacker_test, defender_test)


def _resolve_attack_after_tests(
    request: AttackRequest,
    attacker_test: TestResult,
    defender_test: TestResult | None,
) -> AttackResult:
    """Complete an attack without rerolling already completed Tests.

    The caller retains the full prepared Test/source proofs. This boundary binds
    their results to the selected attack and performs no further RNG work.
    """
    tie_break = _attack_tie_break(request)
    _validate_completed_test(request.attacker_test, attacker_test)
    if request.defender_test is None:
        if defender_test is not None:
            raise ValueError("an unopposed attack cannot carry a defender Test")
        defender_successes = 0
    else:
        _validate_completed_test(request.defender_test, defender_test)
        assert defender_test is not None
        defender_successes = defender_test.effective_successes
    own_grant = attacker_test.honour_bound
    opposing_grant = defender_test.honour_bound if defender_test is not None else None
    if own_grant is not None and opposing_grant is not None:
        raise ValueError('opposed Unmitigated outcomes require an explicitly resolved GM conflict')
    attacker_successes = attacker_test.effective_successes
    tie_break_applied = (
        own_grant is None and opposing_grant is None
        and attacker_successes > 0 and defender_test is not None
        and attacker_successes == defender_successes
    )
    hit = own_grant is not None or opposing_grant is None and attacker_successes > 0 and (
        attacker_successes > defender_successes
        or tie_break_applied and tie_break.winner is OpposedSide.INITIATOR
    )
    success_margin = (attacker_successes if own_grant is not None
        else attacker_successes - defender_successes if hit else 0)
    from towr.domain.honour_bound_models import HONOUR_BOUND_UNMITIGATED_RULE_ID
    override_rules = (HONOUR_BOUND_UNMITIGATED_RULE_ID,) if own_grant or opposing_grant else ()

    if not hit:
        miss_consequence, miss_rule_ids = _resolve_miss_consequence(request)
        if tie_break_applied:
            miss_rule_ids = (*miss_rule_ids, tie_break.rule_id)
        return AttackResult(
            request_id=request.id,
            attacker_test=attacker_test,
            defender_test=defender_test,
            outcome=AttackOutcome.MISS,
            success_margin=0,
            impact_spec=request.impact_spec,
            damage=None,
            effective_resilience=None,
            impact=None,
            miss_consequence=miss_consequence,
            tie_break_applied=tie_break_applied,
            applied_rule_ids=(*miss_rule_ids,*override_rules),
        )

    if not isinstance(request.impact_spec, DamageImpactSpec):
        applied_rule_ids = (request.impact_spec.rule_id,)
        if tie_break_applied:
            applied_rule_ids = (*applied_rule_ids, tie_break.rule_id)
        return AttackResult(
            request_id=request.id,
            attacker_test=attacker_test,
            defender_test=defender_test,
            outcome=AttackOutcome.HIT,
            success_margin=success_margin,
            impact_spec=request.impact_spec,
            damage=None,
            effective_resilience=None,
            impact=None,
            miss_consequence=MissConsequence.NONE,
            tie_break_applied=tie_break_applied,
            applied_rule_ids=(*applied_rule_ids,*override_rules),
        )

    spec = request.impact_spec
    damage_modifiers = effective_damage_modifiers(spec)
    damage_delta = sum(modifier.amount for modifier in damage_modifiers)
    total_damage = (
        spec.damage.base
        + success_margin * spec.damage.success_multiplier
        + damage_delta
    )
    if total_damage < 0:
        raise ValueError("resolved damage must not be negative")

    base_resilience = (
        spec.resilience.toughness
        if effective_ignores_armour(spec)
        else spec.resilience.total
    )
    resilience_delta = sum(
        modifier.amount for modifier in spec.resilience_modifiers
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
            damage_modifiers,
            spec.resilience_modifiers,
        )
        for modifier in modifiers
    )
    if armour_ward_cancels_effects(spec):
        applied_rule_ids = (*applied_rule_ids, METEORIC_PROTECTION_RULE_ID)
    if tie_break_applied:
        applied_rule_ids = (*applied_rule_ids, tie_break.rule_id)
    return AttackResult(
        request_id=request.id,
        attacker_test=attacker_test,
        defender_test=defender_test,
        outcome=AttackOutcome.HIT,
        success_margin=success_margin,
        impact_spec=spec,
        damage=total_damage,
        effective_resilience=effective_resilience,
        impact=impact,
        miss_consequence=MissConsequence.NONE,
        tie_break_applied=tie_break_applied,
        applied_rule_ids=(*applied_rule_ids,*override_rules),
    )


def _attack_tie_break(request: AttackRequest) -> TieBreak:
    """Readmit a cached source before RNG and before completed-Test arithmetic."""
    if not isinstance(request, AttackRequest):
        raise TypeError("attack resolution requires an AttackRequest")
    source = request.tie_break
    if source is None:
        return TieBreak(ATTACK_TIE_RULE_ID, OpposedSide.INITIATOR)
    return compose_talent_tie_break(source, ())


def _validate_completed_test(request: TestRequest, result: TestResult | None) -> None:
    if not isinstance(result, TestResult) or not isinstance(result.trace, RollTrace):
        raise TypeError("attack completion requires a completed TestResult")
    if type(result.trace.request_id) is not str or result.trace.request_id != request.id:
        raise ValueError("completed Test belongs to another attack request")
    if type(result.successes) is not int:
        raise TypeError("completed Test successes must be an integer")
    if result.successes < 0:
        raise ValueError("completed Test successes must be nonnegative")
    if result.honour_bound is not None:
        replace(result)
        if result.honour_bound.activation.source_request.test != request:
            raise ValueError('Honour Bound outcome replaced the actual prepared Attack Test')


def _resolve_miss_consequence(
    request: AttackRequest,
) -> tuple[MissConsequence, tuple[str, ...]]:
    if request.is_close_range and not request.attacker_is_staggered:
        if request.close_miss_stagger_immunity_rule_id is not None:
            return (
                MissConsequence.NONE,
                (request.close_miss_stagger_immunity_rule_id,),
            )
        return MissConsequence.STAGGER_ATTACKER, ()
    return MissConsequence.NONE, ()
