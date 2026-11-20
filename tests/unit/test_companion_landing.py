"""Prepared C16 geometry/clocks with real Wound and turn-start receipts.

These are owner tests, not a native airborne battle or a public Talent claim.
"""
from dataclasses import replace
from pickle import dumps, loads
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent
from tests.unit.test_companion_attack_wrappers import PreparedAttackView, attack_request
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain import talent_actor_models
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
from towr.domain.pc_battlefield_models import PcAirspaceSpec, battlefield_ground_below, with_actor_placement
from towr.domain.pc_blunderbuss_models import PcBlunderbussTargetProof, PcBlunderbussProfileProof, PcNearbyDecisions
from towr.domain.pc_companion_landing_models import (
    PcCompanionLandingProof, expected_companion_landing, project_companion_landing,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcProfileWoundProof, PcRecoverProof, PcTurnEndProof, initial_pc_melee_state, pc_melee_round_participants,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.pc_battlefield_movement_models import battlefield_recovered_injury
from towr.domain.pc_back_in_saddle_models import expected_back_in_saddle_move, project_back_in_saddle_move
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverConditionTarget, RecoverMode, RecoverStandardChoice
from towr.domain.pc_mount_models import CombatMount, expected_pc_dismount, updated_pc_mounts
from towr.domain.pc_mount_retention_models import expected_pc_mount_retention, project_pc_mount_retention
from towr.domain.pc_magic_models import PcMagicEffectProof, PcMagicPending, build_magic_effect
from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind
from towr.domain.pc_weapon_area_models import (
    PcWeaponHazardProof, _hazard_request, weapon_hazard_resolution_request, BLAST_IMPACT_RULE_ID,
)
from towr.domain.pc_warped_form_models import PcWarpedFormTargetProof, PcWarpedFormProfileProof
from towr.domain.resolution_models import StaggerImpactRequest, TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    CombatRoundState, CombatTurnStartRequest, CombatTurnEndRequest, CombatActionSlotRequest,
    CombatActionDeclaration, CombatActionKind, ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.protection_preparation import prepare_protection
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn, end_combat_turn, reserve_combat_action_slot


def append(view, proof, **changes):
    view.history = (*view.history, proof)
    for name, value in changes.items():
        setattr(view, name, value)


def context(*, npc=False, detached=False):
    source = mount_source(CombatMount.PEGASUS)
    rider = 'minion1' if npc else 'pc1'
    talent = free_talent(TalentId.BACK_IN_THE_SADDLE)
    if npc:
        component = replace(source.enemies[0].definition.generated_components, talents=(talent,))
        source = replace(source, enemies=(component.participant(rider),))
    else:
        source = replace(source, party=(replace(source.party[0], talents=(talent,)),))
    source = replace(source, max_rounds=4, battlefield=replace(source.battlefield, airspace=PcAirspaceSpec()))
    base = initial_pc_melee_state(source)
    view = PreparedAttackView(_base=base, **{name: getattr(base, name) for name in base.__dataclass_fields__})
    ground = view.battlefield.spatial.placement_for(rider).zone_id
    air = next(air for air, below in view.battlefield.air_to_ground if below == ground)
    view.battlefield = with_actor_placement(view.battlefield, rider, air)
    if detached:
        detach(view, rider)
    return view, rider, rider+':mount'


def detach(view, rider):
    # A prepared rider Prone observation isolates the genuine dismount and
    # retention owners; this is not a fabricated native falling journal.
    injury = pc_actor_injury(view, rider)
    injury = replace(injury, conditions=injury.conditions.with_condition(Condition.PRONE))
    if rider in view.source.enemy_activation_order:
        view.enemies = pc_actor_npc_update(view, rider, injury=injury)['enemies']
    else:
        view.party = tuple(replace(row, injury=injury) if row.actor_id == rider else row for row in view.party)
    dismount = expected_pc_dismount(view)
    view.mounts = updated_pc_mounts(view, dismount)
    append(view, dismount)
    retention = expected_pc_mount_retention(view)
    append(view, retention, **project_pc_mount_retention(view, retention))


def hazard_w1(view, body_id):
    request = _hazard_request(view, body_id, 'prepared:own-hazard', 2, BLAST_IMPACT_RULE_ID)
    rng = ScriptedD10([1, 10, 10])
    test = resolve_test(request.avoidance_test, rng)
    result = resolve_hazard(weapon_hazard_resolution_request(request, test), rng)
    rng.assert_exhausted()
    receipt = PcWeaponHazardProof(request, test, result)
    append(view, receipt, **pc_actor_npc_update(view, body_id, injury=result.state))
    return receipt


def started(view, actor, *, round_number=2, completed=()):
    # This explicit prepared round boundary isolates the real start receipt.
    clock = CombatRoundState(round_number, pc_melee_round_participants(view), completed_turn_entity_ids=completed)
    receipt = start_combat_turn(CombatTurnStartRequest('prepared:start:'+str(len(view.history)), clock, actor))
    view.battlefield = replace(view.battlefield, spatial=replace(view.battlefield.spatial,
        round_number=round_number, free_move_used_entity_ids=(), gave_ground_entity_ids=(),
        difficult_terrain_tested_entity_ids=()))
    append(view, receipt, round_state=receipt.state)
    return receipt


def finish_recover_turn(view, actor):
    """A genuine paid standard Recover closes this prepared rider clock."""
    slot = reserve_combat_action_slot(CombatActionSlotRequest('prepared:recover-slot',
        view.round_state, actor, CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD))
    append(view, slot, round_state=slot.state)
    before = pc_actor_injury(view, actor)
    choice = RecoverStandardChoice(WizardMagicState(),
        prone_target=RecoverConditionTarget(actor, before.conditions, None)
            if before.conditions.has(Condition.PRONE) else None)
    request = RecoverActionExecutionRequest('prepared:recover', view.round_state, actor,
        before.conditions, False, 1, RecoverMode.STANDARD, choice)
    result = execute_recover_action(request, ScriptedD10([]))
    injury = battlefield_recovered_injury(before, result)
    receipt = PcRecoverProof(result)
    append(view, receipt, round_state=result.round_state,
        party=tuple(replace(row, injury=injury) if row.actor_id == actor else row for row in view.party))
    ended = end_combat_turn(CombatTurnEndRequest('prepared:rider-end', view.round_state, actor))
    append(view, PcTurnEndProof(ended, None), round_state=ended.state)


class CompanionLandingTests(unittest.TestCase):
    def setUp(self):
        # Foundation-only acquisition admission; no production/public cap change.
        for name in ('PC_EXECUTABLE_TALENTS', 'NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models, name,
                getattr(talent_actor_models, name) | {TalentId.BACK_IN_THE_SADDLE}))

    def test_mounted_pegasus_lands_on_the_real_next_rider_turn_without_test_or_action(self):
        for npc in (False, True):
            view, rider, body = context(npc=npc)
            wound = hazard_w1(view, body)
            self.assertIsNone(expected_companion_landing(view))
            clock = started(view, rider, completed=('pc1',) if npc else ())
            with self.subTest(npc=npc):
                proof = expected_companion_landing(view)
                self.assertIs(type(proof), PcCompanionLandingProof)
                self.assertEqual(proof.actor_id, rider)
                self.assertEqual(proof.body_id, body)
                self.assertEqual(proof.wound_receipt, wound)
                self.assertEqual(proof.turn_start, clock)
                self.assertEqual(loads(dumps(proof)), proof)
                before_body, before_clock = view.companions, view.round_state
                updates = project_companion_landing(view, proof)
                self.assertEqual(tuple(updates), ('battlefield',))
                origin = proof.previous_battlefield.spatial.placement_for(rider).zone_id
                self.assertEqual(proof.battlefield.spatial.placement_for(rider).zone_id,
                    battlefield_ground_below(proof.previous_battlefield, origin))
                self.assertEqual(proof.battlefield.spatial.free_move_used_entity_ids, (rider,))
                self.assertEqual(view.companions, before_body)
                self.assertEqual(view.round_state, before_clock)
                self.assertFalse(proof.source_round.active_turn.action_slots)
                append(view, proof, **updates)
                self.assertIsNone(expected_companion_landing(view))
                with self.assertRaises(ValueError):
                    project_companion_landing(view, proof)

    def test_detached_body_waits_for_its_own_turn_and_rider_start_does_not_refresh_the_debt(self):
        view, rider, body = context(detached=True)
        wound = hazard_w1(view, body)
        rider_start = started(view, rider)
        self.assertIsNone(expected_companion_landing(view))
        finish_recover_turn(view, rider)
        body_start = start_combat_turn(CombatTurnStartRequest('prepared:body-start', view.round_state, body))
        append(view, body_start, round_state=body_start.state)
        proof = expected_companion_landing(view)
        self.assertEqual(proof.actor_id, body)
        self.assertEqual(proof.wound_receipt, wound)
        self.assertEqual(proof.turn_start, body_start)
        self.assertNotEqual(proof.turn_start, rider_start)
        self.assertEqual(proof.source_body.snapshot.state.injury, pc_actor_injury(view, body))
        self.assertEqual(proof.battlefield.spatial.placement_for(rider), view.battlefield.spatial.placement_for(rider))
        self.assertEqual(proof.battlefield.spatial.free_move_used_entity_ids, (body,))

    def test_an_earlier_turn_start_and_raw_w1_cannot_manufacture_the_next_turn_obligation(self):
        view, rider, body = context()
        started(view, rider, round_number=1)
        hazard_w1(view, body)
        self.assertIsNone(expected_companion_landing(view))
        view.history = tuple(proof for proof in view.history if type(proof) is not PcWeaponHazardProof)
        self.assertIsNone(expected_companion_landing(view))

    def test_dismount_after_w1_changes_the_real_turn_owner_without_changing_the_wound_source(self):
        view, rider, body = context()
        wound = hazard_w1(view, body)
        wound_index = len(view.history)-1
        detach(view, rider)
        clock = started(view, body, completed=(rider,))
        proof = expected_companion_landing(view)
        self.assertEqual((proof.actor_id, proof.wound_receipt_index), (body, wound_index))
        self.assertEqual((proof.wound_receipt, proof.turn_start), (wound, clock))

    def test_ordinary_attack_profile_acknowledgement_keeps_the_actual_body_and_producer(self):
        view, rider, body = context(npc=True, detached=True)
        actor = 'pc1'
        # Prepared physical contact for a real ordinary Attack execution.
        origin = view.battlefield.spatial.placement_for(body).zone_id
        view.battlefield = with_actor_placement(view.battlefield, actor, origin, close_to_ids=(body,))
        started(view, actor, round_number=1)
        slot = reserve_combat_action_slot(CombatActionSlotRequest('prepared:attack-slot',
            view.round_state, actor, CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD))
        append(view, slot, round_state=slot.state)
        request, protection, intent = attack_request(view, actor, body)
        rng = ScriptedD10([1]*3 + [10]*4)
        execution = execute_attack_action(request, rng)
        rng.assert_exhausted()
        self.assertIsNotNone(execution.resolution.profile_wound)
        producer = PcAttackProof(request, prepare_protection(protection), execution, None, weapon_intent=intent)
        append(view, producer, round_state=execution.state,
            **pc_actor_npc_update(view, body, injury=execution.resolution.target_state))
        acknowledgement = PcProfileWoundProof(execution.resolution.profile_wound.state_change, None)
        append(view, acknowledgement)
        started(view, body, completed=(actor, rider))
        proof = expected_companion_landing(view)
        self.assertEqual((proof.wound_receipt, proof.wound_producer), (acknowledgement, producer))
        # A foreign ordinary producer cannot replace the real ACK owner.
        with self.assertRaises(ValueError):
            replace(proof, wound_producer=replace(producer,
                request=replace(producer.request, target_id=rider)))

    def test_nearby_and_warped_form_acknowledgements_retain_their_exact_own_producer(self):
        for warped in (False, True):
            view, rider, body = context(detached=True)
            before = pc_actor_injury(view, body)
            before = replace(before, conditions=before.conditions.with_condition(Condition.STAGGERED))
            request = StaggerImpactRequest('prepared:impact', body, TargetInjuryPolicy.BRUTE, before, False, False)
            result = resolve_stagger_impact(request, ScriptedD10([]), decisions=PcNearbyDecisions())
            if warped:
                producer = PcWarpedFormTargetProof('prepared:wave', request, result)
                receipt = PcWarpedFormProfileProof('prepared:wave', body, result.profile_wound.state_change, None)
            else:
                producer = PcBlunderbussTargetProof('prepared:shot', request, result)
                receipt = PcBlunderbussProfileProof('prepared:shot', body, result.profile_wound.state_change, None)
            append(view, producer, **pc_actor_npc_update(view, body, injury=result.state))
            append(view, receipt)
            clock = started(view, body, completed=(rider,))
            with self.subTest(warped=warped):
                proof = expected_companion_landing(view)
                self.assertEqual(proof.wound_producer, producer)
                self.assertEqual(proof.wound_receipt, receipt)
                self.assertEqual(proof.turn_start, clock)

    def test_magic_direct_and_repeated_stagger_w1_keep_the_actual_body_before_snapshot(self):
        for repeated_stagger in (False, True):
            view, rider, body = context(detached=True)
            if repeated_stagger:
                injury = pc_actor_injury(view, body)
                view.companions = pc_actor_npc_update(view, body, injury=replace(injury,
                    conditions=injury.conditions.with_condition(Condition.STAGGERED)))['companions']
            before = pc_actor_injury(view, body)
            # Prepared committed spell task isolates the real typed effect
            # builder. No Casting journal or unsupported caster is claimed.
            task = PcMagicTask('prepared:spell-effect', PcMagicTaskKind.DAMAGE, body,
                1 if repeated_stagger else 20)
            view.magic_pending = PcMagicPending('pc1', 'prepared:spell-source', (task,))
            effect = build_magic_effect(view, ScriptedD10([]))
            self.assertIs(type(effect), PcMagicEffectProof)
            self.assertEqual(effect.previous_injury, before)
            append(view, effect, magic_pending=None,
                **pc_actor_npc_update(view, body, injury=effect.result.state))
            started(view, body, completed=(rider,))
            with self.subTest(repeated_stagger=repeated_stagger):
                proof = expected_companion_landing(view)
                self.assertEqual((proof.wound_receipt, proof.wound_producer), (effect, effect))
                self.assertEqual(proof.wound_receipt_index, proof.wound_producer_index)
                with self.assertRaises(TypeError):
                    erased = replace(effect, previous_injury=None)
                    replace(proof, wound_receipt=erased, wound_producer=erased)

    def test_wrong_history_clock_geometry_and_spent_movement_are_rejected(self):
        view, rider, body = context()
        hazard_w1(view, body)
        started(view, rider)
        proof = expected_companion_landing(view)
        for changes in (dict(wound_receipt_index=True), dict(turn_start_index=0), dict(actor_id=body),
                dict(source_round=replace(proof.source_round, round_number=3)),
                dict(battlefield=proof.previous_battlefield)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(proof, **changes)
        view.battlefield = replace(view.battlefield, spatial=replace(view.battlefield.spatial,
            free_move_used_entity_ids=(rider,)))
        with self.assertRaises(ValueError):
            expected_companion_landing(view)

    def test_overdue_landing_is_not_reissued_on_a_later_actual_turn(self):
        view, rider, body = context()
        hazard_w1(view, body)
        started(view, rider, round_number=2)
        self.assertIsNotNone(expected_companion_landing(view))
        # Deliberately malformed prefix: the obligatory landing was omitted.
        started(view, rider, round_number=3)
        with self.assertRaisesRegex(ValueError, 'overdue'):
            expected_companion_landing(view)

    def test_remount_does_not_refresh_an_already_due_body_turn(self):
        view, rider, body = context(detached=True)
        wound = hazard_w1(view, body)
        started(view, body, completed=(rider,))
        original = expected_companion_landing(view)
        self.assertEqual(original.wound_receipt, wound)
        # Deliberately malformed prefix: omit the already-due mandatory landing
        # and observe a later real rider start + source-bound free remount.
        started(view, rider, round_number=3)
        remount = expected_back_in_saddle_move(view)
        self.assertIsNotNone(remount)
        append(view, remount, **project_back_in_saddle_move(view, remount))
        self.assertEqual(pc_actor_injury(view, body).wounds, 1)
        with self.assertRaisesRegex(ValueError, 'overdue'):
            expected_companion_landing(view)


if __name__ == '__main__':
    unittest.main()
