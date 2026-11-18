"""Indexed identity admission preserves source claims and fresh canonical guards."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest
from unittest.mock import patch

from towr.domain import pc_npc_catalog as catalog
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon


def generated_definition():
    return GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),light_loadout(light=False, shield=False),defence=4).participant('generated').definition


class CatalogIdentityIndexTests(unittest.TestCase):
    def test_all_book_profiles_still_admit_their_complete_fresh_definition(self):
        self.assertEqual(len(catalog.PcBookNpcProfile),59)
        for profile in catalog.PcBookNpcProfile:
            with self.subTest(profile=profile):
                definition=catalog.get_pc_book_npc_entry(profile).definition
                catalog.validate_pc_book_npc_definition(definition)

    def test_generated_identity_does_not_scan_or_build_the_book_catalog(self):
        class NoScan(tuple):
            def __iter__(self):
                raise AssertionError('ordinary generated admission scanned the book catalog')
        definition=generated_definition()
        with patch.object(catalog,'_CATALOG_IDENTITIES',NoScan(catalog._CATALOG_IDENTITIES)),\
                patch.object(catalog,'_definition',side_effect=AssertionError('unexpected canonical graph')):
            catalog.validate_pc_book_npc_definition(definition)

    def test_each_identity_or_nested_source_claim_is_reserved_despite_authored_root(self):
        definition=generated_definition()
        canonical=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.FOOTPAD).definition
        claims=[]
        for location,value in (('id',canonical.id),('source_rule_id',canonical.source_rule_id),
                ('attack',canonical.attacks[0].source_rule_id),('protection',canonical.protection[0].source_rule_id)):
            claimed=deepcopy(definition)
            node=claimed.attacks[0] if location=='attack' else claimed.protection[0] if location=='protection' else claimed
            object.__setattr__(node,'source_rule_id' if location in ('attack','protection') else location,value)
            claims.append(claimed)
        for claimed in claims:
            with self.subTest(claimed=claimed),self.assertRaises((TypeError,ValueError)):
                catalog.validate_pc_book_npc_definition(claimed)
        unknown=deepcopy(definition)
        object.__setattr__(unknown,'id','pc-book-npc:unknown-index-entry')
        with self.assertRaises(ValueError):
            catalog.validate_pc_book_npc_definition(unknown)

    def test_conflicting_claims_keep_catalog_order_not_root_or_source_order(self):
        first=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL).definition
        later=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.FOOTPAD).definition
        claims=(replace(later,protection=(replace(later.protection[0],
                    source_rule_id=first.protection[0].source_rule_id),)),
            replace(later,id='authored:conflict',attacks=(replace(later.attacks[0],
                    source_rule_id=first.attacks[0].source_rule_id),)))
        original=catalog._definition
        for claimed in claims:
            with self.subTest(claimed=claimed),patch.object(catalog,'_definition',wraps=original) as build:
                with self.assertRaises((TypeError,ValueError)):
                    catalog.validate_pc_book_npc_definition(claimed)
                build.assert_called_once_with(catalog.PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL)

    def test_string_enum_and_subclass_claims_cannot_bypass_exact_nested_types(self):
        canonical=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.FOOTPAD).definition
        class Text(str):
            pass
        for target,value in (('id',canonical.id),('source_rule_id',canonical.source_rule_id),
                ('attack',canonical.attacks[0].source_rule_id),('protection',canonical.protection[0].source_rule_id)):
            alias=Enum('Alias',{'VALUE':value},type=str).VALUE
            for text in (Text(value),alias):
                claimed=deepcopy(canonical)
                node=(claimed.attacks[0] if target=='attack' else claimed.protection[0] if target=='protection' else claimed)
                object.__setattr__(node,'source_rule_id' if target in ('attack','protection') else target,text)
                with self.subTest(target=target,text_type=type(text)),self.assertRaises(TypeError):
                    catalog.validate_pc_book_npc_definition(claimed)
        claimed=deepcopy(canonical)
        object.__setattr__(claimed,'wound_limit',True)
        with self.assertRaises(TypeError):
            catalog.validate_pc_book_npc_definition(claimed)

    def test_custom_unhashable_string_equality_retains_the_original_claim_guard(self):
        canonical=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL).definition
        class Claim(str):
            def __eq__(self,other):
                return other==canonical.source_rule_id
            __hash__=None
        claimed=generated_definition()
        object.__setattr__(claimed,'source_rule_id',Claim('authored:disguised'))
        with self.assertRaises((TypeError,ValueError)):
            catalog.validate_pc_book_npc_definition(claimed)

    def test_repeated_book_admission_builds_distinct_canonical_graphs(self):
        definition=catalog.get_pc_book_npc_entry(catalog.PcBookNpcProfile.FOOTPAD).definition
        original=catalog._definition
        graphs=[]
        def build(profile):
            graph=original(profile)
            graphs.append(graph)
            return graph
        with patch.object(catalog,'_definition',side_effect=build):
            catalog.validate_pc_book_npc_definition(definition)
            catalog.validate_pc_book_npc_definition(definition)
        self.assertEqual(graphs[0],graphs[1])
        self.assertIsNot(graphs[0],graphs[1])
        self.assertIsNot(graphs[0].attacks[0],graphs[1].attacks[0])


if __name__=='__main__':
    unittest.main()
