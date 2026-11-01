"""ADR-0048 public full-owner stand after an actual registered Wound9.

Copy together with magic_scenario.py. PG1.4 Rules pp116,122-123 and
Wounds Table p190; GM1.1 Champions p92. Numeric profiles/facts are authored.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRestriction
from towr.domain.npc_magic_scenario_models import NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_leg_spasm_resolution import (
    stand_npc_roster_leg_spasm, apply_npc_roster_leg_spasm_stand,
)


def wounded_case(values, entry, *, opted):
    policy = NpcMagicMiscastContinuationPolicy(
        NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
        NpcRosterMiscastFacts(True, True, True, True, True),
        NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)
    source = replace(authored_scenario(wizard_side=CombatSide.OPPOSITION),
                     miscast_continuation=policy if opted else None)
    before = deepcopy(source)
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(values) and source == before
    assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    state = result.current
    injury = state.roster.participant('wizard').state.injury
    assert injury.wounds[-1].entry_id is entry
    assert all(w.effect_resolved and not w.treated and not w.healed for w in injury.wounds)
    assert state.champion_attack.pending is None
    assert state.roster == state.champion_attack.roster == state.minion_attack.roster
    assert len(state.champion_attack.daily_wounds.receipts) == len(injury.wounds)
    assert len(state.champion_attack.consumed_wound_roll_ids) == len(injury.wounds)
    return source, state


def expect_rejection(operation, error_type):
    try:
        operation()
    except error_type:
        return
    raise AssertionError('unsupported or stale transition unexpectedly accepted')


def main():
    global_rng = getstate()
    hit = (1, 2, 3, 10, 10, 10)
    for opted in (False, True):
        source, old = wounded_case((*hit, 9), WoundEntryId.LEG_SPASM, opted=opted)
        before = deepcopy(old)
        # The complete authored hostile-pair snapshot proves no enemy Close.
        assert old.spatial_state.placements == source.initial_frame.key.placements
        enemies = {p.state.actor_id for p in old.roster.participants
                   if p.state.side is not old.roster.participant('wizard').state.side}
        pairs = tuple(p for p in source.initial_frame.pair_ranges
                      if 'wizard' in (p.first_actor_id, p.second_actor_id))
        assert {next(a for a in (p.first_actor_id, p.second_actor_id) if a != 'wizard')
                for p in pairs} == enemies
        assert all(p.target_range is not RangedWeaponRange.CLOSE for p in pairs)
        # Authored scene excludes external causes; Wound9 itself permits removal.
        assert source.facts.no_external_condition_sources
        request = NpcRosterLegSpasmStandRequest('example:leg-spasm:stand', old, 'wizard', False, True)
        result = stand_npc_roster_leg_spasm(request)
        current = apply_npc_roster_leg_spasm_stand(old, result)
        injury = current.roster.participant('wizard').state.injury
        original = old.roster.participant('wizard').state.injury
        assert not injury.conditions.has(Condition.PRONE)
        assert injury.wounds == original.wounds
        assert injury.active_wound_effects == tuple(e for e in original.active_wound_effects
                                                   if e not in result.removed_effects)
        assert len(injury.active_wound_effects) == 1
        assert injury.active_wound_effects[0].restriction is WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN
        assert current.spatial_state == replace(old.spatial_state,
            free_move_used_entity_ids=(*old.spatial_state.free_move_used_entity_ids, 'wizard'))
        for field in fields(old):
            if field.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                assert getattr(current, field.name) == getattr(old, field.name), field.name
        for name in ('champion_attack', 'minion_attack'):
            child = getattr(current, name)
            assert child == replace(getattr(old, name), roster=current.roster)
        assert current.roster == current.champion_attack.roster == current.minion_attack.roster
        assert old == before
        expect_rejection(lambda: apply_npc_roster_leg_spasm_stand(current, result), ValueError)
        stale = replace(old, consumed_execution_ids=(*old.consumed_execution_ids, 'foreign'))
        expect_rejection(lambda: apply_npc_roster_leg_spasm_stand(stale, result), ValueError)
        expect_rejection(lambda: validate_magic_step_policy(source, NpcMagicStep(result)), ValueError)
        assert diagnose_npc_magic_unsupported(source, current, request.id).reason is NpcMagicUnsupportedReason.ACTOR_INJURY
        label = 'opted' if opted else 'None'
        print(f'WOUND 9 / {label}: 7 d10; actual registered wound; runner stops at actor injury')
        print('BOUND STAND: Prone/cause removed; one free move; terrain/wound/daily/roll history retained')
        print('OWNER: both child rosters synchronized; positions/actions/magic unchanged; source immutable')
        print('GUARDS: stale/replay rejected; runner still stops; result excluded from automatic journal')

    for entry, values in (
        (WoundEntryId.CRUSHED_RIB, (*hit, 10)),
        (WoundEntryId.TORN_LEG, (*hit, 3, *((10,) * 9), *hit, 6, 7)),
    ):
        _, state = wounded_case(values, entry, opted=True)
        before = deepcopy(state)
        expect_rejection(lambda: NpcRosterLegSpasmStandRequest(
            'example:foreign-wound', state, 'wizard', False, True), ValueError)
        assert state == before
        total = state.roster.participant('wizard').state.injury.wounds[-1].table_total
        print(f'WOUND {total} CONTROL: {len(values)} d10; bound Leg Spasm stand rejected; source immutable')
    assert getstate() == global_rng
    print('45 scripted d10 total; public APIs only; no stand RNG/Test/treatment/healing')


if __name__ == '__main__':
    main()
