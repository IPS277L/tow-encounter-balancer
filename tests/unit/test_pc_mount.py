"""Literal Horse facts and source-bound dismounts, without fabricated owner turns.

Small views isolate the bank rule; the native owner separately replays each
injury witness against its real Near Miss, spell and condition prefix.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from towr.domain.armour_models import BodyArmour
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
from random import Random
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.application.dynamic_encounter import (
    DynamicEncounterRequest, NpcSearchSpace, automatic_npc_search_space,
)
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, validate_generated_definition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon
from towr.domain.pc_mount_models import (
    CombatMount, HORSE_NOBLE_STEED_RULE_ID, PcDismountProof, PcMountedState,
    expected_pc_dismount, initial_pc_mounts, mount_resilience_bonus,
    pc_is_mounted, pc_mount_speed, pc_mounted_attack_effects, updated_pc_mounts,
    validate_pc_mounts,
)
from towr.domain.pc_weapon_models import pc_weapon_damage_modifiers
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy


def component(**changes):
    values = dict(weapon_skill=3, strength=3, toughness=3, agility=3, melee=4,
        athletics=4, defence=4, weapon=GeneratedWeapon.STAFF,
        light_armour=False, shield=False)
    values.update(changes)
    values['armour'] = light_loadout(light=values.pop('light_armour'), shield=values.pop('shield'))
    values['weapons'] = initial_generated_weapons(values.pop('weapon'), values.pop('weapon_grip', None))
    return GeneratedNpc(**values)


def scene(*, pc_mount=CombatMount.HORSE, npc_mount=CombatMount.HORSE):
    source = make_pc_melee_party_scenario(pc_count=2, enemy_count=1)
    party = tuple(replace(member, policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        mount=pc_mount if index == 0 else None, armour_worn=False)
        for index, member in enumerate(source.party))
    return replace(source, party=party,
        enemies=(component(mount=npc_mount).participant('minion1'),),
        facts=replace(source.facts, unmounted=pc_mount is None and npc_mount is None,
            all_opponents_close=False, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG))


def snapshot(source=None, *, prone=(), mounts=None, history=(), pending=(),
        pending_wound=None, magic_pending=None):
    source = scene() if source is None else source
    conditions = ConditionState(frozenset((Condition.PRONE,)))
    party = {member.actor_id: SimpleNamespace(injury=CharacterInjuryState(
        conditions=conditions if member.actor_id in prone else ConditionState()))
        for member in source.party}
    enemies = {enemy.state.actor_id: replace(enemy, state=replace(enemy.state,
        injury=replace(enemy.state.injury, conditions=conditions
            if enemy.state.actor_id in prone else ConditionState())))
        for enemy in source.enemies}
    return SimpleNamespace(source=source, party=tuple(party.values()),
        enemies=tuple(enemies.values()), participant=party.__getitem__, enemy=enemies.__getitem__,
        mounts=initial_pc_mounts(source) if mounts is None else mounts, companions=(), history=history,
        pending=pending, pending_wound=pending_wound, magic_pending=magic_pending)


def search_space(**changes):
    values = dict(weapon_skill=(3,), strength=(3,), toughness=(3,), agility=(3,),
        melee=(4,), athletics=(4,), defence=(4,), weapon=(GeneratedWeapon.STAFF,),
        armour=(None,), shield=(None,), abilities=((),), allowed_talents=())
    values.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **values)


def request(source, space):
    return DynamicEncounterRequest(source.party, source.facts, source.day_id, space,
        1, 1, .5, 2., 42, 1, 1, 1, 1, 2, 3, NpcDefeatDisposition.KILLED,
        battlefield=source.battlefield)


class PcMountTests(unittest.TestCase):
    def test_initial_bank_uses_only_explicit_components_and_keeps_source_order(self):
        source = scene()
        original = deepcopy(source)
        self.assertEqual(initial_pc_mounts(source), (
            PcMountedState('pc1', CombatMount.HORSE, True),
            PcMountedState('minion1', CombatMount.HORSE, True)))
        self.assertEqual(source, original)
        self.assertEqual(initial_pc_mounts(scene(pc_mount=None, npc_mount=None)), ())
        state = snapshot(source)
        self.assertTrue(pc_is_mounted(state, 'pc1'))
        self.assertFalse(pc_is_mounted(state, 'pc2'))
        self.assertTrue(pc_is_mounted(state, 'minion1'))
        validate_pc_mounts(state)

    def test_typed_mount_states_are_immutable_pickle_safe_and_reject_bad_sources(self):
        value = PcMountedState('rider', CombatMount.HORSE, True)
        self.assertEqual(pickle.loads(pickle.dumps(value)), value)
        with self.assertRaises(FrozenInstanceError):
            value.mounted = False
        for actor, mount, mounted in (('', CombatMount.HORSE, True),
                ('rider', 'horse', True), ('rider', CombatMount.HORSE, 1)):
            with self.subTest(actor=actor, mount=mount, mounted=mounted), self.assertRaises(TypeError):
                PcMountedState(actor, mount, mounted)
        with self.assertRaises(TypeError):
            component(mount='horse')
        source = scene()
        raw = SimpleNamespace(party=source.party, enemies=source.enemies, battlefield=None)
        with self.assertRaises(ValueError):
            initial_pc_mounts(raw)

    def test_horse_is_fast_and_adds_exactly_one_resilience_on_either_side(self):
        state = snapshot()
        for actor in ('pc1', 'minion1'):
            with self.subTest(actor=actor):
                self.assertEqual(mount_resilience_bonus(state, actor), 1)
                for base in MovementSpeed:
                    self.assertIs(pc_mount_speed(state, actor, base), MovementSpeed.SLOW
                        if base is MovementSpeed.SLOW else MovementSpeed.FAST)
        self.assertEqual(mount_resilience_bonus(state, 'pc2'), 0)
        self.assertIs(pc_mount_speed(state, 'pc2', MovementSpeed.SLOW), MovementSpeed.SLOW)
        for actor in ('foreign', '', True):
            with self.subTest(actor=actor), self.assertRaises((TypeError, ValueError)):
                pc_is_mounted(state, actor)
        with self.assertRaises(TypeError):
            pc_mount_speed(state, 'pc1', 'normal')

    def test_horse_bonus_counts_as_armoured_for_axe_and_crossbow_but_is_not_worn_armour(self):
        source = component(mount=CombatMount.HORSE)
        enemy = source.participant('rider')
        self.assertEqual(enemy.state.current_resilience, ResilienceProfile(3, 1))
        self.assertTrue(enemy.state.current_resilience.is_armoured)
        self.assertFalse((BodyArmour.LIGHT in source.armour.body))
        self.assertFalse(source.shield)
        for weapon in (PcMeleeWeapon.AXE, PcMeleeWeapon.CROSSBOW):
            with self.subTest(weapon=weapon):
                self.assertEqual(tuple(value.amount for value in pc_weapon_damage_modifiers(
                    weapon, enemy.state.current_resilience)), (1,))
                self.assertEqual(pc_weapon_damage_modifiers(weapon, ResilienceProfile(3)), ())
        self.assertFalse(scene().party[0].armour_worn)
        validate_generated_definition(enemy.definition)
        with self.assertRaises(ValueError):
            validate_generated_definition(replace(enemy.definition, resilience=ResilienceProfile(3)))

    def test_horse_bonus_composes_with_real_armour_and_shield(self):
        for armour, shield, total in ((False, False, 4), (True, False, 5),
                (False, True, 5), (True, True, 6)):
            with self.subTest(armour=armour, shield=shield):
                rider = component(mount=CombatMount.HORSE, light_armour=armour, shield=shield)
                self.assertEqual(rider.participant('rider').state.current_resilience.total, total)
                self.assertEqual(replace(rider, mount=None).participant('rider')
                    .state.current_resilience.total, total - 1)

    def test_only_actual_mounted_charge_gets_prone_before_give_ground(self):
        state = snapshot()
        for actor, target in (('pc1', 'minion1'), ('minion1', 'pc1')):
            with self.subTest(actor=actor):
                effects = pc_mounted_attack_effects(state, actor, target, is_charge=True)
                self.assertEqual(len(effects), 1)
                self.assertEqual(effects[0].rule_id, HORSE_NOBLE_STEED_RULE_ID)
                self.assertFalse(effects[0].affects_monstrosities)
                self.assertEqual(pc_mounted_attack_effects(state, actor, target, is_charge=False), ())
        self.assertEqual(pc_mounted_attack_effects(state, 'pc2', 'minion1', is_charge=True), ())
        definition = SimpleNamespace(injury_policy=TargetInjuryPolicy.MONSTROSITY)
        state.enemy = lambda actor: SimpleNamespace(definition=definition)
        self.assertEqual(pc_mounted_attack_effects(state, 'pc1', 'minion1', is_charge=True), ())
        with self.assertRaises(TypeError):
            pc_mounted_attack_effects(state, 'pc1', 'minion1', is_charge=1)

    def test_dismount_waits_for_near_miss_and_injury_queue_but_not_the_next_spell_task(self):
        self.assertIsNone(expected_pc_dismount(snapshot()))
        self.assertIsNone(expected_pc_dismount(snapshot(prone=('pc2',))))
        self.assertIsNone(expected_pc_dismount(snapshot(prone=('pc1',), pending=(object(),))))
        self.assertIsNone(expected_pc_dismount(snapshot(prone=('pc1',), pending_wound=object())))
        state = snapshot(prone=('pc1',), magic_pending=object())
        proof = expected_pc_dismount(state)
        self.assertIs(type(proof), PcDismountProof)
        self.assertEqual(proof.source_injury, state.participant('pc1').injury)
        self.assertEqual(proof.history_index, 0)
        self.assertEqual(proof.source_id, state.source.id + ':dismount:0:pc1')

    def test_pc_and_npc_dismount_once_in_source_order_and_horse_does_not_return(self):
        state = snapshot(prone=('pc1', 'minion1'))
        first = expected_pc_dismount(state)
        state.mounts = updated_pc_mounts(state, first)
        state.history += (first,)
        validate_pc_mounts(state)
        second = expected_pc_dismount(state)
        self.assertEqual(second.actor_id, 'minion1')
        self.assertIs(type(second.source_injury), ProfileInjuryState)
        state.mounts = updated_pc_mounts(state, second)
        state.history += (second,)
        validate_pc_mounts(state)
        self.assertIsNone(expected_pc_dismount(state))
        for actor in ('pc1', 'minion1'):
            self.assertFalse(pc_is_mounted(state, actor))
            self.assertEqual(mount_resilience_bonus(state, actor), 0)
            self.assertIs(pc_mount_speed(state, actor, MovementSpeed.NORMAL), MovementSpeed.NORMAL)
        self.assertEqual(pc_mounted_attack_effects(state, 'pc1', 'minion1', is_charge=True), ())
        # Source still describes the initial Horse; it is not rewritten as a new actor.
        self.assertIs(state.source.party[0].mount, CombatMount.HORSE)
        self.assertEqual(len(state.source.enemies), 1)
        with self.assertRaises(ValueError):
            updated_pc_mounts(state, first)

    def test_forged_witness_actor_or_source_prefix_cannot_dismount(self):
        state = snapshot(prone=('pc1',))
        proof = expected_pc_dismount(state)
        with self.assertRaises(ValueError):
            replace(proof, source_injury=CharacterInjuryState())
        for changed in (replace(proof, history_index=1), replace(proof, source_id='foreign'),
                replace(proof, source_injury=CharacterInjuryState(
                    conditions=ConditionState(frozenset((Condition.PRONE, Condition.STAGGERED)))))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                updated_pc_mounts(state, changed)
        with self.assertRaises(ValueError):
            replace(proof, actor_id='pc2')
        with self.assertRaises(ValueError):
            updated_pc_mounts(snapshot(state.source), proof)

    def test_bank_replay_rejects_missing_duplicate_reordered_and_wrong_kind_proofs(self):
        state = snapshot(prone=('pc1',))
        proof = expected_pc_dismount(state)
        bank = updated_pc_mounts(state, proof)
        malformed = (
            snapshot(state.source, mounts=bank),
            snapshot(state.source, mounts=bank, history=(object(), proof)),
            snapshot(state.source, mounts=bank, history=(proof, proof)),
            snapshot(state.source, mounts=tuple(reversed(bank)), history=(proof,)),
            snapshot(state.source, mounts=bank, history=(replace(proof,
                source_injury=ProfileInjuryState(0, 1,
                    ConditionState(frozenset((Condition.PRONE,))))),)),
        )
        for value in malformed:
            with self.subTest(history=value.history), self.assertRaises((TypeError, ValueError)):
                validate_pc_mounts(value)

    def test_mount_is_a_real_search_axis_in_sampling_mutation_and_membership(self):
        space = search_space(mount=(None, CombatMount.HORSE))
        samples = tuple(space.sample(Random(seed)) for seed in range(16))
        self.assertEqual({sample.mount for sample in samples}, {None, CombatMount.HORSE})
        self.assertTrue(all(space.contains(sample) for sample in samples))
        base = component()
        self.assertIs(space.mutate(base, Random(1)).mount, CombatMount.HORSE)
        self.assertIsNone(space.mutate(replace(base, mount=CombatMount.HORSE), Random(1)).mount)
        self.assertFalse(search_space().contains(replace(base, mount=CombatMount.HORSE)))
        for invalid in ((), (None, None), ('horse',), (False,), [None]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                search_space(mount=invalid)

    def test_numeric_resampling_preserves_mount_and_complete_gear(self):
        space = search_space(mount=(None, CombatMount.HORSE), toughness=(2, 3, 4))
        base = (component(mount=CombatMount.HORSE), component())
        for seed in range(4):
            sampled = space.resample_numeric(base, Random(seed))
            self.assertEqual(tuple(npc.mount for npc in sampled.composition), (CombatMount.HORSE, None))
            self.assertEqual(tuple(npc.weapon for npc in sampled.composition),
                (GeneratedWeapon.STAFF, GeneratedWeapon.STAFF))

    def test_automatic_mount_pool_requires_battlefield_and_scenario_uses_actual_composition(self):
        source = scene(pc_mount=None, npc_mount=None)
        self.assertEqual(automatic_npc_search_space(source.party).mount, (None,))
        self.assertEqual(automatic_npc_search_space(source.party, battlefield=source.battlefield).mount,
            (None, CombatMount.HORSE, CombatMount.BRETONNIAN_WARHORSE, CombatMount.ELVEN_STEED))
        configured = request(source, search_space(mount=(None, CombatMount.HORSE)))
        foot = configured.scenario((component(),), 'foot')
        horse = configured.scenario((component(mount=CombatMount.HORSE),), 'horse')
        self.assertTrue(foot.facts.unmounted)
        self.assertFalse(horse.facts.unmounted)
        self.assertEqual(initial_pc_mounts(horse),
            (PcMountedState('generated-npc:1', CombatMount.HORSE, True),))
        self.assertTrue(configured.facts.unmounted)
        with self.assertRaises(ValueError):
            replace(configured, battlefield=None)


if __name__ == '__main__':
    unittest.main()
