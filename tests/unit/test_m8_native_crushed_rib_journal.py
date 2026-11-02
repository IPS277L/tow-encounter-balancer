"""Native journal membership, source boundaries and mandatory tails (ADR-0057)."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.integration.test_m8_crushed_rib_protection_owner import public_fixture
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_magic_scenario_models import NpcMagicCrushedRibPolicy as Policy
from towr.domain.npc_magic_crushed_rib_policy import (
    initial_magic_crushed_rib_history, advance_magic_crushed_rib_history,
)
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


FIRST_TEN = (1, 2, 3, 10, 10, 10, 10)


def derived(source, steps):
    history = initial_magic_crushed_rib_history(source)
    for step in steps:
        validate_magic_step_policy(source, step, crushed_rib_history=history)
        history = advance_magic_crushed_rib_history(source, history, step)
    return history


class NativeCrushedRibJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = public_fixture()

    def setUp(self):
        self.rng = getstate()

    def tearDown(self):
        self.assertEqual(getstate(), self.rng)

    def pair(self):
        legacy = self.fixture.enemy_first()
        source = replace(legacy, crushed_rib_continuation=Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES)
        dice = Dice(FIRST_TEN)
        prefix = run_npc_magic_scenario(legacy, dice)
        dice.exhausted()
        return legacy, source, prefix

    def test_native_first_consumption_publishes_new_wound_pending_before_scope_stop(self):
        legacy, source, _ = self.pair()
        before = deepcopy(source)
        dice = Dice((*FIRST_TEN, 1, 2, 3, 10, 10, 10, 1, 3))
        result = run_npc_magic_scenario(source, dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertEqual(result.executed_actions, 2)
        self.assertIsNotNone(result.current.champion_attack.pending)
        self.assertEqual(tuple(w.table_total for w in result.current.roster.participant('wizard').state.injury.wounds), (10, 4))
        self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 2)
        history = derived(source, result.steps)
        self.assertIsNotNone(history.consumption)
        self.assertEqual(history.state, result.current)
        self.assertEqual(diagnose_npc_magic_unsupported(source, result.current,
            result.unsupported.source_id, crushed_rib_history=history), result.unsupported)
        self.assertEqual(NpcMagicScenarioResult(source, result.steps, result.unsupported), result)
        self.assertEqual(source, before)

    def test_unpermissioned_manual_result_no_longer_passes_complete_journal(self):
        legacy, source, prefix = self.pair()
        current = prefix.current
        first, after = self.fixture.attack(self.fixture.shooting(legacy, current,
            legacy.id + ':unpermissioned', Context(current, 'wizard', True)),
            (1, 2, 3, 10, 10, 10, 1, 3))
        step = NpcMagicStep(first)
        stop = diagnose_npc_magic_unsupported(legacy, after, step.id)
        self.assertIs(stop.reason, Reason.WOUND_EFFECT)
        with self.assertRaises(ValueError):
            validate_magic_step_policy(legacy, step)
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(legacy, (*prefix.steps, step), stop)

    def test_equal_owner_foreign_first_test_cannot_replace_recorded_membership(self):
        legacy, source, prefix = self.pair()
        current = prefix.current
        request = self.fixture.shooting(legacy, current, source.id + ':same-first', Context(current, 'wizard', True))
        first_a, after_a = self.fixture.attack(request, (10, 10, 10, 1, 6, 10, 9))
        first_b, after_b = self.fixture.attack(request, (10,) * 6)
        self.assertEqual(after_a, after_b)
        self.assertNotEqual(first_a, first_b)
        witness_a = Witness(first_a, first_a.attack.crushed_rib)
        witness_b = Witness(first_b, first_b.attack.crushed_rib)
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest(source.id + ':end-E2', after_a, 'E2'))
        started = start_npc_roster_turn(NpcRosterTurnStartRequest(source.id + ':start-E3', ended.state, 'E3',
            CombatActionDeclaration(CombatActionKind.ATTACK)))
        recorded = (*prefix.steps, NpcMagicStep(first_a), NpcMagicStep(ended), NpcMagicStep(started))
        history = derived(source, recorded)
        self.assertEqual(history.consumption, witness_a)
        # Both witnesses are valid standalone56 compatibility proofs.
        Context(started.state, 'wizard', True, witness_b)
        request_b = self.fixture.shooting(legacy, started.state, source.id + ':late',
            Context(started.state, 'wizard', True, witness_b))
        late_b, _ = self.fixture.attack(request_b, (10,) * 6)
        with self.assertRaises(ValueError):
            validate_magic_step_policy(source, NpcMagicStep(late_b), crushed_rib_history=history)
        # The rejection must occur in the journal loop, before EOF diagnosis.
        with patch('towr.domain.npc_magic_scenario_result_models.diagnose_npc_magic_unsupported',
                   side_effect=AssertionError('must reject foreign witness before EOF')):
            with self.assertRaises(ValueError):
                NpcMagicScenarioResult(source, (*recorded, NpcMagicStep(late_b)))

    def test_detached_result_cannot_hide_native_requirement_by_stripping_upper_context(self):
        legacy, source, prefix = self.pair()
        current = prefix.current
        result, _ = self.fixture.attack(self.fixture.shooting(legacy, current, source.id + ':stripped',
            Context(current, 'wizard', True)), (10,) * 6)
        history = derived(source, prefix.steps)
        bad = deepcopy(result)
        object.__setattr__(bad.source, 'crushed_rib_context', None)
        for value, cursor in ((legacy, None), (source, history)):
            with self.subTest(opted=value.crushed_rib_continuation is not None), self.assertRaises(ValueError):
                validate_magic_step_policy(value, NpcMagicStep(bad), crushed_rib_history=cursor)

    def test_extra_permission_preserves_existing_stationary_journal_and_rng(self):
        legacy = self.fixture.authored_input()
        source = replace(legacy, crushed_rib_continuation=Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES)
        hit = (1, 2, 3, 10, 10, 10)
        values = (*hit, 9, *((10,) * 9), *hit, 1, 5, *((10,) * 24))
        before_dice, opted_dice = Dice(values), Dice(values)
        before = run_npc_magic_scenario(legacy, before_dice)
        opted = run_npc_magic_scenario(source, opted_dice)
        before_dice.exhausted()
        opted_dice.exhausted()
        self.assertEqual(opted.steps, before.steps)
        self.assertEqual(opted.current, before.current)
        self.assertEqual(opted.outcome, before.outcome)
        self.assertEqual(opted.unsupported, before.unsupported)
        self.assertIs(opted.source, source)


if __name__ == '__main__':
    unittest.main()
