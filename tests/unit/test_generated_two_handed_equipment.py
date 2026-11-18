"""Fixed two-handed components use real source, hands and shared weapon traits."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from towr.domain.armour_models import BodyArmour, ShieldKind
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.attack_models import DamageModifier
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import (
    GeneratedNpc, GeneratedWeapon, GENERATED_TWO_HANDED_RANGED_WEAPONS,
    generated_weapon_allows_shield, validate_generated_definition,
)
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof, build_pc_melee_attack
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.test_resolution import resolve_test


# Literal PG93 Damage expectations at Strength1 and Strength4, independent of
# the shared production helper that both PC and generated NPC builders invoke.
TWO_HANDED_DAMAGE = (
    (GeneratedWeapon.PICKAXE, 2, 5),
    (GeneratedWeapon.FLAIL, 4, 7),
    (GeneratedWeapon.BILLHOOK, 3, 6),
    (GeneratedWeapon.HALBERD, 3, 6),
    (GeneratedWeapon.GLAIVE, 3, 6),
    (GeneratedWeapon.GREATAXE, 4, 7),
    (GeneratedWeapon.GREATHAMMER, 4, 7),
    (GeneratedWeapon.GREATSWORD, 4, 7),
)


def component(weapon, **changes):
    facts = dict(weapon_skill=3, strength=4, toughness=3, agility=2,
        melee=4, defence=6, athletics=2, weapon=weapon, light_armour=False,
        shield=False)
    facts.update(changes)
    facts['armour'] = light_loadout(light=facts.pop('light_armour'), shield=facts.pop('shield'))
    facts['weapons'] = initial_generated_weapons(facts.pop('weapon'), facts.pop('weapon_grip', None))
    return GeneratedNpc(**facts)


def component_space(**changes):
    facts = dict(weapon_skill=(3,), strength=(4,), toughness=(3,), agility=(2,),
        melee=(4,), defence=(6,), athletics=(2,), weapon=(GeneratedWeapon.GLAIVE,),
        armour=(None,), shield=(None,), abilities=((),), allowed_talents=())
    facts.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **facts)


class FirstChoice:
    def __init__(self):
        self.choices = []

    def choice(self, values):
        self.choices.append(tuple(values))
        return values[0]


class PreferShield(FirstChoice):
    def choice(self,values):
        self.choices.append(tuple(values))
        return ShieldKind.SHIELD if ShieldKind.SHIELD in values else values[0]


class NeverChoose:
    def choice(self, values):
        raise AssertionError('an invalid source must fail before proposal RNG')


class AllMisses:
    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('only an ordinary d10 is required')
        return 10


def battle_source(weapon):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=1)
    member = source.party[0]
    member = replace(member, policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        pc=replace(member.pc, weapon_skill=1, melee=1, defence=1, agility=1,
            athletics=1, strength=1, toughness=20))
    enemy = component(weapon, weapon_skill=1, agility=1, defence=2,
        toughness=20).participant('minion1')
    return replace(source, party=(member,), enemies=(enemy,))


def enemy_attack_state(weapon):
    # Use an actual native prefix to obtain the reserved NPC Attack slot. The
    # pure preparation checks below do not invent a completed combat journal.
    result = run_pc_melee_scenario(battle_source(weapon), AllMisses())
    return next(step.source for step in result.steps
        if type(step.proof) is PcAttackProof and step.proof.request.actor_id == 'minion1')


def with_enemy_conditions(state, *conditions):
    enemy = state.enemy('minion1')
    injury = replace(enemy.state.injury,
        conditions=ConditionState(frozenset(conditions)))
    return replace(state, enemies=(replace(enemy, state=replace(enemy.state, injury=injury)),))


class GeneratedTwoHandedSourceTests(unittest.TestCase):
    def test_each_weapon_derives_damage_both_hands_and_characteristic_cap(self):
        for weapon, low_damage, ordinary_damage in TWO_HANDED_DAMAGE:
            for strength, damage in ((1, low_damage), (4, ordinary_damage)):
                for ws in (1, 4, 7):
                    with self.subTest(weapon=weapon, strength=strength, ws=ws):
                        npc = component(weapon, strength=strength, weapon_skill=ws,
                            light_armour=True)
                        enemy = npc.participant('unlisted-actor')
                        attack = enemy.definition.attacks[0]
                        self.assertEqual(enemy.definition.generated_components, npc)
                        self.assertEqual(attack.damage.base, damage)
                        self.assertIs(attack.hands, RangedWeaponHands.TWO_HANDED)
                        self.assertIs(attack.skill, Skill.MELEE)
                        self.assertEqual(attack.test_profile.maximum_dice, ws*2)
                        self.assertIsNone(attack.test_profile.pool_cap)
                        self.assertEqual(enemy.state.current_resilience.total, 4)
                        self.assertFalse(enemy.state.holds_shield)
                        self.assertTrue(enemy.state.wields_weapon)
                        validate_generated_definition(enemy.definition)

    def test_shield_compatibility_is_typed_and_keeps_reload_hand_restriction(self):
        for weapon in (GeneratedWeapon.STAFF, GeneratedWeapon.DAGGER,
                GeneratedWeapon.AXE, GeneratedWeapon.SWORD,
                GeneratedWeapon.WARHAMMER, GeneratedWeapon.MORNING_STAR):
            self.assertTrue(generated_weapon_allows_shield(weapon))
        for weapon in (*tuple(row[0] for row in TWO_HANDED_DAMAGE), *GENERATED_TWO_HANDED_RANGED_WEAPONS):
            self.assertFalse(generated_weapon_allows_shield(weapon))
        for malformed in ('glaive', PcMeleeWeapon.GLAIVE, None, True):
            with self.subTest(malformed=malformed), self.assertRaises(TypeError):
                generated_weapon_allows_shield(malformed)
        for weapon, _, _ in TWO_HANDED_DAMAGE:
            with self.subTest(weapon=weapon), self.assertRaises(ValueError):
                component(weapon, shield=True)

    def test_unreachable_weapon_or_shield_choices_fail_before_sampling(self):
        for weapons, shields in (
            ((GeneratedWeapon.GLAIVE,), (ShieldKind.SHIELD,)),
            ((GeneratedWeapon.FLAIL,), (None, ShieldKind.SHIELD)),
            ((GeneratedWeapon.GREATAXE, GeneratedWeapon.SWORD), (ShieldKind.SHIELD,)),
        ):
            with self.subTest(weapons=weapons, shields=shields), self.assertRaises(ValueError):
                component_space(weapon=weapons, shield=shields)

    def test_sampling_selects_admissible_shield_branch_without_discarding_it(self):
        for weapon, _, _ in TWO_HANDED_DAMAGE:
            space = component_space(weapon=(weapon, GeneratedWeapon.SWORD),
                shield=(None,ShieldKind.SHIELD))
            rng = FirstChoice()
            npc = space.sample(rng)
            with self.subTest(weapon=weapon):
                self.assertIs(npc.weapon, weapon)
                self.assertFalse(npc.shield)
                self.assertTrue(space.contains(npc))
                # Sampling may choose Shield first; either selected item must
                # survive admission rather than being drawn and discarded.
                shielded=space.sample(PreferShield())
                self.assertIs(shielded.armour.shield,ShieldKind.SHIELD)
                self.assertIs(shielded.weapon,GeneratedWeapon.SWORD)
                self.assertTrue(space.contains(shielded))

    def test_mutation_does_not_switch_a_shielded_actor_and_drop_its_shield(self):
        space = component_space(weapon=(GeneratedWeapon.SWORD, GeneratedWeapon.FLAIL),
            shield=(None,ShieldKind.SHIELD))
        original = component(GeneratedWeapon.SWORD, shield=True)
        proposal = space.mutate(original, FirstChoice())
        self.assertEqual(proposal, replace(original, armour=replace(original.armour, shield=None)))
        self.assertTrue(original.shield)
        self.assertIs(original.weapon, GeneratedWeapon.SWORD)
        self.assertTrue(space.contains(proposal))
        unshielded = replace(original, armour=replace(original.armour, shield=None))
        class ChooseFlail:
            def choice(self,candidates):
                return next(candidate for candidate in candidates
                    if candidate.weapon is GeneratedWeapon.FLAIL)
        proposal = space.mutate(unshielded, ChooseFlail())
        self.assertIs(proposal.weapon, GeneratedWeapon.FLAIL)
        self.assertFalse(proposal.shield)

    def test_contains_and_mutate_readmit_full_equipment_before_rng(self):
        space = component_space()
        forged = deepcopy(component(GeneratedWeapon.GLAIVE))
        object.__setattr__(forged.armour, 'shield', ShieldKind.SHIELD)
        self.assertFalse(space.contains(forged))
        with self.assertRaises(ValueError):
            space.mutate(forged, NeverChoose())

    def test_numeric_resampling_preserves_weapon_armour_and_hand_source(self):
        space = component_space(weapon=(GeneratedWeapon.GREATSWORD,),
            strength=(2, 4), weapon_skill=(2, 3), armour=(BodyArmour.LIGHT,))
        original = component(GeneratedWeapon.GREATSWORD, light_armour=True)
        frozen = deepcopy(original)
        sample = space.resample_numeric((original,), Random(19))
        selected, = sample.composition
        self.assertIs(selected.weapon, GeneratedWeapon.GREATSWORD)
        self.assertTrue((BodyArmour.LIGHT in selected.armour.body))
        self.assertFalse(selected.shield)
        self.assertEqual(original, frozen)
        self.assertTrue(space.contains(selected))
        self.assertIs(selected.participant('resampled').definition.attacks[0].hands,
            RangedWeaponHands.TWO_HANDED)

    def test_definition_readmission_rejects_forged_hands_damage_cap_and_components(self):
        for field in ('hands', 'damage', 'cap', 'components'):
            definition = deepcopy(component(GeneratedWeapon.GREATSWORD).participant('forged').definition)
            attack = definition.attacks[0]
            if field == 'hands':
                object.__setattr__(attack, 'hands', RangedWeaponHands.ONE_HANDED)
            elif field == 'damage':
                object.__setattr__(attack.damage, 'base', 40)
            elif field == 'cap':
                object.__setattr__(attack.test_profile, 'pool_cap', 8)
            else:
                object.__setattr__(definition, 'generated_components',
                    replace(definition.generated_components, weapons=initial_generated_weapons(GeneratedWeapon.GLAIVE)))
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_generated_definition(definition)


class GeneratedTwoHandedPreparationTests(unittest.TestCase):
    def test_flail_negative_modifier_survives_drained_in_the_prepared_native_test(self):
        state = with_enemy_conditions(enemy_attack_state(GeneratedWeapon.FLAIL),
            Condition.STAGGERED, Condition.DRAINED)
        request = build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        self.assertEqual(tuple((m.rule_id, m.amount) for m in request.dice_modifiers),
            (('RULE-EQUIPMENT-003:flail-staggered', -2),))
        rng = ScriptedD10([1])
        result = resolve_test(request, rng)
        rng.assert_exhausted()
        self.assertEqual((result.trace.rolled_dice, result.trace.threshold), (1, 1))

    def test_greataxe_native_preparation_keeps_penalty_and_armoured_target_damage(self):
        source = battle_source(GeneratedWeapon.GREATAXE)
        source = replace(source, party=(replace(source.party[0], armour_worn=True),))
        result = run_pc_melee_scenario(source, AllMisses())
        step = next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'minion1')
        attack = step.proof.request.kernel_request.attack
        self.assertEqual(tuple((m.rule_id, m.amount) for m in attack.attacker_test.dice_modifiers),
            (('RULE-EQUIPMENT-003:greataxe-melee', -1),))
        self.assertEqual(attack.impact_spec.damage.base, 7)
        self.assertEqual(attack.impact_spec.damage_modifiers,
            (DamageModifier('RULE-EQUIPMENT-003:greataxe-armour', 1, armour_specific=True),))

    def test_greathammer_target_bonus_and_own_penalty_stay_distinct(self):
        state = enemy_attack_state(GeneratedWeapon.GREATHAMMER)
        request = build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        self.assertEqual(tuple((m.rule_id, m.amount) for m in request.dice_modifiers),
            (('RULE-EQUIPMENT-003:greathammer-melee', -1),
             ('RULE-EQUIPMENT-003:greathammer-staggered-target', 1)))
        drained = with_enemy_conditions(state, Condition.DRAINED)
        request = build_pc_melee_attack(drained)[0].kernel_request.attack.attacker_test
        self.assertEqual(tuple((m.rule_id, m.amount) for m in request.dice_modifiers),
            (('RULE-EQUIPMENT-003:greathammer-melee', -1),))

    def test_glaive_and_greatsword_defence_bonus_depends_on_actual_conditions(self):
        for weapon, rule in ((GeneratedWeapon.GLAIVE, 'RULE-EQUIPMENT-003:glaive-defence'),
                (GeneratedWeapon.GREATSWORD, 'RULE-EQUIPMENT-003:greatsword-defence')):
            source = battle_source(weapon)
            source = replace(source, enemies=(component(weapon, weapon_skill=1,
                agility=1, defence=6, athletics=2, toughness=20).participant('minion1'),))
            state = tactical_snapshot(source)
            profile, request = npc_protection_test(state, 'minion1', 'pc1', 'defence:healthy')
            with self.subTest(weapon=weapon):
                self.assertIs(profile.skill, Skill.DEFENCE)
                self.assertEqual(tuple((m.rule_id, m.amount) for m in request.dice_modifiers),
                    ((rule, 1),))
                for condition in (Condition.STAGGERED, Condition.DRAINED):
                    _, request = npc_protection_test(with_enemy_conditions(state, condition),
                        'minion1', 'pc1', 'defence:penalized')
                    self.assertEqual(request.dice_modifiers, ())

    def test_greatsword_native_attack_has_its_melee_penalty_without_defence_bonus(self):
        state = enemy_attack_state(GeneratedWeapon.GREATSWORD)
        attack = build_pc_melee_attack(state)[0].kernel_request.attack
        self.assertEqual(tuple((m.rule_id, m.amount) for m in attack.attacker_test.dice_modifiers),
            (('RULE-EQUIPMENT-003:greatsword-melee', -1),))
        self.assertEqual(attack.impact_spec.damage.base, 7)


if __name__ == '__main__':
    unittest.main()
