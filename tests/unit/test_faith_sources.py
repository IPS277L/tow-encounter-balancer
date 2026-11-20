"""Complete Faith sources and lifetime expenditure, no invented divine effects."""
from copy import deepcopy
from dataclasses import FrozenInstanceError,replace
import pickle
import unittest

from tests.support.talent_sources import free_talent
from towr.domain.faith_catalog import (
    DEITY_DEFINITIONS,PRAYER_DEFINITIONS,DeityDefinition,PrayerDefinition,
    PrayerDuration,PrayerId,PrayerTiming,deity_definition,prayer_definition,prayers_for_deity,
)
from towr.domain.faith_models import (
    FaithAccess,FaithMiracleLedger,MiracleUse,faith_access,use_faith_miracle,
)
from towr.domain.talent_catalog import TalentId,TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent,DeityChoice,DeityId,MagicLoreChoice,TalentAcquisition,
    TalentAcquisitionPhase as P,TalentFunding as F,TalentOwnerFacts,validate_acquired_talents,
)


def faith_talents(purchases,*,deity=DeityId.ULRIC):
    if purchases==0:
        return ()
    source=(AcquiredTalent(TalentId.FAITH,(
        TalentAcquisition(P.ADVANCEMENT,F.XP,DeityChoice(deity),True),
        *(TalentAcquisition(P.ADVANCEMENT,F.XP,devotion_confirmed=True)
            for _ in range(purchases-1)))),)
    # Confirm the paid fixture's real Origin and acquisition facts. Access
    # itself does not manufacture these facts or bypass the owner's validator.
    validate_acquired_talents(source,TalentOwnerFacts(origin=TalentOrigin.EMPIRE_HUMAN))
    return source


