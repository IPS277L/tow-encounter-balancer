"""Finite ADR-0045 evidence through existing public K1/M8 APIs.

PG1.4 Magic in the Old World pp156-159, Rules pp114,118,122-123.
Prepared/rolled values remain external because the future prefix owner does
not exist yet. Final root projection below is explicitly manual, not a new
consumer, journal phase, resumed runner, or general range selector.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.action_execution_models import CastingActionMiscastPreparationRequest
from towr.domain.condition_models import Condition
from towr.domain.magic_models import MiscastPreparationRequest, MiscastTableEntryId
from towr.domain.miscast_effect_models import MiscastEffectTarget, MiscastUnnaturalWindRequest
from towr.domain.npc_magic_journal_policy import magic_live_ids, magic_scene_key
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_scene_models import NpcMagicPairRange, NpcMagicSceneKey
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatRoundState
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.casting_action_execution import prepare_casting_action_miscast
from towr.rules.miscast_effect_resolution import resolve_unnatural_wind
from towr.rules.miscast_resolution import resolve_miscast_roll


def archived_scenario():
    """Fresh source: ally defeats one enemy before the Wizard's real trigger."""
    source = authored_scenario()
    old = source.initial
    enemy = old.roster.participant('enemy')
    clone = replace(enemy, state=replace(enemy.state, actor_id='enemy2'))
    roster = NpcRoster((*old.roster.participants, clone))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = replace(old.spatial_state, placements=(*old.spatial_state.placements,
        replace(old.spatial_state.placement_for('enemy'), entity_id='enemy2')))
    initial = replace(old, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=replace(old.champion_attack, roster=roster, round_state=combat))
    actors = tuple(replace(a, target_actor_ids=('enemy', 'enemy2'), defeat_decisions=(
        *a.defeat_decisions, replace(a.defeat_decisions[0], target_id='enemy2')))
        if a.actor_id == 'ally' else a for a in source.actors)
    enemy_policy = source.policy_for('enemy')
    actors = (*actors, replace(enemy_policy, actor_id='enemy2', defeat_decisions=tuple(
        replace(d, attacker_id='enemy2') for d in enemy_policy.defeat_decisions)))
    first = source.initial_frame
    complete = replace(first, key=NpcMagicSceneKey(spatial.placements, ('wizard', 'ally', 'enemy', 'enemy2')),
        pair_ranges=(*first.pair_ranges, NpcMagicPairRange('wizard', 'enemy2', Range.SHORT, False, False),
            NpcMagicPairRange('ally', 'enemy2', Range.SHORT, False, False)),
        give_ground_plans=(*first.give_ground_plans, replace(first.give_ground_plans[0], actor_id='enemy2')),
        attack_departures=(*first.attack_departures, replace(first.attack_departures[-1], actor_id='enemy2')))
    after_defeat = replace(complete,
        key=NpcMagicSceneKey(spatial.placements, ('wizard', 'ally', 'enemy2')),
        pair_ranges=tuple(p for p in complete.pair_ranges if 'enemy' not in (p.first_actor_id, p.second_actor_id)),
        give_ground_plans=tuple(p for p in complete.give_ground_plans if p.actor_id != 'enemy'),
        attack_departures=tuple(p for p in complete.attack_departures if p.actor_id != 'enemy'))
    return replace(source, initial=initial, actors=actors, activation_order=('ally', 'wizard', 'enemy', 'enemy2'),
        scene_frames=(complete, after_defeat), objective=NpcDefeatObjective(('enemy', 'enemy2')))


def prepare_declined(source, casting_values):
    before = deepcopy(source)
    dice = ScriptedDice(casting_values)
    stopped = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(casting_values) and source == before
    assert stopped.unsupported.reason is Reason.MISCAST_PREPARATION
    root = stopped.current
    pending = root.pending_miscast
    assert pending is not None and root.pending_interruption is None
    assert pending.magic_state == root.wizard.magic_state
    # This is an explicit caller decision. No available spell is auto-cast and
    # no future policy/request type is invented in this historical API proof.
    preparation = MiscastPreparationRequest('probe:decline', pending.pending_miscast,
        root.wizard.magic_state, spell_to_cast=None)
    prepared = prepare_casting_action_miscast(CastingActionMiscastPreparationRequest(
        'probe:bound-preparation', pending.post_test, preparation))
    assert prepared.state.miscast_dice == root.wizard.magic_state.miscast_dice == 3
    assert prepared.state.casting_successes == 0 and prepared.state.casting_lore_id is None
    assert prepared.state.latest_casting_roll_successes == 0
    assert len(prepared.preparation.follow_ups) == 1
    roll = prepared.preparation.follow_ups[0]
    assert roll.bonus_dice == 0 and roll.pool_dice_count == 3
    return root, prepared, roll, dice.calls


