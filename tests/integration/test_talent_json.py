"""Common acquisition wire facts only; these tests do not enable battle Talents."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from towr.adapters._talent_json import (
    acquired_talents_document, parse_acquired_talents, parse_talent_owner_facts,
    talent_owner_facts_document,
)
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError as InputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.talent_catalog import (
    FamiliarEffect, TalentEquipmentRequirement, TalentId, TalentOrigin, TalentStatusTier,
)
from towr.domain.talent_models import (
    AcquiredTalent, BloodlineChoice, DeityChoice, DeityId, FamiliarEffectChoice,
    HatredGroupChoice, MagicLoreChoice, OathChoice, TalentAcquisition,
    TalentAcquisitionPhase as Phase, TalentFunding as Funding, TalentLoreFact, TalentOwnerFacts,
)


def parse(raw):
    return parse_acquired_talents(raw, path='/party/0/talents', error_type=InputError)


def parse_facts(raw):
    return parse_talent_owner_facts(raw, path='/party/0/talent_facts', error_type=InputError)


def source(id=TalentId.LUCKY):
    choices = {
        TalentId.FAITH: DeityChoice(DeityId.SIGMAR),
        TalentId.FAMILIAR: FamiliarEffectChoice(FamiliarEffect.BOOKREST),
        TalentId.HATRED: HatredGroupChoice('group:beastmen'),
        TalentId.HONOUR_BOUND: OathChoice('oath:protect-the-village'),
        TalentId.SECRET_BLOODLINE: BloodlineChoice('bloodline:example'),
        TalentId.TOUCHED_BY_THE_WINDS: MagicLoreChoice('elementalism'),
    }
    return AcquiredTalent(id, (TalentAcquisition(Phase.CREATION, Funding.FREE, choices.get(id)),))


def wire(id=TalentId.LUCKY):
    return acquired_talents_document((source(id),))


class TalentJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(Path('src/towr/adapters/schemas/talent-common.schema.json').read_text('utf-8'))
        Draft202012Validator.check_schema(cls.schema)
        registry = Registry().with_resource(cls.schema['$id'], Resource.from_contents(cls.schema))
        cls.talent_validator = Draft202012Validator(
            {'$ref': cls.schema['$id'] + '#/$defs/acquired_talents'}, registry=registry)
        cls.facts_validator = Draft202012Validator(
            {'$ref': cls.schema['$id'] + '#/$defs/owner_facts'}, registry=registry)

    def test_all_59_individual_sources_roundtrip_without_claiming_one_joint_owner(self):
        self.assertEqual(len(TalentId), 59)
        for id in TalentId:
            with self.subTest(id=id):
                original = (source(id),)
                document = acquired_talents_document(original)
                before = deepcopy(document)
                self.talent_validator.validate(document)
                self.assertEqual(parse(json.loads(json.dumps(document))), original)
                self.assertEqual(acquired_talents_document(parse(document)), document)
                self.assertEqual(document, before)
                self.assertEqual(set(document[0]), {'id', 'acquisitions'})
                self.assertEqual(set(document[0]['acquisitions'][0]),
                    {'phase', 'funding', 'choice', 'devotion_confirmed'})

    def test_faith_familiar_and_wizard_preserve_distinct_progression_facts(self):
        faith = replace(source(TalentId.FAITH), acquisitions=(
            source(TalentId.FAITH).acquisitions[0],
            *(TalentAcquisition(Phase.ADVANCEMENT, Funding.XP, devotion_confirmed=True)
                for _ in range(4))))
        familiar = replace(source(TalentId.FAMILIAR), acquisitions=(
            source(TalentId.FAMILIAR).acquisitions[0],
            *(TalentAcquisition(Phase.ADVANCEMENT, Funding.XP, FamiliarEffectChoice(effect))
                for effect in FamiliarEffect if effect is not FamiliarEffect.BOOKREST)))
        wizard = replace(source(TalentId.WIZARD), acquisitions=(
            source(TalentId.WIZARD).acquisitions[0],
            *(TalentAcquisition(Phase.ADVANCEMENT, Funding.XP) for _ in range(3))))
        for original in (faith, familiar, wizard):
            with self.subTest(id=original.id):
                document = acquired_talents_document((original,))
                self.talent_validator.validate(document)
                self.assertEqual(parse(document), (original,))
        document = acquired_talents_document((faith,))
        self.assertEqual(document[0]['acquisitions'][0]['choice'], {'deity': 'sigmar'})
        self.assertIsNone(document[0]['acquisitions'][1]['choice'])

    def test_owner_facts_roundtrip_every_field_without_derived_defaults(self):
        facts = TalentOwnerFacts(3, 4, 5, 6, 7, 8, 9, 10, TalentOrigin.HIGH_ELF,
            (TalentLoreFact('anatomy'), TalentLoreFact('elementalism', True)),
            TalentStatusTier.GOLD, tuple(TalentEquipmentRequirement), True, True)
        document = talent_owner_facts_document(facts)
        self.facts_validator.validate(document)
        self.assertEqual(parse_facts(json.loads(json.dumps(document))), facts)
        self.assertEqual(document['lores'],
            [{'id': 'anatomy', 'magic': False}, {'id': 'elementalism', 'magic': True}])
        self.assertEqual(set(document), {'weapon_skill', 'ballistic_skill', 'strength',
            'toughness', 'initiative', 'agility', 'reason', 'fellowship', 'origin', 'lores',
            'status', 'equipment', 'grail_quest_completed', 'can_cast_spells'})
        empty = parse_facts({})
        self.assertEqual(empty, TalentOwnerFacts())
        complete = talent_owner_facts_document(empty)
        self.assertIsNone(complete['origin'])
        self.assertIsNone(complete['strength'])
        self.assertEqual(complete['lores'], [])
        self.assertFalse(complete['can_cast_spells'])
        self.assertEqual(parse_facts(complete), empty)

    def test_owner_origin_status_and_equipment_enums_match_the_current_schema(self):
        for origin in TalentOrigin:
            with self.subTest(origin=origin):
                facts = TalentOwnerFacts(origin=origin)
                document = talent_owner_facts_document(facts)
                self.facts_validator.validate(document)
                self.assertEqual(parse_facts(document), facts)
        for status in TalentStatusTier:
            with self.subTest(status=status):
                facts = TalentOwnerFacts(status=status,
                    equipment=tuple(TalentEquipmentRequirement))
                document = talent_owner_facts_document(facts)
                self.facts_validator.validate(document)
                self.assertEqual(parse_facts(document), facts)

    def test_old_tags_aliases_unknown_ids_and_extra_fields_are_rejected(self):
        invalid = (['lucky'], [{'talent': 'lucky', 'acquisition': 'earned'}],
            [dict(wire()[0], id='Lucky')], [dict(wire()[0], id=True)],
            [dict(wire()[0], id='invented')], [dict(wire()[0], rank=1)],
            [dict(wire()[0], acquisitions=[])])
        for document in invalid:
            with self.subTest(document=document), self.assertRaises(InputError) as raised:
                parse(document)
            self.assertIs(raised.exception.code, Code.INVALID_INPUT)
            self.assertTrue(raised.exception.path.startswith('/party/0/talents'))
            with self.assertRaises(ValidationError):
                self.talent_validator.validate(document)
        document = wire()
        document[0]['acquisitions'][0]['phase'] = 'creation_free'
        with self.assertRaises(InputError) as raised:
            parse(document)
        self.assertEqual(raised.exception.path, '/party/0/talents/0/acquisitions/0/phase')

    def test_choice_kind_comes_from_talent_and_requires_its_exact_closed_payload(self):
        for id, payload in ((TalentId.HATRED, {'deity': 'morr'}),
                (TalentId.FAITH, {'deity': 'unknown'}),
                (TalentId.FAMILIAR, {'effect': True}),
                (TalentId.HONOUR_BOUND, {'oath_id': ''}),
                (TalentId.SECRET_BLOODLINE, {'bloodline_id': 'lineage', 'kind': 'bloodline'}),
                (TalentId.TOUCHED_BY_THE_WINDS, {'lore_id': 'elementalism', 'deity': 'morr'}),
                (TalentId.LUCKY, {'deity': 'morr'})):
            document = wire(id)
            document[0]['acquisitions'][0]['choice'] = payload
            with self.subTest(id=id, payload=payload), self.assertRaises(InputError):
                parse(document)
            with self.assertRaises(ValidationError):
                self.talent_validator.validate(document)

    def test_duplicate_and_invalid_rank_sources_are_not_corrected(self):
        duplicate = wire() * 2
        with self.assertRaises(InputError) as raised:
            parse(duplicate)
        self.assertEqual(raised.exception.path, '/party/0/talents/1/id')
        invalid = []
        document = wire()
        document[0]['acquisitions'] *= 2
        invalid.append(document)
        document = wire(TalentId.WIZARD)
        document[0]['acquisitions'] *= 5
        invalid.append(document)
        document = wire(TalentId.FAMILIAR)
        another = deepcopy(document[0]['acquisitions'][0])
        another.update(phase='advancement', funding='xp')
        document[0]['acquisitions'].append(another)
        invalid.append(document)
        document = wire(TalentId.FAITH)
        document[0]['acquisitions'].append(dict(phase='advancement', funding='xp',
            choice=None, devotion_confirmed=False))
        invalid.append(document)
        document = wire()
        document[0]['acquisitions'][0]['phase'] = 'advancement'
        invalid.append(document)
        for document in invalid:
            before = deepcopy(document)
            with self.subTest(document=document), self.assertRaises(InputError):
                parse(document)
            self.assertEqual(document, before)

    def test_each_required_initial_choice_is_rejected_when_missing_or_null(self):
        ids = (TalentId.FAITH, TalentId.FAMILIAR, TalentId.HATRED, TalentId.HONOUR_BOUND,
            TalentId.SECRET_BLOODLINE, TalentId.TOUCHED_BY_THE_WINDS)
        for id in ids:
            for missing in (True, False):
                document = wire(id)
                if missing:
                    del document[0]['acquisitions'][0]['choice']
                else:
                    document[0]['acquisitions'][0]['choice'] = None
                with self.subTest(id=id, missing=missing), self.assertRaises(InputError):
                    parse(document)
                with self.assertRaises(ValidationError):
                    self.talent_validator.validate(document)

    def test_owner_facts_reject_boolean_numbers_unknown_aliases_and_duplicate_facts(self):
        for name in ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                'initiative', 'agility', 'reason', 'fellowship'):
            for number in (True, False, 0, -1, 1.5, '4'):
                with self.subTest(name=name, number=number), self.assertRaises(InputError) as raised:
                    parse_facts({name: number})
                self.assertEqual(raised.exception.path, '/party/0/talent_facts/' + name)
                with self.assertRaises(ValidationError):
                    self.facts_validator.validate({name: number})
        invalid = ({'origin': 'Human'}, {'status': 'Gold'}, {'status': True}, {'rank': 1},
            {'equipment': ['musicians_gear', 'musicians_gear']},
            {'lores': [{'id': 'anatomy'}, {'id': 'anatomy', 'magic': True}]},
            {'lores': [{'id': 'anatomy', 'magic': 1}]}, {'grail_quest_completed': 1},
            {'can_cast_spells': 0}, {'lores': None}, {'equipment': None})
        for document in invalid:
            with self.subTest(document=document), self.assertRaises(InputError) as raised:
                parse_facts(document)
            self.assertTrue(raised.exception.path.startswith('/party/0/talent_facts'))

    def test_serializer_revalidates_cached_typed_sources_and_rejects_duplicates(self):
        damaged = deepcopy(source())
        object.__setattr__(damaged.acquisitions[0], 'funding', 'free')
        with self.assertRaises(TypeError):
            acquired_talents_document((damaged,))
        damaged = deepcopy(source(TalentId.FAITH))
        object.__setattr__(damaged.acquisitions[0].choice, 'deity', 'sigmar')
        with self.assertRaises(TypeError):
            acquired_talents_document((damaged,))
        with self.assertRaises(ValueError):
            acquired_talents_document((source(), source()))
        with self.assertRaises(TypeError):
            acquired_talents_document([source()])
        facts = TalentOwnerFacts(lores=(TalentLoreFact('anatomy'),))
        damaged_facts = deepcopy(facts)
        object.__setattr__(damaged_facts.lores[0], 'magic', 1)
        with self.assertRaises(TypeError):
            talent_owner_facts_document(damaged_facts)

    def test_direct_codec_inputs_cannot_smuggle_typed_or_container_aliases(self):
        with self.assertRaises(InputError):
            parse((wire()[0],))
        document = wire()
        document[0]['id'] = TalentId.LUCKY
        with self.assertRaises(InputError):
            parse(document)
        document = wire()
        document[0]['acquisitions'][0]['devotion_confirmed'] = 1
        with self.assertRaises(InputError) as raised:
            parse(document)
        self.assertEqual(raised.exception.path,
            '/party/0/talents/0/acquisitions/0/devotion_confirmed')
        with self.assertRaises(InputError):
            parse_facts({'lores': [{'id': 'anatomy', 'extra': True}]})
