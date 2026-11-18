"""NPC Aim preparation and canonical K1 receipts; no invented native battle prefix.

Prepared clocks isolate the NPC action boundary. Shot and follow-up tests use
real K1 executions; the full runner integration is checked by its owner tests.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from copy import deepcopy
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID, AimFollowUpOutcome
from towr.domain.charge_models import ChargeMovementRequest
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed, RunActionExecutionRequest
from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, with_actor_placement
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof, PcBattlefieldRunProof
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldMoveProof, PcBattlefieldRecoverProof, battlefield_recovered_injury,
)
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_magic_models import PcMagicModifier
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, build_pc_melee_attack, initial_pc_melee_state,
)
from towr.domain.pc_npc_aim_models import (
    PcNpcAimProof, PcNpcAimConsumptionProof, build_npc_aim, current_npc_aim,
    expected_npc_aim_consumption, npc_aim_attack_modifiers, npc_needs_aim,
    project_npc_aim_step, validate_pc_npc_aim_history,
)
from towr.domain.pc_npc_ranged_models import (
    complete_pc_npc_ranged_shot, npc_ranged_inventory_update,
)
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverConditionTarget, RecoverMode, RecoverStandardChoice,
)
from towr.domain.test_models import DiceModifier, InlineProfile, TestQuality, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnStartRequest,
    ManoeuvreKind,
)
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.charge_action_execution import execute_charge_movement
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.run_action_execution import execute_run_action
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.turn_resolution import (
    advance_combat_round, end_combat_turn, reserve_combat_action_slot, start_combat_turn,
)


def source(weapon=GeneratedWeapon.HOCHLAND_LONG_RIFLE, *, distance=Range.MEDIUM,
        maximum=Range.LONG, party=1):
    scene = make_pc_melee_party_scenario(pc_count=party, enemy_count=1, max_rounds=4)
    blackpowder = weapon in (GeneratedWeapon.HANDGUN, GeneratedWeapon.BLUNDERBUSS,
        GeneratedWeapon.HOCHLAND_LONG_RIFLE, GeneratedWeapon.REPEATER_HANDGUN)
    facts = GeneratedRangedFacts(1, 2, 2, None if weapon in (GeneratedWeapon.SHORTBOW,GeneratedWeapon.WARBOW,GeneratedWeapon.LONGBOW) else 3, True,
        True if blackpowder else None, True if blackpowder else None, awareness=3)
    npc = GeneratedNpc(1, 3, 20, 1, 2, 2, initial_generated_weapons(weapon), light_loadout(light=False, shield=False),
        defence=2,  ranged=facts)
    return replace(scene, party=tuple(replace(member, policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        for member in scene.party), enemies=(npc.participant('minion1'),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc, 'minion1'),),
        facts=replace(scene.facts, all_opponents_close=distance is Range.CLOSE,
            can_leave_zone=True, outnumbering_bonus_approved=False),
        battlefield=PcBattlefieldSpec(distance, maximum))


def prepared(scene):
    state = initial_pc_melee_state(scene)
    # Preparation-only: PCs have completed their turns. This does not claim to
    # be a complete source-to-state native journal.
    clock = replace(state.round_state, completed_turn_entity_ids=scene.pc_activation_order)
    clock = start_combat_turn(CombatTurnStartRequest('prepared:npc:start', clock, 'minion1')).state
    return replace(state, round_state=clock)


def reserve(state, kind):
    clock = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve',
        state.round_state, 'minion1', CombatActionDeclaration(kind), ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=clock)


def aim(state, values=(1, 10)):
    state = reserve(state, CombatActionKind.AIM)
    request = build_npc_aim(state)
    rng = ScriptedD10(values)
    proof = PcNpcAimProof(request, execute_aim_action(request, rng))
    rng.assert_exhausted()
    return state, proof, project_npc_aim_step(state, proof)


def next_npc_turn(state):
    ended = end_combat_turn(CombatTurnEndRequest('prepared:npc:end', state.round_state, 'minion1'))
    advanced = advance_combat_round(CombatRoundAdvanceRequest('prepared:next', ended.state,
        ended.state.participants))
    clock = replace(advanced.state, completed_turn_entity_ids=state.source.pc_activation_order)
    started = start_combat_turn(CombatTurnStartRequest('prepared:npc:next:start', clock, 'minion1'))
    battlefield = replace(state.battlefield, spatial=start_next_spatial_round(state.battlefield.spatial))
    return replace(state, round_state=started.state, battlefield=battlefield,
        history=(*state.history, ended, advanced, started))


def journal(scene, *proofs):
    """A history-only unit view with real typed receipts, not a battle owner."""
    return SimpleNamespace(source=scene, history=proofs)


class PcNpcAimTests(unittest.TestCase):
    def test_hochland_always_needs_aim_and_other_two_handed_weapons_need_it_at_extreme(self):
        weapons = (GeneratedWeapon.SHORTBOW, GeneratedWeapon.WARBOW, GeneratedWeapon.LONGBOW,
            GeneratedWeapon.CROSSBOW, GeneratedWeapon.HANDGUN, GeneratedWeapon.BLUNDERBUSS,
            GeneratedWeapon.HOCHLAND_LONG_RIFLE, GeneratedWeapon.REPEATER_CROSSBOW,
            GeneratedWeapon.REPEATER_HANDGUN)
        for weapon in weapons:
            with self.subTest(weapon=weapon, distance='medium'):
                state = prepared(source(weapon))
                self.assertEqual(npc_needs_aim(state, 'minion1'),
                    weapon is GeneratedWeapon.HOCHLAND_LONG_RIFLE)
            with self.subTest(weapon=weapon, distance='extreme'):
                state = prepared(source(weapon, distance=Range.EXTREME, maximum=Range.EXTREME))
                self.assertEqual(npc_needs_aim(state, 'minion1'),
                    weapon is not GeneratedWeapon.BLUNDERBUSS)  # Its printed maximum is Medium.

    def test_awareness_uses_initiative_and_its_own_rating_with_one_standard_action(self):
        state = prepared(source())
        original = deepcopy(state)
        before, proof, after = aim(state)
        self.assertEqual(state, original)
        self.assertEqual(proof.request.awareness_test.profile, InlineProfile(2, 3))
        self.assertEqual(proof.result.awareness_test_result.trace.initial_values, (1, 10))
        self.assertEqual(proof.result.bonus.bonus_dice, 1)
        self.assertEqual(proof.request.actor_id, 'minion1')
        self.assertEqual(proof.request.target_id, 'pc1')
        self.assertEqual(proof.request.slot_index, 1)
        self.assertEqual(len(after.round_state.active_turn.action_slots), 1)
        self.assertIs(proof.result.slot.grant, ActionSlotGrant.STANDARD)
        self.assertEqual(after.party[0].fate, before.party[0].fate)
        self.assertFalse(hasattr(proof, 'fate_decline'))
        self.assertEqual(current_npc_aim(after, 'minion1'), proof.result)
        self.assertEqual(npc_aim_attack_modifiers(after, 'minion1', 'pc1'),
            (DiceModifier(AIM_FOLLOW_UP_RULE_ID, 1),))

    def test_zero_success_aim_still_satisfies_hochland_permission_without_bonus_dice(self):
        _, proof, after = aim(prepared(source()), (10, 10))
        self.assertEqual(proof.result.bonus.bonus_dice, 0)
        self.assertFalse(npc_needs_aim(after, 'minion1'))
        self.assertEqual(npc_aim_attack_modifiers(after, 'minion1', 'pc1'), ())
        self.assertEqual(current_npc_aim(after, 'minion1'), proof.result)

    def test_actual_conditions_and_magic_penalty_are_in_the_awareness_test_and_consumed_once(self):
        state = prepared(source())
        enemy = state.enemy('minion1')
        enemy = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset((Condition.BLINDED, Condition.DRAINED))))))
        penalty = PcMagicModifier('actual:next-test', 'minion1', PcMagicTaskKind.NEXT_TEST_PENALTY)
        grim = PcMagicModifier('actual:awareness', 'minion1', PcMagicTaskKind.AWARENESS_GRIM)
        state = replace(state, enemies=(enemy,), magic_modifiers=(penalty, grim))
        _, proof, after = aim(state, (1, 1))  # One die and its mandatory Grim reroll.
        self.assertEqual(proof.request.awareness_test.dice_modifiers,
            (DiceModifier('actual:next-test', -1),))
        self.assertEqual(tuple(q.rule_id for q in proof.request.awareness_test.quality_modifiers),
            ('actual:awareness', 'RULE-HEALTH-008:blinded'))
        self.assertTrue(all(q.quality is TestQuality.GRIM
            for q in proof.request.awareness_test.quality_modifiers))
        self.assertEqual(proof.result.awareness_test_result.trace.rolled_dice, 1)
        self.assertEqual(proof.result.bonus.bonus_dice, 1)
        self.assertEqual(after.magic_modifiers, (grim,))
        self.assertEqual(after.enemy('minion1').state.injury.conditions, enemy.state.injury.conditions)

    def test_close_broken_defenceless_or_outside_gm_maximum_do_not_select_aim(self):
        for distance, maximum in ((Range.CLOSE, Range.LONG), (Range.EXTREME, Range.LONG)):
            with self.subTest(distance=distance):
                self.assertFalse(npc_needs_aim(prepared(source(distance=distance, maximum=maximum)), 'minion1'))
        for condition in (Condition.BROKEN, Condition.DEFENCELESS):
            with self.subTest(condition=condition):
                state = prepared(source())
                enemy = state.enemy('minion1')
                changed = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
                    conditions=ConditionState(frozenset((condition,))))))
                self.assertFalse(npc_needs_aim(replace(state, enemies=(changed,)), 'minion1'))

    def test_target_is_first_live_legal_range_in_existing_priority(self):
        state = prepared(source(party=2))
        first_zone = state.battlefield.spatial.graph.zone_ids[0]
        changed = with_actor_placement(state.battlefield, 'pc1', first_zone)
        # Preparation-only geometry for this request boundary. A native battle
        # must establish the same placement through its real movement owner.
        # PcMeleeState is slotted; make an explicit read-only view of the facts
        # used by the range/selection helpers without claiming a movement proof.
        view = SimpleNamespace(**{field.name: getattr(state, field.name) for field in fields(state)})
        view.battlefield = changed
        view.enemy = state.enemy
        view.participant = state.participant
        view.live_party = state.live_party
        view.live_enemies = state.live_enemies
        view.exited_npc_ids = state.exited_npc_ids
        self.assertTrue(npc_needs_aim(view, 'minion1'))
        self.assertEqual(build_npc_aim(view).target_id, 'pc2')

    def test_real_shot_preparation_consumes_the_same_aim_once_and_rejects_missing_follow_up(self):
        _, aimed, state = aim(prepared(source()))
        state = reserve(next_npc_turn(state), CombatActionKind.ATTACK)
        request, protection = build_pc_melee_attack(state)
        rng = ScriptedD10((10, 10, 1, 1, 1))
        execution = execute_attack_action(request, rng)
        rng.assert_exhausted()
        shot = complete_pc_npc_ranged_shot(state, request, request, execution)
        proof = PcAttackProof(request, protection, execution, None, npc_ranged_shot=shot)
        after = replace(state, round_state=execution.state,
            history=(*state.history, proof), enemies=npc_ranged_inventory_update(
                state, 'minion1', shot.execution.weapon_state))
        pending = expected_npc_aim_consumption(after)
        self.assertIs(type(pending), PcNpcAimConsumptionProof)
        self.assertEqual(pending.follow_up, shot.preparation.aim_follow_up)
        self.assertEqual(pending.follow_up.source_request.aim, aimed.result)
        self.assertIs(pending.follow_up.outcome, AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
        consumed = project_npc_aim_step(after, pending)
        self.assertIsNone(current_npc_aim(consumed, 'minion1'))
        self.assertIsNone(expected_npc_aim_consumption(consumed))
        with self.assertRaises(ValueError):
            project_npc_aim_step(consumed, pending)
        forged = deepcopy(proof)
        object.__setattr__(forged.npc_ranged_shot.preparation, 'aim_follow_up', None)
        with self.assertRaises(ValueError):
            expected_npc_aim_consumption(journal(state.source, aimed, forged))

    def test_next_standard_recover_loses_aim_and_requires_immediate_exact_consumption(self):
        _, aimed, state = aim(prepared(source()))
        next_state = reserve(next_npc_turn(state), CombatActionKind.RECOVER)
        previous = replace(next_state.enemy('minion1').state.injury,
            conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        request = RecoverActionExecutionRequest('prepared:recover', next_state.round_state,
            'minion1', previous.conditions, False, 1, RecoverMode.STANDARD,
            RecoverStandardChoice(WizardMagicState(),
                staggered_target=RecoverConditionTarget('minion1', previous.conditions, None)))
        result = expected_pc_standard_recover(request)
        recovered = PcBattlefieldRecoverProof(request, result, previous,
            battlefield_recovered_injury(previous, result))
        pending = expected_npc_aim_consumption(journal(state.source, aimed, recovered))
        self.assertIs(pending.follow_up.outcome, AimFollowUpOutcome.LOST)
        self.assertIsNone(pending.follow_up.modifier)
        self.assertEqual(pending.action, result.slot.execution)
        consumed = journal(state.source, aimed, recovered, pending)
        self.assertIsNone(current_npc_aim(consumed, 'minion1'))
        validate_pc_npc_aim_history(consumed)
        with self.assertRaises(ValueError):
            validate_pc_npc_aim_history(journal(state.source, aimed, recovered, recovered))
        with self.assertRaises(ValueError):
            validate_pc_npc_aim_history(journal(state.source, aimed, recovered, pending, pending))
        forged = replace(pending, action=replace(pending.action, id='foreign:action'))
        with self.assertRaises(ValueError):
            validate_pc_npc_aim_history(journal(state.source, aimed, recovered, forged))

    def test_real_free_movement_does_not_consume_aim(self):
        _, aimed, state = aim(prepared(source()))
        state = next_npc_turn(state)
        origin = state.battlefield.spatial.placement_for('minion1').zone_id
        destination = state.battlefield.spatial.graph.adjacent_zone_ids(origin)[-1]
        request = FreeMovementRequest('prepared:free-move', state.round_state,
            state.battlefield.spatial, 'minion1', MovementSpeed.NORMAL, ConditionState(),
            (destination,))
        result = resolve_free_movement(request)
        changed = with_actor_placement(replace(state.battlefield, spatial=result.state),
            'minion1', destination)
        proof = PcBattlefieldMoveProof('minion1', request.id, 'pc1', state.round_state,
            state.battlefield, ConditionState(), MovementSpeed.NORMAL, (), request, result, changed)
        view = journal(state.source, aimed, proof)
        self.assertEqual(current_npc_aim(view, 'minion1'), aimed.result)
        self.assertIsNone(expected_npc_aim_consumption(view))

    def test_wrong_slot_actor_and_forged_awareness_or_bonus_cannot_replace_aim(self):
        state = reserve(prepared(source()), CombatActionKind.ATTACK)
        with self.assertRaises(ValueError):
            build_npc_aim(state)
        with self.assertRaises(ValueError):
            current_npc_aim(state, 'pc1')
        before, proof, _ = aim(prepared(source()))
        changed_request = replace(proof.request, awareness_test=replace(proof.request.awareness_test,
            profile=InlineProfile(2, 4)))
        with self.assertRaises(ValueError):
            project_npc_aim_step(before, replace(proof, request=changed_request))
        forged = deepcopy(proof)
        object.__setattr__(forged.result.bonus, 'bonus_dice', 20)
        with self.assertRaises(ValueError):
            project_npc_aim_step(before, forged)
        with self.assertRaises(ValueError):
            validate_pc_npc_aim_history(journal(before.source, proof, proof))

    def test_run_and_failed_charge_lose_aim_only_on_the_actual_manoeuvre_receipt(self):
        for kind in (ManoeuvreKind.RUN, ManoeuvreKind.CHARGE):
            with self.subTest(kind=kind):
                before, aimed, state = aim(prepared(source(distance=Range.LONG)))
                state = next_npc_turn(state)
                clock = reserve_combat_action_slot(CombatActionSlotRequest('manoeuvre:reserve',
                    state.round_state, 'minion1', CombatActionDeclaration(CombatActionKind.MANOEUVRE,
                        manoeuvre=kind), ActionSlotGrant.STANDARD)).state
                destination = state.source.facts.zone_id + ':zone:1'
                if kind is ManoeuvreKind.RUN:
                    request = RunActionExecutionRequest('npc:run', clock, state.battlefield.spatial,
                        'minion1', 1, MovementSpeed.NORMAL, ConditionState(), destination)
                    result = execute_run_action(request)
                    changed = with_actor_placement(replace(state.battlefield,
                        spatial=result.spatial_state), 'minion1', destination)
                    proof = PcBattlefieldRunProof(request, result, state.battlefield,
                        changed, target_id='pc1')
                    receipt = result.slot.execution
                else:
                    request = ChargeMovementRequest('npc:charge', clock, state.battlefield.spatial,
                        'minion1', 'pc1', 1, MovementSpeed.NORMAL, ConditionState(), Range.LONG,
                        False, TestRequest('npc:charge:athletics', InlineProfile(1, 3)), destination)
                    rng = ScriptedD10((10,))
                    result = execute_charge_movement(request, rng)
                    rng.assert_exhausted()
                    self.assertFalse(result.attack_allowed)
                    changed = with_actor_placement(replace(state.battlefield,
                        spatial=result.spatial_state), 'minion1', destination)
                    proof = PcBattlefieldChargeProof(request, result, state.battlefield, changed)
                    receipt = result.round_state.active_turn.action_slots[0].execution
                view = journal(state.source, aimed, proof)
                consumed = expected_npc_aim_consumption(view)
                self.assertEqual(consumed.action, receipt)
                self.assertIs(consumed.follow_up.outcome, AimFollowUpOutcome.LOST)
                self.assertIsNone(current_npc_aim(journal(state.source, aimed, proof, consumed), 'minion1'))
                validate_pc_npc_aim_history(journal(state.source, aimed, proof, consumed))

    def test_successful_charge_movement_does_not_consume_aim_before_its_attack(self):
        _, aimed, state = aim(prepared(source(distance=Range.MEDIUM)))
        state = next_npc_turn(state)
        clock = reserve_combat_action_slot(CombatActionSlotRequest('charge:reserve',
            state.round_state, 'minion1', CombatActionDeclaration(CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.CHARGE), ActionSlotGrant.STANDARD)).state
        request = ChargeMovementRequest('npc:charge', clock, state.battlefield.spatial,
            'minion1', 'pc1', 1, MovementSpeed.NORMAL, ConditionState(), Range.MEDIUM, False)
        result = execute_charge_movement(request, ScriptedD10(()))
        self.assertTrue(result.attack_allowed)
        self.assertIsNone(result.round_state.active_turn.action_slots[0].execution)
        destination = result.spatial_state.placement_for('minion1').zone_id
        changed = with_actor_placement(replace(state.battlefield, spatial=result.spatial_state),
            'minion1', destination, close_to_ids=('pc1',))
        proof = PcBattlefieldChargeProof(request, result, state.battlefield, changed)
        view = journal(state.source, aimed, proof)
        self.assertIsNone(expected_npc_aim_consumption(view))
        self.assertEqual(current_npc_aim(view, 'minion1'), aimed.result)


if __name__ == '__main__':
    unittest.main()
