"""ADR-0055 actual K1 consumption; copy with the two public fixture modules.

PG1.4 pp108,118,123,156-157,190; GM1.1 p92. Numeric profiles are authored.
K1 receives a chosen actor/injury/Test. No consumed injury is applied to M8.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain import (
    CrushedRibTestPreparationRequest, CrushedRibCastingPreparationRequest,
)
from towr.domain.condition_models import Condition
from towr.domain.drained_test_models import DrainedTestPreparationRequest
from towr.domain.injury_models import WoundRestriction, WoundRestrictionEffect
from towr.domain.magic_models import CastingTestRequest, MiscastPoolOutcome, MiscastPoolResolutionRequest, WizardMagicState
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.test_models import DiceModifier, InlineProfile, QualityModifier, TestQuality, TestRequest
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.crushed_rib_test_resolution import (
    prepare_crushed_rib_test, prepare_crushed_rib_casting,
    resolve_crushed_rib_test, resolve_crushed_rib_casting,
    complete_crushed_rib_test, complete_crushed_rib_casting,
    apply_crushed_rib_test_result,
)
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase


PROFILE = InlineProfile(3, 5)


def refused(call):
    try:
        call()
    except (TypeError, ValueError):
        return
    raise AssertionError('expected a source/admission refusal')


def main():
    global_rng = getstate()
    source = authored_input()
    before = deepcopy(source)
    dice = ScriptedDice((1, 2, 3, 10, 10, 10, 10))
    stopped = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and stopped.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    owner = stopped.current
    original_owner = deepcopy(owner)
    actor = owner.wizard.actor_id
    injury = owner.roster.participant(actor).state.injury
    original = deepcopy(injury)
    total = dice.calls
    print('ACTUAL SOURCE: M8 Wound10 in7d10; full owner/daily histories retained; automatic injury stop remains')

    def check(result, current=injury):
        applied = apply_crushed_rib_test_result(actor, current, result)
        assert applied == result.state and applied != current
        assert applied.wounds == current.wounds and applied.conditions == current.conditions
        assert applied.conditions.has(Condition.DRAINED)
        assert not any(isinstance(e, WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM
                       for e in applied.active_wound_effects)
        assert tuple(e for e in current.active_wound_effects if e != result.consumed_effect) == applied.active_wound_effects
        refused(lambda: apply_crushed_rib_test_result(actor, applied, result))
        refused(lambda: apply_crushed_rib_test_result('another-actor', current, result))
        assert injury == original and owner == original_owner
        return applied

    preparation = prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
        'public:defence', actor, injury, TestRequest('public:defence:test', PROFILE)))
    assert preparation.source_request.state is injury and injury == original
    ordinary_dice = ScriptedDice((1, 6, 2, 8, 3))
    ordinary = resolve_crushed_rib_test(preparation, ordinary_dice)
    assert ordinary_dice.calls == 5 and ordinary.test.successes == 1
    assert ordinary.test.trace.quality is TestQuality.GRIM
    assert complete_crushed_rib_test(preparation, ordinary.test) == ordinary
    after = check(ordinary)
    refused(lambda: prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
        'public:already-consumed', actor, after, TestRequest('public:already-consumed:test', PROFILE))))
    # A later normal Test is selected explicitly, using the retained Drained.
    # This is not a second call to the one-shot consumer or an M8 action.
    later = prepare_drained_test(DrainedTestPreparationRequest(
        'public:later:drained', actor, after.conditions, TestRequest('public:later', PROFILE)))
    assert later.test.quality_modifiers == () and after.conditions.has(Condition.DRAINED)
    total += ordinary_dice.calls
    print('ORDINARY: prepare consumes nothing; actual Grim5d10; strict completion + exact-injury apply; later Test has no Wound Grim')

    magic = WizardMagicState(3, 1, source.spell.lore_id, 1)
    casting = CastingTestRequest('public:casting', actor, source.spell.lore_id,
        TestRequest('public:casting:test', InlineProfile(3, 9)), magic)
    cast_preparation = prepare_crushed_rib_casting(CrushedRibCastingPreparationRequest(
        'public:cast-preparation', actor, injury, casting))
    cast_dice = ScriptedDice((9, 1, 10, 9))
    cast = resolve_crushed_rib_casting(cast_preparation, cast_dice)
    assert cast_dice.calls == 4 and cast.casting.test.trace.final_values == (9, 9, 10)
    assert tuple(r.index for r in cast.casting.test.trace.rerolls) == (1,)
    assert cast.casting.state.casting_successes == 3 and cast.casting.latest_roll_successes == 2
    assert cast.casting.miscast_dice_added == 2 and len(cast.casting.follow_ups) == 1
    assert complete_crushed_rib_casting(cast_preparation, cast.casting) == cast
    after_cast = check(cast)  # Test consumption precedes the pool follow-up.
    assert after_cast.conditions.has(Condition.DRAINED)
    pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest(
        'public:pool', cast.casting.follow_ups[0], cast.casting.state, owner.wizard.caster.wizard_level))
    assert pool.outcome is MiscastPoolOutcome.MISCAST_TRIGGERED and pool.state.miscast_dice == 5
    total += cast_dice.calls
    print('CASTING: actual Grim4d10; original9 locked + reroll-to9; progress1->3; consume before pool3->5/Miscast pending')

    for label, values, qualities in (
        ('zero-success', (8, 9, 10), ()),
        ('failed-rerolls', (1, 2, 10, 8, 9), ()),
        ('already-Grim', (1, 10, 10, 8), (QualityModifier('example:old-grim', TestQuality.GRIM),)),
    ):
        prepared = prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
            'public:' + label, actor, injury,
            TestRequest('public:' + label + ':test', PROFILE, quality_modifiers=qualities)))
        trial_dice = ScriptedDice(values)
        result = resolve_crushed_rib_test(prepared, trial_dice)
        assert trial_dice.calls == len(values) and result.test.successes == 0
        check(result)
        total += trial_dice.calls
    print('COMPLETED FAILURES: zero-success3d10, failed-rerolls5d10, already-Grim4d10 all consume exactly one effect')

    mixed = TestRequest('public:suppressed:test', PROFILE,
        dice_modifiers=(DiceModifier('example:bonus', 2), DiceModifier('example:penalty', -1)),
        quality_modifiers=(QualityModifier('example:ordinary-glorious', TestQuality.GLORIOUS),))
    suppressed = prepare_crushed_rib_test(CrushedRibTestPreparationRequest('public:suppressed', actor, injury, mixed))
    assert suppressed.source_request.test == mixed and suppressed.drained.source_request.test != suppressed.test
    assert suppressed.test.dice_modifiers == (mixed.dice_modifiers[1],)
    assert all(m.quality is TestQuality.GRIM for m in suppressed.test.quality_modifiers)
    suppression_dice = ScriptedDice((1, 10, 8))
    suppression = resolve_crushed_rib_test(suppressed, suppression_dice)
    assert suppression_dice.calls == 3 and suppression.test.trace.rolled_dice == 2
    check(suppression)
    minimum = prepare_crushed_rib_test(CrushedRibTestPreparationRequest('public:minimum', actor, injury,
        TestRequest('public:minimum:test', PROFILE, dice_modifiers=(DiceModifier('example:penalty', -5),))))
    minimum_dice = ScriptedDice((1, 10))
    minimum_result = resolve_crushed_rib_test(minimum, minimum_dice)
    assert minimum_dice.calls == 2 and minimum_result.test.trace.minimum_die_rule_applied
    assert minimum_result.test.trace.threshold == 1 and minimum_result.test.successes == 0
    check(minimum_result)
    total += suppression_dice.calls + minimum_dice.calls
    print('DRAINED: bonus/ordinary Glorious suppressed, penalty retained; actual2dice Test3d10; minimum-die Grim2d10')

    # A same-ID result with altered actual evidence is not a completion witness.
    bad = replace(ordinary.test, trace=replace(ordinary.test.trace, successes=9))
    refused(lambda: complete_crushed_rib_test(preparation, bad))
    refused(lambda: complete_crushed_rib_test(preparation, cast.casting))
    refused(lambda: complete_crushed_rib_casting(cast_preparation, ordinary.test))
    assert diagnose_npc_magic_unsupported(source, owner, stopped.unsupported.source_id) == stopped.unsupported
    assert total == 33 and source == before and owner == original_owner and injury == original
    assert getstate() == global_rng
    print('33 scripted d10; strict witness/stale/wrong-actor guards; source/global RNG unchanged; consumed K1 injury never enters M8 owner')


if __name__ == '__main__':
    main()
