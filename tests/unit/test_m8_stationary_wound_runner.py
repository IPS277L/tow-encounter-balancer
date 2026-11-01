"""ADR-0050 native policy: real Wounds, mandatory stand, exact journal and stops."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import frame as make_frame
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, departures, Dice
from tests.unit.test_m8_stationary_wound_context import with_wizard_injury
from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_models import NpcMagicStationaryWoundPolicy as Policy
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_stationary_wound_policy import (
    magic_leg_spasm_stand_family, magic_leg_spasm_stand_eligible,
    magic_stationary_wound_context, validate_magic_stationary_wound_step,
)
from towr.domain.npc_magic_step_models import (
    NpcMagicStep, NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run


HIT = (1, 2, 3, 10, 10, 10)
WOUND9 = (*HIT, 9)
THROUGH_ROUND1 = (*WOUND9, *((10,) * 9))
THROUGH_ROUND2 = (*THROUGH_ROUND1, *HIT, 1, 5, *((10,) * 9))
FULL_CHAIN = (*THROUGH_ROUND2, *((10,) * 15))


def scenario(*, stationary=True, miscast=False, wizard_level=4):
    """Authored numeric Wizard4; separate Miscast controls use level2 and nines."""
    source = admitted(wizard_side=CombatSide.OPPOSITION)
    initial = replace(source.initial, wizard=replace(source.initial.wizard,
        caster=replace(source.initial.wizard.caster, wizard_level=wizard_level)))
    return replace(source, initial=initial,
        stationary_wound_continuation=Policy.LEG_SPASM_STAND_AND_CONTINUE if stationary else None,
        miscast_continuation=continuation_policy() if miscast else None)


def complete(*, miscast=False):
    source = scenario(miscast=miscast)
    dice = Dice(FULL_CHAIN)
    result = run(source, dice)
    dice.exhausted()
    return result


def before_stand():
    source = scenario()
    legacy = replace(source, stationary_wound_continuation=None)
    dice = Dice(WOUND9)
    result = run(legacy, dice)
    dice.exhausted()
    return source, result.current


class StationaryWoundRunnerTests(unittest.TestCase):
    def test_actual_full_chain_has_one_free_stand_normal_protection_and_archived_expiry(self):
        source = scenario()
        before, rng_before = deepcopy(source), getstate()
        dice = Dice(FULL_CHAIN)
        result = run(source, dice)
        dice.exhausted()
        self.assertEqual(dice.calls, 48)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertIsNone(result.unsupported)
        self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (9, 3, 3))
        stands = [s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult)]
        self.assertEqual(len(stands), 1)
        stood = stands[0]
        self.assertEqual(stood.before.consumed_execution_ids, stood.after.consumed_execution_ids)
        self.assertEqual(stood.before.round_state, stood.after.round_state)
        self.assertEqual(stood.after.spatial_state.free_move_used_entity_ids, ('wizard',))
        self.assertFalse(stood.after.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        injury = result.current.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6))
        self.assertFalse(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(injury.active_wound_effects), 1)
        self.assertFalse(any(w.treated or w.healed for w in injury.wounds))
        ends = [s.result for s in result.steps if isinstance(s.result, NpcWoundTurnEndResult)
                and s.result.source.expiries]
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0].state.wound_turn_end_receipts[-1].expired_sources, ends[0].source.expiries)
        attacks = [s.result.source.attack for s in result.steps
                   if isinstance(s.result, NpcRosterChampionAttackResult)]
        self.assertEqual(len(attacks), 3)
        self.assertIsNone(attacks[0].stationary_wounds)
        for attack in attacks[1:]:
            self.assertIsNotNone(attack.stationary_wounds)
            self.assertIs(attack.execution.kernel_request.can_target_leave_zone, False)
            self.assertEqual(attack.preparation.npc_attack.source_request.dice_modifiers, ())
        for step in result.steps:
            validate_magic_step_policy(source, step)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)

    def test_four_policy_combinations_keep_stationary_and_miscast_permissions_independent(self):
        results = {}
        for stationary in (False, True):
            for miscast in (False, True):
                source = scenario(stationary=stationary, miscast=miscast)
                dice = Dice(FULL_CHAIN if stationary else WOUND9)
                result = run(source, dice)
                dice.exhausted()
                results[stationary, miscast] = result
                with self.subTest(stationary=stationary, miscast=miscast):
                    if stationary:
                        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                    else:
                        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
                        self.assertEqual(result.executed_actions, 1)
        for stationary in (False, True):
            self.assertEqual(results[stationary, False].steps, results[stationary, True].steps)
            self.assertEqual(results[stationary, False].current, results[stationary, True].current)

    def test_first_wound10_or13_is_not_reinterpreted_as_standable_leg_spasm(self):
        for values, total in (((*HIT, 10), 10), ((*HIT, 3, *((10,) * 9), *HIT, 6, 7), 13)):
            dice = Dice(values)
            result = run(scenario(miscast=True), dice)
            dice.exhausted()
            with self.subTest(total=total):
                self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
                self.assertEqual(result.current.roster.participant('wizard').state.injury.wounds[-1].table_total, total)
                self.assertFalse(any(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps))

    def test_repeated_wound9_stops_even_without_wound6_and_does_not_repeat_stand(self):
        dice = Dice((*THROUGH_ROUND1, *HIT, 4, 5))
        result = run(scenario(), dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        self.assertEqual(tuple(w.table_total for w in result.current.roster.participant('wizard').state.injury.wounds), (9, 9))
        self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps), 1)
        self.assertFalse(magic_leg_spasm_stand_family(result.source, result.current))

    def test_new_wound9_with_expired6_history_stops_without_discarding_new_effects(self):
        dice = Dice((*THROUGH_ROUND2, *HIT, 3, 3, 3))
        result = run(scenario(miscast=True), dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        injury = result.current.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6, 9))
        self.assertTrue(injury.conditions.has(Condition.PRONE))
        self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps), 1)

    def test_new_pending_wound_effect_precedes_stationary_action_or_end(self):
        dice = Dice((*THROUGH_ROUND1, *HIT, 1, 3))
        result = run(scenario(miscast=True), dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertIsNotNone(result.current.champion_attack.pending)
        self.assertIsInstance(result.steps[-1].result, NpcRosterChampionAttackResult)
        self.assertEqual(result.current.roster.participant('wizard').state.injury.wounds[-1].table_total, 4)

    def test_lethal_incoming_wound_keeps_immediate_dead_exclusion_before_turn_end(self):
        source = scenario()
        # The corpse remains in placements, but this separate authored frame
        # covers the two surviving actors after the Wizard's actual death.
        survivor_frame = make_frame(source.initial, live=('ally', 'enemy'))
        source = departures(replace(source, scene_frames=(*source.scene_frames, survivor_frame)))
        dice = Dice((*THROUGH_ROUND2, *HIT, 10, 10, 10, *((10,) * 6)))
        result = run(source, dice)
        dice.exhausted()
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertTrue(result.current.roster.participant('wizard').state.injury.dead)
        excluded = [i for i, s in enumerate(result.steps) if isinstance(s.result, NpcRosterDeadChampionExclusionResult)]
        self.assertEqual(len(excluded), 1)
        index = excluded[0]
        self.assertIsInstance(result.steps[index - 1].result, NpcRosterChampionAttackResult)
        self.assertEqual(result.steps[index].result.source.attack, result.steps[index - 1].result)
        self.assertIn('wizard', result.current.round_state.excluded_turn_entity_ids)
        self.assertEqual(result.executed_actions, 8)

    def test_low_level_miscast_pending_has_priority_at_third_cast_when_policy_absent(self):
        dice = Dice((*FULL_CHAIN[:39], 9, 9, 9))
        result = run(scenario(wizard_level=2), dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(result.current.pending_miscast)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertIsInstance(result.steps[-1].result, NpcRosterCastingResult)

    def test_wind_prone_on_retained_terrain_is_not_a_second_leg_spasm_stand(self):
        dice = Dice((*FULL_CHAIN[:39], 9, 9, 9, 7, 7, 7))
        result = run(scenario(wizard_level=2, miscast=True), dice)
        dice.exhausted()
        self.assertIs(result.unsupported.reason, Reason.END_TURN)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 0)
        self.assertIsInstance(result.steps[-1].result, NpcRosterUnnaturalWindResult)
        self.assertTrue(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        self.assertFalse(magic_leg_spasm_stand_family(result.source, result.current))
        self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps), 1)

    def test_helpers_recognize_family_before_scene_and_require_unused_free_move(self):
        source, state = before_stand()
        frame = source.frame_for(make_frame(state).key)
        self.assertTrue(magic_leg_spasm_stand_family(source, state))
        self.assertTrue(magic_leg_spasm_stand_eligible(source, state, frame))
        spent = replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('wizard',)))
        self.assertFalse(magic_leg_spasm_stand_eligible(source, spent, frame))
        self.assertIs(diagnose_npc_magic_unsupported(source, spent, 'spent').reason, Reason.ACTOR_INJURY)
        self.assertIsNone(magic_stationary_wound_context(source, state, 'wizard'))

    def test_actual_post_stand_context_requires_policy_and_exact_wizard_source(self):
        result = complete()
        stand = next(s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
        ctx = magic_stationary_wound_context(result.source, stand.after, 'wizard')
        self.assertEqual(ctx.state, stand.after)
        self.assertIs(ctx.can_give_ground, False)
        self.assertIsNone(magic_stationary_wound_context(
            replace(result.source, stationary_wound_continuation=None), stand.after, 'wizard'))
        self.assertIsNone(magic_stationary_wound_context(result.source, stand.after, 'ally'))

    def test_missing_current_frame_is_missing_scene_not_an_injury_reclassification(self):
        source, state = before_stand()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p
                          for p in state.spatial_state.placements)
        state = replace(state, spatial_state=replace(state.spatial_state, placements=positions))
        self.assertTrue(magic_leg_spasm_stand_family(source, state))
        self.assertIs(diagnose_npc_magic_unsupported(source, state, 'missing').reason, Reason.MISSING_SCENE)

    def test_current_close_scene_blocks_stand_without_falling_back_to_old_prone_path(self):
        source, state = before_stand()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id in ('wizard', 'enemy') else p
                          for p in state.spatial_state.placements)
        state = replace(state, spatial_state=replace(state.spatial_state, placements=positions))
        frame = make_frame(state)
        frame = replace(frame, pair_ranges=tuple(replace(p, target_range=Range.CLOSE)
            if 'wizard' in (p.first_actor_id, p.second_actor_id) else p for p in frame.pair_ranges))
        source = replace(source, scene_frames=(*source.scene_frames, frame))
        self.assertFalse(magic_leg_spasm_stand_eligible(source, state, frame))
        self.assertIs(diagnose_npc_magic_unsupported(source, state, 'close').reason, Reason.ACTOR_INJURY)

    def test_stationary_incoming_shot_still_requires_authored_departure_fact(self):
        result = complete()
        shot = next(s for s in result.steps if isinstance(s.result, NpcRosterChampionAttackResult)
                    and s.result.source.attack.stationary_wounds is not None)
        source = replace(result.source, scene_frames=tuple(replace(f,
            attack_departures=tuple(d for d in f.attack_departures if d.actor_id != 'wizard'))
            for f in result.source.scene_frames))
        self.assertIs(diagnose_npc_magic_unsupported(source, shot.before, 'missing-departure').reason, Reason.MISSING_ROUTE)
        with self.assertRaises(ValueError): validate_magic_step_policy(source, shot)

    def test_context_bearing_steps_and_leg_stand_cannot_be_replayed_under_none_policy(self):
        result = complete()
        legacy = replace(result.source, stationary_wound_continuation=None, miscast_continuation=continuation_policy())
        for step in result.steps:
            inner = step.result.source
            ctx = getattr(inner, 'stationary_wounds', None)
            if isinstance(step.result, NpcRosterChampionAttackResult):
                ctx = inner.attack.stationary_wounds
            if isinstance(step.result, NpcRosterLegSpasmStandResult) or ctx is not None:
                with self.subTest(step=type(step.result).__name__), self.assertRaises(ValueError):
                    validate_magic_stationary_wound_step(legacy, step)
        with self.assertRaises(ValueError): replace(result, source=legacy)

    def test_journal_reconstruction_rejects_skipped_stand_and_same_id_foreign_root(self):
        result = complete()
        index = next(i for i, s in enumerate(result.steps) if isinstance(s.result, NpcRosterLegSpasmStandResult))
        with self.assertRaises(ValueError): replace(result, steps=result.steps[:index] + result.steps[index + 1:])
        stand = result.steps[index].result
        foreign_state = replace(stand.source.state, wizard=replace(stand.source.state.wizard, magic_state=WizardMagicState(1)))
        foreign_source = replace(stand.source, state=foreign_state)
        foreign_step = NpcMagicStep(NpcRosterLegSpasmStandResult(foreign_source, stand.stand))
        self.assertEqual(foreign_step.id, result.steps[index].id)
        with self.assertRaises(ValueError):
            replace(result, steps=(*result.steps[:index], foreign_step, *result.steps[index + 1:]))
        cast = next(s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult)
                    and s.result.source.stationary_wounds is not None)
        source = cast.source
        foreign = replace(source.state, consumed_execution_ids=(*source.state.consumed_execution_ids, 'foreign'))
        with self.assertRaises(ValueError):
            replace(source, stationary_wounds=replace(source.stationary_wounds, state=foreign))

    def test_same_value_string_policy_cannot_launder_diagnosis_or_journal(self):
        result = complete()
        pending_dice = Dice((*FULL_CHAIN[:39], 9, 9, 9))
        pending = run(scenario(wizard_level=2), pending_dice)
        pending_dice.exhausted()
        self.assertIsNotNone(pending.current.pending_miscast)
        for original in (result, pending):
            forged = deepcopy(original.source)
            # Deliberately bypass the frozen constructor: str-enum equality must
            # not admit a malformed source through pure diagnosis or replay.
            object.__setattr__(forged, 'stationary_wound_continuation',
                               Policy.LEG_SPASM_STAND_AND_CONTINUE.value)
            for state in (original.source.initial_runtime_state, original.current):
                with self.subTest(pending=original is pending, idle=state.round_state.active_turn is None):
                    with self.assertRaises(TypeError):
                        diagnose_npc_magic_unsupported(forged, state, 'forged-policy')
            with self.assertRaises(TypeError):
                validate_magic_stationary_wound_step(forged, original.steps[0])
            with self.assertRaises(TypeError):
                replace(original, source=forged)

    def test_transported_stand_cannot_remove_prone_without_spending_free_move(self):
        result = complete()
        index = next(i for i, step in enumerate(result.steps)
                     if isinstance(step.result, NpcRosterLegSpasmStandResult))
        original = result.steps[index]
        forged = deepcopy(original)
        self.assertEqual(forged.result.stand.state.free_move_used_entity_ids, ('wizard',))
        # Model corrupt transport/unpickling, which bypasses frozen constructors.
        object.__setattr__(forged.result.stand.state, 'free_move_used_entity_ids', ())
        self.assertEqual(forged.before, original.before)
        self.assertEqual(forged.result.source, original.result.source)
        self.assertEqual(forged.id, original.id)
        self.assertEqual(forged.after.spatial_state.free_move_used_entity_ids, ())
        self.assertFalse(forged.after.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        with self.assertRaises(ValueError):
            validate_magic_step_policy(result.source, forged)
        with self.assertRaises(ValueError):
            replace(result, steps=(*result.steps[:index], forged, *result.steps[index + 1:]))

    def test_policy_rejects_leg_record_without_terrain_instead_of_legacy_casting_fallback(self):
        result = complete()
        original = next(step for step in result.steps
                        if isinstance(step.result, NpcRosterCastingResult))
        state = with_wizard_injury(original.before,
                                  lambda injury: replace(injury, active_wound_effects=()))
        self.assertEqual(tuple(w.table_total for w in state.roster.participant('wizard').state.injury.wounds), (9,))
        self.assertIsNone(magic_stationary_wound_context(result.source, state, 'wizard'))
        self.assertIs(diagnose_npc_magic_unsupported(result.source, state, 'missing-terrain').reason,
                      Reason.ACTOR_INJURY)
        # The synthetic snapshot still passes the legacy lower Casting boundary;
        # the explicit scenario permission must impose its stronger provenance.
        source = replace(original.result.source, state=state, stationary_wounds=None)
        forged = NpcMagicStep(replace(original.result, source=source))
        self.assertIsNone(forged.result.source.stationary_wounds)
        legacy = replace(result.source, stationary_wound_continuation=None)
        self.assertIsNone(diagnose_npc_magic_unsupported(legacy, state, 'legacy-missing-terrain'))
        with self.assertRaises(ValueError):
            validate_magic_step_policy(result.source, forged)

    def test_stand_exception_propagates_once_without_retry_or_legacy_fallback(self):
        failure = RuntimeError('stand failed')
        dice = Dice(WOUND9)
        with patch('towr.engine.npc_magic_scenario_runner.stand_npc_roster_leg_spasm', side_effect=failure) as reducer:
            with self.assertRaises(RuntimeError) as caught: run(scenario(), dice)
        self.assertIs(caught.exception, failure)
        reducer.assert_called_once()
        dice.exhausted()


if __name__ == '__main__':
    unittest.main()
