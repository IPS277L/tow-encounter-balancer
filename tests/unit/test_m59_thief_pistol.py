"""A real Pistol shot uses the existing complete Now You See Me permission."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario, pistol_profile
from tests.unit.test_m54_pistol_execution import execute, incoming, raw, shots, steps
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeOutcome, PcMeleeStep
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.protection_models import NOW_YOU_SEE_ME_RULE_ID, UnopposedReason
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.rules.protection_preparation import prepare_protection
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def thief_pistol_scene(*, thieves=1, pc_count=1, melee_actor_ids=(), rounds=1):
    base = book_pc_scenario(footpads=0,townsfolk=0,thieves=thieves,
        pc_count=pc_count,max_rounds=rounds)
    party = tuple(member if member.actor_id in melee_actor_ids else replace(member,
        pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile()))
        for member in base.party)
    return replace(base,party=party,facts=replace(base.facts,outnumbering_bonus_approved=False))


class ThiefPistolTests(unittest.TestCase):
    def test_loaded_hit_uses_exact_thief_permission_and_printed_stealth(self):
        result = execute(thief_pistol_scene(),[1]*3+[10]*3)
        shot, = shots(result)
        preparation = shot.proof.protection
        permission = preparation.source_request.halfling_stealth_permission
        self.assertEqual(permission.defender_id,'thief1')
        self.assertEqual(permission.definition,result.source.enemy('thief1').definition)
        self.assertIs(preparation.source_request.attack_skill,Skill.SHOOTING)
        self.assertIs(preparation.source_request.selected_skill,Skill.STEALTH)
        self.assertEqual((raw(shot).defender_test.trace.rolled_dice,
            raw(shot).defender_test.trace.threshold,raw(shot).defender_test.trace.pool_cap),(3,5,6))
        self.assertEqual(preparation.applied_rule_ids.count(NOW_YOU_SEE_ME_RULE_ID),1)
        self.assertFalse(result.state.participant('pc1').ranged.loaded)
        self.assertEqual(result.executed_actions,1)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_winning_stealth_does_not_create_hidden_action_or_counterattack(self):
        result = execute(thief_pistol_scene(),[10]*3+[1]*3+[10]*2+[1]*3)
        shot, = shots(result)
        self.assertEqual(shot.state.participant('pc1').injury.wounds,())
        self.assertFalse(shot.state.participant('pc1').ranged.loaded)
        own_attack, = incoming(result)
        self.assertIs(own_attack.proof.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual(result.executed_actions,2)

    def test_reload_and_next_shot_retain_the_same_source_bound_permission(self):
        result = execute(thief_pistol_scene(rounds=3),
            [10]*3+[1]*3+[10]*2+[1]*3 + [1]*3+[10]*2+[1]*3 + [1]*3+[10]*3)
        self.assertEqual(len(shots(result)),2)
        self.assertEqual(len(steps(result,PcRangedReloadProof)),1)
        for shot in shots(result):
            self.assertEqual(shot.proof.protection.source_request.halfling_stealth_permission.defender_id,'thief1')
            self.assertEqual(raw(shot).defender_test.trace.threshold,5)
        self.assertEqual(result.executed_actions,5)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_mixed_party_and_multiple_thieves_bind_each_actual_defender(self):
        result = execute(thief_pistol_scene(thieves=2,pc_count=2,melee_actor_ids=('pc2',)),
            [1]*3+[10]*3+[1]*3+[10]*3)
        attacks = steps(result,PcAttackProof)
        self.assertEqual(tuple(step.proof.request.target_id for step in attacks),('thief1','thief2'))
        self.assertEqual(tuple(step.proof.protection.source_request.attack_skill for step in attacks),
            (Skill.SHOOTING,Skill.MELEE))
        for step in attacks:
            permission = step.proof.protection.source_request.halfling_stealth_permission
            self.assertEqual(permission.defender_id,step.proof.request.target_id)
            self.assertEqual(permission.definition,step.source.enemy(permission.defender_id).definition)
            self.assertIs(step.proof.protection.source_request.selected_skill,Skill.STEALTH)
        self.assertEqual(result.executed_actions,2)

    def test_unaware_defenceless_precedence_from_real_shooting_preparation(self):
        shot, = shots(execute(thief_pistol_scene(),[1]*3+[10]*3))
        base = shot.proof.protection.source_request
        for aware,defenceless,reason in ((False,False,UnopposedReason.UNAWARE),
                (True,True,UnopposedReason.DEFENCELESS)):
            source = replace(base,defender_is_aware=aware,defender_is_defenceless=defenceless,
                selected_skill=None,options=())
            prepared = prepare_protection(source)
            self.assertIsNone(prepared.attack.defender_test)
            self.assertEqual(prepared.unopposed_reasons,(reason,))
            self.assertNotIn(NOW_YOU_SEE_ME_RULE_ID,prepared.applied_rule_ids)

    def test_authored_stealth_does_not_gain_the_book_permission(self):
        source = make_pc_pistol_scenario()
        enemy = source.enemies[0]
        forged = replace(enemy,definition=replace(enemy.definition,protection=(replace(
            enemy.definition.protection[0],skill=Skill.STEALTH),)))
        with self.assertRaises((TypeError,ValueError)):
            replace(source,enemies=(forged,))

    def test_forged_nested_book_profile_and_skill_alias_fail_before_rng(self):
        class Alias(str,Enum):
            STEALTH = 'stealth'
        request = PcMeleeSimulationRequest(thief_pistol_scene(),42,1)
        for field,value in (('skill',Alias.STEALTH),('threshold',4),('pool_cap',8)):
            forged = deepcopy(request)
            profile = forged.scenario.enemies[0].definition.protection[0]
            object.__setattr__(profile if field=='skill' else profile.test_profile,field,value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_replay_and_foreign_defender_permission_cannot_replace_the_prefix(self):
        shot, = shots(execute(thief_pistol_scene(),[1]*3+[10]*3))
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(shot.state,shot)
        forged = deepcopy(shot.proof)
        permission = forged.protection.source_request.halfling_stealth_permission
        object.__setattr__(permission,'defender_id','another-thief')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,forged)


if __name__ == '__main__':
    unittest.main()
