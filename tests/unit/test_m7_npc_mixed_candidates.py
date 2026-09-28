from dataclasses import replace
import unittest

from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_mixed_scenario_result_models import mixed_scenario_candidates
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import ZoneConnection
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatTurnStartRequest,
)
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


def context_for(source, actor_id, *, injuries=None, completed=()):
    current = source.initial.current
    roster = current.state.roster
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injuries[p.state.actor_id]))
                            if injuries and p.state.actor_id in injuries else p for p in roster.participants))
    state = replace(current.state, roster=roster)
    combat = replace(current.round_state, completed_turn_entity_ids=completed)
    started = start_combat_turn(CombatTurnStartRequest('test:start', combat, actor_id))
    reserved = reserve_combat_action_slot(CombatActionSlotRequest(
        'test:reserve', started.state, actor_id, CombatActionDeclaration(CombatActionKind.ATTACK),
        ActionSlotGrant.STANDARD))
    return current.selection_context(state, reserved.state)


class M7NpcMixedCandidateTests(unittest.TestCase):
    def test_reachable_priority_and_actual_ranges_are_preserved(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        spatial = source.initial.spatial_state
        melee = mixed_scenario_candidates(source, context_for(source, '0:1'), spatial)
        # Full policy starts with the enemy bow at Medium; it is not a Melee target.
        self.assertEqual(source.policy_for('0:1').target_actor_ids, ('1:0', '1:1'))
        self.assertEqual(tuple(c.target_id for c in melee), ('1:1',))
        self.assertIs(melee[0].target_range, Range.CLOSE)
        self.assertTrue(melee[0].has_enemy_in_close_range)
        shooting = mixed_scenario_candidates(source, context_for(source, '0:0'), spatial)
        self.assertEqual(tuple(c.target_id for c in shooting), ('1:0', '1:1'))
        self.assertTrue(all(c.target_range is Range.MEDIUM and not c.has_enemy_in_close_range for c in shooting))

    def test_remote_allies_do_not_give_local_bonus_and_shooting_never_gets_it(self):
        source = scenario()  # Total 3:2; arena 2:2, bow elsewhere.
        for actor_id in ('0:0', '0:1'):
            candidates = mixed_scenario_candidates(source, context_for(source, actor_id), source.initial.spatial_state)
            self.assertTrue(all(c.dice_modifiers == () for c in candidates))
        source = scenario(sizes=(4, 2))
        candidates = mixed_scenario_candidates(source, context_for(source, '0:0'), source.initial.spatial_state)
        self.assertTrue(all(c.dice_modifiers == () for c in candidates))

    def test_current_defeats_on_either_side_and_defenceless_change_counts(self):
        source = scenario(sizes=(4, 2))  # Arena 3:2.
        defeated = ProfileInjuryState(1, 1, defeated=True)
        helpless = ProfileInjuryState(0, 1, ConditionState({Condition.DEFENCELESS}))
        bonus = (DiceModifier('RULE-COMBAT-009:outnumbering', 1),)
        for injuries, expected in (({}, bonus), ({'0:2': defeated}, ()),
                                   ({'0:2': helpless}, ()), ({'1:0': defeated}, bonus)):
            with self.subTest(injuries=injuries):
                candidates = mixed_scenario_candidates(source, context_for(source, '0:1', injuries=injuries),
                                                        source.initial.spatial_state)
                self.assertTrue(all(c.dice_modifiers == expected for c in candidates))
                if '1:0' in injuries:
                    self.assertEqual(tuple(c.target_id for c in candidates), ('1:1',))

    def test_completed_and_staggered_allies_still_count_but_gm_can_withhold(self):
        source = scenario(sizes=(4, 2))
        context = context_for(source, '0:1', completed=('0:2',),
                              injuries={'0:2': ProfileInjuryState(0, 1, ConditionState({Condition.STAGGERED}))})
        projected = mixed_scenario_candidates(source, context, source.initial.spatial_state)
        self.assertEqual(projected[0].dice_modifiers, (DiceModifier('RULE-COMBAT-009:outnumbering', 1),))
        withheld = replace(source, actor_policies=tuple(replace(p, outnumbering_bonus_approved=False)
                                                       if p.actor_id == '0:1' else p for p in source.actor_policies))
        projected = mixed_scenario_candidates(withheld, context, source.initial.spatial_state)
        self.assertTrue(all(c.dice_modifiers == () for c in projected))

    def test_escape_comes_from_target_policy_not_attacker_or_graph(self):
        source = scenario()
        source = replace(source, actor_policies=tuple(replace(p, can_leave_zone=True)
                                                     if p.actor_id == '1:0' else p for p in source.actor_policies))
        candidates = mixed_scenario_candidates(source, context_for(source, '0:0'), source.initial.spatial_state)
        self.assertEqual(tuple(c.can_target_leave_zone for c in candidates), (True, False))
        self.assertTrue(all(c.defender_is_aware and not c.target_has_given_ground_this_round for c in candidates))
        context = context_for(source, '0:0')
        for candidate in candidates:
            target = context.state.roster.participant(candidate.target_id)
            self.assertEqual(candidate.protection_options, target.protection_options(context.id))

    def test_exhausted_close_targets_return_empty_without_selecting_remote_enemy(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        context = context_for(source, '0:1', injuries={'1:1': ProfileInjuryState(1, 1, defeated=True)})
        self.assertEqual(mixed_scenario_candidates(source, context, source.initial.spatial_state), ())
        context = context_for(source, '0:0', injuries={'1:1': ProfileInjuryState(1, 1, defeated=True)})
        self.assertEqual(tuple(c.target_id for c in mixed_scenario_candidates(source, context,
                                                                            source.initial.spatial_state)), ('1:0',))

    def test_spatial_source_and_typed_inputs_are_required(self):
        source = scenario()
        context = context_for(source, '0:0')
        spatial = source.initial.spatial_state
        changed_graph = replace(spatial.graph, connections=(*spatial.graph.connections, ZoneConnection('arena', 'empty')))
        for changed in (replace(spatial, graph=changed_graph), replace(spatial, round_number=2),
                        replace(spatial, free_move_used_entity_ids=('0:0',))):
            with self.assertRaisesRegex(ValueError, 'stationary spatial'):
                mixed_scenario_candidates(source, context, changed)
        for values in ((None, context, spatial), (source, None, spatial), (source, context, None)):
            with self.assertRaises(TypeError):
                mixed_scenario_candidates(*values)

    def test_next_round_and_reversed_pair_records_keep_same_projection(self):
        source = scenario()
        context = context_for(source, '0:0')
        before = mixed_scenario_candidates(source, context, source.initial.spatial_state)
        context = replace(context, round_state=replace(context.round_state, round_number=2))
        changed = replace(source, pair_ranges=tuple(replace(p, first_actor_id=p.second_actor_id,
                                                           second_actor_id=p.first_actor_id)
                                                   for p in source.pair_ranges[::-1]))
        self.assertEqual(mixed_scenario_candidates(changed, context, replace(source.initial.spatial_state, round_number=2)), before)
