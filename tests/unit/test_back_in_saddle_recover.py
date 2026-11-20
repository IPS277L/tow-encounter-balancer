"""Exact simultaneous stand/remount Recover sources; no native mount claim."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pickle import dumps, loads
import unittest

from tests.support.talent_sources import free_talent, paid_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RECOVER_ACTION_RULE_ID, RecoverActionExecutionRequest, RecoverConditionTarget,
    RecoverMode, RecoverMountFollowUp, RecoverStandardChoice,
)
from towr.domain.talent_back_in_saddle_models import (
    BACK_IN_SADDLE_RULE_ID, BackInSaddleSource, validate_back_in_saddle_source,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlotRequest, CombatRoundState, CombatSide, CombatTurnParticipant,
    CombatTurnStartRequest,
)
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class NoRandom:
    def randint(self, low, high):
        raise AssertionError('standard Recover must not roll any dice')


def source(actor='rider', mount='actual-mount', *, free=False):
    acquisition = (free_talent if free else paid_talent)(TalentId.BACK_IN_THE_SADDLE)
    return BackInSaddleSource(actor, mount, acquisition)


def clock(actor='rider', *, side=CombatSide.PLAYERS_AND_ALLIES):
    opposing = CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES
    initial = CombatRoundState(1, (CombatTurnParticipant(actor, side),
        CombatTurnParticipant('ally', side), CombatTurnParticipant('foe', opposing)),
        side_order=(side, opposing))
    active = start_combat_turn(CombatTurnStartRequest('saddle:start', initial, actor)).state
    return reserve_combat_action_slot(CombatActionSlotRequest('saddle:reserve', active, actor,
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state


def choice(actor='rider', *, conditions=None, permission=None, mount='actual-mount'):
    own = ConditionState({Condition.STAGGERED, Condition.PRONE, Condition.DISTRACTED}) if conditions is None else conditions
    target = RecoverConditionTarget(actor, own, None)
    return RecoverStandardChoice(WizardMagicState(miscast_dice=2),
        staggered_target=target if own.has(Condition.STAGGERED) else None,
        prone_target=target,
        mount=RecoverMountFollowUp('saddle:mount', actor, mount, True),
        back_in_saddle_source=source(actor, mount) if permission is None else permission)


def request(*, actor='rider', side=CombatSide.PLAYERS_AND_ALLIES, conditions=None):
    selected = choice(actor, conditions=conditions)
    return RecoverActionExecutionRequest('saddle:recover', clock(actor, side=side), actor,
        selected.prone_target.conditions, False, 1, RecoverMode.STANDARD, selected)


class BackInSaddleRecoverTests(unittest.TestCase):
    def test_exact_immutable_source_keeps_full_acquisition_and_actor_mount_binding(self):
        for free in (False, True):
            original = source(free=free)
            self.assertEqual(loads(dumps(original)), original)
            self.assertTrue(validate_back_in_saddle_source(original, 'rider', 'actual-mount'))
            self.assertFalse(validate_back_in_saddle_source(None, 'rider', 'actual-mount'))
            with self.assertRaises(FrozenInstanceError):
                original.mount_id = 'another'
        for invalid in (True, 'back_in_the_saddle', paid_talent(TalentId.ACROBATIC)):
            with self.subTest(talent=invalid), self.assertRaises((TypeError, ValueError)):
                BackInSaddleSource('rider', 'actual-mount', invalid)
        for actor, mount in ((True, 'mount'), ('rider', True), ('', 'mount'), ('rider', 'rider')):
            with self.subTest(actor=actor, mount=mount), self.assertRaises((TypeError, ValueError)):
                BackInSaddleSource(actor, mount, paid_talent(TalentId.BACK_IN_THE_SADDLE))
        for actor, mount in (('other', 'actual-mount'), ('rider', 'other')):
            with self.assertRaises(ValueError):
                validate_back_in_saddle_source(source(), actor, mount)

    def test_both_sides_execute_one_standard_recover_keep_sources_and_other_benefits(self):
        for side in CombatSide:
            with self.subTest(side=side):
                actual_source = request(side=side)
                before = deepcopy(actual_source)
                actual = execute_recover_action(actual_source, NoRandom())
                self.assertEqual(actual_source, before)
                change, = actual.resolution.condition_changes
                self.assertEqual(change.entity_id, 'rider')
                self.assertEqual(change.removed_conditions, (Condition.STAGGERED, Condition.PRONE))
                self.assertEqual(change.conditions, ConditionState({Condition.DISTRACTED}))
                self.assertIs(actual.resolution.source.back_in_saddle_source,
                    actual_source.choice.back_in_saddle_source)
                self.assertIs(actual.resolution.mount_follow_up, actual_source.choice.mount)
                self.assertEqual(actual.applied_rule_ids, (RECOVER_ACTION_RULE_ID, BACK_IN_SADDLE_RULE_ID))
                self.assertEqual(actual.resolution.magic_state.miscast_dice, 1)
                self.assertIsNone(actual.resolution.object_interaction_follow_up)
                self.assertEqual(len(actual.round_state.active_turn.action_slots), 1)
                self.assertEqual(actual.slot.execution.actor_id, 'rider')
                self.assertTrue(actual.slot.executed)
                self.assertFalse(hasattr(actual, 'fate'))

    def test_only_own_simultaneous_prone_removal_and_mount_receive_the_waiver(self):
        selected = choice()
        for changes in (dict(back_in_saddle_source=None), dict(prone_target=None), dict(mount=None),
                dict(prone_target=replace(selected.prone_target, entity_id='ally', in_close_range=True)),
                dict(prone_target=replace(selected.prone_target, in_close_range=True)),
                dict(back_in_saddle_source=source('other')), dict(back_in_saddle_source=source(mount='other')),
                dict(back_in_saddle_source=True)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(selected, **changes)
        with self.assertRaises(ValueError):
            choice(conditions=ConditionState({Condition.STAGGERED}))
        # Owning the Talent does not authorize another kind of benefit/source.
        with self.assertRaises(ValueError):
            RecoverStandardChoice(WizardMagicState(), back_in_saddle_source=source())

    def test_close_unmounted_and_current_condition_guards_remain_in_force(self):
        original = request()
        for mount_changes in (dict(mount_in_close_range=False), dict(actor_already_mounted=True)):
            selected = replace(original.choice, mount=replace(original.choice.mount, **mount_changes))
            with self.subTest(mount_changes=mount_changes), self.assertRaises(ValueError):
                replace(original, choice=selected)
        with self.assertRaisesRegex(ValueError, 'stale Conditions'):
            replace(original, actor_conditions=ConditionState({Condition.STAGGERED}))
        # A matching foreign snapshot still cannot replace the active actor.
        foreign = choice('ally')
        with self.assertRaises(ValueError):
            replace(original, choice=foreign)
        for conditions, enemy in ((ConditionState({Condition.PRONE, Condition.DEFENCELESS}), False),
                (ConditionState({Condition.PRONE, Condition.BROKEN}), True)):
            blocked = replace(request(conditions=conditions), actor_has_enemy_in_zone=enemy)
            with self.subTest(conditions=conditions), self.assertRaises(ValueError):
                execute_recover_action(blocked, NoRandom())

    def test_cached_source_and_snapshot_forgery_reject_before_rng(self):
        for field, value in (('actor_id', 'other'), ('mount_id', 'other'), ('talent', True)):
            original = deepcopy(request())
            object.__setattr__(original.choice.back_in_saddle_source, field, value)
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                execute_recover_action(original, NoRandom())
        original = deepcopy(request())
        object.__setattr__(original.choice.back_in_saddle_source.talent, 'id', TalentId.ACROBATIC)
        with self.assertRaises(ValueError):
            execute_recover_action(original, NoRandom())
        original = deepcopy(request())
        object.__setattr__(original.choice.mount, 'actor_already_mounted', True)
        with self.assertRaises(ValueError):
            execute_recover_action(original, NoRandom())
        original = deepcopy(request())
        object.__setattr__(original.choice.prone_target.conditions, 'conditions', frozenset({'prone'}))
        with self.assertRaises(TypeError):
            execute_recover_action(original, NoRandom())

    def test_result_rejects_erased_duplicated_invented_or_changed_talent_provenance(self):
        actual = execute_recover_action(request(), NoRandom())
        for trace in ((RECOVER_ACTION_RULE_ID,),
                (*actual.applied_rule_ids, BACK_IN_SADDLE_RULE_ID)):
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                replace(actual, applied_rule_ids=trace)
        original = request()
        simple = replace(original, choice=RecoverStandardChoice(WizardMagicState(),
            prone_target=original.choice.prone_target, staggered_target=original.choice.staggered_target))
        ordinary = execute_recover_action(simple, NoRandom())
        with self.assertRaises(ValueError):
            replace(ordinary, applied_rule_ids=(*ordinary.applied_rule_ids, BACK_IN_SADDLE_RULE_ID))
        forged = deepcopy(actual)
        object.__setattr__(forged.source_request.choice.back_in_saddle_source, 'mount_id', 'other')
        with self.assertRaises(ValueError):
            replace(forged)
        # Another fully valid source is still not the source used by this result.
        other = choice(mount='other')
        with self.assertRaises(ValueError):
            replace(actual, resolution=replace(actual.resolution, source=other,
                mount_follow_up=other.mount))

    def test_paid_source_cannot_execute_the_same_completed_slot_twice(self):
        original = request()
        actual = execute_recover_action(original, NoRandom())
        with self.assertRaisesRegex(ValueError, 'already been executed'):
            execute_recover_action(replace(original, round_state=actual.round_state), NoRandom())
        self.assertEqual(actual.resolution.condition_changes[0].previous_conditions, original.actor_conditions)
        self.assertFalse(hasattr(actual.resolution, 'wound_treatment'))


if __name__ == '__main__':
    unittest.main()
