"""GM187 Skin Wolf profile and caller-confirmed Close/end-phase policies."""
from copy import deepcopy
from dataclasses import fields, replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeScenario, validate_pc_melee_scenario_admission
from towr.domain.pc_npc_ability_models import pc_npc_attack_modifiers
from towr.domain.pc_npc_blood_rage_policy_models import SKIN_WOLF_BLOOD_RAGE_RULE_ID
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, PcBookNpcWoundBand, create_pc_book_npc, get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, InlineProfile, Skill


PROFILE = PcBookNpcProfile.SKIN_WOLF
SOURCE = 'BOOK-GM-GUIDE:1.1:p187:skin_wolf'


def scene(**kwargs):
    return book_pc_scenario(skin_wolves=kwargs.pop('skin_wolves', 1), footpads=kwargs.pop('footpads', 0),
        townsfolk=kwargs.pop('townsfolk', 0), **kwargs)


def policy(source, actor='skin_wolf1', close=None):
    close = source.pc_activation_order if close is None else close
    decisions = tuple(MinionDefeatDecision(actor, target, NpcDefeatDisposition.KILLED, True)
        for target in close if target in source.enemy_activation_order)
    return PcWarpedFormPolicy(actor, close, decisions)


class PcSkinWolfCatalogTests(unittest.TestCase):
    def test_exact_printed_natural_attack_resilience_and_source(self):
        entry = get_pc_book_npc_entry(PROFILE)
        definition = entry.definition
        self.assertEqual((entry.profile_id, entry.book_id, entry.version, entry.chapter, entry.page),
            (PROFILE, 'BOOK-GM-GUIDE', '1.1', 'Allies and Antagonists', 187))
        self.assertEqual((definition.id, definition.source_rule_id, definition.injury_policy,
            definition.wound_limit, definition.resilience),
            ('pc-book-npc:skin_wolf', SOURCE, TargetInjuryPolicy.BRUTE, 3, ResilienceProfile(4, 1)))
        attack, = definition.attacks
        self.assertEqual((attack.id, attack.source_rule_id, attack.skill, attack.test_profile,
            attack.damage, attack.range_min, attack.range_max, attack.hands,
            attack.ignores_armour, attack.secondary_effects),
            ('claws_and_fangs', SOURCE+':claws_and_fangs', Skill.MELEE, InlineProfile(5, 3),
             DamageProfile(5), RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None, False, ()))
        validate_pc_book_npc_definition(definition)

    def test_athletics_has_its_own_implicit_cap_and_no_unselected_protection(self):
        entry = get_pc_book_npc_entry(PROFILE)
        protection, = entry.definition.protection
        self.assertEqual((protection.source_rule_id, protection.skill, protection.test_profile),
            (SOURCE+':athletics', Skill.ATHLETICS, InlineProfile(4, 3)))
        self.assertEqual((entry.definition.attacks[0].test_profile.maximum_dice,
            protection.test_profile.maximum_dice), (10, 8))
        self.assertIsNone(entry.definition.attacks[0].test_profile.pool_cap)
        self.assertIsNone(protection.test_profile.pool_cap)
        self.assertEqual(entry.unselected_protection, ())

    def test_fresh_factory_preserves_healthy_natural_armed_facts_and_graph_independence(self):
        first = create_pc_book_npc(PROFILE, 'wolf1')
        second = create_pc_book_npc(PROFILE, 'wolf2')
        self.assertEqual((first.state.wields_weapon, first.state.holds_shield,
            first.state.available_attack_ids, first.state.current_resilience),
            (False, False, ('claws_and_fangs',), ResilienceProfile(4, 1)))
        self.assertEqual((first.state.injury.wounds, first.state.injury.wound_limit,
            first.state.injury.defeated, first.state.injury.conditions.conditions), (0, 3, False, frozenset()))
        self.assertIsNot(first.definition, second.definition)
        self.assertIsNot(first.state.injury, second.state.injury)
        object.__setattr__(first.definition.attacks[0].test_profile, 'threshold', 1)
        self.assertEqual(second.definition, get_pc_book_npc_entry(PROFILE).definition)

    def test_card_preserves_both_abilities_non_fire_boundary_and_wound_bands(self):
        entry = get_pc_book_npc_entry(PROFILE)
        rage, warped = entry.active_abilities
        self.assertEqual(rage.name, 'Blood Rage')
        self.assertIn('Staggered Skin Wolves gain +1d Melee', rage.effect)
        self.assertEqual(warped.name, 'Warped Form')
        self.assertIn('end of its own turn', warped.scope)
        self.assertIn('non-fire Wound', warped.effect)
        self.assertIn('all other creatures in Close Range', warped.effect)
        self.assertEqual(entry.wound_bands, (PcBookNpcWoundBand(0, 'No effect'),
            PcBookNpcWoundBand(1, 'Warped Form'), PcBookNpcWoundBand(2, 'Warped Form'),
            PcBookNpcWoundBand(3, 'Defeated')))
        self.assertEqual((entry.inactive_abilities, entry.unselected_attack_names,
            entry.unselected_variant_names), ((), (), ()))

    def test_changed_numbers_caps_hands_gear_and_partial_source_renames_are_rejected(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        attack, = definition.attacks
        protection, = definition.protection
        for candidate in (replace(definition, attacks=(replace(attack, damage=DamageProfile(6)),)),
                replace(definition, attacks=(replace(attack, test_profile=InlineProfile(5, 3, 10)),)),
                replace(definition, protection=(replace(protection, test_profile=InlineProfile(4, 4)),)),
                replace(definition, resilience=ResilienceProfile(4, 0)),
                replace(definition, id='authored:root', source_rule_id='authored:root')):
            with self.subTest(candidate=candidate), self.assertRaises((TypeError, ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_cached_aliases_do_not_claim_canonical_types(self):
        canonical = get_pc_book_npc_entry(PROFILE).definition
        for target, name, value in (('definition', 'injury_policy', 'brute'),
                ('attack', 'skill', 'melee'), ('profile', 'dice', 5.0),
                ('profile', 'threshold', 3.0), ('damage', 'success_multiplier', True)):
            forged = deepcopy(canonical)
            obj = {'definition':forged, 'attack':forged.attacks[0],
                'profile':forged.attacks[0].test_profile, 'damage':forged.attacks[0].damage}[target]
            object.__setattr__(obj, name, value)
            self.assertEqual(forged, canonical)
            with self.subTest(target=target, name=name), self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)

    def test_staggered_bonus_uses_skin_wolf_rule_independent_of_voluntary_selection(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        for wounds in (0, 1, 2):
            self.assertEqual(pc_npc_attack_modifiers(definition, ConditionState((Condition.STAGGERED,)),
                target_conditions=ConditionState(), attacker_wounds=wounds),
                (DiceModifier(SKIN_WOLF_BLOOD_RAGE_RULE_ID, 1),))
        self.assertEqual(pc_npc_attack_modifiers(definition, ConditionState(),
            target_conditions=ConditionState(), attacker_wounds=1), ())


class PcWarpedFormPolicyTests(unittest.TestCase):
    def test_field_is_required_keyword_only_without_compatibility_default(self):
        field = next(item for item in fields(PcMeleeScenario) if item.name == 'npc_warped_form_policies')
        self.assertTrue(field.kw_only)
        from dataclasses import MISSING
        self.assertIs(field.default, MISSING)
        source = scene()
        values = {item.name:getattr(source, item.name) for item in fields(source)}
        del values['npc_warped_form_policies']
        with self.assertRaises(TypeError):
            PcMeleeScenario(**values)

    def test_all_pcs_and_explicit_same_side_npcs_keep_literal_order(self):
        source = scene(footpads=2)
        selected = policy(source, close=('pc2', 'footpad2', 'pc1', 'footpad1'))
        actual = replace(source, npc_warped_form_policies=(selected,))
        self.assertEqual(actual.npc_warped_form_policies[0].close_actor_ids,
            ('pc2', 'footpad2', 'pc1', 'footpad1'))
        self.assertEqual(tuple(row.target_id for row in selected.npc_defeat_decisions),
            ('footpad2', 'footpad1'))
        validate_pc_melee_scenario_admission(actual)

    def test_unknown_duplicate_self_missing_pc_and_extra_pc_decision_rejected(self):
        source = scene(footpads=1)
        for close in (('pc1',), ('pc1', 'pc2', 'unknown'), ('pc1', 'pc2', 'skin_wolf1'),
                ('pc1', 'pc1', 'pc2')):
            with self.subTest(close=close), self.assertRaises((TypeError, ValueError)):
                replace(source, npc_warped_form_policies=(policy(source, close=close),))
        selected = policy(source)
        with self.assertRaises(ValueError):
            replace(source, npc_warped_form_policies=(replace(selected,
                npc_defeat_decisions=(MinionDefeatDecision('skin_wolf1', 'pc1',
                    NpcDefeatDisposition.KILLED, True),)),))

    def test_caster_requires_complete_canonical_opposition_skin_wolf_and_unique_policy(self):
        source = scene(footpads=1)
        selected = policy(source)
        for actor in ('pc1', 'unknown', 'footpad1'):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                replace(source, npc_warped_form_policies=(policy(source, actor),))
        with self.assertRaises(ValueError):
            replace(source, npc_warped_form_policies=(selected, selected))
        forged = deepcopy(source)
        object.__setattr__(forged.enemies[0].definition.attacks[0].test_profile, 'threshold', 2)
        with self.assertRaises(ValueError):
            replace(forged, npc_warped_form_policies=(selected,))

    def test_npc_decisions_cover_each_same_side_target_in_order_and_belong_to_caster(self):
        source = scene(footpads=2)
        selected = policy(source, close=('pc1', 'footpad2', 'pc2', 'footpad1'))
        for decisions in ((), selected.npc_defeat_decisions[::-1], selected.npc_defeat_decisions[:1]):
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                replace(source, npc_warped_form_policies=(replace(selected, npc_defeat_decisions=decisions),))
        decision = selected.npc_defeat_decisions[0]
        for candidate in (replace(decision, attacker_id='pc1'), replace(decision, gm_approved=False)):
            with self.assertRaises(ValueError):
                replace(selected, npc_defeat_decisions=(candidate, selected.npc_defeat_decisions[1]))

    def test_configured_wolves_require_symmetric_explicit_close_facts(self):
        source = scene(skin_wolves=2)
        first = policy(source, close=('pc1', 'skin_wolf2', 'pc2'))
        second = policy(source, actor='skin_wolf2', close=('pc2', 'pc1', 'skin_wolf1'))
        replace(source, npc_warped_form_policies=(first, second))
        with self.assertRaises(ValueError):
            replace(source, npc_warped_form_policies=(first, policy(source, actor='skin_wolf2')))
        replace(source, npc_warped_form_policies=(policy(source), policy(source, actor='skin_wolf2')))

    def test_exact_collection_record_and_nested_alias_types_are_readmitted(self):
        source = scene(footpads=1)
        selected = policy(source, close=('pc1', 'pc2', 'footpad1'))
        for policies in ([selected], (object(),)):
            with self.assertRaises(TypeError):
                replace(source, npc_warped_form_policies=policies)
        for field, value in (('actor_id', 1), ('close_actor_ids', ['pc1', 'pc2']),
                ('npc_defeat_decisions', list(selected.npc_defeat_decisions))):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(selected, **{field:value})
        for field, value in (('disposition', 'killed'), ('gm_approved', 1)):
            forged = deepcopy(selected)
            object.__setattr__(forged.npc_defeat_decisions[0], field, value)
            self.assertEqual(forged, selected)
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(source, npc_warped_form_policies=(forged,))

    def test_empty_policy_declines_form_and_rage_can_be_selected_independently(self):
        source = scene()
        selected = replace(source, npc_blood_rage_actor_ids=('skin_wolf1',))
        self.assertEqual(selected.npc_warped_form_policies, ())
        self.assertEqual(replace(source, npc_warped_form_policies=(policy(source),)).npc_blood_rage_actor_ids, ())
        both = replace(selected, npc_warped_form_policies=(policy(source),))
        self.assertEqual(both.npc_blood_rage_actor_ids, ('skin_wolf1',))
