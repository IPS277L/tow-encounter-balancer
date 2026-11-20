"""A Character's Wounds and death never become profile NPC HP."""
from dataclasses import replace
from unittest import TestCase

from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,ProfileInjuryState,WoundRecord,WoundEntryId,
    injury_is_defeated,injury_wound_count,
)


class InjuryQueryTests(TestCase):
    def test_character_conditions_do_not_invent_defeat_or_a_profile_wound_limit(self):
        injury=CharacterInjuryState(conditions=ConditionState(frozenset((Condition.DEFENCELESS,))))
        self.assertFalse(injury_is_defeated(injury))
        self.assertTrue(injury_is_defeated(replace(injury,dead=True)))
        self.assertFalse(hasattr(injury,'wound_limit'))

    def test_character_count_uses_actual_unhealed_records_and_preserves_treated_wounds(self):
        first=WoundRecord(1,WoundEntryId.SUPERFICIAL_INJURY,1,(1,),treated=True,effect_resolved=True)
        second=replace(first,sequence=2,healed=True)
        injury=CharacterInjuryState(wounds=(first,second))
        self.assertEqual(injury_wound_count(injury),1)
        self.assertEqual(injury.wounds,(first,second))

    def test_profile_npc_keeps_its_actual_defeat_and_numeric_wounds(self):
        injury=ProfileInjuryState(1,3)
        self.assertEqual(injury_wound_count(injury),1)
        self.assertFalse(injury_is_defeated(injury))
        self.assertTrue(injury_is_defeated(ProfileInjuryState(3,3,defeated=True)))

    def test_query_does_not_accept_a_bare_hp_number_or_a_fake_snapshot(self):
        for value in (1,None,object()):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(TypeError): injury_is_defeated(value)
                with self.assertRaises(TypeError): injury_wound_count(value)
