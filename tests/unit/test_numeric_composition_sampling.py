"""Numeric cohort sampling preserves facts and uses explicit, bounded RNG."""
from collections import Counter
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from towr.application.dynamic_encounter import NpcSearchSpace, NumericCompositionSample
from towr.domain.generated_npc_models import (
    GeneratedAbility, GeneratedNpc, GeneratedRangedFacts, GeneratedTalent, GeneratedWeapon,
)


def numeric_space(**changes):
    return NpcSearchSpace(**(dict(weapon_skill=(3,), strength=(4,), toughness=(5,2,3),
        agility=(3,), melee=(4,), athletics=(4,), defence=(4,),
        weapon=(GeneratedWeapon.SWORD,), light_armour=(True,), shield=(True,),
        abilities=((),), allowed_talents=(), ballistic_skill=(3,), shooting=(4,),
        initiative=(3,), dexterity=(4,)) | changes))


def fixed_member(space):
    return replace(space.sample(Random(12)), toughness=3)


class NumericCompositionSamplingTests(unittest.TestCase):
    def test_weighted_endpoint_midpoint_tickets_have_exact_rank_weights(self):
        space=numeric_space()
        member=fixed_member(space)
        for bias,expected in ((1,{2:1,3:3,5:9}),(-1,{2:9,3:3,5:1})):
            actual=Counter()
            for index in range(13):
                rng=Random(42)
                with patch.object(rng,'random',return_value=(index+.5)/13) as draw, \
                        patch.object(rng,'choice',side_effect=AssertionError('weighted draw used choice')):
                    result=space.resample_numeric((member,),rng,bias=bias)
                actual[result.composition[0].toughness]+=1
                draw.assert_called_once_with()
                self.assertIsInstance(result,NumericCompositionSample)
                self.assertEqual(result.variable_fields,1)
                self.assertEqual(result.changed_members,int(result.composition[0]!=member))
                self.assertEqual(result.bias,float(bias))
            self.assertEqual(actual,Counter(expected))

    def test_weighted_sampling_is_independent_of_allowed_tuple_order(self):
        unsorted=numeric_space(toughness=(5,2,3))
        ordered=numeric_space(toughness=(2,3,5))
        member=fixed_member(unsorted)
        for bias in (-1.,-.25,.25,1.):
            for seed in (0,42,202):
                with self.subTest(bias=bias,seed=seed):
                    self.assertEqual(unsorted.resample_numeric((member,),Random(seed),bias=bias),
                        ordered.resample_numeric((member,),Random(seed),bias=bias))

    def test_neutral_sampling_is_uniform_choice_including_current_value(self):
        space=numeric_space()
        member=fixed_member(space)
        values=[]
        for index in range(3):
            rng=Random(42)
            with patch.object(rng,'choice',side_effect=lambda choices:choices[index]) as choose, \
                    patch.object(rng,'random',side_effect=AssertionError('neutral draw used weighted CDF')):
                result=space.resample_numeric((member,),rng)
            choose.assert_called_once()
            values.append(result.composition[0].toughness)
        self.assertEqual(Counter(values),Counter({2:1,3:1,5:1}))
        self.assertEqual(values.count(member.toughness),1)
        self.assertTrue(any(value!=member.toughness for value in values))

    def test_numeric_fields_change_while_equipment_talents_and_ranged_confirmations_remain(self):
        stance,wild,resistance=(GeneratedTalent.DEFENSIVE_STANCE,GeneratedTalent.WILD_ATTACK,
            GeneratedTalent.MAGIC_RESISTANCE)
        space=numeric_space(weapon_skill=(2,3,5),strength=(3,4,6),agility=(2,3,5),
            melee=(2,4,6),athletics=(2,4,6),defence=(2,4,6),
            weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_HANDBOW),
            light_armour=(False,True),shield=(False,True),
            abilities=((),(GeneratedAbility.DRAINED_ON_HIT,)),allowed_talents=(stance,wild,resistance),
            ballistic_skill=(2,3,5),shooting=(2,4,6),initiative=(2,3,5),dexterity=(2,4,6))
        melee=GeneratedNpc(3,4,3,3,4,4,GeneratedWeapon.SWORD,True,
            (GeneratedAbility.DRAINED_ON_HIT,),defence=4,shield=True,talents=(stance,wild))
        pistol=GeneratedNpc(3,4,3,3,4,4,GeneratedWeapon.PISTOL,False,(),defence=4,shield=False,
            talents=(resistance,),ranged=GeneratedRangedFacts(3,4,3,4,True,True,True,True))
        handbow=GeneratedNpc(3,4,3,3,4,4,GeneratedWeapon.REPEATER_HANDBOW,True,(),
            defence=4,shield=False,talents=(stance,wild),
            ranged=GeneratedRangedFacts(3,4,3,4,True,True,None,None))
        composition=(melee,pistol,handbow)
        original=deepcopy(composition)
        rng=Random(42)
        with patch.object(rng,'random',return_value=.999999):
            result=space.resample_numeric(composition,rng,bias=1)
        self.assertEqual(result.variable_fields,7*3+4*2)
        self.assertEqual(result.changed_members,3)
        for before,after in zip(composition,result.composition):
            self.assertTrue(space.contains(after))
            for field in ('weapon','light_armour','shield','abilities','talents'):
                self.assertEqual(getattr(after,field),getattr(before,field))
            self.assertEqual((after.weapon_skill,after.strength,after.toughness,after.agility),
                (5,6,5,5))
            self.assertEqual((after.melee,after.athletics,after.defence),(6,6,6))
            if before.ranged is None:
                self.assertIsNone(after.ranged)
            else:
                for field in ('initially_loaded','ammunition_supply_confirmed',
                        'has_blackpowder_lore','has_blackpowder_kit'):
                    self.assertIs(getattr(after.ranged,field),getattr(before.ranged,field))
                self.assertEqual((after.ranged.ballistic_skill,after.ranged.shooting,
                    after.ranged.initiative,after.ranged.dexterity),(5,6,5,6))
        self.assertEqual(composition,original)

    def test_prerequisites_filter_candidates_before_weighted_selection(self):
        talents=(GeneratedTalent.DEFENSIVE_STANCE,GeneratedTalent.WILD_ATTACK)
        space=numeric_space(weapon_skill=(2,3,5),strength=(3,4,6),toughness=(3,),
            allowed_talents=talents)
        member=replace(fixed_member(space),weapon_skill=3,strength=4,talents=talents)
        for bias,ticket,expected in ((-1,0.,(3,4)),(1,.999999,(5,6))):
            rng=Random(42)
            with patch.object(rng,'random',return_value=ticket) as draw:
                result=space.resample_numeric((member,),rng,bias=bias)
            after,=result.composition
            self.assertEqual((after.weapon_skill,after.strength),expected)
            self.assertEqual(after.talents,talents)
            self.assertTrue(space.contains(after))
            self.assertEqual(result.variable_fields,2)
            self.assertEqual(draw.call_count,2)

    def test_ten_member_sampling_is_reproducible_and_changes_multiple_members(self):
        space=numeric_space()
        composition=(fixed_member(space),)*10
        original=deepcopy(composition)
        first=space.resample_numeric(composition,Random(42),bias=1)
        repeated=space.resample_numeric(composition,Random(42),bias=1)
        self.assertEqual(first,repeated)
        self.assertEqual(first.variable_fields,10)
        self.assertGreaterEqual(first.changed_members,2)
        self.assertEqual(first.changed_members,sum(a!=b for a,b in zip(composition,first.composition)))
        self.assertTrue(all(space.contains(member) for member in first.composition))
        self.assertEqual(composition,original)
        with self.assertRaises(FrozenInstanceError):
            first.bias=0.

    def test_immutable_numeric_space_does_not_consume_rng(self):
        space=numeric_space(toughness=(3,))
        composition=(fixed_member(space),)*3
        for bias in (-1,0,1):
            rng=Random(42)
            before=rng.getstate()
            with patch.object(rng,'random',side_effect=AssertionError('unexpected random draw')), \
                    patch.object(rng,'choice',side_effect=AssertionError('unexpected choice')):
                result=space.resample_numeric(composition,rng,bias=bias)
            self.assertEqual(result.composition,composition)
            self.assertEqual(result.variable_fields,0)
            self.assertEqual(result.changed_members,0)
            self.assertEqual(rng.getstate(),before)

    def test_invalid_bias_is_rejected_before_rng(self):
        class FloatSubclass(float):pass
        space=numeric_space()
        composition=(fixed_member(space),)
        values=(True,False,None,'0',-2,2,-1.01,1.01,float('nan'),float('inf'),
            -float('inf'),Decimal('0'),Fraction(0,1),FloatSubclass(0))
        for bias in values:
            rng=Random(42)
            before=rng.getstate()
            with self.subTest(bias=bias), \
                    patch.object(rng,'random',side_effect=AssertionError('unexpected random draw')), \
                    patch.object(rng,'choice',side_effect=AssertionError('unexpected choice')):
                with self.assertRaises((ValueError,TypeError)):
                    space.resample_numeric(composition,rng,bias=bias)
            self.assertEqual(rng.getstate(),before)

    def test_whole_composition_admission_precedes_any_sampling(self):
        space=numeric_space()
        member=fixed_member(space)
        foreign=replace(member,toughness=99)
        inputs=((),[member],iter((member,)),(object(),),(member,foreign))
        for composition in inputs:
            rng=Random(42)
            before=rng.getstate()
            with self.subTest(composition=composition), \
                    patch.object(rng,'random',side_effect=AssertionError('unexpected random draw')), \
                    patch.object(rng,'choice',side_effect=AssertionError('unexpected choice')):
                with self.assertRaises((ValueError,TypeError)):
                    space.resample_numeric(composition,rng,bias=1)
            self.assertEqual(rng.getstate(),before)


if __name__=='__main__':unittest.main()
