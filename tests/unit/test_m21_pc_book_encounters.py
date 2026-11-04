"""Literal native encounters retain printed NPC Protection Skill and full source."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.test_models import Skill,InlineProfile
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest


def single_source(footpad):
    return book_pc_scenario(footpads=int(footpad),townsfolk=int(not footpad),pc_count=1,max_rounds=1)


class PcBookEncounterTests(unittest.TestCase):
    def test_actual_protection_uses_printed_athletics_without_deriving_from_agility(self):
        for footpad,dice,threshold in ((True,3,3),(False,2,2)):
            source=single_source(footpad)
            rng=ScriptedD10([1,10,10]+[10]*dice)
            result=run_pc_melee_scenario(source,rng)
            rng.assert_exhausted()
            proof=next(s.proof for s in result.steps if isinstance(s.proof,PcAttackProof))
            self.assertIs(proof.protection.source_request.selected_skill,Skill.ATHLETICS)
            defender=proof.execution.resolution.attack.defender_test
            self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold),(dice,threshold))
            self.assertEqual(result.source.enemies[0].definition,source.enemies[0].definition)

    def test_npc_dagger_uses_printed_numeric_attack_and_damage(self):
        for footpad,dice,threshold in ((True,3,3),(False,2,2)):
            source=single_source(footpad)
            rng=ScriptedD10([10]*3+[1]*dice+[1]*dice+[10]*3+[1])
            result=run_pc_melee_scenario(source,rng)
            rng.assert_exhausted()
            proof=next(s.proof for s in result.steps if isinstance(s.proof,PcAttackProof)
                and s.proof.request.actor_id not in source.pc_activation_order)
            attack=proof.execution.resolution.attack
            self.assertEqual((attack.attacker_test.trace.rolled_dice,attack.attacker_test.trace.threshold),(dice,threshold))
            self.assertEqual(attack.impact_spec.damage.base,2)
            self.assertEqual(attack.impact_spec.damage_modifiers,())

    def test_known_book_identity_cannot_be_used_to_supply_different_stats(self):
        source=single_source(True)
        enemy=source.enemies[0]
        for changes in ({'protection':(replace(enemy.definition.protection[0],skill=Skill.DEFENCE),)},
                {'attacks':(replace(enemy.definition.attacks[0],test_profile=InlineProfile(4,3)),)},
                {'source_rule_id':'authored:changed-source'}):
            definition=replace(enemy.definition,**changes)
            with self.assertRaises((TypeError,ValueError)):
                replace(source,enemies=(replace(enemy,definition=definition),))
        forged=deepcopy(source)
        object.__setattr__(forged.enemies[0].definition.protection[0],'skill',Skill.DEFENCE)
        with patch('towr.engine.pc_melee_runner.resolve_test') as rng:
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_scenario(forged,Random(42))
            rng.assert_not_called()

    def test_scene_cannot_silently_enable_ambush_or_other_ability_paths(self):
        source=single_source(True)
        for flag in ('targets_aware','no_ambush','no_additional_abilities','no_external_effects'):
            with self.assertRaises(ValueError):
                replace(source,facts=replace(source.facts,**{flag:False}))
        self.assertEqual(PcMeleeSimulationRequest(source,42,1).scenario,source)


if __name__=='__main__':
    unittest.main()
