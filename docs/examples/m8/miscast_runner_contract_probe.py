"""Finite ADR-0046 prerequisites through existing public APIs only.

PG1.4 V Combat Actions116/Recover118/Attack Modifiers119/Broken122/Prone123;
VIII Casting156/Miscasts157-159. GM1.1 VII Minions91/Champions92.
The current runner still stops after Wind. K1 stand/Recover results below are
separate low-level evidence, never published as future bound roster states.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from unnatural_wind import ScriptedDice, authored_scenario, complete_wind, fresh_pending
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMoveProneRemovalRequest, ProneRemovalTargetKind
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverConditionRemovalChoice, RecoverConditionTarget,
    RecoverMode, RecoverStandardChoice, RecoverStandardResult,
)
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.npc_attack_preparation import prepare_npc_attack
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def expect_rejection(operation, message):
    try:
        operation()
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError('this unsupported/illegal operation must be rejected')


def authored_recover_turn():
    """Independent K1 action context, not a future M8 runner transition."""
    combat = CombatRoundState(1, (
        CombatTurnParticipant('actor', CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy', CombatSide.OPPOSITION),
    ))
    combat = start_combat_turn(CombatTurnStartRequest('probe:start', combat, 'actor')).state
    return reserve_combat_action_slot(CombatActionSlotRequest(
        'probe:slot', combat, 'actor', CombatActionDeclaration(CombatActionKind.RECOVER),
        ActionSlotGrant.STANDARD)).state


def main():
    global_rng = getstate()
    scenario = authored_scenario()
    raw, casting_draws = fresh_pending(scenario, (9, 9, 9))
    final, wind, _, table_draws = complete_wind(scenario, raw, (7, 7, 7), 'probe:wind')
    snapshot = deepcopy(final)
    assert wind.wind.targets[0].target_id == final.wizard.actor_id
    assert final.wizard.magic_state == WizardMagicState()
    assert diagnose_npc_magic_unsupported(scenario, final, 'probe:after').reason is Reason.END_TURN
    print('CURRENT RUNNER: fresh Casting -> bound preparation/roll/Wind21; 3+3 d10; actual END_TURN stop')

    # Every hostile pair in this exact frame is explicitly Short, not Close.
    # No enemy-Close fact is inferred from Zone adjacency or a same-Zone test.
    frame = scenario.initial_frame
    assert frame.key.placements == final.spatial_state.placements
    assert all(pair.target_range is Range.SHORT for pair in frame.pair_ranges)
    caster = final.wizard.actor_id
    free = FreeMoveProneRemovalRequest(
        'probe:self-stand', final.round_state, final.spatial_state, caster,
        ProneRemovalTargetKind.SELF, caster,
        final.roster.participant(caster).state.injury.conditions, None, False)
    stood = resolve_free_move_prone_removal(free)
    assert not stood.target_conditions.has(Condition.PRONE)
    assert stood.state.free_move_used_entity_ids == (*free.state.free_move_used_entity_ids, caster)
    assert stood.state.placements == free.state.placements and stood.round_state == free.round_state
    expect_rejection(lambda: resolve_free_move_prone_removal(replace(
        free, id='probe:second-stand', state=stood.state, target_conditions=stood.target_conditions)),
        'only use free movement once')
    expect_rejection(lambda: resolve_free_move_prone_removal(replace(
        free, id='probe:close-stand', actor_has_enemy_in_close_range=True)),
        'enemy in Close Range')
    assert final == snapshot and final.roster.participant(caster).state.injury.conditions.has(Condition.PRONE)
    print('SELF STAND K1: explicit no enemy Close; free move spent, no Zone/action change; second/Close attempts rejected')

    # The derived penalty uses the actual target injury; the general NPC
    # preparation accepts explicit modifiers but is not a future bound adapter.
    actor, target = final.roster.participant('ally'), final.roster.participant('enemy')
    assert target.state.injury.conditions.has(Condition.PRONE)
    prepared = prepare_npc_attack(NpcAttackPreparationRequest(
        'probe:shot:prepare', 'probe:shot', 'probe:shot:test', actor.attack_snapshot('probe:shot:snapshot'),
        'shot', target.state.actor_id, Range.SHORT, target.state.current_resilience, False,
        actor.state.injury.conditions.has(Condition.STAGGERED), False,
        (DiceModifier('RULE-COMBAT-009:prone-target', -1),)))
    shot_dice = ScriptedDice((1, 10))
    shot = resolve_test(prepared.attack.attacker_test, shot_dice)
    assert shot.trace.base_dice == 3 and shot.trace.regular_dice_delta == -1
    assert shot.trace.rolled_dice == shot_dice.calls == 2 and shot.trace.initial_values == (1, 10)
    print('PRONE TARGET K1: explicit RULE-COMBAT-009:prone-target -1d; actual Shooting Test 3d->2d, 2 draws')

    # Standard Recover can remove Prone even with an enemy Close. The explicit
    # authored Close context entails an enemy in the Zone, the K1 request fact.
    conditions = ConditionState({Condition.PRONE, Condition.STAGGERED})
    self_target = RecoverConditionTarget('actor', conditions, None)
    standard_source = RecoverActionExecutionRequest(
        'probe:standard', authored_recover_turn(), 'actor', conditions, True, 1,
        RecoverMode.STANDARD, RecoverStandardChoice(
            WizardMagicState(2), staggered_target=self_target, prone_target=self_target))
    no_dice = ScriptedDice(())
    standard = execute_recover_action(standard_source, no_dice)
    assert isinstance(standard.resolution, RecoverStandardResult)
    assert standard.resolution.condition_changes[0].conditions == ConditionState()
    assert standard.resolution.magic_state == WizardMagicState(1)
    assert standard.slot.executed and no_dice.calls == 0
    print('STANDARD RECOVER K1: authored enemy Close; Prone/Staggered removed, Pool2->1; one action, 0 draws')

    broken_conditions = ConditionState({Condition.BROKEN, Condition.PRONE, Condition.STAGGERED})
    alternative_source = RecoverActionExecutionRequest(
        'probe:broken', authored_recover_turn(), 'actor', broken_conditions, False, 1,
        RecoverMode.REMOVE_CONDITION, RecoverConditionRemovalChoice(
            RecoverConditionTarget('actor', broken_conditions, None), Condition.BROKEN,
            TestRequest('probe:broken:test', InlineProfile(2, 3)), Skill.WILLPOWER, True))
    broken_dice = ScriptedDice((1, 10))
    recovered = execute_recover_action(alternative_source, broken_dice)
    assert recovered.resolution.conditions == broken_conditions.without_condition(Condition.BROKEN)
    assert recovered.resolution.conditions.has(Condition.PRONE)
    assert recovered.resolution.conditions.has(Condition.STAGGERED)
    assert recovered.slot.executed and broken_dice.calls == 2
    expect_rejection(lambda: execute_recover_action(replace(
        alternative_source, actor_has_enemy_in_zone=True), ScriptedDice(())),
        'Broken characters can Recover only in a safe Zone')
    print('ALTERNATIVE RECOVER K1: safe Broken Willpower succeeds in 2 draws; Prone/Staggered retained; unsafe Zone rejected')

    # Two independent experiments from the same immutable K1 input. A future
    # journal must compare the full witness, not just an equal resulting state.
    other_dice = ScriptedDice((2, 9))
    other = execute_recover_action(alternative_source, other_dice)
    assert other.round_state == recovered.round_state
    assert other.resolution.conditions == recovered.resolution.conditions
    assert other.resolution.test_result.trace != recovered.resolution.test_result.trace
    assert other != recovered and other_dice.calls == 2
    print('SOURCE PROOF K1: equal Recover post-state/IDs with different actual dice traces; full witnesses differ')

    assert final == snapshot and diagnose_npc_magic_unsupported(scenario, final, 'probe:still').reason is Reason.END_TURN
    draws = casting_draws + table_draws + shot_dice.calls + broken_dice.calls + other_dice.calls
    assert draws == 12 and getstate() == global_rng
    print('GAP: K1 stand/Recover results remain external; current full owner still Prone/END_TURN; no future policy/journal/root fabricated')
    print('12 scripted d10; existing public APIs only; global RNG unchanged; contract evidence, not automatic battle continuation')


if __name__ == '__main__':
    main()
