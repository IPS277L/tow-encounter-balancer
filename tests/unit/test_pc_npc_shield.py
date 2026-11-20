"""NPC physical Shield queries/projections and actual generic Recover execution.

Small views isolate the owner helpers; the native integration separately proves
the preceding shots/reloads against the complete combat journal.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from towr.domain.armour_models import ArmourLoadout, BodyArmour, HelmetKind, ShieldKind
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.exacting_test_models import ExactingTestContribution
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon, generated_weapon_allows_shield
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, build_pc_battlefield, with_actor_placement
from towr.domain.pc_mount_models import CombatMount,PcMountedState
from towr.domain.pc_npc_ranged_models import (
    initial_pc_npc_weapon_inventories, pc_npc_ranged_weapon, npc_ranged_inventory_update,
)
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_shield_models import (
    NpcShieldLocation, PcNpcShieldState, NpcShieldGroundPosition,
    build_npc_shield_pickup, complete_npc_shield_pickup, expected_npc_shield_drop,
    initial_npc_shields, npc_shield_drop_updates, npc_shield_item_close,
    npc_shield_pickup_updates, validate_npc_shields,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.reload_models import begin_reload_cycle, create_initial_ranged_weapon_reload_state
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.weapon_inventory_models import weapon_reload_cycle_id
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnState,
)
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import reserve_combat_action_slot


class NeverRoll:
    def randint(self, low, high):
        raise AssertionError('standard Shield Recover must not roll dice')


def view(*, shield=ShieldKind.SHIELD, weapon=GeneratedWeapon.PISTOL,
        loaded=False, battlefield=True, armour=None, mount=None):
    firearm = weapon is not GeneratedWeapon.REPEATER_HANDBOW
    facts = GeneratedNpc(3, 3, 4, 3, 4, 4, initial_generated_weapons(weapon),
        ArmourLoadout(shield=shield) if armour is None else armour, defence=4, mount=mount,
        ranged=GeneratedRangedFacts(3, 4, 3, 4,  True,
            True if firearm else None, True if firearm else None))
    enemy = facts.participant('enemy')
    policy = pc_npc_ranged_policy_for_generated(facts, 'enemy')
    source = SimpleNamespace(id='shield-fixture', enemies=(enemy,),
        pc_activation_order=('pc',), enemy_activation_order=('enemy',),
        npc_ranged_policies=(policy,), enemy=lambda actor: enemy,
        facts=SimpleNamespace(zone_id='arena', all_opponents_close=True))
    clock = CombatRoundState(1, (CombatTurnParticipant('pc', CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy', CombatSide.OPPOSITION)), completed_turn_entity_ids=('pc',),
        active_turn=CombatTurnState('enemy', CombatSide.OPPOSITION))
    state = SimpleNamespace(source=source, enemies=initial_pc_npc_weapon_inventories(source), round_state=clock,
        participant=lambda actor: SimpleNamespace(injury=CharacterInjuryState()),
        pending=(), pending_wound=None, magic_pending=None, exited_npc_ids=(), history=(),
        battlefield=build_pc_battlefield(PcBattlefieldSpec(RangedWeaponRange.CLOSE,
            RangedWeaponRange.LONG), ('pc',), ('enemy',), 'shield-fixture') if battlefield else None,
        npc_shields=initial_npc_shields(source),
        mounts=() if mount is None else (PcMountedState('enemy',mount,True),))
    state.enemy = lambda actor: next(value for value in state.enemies if value.state.actor_id == actor)
    if not loaded:
        weapon_state = pc_npc_ranged_weapon(state,'enemy')
        state.enemies = npc_ranged_inventory_update(state,'enemy',begin_reload_cycle(weapon_state,
            weapon_reload_cycle_id(weapon_state.weapon_instance_id,1)))
    return state


def policy_weapon(weapon):
    from towr.domain.ranged_weapon_profiles import RangedWeaponId
    return RangedWeaponId(weapon.value)


def apply_updates(state, changes, proof):
    for name, value in changes.items():
        setattr(state, name, value)
    state.history = (*state.history, proof)


def dropped_view(**kwargs):
    state = view(**kwargs)
    proof = expected_npc_shield_drop(state)
    apply_updates(state, npc_shield_drop_updates(state, proof), proof)
    return state


def finish_reload_view(state):
    """An explicit completed progress fixture, not a fabricated owner receipt."""
    before = pc_npc_ranged_weapon(state,'enemy')
    contribution = ExactingTestContribution('fixture:reload', 'fixture:dexterity',
        'enemy', before.required_successes)
    weapon = replace(before, loaded=True,
        exacting=replace(before.exacting, contributions=(contribution,)))
    state.enemies = npc_ranged_inventory_update(state,'enemy',weapon)


def reserve_recover(state):
    state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('shield:reserve',
        state.round_state, 'enemy', CombatActionDeclaration(CombatActionKind.RECOVER),
        ActionSlotGrant.STANDARD)).state


class PcNpcShieldTests(unittest.TestCase):
    def setUp(self):
        # These small views author an explicit selected-action fact. The native
        # integration exercises the real complete tactical decision owner.
        selected = patch('towr.domain.pc_melee_result_models.pc_melee_selected_action',
            return_value=CombatActionKind.IMPROVISE)
        selected.start()
        self.addCleanup(selected.stop)

    def test_one_handed_shooters_allow_real_shields_but_two_handed_weapons_do_not(self):
        for weapon in (GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL, GeneratedWeapon.REPEATER_HANDBOW):
            self.assertTrue(generated_weapon_allows_shield(weapon))
            self.assertEqual(len(initial_npc_shields(view(weapon=weapon).source)), 1)
        for weapon in (GeneratedWeapon.CROSSBOW, GeneratedWeapon.HANDGUN, GeneratedWeapon.LONGBOW):
            self.assertFalse(generated_weapon_allows_shield(weapon))

    def test_initial_bank_has_one_source_item_and_rejects_membership_changes(self):
        state = view(loaded=True)
        self.assertEqual(state.npc_shields, (PcNpcShieldState('enemy', 'enemy:shield',
            ShieldKind.SHIELD, NpcShieldLocation.HELD),))
        validate_npc_shields(state)
        state.npc_shields = ()
        with self.assertRaises(TypeError):
            validate_npc_shields(state)
        self.assertEqual(view(shield=None, loaded=True).npc_shields, ())

    def test_only_an_actual_empty_weapon_drops_its_held_source_shield(self):
        self.assertIsNone(expected_npc_shield_drop(view(loaded=True)))
        self.assertIsNone(expected_npc_shield_drop(view(shield=None)))
        state = view()
        proof = expected_npc_shield_drop(state)
        before = state.enemy('enemy').state.current_resilience
        self.assertTrue(state.enemy('enemy').state.holds_shield)
        apply_updates(state, npc_shield_drop_updates(state, proof), proof)
        self.assertFalse(state.enemy('enemy').state.holds_shield)
        self.assertEqual(state.enemy('enemy').state.current_resilience.bonus, before.bonus-1)
        self.assertTrue(npc_shield_item_close(state, 'enemy'))
        self.assertIsNone(expected_npc_shield_drop(state))
        with self.assertRaises(ValueError):
            npc_shield_drop_updates(state, proof)

    def test_body_helmet_mount_and_meteoric_ward_survive_exact_shield_subtraction(self):
        armour = ArmourLoadout((BodyArmour.METEORIC_IRON,), BodyArmour.METEORIC_IRON,
            HelmetKind.HUNT, ShieldKind.BRIARROOT, True)
        state = view(armour=armour, mount=CombatMount.HORSE)
        before = state.enemy('enemy').state.current_resilience
        proof = expected_npc_shield_drop(state)
        self.assertIs(proof.previous.kind, ShieldKind.BRIARROOT)
        after = proof.enemy.state.current_resilience
        self.assertEqual(after, replace(before, bonus=before.bonus-1))
        self.assertTrue(after.mundane_armour_ward)

    def test_pickup_waits_for_reload_and_actual_physical_proximity(self):
        state = dropped_view()
        self.assertIsNone(build_npc_shield_pickup(state))
        finish_reload_view(state)
        self.assertIsNotNone(build_npc_shield_pickup(state))
        zone = state.battlefield.spatial.placement_for('enemy').zone_id
        state.battlefield = with_actor_placement(state.battlefield, 'enemy', zone, close_to_ids=())
        self.assertFalse(npc_shield_item_close(state, 'enemy'))
        self.assertIsNone(build_npc_shield_pickup(state))

    def test_zero_bonus_worn_helmet_remains_armoured_after_drop(self):
        state = view(armour=ArmourLoadout(helmet=HelmetKind.HELMET, shield=ShieldKind.SHIELD))
        proof = expected_npc_shield_drop(state)
        resilience = proof.enemy.state.current_resilience
        self.assertEqual(resilience.bonus, 0)
        self.assertTrue(resilience.is_armoured)
        self.assertIs(resilience.armoured, True)

    def test_paid_standard_recover_restores_one_item_and_normal_condition_benefits(self):
        for shield in ShieldKind:
            for battlefield in (False, True):
                with self.subTest(shield=shield, battlefield=battlefield):
                    state = dropped_view(shield=shield, battlefield=battlefield)
                    finish_reload_view(state)
                    enemy = state.enemy('enemy')
                    state.enemies = (replace(enemy, state=replace(enemy.state,
                        injury=replace(enemy.state.injury, conditions=ConditionState(
                            frozenset((Condition.STAGGERED, Condition.PRONE, Condition.BURDENED)))))),)
                    reserve_recover(state)
                    request = build_npc_shield_pickup(state)
                    result = execute_recover_action(request, NeverRoll())
                    proof = complete_npc_shield_pickup(state, request, result)
                    apply_updates(state, npc_shield_pickup_updates(state, proof), proof)
                    self.assertTrue(state.enemy('enemy').state.holds_shield)
                    self.assertIs(state.npc_shields[0].location, NpcShieldLocation.HELD)
                    self.assertIsNone(state.npc_shields[0].ground)
                    self.assertTrue(state.round_state.active_turn.action_slots[0].executed)
                    self.assertEqual(state.enemy('enemy').state.injury.conditions.conditions,
                        frozenset((Condition.BURDENED,)))
                    self.assertIsNone(build_npc_shield_pickup(state))
                    with self.assertRaises(ValueError):
                        npc_shield_pickup_updates(state, proof)

    def test_drop_proofs_retain_all_other_participant_and_item_facts(self):
        state = view()
        proof = expected_npc_shield_drop(state)
        with self.assertRaises(ValueError):
            replace(proof, state=replace(proof.state, kind=ShieldKind.BRIARROOT))
        with self.assertRaises(ValueError):
            replace(proof, enemy=replace(proof.enemy, state=replace(proof.enemy.state,
                wields_weapon=False)))
        with self.assertRaises(ValueError):
            replace(proof, weapon=create_initial_ranged_weapon_reload_state('enemy:weapon', policy_weapon(GeneratedWeapon.PISTOL)))
        detached = replace(proof, history_index=1)
        with self.assertRaises(ValueError):
            npc_shield_drop_updates(state, detached)

    def test_bank_rejects_an_erased_drop_receipt_and_a_forged_marker(self):
        state = dropped_view()
        state.history = ()
        with self.assertRaises(ValueError):
            validate_npc_shields(state)
        fresh = view(loaded=True)
        foreign = deepcopy(fresh.npc_shields[0])
        object.__setattr__(foreign, 'item_id', 'another:shield')
        fresh.npc_shields = (foreign,)
        with self.assertRaises((TypeError, ValueError)):
            validate_npc_shields(fresh)
        fresh = view(loaded=True)
        zone = fresh.battlefield.spatial.placement_for('enemy').zone_id
        fresh.battlefield = replace(fresh.battlefield, spatial=replace(fresh.battlefield.spatial,
            placements=(*fresh.battlefield.spatial.placements,
                SpatialEntityPlacement('enemy:shield:ground', 'objects', zone))))
        with self.assertRaisesRegex(ValueError, 'held NPC Shield cannot retain'):
            validate_npc_shields(fresh)

    def test_pending_work_broken_defenceless_and_defeat_block_equipment_actions(self):
        for condition in (Condition.BROKEN, Condition.DEFENCELESS):
            state = view()
            enemy = state.enemy('enemy')
            state.enemies = (replace(enemy, state=replace(enemy.state,
                injury=replace(enemy.state.injury, conditions=ConditionState(frozenset((condition,)))))),)
            self.assertIsNone(expected_npc_shield_drop(state))
        state = view()
        state.pending = (object(),)
        self.assertIsNone(expected_npc_shield_drop(state))

    def test_drop_waits_for_a_selected_reload_instead_of_another_pending_action(self):
        state = view()
        with patch('towr.domain.pc_melee_result_models.pc_melee_selected_action',
                return_value=CombatActionKind.RECOVER):
            self.assertIsNone(expected_npc_shield_drop(state))
        self.assertIsNotNone(expected_npc_shield_drop(state))

    def test_item_fields_are_exact_and_ground_is_required_only_when_dropped(self):
        held = PcNpcShieldState('enemy', 'enemy:shield', ShieldKind.SHIELD, NpcShieldLocation.HELD)
        for changes in (dict(kind='shield'), dict(location='held'), dict(item_id='foreign'),
                dict(ground=NpcShieldGroundPosition('zone', ('enemy',)))):
            with self.assertRaises((TypeError, ValueError)):
                replace(held, **changes)
        with self.assertRaises(TypeError):
            replace(held, location=NpcShieldLocation.DROPPED)


if __name__ == '__main__':
    unittest.main()
