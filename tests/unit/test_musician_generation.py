"""Music generation preserves explicit independent acquisition and gear sources."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from random import Random
import unittest

from tests.unit.test_generated_npc_talent_generation import FixedChoices
from tests.unit.test_musician_tool_source import character
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.application.dynamic_encounter import NpcSearchSpace, automatic_npc_search_space
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.talent_catalog import TalentId, TalentEquipmentRequirement
from towr.domain.talent_models import TalentLoreFact, TalentOwnerFacts
from towr.domain.tool_inventory_models import ToolKind
from towr.domain.weapon_inventory_models import WeaponItemLocation


def music_space(**changes):
    return NpcSearchSpace(**(dict(weapon_skill=(3,), strength=(3,), toughness=(3,), agility=(3,),
        melee=(4,), athletics=(4,), defence=(4,), brawn=(4,), endurance=(4,),
        weapon=(GeneratedWeapon.SWORD,), weapon_count=(1,), armour=(None,), shield=(None,),
        allowed_talents=(TalentId.BATTLEFIELD_MUSICIAN,), fellowship=(3,), leadership=(4,),
        musician_instrument_hands=(1,)) | changes))


class MusicianGenerationTests(unittest.TestCase):
    def test_selected_paid_music_has_real_separate_tools_lore_facts_and_ratings(self):
        for hands in (1,2):
            space=music_space(musician_instrument_hands=(hands,))
            npc=space.sample(FixedChoices(1))
            with self.subTest(hands=hands):
                self.assertEqual(tuple(talent.id for talent in npc.talents), (TalentId.BATTLEFIELD_MUSICIAN,))
                self.assertEqual(len(npc.tools),1)
                tool,=npc.tools
                self.assertIs(tool.kind,ToolKind.MUSICIANS_GEAR)
                self.assertEqual(tool.hands_required,hands)
                self.assertIs(tool.initial_location,WeaponItemLocation.CARRIED)
                self.assertIsNone(tool.initial_grip)
                self.assertEqual((npc.fellowship,npc.leadership),(3,4))
                self.assertEqual(npc.talent_facts.fellowship,npc.fellowship)
                self.assertIn(TalentLoreFact('music',False),npc.talent_facts.lores)
                self.assertIn(TalentEquipmentRequirement.MUSICIANS_GEAR,npc.talent_facts.equipment)
                self.assertEqual(npc.weapons[0].id,'item:1')
                self.assertIs(npc.weapons[0].initial_location,WeaponItemLocation.HELD)
                self.assertTrue(space.contains(npc))
                self.assertFalse(hasattr(npc,'fate'))

    def test_unselected_music_creates_no_ratings_lore_or_instrument(self):
        npc=music_space().sample(FixedChoices(0))
        self.assertEqual(npc.talents,())
        self.assertEqual(npc.tools,())
        self.assertIsNone(npc.fellowship)
        self.assertIsNone(npc.leadership)
        self.assertIsNone(npc.talent_facts)

    def test_unused_music_ranges_do_not_change_existing_random_paths(self):
        left=music_space(allowed_talents=(),fellowship=(2,),leadership=(2,),musician_instrument_hands=(1,))
        right=replace(left,fellowship=(7,8),leadership=(5,6),musician_instrument_hands=(2,))
        for seed in (0,7,42):
            member=left.sample(Random(seed))
            self.assertEqual(right.sample(Random(seed)),member)
            self.assertEqual(left.mutate(member,Random(seed)),right.mutate(member,Random(seed)))
            self.assertEqual(left.resample_numeric((member,),Random(seed)),
                right.resample_numeric((member,),Random(seed)))

    def test_real_generated_snapshot_retains_the_concrete_carried_instrument(self):
        npc=music_space(musician_instrument_hands=(2,)).sample(FixedChoices(1))
        snapshot=npc.participant('npc:musician')
        self.assertEqual(snapshot.definition.generated_components,npc)
        self.assertEqual(snapshot.definition.talent_facts,npc.talent_facts)
        tool,=snapshot.state.tool_inventory.items
        self.assertEqual(tool.source,npc.tools[0])
        self.assertEqual(tool.initial_actor_id,'npc:musician')
        self.assertIs(tool.location,WeaponItemLocation.CARRIED)
        self.assertFalse(hasattr(snapshot.state,'fate'))

    def test_mixed_allies_and_music_share_actual_fellowship_without_changing_talents(self):
        space=music_space(allowed_talents=(TalentId.ALLIES_IN_ARMS,TalentId.BATTLEFIELD_MUSICIAN),
            fellowship=(4,5),leadership=(3,6))
        npc=space.sample(FixedChoices(1))
        self.assertEqual(tuple(talent.id for talent in npc.talents),space.allowed_talents)
        self.assertEqual(npc.talent_facts.fellowship,npc.fellowship)
        self.assertTrue(space.contains(npc))
        for seed in range(8):
            result=space.resample_numeric((npc,),Random(seed)).composition[0]
            self.assertEqual(result.talents,npc.talents)
            self.assertEqual(result.talent_facts.fellowship,result.fellowship)
            self.assertGreaterEqual(result.fellowship,4)

    def test_numeric_resampling_preserves_tool_origin_pose_lore_and_acquisitions(self):
        space=music_space(fellowship=(2,3,5),leadership=(2,4,6))
        npc=space.sample(FixedChoices(1))
        seen=set()
        for seed in range(20):
            result=space.resample_numeric((npc,),Random(seed),bias=.25).composition[0]
            self.assertEqual(result.tools,npc.tools)
            self.assertEqual(result.weapons,npc.weapons)
            self.assertEqual(result.talents,npc.talents)
            self.assertEqual(result.talent_facts.lores,npc.talent_facts.lores)
            self.assertEqual(result.talent_facts.equipment,npc.talent_facts.equipment)
            self.assertEqual(result.talent_facts.fellowship,result.fellowship)
            self.assertTrue(space.contains(result))
            seen.add((result.fellowship,result.leadership))
        self.assertGreater(len(seen),1)

    def test_mutation_adds_explicit_bundle_and_removal_preserves_independent_facts(self):
        space=music_space()
        ordinary=space.sample(FixedChoices(0))
        musician=space.mutate(ordinary,FixedChoices(0))
        self.assertEqual(tuple(talent.id for talent in musician.talents),(TalentId.BATTLEFIELD_MUSICIAN,))
        self.assertEqual(len(musician.tools),1)
        self.assertTrue(space.contains(musician))
        removed=space.mutate(musician,FixedChoices(0))
        self.assertEqual(removed.talents,())
        self.assertEqual(removed.tools,musician.tools)
        self.assertEqual(removed.talent_facts,musician.talent_facts)
        self.assertEqual((removed.fellowship,removed.leadership),(musician.fellowship,musician.leadership))
        self.assertTrue(space.contains(removed))

    def test_generated_instrument_cannot_alias_an_existing_weapon_source_id(self):
        space=music_space()
        before=space.sample(FixedChoices(0))
        before=replace(before,weapons=(replace(before.weapons[0],id='musicians-gear'),))
        self.assertTrue(space.contains(before))
        after=space.mutate(before,FixedChoices(0))
        self.assertEqual(after.weapons,before.weapons)
        self.assertEqual(after.tools[0].id,'musicians-gear:1')
        self.assertTrue(space.contains(after))

    def test_component_mutations_keep_whole_typed_source_and_instrument_choices(self):
        space=music_space(fellowship=(2,3,4),leadership=(2,4,6),musician_instrument_hands=(1,2),
            weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.AXE),weapon_count=(1,2))
        current=space.sample(FixedChoices(1))
        for seed in range(25):
            changed=space.mutate(current,Random(seed))
            self.assertTrue(space.contains(changed))
            replace(changed)
            if changed.fellowship is not None:
                self.assertEqual(changed.talent_facts.fellowship,changed.fellowship)
            self.assertTrue(all(tool.hands_required in (1,2) for tool in changed.tools))
            current=changed

    def test_existing_lore_and_tool_are_retained_when_readding_talent(self):
        space=music_space()
        musician=space.sample(FixedChoices(1))
        facts=replace(musician.talent_facts,lores=(*musician.talent_facts.lores,TalentLoreFact('anatomy',False)))
        before=replace(musician,talents=(),talent_facts=facts)
        restored=space.mutate(before,FixedChoices(0))
        self.assertEqual(restored.tools,before.tools)
        self.assertEqual(restored.talent_facts,facts)
        self.assertEqual(tuple(talent.id for talent in restored.talents),(TalentId.BATTLEFIELD_MUSICIAN,))

    def test_contains_rejects_missing_operational_sources_and_outside_component_choices(self):
        space=music_space()
        npc=space.sample(FixedChoices(1))
        corrupt=replace(npc)
        object.__setattr__(corrupt,'fellowship',None)
        for changed in (replace(npc,tools=()), corrupt,replace(npc,leadership=None),
                replace(npc,tools=(replace(npc.tools[0],hands_required=2),)),
                replace(npc,talent_facts=replace(npc.talent_facts,lores=()))):
            with self.subTest(changed=changed):
                self.assertFalse(space.contains(changed))

    def test_space_rejects_nonliteral_empty_duplicate_or_outside_numeric_choices(self):
        for field,values in (('leadership',()),('leadership',(True,)),('leadership',(1,)),
                ('leadership',(7,)),('leadership',(3,3)),('musician_instrument_hands',()),
                ('musician_instrument_hands',(True,)),('musician_instrument_hands',(0,)),
                ('musician_instrument_hands',(3,)),('musician_instrument_hands',(1,1))):
            with self.subTest(field=field,values=values),self.assertRaises((ValueError,TypeError)):
                music_space(**{field:values})

    def test_current_json_parses_new_ranges_without_opening_music_talent_cap(self):
        raw=json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
        space=NpcSearchSpace(allowed_talents=(),leadership=(2,5,6),musician_instrument_hands=(2,))
        raw['search_space']=json.loads(json.dumps(asdict(space)))
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(command.request.space,space)
        for field,values in (('leadership',[True]),('leadership',[7]),('musician_instrument_hands',[True]),
                ('musician_instrument_hands',[3])):
            raw['search_space']=json.loads(json.dumps(asdict(space)))
            raw['search_space'][field]=values
            with self.subTest(field=field,values=values),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))

    def test_automatic_ranges_use_actual_fellowship_and_leadership(self):
        member=character(fellowship=5,leadership=5).participant('generation',NpcDefeatDisposition.KILLED)
        space=automatic_npc_search_space((member,))
        self.assertEqual(space.fellowship,(4,5,6))
        self.assertEqual(space.leadership,(4,5,6))
        self.assertEqual(space.musician_instrument_hands,(1,2))


if __name__=='__main__':
    unittest.main()
