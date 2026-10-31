"""Actual bound results assembled explicitly, never an imitation runner."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario, frame, OPPOSITION
from tests.unit.test_m8_npc_roster_minion_attack import parts
from tests.unit.test_m8_npc_roster_turn import ATTACK, CAST
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_magic_step_models import (
    NpcMagicStep, NpcMagicUnsupported, NpcMagicUnsupportedReason as Reason, NpcMagicPhase as Phase,
    NpcMagicScenarioOutcome as Outcome,
)
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported
from towr.domain.npc_magic_scene_models import NpcMagicAttackDeparture
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_minion_defeat_resolution import acknowledge_npc_roster_minion_defeat
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn, advance_npc_roster_round
from towr.rules.npc_wound_turn_end import end_npc_wound_turn
from towr.rules.spatial_resolution import resolve_give_ground


class Journal:
    def __init__(self, source=None):
        self.source = scenario() if source is None else source
        # These hand-built attack fixtures use open arenas and can_leave=True.
        # Record that authored fact explicitly, just as the runner fixture does.
        self.source = replace(self.source, scene_frames=tuple(replace(f,
            attack_departures=f.attack_departures or tuple(
                NpcMagicAttackDeparture(i, True) for i in f.key.live_actor_ids))
            for f in self.source.scene_frames))
        self.current = self.source.initial_runtime_state
        self.steps = []

    def id(self, label):
        return f'{self.source.id}:{len(self.steps)}:{label}'

    def add(self, result):
        step = NpcMagicStep(result)
        self.steps.append(step)
        self.current = step.after
        return result

    def start(self, actor, declaration=None, identifier=None):
        declaration = (CAST if actor == 'wizard' else ATTACK) if declaration is None else declaration
        return self.add(start_npc_roster_turn(NpcRosterTurnStartRequest(
            identifier or self.id('start'), self.current, actor, declaration)))

    def cast(self, dice=(10, 10, 10), *, zone='arena', targets=('enemy',), can_move=True):
        request = prepare_npc_roster_casting(request_id=self.id('cast'), state=self.current,
            selected_zone_id=zone,
            targets=tuple(NpcRosterCastingTargetContext(i, self.source.policy_for(i).willpower_profile, can_move) for i in targets),
            facts=CowardlyFlightCastingFacts(*((True,) * 12)), policy=self.source.policy_for('wizard').casting_policy)
        return self.add(NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, SequenceRandom(dice))))

    def shot(self, actor, target, dice=(10,) * 6, distance=Range.SHORT):
        prepared, execution = parts(self.current, actor, target, self.id('shot'), target_range=distance)
        if target == 'wizard':
            request = NpcRosterChampionAttackRequest(self.current,
                NpcChampionAttackRequest(self.current.champion_attack, prepared, execution))
            result = NpcRosterChampionAttackResult(request, execute_npc_champion_attack(request.attack, SequenceRandom(dice)))
        else:
            request = NpcRosterMinionAttackRequest(self.current,
                NpcRosterAttackExecutionRequest(self.current.minion_attack, prepared, execution))
            result = execute_npc_roster_minion_attack(request, SequenceRandom(dice))
        return self.add(result)

    def ack(self, decision=None):
        attack = self.current.pending_minion_attack
        if decision is None:
            decision = next(d for d in self.source.policy_for(attack.execution.actor_id).defeat_decisions
                            if d.target_id == attack.execution.target_id)
        return self.add(acknowledge_npc_roster_minion_defeat(NpcRosterMinionDefeatRequest(self.id('ack'), self.current, decision)))

    def end(self, actor, sources=()):
        return self.add(end_npc_wound_turn(NpcWoundTurnEndRequest(self.id('end'), self.current, actor, sources)))

    def advance(self):
        return self.add(advance_npc_roster_round(NpcRosterRoundAdvanceRequest(self.id('advance'), self.current)))

    def movement(self, prefix=(), destination='middle'):
        pending = self.current.pending_movement
        follow = pending.zone.movement_follow_ups[len(prefix)]
        spatial = prefix[-1].resolution.state if prefix else pending.source.spatial_state
        moved = resolve_give_ground(GiveGroundResolutionRequest(follow.request, spatial, follow.target_id, destination,
            self.current.roster.participant(follow.target_id).state.injury.conditions, away_from_entity_id='wizard'))
        return complete_cowardly_flight_movement(follow, moved)

    def complete(self, moves, dice=(10, 10, 10)):
        request = NpcRosterCastingCompletionRequest(self.current, CowardlyFlightCastingCompletionRequest(
            self.current.pending_movement, moves, moves[-1].resolution.state))
        return self.add(NpcRosterCastingCompletionResult(request, complete_cowardly_flight_casting(request.completion, SequenceRandom(dice))))

    def result(self, unsupported=None):
        return NpcMagicScenarioResult(self.source, self.steps, unsupported)


def victory(*, perspective=OPPOSITION, order=('wizard', 'ally', 'enemy')):
    journal = Journal(replace(scenario(perspective=perspective), activation_order=order))
    if order[0] == 'wizard':
        journal.start('wizard'); journal.cast(); journal.end('wizard')
    journal.start('ally'); journal.shot('ally', 'enemy', (1, 2, 3, 10, 10, 10)); journal.ack(); journal.end('ally')
    return journal


def miscast():
    journal = Journal(); journal.start('wizard'); journal.cast((9, 9, 9))
    diagnostic = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISCAST_PREPARATION, 'wizard', journal.steps[-1].id)
    return journal, diagnostic


class MagicJournalTests(unittest.TestCase):
    def test_derived_current_and_counters_keep_full_results_and_source(self):
        journal = victory(); result = journal.result()
        self.assertEqual(result.current, journal.current)
        self.assertIs(result.source, journal.source)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (1, 1, 2))
        self.assertIs(result.steps[1].result, journal.steps[1].result)
        self.assertIs(result.outcome, Outcome.PERSPECTIVE_DEFEATED)

    def test_outcome_changes_with_perspective_without_changing_action_chain(self):
        journal = victory(perspective=scenario().perspective_side)
        self.assertIs(journal.result().outcome, Outcome.OBJECTIVE_ACHIEVED)

    def test_pending_miscast_cannot_be_reported_as_finished_or_lost_pool(self):
        journal, diagnostic = miscast()
        result = journal.result(diagnostic)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIsNotNone(result.current.pending_miscast)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(result.executed_actions, 1)
        self.assertEqual(diagnose_npc_magic_unsupported(journal.source, journal.current, journal.steps[-1].id), diagnostic)
        with self.assertRaisesRegex(ValueError, 'exact currently unsupported'): journal.result()

    def test_unsupported_rejects_wrong_phase_source_actor_reason_or_missing_ids(self):
        journal, diagnostic = miscast()
        for changes in ({'phase': Phase.ACTION}, {'actor_id': None}, {'actor_id': 'enemy'}, {'source_id': 'foreign'},
                        {'reason': Reason.WOUND_EFFECT}, {'missing_actor_ids': ('enemy',)}, {'missing_zone_ids': ('arena',)}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'exact currently unsupported'):
                journal.result(replace(diagnostic, **changes))

    def test_result_rejects_arbitrary_valid_prefix_even_with_plausible_diagnostic(self):
        journal = Journal()
        for actor in (None, 'wizard'):
            with self.assertRaises(ValueError):
                journal.result(NpcMagicUnsupported(Phase.SCHEDULING, Reason.NO_LEGAL_TARGET, actor, journal.source.id))
        journal.start('wizard')
        with self.assertRaises(ValueError): journal.result()
        with self.assertRaises(ValueError):
            journal.result(NpcMagicUnsupported(Phase.ACTION, Reason.NO_LEGAL_TARGET, 'wizard', journal.steps[-1].id))

    def test_discontinuous_missing_reordered_foreign_and_repeated_steps_rejected(self):
        result = victory().result(); steps = result.steps
        bad = (steps[1:], steps[:2] + steps[3:], steps[:1] + steps[2:3] + steps[1:2] + steps[3:], steps + steps[-1:],
               (*steps[:1], NpcMagicStep(replace(steps[1].result, source=replace(steps[1].result.source,
                    state=replace(steps[1].before, consumed_execution_ids=('foreign',))))), *steps[2:]))
        for chain in bad:
            with self.assertRaises(ValueError): replace(result, steps=chain)

    def test_full_source_checks_include_magic_spatial_ledgers_and_scenario_facts(self):
        result = victory().result()
        changed = replace(result.source, initial=replace(result.source.initial,
            champion_attack=replace(result.source.initial.champion_attack,
                daily_wounds=replace(result.source.initial.champion_attack.daily_wounds, day_id='another-day'))))
        with self.assertRaisesRegex(ValueError, 'continuous full-owner'): replace(result, source=changed)

    def test_intra_side_order_is_checked_even_if_scheduler_would_allow_actor(self):
        result = victory().result()
        with self.assertRaisesRegex(ValueError, 'activation differs'):
            replace(result, source=replace(result.source, activation_order=('ally', 'wizard', 'enemy')))

    def test_casting_zone_priority_target_willpower_and_departure_facts_are_bound(self):
        journal, stop = miscast()
        result = journal.result(stop)
        source = result.source
        enemy = replace(source.policy_for('enemy'), willpower_profile=replace(source.policy_for('enemy').willpower_profile, threshold=2))
        with self.assertRaisesRegex(ValueError, 'target facts'):
            replace(result, source=replace(source, actors=tuple(enemy if p.actor_id == 'enemy' else p for p in source.actors)))
        plan = replace(source.initial_frame.give_ground_plans[0], can_leave_zone=False,
            destination_zone_id=None, route=None, impossible_confirmed=True)
        with self.assertRaisesRegex(ValueError, 'target facts'):
            replace(result, source=replace(source, scene_frames=(replace(source.initial_frame, give_ground_plans=(plan,)),)))
        source = scenario(enemy_zone='middle', blocker=True)
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'blocker' else p for p in source.initial.spatial_state.placements)))
        source = replace(source, initial=initial, scene_frames=(frame(initial),))
        journal = Journal(source); journal.start('wizard'); journal.cast((9, 9, 9), zone='middle')
        stop = NpcMagicUnsupported(Phase.CONTINUATION, Reason.MISCAST_PREPARATION, 'wizard', journal.steps[-1].id)
        with self.assertRaisesRegex(ValueError, 'Zone/Casting policy'): journal.result(stop)

    def test_normal_role_declaration_cannot_be_changed_to_idle_recover(self):
        journal = Journal(); journal.start('wizard', CombatActionDeclaration(CombatActionKind.RECOVER))
        with self.assertRaisesRegex(ValueError, 'declaration differs'): journal.result()

    def test_protection_cannot_smuggle_an_unapproved_test_modifier(self):
        from towr.domain.test_models import DiceModifier
        from towr.rules.npc_attack_preparation import prepare_npc_attack_protection
        journal = Journal(); journal.start('wizard'); journal.cast(); journal.end('wizard'); journal.start('ally')
        protected, execution = parts(journal.current, 'ally', 'enemy', journal.id('shot'))
        protection = protected.protection.source_request
        option = protection.options[0]
        protection = replace(protection, options=(replace(option, test=replace(option.test,
            dice_modifiers=(DiceModifier('not-approved', 1),))),))
        protected = prepare_npc_attack_protection(protected.npc_attack, protection)
        execution = replace(execution, kernel_request=replace(execution.kernel_request, attack=protected.attack))
        request = NpcRosterMinionAttackRequest(journal.current,
            NpcRosterAttackExecutionRequest(journal.current.minion_attack, protected, execution))
        journal.add(execute_npc_roster_minion_attack(request, SequenceRandom((10,) * 7)))
        with self.assertRaisesRegex(ValueError, 'Attack facts'): journal.result()

    def test_live_archive_scene_key_is_not_replaced_by_initial_geometry(self):
        journal = Journal(); journal.start('wizard'); journal.cast((1, 2, 3)); move = journal.movement()
        journal.complete((move,)); journal.end('wizard'); journal.start('ally')
        from towr.domain.npc_magic_journal_policy import magic_scene_key
        diagnostic = NpcMagicUnsupported(Phase.ACTION, Reason.MISSING_SCENE, 'ally', journal.steps[-1].id,
            required_scene_key=magic_scene_key(journal.current))
        result = journal.result(diagnostic)
        self.assertEqual(result.current.spatial_state.placement_for('enemy').zone_id, 'middle')
        self.assertTrue(result.current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        with self.assertRaises(ValueError):
            journal.result(replace(diagnostic, required_scene_key=journal.source.initial_frame.key))

    def test_defeat_disposition_is_checked_against_scenario_gm_policy(self):
        result = victory().result()
        from towr.domain.minion_defeat_models import NpcDefeatDisposition
        source = result.source
        ally = source.policy_for('ally')
        ally = replace(ally, defeat_decisions=(replace(ally.defeat_decisions[0], disposition=NpcDefeatDisposition.KILLED),))
        source = replace(source, actors=tuple(ally if p.actor_id == 'ally' else p for p in source.actors))
        with self.assertRaisesRegex(ValueError, 'GM policy'): replace(result, source=source)

    def test_terminal_suffix_rejected_before_another_actual_start(self):
        journal = victory(order=('ally', 'wizard', 'enemy'))
        journal.start('wizard')  # legal raw phase, prohibited after scenario objective
        with self.assertRaisesRegex(ValueError, 'after a terminal'): journal.result()

    def test_terminal_result_cannot_claim_unsupported(self):
        result = victory().result()
        with self.assertRaisesRegex(ValueError, 'terminal journal'):
            replace(result, unsupported=NpcMagicUnsupported(Phase.SCHEDULING, Reason.CHRONOLOGY, None, result.steps[-1].id))

    def test_global_budget_rejects_real_advance_after_completed_limit(self):
        journal = Journal(replace(scenario(), max_rounds=1))
        journal.start('wizard'); journal.cast(); journal.end('wizard')
        journal.start('ally'); journal.shot('ally', 'enemy'); journal.end('ally')
        journal.start('enemy'); journal.shot('enemy', 'wizard'); journal.end('enemy')
        result = journal.result()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions), (1, 1, 3))
        journal.advance()
        with self.assertRaisesRegex(ValueError, 'after a terminal'): journal.result()

    def test_namespace_and_phase_action_id_collisions_across_complete_sources(self):
        journal, diagnostic = miscast()
        with self.assertRaisesRegex(ValueError, 'namespace'):
            NpcMagicScenarioResult(replace(journal.source, id='different'), journal.steps, diagnostic)
        journal = Journal(); start = journal.start('wizard'); journal.cast(); journal.end('wizard')
        journal.start('ally', identifier=start.source.id)  # lower API allows phase-ID reuse
        with self.assertRaisesRegex(ValueError, 'collide'): journal.result()

    def test_strict_types_frozen_and_owned_tuple_copies(self):
        journal, diagnostic = miscast(); result = journal.result(diagnostic)
        journal.steps.clear()
        self.assertEqual(len(result.steps), 2)
        with self.assertRaises(FrozenInstanceError): result.source = None
        with self.assertRaises(FrozenInstanceError): diagnostic.source_id = 'changed'
        for call in (lambda: NpcMagicStep(result), lambda: NpcMagicStep(result.current),
                     lambda: replace(result, source=None), lambda: replace(result, steps='steps'),
                     lambda: replace(result, unsupported='pending'), lambda: replace(diagnostic, phase='action'),
                     lambda: replace(diagnostic, reason='miscast_preparation'), lambda: replace(diagnostic, source_id=False),
                     lambda: replace(diagnostic, staged_movements=('not-movement',)),
                     lambda: diagnose_npc_magic_unsupported(None, result.current, 'source'),
                     lambda: replace(diagnostic, missing_actor_ids={'enemy'})):
            with self.assertRaises(TypeError): call()
        with self.assertRaises(ValueError): replace(diagnostic, source_id=' ')
        with self.assertRaises(ValueError): replace(diagnostic, missing_actor_ids=('enemy', 'enemy'))
        with self.assertRaises(ValueError): replace(diagnostic, required_scene_key=journal.source.initial_frame.key)

    def test_result_validation_does_not_call_rng_executor_or_scheduler(self):
        journal, diagnostic = miscast(); before = deepcopy(journal.current); global_rng = random.getstate()
        with (patch('towr.rules.npc_roster_turn_resolution.start_combat_turn', side_effect=AssertionError('no scheduler')),
              patch('towr.engine.cowardly_flight_casting.execute_cowardly_flight_casting', side_effect=AssertionError('no cast')),
              patch('towr.rules.npc_roster_attack_execution.execute_npc_roster_attack', side_effect=AssertionError('no attack')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            result = journal.result(diagnostic)
            self.assertEqual(result.current, before)
        self.assertEqual(random.getstate(), global_rng)


if __name__ == '__main__':
    unittest.main()
