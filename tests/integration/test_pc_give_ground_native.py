"""Reactive Give Ground in actual fresh Dynamic/native battles, both roles."""
import unittest
from dataclasses import replace

from tests.support.magic_weapon_battles import magic_battle,run_native
from towr.domain.pc_give_ground_models import PcGiveGroundProof
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand
from towr.domain.condition_models import Condition,StaggerOutcome
from towr.domain.weapon_quality_preparation import UNWAVERING_GIVEN_GROUND_RULE_ID


class PcGiveGroundNativeTests(unittest.TestCase):
    def test_generated_npc_gives_ground_without_buying_another_action(self):
        source=magic_battle('staff',pc_ws=6,npc_ws=1,rounds=2)
        result=run_native(self,source)
        movements=[step for step in result.steps if type(step.proof) is PcGiveGroundProof]
        self.assertEqual(len(movements),1)
        movement=movements[0]
        self.assertEqual(movement.proof.actor_id,source.enemy_activation_order[0])
        previous=result.steps[result.steps.index(movement)-1].state
        self.assertEqual(movement.state.round_state,previous.round_state)
        self.assertEqual(movement.proof.result.state.free_move_used_entity_ids,
            movement.proof.previous.spatial.free_move_used_entity_ids)
        self.assertEqual(result.executed_actions,4)

    def test_automatic_player_gives_ground_from_the_actual_npc_attack(self):
        source=magic_battle('staff',pc_ws=1,npc_ws=6)
        result=run_native(self,source)
        movements=[step for step in result.steps if type(step.proof) is PcGiveGroundProof]
        self.assertEqual(len(movements),1)
        movement=movements[0]
        self.assertEqual(movement.proof.actor_id,'pc')
        self.assertIs(type(movement.proof.attack),PcAttackProof)
        self.assertEqual(movement.proof.attack.request.actor_id,source.enemy_activation_order[0])
        self.assertFalse(result.state.participant('pc').injury.wounds)
        self.assertEqual(result.executed_actions,2)

    def test_a_new_spatial_round_renews_the_reaction_once_without_erasing_its_history(self):
        source=magic_battle('staff',pc_ws=6,npc_ws=1,rounds=3)
        result=run_native(self,source)
        moves=[step.proof for step in result.steps if type(step.proof) is PcGiveGroundProof]
        self.assertEqual(tuple(proof.request.state.round_number for proof in moves),(2,3))
        self.assertTrue(all(proof.actor_id==source.enemy_activation_order[0] for proof in moves))
        self.assertTrue(all(not proof.request.state.gave_ground_entity_ids for proof in moves))
        self.assertEqual(result.executed_actions,6)

    def test_unwavering_uses_the_real_earlier_give_ground_bank_in_the_same_round(self):
        source=magic_battle('unwavering_spear',players=3,pc_ws=6,npc_ws=1)
        first,second,spear=source.party
        def staff(member):
            return replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.STAFF),
                initial_weapon_hand=PcWeaponHand.LEFT,
                combat_equipment=(replace(member.combat_equipment[0],weapon=PcMeleeWeapon.STAFF,
                    hand=PcWeaponHand.LEFT),))
        source=replace(source,party=(staff(first),staff(second),spear))
        result=run_native(self,source)
        movement=next(step for step in result.steps if type(step.proof) is PcGiveGroundProof)
        strike=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==spear.actor_id)
        self.assertLess(result.steps.index(movement),result.steps.index(strike))
        context=strike.proof.weapon_intent.magic_context
        self.assertTrue(context.target_given_ground_this_round)
        self.assertTrue(any(modifier.rule_id==UNWAVERING_GIVEN_GROUND_RULE_ID
            for modifier in strike.proof.request.kernel_request.attack.attacker_test.quality_modifiers))
        self.assertFalse(strike.proof.request.kernel_request.can_target_leave_zone)
        self.assertTrue(strike.proof.request.kernel_request.target_has_given_ground_this_round)
        self.assertIs(strike.proof.execution.resolution.stagger.outcome,StaggerOutcome.FELL_PRONE)
        self.assertTrue(strike.state.enemy(source.enemy_activation_order[0]).state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(sum(type(step.proof) is PcGiveGroundProof for step in result.steps),1)


if __name__=='__main__':
    unittest.main()
