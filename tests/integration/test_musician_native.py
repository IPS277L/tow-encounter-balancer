"""Native music actions with literal dice and a complete replayable journal."""
from dataclasses import replace
import json
from pathlib import Path
from unittest import TestCase

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.talent_sources import free_talent
from towr.domain.battlefield_music_models import BattlefieldMusicAcoustics
from towr.domain.pc_melee_result_models import initial_pc_melee_state, PcMeleeStep
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_demigryph_models import pc_kernel_resolution
from towr.domain.attack_models import AttackOutcome
from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
from towr.domain.pc_melee_result_models import PcBodyConsequenceProof,PcHandDropProof
from towr.domain.fate_models import FateSessionState
from towr.domain.pc_melee_models import PcFatePolicy,PcGloriousPolicy
from towr.domain.test_models import Skill
from towr.domain.condition_models import Condition
from towr.domain.pc_generated_talents import PcDefensiveStanceProof
from towr.domain.pc_musician_effect_models import PcMusicianActionProof, PcMusicianSignalProof
from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts, TalentLoreFact
from towr.domain.tool_inventory_models import ToolItemSource, ToolKind
from towr.domain.weapon_inventory_models import WeaponItemLocation, WeaponGrip
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from tests.support.generated_weapon_sources import initial_generated_weapons


def music_scenario(*,hands=1,rounds=1):
    source=automatic_source(pc_count=3,enemy_count=3,rounds=rounds)
    musician=source.party[0]
    tool=ToolItemSource('instrument',ToolKind.MUSICIANS_GEAR,hands,WeaponItemLocation.CARRIED,None,'Marching drum')
    definition=replace(musician.pc,weapon_skill=1,strength=1,melee=1,fellowship=5,leadership=4,tools=(tool,))
    musician=replace(musician,pc=definition,talents=(free_talent(TalentId.BATTLEFIELD_MUSICIAN),),
        talent_facts=TalentOwnerFacts(fellowship=5,lores=(TalentLoreFact('music',False),)))
    return replace(source,party=(musician,*source.party[1:]),music_acoustics=BattlefieldMusicAcoustics(True))


def npc_music_scenario(*,hands=1,rounds=1):
    source=automatic_source(pc_count=3,enemy_count=3,rounds=rounds)
    actor=source.enemy_activation_order[0]
    tool=ToolItemSource('instrument',ToolKind.MUSICIANS_GEAR,hands,WeaponItemLocation.CARRIED,None,'Marching drum')
    npc=GeneratedNpc(1,1,3,3,2,4,initial_generated_weapons(GeneratedWeapon.DAGGER),ArmourLoadout(),
        defence=2,fellowship=5,leadership=4,tools=(tool,),
        talents=(free_talent(TalentId.BATTLEFIELD_MUSICIAN),),
        talent_facts=TalentOwnerFacts(fellowship=5,lores=(TalentLoreFact('music',False),)))
    return replace(source,enemies=(npc.participant(actor),*source.enemies[1:]),
        music_acoustics=BattlefieldMusicAcoustics(True))


