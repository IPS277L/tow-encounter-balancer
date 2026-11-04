"""Source-bound adjacent NPC exits use actual own turns and common free movement."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m23_pc_official_wounds import official_scene,retarget
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_models import PcAdjacentNpcExitPolicy,PcMeleePolicy,PcHelpPolicy,PcHelpTarget
from towr.domain.pc_melee_result_models import (PcMeleeOutcome,PcAttackProof,PcHelpProof,PcTurnEndProof,
    PcMeleeStep,initial_pc_melee_state,pc_melee_round_participants)
from towr.domain.pc_npc_exit_models import PcNpcExitProof,build_pc_npc_exit
from towr.domain.test_models import Skill,DiceModifier
from towr.domain.turn_models import (CombatActionSlotRequest,CombatActionDeclaration,CombatActionKind,
    ActionSlotGrant,CombatTurnStartResult)
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.turn_resolution import reserve_combat_action_slot


def scene_with_exit(**kwargs):
    scene = official_scene(**kwargs)
    return replace(scene,facts=replace(scene.facts,can_leave_zone=True),
        npc_broken_exit_policy=PcAdjacentNpcExitPolicy('outside',True,True))


def execute(scene,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(scene,rng)
    rng.assert_exhausted()
    return result


def exits(result):
    return tuple(step for step in result.steps if type(step.proof) is PcNpcExitProof)


def basic_exit():
    return execute(scene_with_exit(),[1]*3+[10]*3)


class NpcExitTests(unittest.TestCase):
    def test_actual_final_exit_succeeds_on_last_round_without_standard_action_or_fake_turn_end(self):
        result = basic_exit()
        exit_step, = exits(result)
        proof = exit_step.proof
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.exited_npc_ids,('minion1',))
        self.assertEqual(result.state.exited_npc_ids,('minion1',))
        self.assertEqual(result.executed_actions,1)
        self.assertEqual(proof.result,resolve_free_movement(proof.request))
        self.assertEqual(proof.request.round_state.active_turn.actor_id,'minion1')
        self.assertEqual(proof.request.round_state.active_turn.action_slots,())
        self.assertEqual(proof.request.state.graph.zone_ids,('arena','outside'))
        self.assertEqual(proof.request.traversed_zone_ids,('outside',))
        self.assertEqual(proof.request.path_entity_ids,())
        self.assertEqual(proof.result.state.placement_for('pc').zone_id,'arena')
        self.assertEqual(proof.result.state.placement_for('minion1').zone_id,'outside')
        self.assertEqual(proof.result.state.free_move_used_entity_ids,('minion1',))
        self.assertIsNone(result.state.round_state.active_turn)
        self.assertEqual(result.state.round_state.excluded_turn_entity_ids,('minion1',))
        self.assertEqual(result.state.round_state.completed_turn_entity_ids,('pc',))
        self.assertTrue(result.state.round_state.round_complete)
        self.assertEqual(result.state.live_enemies,())
        npc = result.state.enemy('minion1').state.injury
        self.assertEqual(npc.wounds,1)
        self.assertFalse(npc.defeated)
        self.assertTrue(npc.conditions.has(Condition.BROKEN))
        self.assertFalse(any(isinstance(step.proof,PcTurnEndProof)
            and step.proof.result.completed_turn.actor_id=='minion1' for step in result.steps))
        self.assertIsInstance(result.steps[-2].proof,CombatTurnStartResult)
        self.assertIsNone(result.unsupported)

    def test_other_pc_can_defeat_official_before_its_exit(self):
        result = execute(scene_with_exit(pcs=2),[1]*4+[10]*3+[1]*4+[10]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.exited_npc_ids,())
        self.assertEqual(exits(result),())
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)

    def test_exit_ids_follow_source_order_and_each_movement_source_preserves_earlier_exit(self):
        scene = scene_with_exit(pcs=2,enemies=2,officials=('minion1','minion2'))
        first,second = scene.party
        scene = replace(scene,party=(first,retarget(second,('minion2','minion1'))),
            enemy_activation_order=('minion2','minion1'))
        result = execute(scene,[1]*3+[10]*3+[1]*3+[10]*3)
        first_exit,second_exit = exits(result)
        self.assertEqual(tuple(step.proof.request.actor_id for step in exits(result)),('minion2','minion1'))
        self.assertEqual(result.exited_npc_ids,('minion1','minion2'))
        self.assertEqual(first_exit.proof.request.state.free_move_used_entity_ids,())
        self.assertEqual(second_exit.proof.request.state.free_move_used_entity_ids,('minion2',))
        self.assertEqual(second_exit.proof.request.state.placement_for('minion2').zone_id,'outside')
        self.assertEqual(second_exit.proof.request.state.placement_for('minion1').zone_id,'arena')

    def test_next_round_targets_and_outnumbering_ignore_exited_npc(self):
        scene = scene_with_exit(pcs=2,enemies=2,rounds=2)
        first,second = scene.party
        scene = replace(scene,party=(first,retarget(second,('minion2','minion1'))))
        result = execute(scene,[1]*3+[10]*3+[10]*3+[1]*2+[10]*2+[1]*3+[1]*4+[10]*2)
        attack = next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertEqual(attack.proof.request.target_id,'minion2')
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-COMBAT-007:outnumbering',1),))
        self.assertEqual(tuple(p.entity_id for p in attack.source.round_state.participants),('pc1','pc2','minion2'))
        self.assertEqual(tuple(p.entity_id for p in pc_melee_round_participants(attack.source)),('pc1','pc2','minion2'))
        self.assertEqual(result.exited_npc_ids,('minion1',))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_later_round_movement_keeps_placements_but_clears_previous_round_used_movement(self):
        scene = scene_with_exit(pcs=2,enemies=2,officials=('minion1','minion2'),rounds=2)
        first,second = scene.party
        scene = replace(scene,party=(first,retarget(second,('minion2','minion1'))))
        result = execute(scene,[1]*3+[10]*3+[10]*3+[1]*3+[10]*2+[1]*3
            +[1]*4+[10]*3+[10]*4+[1]*3)
        first_exit,second_exit = exits(result)
        self.assertEqual(first_exit.source.round_state.round_number,1)
        self.assertEqual(second_exit.source.round_state.round_number,2)
        self.assertEqual(second_exit.proof.request.state.free_move_used_entity_ids,())
        self.assertEqual(second_exit.proof.request.state.placement_for('minion1').zone_id,'outside')
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_protection_help_for_exited_incoming_actor_stays_unused_and_next_round_binds_remaining_npc(self):
        scene = scene_with_exit(pcs=2,enemies=2,rounds=2)
        helper,beneficiary = scene.party
        scene = replace(scene,party=(replace(helper,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE)),beneficiary),
            enemy_target_priority=('pc2','pc1'))
        result = execute(scene,[1]*3+[1]*3+[10]*3+[10]*2+[1]*3
            +[1]*3+[10]*4+[1]*2+[10]*2+[1]*6)
        help_steps = tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))
        self.assertEqual(len(help_steps),2)
        first = help_steps[0].proof.execution.bonus
        second = help_steps[1].proof.execution.bonus
        self.assertEqual(first.beneficiary_test_id,'pc-melee:r1:minion1:protection')
        self.assertEqual(second.beneficiary_test_id,'pc-melee:r2:minion2:protection')
        incoming = tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='minion2')
        self.assertEqual(incoming[0].proof.help_applications,())
        self.assertEqual(incoming[0].proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        self.assertEqual(len(incoming[1].proof.help_applications),1)
        self.assertEqual(incoming[1].proof.execution.resolution.attack.defender_test.trace.rolled_dice,6)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_null_policy_preserves_unsupported_and_live_remaining_npc_preserves_round_limit(self):
        null = execute(official_scene(),[1]*3+[10]*3)
        self.assertIs(null.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(null.exited_npc_ids,())
        scene = scene_with_exit(pcs=2,enemies=2)
        first,second = scene.party
        scene = replace(scene,party=(first,retarget(second,('minion2','minion1'))))
        limited = execute(scene,[1]*3+[10]*3+[10]*3+[1]*2+[10]*2+[1]*3)
        self.assertIs(limited.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(limited.exited_npc_ids,('minion1',))
        self.assertEqual(tuple(enemy.state.actor_id for enemy in limited.state.live_enemies),('minion2',))

    def test_replay_and_forged_movement_source_or_clock_are_rejected_before_observation(self):
        result = basic_exit()
        step, = exits(result)
        current = initial_pc_melee_state(result.source)
        for transition in result.steps:
            current = apply_pc_melee_step(current,transition)
        self.assertEqual(current,result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)
        with self.assertRaises(ValueError):
            replace(result,steps=result.steps[:-1])
        for request in (replace(step.proof.request,actor_conditions=ConditionState()),
                replace(step.proof.request,state=replace(step.proof.request.state,free_move_used_entity_ids=('pc',))),
                replace(step.proof.request,id='foreign:movement')):
            forged = PcNpcExitProof(request,resolve_free_movement(request))
            with self.subTest(request=request),self.assertRaises(ValueError):
                PcMeleeStep(step.source,forged)
        reservation = reserve_combat_action_slot(CombatActionSlotRequest('skip:reserve',step.source.round_state,'minion1',
            CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,reservation)
        forged = deepcopy(result)
        forged_step = exits(forged)[0]
        object.__setattr__(forged_step.state,'round_state',replace(forged_step.state.round_state,
            excluded_turn_entity_ids=(),completed_turn_entity_ids=('pc','minion1')))
        with self.assertRaises(ValueError):
            replace(forged)
        mutated = deepcopy(step.proof)
        object.__setattr__(mutated.result,'state',replace(mutated.result.state,
            placements=(replace(mutated.result.state.placements[0],zone_id='outside'),
                *mutated.result.state.placements[1:])))
        with self.assertRaises(ValueError):
            replace(mutated)

    def test_native_critical_pc_tail_and_other_actors_finish_before_exit(self):
        scene = scene_with_exit(pcs=2,enemies=4,officials=('minion4',),rounds=2)
        first,second = scene.party
        scene = replace(scene,party=(retarget(first,('minion4','minion1','minion2','minion3'),
            pc=replace(first.pc,toughness=4,armour_bonus=2)),second))
        result = execute(scene,[10]*3+[1]*3+[1]*3+[10]*2
            +[1,1,1,10,10,10,1]+[1,1,1,10,10,10]+[1,1,1,10,10,10,7,7]
            +[1]*3+[10]*3+[1]*4+[1]*3+[10]*2+[10]*2+[1]*3)
        exit_step, = exits(result)
        tail = next(step for step in result.steps if isinstance(step.proof,PcTurnEndProof)
            and step.proof.result.completed_turn.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertIsNotNone(tail.proof.critical)
        self.assertLess(result.steps.index(tail),result.steps.index(exit_step))
        self.assertEqual(exit_step.source.round_state.completed_turn_entity_ids,('pc1','pc2','minion3'))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(result.exited_npc_ids,('minion4',))

    def test_pure_final_round_budget_does_not_invent_future_exit(self):
        # Synthetic completed-round boundary; the native W1 path otherwise reaches this NPC turn.
        stopped = execute(official_scene(),[1]*3+[10]*3).state
        enabled = replace(stopped.source,facts=replace(stopped.source.facts,can_leave_zone=True),
            npc_broken_exit_policy=PcAdjacentNpcExitPolicy('outside',True,True))
        state = replace(stopped,source=enabled,round_state=replace(stopped.round_state,
            completed_turn_entity_ids=('pc','minion1')))
        self.assertTrue(state.round_state.round_complete)
        self.assertIsNone(build_pc_npc_exit(state,'minion1'))
        self.assertEqual(state.exited_npc_ids,())


if __name__ == '__main__':
    unittest.main()
