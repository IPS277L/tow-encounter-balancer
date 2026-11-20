"""Actual Fellowship/Leadership sources without enabling Musician execution."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.talent_sources import free_talent, paid_talent
from towr.adapters._pc_melee_scenario_json import (
    generated_components_document, parse_generated_components, scenario_document,
)
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.application.encounter_character import EncounterCharacter
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
from towr.domain.talent_actor_models import talent_facts_for_actor
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.test_models import TestProfile


def player():
    return make_pc_melee_scenario().party[0]


def creature(**changes):
    return replace(GeneratedNpc(3, 3, 3, 3, 4, 4,
        initial_generated_weapons(GeneratedWeapon.SWORD), ArmourLoadout(), defence=4), **changes)


def character(**changes):
    return replace(EncounterCharacter('pc', 3, 3, 3, 3, 5, 5, 4, 4,
        PcMeleeWeapon.SWORD, ArmourLoadout(), False, PcWeaponHand.RIGHT, (), 3), **changes)


def dynamic_document():
    raw = json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    raw['party'] = raw['party'][:1]
    return raw


def native_document(scenario):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='ratings:wire',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(scenario),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


class MusicianRatingSourceTests(unittest.TestCase):
    def test_existing_sources_keep_optional_none_without_a_fabricated_test(self):
        for source in (player().pc, creature()):
            with self.subTest(source=type(source).__name__):
                self.assertIsNone(source.fellowship)
                self.assertIsNone(source.leadership)
                with self.assertRaisesRegex(ValueError, 'explicit Fellowship and Leadership'):
                    source.leadership_profile
        original = character()
        self.assertIsNone(original.fellowship)
        self.assertIsNone(original.participant('session', NpcDefeatDisposition.KILLED).pc.leadership)

    def test_actual_profiles_use_fellowship_dice_and_leadership_threshold(self):
        for fellowship, leadership in ((1, 1), (4, 5), (15, 10)):
            with self.subTest(fellowship=fellowship, leadership=leadership):
                pc = replace(player().pc, fellowship=fellowship, leadership=leadership)
                self.assertEqual(pc.leadership_profile, TestProfile(fellowship, leadership))
                self.assertEqual(pc.leadership_profile.base_dice, fellowship)
                self.assertEqual(pc.leadership_profile.maximum_dice, 2 * fellowship)
                self.assertEqual(pc.leadership_profile.threshold, leadership)
        for fellowship, leadership in ((1, 2), (4, 4), (15, 6)):
            with self.subTest(fellowship=fellowship, leadership=leadership):
                npc = creature(fellowship=fellowship, leadership=leadership)
                self.assertEqual(npc.leadership_profile, TestProfile(fellowship, leadership))
                self.assertEqual(npc.talents, ())

    def test_ratings_reject_bool_float_zero_and_unpaired_leadership(self):
        for source in (player().pc, creature()):
            for name in ('fellowship', 'leadership'):
                for value in (True, False, 0, -1, 4.0, '4'):
                    with self.subTest(source=type(source).__name__, name=name, value=value):
                        with self.assertRaises((TypeError, ValueError)):
                            changes = {'fellowship': 4, name: value}
                            replace(source, **changes)
            with self.assertRaisesRegex(ValueError, 'explicit Fellowship and Leadership'):
                replace(source, leadership=4)
            fellowship_only = replace(source, fellowship=4)
            with self.assertRaises(ValueError):
                fellowship_only.leadership_profile
        for leadership in (1, 7, 10):
            with self.subTest(npc_leadership=leadership), self.assertRaises(ValueError):
                creature(fellowship=4, leadership=leadership)
        with self.assertRaises(ValueError):
            replace(player().pc, fellowship=4, leadership=11)

    def test_actual_fellowship_binds_prerequisite_facts_for_both_sources(self):
        member = replace(player(), pc=replace(player().pc, fellowship=4, leadership=5))
        npc = creature(fellowship=4, leadership=5)
        for source in (member, npc):
            with self.subTest(source=type(source).__name__):
                matching = replace(source, talent_facts=TalentOwnerFacts(fellowship=4))
                self.assertEqual(matching.talent_facts.fellowship, 4)
                for talents in ((), (free_talent(TalentId.ALLIES_IN_ARMS),)):
                    with self.assertRaisesRegex(ValueError, 'initial fellowship'):
                        replace(source, talent_facts=TalentOwnerFacts(fellowship=5), talents=talents)
                paid = replace(source, talents=(paid_talent(TalentId.ALLIES_IN_ARMS),))
                self.assertEqual(paid.talents, (paid_talent(TalentId.ALLIES_IN_ARMS),))
                self.assertIsNone(paid.talent_facts)

    def test_acquisition_only_fellowship_does_not_become_an_actual_rating(self):
        facts = TalentOwnerFacts(fellowship=4)
        for source in (player(), creature()):
            with self.subTest(source=type(source).__name__):
                admitted = replace(source, talent_facts=facts,
                    talents=(paid_talent(TalentId.ALLIES_IN_ARMS),))
                current = admitted.pc if hasattr(admitted, 'pc') else admitted
                self.assertIsNone(current.fellowship)
                self.assertIsNone(current.leadership)
                self.assertIs(admitted.talent_facts, facts)
                with self.assertRaises(ValueError):
                    current.leadership_profile
                with self.assertRaises(ValueError):
                    replace(current, leadership=4)
        derived = talent_facts_for_actor(facts, weapon_skill=3, strength=3, toughness=3,
            agility=3, fellowship=None)
        self.assertEqual(derived.fellowship, 4)
        self.assertIsNone(facts.weapon_skill)

    def test_paid_allies_uses_actual_fellowship_and_free_acquisition_preserves_it(self):
        member = replace(player(), pc=replace(player().pc, fellowship=3))
        npc = creature(fellowship=3)
        for source in (member, npc):
            with self.subTest(source=type(source).__name__):
                with self.assertRaises(ValueError):
                    replace(source, talents=(paid_talent(TalentId.ALLIES_IN_ARMS),))
                admitted = replace(source, talents=(free_talent(TalentId.ALLIES_IN_ARMS),))
                current = admitted.pc if hasattr(admitted, 'pc') else admitted
                self.assertEqual(current.fellowship, 3)
                self.assertIsNone(current.leadership)

    def test_character_compilation_preserves_actual_ratings_without_rewriting_facts(self):
        facts = TalentOwnerFacts(fellowship=5)
        original = character(fellowship=5, leadership=6, talent_facts=facts)
        compiled = original.participant('ratings', NpcDefeatDisposition.KILLED)
        self.assertEqual(compiled.pc.leadership_profile, TestProfile(5, 6))
        self.assertIs(compiled.talent_facts, facts)
        self.assertEqual(compiled.talents, ())
        for changes in (dict(fellowship=True), dict(fellowship=None),
                dict(leadership=True), dict(leadership=11),
                dict(talent_facts=TalentOwnerFacts(fellowship=4))):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(original, **changes)

    def test_cached_actual_ratings_are_readmitted_by_character_and_source_models(self):
        for original in (player().pc, creature(), character()):
            corrupt = deepcopy(original)
            object.__setattr__(corrupt, 'fellowship', True)
            with self.subTest(source=type(corrupt).__name__), self.assertRaises((TypeError, ValueError)):
                replace(corrupt)
        corrupt = character(fellowship=4, leadership=4)
        object.__setattr__(corrupt, 'leadership', True)
        with self.assertRaises((TypeError, ValueError)):
            corrupt.participant('again', NpcDefeatDisposition.KILLED)
        corrupt_npc = creature(fellowship=4, leadership=4)
        object.__setattr__(corrupt_npc, 'leadership', 7)
        with self.assertRaises(ValueError):
            corrupt_npc.leadership_profile

    def test_dynamic_json_preserves_actual_ratings_and_exact_source_echo(self):
        raw = dynamic_document()
        raw['party'][0]['characteristics']['fellowship'] = 5
        raw['party'][0]['skills']['leadership'] = 6
        before = deepcopy(raw)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        member = command.request.party[0]
        self.assertEqual(member.pc.leadership_profile, TestProfile(5, 6))
        self.assertEqual(member.talent_facts.fellowship, 5)
        self.assertEqual(member.talents, ())
        self.assertEqual(json.loads(command.source_json), before)
        self.assertEqual(raw, before)
        replay = parse_dynamic_encounter_request(command.source_json)
        self.assertEqual(replay.request, command.request)

    def test_dynamic_none_and_acquisition_only_fellowship_do_not_supply_a_test(self):
        for present_nulls in (False, True):
            raw = dynamic_document()
            raw['party'][0]['talent_facts'] = {'fellowship': 4}
            if present_nulls:
                raw['party'][0]['characteristics']['fellowship'] = None
                raw['party'][0]['skills']['leadership'] = None
            command = parse_dynamic_encounter_request(json.dumps(raw))
            member = command.request.party[0]
            with self.subTest(present_nulls=present_nulls):
                self.assertIsNone(member.pc.fellowship)
                self.assertIsNone(member.pc.leadership)
                self.assertEqual(member.talent_facts.fellowship, 4)
                self.assertEqual(json.loads(command.source_json), raw)
                with self.assertRaises(ValueError):
                    member.pc.leadership_profile

    def test_dynamic_json_rejects_missing_actual_fellowship_and_conflicting_facts(self):
        for fellowship in (None, True, 0, 4.0, '4'):
            raw = dynamic_document()
            raw['party'][0]['characteristics']['fellowship'] = fellowship
            raw['party'][0]['skills']['leadership'] = 4
            raw['party'][0]['talent_facts'] = {'fellowship': 4}
            with self.subTest(fellowship=fellowship), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw = dynamic_document()
        raw['party'][0]['skills']['leadership'] = 4
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))
        raw['party'][0]['characteristics']['fellowship'] = 5
        raw['party'][0]['talent_facts'] = {'fellowship': 4}
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_native_pc_json1_roundtrip_preserves_actual_ratings_and_optional_none(self):
        source = make_pc_melee_scenario()
        member = replace(source.party[0], pc=replace(source.party[0].pc,
            fellowship=5, leadership=6), talent_facts=TalentOwnerFacts(fellowship=5))
        source = replace(source, party=(member,))
        raw = native_document(source)
        self.assertEqual(raw['schema_version'], '1')
        self.assertEqual(raw['scenario']['party'][0]['pc']['fellowship'], 5)
        self.assertEqual(raw['scenario']['party'][0]['pc']['leadership'], 6)
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario, source)
        original = make_pc_melee_scenario()
        nulls = native_document(original)
        nulls['scenario']['party'][0]['pc'].update(fellowship=None, leadership=None)
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(nulls)).request.scenario, original)
        self.assertNotIn('fellowship', scenario_document(original)['party'][0]['pc'])

    def test_native_pc_json_rejects_bool_unpaired_and_conflicting_rating_sources(self):
        for changes in (dict(fellowship=None, leadership=4), dict(leadership=4),
                dict(fellowship=True), dict(fellowship=4, leadership=True),
                dict(fellowship=4, leadership=11)):
            raw = native_document(make_pc_melee_scenario())
            raw['scenario']['party'][0]['pc'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(PcMeleeSimulationInputError):
                parse_pc_melee_simulation_request(json.dumps(raw))
        raw = native_document(make_pc_melee_scenario())
        raw['scenario']['party'][0]['pc'].update(fellowship=5, leadership=4)
        raw['scenario']['party'][0]['talent_facts'] = {'fellowship': 4}
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))

    def test_generated_document_and_character_file_preserve_both_ratings_and_none(self):
        for original in (creature(), creature(fellowship=15), creature(fellowship=5, leadership=6)):
            raw = generated_components_document(original)
            with self.subTest(fellowship=original.fellowship, leadership=original.leadership):
                self.assertEqual(raw['fellowship'], original.fellowship)
                self.assertEqual(raw['leadership'], original.leadership)
                self.assertEqual(parse_generated_components(raw, path_prefix='/npc',
                    error_type=DynamicEncounterInputError), original)
                self.assertEqual(parse_character_file(json.dumps(raw), 'npc'), raw)
        omitted = generated_components_document(creature())
        del omitted['fellowship'], omitted['leadership']
        self.assertEqual(parse_character_file(json.dumps(omitted), 'npc'), omitted)
        self.assertEqual(parse_generated_components(omitted, path_prefix='/npc',
            error_type=DynamicEncounterInputError), creature())

    def test_generated_json1_source_roundtrip_retains_both_actual_ratings(self):
        command = parse_dynamic_encounter_request(json.dumps(dynamic_document()))
        npc = creature(fellowship=5, leadership=6, talent_facts=TalentOwnerFacts(fellowship=5))
        source = command.request.scenario((npc,), 'ratings:generated')
        raw = native_document(source)
        restored = parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
        self.assertEqual(restored, source)
        components = restored.enemies[0].definition.generated_components
        self.assertEqual(components.leadership_profile, TestProfile(5, 6))
        self.assertEqual(components.talent_facts.fellowship, 5)

    def test_player_character_file_roundtrip_preserves_nullable_actual_ratings(self):
        for fellowship, leadership in ((5, 6), (15, None), (None, None)):
            raw = dynamic_document()['party'][0]
            raw['characteristics']['fellowship'] = fellowship
            raw['skills']['leadership'] = leadership
            with self.subTest(fellowship=fellowship, leadership=leadership):
                self.assertEqual(parse_character_file(json.dumps(raw), 'player'), raw)
        raw['talent_facts'] = {'fellowship': 4}
        self.assertEqual(parse_character_file(json.dumps(raw), 'player'), raw)
        raw['characteristics']['fellowship'] = 5
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(raw), 'player')

    def test_character_files_reject_unpaired_bool_and_out_of_bounds_leadership(self):
        for kind in ('player', 'npc'):
            for fellowship, leadership in ((None, 4), (True, None), (4, True),
                    (0, None), (4, 0), (4, 11), (4, 4.0)):
                raw = (dynamic_document()['party'][0] if kind == 'player'
                    else generated_components_document(creature()))
                if kind == 'player':
                    raw['characteristics']['fellowship'] = fellowship
                    raw['skills']['leadership'] = leadership
                else:
                    raw.update(fellowship=fellowship, leadership=leadership)
                with self.subTest(kind=kind, fellowship=fellowship, leadership=leadership):
                    with self.assertRaises(DynamicEncounterInputError):
                        parse_character_file(json.dumps(raw), kind)
        raw = generated_components_document(creature(fellowship=4))
        for leadership in (1, 7):
            raw['leadership'] = leadership
            with self.subTest(npc_leadership=leadership), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(raw), 'npc')


if __name__ == '__main__':
    unittest.main()
