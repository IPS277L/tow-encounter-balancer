"""Actual heavy-Wound prefixes, typed body evidence and mandatory end phases."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, unavailable_arm_source, unavailable_arm_script
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundConsequence
from towr.domain.pc_heavy_wound_models import PcBodyFactKind
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBodyConsequenceProof, PcHandDropProof, PcHandSwapProof,
    PcIncapacitatedTurnEndProof, PcMeleeOutcome, PcMeleeStep, PcRecoverProof, PcTurnEndProof,
)
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def heavy_prefix(total, *, endurance_success=False, side=1):
    # A miss, then three hits: superficial1, superficial2, actual heavy3d Wound.
    values = [10,10,10,1,1] + [1,1,1,10,10,10,1] + [1,1,1,10,10,10,1,1]
    wound = [1,1,total-2] if total <= 12 else [10,1,total-11] if total <= 21 else [10,10,total-20]
    values += [1,1,1,10,10,10] + wound
    if total == 12:
        values.append(side)
    if total in (11,12,19):
        values += [1,10,10] if endurance_success else [10,10,10]
        if not endurance_success and total == 11:
            values.append(7)
        if not endurance_success and total == 19:
            values.append(side)
    if total in (16,20,21):
        values.append(side)
    return values


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def critical_last_victory():
    source = make_pc_melee_scenario(enemy_count=2,max_rounds=3)
    source = replace(source,party=(replace(source.party[0],pc=replace(source.party[0].pc,endurance=1)),))
    return execute(source,[10,10,10,1,1]
        + [1,1,1,10,10,10,1]
        + [1,1,1,10,10,10,7,7]
        + [1,1,1,10,10] + [1,1,1]
        + [10,10,1,1,1]
        + [1,1,1,10,10] + [10,10,10])


class PcHeavyWoundTests(unittest.TestCase):
    def test_every_heavy_row_completes_actual_lifecycle_and_all_immediate_work(self):
        expected_conditions = {11:Condition.DEAFENED,13:Condition.PRONE,14:Condition.DRAINED,
            15:Condition.STAGGERED,16:Condition.CRITICALLY_INJURED,17:Condition.PRONE,
            18:Condition.CRITICALLY_INJURED,19:Condition.BLINDED,20:Condition.DEFENCELESS,
            21:Condition.DEFENCELESS,22:Condition.DEFENCELESS,23:Condition.BLINDED}
        expected_facts = {11:PcBodyFactKind.LOST_TEETH,12:PcBodyFactKind.INJURED_HAND,
            16:PcBodyFactKind.UNUSABLE_ARM,18:PcBodyFactKind.CLUTCH_STOMACH,
            19:PcBodyFactKind.LOST_EYE,20:PcBodyFactKind.LOST_ARM,21:PcBodyFactKind.LOST_LEG}
        for total in range(11,24):
            with self.subTest(total=total):
                result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=1),heavy_prefix(total))
                member = result.state.party[0]
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                self.assertIsNone(result.unsupported)
                self.assertFalse(result.state.pending)
                self.assertIsNone(result.state.pending_wound)
                self.assertEqual(member.injury.wounds[-1].table_total,total)
                self.assertTrue(member.injury.wounds[-1].effect_resolved)
                self.assertEqual(member.daily_wounds.wound_count,3)
                self.assertEqual(result.executed_actions,4)
                self.assertEqual(member.fate,result.source.party[0].fate)
                if total in expected_conditions:
                    self.assertTrue(member.injury.conditions.has(expected_conditions[total]))
                if total in expected_facts:
                    self.assertIn(expected_facts[total],tuple(f.kind for f in member.body_facts))
                if total == 11:
                    self.assertEqual(member.body_facts[0].count,7)
                if total == 12:
                    self.assertEqual(tuple(f.kind for f in member.body_facts),
                        (PcBodyFactKind.INJURED_HAND,PcBodyFactKind.LOST_FINGER))

    def test_heavy_endurance_success_keeps_conditions_but_avoids_anatomical_loss(self):
        for total in (11,12,19):
            with self.subTest(total=total):
                result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=1),
                    heavy_prefix(total,endurance_success=True))
                facts = result.state.party[0].body_facts
                self.assertEqual(tuple(f.kind for f in facts),
                    (PcBodyFactKind.INJURED_HAND,) if total == 12 else ())
                if total == 19:
                    self.assertTrue(result.state.party[0].injury.conditions.has(Condition.BLINDED))

    def test_torn_leg_recover_and_internal_face_attacks_trigger_critical_before_end_test(self):
        for total in (13,14,15):
            values = heavy_prefix(total)
            if total != 13:
                values += [10,10,10,1,1]
            values += [10,10,10] + [10,10,10]*3
            with self.subTest(total=total):
                result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=2),values)
                member = result.state.party[0]
                self.assertTrue(member.injury.conditions.has(Condition.CRITICALLY_INJURED))
                self.assertTrue(member.injury.conditions.has(Condition.DEFENCELESS))
                self.assertFalse(member.injury.dead)
                critical = [s.proof.critical for s in result.steps if isinstance(s.proof,PcTurnEndProof) and s.proof.critical]
                self.assertEqual(len(critical),1)
                self.assertEqual(critical[0].fate_decline.window,'test')
                if total == 13:
                    self.assertFalse(member.injury.conditions.has(Condition.PRONE))
                if total == 15:
                    self.assertTrue(member.injury.conditions.has(Condition.STAGGERED))

    def test_smashed_hand_recovery_uses_healthy_hand_and_does_not_invent_critical(self):
        result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=2),
            heavy_prefix(12) + [10,10,10,1,1,1]*3)
        self.assertIs(result.state.party[0].weapon_hand,PcWeaponHand.RIGHT)
        self.assertFalse(result.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(sum(isinstance(s.proof,PcRecoverProof) for s in result.steps),1)

    def test_unusable_armed_hand_cannot_defend_then_swaps_on_own_turn(self):
        result = execute(make_pc_melee_scenario(enemy_count=4,max_rounds=2),
            heavy_prefix(16) + [10,10,10,1,1,1]
            + [10,10,10,1,1] + [1,1,1] + [10,10,10,1,1,1]*4)
        fourth = next(s.proof for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'minion4' and s.source.round_state.round_number == 1)
        self.assertIs(fourth.protection.source_request.selected_skill,Skill.ATHLETICS)
        swaps = [s.proof for s in result.steps if isinstance(s.proof,PcHandSwapProof)]
        self.assertEqual(swaps, [PcHandSwapProof(PcWeaponHand.LEFT,PcWeaponHand.RIGHT)])
        self.assertIs(result.state.party[0].weapon_hand,PcWeaponHand.RIGHT)

    def test_repeated_spilling_guts_reuses_existing_clutch_hand(self):
        result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=1),
            [10,10,10,1,1] + [1,1,1,10,10,10,1]
            + [1,1,1,10,10,10,9,9] + [1,1,1,10,10,10,6,6,6])
        member = result.state.party[0]
        self.assertEqual(tuple(f.side for f in member.body_facts), (PcWeaponHand.RIGHT,PcWeaponHand.RIGHT))
        self.assertIs(member.weapon_hand,PcWeaponHand.LEFT)

    def test_defenceless_keeps_empty_turn_and_critical_test_can_kill_without_new_wound(self):
        result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=2),heavy_prefix(20)+[10,10,10])
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        end = result.steps[-1].proof
        self.assertIsInstance(end,PcIncapacitatedTurnEndProof)
        self.assertFalse(end.result.completed_turn.action_slots)
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(result.state.party[0].daily_wounds.wound_count,3)
        self.assertEqual(len(result.state.party[0].injury.wounds),3)

    def test_defenceless_successful_end_test_does_not_restore_action_or_remove_condition(self):
        result = execute(make_pc_melee_scenario(enemy_count=3,max_rounds=2),
            heavy_prefix(23)+[1,1,1]+[10,10,10]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(result.state.party[0].injury.dead)
        self.assertEqual(result.executed_actions,7)

    def test_terminal_victory_cannot_skip_mandatory_critical_end_phase(self):
        result = critical_last_victory()
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertIsInstance(result.steps[-1].proof,PcTurnEndProof)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DEFENCELESS))
        with self.assertRaises(ValueError):
            replace(result,steps=result.steps[:-1])

    def test_body_and_critical_receipts_require_exact_source_types_and_single_application(self):
        result = execute(unavailable_arm_source(),unavailable_arm_script())
        body = next(s for s in result.steps if isinstance(s.proof,PcBodyConsequenceProof))
        self.assertEqual(apply_pc_melee_step(body.source,body),body.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(body.state,body)
        proof = deepcopy(body.proof)
        object.__setattr__(proof,'count',True)
        with self.assertRaises(TypeError):
            PcMeleeStep(body.source,proof)
        victory = critical_last_victory()
        end = victory.steps[-1]
        forged = deepcopy(end.proof)
        object.__setattr__(forged.critical.test_request.profile,'skill',True)
        self.assertEqual(forged.critical.test_request,end.proof.critical.test_request)
        with self.assertRaises(TypeError):
            PcMeleeStep(end.source,forged)

    def test_ongoing_staggered_survives_later_wound_without_duplicate_application(self):
        result = execute(make_pc_melee_scenario(enemy_count=4,max_rounds=1),
            heavy_prefix(15)+[1,1,1,10,10,10,1,1,1,1]+[1,1,1])
        member = result.state.party[0]
        self.assertTrue(member.injury.conditions.has(Condition.STAGGERED))
        effects = [effect for effect in member.injury.active_wound_effects
            if isinstance(effect,WoundConditionEffect) and effect.condition is Condition.STAGGERED]
        self.assertEqual(effects,[WoundConditionEffect(3,Condition.STAGGERED,WoundEffectDuration.UNTIL_HEALED)])
        attack = next(s.proof for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.request.actor_id == 'minion4')
        self.assertTrue(attack.execution.resolution.character_wound.state.conditions.has(Condition.STAGGERED))

    def test_no_anatomical_hand_stops_smashed_hand_but_light_drop_can_do_nothing(self):
        prefix = unavailable_arm_script()[:-4]
        for total,dice,extra in ((12,[3,3,3,3],[]),(4,[1,1,1,1],[10,10,10]),(8,[2,2,2,2],[])):
            with self.subTest(total=total):
                result = execute(unavailable_arm_source(),prefix+dice+extra)
                self.assertEqual(result.state.party[0].daily_wounds.wound_count,4)
                if total == 12:
                    self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
                    self.assertEqual(result.unsupported.table_total,12)
                    self.assertEqual(result.unsupported.reason,'unavailable_anatomical_target')
                else:
                    self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                    self.assertFalse(result.state.pending)

    def test_recover_preserves_independent_prone_source_when_ongoing_prone_blocks_removal(self):
        source = make_pc_melee_scenario(enemy_count=4,max_rounds=2)
        values = ([10,10,10,1,1] + [1,1,1,10,10,10,9]
            + [1,1,1,1,10,10,10,8,9]
            + [1,1,1,1,10,10,10,2,3,3,1]
            + [10,10,10,10,1,1,1]
            + [1,1,1] + [10,10,10,10,1,1,1]*4)
        result = execute(source,values)
        recover = next(s for s in result.steps if isinstance(s.proof,PcRecoverProof))
        self.assertIsNone(recover.proof.result.source_request.choice.prone_target)
        self.assertIn(WoundConditionEffect(1,Condition.PRONE,WoundEffectDuration.UNTIL_REMOVED),
            recover.state.party[0].injury.active_wound_effects)
        self.assertTrue(recover.state.party[0].injury.conditions.has(Condition.PRONE))


class IncidentalHandUseTests(unittest.TestCase):
    def check_incidental_use(self, mode, danger):
        source = make_pc_melee_scenario(enemy_count=3 if danger is None else 4,max_rounds=2)
        values = [10,10,10,1,1] + [1,1,1,10,10,10,1]
        if danger is not None:
            values += [1,1,1,10,10,10] + ([7,7] if danger == 14 else [7,8])
        values += [1,1,1,10,10,10] + ([6,6] if danger is None else [4,4,4]) + [10,1,10,10]
        if mode == 'swap':
            values += [1,1,1,10,10,10] + ([5,5,6] if danger is None else [4,4,4,4]) + [1]
        else:
            values += [1,1,1,10,10,10] + ([6,6,6] if danger is None else [4,4,5,5])
        values += [10,10,10,1,1] + [1,1,1] + [10,10,10,1,1,1] * len(source.enemies)
        result = execute(source,values)
        index,step = next((i,item) for i,item in enumerate(result.steps) if (
            isinstance(item.proof,PcHandSwapProof) if mode == 'swap' else
            isinstance(item.proof,PcBodyConsequenceProof) and item.proof.source.consequence
                is WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH))
        def sources(state):
            return tuple(effect.wound_sequence for effect in state.party[0].injury.active_wound_effects
                if isinstance(effect,WoundConditionEffect) and effect.condition is Condition.CRITICALLY_INJURED)
        expected = (3,2) if danger is None else (4,2,3)
        self.assertEqual(sources(step.source),(3,) if danger is None else (4,))
        self.assertEqual(sources(step.state),expected)
        attack = next(item for item in result.steps[index+1:] if isinstance(item.proof,PcAttackProof))
        self.assertEqual(sources(attack.state),expected)

    def test_incidental_weapon_swap_immediately_binds_hand_and_nonrecover_sources(self):
        for danger in (None,14,15):
            with self.subTest(danger=danger):
                self.check_incidental_use('swap',danger)

    def test_voluntary_clutch_immediately_binds_hand_and_nonrecover_sources(self):
        for danger in (None,14,15):
            with self.subTest(danger=danger):
                self.check_incidental_use('clutch',danger)


if __name__ == '__main__':
    unittest.main()
