"""Actual Official Wound acknowledgements and the precise unsupported Broken-turn prefix."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import (make_pc_melee_scenario,
    make_pc_melee_party_scenario,with_pc_melee_brute)
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import ProfileStateChangeRequest,ProfileNpcType
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc
from towr.domain.pc_npc_wound_models import (PcNpcBrokenTurnUnsupported,
    OFFICIAL_BROKEN_RULE_ID,pc_npc_broken_turn_unsupported)
from towr.domain.pc_melee_result_models import (PcAttackProof,PcProfileWoundProof,PcTurnEndProof,
    PcMeleeOutcome,PcMeleeStep,initial_pc_melee_state,pc_melee_unsupported)
from towr.domain.test_models import Skill,TestQuality
from towr.domain.turn_models import CombatTurnStartRequest,CombatTurnStartResult,CombatRoundState
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.turn_resolution import start_combat_turn


def official_scene(*,pcs=1,enemies=1,officials=('minion1',),rounds=1):
    scene = (make_pc_melee_scenario(enemy_count=enemies,max_rounds=rounds) if pcs==1
        else make_pc_melee_party_scenario(pc_count=pcs,enemy_count=enemies,max_rounds=rounds))
    return replace(scene,enemies=tuple(create_pc_book_npc(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,
        enemy.state.actor_id) if enemy.state.actor_id in officials else enemy for enemy in scene.enemies))


def execute(scene,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(scene,rng)
    rng.assert_exhausted()
    return result


def basic_stop():
    return execute(official_scene(),[1]*3+[10]*3)


def retarget(member,priority,**changes):
    return replace(member,target_priority=priority,
        defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority),**changes)


class OfficialWoundTests(unittest.TestCase):
    def test_first_wound_ack_adds_broken_once_then_stops_before_own_unstarted_turn(self):
        result = basic_stop()
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        attack = next(step for step in result.steps if isinstance(step.proof,PcAttackProof))
        ack, = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertFalse(ack.source.enemy('minion1').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(ack.state.enemy('minion1').state.injury.conditions.conditions,frozenset({Condition.BROKEN}))
        self.assertEqual(result.unsupported,PcNpcBrokenTurnUnsupported('minion1',
            f'{OFFICIAL_BROKEN_RULE_ID}:minion1:{attack.proof.request.id}',attack.proof.request.id,ack.proof.source))
        self.assertFalse(hasattr(result.unsupported,'table_total'))
        self.assertIsInstance(result.steps[-1].proof,PcTurnEndProof)
        self.assertIsNone(result.state.round_state.active_turn)
        self.assertEqual(result.state.round_state.completed_turn_entity_ids,('pc',))
        self.assertFalse(any(isinstance(step.proof,CombatTurnStartResult)
            and step.proof.turn.actor_id=='minion1' for step in result.steps))
        self.assertEqual(result.state.pending,())
        self.assertIsNone(result.state.pending_wound)
        self.assertEqual(result.executed_actions,1)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)

    def test_later_pc_attacks_broken_official_with_unchanged_athletics_and_second_wound_defeats(self):
        result = execute(official_scene(pcs=2),[1]*4+[10]*3+[1]*4+[10]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        attacks = tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof))
        self.assertEqual(len(attacks),2)
        second = attacks[1]
        self.assertTrue(second.source.enemy('minion1').state.injury.conditions.has(Condition.BROKEN))
        self.assertIs(second.proof.protection.source_request.selected_skill,Skill.ATHLETICS)
        defender = second.proof.execution.resolution.attack.defender_test
        self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold,defender.trace.quality),
            (3,3,TestQuality.NORMAL))
        changes = tuple(step.proof for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(tuple((p.source.previous_wounds,p.source.current_wounds,p.source.defeated) for p in changes),
            ((0,1,False),(1,2,True)))
        self.assertIsNotNone(changes[-1].decision)
        self.assertIsNone(result.unsupported)

    def test_identical_changes_for_two_officials_bind_the_selected_actor_and_parent_attack(self):
        scene = official_scene(pcs=2,enemies=2,officials=('minion1','minion2'))
        first,second = scene.party
        scene = replace(scene,party=(first,retarget(second,('minion2','minion1'))),
            enemy_activation_order=('minion2','minion1'))
        result = execute(scene,[1]*3+[10]*3+[1]*3+[10]*3)
        changes = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(changes[0].proof.source,changes[1].proof.source)
        self.assertEqual(result.unsupported.actor_id,'minion2')
        attack = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc2')
        self.assertEqual(result.unsupported.attack_id,attack.request.id)

    def test_other_npc_turn_before_official_completes_before_the_stop(self):
        scene = official_scene(enemies=2,officials=('minion2',))
        scene = replace(scene,party=(retarget(scene.party[0],('minion2','minion1')),))
        result = execute(scene,[1]*3+[10]*3+[10]*3+[1]*3)
        self.assertEqual(result.unsupported.actor_id,'minion2')
        self.assertEqual(result.executed_actions,2)
        self.assertIsInstance(result.steps[-1].proof,PcTurnEndProof)
        self.assertEqual(result.steps[-1].proof.result.completed_turn.actor_id,'minion1')

    def test_party_death_before_official_turn_keeps_normal_defeat(self):
        scene = official_scene(enemies=4,officials=('minion4',))
        scene = replace(scene,party=(retarget(scene.party[0],('minion4','minion1','minion2','minion3')),))
        result = execute(scene,[1]*3+[10]*3
            +[1]*3+[10]*3+[1]+[1]*3+[10]*3+[1,1]+[1]*3+[10]*3+[10,10,10])
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertIsNone(result.unsupported)
        self.assertTrue(result.state.party[0].injury.dead)
        self.assertTrue(result.state.enemy('minion4').state.injury.conditions.has(Condition.BROKEN))

    def test_native_pc_critical_tail_and_later_actors_complete_before_official_stop(self):
        scene = official_scene(pcs=2,enemies=4,officials=('minion4',),rounds=2)
        first,second = scene.party
        scene = replace(scene,party=(retarget(first,('minion4','minion1','minion2','minion3'),
            pc=replace(first.pc,toughness=4,armour_bonus=2)),second))
        result = execute(scene,[10]*3+[1]*3+[1]*3+[10]*2
            +[1,1,1,10,10,10,1]+[1,1,1,10,10,10]+[1,1,1,10,10,10,7,7]
            +[1]*3+[10]*3+[1]*4+[1]*3+[10]*2+[10]*2+[1]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        wounded_attack = next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
        tail = next(step for step in result.steps if isinstance(step.proof,PcTurnEndProof)
            and step.proof.result.completed_turn.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertIsNotNone(tail.proof.critical)
        self.assertGreater(result.steps.index(tail),result.steps.index(wounded_attack))
        self.assertEqual(result.steps[-1].proof.result.completed_turn.actor_id,'minion3')

    def test_numeric_brute_and_unwounded_official_do_not_gain_first_wound_rule(self):
        numeric = with_pc_melee_brute(make_pc_melee_scenario(max_rounds=1),'minion1',wound_limit=2)
        result = execute(numeric,[1]*3+[10]*2+[10]*2+[1]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertFalse(result.state.enemy('minion1').state.injury.conditions.has(Condition.BROKEN))
        untouched = execute(official_scene(),[10]*3+[1]*3+[10]*2+[1]*3)
        self.assertIs(untouched.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(untouched.state.enemy('minion1').state.injury.wounds,0)

    def test_replay_rejects_missing_stacked_forged_or_foreign_cause_and_start_after_stop(self):
        result = basic_stop()
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        ack = next(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        with self.assertRaises(ValueError):
            replace(result,steps=tuple(step for step in result.steps if step is not ack))
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.state,ack.proof)
        with self.assertRaises(ValueError):
            replace(result,unsupported=None)
        foreign_attack = 'foreign:execute'
        foreign = replace(result.unsupported,attack_id=foreign_attack,
            source_id=f'{OFFICIAL_BROKEN_RULE_ID}:minion1:{foreign_attack}')
        with self.assertRaises(ValueError):
            replace(result,unsupported=foreign)
        with self.assertRaises(ValueError):
            replace(result.unsupported,profile_change=ProfileStateChangeRequest(ProfileNpcType.BRUTE,False,1,False))
        with self.assertRaises(ValueError):
            replace(result.unsupported,source_id='foreign:cause')
        start = start_combat_turn(CombatTurnStartRequest('illegal:start',result.state.round_state,'minion1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(result.state,start)
        forged = deepcopy(result)
        forged_ack = next(step for step in forged.steps if isinstance(step.proof,PcProfileWoundProof))
        object.__setattr__(forged_ack.state.enemy('minion1').state.injury,'conditions',ConditionState())
        with self.assertRaises(ValueError):
            replace(forged)

    def test_pure_budget_and_new_round_gates_do_not_predict_future_npc_turns(self):
        # Synthetic clock boundaries, not claims that this native prefix reached a final-round limit.
        state = basic_stop().state
        complete = replace(state,round_state=replace(state.round_state,
            completed_turn_entity_ids=('pc','minion1')))
        self.assertTrue(complete.round_state.round_complete)
        self.assertIsNone(pc_npc_broken_turn_unsupported(complete))
        next_round = replace(state,round_state=CombatRoundState(2,state.round_state.participants))
        self.assertIsNone(pc_npc_broken_turn_unsupported(next_round))

    def test_pure_stop_cause_validation_requires_one_actual_acknowledgement(self):
        # Direct helper boundaries; full-journal replay rejects these altered histories separately.
        state = basic_stop().state
        ack = next(proof for proof in state.history if isinstance(proof,PcProfileWoundProof))
        missing = replace(state,history=tuple(proof for proof in state.history if proof is not ack))
        with self.assertRaises(ValueError):
            pc_npc_broken_turn_unsupported(missing)
        duplicated = replace(state,history=(*state.history,ack))
        with self.assertRaises(ValueError):
            pc_npc_broken_turn_unsupported(duplicated)


if __name__ == '__main__':
    unittest.main()
