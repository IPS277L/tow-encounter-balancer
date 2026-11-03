"""ADR-0065 preflight: real PC profiles, explicit strategies and full sources."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, MISSING, fields, replace
from enum import Enum
import pickle
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.fate_models import (
    FATE_GLORIOUS_RULE_ID, FateBurnKind, FateBurnRecord, FateSessionState,
    FateSpendKind, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleePolicy, PcMeleeScenario,
    PcMeleeWeapon, PcRandomHandPolicy, PcWeaponHand, validate_pc_melee_scenario_admission,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import InlineProfile, Skill, TestProfile
from towr.domain.turn_models import CombatSide


def enemy_changed(source, *, definition=None, state=None):
    enemy = source.enemies[0]
    return replace(source, enemies=(replace(enemy,
        definition=definition if definition is not None else enemy.definition,
        state=state if state is not None else enemy.state), *source.enemies[1:]))


class PcMeleeModelTests(unittest.TestCase):
    def test_supplied_pc_characteristics_produce_book_profiles_and_resilience(self):
        source = make_pc_melee_scenario()
        pc = replace(source.pc, weapon_skill=6, strength=4, toughness=5, agility=2,
            melee=7, defence=8, athletics=3, endurance=9, armour_bonus=2)
        self.assertEqual((pc.melee_profile, pc.defence_profile,
            pc.athletics_profile, pc.endurance_profile),
            (TestProfile(6, 7), TestProfile(6, 8), TestProfile(2, 3), TestProfile(5, 9)))
        self.assertEqual(pc.melee_profile.maximum_dice, 12)
        self.assertEqual(pc.resilience, ResilienceProfile(5, 2))
        self.assertEqual(pc.strength, 4)
        self.assertIs(source.fate_policy, PcFatePolicy.DECLINE_OPTIONAL_FATE)

    def test_all_source_fields_and_policies_are_required(self):
        for cls in (PcMeleeDefinition, PcMeleeFacts, PcMeleeScenario):
            self.assertTrue(all(field.default is MISSING and field.default_factory is MISSING
                                for field in fields(cls)))
        self.assertEqual(tuple(field.name for field in fields(PcMeleeScenario)), (
            'id', 'actor_id', 'pc', 'fate', 'day_id', 'enemies', 'facts', 'policy',
            'fate_policy', 'random_hand_policy', 'initial_weapon_hand',
            'enemy_activation_order', 'target_priority', 'defeat_decisions', 'max_rounds'))

    def test_numeric_pc_guards_use_positive_characteristics_and_skill_thresholds(self):
        pc = make_pc_melee_scenario().pc
        for name in ('weapon_skill', 'strength', 'toughness', 'agility'):
            for value in (True, 1.0, '3', None, 0, -1):
                with self.subTest(field=name, value=value), self.assertRaises((TypeError, ValueError)):
                    replace(pc, **{name: value})
        for name in ('melee', 'defence', 'athletics', 'endurance'):
            for value in (True, 1.0, '4', None, 0, 11):
                with self.subTest(field=name, value=value), self.assertRaises((TypeError, ValueError)):
                    replace(pc, **{name: value})
        for value in (True, 0.0, None, -1):
            with self.subTest(armour=value), self.assertRaises((TypeError, ValueError)):
                replace(pc, armour_bonus=value)

    def test_weapon_and_all_policies_require_their_exact_enums(self):
        class Foreign(str, Enum):
            STAFF = 'staff'
            DECLINE = 'decline_optional_fate'
        source = make_pc_melee_scenario()
        for weapon in ('staff', Foreign.STAFF, None, PcWeaponHand.LEFT):
            with self.subTest(weapon=weapon), self.assertRaises(TypeError):
                replace(source.pc, weapon=weapon)
        for name, valid in (
            ('policy', PcMeleePolicy.ATTACK_OR_RECOVER_SELF),
            ('fate_policy', PcFatePolicy.DECLINE_OPTIONAL_FATE),
            ('random_hand_policy', PcRandomHandPolicy.D10_LOW_LEFT_HIGH_RIGHT),
            ('initial_weapon_hand', PcWeaponHand.LEFT),
        ):
            for value in (valid.value, None, Foreign.DECLINE):
                with self.subTest(field=name, value=value), self.assertRaises(TypeError):
                    replace(source, **{name: value})
        self.assertIs(replace(source.pc, weapon=PcMeleeWeapon.SWORD).weapon, PcMeleeWeapon.SWORD)

    def test_facts_are_explicit_and_unsupported_assertions_are_rejected(self):
        facts = make_pc_melee_scenario().facts
        for name in (field.name for field in fields(facts) if field.name != 'zone_id'):
            for invalid in (1, 0, None, 'true'):
                with self.subTest(field=name, value=invalid), self.assertRaises(TypeError):
                    replace(facts, **{name: invalid})
            if name not in ('outnumbering_bonus_approved', 'can_leave_zone'):
                with self.subTest(field=name), self.assertRaises(ValueError):
                    replace(facts, **{name: False})
        for approved in (False, True):
            for can_leave in (False, True):
                replace(facts, outnumbering_bonus_approved=approved, can_leave_zone=can_leave)

    def test_ids_and_round_budget_are_not_coerced(self):
        source = make_pc_melee_scenario()
        for name in ('id', 'actor_id', 'day_id'):
            for invalid in ('', '  ', None, True, 7):
                with self.subTest(field=name, value=invalid), self.assertRaises((TypeError, ValueError)):
                    replace(source, **{name: invalid})
        for invalid in (False, True, 1.0, '1', 0, -1):
            with self.subTest(rounds=invalid), self.assertRaises((TypeError, ValueError)):
                replace(source, max_rounds=invalid)
        self.assertEqual(replace(source, id=' supplied id ').id, ' supplied id ')

    def test_orders_and_dispositions_cover_exactly_the_reserve_without_forcing_same_order(self):
        source = make_pc_melee_scenario(enemy_count=3)
        priority = ('minion3', 'minion1', 'minion2')
        decisions = tuple(MinionDefeatDecision('pc', target,
            NpcDefeatDisposition.KILLED, True) for target in priority)
        changed = replace(source, target_priority=priority, defeat_decisions=decisions,
            enemy_activation_order=('minion2', 'minion3', 'minion1'))
        self.assertEqual(changed.enemies, source.enemies)
        self.assertEqual(changed.target_priority, priority)
        self.assertIs(changed.enemy('minion1'), source.enemies[0])
        self.assertIs(changed.defeat_decision('minion3'), decisions[0])
        for name in ('target_priority', 'enemy_activation_order'):
            for invalid in ((), ('minion1',), ('minion1',) * 3,
                            ('minion1', 'minion2', 'foreign'), ('minion1', 'minion2', 'pc')):
                with self.subTest(field=name, value=invalid), self.assertRaises(ValueError):
                    replace(source, **{name: invalid})
        for invalid in ((), source.defeat_decisions[:1], tuple(reversed(source.defeat_decisions))):
            with self.subTest(decisions=invalid), self.assertRaises(ValueError):
                replace(source, defeat_decisions=invalid)

    def test_defeat_decisions_require_pc_identity_typed_disposition_and_real_gm_approval(self):
        source = make_pc_melee_scenario()
        for decision in (replace(source.defeat_decisions[0], attacker_id='another'),
                         replace(source.defeat_decisions[0], gm_approved=False)):
            with self.assertRaises(ValueError):
                replace(source, defeat_decisions=(decision,))
        forged = deepcopy(source.defeat_decisions[0])
        object.__setattr__(forged, 'gm_approved', 1)
        with self.assertRaises(TypeError):
            replace(source, defeat_decisions=(forged,))
        forged = deepcopy(source.defeat_decisions[0])
        object.__setattr__(forged, 'disposition', 'killed')
        with self.assertRaises(TypeError):
            replace(source, defeat_decisions=(forged,))

    def test_ordered_lists_are_copied_but_sets_mappings_strings_and_iterators_are_refused(self):
        source = make_pc_melee_scenario()
        for name in ('enemies', 'enemy_activation_order', 'target_priority', 'defeat_decisions'):
            ordered = list(getattr(source, name))
            copied = replace(source, **{name: ordered})
            ordered.clear()
            self.assertEqual(getattr(copied, name), getattr(source, name))
            for invalid in ({}, set(), 'minion1', iter(getattr(source, name))):
                with self.subTest(field=name, value=type(invalid)), self.assertRaises(TypeError):
                    replace(source, **{name: invalid})
        consumed = []
        def sequence():
            consumed.append(True)
            yield source.enemies[0]
        with self.assertRaises(TypeError):
            replace(source, enemies=sequence())
        self.assertEqual(consumed, [])

    def test_fate_retains_positive_rating_and_exhausted_session_resources(self):
        source = make_pc_melee_scenario()
        spend = FateSpendRecord('earlier-spend', 'session', 'pc', FateSpendKind.GLORIOUS_TEST,
            'earlier-test', FATE_GLORIOUS_RULE_ID)
        fate = FateSessionState('session', 'pc', 3, 1, spends=(spend,))
        changed = replace(source, fate=fate)
        self.assertIs(changed.fate, fate)
        self.assertEqual(changed.fate.rating, 3)
        self.assertEqual(changed.fate.remaining_spends, 0)
        self.assertEqual(changed.fate.spends, (spend,))
        burn = FateBurnRecord('earlier-burn', 'session', 'pc', FateBurnKind.NEAR_MISS,
            'earlier-wound', 3, 2, 3, 2, True)
        historical = FateSessionState('session', 'pc', 2, 2,
            burns=(burn,), resource_event_ids=('earlier-burn',))
        self.assertIs(replace(source, fate=historical).fate, historical)

    def test_fate_actor_and_lucky_and_foreign_source_are_refused(self):
        source = make_pc_melee_scenario()
        for fate in (replace(source.fate, actor_id='foreign'), replace(source.fate, has_lucky=True)):
            with self.assertRaises(ValueError):
                replace(source, fate=fate)
        for value in (None, {}, source.pc):
            with self.assertRaises(TypeError):
                replace(source, fate=value)

    def test_scenario_requires_nonempty_distinct_enemy_actors_and_consistent_definitions(self):
        source = make_pc_melee_scenario(enemy_count=2)
        for enemies in ((), (source.enemies[0], source.enemies[0])):
            with self.assertRaises(ValueError):
                replace(source, enemies=enemies)
        with self.assertRaises(ValueError):
            replace(source, actor_id='minion1', fate=replace(source.fate, actor_id='minion1'))
        other = source.enemies[1]
        conflicting = replace(other, definition=replace(other.definition,
            attacks=(replace(other.definition.attacks[0], damage=DamageProfile(99)),)))
        with self.assertRaises(ValueError):
            replace(source, enemies=(source.enemies[0], conflicting))

    def test_minions_start_healthy_armed_without_shields_and_on_opposition_side(self):
        source = make_pc_melee_scenario()
        state = source.enemies[0].state
        variants = (
            replace(state, injury=ProfileInjuryState(1, 1, defeated=True)),
            replace(state, injury=ProfileInjuryState(0, 1,
                conditions=ConditionState(frozenset({Condition.STAGGERED})))),
            replace(state, wields_weapon=False), replace(state, holds_shield=True),
            replace(state, side=CombatSide.PLAYERS_AND_ALLIES),
            replace(state, current_resilience=ResilienceProfile(9)),
            replace(state, available_attack_ids=()),
        )
        for changed in variants:
            with self.subTest(state=changed), self.assertRaises(ValueError):
                enemy_changed(source, state=changed)

    def test_minion_numeric_profiles_require_one_ordinary_close_melee_and_defence(self):
        source = make_pc_melee_scenario()
        definition = source.enemies[0].definition
        attack = definition.attacks[0]
        variants = (
            replace(definition, attacks=()), replace(definition, protection=()),
            replace(definition, attacks=(replace(attack, ignores_armour=True),)),
            replace(definition, attacks=(replace(attack, skill=Skill.SHOOTING),)),
            replace(definition, attacks=(replace(attack, range_max=RangedWeaponRange.SHORT),)),
            replace(definition, attacks=(replace(attack, damage=DamageProfile(3, 2)),)),
            replace(definition, attacks=(replace(attack, test_profile=InlineProfile(2, 4, 4)),)),
            replace(definition, protection=(replace(definition.protection[0], skill=Skill.ATHLETICS),)),
        )
        for changed in variants:
            with self.subTest(definition=changed), self.assertRaises(ValueError):
                enemy_changed(source, definition=changed)

    def test_admission_rechecks_equal_but_corrupt_nested_numeric_and_boolean_snapshots(self):
        source = make_pc_melee_scenario(max_rounds=1)
        source = replace(source, pc=replace(source.pc, strength=1),
            fate=replace(source.fate, rating=1, session_spend_limit=1))
        corruptions = (
            lambda value: object.__setattr__(value, 'max_rounds', True),
            lambda value: object.__setattr__(value.pc, 'strength', True),
            lambda value: object.__setattr__(value.pc, 'armour_bonus', False),
            lambda value: object.__setattr__(value.fate, 'rating', True),
            lambda value: object.__setattr__(value.fate, 'has_lucky', 0),
            lambda value: object.__setattr__(value.enemies[0].state.injury, 'wounds', False),
            lambda value: object.__setattr__(value.enemies[0].state.current_resilience, 'bonus', False),
            lambda value: object.__setattr__(value.enemies[0].definition.attacks[0].damage,
                                            'success_multiplier', True),
            lambda value: object.__setattr__(value.defeat_decisions[0], 'gm_approved', 1),
        )
        for mutate in corruptions:
            forged = deepcopy(source)
            mutate(forged)
            self.assertEqual(forged, source)
            with self.subTest(mutate=mutate), self.assertRaises((TypeError, ValueError)):
                validate_pc_melee_scenario_admission(forged)

    def test_admission_rechecks_fate_records_and_canonical_immutable_collections(self):
        source = make_pc_melee_scenario()
        spend = FateSpendRecord('old', 'session', 'pc', FateSpendKind.GLORIOUS_TEST,
            'old-test', FATE_GLORIOUS_RULE_ID)
        source = replace(source, fate=replace(source.fate, spends=(spend,)))
        forged = deepcopy(source)
        object.__setattr__(forged.fate.spends[0], 'actor_id', 'foreign')
        with self.assertRaises(ValueError):
            validate_pc_melee_scenario_admission(forged)
        for field_name in ('enemies', 'enemy_activation_order', 'target_priority', 'defeat_decisions'):
            forged = deepcopy(source)
            object.__setattr__(forged, field_name, list(getattr(forged, field_name)))
            with self.subTest(field=field_name), self.assertRaises(TypeError):
                validate_pc_melee_scenario_admission(forged)
        forged = deepcopy(source)
        object.__setattr__(forged.enemies[0].definition, 'attacks',
                           list(forged.enemies[0].definition.attacks))
        with self.assertRaises(TypeError):
            validate_pc_melee_scenario_admission(forged)

    def test_imported_snapshot_ids_ranges_and_skills_are_typed_even_when_equal(self):
        source = make_pc_melee_scenario()
        for target, name, invalid in (
            ('attack', 'range_max', 'close'), ('attack', 'range_min', 'close'),
            ('attack', 'skill', 'melee'), ('defence', 'skill', 'defence'),
        ):
            forged = deepcopy(source)
            definition = forged.enemies[0].definition
            item = definition.attacks[0] if target == 'attack' else definition.protection[0]
            object.__setattr__(item, name, invalid)
            self.assertEqual(forged, source)
            with self.subTest(field=name, value=invalid), self.assertRaises(TypeError):
                validate_pc_melee_scenario_admission(forged)

    def test_model_and_fixtures_are_independent_immutable_and_pickleable_without_rng(self):
        with patch('random.Random', side_effect=AssertionError('preflight uses RNG')):
            source = make_pc_melee_scenario()
            another = make_pc_melee_scenario()
            self.assertEqual(source, another)
            self.assertIsNot(source, another)
            self.assertIsNot(source.pc, another.pc)
            self.assertIsNot(source.fate, another.fate)
            self.assertIsNot(source.enemies[0].definition, another.enemies[0].definition)
            self.assertEqual(pickle.loads(pickle.dumps(source)), source)
            validate_pc_melee_scenario_admission(source)
        for value in (source, source.pc, source.facts):
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
                value.extra = 1


if __name__ == '__main__':
    unittest.main()