class FaithCatalogTests(unittest.TestCase):
    def test_all_ten_gods_and_thirty_named_prayers_have_their_exact_book_sources(self):
        expected=(
            (DeityId.ULRIC,140,('Hoarfrost’s Chill','Howl of the Wolf','Winter’s Bite')),
            (DeityId.TAAL,141,('Lord of the Wild','Stag’s Leap','Tanglefoot')),
            (DeityId.RHYA,142,('Rhya’s Shelter','Rhya’s Harvest','Rhya’s Children')),
            (DeityId.SIGMAR,143,('Hammer of Sigmar','Heed Not the Witch','Beacon of Righteous Virtue')),
            (DeityId.MANANN,144,('Drowned Man’s Face','Winds Fair & Foul','Waterwalk')),
            (DeityId.MORR,145,('Last Rites','Stay Morr’s Hand','Portal’s Threshold')),
            (DeityId.RANALD,146,('An Invitation','Rich Man, Poor Man, Beggar, Thief','Ranald’s Luck')),
            (DeityId.VERENA,147,('Shackles of Truth','Sword of Justice','Truth Will Out')),
            (DeityId.MYRMIDIA,148,('Eagle’s Eyes','Blazing Sun','Shield of Myrmidia')),
            (DeityId.SHALLYA,149,('Bitter Carthasis','Martyr','Shallya’s Tears')),
        )
        self.assertEqual(tuple(entry.id for entry in DEITY_DEFINITIONS),tuple(row[0] for row in expected))
        self.assertEqual(len(PRAYER_DEFINITIONS),30)
        self.assertEqual({entry.id for entry in PRAYER_DEFINITIONS},set(PrayerId))
        assigned=[]
        for deity,page,names in expected:
            with self.subTest(deity=deity):
                definition=deity_definition(deity)
                prayers=prayers_for_deity(deity)
                self.assertEqual(definition.page,page)
                self.assertEqual(tuple(prayer.name for prayer in prayers),names)
                self.assertEqual(tuple(prayer.id for prayer in prayers),definition.prayer_ids)
                self.assertTrue(all(prayer.deity is deity and prayer.page==page for prayer in prayers))
                self.assertTrue(all(prayer.book=='BOOK-PLAYER-GUIDE' and prayer.version=='1.4'
                    and prayer.chapter=='VII — Religion and Belief' for prayer in prayers))
                self.assertTrue(definition.strictures)
                self.assertTrue(definition.favoured_lores)
                self.assertTrue(definition.favour)
                self.assertTrue(definition.miracle_scope)
                assigned.extend(definition.prayer_ids)
        self.assertEqual(len(assigned),len(set(assigned)))

    def test_printed_exceptions_are_not_collapsed_into_a_battle_duration(self):
        self.assertIs(prayer_definition(PrayerId.PORTALS_THRESHOLD).duration,PrayerDuration.UNTIL_NEXT_DAWN)
        self.assertIs(prayer_definition(PrayerId.DROWNED_MANS_FACE).duration,
            PrayerDuration.END_OF_TARGET_NEXT_TURN)
        self.assertIs(prayer_definition(PrayerId.BLAZING_SUN).duration,
            PrayerDuration.END_OF_CASTER_NEXT_TURN)
        self.assertIs(prayer_definition(PrayerId.RANALDS_LUCK).timing,PrayerTiming.SESSION_START)
        self.assertIs(prayer_definition(PrayerId.RANALDS_LUCK).duration,PrayerDuration.SESSION)
        self.assertIs(prayer_definition(PrayerId.RHYAS_HARVEST).duration,PrayerDuration.CONDITIONAL)
        self.assertIn('consumed',prayer_definition(PrayerId.RHYAS_HARVEST).duration_detail)
        self.assertIn('everyone',prayer_definition(PrayerId.BLAZING_SUN).targets.lower())
        self.assertIn('no numeric Range',prayer_definition(PrayerId.LORD_OF_THE_WILD).targets)
        self.assertIn('no numeric Range',prayer_definition(PrayerId.TRUTH_WILL_OUT).targets)

    def test_special_prayer_and_favour_limits_remain_explicit(self):
        tears=prayer_definition(PrayerId.SHALLYAS_TEARS)
        self.assertIn('specific injury',tears.effect)
        self.assertIn('severed limb is not restored',tears.effect)
        self.assertIn('0:',tears.duration_detail)
        self.assertIn('3+:',tears.duration_detail)
        self.assertIn('opposed by Endurance',prayer_definition(PrayerId.DROWNED_MANS_FACE).effect)
        self.assertIn('first foe struck',prayer_definition(PrayerId.HAMMER_OF_SIGMAR).effect)
        self.assertIn('not restrict this to hostile',prayer_definition(PrayerId.HEED_NOT_THE_WITCH).effect)
        self.assertIn('Most Human attackers',deity_definition(DeityId.SHALLYA).favour)
        self.assertIn('no rounding rule printed',deity_definition(DeityId.RANALD).favour)
        self.assertIn('never harmful',deity_definition(DeityId.RHYA).miracle_scope)
        self.assertIn('cannot restore the dead',deity_definition(DeityId.SHALLYA).miracle_scope)

    def test_catalog_is_typed_immutable_and_pickle_safe(self):
        prayers=pickle.loads(pickle.dumps(PRAYER_DEFINITIONS))
        deities=pickle.loads(pickle.dumps(DEITY_DEFINITIONS))
        self.assertEqual(prayers,PRAYER_DEFINITIONS)
        self.assertEqual(deities,DEITY_DEFINITIONS)
        for id in ('taal',1,True):
            with self.subTest(id=id),self.assertRaises(TypeError):
                deity_definition(id)
        with self.assertRaises(TypeError):
            prayer_definition('martyr')
        with self.assertRaises(TypeError):
            replace(PRAYER_DEFINITIONS[0],dependencies=['untyped'])
        with self.assertRaises(ValueError):
            replace(PRAYER_DEFINITIONS[0],page=150)
        with self.assertRaises(FrozenInstanceError):
            PRAYER_DEFINITIONS[0].page=150


