"""Requirements and valid proposals, without enumerating a Talent powerset."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedTalent,GeneratedWeapon


class FixedChoices:
    def __init__(self,bit=0):
        self.bit=bit
        self.calls=0

    def choice(self,values):
        self.calls+=1
        return values[0]

    def randrange(self,stop):
        self.calls+=1
        if stop!=2:
            raise AssertionError('this source only needs binary Talent choices')
        return self.bit


def space(**changes):
    values=dict(weapon_skill=(3,),strength=(4,),toughness=(3,),agility=(3,),melee=(4,),
        athletics=(4,),defence=(4,),brawn=(4,),weapon=(GeneratedWeapon.SWORD,),armour=(None,),
        shield=(None,),abilities=((),),allowed_talents=tuple(GeneratedTalent))
    values.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **values)


class GeneratedTalentGenerationTests(unittest.TestCase):
    def test_empty_and_complete_eligible_subsets_preserve_facts_and_source(self):
        source=space()
        empty,complete=source.sample(FixedChoices()),source.sample(FixedChoices(1))
        self.assertEqual(empty.talents,())
        self.assertEqual(complete.talents,tuple(GeneratedTalent))
        self.assertEqual(replace(complete,talents=()),empty)
        self.assertEqual(complete.participant('renamed').definition.generated_components,complete)

    def test_sampling_filters_requirements_at_the_exact_threshold(self):
        for ws,strength,expected in ((2,3,(GeneratedTalent.MAGIC_RESISTANCE,)),
                (3,3,(GeneratedTalent.MAGIC_RESISTANCE,GeneratedTalent.DEFENSIVE_STANCE)),
                (2,4,(GeneratedTalent.MAGIC_RESISTANCE,GeneratedTalent.WILD_ATTACK)),
                (3,4,tuple(GeneratedTalent))):
            with self.subTest(ws=ws,strength=strength):
                self.assertEqual(space(weapon_skill=(ws,),strength=(strength,)).sample(FixedChoices(1)).talents,expected)

    def test_fixed_numeric_source_can_generate_different_valid_talent_subsets(self):
        source=space()
        rng=Random(42)
        proposals=tuple(source.sample(rng) for _ in range(20))
        self.assertGreater(len({npc.talents for npc in proposals}),1)
        self.assertTrue(all(source.contains(npc) for npc in proposals))
        self.assertEqual(len({replace(npc,talents=()) for npc in proposals}),1)

    def test_explicit_empty_pool_disables_talents_and_has_no_talent_mutation(self):
        source=space(allowed_talents=())
        npc=source.sample(FixedChoices(1))
        self.assertEqual(npc.talents,())
        self.assertEqual(source.mutate(npc,FixedChoices()),npc)

    def test_stat_mutation_cannot_retain_a_talent_with_missing_requirement(self):
        source=space(strength=(3,4),allowed_talents=(GeneratedTalent.WILD_ATTACK,))
        initial=replace(source.sample(FixedChoices()),strength=4,talents=(GeneratedTalent.WILD_ATTACK,))
        without=source.mutate(initial,FixedChoices())
        self.assertEqual((without.strength,without.talents),(4,()))
        lower=source.mutate(without,FixedChoices())
        self.assertEqual((lower.strength,lower.talents),(3,()))
        self.assertEqual(initial.talents,(GeneratedTalent.WILD_ATTACK,))

    def test_invalid_source_is_rejected_instead_of_pruned_or_repaired(self):
        npc=space().sample(FixedChoices(1))
        for change in (dict(weapon_skill=2),dict(strength=3),dict(talents=('wild_attack',)),
                dict(talents=(GeneratedTalent.WILD_ATTACK,)*2),dict(talents=[])):
            with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                replace(npc,**change)
        forged=deepcopy(npc)
        object.__setattr__(forged,'strength',3)
        with self.assertRaises(ValueError):
            forged.participant('forged')
        self.assertEqual(forged.talents,npc.talents)

    def test_pool_is_typed_unique_and_mutation_admits_before_spending_rng(self):
        for invalid in ([],('unknown',),(GeneratedTalent.WILD_ATTACK,)*2,(True,)):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                space(allowed_talents=invalid)
        source=space(allowed_talents=())
        npc=replace(source.sample(FixedChoices()),talents=(GeneratedTalent.MAGIC_RESISTANCE,))
        rng=FixedChoices()
        with self.assertRaises(ValueError):
            source.mutate(npc,rng)
        self.assertEqual(rng.calls,0)


if __name__=='__main__':
    unittest.main()
