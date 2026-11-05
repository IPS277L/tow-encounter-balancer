"""Natural Melee preparation and the explicit PC versus older-family admission boundaries."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.unit.test_m6_npc_melee_scenario import scenario as melee_scenario
from tests.unit.test_m7_npc_mixed_scenario import scenario as mixed_scenario
from tests.unit.test_m8_npc_magic_scenario import scenario as magic_scenario
from towr.adapters._melee_scenario_json import scenario_document as melee_document
from towr.adapters._mixed_scenario_json import scenario_document as mixed_document
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.npc_attack_preparation_models import (NpcAttackProfile,NpcAttackPreparationRequest,
    NpcAttackSelectionSnapshot)
from towr.domain.npc_magic_scenario_models import validate_npc_magic_scenario_admission
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import initial_pc_melee_state,build_pc_melee_attack
from towr.domain.pc_npc_ability_models import pc_npc_allows_give_ground
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands,RangedWeaponRange as Range
from towr.domain.test_models import InlineProfile,Skill
from towr.domain.turn_models import CombatTurnStartRequest
from towr.rules.npc_attack_preparation import prepare_npc_attack
from towr.rules.turn_resolution import start_combat_turn


class ForeignHands(str,Enum):
    ONE_HANDED = '1h'


def natural_profile():
    return NpcAttackProfile('bite','authored:bite',Skill.MELEE,InlineProfile(3,3),DamageProfile(3),
        Range.CLOSE,Range.CLOSE,None)


def preparation_request(profile):
    return NpcAttackPreparationRequest('prepare:natural','attack:natural','test:natural',
        NpcAttackSelectionSnapshot('snapshot:natural','creature',(profile,),(profile.id,)),profile.id,
        'target',Range.CLOSE,ResilienceProfile(3),True,False,False)


def natural_pc_source():
    source = make_pc_melee_scenario(max_rounds=1)
    enemy = source.enemies[0]
    definition = replace(enemy.definition,attacks=(replace(enemy.definition.attacks[0],hands=None),),
        protection=(replace(enemy.definition.protection[0],skill=Skill.ATHLETICS),))
    enemy = replace(enemy,definition=definition,state=replace(enemy.state,wields_weapon=False))
    return replace(source,enemies=(enemy,))


class NaturalAttackBoundaryTests(unittest.TestCase):
    def test_shared_natural_melee_preparation_keeps_none_and_printed_numeric_attack(self):
        request = preparation_request(natural_profile())
        result = prepare_npc_attack(request)
        self.assertIs(result.source_request,request)
        self.assertIsNone(result.selected_profile.hands)
        self.assertEqual(result.attack.attacker_test.profile,InlineProfile(3,3))
        self.assertEqual(result.attack.impact_spec.damage,DamageProfile(3))
        self.assertEqual(result.attack.impact_spec.damage_modifiers,())
        self.assertEqual(result.attack.secondary_effects,())
        self.assertIsNone(result.attack.defender_test)

    def test_shooting_requires_weapon_hands_and_aliases_never_mean_natural(self):
        profile = natural_profile()
        with self.assertRaises(ValueError):
            replace(profile,skill=Skill.SHOOTING,range_min=Range.MEDIUM,range_max=Range.LONG)
        for value in ('natural','1h',False,ForeignHands.ONE_HANDED):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(profile,hands=value)
        for hands in Hands:
            self.assertIs(replace(profile,hands=hands).hands,hands)

    def test_cached_shooting_none_and_hand_alias_are_rejected_by_actual_preparation(self):
        profile = replace(natural_profile(),skill=Skill.SHOOTING,hands=Hands.ONE_HANDED)
        request = preparation_request(profile)
        for hands in (None,'1h',ForeignHands.ONE_HANDED):
            forged = deepcopy(request)
            object.__setattr__(forged.snapshot.profiles[0],'hands',hands)
            with self.subTest(hands=hands),self.assertRaises((TypeError,ValueError)):
                prepare_npc_attack(forged)

    def test_pc_source_admits_natural_without_weapon_and_prepares_actual_unarmed_target(self):
        source = natural_pc_source()
        validate_pc_melee_scenario_admission(source)
        state = initial_pc_melee_state(source)
        clock = start_combat_turn(CombatTurnStartRequest('pure:start',state.round_state,'pc')).state
        state = replace(state,round_state=clock)
        # Pure request-preparation boundary, not an executed native encounter.
        execution,protection = build_pc_melee_attack(state)
        self.assertFalse(protection.defender_wields_weapon)
        self.assertIs(protection.selected_skill,Skill.ATHLETICS)
        self.assertEqual(execution.kernel_request.attack.defender_test.profile,InlineProfile(2,4))

    def test_pc_natural_equipment_and_protection_pairs_require_consistent_facts(self):
        source = natural_pc_source()
        enemy = source.enemies[0]
        candidates = (replace(enemy,state=replace(enemy.state,wields_weapon=True)),
            replace(enemy,state=replace(enemy.state,holds_shield=True)),
            replace(enemy,definition=replace(enemy.definition,
                protection=(replace(enemy.definition.protection[0],skill=Skill.DEFENCE),))),
            replace(enemy,definition=replace(enemy.definition,
                attacks=(replace(enemy.definition.attacks[0],hands=Hands.ONE_HANDED),))))
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                replace(source,enemies=(candidate,))

    def test_cached_pc_hand_alias_and_natural_weapon_flag_are_readmitted_strictly(self):
        for hands in ('1h',False,ForeignHands.ONE_HANDED):
            forged = deepcopy(natural_pc_source())
            object.__setattr__(forged.enemies[0].definition.attacks[0],'hands',hands)
            with self.subTest(hands=hands),self.assertRaises(TypeError):
                validate_pc_melee_scenario_admission(forged)
        for value in (True,0):
            forged = deepcopy(natural_pc_source())
            object.__setattr__(forged.enemies[0].state,'wields_weapon',value)
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                validate_pc_melee_scenario_admission(forged)

    def test_older_melee_and_mixed_families_keep_weapon_only_hands_including_cached_sources(self):
        for build in (melee_scenario,mixed_scenario):
            for hands in (None,'1h',ForeignHands.ONE_HANDED):
                scene = build()
                actor = next(p for p in scene.initial.current.state.roster.participants
                    if p.definition.attacks[0].skill is Skill.MELEE)
                object.__setattr__(actor.definition.attacks[0],'hands',hands)
                with self.subTest(family=type(scene).__name__,hands=hands),self.assertRaises(TypeError):
                    replace(scene)

    def test_older_magic_family_rejects_cached_none_and_hand_alias_before_wire_observation(self):
        for hands in (None,'2h',ForeignHands.ONE_HANDED):
            scene = magic_scenario()
            actor = next(p for p in scene.initial.roster.participants if p.definition.attacks)
            object.__setattr__(actor.definition.attacks[0],'hands',hands)
            with self.subTest(hands=hands),self.assertRaises(TypeError):
                validate_npc_magic_scenario_admission(scene)

    def test_older_melee_and_mixed_codecs_reject_cached_none_before_hands_value_encoding(self):
        for build,encode in ((melee_scenario,melee_document),(mixed_scenario,mixed_document)):
            for hands in (None,'1h',ForeignHands.ONE_HANDED):
                scene = build()
                roster = scene.initial.current.state.roster
                order = tuple(dict.fromkeys(p.definition.id for p in roster.participants))
                actor = next(p for p in roster.participants if p.definition.attacks[0].skill is Skill.MELEE)
                object.__setattr__(actor.definition.attacks[0],'hands',hands)
                with self.subTest(family=type(scene).__name__,hands=hands),self.assertRaises(TypeError):
                    encode(scene,order)

    def test_only_canonical_giant_wolf_disallows_give_ground(self):
        for profile in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GIANT_WOLF,PcBookNpcProfile.GIANT_BOAR):
            definition = get_pc_book_npc_entry(profile).definition
            with self.subTest(profile=profile):
                self.assertIs(pc_npc_allows_give_ground(definition),profile is not PcBookNpcProfile.GIANT_WOLF)
        self.assertTrue(pc_npc_allows_give_ground(make_pc_melee_scenario().enemies[0].definition))
        wolf = get_pc_book_npc_entry(PcBookNpcProfile.GIANT_WOLF).definition
        with self.assertRaises(ValueError):
            pc_npc_allows_give_ground(replace(wolf,source_rule_id='authored:fake-wolf'))


if __name__ == '__main__':
    unittest.main()
