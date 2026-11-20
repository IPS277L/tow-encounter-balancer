"""Deterministic C17 action, audience, final-Test and incidental-signal receipts."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.support.talent_sources import free_talent, paid_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_battlefield_musician_models import (
    BATTLEFIELD_MUSICIAN_RULE_ID, BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID,
    BattlefieldMusicianActionRequest, BattlefieldMusicianListener,
    BattlefieldMusicianSignalKind, BattlefieldMusicianSignalRequest,
    BattlefieldMusicianSource,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentLoreFact
from towr.domain.test_models import (
    FATE_GLORIOUS_RULE_ID, QualityModifier, QualityModifierSource,
    RerollLock, TestProfile, TestQuality, TestRequest,
)
from towr.domain.tool_inventory_models import (
    ToolItemSource, ToolKind, build_tool_use, initial_tool_inventory,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt, ActionSlotGrant, CombatActionDeclaration,
    CombatActionKind, CombatActionSlot, CombatRoundState, CombatSide,
    CombatTurnParticipant, CombatTurnState, ImproviseKind,
)
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation
from towr.rules.battlefield_musician_resolution import (
    complete_battlefield_musician_action, execute_battlefield_musician_action,
    issue_battlefield_musician_signal,
)
from towr.rules.test_resolution import KeepAllFailures, RerollAllFailures, resolve_test


class CountingRandom(SequenceRandom):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def randint(self, start, end):
        self.calls.append((start, end))
        return super().randint(start, end)


def source(*, actor='musician', item_id='flute', hands=1, talent=None):
    item = ToolItemSource(item_id, ToolKind.MUSICIANS_GEAR, hands,
        WeaponItemLocation.HELD, WeaponGrip.LEFT if hands == 1 else WeaponGrip.BOTH)
    inventory = initial_tool_inventory(actor, (item,))
    return BattlefieldMusicianSource(actor,
        talent if talent is not None else paid_talent(TalentId.BATTLEFIELD_MUSICIAN),
        build_tool_use(actor, inventory, inventory.items[0].id),
        TalentLoreFact('music'), 2, 5)


def listener(actor='ally1', *, side=CombatSide.PLAYERS_AND_ALLIES,
        alive=True, distance=RangedWeaponRange.MEDIUM, hearing=True, conditions=None):
    return BattlefieldMusicianListener(actor, side, alive,
        conditions if conditions is not None else ConditionState(), distance, hearing)


def active_round(*, actor='musician', side=CombatSide.PLAYERS_AND_ALLIES,
        listeners=None, slots=None, round_number=1):
    listeners = listeners if listeners is not None else (listener(), listener('ally2'))
    other = next(value for value in CombatSide if value is not side)
    participants = {actor: CombatTurnParticipant(actor, side),
        'enemy': CombatTurnParticipant('enemy', other)}
    for value in listeners:
        participants.setdefault(value.actor_id, CombatTurnParticipant(value.actor_id, value.side))
    if slots is None:
        declaration = CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.ABILITY,
            improvise_approach_id=BATTLEFIELD_MUSICIAN_RULE_ID)
        slots = (CombatActionSlot(1, declaration, ActionSlotGrant.STANDARD),)
    return CombatRoundState(round_number, tuple(participants.values()),
        side_order=(side, other), active_turn=CombatTurnState(actor, side, slots))


def action_request(*, actor='musician', side=CombatSide.PLAYERS_AND_ALLIES,
        listeners=None, state=None, musician=None, test=None, conditions=None,
        slot_index=1, audience=()):
    listeners = listeners if listeners is not None else (listener(side=side), listener('ally2', side=side))
    musician = musician if musician is not None else source(actor=actor)
    state = state if state is not None else active_round(actor=actor, side=side, listeners=listeners)
    return BattlefieldMusicianActionRequest('musician:action', state, musician,
        conditions if conditions is not None else ConditionState(), slot_index,
        test if test is not None else TestRequest('musician:leadership', TestProfile(2, 5)),
        listeners, audience_participants=audience)


def signal_request(*, state=None, musician=None, listeners=None, prior=(),
        kind=BattlefieldMusicianSignalKind.PRESENCE, request_id='musician:signal', audience=()):
    listeners = listeners if listeners is not None else (listener(),)
    return BattlefieldMusicianSignalRequest(request_id,
        state if state is not None else active_round(listeners=listeners, slots=()),
        musician if musician is not None else source(), ConditionState(), kind,
        listeners, prior, audience_participants=audience)


class BattlefieldMusicianActionTests(unittest.TestCase):
    def test_pc_and_generated_npc_pay_the_actual_action_at_zero_or_multiple_successes(self):
        for actor, side in (('pc', CombatSide.PLAYERS_AND_ALLIES), ('npc', CombatSide.OPPOSITION)):
            for values, beneficiaries in (([10, 10], ()), ([1, 2], ('ally1', 'ally2'))):
                with self.subTest(actor=actor, values=values):
                    request = action_request(actor=actor, side=side)
                    rng = CountingRandom(values)
                    result = execute_battlefield_musician_action(request, rng)
                    self.assertEqual(result.beneficiary_ids, beneficiaries)
                    self.assertIs(result.source_request, request)
                    self.assertEqual(result.previous_round_state, request.round_state)
                    self.assertTrue(result.slot.executed)
                    receipt = result.slot.execution
                    self.assertEqual((receipt.actor_id, receipt.round_number, receipt.slot_index,
                        receipt.source_request_id, receipt.result_request_id),
                        (actor, 1, 1, request.id, request.leadership_test.id))
                    self.assertEqual(result.round_state, replace(request.round_state,
                        active_turn=replace(request.round_state.active_turn, action_slots=(result.slot,))))
                    self.assertEqual(result.applied_rule_ids, (BATTLEFIELD_MUSICIAN_RULE_ID,))
                    self.assertEqual(rng.calls, [(1, 10)] * 2)

    def test_final_successes_select_distinct_eligible_allies_in_owner_priority(self):
        audience = (
            listener('silent', hearing=False), listener('musician'),
            listener('enemy', side=CombatSide.OPPOSITION), listener('dead', alive=False),
            listener('far', distance=RangedWeaponRange.LONG),
            listener('deaf', conditions=ConditionState(frozenset((Condition.DEAFENED,)))),
            listener('ally2', distance=RangedWeaponRange.CLOSE),
            listener('ally1', distance=RangedWeaponRange.SHORT), listener('extra'),
        )
        result = execute_battlefield_musician_action(action_request(listeners=audience),
            SequenceRandom([1, 2]))
        self.assertEqual(result.beneficiary_ids, ('ally2', 'ally1'))
        self.assertEqual(result.selected_listeners, (audience[6], audience[7]))

    def test_no_eligible_audience_still_spends_the_successful_action(self):
        request = action_request(listeners=(listener(hearing=False),))
        result = execute_battlefield_musician_action(request, SequenceRandom([1, 2]))
        self.assertEqual(result.test_result.successes, 2)
        self.assertEqual(result.beneficiary_ids, ())
        self.assertTrue(result.slot.executed)

    def test_retained_companion_is_a_listener_without_granting_a_clock_participant(self):
        state = active_round()
        companion = listener('retained-horse')
        roster = (CombatTurnParticipant(companion.actor_id, companion.side),)
        request = action_request(state=state, listeners=(companion,), audience=roster)
        result = execute_battlefield_musician_action(request, SequenceRandom([1, 10]))
        self.assertEqual(result.beneficiary_ids, ('retained-horse',))
        self.assertEqual(result.round_state.participants, state.participants)
        self.assertNotIn('retained-horse', tuple(p.entity_id for p in state.participants))
        with self.assertRaises(ValueError):
            replace(request, audience_participants=())

    def test_completion_keeps_final_external_fate_test_without_any_new_rng(self):
        request = action_request()
        fate_test = replace(request.leadership_test, quality_modifiers=(QualityModifier(
            FATE_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
            QualityModifierSource.FATE, 'actual:fate-spend'),))
        request = replace(request, leadership_test=fate_test)
        final = resolve_test(fate_test, SequenceRandom([1, 10, 2]), decisions=RerollAllFailures())
        with patch('towr.rules.battlefield_musician_resolution.resolve_test',
                side_effect=AssertionError('completed Leadership rerolled')):
            result = complete_battlefield_musician_action(request, final)
        self.assertIs(result.test_result, final)
        self.assertEqual(final.trace.initial_values, (1, 10))
        self.assertEqual(final.trace.final_values, (1, 2))
        self.assertEqual(result.beneficiary_ids, ('ally1', 'ally2'))
        self.assertEqual(result.applied_rule_ids, (BATTLEFIELD_MUSICIAN_RULE_ID, FATE_GLORIOUS_RULE_ID))

    def test_grim_final_dice_and_locks_determine_actual_recipient_count(self):
        test = TestRequest('musician:leadership', TestProfile(2, 5),
            quality_modifiers=(QualityModifier('source:grim', TestQuality.GRIM),),
            reroll_locks=(RerollLock('source:lock', 1),))
        rng = CountingRandom([1, 2, 10])
        result = execute_battlefield_musician_action(action_request(test=test), rng)
        self.assertEqual(result.test_result.trace.final_values, (1, 10))
        self.assertEqual(result.beneficiary_ids, ('ally1',))
        self.assertEqual(rng.calls, [(1, 10)] * 3)

    def test_completion_preserves_actual_choice_to_keep_a_glorious_failure(self):
        test = TestRequest('musician:leadership', TestProfile(2, 5),
            quality_modifiers=(QualityModifier('source:glorious', TestQuality.GLORIOUS),))
        request = action_request(test=test)
        final = resolve_test(test, SequenceRandom([1, 10]), decisions=KeepAllFailures())
        result = complete_battlefield_musician_action(request, final)
        self.assertIs(result.test_result, final)
        self.assertEqual(result.test_result.trace.rerolls, ())
        self.assertEqual(result.beneficiary_ids, ('ally1',))

    def test_paid_fate_second_slot_is_consumed_after_executed_first_action(self):
        first_declaration = CombatActionDeclaration(CombatActionKind.RECOVER)
        receipt = ActionExecutionReceipt('recover', 'rule:recover', 'recover', 'recover',
            'musician', 1, 1, first_declaration)
        first = CombatActionSlot(1, first_declaration, ActionSlotGrant.STANDARD, execution=receipt)
        ability = active_round().active_turn.action_slots[0].declaration
        second = CombatActionSlot(2, ability, ActionSlotGrant.FATE)
        state = active_round(slots=(first, second))
        result = execute_battlefield_musician_action(action_request(state=state, slot_index=2),
            SequenceRandom([10, 10]))
        self.assertEqual(result.round_state.active_turn.action_slots[0], first)
        self.assertTrue(result.round_state.active_turn.action_slots[1].executed)
        self.assertEqual(result.slot.execution.slot_index, 2)

    def test_executed_slot_cannot_be_used_again(self):
        request = action_request()
        result = execute_battlefield_musician_action(request, SequenceRandom([10, 10]))
        with self.assertRaises(ValueError):
            replace(request, round_state=result.round_state)


class BattlefieldMusicianSignalTests(unittest.TestCase):
    def test_presence_and_retreat_are_free_receipts_with_no_test_or_action_change(self):
        audience = (listener('far', distance=RangedWeaponRange.EXTREME),
            listener('silent', hearing=False),
            listener('deaf', conditions=ConditionState(frozenset((Condition.DEAFENED,)))))
        for kind in BattlefieldMusicianSignalKind:
            with self.subTest(kind=kind):
                request = signal_request(kind=kind, listeners=audience)
                with patch('towr.rules.battlefield_musician_resolution.resolve_test',
                        side_effect=AssertionError('free signal rolled a Test')):
                    result = issue_battlefield_musician_signal(request)
                self.assertEqual(result.receipt.heard_actor_ids, ('far',))
                self.assertEqual(result.receipt.kind, kind)
                self.assertEqual(result.receipt.round_state, request.round_state)
                self.assertEqual(result.receipt.round_state.active_turn.action_slots, ())
                self.assertEqual(result.receipts, (result.receipt,))
                self.assertEqual(result.receipt.applied_rule_ids, (BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID,))
                self.assertEqual(result.receipt.listeners, audience)

    def test_one_selected_signal_per_musician_turn_survives_item_change(self):
        result = issue_battlefield_musician_signal(signal_request())
        with self.assertRaises(ValueError):
            signal_request(kind=BattlefieldMusicianSignalKind.RETREAT,
                musician=source(item_id='drum'), prior=result.receipts, request_id='another-signal')
        next_round = replace(result.receipt.round_state, round_number=2)
        later = issue_battlefield_musician_signal(signal_request(state=next_round,
            kind=BattlefieldMusicianSignalKind.RETREAT, prior=result.receipts,
            request_id='later-signal'))
        self.assertEqual(len(later.receipts), 2)

    def test_signal_and_paid_action_are_separate_receipts_on_the_same_turn(self):
        action = action_request()
        signal = issue_battlefield_musician_signal(signal_request(state=action.round_state))
        result = execute_battlefield_musician_action(action, SequenceRandom([1, 10]))
        self.assertEqual(signal.receipt.round_state, action.round_state)
        self.assertFalse(signal.receipt.round_state.active_turn.action_slots[0].executed)
        self.assertTrue(result.slot.executed)

    def test_signal_retained_companion_witness_never_changes_clock_roster(self):
        state = active_round(slots=())
        companion = listener('retained-horse', distance=RangedWeaponRange.LONG)
        result = issue_battlefield_musician_signal(signal_request(state=state,
            listeners=(companion,), audience=(CombatTurnParticipant(companion.actor_id, companion.side),)))
        self.assertEqual(result.receipt.heard_actor_ids, ('retained-horse',))
        self.assertEqual(result.receipt.round_state, state)


class BattlefieldMusicianAdmissionTests(unittest.TestCase):
    def test_source_requires_actual_talent_music_lore_tool_holder_and_usable_hands(self):
        actual = source()
        for changes in (
                {'talent': paid_talent(TalentId.HARDY)},
                {'tool_use': replace(actual.tool_use, actor_id='another')},
                {'music_lore': TalentLoreFact('anatomy')},
                {'music_lore': TalentLoreFact('music', magic=True)},
                {'fellowship': True}, {'leadership': True}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(actual, **changes)
        with self.assertRaises(ValueError):
            replace(actual.tool_use, usable_hands=(WeaponGrip.RIGHT,))
        both = source(hands=2)
        self.assertEqual(both.tool_use.used_hands, (WeaponGrip.LEFT, WeaponGrip.RIGHT))
        with self.assertRaises(ValueError):
            replace(both.tool_use, usable_hands=(WeaponGrip.LEFT,))
        free = source(talent=free_talent(TalentId.BATTLEFIELD_MUSICIAN))
        with self.assertRaises(ValueError):
            replace(free, music_lore=TalentLoreFact('anatomy'))

    def test_action_rejects_wrong_skill_profile_slot_declaration_actor_and_defenceless(self):
        request = action_request()
        wrong_declaration = CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.SKILL,
            improvise_approach_id=BATTLEFIELD_MUSICIAN_RULE_ID)
        wrong_slot = replace(request.round_state.active_turn.action_slots[0], declaration=wrong_declaration)
        wrong_state = replace(request.round_state,
            active_turn=replace(request.round_state.active_turn, action_slots=(wrong_slot,)))
        for changes in (
                {'leadership_test': TestRequest('foreign-profile', TestProfile(3, 5))},
                {'slot_index': True}, {'slot_index': 2}, {'round_state': wrong_state},
                {'source': source(actor='another')},
                {'actor_conditions': ConditionState(frozenset((Condition.DEFENCELESS,)))}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(request, **changes)

    def test_audience_rejects_duplicate_ids_foreign_sides_and_alias_clock_witnesses(self):
        request = action_request()
        for changes in (
                {'listeners': (listener(), listener())},
                {'listeners': (listener(side=CombatSide.OPPOSITION),)},
                {'listeners': (listener('unknown'),)},
                {'audience_participants': (CombatTurnParticipant('ally1', CombatSide.PLAYERS_AND_ALLIES),)},
                {'audience_participants': (CombatTurnParticipant('extra', CombatSide.PLAYERS_AND_ALLIES),) * 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(request, **changes)

    def test_second_action_cannot_skip_first_or_claim_an_unrelated_ability_grant(self):
        original = active_round()
        first = CombatActionSlot(1, CombatActionDeclaration(CombatActionKind.RECOVER),
            ActionSlotGrant.STANDARD)
        declaration = original.active_turn.action_slots[0].declaration
        second = CombatActionSlot(2, declaration, ActionSlotGrant.FATE)
        with self.assertRaises(ValueError):
            action_request(state=active_round(slots=(first, second)), slot_index=2)
        receipt = ActionExecutionReceipt('recover', 'rule:recover', 'recover', 'recover',
            'musician', 1, 1, first.declaration)
        first = replace(first, execution=receipt)
        second = replace(second, grant=ActionSlotGrant.ABILITY, grant_rule_id='unrelated:grant')
        with self.assertRaises(ValueError):
            action_request(state=active_round(slots=(first, second)), slot_index=2)

    def test_completion_rejects_foreign_test_or_tampered_final_dice_and_counters(self):
        request = action_request()
        final = resolve_test(request.leadership_test, SequenceRandom([1, 10]))
        for changes in ({'request_id': 'foreign'}, {'successes': 2}, {'successes': True},
                {'final_values': (1, 2)}, {'threshold': 6}, {'applied_rule_ids': ('invented',)}):
            changed = replace(final, trace=replace(final.trace, **changes))
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                complete_battlefield_musician_action(request, changed)

    def test_cached_source_mutation_is_rejected_before_rng_or_signal(self):
        request = action_request()
        object.__setattr__(request.source.tool_use.item.source, 'hands_required', True)
        rng = CountingRandom([1, 2])
        with self.assertRaises(TypeError):
            execute_battlefield_musician_action(request, rng)
        self.assertEqual(rng.calls, [])
        signal = signal_request()
        object.__setattr__(signal.listeners[0], 'can_hear', 1)
        with self.assertRaises(TypeError):
            issue_battlefield_musician_signal(signal)

    def test_action_and_signal_receipts_cannot_change_actual_selected_sources(self):
        result = execute_battlefield_musician_action(action_request(), SequenceRandom([1, 10]))
        for changes in ({'selected_listeners': ()}, {'applied_rule_ids': ()},
                {'round_state': result.previous_round_state}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        signal = issue_battlefield_musician_signal(signal_request())
        with self.assertRaises(ValueError):
            replace(signal.receipt, heard_actor_ids=())
        with self.assertRaises(ValueError):
            replace(signal, receipts=())

    def test_defenceless_cannot_issue_even_an_incidental_signal(self):
        request=signal_request()
        conditions=ConditionState(frozenset((Condition.DEFENCELESS,)))
        with self.assertRaises(ValueError):
            replace(request,actor_conditions=conditions)
        result=issue_battlefield_musician_signal(request)
        with self.assertRaises(ValueError):
            replace(result.receipt,actor_conditions=conditions)

    def test_cached_receipt_aliases_cannot_pass_by_boolean_integer_equality(self):
        result = execute_battlefield_musician_action(action_request(), SequenceRandom([1, 10]))
        forged_slot = replace(result.slot, execution=replace(result.slot.execution))
        object.__setattr__(forged_slot.execution, 'slot_index', True)
        with self.assertRaises(TypeError):
            replace(result, slot=forged_slot)
        signal = issue_battlefield_musician_signal(signal_request())
        forged_receipt = replace(signal.receipt, round_state=replace(signal.receipt.round_state))
        object.__setattr__(forged_receipt.round_state, 'round_number', True)
        with self.assertRaises(TypeError):
            replace(signal, receipts=(forged_receipt,))


if __name__ == '__main__':
    unittest.main()
