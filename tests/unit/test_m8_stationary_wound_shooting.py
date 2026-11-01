"""ADR-0049 Shooting uses the complete stationary source, preserving new Wounds."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_prone_stand import with_injury, with_round
from tests.unit.test_m8_npc_roster_turn import ATTACK
from tests.unit.test_m8_npc_wound_turn_end import wounded
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import WoundEntryId, WoundRecord, WoundRestriction, WoundRestrictionEffect, WoundEffectDuration
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext as Context
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import DiceModifier, QualityModifier, Skill, TestQuality, TestRequest
from towr.rules.npc_attack_preparation import prepare_npc_attack_protection
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def terrain():
    return WoundRestrictionEffect(1, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                                  WoundEffectDuration.UNTIL_TREATED)


def ready():
    """Authored post-stand injury plus real bound enemy activation."""
    state = admitted().initial_runtime_state
    state = with_injury(state, 'wizard', lambda i: replace(i,
        wounds=(WoundRecord(1, WoundEntryId.LEG_SPASM, 9, (9,), effect_resolved=True),),
        active_wound_effects=(terrain(),)))
    enemy = state.roster.participant('enemy')
    if enemy.state.side is not state.round_state.next_side:
        state = with_round(state, replace(state.round_state, side_order=tuple(reversed(state.round_state.side_order))))
    return start_npc_roster_turn(NpcRosterTurnStartRequest('stationary:enemy', state, 'enemy', ATTACK)).state


def prepare(state=None, *, context=True, can_leave=True, request_id='stationary:shot', target_id='wizard'):
    state = ready() if state is None else state
    return prepare_npc_roster_shooting(request_id=request_id, state=state, actor_id='enemy', target_id=target_id,
        selected_attack_id='shot', target_range=RangedWeaponRange.SHORT,
        has_enemy_in_close_range=False, range_approved_by_gm=False,
        defender_is_aware=True, selected_protection_skill=Skill.ATHLETICS,
        can_target_leave_zone=can_leave,
        stationary_wounds=Context(state, 'wizard', True) if context is True else context)


class StationaryWoundShootingTests(unittest.TestCase):
    def test_full_context_preserves_source_and_disables_only_give_ground(self):
        state = ready()
        original, rng = deepcopy(state), getstate()
        result = prepare(state)
        self.assertIs(result.attack.stationary_wounds.state, state)
        self.assertEqual(result.attack.execution.kernel_request.target_state, state.roster.participant('wizard').state.injury)
        self.assertIs(result.attack.execution.kernel_request.can_target_leave_zone, False)
        self.assertEqual(result.attack.preparation.npc_attack.source_request.dice_modifiers, ())
        for option in result.attack.preparation.protection.source_request.options:
            self.assertEqual(option.test, TestRequest(option.test.id, option.test.profile))
        self.assertEqual(state, original)
        self.assertEqual(getstate(), rng)
        self.assertIs(prepare(state, can_leave=False).attack.execution.kernel_request.can_target_leave_zone, False)

    def test_none_keeps_existing_rejection_and_context_requires_type_and_target_role(self):
        with self.assertRaises(ValueError): prepare(context=None)
        for bad in (False, 0, {}, object()):
            with self.subTest(bad=bad), self.assertRaises(TypeError): prepare(context=bad)
        state = ready()
        with self.assertRaises(ValueError): prepare(state, context=Context(state, 'wizard', True), target_id='ally')

    def test_foreign_root_with_equal_child_rejected_by_outer_bridge_and_preparation(self):
        source = prepare()
        foreign = replace(source.state, wizard=replace(source.state.wizard, magic_state=WizardMagicState(1)))
        self.assertEqual(foreign.champion_attack, source.state.champion_attack)
        with self.assertRaises(ValueError): NpcRosterChampionAttackRequest(foreign, source.attack)
        with self.assertRaises(ValueError): prepare(foreign, context=source.attack.stationary_wounds)

    def test_lower_child_and_give_ground_usage_must_match_full_context(self):
        source = prepare()
        lower = source.attack
        with self.assertRaises(ValueError): replace(lower, state=replace(lower.state, consumed_execution_ids=('other',)))
        for changes in ({'can_target_leave_zone': True}, {'target_has_given_ground_this_round': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(lower, execution=replace(lower.execution,
                    kernel_request=replace(lower.execution.kernel_request, **changes)))

    def test_protection_bonus_and_glorious_are_rejected_even_with_canonical_profile(self):
        source = prepare()
        protected = source.attack.preparation
        for changes in ({'dice_modifiers': (DiceModifier('authored:bonus', 1),)},
                        {'quality_modifiers': (QualityModifier('authored:glorious', TestQuality.GLORIOUS),)}):
            option = protected.protection.source_request.options[0]
            request = replace(protected.protection.source_request,
                options=(replace(option, test=replace(option.test, **changes)),))
            changed = prepare_npc_attack_protection(protected.npc_attack, request)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'normal Tests'):
                replace(source.attack, preparation=changed, execution=replace(source.attack.execution,
                    kernel_request=replace(source.attack.execution.kernel_request, attack=changed.attack)))

    def test_new_stomach_blow_keeps_terrain_and_adds_actual_expiry_and_receipts(self):
        source = prepare()
        old = deepcopy(source.state)
        dice = Dice((1, 2, 3, 10, 10, 10, 1, 5))
        attack = execute_npc_champion_attack(source.attack, dice)
        dice.exhausted()
        result = NpcRosterChampionAttackResult(source, attack)
        final = apply_npc_roster_champion_attack_result(source.state, result)
        injury = final.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6))
        self.assertIn(terrain(), injury.active_wound_effects)
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(final.wound_expiries), 1)
        self.assertIs(final.wound_expiries[0].source, attack)
        self.assertEqual(final.wound_expiries[0].deadline_round_number, 1)
        self.assertEqual(len(final.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertEqual(source.state, old)
        Context(final, 'wizard', True)
        with self.assertRaises(ValueError): apply_npc_roster_champion_attack_result(final, result)

    def test_drained_target_uses_normal_protection_and_retains_its_active_expiry(self):
        # Actual Wound6 after the target already completed its turn, plus an
        # explicitly authored post-stand9 history. The next enemy activation
        # is scheduled normally; no expiry/deadline is invented or advanced.
        state = wounded(completed=True)
        wizard = state.wizard.actor_id
        state = with_injury(state, wizard, lambda i: replace(i,
            wounds=(*i.wounds, WoundRecord(2, WoundEntryId.LEG_SPASM, 9, (4, 5), effect_resolved=True)),
            active_wound_effects=(*i.active_wound_effects,
                WoundRestrictionEffect(2, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                                       WoundEffectDuration.UNTIL_TREATED))))
        state = end_npc_wound_turn(NpcWoundTurnEndRequest('stationary:end-first', state, 'brigand:0')).state
        state = start_npc_roster_turn(NpcRosterTurnStartRequest(
            'stationary:next-enemy', state, 'brigand:1', ATTACK)).state
        context = Context(state, wizard, True)
        result = prepare_npc_roster_shooting(request_id='stationary:drained-shot', state=state,
            actor_id='brigand:1', target_id=wizard, selected_attack_id='warbow',
            target_range=RangedWeaponRange.SHORT, has_enemy_in_close_range=False,
            range_approved_by_gm=False, defender_is_aware=True,
            selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=True,
            stationary_wounds=context)
        self.assertTrue(context.injury.conditions.has(Condition.DRAINED))
        self.assertIs(result.attack.execution.kernel_request.can_target_leave_zone, False)
        for option in result.attack.preparation.protection.source_request.options:
            self.assertEqual(option.test, TestRequest(option.test.id, option.test.profile))
        outcome = execute_npc_champion_attack(result.attack, SequenceRandom((10,) * 6))
        current = NpcRosterChampionAttackResult(result, outcome).state
        self.assertEqual(current.wound_expiries, state.wound_expiries)
        self.assertEqual(current.roster.participant(wizard).state.injury, context.injury)

    def test_new_unsupported_wounds_are_registered_without_losing_old_terrain(self):
        for total, rolls in ((4, (1, 3)), (9, (4, 5)), (10, (5, 5)), (13, (6, 7))):
            source = prepare()
            dice = Dice((1, 2, 3, 10, 10, 10, *rolls))
            attack = execute_npc_champion_attack(source.attack, dice)
            dice.exhausted()
            final = NpcRosterChampionAttackResult(source, attack).state
            with self.subTest(total=total):
                injury = final.roster.participant('wizard').state.injury
                self.assertEqual(injury.wounds[-1].table_total, total)
                self.assertIn(terrain(), injury.active_wound_effects)
                self.assertEqual(len(final.champion_attack.daily_wounds.receipts), 1)
                self.assertEqual(final.champion_attack.roster, final.roster)
                self.assertEqual(final.minion_attack.roster, final.roster)
                with self.assertRaises(ValueError): Context(final, 'wizard', True)
                if total == 4:
                    self.assertIsNotNone(final.champion_attack.pending)
                else:
                    self.assertIsNone(final.champion_attack.pending)

    def test_repeated_stagger_cannot_choose_give_ground_but_can_fall_prone(self):
        state = with_injury(ready(), 'wizard', lambda i: replace(i,
            conditions=i.conditions.with_condition(Condition.STAGGERED)))
        source = prepare(state)
        with self.assertRaises(ValueError):
            execute_npc_champion_attack(source.attack, SequenceRandom((1, 10, 10, 10, 10, 10)),
                decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
        result = execute_npc_champion_attack(source.attack, SequenceRandom((1, 10, 10, 10, 10, 10)),
                decisions=FixedKernelDecisions(stagger=StaggerChoice.FALL_PRONE))
        self.assertTrue(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        self.assertIn(terrain(), result.state.roster.participant('wizard').state.injury.active_wound_effects)
        self.assertFalse(result.pending_follow_ups)


if __name__ == '__main__':
    unittest.main()