def manual_wind_projection(source, root, roll, *, no_cross_zone_close, no_external_short_range_creatures):
    """One authored same-Zone experiment; this is not production discovery."""
    assert no_cross_zone_close is True
    # A complete combat roster alone does not exclude nearby noncombatants.
    assert no_external_short_range_creatures is True
    assert source.facts.all_combatants_included and source.facts.unmounted_combatants_only
    assert source.facts.no_effect_immunities
    frame = source.frame_for(magic_scene_key(root))
    assert frame is not None
    wizard = root.wizard.actor_id
    zone = root.spatial_state.placement_for(wizard).zone_id
    distances = {z.zone_id: z.target_range for z in frame.zone_ranges}
    assert distances[zone] is Range.SHORT
    live = magic_live_ids(root)
    # Explicit no-cross-Zone-Close assertion is essential: PG114 allows Close
    # across a Zone boundary, so same Zone is not a universal range algorithm.
    selected = (wizard, *(p.state.actor_id for p in root.roster.participants
        if p.state.actor_id != wizard and p.state.actor_id in live
        and root.spatial_state.placement_for(p.state.actor_id).zone_id == zone))
    for actor in live:
        if actor not in selected:
            assert distances[root.spatial_state.placement_for(actor).zone_id] in (Range.MEDIUM, Range.LONG)
    targets = tuple(MiscastEffectTarget(actor, root.roster.participant(actor).definition.injury_policy,
        root.roster.participant(actor).state.injury) for actor in selected)
    application = resolve_unnatural_wind(MiscastUnnaturalWindRequest(
        'probe:wind', roll.effect_request, roll.state, targets))
    assert application.magic_state.miscast_dice == 0
    updates = {t.target_id: t.state for t in application.targets}
    assert tuple(updates) == selected
    assert all(updates[actor].conditions.has(Condition.PRONE) for actor in selected)
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=updates[p.state.actor_id]))
        if p.state.actor_id in updates else p for p in root.roster.participants))
    final = replace(root, roster=roster, pending_miscast=None,
        wizard=replace(root.wizard, magic_state=application.magic_state),
        champion_attack=replace(root.champion_attack, roster=roster),
        minion_attack=replace(root.minion_attack, roster=roster))
    for field in fields(root):
        if field.name not in ('roster', 'wizard', 'pending_miscast', 'champion_attack', 'minion_attack'):
            assert getattr(final, field.name) == getattr(root, field.name)
    for old, new in ((root.champion_attack, final.champion_attack), (root.minion_attack, final.minion_attack)):
        for field in fields(old):
            if field.name != 'roster':
                assert getattr(new, field.name) == getattr(old, field.name)
    for old, new in zip(root.roster.participants, final.roster.participants):
        if old.state.actor_id not in selected:
            assert old == new
        else:
            assert new.state.injury.conditions == old.state.injury.conditions.with_condition(Condition.PRONE)
            assert replace(new.state.injury, conditions=old.state.injury.conditions) == old.state.injury
    stop = diagnose_npc_magic_unsupported(source, final, 'probe:after-wind')
    assert stop.reason is Reason.END_TURN
    try:
        NpcWoundTurnEndRequest('probe:end', final, wizard)
    except ValueError as error:
        assert 'unsupported end-turn Condition' in str(error)
    else:
        raise AssertionError('Prone end-turn is not admitted by the current boundary')
    return final, selected


