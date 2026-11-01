"""Finite Wound9 contract evidence, not a future full-owner implementation.

Copy together with magic_scenario.py. PG1.4 Rules pp116,122-123 and
Wounds Table p190; GM1.1 Champions p92. Authored numeric profiles/facts.
Actual fresh runner stops are separate from one standalone K1 stand primitive.
No guessed continuation, patched injury, treatment, healing or Monte Carlo.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.movement_models import FreeMoveProneRemovalRequest, ProneRemovalTargetKind
from towr.domain.npc_magic_scenario_models import NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome, NpcMagicUnsupportedReason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal


def wounded_case(values, entry_id, *, opted=True):
    """The first side shoots before Wizard acts; inputs are always fresh."""
    policy = NpcMagicMiscastContinuationPolicy(
        NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
        NpcRosterMiscastFacts(
            all_combatants_in_roster=True, no_external_short_range_creatures=True,
            unmounted_combatants_only=True, no_effect_immunities=True,
            no_cross_zone_close=True),
        NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)
    source = replace(authored_scenario(wizard_side=CombatSide.OPPOSITION),
                     miscast_continuation=policy if opted else None)
    original = deepcopy(source)
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert source == original and result.source is source and dice.calls == len(values)
    assert result.outcome is NpcMagicScenarioOutcome.UNSUPPORTED_PATH
    assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert result.unsupported.actor_id == 'wizard'
    state = result.current
    assert state.round_state.active_turn.actor_id == 'wizard'
    assert not state.round_state.active_turn.action_slots[0].executed
    assert state.champion_attack.pending is None
    injury = state.roster.participant('wizard').state.injury
    assert injury.wounds[-1].entry_id is entry_id
    assert all(w.effect_resolved and not w.treated and not w.healed for w in injury.wounds)
    attacks = tuple(step.result for step in result.steps
                    if isinstance(step.result, NpcRosterChampionAttackResult))
    assert attacks[-1].attack.pending_follow_ups == ()
    assert len(state.champion_attack.daily_wounds.receipts) == len(injury.wounds)
    assert len(state.champion_attack.consumed_wound_roll_ids) == len(injury.wounds)
    assert state.roster == state.champion_attack.roster == state.minion_attack.roster
    assert state.round_state == state.champion_attack.round_state
    return source, result, dice.calls


def rejects_bound_stand(state):
    """Existing ADR46 owner must not silently admit an ongoing Wound cause."""
    try:
        NpcRosterProneStandRequest('probe:bound-stand', state, 'wizard', False, True)
    except ValueError as error:
        assert 'unsupported ongoing Wound effects' in str(error), str(error)
        return
    raise AssertionError('existing bound stand unexpectedly admitted an ongoing Wound')


def main():
    global_rng = getstate()
    hit = (1, 2, 3, 10, 10, 10)
    source, leg, calls = wounded_case((*hit, 9), WoundEntryId.LEG_SPASM)
    state = leg.current
    original = deepcopy(state)
    injury = state.roster.participant('wizard').state.injury
    prone = WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)
    terrain = WoundRestrictionEffect(1, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                                     WoundEffectDuration.UNTIL_TREATED)
    assert injury.active_wound_effects == (prone, terrain)
    assert injury.conditions.has(Condition.PRONE) and not injury.dead
    rejects_bound_stand(state)
    print(f'WOUND 9: {calls} d10; actual unsupported_actor_injury; resolved Leg Spasm; no pending')

    # K1 only: this produces Conditions/spatial state, NOT a changed full owner.
    # Exact supplied hostile pair facts prove no enemy Close; same Zone alone
    # is deliberately not used as the range test.
    assert all(pair.target_range is not RangedWeaponRange.CLOSE
               for pair in source.initial_frame.pair_ranges
               if 'wizard' in (pair.first_actor_id, pair.second_actor_id))
    request = FreeMoveProneRemovalRequest(
        'probe:k1-only-stand', state.round_state, state.spatial_state, 'wizard',
        ProneRemovalTargetKind.SELF, 'wizard', injury.conditions, None, False)
    primitive = resolve_free_move_prone_removal(request)
    assert primitive.target_conditions == injury.conditions.without_condition(Condition.PRONE)
    assert primitive.state == replace(state.spatial_state,
        free_move_used_entity_ids=(*state.spatial_state.free_move_used_entity_ids, 'wizard'))
    assert primitive.state.placements == state.spatial_state.placements
    assert primitive.round_state == state.round_state
    assert state == original and state.roster.participant('wizard').state.injury == injury
    assert injury.active_wound_effects == (prone, terrain)
    assert not injury.wounds[0].treated and not injury.wounds[0].healed
    print('K1 ONLY: Prone removed in primitive result; free move spent; positions/turn unchanged; no RNG')
    print('OWNER GAP: original Prone/effects/daily history unchanged; terrain must survive a future bound stand')

    _, legacy, legacy_calls = wounded_case((*hit, 9), WoundEntryId.LEG_SPASM, opted=False)
    assert legacy.current.roster.participant('wizard').state.injury == injury
    print(f'LEGACY CONTROL: {legacy_calls} d10; same honest actor-injury stop; no opt-in bypass')

    _, rib, rib_calls = wounded_case((*hit, 10), WoundEntryId.CRUSHED_RIB)
    rib_injury = rib.current.roster.participant('wizard').state.injury
    assert rib_injury.active_wound_effects == (
        WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED),
        WoundRestrictionEffect(1, WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST))
    assert not rib_injury.conditions.has(Condition.PRONE)
    print(f'WOUND 10 CONTROL: {rib_calls} d10; Drained plus next-Test Grim, not Leg Spasm')

    # First superficial Wound3, failed Wizard cast/allied shot, then Wound13
    # from two dice. Every injury and daily receipt comes from actual attacks.
    _, torn, torn_calls = wounded_case((*hit, 3, *((10,) * 9), *hit, 6, 7), WoundEntryId.TORN_LEG)
    torn_injury = torn.current.roster.participant('wizard').state.injury
    assert tuple(w.table_total for w in torn_injury.wounds) == (3, 13)
    assert torn_injury.active_wound_effects == (
        WoundConditionEffect(2, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
        WoundRestrictionEffect(2, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
                               WoundEffectDuration.UNTIL_TREATED))
    rejects_bound_stand(torn.current)
    print(f'WOUND 13 CONTROL: {torn_calls} d10; Prone plus critical-on-removal; bound stand still rejected')
    assert getstate() == global_rng
    print('Public APIs only; fresh runner evidence; immutable sources/global RNG; no future continuation fabricated')


if __name__ == '__main__':
    main()
