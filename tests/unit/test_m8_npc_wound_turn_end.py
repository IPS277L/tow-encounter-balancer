from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from tests.integration.test_m8_npc_broken_run import from_owner
from tests.unit.test_m8_npc_roster_casting_completion import begin
from tests.unit.test_m8_npc_broken_recover import request as broken_recover_request
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundConditionSourceSnapshot, WoundEffectDuration, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry, NpcWoundTurnEndReceipt
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest, NpcWoundTurnEndResult
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
from towr.rules.turn_resolution import end_combat_turn


def wounded(*, completed=False, excluded=False):
    source = incoming_attack()
    target = source.state.wizard.actor_id
    combat = replace(source.state.round_state,
                     completed_turn_entity_ids=(target,) if completed else (),
                     excluded_turn_entity_ids=(target,) if excluded else ())
    champion = replace(source.attack.state, round_state=combat)
    source = replace(source, state=replace(source.state, round_state=combat, champion_attack=champion),
                     attack=replace(source.attack, state=champion, execution=replace(source.attack.execution, state=combat)))
    attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
    return NpcRosterChampionAttackResult(source, attack).state


def ready(pool=0):
    _, _, owner = wounded_broken_wizard(pool)
    return execute_npc_broken_run(from_owner(owner, owner.wizard.actor_id)).state


def request(state=None, other=False):
    state = ready() if state is None else state
    return NpcWoundTurnEndRequest('end:wizard', state, state.wizard.actor_id,
                                (WoundConditionSourceSnapshot(Condition.DRAINED, other),))


def change_injury(state, transform):
    actor = state.roster.participant(state.wizard.actor_id)
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=transform(p.state.injury)))
                            if p is actor else p for p in state.roster.participants))
    return replace(state, roster=roster, champion_attack=replace(state.champion_attack, roster=roster))