def main():
    global_rng = getstate()
    source = authored_scenario()
    source_before = deepcopy(source)
    root, prepared, roll_request, draws = prepare_declined(source, (9, 9, 9))
    root_before = deepcopy(root)
    try:
        replace(root, wizard=replace(root.wizard, magic_state=prepared.state))
    except ValueError as error:
        assert 'pending Miscast must match' in str(error)
    else:
        raise AssertionError('old pending cannot represent prepared magic')
    print('PREFIX GAP: current root rejects prepared magic under old pending; future typed prefix is required')
    total_draws = 0
    for index, values in enumerate(((7, 7, 7), (7, 7, 8))):
        # Separate fresh experiments, never a second roll of one staged prefix.
        experiment = source if index == 0 else replace(authored_scenario(), id='probe:wind22')
        if index == 0:
            current, prep, pending_roll, calls = root, prepared, roll_request, draws
        else:
            current, prep, pending_roll, calls = prepare_declined(experiment, (9, 9, 9))
        rng = ScriptedDice(values)
        rolled = resolve_miscast_roll(pending_roll, prep.state, rng)
        assert rng.calls == 3 and rolled.state.miscast_dice == 3
        assert rolled.entry.id is MiscastTableEntryId.UNNATURAL_WIND
        final, targets = manual_wind_projection(experiment, current, rolled,
            no_cross_zone_close=True, no_external_short_range_creatures=True)
        assert root == root_before and source == source_before
        total_draws += calls + rng.calls
        print(f'WIND {rolled.total}: 3 Casting + 3 table d10; targets={targets}; pool3->0; actual unsupported_end_turn')

    outside = authored_scenario()
    spatial = replace(outside.initial.spatial_state, placements=outside.scene_frames[1].key.placements)
    outside = replace(outside, initial=replace(outside.initial, spatial_state=spatial))
    archive = archived_scenario()
    cases = (
        ('OUTSIDE', outside, (9, 9, 9)),
        ('ARCHIVE', archive, (1, 2, 3, 10, 10, 10, 9, 9, 9)),
        ('AVAILABLE SPELL DECLINED', source, (1, 9, 9) + (10,) * 12 + (1, 1, 9)),
    )
    for label, scenario, values in cases:
        current, prep, pending_roll, calls = prepare_declined(scenario, values)
        snapshot = deepcopy(current)
        rng = ScriptedDice((7, 7, 7))
        rolled = resolve_miscast_roll(pending_roll, prep.state, rng)
        final, targets = manual_wind_projection(scenario, current, rolled,
            no_cross_zone_close=True, no_external_short_range_creatures=True)
        assert rng.calls == 3 and current == snapshot
        if label == 'OUTSIDE':
            assert targets == ('wizard', 'ally')
            assert final.roster.participant('enemy') == current.roster.participant('enemy')
        elif label == 'ARCHIVE':
            assert current.roster.participant('enemy').state.injury.defeated
            assert targets == ('wizard', 'ally', 'enemy2')
            assert final.round_state.excluded_turn_entity_ids == ('enemy',)
            assert len(final.roster.participants) == len(final.spatial_state.placements) == 4
        else:
            assert current.wizard.magic_state.casting_successes == 3
            assert prep.preparation.previous_casting_successes == 3 and pending_roll.bonus_dice == 0
        total_draws += calls + rng.calls
        print(f'{label}: {calls} prior + 3 table d10; targets={targets}; root/archives/histories preserved')

    other_source = replace(authored_scenario(), id='probe:other30')
    other_root, other_preparation, other_request, calls = prepare_declined(other_source, (9, 9, 9))
    other_before = deepcopy(other_root)
    rng = ScriptedDice((10, 10, 10))
    other = resolve_miscast_roll(other_request, other_preparation.state, rng)
    assert rng.calls == 3 and other.total == 30 and other.state.miscast_dice == 3
    assert other.entry.id is not MiscastTableEntryId.UNNATURAL_WIND
    assert other_root == other_before and other_root.pending_miscast is not None
    total_draws += calls + rng.calls
    print('OTHER ROW 30: one retained K1 roll/pool3; no effect, cleanup or retry; not a published future prefix')
    assert getstate() == global_rng
    print(f'{total_draws} scripted d10; public APIs plus manual final projection; no new consumer/journal/runner; global RNG unchanged')


if __name__ == '__main__':
    main()