class FaithAccessTests(unittest.TestCase):
    def test_acquisitions_unlock_favour_three_prayers_and_individually_purchased_miracles(self):
        for purchases,favour,prayers,capacity in ((0,False,0,0),(1,True,0,0),
                (2,True,3,0),(3,True,3,1),(4,True,3,2),(7,True,3,5)):
            with self.subTest(purchases=purchases):
                source=faith_talents(purchases,deity=DeityId.MORR)
                access=faith_access(source)
                self.assertEqual(access.talents,source)
                self.assertEqual(access.has_favour,favour)
                self.assertEqual(len(access.prayers),prayers)
                self.assertEqual(access.miracle_capacity,capacity)
                self.assertEqual(access.available_miracles,capacity)
                self.assertIs(access.deity,DeityId.MORR if purchases else None)
                if prayers:
                    self.assertEqual(access.prayers,deity_definition(DeityId.MORR).prayer_ids)

    def test_prayers_and_favour_have_no_fake_global_uses_or_session_refresh(self):
        source=faith_talents(4)
        access=faith_access(source,2)
        self.assertTrue(access.has_favour)
        self.assertEqual(len(access.prayers),3)
        self.assertEqual(access.available_miracles,0)
        self.assertEqual(faith_access(access.talents,access.miracles_spent),access)
        self.assertEqual(access.miracle_capacity,2)
        self.assertFalse(hasattr(access,'fate'))

    def test_spent_miracles_reject_impossible_negative_bool_and_excess_counts(self):
        for count in (0,1,2):
            with self.subTest(count=count),self.assertRaises(ValueError):
                faith_access(faith_talents(count),1)
        for bad in (-1,True,1.0,'1',None):
            with self.subTest(bad=bad),self.assertRaises((TypeError,ValueError)):
                faith_access(faith_talents(3),bad)
        with self.assertRaises(ValueError):
            faith_access(faith_talents(3),2)

    def test_incomplete_and_conflicting_acquisition_sources_are_not_repaired(self):
        source=faith_talents(1)
        for malformed in ([source[0]],source*2,('faith',)):
            with self.subTest(malformed=malformed),self.assertRaises((TypeError,ValueError)):
                faith_access(malformed)
        forged=deepcopy(source)
        object.__setattr__(forged[0].acquisitions[0],'devotion_confirmed',False)
        with self.assertRaises(ValueError):
            faith_access(forged)
        with self.assertRaises(ValueError):
            faith_access((*source,free_talent(TalentId.WIZARD)))
        touched=AcquiredTalent(TalentId.TOUCHED_BY_THE_WINDS,
            (TalentAcquisition(P.CREATION,F.FREE,MagicLoreChoice('elementalism')),))
        with self.assertRaises(ValueError):
            faith_access((*source,touched))
        with self.assertRaises(TypeError):
            AcquiredTalent(TalentId.FAITH,(TalentAcquisition(P.CREATION,F.FREE),))

    def test_access_and_ledger_retain_pickle_and_actual_acquisition_sources(self):
        access=faith_access(faith_talents(5,deity=DeityId.MYRMIDIA),1)
        ledger=FaithMiracleLedger('pc:priest',access)
        restored=pickle.loads(pickle.dumps(ledger))
        self.assertEqual(restored,ledger)
        self.assertEqual(restored.access.available_miracles,2)
        self.assertEqual(restored.access.deity,DeityId.MYRMIDIA)
        self.assertEqual(restored.initial_access.talents,access.talents)


