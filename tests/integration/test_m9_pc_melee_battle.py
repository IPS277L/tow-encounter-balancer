"""Actual PC/Minion combat and mandatory Wounds1–10, not mocked outcomes."""
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, blind_expiry_script, first_wound_script, run_first_wound
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSessionState, FateSpendKind, FateSpendRecord
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRestriction, WoundRestrictionEffect
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcEnduranceProof, PcHandDropProof, PcMeleeOutcome,
    PcRecoverProof, PcTurnEndProof, PcWoundCompletionProof,
)
from towr.domain.test_models import FATE_GLORIOUS_RULE_ID, Skill, TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario


class PcMeleeBattleTests(unittest.TestCase):
    def test_every_first_wound_one_to_ten_is_completed_with_actual_required_work(self):
        for total in range(1,11):
            with self.subTest(total=total):
                result = run_first_wound(total)
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                state = result.state
                self.assertEqual([w.table_total for w in state.pc_injury.wounds],[total])
                self.assertTrue(state.pc_injury.wounds[0].effect_resolved)
                self.assertEqual(state.daily_wounds.wound_count,1)
                self.assertEqual(state.fate,result.source.fate)
                self.assertEqual(state.fate.rating,3)
                self.assertFalse(state.pc_injury.conditions.has(Condition.STAGGERED))
                expected = {5:{Condition.PRONE},6:{Condition.DRAINED},7:{Condition.BLINDED},
                    9:{Condition.PRONE},10:{Condition.DRAINED}}.get(total,set())
                self.assertEqual(state.pc_injury.conditions.conditions,expected)
                self.assertEqual(sum(isinstance(s.proof,PcEnduranceProof) for s in result.steps),int(total in (4,5,7)))
                self.assertEqual(sum(isinstance(s.proof,PcHandDropProof) for s in result.steps),int(total in (4,8)))
                if total in (4,8):
                    self.assertIsNone(state.weapon_hand)
                else:
                    self.assertIs(state.weapon_hand,PcWeaponHand.LEFT)
                restrictions = {e.restriction for e in state.pc_injury.active_wound_effects if isinstance(e,WoundRestrictionEffect)}
                self.assertEqual(restrictions,{8:{WoundRestriction.CANNOT_AIM},9:{WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN},
                    10:{WoundRestriction.NEXT_TEST_IS_GRIM}}.get(total,set()))

    def test_endurance_success_avoids_drop_prone_and_blinded_without_random_hand_roll(self):
        for total in (4,5,7):
            with self.subTest(total=total):
                result = run_first_wound(total,endurance_success=True)
                self.assertEqual(result.state.pc_injury.conditions.conditions,frozenset())
                self.assertIs(result.state.weapon_hand,PcWeaponHand.LEFT)
                self.assertFalse(any(isinstance(s.proof,PcHandDropProof) for s in result.steps))

    def test_random_empty_hand_does_not_drop_the_other_hand_weapon(self):
        for total in (4,8):
            result = run_first_wound(total,hand=10)
            self.assertIs(result.state.weapon_hand,PcWeaponHand.LEFT)
            drop = next(s.proof for s in result.steps if isinstance(s.proof,PcHandDropProof))
            self.assertEqual(drop.die,10)
            self.assertIs(drop.hand,PcWeaponHand.RIGHT)

    def test_lost_weapon_uses_athletics_then_one_standard_recover_restores_it(self):
        source = make_pc_melee_scenario(enemy_count=2,max_rounds=2)
        values = [10,10,10,1,1, 1,1,1,10,10,10,8,1,
            10,10,10,1,1,1, 10,10,10,1,1,1, 10,10,10,1,1,1]
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        unarmed = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'minion2' and s.source.round_state.round_number == 1)
        self.assertIsNone(unarmed.source.weapon_hand)
        self.assertIs(unarmed.proof.protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertEqual(unarmed.proof.execution.resolution.attack.defender_test.trace.threshold,source.pc.athletics)
        recover = next(s for s in result.steps if isinstance(s.proof,PcRecoverProof))
        self.assertTrue(recover.proof.result.source_request.actor_has_enemy_in_zone)
        self.assertIs(recover.state.weapon_hand,PcWeaponHand.LEFT)
        self.assertEqual(recover.proof.result.slot.index,1)
        self.assertEqual(recover.state.fate,source.fate)
        self.assertEqual(result.executed_actions,6)

    def test_blinded_makes_visual_attack_grim_then_expires_at_next_own_turn_end(self):
        source = make_pc_melee_scenario(max_rounds=2)
        rng = ScriptedD10(blind_expiry_script())
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        own = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'pc' and s.source.round_state.round_number == 2)
        self.assertIs(own.proof.execution.resolution.attack.attacker_test.trace.quality,TestQuality.GRIM)
        self.assertEqual(len(own.proof.execution.resolution.attack.attacker_test.trace.rerolls),2)
        end = next(s for s in result.steps if isinstance(s.proof,PcTurnEndProof)
            and s.proof.result.completed_turn.actor_id == 'pc' and s.source.round_state.round_number == 2)
        self.assertTrue(end.source.pc_injury.conditions.has(Condition.BLINDED))
        self.assertFalse(end.state.pc_injury.conditions.has(Condition.BLINDED))
        self.assertFalse(end.state.timed_wounds)

    def test_temporary_drained_expiry_preserves_the_independent_crushed_rib_source(self):
        source = make_pc_melee_scenario(enemy_count=2,max_rounds=2)
        values = [10,10,10,1,1, 1,1,1,10,10,10,6, 1,1,1,10,10,10,5,5,
            10,10,10,1,1, 10,10,10,1,1,1, 10,10,10,1,1,1]
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        end = next(s for s in result.steps if isinstance(s.proof,PcTurnEndProof)
            and s.proof.result.completed_turn.actor_id == 'pc' and s.source.round_state.round_number == 2)
        self.assertTrue(end.state.pc_injury.conditions.has(Condition.DRAINED))
        self.assertFalse(end.state.timed_wounds)
        self.assertEqual([(e.wound_sequence,e.duration) for e in end.state.pc_injury.active_wound_effects
            if isinstance(e,WoundConditionEffect) and e.condition is Condition.DRAINED],[(2,WoundEffectDuration.UNTIL_TREATED)])
        self.assertFalse(any(isinstance(e,WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM
            for e in end.state.pc_injury.active_wound_effects))

    def test_crushed_rib_next_attack_is_grim_and_drained_blocks_sword_bonus(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD,max_rounds=2)
        values = first_wound_script(10) + [1,10,10,1,1,10, 1,1,1,1,10]
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        own = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'pc' and s.source.round_state.round_number == 2)
        self.assertIs(own.proof.execution.resolution.attack.attacker_test.trace.quality,TestQuality.GRIM)
        enemy = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'minion1' and s.source.round_state.round_number == 2)
        self.assertFalse(enemy.source.pc_injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(enemy.source.pc_injury.conditions.has(Condition.DRAINED))
        self.assertEqual(enemy.proof.request.kernel_request.attack.defender_test.dice_modifiers,())
        self.assertIs(enemy.proof.execution.resolution.attack.defender_test.trace.quality,TestQuality.NORMAL)

    def test_lethal_player_wound_is_completed_after_near_miss_decline_with_spent_fate(self):
        source = make_pc_melee_scenario(enemy_count=3,max_rounds=6)
        spend = FateSpendRecord('earlier','session','pc',FateSpendKind.GLORIOUS_TEST,'earlier-test',FATE_GLORIOUS_RULE_ID)
        source = replace(source,fate=FateSessionState('session','pc',3,1,spends=(spend,)))
        self.assertEqual(source.fate.remaining_spends,0)
        result = run_pc_melee_scenario(source,Random(16))
        self.assertIs(result.outcome,PcMeleeOutcome.PC_DEFEATED)
        last = next(s for s in reversed(result.steps) if isinstance(s.proof,PcWoundCompletionProof))
        self.assertTrue(last.source.pc_injury.dead)
        self.assertIsNotNone(last.source.pending_wound)
        self.assertTrue(last.source.pending_wound.near_miss_eligible)
        self.assertEqual(last.proof.fate_decline.window,'wound')
        self.assertIsNone(last.state.pending_wound)
        self.assertEqual(last.state.fate,source.fate)
        self.assertEqual(last.state.daily_wounds.wound_count,len(last.state.pc_injury.wounds))
        self.assertFalse(last.state.fate.burns)

    def test_heavy_unsupported_wound_keeps_its_unresolved_lifecycle_and_daily_prefix(self):
        source = make_pc_melee_scenario(enemy_count=3,max_rounds=6)
        result = run_pc_melee_scenario(source,Random(4))
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        pending = result.state.pending_wound
        self.assertIsNotNone(pending)
        self.assertEqual(result.unsupported.source_id,pending.request_id)
        self.assertTrue(11 <= result.unsupported.table_total <= 23)
        self.assertFalse(result.state.pc_injury.wounds[-1].effect_resolved)
        self.assertEqual(result.state.daily_wounds.wound_count,len(result.state.pc_injury.wounds)-1)
        with self.assertRaises(ValueError):
            replace(result,outcome=PcMeleeOutcome.PC_DEFEATED)


if __name__=='__main__':
    unittest.main()
