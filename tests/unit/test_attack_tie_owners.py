"""Canonical owners and reaction predicates consume actual K1 tie receipts.

These explicit low-level preferences do not claim a Musician action source;
the public Talent consumer remains closed pending its full runtime owner.
"""
from dataclasses import replace
from unittest import TestCase, main

from tests.helpers import SequenceRandom
from tests.unit.test_attack_talent_ties import attack_request, preferred
from towr.domain.attack_models import defender_won_attack_opposition
from towr.domain._pc_melee_projection import _canonical_attack
from towr.domain.npc_champion_attack_models import _actual_attack
from towr.rules.attack_resolution import resolve_attack


class AttackTieOwnerTests(TestCase):
    def test_both_canonical_owners_accept_real_defender_and_ordinary_positive_ties(self):
        for source in (None,preferred()):
            request=attack_request(source=source)
            result=resolve_attack(request,SequenceRandom([1,10,2,10]))
            with self.subTest(source=source):
                _canonical_attack(request,result)
                _actual_attack(request,result)
                for forged in (replace(result,tie_break_applied=False),replace(result,applied_rule_ids=())):
                    for owner in (_canonical_attack,_actual_attack):
                        with self.assertRaises(ValueError): owner(request,forged)

    def test_defensive_reactions_require_real_positive_victory_and_actual_tie_source(self):
        request=attack_request(source=preferred())
        result=resolve_attack(request,SequenceRandom([1,10,2,10]))
        self.assertTrue(defender_won_attack_opposition(request,result))
        self.assertFalse(defender_won_attack_opposition(replace(request,tie_break=None),result))
        self.assertFalse(defender_won_attack_opposition(request,replace(result,applied_rule_ids=())))
        ordinary=attack_request()
        defeated=resolve_attack(ordinary,SequenceRandom([10,10,1,10]))
        self.assertTrue(defender_won_attack_opposition(ordinary,defeated))

    def test_double_zero_unopposed_and_immunity_are_not_defensive_victories(self):
        request=attack_request(source=preferred())
        zero=resolve_attack(request,SequenceRandom([10]*4))
        self.assertFalse(defender_won_attack_opposition(request,zero))
        _canonical_attack(request,zero)
        _actual_attack(request,zero)
        unopposed=attack_request(source=preferred(),opposed=False)
        result=resolve_attack(unopposed,SequenceRandom([1,10]))
        self.assertFalse(defender_won_attack_opposition(unopposed,result))
        _canonical_attack(unopposed,result)
        immune=attack_request(source=preferred(),immunity='source:miss-stagger-immunity')
        missed=resolve_attack(immune,SequenceRandom([10]*4))
        self.assertFalse(defender_won_attack_opposition(immune,missed))
        _canonical_attack(immune,missed)
        _actual_attack(immune,missed)

    def test_defensive_receipt_cannot_use_a_different_attack_or_test_source(self):
        request=attack_request(source=preferred())
        result=resolve_attack(request,SequenceRandom([1,10,2,10]))
        for forged in (replace(request,id='other'),
                replace(request,defender_test=replace(request.defender_test,id='another-test'))):
            with self.assertRaises(ValueError): defender_won_attack_opposition(forged,result)


if __name__=='__main__': main()
