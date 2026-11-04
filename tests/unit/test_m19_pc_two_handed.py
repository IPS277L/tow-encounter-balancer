"""Literal native two-handed encounters, injuries and completed unsupported boundaries."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario, make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10, first_wound_script
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.attack_models import ImpactOutcome, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import PcBodyFactKind, usable_weapon_hand
from towr.domain.pc_melee_models import (PcMeleeWeapon, PcWeaponHand, PcTwoHandedGrip,
    PcFatePolicy, PcNearMissPolicy, PcGloriousPolicy, PcMeleePolicy, PcHelpPolicy, PcHelpTarget)
from towr.domain.pc_melee_result_models import (PcAttackProof, PcHandDropProof, PcRecoverProof,
    PcBodyConsequenceProof, PcMeleeOutcome,
    PcMeleeUnsupported, PcTurnEndProof, PcHelpProof, initial_pc_melee_state)
from towr.domain.test_models import DiceModifier, Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


TWO_HANDED = (PcMeleeWeapon.PICKAXE,PcMeleeWeapon.FLAIL,PcMeleeWeapon.BILLHOOK,
    PcMeleeWeapon.HALBERD,PcMeleeWeapon.GLAIVE,PcMeleeWeapon.GREATAXE,PcMeleeWeapon.GREATHAMMER)


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def two_handed_source(*, enemies=1, rounds=1, weapon=PcMeleeWeapon.PICKAXE):
    return make_pc_melee_scenario(weapon=weapon,enemy_count=enemies,max_rounds=rounds)


class PcTwoHandedNativeTests(unittest.TestCase):
    def test_all_seven_native_attacks_use_both_hands_and_exact_damage(self):
        cases = ((PcMeleeWeapon.PICKAXE,4,3),(PcMeleeWeapon.FLAIL,6,3),
            (PcMeleeWeapon.BILLHOOK,5,3),(PcMeleeWeapon.HALBERD,5,3),
            (PcMeleeWeapon.GLAIVE,5,3),(PcMeleeWeapon.GREATAXE,6,2),(PcMeleeWeapon.GREATHAMMER,6,2))
        for weapon,base,dice in cases:
            with self.subTest(weapon=weapon):
                result = execute(two_handed_source(weapon=weapon),[1]*dice+[10,10])
                attack = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof))
                self.assertEqual((attack.execution.resolution.attack.impact_spec.damage.base,
                    attack.execution.resolution.attack.damage),(base,base+dice))
                self.assertIs(result.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_halberd_and_greataxe_native_armour_trait_crosses_damage_boundary(self):
        for weapon,base,dice,rule in ((PcMeleeWeapon.HALBERD,5,3,'halberd-armour'),
                (PcMeleeWeapon.GREATAXE,6,2,'greataxe-armour')):
            with self.subTest(weapon=weapon):
                source = two_handed_source(weapon=weapon)
                enemy = source.enemies[0]
                resilience = ResilienceProfile(3,base-2)
                source = replace(source,enemies=(replace(enemy,
                    definition=replace(enemy.definition,resilience=resilience),
                    state=replace(enemy.state,current_resilience=resilience)),))
                result = execute(source,[1]+[10]*(dice-1)+[10,10])
                attack = next(step.proof.execution.resolution.attack for step in result.steps if isinstance(step.proof,PcAttackProof))
                self.assertEqual((attack.damage,attack.effective_resilience),(base+2,base+1))
                self.assertIs(attack.impact,ImpactOutcome.WOUND)
                self.assertEqual(attack.applied_rule_ids,('RULE-EQUIPMENT-003:'+rule,))

    def test_native_flail_staggered_attack_loses_two_dice(self):
        result = execute(two_handed_source(weapon=PcMeleeWeapon.FLAIL,rounds=2),
            [10]*3+[1]*2+[10]*2+[1]*3+[1]+[10]*2)
        second = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc')[1]
        self.assertEqual(second.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-EQUIPMENT-003:flail-staggered',-2),))
        self.assertEqual((second.execution.resolution.attack.attacker_test.trace.rolled_dice,
            second.execution.resolution.attack.attacker_test.trace.threshold),(1,5))

    def test_native_greathammer_keeps_actor_penalty_and_enemy_bonus_as_separate_sources(self):
        source = two_handed_source(weapon=PcMeleeWeapon.GREATHAMMER,rounds=2)
        source = replace(source,party=(replace(source.party[0],pc=replace(source.party[0].pc,strength=1)),))
        enemy = source.enemies[0]
        source = replace(source,enemies=(replace(enemy,definition=replace(enemy.definition,resilience=ResilienceProfile(7)),
            state=replace(enemy.state,current_resilience=ResilienceProfile(7))),))
        result = execute(source,[1,10]+[10]*2+[10]*2+[1]*3+[1]*3+[10]*2)
        first,second = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc')
        self.assertEqual(first.execution.resolution.attack.attacker_test.trace.rolled_dice,2)
        self.assertEqual(second.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(second.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-EQUIPMENT-003:greathammer-staggered-target',1),
             DiceModifier('RULE-EQUIPMENT-003:greathammer-melee',-1)))

    def test_native_glaive_not_staggered_defence_receives_one_die(self):
        source = two_handed_source(weapon=PcMeleeWeapon.GLAIVE)
        source = replace(source,party=(replace(source.party[0],pc=replace(source.party[0].pc,strength=1)),))
        enemy = source.enemies[0]
        source = replace(source,enemies=(replace(enemy,definition=replace(enemy.definition,resilience=ResilienceProfile(5)),
            state=replace(enemy.state,current_resilience=ResilienceProfile(5))),))
        result = execute(source,[1,10,10]+[10]*2+[10]*2+[1]*4)
        incoming = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='minion1')
        self.assertEqual(incoming.request.kernel_request.attack.defender_test.dice_modifiers,
            (DiceModifier('RULE-EQUIPMENT-003:glaive-defence',1),))
        self.assertEqual(incoming.execution.resolution.attack.defender_test.trace.rolled_dice,4)

    def test_random_drop_from_either_hand_drops_whole_weapon_then_recovers_both(self):
        for total in (4,8):
            for side,hand in ((1,PcWeaponHand.LEFT),(10,PcWeaponHand.RIGHT)):
                with self.subTest(total=total,side=side):
                    result = execute(two_handed_source(rounds=2),
                        first_wound_script(total,hand=side)+[10,10]+[1]*3)
                    dropped, = tuple(step for step in result.steps if isinstance(step.proof,PcHandDropProof))
                    self.assertIs(dropped.proof.hand,hand)
                    self.assertIs(dropped.source.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                    self.assertIsNone(dropped.state.party[0].weapon_hand)
                    recover, = tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
                    self.assertIs(recover.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                    self.assertIs(result.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                    self.assertIsNone(result.unsupported)

    def test_smashed_hand_recovers_both_and_triggers_critical_on_injured_hand_use(self):
        for side in (1,10):
            with self.subTest(side=side):
                source = two_handed_source(enemies=3,rounds=2)
                result = execute(source,heavy_prefix(12,side=side)+[1]*3+[10,10,10,1,1,1]*3)
                recover, = tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
                self.assertIsNone(recover.source.party[0].weapon_hand)
                self.assertIs(recover.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                self.assertTrue(recover.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
                end = next(step.proof for step in result.steps if isinstance(step.proof,PcTurnEndProof)
                    and step.proof.result.completed_turn.actor_id=='pc' and step.source.round_state.round_number==2)
                self.assertIsNotNone(end.critical)
                self.assertIsNone(result.unsupported)
                protections = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
                    and step.proof.request.actor_id.startswith('minion') and step.source.round_state.round_number==2)
                self.assertEqual(len(protections),3)
                self.assertTrue(all(proof.protection.source_request.selected_skill is Skill.DEFENCE for proof in protections))
                self.assertTrue(all(proof.request.kernel_request.target_state.conditions.has(Condition.CRITICALLY_INJURED)
                    for proof in protections))

    def test_injured_both_hand_pickup_critical_test_uses_actual_glorious_fate(self):
        source = two_handed_source(enemies=3,rounds=2)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.ENDURANCE,),0,0)),))
        # The Wound's Endurance has one success, so the actual spend is the later Critical Test.
        result = execute(source,heavy_prefix(12,endurance_success=True)
            +[10]*3+[1]*3+[10,10,10,1,1,1]*3)
        recover, = tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
        self.assertTrue(recover.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        end = next(step.proof for step in result.steps if isinstance(step.proof,PcTurnEndProof)
            and step.proof.result.completed_turn.actor_id=='pc' and step.source.round_state.round_number==2)
        self.assertIsNotNone(end.critical.glorious)
        self.assertEqual(end.critical.glorious.source_request.initial_roll.initial_values,(10,10,10))
        self.assertEqual(result.state.party[0].fate.remaining_spends,2)
        self.assertEqual(result.state.party[0].fate.rating,3)

    def test_native_injured_two_handed_helper_recovers_then_uses_both_hands_for_help(self):
        source = make_pc_melee_party_scenario(enemy_count=3,max_rounds=3)
        helper, beneficiary = source.party
        source = replace(source,party=(replace(helper,pc=replace(helper.pc,weapon=PcMeleeWeapon.PICKAXE),
            initial_weapon_hand=PcTwoHandedGrip.BOTH,
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None)),beneficiary))
        result = execute(source,[10]*3+[10]*3+[1]*2
            +[1,1,1,10,10,10,1]+[1,1,1,10,10,10,1,1]
            +[1,1,1,10,10,10,1,1,10,1,10,10,10]
            +[1]*3+[10]*3+[1]*2+[10,10,10,1,1,1]*3
            +[1]*3+[1]*3+[1]*6+[10]*2+[10,10,1,1,1]*2)
        help_steps = tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))
        self.assertEqual(len(help_steps),2)
        helped = help_steps[-1]
        self.assertEqual(helped.source.round_state.round_number,3)
        self.assertIs(helped.source.participant('pc1').weapon_hand,PcTwoHandedGrip.BOTH)
        self.assertIn(PcBodyFactKind.INJURED_HAND,tuple(fact.kind for fact in helped.source.participant('pc1').body_facts))
        self.assertEqual(helped.proof.execution.help_test_result.trace.rolled_dice,3)
        self.assertTrue(helped.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_unavailable_grip_stops_only_after_complete_wound_and_immediate_consequences(self):
        for total,kind in ((16,PcBodyFactKind.UNUSABLE_ARM),(18,PcBodyFactKind.CLUTCH_STOMACH),
                (20,PcBodyFactKind.LOST_ARM)):
            for side in ((1,10) if total!=18 else (1,)):
                with self.subTest(total=total,side=side):
                    source = two_handed_source(enemies=4,rounds=3)
                    result = execute(source,heavy_prefix(total,side=side))
                    self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
                    self.assertEqual(result.unsupported,PcMeleeUnsupported('pc',
                        'RULE-EQUIPMENT-002:pc:w3:two-handed-grip','two_handed_grip_unavailable',3,total))
                    member = result.state.party[0]
                    self.assertEqual(member.daily_wounds.wound_count,3)
                    self.assertEqual(member.injury.wounds[-1].table_total,total)
                    self.assertTrue(member.injury.wounds[-1].effect_resolved)
                    self.assertIn(kind,tuple(fact.kind for fact in member.body_facts))
                    self.assertIsNone(usable_weapon_hand(member))
                    if total in (16,20):
                        self.assertIs(member.weapon_hand,PcTwoHandedGrip.BOTH)
                    else:
                        self.assertIsNone(member.weapon_hand)
                    self.assertEqual(result.state.pending,())
                    self.assertIsNone(result.state.pending_wound)
                    self.assertEqual(result.executed_actions,4)
                    self.assertIsInstance(result.steps[-1].proof,PcBodyConsequenceProof)
                    self.assertEqual(result.state.round_state.active_turn.actor_id,'minion3')
                    self.assertEqual(result.state.round_state.round_number,1)
                    self.assertFalse(any(isinstance(step.proof,PcAttackProof)
                        and step.proof.request.actor_id=='minion4' for step in result.steps))
                    self.assertEqual(member.fate,source.party[0].fate)

    def test_actual_unsupported_replays_and_rejects_forged_source_or_skipped_consequence(self):
        result = execute(two_handed_source(enemies=4),heavy_prefix(18))
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        with self.assertRaises(ValueError):
            replace(result,steps=result.steps[:-1])
        with self.assertRaises(ValueError):
            replace(result,unsupported=None)
        with self.assertRaises(ValueError):
            replace(result,unsupported=replace(result.unsupported,source_id='RULE-EQUIPMENT-002:pc:w2:two-handed-grip'))
        with self.assertRaises(ValueError):
            replace(result,outcome=PcMeleeOutcome.ROUND_LIMIT)

    def test_near_miss_negates_actual_grip_losing_wound_before_stop_decision(self):
        for total in (16,18,20):
            with self.subTest(total=total):
                source = two_handed_source(enemies=3)
                source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
                    near_miss_policy=PcNearMissPolicy(16,0)),))
                values = heavy_prefix(total)
                if total in (16,20):
                    values = values[:-1]  # No random anatomical consequence after an actual Near Miss.
                result = execute(source,values)
                self.assertIsNone(result.unsupported)
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                self.assertEqual(result.state.party[0].daily_wounds.wound_count,2)
                self.assertEqual(result.state.party[0].fate.rating,2)
                self.assertEqual(result.state.party[0].body_facts,())
                self.assertIs(result.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)

    def test_forged_single_hand_state_and_omitted_recover_are_rejected(self):
        result = execute(two_handed_source(rounds=2),first_wound_script(8)+[10,10]+[1]*3)
        recover = next(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
        with self.assertRaises(ValueError):
            replace(recover.state,party=(replace(recover.state.party[0],weapon_hand=PcWeaponHand.LEFT),))
        forged = deepcopy(result)
        forged_recover = next(step for step in forged.steps if isinstance(step.proof,PcRecoverProof))
        object.__setattr__(forged_recover.state.party[0],'weapon_hand',PcWeaponHand.RIGHT)
        with self.assertRaises(ValueError):
            replace(forged)
        with self.assertRaises(ValueError):
            replace(result,steps=tuple(step for step in result.steps if step is not recover))


if __name__ == '__main__':
    unittest.main()
