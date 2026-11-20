"""Requirements and valid proposals, without enumerating a Talent powerset."""
from tests.support.talent_sources import paid_talent, free_talent
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.talent_catalog import TalentId
from towr.domain.ranged_weapon_profiles import RangedWeaponHands


CONNECTED_TALENTS=(TalentId.MAGIC_RESISTANCE,TalentId.DEFENSIVE_STANCE,TalentId.WILD_ATTACK)


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
        athletics=(4,),defence=(4,),brawn=(4,),endurance=(4,),weapon=(GeneratedWeapon.SWORD,),armour=(None,),
        shield=(None,),abilities=((),),allowed_talents=CONNECTED_TALENTS)
    values.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **values)


class GeneratedNpcTalentGenerationTests(unittest.TestCase):
    def test_armour_bane_is_a_generated_component_without_characteristic_requirements(self):
        search=space(weapon_skill=(1,),strength=(1,),weapon=(GeneratedWeapon.AXE,),
            allowed_talents=(TalentId.ARMOUR_BANE,))
        empty=search.sample(FixedChoices())
        selected=search.sample(FixedChoices(1))
        self.assertEqual(empty.talents,())
        self.assertEqual(selected.talents,(paid_talent(TalentId.ARMOUR_BANE),))
        self.assertTrue(search.contains(selected))
        self.assertEqual(selected.participant('generated:bane').definition.talents,selected.talents)
        self.assertEqual(search.mutate(empty,FixedChoices()).talents,selected.talents)
        self.assertEqual(search.mutate(selected,FixedChoices()).talents,())

    def test_mighty_blow_and_rapid_reload_use_actual_generated_strength_and_bs(self):
        for strength,bs in ((3,3),(3,4),(4,3),(4,4)):
            with self.subTest(strength=strength,bs=bs):
                search=space(strength=(strength,),ballistic_skill=(bs,),shooting=(4,),
                    initiative=(3,),dexterity=(4,),weapon=(GeneratedWeapon.PISTOL,),
                    weapon_grip=(RangedWeaponHands.ONE_HANDED,),
                    allowed_talents=(TalentId.MIGHTY_BLOW,TalentId.RAPID_RELOAD))
                npc=search.sample(FixedChoices(1))
                expected=tuple(paid_talent(talent) for talent,eligible in (
                    (TalentId.MIGHTY_BLOW,strength>=4),(TalentId.RAPID_RELOAD,bs>=4)) if eligible)
                self.assertEqual(npc.talents,expected)
                self.assertEqual(npc.ranged.ballistic_skill,bs)
                self.assertTrue(search.contains(npc))
                self.assertEqual(npc.participant('generated:shooting').definition.talents,expected)

    def test_numeric_ranged_mutation_never_keeps_a_failed_rapid_reload_requirement(self):
        for weapon in (GeneratedWeapon.PISTOL,GeneratedWeapon.THROWING_AXE):
            with self.subTest(weapon=weapon):
                search=space(ballistic_skill=(3,4),shooting=(4,),initiative=(3,),dexterity=(4,),
                    throwing=(4,),weapon=(weapon,),weapon_grip=(RangedWeaponHands.ONE_HANDED,),
                    allowed_talents=(TalentId.RAPID_RELOAD,))
                base=search.sample(FixedChoices())
                def with_bs(npc,value,**changes):
                    return replace(npc,**changes,**({'ranged':replace(npc.ranged,ballistic_skill=value)}
                        if npc.ranged is not None else {'ballistic_skill':value}))
                admitted=with_bs(base,4,talents=(paid_talent(TalentId.RAPID_RELOAD),))
                with self.assertRaises(ValueError):
                    with_bs(admitted,3)
                for seed in range(8):
                    proposed=search.mutate(admitted,Random(seed))
                    self.assertTrue(search.contains(proposed))
                    if proposed.talents:
                        self.assertGreaterEqual(proposed.ballistic_skill if proposed.ranged is None
                            else proposed.ranged.ballistic_skill,4)

    def test_empty_and_complete_eligible_subsets_preserve_facts_and_source(self):
        source=space()
        empty,complete=source.sample(FixedChoices()),source.sample(FixedChoices(1))
        self.assertEqual(empty.talents,())
        self.assertEqual(complete.talents,tuple(paid_talent(id) for id in CONNECTED_TALENTS))
        self.assertEqual(replace(complete,talents=()),empty)
        self.assertEqual(complete.participant('renamed').definition.generated_components,complete)

    def test_sampling_filters_requirements_at_the_exact_threshold(self):
        for ws,strength,expected in ((2,3,(TalentId.MAGIC_RESISTANCE,)),
                (3,3,(TalentId.MAGIC_RESISTANCE,TalentId.DEFENSIVE_STANCE)),
                (2,4,(TalentId.MAGIC_RESISTANCE,TalentId.WILD_ATTACK)),
                (3,4,CONNECTED_TALENTS)):
            with self.subTest(ws=ws,strength=strength):
                self.assertEqual(space(weapon_skill=(ws,),strength=(strength,)).sample(FixedChoices(1)).talents,
                    tuple(paid_talent(id) for id in expected))

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
        source=space(strength=(3,4),allowed_talents=(TalentId.WILD_ATTACK,))
        initial=replace(source.sample(FixedChoices()),strength=4,talents=(paid_talent(TalentId.WILD_ATTACK),))
        without=source.mutate(initial,FixedChoices())
        self.assertEqual((without.strength,without.talents),(4,()))
        lower=source.mutate(without,FixedChoices())
        self.assertEqual((lower.strength,lower.talents),(3,()))
        self.assertEqual(initial.talents,(paid_talent(TalentId.WILD_ATTACK),))

    def test_invalid_source_is_rejected_instead_of_pruned_or_repaired(self):
        npc=space().sample(FixedChoices(1))
        for change in (dict(weapon_skill=2),dict(strength=3),dict(talents=('wild_attack',)),
                dict(talents=(paid_talent(TalentId.WILD_ATTACK),)*2),
                dict(talents=(TalentId.WILD_ATTACK,)),dict(talents=[]),
                dict(talents=(free_talent(TalentId.LUCKY),))):
            with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                replace(npc,**change)
        forged=deepcopy(npc)
        object.__setattr__(forged,'strength',3)
        with self.assertRaises(ValueError):
            forged.participant('forged')
        self.assertEqual(forged.talents,npc.talents)

    def test_pool_is_typed_unique_and_mutation_admits_before_spending_rng(self):
        for invalid in ([],('unknown',),(TalentId.WILD_ATTACK,)*2,(True,),
                (TalentId.LUCKY,),(paid_talent(TalentId.WILD_ATTACK),)):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                space(allowed_talents=invalid)
        source=space(allowed_talents=())
        npc=replace(source.sample(FixedChoices()),talents=(paid_talent(TalentId.MAGIC_RESISTANCE),))
        rng=FixedChoices()
        with self.assertRaises(ValueError):
            source.mutate(npc,rng)
        self.assertEqual(rng.calls,0)


if __name__=='__main__':
    unittest.main()
