"""Prepared typed companion banks; no native detach/remount journal claimed."""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, replace
from pickle import dumps, loads
from types import SimpleNamespace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_actor_models import (
    pc_active_actor_ids, pc_actor_injury, pc_actor_inventory, pc_actor_npc_snapshot,
    pc_actor_npc_update, pc_actor_side, pc_companion, pc_companion_turn_eligible,
    pc_opponent_ids,
)
from towr.domain.pc_companion_models import PcMountCompanionState, mount_companion_actor_id
from towr.domain.pc_melee_result_models import PcMeleeState, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount, PcMountedState
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


def companion(rider, side, *, retained=1, brute=False, conditions=ConditionState()):
    """An authored ordinary NPC source, not a purported book Horse profile."""
    attack = NpcAttackProfile('prepared:natural', 'prepared:natural', Skill.MELEE,
        InlineProfile(3, 3), DamageProfile(3), RangedWeaponRange.CLOSE,
        RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED)
    policy, limit = (TargetInjuryPolicy.BRUTE, 3) if brute else (TargetInjuryPolicy.MINION, 1)
    definition = NpcDefinition('prepared:companion', 'prepared:companion', policy, limit,
        ResilienceProfile(3), (attack,),
        (NpcProtectionProfile('prepared:athletics', Skill.ATHLETICS, InlineProfile(3, 4)),))
    state = NpcParticipantState(mount_companion_actor_id(rider), definition.id, side,
        ProfileInjuryState(0, limit, conditions), (attack.id,), definition.resilience, False, False)
    return PcMountCompanionState(rider, NpcParticipantSnapshot(definition, state), retained)


