from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack, wizard_turn, prepare
from towr.domain.condition_models import Condition
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_turn_models import _validate_phase_source
from towr.domain.test_models import InlineProfile
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_battered_leg_resolution import (
    execute_npc_roster_battered_leg as execute, apply_npc_roster_battered_leg as apply,
)


def request(*, completed=False):
    source = incoming_attack()
    combat = source.state.round_state
    if completed:
        combat = replace(combat, completed_turn_entity_ids=(source.state.wizard.actor_id,))
    lower = replace(source.attack.state, round_state=combat)
    state = replace(source.state, round_state=combat, champion_attack=lower,
                    minion_attack=NpcRosterAttackState(source.state.roster))
    source = replace(source, state=state, attack=replace(source.attack, state=lower,
                     execution=replace(source.attack.execution, state=combat)))
    attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 5)))
    bound = NpcRosterChampionAttackResult(source, attack)
    return NpcRosterBatteredLegRequest('endurance:owner', bound.state, bound, InlineProfile(2, 5), True, True)


class BatteredLegOwnerTests(unittest.TestCase):
    def test_success_closes_only_pending_and_retains_both_children_and_histories(self):
        source = request()
        before = deepcopy(source)
        rng = Mock(wraps=SequenceRandom((1, 10, 7)))
        result = execute(source, rng)
        state = apply(source.state, result)
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)
        self.assertEqual(result.endurance.request.endurance_test.id,
                         source.attack.attack.pending_follow_ups[0].test_id)
        self.assertIsNone(state.champion_attack.pending)
        self.assertEqual(state.roster, source.state.roster)
        self.assertEqual(state.champion_attack.roster, state.roster)
        self.assertEqual(state.minion_attack.roster, state.roster)
        for name in ('round_state', 'spatial_state', 'wizard', 'consumed_execution_ids'):
            self.assertEqual(getattr(state, name), getattr(source.state, name))
        for name in ('daily_wounds', 'consumed_execution_ids', 'consumed_wound_roll_ids'):
            self.assertEqual(getattr(state.champion_attack, name), getattr(source.state.champion_attack, name))
        self.assertEqual(state.battered_leg_receipt.endurance, result.endurance)
        self.assertEqual(rng.randint(1, 10), 7)

    def test_failure_applies_sourced_prone_and_still_consumes_the_follow_up(self):
        source = request()
        result = execute(source, SequenceRandom((10, 10)))
        state = apply(source.state, result)
        injury = state.roster.participant(state.wizard.actor_id).state.injury
        self.assertTrue(injury.conditions.has(Condition.PRONE))
        self.assertEqual(len(injury.active_wound_effects), 1)
        self.assertIsNone(state.champion_attack.pending)
        self.assertIsNotNone(state.battered_leg_receipt)
        self.assertEqual(injury.wounds, source.k1_request.injury_state.wounds)

    def test_apply_and_execution_cannot_repeat_a_consumed_follow_up(self):
        source = request()
        result = execute(source, SequenceRandom((1, 10)))
        state = apply(source.state, result)
        with self.assertRaises(ValueError):
            apply(state, result)
        with self.assertRaises(ValueError):
            replace(source, state=state)

    def test_follow_up_does_not_require_an_awaiting_wizard_turn(self):
        source = request(completed=True)
        result = execute(source, SequenceRandom((1, 10)))
        self.assertTrue(result.endurance.test_result.succeeded)
        self.assertEqual(result.state.round_state.completed_turn_entity_ids,
                         source.state.round_state.completed_turn_entity_ids)

    def test_facts_and_profile_are_typed_before_rng(self):
        source = request()
        for changes in ({'unmounted': False}, {'unmounted': 1},
                        {'no_external_condition_sources': False}, {'endurance_profile': {'dice': 2}}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)

    def test_stale_magic_and_history_sources_reject_before_rng(self):
        source = request()
        state = replace(source.state, wizard=replace(source.state.wizard,
            magic_state=replace(source.state.wizard.magic_state, miscast_dice=0)))
        with self.assertRaises(ValueError):
            replace(source, state=state)
        with self.assertRaises(ValueError):
            replace(source.state, consumed_execution_ids=())

    def test_stripped_pending_does_not_authorize_casting_or_turn_end(self):
        source = request()
        stripped = replace(source.state, champion_attack=replace(source.state.champion_attack, pending=None))
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            _validate_phase_source(stripped)
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            NpcWoundTurnEndRequest('end', stripped, stripped.round_state.active_turn.actor_id)
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            prepare(wizard_turn(stripped))

    def test_stripped_completed_receipt_does_not_authorize_casting(self):
        result = execute(request(), SequenceRandom((1, 10)))
        stripped = replace(result.state, battered_leg_receipt=None)
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            prepare(wizard_turn(stripped))

    def test_result_cannot_rebind_another_authored_profile(self):
        source = request()
        result = execute(source, SequenceRandom((1, 10)))
        with self.assertRaises(ValueError):
            replace(result, source=replace(source, endurance_profile=InlineProfile(1, 10)))

    def test_corrupt_attack_trace_is_rejected_before_endurance_rng(self):
        source = deepcopy(request())
        trace = source.attack.attack.execution.resolution.attack.defender_test.trace
        object.__setattr__(trace, 'threshold', 10)
        rng = Mock()
        with self.assertRaises(ValueError):
            execute(source, rng)
        rng.randint.assert_not_called()

    def test_receipt_cannot_drop_the_minion_child_or_wound_history(self):
        state = execute(request(), SequenceRandom((1, 10))).state
        with self.assertRaisesRegex(ValueError, 'Minion child'):
            replace(state, minion_attack=None)
        with self.assertRaisesRegex(ValueError, 'histories'):
            replace(state, champion_attack=replace(state.champion_attack, consumed_wound_roll_ids=()))

    def test_apply_rejects_equal_but_untyped_current_equipment_flags(self):
        source = request()
        result = execute(source, SequenceRandom((1, 10)))
        current = deepcopy(source.state)
        object.__setattr__(current.roster.participants[0].state, 'wields_weapon', 1)
        with self.assertRaises(TypeError):
            apply(current, result)

    def test_stripped_pending_does_not_authorize_another_bound_attack(self):
        source = request()
        stripped = replace(source.state, champion_attack=replace(source.state.champion_attack, pending=None))
        from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            NpcRosterChampionAttackRequest(stripped, source.attack.source.attack)
