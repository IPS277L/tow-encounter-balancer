"""Acrobatic falling preparation snapshots; native flight journals are separate."""
from copy import copy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent, paid_talent
from tests.unit.test_pc_falling import view
from towr.domain.armour_models import BodyArmour, ITHILMAR_ENVIRONMENT_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.pc_falling_models import (
    PcFallingProof, expected_pc_falling_request, falling_hazard_request,
    falling_npc_disposition, prepare_hazard_avoidance, project_pc_falling_step,
)
from towr.domain.pc_melee_result_models import PcFateDecline
from towr.domain.resolution_models import HazardExposureRequest
from towr.domain.talent_acrobatic_models import AcrobaticFallReduction, AcrobaticSource
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.test_resolution import resolve_test


def acrobatic_view(*, npc=False, rating=1, body=BodyArmour.HEAVY, hardy=False, drained=False):
    """An explicit local dismount snapshot, with real free-creation provenance.

    The existing low-Agility fall fixtures keep their actual dice profiles:
    free creation legally waives Requirements; it does not alter runtime caps.
    """
    state = view(npc=npc, body=body)
    actor = 'minion1' if npc else 'pc'
    talents = (free_talent(TalentId.ACROBATIC),)
    if hardy:
        talents += (free_talent(TalentId.HARDY),)
    battlefield = replace(state.source.battlefield,
        airspace=replace(state.source.battlefield.airspace, fall_hazard_rating=rating))
    if npc:
        original = state.enemy(actor)
        components = replace(original.definition.generated_components, talents=talents)
        healthy = components.participant(actor)
        changed = replace(healthy, state=replace(healthy.state, injury=original.state.injury))
        if drained:
            changed = replace(changed, state=replace(changed.state, injury=replace(changed.state.injury,
                conditions=changed.state.injury.conditions.with_condition(Condition.DRAINED))))
        state.enemies = tuple(changed if item.state.actor_id == actor else item for item in state.enemies)
        state.enemy = lambda identifier: next(item for item in state.enemies if item.state.actor_id == identifier)
        state.source = replace(state.source, battlefield=battlefield,
            enemies=tuple(healthy if item.state.actor_id == actor else item for item in state.source.enemies))
    else:
        state.source = replace(state.source, battlefield=battlefield,
            party=tuple(replace(member, talents=talents) if member.actor_id == actor else member
                for member in state.source.party))
        if drained:
            state.party = tuple(replace(member, injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
                if member.actor_id == actor else member for member in state.party)
            state.participant = lambda identifier: next(item for item in state.party if item.actor_id == identifier)
    return state


def execute_prepared(state, values):
    request = expected_pc_falling_request(state)
    rng = ScriptedD10(values)
    test = resolve_test(request.avoidance_test, rng)
    result = resolve_hazard(falling_hazard_request(request, test), rng)
    rng.assert_exhausted()
    is_pc = request.actor_id in state.source.pc_activation_order
    decline = (PcFateDecline(request.actor_id, request.avoidance_test.id, 'test',
        state.source.participant(request.actor_id).fate_policy) if is_pc else None)
    disposition = (falling_npc_disposition(state.source, request.actor_id)
        if not is_pc and result.profile_wound is not None else None)
    proof = PcFallingProof(request, test, result, decline, npc_disposition=disposition)
    return proof, project_pc_falling_step(state, proof)


class AcrobaticFallingTests(unittest.TestCase):
    def test_rating_one_becomes_zero_with_a_real_zero_success_test_for_both_sides(self):
        for npc in (False, True):
            with self.subTest(npc=npc):
                state = acrobatic_view(npc=npc)
                proof, updates = execute_prepared(state, [10, 10])
                reduction = proof.request.exposure.acrobatic_fall
                self.assertEqual((reduction.base_rating, reduction.rating), (1, 0))
                self.assertEqual(reduction.source.actor_id, proof.actor_id)
                self.assertEqual(reduction.source.talent, free_talent(TalentId.ACROBATIC))
                self.assertEqual((proof.test.trace.initial_values, proof.test.successes), ((10, 10), 0))
                self.assertEqual((proof.result.rating, proof.result.shortfall, proof.result.avoided), (0, 0, True))
                self.assertIsNone(proof.result.pending_character_wound)
                self.assertIsNone(proof.result.profile_wound)
                self.assertEqual(proof.result.state, proof.request.target_injury)
                if npc:
                    self.assertIsNone(proof.fate_decline)
                    self.assertIsNone(proof.glorious)
                else:
                    self.assertEqual(updates['party'][0].fate, state.participant('pc').fate)
                # Only this prepared fall has now occurred; its same dismount
                # cannot be consumed again. No earlier battle is being claimed.
                after = copy(state)
                after.history = (*state.history, proof)
                for name, value in updates.items():
                    setattr(after, name, value)
                if npc:
                    after.enemy = lambda identifier: next(item for item in after.enemies if item.state.actor_id == identifier)
                else:
                    after.participant = lambda identifier: next(item for item in after.party if item.actor_id == identifier)
                with self.assertRaises(ValueError):
                    project_pc_falling_step(after, proof)

    def test_three_halves_down_to_one_and_retains_real_failed_hazard_wound(self):
        for npc in (False, True):
            with self.subTest(npc=npc):
                state = acrobatic_view(npc=npc, rating=3)
                proof, _ = execute_prepared(state, [10, 10] if npc else [10, 10, 2])
                self.assertEqual((proof.request.exposure.acrobatic_fall.base_rating,
                    proof.result.rating, proof.result.shortfall), (3, 1, 1))
                self.assertFalse(proof.result.avoided)
                if npc:
                    self.assertEqual(proof.result.profile_wound.wounds_inflicted, 1)
                else:
                    self.assertEqual(proof.result.pending_character_wound.source_request.wound.base_dice, 1)

    def test_same_rounded_rating_cannot_hide_wrong_gm_base_erasure_or_different_acquisition(self):
        state = acrobatic_view(rating=3)
        proof, _ = execute_prepared(state, [1, 10])
        exposure = proof.request.exposure
        changed = (
            replace(exposure, acrobatic_fall=None),
            replace(exposure, acrobatic_fall=replace(exposure.acrobatic_fall, base_rating=2)),
            replace(exposure, acrobatic_fall=AcrobaticFallReduction(
                AcrobaticSource('pc', paid_talent(TalentId.ACROBATIC)), 3)),
        )
        for forged in changed:
            self.assertEqual(forged.rating, 1)
            with self.subTest(exposure=forged), self.assertRaises(ValueError):
                project_pc_falling_step(state, replace(proof, request=replace(proof.request, exposure=forged)))
        foreign = AcrobaticFallReduction(AcrobaticSource('foreign', free_talent(TalentId.ACROBATIC)), 3)
        with self.assertRaises(ValueError):
            replace(proof.request, exposure=replace(exposure, acrobatic_fall=foreign))
        zero = expected_pc_falling_request(acrobatic_view()).exposure
        with self.assertRaises(ValueError):
            replace(zero, acrobatic_fall=None)

    def test_ithilmar_bonus_and_drained_remain_independent_of_rating_reduction(self):
        for npc in (False, True):
            for drained in (False, True):
                with self.subTest(npc=npc, drained=drained):
                    state = acrobatic_view(npc=npc, body=BodyArmour.ITHILMAR, drained=drained)
                    proof, _ = execute_prepared(state, [10] * (3 if drained else 4))
                    bonuses = tuple(mod.amount for mod in proof.request.avoidance_test.dice_modifiers
                        if mod.rule_id == ITHILMAR_ENVIRONMENT_RULE_ID)
                    self.assertEqual(bonuses, () if drained else (1,))
                    self.assertEqual(proof.result.rating, 0)
                    self.assertTrue(proof.result.avoided)

    def test_hardy_modifies_actual_remaining_wound_dice_after_acrobatic_reduces_rating(self):
        state = acrobatic_view(rating=6, hardy=True)
        proof, _ = execute_prepared(state, [10, 10, 1, 1])
        wound = proof.result.pending_character_wound
        self.assertEqual((proof.request.exposure.acrobatic_fall.base_rating, proof.result.rating), (6, 3))
        self.assertEqual(wound.source_request.wound.base_dice, 3)
        self.assertEqual(tuple(mod.amount for mod in wound.source_request.wound.dice_modifiers), (-1,))
        self.assertEqual(len(wound.wound_result.table_roll.values), 2)

    def test_ordinary_athletics_hazard_is_not_reclassified_as_falling(self):
        state = acrobatic_view(body=BodyArmour.ITHILMAR)
        exposure = HazardExposureRequest('ordinary', 'ordinary:test', 3, Skill.ATHLETICS,
            'authored:environment', False, (Condition.DRAINED,))
        test = prepare_hazard_avoidance(state, 'pc', exposure, environmental=True)
        self.assertEqual(exposure.rating, 3)
        self.assertIsNone(exposure.acrobatic_fall)
        self.assertEqual(tuple(mod.amount for mod in test.dice_modifiers
            if mod.rule_id == ITHILMAR_ENVIRONMENT_RULE_ID), (1,))


if __name__ == '__main__':
    unittest.main()
