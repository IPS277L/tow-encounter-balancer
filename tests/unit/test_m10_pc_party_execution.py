"""One shared PC-party battle, actor-bound consequences and actual losses."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario, replace_pc_melee_member
from tests.support.pc_melee_scripted import ScriptedD10, party_casualty_source, party_casualty_script
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSessionState
from towr.domain.injury_models import WoundRestriction, WoundRestrictionEffect
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcRecoverProof,
    PcTurnEndProof, PcWoundCompletionProof,
)
from towr.domain.test_models import TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def run_script(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def drops_second_pc():
    source = make_pc_melee_party_scenario(max_rounds=2)
    source = replace(source, enemy_target_priority=('pc2', 'pc1'))
    return run_script(source,
        [10,10,10,1,1] * 2
        + [1,1,10,10,10,8,1]
        + [10,10,1,1,1]
        + [10,10,10,1,1]
        + [10,10,1,1,1] * 2)


class PcPartyExecutionTests(unittest.TestCase):
    def test_copied_historical_proofs_cannot_hide_equal_but_different_value_types(self):
        result = run_script(party_casualty_source(),party_casualty_script())
        index = next(i for i,step in enumerate(result.steps)
            if any(isinstance(proof,PcAttackProof) for proof in step.source.history))
        original = result.steps[index]
        for field in ('source','state'):
            forged = deepcopy(original)
            snapshot = deepcopy(getattr(original,field))
            historical = next(proof for proof in snapshot.history if isinstance(proof,PcAttackProof))
            trace = historical.execution.resolution.attack.attacker_test.trace
            self.assertEqual(trace.success_delta,0)
            object.__setattr__(trace,'success_delta',False)
            self.assertEqual(snapshot,getattr(original,field))
            object.__setattr__(forged,field,snapshot)
            with self.subTest(field=field),self.assertRaises(TypeError):
                apply_pc_melee_step(original.source,forged)
            steps = (*result.steps[:index],forged,*result.steps[index+1:])
            with self.subTest(result_field=field),self.assertRaises(TypeError):
                replace(result,steps=steps)

    def test_each_members_transported_priorities_and_defeat_decisions_are_canonical(self):
        source = make_pc_melee_party_scenario()
        for field in ('target_priority','defeat_decisions'):
            forged = deepcopy(source)
            object.__setattr__(forged.party[1],field,list(getattr(forged.party[1],field)))
            with self.subTest(field=field),self.assertRaises(TypeError):
                validate_pc_melee_scenario_admission(forged)

    def test_casualty_closes_lifecycle_then_retargets_and_survivor_takes_next_turn(self):
        source = party_casualty_source()
        result = run_script(source, party_casualty_script())
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(result.defeated_pc_ids, ('pc1',))
        self.assertEqual(result.executed_actions, 10)
        self.assertEqual((result.started_rounds, result.completed_rounds), (2, 2))
        self.assertEqual(tuple(m.actor_id for m in result.state.live_party), ('pc2',))
        completion = next(s for s in result.steps if isinstance(s.proof, PcWoundCompletionProof)
            and s.proof.completion.state.dead)
        self.assertEqual(completion.source.pending_actor_id, 'pc1')
        self.assertIsNotNone(completion.source.pending_wound)
        self.assertTrue(completion.source.participant('pc1').injury.dead)
        self.assertIsNone(completion.state.pending_wound)
        retarget = next(s for s in result.steps if isinstance(s.proof, PcAttackProof)
            and s.proof.request.actor_id == 'minion4' and s.source.round_state.round_number == 1)
        self.assertEqual(retarget.proof.request.target_id, 'pc2')
        attacks_next_round = [s.proof.request.actor_id for s in result.steps
            if isinstance(s.proof, PcAttackProof) and s.source.round_state.round_number == 2]
        self.assertEqual(attacks_next_round, ['pc2', 'minion2', 'minion3', 'minion4'])
        self.assertNotIn('pc1', tuple(p.entity_id for p in result.state.round_state.participants))
        self.assertEqual(result.state.participant('pc1').daily_wounds.wound_count, 3)
        self.assertEqual(result.state.participant('pc2').daily_wounds.wound_count, 0)
        for member in source.party:
            self.assertEqual(result.state.participant(member.actor_id).fate, member.fate)

    def test_all_pc_deaths_complete_their_own_lifecycles_before_party_defeat(self):
        source = make_pc_melee_party_scenario(pc_count=2, enemy_count=7, max_rounds=1)
        wound_triplet = ([1,1,1,10,10,10,1]
            + [1,1,1,10,10,10,1,1]
            + [1,1,1,10,10,10,10,10,10])
        result = run_script(source, [10,10,10,1,1] * 2 + wound_triplet * 2)
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
        self.assertEqual(result.defeated_pc_ids, ('pc1', 'pc2'))
        self.assertEqual(result.executed_actions, 8)
        self.assertFalse(result.state.live_party)
        self.assertIsNone(result.state.pending_wound)
        self.assertIsNone(result.state.pending_actor_id)
        self.assertEqual([m.daily_wounds.wound_count for m in result.state.party], [3, 3])
        deaths = [s for s in result.steps if isinstance(s.proof, PcWoundCompletionProof)
            and s.proof.completion.state.dead]
        self.assertEqual([s.proof.fate_decline.actor_id for s in deaths], ['pc1', 'pc2'])
        self.assertEqual([s.proof.fate_decline.window for s in deaths], ['wound', 'wound'])
        self.assertEqual([s.proof.result.source_request.actor_id for s in result.steps
            if isinstance(s.proof, PcRecoverProof)], [])

    def test_unsupported_second_pc_keeps_actor_pending_source_and_first_pc_confirmed_death(self):
        source = make_pc_melee_party_scenario(pc_count=2, enemy_count=7, max_rounds=1)
        result = run_script(source, [10,10,10,1,1] * 2
            + [1,1,1,10,10,10,1]
            + [1,1,1,10,10,10,1,1]
            + [1,1,1,10,10,10,10,10,10]
            + [1,1,1,10,10,10,1]
            + [1,1,1,10,10,10,10,10,1]
            + [1,1,1,7,7,6]
            + [1,1,1,5,5,5,5])
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.unsupported.actor_id, 'pc2')
        self.assertEqual(result.unsupported.table_total, 20)
        self.assertEqual(result.state.pending_actor_id, 'pc2')
        self.assertIsNone(result.state.pending_wound)
        self.assertEqual(result.state.pending[0].wound_sequence,4)
        self.assertEqual(result.defeated_pc_ids, ('pc1',))
        self.assertEqual(result.state.participant('pc2').daily_wounds.wound_count, 4)
        self.assertTrue(result.state.participant('pc2').injury.wounds[-1].effect_resolved)
        with self.assertRaises(ValueError):
            replace(result, unsupported=replace(result.unsupported, actor_id='pc1'))

    def test_outnumbering_changes_after_a_minion_falls_before_the_next_pc_attack(self):
        source = make_pc_melee_party_scenario(max_rounds=1)
        result = run_script(source, [1,1,1,10,10] + [10,10,10,10,1,1] + [10,10,1,1,1])
        attacks = [s.proof for s in result.steps if isinstance(s.proof, PcAttackProof)]
        self.assertEqual([a.request.actor_id for a in attacks], ['pc1', 'pc2', 'minion2'])
        self.assertEqual([a.execution.resolution.attack.attacker_test.trace.regular_dice_delta
            for a in attacks], [0, 1, 0])
        self.assertEqual(attacks[1].execution.resolution.attack.attacker_test.trace.rolled_dice, 4)

    def test_outnumbering_recalculates_after_pc_death_within_the_enemy_side(self):
        source = make_pc_melee_party_scenario(max_rounds=2)
        result = run_script(source,
            [10,10,10,1,1] * 2
            + [1,1,10,10,10,1] + [1,1,10,10,10,1,1]
            + [10,10,10,1,1] * 2
            + [1,1,10,10,10,10,10,10] + [10,10,10,1,1,1])
        attacks = [s for s in result.steps if isinstance(s.proof, PcAttackProof)
            and s.proof.request.actor_id == 'minion2']
        self.assertEqual([s.proof.execution.resolution.attack.attacker_test.trace.regular_dice_delta
            for s in attacks], [0, 1])
        self.assertEqual([s.proof.request.target_id for s in attacks], ['pc1', 'pc2'])
        self.assertEqual(result.defeated_pc_ids, ('pc1',))

    def test_drained_blocks_pc_outnumbering_and_an_ally_test_does_not_consume_grim(self):
        source = make_pc_melee_party_scenario(max_rounds=2)
        source = replace(source, enemy_target_priority=('pc2', 'pc1'))
        result = run_script(source,
            [1,1,1,10,10] + [10,10,10,10,1,1] + [1,1,10,10,10,10]
            + [10,10,10,10,1,1] + [1,10,10,10,1,1] + [10,10,1,1,1])
        attacks = [s for s in result.steps if isinstance(s.proof, PcAttackProof)
            and s.source.round_state.round_number == 2 and s.proof.request.actor_id.startswith('pc')]
        first, second = attacks
        restriction = WoundRestriction.NEXT_TEST_IS_GRIM
        self.assertTrue(any(isinstance(e, WoundRestrictionEffect) and e.restriction is restriction
            for e in first.state.participant('pc2').injury.active_wound_effects))
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.regular_dice_delta, 1)
        self.assertIs(first.proof.execution.resolution.attack.attacker_test.trace.quality, TestQuality.NORMAL)
        own_trace = second.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual(own_trace.regular_dice_delta, 0)
        self.assertIs(own_trace.quality, TestQuality.GRIM)
        self.assertFalse(any(isinstance(e, WoundRestrictionEffect) and e.restriction is restriction
            for e in second.state.participant('pc2').injury.active_wound_effects))

    def test_drop_recover_weapon_restriction_daily_and_fate_belong_only_to_the_second_pc(self):
        result = drops_second_pc()
        recover = next(s for s in result.steps if isinstance(s.proof, PcRecoverProof))
        self.assertEqual(recover.proof.result.source_request.actor_id, 'pc2')
        self.assertIsNone(recover.source.participant('pc2').weapon_hand)
        self.assertIsNotNone(recover.state.participant('pc2').weapon_hand)
        self.assertEqual(recover.source.participant('pc1'), recover.state.participant('pc1'))
        self.assertEqual([m.daily_wounds.wound_count for m in result.state.party], [0, 1])
        self.assertEqual([len(m.injury.wounds) for m in result.state.party], [0, 1])
        self.assertFalse(result.state.participant('pc1').injury.active_wound_effects)
        self.assertEqual([m.fate for m in result.state.party], [m.fate for m in result.source.party])

    def test_blinded_expiry_waits_for_its_own_turn_and_leaves_ally_body_untouched(self):
        source = make_pc_melee_party_scenario(max_rounds=2)
        source = replace(source, enemy_target_priority=('pc2', 'pc1'))
        result = run_script(source, [10,10,10,1,1] * 2
            + [1,1,10,10,10,7,10,10,10]
            + [10,10,1,1,1,10,10,10]
            + [10,10,10,1,1] + [1,10,10,10,1,1]
            + [10,10,1,1,1] * 2)
        ends = [s for s in result.steps if isinstance(s.proof, PcTurnEndProof)
            and s.source.round_state.round_number == 2 and s.proof.result.completed_turn.actor_id.startswith('pc')]
        first, second = ends
        self.assertTrue(first.state.participant('pc2').injury.conditions.has(Condition.BLINDED))
        self.assertTrue(first.state.participant('pc2').timed_wounds)
        self.assertFalse(second.state.participant('pc2').injury.conditions.has(Condition.BLINDED))
        self.assertFalse(second.state.participant('pc2').timed_wounds)
        self.assertEqual(second.source.participant('pc1'), second.state.participant('pc1'))

    def test_whole_party_source_and_prefix_reject_cross_pc_receipts_and_body_transplants(self):
        result = drops_second_pc()
        wounded = next(s for s in result.steps if isinstance(s.proof, PcWoundCompletionProof))
        with self.assertRaises(ValueError):
            PcMeleeStep(wounded.source, replace(wounded.proof,
                fate_decline=replace(wounded.proof.fate_decline, actor_id='pc1')))
        with self.assertRaises(ValueError):
            replace(wounded.source, pending_actor_id='pc1')
        forged = deepcopy(result)
        object.__setattr__(forged.steps[-1].state.party[0], 'injury', forged.steps[-1].state.party[1].injury)
        with self.assertRaises(ValueError):
            replace(forged)
        step = result.steps[0]
        self.assertEqual(apply_pc_melee_step(step.source, step), step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state, step)
        changed_party = replace_pc_melee_member(result.source, 'pc1',
            pc=replace(result.source.participant('pc1').pc, strength=9))
        with self.assertRaises(ValueError):
            replace(result, source=changed_party)

    def test_every_party_member_is_admitted_before_rng(self):
        source = make_pc_melee_party_scenario()
        forged = deepcopy(source)
        object.__setattr__(forged.party[1].fate, 'rating', True)
        class NoRandom:
            def randint(self, *_):
                raise AssertionError('malformed party reached RNG')
        with self.assertRaises((TypeError, ValueError)):
            run_pc_melee_scenario(forged, NoRandom())
        for name in ('pc_activation_order', 'enemy_target_priority'):
            for invalid in ((), ('pc1',), ('pc1', 'pc1'), ('pc1', 'minion1')):
                with self.assertRaises(ValueError):
                    replace(source, **{name: invalid})
        with self.assertRaises(ValueError):
            replace_pc_melee_member(source, 'pc2', fate=FateSessionState('session', 'foreign', 3, 3))
        with self.assertRaises(ValueError):
            replace(source, party=())
        validate_pc_melee_scenario_admission(source)

    def test_equal_but_wrong_type_recorded_source_body_is_readmitted(self):
        result = run_script(party_casualty_source(), party_casualty_script())
        original = result.steps[0]
        malformed_source = deepcopy(original.source)
        object.__setattr__(malformed_source.party[1].injury, 'dead', 0)
        self.assertEqual(malformed_source, original.source)
        forged_step = deepcopy(original)
        object.__setattr__(forged_step, 'source', malformed_source)
        with self.assertRaises(TypeError):
            replace(result, steps=(forged_step, *result.steps[1:]))
        with self.assertRaises(TypeError):
            apply_pc_melee_step(original.source, forged_step)
        with self.assertRaises(TypeError):
            apply_pc_melee_step(malformed_source, original)


if __name__ == '__main__':
    unittest.main()