class MiracleExpenditureTests(unittest.TestCase):
    def spend(self,ledger,*,id='use:1',battle='battle:1',action='action:1',scope='gm:aid',confirmed=True):
        return use_faith_miracle(ledger,use_id=id,battle_id=battle,action_id=action,
            scope_id=scope,gm_scope_confirmed=confirmed)

    def test_expenditure_is_finite_actor_bound_and_does_not_mutate_or_refill_source(self):
        access=faith_access(faith_talents(3))
        before=FaithMiracleLedger('pc:priest',access)
        after=self.spend(before)
        self.assertEqual(len(before.uses),0)
        self.assertEqual(before.access.available_miracles,1)
        self.assertEqual(after.access.available_miracles,0)
        self.assertEqual(after.access.miracles_spent,1)
        self.assertEqual(after.access.talents,access.talents)
        use,=after.uses
        self.assertEqual((use.actor_id,use.battle_id,use.action_id,use.use_id,use.scope_id),
            ('pc:priest','battle:1','action:1','use:1','gm:aid'))
        self.assertEqual(use.source,access)
        self.assertEqual(use.result_access,after.access)
        with self.assertRaises(ValueError):
            self.spend(after,id='use:2',battle='next:battle',action='next:action')

    def test_two_purchased_miracles_span_battles_without_a_session_reset(self):
        ledger=FaithMiracleLedger('npc:priest',faith_access(faith_talents(4)))
        ledger=self.spend(ledger)
        ledger=self.spend(ledger,id='use:2',battle='battle:2',action='action:2')
        self.assertEqual(ledger.access.miracles_spent,2)
        self.assertEqual(ledger.access.available_miracles,0)
        self.assertFalse(hasattr(ledger,'fate'))
        with self.assertRaises(ValueError):
            self.spend(ledger,id='use:3',battle='battle:3',action='action:3')

    def test_duplicate_ids_aliases_foreign_actor_and_changed_resource_source_are_rejected(self):
        ledger=FaithMiracleLedger('pc:priest',faith_access(faith_talents(5)))
        after=self.spend(ledger)
        with self.assertRaises(ValueError):
            self.spend(after,id='use:1',action='different:action')
        with self.assertRaises(ValueError):
            self.spend(after,id='aliased:use')
        receipt,=after.uses
        with self.assertRaises(ValueError):
            replace(after,uses=(replace(receipt,actor_id='foreign:actor'),))
        foreign_access=faith_access(faith_talents(5,deity=DeityId.TAAL))
        with self.assertRaises(ValueError):
            replace(after,uses=(replace(receipt,source=foreign_access),))
        with self.assertRaises(ValueError):
            replace(after,uses=(receipt,replace(receipt,use_id='aliased:receipt')))

    def test_particular_gm_scope_and_exact_identifiers_are_required(self):
        ledger=FaithMiracleLedger('pc:priest',faith_access(faith_talents(3)))
        for confirmed in (False,True,1,None):
            with self.subTest(confirmed=confirmed):
                if confirmed is True:
                    self.assertEqual(self.spend(ledger,confirmed=confirmed).access.available_miracles,0)
                else:
                    with self.assertRaises((TypeError,ValueError)):
                        self.spend(ledger,confirmed=confirmed)
        for key in ('id','battle','action','scope'):
            for bad in ('',True):
                with self.subTest(key=key,bad=bad),self.assertRaises(TypeError):
                    self.spend(ledger,**{key:bad})

    def test_forged_cached_access_and_expenditure_ledgers_cannot_create_extra_charges(self):
        ledger=FaithMiracleLedger('pc:priest',faith_access(faith_talents(3)))
        spent=self.spend(ledger)
        forged=deepcopy(spent)
        object.__setattr__(forged.access,'available_miracles',100)
        with self.assertRaises(ValueError):
            self.spend(forged,id='forged:use',action='forged:action')
        access=deepcopy(spent.access)
        object.__setattr__(access,'available_miracles',100)
        with self.assertRaises(ValueError):
            MiracleUse('fake','pc:priest','battle:2','action:2','gm:aid',True,access)
        self.assertEqual(pickle.loads(pickle.dumps(spent)),spent)
        with self.assertRaises(TypeError):
            replace(spent,uses=list(spent.uses))


if __name__=='__main__':
    unittest.main()