class NpcWoundTurnEndTests(unittest.TestCase):
    def test_real_attack_registers_source_and_next_target_turn(self):
        for completed, deadline in ((False, 1), (True, 2)):
            with self.subTest(completed=completed):
                state = wounded(completed=completed)
                expiry, = state.wound_expiries
                self.assertEqual(expiry.deadline_round_number, deadline)
                self.assertEqual(expiry.actor_id, state.wizard.actor_id)
                self.assertEqual(expiry.wound.entry_id, WoundEntryId.STOMACH_BLOW)
                self.assertEqual(expiry.attack_id, state.consumed_execution_ids[0])

    def test_end_is_atomic_preserves_wound_magic_and_all_histories(self):
        source = request()
        old = source.state
        with patch('towr.rules.npc_wound_turn_end.end_combat_turn', wraps=end_combat_turn) as scheduler:
            result = end_npc_wound_turn(source)
            scheduler.assert_called_once()
        with patch('towr.rules.npc_wound_turn_end.end_combat_turn', side_effect=AssertionError('no rerun')):
            final = apply_npc_wound_turn_end_result(old, result)
        before = old.roster.participant(source.actor_id).state.injury
        after = final.roster.participant(source.actor_id).state.injury
        self.assertTrue(before.conditions.has(Condition.DRAINED))
        self.assertFalse(after.conditions.has(Condition.DRAINED))
        self.assertTrue(after.conditions.has(Condition.BROKEN))
        self.assertEqual(after.wounds, before.wounds)
        self.assertFalse(after.wounds[0].treated)
        self.assertFalse(after.wounds[0].healed)
        self.assertEqual(after.active_wound_effects, ())
        self.assertEqual(final.wound_expiries, ())
        self.assertIsNone(final.round_state.active_turn)
        self.assertEqual(final.round_state.completed_turn_entity_ids[-1], source.actor_id)
        self.assertIs(final.wizard, old.wizard)
        self.assertIs(final.spatial_state, old.spatial_state)
        self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
        self.assertEqual(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, old.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.champion_attack.consumed_execution_ids, old.champion_attack.consumed_execution_ids)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertEqual(final.wound_turn_end_receipts, (NpcWoundTurnEndReceipt(
            source.id, source.actor_id, 1, (old.wound_expiries[0].attack_id,)),))

    def test_external_drained_source_is_retained(self):
        result = end_npc_wound_turn(request(other=True)).state
        injury = result.roster.participant(result.wizard.actor_id).state.injury
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(injury.active_wound_effects, ())

    def test_remaining_known_wound_source_cannot_be_denied(self):
        state = change_injury(ready(), lambda i: replace(i,
            wounds=(*i.wounds, replace(i.wounds[0], sequence=2, entry_id=WoundEntryId.INTERNAL_INJURY,
                                      table_total=14, roll_values=(4, 10))),
            active_wound_effects=(*i.active_wound_effects, WoundConditionEffect(
                2, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED))))
        with self.assertRaisesRegex(ValueError, 'cannot be denied'):
            request(state)
        final = end_npc_wound_turn(request(state, other=True)).state
        injury = final.roster.participant(final.wizard.actor_id).state.injury
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(injury.active_wound_effects, (WoundConditionEffect(
            2, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),))

    def test_other_actor_end_does_not_expire_wizard_effect(self):
        state = wounded()
        source = NpcWoundTurnEndRequest('end:attacker', state, 'brigand:0')
        final = end_npc_wound_turn(source).state
        self.assertEqual(final.roster, state.roster)
        self.assertEqual(final.wound_expiries, state.wound_expiries)
        self.assertEqual(final.wound_turn_end_receipts[0].expired_attack_ids, ())
        # A Minion's applied Broken Recover also ends without touching the
        # Wizard's active Casting or requiring any invented expiry source.
        state = execute_npc_broken_recover(broken_recover_request(actor='first'), SequenceRandom((10,) * 20)).state
        final = end_npc_wound_turn(NpcWoundTurnEndRequest('end:minion', state, 'first')).state
        self.assertIs(final.wizard, state.wizard)
        self.assertEqual(final.roster, state.roster)

    def test_sources_are_exact_and_ordered(self):
        source = request()
        self.assertEqual(replace(source, condition_sources=list(source.condition_sources)), source)
        for snapshots in ((), (*source.condition_sources, *source.condition_sources),
                          (WoundConditionSourceSnapshot(Condition.STAGGERED, False),)):
            with self.subTest(snapshots=snapshots), self.assertRaisesRegex(ValueError, 'match exactly'):
                replace(source, condition_sources=snapshots)
        for snapshots in (None, set(source.condition_sources), (False,)):
            with self.assertRaises(TypeError):
                replace(source, condition_sources=snapshots)

    def test_untracked_timed_effect_rejected(self):
        state = replace(ready(), wound_expiries=())
        with self.assertRaisesRegex(ValueError, 'chronology'):
            request(state)

    def test_early_overdue_and_excluded_source_are_not_guessed(self):
        state = ready()
        for other in (wounded(completed=True), wounded(excluded=True)):
            current = replace(state, wound_expiries=other.wound_expiries)
            with self.assertRaisesRegex(ValueError, 'another target turn|chronology'):
                request(current)
        turn = state.round_state.active_turn
        slot = turn.action_slots[0]
        combat = replace(state.round_state, round_number=2, active_turn=replace(turn,
            action_slots=(replace(slot, execution=replace(slot.execution, round_number=2)),)))
        current = replace(state, round_state=combat, spatial_state=replace(state.spatial_state, round_number=2),
                          champion_attack=replace(state.champion_attack, round_state=combat))
        with self.assertRaisesRegex(ValueError, 'another target turn'):
            request(current)
        # Same current turn with a source captured after the target's previous
        # turn is due now; deadline was not supplied by the caller.
        current = replace(current, wound_expiries=wounded(completed=True).wound_expiries)
        self.assertEqual(end_npc_wound_turn(request(current)).state.wound_expiries, ())

    def test_pending_interruption_and_attack_block_before_scheduler(self):
        state = ready(pool=2)
        self.assertIsNotNone(state.pending_interruption)
        with patch('towr.rules.npc_wound_turn_end.end_combat_turn', side_effect=AssertionError('no turn end')):
            with self.assertRaisesRegex(ValueError, 'mandatory pending'):
                request(state)
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        state = NpcRosterChampionAttackResult(source, attack).state
        with self.assertRaisesRegex(ValueError, 'mandatory pending'):
            NpcWoundTurnEndRequest('end', state, 'brigand:0')
        _, _, state, _ = begin()
        self.assertIsNotNone(state.pending_movement)
        with self.assertRaisesRegex(ValueError, 'mandatory pending'):
            NpcWoundTurnEndRequest('end', state, state.wizard.actor_id)

    def test_unsupported_conditions_and_restrictions_block_end(self):
        for condition in (Condition.ABLAZE, Condition.CRITICALLY_INJURED, Condition.BLINDED):
            state = change_injury(ready(), lambda i: replace(i, conditions=i.conditions.with_condition(condition)))
            with self.subTest(condition=condition), self.assertRaisesRegex(ValueError, 'unsupported end-turn Condition'):
                request(state)
        state = change_injury(ready(), lambda i: replace(i, active_wound_effects=(*i.active_wound_effects,
            WoundRestrictionEffect(1, WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST))))
        with self.assertRaisesRegex(ValueError, 'unsupported end-turn Wound'):
            request(state)

    def test_actor_unexecuted_action_and_unbound_wizard_action_rejected(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'active actor'):
            replace(source, actor_id='brigand:0')
        for slots in ((), (replace(source.state.round_state.active_turn.action_slots[0], execution=None),)):
            old = source.state
            combat = replace(old.round_state, active_turn=replace(old.round_state.active_turn, action_slots=slots))
            state = replace(old, round_state=combat, champion_attack=replace(old.champion_attack, round_state=combat))
            with self.assertRaisesRegex(ValueError, 'executed standard action'):
                request(state)
        state = replace(source.state, consumed_execution_ids=source.state.consumed_execution_ids[:1])
        with self.assertRaisesRegex(ValueError, 'bound consumer'):
            request(state)

    def test_stale_source_replay_and_requeue_expired_attack_rejected(self):
        source = request()
        result = end_npc_wound_turn(source)
        final = result.state
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply_npc_wound_turn_end_result(final, result)
        with self.assertRaisesRegex(ValueError, 'stale source'):
            apply_npc_wound_turn_end_result(replace(source.state, consumed_execution_ids=(
                *source.state.consumed_execution_ids, 'another')), result)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            replace(source, state=final)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            replace(final, wound_expiries=source.state.wound_expiries)

    def test_scheduler_result_cannot_substitute_actor_history_or_rules(self):
        result = end_npc_wound_turn(request())
        for changes in ({'request_id': 'other'}, {'completed_turn': None}, {'next_side': None},
                        {'round_complete': not result.turn_end.round_complete},
                        {'round_complete': int(result.turn_end.round_complete)},
                        {'next_side': result.turn_end.next_side.value}, {'applied_rule_ids': ()},
                        {'state': replace(result.turn_end.state, completed_turn_entity_ids=('brigand:2',))}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'complete bound turn'):
                replace(result, turn_end=replace(result.turn_end, **changes))

    def test_expiry_and_phase_history_are_bound_typed_immutable(self):
        state = wounded()
        expiry, = state.wound_expiries
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            expiry.source = None
        with self.assertRaises(TypeError):
            NpcStomachBlowExpiry(None)
        source = incoming_attack()
        miss = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        with self.assertRaisesRegex(ValueError, 'accepted resolved Stomach Blow'):
            NpcStomachBlowExpiry(miss)
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            replace(state, wound_expiries=(expiry, expiry))
        with self.assertRaisesRegex(ValueError, 'current Champion'):
            replace(state, champion_attack=None)
        receipt = NpcWoundTurnEndReceipt('end', 'brigand:0', 1, ())
        with self.assertRaisesRegex(ValueError, 'completed actor/round'):
            replace(state, wound_turn_end_receipts=(receipt,))
        for value in (None, set()):
            with self.assertRaises(TypeError):
                replace(state, wound_expiries=value)
        source = request()
        for changes in ({'id': ''}, {'actor_id': ''}):
            with self.assertRaises(ValueError):
                replace(source, **changes)
        for changes in ({'state': None}, {'id': 4}, {'actor_id': False}):
            with self.assertRaises(TypeError):
                replace(source, **changes)
        result = end_npc_wound_turn(source)
        with self.assertRaises(TypeError):
            NpcWoundTurnEndResult(source, None)
        with self.assertRaises(TypeError):
            end_npc_wound_turn(None)
        with self.assertRaises(TypeError):
            apply_npc_wound_turn_end_result(None, result)


if __name__ == '__main__':
    unittest.main()
