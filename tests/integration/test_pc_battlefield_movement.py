"""Real Zone movement, separate Short approach and ordinary Recover receipts."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedRangedFacts
from towr.domain.movement_models import FreeMovementRequest
from towr.domain.pc_battlefield_models import (
    PcBattlefieldSpec, battlefield_range, with_actor_placement,
)
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldMoveProof, PcBattlefieldRecoverProof,
    expected_pc_battlefield_move, pc_battlefield_allows_outnumbering,
    pc_battlefield_attack_available, pc_battlefield_npc_recover_selected,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcRecoverProof,
    initial_pc_melee_state,
)
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatRoundAdvanceResult
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class Misses:
    def randint(self, low, high):
        if (low,high) != (1,10):
            raise AssertionError('this literal all-miss battle needs only d10')
        return 10


def scene(distance=RangedWeaponRange.MEDIUM, *, pcs=1, enemies=1, rounds=1):
    source = automatic_source(pc_count=pcs,enemy_count=enemies,rounds=rounds)
    return replace(source, facts=replace(source.facts,
        all_opponents_close=distance is RangedWeaponRange.CLOSE,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(distance,RangedWeaponRange.LONG))


def movement_snapshot(source):
    """Preparation snapshot: Burdened allows free movement but forbids Charge."""
    state=tactical_snapshot(source)
    actor=state.round_state.active_turn.actor_id
    member=state.participant(actor)
    return replace(state,party=tuple(replace(item,injury=replace(item.injury,
        conditions=item.injury.conditions.with_condition(Condition.BURDENED)))
        if item.actor_id==actor else item for item in state.party))


def waiting_net_holders():
    source=automatic_source(pc_count=1,enemy_count=3,rounds=4)
    member=replace(source.party[0],pc=replace(source.party[0].pc,weapon_skill=1,melee=2))
    npc=GeneratedNpc(3,3,4,2,3,3,initial_generated_weapons(GeneratedWeapon.WEIGHTED_NET),light_loadout(light=False, shield=False),defence=3,
        # No spare Unarmed attack: this fixture exercises waiting Recover
        # after its finite Net is attached to the target, not Brawn tactics.
        ballistic_skill=3,throwing=4,brawn=None)
    return replace(source,party=(member,),enemies=tuple(npc.participant(actor)
        for actor in source.enemy_activation_order))


class BattlefieldMovementTests(unittest.TestCase):
    def execute(self, source):
        result = run_pc_melee_scenario(source,Misses())
        self.assertEqual(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertIsNone(result.unsupported)
        current = initial_pc_melee_state(source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def test_medium_move_uses_actual_k1_and_establishes_only_chosen_close(self):
        source = scene(enemies=2)
        state = movement_snapshot(source)
        proof = expected_pc_battlefield_move(state)
        self.assertIs(type(proof),PcBattlefieldMoveProof)
        self.assertIs(type(proof.movement_request),FreeMovementRequest)
        self.assertEqual(proof.movement_result,resolve_free_movement(proof.movement_request))
        self.assertEqual(proof.state.spatial.free_move_used_entity_ids,('pc1',))
        self.assertEqual(battlefield_range(proof.state,'pc1','minion1'),RangedWeaponRange.CLOSE)
        self.assertEqual(battlefield_range(proof.state,'pc1','minion2'),RangedWeaponRange.SHORT)
        moved = PcMeleeStep(state,proof).state
        self.assertIsNone(expected_pc_battlefield_move(moved))
        self.assertTrue(pc_battlefield_attack_available(moved,'pc1','minion1'))
        self.assertFalse(pc_battlefield_attack_available(moved,'pc1','minion2'))
        with self.assertRaises(ValueError):
            PcMeleeStep(moved,proof)

    def test_short_approach_does_not_spend_zone_free_move(self):
        state = movement_snapshot(scene(RangedWeaponRange.SHORT))
        proof = expected_pc_battlefield_move(state)
        self.assertIsNone(proof.movement_request)
        self.assertIsNone(proof.movement_result)
        self.assertEqual(proof.state.spatial,proof.previous.spatial)
        self.assertEqual(proof.state.spatial.free_move_used_entity_ids,())
        moved = PcMeleeStep(state,proof).state
        # Short approach did not fabricate an empty route or consume the K1
        # allowance: an independent real Zone move remains legally available.
        spatial = moved.battlefield.spatial
        zone = spatial.placement_for('pc1').zone_id
        adjacent = spatial.graph.adjacent_zone_ids(zone)[0]
        request = FreeMovementRequest('proof:remaining-zone-move',moved.round_state,
            spatial,'pc1',proof.speed,proof.actor_conditions,(adjacent,))
        actual = resolve_free_movement(request)
        self.assertEqual(actual.state.free_move_used_entity_ids,('pc1',))

    def test_zone_move_then_failed_long_charge_never_invents_pc_attack(self):
        result = self.execute(scene(RangedWeaponRange.EXTREME,rounds=2))
        first_round = [step for step in result.steps if step.source.round_state.round_number==1]
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc1'
            for step in first_round))
        charge=next(step for step in first_round if type(step.proof) is PcBattlefieldChargeProof
            and step.proof.actor_id=='pc1')
        self.assertFalse(charge.proof.result.attack_allowed)
        self.assertTrue(charge.proof.result.round_state.active_turn.action_slots[0].executed)
        self.assertTrue(charge.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.executed_actions,4)
        for step in result.steps:
            if type(step.proof) is PcAttackProof:
                self.assertTrue(pc_battlefield_attack_available(step.source,
                    step.proof.request.actor_id,step.proof.request.target_id))

    def test_native_round_advance_resets_usage_without_resetting_positions(self):
        result = self.execute(scene(RangedWeaponRange.EXTREME,rounds=2))
        advance = next(step for step in result.steps if type(step.proof) is CombatRoundAdvanceResult)
        self.assertTrue(advance.source.battlefield.spatial.free_move_used_entity_ids)
        self.assertEqual(advance.state.battlefield.spatial.free_move_used_entity_ids,())
        self.assertEqual(advance.state.battlefield.spatial.placements,
            advance.source.battlefield.spatial.placements)
        self.assertEqual(advance.state.battlefield.close_pairs,advance.source.battlefield.close_pairs)
        self.assertEqual(advance.state.battlefield.spatial.round_number,2)

    def test_standard_npc_recover_is_counted_without_invented_healing_limit(self):
        source = waiting_net_holders()
        request = PcMeleeSimulationRequest(source,master_seed=42,trials=1)
        class Ones:
            def randint(self,low,high):
                if (low,high)!=(1,10):
                    raise AssertionError('literal combat uses d10 only')
                return 1
        trial = run_pc_melee_trial(request,0,rng_factory=lambda _:Ones())
        self.assertEqual(trial.executed_actions,16)
        self.assertEqual(tuple(item.count for item in trial.npc_recover_action_counts),(3,3,3))
        self.assertEqual(trial.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_full_source_and_placement_tampering_are_rejected(self):
        state = movement_snapshot(scene(enemies=2))
        proof = expected_pc_battlefield_move(state)
        with self.assertRaises(ValueError):
            replace(proof,actor_id='minion1')
        with self.assertRaises(ValueError):
            replace(proof,source_round=replace(proof.source_round,round_number=2))
        with self.assertRaises(ValueError):
            replace(proof,state=with_actor_placement(proof.state,'minion2',
                proof.previous.spatial.placement_for('pc1').zone_id))
        with self.assertRaises(ValueError):
            replace(state,battlefield=proof.state)
        forged_request = replace(proof.movement_request,
            actor_conditions=proof.actor_conditions.with_condition(Condition.DRAINED))
        forged = replace(proof,actor_conditions=forged_request.actor_conditions,
            movement_request=forged_request,movement_result=resolve_free_movement(forged_request))
        # A self-consistent K1 result is still bound to actual owner Conditions.
        with self.assertRaises(ValueError):
            PcMeleeStep(state,forged)

    def test_conditions_are_not_bypassed_and_burdened_allows_free_move(self):
        state = tactical_snapshot(scene())
        member = state.participant('pc1')
        for condition in (Condition.PRONE,Condition.DEFENCELESS,Condition.BROKEN):
            injury = replace(member.injury,conditions=member.injury.conditions.with_condition(condition))
            snapshot = replace(state,party=(replace(member,injury=injury),))
            self.assertIsNone(expected_pc_battlefield_move(snapshot))
        injury = replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.BURDENED))
        burdened = replace(state,party=(replace(member,injury=injury),))
        proof = expected_pc_battlefield_move(burdened)
        self.assertIsNotNone(proof)
        self.assertTrue(proof.actor_conditions.has(Condition.BURDENED))
        self.assertEqual(proof.movement_result.state.free_move_used_entity_ids,('pc1',))

    def test_outnumbering_counts_actual_zone_without_transitive_close(self):
        state = movement_snapshot(scene(pcs=2,enemies=1))
        self.assertTrue(pc_battlefield_allows_outnumbering(state,'pc1'))
        self.assertTrue(pc_battlefield_allows_outnumbering(state,'minion1'))
        proof = expected_pc_battlefield_move(state)
        moved = PcMeleeStep(state,proof).state
        self.assertFalse(pc_battlefield_allows_outnumbering(moved,'pc1'))
        self.assertFalse(pc_battlefield_allows_outnumbering(moved,'minion1'))
        self.assertTrue(pc_battlefield_allows_outnumbering(moved,'pc2'))

    def test_legacy_encounter_has_no_battlefield_or_positioning_proof(self):
        result = self.execute(automatic_source(pc_count=1,enemy_count=1))
        self.assertIsNone(result.state.battlefield)
        self.assertFalse(any(type(step.proof) is PcBattlefieldMoveProof for step in result.steps))


if __name__ == '__main__':
    unittest.main()
