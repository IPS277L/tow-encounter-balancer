"""Printed Gor/Warhound/Orc modifiers retain actual conditions and source receipts."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageModifier
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_result_models import (PcAttackProof,PcMeleeStep,PcMeleeOutcome,
    initial_pc_melee_state,build_pc_melee_attack)
from towr.domain.pc_npc_ability_models import (GOR_PRIMAL_RAGE_RULE_ID,GOR_DUAL_AXES_RULE_ID,
    pc_npc_attack_modifiers,pc_npc_damage_modifiers,pc_npc_allows_give_ground)
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn


class ForeignRule(str,Enum):
    DUAL = 'RULE-PROFILE-BEASTMEN-002:dual-axes-damage'


def scene(**kwargs):
    return book_pc_scenario(footpads=0,townsfolk=0,pc_count=1,**kwargs)


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def gor_rage_result():
    return execute(scene(gors=1,max_rounds=2),[10]*3+[1]*4+[10]*4+[1]*3
        +[10]*3+[1]*4+[10]*5+[1]*3)


def npc_attacks(result,actor):
    return tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof)
        and step.proof.request.actor_id==actor)


def pure_active(source,actor):
    """Authored request-preparation boundary, not a native encounter prefix."""
    state = initial_pc_melee_state(source)
    clock = state.round_state
    if actor not in source.pc_activation_order:
        clock = replace(clock,completed_turn_entity_ids=source.pc_activation_order)
    clock = start_combat_turn(CombatTurnStartRequest('pure:start',clock,actor)).state
    return replace(state,round_state=clock)


class BeastOrcModifierTests(unittest.TestCase):
    def test_native_gor_miss_adds_stagger_then_next_actual_attack_gets_one_rage_die(self):
        result = gor_rage_result()
        first,second = npc_attacks(result,'gor1')
        self.assertEqual(first.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertTrue(second.source.enemy('gor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1),))
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,5)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_native_gor_damage_keeps_printed_base_plus_one_dual_modifier_against_any_armour(self):
        for armour in (0,3):
            with self.subTest(armour=armour):
                source = scene(gors=1,max_rounds=1)
                member = source.party[0]
                source = replace(source,party=(replace(member,pc=replace(member.pc,armour_bonus=armour)),))
                result = execute(source,[10]*3+[1]*4+[1,1,1,10]+[10]*3+[1])
                attack, = npc_attacks(result,'gor1')
                raw = attack.proof.execution.resolution.attack
                self.assertEqual((raw.impact_spec.damage.base,raw.success_margin,raw.damage),(3,3,7))
                self.assertEqual(raw.impact_spec.damage_modifiers,(DamageModifier(GOR_DUAL_AXES_RULE_ID,1),))
                self.assertEqual(raw.applied_rule_ids,(GOR_DUAL_AXES_RULE_ID,))
                self.assertEqual(raw.effective_resilience,3+armour)
                self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_native_gor_wound_defeat_clears_stagger_and_later_actor_has_no_stale_rage(self):
        result = execute(scene(gors=1,horses=1,max_rounds=2),[10]*3+[1]*4+[10]*5+[1]*3
            +[10]*4+[1]*3+[1]*3+[10]*4+[10]*3+[1]*3)
        gor = result.state.enemy('gor1').state.injury
        self.assertTrue(gor.defeated)
        self.assertFalse(gor.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(npc_attacks(result,'gor1')),1)
        horse = npc_attacks(result,'horse1')[-1]
        self.assertEqual(horse.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(horse.proof.request.kernel_request.attack.impact_spec.damage_modifiers,())

    def test_pure_drained_removes_outnumber_higher_ground_and_rage_but_keeps_dual_damage(self):
        state = pure_active(scene(gors=1,horses=1),'gor1')
        enemy = state.enemy('gor1')
        target = state.party[0]
        state = replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.STAGGERED}))))),state.enemies[1]),
            party=(replace(target,injury=replace(target.injury,conditions=ConditionState(frozenset({Condition.PRONE})))),))
        prepared = build_pc_melee_attack(state)[0].kernel_request.attack
        self.assertEqual(prepared.attacker_test.dice_modifiers,(DiceModifier('RULE-COMBAT-007:outnumbering',1),
            DiceModifier('RULE-COMBAT-007:higher-ground',1),DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1)))
        rng = ScriptedD10([1]*8)
        capped = replace(prepared.attacker_test,dice_modifiers=(*prepared.attacker_test.dice_modifiers,
            DiceModifier('authored:cap-check',9)))
        self.assertEqual(resolve_test(capped,rng).trace.rolled_dice,8)
        rng.assert_exhausted()
        enemy = state.enemy('gor1')
        drained = replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.STAGGERED,Condition.DRAINED}))))),state.enemies[1]))
        attack = build_pc_melee_attack(drained)[0].kernel_request.attack
        self.assertEqual(attack.attacker_test.dice_modifiers,())
        self.assertEqual(attack.impact_spec.damage_modifiers,(DamageModifier(GOR_DUAL_AXES_RULE_ID,1),))

    def test_pure_warhound_and_wolf_forbid_give_ground_only_as_actual_npc_attacker(self):
        for kwargs,actor in (({'warhounds':1},'warhound1'),({'wolves':1},'wolf1')):
            source = scene(**kwargs)
            source = replace(source,facts=replace(source.facts,can_leave_zone=True))
            incoming = build_pc_melee_attack(pure_active(source,actor))[0].kernel_request
            self.assertFalse(incoming.can_target_leave_zone)
            outgoing = build_pc_melee_attack(pure_active(source,'pc1'))[0].kernel_request
            self.assertTrue(outgoing.can_target_leave_zone)
            if actor=='warhound1':
                self.assertEqual((incoming.attack.attacker_test.profile.dice,incoming.attack.attacker_test.profile.threshold),(3,3))
        for profile in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GOR_DUAL_AXES,PcBookNpcProfile.ORC_BOY_CHOPPAS):
            self.assertTrue(pc_npc_allows_give_ground(get_pc_book_npc_entry(profile).definition))

    def test_native_orc_uses_combined_printed_damage_four_without_dual_or_charge_extras(self):
        source = scene(orcs=1,max_rounds=1)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,armour_bonus=3)),))
        result = execute(source,[10]*3+[1]*3+[1]*3+[10]*3+[1])
        attack, = npc_attacks(result,'orc1')
        raw = attack.proof.execution.resolution.attack
        self.assertEqual((raw.attacker_test.trace.rolled_dice,raw.attacker_test.trace.threshold),(3,4))
        self.assertEqual((raw.impact_spec.damage.base,raw.damage),(4,7))
        self.assertEqual(raw.impact_spec.damage_modifiers,())
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_helpers_require_canonical_gor_and_do_not_infer_traits_from_authored_weapon_names(self):
        gor = get_pc_book_npc_entry(PcBookNpcProfile.GOR_DUAL_AXES).definition
        self.assertEqual(pc_npc_attack_modifiers(gor,ConditionState(),target_conditions=ConditionState(),attacker_wounds=0),())
        self.assertEqual(pc_npc_attack_modifiers(gor,ConditionState(frozenset({Condition.STAGGERED})),
            target_conditions=ConditionState(),attacker_wounds=0),
            (DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1),))
        with self.assertRaises(ValueError):
            pc_npc_damage_modifiers(replace(gor,source_rule_id='authored:fake-gor'))
        numeric = make_pc_melee_scenario().enemies[0].definition
        numeric = replace(numeric,attacks=(replace(numeric.attacks[0],id='crude_axes'),))
        self.assertEqual(pc_npc_damage_modifiers(numeric),())
        self.assertEqual(pc_npc_attack_modifiers(numeric,ConditionState(frozenset({Condition.STAGGERED})),
            target_conditions=ConditionState(),attacker_wounds=0),())

    def test_actual_modifier_receipts_reject_aliases_duplicates_or_replayed_source(self):
        result = gor_rage_result()
        first,second = npc_attacks(result,'gor1')
        self.assertEqual(apply_pc_melee_step(second.source,second),second.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(second.state,second)
        for name,value in (('amount',True),('rule_id',ForeignRule.DUAL)):
            proof = deepcopy(first.proof)
            modifier = proof.request.kernel_request.attack.impact_spec.damage_modifiers[0]
            object.__setattr__(modifier,name,value)
            with self.subTest(name=name),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(first.source,proof)
        proof = deepcopy(second.proof)
        test = proof.request.kernel_request.attack.attacker_test
        object.__setattr__(test,'dice_modifiers',(*test.dice_modifiers,*test.dice_modifiers))
        with self.assertRaises(ValueError):
            PcMeleeStep(second.source,proof)
        proof = deepcopy(second.proof)
        object.__setattr__(proof.request.kernel_request.attack.attacker_test.dice_modifiers[0],'amount',True)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(second.source,proof)


if __name__ == '__main__':
    unittest.main()
