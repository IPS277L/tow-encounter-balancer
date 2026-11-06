"""Both Bear attacks are real, source-bound actions in one turn."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_bear_scenarios import bear_scene
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackOutcome, ImpactOutcome
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (PcFatePolicy, PcNearMissPolicy,
    PcHelpPolicy, PcHelpTarget, PcMeleePolicy)
from towr.domain.test_models import Skill
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeStep, PcTurnEndProof, PcWoundCompletionProof,
)
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.turn_models import CombatActionSlotResult, CombatTurnEndRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.attack_action_execution import _validate_attack_action_slot
from towr.rules.turn_resolution import end_combat_turn


PC_MISS = [10,10,10,1,1,1]
BEAR_HIT = [1,1,1,1,10,10,10,1]
BEAR_MISS = [10,10,10,10,1,1,1]


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def incoming(result):
    return tuple(step for step in result.steps if type(step.proof) is PcAttackProof
        and step.proof.request.actor_id == 'bear1')


class PcBearExecutionTests(unittest.TestCase):
    def test_two_attacks_have_distinct_targets_slots_tests_receipts_and_one_end(self):
        result = execute(bear_scene(), PC_MISS*2 + BEAR_HIT*2)
        first, second = incoming(result)
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc1','pc2'))
        self.assertEqual((first.proof.execution.slot_index, second.proof.execution.slot_index), (1,2))
        self.assertNotEqual(first.proof.request.id, second.proof.request.id)
        self.assertNotEqual(first.proof.request.kernel_request.attack.attacker_test.id,
            second.proof.request.kernel_request.attack.attacker_test.id)
        self.assertNotEqual(first.proof.request.kernel_request.attack.defender_test.id,
            second.proof.request.kernel_request.attack.defender_test.id)
        self.assertFalse(second.source.pending)
        self.assertIsNone(second.source.pending_wound)
        self.assertEqual(len(second.source.party[0].injury.wounds), 1)
        self.assertEqual(result.executed_actions, 4)
        self.assertEqual(sum(type(s.proof) is PcTurnEndProof and s.proof.result.completed_turn.actor_id=='bear1'
            for s in result.steps), 1)
        self.assertEqual(len(result.state.party[1].injury.wounds), 1)

    def test_miss_and_zero_zero_do_not_grant_second_attack(self):
        for values in (BEAR_MISS, [10]*7):
            result = execute(bear_scene(), PC_MISS*2 + values)
            self.assertEqual(len(incoming(result)), 1)
            self.assertIs(incoming(result)[0].proof.execution.resolution.attack.outcome, AttackOutcome.MISS)
            self.assertEqual(result.executed_actions, 3)

    def test_empty_policy_and_single_pc_skip_without_extra_rolls(self):
        for source, count in ((bear_scene(enabled=False),2), (bear_scene(pcs=1),1)):
            result = execute(source, PC_MISS*count + BEAR_HIT)
            self.assertEqual(len(incoming(result)), 1)
            self.assertEqual(result.executed_actions, count+1)

    def test_positive_tie_hit_without_wound_still_grants_other_target(self):
        source = bear_scene()
        source = replace(source, party=tuple(replace(member,pc=replace(member.pc,toughness=8))
            for member in source.party))
        # First PC ties Bear without Wounding and remains unstaggered. Second PC misses.
        result = execute(source, [1,10,10,1,10,10] + PC_MISS
            + [1,10,10,10,1,10,10] + BEAR_MISS)
        first, second = incoming(result)
        attack = first.proof.execution.resolution.attack
        self.assertIs(attack.outcome, AttackOutcome.HIT)
        self.assertTrue(attack.tie_break_applied)
        self.assertIs(attack.impact, ImpactOutcome.STAGGERED)
        self.assertIsNone(first.proof.execution.resolution.character_wound)
        self.assertEqual(second.proof.request.target_id, 'pc2')

    def test_near_miss_negates_first_wound_and_preserves_second_attack(self):
        source = bear_scene()
        first = replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1,0))
        source = replace(source, party=(first, source.party[1]))
        result = execute(source, PC_MISS*2 + BEAR_HIT*2)
        attacks = incoming(result)
        self.assertEqual(len(attacks), 2)
        self.assertEqual(len(attacks[1].source.party[0].injury.wounds), 0)
        completions = [s.proof for s in result.steps if type(s.proof) is PcWoundCompletionProof]
        self.assertEqual(len(completions), 2)
        self.assertEqual(result.state.party[0].fate.rating, source.party[0].fate.rating-1)

    def test_actual_priority_selects_first_other_pc(self):
        source = replace(bear_scene(pcs=3), enemy_target_priority=('pc3','pc1','pc2'))
        result = execute(source, PC_MISS*3 + BEAR_HIT*2)
        self.assertEqual(tuple(s.proof.request.target_id for s in incoming(result)), ('pc3','pc1'))

    def test_cannot_skip_granted_attack_or_execute_against_primary_target(self):
        result = execute(bear_scene(), PC_MISS*2 + BEAR_HIT*2)
        _, second = incoming(result)
        with self.assertRaises(ValueError):
            _validate_attack_action_slot(replace(second.proof.request, target_id='pc1',
                kernel_request=replace(second.proof.request.kernel_request,target_id='pc1')))
        slot = next(s for s in result.steps if type(s.proof) is CombatActionSlotResult and s.proof.slot.index==2)
        clock = slot.source.round_state
        end = end_combat_turn(CombatTurnEndRequest('pc-melee:r1:bear1:end',clock,'bear1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(slot.source, PcTurnEndProof(end,None))
        self.assertIsNotNone(build_pc_npc_extra_attack_slot(slot.source))

    def test_cached_target_and_receipt_tampering_are_rejected(self):
        result = execute(bear_scene(), PC_MISS*2 + BEAR_HIT*2)
        _, second = incoming(result)
        for attribute, value in (('target_id','pc1'), ('slot_index',1)):
            forged = deepcopy(second.proof)
            object.__setattr__(forged.execution, attribute, value)
            with self.subTest(attribute=attribute), self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(second.source, forged)
        slot = next(s for s in result.steps if type(s.proof) is CombatActionSlotResult and s.proof.slot.index==2)
        forged = deepcopy(slot.proof)
        object.__setattr__(forged.slot.enduring_strength,'first_target_id','pc2')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(slot.source, forged)

    def test_primary_death_does_not_erase_actual_primary_target(self):
        source = bear_scene(rounds=3)
        hit2 = [1]*4 + [10]*3 + [1,1]
        result = execute(source, PC_MISS*2 + BEAR_HIT*2
            + PC_MISS*2 + hit2*2
            + PC_MISS*2 + [1]*4 + [10]*3 + [10,10,10]
            + [1]*4 + [10]*3 + [1,1,1])
        attacks = incoming(result)
        self.assertEqual(len(attacks), 6)
        self.assertTrue(attacks[-1].source.participant('pc1').injury.dead)
        self.assertEqual(attacks[-1].proof.request.target_id, 'pc2')
        self.assertEqual(attacks[-1].proof.request.state.active_turn.action_slots[-1].enduring_strength.first_target_id,'pc1')

    def test_living_defenceless_secondary_target_is_attacked_unopposed(self):
        source = bear_scene(rounds=3)
        hit2 = [1]*4 + [10]*3 + [1,1]
        result = execute(source, PC_MISS*2 + BEAR_HIT*2
            + PC_MISS*2 + hit2 + [1]*4 + [10]*3 + [10,10,1]
            + PC_MISS + [1,1,1]  # pc2's actionless Critical end phase
            + [1]*4 + [10]*3 + [1,1,1] + [1]*4 + [1,1,1])
        second = incoming(result)[-1]
        self.assertTrue(second.source.participant('pc2').injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(second.source.participant('pc2').injury.dead)
        self.assertIsNone(second.proof.request.kernel_request.attack.defender_test)
        self.assertEqual(second.proof.request.target_id,'pc2')

    def test_first_wound_drained_bear_can_still_attack_twice(self):
        source = bear_scene()
        source = replace(source, party=(replace(source.party[0],pc=replace(source.party[0].pc,strength=6)),source.party[1]))
        result = execute(source, [1]*3 + [10]*3 + PC_MISS
            + [1]*4 + [10]*3 + [1] + BEAR_HIT)
        first, second = incoming(result)
        self.assertTrue(first.source.enemy('bear1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertEqual(second.proof.execution.slot_index,2)

    def test_pending_first_wound_cannot_be_skipped_to_extra_slot(self):
        result = execute(bear_scene(), PC_MISS*2 + BEAR_HIT*2)
        first = incoming(result)[0]
        self.assertIsNotNone(first.state.pending_wound)
        with self.assertRaises(ValueError):
            build_pc_npc_extra_attack_slot(first.state)

    def test_protection_help_applies_only_to_its_actual_first_incoming_test(self):
        source = bear_scene()
        helper = replace(source.party[0],policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE))
        source = replace(source,party=(helper,source.party[1]),enemy_target_priority=('pc2','pc1'))
        result = execute(source,[1]*3 + PC_MISS + [1]*4 + [10]*6 + [1] + BEAR_HIT)
        first,second = incoming(result)
        self.assertEqual(len(first.proof.help_applications),1)
        self.assertEqual(first.proof.help_applications[0].source_request.beneficiary_id,'pc2')
        self.assertEqual(first.proof.execution.resolution.attack.defender_test.trace.rolled_dice,6)
        self.assertEqual(second.proof.help_applications,())
        self.assertEqual(second.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)

    def test_npc_help_does_not_move_from_primary_attack_test_to_second(self):
        source = book_pc_scenario(bears=1,peasants=1,footpads=0,townsfolk=0,max_rounds=1)
        source = replace(source,enemy_activation_order=('peasant1','bear1'),
            npc_help_policies=(PcNpcHelpPolicy('peasant1','bear1'),),
            npc_extra_attack_actor_ids=('bear1',))
        result = execute(source,PC_MISS*2 + [1]*5 + [10]*3 + [1] + BEAR_HIT)
        first,second = incoming(result)
        self.assertEqual(len(first.proof.npc_help_applications),1)
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,5)
        self.assertEqual(second.proof.npc_help_applications,())
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)

    def test_staggered_bear_retains_ability_to_take_second_attack(self):
        result = execute(bear_scene(),[1,10,10,1,10,10] + PC_MISS + BEAR_HIT*2)
        first,second = incoming(result)
        self.assertTrue(first.source.enemy('bear1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.execution.slot_index,2)


if __name__ == '__main__':
    unittest.main()
