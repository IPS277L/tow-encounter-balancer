"""Standalone public bound API example of ADR-0045 Unnatural Wind21-22.

PG1.4 VIII Magic pp156-159; V Range p114, Prone p123; GM1.1 VII pp91-92.
Numeric profiles and scope/GM facts are authored, not named book NPCs.
Fresh Casting cases and an explicit already-Prone bound input are separate.
No manual effect projection, automatic runner continuation or interruption claim.
"""
from copy import deepcopy
from dataclasses import dataclass, fields, replace
from random import getstate

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.cowardly_flight_casting_models import CastingCasterDefinition, CowardlyFlightCastingPolicy
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import COWARDLY_FLIGHT_SPELL_DEFINITION, WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import NpcMagicActorPolicy, NpcMagicScenario, NpcMagicScenarioFacts
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind, NpcMagicGiveGroundPlan,
    NpcMagicPairRange, NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey, NpcMagicZoneRange,
)
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcCastingWizardState, NpcRosterCastingState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastFacts, NpcRosterMiscastPolicy, NpcRosterMiscastPreparationRequest,
    NpcRosterMiscastRollRequest, NpcRosterUnnaturalWindRequest,
)
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.rules.npc_roster_miscast_resolution import (
    prepare_npc_roster_miscast, apply_npc_roster_miscast_preparation,
    roll_npc_roster_miscast, apply_npc_roster_miscast_roll,
    resolve_npc_roster_unnatural_wind, apply_npc_roster_unnatural_wind,
)



@dataclass(slots=True)
class ScriptedDice:
    values: tuple[int, ...]
    calls: int = 0

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (1, 10) and self.calls < len(self.values), 'unexpected RNG draw'
        value = self.values[self.calls]
        self.calls += 1
        assert low <= value <= high
        return value