class PreparedActors(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy


def prepared(*, round_number=1, retained=1, mounted=False, brute=False):
    """Complete original source/state plus explicit detached NPC observations."""
    actual = initial_pc_melee_state(automatic_source(pc_count=2, enemy_count=2, rounds=4))
    rows = (companion('pc1', CombatSide.PLAYERS_AND_ALLIES, retained=retained, brute=brute),
        companion('minion1', CombatSide.OPPOSITION, retained=retained, brute=brute))
    values = {name: getattr(actual, name) for name in actual.__dataclass_fields__}
    values.update(companions=rows, mounts=(PcMountedState('pc1', CombatMount.HORSE, mounted),
        PcMountedState('minion1', CombatMount.HORSE, mounted)), exited_npc_ids=(),
        round_state=CombatRoundState(round_number, actual.round_state.participants))
    return PreparedActors(**values)


class PcCompanionActorQueryTests(unittest.TestCase):
    def test_typed_profile_source_is_immutable_and_survives_pickle(self):
        for brute in (False, True):
            with self.subTest(brute=brute):
                row = companion('rider', CombatSide.PLAYERS_AND_ALLIES, brute=brute)
                self.assertEqual(loads(dumps(row)), row)
                self.assertEqual(mount_companion_actor_id('rider'), 'rider:mount')
                self.assertIs(type(row.snapshot.state.injury), ProfileInjuryState)
                self.assertFalse(hasattr(row, 'fate'))
                self.assertFalse(hasattr(row.snapshot.state, 'fate'))
                with self.assertRaises(FrozenInstanceError):
                    row.retained_since_round = 2
                with self.assertRaises(ValueError):
                    replace(row, snapshot=replace(row.snapshot,
                        state=replace(row.snapshot.state, actor_id='different:mount')))

    def test_raw_identifiers_rounds_types_and_cached_nested_sources_reject(self):
        row = companion('pc1', CombatSide.PLAYERS_AND_ALLIES)
        for invalid in (None, True, 1, ''):
            with self.subTest(identifier=invalid), self.assertRaises(TypeError):
                mount_companion_actor_id(invalid)
        for invalid in (True, '1', 0, -1):
            with self.subTest(round=invalid), self.assertRaises((TypeError, ValueError)):
                replace(row, retained_since_round=invalid)
        for changes in (dict(snapshot=True), dict(rider_id=True)):
            with self.subTest(changes=changes), self.assertRaises(TypeError):
                replace(row, **changes)
        for field, value in (('side', 'players_and_allies'), ('injury', CharacterInjuryState()),
                ('available_attack_ids', ['prepared:natural'])):
            forged = deepcopy(row)
            object.__setattr__(forged.snapshot.state, field, value)
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                replace(forged)
        forged = deepcopy(row)
        object.__setattr__(forged.snapshot.definition.attacks[0].test_profile, 'dice', True)
        with self.assertRaises((TypeError, ValueError)):
            replace(forged)

    def test_champion_and_pc_injury_cannot_be_disguised_as_companion(self):
        row = companion('pc1', CombatSide.PLAYERS_AND_ALLIES)
        champion = NpcDefinition('champion', 'prepared:champion', TargetInjuryPolicy.CHAMPION,
            None, row.snapshot.definition.resilience, row.snapshot.definition.attacks,
            row.snapshot.definition.protection)
        state = replace(row.snapshot.state, definition_id=champion.id, injury=CharacterInjuryState())
        with self.assertRaises(ValueError):
            replace(row, snapshot=NpcParticipantSnapshot(champion, state))

    def test_allied_npc_keeps_its_side_profile_and_inventory_without_becoming_pc(self):
        state = prepared()
        ally = state.companions[0]
        self.assertIs(pc_companion(state, 'pc1:mount'), ally)
        self.assertIs(pc_actor_npc_snapshot(state, 'pc1:mount'), ally.snapshot)
        self.assertIs(pc_actor_injury(state, 'pc1:mount'), ally.snapshot.state.injury)
        self.assertIs(pc_actor_side(state, 'pc1:mount'), CombatSide.PLAYERS_AND_ALLIES)
        self.assertIs(pc_actor_side(state, 'minion1:mount'), CombatSide.OPPOSITION)
        self.assertIsNone(pc_actor_inventory(state, 'pc1:mount'))
        self.assertIs(pc_actor_inventory(state, 'pc1'), state.participant('pc1').weapon_inventory)
        self.assertIs(pc_actor_npc_snapshot(state, 'minion1'), state.enemy('minion1'))
        self.assertIsNone(pc_companion(state, 'pc1'))
        with self.assertRaises(ValueError):
            pc_actor_npc_snapshot(state, 'pc1')
        for query in (pc_actor_side, pc_actor_injury, pc_actor_inventory, pc_actor_npc_snapshot, pc_opponent_ids):
            with self.subTest(query=query.__name__), self.assertRaises(ValueError):
                query(state, 'foreign')

    def test_active_ids_preserve_sides_and_rider_order_without_granting_early_turn(self):
        state = prepared()
        self.assertEqual(pc_active_actor_ids(state),
            ('pc1', 'pc1:mount', 'pc2', 'minion1', 'minion1:mount', 'minion2'))
        self.assertEqual(pc_active_actor_ids(state, CombatSide.PLAYERS_AND_ALLIES),
            ('pc1', 'pc1:mount', 'pc2'))
        self.assertEqual(pc_opponent_ids(state, 'pc1:mount'),
            ('minion1', 'minion1:mount', 'minion2'))
        self.assertEqual(pc_opponent_ids(state, 'minion1:mount'), ('pc1', 'pc1:mount', 'pc2'))
        self.assertFalse(pc_companion_turn_eligible(state, 'pc1:mount'))
        self.assertFalse(pc_companion_turn_eligible(prepared(round_number=1, retained=2), 'pc1:mount'))
        later = prepared(round_number=2)
        self.assertTrue(pc_companion_turn_eligible(later, 'pc1:mount'))
        self.assertTrue(pc_companion_turn_eligible(later, 'minion1:mount'))
        self.assertFalse(pc_companion_turn_eligible(later, 'pc1'))
        self.assertNotIn('pc1:mount', tuple(row.entity_id for row in state.round_state.participants))
        with self.assertRaises(TypeError):
            pc_active_actor_ids(state, 'players_and_allies')

    def test_mounted_departed_and_defeated_states_are_inactive_but_defenceless_is_not_dead(self):
        originals = ('pc1', 'pc2', 'minion1', 'minion2')
        for state in (prepared(mounted=True), prepared(retained=None)):
            self.assertEqual(pc_active_actor_ids(state), originals)
            self.assertFalse(pc_companion_turn_eligible(state, 'pc1:mount'))
        state = prepared(round_number=2)
        row = state.companions[0]
        defeated = replace(row.snapshot.state.injury, wounds=1, defeated=True)
        updates = pc_actor_npc_update(state, 'pc1:mount', injury=defeated)
        state.companions = updates['companions']
        self.assertNotIn('pc1:mount', pc_active_actor_ids(state))
        self.assertFalse(pc_companion_turn_eligible(state, 'pc1:mount'))
        row = state.companions[1]
        state.companions = (state.companions[0], replace(row, snapshot=replace(row.snapshot,
            state=replace(row.snapshot.state, injury=replace(row.snapshot.state.injury,
                conditions=ConditionState(frozenset({Condition.DEFENCELESS})))))))
        self.assertIn('minion1:mount', pc_active_actor_ids(state))

    def test_dead_or_exited_rider_does_not_erase_an_independently_living_mount(self):
        state = prepared(round_number=2)
        state.party = tuple(replace(member, injury=replace(member.injury, dead=True))
            if member.actor_id == 'pc1' else member for member in state.party)
        state.exited_npc_ids = ('minion1',)
        self.assertEqual(pc_active_actor_ids(state), ('pc1:mount', 'pc2', 'minion1:mount', 'minion2'))
        self.assertTrue(pc_companion_turn_eligible(state, 'pc1:mount'))
        self.assertTrue(pc_companion_turn_eligible(state, 'minion1:mount'))

    def test_typed_update_routes_one_bank_and_preserves_detach_clock_without_mutation(self):
        state = prepared(brute=True)
        before = deepcopy(state)
        for actor, key in (('pc1:mount', 'companions'), ('minion1:mount', 'companions'),
                ('minion1', 'enemies')):
            with self.subTest(actor=actor):
                old = pc_actor_npc_snapshot(state, actor)
                injury = replace(old.state.injury,
                    conditions=old.state.injury.conditions.with_condition(Condition.STAGGERED))
                update = pc_actor_npc_update(state, actor, injury=injury)
                self.assertEqual(tuple(update), (key,))
                if key == 'companions':
                    changed = next(row for row in update[key] if row.snapshot.state.actor_id == actor)
                    self.assertEqual(changed.retained_since_round, 1)
                    self.assertEqual(changed.snapshot.state.injury, injury)
                    self.assertEqual(changed.snapshot.definition, old.definition)
                else:
                    self.assertEqual(update[key][0].state.injury, injury)
                self.assertEqual(state, before)
        snapshot = state.companions[0].snapshot
        update = pc_actor_npc_update(state, 'pc1:mount', snapshot=replace(snapshot,
            state=replace(snapshot.state, current_resilience=replace(snapshot.state.current_resilience, bonus=1))))
        self.assertEqual(update['companions'][0].snapshot.state.current_resilience.bonus, 1)
        self.assertEqual(state, before)

    def test_update_rejects_foreign_identity_static_definition_side_and_incompatible_injury(self):
        state = prepared()
        snapshot = state.companions[0].snapshot
        bad = (replace(snapshot, state=replace(snapshot.state, actor_id='minion1:mount')),
            replace(snapshot, state=replace(snapshot.state, side=CombatSide.OPPOSITION)),
            replace(snapshot, definition=replace(snapshot.definition, source_rule_id='foreign:source')))
        for forged in bad:
            with self.subTest(forged=forged), self.assertRaises(ValueError):
                pc_actor_npc_update(state, 'pc1:mount', snapshot=forged)
        for kwargs in ({}, dict(injury=True), dict(snapshot=True),
                dict(injury=snapshot.state.injury, snapshot=snapshot),
                dict(injury=CharacterInjuryState())):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                pc_actor_npc_update(state, 'pc1:mount', **kwargs)
        with self.assertRaises(ValueError):
            pc_actor_npc_update(state, 'pc1', injury=snapshot.state.injury)
        with self.assertRaises(ValueError):
            pc_actor_npc_update(state, 'foreign', injury=snapshot.state.injury)

    def test_banks_cannot_alias_duplicate_or_forge_the_mounted_witness(self):
        state = prepared()
        for bank in (list(state.companions), (True,), (state.companions[0], state.companions[0])):
            changed = copy(state)
            changed.companions = bank
            with self.subTest(bank=bank), self.assertRaises((TypeError, ValueError)):
                pc_active_actor_ids(changed)
        changed = copy(state)
        changed.mounts = ()
        with self.assertRaises(ValueError):
            pc_active_actor_ids(changed)
        changed = deepcopy(state)
        object.__setattr__(changed.mounts[0], 'mounted', 0)
        with self.assertRaises(TypeError):
            pc_companion_turn_eligible(changed, 'pc1:mount')
        changed = deepcopy(state)
        object.__setattr__(changed.companions[0].snapshot.state, 'side', True)
        with self.assertRaises(TypeError):
            pc_actor_side(changed, 'pc1:mount')


if __name__ == '__main__':
    unittest.main()
