"""ADR-0046 bound Shooting/Protection with actual standalone Prone."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.unit.test_m8_npc_roster_minion_attack import begin, changed_roster, request as ordinary_request
from tests.unit.test_m8_npc_magic_scenario import scenario
from tests.unit.test_m8_npc_roster_prone_stand import with_injury
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.test_models import DiceModifier, Skill
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting


PRONE = DiceModifier('RULE-COMBAT-009:prone-target', -1)


def add_condition(state, actor, condition=Condition.PRONE):
    return with_injury(state, actor, lambda injury: replace(
        injury, conditions=injury.conditions.with_condition(condition)))


def minion_state(*, actor_prone=False, target_prone=False):
    state = begin(scenario().initial_runtime_state, 'ally')
    if actor_prone:
        state = add_condition(state, 'ally')
    if target_prone:
        state = add_condition(state, 'enemy')
    return state


def prepare(state, target='enemy', **changes):
    actor = state.roster.participant(state.round_state.active_turn.actor_id)
    selected = next((profile for profile in actor.definition.attacks if profile.skill is Skill.SHOOTING),
                    actor.definition.attacks[0])
    args = dict(request_id='prone:shoot', state=state, actor_id=actor.state.actor_id,
                target_id=target, selected_attack_id=selected.id,
                target_range=Range.SHORT, has_enemy_in_close_range=False,
                range_approved_by_gm=False, defender_is_aware=True,
                selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=True)
    args.update(changes)
    return prepare_npc_roster_shooting(**args)


def modified_preparation(source, modifiers):
    """Rebuild real K1 preparations; do not forge a frozen result object."""
    old = source.attack
    npc = prepare_npc_attack(replace(old.preparation.npc_attack.source_request,
                                     dice_modifiers=modifiers))
    protected = prepare_npc_attack_protection(npc, replace(
        old.preparation.protection.source_request, attack=npc.attack))
    execution = replace(old.execution, kernel_request=replace(
        old.execution.kernel_request, attack=protected.attack))
    return replace(source, attack=replace(old, preparation=protected, execution=execution))


class ProneShootingTests(unittest.TestCase):
    def test_healthy_factory_matches_existing_preparation_and_preserves_departure(self):
        source = prepare(minion_state())
        self.assertIsInstance(source, NpcRosterMinionAttackRequest)
        self.assertEqual(source.attack.preparation.npc_attack.source_request.dice_modifiers, ())
        self.assertTrue(source.attack.execution.kernel_request.can_target_leave_zone)
        self.assertEqual(source.attack.preparation.attack.attacker_test.profile,
                         ordinary_request().attack.preparation.attack.attacker_test.profile)

    def test_own_prone_has_no_attack_or_protection_penalty(self):
        healthy = prepare(minion_state())
        prone = prepare(minion_state(actor_prone=True))
        self.assertEqual(prone.attack.preparation, healthy.attack.preparation)
        self.assertTrue(prone.state.roster.participant('ally').state.injury.conditions.has(Condition.PRONE))

    def test_prone_minion_target_has_exactly_one_minus_die_and_effective_false(self):
        state = minion_state(actor_prone=True, target_prone=True)
        before = deepcopy(state)
        source = prepare(state)
        self.assertIs(source.state, state)
        self.assertEqual(source.attack.preparation.npc_attack.source_request.dice_modifiers, (PRONE,))
        self.assertEqual(source.attack.preparation.attack.attacker_test.dice_modifiers, (PRONE,))
        self.assertFalse(source.attack.execution.kernel_request.can_target_leave_zone)
        self.assertEqual(state, before)

    def test_prone_champion_target_uses_same_modifier_and_keeps_full_owner(self):
        old = incoming_attack()
        target = old.attack.execution.target_id
        state = add_condition(old.state, target)
        source = prepare(state, target)
        self.assertIsInstance(source, NpcRosterChampionAttackRequest)
        self.assertEqual(source.attack.preparation.npc_attack.source_request.dice_modifiers, (PRONE,))
        self.assertFalse(source.attack.execution.kernel_request.can_target_leave_zone)
        self.assertIs(source.state, state)
        self.assertEqual(source.attack.state.daily_wounds, old.attack.state.daily_wounds)

    def test_prone_shooter_cannot_claim_champion_departure_without_adjacent_zone(self):
        old = incoming_attack()
        state = add_condition(old.state, old.attack.execution.actor_id)
        target = old.attack.execution.target_id
        with self.assertRaisesRegex(ValueError, 'adjacent Zone'):
            prepare(state, target)
        source = prepare(state, target, can_target_leave_zone=False)
        self.assertEqual(source.attack.preparation.npc_attack.source_request.dice_modifiers, ())

    def test_protection_test_is_identical_for_prone_target(self):
        ordinary = prepare(minion_state())
        prone = prepare(minion_state(target_prone=True))
        self.assertEqual(prone.attack.preparation.attack.defender_test,
                         ordinary.attack.preparation.attack.defender_test)
        self.assertEqual(prone.attack.preparation.protection.eligible_skills,
                         ordinary.attack.preparation.protection.eligible_skills)

    def test_direct_bound_handoff_rejects_invented_prone_protection_penalty(self):
        source = prepare(minion_state(target_prone=True))
        old = source.attack
        protection = old.preparation.protection.source_request
        options = tuple(replace(option, test=replace(option.test,
            dice_modifiers=(DiceModifier('authored:prone-protection', -1),)))
            for option in protection.options)
        protected = prepare_npc_attack_protection(old.preparation.npc_attack,
                                                   replace(protection, options=options))
        execution = replace(old.execution, kernel_request=replace(
            old.execution.kernel_request, attack=protected.attack))
        with self.assertRaises(ValueError):
            replace(source, attack=replace(old, preparation=protected, execution=execution))

    def test_prone_modifier_composes_with_existing_outside_optimum(self):
        old = incoming_attack()
        target = old.attack.execution.target_id
        source = prepare(add_condition(old.state, target), target, target_range=Range.SHORT)
        modifiers = source.attack.preparation.attack.attacker_test.dice_modifiers
        self.assertEqual(modifiers.count(PRONE), 1)
        self.assertIn(DiceModifier('RULE-NPC-007:outside-optimum', -1), modifiers)

    def test_missing_duplicate_positive_and_foreign_modifiers_rejected(self):
        source = prepare(minion_state(target_prone=True))
        cases = ((), (PRONE, PRONE), (DiceModifier(PRONE.rule_id, 1),),
                 (PRONE, DiceModifier('authored:other', -1)),
                 (DiceModifier('authored:other', -1),))
        for modifiers in cases:
            with self.subTest(modifiers=modifiers), self.assertRaises(ValueError):
                modified_preparation(source, modifiers)

    def test_stray_prone_modifier_rejected_for_healthy_target(self):
        for actor_prone in (False, True):
            with self.subTest(actor_prone=actor_prone), self.assertRaises(ValueError):
                modified_preparation(prepare(minion_state(actor_prone=actor_prone)), (PRONE,))

    def test_healthy_explicit_modifiers_remain_an_existing_bound_input(self):
        modifier = DiceModifier('authored:other', -1)
        source = modified_preparation(prepare(minion_state()), (modifier,))
        self.assertEqual(source.attack.preparation.npc_attack.source_request.dice_modifiers, (modifier,))

    def test_direct_bound_handoffs_reject_prone_true_departure(self):
        champion = incoming_attack()
        target = champion.attack.execution.target_id
        sources = (prepare(minion_state(target_prone=True)),
                   prepare(add_condition(champion.state, target), target))
        for source in sources:
            with self.subTest(kind=type(source)), self.assertRaises(ValueError):
                execution = replace(source.attack.execution, kernel_request=replace(
                    source.attack.execution.kernel_request, can_target_leave_zone=True))
                replace(source, attack=replace(source.attack, execution=execution))

    def test_actual_given_ground_usage_is_not_reset_by_prone(self):
        state = minion_state(target_prone=True)
        state = replace(state, spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('enemy',)))
        source = prepare(state)
        self.assertTrue(source.attack.execution.kernel_request.target_has_given_ground_this_round)
        with self.assertRaises(ValueError):
            execution = replace(source.attack.execution, kernel_request=replace(
                source.attack.execution.kernel_request, target_has_given_ground_this_round=False))
            replace(source, attack=replace(source.attack, execution=execution))

    def test_factory_boolean_inputs_are_strict_even_when_prone_forces_false(self):
        state = minion_state(target_prone=True)
        for name in ('has_enemy_in_close_range', 'range_approved_by_gm',
                     'defender_is_aware', 'can_target_leave_zone'):
            for value in (0, 1, None, 'false'):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    prepare(state, **{name: value})

    def test_extra_actor_and_target_conditions_remain_unsupported(self):
        for actor, condition in (('ally', Condition.BROKEN), ('ally', Condition.DRAINED),
                                 ('enemy', Condition.DRAINED), ('enemy', Condition.BLINDED)):
            state = add_condition(minion_state(actor_prone=True, target_prone=True), actor, condition)
            with self.subTest(actor=actor, condition=condition), self.assertRaises(ValueError):
                prepare(state)

    def test_champion_ongoing_prone_causes_and_unresolved_wounds_rejected(self):
        old = incoming_attack()
        target = old.attack.execution.target_id
        state = add_condition(old.state, target)
        wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        effects = (WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
                   WoundRestrictionEffect(1, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
                                          WoundEffectDuration.UNTIL_TREATED))
        for effect in effects:
            bad = with_injury(state, target, lambda injury: replace(
                injury, wounds=(wound,), active_wound_effects=(effect,)))
            with self.subTest(effect=effect), self.assertRaises(ValueError):
                prepare(bad, target)
        unresolved = with_injury(state, target, lambda injury: replace(
            injury, wounds=(replace(wound, effect_resolved=False),)))
        with self.assertRaises(ValueError):
            prepare(unresolved, target)

    def test_full_owner_untracked_wound_clock_blocks_prone_minion_attack(self):
        state = minion_state(target_prone=True)
        wound = WoundRecord(1, WoundEntryId.STOMACH_BLOW, 6, (6,), effect_resolved=True)
        state = with_injury(state, 'wizard', lambda injury: replace(injury,
            wounds=(wound,), conditions=injury.conditions.with_condition(Condition.DRAINED),
            active_wound_effects=(WoundConditionEffect(1, Condition.DRAINED,
                                                       WoundEffectDuration.END_OF_NEXT_TURN),)))
        with self.assertRaises(ValueError):
            prepare(state)

    def test_live_excluded_actor_and_inactive_action_rejected(self):
        state = minion_state(target_prone=True)
        combat = replace(state.round_state, excluded_turn_entity_ids=('wizard',))
        state = replace(state, round_state=combat,
                        champion_attack=replace(state.champion_attack, round_state=combat))
        with self.assertRaises(ValueError):
            prepare(state)
        source = prepare(minion_state(target_prone=True))
        with self.assertRaises(ValueError):
            prepare(source.state, actor_id='enemy')

    def test_prone_melee_context_is_not_silently_treated_as_shooting(self):
        state = minion_state(target_prone=True)
        def melee(participant):
            if participant.state.actor_id != 'ally':
                return participant
            profile = replace(participant.definition.attacks[0], skill=Skill.MELEE,
                              range_min=Range.CLOSE, range_max=Range.CLOSE)
            definition = replace(participant.definition, id='authored:prone-melee', attacks=(profile,))
            return replace(participant, definition=definition,
                           state=replace(participant.state, definition_id=definition.id))
        state = changed_roster(state, melee)
        with self.assertRaises(ValueError):
            prepare(state, target_range=Range.CLOSE, has_enemy_in_close_range=True)


if __name__ == '__main__':
    unittest.main()