def authored_scenario(*, wizard_side: CombatSide = CombatSide.PLAYERS_AND_ALLIES) -> NpcMagicScenario:
    """Three fixed actors, explicit frames, ordinary bows and one memorised Curse.

    No armour/shield/reload, hidden actors, additional rules or external causes.
    Same Zone explicitly means Short here. The ordered facts below are authored;
    no range, route or departure availability is discovered from the graph.
    """
    provenance = 'example:ADR-0037:authored'
    shot = NpcAttackProfile('shot', provenance, Skill.SHOOTING, InlineProfile(3, 3), DamageProfile(3),
        Range.SHORT, Range.LONG, RangedWeaponHands.TWO_HANDED)
    protection = (NpcProtectionProfile(provenance, Skill.ATHLETICS, InlineProfile(3, 3)),)
    wizard = NpcDefinition('authored:wizard', provenance, TargetInjuryPolicy.CHAMPION, None,
        ResilienceProfile(4), (), protection)
    minion = NpcDefinition('authored:archer', provenance, TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3), (shot,), protection)
    opposite = next(side for side in CombatSide if side is not wizard_side)
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor, definition.id, side, CharacterInjuryState() if actor == 'wizard' else ProfileInjuryState(0, 1),
        () if actor == 'wizard' else ('shot',), definition.resilience, actor != 'wizard', False,
    )) for actor, definition, side in (
        ('wizard', wizard, wizard_side), ('ally', minion, wizard_side), ('enemy', minion, opposite))))
    combat = CombatRoundState(1, roster.turn_participants)
    graph = ZoneGraph(('arena', 'shelter', 'boundary'),
        (ZoneConnection('arena', 'shelter'), ZoneConnection('shelter', 'boundary')))
    # Spatial order deliberately differs from roster/activation order.
    spatial = SpatialBattleState(graph, tuple(SpatialEntityPlacement(actor,
        roster.participant(actor).state.side.value, 'arena') for actor in ('enemy', 'wizard', 'ally')))
    state = NpcRosterCastingState(roster, NpcCastingWizardState('wizard', CastingCasterDefinition(
        'authored:caster', provenance, 2, InlineProfile(3, 3)), WizardMagicState()), combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState('example:day', 'wizard')))
    actors = (
        NpcMagicActorPolicy('wizard', InlineProfile(3, 3), MovementSpeed.NORMAL, (), (), None,
            CowardlyFlightCastingPolicy.CAST_WHEN_READY, graph.zone_ids),
        NpcMagicActorPolicy('ally', InlineProfile(3, 3), MovementSpeed.NORMAL, ('enemy',),
            (MinionDefeatDecision('ally', 'enemy', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
        NpcMagicActorPolicy('enemy', InlineProfile(3, 3), MovementSpeed.NORMAL, ('wizard', 'ally'),
            (MinionDefeatDecision('enemy', 'ally', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
    )
    route = NpcMagicRouteFacts((), False, False)
    frames = []
    for zone, distance, destination, departures in (
        ('arena', Range.SHORT, 'shelter', (True, True, True)),
        ('shelter', Range.MEDIUM, 'boundary', (False, False, True)),
        ('boundary', Range.LONG, None, (False, False, False)),
    ):
        positions = tuple(replace(p, zone_id=zone) if p.entity_id == 'enemy' else p for p in spatial.placements)
        broken = (() if zone == 'arena' else (NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER,
            (), None, None, None, True),))
        frames.append(NpcMagicSceneFrame(NpcMagicSceneKey(positions, ('wizard', 'ally', 'enemy')),
            (NpcMagicPairRange('wizard', 'enemy', distance, False, False),
             NpcMagicPairRange('ally', 'enemy', distance, False, False)),
            (NpcMagicZoneRange('arena', Range.SHORT), NpcMagicZoneRange('shelter', Range.MEDIUM),
             NpcMagicZoneRange('boundary', Range.LONG)),
            (NpcMagicGiveGroundPlan('enemy', destination is not None, destination,
                route if destination else None, destination is None),), broken,
            tuple(NpcMagicAttackDeparture(actor.actor_id, can_leave) for actor, can_leave in zip(actors, departures))))
    facts = NpcMagicScenarioFacts(
        authored_wizard_profile=True, targets_aware=True, clear_line_of_sight=True,
        all_combatants_included=True, unmounted_combatants_only=True, no_additional_rules=True,
        no_other_test_modifiers=True, no_cover_or_concealment=True, no_terrain_or_obstacles=True,
        no_external_scene_changes=True, no_external_condition_sources=True, ammunition_sufficient=True,
        requires_reload_action=False, knows_battle_magic=True, spell_memorised=True, no_bulky_items=True,
        no_casting_opposition=True, no_mixing_winds=True, no_potency_modifiers=True, no_effect_immunities=True,
    )
    return NpcMagicScenario('example:magic', state, facts, ('wizard', 'ally', 'enemy'), actors, tuple(frames),
        wizard_side, NpcDefeatObjective(('enemy',)), 3, StaggerChoice.SUFFER_WOUND, COWARDLY_FLIGHT_SPELL_DEFINITION)


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


def fresh_pending(source, casting_values):
    before = deepcopy(source)
    rng = ScriptedDice(casting_values)
    stopped = run_npc_magic_scenario(source, rng)
    assert rng.calls == len(casting_values) and source == before
    assert stopped.unsupported.reason is Reason.MISCAST_PREPARATION
    assert stopped.current.pending_miscast is not None and stopped.current.pending_interruption is None
    return stopped.current, rng.calls


def prepare_and_roll(scenario, root, table_values, identifier):
    """Publish each actual bound result, retaining the complete prior source."""
    before = deepcopy(root)
    facts = NpcRosterMiscastFacts(
        all_combatants_in_roster=True, no_external_short_range_creatures=True,
        unmounted_combatants_only=True, no_effect_immunities=True, no_cross_zone_close=True,
    )
    preparation = prepare_npc_roster_miscast(NpcRosterMiscastPreparationRequest(
        identifier + ':decline', root, NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST, facts))
    prepared = apply_npc_roster_miscast_preparation(root, preparation)
    assert prepared.pending_miscast is None and prepared.pending_interruption is None
    assert prepared.pending_miscast_continuation is preparation
    assert preparation.source.state is root and prepared.wizard.magic_state == WizardMagicState(3)
    assert preparation.roll_request.bonus_dice == 0
    stop = diagnose_npc_magic_unsupported(scenario, prepared, 'caller:last')
    assert stop.reason is Reason.MISCAST_ROLL and stop.source_id == preparation.roll_request.resolution_id
    rng = ScriptedDice(table_values)
    rolled_result = roll_npc_roster_miscast(NpcRosterMiscastRollRequest(
        preparation.roll_request.resolution_id, prepared), rng)
    rolled = apply_npc_roster_miscast_roll(prepared, rolled_result)
    assert rng.calls == 3 and rolled.wizard.magic_state == prepared.wizard.magic_state
    assert rolled.pending_miscast_continuation is rolled_result
    assert rolled_result.source.state.pending_miscast_continuation is preparation
    for field in fields(prepared):
        if field.name != 'pending_miscast_continuation':
            assert getattr(rolled, field.name) == getattr(prepared, field.name)
    stop = diagnose_npc_magic_unsupported(scenario, rolled, 'caller:last')
    assert stop.reason is Reason.MISCAST_EFFECT and stop.source_id == rolled_result.effect_request.resolution_id
    assert root == before
    return preparation, rolled_result, rolled, rng.calls


def complete_wind(scenario, root, table_values, identifier):
    preparation, rolled_result, rolled, calls = prepare_and_roll(scenario, root, table_values, identifier)
    before = deepcopy(rolled)
    result = resolve_npc_roster_unnatural_wind(NpcRosterUnnaturalWindRequest(
        rolled_result.effect_request.resolution_id + ':apply', rolled))
    final = apply_npc_roster_unnatural_wind(rolled, result)
    targets = tuple(t.target_id for t in result.wind.targets)
    assert targets[0] == root.wizard.actor_id
    assert final.wizard.magic_state == WizardMagicState() and final.pending_miscast_continuation is None
    assert all(t.condition_application.condition is Condition.PRONE
               and t.condition_application.blocked is False for t in result.wind.targets)
    changed = {'roster', 'wizard', 'champion_attack', 'minion_attack', 'pending_miscast_continuation'}
    for field in fields(rolled):
        if field.name not in changed:
            assert getattr(final, field.name) == getattr(rolled, field.name)
    assert final.wizard.actor_id == rolled.wizard.actor_id and final.wizard.caster == rolled.wizard.caster
    for old, new in ((rolled.champion_attack, final.champion_attack), (rolled.minion_attack, final.minion_attack)):
        if old is None:
            assert new is None
        else:
            assert new.roster == final.roster
            for field in fields(old):
                if field.name != 'roster':
                    assert getattr(new, field.name) == getattr(old, field.name)
    for old, new in zip(rolled.roster.participants, final.roster.participants):
        if old.state.actor_id not in targets:
            assert new == old
        else:
            assert new.state.injury.conditions == old.state.injury.conditions.with_condition(Condition.PRONE)
            assert replace(new.state.injury, conditions=old.state.injury.conditions) == old.state.injury
            assert replace(new, state=replace(new.state, injury=old.state.injury)) == old
    assert rolled == before and result.source.state is rolled
    stop = diagnose_npc_magic_unsupported(scenario, final, identifier + ':after')
    assert stop.reason is Reason.END_TURN
    try:
        NpcWoundTurnEndRequest(identifier + ':end', final, final.wizard.actor_id)
    except ValueError as error:
        assert 'unsupported end-turn Condition' in str(error)
    else:
        raise AssertionError('Prone end-turn is not admitted by the current runner boundary')
    return final, result, preparation, calls


def authored_bound_prone_ally(root):
    """Explicit low-level input, not a fresh-runner-reachable Condition source.

    The actual Casting proof targets the enemy and stays unchanged. An authored
    already-Prone/Staggered ally is admitted by the low-level roster owner; this
    is input construction, never the projection of the Wind effect being shown.
    """
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
        conditions=p.state.injury.conditions.with_condition(Condition.PRONE).with_condition(Condition.STAGGERED))))
        if p.state.actor_id == 'ally' else p for p in root.roster.participants))
    return replace(root, roster=roster, champion_attack=replace(root.champion_attack, roster=roster),
                   minion_attack=replace(root.minion_attack, roster=roster))


