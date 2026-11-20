"""Physical tools through current PC/Dynamic sources and character files."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters._pc_melee_scenario_json import (
    generated_components_document, parse_generated_components, scenario_document,
)
from towr.adapters._tool_json import (
    parse_tool_item_source, parse_tool_item_sources, tool_item_source_document,
)
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.encounter_character import EncounterCharacter
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, generated_initial_weapon_inventory
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import (
    PcGloriousPolicy, PcMeleeWeapon, PcShieldHandConflictPolicy, PcShieldLoadout, PcShieldRecoveryPolicy, PcWeaponHand,
)
from towr.domain.talent_catalog import TalentEquipmentRequirement
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.tool_inventory_models import (
    ToolInventoryState, ToolItemSource, ToolKind, initial_tool_inventory, validate_tool_equipment_hands,
)
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponInventoryState, WeaponItemLocation as L,
)
from towr.domain.test_models import Skill


def tool(identifier='instrument', *, hands=1, location=L.CARRIED, grip=None, name=None):
    return ToolItemSource(identifier, ToolKind.MUSICIANS_GEAR, hands, location, grip, name)


def wire(identifier='instrument', *, hands=1, location='carried', **extra):
    return dict(id=identifier, kind='musicians_gear', hands_required=hands, location=location, **extra)


def parse_item(raw):
    return parse_tool_item_source(raw, path_prefix='/tools/0', error_type=DynamicEncounterInputError)


def creature(**changes):
    return replace(GeneratedNpc(3, 3, 3, 3, 4, 4,
        initial_generated_weapons(GeneratedWeapon.SWORD), ArmourLoadout(), defence=4), **changes)


def character(**changes):
    return replace(EncounterCharacter('pc', 3, 3, 3, 3, 5, 5, 4, 4,
        PcMeleeWeapon.SWORD, ArmourLoadout(), False, PcWeaponHand.LEFT, (), 3), **changes)


def dynamic_document():
    raw = json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    raw['party'] = raw['party'][:1]
    return raw


def native_document(source):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='tools:wire',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


class MusicianToolSourceTests(unittest.TestCase):
    def test_explicit_leadership_glorious_policy_is_admitted_without_changing_defaults(self):
        self.assertEqual(PcGloriousPolicy((Skill.LEADERSHIP,), 0, 0).skills, (Skill.LEADERSHIP,))
        default = character(fellowship=4, leadership=4).participant('session', NpcDefeatDisposition.KILLED)
        self.assertNotIn(Skill.LEADERSHIP, default.glorious_policy.skills)
        configured = replace(default, glorious_policy=PcGloriousPolicy((Skill.LEADERSHIP,), 0, 0))
        command = parse_dynamic_encounter_request(json.dumps(dynamic_document()))
        source = command.request.scenario((creature(),), 'leadership:glorious')
        configured = replace(configured, target_priority=source.party[0].target_priority,
            defeat_decisions=source.party[0].defeat_decisions)
        source = replace(source, party=(configured,))
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario, source)

    def test_one_shared_wire_shape_preserves_actual_source_and_instrument_name(self):
        for hands, location, expected_grip in (
                (1, 'left_hand', G.LEFT), (1, 'right_hand', G.RIGHT),
                (2, 'both_hands', G.BOTH), (1, 'carried', None), (2, 'carried', None)):
            raw = wire(hands=hands, location=location, instrument_name='The old marching drum')
            before = deepcopy(raw)
            with self.subTest(hands=hands, location=location):
                source = parse_item(raw)
                self.assertIs(source.kind, ToolKind.MUSICIANS_GEAR)
                self.assertEqual(source.hands_required, hands)
                self.assertIs(source.initial_grip, expected_grip)
                self.assertEqual(source.instrument_name, 'The old marching drum')
                self.assertEqual(tool_item_source_document(source), before)
                self.assertEqual(raw, before)
                self.assertEqual(set(before), {'id', 'kind', 'hands_required', 'location', 'instrument_name'})

    def test_wire_rejects_bool_missing_unknown_and_incompatible_physical_facts(self):
        for changes in (dict(id=True), dict(kind='sword'), dict(kind=True),
                dict(hands_required=True), dict(hands_required=0), dict(hands_required=3),
                dict(hands_required=1.0), dict(location='held'), dict(location='dropped'),
                dict(location=True), dict(location='both_hands'),
                dict(hands_required=2, location='left_hand'),
                dict(instrument_name=None), dict(instrument_name=True), dict(instrument_name=' '),
                dict(weapon='sword'), dict(hand='left'), dict(initial_grip='left')):
            with self.subTest(changes=changes), self.assertRaises(DynamicEncounterInputError):
                parse_item({**wire(), **changes})
        for field in ('id', 'kind', 'hands_required', 'location'):
            raw = wire()
            del raw[field]
            with self.subTest(missing=field), self.assertRaises(DynamicEncounterInputError):
                parse_item(raw)

    def test_wire_list_rejects_duplicate_sources_malformed_container_and_shared_hands(self):
        for raw in (None, (), True, [wire(), wire()],
                [wire('one', location='right_hand'), wire('two', location='right_hand')]):
            with self.subTest(raw=raw), self.assertRaises(DynamicEncounterInputError):
                parse_tool_item_sources(raw, path_prefix='/tools', error_type=DynamicEncounterInputError)
        sources = parse_tool_item_sources([wire('one'), wire('two', hands=2)],
            path_prefix='/tools', error_type=DynamicEncounterInputError)
        self.assertEqual(tuple(item.id for item in sources), ('one', 'two'))

    def test_optional_tool_sources_do_not_create_items_from_prerequisite_facts(self):
        facts = TalentOwnerFacts(equipment=(TalentEquipmentRequirement.MUSICIANS_GEAR,))
        pc = replace(make_pc_melee_scenario().party[0], talent_facts=facts)
        npc = creature(talent_facts=facts)
        self.assertEqual((pc.pc.tools, npc.tools, character().tools), ((), (), ()))
        self.assertEqual(npc.participant('npc').state.tool_inventory, ToolInventoryState())
        raw = dynamic_document()
        raw['party'][0]['talent_facts'] = {'equipment': ['musicians_gear']}
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.party[0].pc.tools, ())

    def test_model_sources_require_exact_tuples_and_revalidate_nested_tools(self):
        for source in (make_pc_melee_scenario().party[0].pc, creature(), character()):
            for tools in ([tool()], (True,), (tool(), tool())):
                with self.subTest(source=type(source).__name__, tools=tools):
                    with self.assertRaises((TypeError, ValueError)):
                        replace(source, tools=tools)
            broken = tool()
            object.__setattr__(broken, 'hands_required', True)
            with self.subTest(source=type(source).__name__), self.assertRaises((TypeError, ValueError)):
                replace(source, tools=(broken,))

    def test_pc_initial_held_tools_share_actual_hands_with_weapons(self):
        member = make_pc_melee_scenario().party[0]
        held = tool(location=L.HELD, grip=G.RIGHT)
        admitted = replace(member, pc=replace(member.pc, tools=(held,)))
        self.assertEqual(admitted.pc.tools, (held,))
        for source in (tool(location=L.HELD, grip=G.LEFT),
                tool(hands=2, location=L.HELD, grip=G.BOTH)):
            with self.subTest(tool=source), self.assertRaises(ValueError):
                replace(member, pc=replace(member.pc, tools=(source,)))
        with self.assertRaises(ValueError):
            replace(member, pc=replace(member.pc, tools=(tool('weapon'),)))

    def test_pc_shield_hand_cannot_be_occupied_by_a_tool(self):
        member = make_pc_melee_scenario().party[0]
        shield = PcShieldLoadout(PcWeaponHand.RIGHT, PcShieldHandConflictPolicy.WEAPON_FIRST,
            PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
        with self.assertRaises(ValueError):
            replace(member, shield=shield,
                pc=replace(member.pc, tools=(tool(location=L.HELD, grip=G.RIGHT),)))
        admitted = replace(member, shield=shield, pc=replace(member.pc, tools=(tool(),)))
        self.assertEqual(admitted.pc.tools[0].initial_location, L.CARRIED)

    def test_character_compilation_preserves_full_physical_tool_sources(self):
        sources = (tool(location=L.HELD, grip=G.RIGHT, name='A brass horn'), tool('flute', hands=2))
        original = character(tools=sources)
        participant = original.participant('tools', NpcDefeatDisposition.KILLED)
        self.assertIs(participant.pc.tools, sources)
        self.assertEqual(participant.talents, ())
        with self.assertRaises(ValueError):
            replace(original, tools=(tool(location=L.HELD, grip=G.LEFT),))

    def test_generated_source_uses_tools_without_converting_them_to_weapons(self):
        source = tool(location=L.HELD, grip=G.RIGHT, name='A field horn')
        npc = creature(tools=(source,))
        self.assertEqual(len(npc.weapons), 1)
        self.assertIs(npc.tools[0], source)
        participant = npc.participant('npc')
        self.assertEqual(participant.state.tool_inventory, initial_tool_inventory('npc', (source,)))
        self.assertIs(participant.state.tool_inventory.items[0].source, source)
        self.assertEqual(participant.definition.generated_components.tools, (source,))
        for tools in ((tool(location=L.HELD, grip=G.LEFT),),
                (tool(hands=2, location=L.HELD, grip=G.BOTH),), (tool('weapon'),)):
            with self.subTest(tools=tools), self.assertRaises(ValueError):
                creature(tools=tools)

    def test_generated_shield_chooses_an_actual_unoccupied_initial_hand(self):
        carried = tuple(replace(source, initial_location=L.CARRIED, initial_grip=None)
            for source in creature().weapons)
        source = tool(location=L.HELD, grip=G.RIGHT)
        npc = creature(weapons=carried, brawn=4, tools=(source,),
            armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        inventory = generated_initial_weapon_inventory(npc, 'npc')
        self.assertIs(inventory.shield_hand, G.LEFT)
        self.assertEqual(npc.participant('npc').state.tool_inventory.occupied_hands, (G.RIGHT,))
        with self.assertRaises(ValueError):
            creature(tools=(source,), armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        with self.assertRaises(ValueError):
            replace(npc, tools=(tool(hands=2, location=L.HELD, grip=G.BOTH),))

    def test_common_hand_guard_uses_complete_tool_weapon_and_shield_banks(self):
        tools = initial_tool_inventory('actor', (tool(location=L.HELD, grip=G.RIGHT),))
        validate_tool_equipment_hands(tools, WeaponInventoryState(shield_hand=G.LEFT))
        with self.assertRaises(ValueError):
            validate_tool_equipment_hands(tools, WeaponInventoryState(shield_hand=G.RIGHT))
        for wrong_tools, wrong_weapons in ((True, WeaponInventoryState()), (tools, True)):
            with self.assertRaises(TypeError):
                validate_tool_equipment_hands(wrong_tools, wrong_weapons)

    def test_dynamic_json_and_player_file_preserve_same_current_tool_shape(self):
        raw = dynamic_document()
        raw['party'][0]['equipment']['tools'] = [wire(location='right_hand', instrument_name='The horn'),
            wire('spare', hands=2)]
        before = deepcopy(raw)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(command.request.party[0].pc.tools,
            (tool(location=L.HELD, grip=G.RIGHT, name='The horn'), tool('spare', hands=2)))
        self.assertEqual(json.loads(command.source_json), before)
        self.assertEqual(parse_character_file(json.dumps(raw['party'][0]), 'player'), raw['party'][0])
        self.assertEqual(parse_dynamic_encounter_request(command.source_json).request, command.request)
        self.assertEqual(raw, before)

    def test_dynamic_two_handed_tool_keeps_carried_weapon_and_explicit_brawn(self):
        raw = dynamic_document()
        member = raw['party'][0]
        member['equipment']['weapons'][0]['location'] = 'carried'
        member['equipment']['tools'] = [wire(hands=2, location='both_hands')]
        member['skills']['brawn'] = 4
        command = parse_dynamic_encounter_request(json.dumps(raw))
        pc = command.request.party[0]
        self.assertIs(pc.pc.weapon, PcMeleeWeapon.UNARMED)
        self.assertIsNone(pc.initial_weapon_hand)
        self.assertIs(pc.pc.tools[0].initial_grip, G.BOTH)
        self.assertEqual(len(pc.combat_equipment), 1)
        self.assertEqual(pc.combat_equipment[0].location.value, 'carried')

    def test_public_tool_hand_overlap_and_cross_bank_ids_are_rejected(self):
        for location in ('left_hand', 'both_hands'):
            raw = dynamic_document()
            raw['party'][0]['equipment']['tools'] = [wire(hands=2 if location == 'both_hands' else 1,
                location=location)]
            for parser in (lambda: parse_dynamic_encounter_request(json.dumps(raw)),
                    lambda: parse_character_file(json.dumps(raw['party'][0]), 'player')):
                with self.subTest(location=location), self.assertRaises(DynamicEncounterInputError):
                    parser()
        for bank in ('weapons', 'armour', 'consumables'):
            raw = dynamic_document()
            member = raw['party'][0]
            if bank == 'weapons':
                identifier = member['equipment']['weapons'][0]['id']
            elif bank == 'armour':
                identifier = 'mail'
                member['equipment']['armour'] = [dict(id=identifier, kind='light_armour', location='worn')]
            else:
                identifier = 'potion'
                member['consumables'] = [dict(id=identifier, kind='healing_potion', quantity=1, characteristic=None)]
            member['equipment']['tools'] = [wire(identifier)]
            with self.subTest(bank=bank):
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                with self.assertRaises(DynamicEncounterInputError):
                    parse_character_file(json.dumps(member), 'player')

    def test_player_character_draft_preserves_explicit_shield_tool_conflicts(self):
        raw = dynamic_document()
        member = raw['party'][0]
        member['equipment']['armour'] = [dict(id='shield', kind='shield', location='right_hand')]
        member['equipment']['tools'] = [wire(location='right_hand')]
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(member), 'player')
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_native_pc_json1_roundtrip_preserves_original_tools_and_hand_shape(self):
        source = make_pc_melee_scenario()
        member = replace(source.party[0], pc=replace(source.party[0].pc,
            tools=(tool(location=L.HELD, grip=G.RIGHT, name='The horn'), tool('spare', hands=2))))
        source = replace(source, party=(member,))
        raw = native_document(source)
        self.assertEqual(raw['scenario']['party'][0]['pc']['tools'],
            [wire(location='right_hand', instrument_name='The horn'), wire('spare', hands=2)])
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario, source)
        self.assertEqual(raw['schema_version'], '1')
        self.assertNotIn('tools', scenario_document(make_pc_melee_scenario())['party'][0]['pc'])

    def test_generated_document_character_file_and_native_json_keep_source_tools(self):
        original = creature(tools=(tool(location=L.HELD, grip=G.RIGHT, name='The horn'), tool('spare', hands=2)))
        raw = generated_components_document(original)
        self.assertEqual(raw['tools'], [wire(location='right_hand', instrument_name='The horn'), wire('spare', hands=2)])
        self.assertEqual(parse_character_file(json.dumps(raw), 'npc'), raw)
        self.assertEqual(parse_generated_components(raw, path_prefix='/npc', error_type=DynamicEncounterInputError), original)
        command = parse_dynamic_encounter_request(json.dumps(dynamic_document()))
        source = command.request.scenario((original,), 'tools:generated')
        restored = parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario
        self.assertEqual(restored, source)
        self.assertEqual(restored.enemies[0].state.tool_inventory,
            initial_tool_inventory(restored.enemies[0].state.actor_id, original.tools))

    def test_all_public_tool_arrays_reject_bool_quantity_and_fake_weapon_fields(self):
        for changes in (dict(hands_required=True), dict(hands_required=1.0), dict(quantity=2),
                dict(location='held'), dict(weapon='sword'), dict(instrument_name=None)):
            player_raw = dynamic_document()['party'][0]
            player_raw['equipment']['tools'] = [{**wire(), **changes}]
            npc_raw = generated_components_document(creature())
            npc_raw['tools'] = [{**wire(), **changes}]
            for kind, raw in (('player', player_raw), ('npc', npc_raw)):
                with self.subTest(kind=kind, changes=changes), self.assertRaises(DynamicEncounterInputError):
                    parse_character_file(json.dumps(raw), kind)


if __name__ == '__main__':
    unittest.main()
