"""Literal PG95 generated Shooting sources, free bows and real Reload costs."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.application.dynamic_encounter import DynamicEncounterRequest, NpcSearchSpace, automatic_npc_search_space
from towr.domain.generated_npc_models import (
    GeneratedNpc, GeneratedWeapon, GeneratedRangedFacts,
    GENERATED_TWO_HANDED_RANGED_WEAPONS, GENERATED_CLOSE_WEAPONS,
    generated_weapon_allows_shield, validate_generated_definition,
)
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_generated_ranged_advice import _repeater_choice, pc_shooting_protection
from towr.domain.pc_melee_models import (
    PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy, PcWeaponHand,
)
from towr.domain.pc_npc_ranged_models import (
    PcNpcRangedState, initial_pc_npc_ranged_weapons, npc_ranged_is_loaded,
    npc_ranged_reload_test,
)
from towr.domain.pc_npc_ranged_source_models import (
    pc_npc_ranged_policy_for_generated, pc_npc_ranged_profile,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponId, RangedWeaponRange
from towr.domain.reload_models import FreeReloadWeaponState, ReloadableWeaponState, begin_reload_cycle
from towr.domain.test_models import InlineProfile, Skill


R = RangedWeaponRange
WEAPONS = (
    # weapon, Damage, optimum minimum, maximum, ignores Armour, Exacting target
    (GeneratedWeapon.SHORTBOW, 3, R.SHORT, R.MEDIUM, False, None),
    (GeneratedWeapon.WARBOW, 3, R.MEDIUM, R.LONG, False, None),
    (GeneratedWeapon.LONGBOW, 4, R.MEDIUM, R.LONG, False, None),
    (GeneratedWeapon.CROSSBOW, 4, R.SHORT, R.LONG, False, 2),
    (GeneratedWeapon.HANDGUN, 5, R.MEDIUM, R.LONG, True, 3),
    (GeneratedWeapon.BLUNDERBUSS, 4, R.SHORT, R.SHORT, False, 3),
    (GeneratedWeapon.HOCHLAND_LONG_RIFLE, 6, R.MEDIUM, R.EXTREME, True, 4),
    (GeneratedWeapon.REPEATER_CROSSBOW, 4, R.SHORT, R.MEDIUM, False, 3),
    (GeneratedWeapon.REPEATER_HANDGUN, 5, R.SHORT, R.LONG, True, 5),
)
FIREARMS = frozenset((GeneratedWeapon.HANDGUN,GeneratedWeapon.BLUNDERBUSS,
    GeneratedWeapon.HOCHLAND_LONG_RIFLE,GeneratedWeapon.REPEATER_HANDGUN,
    GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_PISTOL))


def component(weapon=GeneratedWeapon.SHORTBOW, **changes):
    firearm = weapon in FIREARMS
    facts = GeneratedRangedFacts(4,5,2,4,True,True,
        True if firearm else None, True if firearm else None,
        awareness=4 if weapon in GENERATED_TWO_HANDED_RANGED_WEAPONS else None)
    values = dict(weapon_skill=3,strength=3,toughness=4,agility=2,melee=4,
        athletics=3,defence=4,weapon=weapon,light_armour=False,shield=False,ranged=facts)
    values.update(changes)
    return GeneratedNpc(**values)


def space(**changes):
    values = dict(weapon_skill=(3,),strength=(3,),toughness=(4,),agility=(2,),
        melee=(4,),athletics=(3,),defence=(4,),light_armour=(False,),shield=(False,),
        weapon=GENERATED_TWO_HANDED_RANGED_WEAPONS,allowed_talents=(),
        ballistic_skill=(4,),shooting=(5,),initiative=(2,),dexterity=(4,),awareness=(4,))
    values.update(changes)
    return NpcSearchSpace(**values)


def battle_source(weapons=(GeneratedWeapon.SHORTBOW,), *, initial=R.SHORT, maximum=R.LONG):
    source = automatic_source(pc_count=1,enemy_count=len(weapons),rounds=3)
    npcs = tuple(component(weapon) for weapon in weapons)
    return replace(source,
        enemies=tuple(npc.participant(actor) for npc,actor in zip(npcs,source.enemy_activation_order)),
        npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
            for npc,actor in zip(npcs,source.enemy_activation_order)),
        facts=replace(source.facts,all_opponents_close=initial is R.CLOSE,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(initial,maximum))


def request(**changes):
    source = automatic_source(pc_count=1,rounds=3)
    values = dict(party=source.party,facts=source.facts,day_id=source.day_id,space=space(),
        minimum_npcs=1,maximum_npcs=1,target_win_rate=.5,target_rounds=2.,master_seed=42,
        max_candidates=1,exploration_trials=1,finalist_trials=1,top_k=1,max_total_trials=2,
        max_rounds=3,defeat_disposition=NpcDefeatDisposition.KILLED)
    values.update(changes)
    return DynamicEncounterRequest(**values)


class FirstChoice:
    def __init__(self):
        self.draws = []

    def choice(self, values):
        self.draws.append(tuple(values))
        return values[0]


class GeneratedTwoHandedShootingSourceTests(unittest.TestCase):
    def test_complete_inventory_has_nine_literal_profiles_without_catalogue_identity(self):
        self.assertEqual(GENERATED_TWO_HANDED_RANGED_WEAPONS,tuple(row[0] for row in WEAPONS))
        for weapon,damage,minimum,maximum,ignores,_ in WEAPONS:
            with self.subTest(weapon=weapon):
                npc = component(weapon)
                definition = npc.participant('arbitrary-actor').definition
                attack, = definition.attacks
                self.assertIs(attack.skill,Skill.SHOOTING)
                self.assertIs(attack.hands,RangedWeaponHands.TWO_HANDED)
                self.assertEqual((attack.range_min,attack.range_max),(minimum,maximum))
                self.assertEqual(attack.damage.base,damage)
                self.assertIs(attack.ignores_armour,ignores)
                self.assertEqual(attack.test_profile,InlineProfile(4,5))
                self.assertEqual(attack.test_profile.maximum_dice,8)
                self.assertFalse(generated_weapon_allows_shield(weapon))
                self.assertEqual(definition.attacks,component(weapon).participant('another').definition.attacks)
                validate_generated_definition(definition)
                derived = pc_npc_ranged_profile(definition)
                self.assertIs(derived.weapon_id,RangedWeaponId(weapon.value))
                self.assertEqual(derived.dexterity_profile,InlineProfile(2,4))
                self.assertEqual(derived.awareness_profile,InlineProfile(2,4))

    def test_every_two_handed_shooter_requires_actual_awareness_and_no_shield(self):
        for weapon, *_ in WEAPONS:
            npc = component(weapon)
            with self.subTest(weapon=weapon):
                with self.assertRaises(ValueError):
                    replace(npc,ranged=replace(npc.ranged,awareness=None))
                with self.assertRaises(ValueError):
                    replace(npc,shield=True)
        for value in (True,1,7,4.,'4'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                replace(component().ranged,awareness=value)
        self.assertIsNone(component(GeneratedWeapon.PISTOL).ranged.awareness)

    def test_blackpowder_facts_follow_the_actual_weapon_including_crossbows(self):
        for weapon, *_ in WEAPONS:
            npc = component(weapon)
            expected = True if weapon in FIREARMS else None
            self.assertIs(npc.ranged.has_blackpowder_lore,expected)
            self.assertIs(npc.ranged.has_blackpowder_kit,expected)
            for field in ('has_blackpowder_lore','has_blackpowder_kit'):
                bad = None if expected else True
                with self.subTest(weapon=weapon,field=field),self.assertRaises(ValueError):
                    replace(npc,ranged=replace(npc.ranged,**{field:bad}))

    def test_complete_source_readmission_rejects_changed_hands_damage_range_and_awareness(self):
        for field in ('hands','damage','range','awareness'):
            definition = deepcopy(component().participant('source').definition)
            attack, = definition.attacks
            if field == 'hands':
                object.__setattr__(attack,'hands',RangedWeaponHands.ONE_HANDED)
            elif field == 'damage':
                object.__setattr__(attack.damage,'base',5)
            elif field == 'range':
                object.__setattr__(attack,'range_min',R.CLOSE)
            else:
                object.__setattr__(definition.generated_components.ranged,'awareness',None)
            with self.subTest(field=field),self.assertRaises((ValueError,TypeError)):
                validate_generated_definition(definition)


class GeneratedTwoHandedShootingSpaceTests(unittest.TestCase):
    def test_stationary_python_default_excludes_two_handed_shooting_until_scene_is_explicit(self):
        source = automatic_source(pc_count=1)
        self.assertEqual(NpcSearchSpace().weapon,GENERATED_CLOSE_WEAPONS)
        self.assertEqual(automatic_npc_search_space(source.party).weapon,GENERATED_CLOSE_WEAPONS)
        full = automatic_npc_search_space(source.party,battlefield=PcBattlefieldSpec(R.SHORT,R.LONG))
        self.assertEqual(full.weapon,tuple(GeneratedWeapon))
        self.assertEqual(full.awareness,(3,4,5))

    def test_two_handed_request_requires_scene_before_sampling_and_passes_it_to_native_source(self):
        with patch.object(NpcSearchSpace,'sample',side_effect=AssertionError('no RNG before admission')):
            with self.assertRaises(ValueError):
                request()
        original = automatic_source(pc_count=1,rounds=3)
        facts = replace(original.facts,all_opponents_close=False,can_leave_zone=True)
        spec = PcBattlefieldSpec(R.SHORT,R.EXTREME)
        admitted = request(facts=facts,battlefield=spec)
        scenario = admitted.scenario((component(),),'native-arena')
        self.assertEqual(scenario.battlefield,spec)
        self.assertEqual(scenario.facts,facts)

    def test_one_handed_sources_ignore_unused_awareness_axis_without_rng_draws(self):
        first = space(weapon=(GeneratedWeapon.PISTOL,),awareness=(2,))
        second = replace(first,awareness=(6,))
        a_rng,b_rng = FirstChoice(),FirstChoice()
        a,b = first.sample(a_rng),second.sample(b_rng)
        self.assertEqual(a,b)
        self.assertEqual(a_rng.draws,b_rng.draws)
        self.assertIsNone(a.ranged.awareness)

    def test_sampling_contains_mutation_and_numeric_resampling_preserve_full_source(self):
        envelope = space(weapon=(GeneratedWeapon.PISTOL,*GENERATED_TWO_HANDED_RANGED_WEAPONS),
            awareness=(2,4,6),initiative=(2,4),shooting=(3,5))
        for weapon in envelope.weapon:
            original = component(weapon)
            self.assertTrue(envelope.contains(original))
            mutated = envelope.mutate(original,Random(29))
            self.assertTrue(envelope.contains(mutated))
            sampled, = envelope.resample_numeric((original,),Random(18),bias=.5).composition
            self.assertTrue(envelope.contains(sampled))
            self.assertEqual((sampled.weapon,sampled.weapon_grip,sampled.shield,sampled.light_armour),
                (original.weapon,None,False,False))
            self.assertEqual(original,component(weapon))
        fixed = space()
        self.assertFalse(fixed.contains(component(ranged=replace(component().ranged,awareness=5))))
        for seed in range(20):
            proposal = envelope.sample(Random(seed))
            self.assertTrue(envelope.contains(proposal))
            self.assertFalse(proposal.shield)


class GeneratedTwoHandedShootingStateTests(unittest.TestCase):
    def test_bows_keep_free_state_and_exacting_weapons_keep_literal_two_to_five_targets(self):
        source = battle_source(tuple(row[0] for row in WEAPONS))
        states = initial_pc_npc_ranged_weapons(source)
        for entry,row in zip(states,WEAPONS,strict=True):
            with self.subTest(weapon=row[0]):
                self.assertTrue(npc_ranged_is_loaded(entry.weapon_state))
                if row[-1] is None:
                    self.assertIs(type(entry.weapon_state),FreeReloadWeaponState)
                    self.assertFalse(hasattr(entry.weapon_state,'loaded'))
                    self.assertFalse(hasattr(entry.weapon_state,'exacting'))
                else:
                    self.assertIs(type(entry.weapon_state),ReloadableWeaponState)
                    self.assertEqual(entry.weapon_state.required_successes,row[-1])
                    unloaded = begin_reload_cycle(entry.weapon_state,'actual:'+row[0].value)
                    self.assertFalse(npc_ranged_is_loaded(unloaded))
                    self.assertEqual(unloaded.exacting.required_successes,row[-1])
                    self.assertEqual(unloaded.exacting.accumulated_successes,0)
        with self.assertRaises(ValueError):
            PcNpcRangedState('other','primary',states[0].weapon_state)

    def test_bow_has_no_separate_exacting_test_while_crossbow_uses_actual_dexterity(self):
        source = battle_source((GeneratedWeapon.SHORTBOW,GeneratedWeapon.CROSSBOW))
        from towr.domain.pc_melee_result_models import initial_pc_melee_state
        state = initial_pc_melee_state(source)
        with self.assertRaises(ValueError):
            npc_ranged_reload_test(state,'minion1','no-bow-reload')
        test = npc_ranged_reload_test(state,'minion2','real-crossbow-reload')
        self.assertEqual(test.profile,InlineProfile(2,4))

    def test_repeater_forecast_uses_actual_reload_three_or_five_without_changing_shot_values(self):
        # A Test with exactly3 successes reloads a Crossbow in one action,
        # but a Handgun needs two. That alone changes this three-turn choice.
        reload_distribution = (0.,0.,0.,1.)
        self.assertTrue(_repeater_choice(1.,2.2,reload_distribution,3,3))
        self.assertFalse(_repeater_choice(1.,2.2,reload_distribution,3,5))

    def test_non_close_shooting_protection_does_not_offer_melee_or_shieldless_defence(self):
        source = battle_source()
        member = source.party[0]
        member = replace(member,pc=replace(member.pc,weapon_skill=10,melee=6,defence=6,
            agility=1,athletics=2))
        state = tactical_snapshot(replace(source,party=(member,)))
        self.assertIs(pc_shooting_protection(state,'pc1','minion1','protection')[0],Skill.ATHLETICS)
        shield = PcShieldLoadout(PcWeaponHand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
            PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
        protected = tactical_snapshot(replace(source,party=(replace(member,shield=shield),)))
        self.assertIs(pc_shooting_protection(protected,'pc1','minion1','protection')[0],Skill.DEFENCE)


if __name__ == '__main__':
    unittest.main()
