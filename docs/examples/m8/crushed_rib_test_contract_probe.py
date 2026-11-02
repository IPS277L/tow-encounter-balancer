"""ADR-0055 finite K1-only next-Test proposal, with unchanged M8 refusal.

Copy with stationary_wound_runner.py and magic_scenario.py. This is not a new
consumer or completion validator. The explicitly labelled manual injury-only
projection below is an oracle, never an M8 roster/application/chronology proof.
PG1.4 pp108,118,123,156-157,190; GM1.1 p92. Authored numeric profiles.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain.condition_models import Condition
from towr.domain.drained_test_models import DrainedTestPreparationRequest
from towr.domain.injury_models import (
    CharacterWoundRequest, CharacterWoundType, WoundConditionEffect, WoundEffectDuration,
    WoundEntryId, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import CastingTestRequest, MiscastPoolResolutionRequest, MiscastPoolOutcome
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.test_models import InlineProfile, QualityModifier, TestQuality, TestRequest
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.casting_test_resolution import resolve_casting_test
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.miscast_pool_resolution import RULE_OF_NINE_RULE_ID, resolve_miscast_pool_increase
from towr.rules.test_resolution import resolve_test


CRUSHED_RIB_RULE = 'RULE-WOUND-TABLE:crushed_rib'
GRIM = QualityModifier(CRUSHED_RIB_RULE, TestQuality.GRIM)
PROFILE = InlineProfile(3, 5)


def finite_prepare(injury, actor_id, test):
    """Explicit fixture preparation with existing K1 models; no new public API."""
    assert len(injury.wounds) == 1 and injury.wounds[0].entry_id is WoundEntryId.CRUSHED_RIB
    assert injury.wounds[0].effect_resolved and not injury.wounds[0].treated and not injury.wounds[0].healed
    assert injury.active_wound_effects == (
        WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED),
        WoundRestrictionEffect(1, WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST),
    )
    modified = replace(test, quality_modifiers=(*test.quality_modifiers, GRIM))
    prepared = prepare_drained_test(DrainedTestPreparationRequest(
        test.id + ':drained', actor_id, injury.conditions, modified))
    assert prepared.drained_active and prepared.test == modified
    return prepared.test


def manual_consumed_injury(injury):
    """MANUAL finite oracle: not a source-bound consumer/apply or trace validator.

    The example calls this only after asserting an actual existing K1 result.
    No caller should project this value into an M8 owner to bypass admission.
    """
    effect = WoundRestrictionEffect(1, WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST)
    assert injury.active_wound_effects.count(effect) == 1
    result = replace(injury, active_wound_effects=tuple(e for e in injury.active_wound_effects if e != effect))
    assert result.wounds == injury.wounds and result.conditions == injury.conditions
    assert result.conditions.has(Condition.DRAINED) and not result.wounds[0].treated
    assert result.active_wound_effects == (WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED),)
    return result


def main():
    rng_before = getstate()
    source = authored_input()
    source_before = deepcopy(source)
    dice = ScriptedDice((1, 2, 3, 10, 10, 10, 10))
    stopped = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and stopped.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert NpcMagicScenarioResult(source, stopped.steps, stopped.unsupported) == stopped
    owner = stopped.current
    owner_before = deepcopy(owner)
    actor_id = owner.wizard.actor_id
    injury = owner.roster.participant(actor_id).state.injury
    injury_before = deepcopy(injury)
    attack = next(s.result for s in stopped.steps if isinstance(s.result, NpcRosterChampionAttackResult))
    assert attack.attack.completion.wound_effect.request.rule_id == CRUSHED_RIB_RULE
    assert injury.wounds[0].table_total == 10 and injury.wounds[0].roll_values == (10,)
    assert owner.champion_attack.roster == owner.roster
    assert owner.minion_attack is None or owner.minion_attack.roster == owner.roster
    assert len(owner.champion_attack.daily_wounds.receipts) == 1
    assert len(owner.champion_attack.consumed_wound_roll_ids) == 1
    total = dice.calls
    print('ACTUAL M8: first Wound10 in7d10; resolved Drained + NEXT_TEST_IS_GRIM; source/daily/child owners retained; actor-injury stop')

    defence = TestRequest('finite:defence-first', PROFILE)
    prepared = finite_prepare(injury, actor_id, defence)
    assert injury == injury_before and owner == owner_before  # Preparation consumes nothing.
    first_dice = ScriptedDice((1, 6, 2, 8, 3))
    first = resolve_test(prepared, first_dice)
    assert first_dice.calls == 5 and first.trace.quality is TestQuality.GRIM
    assert first.trace.initial_values == (1, 6, 2) and first.trace.final_values == (8, 6, 3)
    assert tuple(r.index for r in first.trace.rerolls) == (0, 2) and first.successes == 1
    assert first.trace.applied_rule_ids == (CRUSHED_RIB_RULE,)
    after_defence = manual_consumed_injury(injury)
    normal_cast = prepare_drained_test(DrainedTestPreparationRequest('finite:later-cast:drained', actor_id,
        after_defence.conditions, TestRequest('finite:later-cast:test', PROFILE)))
    casting_request = CastingTestRequest('finite:later-cast', actor_id, source.spell.lore_id,
                                        normal_cast.test, owner.wizard.magic_state)
    cast_dice = ScriptedDice((1, 6, 10))
    cast = resolve_casting_test(casting_request, cast_dice)
    assert cast_dice.calls == 3 and cast.test.trace.quality is TestQuality.NORMAL and not cast.test.trace.rerolls
    assert cast.test.successes == 1 and not cast.follow_ups and cast.miscast_dice_added == 0
    total += first_dice.calls + cast_dice.calls
    print('K1 DEFENCE-LABEL FIRST: Grim5d10 -> manual injury-only consumption oracle -> normal Casting3d10; Drained/Wound retained; not M8 Protection')

    # Separate branch from the original injury. The authored 3d/9 profile makes
    # the initial nine successful, proving the Casting-owned lock prevents its
    # Grim reroll. Another success rerolls TO nine; final nines feed the pool.
    cast_test = finite_prepare(injury, actor_id, TestRequest('finite:cast-first:test', InlineProfile(3, 9)))
    first_cast_request = CastingTestRequest('finite:cast-first', actor_id, source.spell.lore_id,
                                           cast_test, owner.wizard.magic_state)
    first_cast_dice = ScriptedDice((9, 1, 10, 9))
    first_cast = resolve_casting_test(first_cast_request, first_cast_dice)
    assert first_cast_dice.calls == 4 and first_cast.test.trace.quality is TestQuality.GRIM
    assert first_cast.test.trace.initial_values == (9, 1, 10) and first_cast.test.trace.final_values == (9, 9, 10)
    assert tuple(r.index for r in first_cast.test.trace.rerolls) == (1,)
    assert first_cast.test.trace.applied_rule_ids == (CRUSHED_RIB_RULE, RULE_OF_NINE_RULE_ID)
    assert first_cast.latest_roll_successes == 2 and first_cast.state.casting_successes == 2
    assert first_cast.miscast_dice_added == 2 and len(first_cast.follow_ups) == 1
    follow = first_cast.follow_ups[0]
    assert follow.target_id == actor_id and follow.source_id == first_cast_request.test.id and follow.amount == 2
    # A completed Test precedes its pool follow-up: the manual injury oracle
    # illustrates that boundary without pretending to commit an M8 owner.
    after_cast = manual_consumed_injury(injury)
    pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest('finite:cast-first:pool', follow,
        first_cast.state, owner.wizard.caster.wizard_level))
    assert pool.state.miscast_dice == 2 and pool.outcome is MiscastPoolOutcome.ACCUMULATED
    later_defence = prepare_drained_test(DrainedTestPreparationRequest('finite:later-defence:drained', actor_id,
        after_cast.conditions, TestRequest('finite:later-defence', PROFILE)))
    later_dice = ScriptedDice((1, 6, 10))
    later = resolve_test(later_defence.test, later_dice)
    assert later_dice.calls == 3 and later.trace.quality is TestQuality.NORMAL and later.successes == 1
    total += first_cast_dice.calls + later_dice.calls
    print('K1 CASTING FIRST: Grim4d10; initial9 locked, rerolled9 retained, final2nines produce actual pool+2; later normal Test3d10 via manual injury oracle')

    for label, values, existing in (
        ('zero-initial-success', (8, 9, 10), ()),
        ('failed-after-rerolls', (1, 2, 10, 8, 9), ()),
        ('already-Grim', (1, 10, 10, 8), (QualityModifier('example:existing-grim', TestQuality.GRIM),)),
    ):
        request = finite_prepare(injury, actor_id, TestRequest('finite:' + label, PROFILE, quality_modifiers=existing))
        control_dice = ScriptedDice(values)
        result = resolve_test(request, control_dice)
        assert control_dice.calls == len(values) and result.trace.quality is TestQuality.GRIM and result.successes == 0
        assert len(result.trace.rerolls) == sum(v <= PROFILE.threshold for v in values[:3])
        assert manual_consumed_injury(injury) == after_defence
        total += control_dice.calls
    print('FAILED CONTROLS: zero initial successes3d10, failed rerolls5d10, already-Grim4d10; one completed Test consumes in manual oracle regardless of success')

    other_dice = ScriptedDice((1,))
    other = resolve_test(TestRequest('finite:other-actor', InlineProfile(1, 5)), other_dice)
    assert other.successes == 1 and other_dice.calls == 1
    wound_dice = ScriptedDice((1, 1))
    wound = resolve_character_wound(CharacterWoundRequest('finite:another-wound-roll', injury,
        subject_type=CharacterWoundType.CHAMPION), wound_dice)
    assert wound_dice.calls == 2 and wound.table_roll.values == (1, 1)
    assert wound.state.active_wound_effects == injury.active_wound_effects
    assert injury == injury_before and owner == owner_before
    total += other_dice.calls + wound_dice.calls
    print('NO CONSUMPTION: preparation, another labelled actor Test1d10 and Wounds Table2d10 retain original restriction; K1 does not prove actor identity or chronology')

    # Pure quality algebra, deliberately outside the Crushed Rib/Drained slice.
    cancellation = TestRequest('finite:algebra-only', PROFILE, quality_modifiers=(GRIM,
        QualityModifier('example:glorious-without-drained', TestQuality.GLORIOUS)))
    algebra_dice = ScriptedDice((1, 7, 10))
    algebra = resolve_test(cancellation, algebra_dice)
    assert algebra_dice.calls == 3 and algebra.trace.quality is TestQuality.NORMAL and not algebra.trace.rerolls
    total += algebra_dice.calls
    assert total == 40
    assert diagnose_npc_magic_unsupported(source, owner, stopped.unsupported.source_id) == stopped.unsupported
    assert source == source_before and owner == owner_before and injury == injury_before and getstate() == rng_before
    print('ALGEBRA ONLY: Grim/Glorious cancellation3d10 outside admitted injury slice; no Fate or Lucky proof invented')
    print('40 scripted d10; M8 still rejects unchanged Wound10; manual injury views never enter owner; exact consumer/trace validation and full-owner bridge remain future work')


if __name__ == '__main__':
    main()
