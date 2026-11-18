"""Explicit sky geometry and actual Fly route eligibility, without MC estimates."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec, PcBattlefieldSpec, PcBattlefieldState, build_pc_battlefield,
    battlefield_is_midair, battlefield_ground_below, battlefield_range, with_actor_placement,
)
from towr.domain.pc_battlefield_movement_models import (
    aerialmovement_permission, battlefield_path_available, expected_pc_battlefield_move,
    PcBattlefieldMoveProof, _ranges,
)
from towr.domain.pc_battlefield_manoeuvre_models import (
    build_pc_battlefield_charge, build_pc_battlefield_run, build_pc_battlefield_run_extension,
    _run_athletics, _attack_skill, proposed_pc_battlefield_manoeuvre,
)
from towr.domain.pc_melee_models import PcMeleePolicy, PcTwoHandedGrip, PcWeaponHand
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.injury_models import WoundRecord, WoundEntryId
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_npc_shield_models import (
    PcNpcShieldState, NpcShieldLocation, NpcShieldGroundPosition,
    _add_marker as add_shield_marker, _remove_marker as remove_shield_marker,
    _drop_position as shield_drop_position,
)
from towr.domain.pc_weighted_net_models import (
    PcWeightedNetState, PcNetLocation, PcNetGroundPosition,
    _add_marker as add_net_marker, _remove_marker as remove_net_marker,
    complete_weighted_net_throw, weighted_net_profile, weighted_net_release_item,
)
from towr.domain.armour_models import (
    ShieldKind, BodyArmour, HelmetKind, HELM_OF_HUNT_GLORIOUS_RULE_ID,
    HEAVY_ARMOUR_AGILITY_RULE_ID, FULL_PLATE_ARMOUR_AGILITY_RULE_ID, BARDING_AGILITY_RULE_ID,
)
from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, ManoeuvreKind,
    CombatRoundState, CombatTurnState, CombatSide,
)
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.turn_resolution import reserve_combat_action_slot
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.armour_models import ArmourLoadout
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.attack_models import AttackRequest
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import TestRequest, TestQuality, Skill
from towr.domain.pc_briarroot_models import PcBriarrootBinding
from towr.rules.attack_action_execution import execute_attack_action
from tests.support.pc_melee_scripted import ScriptedD10
from towr.rules.run_action_execution import execute_run_action
from towr.rules.test_resolution import resolve_test, RerollAllFailures


R = RangedWeaponRange


def source(*, distance=R.SHORT, mounted=True, ranged=False, maximum=R.LONG):
    original = (make_pc_bow_scenario(max_rounds=1, backup=False) if ranged else
        automatic_source(pc_count=1, enemy_count=1, rounds=1))
    pc = replace(original.party[0], policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        mount=CombatMount.PEGASUS if mounted else None,
        rider_kind=RiderKind.HUMAN if mounted else None,
        combat_equipment=(PcWeaponItem('bow', original.party[0].pc.weapon,
            PcItemLocation.HELD, PcTwoHandedGrip.BOTH),) if ranged else None)
    return replace(original, party=(pc,), short_range_opening=None,
        facts=replace(original.facts, all_opponents_close=distance is R.CLOSE,
            can_leave_zone=True, unmounted=not mounted),
        battlefield=PcBattlefieldSpec(distance, maximum, airspace=PcAirspaceSpec()))


def preparation_view(original):
    """A geometry preparation view; arbitrary placements are never an owner replay."""
    state = tactical_snapshot(original)
    values = {name: getattr(state, name) for name in state.__dataclass_fields__}
    values.update(participant=state.participant, enemy=state.enemy,
        live_party=state.live_party, live_enemies=state.live_enemies,
        exited_npc_ids=state.exited_npc_ids)
    view = SimpleNamespace(**values)
    view.participant = lambda actor: next(member for member in view.party if member.actor_id == actor)
    view.enemy = lambda actor: next(enemy for enemy in view.enemies if enemy.state.actor_id == actor)
    return view


def air_above(state, actor='pc1'):
    ground = state.battlefield.spatial.placement_for(actor).zone_id
    return next(air for air, below in state.battlefield.air_to_ground if below == ground)


def reserve(state, manoeuvre, actor='pc1'):
    state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('flight:reserve',
        state.round_state, actor, CombatActionDeclaration(CombatActionKind.MANOEUVRE,
            manoeuvre=manoeuvre), ActionSlotGrant.STANDARD)).state


def npc_turn(state):
    state.round_state = CombatRoundState(state.round_state.round_number,
        state.round_state.participants, completed_turn_entity_ids=('pc1',),
        active_turn=CombatTurnState('minion1', CombatSide.OPPOSITION))


def helm_run_view(*, actor='pc1', retreat=False, drained=False):
    original = (make_pc_hochland_scenario(max_rounds=1, backup=False, use_second_action=False)
        if retreat else source(distance=R.EXTREME, mounted=False))
    helmet = ArmourLoadout(helmet=HelmetKind.HUNT)
    party, enemies = original.party, original.enemies
    if actor == 'pc1':
        member = replace(original.party[0], armour=helmet, armour_worn=True,
            policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            pc=replace(original.party[0].pc, armour_bonus=1),
            combat_equipment=(PcWeaponItem('rifle', original.party[0].pc.weapon,
                PcItemLocation.HELD, PcTwoHandedGrip.BOTH,initially_loaded=True),)
                if original.party[0].pc.ranged is not None else original.party[0].combat_equipment)
        party = (member,)
    else:
        npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), helmet, defence=4)
        enemies = (npc.participant('minion1'),)
    original = replace(original, party=party, enemies=enemies, short_range_opening=None,
        facts=replace(original.facts, all_opponents_close=False, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(R.SHORT if retreat else R.EXTREME, R.LONG))
    state = preparation_view(original)
    if actor != 'pc1':
        npc_turn(state)
    if drained:
        if actor == 'pc1':
            member = state.participant(actor)
            state.party = (replace(member, injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED))),)
        else:
            enemy = state.enemy(actor)
            state.enemies = (replace(enemy, state=replace(enemy.state,
                injury=replace(enemy.state.injury,
                    conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED)))),)
    reserve(state, ManoeuvreKind.RUN, actor)
    target = 'minion1' if actor == 'pc1' else 'pc1'
    run = execute_run_action(build_pc_battlefield_run(state, target))
    return state, build_pc_battlefield_run_extension(state, run, target)


class NeverRoll:
    def randint(self, low, high):
        return 10


class PcFlightTests(unittest.TestCase):
    def test_no_usable_rider_hands_position_for_real_mount_melee(self):
        for distance in (R.MEDIUM, R.EXTREME):
            with self.subTest(distance=distance):
                state = preparation_view(source(distance=distance, ranged=True))
                member = state.participant('pc1')
                injury = replace(member.injury, wounds=tuple(WoundRecord(index,
                    WoundEntryId.SLASHED_FOREARMS, 16, (6, 10), effect_resolved=True)
                    for index in (1, 2)))
                state.party = (replace(member,
                    injury=injury,
                    weapon_inventory=replace(member.weapon_inventory, items=tuple(
                        replace(item, location=PcItemLocation.DROPPED, grip=None)
                        for item in member.weapon_inventory.items)),
                    body_facts=tuple(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,
                        index+1, hand) for index, hand in enumerate(PcWeaponHand))),)
                self.assertEqual(_ranges(state, 'pc1'), (R.CLOSE, R.CLOSE, R.CLOSE, True))
                self.assertIs(_attack_skill(state, 'pc1'), Skill.MELEE)
                if distance is R.MEDIUM:
                    proposal = proposed_pc_battlefield_manoeuvre(state)
                    self.assertIsNotNone(proposal)
                    self.assertIs(proposal.kind, ManoeuvreKind.CHARGE)
                else:
                    move = expected_pc_battlefield_move(state)
                    self.assertIsNotNone(move)
                    self.assertFalse(battlefield_is_midair(move.state, 'pc1'))
                state.party = (replace(state.party[0], injury=replace(injury,
                    conditions=injury.conditions.with_condition(Condition.PRONE))),)
                self.assertIsNone(proposed_pc_battlefield_manoeuvre(state))
                self.assertIsNone(expected_pc_battlefield_move(state))

    def test_dropped_npc_weapon_positions_for_mount_without_reusing_shooting(self):
        original = source(distance=R.MEDIUM, mounted=False)
        npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout(), defence=4, mount=CombatMount.HORSE)
        original = replace(original, enemies=(npc.participant('minion1'),),
            facts=replace(original.facts, unmounted=False))
        state = preparation_view(original)
        npc_turn(state)
        enemy = state.enemy('minion1')
        state.enemies = (replace(enemy, state=replace(enemy.state, wields_weapon=False)),)
        self.assertEqual(_ranges(state, 'minion1'), (R.CLOSE, R.CLOSE, R.CLOSE, True))
        self.assertIs(_attack_skill(state, 'minion1'), Skill.MELEE)
        self.assertIs(proposed_pc_battlefield_manoeuvre(state).kind, ManoeuvreKind.CHARGE)

    def test_helm_of_hunt_makes_actual_pursuit_extension_glorious_for_both_sides(self):
        for actor in ('pc1', 'minion1'):
            with self.subTest(actor=actor):
                _, extension = helm_run_view(actor=actor)
                self.assertIsNotNone(extension)
                request = extension.athletics_test
                self.assertEqual(tuple(item.rule_id for item in request.quality_modifiers),
                    (HELM_OF_HUNT_GLORIOUS_RULE_ID,))
                result = resolve_test(request, ScriptedD10([1]*request.profile.base_dice),
                    decisions=RerollAllFailures())
                self.assertIs(result.trace.quality, TestQuality.GLORIOUS)

    def test_helm_pursuit_context_excludes_retreat_and_respects_actual_drained(self):
        state, retreat = helm_run_view(retreat=True)
        # The automatic policy stops at optimum range; taking another optional
        # physical Run step away remains a retreat context rather than pursuit.
        self.assertIsNone(retreat)
        base = execute_run_action(build_pc_battlefield_run(state,'minion1'))
        origin = base.spatial_state.placement_for('pc1').zone_id
        target = base.spatial_state.placement_for('minion1').zone_id
        from towr.domain.pc_battlefield_movement_models import _zone_distance
        destination = max(base.spatial_state.graph.adjacent_zone_ids(origin),
            key=lambda zone: _zone_distance(base.spatial_state.graph,zone,target))
        test = _run_athletics(state,base,destination,'minion1')
        self.assertFalse(any(item.rule_id == HELM_OF_HUNT_GLORIOUS_RULE_ID
            for item in test.quality_modifiers))
        for actor in ('pc1', 'minion1'):
            with self.subTest(actor=actor):
                _, drained = helm_run_view(actor=actor, drained=True)
                self.assertIsNotNone(drained)
                self.assertFalse(any(item.rule_id == HELM_OF_HUNT_GLORIOUS_RULE_ID
                    for item in drained.athletics_test.quality_modifiers))

    def test_actual_long_charge_athletics_prepares_mount_control_for_both_sides(self):
        cases = ((CombatMount.BRETONNIAN_WARHORSE, BodyArmour.HEAVY, ()),
            (CombatMount.BRETONNIAN_WARHORSE, BodyArmour.FULL_PLATE,
                ((FULL_PLATE_ARMOUR_AGILITY_RULE_ID, -1),)),
            (CombatMount.ELVEN_STEED, BodyArmour.HEAVY,
                ((HEAVY_ARMOUR_AGILITY_RULE_ID, -1), (BARDING_AGILITY_RULE_ID, -1),
                    ('RULE-MOUNT-002:elven-steed', 1))))
        for actor in ('pc1', 'minion1'):
            for mount, body, expected in cases:
                with self.subTest(actor=actor, mount=mount, body=body):
                    original = source(distance=R.LONG, mounted=False)
                    armour = ArmourLoadout((body,), body, barding=True)
                    if actor == 'pc1':
                        member = replace(original.party[0], mount=mount, armour=armour,
                            pc=replace(original.party[0].pc, strength=4,
                                armour_bonus=2 if body is BodyArmour.HEAVY else 3))
                        original = replace(original, party=(member,),
                            facts=replace(original.facts, unmounted=False))
                    else:
                        npc = GeneratedNpc(3, 4, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), armour,
                            defence=4, mount=mount)
                        original = replace(original, enemies=(npc.participant('minion1'),),
                            facts=replace(original.facts, unmounted=False))
                    state = preparation_view(original)
                    if actor != 'pc1':
                        npc_turn(state)
                    reserve(state, ManoeuvreKind.CHARGE, actor)
                    target = 'minion1' if actor == 'pc1' else 'pc1'
                    request = build_pc_battlefield_charge(state, target).athletics_test
                    self.assertIsNotNone(request)
                    self.assertEqual(tuple((item.rule_id, item.amount) for item in request.dice_modifiers), expected)
                    self.assertEqual(request.profile.maximum_dice, 6)

    def test_airspace_premise_is_explicit_and_exact(self):
        plain = build_pc_battlefield(PcBattlefieldSpec(R.SHORT, R.LONG), ('pc',), ('npc',), 'plain')
        self.assertEqual(plain.air_to_ground, ())
        for changes in (dict(fall_hazard_rating=True), dict(fall_hazard_rating=0),
                dict(fall_hazard_rating=2.0), dict(open_sky_confirmed=1), dict(open_sky_confirmed=False)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                PcAirspaceSpec(**changes)
        with self.assertRaises(TypeError):
            PcBattlefieldSpec(R.SHORT, R.LONG, airspace={})

    def test_parallel_air_layer_is_source_ordered_and_all_combatants_start_on_ground(self):
        battlefield = build_pc_battlefield(PcBattlefieldSpec(R.MEDIUM, R.LONG,
            airspace=PcAirspaceSpec()), ('pc',), ('npc',), 'sky')
        mapping = battlefield.air_to_ground
        self.assertEqual(len(mapping), 8)
        self.assertEqual(mapping[0], ('sky:air:-3', 'sky:zone:-3'))
        self.assertEqual(mapping[-1], ('sky:air:4', 'sky:zone:4'))
        for air, ground in mapping:
            self.assertTrue(battlefield.spatial.graph.are_adjacent(air, ground))
            self.assertTrue(battlefield_is_midair(battlefield, air, zone=True))
            self.assertEqual(battlefield_ground_below(battlefield, air), ground)
            self.assertEqual(battlefield_ground_below(battlefield, ground), ground)
        self.assertFalse(battlefield_is_midair(battlefield, 'pc'))
        self.assertFalse(battlefield_is_midair(battlefield, 'npc'))
        with self.assertRaises(ValueError):
            battlefield_ground_below(battlefield, 'missing')

    def test_mapping_rejects_forged_duplicates_disconnected_pairs_and_aliases(self):
        battlefield = build_pc_battlefield(PcBattlefieldSpec(R.SHORT, R.LONG,
            airspace=PcAirspaceSpec()), ('pc',), ('npc',), 'sky')
        first, second = battlefield.air_to_ground[:2]
        for mapping in ([first], (first, first), ((first[0], second[1]),), ((first[0], first[0]),)):
            with self.assertRaises((TypeError, ValueError)):
                replace(battlefield, air_to_ground=mapping)

    def test_non_flyers_cannot_cross_or_finish_in_air_and_ids_do_not_grant_flight(self):
        state = preparation_view(source(mounted=False))
        air = air_above(state)
        ground = state.battlefield.spatial.placement_for('pc1').zone_id
        self.assertFalse(aerialmovement_permission(state, 'pc1', (air,)))
        self.assertFalse(aerialmovement_permission(state, 'pc1', (air, ground)))
        self.assertTrue(aerialmovement_permission(state, 'pc1', ()))
        with self.assertRaises(ValueError):
            aerialmovement_permission(state, 'Pegasus', (air,))

    def test_flyer_checks_every_zone_and_the_actual_close_ground_start(self):
        state = preparation_view(source(distance=R.CLOSE))
        air = air_above(state)
        self.assertFalse(aerialmovement_permission(state, 'pc1', (air,)))
        ground = state.battlefield.spatial.placement_for('pc1').zone_id
        adjacent_ground = next(zone for zone in state.battlefield.spatial.graph.adjacent_zone_ids(ground)
            if not battlefield_is_midair(state.battlefield, zone, zone=True))
        above_next = next(a for a, g in state.battlefield.air_to_ground if g == adjacent_ground)
        self.assertFalse(aerialmovement_permission(state, 'pc1', (adjacent_ground, above_next)))
        self.assertTrue(aerialmovement_permission(state, 'pc1', (adjacent_ground,)))

    def test_separate_move_after_unlink_uses_its_new_start_but_run_extension_does_not(self):
        state = preparation_view(source(distance=R.CLOSE))
        original = state.battlefield
        ground = original.spatial.placement_for('pc1').zone_id
        next_ground = next(zone for zone in original.spatial.graph.adjacent_zone_ids(ground)
            if not battlefield_is_midair(original, zone, zone=True))
        current = with_actor_placement(original, 'pc1', next_ground)
        air = next(a for a, g in original.air_to_ground if g == next_ground)
        self.assertFalse(aerialmovement_permission(state, 'pc1', (air,), battlefield=current))
        # A separately paid action begins from its current actual separation.
        state.battlefield = current
        self.assertTrue(aerialmovement_permission(state, 'pc1', (air,)))

    def test_current_dismount_removes_flight_before_any_voluntary_move(self):
        state = preparation_view(source())
        air = air_above(state)
        state.battlefield = with_actor_placement(state.battlefield, 'pc1', air)
        next_air = next(zone for zone in state.battlefield.spatial.graph.adjacent_zone_ids(air)
            if battlefield_is_midair(state.battlefield, zone, zone=True))
        self.assertTrue(aerialmovement_permission(state, 'pc1', (next_air,)))
        state.mounts = (replace(state.mounts[0], mounted=False),)
        self.assertFalse(aerialmovement_permission(state, 'pc1', (next_air,)))

    def test_ground_charge_and_run_cannot_enter_an_airborne_target_zone(self):
        for kind, builder in ((ManoeuvreKind.CHARGE, build_pc_battlefield_charge),
                (ManoeuvreKind.RUN, build_pc_battlefield_run)):
            state = preparation_view(source(mounted=False))
            air = air_above(state)
            state.battlefield = with_actor_placement(state.battlefield, 'minion1', air)
            reserve(state, kind)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                builder(state, 'minion1')

    def test_real_ranged_pegasus_free_move_uses_air_and_preserves_k1_movement_usage(self):
        result = run_pc_melee_scenario(source(ranged=True), NeverRoll())
        self.assertIsNone(result.unsupported)
        move = next(step for step in result.steps if type(step.proof) is PcBattlefieldMoveProof
            and step.proof.actor_id == 'pc1')
        self.assertTrue(battlefield_is_midair(move.state.battlefield, 'pc1'))
        self.assertIn('pc1', move.state.battlefield.spatial.free_move_used_entity_ids)
        self.assertEqual(move.state.battlefield.air_to_ground, move.source.battlefield.air_to_ground)
        self.assertIsNone(expected_pc_battlefield_move(move.state))

    def test_within_zone_unlink_cannot_enable_a_second_free_flight_same_turn(self):
        original = source(distance=R.CLOSE, ranged=True, maximum=R.SHORT)
        state = preparation_view(original)
        proof = expected_pc_battlefield_move(state)
        self.assertIsNotNone(proof)
        self.assertIsNone(proof.movement_request)
        state.battlefield = proof.state
        state.history = (*state.history, proof)
        self.assertIsNone(expected_pc_battlefield_move(state))

    def test_existing_net_and_shield_markers_preserve_the_airspace_metadata(self):
        battlefield = build_pc_battlefield(PcBattlefieldSpec(R.SHORT, R.LONG,
            airspace=PcAirspaceSpec()), ('pc',), ('npc',), 'sky')
        ground = battlefield.spatial.placement_for('npc').zone_id
        shield = PcNpcShieldState('npc', 'npc:shield', ShieldKind.SHIELD,
            NpcShieldLocation.DROPPED, ground=NpcShieldGroundPosition(ground, ('npc',)))
        net = PcWeightedNetState('net', 'pc', PcNetLocation.FREE,
            ground=PcNetGroundPosition(ground, ('pc',)))
        for item, add, remove in ((shield, add_shield_marker, remove_shield_marker),
                (net, add_net_marker, remove_net_marker)):
            dropped = add(battlefield, item)
            self.assertEqual(dropped.air_to_ground, battlefield.air_to_ground)
            self.assertEqual(remove(dropped, item), battlefield)

    def test_briarroot_blocks_the_bound_attacker_route_but_not_the_bearer(self):
        original = source(distance=R.CLOSE)
        bearer = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout(shield=ShieldKind.BRIARROOT), defence=4)
        state = preparation_view(replace(original, enemies=(bearer.participant('minion1'),)))
        state.briarroot_bindings = (PcBriarrootBinding('vines', 'minion1', 'pc1',
            state.participant('pc1').weapon_inventory.active_item_id, 'attack', 0),)
        ground = state.battlefield.spatial.placement_for('pc1').zone_id
        next_ground = next(zone for zone in state.battlefield.spatial.graph.adjacent_zone_ids(ground)
            if not battlefield_is_midair(state.battlefield, zone, zone=True))
        self.assertFalse(battlefield_path_available(state, 'pc1', (next_ground,)))
        self.assertFalse(battlefield_path_available(state, 'pc1', ()))
        self.assertTrue(battlefield_path_available(state, 'pc1', (), close_to_ids=('minion1',)))
        self.assertTrue(battlefield_path_available(state, 'minion1', (next_ground,)))
        state.briarroot_bindings = ()
        self.assertTrue(battlefield_path_available(state, 'pc1', (next_ground,)))

    def test_dropped_shield_lands_directly_below_without_invented_close_contacts(self):
        state = preparation_view(source())
        air = air_above(state)
        ground = battlefield_ground_below(state.battlefield, air)
        state.battlefield = with_actor_placement(state.battlefield, 'pc1', air)
        position = shield_drop_position(state, 'pc1')
        self.assertEqual(position.zone_id, ground)
        self.assertEqual(position.initial_close_actor_ids, ())

    def test_free_net_lands_at_frozen_ground_shadow_but_bound_net_stays_with_airborne_target(self):
        original = source(mounted=False)
        member = original.party[0]
        member = replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.WEIGHTED_NET,
            throwing=4, ballistic_skill=2, brawn=4), initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=(PcWeaponItem('net', PcMeleeWeapon.WEIGHTED_NET,
                PcItemLocation.HELD, PcTwoHandedGrip.BOTH),))
        npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(),
            defence=4, mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN, brawn=4)
        scenario = replace(original, party=(member,), enemies=(npc.participant('minion1'),),
            facts=replace(original.facts, unmounted=False))
        for hit in (False, True):
            state = preparation_view(scenario)
            air = air_above(state, 'minion1')
            ground = battlefield_ground_below(state.battlefield, air)
            state.battlefield = with_actor_placement(state.battlefield, 'minion1', air)
            state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('net:reserve',
                state.round_state, 'pc1', CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)).state
            profile = weighted_net_profile(2, 4, member.pc.strength)
            request = AttackActionExecutionRequest('air-net', state.round_state, 'pc1', 'minion1', 1,
                KernelAttackRequest('air-net:kernel', 'minion1', AttackRequest('air-net:attack',
                    TestRequest('air-net:throwing', profile.test_profile), None, profile.condition_impact,
                    False, False), TargetInjuryPolicy.MINION, state.enemy('minion1').state.injury, False, False))
            execution = execute_attack_action(request, ScriptedD10([1, 10] if hit else [10, 10]))
            landing = complete_weighted_net_throw(state, request, execution)
            with self.subTest(hit=hit):
                if hit:
                    self.assertIs(landing.item.location, PcNetLocation.BOUND)
                    self.assertEqual(landing.item.bound_target_id, 'minion1')
                    self.assertIsNone(landing.item.ground)
                    self.assertEqual(landing.state, state.battlefield)
                    state.weighted_nets = (landing.item,)
                    unchanged, world = weighted_net_release_item(state, landing.item_id,
                        SimpleNamespace(resolution=SimpleNamespace(removed=False)))
                    self.assertEqual(unchanged, landing.item)
                    self.assertEqual(world, state.battlefield)
                    freed, world = weighted_net_release_item(state, landing.item_id,
                        SimpleNamespace(resolution=SimpleNamespace(removed=True)))
                    self.assertIs(freed.location, PcNetLocation.FREE)
                    self.assertEqual(freed.ground.zone_id, ground)
                    self.assertEqual(freed.ground.initial_close_actor_ids, ())
                    self.assertEqual(world.air_to_ground, state.battlefield.air_to_ground)
                else:
                    self.assertIs(landing.item.location, PcNetLocation.FREE)
                    self.assertEqual(landing.item.ground.zone_id, ground)
                    self.assertEqual(landing.item.ground.initial_close_actor_ids, ())
                    frozen = landing.state.spatial.placement_for(landing.item.marker_id)
                    next_air = next(zone for zone in landing.state.spatial.graph.adjacent_zone_ids(air)
                        if battlefield_is_midair(landing.state, zone, zone=True))
                    moved = with_actor_placement(landing.state, 'minion1', next_air)
                    self.assertEqual(moved.spatial.placement_for(landing.item.marker_id), frozen)


if __name__ == '__main__':
    unittest.main()
