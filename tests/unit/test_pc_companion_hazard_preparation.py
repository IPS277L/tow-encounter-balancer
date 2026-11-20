"""Own mount Tests in complete-source prepared views, without RNG or turns."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.talent_sources import free_talent
from towr.domain.armour_models import (
    ArmourLoadout, BodyArmour, BARDING_AGILITY_RULE_ID, ITHILMAR_ENVIRONMENT_RULE_ID,
    body_resilience_bonus,
)
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_companion_effect_models import companion_profile, companion_test_request
from towr.domain.pc_companion_models import PcMountCompanionState, mount_companion_actor_id
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_falling_models import _injury, prepare_hazard_avoidance
from towr.domain.pc_magic_models import PcMagicModifier
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_melee_result_models import PcMeleeState, initial_pc_melee_state
from towr.domain.pc_mount_companion_sources import initial_mount_companion_snapshot
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import HazardExposureRequest
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import InlineProfile, Skill, TestQuality
from towr.domain.turn_models import CombatSide


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy


def view(kind=CombatMount.HORSE, *, barding=False):
    original = automatic_source(pc_count=1, enemy_count=1)
    armour = ArmourLoadout((BodyArmour.ITHILMAR,), BodyArmour.ITHILMAR, barding=barding)
    rider_kind = RiderKind.HUMAN if kind in (CombatMount.PEGASUS, CombatMount.DEMIGRYPH) else None
    member = replace(original.party[0], mount=kind, rider_kind=rider_kind,
        armour=armour, armour_worn=True,
        pc=replace(original.party[0].pc, armour_bonus=body_resilience_bonus(armour)),
        talents=(free_talent(TalentId.ACROBATIC),))
    npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), armour,
        defence=4, mount=kind, rider_kind=rider_kind)
    source = replace(original, party=(member,), enemies=(npc.participant('minion1'),),
        facts=replace(original.facts, all_opponents_close=False, can_leave_zone=True, unmounted=False),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG))
    actual = initial_pc_melee_state(source)
    return Preparation(**{name: getattr(actual, name) for name in actual.__dataclass_fields__})


def exposure(actor, skill=Skill.ATHLETICS):
    return HazardExposureRequest('prepared:hazard:'+actor, 'prepared:test:'+actor, 2, skill,
        'prepared:actual-hazard', True, ())


def replace_body(state, actor, **changes):
    rows = []
    for row in state.companions:
        if row.snapshot.state.actor_id == actor:
            body = replace(row.snapshot.state.injury, **changes)
            row = replace(row, snapshot=replace(row.snapshot, state=replace(row.snapshot.state, injury=body)))
        rows.append(row)
    state.companions = tuple(rows)


class PcCompanionHazardPreparationTests(unittest.TestCase):
    def test_all_six_mounts_both_sides_use_own_printed_natural_endurance_and_athletics(self):
        # Literal book profiles: GM135 Horse family; GM175 Demigryph; GM176 Pegasus.
        cases = ((CombatMount.HORSE, (3, 3, 6), (4, 4, 8)),
            (CombatMount.BRETONNIAN_WARHORSE, (3, 3, 6), (4, 4, 8)),
            (CombatMount.ELVEN_STEED, (3, 3, 6), (4, 4, 8)),
            (CombatMount.SKELETAL_STEED, (3, 3, 6), (4, 4, 8)),
            (CombatMount.DEMIGRYPH, (4, 3, 8), (4, 3, 8)),
            (CombatMount.PEGASUS, (3, 3, 6), (4, 4, 8)))
        for kind, endurance, athletics in cases:
            state = view(kind)
            for actor in ('pc1:mount', 'minion1:mount'):
                for skill, expected in ((Skill.ENDURANCE, endurance), (Skill.ATHLETICS, athletics)):
                    with self.subTest(kind=kind, actor=actor, skill=skill):
                        source = exposure(actor, skill)
                        request = prepare_hazard_avoidance(state, actor, source, environmental=True)
                        self.assertEqual(request.id, source.test_id)
                        self.assertEqual(request.profile, InlineProfile(*expected))
                        self.assertEqual(request.dice_modifiers, ())
                        self.assertEqual(request.quality_modifiers, ())
                        self.assertFalse(hasattr(request, 'fate'))
                        self.assertIs(_injury(state, actor), pc_actor_injury(state, actor))

    def test_own_barding_penalty_is_not_a_rider_exception(self):
        for kind in CombatMount:
            state = view(kind, barding=True)
            for actor in ('pc1:mount', 'minion1:mount'):
                with self.subTest(kind=kind, actor=actor):
                    profile = companion_profile(state, actor)
                    self.assertTrue(profile.barding)
                    athletics = prepare_hazard_avoidance(state, actor, exposure(actor), environmental=True)
                    self.assertEqual(tuple((row.rule_id, row.amount) for row in athletics.dice_modifiers),
                        ((BARDING_AGILITY_RULE_ID, -1),))
                    endurance = prepare_hazard_avoidance(state, actor, exposure(actor, Skill.ENDURANCE), environmental=True)
                    self.assertEqual(endurance.dice_modifiers, ())
                    self.assertNotIn(ITHILMAR_ENVIRONMENT_RULE_ID, tuple(row.rule_id for row in athletics.dice_modifiers))

    def test_barding_is_from_original_equipment_and_not_mutable_resilience(self):
        state = view(barding=True)
        row = state.companions[0]
        changed = replace(row.snapshot, state=replace(row.snapshot.state,
            current_resilience=ResilienceProfile(3, 0, armoured=False)))
        state.companions = (replace(row, snapshot=changed), state.companions[1])
        request = companion_test_request(state, 'pc1:mount', 'actual:test', Skill.ATHLETICS)
        self.assertEqual(tuple((row.rule_id, row.amount) for row in request.dice_modifiers),
            ((BARDING_AGILITY_RULE_ID, -1),))
        self.assertTrue(companion_profile(state, 'pc1:mount').barding)

    def test_rider_mantle_talent_conditions_and_magic_do_not_become_creature_benefits(self):
        state = view()
        rider = state.participant('pc1')
        state.party = (replace(rider, injury=replace(rider.injury,
            conditions=rider.injury.conditions.with_condition(Condition.BLINDED))),)
        state.magic_modifiers = (PcMagicModifier('rider:penalty', 'pc1', PcMagicTaskKind.NEXT_TEST_PENALTY),)
        request = prepare_hazard_avoidance(state, 'pc1:mount', exposure('pc1:mount'), environmental=True)
        self.assertEqual(request.profile, InlineProfile(4, 4, 8))
        self.assertEqual(request.dice_modifiers, ())
        self.assertEqual(request.quality_modifiers, ())
        self.assertEqual(exposure('pc1:mount').rating, 2)  # Rider Acrobatic did not halve it.
        self.assertEqual(state.source.party[0].talents[0].id, TalentId.ACROBATIC)

    def test_actual_targeted_magic_and_own_blinded_conditions_are_prepared_once(self):
        for actor in ('pc1:mount', 'minion1:mount'):
            state = view(barding=True)
            state.magic_modifiers = (PcMagicModifier('own:next-test', actor, PcMagicTaskKind.NEXT_TEST_PENALTY),
                PcMagicModifier('other:next-test', 'pc1' if actor == 'pc1:mount' else 'minion1',
                    PcMagicTaskKind.NEXT_TEST_PENALTY))
            body = _injury(state, actor)
            replace_body(state, actor, conditions=body.conditions.with_condition(Condition.BLINDED)
                .with_condition(Condition.DRAINED))
            actual = prepare_hazard_avoidance(state, actor, exposure(actor), environmental=True)
            self.assertEqual(tuple((row.rule_id, row.amount) for row in actual.dice_modifiers),
                ((BARDING_AGILITY_RULE_ID, -1), ('own:next-test', -1)))
            self.assertEqual(tuple((row.rule_id, row.quality) for row in actual.quality_modifiers),
                (('RULE-HEALTH-008:blinded', TestQuality.GRIM),))
            endurance = prepare_hazard_avoidance(state, actor, exposure(actor, Skill.ENDURANCE), environmental=True)
            self.assertEqual(tuple(row.rule_id for row in endurance.dice_modifiers), ('own:next-test',))
            self.assertEqual(endurance.quality_modifiers, ())

    def test_general_own_skill_query_uses_brawn_and_does_not_manufacture_bs_zero_shooting(self):
        state = view()
        for actor in ('pc1:mount', 'minion1:mount'):
            brawn = companion_test_request(state, actor, 'own:brawn', Skill.BRAWN)
            self.assertEqual(brawn.profile, InlineProfile(3, 4, 6))
            with self.assertRaises(ValueError):
                companion_test_request(state, actor, 'own:shooting', Skill.SHOOTING)
        for invalid in ('athletics', True):
            with self.subTest(skill=invalid), self.assertRaises(TypeError):
                companion_test_request(state, 'pc1:mount', 'actual:test', invalid)

    def test_canonical_source_definition_side_and_mount_kind_cannot_be_substituted(self):
        for wrong_side in (False, True):
            state = view()
            row = state.companions[0]
            snapshot = initial_mount_companion_snapshot(row.snapshot.state.actor_id,
                CombatSide.OPPOSITION if wrong_side else CombatSide.PLAYERS_AND_ALLIES,
                CombatMount.HORSE if wrong_side else CombatMount.DEMIGRYPH)
            state.companions = (PcMountCompanionState(row.rider_id, snapshot), state.companions[1])
            with self.subTest(wrong_side=wrong_side), self.assertRaises(ValueError):
                companion_profile(state, 'pc1:mount')
        state = view()
        state.mounts = tuple(replace(row, mount=CombatMount.DEMIGRYPH)
            if row.actor_id == 'pc1' else row for row in state.mounts)
        with self.assertRaises(ValueError):
            companion_profile(state, 'pc1:mount')
        with self.assertRaises(ValueError):
            companion_profile(view(), 'pc1')
        with self.assertRaises(ValueError):
            prepare_hazard_avoidance(view(), 'foreign', exposure('foreign'))

    def test_cached_modifiers_source_and_exact_preparation_inputs_reject(self):
        for bank in ([True], (True,)):
            state = view()
            state.magic_modifiers = bank
            with self.subTest(bank=bank), self.assertRaises(TypeError):
                companion_test_request(state, 'pc1:mount', 'actual:test', Skill.ATHLETICS)
        state = view()
        modifier = PcMagicModifier('actual:source', 'pc1:mount', PcMagicTaskKind.NEXT_TEST_PENALTY)
        state.magic_modifiers = (modifier,)
        object.__setattr__(modifier, 'kind', 'next_test_penalty')
        with self.assertRaises(ValueError):
            companion_test_request(state, 'pc1:mount', 'actual:test', Skill.ATHLETICS)
        state = deepcopy(view())
        object.__setattr__(state.companions[0].snapshot.definition.attacks[0].test_profile, 'dice', True)
        with self.assertRaises(TypeError):
            companion_profile(state, 'pc1:mount')
        with self.assertRaises(TypeError):
            prepare_hazard_avoidance(view(), 'pc1:mount', True)
        with self.assertRaises(TypeError):
            prepare_hazard_avoidance(view(), 'pc1:mount', exposure('pc1:mount'), environmental=1)

    def test_original_pc_and_npc_hazard_preparation_keep_their_actual_mantle_effect(self):
        state = view()
        for actor in ('pc1', 'minion1'):
            source = exposure(actor)
            ordinary = prepare_hazard_avoidance(state, actor, source)
            environmental = prepare_hazard_avoidance(state, actor, source, environmental=True)
            self.assertEqual(sum(row.amount for row in environmental.dice_modifiers)
                - sum(row.amount for row in ordinary.dice_modifiers), 1)
            self.assertIs(_injury(state, actor),
                state.participant(actor).injury if actor == 'pc1' else state.enemy(actor).state.injury)


if __name__ == '__main__':
    unittest.main()
