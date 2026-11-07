"""Literal fresh-battle scripts for Skin Wolf end phases and target lifecycles."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_bestigor_models import PcNpcBloodRageProof, PcBestigorWaveGloriousSource, pc_bestigor_glorious_source
from towr.domain.pc_flagellant_models import PcNpcRecoverProof
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy, PcFeelNoPainPolicy, FEEL_NO_PAIN_RULE_ID
from towr.domain.pc_melee_models import PcMeleeWeapon, PcFatePolicy, PcNearMissPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcWoundCompletionProof, PcEnduranceProof, PcTurnEndProof,
    PcMeleeStep, PcMeleeOutcome, PcMeleeScenarioResult, build_pc_melee_attack,
)
from towr.domain.pc_npc_distraction_models import PcNpcWaveDistractionSource
from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof, PcWarpedFormTargetProof, PcWarpedFormProfileProof,
    PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof, current_warped_form,
    expected_pc_warped_form_activation, next_warped_form_target,
)
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


# Axe Wounds the Wolf, which hits the PC with a superficial Wound then heals.
SINGLE = [1]*3+[10]*4+[1]*5+[10]*3+[1]
# pc1 Wounds Wolf, pc2 misses; Wolf Wounds pc1. Wave visits pc2 first.
TWO_PC_PREFIX = [1]*4+[10]*4+[10]*4+[1]*4+[1]*5+[10]*3+[1]


def scene(*, pcs=1, close=None, order=None, armour=0, rounds=1, **counts):
    source = book_pc_scenario(skin_wolves=counts.pop('skin_wolves', 1),
        footpads=counts.pop('footpads', 0), townsfolk=0, pc_count=pcs, max_rounds=rounds, **counts)
    if close is None:
        close = source.pc_activation_order+tuple(actor for actor in source.enemy_activation_order if actor != 'skin_wolf1')
    policy = PcWarpedFormPolicy('skin_wolf1', close,
        tuple(MinionDefeatDecision('skin_wolf1', actor, NpcDefeatDisposition.KILLED, True)
            for actor in close if actor in source.enemy_activation_order))
    return replace(source, party=tuple(replace(member,
        pc=replace(member.pc, weapon=PcMeleeWeapon.AXE, armour_bonus=armour)) for member in source.party),
        npc_warped_form_policies=(policy,), enemy_activation_order=order or source.enemy_activation_order)


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


class PcWarpedFormExecutionTests(unittest.TestCase):
    def test_own_end_phase_pays_one_stagger_heals_one_without_rng_action_or_self_wave(self):
        result = execute(scene(), SINGLE)
        activation, = steps(result, PcWarpedFormActivationProof)
        self.assertEqual((activation.proof.actor_id, activation.proof.target_ids), ('skin_wolf1', ('pc1',)))
        self.assertEqual((activation.proof.previous_injury.wounds, activation.proof.injury.wounds), (1, 0))
        self.assertFalse(activation.proof.previous_injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(activation.proof.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(activation.source.round_state, activation.state.round_state)
        self.assertEqual((result.executed_actions, len(steps(result, PcAttackProof))), (2, 2))
        self.assertFalse(steps(result, PcNpcRecoverProof))
        self.assertTrue(result.state.enemy('skin_wolf1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 0)
        wave, = steps(result, PcWarpedFormTargetProof)
        self.assertIsNone(wave.proof.result.character_wound)
        self.assertTrue(wave.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)

    def test_activation_cannot_be_replayed_applied_early_or_change_snapshot_cost_heal(self):
        result = execute(scene(), SINGLE)
        activation, = steps(result, PcWarpedFormActivationProof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(activation.state, activation)
        with self.assertRaises(ValueError):
            PcMeleeStep(result.steps[0].source, activation.proof)
        for proof in (replace(activation.proof, activation_id='foreign'),
                replace(activation.proof, target_ids=()),
                replace(activation.proof, injury=activation.proof.previous_injury)):
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                PcMeleeStep(activation.source, proof)
        forged = deepcopy(activation.proof)
        object.__setattr__(forged.injury, 'wounds', 0.0)
        self.assertEqual(forged, activation.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(activation.source, forged)

    def test_wave_must_close_targets_before_end_turn_or_terminal_result(self):
        result = execute(scene(), SINGLE)
        activation, = steps(result, PcWarpedFormActivationProof)
        end, = steps(result, PcWarpedFormEndProof)
        turn_end = result.steps[-1]
        self.assertIs(type(turn_end.proof), PcTurnEndProof)
        for proof in (end.proof, turn_end.proof):
            with self.assertRaises(ValueError):
                PcMeleeStep(activation.state, proof)
        with self.assertRaises(ValueError):
            PcMeleeScenarioResult(result.source, result.steps[:-1], result.outcome)
        with self.assertRaises(ValueError):
            build_pc_melee_attack(activation.state)
        self.assertIsNone(current_warped_form(end.state))
        self.assertIsNone(expected_pc_warped_form_activation(end.state))

    def test_source_order_and_actual_pending_pc_owner_are_independent_of_attack_target(self):
        result = execute(scene(pcs=2, close=('pc2', 'pc1')), TWO_PC_PREFIX+[1])
        first, second = steps(result, PcWarpedFormTargetProof)
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc2', 'pc1'))
        self.assertEqual(first.state.pending_actor_id, 'pc2')
        completion = next(step for step in steps(result, PcWoundCompletionProof)
            if step.source.pending_actor_id == 'pc2')
        self.assertEqual(completion.proof.completion.source_request.roll.source_request.target_id, 'pc2')
        self.assertLess(result.steps.index(first), result.steps.index(completion))
        self.assertLess(result.steps.index(completion), result.steps.index(second))
        self.assertEqual(tuple(len(member.injury.wounds) for member in result.state.party), (1, 1))
        with self.assertRaises(ValueError):
            PcMeleeStep(first.source, second.proof)
        with self.assertRaises(ValueError):
            PcMeleeStep(first.state, second.proof)

    def test_wave_near_miss_burns_only_its_pc_owner_and_retains_staggered(self):
        source = scene(pcs=2, close=('pc2', 'pc1'))
        source = replace(source, party=(source.party[0], replace(source.party[1],
            fate_policy=PcFatePolicy.CONFIGURED, near_miss_policy=PcNearMissPolicy(1, 0))))
        result = execute(source, TWO_PC_PREFIX+[10])
        completion = next(step for step in steps(result, PcWoundCompletionProof)
            if step.source.pending_actor_id == 'pc2')
        self.assertIs(completion.proof.completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(tuple(member.fate.rating for member in result.state.party), (3, 2))
        self.assertEqual(tuple(len(member.injury.wounds) for member in result.state.party), (1, 0))
        self.assertTrue(result.state.participant('pc2').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.pending)

    def test_wave_endurance_and_body_queue_finish_before_next_target(self):
        result = execute(scene(pcs=2, close=('pc2', 'pc1')), TWO_PC_PREFIX+[7]+[10]*3)
        first, second = steps(result, PcWarpedFormTargetProof)
        endurance, = steps(result, PcEnduranceProof)
        self.assertEqual(endurance.source.pending_actor_id, 'pc2')
        self.assertLess(result.steps.index(first), result.steps.index(endurance))
        self.assertLess(result.steps.index(endurance), result.steps.index(second))
        self.assertTrue(result.state.participant('pc2').injury.conditions.has(Condition.BLINDED))
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.BLINDED))

    def test_voluntary_rage_blocks_end_heal_and_retains_actual_wound(self):
        source = replace(scene(), npc_blood_rage_actor_ids=('skin_wolf1',))
        result = execute(source, [1]*3+[10]*4+[1]*6+[10]*3+[1])
        self.assertEqual(len(steps(result, PcNpcBloodRageProof)), 1)
        self.assertFalse(steps(result, PcWarpedFormActivationProof))
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 1)
        self.assertTrue(result.state.enemy('skin_wolf1').state.injury.conditions.has(Condition.STAGGERED))
        wolf = steps(result, PcAttackProof)[1]
        self.assertIsNone(wolf.proof.npc_glorious_source)
        self.assertEqual(wolf.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 6)

    def test_two_actual_wounds_heal_to_one_with_one_self_cost(self):
        result = execute(scene(pcs=2), [1]*4+[10]*4+[1]*4+[10]*4+[1]*5+[10]*3+[1])
        activation, = steps(result, PcWarpedFormActivationProof)
        self.assertEqual((activation.proof.previous_injury.wounds, activation.proof.injury.wounds), (2, 1))
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 1)
        self.assertEqual(len(steps(result, PcWarpedFormEndProof)), 1)

    def test_first_wave_stagger_on_living_defenceless_pc_is_not_automatic_wound(self):
        source = scene(footpads=1, minotaurs=2, armour=3,
            order=('footpad1', 'minotaur1', 'minotaur2', 'skin_wolf1'))
        values = ([1]*3+[10]*4+[1]*4+[10]*3+[1]*5+[10]*3+[10, 10, 1]
            +[1]*5+[10, 9, 1]+[1]*6+[1]*3)
        result = execute(source, values)
        first = steps(result, PcWarpedFormTargetProof)[0]
        self.assertEqual(first.proof.request.target_id, 'pc1')
        self.assertTrue(first.source.participant('pc1').injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(first.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertIsNone(first.proof.result.character_wound)
        self.assertIsNone(first.proof.result.pending_character_wound)
        self.assertEqual(len(result.state.participant('pc1').injury.wounds), 3)
        self.assertTrue(first.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_wave_receipt_readmits_equal_cached_boolean_alias_and_cannot_repeat_end(self):
        result = execute(scene(), SINGLE)
        wave, = steps(result, PcWarpedFormTargetProof)
        forged = deepcopy(wave.proof)
        object.__setattr__(forged.result.stagger, 'wound_requested', 0)
        self.assertEqual(forged, wave.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(wave.source, forged)
        end, = steps(result, PcWarpedFormEndProof)
        with self.assertRaises(ValueError):
            PcMeleeStep(end.state, end.proof)

    def test_escape_fact_retains_actual_range_context_while_strategy_still_suffers_wound(self):
        source = scene(pcs=2, close=('pc2', 'pc1'))
        source = replace(source, facts=replace(source.facts, can_leave_zone=True))
        result = execute(source, TWO_PC_PREFIX+[1])
        first, = tuple(step for step in steps(result, PcWarpedFormTargetProof)
            if step.proof.request.target_id == 'pc2')
        self.assertTrue(first.proof.request.can_target_leave_zone)
        self.assertIsNotNone(first.proof.result.pending_character_wound)
        self.assertFalse(first.proof.result.stagger.gave_ground)

    def test_declined_form_and_healthy_or_missed_actor_do_not_activate(self):
        source = replace(scene(), npc_warped_form_policies=())
        result = execute(source, SINGLE)
        self.assertFalse(steps(result, PcWarpedFormActivationProof))
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 1)
        # Both attacks fail: no Wounds, Wolf's own miss leaves Staggered.
        result = execute(scene(), [10]*3+[1]*4+[10]*5+[1]*3)
        self.assertFalse(steps(result, PcWarpedFormActivationProof))
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 0)

    def test_feel_no_pain_wave_wound_precedes_real_npc_recover_action(self):
        source = scene(flagellant_flails=1)
        source = replace(source, npc_flagellant_policies=(
            PcFlagellantPolicy('flagellant_flails1', PcFeelNoPainPolicy.WOUND_AT_ZERO, True),))
        result = execute(source, [1]*3+[10]*4+[1]*6+[10]*3+[1])
        wave = next(step for step in steps(result, PcWarpedFormTargetProof)
            if step.proof.request.target_id == 'flagellant_flails1')
        ack, = steps(result, PcWarpedFormProfileProof)
        recover, = steps(result, PcNpcRecoverProof)
        self.assertEqual(wave.proof.request.first_stagger_wound.rule_id, FEEL_NO_PAIN_RULE_ID)
        self.assertEqual((ack.proof.source.previous_wounds, ack.proof.source.current_wounds), (0, 1))
        self.assertEqual((recover.proof.previous_injury.wounds, recover.proof.injury.wounds), (1, 0))
        self.assertLess(result.steps.index(ack), result.steps.index(recover))
        self.assertEqual((result.executed_actions, len(steps(result, PcAttackProof))), (3, 2))
        self.assertEqual(recover.proof.execution.slot.declaration.kind.value, 'recover')

    def test_dirty_coward_wave_defeat_has_no_wound_or_fictitious_gm_kill(self):
        result = self.npc_miss_then_wave('goblin1', 3, goblins=1)
        defeat, = steps(result, PcWarpedFormMinionDefeatProof)
        self.assertEqual(defeat.proof.target_id, 'goblin1')
        enemy = result.state.enemy('goblin1')
        self.assertEqual((enemy.state.injury.wounds, enemy.state.injury.defeated), (0, True))
        self.assertIsNotNone(enemy.state.injury.defeat_cause)
        self.assertFalse(enemy.state.wields_weapon)
        self.assertEqual(enemy.state.available_attack_ids, ())
        self.assertFalse(steps(result, PcWarpedFormProfileProof))

    def test_wave_minion_wound_ack_uses_caster_gm_disposition_and_actual_target(self):
        result = self.npc_miss_then_wave('footpad1', 4, footpads=1)
        ack, = steps(result, PcWarpedFormProfileProof)
        self.assertEqual((ack.proof.target_id, ack.proof.source.current_wounds, ack.proof.source.defeated),
            ('footpad1', 1, True))
        self.assertEqual((ack.proof.decision.attacker_id, ack.proof.decision.target_id,
            ack.proof.decision.disposition), ('skin_wolf1', 'footpad1', NpcDefeatDisposition.KILLED))
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.source, replace(ack.proof, target_id='skin_wolf1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.source, replace(ack.proof, decision=replace(ack.proof.decision, attacker_id='pc1')))

    def test_non_attack_w1_preserves_official_merchant_drained_and_prone_effects(self):
        cases = (({'officials':1}, 'official1', 3, Condition.BROKEN),
            ({'merchants':1}, 'merchant1', 5, Condition.STAGGERED),
            ({'big_uns':1}, 'big_un1', 4, Condition.DRAINED),
            ({'centigors':1}, 'centigor1', 5, Condition.PRONE))
        for counts, actor, dice, condition in cases:
            with self.subTest(actor=actor):
                result = self.npc_miss_then_wave(actor, dice, **counts)
                ack, = steps(result, PcWarpedFormProfileProof)
                self.assertEqual(ack.proof.target_id, actor)
                self.assertTrue(result.state.enemy(actor).state.injury.conditions.has(condition))
                self.assertEqual(result.state.enemy(actor).state.injury.wounds, 1)

    def test_official_broken_stop_on_next_own_turn_keeps_wave_source_without_fake_attack(self):
        source = scene(officials=1, order=('official1', 'skin_wolf1'), rounds=2)
        values = ([1]*3+[10]*4+[10]*3+[1]*3+[1]*6+[10]*3+[1]
            +[10]*3+[1]*4)
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.unsupported.actor_id, 'official1')
        self.assertEqual(result.unsupported.reason, 'npc_broken_turn')
        self.assertFalse(hasattr(result.unsupported, 'attack_id'))
        self.assertEqual(result.unsupported.wave_id, steps(result, PcWarpedFormActivationProof)[0].proof.activation_id)
        self.assertEqual(len(steps(result, PcWarpedFormEndProof)), 1)
        self.assertIsNone(result.state.round_state.active_turn)

    def test_bestigor_wave_w1_entitlement_and_brewguard_npc_focus_have_typed_causes(self):
        result = self.npc_miss_then_wave('bestigor1', 4, bestigors=1)
        entitlement = pc_bestigor_glorious_source(result.state, 'bestigor1')
        self.assertIs(type(entitlement), PcBestigorWaveGloriousSource)
        self.assertFalse(hasattr(entitlement, 'wound_attack_id'))
        self.assertEqual(entitlement.wave_id, steps(result, PcWarpedFormActivationProof)[0].proof.activation_id)
        result = self.npc_miss_then_wave('brewguard1', 5, brewguards=1)
        distraction, = result.state.npc_distractions
        self.assertIs(type(distraction), PcNpcWaveDistractionSource)
        self.assertEqual((distraction.actor_id, distraction.focus_actor_id), ('brewguard1', 'skin_wolf1'))
        self.assertFalse(hasattr(distraction, 'attack_id'))

    def test_distinct_own_turns_can_activate_again_but_each_phase_is_once(self):
        source = scene(rounds=3)
        # Seed0 repeatedly wounds the Wolf. Assertions concern explicit lifecycle,
        # not a Monte Carlo proportion or exact aggregate outcome.
        source = replace(source, party=tuple(replace(member,
            pc=replace(member.pc, weapon=PcMeleeWeapon.STAFF)) for member in source.party))
        result = run_pc_melee_scenario(source, Random(0))
        activations = steps(result, PcWarpedFormActivationProof)
        self.assertGreaterEqual(len(activations), 2)
        ids = tuple(step.proof.activation_id for step in activations)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(tuple(step.proof.activation_id for step in steps(result, PcWarpedFormEndProof)), ids)
        for activation in activations:
            self.assertIsNone(expected_pc_warped_form_activation(activation.state))

    def test_last_pc_killed_by_attack_still_runs_eligible_heal_npc_wave_and_turn_end(self):
        source = scene(footpads=2, order=('footpad1', 'footpad2', 'skin_wolf1'))
        values = ([1]*3+[10]*4+[1]*4+[10]*3+[1]
            +[1]*4+[10]*3+[1, 1]+[1]*6+[10]*3+[10]*3)
        result = execute(source, values)
        activation, = steps(result, PcWarpedFormActivationProof)
        self.assertFalse(activation.source.live_party)
        self.assertEqual(activation.proof.target_ids, ('footpad1', 'footpad2'))
        self.assertEqual(tuple(step.proof.request.target_id for step in steps(result, PcWarpedFormTargetProof)),
            ('footpad1', 'footpad2'))
        self.assertIs(type(result.steps[-1].proof), PcTurnEndProof)
        self.assertIsNone(result.state.round_state.active_turn)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)

    def test_last_pc_dies_mid_wave_remaining_npc_targets_and_turn_end_still_finish(self):
        source = scene(footpads=4, armour=6,
            order=('footpad1', 'footpad2', 'footpad3', 'footpad4', 'skin_wolf1'))
        # Four weak Footpad hits produce Stagger/W1/Stagger/W2. Wolf's weak hit
        # adds Stagger; the wave's repeated Stagger rolls lethal third Wound30.
        values = ([1]*3+[10]*4+[1]*4+[10]*3+[1]*4+[10]*3+[1]
            +[1]*4+[10]*3+[1]*4+[10]*3+[1, 1]+[1]+[10]*5+[10]*3+[10]*3)
        result = execute(source, values)
        wave = steps(result, PcWarpedFormTargetProof)
        self.assertEqual(tuple(step.proof.request.target_id for step in wave),
            ('pc1', 'footpad1', 'footpad2', 'footpad3', 'footpad4'))
        self.assertTrue(wave[0].proof.result.pending_character_wound.wound_result.state.dead)
        for later in wave[1:]:
            self.assertFalse(later.source.live_party)
            self.assertTrue(later.state.enemy(later.proof.request.target_id).state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(steps(result, PcWarpedFormEndProof)), 1)
        self.assertIs(type(result.steps[-1].proof), PcTurnEndProof)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)

    def test_unsupported_anatomy_retains_actual_wave_prefix_without_later_targets_or_turn_end(self):
        source = scene(footpads=1, minotaurs=2, armour=3,
            order=('footpad1', 'minotaur1', 'minotaur2', 'skin_wolf1'))
        # Real Devour Wounds20/20 sever both arms. Wolf hits Defenceless PC for
        # W3 total15 (ongoing Staggered). Wave W4 total12 has no anatomical hand.
        values = ([1]*3+[10]*4+[1]*4+[10]*3+[1]*5+[10]*3+[10, 10, 1]
            +[1]*5+[10, 9, 1]+[1]*6+[5]*3+[3]*4)
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual((result.unsupported.actor_id, result.unsupported.reason, result.unsupported.table_total),
            ('pc1', 'unavailable_anatomical_target', 12))
        self.assertEqual(tuple(wound.table_total for wound in result.state.participant('pc1').injury.wounds),
            (20, 20, 15, 12))
        self.assertEqual(result.state.pending_actor_id, 'pc1')
        self.assertTrue(result.state.pending)
        self.assertEqual(len(steps(result, PcWarpedFormActivationProof)), 1)
        self.assertEqual(tuple(step.proof.request.target_id for step in steps(result, PcWarpedFormTargetProof)), ('pc1',))
        self.assertFalse(steps(result, PcWarpedFormEndProof))
        self.assertIsNotNone(current_warped_form(result.state))
        self.assertEqual(result.state.round_state.active_turn.actor_id, 'skin_wolf1')
        self.assertEqual(result.state.enemy('skin_wolf1').state.injury.wounds, 0)
        self.assertFalse(result.state.enemy('footpad1').state.injury.conditions.has(Condition.STAGGERED))

    def npc_miss_then_wave(self, actor, dice, **counts):
        source = scene(order=(actor, 'skin_wolf1'), **counts)
        return execute(source, [1]*3+[10]*4+[10]*dice+[1]*3+[1]*6+[10]*3+[1])
