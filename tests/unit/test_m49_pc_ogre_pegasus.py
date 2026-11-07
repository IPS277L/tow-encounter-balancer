"""Printed Ogre cap and a genuinely grounded Pegasus in the existing owner."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.attack_models import DamageProfile, ResilienceProfile, ImpactOutcome
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeWeapon, validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcProfileWoundProof, PcTurnEndProof,
    build_pc_melee_attack,
)
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry, validate_pc_book_npc_definition,
)
from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof, PcWarpedFormTargetProof
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, InlineProfile, Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.test_resolution import resolve_test


OGRE = PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER
PEGASUS = PcBookNpcProfile.PEGASUS_GROUNDED


def scene(*, pegasus=False, rounds=1, **counts):
    return book_pc_scenario(ogres=0 if pegasus else 1, pegasi=1 if pegasus else 0,
        footpads=counts.pop('footpads', 0), townsfolk=0, pc_count=1, max_rounds=rounds, **counts)


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def proofs(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def axe(source):
    return replace(source, party=tuple(replace(m, pc=replace(m.pc, weapon=PcMeleeWeapon.AXE))
        for m in source.party))


class PcOgrePegasusCatalogTests(unittest.TestCase):
    def test_ogre_full_printed_profile_keeps_modified_base_and_characteristic_cap_separate(self):
        entry = get_pc_book_npc_entry(OGRE)
        definition = entry.definition
        source = 'BOOK-GM-GUIDE:1.1:p103:imperial_ogre_greathammer'
        self.assertEqual((entry.book_id, entry.version, entry.chapter, entry.page),
            ('BOOK-GM-GUIDE', '1.1', 'Allies and Antagonists', 103))
        self.assertEqual((definition.id, definition.source_rule_id, definition.injury_policy,
            definition.wound_limit, definition.resilience),
            ('pc-book-npc:imperial_ogre_greathammer', source, TargetInjuryPolicy.BRUTE, 3,
             ResilienceProfile(5, 1)))
        attack, = definition.attacks
        self.assertEqual((attack.id, attack.source_rule_id, attack.skill, attack.test_profile,
            attack.damage, attack.range_min, attack.range_max, attack.hands,
            attack.ignores_armour, attack.secondary_effects),
            ('greathammer', source+':greathammer', Skill.MELEE, InlineProfile(2, 4, 6),
             DamageProfile(8), RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE,
             RangedWeaponHands.TWO_HANDED, False, ()))
        protection, = definition.protection
        self.assertEqual((protection.source_rule_id, protection.skill, protection.test_profile),
            (source+':athletics', Skill.ATHLETICS, InlineProfile(3, 3)))
        self.assertEqual((attack.test_profile.base_dice, attack.test_profile.maximum_dice), (2, 6))

    def test_grounded_pegasus_is_natural_unarmoured_brute_with_its_own_protection(self):
        entry = get_pc_book_npc_entry(PEGASUS)
        definition = entry.definition
        source = 'BOOK-GM-GUIDE:1.1:p176:pegasus_grounded'
        self.assertEqual((entry.book_id, entry.version, entry.page), ('BOOK-GM-GUIDE', '1.1', 176))
        self.assertEqual((definition.id, definition.source_rule_id, definition.injury_policy,
            definition.wound_limit, definition.resilience),
            ('pc-book-npc:pegasus_grounded', source, TargetInjuryPolicy.BRUTE, 2, ResilienceProfile(3)))
        attack, = definition.attacks
        self.assertEqual((attack.id, attack.source_rule_id, attack.skill, attack.test_profile,
            attack.damage, attack.range_min, attack.range_max, attack.hands, attack.secondary_effects),
            ('hooves', source+':hooves', Skill.MELEE, InlineProfile(3, 3), DamageProfile(3),
             RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None, ()))
        protection, = definition.protection
        self.assertEqual((protection.skill, protection.test_profile), (Skill.ATHLETICS, InlineProfile(4, 4)))
        self.assertEqual((attack.test_profile.maximum_dice, protection.test_profile.maximum_dice), (6, 8))
        self.assertIn('ground', entry.name.lower())

    def test_snapshot_facts_and_nested_graphs_are_fresh_without_shields(self):
        for profile, armed, attack_id, limit in ((OGRE, True, 'greathammer', 3),
                (PEGASUS, False, 'hooves', 2)):
            first = create_pc_book_npc(profile, 'first')
            second = create_pc_book_npc(profile, 'second')
            self.assertEqual((first.state.wields_weapon, first.state.holds_shield,
                first.state.available_attack_ids, first.state.injury.wounds,
                first.state.injury.wound_limit, first.state.injury.defeated),
                (armed, False, (attack_id,), 0, limit, False))
            self.assertIsNot(first.definition, second.definition)
            self.assertIsNot(first.definition.attacks[0].test_profile, second.definition.attacks[0].test_profile)
            self.assertIsNot(first.state.injury, second.state.injury)
            object.__setattr__(first.definition.attacks[0].damage, 'base', 99)
            self.assertEqual(second.definition, get_pc_book_npc_entry(profile).definition)

    def test_ogre_keeps_complete_unselected_attack_triggers_and_speed_bands(self):
        entry = get_pc_book_npc_entry(OGRE)
        self.assertEqual(entry.unselected_attack_names, ('Rough Shove', 'Ogre Pistol'))
        abilities = {a.name:a for a in entry.inactive_abilities}
        self.assertEqual(set(abilities), {'Ogre Charge', 'Fearsome', 'Mighty Throw'})
        self.assertIn('Rough Shove', abilities['Ogre Charge'].scope)
        self.assertIn('Charge', abilities['Ogre Charge'].scope)
        self.assertIn('Staggered', abilities['Mighty Throw'].scope)
        self.assertIn('Long', abilities['Mighty Throw'].effect)
        self.assertIn('Prone', abilities['Mighty Throw'].effect)
        self.assertIn('Give', abilities['Fearsome'].scope)
        self.assertFalse(entry.active_abilities)
        self.assertEqual(tuple(b.wounds for b in entry.wound_bands), (0, 1, 2, 3))
        self.assertIn('Normal', entry.wound_bands[1].effect)
        self.assertIn('Normal', entry.wound_bands[2].effect)
        self.assertEqual(entry.wound_bands[-1].effect, 'Defeated')

    def test_pegasus_preserves_fly_and_rider_conditions_without_claiming_airborne_support(self):
        entry = get_pc_book_npc_entry(PEGASUS)
        abilities = {a.name:a for a in entry.inactive_abilities}
        self.assertEqual(set(abilities), {'Fly', 'Pegasus Knights'})
        self.assertIn('vertical', abilities['Fly'].scope.lower())
        self.assertIn('Close', abilities['Fly'].effect)
        self.assertIn('ground', abilities['Fly'].effect.lower())
        self.assertIn('mounted', abilities['Pegasus Knights'].scope.lower())
        self.assertEqual(tuple(b.wounds for b in entry.wound_bands), (0, 1, 2))
        self.assertIn('fly', entry.wound_bands[1].effect.lower())
        self.assertIn('ground', entry.wound_bands[1].effect.lower())
        self.assertFalse(entry.active_abilities)

    def test_wrong_caps_or_second_weapon_penalty_cannot_claim_ogre(self):
        definition = get_pc_book_npc_entry(OGRE).definition
        attack, = definition.attacks
        for profile in (InlineProfile(2, 4), InlineProfile(2, 4, 4), InlineProfile(2, 4, 8),
                InlineProfile(1, 4, 6), InlineProfile(3, 4, 6)):
            with self.subTest(profile=profile), self.assertRaises((TypeError, ValueError)):
                validate_pc_book_npc_definition(replace(definition,
                    attacks=(replace(attack, test_profile=profile),)))
        protection, = definition.protection
        with self.assertRaises((TypeError, ValueError)):
            validate_pc_book_npc_definition(replace(definition,
                protection=(replace(protection, test_profile=InlineProfile(3, 3, 6)),)))

    def test_other_book_and_authored_sources_cannot_borrow_explicit_six(self):
        sources = (scene(pegasus=True), book_pc_scenario(footpads=1, townsfolk=0, pc_count=1),
            make_pc_melee_scenario())
        for source in sources:
            enemy = source.enemies[0]
            attack, = enemy.definition.attacks
            definition = replace(enemy.definition, attacks=(replace(attack,
                test_profile=replace(attack.test_profile, pool_cap=6)),))
            with self.subTest(definition=definition.id), self.assertRaises((TypeError, ValueError)):
                replace(source, enemies=(replace(enemy, definition=definition),))

    def test_partial_ground_or_book_identity_renames_do_not_create_an_authored_shortcut(self):
        for profile in (OGRE, PEGASUS):
            definition = get_pc_book_npc_entry(profile).definition
            for changed in (replace(definition, id='authored:root'),
                    replace(definition, source_rule_id='authored:source'),
                    replace(definition, id=definition.id.replace('_grounded', ''),
                        source_rule_id=definition.source_rule_id.replace('_grounded', ''))
                        if profile is PEGASUS else replace(definition, wound_limit=2)):
                with self.subTest(profile=profile, changed=changed), self.assertRaises((TypeError, ValueError)):
                    validate_pc_book_npc_definition(changed)

    def test_cached_equal_scalar_and_enum_aliases_are_rejected_before_execution(self):
        for profile, field, value in ((OGRE, 'pool_cap', 6.0), (PEGASUS, 'dice', 3.0)):
            definition = deepcopy(get_pc_book_npc_entry(profile).definition)
            object.__setattr__(definition.attacks[0].test_profile, field, value)
            self.assertEqual(definition, get_pc_book_npc_entry(profile).definition)
            with self.assertRaises(TypeError):
                validate_pc_book_npc_definition(definition)
        source = deepcopy(scene())
        object.__setattr__(source.enemies[0].definition.attacks[0], 'hands', '2h')
        with self.assertRaises(TypeError):
            validate_pc_melee_scenario_admission(source)


class PcOgrePegasusExecutionTests(unittest.TestCase):
    def test_prepared_ogre_uses_two_dice_cap6_and_neither_rage_devour_nor_pc_traits(self):
        request, _ = build_pc_melee_attack(pure_active(scene(), 'ogre1'))
        attack = request.kernel_request.attack
        self.assertEqual(attack.attacker_test.profile, InlineProfile(2, 4, 6))
        self.assertEqual(attack.attacker_test.dice_modifiers, ())
        self.assertEqual(attack.impact_spec.damage, DamageProfile(8))
        self.assertEqual(attack.impact_spec.damage_modifiers, ())
        self.assertEqual(request.kernel_request.wound_dice_modifiers, ())

    def test_regular_bonus_caps_at_six_then_explicit_help_bypass_adds_after_cap(self):
        request, _ = build_pc_melee_attack(pure_active(scene(), 'ogre1'))
        test = replace(request.kernel_request.attack.attacker_test,
            dice_modifiers=(DiceModifier('authored:ordinary', 20), DiceModifier('authored:help', 2, True)))
        rng = ScriptedD10([1]*8)
        trace = resolve_test(test, rng).trace
        rng.assert_exhausted()
        self.assertEqual((trace.base_dice, trace.pool_cap, trace.cap_bypassing_dice, trace.rolled_dice),
            (2, 6, 2, 8))

    def test_drained_suppresses_positive_test_modifiers_without_changing_printed_cap_or_damage(self):
        state = pure_active(scene(footpads=1), 'ogre1')
        enemy = state.enemy('ogre1')
        changed = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.DRAINED, Condition.STAGGERED})), wounds=1)))
        state = replace(state, enemies=tuple(changed if e.state.actor_id=='ogre1' else e for e in state.enemies))
        request, _ = build_pc_melee_attack(state)
        test = request.kernel_request.attack.attacker_test
        self.assertEqual(test.profile, InlineProfile(2, 4, 6))
        self.assertFalse(test.dice_modifiers)
        self.assertEqual(request.kernel_request.attack.impact_spec.damage_modifiers, ())

    def test_real_direct_wounds_reach_each_limit_and_apply_only_the_actual_gm_disposition(self):
        for pegasus, defence, incoming, limit, actor in ((False, 3, 2, 3, 'ogre1'),
                (True, 4, 3, 2, 'pegasus1')):
            source = axe(scene(pegasus=pegasus, rounds=limit))
            pc_hit = [1]*3+[10]*defence
            npc_miss = [10]*incoming+[1]*3
            result = execute(source, (pc_hit+npc_miss)*(limit-1)+pc_hit)
            changes = proofs(result, PcProfileWoundProof)
            self.assertEqual(tuple(p.proof.source.current_wounds for p in changes), tuple(range(1, limit+1)))
            self.assertTrue(all(p.proof.decision is None for p in changes[:-1]))
            self.assertEqual(changes[-1].proof.decision, source.party[0].defeat_decision(actor))
            self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
            self.assertEqual(result.executed_actions, 2*limit-1)
            self.assertFalse(any(p.state.enemy(actor).state.injury.conditions.has(Condition.DRAINED)
                for p in changes))

    def test_repeated_stagger_wounds_each_brute_without_pc_wounds_table_rolls(self):
        for pegasus, defence, incoming, limit, actor in ((False, 3, 2, 3, 'ogre1'),
                (True, 4, 3, 2, 'pegasus1')):
            source = scene(pegasus=pegasus, rounds=limit+1)
            source = replace(source, party=tuple(replace(m, pc=replace(m.pc, strength=1)) for m in source.party))
            weak_hit = [1, 10, 10]+[1]+[10]*(defence-1)
            npc_miss = [10]*incoming+[1]*3
            result = execute(source, (weak_hit+npc_miss)*limit+weak_hit)
            attacks = tuple(p for p in proofs(result, PcAttackProof) if p.proof.request.actor_id=='pc1')
            self.assertTrue(all(p.proof.execution.resolution.attack.impact is ImpactOutcome.STAGGERED for p in attacks))
            self.assertIsNone(attacks[0].proof.execution.resolution.profile_wound)
            self.assertEqual(tuple(p.proof.source.current_wounds for p in proofs(result, PcProfileWoundProof)),
                tuple(range(1, limit+1)))
            self.assertFalse(result.state.party[0].injury.wounds)
            self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_grounded_pegasus_first_wound_continues_ordinary_turn_without_landing_action(self):
        result = execute(axe(scene(pegasus=True)), [1]*3+[10]*4+[10]*3+[1]*3)
        ack, = proofs(result, PcProfileWoundProof)
        incoming = next(p for p in proofs(result, PcAttackProof) if p.proof.request.actor_id=='pegasus1')
        self.assertEqual(incoming.source.enemy('pegasus1').state.injury.wounds, 1)
        self.assertFalse(ack.state.enemy('pegasus1').state.injury.conditions.conditions)
        self.assertEqual(incoming.proof.request.kernel_request.attack.attacker_test.profile, InlineProfile(3, 3))
        self.assertFalse(incoming.source.enemy('pegasus1').state.wields_weapon)
        self.assertEqual(result.executed_actions, 2)
        self.assertIs(type(result.steps[-1].proof), PcTurnEndProof)
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)

    def test_warped_form_w1_uses_each_actual_npc_target_source_and_does_not_invent_landing(self):
        for pegasus, actor, npc_dice in ((False, 'ogre1', 3), (True, 'pegasus1', 4)):
            source = axe(scene(pegasus=pegasus, skin_wolves=1))
            targets = ('skin_wolf1', actor)
            source = replace(source, enemy_activation_order=(actor, 'skin_wolf1'),
                party=tuple(replace(m, target_priority=targets,
                    defeat_decisions=tuple(m.defeat_decision(target) for target in targets)) for m in source.party),
                npc_warped_form_policies=(PcWarpedFormPolicy('skin_wolf1', ('pc1', actor),
                    (MinionDefeatDecision('skin_wolf1', actor, NpcDefeatDisposition.KILLED, True),)),))
            values = [1]*3+[10]*4+[10]*npc_dice+[1]*3+[1]*6+[10]*3+[1]
            result = execute(source, values)
            ack, = proofs(result, PcWarpedFormProfileProof)
            self.assertEqual((ack.proof.target_id, ack.proof.source.previous_wounds,
                ack.proof.source.current_wounds, ack.proof.decision), (actor, 0, 1, None))
            wave = tuple(p.proof.request.target_id for p in proofs(result, PcWarpedFormTargetProof))
            self.assertEqual(wave, ('pc1', actor))
            self.assertEqual(result.state.enemy(actor).state.injury.wounds, 1)
            self.assertEqual(result.executed_actions, 3)
            self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)

    def test_ogre_native_receipt_cannot_replace_explicit_cap_with_equal_float_or_implicit_value(self):
        result = execute(axe(scene()), [1]*3+[10]*3+[10]*2+[1]*3)
        incoming = next(p for p in proofs(result, PcAttackProof) if p.proof.request.actor_id=='ogre1')
        for cap in (None, 4, 8, 6.0):
            proof = deepcopy(incoming.proof)
            object.__setattr__(proof.request.kernel_request.attack.attacker_test.profile, 'pool_cap', cap)
            with self.subTest(cap=cap), self.assertRaises((TypeError, ValueError)):
                PcMeleeStep(incoming.source, proof)


if __name__ == '__main__':
    unittest.main()
