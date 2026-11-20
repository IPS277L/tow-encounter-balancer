"""Prepared native-owner geometry and real K1 movement factories.

Every view retains a complete admitted encounter source and its actual actors.
Changed placements, defeats, exits and bindings are explicit preparation-only
observations, not invented native journals. Runner/replay coverage is separate.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from tests.support.talent_sources import free_talent
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_acrobatic_models import actor_acrobatic_source
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec, PcBattlefieldSpec, with_actor_placement,
)
from towr.domain.pc_battlefield_manoeuvre_models import (
    build_pc_battlefield_charge, build_pc_battlefield_run,
    build_pc_battlefield_run_extension,
)
from towr.domain.pc_battlefield_movement_models import (
    aerialmovement_permission, battlefield_path_available,
)
from towr.domain.pc_briarroot_models import PcBriarrootBinding
from towr.domain.pc_melee_result_models import PcMeleeState
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_movement_block_models import pc_enemy_path_blockers
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.talent_acrobatic_models import ACROBATIC_RULE_ID
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlotRequest, CombatRoundState, CombatSide, CombatTurnState,
    ManoeuvreKind,
)
from towr.rules.run_action_execution import (
    execute_run_action, resolve_run_athletics_extension,
)
from towr.rules.turn_resolution import reserve_combat_action_slot


class GeometryView(SimpleNamespace):
    """Reuse the actual owner queries without claiming a replayed position."""

    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies


def view(*, actor='pc1', acrobatic=True, blocking=True, mount=None,
         airspace=True, distance=R.EXTREME, briarroot=False):
    original = automatic_source(pc_count=2, enemy_count=3)
    talents = (free_talent(TalentId.ACROBATIC),) if acrobatic else ()
    rider_kind = RiderKind.HUMAN if mount in (CombatMount.PEGASUS, CombatMount.DEMIGRYPH) else None
    party = tuple(replace(member,
        talents=talents if member.actor_id == actor else (),
        mount=mount if member.actor_id == actor else None,
        rider_kind=rider_kind if member.actor_id == actor else None)
        for member in original.party)
    enemies = tuple(GeneratedNpc(3, 3, 3, 3, 4, 4,
        initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(shield=ShieldKind.BRIARROOT if briarroot and index == 1 else None),
        defence=4, talents=talents if identifier == actor else (),
        mount=mount if identifier == actor else None,
        rider_kind=rider_kind if identifier == actor else None,
        ).participant(identifier)
        for index, identifier in enumerate(original.enemy_activation_order, 1))
    source = replace(original, party=party, enemies=enemies,
        facts=replace(original.facts, all_opponents_close=distance is R.CLOSE,
            can_leave_zone=True, unmounted=mount is None),
        battlefield=PcBattlefieldSpec(distance, R.LONG,
            airspace=PcAirspaceSpec() if airspace else None,
            enemy_zone_blocking=blocking))
    state = tactical_snapshot(source)
    return GeometryView(**{name: getattr(state, name) for name in state.__dataclass_fields__},
        exited_npc_ids=())


def zone(state, index, *, air=False):
    return f'{state.source.facts.zone_id}:{"air" if air else "zone"}:{index}'


def place(state, actor, index, *, close=()):
    state.battlefield = with_actor_placement(state.battlefield, actor,
        zone(state, index), close_to_ids=close)


def reserve(state, actor, kind):
    if actor in state.source.enemy_activation_order:
        state.round_state = CombatRoundState(state.round_state.round_number,
            state.round_state.participants,
            completed_turn_entity_ids=state.source.pc_activation_order,
            active_turn=CombatTurnState(actor, CombatSide.OPPOSITION))
    state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('paths:reserve',
        state.round_state, actor, CombatActionDeclaration(CombatActionKind.MANOEUVRE,
            manoeuvre=kind), ActionSlotGrant.STANDARD)).state


class AcrobaticNativePathsTests(unittest.TestCase):
    def test_intermediate_enemy_is_preserved_but_destination_is_not_invented_as_crossed(self):
        for acrobatic in (False, True):
            with self.subTest(acrobatic=acrobatic):
                state = view(acrobatic=acrobatic)
                place(state, 'minion1', 1)
                place(state, 'minion2', 2)
                path = (zone(state, 1), zone(state, 2))
                before = deepcopy(state.battlefield)
                self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path), ('minion1',))
                self.assertEqual(battlefield_path_available(state, 'pc1', path), acrobatic)
                self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path[:1]), ())
                self.assertTrue(battlefield_path_available(state, 'pc1', path[:1]))
                self.assertEqual(state.battlefield, before)
                self.assertIn('minion1', tuple(row.entity_id for row in before.spatial.placements))

    def test_origin_close_is_an_actual_side_bound_source_not_every_same_zone_occupant(self):
        state = view()
        place(state, 'minion1', 0)  # Same Zone at Short, without an invented Close link.
        place(state, 'minion2', 0, close=('pc1',))
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', (zone(state, 1),)), ('minion2',))
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', ()), ())
        place(state, 'pc2', 1)
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', (zone(state, 1), zone(state, 2))),
            ('minion2',))  # An ally in the intermediate Zone is not an enemy.

        opposite = view(actor='minion1')
        place(opposite, 'minion1', 0)
        place(opposite, 'pc1', 1)
        place(opposite, 'pc2', 2)
        place(opposite, 'minion2', 1)
        self.assertEqual(pc_enemy_path_blockers(opposite, 'minion1',
            (zone(opposite, 1), zone(opposite, 2))), ('pc1',))

    def test_prepared_defeat_and_exit_remove_only_the_unavailable_actor_not_placements(self):
        state = view()
        for actor in state.source.enemy_activation_order:
            place(state, actor, 1)
        path = (zone(state, 1), zone(state, 2))
        spatial = deepcopy(state.battlefield.spatial)
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path),
            ('minion1', 'minion2', 'minion3'))
        enemy = state.enemy('minion1')
        defeated = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
            wounds=enemy.state.injury.wound_limit, defeated=True)))
        state.enemies = tuple(defeated if item.state.actor_id == 'minion1' else item
            for item in state.enemies)
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path), ('minion2', 'minion3'))
        state.exited_npc_ids = ('minion2',)  # Explicit prepared observation, no exit journal claimed.
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path), ('minion3',))
        self.assertEqual(state.battlefield.spatial, spatial)
        self.assertEqual(tuple(item.state.actor_id for item in state.enemies),
            state.source.enemy_activation_order)

    def test_gm_toggle_keeps_the_snapshot_and_invalid_geometry_is_rejected(self):
        state = view(acrobatic=False)
        place(state, 'minion1', 1)
        path = (zone(state, 1), zone(state, 2))
        before = deepcopy(state.battlefield)
        self.assertFalse(battlefield_path_available(state, 'pc1', path))
        state.source = replace(state.source,
            battlefield=replace(state.source.battlefield, enemy_zone_blocking=False))
        self.assertEqual(pc_enemy_path_blockers(state, 'pc1', path), ())
        self.assertTrue(battlefield_path_available(state, 'pc1', path))
        self.assertEqual(state.battlefield, before)
        state.source = replace(state.source,
            battlefield=replace(state.source.battlefield, enemy_zone_blocking=True))
        for invalid in ((zone(state, 2),), ('outside:actual:graph',)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                pc_enemy_path_blockers(state, 'pc1', invalid)
        with self.assertRaises(ValueError):
            pc_enemy_path_blockers(state, 'foreign-actor', path)

    def test_c9_takeoff_requires_the_actual_talent_mount_and_airspace_for_both_roles(self):
        for actor in ('pc1', 'minion1'):
            for acrobatic, mount, allowed in ((False, CombatMount.PEGASUS, False),
                    (True, CombatMount.HORSE, False), (True, CombatMount.PEGASUS, True)):
                with self.subTest(actor=actor, acrobatic=acrobatic, mount=mount):
                    state = view(actor=actor, acrobatic=acrobatic, mount=mount, distance=R.CLOSE)
                    before = deepcopy(state.battlefield)
                    path = (zone(state, 0, air=True),)
                    self.assertEqual(aerialmovement_permission(state, actor, path), allowed)
                    self.assertEqual(battlefield_path_available(state, actor, path), allowed)
                    self.assertEqual(state.battlefield, before)
            state = view(actor=actor, mount=CombatMount.PEGASUS, airspace=False, distance=R.CLOSE)
            with self.subTest(actor=actor, no_airspace=True), self.assertRaises(ValueError):
                aerialmovement_permission(state, actor, (zone(state, 0, air=True),))

    def test_acrobatic_does_not_release_briarroot_or_allow_charge_begun_close(self):
        state = view(mount=CombatMount.PEGASUS, distance=R.CLOSE, briarroot=True)
        item = state.participant('pc1').weapon_inventory.active_item_id
        state.briarroot_bindings = (PcBriarrootBinding('prepared:vines', 'minion1', 'pc1',
            item, 'prepared:attack', 0),)
        path = (zone(state, 0, air=True),)
        self.assertTrue(aerialmovement_permission(state, 'pc1', path))
        self.assertFalse(battlefield_path_available(state, 'pc1', path))

        state = view(distance=R.CLOSE)
        place(state, 'minion2', 1)
        reserve(state, 'pc1', ManoeuvreKind.CHARGE)
        with self.assertRaisesRegex(ValueError, 'beginning-of-turn Close'):
            build_pc_battlefield_charge(state, 'minion2')

    def test_real_run_extension_factory_retains_ownership_and_drops_old_close_blockers(self):
        for actor, target, old_blocker in (('pc1', 'minion1', 'minion2'),
                ('minion1', 'pc1', 'pc2')):
            with self.subTest(actor=actor):
                state = view(actor=actor, airspace=False)
                place(state, actor, 0)
                place(state, target, 3)
                place(state, old_blocker, 0, close=(actor,))
                before = deepcopy(state.battlefield)
                reserve(state, actor, ManoeuvreKind.RUN)
                request = build_pc_battlefield_run(state, target)
                self.assertEqual(request.path_entity_ids, (old_blocker,))
                base = execute_run_action(request)
                self.assertEqual(base.destination_zone_id, zone(state, 1))
                extension = build_pc_battlefield_run_extension(state, base, target)
                self.assertIsNotNone(extension)
                self.assertEqual(extension.acrobatic, actor_acrobatic_source(state, actor))
                self.assertEqual(extension.acrobatic.actor_id, actor)
                self.assertEqual(extension.destination_zone_id, zone(state, 2))
                self.assertEqual(extension.path_entity_ids, ())  # Former Close does not follow the actor.
                self.assertIs(extension.base_run, base)
                dice = extension.athletics_test.profile.base_dice
                rng = ScriptedD10([1]*dice)
                result = resolve_run_athletics_extension(extension, rng)
                rng.assert_exhausted()
                self.assertEqual(result.applied_rule_ids.count(ACROBATIC_RULE_ID), 1)
                self.assertEqual(result.path_entity_ids, ())
                self.assertEqual(result.acrobatic, extension.acrobatic)
                self.assertEqual(state.battlefield, before)  # Factories never fake a native owner transition.


if __name__ == '__main__':
    unittest.main()
