"""Acquisition source boundaries from PG1.4 III73–81/138–139, no combat/RNG."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from towr.domain.talent_catalog import (
    FamiliarEffect, TalentEquipmentRequirement as E, TalentId as T,
    TalentOrigin as O, TalentStatusTier as S,
)
from towr.domain.talent_models import (
    AcquiredTalent, BloodlineChoice, DeityChoice, DeityId, FamiliarEffectChoice,
    HatredGroupChoice, MagicLoreChoice, OathChoice, TalentAcquisition,
    TalentAcquisitionPhase as P, TalentFunding as F, TalentLoreFact,
    TalentOwnerFacts, has_talent, talent_purchases, validate_acquired_talents,
)


CHOICES = {
    T.FAITH: DeityChoice(DeityId.ULRIC),
    T.FAMILIAR: FamiliarEffectChoice(FamiliarEffect.ARMOURED),
    T.HATRED: HatredGroupChoice('faction:greenskins'),
    T.HONOUR_BOUND: OathChoice('oath:protect-allies'),
    T.SECRET_BLOODLINE: BloodlineChoice('bloodline:ancestor'),
    T.TOUCHED_BY_THE_WINDS: MagicLoreChoice('elementalism'),
}
CREATION_ONLY = (T.LONGBEARD, T.SECRET_BLOODLINE, T.SHORT_SIZE)


def acquired(id, *, free=False, phase=None):
    """Declare the selected source, not inferred or repaired production facts."""
    phase = phase or (P.CREATION if free or id in CREATION_ONLY else P.ADVANCEMENT)
    return AcquiredTalent(id, (TalentAcquisition(phase, F.FREE if free else F.XP,
        CHOICES.get(id), True if id is T.FAITH and phase is P.ADVANCEMENT else None),))


# Independent source cases, not calculated from the catalog being validated.
# Each row is (Talent, its minimal relevant facts, explicitly owned prerequisite).
PAID_CASES = (
    (T.ACCELERATED_RECOVERY, dict(toughness=5), ()),
    (T.ACROBATIC, dict(agility=4), ()),
    (T.ALLIES_IN_ARMS, dict(fellowship=4), ()),
    (T.ARMOUR_BANE, {}, ()),
    (T.BASH_ATTACK, dict(strength=5), ()),
    (T.BACK_IN_THE_SADDLE, dict(agility=4), ()),
    (T.BATTLEFIELD_MUSICIAN, dict(equipment=(E.MUSICIANS_GEAR,)), ()),
    (T.BLESSINGS_OF_THE_LADY, dict(origin=O.BRETONNIAN_HUMAN,
        lores=(TalentLoreFact('high_society'),)), (T.HONOUR_BOUND,)),
    (T.CAREFUL_AIM, dict(reason=4), ()),
    (T.CLEAVING_BLOW, dict(strength=5), ()),
    (T.COMBAT_SURGEON, dict(lores=(TalentLoreFact('anatomy'),)), ()),
    (T.DEEP_FORMATION, {}, ()),
    (T.DEFENSIVE_STANCE, dict(weapon_skill=3), ()),
    (T.DISPELLER, {}, (T.WIZARD,)),
    (T.EXCEPTIONAL_HEARING, dict(initiative=4), ()),
    (T.FAITH, dict(origin=O.EMPIRE_HUMAN), ()),
    (T.FAMILIAR, {}, (T.WIZARD,)),
    (T.FEIGNED_FLIGHT, {}, ()),
    (T.FIGHT_AS_ONE, {}, ()),
    (T.FRIGHTENING, {}, ()),
    (T.GOLDEN_VOICE, dict(fellowship=4), ()),
    (T.GRAIL_VOW, dict(grail_quest_completed=True), (T.QUESTING_VOW,)),
    (T.HARDY, dict(toughness=4), ()),
    (T.HATRED, {}, ()),
    (T.HOLD_THE_LINE, dict(fellowship=4), ()),
    (T.HONOUR_BOUND, {}, ()),
    (T.INTENSE_SCRUTINY, dict(initiative=4), ()),
    (T.INTERCEPTOR, dict(agility=5), ()),
    (T.IRON_GUT, dict(origin=O.DWARF), ()),
    (T.KEEN_EYED, dict(initiative=4), ()),
    (T.LIGHTNING_REFLEXES, dict(initiative=5), ()),
    (T.LONGBEARD, dict(origin=O.DWARF), ()),
    (T.LUCKY, {}, ()),
    (T.MAGIC_RESISTANCE, {}, ()),
    (T.MIGHTY_BLOW, dict(strength=4), ()),
    (T.NIGHT_DWELLER, {}, ()),
    (T.POLYMATH, dict(reason=4), ()),
    (T.QUESTING_VOW, {}, (T.BLESSINGS_OF_THE_LADY,)),
    (T.QUICK_CHANGE, dict(equipment=(E.GROOMING_KIT,)), ()),
    (T.QUICK_THROW, dict(weapon_skill=4, ballistic_skill=4), ()),
    (T.RAPID_RELOAD, dict(ballistic_skill=4), ()),
    (T.RESISTANCE_TO_CORRUPTION, {}, ()),
    (T.RESOLUTE, dict(reason=4), ()),
    (T.RIPOSTE, dict(weapon_skill=5), ()),
    (T.SECRET_BLOODLINE, {}, ()),
    (T.SHORT_SIZE, {}, ()),
    (T.SNAKE_CHARMER, {}, ()),
    (T.SPITESEER, dict(origin=O.WOOD_ELF), ()),
    (T.STAND_AND_SHOOT, dict(initiative=4), ()),
    (T.STEER_CLEAR, {}, ()),
    (T.TAUNTER, {}, ()),
    (T.THIRST_FOR_KNOWLEDGE, dict(reason=4), ()),
    (T.TOUCHED_BY_THE_WINDS, dict(origin=O.EMPIRE_HUMAN), ()),
    (T.UNBREAKABLE, {}, (T.RESOLUTE,)),
    (T.VALOUR_OF_AGES, dict(origin=O.HIGH_ELF), ()),
    (T.VANGUARD, dict(agility=4), ()),
    (T.VOUCH_FOR_THEM, dict(fellowship=4, status=S.SILVER), ()),
    (T.WILD_ATTACK, dict(strength=4), ()),
    (T.WIZARD, dict(origin=O.EMPIRE_HUMAN,
        lores=(TalentLoreFact('elementalism', magic=True),)), ()),
)


class TalentModelsTests(unittest.TestCase):
    def test_all59_paid_sources_and_free_creation_sources_are_valid(self):
        self.assertEqual(len(PAID_CASES), 59)
        self.assertEqual({id for id, _, _ in PAID_CASES}, set(T))
        for id, kwargs, prerequisites in PAID_CASES:
            with self.subTest(id=id):
                facts = TalentOwnerFacts(**kwargs)
                owned = (acquired(id), *(acquired(value, free=True) for value in prerequisites))
                validate_acquired_talents(owned, facts)
                self.assertTrue(has_talent(owned, id))
                self.assertEqual(talent_purchases(owned, id), 1)
                validate_acquired_talents((acquired(id, free=True),),
                    TalentOwnerFacts(grail_quest_completed=id is T.GRAIL_VOW))

    def test_every_printed_numeric_threshold_rejects_lower_and_missing_base_fact(self):
        for id, kwargs, prerequisites in PAID_CASES:
            for field, value in kwargs.items():
                if type(value) is not int:
                    continue
                for bad in (None, value - 1):
                    with self.subTest(id=id, field=field, bad=bad):
                        facts = TalentOwnerFacts(**dict(kwargs, **{field: bad}))
                        owned = (acquired(id), *(acquired(t, free=True) for t in prerequisites))
                        with self.assertRaises(ValueError):
                            validate_acquired_talents(owned, facts)

    def test_paid_creation_checks_requirements_and_free_creation_waives_them(self):
        facts = TalentOwnerFacts(weapon_skill=2)
        validate_acquired_talents((acquired(T.DEFENSIVE_STANCE, free=True),), facts)
        for phase in (P.CREATION, P.ADVANCEMENT):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(T.DEFENSIVE_STANCE, phase=phase),), facts)
        validate_acquired_talents((acquired(T.DEFENSIVE_STANCE, phase=P.CREATION),),
            TalentOwnerFacts(weapon_skill=3))
        with self.assertRaises(ValueError):
            TalentAcquisition(P.ADVANCEMENT, F.FREE)

    def test_three_creation_only_clauses_are_not_a_prerequisite_waiver(self):
        for id in CREATION_ONLY:
            with self.subTest(id=id), self.assertRaises(ValueError):
                acquired(id, phase=P.ADVANCEMENT)
        validate_acquired_talents((acquired(T.LONGBEARD, free=True),), TalentOwnerFacts())
        with self.assertRaises(ValueError):
            validate_acquired_talents((acquired(T.LONGBEARD),), TalentOwnerFacts(origin=O.EMPIRE_HUMAN))

    def test_specific_origin_requirements_and_exclusions_need_actual_origin_facts(self):
        cases = ((T.SPITESEER, O.WOOD_ELF, O.HIGH_ELF),
            (T.VALOUR_OF_AGES, O.HIGH_ELF, O.WOOD_ELF),
            (T.IRON_GUT, O.EMPIRE_HUMAN, O.HIGH_ELF),
            (T.TOUCHED_BY_THE_WINDS, O.EMPIRE_HUMAN, O.DWARF))
        for id, allowed, forbidden in cases:
            with self.subTest(id=id):
                validate_acquired_talents((acquired(id),), TalentOwnerFacts(origin=allowed))
                for origin in (None, forbidden):
                    with self.assertRaises(ValueError):
                        validate_acquired_talents((acquired(id),), TalentOwnerFacts(origin=origin))
                validate_acquired_talents((acquired(id, free=True),), TalentOwnerFacts(origin=forbidden))

    def test_known_magic_lore_and_explicit_touched_lore_are_different_sources(self):
        for origin in (None, O.DWARF, O.HALFLING):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(T.WIZARD),), TalentOwnerFacts(origin=origin,
                    lores=(TalentLoreFact('elementalism', magic=True),)))
        for lores in ((), (TalentLoreFact('anatomy'),)):
            with self.subTest(lores=lores), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(T.WIZARD),),
                    TalentOwnerFacts(origin=O.EMPIRE_HUMAN, lores=lores))
        validate_acquired_talents((acquired(T.TOUCHED_BY_THE_WINDS),),
            TalentOwnerFacts(origin=O.EMPIRE_HUMAN))

    def test_lore_equipment_and_status_facts_are_not_inferred(self):
        for id in (T.COMBAT_SURGEON, T.BATTLEFIELD_MUSICIAN, T.QUICK_CHANGE):
            with self.subTest(id=id), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(id),), TalentOwnerFacts())
        with self.assertRaises(ValueError):
            validate_acquired_talents((acquired(T.COMBAT_SURGEON),),
                TalentOwnerFacts(lores=(TalentLoreFact('high_society'),)))
        for status in (None, S.BRASS):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(T.VOUCH_FOR_THEM),),
                    TalentOwnerFacts(fellowship=4, status=status))
        validate_acquired_talents((acquired(T.VOUCH_FOR_THEM),),
            TalentOwnerFacts(fellowship=4, status=S.GOLD))

    def test_prerequisite_talents_use_complete_set_without_cross_talent_order(self):
        owned = (acquired(T.DISPELLER), acquired(T.WIZARD, free=True))
        validate_acquired_talents(owned, TalentOwnerFacts())
        validate_acquired_talents(tuple(reversed(owned)), TalentOwnerFacts())
        for id in (T.DISPELLER, T.FAMILIAR, T.QUESTING_VOW, T.UNBREAKABLE):
            with self.subTest(id=id), self.assertRaises(ValueError):
                validate_acquired_talents((acquired(id),), TalentOwnerFacts())

    def test_grail_quest_is_operative_even_for_free_creation(self):
        owned = (acquired(T.GRAIL_VOW, free=True),)
        with self.assertRaises(ValueError):
            validate_acquired_talents(owned, TalentOwnerFacts())
        validate_acquired_talents(owned, TalentOwnerFacts(grail_quest_completed=True))

    def test_faith_has_one_chosen_god_and_unlimited_confirmed_purchases(self):
        self.assertEqual({value.value for value in DeityId},
            {'ulric', 'taal', 'rhya', 'sigmar', 'manann', 'morr', 'ranald', 'verena', 'myrmidia', 'shallya'})
        source = (TalentAcquisition(P.ADVANCEMENT, F.XP, DeityChoice(DeityId.SHALLYA), True),
            *(TalentAcquisition(P.ADVANCEMENT, F.XP, devotion_confirmed=True) for _ in range(19)))
        faith = AcquiredTalent(T.FAITH, source)
        validate_acquired_talents((faith,), TalentOwnerFacts(origin=O.EMPIRE_HUMAN))
        self.assertEqual(talent_purchases((faith,), T.FAITH), 20)
        for bad in (None, False):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                replace(faith, acquisitions=(*source[:-1], replace(source[-1], devotion_confirmed=bad)))
        with self.assertRaises(ValueError):
            replace(faith, acquisitions=(*source[:1], replace(source[1], choice=DeityChoice(DeityId.MORR))))
        validate_acquired_talents((acquired(T.FAITH, phase=P.CREATION),),
            TalentOwnerFacts(origin=O.EMPIRE_HUMAN))

    def test_faith_spellcasting_exclusion_is_not_a_free_creation_waiver(self):
        faith = acquired(T.FAITH, free=True)
        with self.assertRaises(ValueError):
            validate_acquired_talents((faith,), TalentOwnerFacts(can_cast_spells=True))
        for id in (T.WIZARD, T.TOUCHED_BY_THE_WINDS):
            with self.subTest(id=id), self.assertRaises(ValueError):
                validate_acquired_talents((faith, acquired(id, free=True)), TalentOwnerFacts())
        validate_acquired_talents((faith,), TalentOwnerFacts(origin=O.DWARF))

    def test_familiar_purchases_add_distinct_effects_instead_of_numeric_upgrades(self):
        familiar = AcquiredTalent(T.FAMILIAR, tuple(TalentAcquisition(P.CREATION, F.FREE,
            FamiliarEffectChoice(effect)) for effect in FamiliarEffect))
        validate_acquired_talents((familiar,), TalentOwnerFacts())
        self.assertEqual(talent_purchases((familiar,), T.FAMILIAR), 9)
        with self.assertRaises(ValueError):
            replace(familiar, acquisitions=(*familiar.acquisitions, familiar.acquisitions[0]))
        with self.assertRaises(TypeError):
            replace(familiar, acquisitions=(replace(familiar.acquisitions[0], choice=None),))

    def test_only_wizard_can_have_up_to_four_purchases(self):
        source = tuple(TalentAcquisition(P.CREATION, F.FREE) for _ in range(4))
        wizard = AcquiredTalent(T.WIZARD, source)
        validate_acquired_talents((wizard,), TalentOwnerFacts())
        self.assertEqual(talent_purchases((wizard,), T.WIZARD), 4)
        with self.assertRaises(ValueError):
            replace(wizard, acquisitions=(*source, source[0]))
        for id in set(T) - {T.WIZARD, T.FAITH, T.FAMILIAR}:
            with self.subTest(id=id), self.assertRaises(ValueError):
                first = acquired(id, free=True)
                replace(first, acquisitions=first.acquisitions * 2)

    def test_choices_are_typed_required_and_cannot_appear_on_other_talents(self):
        for id in CHOICES:
            with self.subTest(id=id), self.assertRaises(TypeError):
                AcquiredTalent(id, (TalentAcquisition(P.CREATION, F.FREE),))
        with self.assertRaises(TypeError):
            AcquiredTalent(T.HATRED, (TalentAcquisition(P.CREATION, F.FREE, OathChoice('wrong')),))
        with self.assertRaises(ValueError):
            AcquiredTalent(T.LUCKY, (TalentAcquisition(P.CREATION, F.FREE, MagicLoreChoice('wrong')),))
        for constructor in (HatredGroupChoice, OathChoice, BloodlineChoice, MagicLoreChoice, TalentLoreFact):
            for bad in ('', '  ', True):
                with self.subTest(constructor=constructor, bad=bad), self.assertRaises(TypeError):
                    constructor(bad)
        with self.assertRaises(TypeError):
            DeityChoice('ulric')
        with self.assertRaises(TypeError):
            FamiliarEffectChoice('armoured')

    def test_immutable_exact_sources_reject_bool_numbers_aliases_and_duplicates(self):
        for field in ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                'initiative', 'agility', 'reason', 'fellowship'):
            for bad in (True, 0, -1, 3.0):
                with self.subTest(field=field, bad=bad), self.assertRaises(TypeError):
                    TalentOwnerFacts(**{field: bad})
        for kwargs in (dict(origin='dwarf'), dict(status='silver'), dict(can_cast_spells=1),
                dict(grail_quest_completed=1), dict(lores=[]), dict(equipment=[])):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                TalentOwnerFacts(**kwargs)
        with self.assertRaises(ValueError):
            TalentOwnerFacts(lores=(TalentLoreFact('anatomy'), TalentLoreFact('anatomy', True)))
        with self.assertRaises(ValueError):
            TalentOwnerFacts(equipment=(E.GROOMING_KIT, E.GROOMING_KIT))
        with self.assertRaises(TypeError):
            TalentAcquisition('creation', F.FREE)
        with self.assertRaises(TypeError):
            TalentAcquisition(P.CREATION, 'free')
        with self.assertRaises(TypeError):
            TalentAcquisition(P.CREATION, F.FREE, devotion_confirmed=1)
        with self.assertRaises(ValueError):
            AcquiredTalent(T.LUCKY, (TalentAcquisition(P.CREATION, F.FREE, devotion_confirmed=True),))

    def test_queries_and_validator_recheck_untrusted_nested_immutable_source(self):
        owned = (acquired(T.LUCKY),)
        self.assertTrue(has_talent(owned, T.LUCKY))
        self.assertFalse(has_talent(owned, T.WIZARD))
        self.assertEqual(talent_purchases(owned, T.WIZARD), 0)
        for bad in ([owned[0]], (owned[0], owned[0]), (True,)):
            with self.subTest(bad=bad), self.assertRaises((TypeError, ValueError)):
                has_talent(bad, T.LUCKY)
        with self.assertRaises(TypeError):
            talent_purchases(owned, 'lucky')
        forged = deepcopy(owned)
        object.__setattr__(forged[0].acquisitions[0], 'funding', 'xp')
        with self.assertRaises(TypeError):
            validate_acquired_talents(forged, TalentOwnerFacts())
        facts = TalentOwnerFacts(lores=(TalentLoreFact('elementalism', True),))
        forged_facts = deepcopy(facts)
        object.__setattr__(forged_facts.lores[0], 'magic', 1)
        with self.assertRaises(TypeError):
            validate_acquired_talents(owned, forged_facts)

    def test_pickle_preserves_complete_acquisition_choices_and_base_facts(self):
        owned = (acquired(T.HATRED, free=True), acquired(T.WIZARD, free=True),
            acquired(T.FAMILIAR, free=True))
        facts = TalentOwnerFacts(origin=O.EMPIRE_HUMAN,
            lores=(TalentLoreFact('elementalism', True),), equipment=(E.GROOMING_KIT,))
        restored = pickle.loads(pickle.dumps((owned, facts)))
        self.assertEqual(restored, (owned, facts))
        validate_acquired_talents(*restored)
        with self.assertRaises(FrozenInstanceError):
            facts.origin = O.DWARF
        with self.assertRaises(FrozenInstanceError):
            owned[0].acquisitions[0].choice.group_id = 'changed'


if __name__ == '__main__':
    unittest.main()
