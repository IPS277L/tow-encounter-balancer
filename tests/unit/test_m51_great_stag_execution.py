"""Full journals bind Crown to new Prone and execute the actual same-target Trample."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcFatePolicy, PcNearMissPolicy, PcGloriousPolicy, PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcEnduranceProof, PcMeleeOutcome, PcMeleeStep, PcProfileWoundProof,
    PcTurnEndProof, PcWoundCompletionProof, pc_melee_action_id,
)
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionSlotResult, CombatTurnEndRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.turn_resolution import end_combat_turn


ACTOR = 'great_stag1'
PC_MISS = [10]*3+[1]*5
ANTLERS = [1]*4+[10]*3
TRAMPLE_MISS = [10]*6+[1]*3


def scene(*, pcs=1, rounds=1, enabled=True, **counts):
    source = book_pc_scenario(great_stags=1, footpads=counts.pop('footpads', 0), townsfolk=0,
        pc_count=pcs, max_rounds=rounds, **counts)
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_extra_attack_actor_ids=(ACTOR,) if enabled else ())


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def incoming(result):
    return tuple(step for step in steps(result, PcAttackProof) if step.proof.request.actor_id == ACTOR)


class PcGreatStagExecutionTests(unittest.TestCase):
    def test_leg_spasm_grants_real_same_target_brawn_trample_and_one_turn_end(self):
        result = execute(scene(pcs=2), PC_MISS*2+ANTLERS+[9]+TRAMPLE_MISS)
        first, second = incoming(result)
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc1', 'pc1'))
        self.assertEqual((first.proof.execution.slot_index, second.proof.execution.slot_index), (1, 2))
        self.assertFalse(first.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(second.source.pending)
        self.assertIsNone(second.source.pending_wound)
        grant = second.proof.execution.slot.crown_of_antlers
        self.assertEqual(type(grant).__name__, 'CrownOfAntlersGrant')
        self.assertEqual((grant.first_target_id, grant.target_id, grant.attack_id), ('pc1', 'pc1', 'trample'))
        self.assertIsNone(second.proof.execution.slot.enduring_strength)
        self.assertEqual(second.proof.protection.source_request.attack_skill, Skill.BRAWN)
        self.assertEqual(second.proof.protection.source_request.selected_skill, Skill.ENDURANCE)
        raw = second.proof.execution.resolution.attack
        self.assertEqual((raw.attacker_test.trace.base_dice, raw.attacker_test.trace.pool_cap,
            raw.attacker_test.trace.rolled_dice), (5, 10, 6))
        self.assertEqual(raw.impact_spec.damage.base, 5)
        self.assertEqual(raw.defender_test.trace.threshold, 4)
        self.assertNotEqual(first.proof.request.id, second.proof.request.id)
        self.assertEqual(sum(step.proof.result.completed_turn.actor_id==ACTOR
            for step in steps(result, PcTurnEndProof)), 1)
        self.assertEqual(result.executed_actions, 4)

    def test_failed_battered_leg_endurance_closes_before_crown_reservation(self):
        result = execute(scene(), PC_MISS+ANTLERS+[5]+[10]*3+TRAMPLE_MISS)
        first, second = incoming(result)
        endurance, = steps(result, PcEnduranceProof)
        self.assertLess(result.steps.index(first), result.steps.index(endurance))
        self.assertLess(result.steps.index(endurance), result.steps.index(second))
        self.assertTrue(endurance.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(second.source.pending)
        self.assertEqual(len(incoming(result)), 2)

    def test_successful_battered_leg_endurance_does_not_grant_trample(self):
        result = execute(scene(), PC_MISS+ANTLERS+[5]+[1]*3)
        self.assertEqual(len(incoming(result)), 1)
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))

    def test_torn_leg_and_shattered_knee_from_accepted_second_wound_can_trigger_crown(self):
        for dice, total in (([6, 7], 13), ([8, 9], 17)):
            source = scene(footpads=1)
            source = replace(source, enemy_activation_order=('footpad1', ACTOR))
            result = execute(source, PC_MISS+[1]*3+[10]*3+[1]+ANTLERS+dice+TRAMPLE_MISS)
            first, second = incoming(result)
            self.assertEqual(second.source.participant('pc1').injury.wounds[-1].table_total, total)
            self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.PRONE))
            self.assertEqual(first.proof.request.target_id, second.proof.request.target_id)

    def test_near_miss_negates_only_prone_cause_and_no_grant_survives(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1, 0)),))
        result = execute(source, PC_MISS+ANTLERS+[9])
        self.assertEqual(len(incoming(result)), 1)
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(result.state.participant('pc1').injury.wounds, ())
        self.assertEqual(result.state.participant('pc1').fate.rating, 2)
        self.assertEqual(len(steps(result, PcWoundCompletionProof)), 1)

    def test_superficial_wound_and_miss_do_not_invent_prone_or_grant(self):
        for attack in (ANTLERS+[1], [10]*4+[1]*3, [10]*7):
            result = execute(scene(), PC_MISS+attack)
            self.assertEqual(len(incoming(result)), 1)
            self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))

    def test_positive_tie_without_wound_is_not_a_prone_trigger(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc,
            toughness=10, strength=1)),))
        values = [1, 10, 10]+[1]+[10]*4+[1, 10, 10, 10]+[1, 10, 10]
        result = execute(source, values)
        first, = incoming(result)
        self.assertTrue(first.proof.execution.resolution.attack.tie_break_applied)
        self.assertIsNone(first.proof.execution.resolution.character_wound)
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))

    def test_empty_policy_declines_crown_but_keeps_actual_wound_prone(self):
        result = execute(scene(enabled=False), PC_MISS+ANTLERS+[9])
        self.assertEqual(len(incoming(result)), 1)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))

    def test_already_prone_from_another_actor_and_another_prone_wound_do_not_trigger(self):
        source = scene(crushing_bears=1)
        source = replace(source, enemy_activation_order=('crushing_bear1', ACTOR))
        result = execute(source, PC_MISS+[1]*3+[10]*3+[1]+[1]*5+[10]*3+[4, 5])
        first, = incoming(result)
        self.assertTrue(first.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(result.state.participant('pc1').injury.wounds[-1].table_total, 9)
        self.assertEqual(len(incoming(result)), 1)

    def test_wound_one_has_no_drained_and_wound_two_suppresses_trample_higher_ground_bonus(self):
        source = scene(pcs=2)
        source = replace(source, party=tuple(replace(m, pc=replace(m.pc, weapon=PcMeleeWeapon.AXE))
            for m in source.party))
        result = execute(source, ([1]*3+[10]*5)*2+ANTLERS+[9]+[10]*5+[1]*3)
        acks = steps(result, PcProfileWoundProof)
        self.assertFalse(acks[0].state.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED))
        self.assertTrue(acks[1].state.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED))
        first, second = incoming(result)
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 4)
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 5)
        self.assertEqual(second.proof.execution.resolution.attack.impact_spec.damage.base, 5)

    def test_endurance_protection_uses_actual_glorious_fate_skill(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.ENDURANCE,), 0, 0)),))
        result = execute(source, PC_MISS+ANTLERS+[9]+[1]*6+[10]*3+[1]*3+[1, 1])
        first, second = incoming(result)
        self.assertIsNone(first.proof.glorious)
        self.assertIsNotNone(second.proof.glorious)
        self.assertEqual(second.proof.protection.source_request.selected_skill, Skill.ENDURANCE)
        self.assertEqual(len(result.state.participant('pc1').fate.spends), 1)
        self.assertEqual(second.proof.execution.resolution.attack.defender_test.successes, 3)

    def test_npc_help_bound_to_antlers_is_not_copied_to_trample(self):
        source = scene(peasants=1)
        source = replace(source, enemy_activation_order=('peasant1', ACTOR),
            npc_help_policies=(PcNpcHelpPolicy('peasant1', ACTOR),))
        result = execute(source, PC_MISS+[1]*5+[10]*3+[9]+TRAMPLE_MISS)
        first, second = incoming(result)
        self.assertEqual(len(first.proof.npc_help_applications), 1)
        self.assertEqual(second.proof.npc_help_applications, ())
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.cap_bypassing_dice, 1)
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.cap_bypassing_dice, 0)

    def test_pending_lifecycle_and_available_crown_cannot_be_skipped_or_replayed(self):
        result = execute(scene(), PC_MISS+ANTLERS+[9]+TRAMPLE_MISS)
        first, second = incoming(result)
        self.assertIsNotNone(first.state.pending_wound)
        with self.assertRaises(ValueError):
            build_pc_npc_extra_attack_slot(first.state)
        reservation = next(step for step in steps(result, CombatActionSlotResult) if step.proof.slot.index==2)
        current = reservation.source
        ended = end_combat_turn(CombatTurnEndRequest(pc_melee_action_id(current, ACTOR)+':end',
            current.round_state, ACTOR))
        with self.assertRaises(ValueError):
            PcMeleeStep(current, PcTurnEndProof(ended, None))
        with self.assertRaises(ValueError):
            apply_pc_melee_step(second.state, second)
        forged = deepcopy(second.proof)
        object.__setattr__(forged.protection.source_request, 'selected_skill', Skill.DEFENCE)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(second.source, forged)
        forged = deepcopy(second.proof)
        object.__setattr__(forged.execution.slot.crown_of_antlers, 'round_number', True)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(second.source, forged)

    def test_wave_second_wound_applies_drained_from_actual_target_scoped_ack(self):
        source = scene(pcs=2, skin_wolves=1)
        party = []
        for member, target in zip(source.party, (ACTOR, 'skin_wolf1')):
            priorities = (target, 'skin_wolf1' if target==ACTOR else ACTOR)
            party.append(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.AXE),
                target_priority=priorities, defeat_decisions=tuple(member.defeat_decision(a) for a in priorities)))
        source = replace(source, party=tuple(party), enemy_activation_order=(ACTOR, 'skin_wolf1'),
            npc_warped_form_policies=(PcWarpedFormPolicy('skin_wolf1', ('pc1', 'pc2', ACTOR),
                (MinionDefeatDecision('skin_wolf1', ACTOR, NpcDefeatDisposition.KILLED, True),)),))
        result = execute(source, [1]*3+[10]*5+[1]*3+[10]*4+[10]*4+[1]*3+[1]*5+[10]*3+[1])
        ack, = steps(result, PcWarpedFormProfileProof)
        self.assertEqual((ack.proof.target_id, ack.proof.source.previous_wounds,
            ack.proof.source.current_wounds), (ACTOR, 1, 2))
        self.assertTrue(ack.state.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED))

    def test_first_target_death_does_not_redirect_to_another_live_pc(self):
        source = scene(pcs=2, footpads=2)
        source = replace(source, enemy_activation_order=('footpad1', 'footpad2', ACTOR))
        values = PC_MISS*2+[1]*3+[10]*3+[1]+[1]*3+[10]*3+[1, 1]+ANTLERS+[10]*3
        result = execute(source, values)
        self.assertTrue(result.state.participant('pc1').injury.dead)
        self.assertFalse(result.state.participant('pc2').injury.dead)
        self.assertEqual(len(incoming(result)), 1)
        self.assertIs(type(result.steps[-1].proof), PcTurnEndProof)
        self.assertEqual(result.steps[-1].proof.result.completed_turn.actor_id, ACTOR)

    def test_last_pc_death_closes_great_stag_turn_before_terminal_result(self):
        source = scene(footpads=2)
        source = replace(source, enemy_activation_order=('footpad1', 'footpad2', ACTOR))
        values = PC_MISS+[1]*3+[10]*3+[1]+[1]*3+[10]*3+[1, 1]+ANTLERS+[10]*3
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
        self.assertTrue(result.state.participant('pc1').injury.dead)
        self.assertEqual(len(incoming(result)), 1)
        self.assertIs(type(result.steps[-1].proof), PcTurnEndProof)
        self.assertEqual(result.steps[-1].proof.result.completed_turn.actor_id, ACTOR)

    def test_living_defenceless_prone_target_can_receive_unopposed_trample(self):
        source = scene(pcs=2, footpads=1, minotaurs=2)
        source = replace(source, enemy_activation_order=('footpad1', 'minotaur1', 'minotaur2', ACTOR))
        prefix = (PC_MISS*2+[1]*3+[10]*3+[1]+[1]*4+[10]*3+[10, 9, 1]+[1]
            +[1]*4+[10, 8, 1, 1])
        result = execute(source, prefix+[1]*4+[2, 2, 2, 3]+[10]*6)
        first, second = incoming(result)
        member = second.source.participant('pc1')
        self.assertFalse(member.injury.dead)
        self.assertTrue(member.injury.conditions.has(Condition.DEFENCELESS))
        self.assertTrue(member.injury.conditions.has(Condition.PRONE))
        self.assertIsNone(second.proof.protection.source_request.selected_skill)
        self.assertIsNone(second.proof.execution.resolution.attack.defender_test)
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc1', 'pc1'))

    def test_unsupported_body_queue_preserves_first_attack_prefix_and_no_trample(self):
        source = scene(pcs=2, footpads=1, minotaurs=2)
        source = replace(source, enemy_activation_order=('footpad1', 'minotaur1', 'minotaur2', ACTOR))
        values = (PC_MISS*2+[1]*3+[10]*3+[1]+[1]*4+[10]*3+[10, 9, 1]+[1]
            +[1]*4+[10, 8, 1, 1]+[1]*4+[3]*4)
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.unsupported.reason, 'unavailable_anatomical_target')
        self.assertTrue(result.state.pending)
        self.assertEqual(len(incoming(result)), 1)
        self.assertFalse(any(step.proof.slot.index==2 for step in steps(result, CombatActionSlotResult)))


if __name__ == '__main__':
    unittest.main()
