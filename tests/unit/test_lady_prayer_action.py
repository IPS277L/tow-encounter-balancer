"""C18 paid prayer uses the first own actual TurnStart, on either side."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import free_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.fate_models import FateSecondActionSpendRequest, FateSessionState
from towr.domain.lady_blessing_models import (
    LadyBlessingState, LadyOathDecision, OathDecisionKind, record_lady_oath_decision,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_lady_prayer_models import (
    LADY_PRAYER_RULE_ID, LadyPrayerActionRequest, execute_lady_prayer, lady_prayer_declaration,
)
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatRoundState, CombatSide, CombatTurnEndRequest,
    CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.rules.fate_resolution import spend_fate_for_second_action
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import (
    advance_combat_round, end_combat_turn, reserve_combat_action_slot, start_combat_turn,
)


PARTICIPANTS = (CombatTurnParticipant('pc', CombatSide.PLAYERS_AND_ALLIES),
    CombatTurnParticipant('npc', CombatSide.OPPOSITION))


def blessing(actor):
    return LadyBlessingState(actor, free_talent(TalentId.BLESSINGS_OF_THE_LADY), 'battle')


def started(clock, actor):
    return start_combat_turn(CombatTurnStartRequest(f'turn:{clock.round_number}:{actor}', clock, actor))


def prayer_slot(clock, actor):
    return reserve_combat_action_slot(CombatActionSlotRequest(
        f'slot:{clock.round_number}:{actor}:prayer', clock, actor,
        lady_prayer_declaration(), ActionSlotGrant.STANDARD))


def request_for(starts, *, source=None, conditions=None):
    current = starts[-1]
    actor = current.turn.actor_id
    reserved = prayer_slot(current.state, actor)
    return LadyPrayerActionRequest(f'prayer:{reserved.state.round_number}:{actor}',
        source if source is not None else blessing(actor), reserved.state, starts,
        conditions if conditions is not None else ConditionState(), 1)


def recover(clock, actor):
    reserved = reserve_combat_action_slot(CombatActionSlotRequest(
        f'slot:{clock.round_number}:{actor}:recover', clock, actor,
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD))
    return execute_recover_action(RecoverActionExecutionRequest(
        f'recover:{clock.round_number}:{actor}', reserved.state, actor,
        ConditionState(), True, 1, RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState())),
        SequenceRandom([]))


def finish_recover(start):
    result = recover(start.state, start.turn.actor_id)
    return end_combat_turn(CombatTurnEndRequest(f'end:{start.request_id}',
        result.round_state, start.turn.actor_id)).state


class LadyPrayerActionTests(unittest.TestCase):
    def test_each_side_can_pray_in_its_own_first_turn_after_opponent_has_acted(self):
        pc = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        pc_request = request_for((pc,))
        pc_result = execute_lady_prayer(pc_request)
        after_pc = end_combat_turn(CombatTurnEndRequest('end:pc', pc_result.round_state, 'pc')).state
        npc = started(after_pc, 'npc')
        npc_request = request_for((pc, npc))
        npc_result = execute_lady_prayer(npc_request)
        for actor, result in (('pc', pc_result), ('npc', npc_result)):
            with self.subTest(actor=actor):
                self.assertTrue(result.blessing.available)
                self.assertEqual(result.blessing.actor_id, actor)
                self.assertEqual(result.blessing.prayers, (f'prayer:1:{actor}',))
                self.assertTrue(result.slot.executed)
                self.assertEqual(result.slot.execution.executor_rule_id, LADY_PRAYER_RULE_ID)
        self.assertEqual(npc_result.round_state.completed_turn_entity_ids, ('pc',))

    def test_paid_prayer_executes_only_reserved_slot_and_cannot_execute_twice(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        request = request_for((start,))
        result = execute_lady_prayer(request)
        receipt = result.slot.execution
        self.assertEqual((receipt.actor_id, receipt.round_number, receipt.slot_index), ('pc', 1, 1))
        self.assertEqual((receipt.id, receipt.source_request_id, receipt.result_request_id),
            (request.id, request.id, request.id))
        self.assertEqual(result.applied_rule_ids, (LADY_PRAYER_RULE_ID,))
        self.assertFalse(request.round_state.active_turn.action_slots[0].executed)
        self.assertFalse(request.blessing.available)
        with self.assertRaises(ValueError):
            replace(request, round_state=result.round_state, blessing=result.blessing)
        with self.assertRaises(ValueError):
            replace(request, round_state=start.state)

    def test_second_own_turn_has_no_prayer_window_with_complete_prefix(self):
        pc = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        npc = started(finish_recover(pc), 'npc')
        round_two = advance_combat_round(CombatRoundAdvanceRequest('round:2',
            finish_recover(npc), PARTICIPANTS)).state
        pc_two = started(round_two, 'pc')
        with self.assertRaises(ValueError):
            request_for((pc, npc, pc_two))
        npc_two = started(finish_recover(pc_two), 'npc')
        with self.assertRaises(ValueError):
            request_for((pc, npc, pc_two, npc_two))

    def test_first_actual_turn_can_be_later_than_round_one(self):
        clock = CombatRoundState(1, PARTICIPANTS, excluded_turn_entity_ids=('npc',))
        pc = started(clock, 'pc')
        round_two = advance_combat_round(CombatRoundAdvanceRequest('round:2',
            finish_recover(pc), PARTICIPANTS)).state
        pc_two = started(round_two, 'pc')
        npc_first = started(finish_recover(pc_two), 'npc')
        result = execute_lady_prayer(request_for((pc, pc_two, npc_first)))
        self.assertEqual(result.slot.execution.round_number, 2)
        self.assertTrue(result.blessing.available)

    def test_real_fate_reserved_second_slot_is_a_legal_first_turn_prayer(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        recovered = recover(start.state, 'pc')
        source_fate = FateSessionState('session', 'pc', 1, 1)
        second_slot = CombatActionSlotRequest('slot:pc:fate', recovered.round_state, 'pc',
            lady_prayer_declaration(), ActionSlotGrant.FATE)
        spent = spend_fate_for_second_action(FateSecondActionSpendRequest('spend:prayer',
            source_fate, second_slot))
        request = LadyPrayerActionRequest('prayer:second', blessing('pc'),
            spent.slot_result.state, (start,), ConditionState(), 2)
        result = execute_lady_prayer(request)
        self.assertEqual(source_fate.remaining_spends, 1)
        self.assertEqual(spent.state.remaining_spends, 0)
        self.assertEqual(result.round_state.active_turn.action_slots[0], recovered.slot)
        self.assertTrue(result.slot.executed)
        self.assertIs(result.slot.grant, ActionSlotGrant.FATE)
        self.assertEqual(result.slot.execution.slot_index, 2)
        self.assertTrue(result.blessing.available)

    def test_second_slot_cannot_skip_unexecuted_first_action_or_use_an_ability_grant(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        first = reserve_combat_action_slot(CombatActionSlotRequest('first', start.state, 'pc',
            CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD))
        second = CombatActionSlotRequest('second', first.state, 'pc', lady_prayer_declaration(),
            ActionSlotGrant.FATE)
        reserved = spend_fate_for_second_action(FateSecondActionSpendRequest('fate',
            FateSessionState('session', 'pc', 1, 1), second))
        with self.assertRaises(ValueError):
            LadyPrayerActionRequest('prayer', blessing('pc'), reserved.slot_result.state,
                (start,), ConditionState(), 2)
        recovered = recover(start.state, 'pc')
        ability = reserve_combat_action_slot(CombatActionSlotRequest('ability', recovered.round_state,
            'pc', lady_prayer_declaration(), ActionSlotGrant.ABILITY, 'some:ability'))
        with self.assertRaises(ValueError):
            LadyPrayerActionRequest('prayer', blessing('pc'), ability.state,
                (start,), ConditionState(), 2)

    def test_defenceless_broken_or_oath_bar_prevent_prayer_without_paying(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        for condition in (Condition.DEFENCELESS, Condition.BROKEN):
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                request_for((start,), conditions=ConditionState(frozenset({condition})))
        barred = record_lady_oath_decision(blessing('pc'),
            LadyOathDecision('breach', 'pc', OathDecisionKind.BREACH))
        with self.assertRaises(ValueError):
            request_for((start,), source=barred)
        self.assertFalse(start.state.active_turn.action_slots)

    def test_foreign_actor_current_clock_and_repeated_turn_prefix_are_rejected(self):
        pc = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        npc = started(finish_recover(pc), 'npc')
        request = request_for((pc, npc))
        with self.assertRaises(ValueError):
            replace(request, blessing=blessing('pc'))
        with self.assertRaises(ValueError):
            replace(request, turn_starts=(pc,))
        with self.assertRaises(ValueError):
            replace(request, turn_starts=(pc, npc, npc))
        aliased = replace(npc, request_id='same-turn:alias')
        with self.assertRaises(ValueError):
            replace(request, turn_starts=(pc, npc, aliased))
        with self.assertRaises(ValueError):
            replace(request, round_state=replace(request.round_state,
                participants=(*PARTICIPANTS, CombatTurnParticipant('extra', CombatSide.OPPOSITION))))

    def test_prefix_clock_must_be_the_unmodified_actual_turn_start(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        request = request_for((start,))
        modified = replace(start, state=request.round_state,
            turn=request.round_state.active_turn)
        with self.assertRaises(ValueError):
            replace(request, turn_starts=(modified,))
        with self.assertRaises(TypeError):
            replace(request, turn_starts=[])
        with self.assertRaises(TypeError):
            replace(request, turn_starts=())
        with self.assertRaises(TypeError):
            replace(request, turn_starts=(True,))
        with self.assertRaises(TypeError):
            replace(request, slot_index=True)
        with self.assertRaises(ValueError):
            replace(request, slot_index=2)

    def test_backward_rounds_in_turn_start_prefix_are_rejected(self):
        pc = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        npc = started(finish_recover(pc), 'npc')
        second = advance_combat_round(CombatRoundAdvanceRequest('round:2',
            finish_recover(npc), PARTICIPANTS)).state
        pc_two = started(second, 'pc')
        request = request_for((pc,))
        with self.assertRaises(ValueError):
            replace(request, turn_starts=(pc_two, pc))

    def test_altered_results_and_cached_requests_cannot_replace_resource_or_paid_clock(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        request = request_for((start,))
        result = execute_lady_prayer(request)
        for changes in (
            {'blessing': request.blessing},
            {'round_state': request.round_state},
            {'slot': request.round_state.active_turn.action_slots[0]},
            {'applied_rule_ids': ()},
            {'applied_rule_ids': [LADY_PRAYER_RULE_ID]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        malformed = deepcopy(request)
        object.__setattr__(malformed, 'slot_index', True)
        with self.assertRaises(TypeError):
            execute_lady_prayer(malformed)

    def test_cached_string_enums_and_bool_execution_coordinates_are_not_authentic_clocks(self):
        start = started(CombatRoundState(1, PARTICIPANTS), 'pc')
        original = request_for((start,))
        malformed = deepcopy(original)
        object.__setattr__(malformed.round_state.active_turn.action_slots[0].declaration,
            'kind', 'improvise')
        with self.assertRaises(TypeError):
            execute_lady_prayer(malformed)
        result = execute_lady_prayer(original)
        object.__setattr__(result.slot.execution, 'slot_index', True)
        with self.assertRaises(TypeError):
            replace(result)


if __name__ == '__main__':
    unittest.main()