def main():
    global_rng = getstate()
    source = authored_scenario()
    outside = authored_scenario()
    spatial = replace(outside.initial.spatial_state, placements=outside.scene_frames[1].key.placements)
    outside = replace(outside, initial=replace(outside.initial, spatial_state=spatial))
    cases = (
        ('WIND21', source, (9, 9, 9), (7, 7, 7), ('wizard', 'ally', 'enemy')),
        ('WIND22', source, (9, 9, 9), (7, 7, 8), ('wizard', 'ally', 'enemy')),
        ('OUTSIDE', outside, (9, 9, 9), (7, 7, 7), ('wizard', 'ally')),
        ('ARCHIVE', archived_scenario(), (1, 2, 3, 10, 10, 10, 9, 9, 9), (7, 7, 7), ('wizard', 'ally', 'enemy2')),
        ('AVAILABLE SPELL DECLINED', source, (1, 9, 9) + (10,) * 12 + (1, 1, 9), (7, 7, 7), ('wizard', 'ally', 'enemy')),
    )
    draws = 0
    for label, scenario, casting_values, table_values, expected in cases:
        root, count = fresh_pending(scenario, casting_values)
        before = deepcopy(root)
        final, result, preparation, table_count = complete_wind(scenario, root, table_values, 'example:' + label)
        assert tuple(t.target_id for t in result.wind.targets) == expected and root == before
        if label == 'OUTSIDE':
            assert final.roster.participant('enemy') == root.roster.participant('enemy')
        elif label == 'ARCHIVE':
            assert final.roster.participant('enemy').state.injury.defeated
            assert final.round_state.excluded_turn_entity_ids == ('enemy',)
            assert len(final.roster.participants) == len(final.spatial_state.placements) == 4
        elif label == 'AVAILABLE SPELL DECLINED':
            assert preparation.preparation.previous_casting_successes == 3
        draws += count + table_count
        print(f'{label}: {count} prior + {table_count} table d10; targets={expected}; pool3->0; unsupported_end_turn')

    root, count = fresh_pending(source, (9, 9, 9))
    bound = authored_bound_prone_ally(root)
    final, result, _, table_count = complete_wind(source, bound, (7, 7, 7), 'example:already-prone')
    ally = next(t for t in result.wind.targets if t.target_id == 'ally')
    assert ally.condition_application.was_already_present is True
    assert final.roster.participant('ally') == bound.roster.participant('ally')
    draws += count + table_count
    print('ALREADY PRONE: explicit bound input, not fresh runner reachability; actual application retains Staggered; pool3->0')

    root, count = fresh_pending(source, (9, 9, 9))
    _, other, rolled, table_count = prepare_and_roll(source, root, (10, 10, 10), 'example:other30')
    assert other.roll.total == 30 and rolled.wizard.magic_state.miscast_dice == 3
    try:
        NpcRosterUnnaturalWindRequest(other.effect_request.resolution_id + ':apply', rolled)
    except ValueError as error:
        assert 'canonical 21/22 entry' in str(error)
    else:
        raise AssertionError('another row cannot be redirected to Wind')
    assert rolled.pending_miscast_continuation is other
    draws += count + table_count
    print('OTHER ROW30: complete rolled pending/pool3 retained; Wind rejected before effect; no cleanup/reroll')
    assert draws == 63 and getstate() == global_rng
    print('63 scripted d10; standalone bound public APIs; owners/histories/global RNG preserved; no resumed battle or interruption claim')


if __name__ == '__main__':
    main()