class MusicianNativeTests(TestCase):
    def test_zero_success_music_spends_one_action_with_real_tool_and_replay(self):
        source=music_scenario()
        rng=ScriptedD10([10]*24)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        music=tuple(step.proof for step in result.steps if type(step.proof) is PcMusicianActionProof)
        self.assertEqual(len(music),1)
        self.assertEqual(result.executed_actions,6)
        self.assertEqual(music[0].result.test_result.successes,0)
        self.assertEqual(music[0].result.beneficiary_ids,())
        self.assertEqual(len(tuple(step for step in result.steps if type(step.proof) is PcMusicianSignalProof)),1)
        self.assertTrue(any(type(step.proof) is PcMusicianEquipmentProof for step in result.steps))
        state=initial_pc_melee_state(source)
        for step in result.steps:
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)

    def test_generated_npc_uses_real_leadership_without_fate(self):
        source=npc_music_scenario()
        rng=ScriptedD10([10]*30)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        music=tuple(step.proof for step in result.steps if type(step.proof) is PcMusicianActionProof)
        self.assertEqual(len(music),1)
        self.assertEqual(music[0].result.source_request.actor_id,source.enemy_activation_order[0])
        self.assertIsNone(music[0].decline)
        self.assertIsNone(music[0].glorious)
        self.assertEqual(result.executed_actions,6)

    def test_positive_tie_attack_fails_against_a_really_inspired_ally(self):
        source=music_scenario()
        source=replace(source,enemy_target_priority=('pc2','pc1','pc3'))
        rng=ScriptedD10([1,10,10,10,10]+[10]*10+[1,10,1,10,10]+[10]*10)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        music=next(step.proof for step in result.steps if type(step.proof) is PcMusicianActionProof)
        self.assertEqual(music.result.beneficiary_ids,('pc2',))
        first=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        attack=pc_kernel_resolution(first).attack
        self.assertIs(attack.outcome,AttackOutcome.MISS)
        self.assertTrue(attack.tie_break_applied)
        self.assertEqual(first.request.target_id,'pc2')
        self.assertEqual(first.request.kernel_request.attack.tie_break.rule_id,attack.applied_rule_ids[-1])

    def test_defensive_stance_can_use_the_actual_music_defensive_tie(self):
        source=music_scenario()
        ally=replace(source.party[1],talents=(free_talent(TalentId.DEFENSIVE_STANCE),))
        source=replace(source,party=(source.party[0],ally,source.party[2]),
            enemy_target_priority=('pc2','pc1','pc3'))
        rng=ScriptedD10([1,10,10,10,10]+[10]*10+[1,10,1,10,10]+[10]*10)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertEqual(sum(type(step.proof) is PcDefensiveStanceProof for step in result.steps),1)
        self.assertFalse(result.state.participant('pc2').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))

    def test_wound_drops_the_real_instrument_then_a_paid_recover_retrieves_it(self):
        source=music_scenario(rounds=3)
        rng=ScriptedD10([10]*15+[1,1,10,4,10,10,10,10]+[10]*49)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        drops=tuple(drop for step in result.steps if type(step.proof) in (PcBodyConsequenceProof,PcHandDropProof)
            for drop in step.proof.tool_drops)
        self.assertEqual(len(drops),1)
        self.assertEqual(drops[0].actor_id,'pc1')
        self.assertEqual(drops[0].after.items[0].dropped_zone_id,'arena')
        recovered=tuple(step.proof for step in result.steps if type(step.proof) is PcMusicianRecoverProof)
        self.assertEqual(len(recovered),1)
        self.assertTrue(recovered[0].result.slot.executed)
        self.assertEqual(recovered[0].result.resolution.object_interaction_follow_up.object_id,drops[0].item_id)
        member=result.state.participant('pc1')
        self.assertIs(member.tool_inventory.items[0].location,WeaponItemLocation.HELD)
        self.assertEqual(len(member.injury.wounds),1)

    def test_player_leadership_uses_the_real_fate_window(self):
        source=music_scenario()
        member=source.party[0]
        member=replace(member,fate=FateSessionState('music-session','pc1',1,1),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.LEADERSHIP,),0,0))
        source=replace(source,party=(member,*source.party[1:]))
        rng=ScriptedD10([10]*5+[1,10,10,10,10]+[10]*19)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof=next(step.proof for step in result.steps if type(step.proof) is PcMusicianActionProof)
        self.assertIsNotNone(proof.glorious)
        self.assertIsNone(proof.decline)
        self.assertEqual(proof.result.test_result.successes,1)
        self.assertEqual(result.state.participant('pc1').fate.remaining_spends,0)

    def test_two_handed_instrument_uses_both_real_hands_for_either_side(self):
        for builder,count in ((music_scenario,30),(npc_music_scenario,30)):
            with self.subTest(side=builder.__name__):
                source=builder(hands=2)
                rng=ScriptedD10([10]*count)
                result=run_pc_melee_scenario(source,rng)
                rng.assert_exhausted()
                music=next(step.proof for step in result.steps if type(step.proof) is PcMusicianActionProof)
                self.assertEqual(music.result.source_request.source.tool_use.used_hands,
                    (WeaponGrip.LEFT,WeaponGrip.RIGHT))
                equipment=next(step.proof for step in result.steps if type(step.proof) is PcMusicianEquipmentProof)
                self.assertTrue(all(item.location is WeaponItemLocation.CARRIED for item in equipment.weapons.items))

    def test_without_allies_player_stows_ready_music_and_draws_the_carried_weapon(self):
        from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        raw=json.loads(Path('docs/examples/dynamic/battlefield-musician.request.json').read_text(encoding='utf-8'))
        raw['party']=raw['party'][:1]
        actor=raw['party'][0]
        actor['characteristics'].update(weapon_skill=3,strength=3)
        actor['skills'].update(melee=5,brawn=4)
        actor['resources']['fate']=0
        actor['equipment']['weapons']=[dict(id='glaive',weapon='glaive',location='carried')]
        actor['equipment']['tools'][0]['location']='both_hands'
        raw['npc_count']=dict(minimum=1,maximum=1)
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=GeneratedNpc(1,1,1,1,2,2,initial_generated_weapons(GeneratedWeapon.DAGGER),ArmourLoadout(),defence=2)
        source=command.request.scenario((npc,),'music:return-to-weapon')
        rng=ScriptedD10([10]*8)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertFalse(any(type(step.proof) is PcMusicianActionProof for step in result.steps))
        self.assertTrue(any(type(step.proof) is PcWeaponSwapProof for step in result.steps))
        member=result.state.participant('musician')
        self.assertIs(member.tool_inventory.items[0].location,WeaponItemLocation.CARRIED)
        self.assertEqual(member.weapon_inventory.active.source_item_id,'glaive')
        self.assertIs(member.weapon_inventory.active.location,WeaponItemLocation.HELD)
