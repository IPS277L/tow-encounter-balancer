"""ADR-0052 finite contract proof; no new consumer or manual root projection.

Copy with stationary_wound_runner.py and magic_scenario.py. Authored profiles.
PG1.4 Rules116/119/122-123, Wounds190; GM1.1 Champions92.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.movement_models import FreeMoveProneRemovalRequest, ProneRemovalTargetKind
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome, NpcMagicUnsupportedReason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest, NpcRosterLegSpasmStandResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.npc_roster_leg_spasm_resolution import stand_npc_roster_leg_spasm


def main():
    global_rng = getstate()
    source = authored_input()
    source_before = deepcopy(source)
    hit = (1, 2, 3, 10, 10, 10)
    values = (*hit, 9, *((10,) * 9), *hit, 4, 5)
    assert len(values) == 24
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == 24 and result.source is source
    assert result.outcome is NpcMagicScenarioOutcome.UNSUPPORTED_PATH
    assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    current = result.current
    current_before = deepcopy(current)
    stands = tuple(s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
    assert len(stands) == 1
    prior_step = stands[0]
    prior = prior_step.result
    assert prior.source.state == prior_step.before and prior.state == prior_step.after
    assert stand_npc_roster_leg_spasm(prior.source) == prior
    assert prior.source.actor_id == current.wizard.actor_id == 'wizard'
    old_injury = prior.state.roster.participant('wizard').state.injury
    injury = current.roster.participant('wizard').state.injury
    assert tuple(w.entry_id for w in injury.wounds) == (WoundEntryId.LEG_SPASM,) * 2
    assert tuple(w.table_total for w in injury.wounds) == (9, 9)
    assert tuple(w.roll_values for w in injury.wounds) == ((9,), (4, 5))
    assert injury.wounds[:1] == old_injury.wounds
    assert all(w.effect_resolved and not w.treated and not w.healed for w in injury.wounds)
    first, second = (w.sequence for w in injury.wounds)
    old_prone = WoundConditionEffect(first, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)
    new_prone = WoundConditionEffect(second, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)
    terrains = tuple(WoundRestrictionEffect(sequence, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
        WoundEffectDuration.UNTIL_TREATED) for sequence in (first, second))
    assert prior.removed_effects == (old_prone,)
    assert old_injury.active_wound_effects == (terrains[0],)
    assert injury.active_wound_effects == (terrains[0], new_prone, terrains[1])
    assert injury.conditions.conditions == {Condition.PRONE}
    attacks = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterChampionAttackResult))
    assert len(attacks) == 2
    assert attacks[1].source.state.roster.participant('wizard').state.injury == old_injury
    assert attacks[1].source.attack.stationary_wounds is not None
    assert attacks[1].source.attack.execution.kernel_request.can_target_leave_zone is False
    champion = current.champion_attack
    assert champion is not None and current.minion_attack is not None
    assert current.roster == champion.roster == current.minion_attack.roster
    assert len(champion.daily_wounds.receipts) == len(champion.consumed_wound_roll_ids) == 2
    for attack, receipt, wound in zip(attacks, champion.daily_wounds.receipts, injury.wounds, strict=True):
        assert attack.attack.completion.daily_registration.receipt == receipt
        # Daily registration precedes effect resolution; its immutable record stays unresolved.
        assert not receipt.wound.effect_resolved
        assert replace(receipt.wound, effect_resolved=True) == wound
        assert receipt.source_request_id + '-lifecycle' in champion.consumed_wound_roll_ids
        assert attack.attack.execution.request_id in champion.consumed_execution_ids
        assert attack.attack.execution.request_id in current.consumed_execution_ids
    assert not current.wound_expiries
    assert current.round_state.round_number == 2
    assert current.round_state.active_turn.actor_id == 'wizard'
    assert not current.round_state.active_turn.action_slots[0].executed
    assert 'wizard' not in current.spatial_state.free_move_used_entity_ids
    assert current.spatial_state.placements == source.initial_frame.key.placements
    print('ACTUAL: 24 scripted d10; first9 -> stand -> Casting/end -> second9; actor-injury stop')
    print('HISTORY: exact prior StandResult; rolls (9)/(4,5); old terrain + new Prone + new terrain; both child owners')

    # Rejection is the current public constructor's boundary, not a future validator.
    try:
        NpcRosterLegSpasmStandRequest('repeat:old-admission', current, 'wizard', False, True)
    except ValueError as error:
        assert 'canonical effect pair' in str(error)
    else:
        raise AssertionError('old stand unexpectedly admitted a previously removed Prone cause')
    assert dice.calls == 24
    print('CURRENT CONSUMER: stand48 rejects missing old Prone pair before execution; no additional RNG')

    # This fixture explicitly supplies every hostile range; no distance inferred from a Zone.
    enemies = tuple(p.state.actor_id for p in current.roster.participants
        if p.state.side is not current.roster.participant('wizard').state.side)
    for enemy in enemies:
        pairs = tuple(p for p in source.initial_frame.pair_ranges
            if {p.first_actor_id, p.second_actor_id} == {'wizard', enemy})
        assert len(pairs) == 1 and pairs[0].target_range is not RangedWeaponRange.CLOSE
    primitive_request = FreeMoveProneRemovalRequest('repeat:k1-only', current.round_state,
        current.spatial_state, 'wizard', ProneRemovalTargetKind.SELF, 'wizard',
        injury.conditions, None, False)
    primitive = resolve_free_move_prone_removal(primitive_request)
    assert not primitive.target_conditions.has(Condition.PRONE)
    assert primitive.state.free_move_used_entity_ids == (*current.spatial_state.free_move_used_entity_ids, 'wizard')
    assert primitive.state.placements == current.spatial_state.placements
    assert primitive.round_state == current.round_state
    assert current == current_before and injury.conditions.has(Condition.PRONE)
    assert injury.active_wound_effects == (terrains[0], new_prone, terrains[1])
    print('K1 ONLY: Condition removal and one free move; no crossing/Test; owner/injury deliberately unchanged')

    legacy = authored_input(stationary=False)
    legacy_before = deepcopy(legacy)
    legacy_dice = ScriptedDice((*hit, 9))
    legacy_result = run_npc_magic_scenario(legacy, legacy_dice)
    assert legacy_dice.calls == 7
    assert legacy_result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert legacy_result.current == prior.source.state
    assert not any(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in legacy_result.steps)
    assert source == source_before and legacy == legacy_before and current == current_before
    assert getstate() == global_rng
    print('NONE CONTROL: 7 scripted d10; first9 stop; no stand')
    print('31 scripted d10 total; sources/global RNG immutable; finite proof, no new consumer or owner projection')


if __name__ == '__main__':
    main()
