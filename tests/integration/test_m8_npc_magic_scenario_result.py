"""Journal source/owner/diagnostic validation over genuine multi-family chains."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario, frame, OPPOSITION, ROUTE
from tests.unit.test_m8_npc_magic_scenario_result import Journal, victory
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_magic_journal_policy import magic_scene_key
from towr.domain.npc_magic_scene_models import NpcMagicBrokenPlan, NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicUnsupported, NpcMagicPhase as Phase, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine.npc_broken_recover import execute_npc_broken_recover


class MagicJournalIntegrationTests(unittest.TestCase):
    def test_two_rounds_then_real_miscast_keep_distinct_counts_and_complete_owners(self):
        journal = Journal()
        for _ in range(2):
            journal.start('wizard'); journal.cast(); journal.end('wizard')
            journal.start('ally'); journal.shot('ally', 'enemy'); journal.end('ally')
            journal.start('enemy'); journal.shot('enemy', 'wizard'); journal.end('enemy')
            journal.advance()
        journal.start('wizard'); journal.cast((9, 9, 9))
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISCAST_PREPARATION, 'wizard', journal.steps[-1].id)
        result = journal.result(stop)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (3, 2, 7))
        self.assertEqual(len(result.current.minion_attack.consumed_execution_ids), 2)
        self.assertEqual(len(result.current.champion_attack.consumed_execution_ids), 2)
        self.assertEqual(len(result.current.wound_turn_end_receipts), 6)
        self.assertEqual(result.current.round_state.round_number, result.current.spatial_state.round_number)

    def test_pending_defeat_and_explicit_end_turn_precede_terminal_result(self):
        journal = victory(order=('ally', 'wizard', 'enemy'))
        result = journal.result()
        self.assertIs(result.outcome, Outcome.PERSPECTIVE_DEFEATED)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (1, 0, 1))
        self.assertEqual(result.current.round_state.completed_turn_entity_ids, ('ally',))
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ('enemy',))
        self.assertEqual(len(result.current.roster.participants), 3)
        for prefix in (result.steps[:-2], result.steps[:-1]):
            with self.assertRaises(ValueError): replace(result, steps=prefix)

    def test_real_wound_stop_preserves_pending_daily_roll_and_action_receipt(self):
        journal = Journal(scenario(wizard_side=OPPOSITION))
        journal.start('enemy'); attack = journal.shot('enemy', 'wizard', (1, 2, 3, 10, 10, 10, 4))
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.WOUND_EFFECT, 'enemy', journal.steps[-1].id,
            missing_actor_ids=('wizard',))
        result = journal.result(stop)
        self.assertEqual(result.current.champion_attack.pending, attack.attack)
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
        self.assertTrue(result.current.champion_attack.consumed_wound_roll_ids)
        self.assertTrue(result.current.round_state.active_turn.action_slots[0].executed)
        with self.assertRaises(ValueError): journal.result(replace(stop, reason=Reason.END_TURN))

    def test_drained_champion_remains_first_target_and_is_not_skipped_for_ally(self):
        journal = Journal(scenario(wizard_side=OPPOSITION, blocker=True))
        journal.start('enemy'); journal.shot('enemy', 'wizard', (1, 2, 3, 10, 10, 10, 6)); journal.end('enemy')
        journal.start('blocker')
        stop = NpcMagicUnsupported(Phase.ACTION, Reason.TARGET_INJURY, 'blocker', journal.steps[-1].id,
            missing_actor_ids=('wizard',))
        result = journal.result(stop)
        self.assertTrue(result.current.wound_expiries)
        self.assertEqual(result.executed_actions, 1)
        journal.shot('blocker', 'ally', distance=Range.MEDIUM)
        with self.assertRaisesRegex(ValueError, 'target priority'): journal.result(stop)

    def test_complete_curse_prefix_does_not_require_a_post_movement_frame(self):
        journal = Journal(scenario(blocker=True))
        journal.start('wizard'); journal.cast((1, 2, 3), targets=('enemy',))
        # This fixture only targets the arena enemy; one movement is complete,
        # so absence of the post-movement frame must not block Willpower.
        movement = journal.movement()
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISSING_SCENE, 'wizard', journal.steps[-1].id,
            required_scene_key=replace(journal.source.initial_frame.key, placements=movement.resolution.state.placements),
            staged_movements=(movement,))
        with self.assertRaises(ValueError): journal.result(stop)
        journal.complete((movement,)); journal.end('wizard'); journal.start('ally')
        key = magic_scene_key(journal.current)
        stop = NpcMagicUnsupported(Phase.ACTION, Reason.MISSING_SCENE, 'ally', journal.steps[-1].id, required_scene_key=key)
        result = journal.result(stop)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'middle')

    def test_missing_intermediate_frame_preserves_checked_prefix_and_full_pending(self):
        source = scenario(blocker=True)
        spatial = replace(source.initial.spatial_state, placements=tuple(replace(p, zone_id='arena')
            if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements))
        initial = replace(source.initial, spatial_state=spatial)
        source = replace(source, initial=initial, scene_frames=(frame(initial),))
        journal = Journal(source); journal.start('wizard'); journal.cast((1, 2, 3), targets=('enemy', 'blocker'))
        pending = journal.current
        movement = journal.movement()
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISSING_SCENE, 'wizard', journal.steps[-1].id,
            missing_actor_ids=('blocker',), required_scene_key=replace(source.initial_frame.key,
                placements=movement.resolution.state.placements), staged_movements=(movement,))
        result = journal.result(stop)
        self.assertEqual(result.current, pending)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'arena')
        self.assertEqual(result.unsupported.staged_movements[0].resolution.state.placement_for('enemy').zone_id, 'middle')
        self.assertEqual(len(result.current.pending_movement.zone.movement_follow_ups), 2)
        self.assertEqual(result.executed_actions, 1)
        for changes in ({'staged_movements': ()}, {'missing_actor_ids': ('enemy',)},
                        {'required_scene_key': source.initial_frame.key}):
            with self.assertRaises(ValueError): journal.result(replace(stop, **changes))
        changed_plan = replace(source.initial_frame.give_ground_plans[0], route=replace(ROUTE, path_entity_ids=('blocker',)))
        changed_frame = replace(source.initial_frame, give_ground_plans=(changed_plan, source.initial_frame.give_ground_plans[1]))
        with self.assertRaisesRegex(ValueError, 'scene route'):
            replace(result, source=replace(source, scene_frames=(changed_frame,)))
        forged = replace(movement, resolution=replace(movement.resolution,
            applied_rule_ids=(movement.resolution.source.rule_id,)))
        with self.assertRaisesRegex(ValueError, 'trace differs'):
            journal.result(replace(stop, staged_movements=(forged,)))

    def test_after_curse_out_of_range_target_is_a_real_no_legal_target_stop(self):
        source = scenario(enemy_zone='shelter')
        positions = tuple(replace(p, zone_id='far') if p.entity_id == 'enemy' else p for p in source.initial.spatial_state.placements)
        future = frame(source.initial, placements=positions)
        source = replace(source, scene_frames=(*source.scene_frames, future))
        journal = Journal(source); journal.start('wizard'); journal.cast((1, 2, 3), zone='shelter')
        journal.complete((journal.movement(destination='far'),), (1, 2, 3)); journal.end('wizard'); journal.start('ally')
        stop = NpcMagicUnsupported(Phase.ACTION, Reason.NO_LEGAL_TARGET, 'ally', journal.steps[-1].id)
        result = journal.result(stop)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertEqual(result.executed_actions, 1)
        self.assertFalse(result.current.round_state.active_turn.action_slots[0].executed)

    def test_broken_without_supplied_plan_stops_with_reserved_recover_slot(self):
        source = scenario()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p for p in source.initial.spatial_state.placements)
        source = replace(source, scene_frames=(*source.scene_frames, frame(source.initial, placements=positions)))
        journal = Journal(source); journal.start('wizard'); journal.cast((1, 2, 3))
        journal.complete((journal.movement(),)); journal.end('wizard')
        journal.start('ally'); journal.shot('ally', 'enemy', distance=Range.MEDIUM); journal.end('ally')
        journal.start('enemy', CombatActionDeclaration(CombatActionKind.RECOVER))
        stop = NpcMagicUnsupported(Phase.ACTION, Reason.BROKEN_ROUTE, 'enemy', journal.steps[-1].id,
            missing_actor_ids=('enemy',))
        self.assertIs(journal.result(stop).outcome, Outcome.UNSUPPORTED_PATH)

    def test_supported_broken_recover_keeps_receipt_and_requires_supplied_plan(self):
        source = scenario()
        placements = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p for p in source.initial.spatial_state.placements)
        future = frame(source.initial, placements=placements)
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER, (), None, None, None, True)
        source = replace(source, max_rounds=1, scene_frames=(*source.scene_frames, replace(future, broken_plans=(plan,))))
        journal = Journal(source)
        journal.start('wizard'); journal.cast((1, 2, 3)); journal.complete((journal.movement(),)); journal.end('wizard')
        journal.start('ally'); journal.shot('ally', 'enemy', distance=Range.MEDIUM); journal.end('ally')
        journal.start('enemy', CombatActionDeclaration(CombatActionKind.RECOVER))
        request = NpcBrokenRecoverRequest(journal.id('recover'), journal.current, 'enemy', source.policy_for('enemy').willpower_profile,
            None, True, True)
        journal.add(execute_npc_broken_recover(request, SequenceRandom((1, 2, 3)))); journal.end('enemy')
        result = journal.result()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertFalse(result.current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        with self.assertRaisesRegex(ValueError, 'supplied route policy'):
            replace(result, source=replace(source, scene_frames=(source.initial_frame, replace(future, broken_plans=()))))

    def test_wound_expiry_and_advance_cannot_invent_external_condition_source(self):
        journal = Journal()
        journal.start('wizard'); journal.cast(); journal.end('wizard')
        journal.start('ally'); journal.shot('ally', 'enemy'); journal.end('ally')
        journal.start('enemy'); journal.shot('enemy', 'wizard', (1, 2, 3, 10, 10, 10, 6)); journal.end('enemy')
        journal.advance(); journal.start('wizard'); journal.cast((9, 9, 9))
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISCAST_PREPARATION, 'wizard', journal.steps[-1].id)
        result = journal.result(stop)
        self.assertEqual(result.current.wound_expiries[0].deadline_round_number, 2)
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 1)
        # Rebuild the final activation with WAIT, then use the real bound expiry.
        journal.steps.pop(); journal.current = journal.steps[-1].after
        journal.cast()
        journal.end('wizard', (WoundConditionSourceSnapshot(Condition.DRAINED, True),))
        with self.assertRaisesRegex(ValueError, 'external Condition sources'): journal.result()

    def test_necessary_broken_run_uses_full_free_move_and_preserves_its_bound_result(self):
        from towr.domain.movement_models import FreeMovementRequest
        from towr.domain.npc_broken_run_models import NpcBrokenRunRequest
        from towr.domain.npc_magic_scene_models import NpcMagicPairRange, NpcMagicZoneRange
        from towr.domain.spatial_models import ZoneGraph, ZoneConnection
        from towr.domain.turn_models import ManoeuvreKind
        from towr.engine.npc_broken_run import execute_npc_broken_run
        source = scenario()
        graph = ZoneGraph(('arena', 'middle', 'shelter', 'far'),
            (ZoneConnection('arena', 'middle'), ZoneConnection('arena', 'shelter'), ZoneConnection('shelter', 'far')))
        placements = tuple(replace(p, zone_id='middle') if p.entity_id == 'ally' else p for p in source.initial.spatial_state.placements)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, graph=graph, placements=placements))
        zones = tuple(NpcMagicZoneRange(z, r) for z, r in zip(graph.zone_ids, (Range.SHORT, Range.MEDIUM, Range.MEDIUM, Range.LONG)))
        first = replace(source.initial_frame, key=replace(source.initial_frame.key, placements=placements), zone_ranges=zones,
            pair_ranges=(NpcMagicPairRange('wizard', 'enemy', Range.SHORT, False, False),
                         NpcMagicPairRange('ally', 'enemy', Range.MEDIUM, False, False)))
        plan = NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.FREE_MOVE_RUN, ('arena',), ROUTE, 'shelter', ROUTE, True)
        future = replace(first, key=replace(first.key, placements=tuple(replace(p, zone_id='middle')
            if p.entity_id == 'enemy' else p for p in placements)),
            pair_ranges=(NpcMagicPairRange('wizard', 'enemy', Range.MEDIUM, False, False),
                         NpcMagicPairRange('ally', 'enemy', Range.SHORT, False, False)), broken_plans=(plan,),
            give_ground_plans=(replace(first.give_ground_plans[0], destination_zone_id=None, route=None,
                can_leave_zone=False, impossible_confirmed=True),))
        source = replace(source, initial=initial, max_rounds=1, scene_frames=(first, future))
        journal = Journal(source); journal.start('wizard'); journal.cast((1, 2, 3)); journal.complete((journal.movement(),))
        journal.end('wizard'); journal.start('ally'); journal.shot('ally', 'enemy'); journal.end('ally')
        journal.start('enemy', CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN))
        identifier = journal.id('run')
        movement = FreeMovementRequest(identifier + ':free-move', journal.current.round_state, journal.current.spatial_state,
            'enemy', source.policy_for('enemy').speed, journal.current.roster.participant('enemy').state.injury.conditions, ('arena',))
        bound = journal.add(execute_npc_broken_run(NpcBrokenRunRequest(identifier, journal.current, 'enemy', movement,
            'shelter', (), False, False, True)))
        journal.end('enemy')
        result = journal.result()
        self.assertIs(result.steps[-2].result, bound)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'shelter')


if __name__ == '__main__':
    unittest.main()
