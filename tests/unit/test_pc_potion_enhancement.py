from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_potion_scenarios import enhancement_source
from tests.support.pc_tactics_fixtures import tactical_snapshot
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import _pc_test, PcAttackProof
from towr.domain.pc_potion_models import PcPotionRecoverProof, pc_effective_definition
from towr.domain.pc_shield_models import pc_shield_resilience
from towr.domain.pc_tactical_models import select_pc_tactic
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class PcPotionEnhancementTests(unittest.TestCase):
    def test_three_initial_enhancements_execute_native_recover_without_changing_source(self):
        for characteristic in ('weapon_skill', 'strength', 'toughness'):
            with self.subTest(characteristic=characteristic):
                source = enhancement_source(characteristic)
                result = run_pc_melee_scenario(source, Random(42))
                used = tuple(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
                self.assertEqual(len(used), 1)
                step = used[0]
                self.assertEqual(step.proof.after.enhancements, (characteristic,))
                self.assertEqual(step.proof.after.potions[0].quantity, 1)
                self.assertEqual(source.party[0].consumables[0].quantity, 2)
                self.assertIsNotNone(step.proof.result.slot.execution)
                self.assertIn('RULE-MAGIC-ITEM-007:enhancement-potion', step.proof.applied_rule_ids)
                current = pc_effective_definition(step.state, 'pc1')
                self.assertEqual(getattr(current, characteristic), getattr(source.party[0].pc, characteristic)+1)
                if characteristic == 'weapon_skill':
                    self.assertEqual(_pc_test(step.state,'pc1','check',Skill.MELEE).profile.base_dice, 2)
                    self.assertEqual(_pc_test(step.state,'pc1','check',Skill.MELEE).profile.maximum_dice, 4)
                if characteristic == 'toughness':
                    self.assertEqual(pc_shield_resilience(step.state,'pc1').total, 4)
                if characteristic == 'strength':
                    attack = next(s.proof for s in result.steps if type(s.proof) is PcAttackProof
                        and s.proof.request.actor_id == 'pc1')
                    # Check the actual execution's bound damage, not only a UI number.
                    self.assertEqual(attack.request.kernel_request.attack.impact_spec.damage.base, 4)

    def test_agility_after_actual_hand_drop_does_not_pick_up_the_weapon_for_free(self):
        source = enhancement_source('agility', rounds=3)
        # Miss; first NPC inflicts Shaking Grip8 and drops the left-hand Staff;
        # remaining NPCs miss. Round2 drinks, round3 retrieves the Staff.
        values = [10,1] + [1,1,1,10,8,1] + [10]*12 + [10]*21 + [10]*12
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        step = next(s for s in result.steps if type(s.proof) is PcPotionRecoverProof)
        self.assertIsNone(step.proof.before.weapon_hand)
        self.assertIsNone(step.proof.after.weapon_hand)
        self.assertEqual(step.proof.after.enhancements, ('agility',))
        self.assertEqual(_pc_test(step.state,'pc1','check',Skill.ATHLETICS).profile.base_dice, 4)
        self.assertIsNotNone(result.state.participant('pc1').weapon_hand)

    def test_real_trial_counts_are_complete_and_each_trial_gets_its_own_supply(self):
        request = PcMeleeSimulationRequest(enhancement_source(), 42, 2)
        first = run_pc_melee_trial(request,0)
        again = run_pc_melee_trial(request,0)
        self.assertEqual(first, again)
        self.assertEqual(tuple((item.actor_id,item.item_id,item.count) for item in first.potion_use_counts),
            (('pc1','enhancement',1),))
        self.assertEqual(request.scenario.party[0].consumables[0].quantity, 2)

    def test_drained_keeps_the_characteristic_change_and_does_not_turn_it_into_bonus_dice(self):
        state = tactical_snapshot(enhancement_source())
        member = state.party[0]
        state = replace(state,party=(replace(member,enhancements=('weapon_skill',),
            injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
        request = _pc_test(state,'pc1','drained',Skill.MELEE)
        self.assertEqual(request.profile.base_dice, 2)
        self.assertEqual(request.profile.maximum_dice, 4)
        self.assertEqual(request.profile.threshold, 1)
        self.assertFalse(any(item.amount>0 for item in request.dice_modifiers))

    def test_once_per_characteristic_across_item_ids_and_no_wasted_final_turn(self):
        source = enhancement_source()
        extra = ConsumableItem('second',ConsumableKind.ENHANCEMENT,3,'weapon_skill')
        source = replace(source,party=(replace(source.party[0],consumables=(*source.party[0].consumables,extra)),))
        result = run_pc_melee_scenario(source,Random(42))
        self.assertEqual(sum(type(s.proof) is PcPotionRecoverProof for s in result.steps),1)
        self.assertIsNone(select_pc_tactic(tactical_snapshot(enhancement_source(rounds=1))).potion)


if __name__ == '__main__':
    unittest.main()
