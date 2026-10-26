from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario
from tests.unit.test_m8_npc_roster_minion_attack import changed_roster
from towr.domain.npc_roster_turn_models import (
    NpcRosterTurnStartRequest, NpcRosterTurnStartResult, NpcRosterRoundAdvanceRequest, NpcRosterRoundAdvanceResult,
)
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, CombatSide, ImproviseKind, ManoeuvreKind
from towr.domain.magic_models import WizardMagicState
from towr.rules.npc_roster_turn_resolution import (
    start_npc_roster_turn as start, advance_npc_roster_round as advance,
    apply_npc_roster_turn_start_result as apply_start, apply_npc_roster_round_advance_result as apply_advance,
)


ATTACK = CombatActionDeclaration(CombatActionKind.ATTACK)
CAST = CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                               improvise_approach_id='lore:battle-magic')


def completed(state=None):
    state = scenario().initial_runtime_state if state is None else state
    combat = replace(state.round_state, active_turn=None,
                     completed_turn_entity_ids=tuple(p.entity_id for p in state.round_state.participants),
                     excluded_turn_entity_ids=())
    return replace(state, round_state=combat,
                   champion_attack=None if state.champion_attack is None else replace(state.champion_attack, round_state=combat))


class RosterTurnPhaseTests(unittest.TestCase):
    def test_start_and_slot_once_preserve_both_owners_and_no_execution(self):
        source = NpcRosterTurnStartRequest('phase', scenario().initial_runtime_state, 'ally', ATTACK)
        from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot
        with (patch('towr.rules.npc_roster_turn_resolution.start_combat_turn', wraps=start_combat_turn) as begin,
              patch('towr.rules.npc_roster_turn_resolution.reserve_combat_action_slot', wraps=reserve_combat_action_slot) as slot):
            result = start(source)
            begin.assert_called_once(); slot.assert_called_once()
        final = apply_start(source.state, result)
        turn = final.round_state.active_turn
        self.assertEqual(turn.actor_id, 'ally')
        self.assertEqual(len(turn.action_slots), 1)
        self.assertFalse(turn.action_slots[0].executed)
        self.assertIs(final.wizard, source.state.wizard)
        self.assertIs(final.roster, source.state.roster)
        self.assertIs(final.spatial_state, source.state.spatial_state)
        self.assertIs(final.minion_attack, source.state.minion_attack)
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertEqual(final.consumed_execution_ids, ())

    def test_four_declarations_are_only_reservations(self):
        declarations = (ATTACK, CAST, CombatActionDeclaration(CombatActionKind.RECOVER),
                        CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN))
        state = scenario().initial_runtime_state
        state = replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1, 1, 'lore:battle-magic', 1)))
        for declaration in declarations:
            final = start(NpcRosterTurnStartRequest('reserve', state, 'wizard', declaration)).state
            self.assertEqual(final.wizard.magic_state, state.wizard.magic_state)
            self.assertEqual(final.round_state.active_turn.action_slots[0].declaration, declaration)
            self.assertEqual(final.consumed_execution_ids, ())
        with self.assertRaisesRegex(ValueError, 'unsupported declaration'):
            NpcRosterTurnStartRequest('aim', state, 'wizard', CombatActionDeclaration(CombatActionKind.AIM))

    def test_advance_calls_each_reducer_once_and_resets_only_round_usage(self):
        old = completed()
        old = replace(old, spatial_state=replace(old.spatial_state, gave_ground_entity_ids=('enemy',),
            free_move_used_entity_ids=('wizard',), difficult_terrain_tested_entity_ids=('ally',)))
        source = NpcRosterRoundAdvanceRequest('advance', old)
        from towr.rules.turn_resolution import advance_combat_round
        from towr.rules.spatial_resolution import start_next_spatial_round
        with (patch('towr.rules.npc_roster_turn_resolution.advance_combat_round', wraps=advance_combat_round) as combat,
              patch('towr.rules.npc_roster_turn_resolution.start_next_spatial_round', wraps=start_next_spatial_round) as spatial):
            result = advance(source)
            combat.assert_called_once(); spatial.assert_called_once()
        with patch('towr.rules.npc_roster_turn_resolution.advance_combat_round', side_effect=AssertionError('no repeat')):
            final = apply_advance(old, result)
        self.assertEqual(final.round_state.round_number, 2)
        self.assertEqual(final.spatial_state.round_number, 2)
        self.assertEqual(final.round_state.completed_turn_entity_ids, ())
        self.assertIsNone(final.round_state.active_turn)
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ())
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, ())
        self.assertEqual(final.spatial_state.difficult_terrain_tested_entity_ids, ())
        self.assertIs(final.spatial_state.placements, old.spatial_state.placements)
        self.assertIs(final.spatial_state.graph, old.spatial_state.graph)
        self.assertIs(final.roster, old.roster)
        self.assertIs(final.minion_attack, old.minion_attack)
        self.assertIs(final.wizard, old.wizard)
        self.assertEqual(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)

    def test_archives_retained_and_dead_champion_defeated_minion_excluded(self):
        old = scenario().initial_runtime_state
        old = changed_roster(old, lambda p: replace(p, state=replace(p.state, injury=replace(p.state.injury, dead=True)))
            if p.state.actor_id == 'wizard' else replace(p, state=replace(p.state,
                injury=replace(p.state.injury, wounds=1, defeated=True))) if p.state.actor_id == 'enemy' else p)
        source = completed(old)
        final = advance(NpcRosterRoundAdvanceRequest('advance', source)).state
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ('wizard', 'enemy'))
        self.assertEqual(final.round_state.participants, source.round_state.participants)
        self.assertEqual(final.spatial_state.placements, source.spatial_state.placements)
        self.assertEqual(start(NpcRosterTurnStartRequest('ally', final, 'ally', ATTACK)).state.round_state.active_turn.actor_id, 'ally')
        for actor in ('wizard', 'enemy'):
            with self.assertRaisesRegex(ValueError, 'dead or defeated'):
                NpcRosterTurnStartRequest('dead', final, actor, ATTACK)

    def test_all_dead_is_a_technical_stop_without_infinite_empty_rounds(self):
        state = scenario().initial_runtime_state
        state = changed_roster(state, lambda p: replace(p, state=replace(p.state, injury=replace(p.state.injury,
            **({'dead': True} if p.state.actor_id == 'wizard' else {'wounds': 1, 'defeated': True})))))
        with self.assertRaisesRegex(ValueError, 'no living actor'):
            NpcRosterRoundAdvanceRequest('advance', completed(state))

    def test_start_actor_side_active_and_completed_guards(self):
        state = scenario().initial_runtime_state
        for actor in ('enemy', 'other'):
            with self.assertRaises(ValueError): NpcRosterTurnStartRequest('start', state, actor, ATTACK)
        active = start(NpcRosterTurnStartRequest('one', state, 'ally', ATTACK)).state
        with self.assertRaisesRegex(ValueError, 'idle incomplete'):
            NpcRosterTurnStartRequest('two', active, 'wizard', CAST)
        with self.assertRaisesRegex(ValueError, 'idle incomplete'):
            NpcRosterTurnStartRequest('end', completed(), 'wizard', CAST)
        combat = replace(state.round_state, completed_turn_entity_ids=('ally',))
        current = replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat))
        with self.assertRaisesRegex(ValueError, 'already completed'):
            NpcRosterTurnStartRequest('again', current, 'ally', ATTACK)
        with self.assertRaisesRegex(ValueError, 'completed round'):
            NpcRosterRoundAdvanceRequest('early', state)

    def test_live_exclusion_is_not_guessed_into_a_supported_policy(self):
        state = scenario().initial_runtime_state
        combat = replace(state.round_state, excluded_turn_entity_ids=('enemy',))
        source = replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat))
        with self.assertRaisesRegex(ValueError, 'live excluded'):
            NpcRosterTurnStartRequest('start', source, 'wizard', CAST)

    def test_stale_source_replay_and_new_advance_on_unplayed_round_rejected(self):
        source = NpcRosterTurnStartRequest('start', scenario().initial_runtime_state, 'wizard', CAST)
        result = start(source)
        for state in (result.state, replace(source.state, wizard=replace(source.state.wizard, magic_state=WizardMagicState(1)))):
            with self.assertRaisesRegex(ValueError, 'stale full source'): apply_start(state, result)
        advance_result = advance(NpcRosterRoundAdvanceRequest('advance', completed()))
        with self.assertRaisesRegex(ValueError, 'stale full source'): apply_advance(advance_result.state, advance_result)
        with self.assertRaisesRegex(ValueError, 'completed round'):
            NpcRosterRoundAdvanceRequest('repeat', advance_result.state)

    def test_start_result_checks_whole_start_slot_ids_round_history_and_rules(self):
        result = start(NpcRosterTurnStartRequest('start', scenario().initial_runtime_state, 'wizard', CAST))
        for changes in ({'request_id': 'wrong'}, {'applied_rule_ids': ()}, {'turn': None},
                        {'state': replace(result.start.state, completed_turn_entity_ids=('enemy',))}):
            with self.assertRaisesRegex(ValueError, 'complete bound transition'):
                replace(result, start=replace(result.start, **changes))
        for changes in ({'request_id': 'wrong'}, {'applied_rule_ids': ()}, {'slot': None},
                        {'state': replace(result.slot.state, completed_turn_entity_ids=('ally',))}):
            with self.assertRaisesRegex(ValueError, 'complete bound transition'):
                replace(result, slot=replace(result.slot, **changes))

    def test_advance_result_checks_both_transitions_and_archived_participants(self):
        result = advance(NpcRosterRoundAdvanceRequest('advance', completed()))
        for combat in (replace(result.combat, request_id='other'), replace(result.combat, applied_rule_ids=()),
                       replace(result.combat, state=replace(result.combat.state, completed_turn_entity_ids=('enemy',))),
                       replace(result.combat, state=replace(result.combat.state, side_order=tuple(s.value for s in CombatSide)))):
            with self.assertRaisesRegex(ValueError, 'complete bound advance'): replace(result, combat=combat)
        for spatial in (result.source.state.spatial_state,
                        replace(result.spatial, gave_ground_entity_ids=('enemy',)),
                        replace(result.spatial, placements=result.spatial.placements[::-1])):
            with self.assertRaisesRegex(ValueError, 'complete bound advance'): replace(result, spatial=spatial)

    def test_types_frozen_and_no_global_rng_or_partial_source_on_failure(self):
        state = scenario().initial_runtime_state; before = deepcopy(state); global_rng = random.getstate()
        source = NpcRosterTurnStartRequest('start', state, 'wizard', CAST)
        with self.assertRaises(FrozenInstanceError): source.id = 'changed'
        with patch('towr.rules.npc_roster_turn_resolution.reserve_combat_action_slot', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError): start(source)
        self.assertEqual(state, before); self.assertEqual(global_rng, random.getstate())
        with self.assertRaises(ValueError): replace(source, id='')
        for changes in ({'id': 1}, {'actor_id': False}, {'state': None}, {'declaration': 'Attack'}):
            with self.assertRaises(TypeError): replace(source, **changes)
        for call in (lambda: start(None), lambda: advance(None), lambda: apply_start(state, None),
                     lambda: apply_advance(None, None), lambda: NpcRosterTurnStartResult(source, None, None),
                     lambda: NpcRosterRoundAdvanceResult(NpcRosterRoundAdvanceRequest('advance', completed()), None, None)):
            with self.assertRaises(TypeError): call()

    def test_due_wound_cannot_be_skipped_by_raw_completed_turn_or_advance(self):
        from tests.unit.test_m8_npc_wound_turn_end import wounded
        state = completed(wounded())
        with self.assertRaisesRegex(ValueError, 'due Wound expiry'): NpcRosterRoundAdvanceRequest('skip', state)
        with self.assertRaisesRegex(ValueError, 'due Wound expiry'):
            NpcRosterTurnStartRequest('skip', state, state.wizard.actor_id, CAST)
        future = completed(wounded(completed=True))
        result = advance(NpcRosterRoundAdvanceRequest('future', future))
        self.assertEqual(result.state.wound_expiries, future.wound_expiries)
        self.assertEqual(result.state.wound_expiries[0].deadline_round_number, 2)

    def test_all_five_pending_families_block_start_and_advance_before_reducers(self):
        from tests.unit.test_m8_npc_roster_minion_defeat import defeated
        from tests.unit.test_m8_npc_roster_minion_attack import begin
        from tests.integration.test_m8_npc_roster_minion_attack import cast, wounded_owner
        from tests.unit.test_m8_npc_broken_run import request as run_request
        from towr.engine.npc_broken_run import execute_npc_broken_run
        caster = begin(scenario().initial_runtime_state, 'wizard', CombatActionKind.IMPROVISE)
        states = (defeated(), cast(caster, (9, 9, 9)), cast(caster, (1, 2, 3)),
                  wounded_owner(4), execute_npc_broken_run(run_request(pool=2)).state)
        with (patch('towr.rules.npc_roster_turn_resolution.start_combat_turn', side_effect=AssertionError('no start')),
              patch('towr.rules.npc_roster_turn_resolution.advance_combat_round', side_effect=AssertionError('no advance'))):
            for state in states:
                with self.assertRaisesRegex(ValueError, 'mandatory pending'):
                    start(NpcRosterTurnStartRequest('blocked', state, state.wizard.actor_id, CAST))
                with self.assertRaisesRegex(ValueError, 'mandatory pending'):
                    advance(NpcRosterRoundAdvanceRequest('blocked', state))

    def test_untracked_timers_and_advance_failure_preserve_source(self):
        from tests.unit.test_m8_npc_wound_turn_end import wounded
        state = completed(wounded())
        state = replace(state, wound_expiries=())
        with self.assertRaisesRegex(ValueError, 'untracked next-turn'):
            NpcRosterRoundAdvanceRequest('unknown', state)
        source = NpcRosterRoundAdvanceRequest('advance', completed()); before = deepcopy(source)
        with patch('towr.rules.npc_roster_turn_resolution.start_next_spatial_round', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError): advance(source)
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
