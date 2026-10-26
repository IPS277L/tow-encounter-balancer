"""Pure ADR-0037 admission: authored inputs, no runner or RNG."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from itertools import combinations
import random
import unittest
from unittest.mock import patch

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
from towr.domain.npc_magic_scene_models import (
    NpcMagicBrokenPlan, NpcMagicBrokenPlanKind as Broken, NpcMagicGiveGroundPlan,
    NpcMagicPairRange, NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey, NpcMagicZoneRange,
)
from towr.domain.npc_magic_scenario_models import NpcMagicActorPolicy, NpcMagicScenario, NpcMagicScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcCastingWizardState, NpcRosterCastingState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy as Injury
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


ZONES = ('arena', 'middle', 'shelter', 'far')
PLAYERS, OPPOSITION = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
ROUTE = NpcMagicRouteFacts((), False, False)


def owner(*, wizard_side=PLAYERS, enemy_zone='arena', short_optimum=False, blocker=False, fast_blocker=False):
    profile = NpcAttackProfile('shot', 'authored:shot', Skill.SHOOTING, InlineProfile(3, 3),
        DamageProfile(3), Range.SHORT, Range.SHORT if short_optimum else Range.LONG, Hands.TWO_HANDED)
    protection = (NpcProtectionProfile('authored:athletics', Skill.ATHLETICS, InlineProfile(3, 3)),)
    wizard = NpcDefinition('wizard', 'authored:wizard', Injury.CHAMPION, None, ResilienceProfile(4), (), protection)
    minion = NpcDefinition('archer', 'authored:archer', Injury.MINION, 1, ResilienceProfile(3), (profile,), protection)
    other = OPPOSITION if wizard_side is PLAYERS else PLAYERS
    rows = [('wizard', wizard, wizard_side, 'arena'), ('ally', minion, wizard_side, 'arena'),
            ('enemy', minion, other, enemy_zone)]
    if blocker:
        rows.append(('blocker', minion, other, 'middle'))
    if fast_blocker:
        rows.append(('far-blocker', minion, other, 'shelter'))
    roster = NpcRoster(tuple(NpcParticipantSnapshot(d, NpcParticipantState(
        i, d.id, s, CharacterInjuryState() if i == 'wizard' else ProfileInjuryState(0, 1),
        () if i == 'wizard' else ('shot',), d.resilience, i != 'wizard', False)) for i, d, s, _ in rows))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = SpatialBattleState(ZoneGraph(ZONES, tuple(ZoneConnection(a, b) for a, b in zip(ZONES, ZONES[1:]))),
        tuple(SpatialEntityPlacement(i, s.value, z) for i, _, s, z in rows))
    return NpcRosterCastingState(roster, NpcCastingWizardState('wizard', CastingCasterDefinition(
        'caster', 'authored:caster', 2, InlineProfile(3, 3)), WizardMagicState()), combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState('day:1', 'wizard')))


def frame(state, *, live=None, placements=None, approval=False):
    placements = state.spatial_state.placements if placements is None else placements
    ids = tuple(p.state.actor_id for p in state.roster.participants)
    live = ids if live is None else live
    locations = {p.entity_id: p.zone_id for p in placements}
    # Authored facts for this four-Zone straight layout, not a production mapper.
    ranges = (Range.SHORT, Range.MEDIUM, Range.LONG, Range.EXTREME)
    pairs = tuple(NpcMagicPairRange(a, b, ranges[abs(ZONES.index(locations[a])-ZONES.index(locations[b]))],
        approval and a != 'wizard', approval and b != 'wizard') for a, b in combinations(live, 2)
        if state.roster.participant(a).state.side is not state.roster.participant(b).state.side)
    ground = []
    if 'wizard' in live:
        for i in live:
            if state.roster.participant(i).state.side is not state.roster.participant('wizard').state.side:
                index = ZONES.index(locations[i])
                destination = ZONES[index+1] if index < 3 else None
                ground.append(NpcMagicGiveGroundPlan(i, True, destination, ROUTE if destination else None, destination is None))
    return NpcMagicSceneFrame(NpcMagicSceneKey(placements, live), pairs,
        tuple(NpcMagicZoneRange(z, ranges[abs(ZONES.index(z)-ZONES.index(locations['wizard']))]) for z in ZONES),
        tuple(ground), ())


def scenario(*, wizard_side=PLAYERS, perspective=PLAYERS, enemy_zone='arena', short_optimum=False,
             approval=False, blocker=False, fast_blocker=False):
    state = owner(wizard_side=wizard_side, enemy_zone=enemy_zone, short_optimum=short_optimum,
                  blocker=blocker, fast_blocker=fast_blocker)
    actors = []
    for p in state.roster.participants:
        i = p.state.actor_id
        targets = tuple(t.state.actor_id for t in state.roster.participants if t.state.side is not p.state.side)
        wizard = i == 'wizard'
        actors.append(NpcMagicActorPolicy(i, InlineProfile(3, 3), MovementSpeed.NORMAL,
            () if wizard else targets,
            () if wizard else tuple(MinionDefeatDecision(i, t, NpcDefeatDisposition.KNOCKED_OUT, True)
                                     for t in targets if t != 'wizard'),
            None if wizard else 'shot', CowardlyFlightCastingPolicy.CAST_WHEN_READY if wizard else None,
            ZONES if wizard else ()))
    facts = NpcMagicScenarioFacts(**{f.name: f.name != 'requires_reload_action' for f in fields(NpcMagicScenarioFacts)})
    return NpcMagicScenario('authored:scenario', state, facts,
        tuple(p.state.actor_id for p in state.roster.participants), tuple(actors), (frame(state, approval=approval),),
        perspective, NpcDefeatObjective(tuple(p.state.actor_id for p in state.roster.participants
                                              if p.state.side is not perspective)),
        3, StaggerChoice.SUFFER_WOUND, COWARDLY_FLIGHT_SPELL_DEFINITION)


def with_roster(state, roster):
    return replace(state, roster=roster, champion_attack=replace(state.champion_attack, roster=roster))


def transform_actor(state, actor, transform):
    return with_roster(state, NpcRoster(tuple(transform(p) if p.state.actor_id == actor else p
                                              for p in state.roster.participants)))


class MagicScenarioAdmissionTests(unittest.TestCase):
    def test_both_wizard_sides_and_perspectives_are_independent(self):
        for wizard_side in CombatSide:
            for perspective in CombatSide:
                source = scenario(wizard_side=wizard_side, perspective=perspective)
                self.assertEqual(source.initial.round_state.side_order, (PLAYERS, OPPOSITION))
                self.assertEqual(source.perspective_side, perspective)
                self.assertIs(source.policy_for('wizard').casting_policy, CowardlyFlightCastingPolicy.CAST_WHEN_READY)
                self.assertIs(source.initial_frame, source.frame_for(source.initial_frame.key))

    def test_orders_and_flags_are_preserved_not_sorted(self):
        source = scenario(blocker=True)
        actors = tuple(replace(p, target_actor_ids=tuple(reversed(p.target_actor_ids)),
            defeat_decisions=tuple(reversed(p.defeat_decisions))) if p.actor_id == 'enemy' else
            replace(p, zone_priorities=tuple(reversed(ZONES))) if p.actor_id == 'wizard' else p for p in source.actors)
        updated = replace(source, activation_order=tuple(reversed(source.activation_order)), actors=actors)
        self.assertEqual(updated.actors, actors)
        self.assertEqual(updated.activation_order, ('blocker', 'enemy', 'ally', 'wizard'))
        self.assertFalse(updated.facts.requires_reload_action)
        self.assertTrue(all(not pair.first_range_approved_by_gm for pair in updated.initial_frame.pair_ranges))
        reverse = replace(source.initial_frame, pair_ranges=tuple(replace(p, first_actor_id=p.second_actor_id,
            second_actor_id=p.first_actor_id) for p in reversed(source.initial_frame.pair_ranges)))
        self.assertEqual(replace(source, scene_frames=(reverse,)).initial_frame, reverse)

    def test_list_inputs_are_copied_and_models_frozen(self):
        source = scenario()
        orders, actors, frames = list(source.activation_order), list(source.actors), list(source.scene_frames)
        rebuilt = replace(source, activation_order=orders, actors=actors, scene_frames=frames)
        orders.clear(); actors.clear(); frames.clear()
        self.assertEqual(rebuilt, source)
        key = replace(source.initial_frame.key, placements=list(source.initial_frame.key.placements),
                      live_actor_ids=list(source.initial_frame.key.live_actor_ids))
        self.assertEqual(key, source.initial_frame.key)
        for value, attribute in ((source, 'max_rounds'), (source.facts, 'targets_aware'),
                                 (source.actors[0], 'speed'), (source.initial_frame, 'key'),
                                 (key, 'live_actor_ids'), (ROUTE, 'crosses_obstacle')):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, None)

    def test_all_scene_scope_assertions_are_explicit_and_typed(self):
        facts = scenario().facts
        for field in fields(facts):
            with self.subTest(field=field.name):
                with self.assertRaises(ValueError): replace(facts, **{field.name: not getattr(facts, field.name)})
                for value in (None, 1, 'yes'):
                    with self.assertRaises(TypeError): replace(facts, **{field.name: value})

    def test_types_ids_budget_and_canonical_spell_are_checked(self):
        source = scenario()
        for value in (True, 1.0, '3', None):
            with self.assertRaises(TypeError): replace(source, max_rounds=value)
        for value in (0, -1):
            with self.assertRaises(ValueError): replace(source, max_rounds=value)
        for changes in ({'id': ''}, {'spell': replace(source.spell, casting_value=4)},
                        {'spell': replace(source.spell, lore_id='other')},
                        {'repeated_stagger_choice': StaggerChoice.GIVE_GROUND}):
            with self.assertRaises(ValueError): replace(source, **changes)
        for changes in ({'initial': None}, {'facts': None}, {'perspective_side': PLAYERS.value},
                        {'objective': ()}, {'spell': None}, {'repeated_stagger_choice': 'suffer_wound'}):
            with self.assertRaises(TypeError): replace(source, **changes)

    def test_initial_owner_is_fresh_including_magic_daily_round_and_usage(self):
        source = scenario(); state = source.initial
        variants = [replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1))),
                    replace(state, consumed_execution_ids=('old',)),
                    replace(state, spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('enemy',))),
                    replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('ally',))),
                    replace(state, champion_attack=replace(state.champion_attack, consumed_wound_roll_ids=('old',))),
                    replace(state, champion_attack=replace(state.champion_attack, daily_wounds=replace(
                        state.champion_attack.daily_wounds, closed_by_infection_id='closed')))]
        combat = replace(state.round_state, side_order=(OPPOSITION, PLAYERS))
        variants.append(replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat)))
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'fresh'):
                replace(source, initial=variant)
        with self.assertRaisesRegex(ValueError, 'Champion attack/daily'):
            replace(source, initial=replace(state, champion_attack=None))

    def test_initial_health_and_equipment_not_hidden_by_scope_assertions(self):
        source = scenario()
        for actor in ('wizard', 'ally', 'enemy'):
            state = transform_actor(source.initial, actor, lambda p: replace(p, state=replace(p.state,
                injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(Condition.BROKEN)))))
            with self.assertRaisesRegex(ValueError, 'healthy'): replace(source, initial=state)
        for actor in ('wizard', 'ally'):
            state = transform_actor(source.initial, actor, lambda p: replace(p, state=replace(p.state, holds_shield=True)))
            with self.assertRaisesRegex(ValueError, 'shields'): replace(source, initial=state)
        state = transform_actor(source.initial, 'wizard', lambda p: replace(p, state=replace(p.state, wields_weapon=True)))
        with self.assertRaisesRegex(ValueError, 'authored Wizard'): replace(source, initial=state)

    def test_numeric_profile_and_current_availability_restrictions(self):
        source = scenario()
        for actor in ('ally', 'wizard'):
            state = transform_actor(source.initial, actor, lambda p: replace(p,
                state=replace(p.state, definition_id=p.definition.id + ':cap'),
                definition=replace(p.definition, id=p.definition.id + ':cap', protection=(
                    replace(p.definition.protection[0], test_profile=InlineProfile(3, 3, 9)),))))
            with self.assertRaisesRegex(ValueError, 'Athletics'): replace(source, initial=state)
        state = transform_actor(source.initial, 'ally', lambda p: replace(p, state=replace(p.state, available_attack_ids=())))
        with self.assertRaisesRegex(ValueError, 'numeric Shooting'): replace(source, initial=state)
        for changes in ({'test_profile': InlineProfile(3, 3, 9)}, {'ignores_armour': True},
                        {'range_min': Range.CLOSE}, {'damage': DamageProfile(3, success_multiplier=2)}):
            # Change both instances of the shared authored archer definition.
            roster = NpcRoster(tuple(replace(p, definition=replace(p.definition, attacks=(
                replace(p.definition.attacks[0], **changes),))) if p.definition.injury_policy is Injury.MINION else p
                for p in source.initial.roster.participants))
            with self.assertRaisesRegex(ValueError, 'numeric Shooting'):
                replace(source, initial=with_roster(source.initial, roster))

    def test_exact_actor_activation_target_zone_and_objective_partitions(self):
        source = scenario()
        for changes in ({'actors': source.actors[::-1]}, {'actors': source.actors[:-1]},
                        {'activation_order': ('wizard', 'ally')}, {'activation_order': ('wizard', 'ally', 'other')},
                        {'activation_order': ('wizard', 'ally', 'wizard')},
                        {'objective': NpcDefeatObjective(('ally',))}):
            with self.assertRaises(ValueError): replace(source, **changes)
        for actor in (replace(source.actors[0], zone_priorities=ZONES[:-1]),
                      replace(source.actors[0], willpower_profile=InlineProfile(4, 3)),
                      replace(source.actors[-1], target_actor_ids=('ally',))):
            policies = tuple(actor if p.actor_id == actor.actor_id else p for p in source.actors)
            with self.assertRaises(ValueError): replace(source, actors=policies)

    def test_minion_defeat_decisions_are_only_for_minion_targets(self):
        source = scenario(); enemy = source.actors[-1]
        self.assertEqual(enemy.target_actor_ids, ('wizard', 'ally'))
        self.assertEqual(tuple(d.target_id for d in enemy.defeat_decisions), ('ally',))
        for decisions in ((), (replace(enemy.defeat_decisions[0], gm_approved=False),),
                          (replace(enemy.defeat_decisions[0], attacker_id='wizard'),),
                          (MinionDefeatDecision('enemy', 'wizard', NpcDefeatDisposition.KILLED, True),)):
            with self.assertRaisesRegex(ValueError, 'defeat decisions'):
                replace(source, actors=(*source.actors[:-1], replace(enemy, defeat_decisions=decisions)))

    def test_future_frames_optional_and_missing_key_does_not_infer_facts(self):
        source = scenario()
        placements = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p
                           for p in source.initial.spatial_state.placements)
        future = frame(source.initial, placements=placements)
        self.assertIsNone(source.frame_for(future.key))
        extended = replace(source, scene_frames=(future, *source.scene_frames))
        self.assertIs(extended.frame_for(future.key), future)
        self.assertIs(extended.initial_frame, source.initial_frame)
        with self.assertRaisesRegex(ValueError, 'unique'): replace(source, scene_frames=source.scene_frames * 2)
        with self.assertRaisesRegex(ValueError, 'initial scene'): replace(source, scene_frames=(future,))

    def test_archived_entries_retained_but_not_counted_as_living_enemies(self):
        source = scenario()
        archived = frame(source.initial, live=('wizard', 'ally'))
        safe = NpcMagicBrokenPlan('wizard', Broken.SAFE_RECOVER, (), None, None, None, True)
        archived = replace(archived, broken_plans=(safe,))
        admitted = replace(source, scene_frames=(*source.scene_frames, archived))
        self.assertEqual(admitted.frame_for(archived.key).pair_ranges, ())
        self.assertEqual(len(archived.key.placements), 3)
        with self.assertRaisesRegex(ValueError, 'placements'):
            replace(source, scene_frames=(*source.scene_frames, replace(archived,
                key=replace(archived.key, placements=archived.key.placements[:-1]))))

    def test_frame_source_side_order_live_partition_and_unknown_zones(self):
        source = scenario(); original = source.initial_frame
        keys = [replace(original.key, placements=original.key.placements[::-1]),
                replace(original.key, live_actor_ids=original.key.live_actor_ids[::-1]),
                replace(original.key, placements=(replace(original.key.placements[0], side_id=OPPOSITION.value),
                                                *original.key.placements[1:])),
                replace(original.key, placements=(replace(original.key.placements[0], zone_id='missing'),
                                                *original.key.placements[1:]))]
        for key in keys:
            with self.assertRaises(ValueError):
                replace(source, scene_frames=(*source.scene_frames, replace(original, key=key)))

    def test_pair_completeness_hostility_reversal_and_range_geometry(self):
        source = scenario(); original = source.initial_frame
        variants = [original.pair_ranges[:-1], original.pair_ranges * 2,
            (*original.pair_ranges, NpcMagicPairRange('wizard', 'ally', Range.SHORT, False, False)),
            (replace(original.pair_ranges[0], first_actor_id='other'), *original.pair_ranges[1:]),
            (replace(original.pair_ranges[0], target_range=Range.LONG), *original.pair_ranges[1:]),
            (replace(original.pair_ranges[0], first_range_approved_by_gm=True), *original.pair_ranges[1:])]
        for pairs in variants:
            with self.assertRaises(ValueError): replace(source, scene_frames=(replace(original, pair_ranges=pairs),))

    def test_all_zone_facts_required_including_empty_zones(self):
        source = scenario(); original = source.initial_frame
        for zones in (original.zone_ranges[:-1], original.zone_ranges[::-1],
                      (replace(original.zone_ranges[0], target_range=Range.LONG), *original.zone_ranges[1:])):
            with self.assertRaises(ValueError): replace(source, scene_frames=(replace(original, zone_ranges=zones),))

    def test_any_close_enemy_blocks_initial_shooting_even_if_not_first_priority(self):
        source = scenario(); original = source.initial_frame
        pairs = tuple(replace(p, target_range=Range.CLOSE) if p.first_actor_id == 'wizard' else p
                      for p in original.pair_ranges)
        with self.assertRaisesRegex(ValueError, 'no hostile actor in Close'):
            replace(source, scene_frames=(replace(original, pair_ranges=pairs),))

    def test_true_and_false_directional_gm_approval_are_retained(self):
        source = scenario(enemy_zone='middle', short_optimum=True, approval=True)
        self.assertFalse(source.initial_frame.pair_ranges[0].first_range_approved_by_gm)
        self.assertTrue(source.initial_frame.pair_ranges[0].second_range_approved_by_gm)
        self.assertTrue(source.initial_frame.pair_ranges[1].first_range_approved_by_gm)
        reversed_pairs = tuple(replace(p, first_actor_id=p.second_actor_id, second_actor_id=p.first_actor_id,
            first_range_approved_by_gm=p.second_range_approved_by_gm,
            second_range_approved_by_gm=p.first_range_approved_by_gm) for p in source.initial_frame.pair_ranges)
        self.assertEqual(replace(source, scene_frames=(replace(source.initial_frame,
            pair_ranges=reversed_pairs),)).initial_frame.pair_ranges, reversed_pairs)
        with self.assertRaisesRegex(ValueError, 'available Shooting'):
            scenario(enemy_zone='middle', short_optimum=True, approval=False)
        with self.assertRaisesRegex(ValueError, 'not applicable'): scenario(approval=True)

    def test_out_of_range_initial_curse_is_rejected_but_future_extreme_frame_allowed(self):
        with self.assertRaisesRegex(ValueError, 'within Long'): scenario(enemy_zone='far')
        source = scenario()
        future = frame(source.initial, placements=tuple(replace(p, zone_id='far') if p.entity_id == 'enemy' else p
                                                        for p in source.initial.spatial_state.placements))
        self.assertIs(replace(source, scene_frames=(*source.scene_frames, future)).scene_frames[-1], future)

    def test_give_ground_requires_complete_route_or_explicit_impossibility(self):
        source = scenario(); original = source.initial_frame
        with self.assertRaises(ValueError): NpcMagicGiveGroundPlan('enemy', True, None, None, False)
        impossible = NpcMagicGiveGroundPlan('enemy', False, None, None, True)
        preserved = replace(source, scene_frames=(replace(original, give_ground_plans=(impossible,)),))
        self.assertFalse(preserved.initial_frame.give_ground_plans[0].can_leave_zone)
        for plans in ((), original.give_ground_plans*2, (replace(original.give_ground_plans[0], actor_id='ally'),)):
            with self.assertRaises(ValueError): replace(source, scene_frames=(replace(original, give_ground_plans=plans),))

    def test_give_ground_adjacency_away_and_route_facts_checked_without_execution(self):
        source = scenario(); original = source.initial_frame
        for plan in (replace(original.give_ground_plans[0], destination_zone_id='shelter'),
                     replace(original.give_ground_plans[0], route=replace(ROUTE, crosses_obstacle=True)),
                     replace(original.give_ground_plans[0], route=replace(ROUTE, path_entity_ids=('wizard',))),
                     replace(original.give_ground_plans[0], route=replace(ROUTE, path_entity_ids=('enemy',)))):
            with self.assertRaises(ValueError): replace(source, scene_frames=(replace(original, give_ground_plans=(plan,)),))
        source = scenario(enemy_zone='middle'); original = source.initial_frame
        with self.assertRaisesRegex(ValueError, 'away'):
            replace(source, scene_frames=(replace(original, give_ground_plans=(
                replace(original.give_ground_plans[0], destination_zone_id='arena'),)),))

    def test_broken_free_move_recover_and_slow_are_admitted(self):
        source = scenario(); original = source.initial_frame
        plan = NpcMagicBrokenPlan('wizard', Broken.FREE_MOVE_RECOVER, ('middle',), ROUTE, None, None, True)
        policies = (replace(source.actors[0], speed=MovementSpeed.SLOW), *source.actors[1:])
        admitted = replace(source, actors=policies, scene_frames=(replace(original, broken_plans=(plan,)),))
        self.assertEqual(admitted.initial_frame.broken_plans, (plan,))
        with self.assertRaisesRegex(ValueError, 'safe Recover'):
            replace(source, scene_frames=(replace(original, broken_plans=(NpcMagicBrokenPlan(
                'wizard', Broken.SAFE_RECOVER, (), None, None, None, True),)),))

    def test_broken_run_requires_unsafe_full_free_move_and_safe_run_zone(self):
        source = scenario(blocker=True); original = source.initial_frame
        plan = NpcMagicBrokenPlan('wizard', Broken.FREE_MOVE_RUN, ('middle',), ROUTE, 'shelter', ROUTE, True)
        self.assertEqual(replace(source, scene_frames=(replace(original, broken_plans=(plan,)),)).initial_frame.broken_plans, (plan,))
        with self.assertRaisesRegex(ValueError, 'Normal/Fast'):
            replace(source, actors=(replace(source.actors[0], speed=MovementSpeed.SLOW), *source.actors[1:]),
                    scene_frames=(replace(original, broken_plans=(plan,)),))
        with self.assertRaisesRegex(ValueError, 'Normal/Fast'):
            replace(source, actors=(replace(source.actors[0], speed=MovementSpeed.FAST), *source.actors[1:]),
                    scene_frames=(replace(original, broken_plans=(plan,)),))
        simple = scenario()
        with self.assertRaisesRegex(ValueError, 'unsafe free route'):
            replace(simple, scene_frames=(replace(simple.initial_frame, broken_plans=(plan,)),))

    def test_broken_route_geometry_speed_first_safe_and_path_guards(self):
        source = scenario(); original = source.initial_frame
        plan = NpcMagicBrokenPlan('wizard', Broken.FREE_MOVE_RECOVER, ('middle',), ROUTE, None, None, True)
        for other in (replace(plan, free_move_zone_ids=('shelter',)),
                      replace(plan, free_move_zone_ids=('middle', 'shelter')),
                      replace(plan, free_move_route=replace(ROUTE, crosses_difficult_terrain=True)),
                      replace(plan, free_move_route=replace(ROUTE, path_entity_ids=('enemy',))),
                      replace(plan, actor_id='missing')):
            with self.assertRaises(ValueError): replace(source, scene_frames=(replace(original, broken_plans=(other,)),))
        with self.assertRaisesRegex(ValueError, 'first safe'):
            replace(source, actors=(replace(source.actors[0], speed=MovementSpeed.FAST), *source.actors[1:]),
                    scene_frames=(replace(original, broken_plans=(replace(plan, free_move_zone_ids=('middle', 'shelter')),)),))
        with self.assertRaises(ValueError): replace(plan, fastest_route_confirmed=False)

    def test_fast_run_preserves_two_zone_free_route_and_one_run_zone(self):
        source = scenario(blocker=True, fast_blocker=True)
        plan = NpcMagicBrokenPlan('wizard', Broken.FREE_MOVE_RUN, ('middle', 'shelter'), ROUTE, 'far', ROUTE, True)
        policies = (replace(source.actors[0], speed=MovementSpeed.FAST), *source.actors[1:])
        admitted = replace(source, actors=policies,
                           scene_frames=(replace(source.initial_frame, broken_plans=(plan,)),))
        self.assertEqual(admitted.initial_frame.broken_plans[0].free_move_zone_ids, ('middle', 'shelter'))
        with self.assertRaisesRegex(ValueError, 'Speed'):
            replace(admitted, actors=source.actors)

    def test_archived_ally_cannot_be_used_as_a_live_route_fact(self):
        source = scenario(blocker=True)
        future = frame(source.initial, live=('wizard', 'ally', 'enemy'))
        plan = replace(future.give_ground_plans[0], route=replace(ROUTE, path_entity_ids=('blocker',)))
        with self.assertRaisesRegex(ValueError, 'archived'):
            replace(source, scene_frames=(*source.scene_frames, replace(future, give_ground_plans=(plan,))))

    def test_source_requires_allied_minion_and_retains_independent_placement_order(self):
        source = scenario(); state = source.initial
        roster = NpcRoster(tuple(p for p in state.roster.participants if p.state.actor_id != 'ally'))
        combat = CombatRoundState(1, roster.turn_participants)
        spatial = replace(state.spatial_state, placements=tuple(p for p in state.spatial_state.placements if p.entity_id != 'ally'))
        smaller = replace(state, roster=roster, round_state=combat, spatial_state=spatial,
                          champion_attack=replace(state.champion_attack, roster=roster, round_state=combat))
        with self.assertRaisesRegex(ValueError, 'allied and an opposing'):
            replace(source, initial=smaller)
        spatial = replace(state.spatial_state, placements=state.spatial_state.placements[::-1])
        reordered = replace(state, spatial_state=spatial)
        admitted = replace(source, initial=reordered, scene_frames=(frame(reordered),))
        self.assertEqual(admitted.initial_frame.key.placements, spatial.placements)
        self.assertEqual(admitted.initial_frame.key.live_actor_ids, source.activation_order)

    def test_lookup_and_collection_types_fail_without_rule_or_rng_calls(self):
        before = random.getstate()
        source = scenario(); saved = deepcopy(source)
        with (patch('towr.rules.turn_resolution.start_combat_turn', side_effect=AssertionError('no scheduler')),
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test'))):
            self.assertEqual(replace(source), source)
            for changes in ({'actors': set(source.actors)}, {'activation_order': 'wizard'}, {'scene_frames': None}):
                with self.assertRaises(TypeError): replace(source, **changes)
            with self.assertRaises(TypeError): source.frame_for(None)
            with self.assertRaises(ValueError): source.policy_for('other')
        self.assertEqual(source, saved)
        self.assertEqual(random.getstate(), before)


class MagicSceneValueTests(unittest.TestCase):
    def test_scene_key_validates_types_unique_ids_and_live_membership(self):
        key = scenario().initial_frame.key
        for changes in ({'placements': ()}, {'placements': key.placements*2},
                        {'live_actor_ids': ('missing',)}, {'live_actor_ids': ('wizard', 'wizard')}):
            with self.assertRaises(ValueError): replace(key, **changes)
        for changes in ({'placements': set(key.placements)}, {'placements': (None,)}, {'live_actor_ids': 'wizard'}):
            with self.assertRaises(TypeError): replace(key, **changes)

    def test_actor_role_types_and_profile_guards(self):
        policy = scenario().actors[0]
        for changes in ({'actor_id': ''}, {'willpower_profile': InlineProfile(3, 3, 9)},
                        {'attack_id': 'shot'}, {'zone_priorities': ()}, {'target_actor_ids': ('enemy',)}):
            with self.assertRaises(ValueError): replace(policy, **changes)
        for changes in ({'actor_id': 1}, {'speed': 'normal'}, {'willpower_profile': None},
                        {'casting_policy': 'cast_when_ready'}, {'defeat_decisions': (None,)},
                        {'zone_priorities': set(ZONES)}):
            with self.assertRaises(TypeError): replace(policy, **changes)

    def test_pair_zone_route_and_frame_primitive_validation(self):
        original = scenario().initial_frame
        for changes in ({'first_actor_id': ''}, {'second_actor_id': original.pair_ranges[0].first_actor_id}):
            with self.assertRaises(ValueError): replace(original.pair_ranges[0], **changes)
        for changes in ({'target_range': 'short'}, {'first_range_approved_by_gm': 1}):
            with self.assertRaises(TypeError): replace(original.pair_ranges[0], **changes)
        with self.assertRaises(ValueError): NpcMagicZoneRange('arena', Range.CLOSE)
        with self.assertRaises(TypeError): NpcMagicZoneRange('arena', 'short')
        for changes in ({'crosses_obstacle': 1}, {'path_entity_ids': 'ally'}):
            with self.assertRaises(TypeError): replace(ROUTE, **changes)
        for changes in ({'key': None}, {'pair_ranges': set(original.pair_ranges)}, {'broken_plans': (None,)}):
            with self.assertRaises(TypeError): replace(original, **changes)
        plans = list(original.give_ground_plans)
        rebuilt = replace(original, give_ground_plans=plans, zone_ranges=list(original.zone_ranges))
        plans.clear()
        self.assertEqual(rebuilt, original)

    def test_plan_shapes_and_departure_confirmation_are_explicit(self):
        ground = scenario().initial_frame.give_ground_plans[0]
        for changes in ({'can_leave_zone': False}, {'impossible_confirmed': True}):
            with self.assertRaises(ValueError): replace(ground, **changes)
        for changes in ({'route': None}, {'can_leave_zone': 1}, {'impossible_confirmed': 0}):
            with self.assertRaises(TypeError): replace(ground, **changes)
        plan = NpcMagicBrokenPlan('wizard', Broken.FREE_MOVE_RECOVER, ('middle',), ROUTE, None, None, True)
        for changes in ({'free_move_zone_ids': ()}, {'free_move_route': None},
                        {'run_destination_zone_id': 'shelter'}, {'fastest_route_confirmed': False},
                        {'kind': Broken.SAFE_RECOVER}):
            with self.assertRaises(ValueError): replace(plan, **changes)
        for changes in ({'kind': 'free_move_recover'}, {'fastest_route_confirmed': 1}):
            with self.assertRaises(TypeError): replace(plan, **changes)


if __name__ == '__main__':
    unittest.main()
