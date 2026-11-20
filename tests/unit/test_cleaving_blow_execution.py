"""Actual weapon Wounds and non-recursive Cleaving waves on both sides."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.support.pc_melee_fixtures import make_pc_melee_scenario,make_pc_melee_party_scenario
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip,PcWeaponHand
from towr.domain.pc_melee_result_models import PcMeleeStep,initial_pc_melee_state,PcAttackProof
from towr.domain.pc_cleaving_blow_models import (
    PcCleavingStartProof,PcCleavingTargetProof,PcCleavingEndProof,
    expected_cleaving_start,cleaving_wound_triggers,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.condition_models import Condition
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def pc_source(weapon=PcMeleeWeapon.GREATAXE,*,talent=True,rounds=1):
    source=make_pc_melee_scenario(weapon=weapon,enemy_count=3,max_rounds=rounds)
    member=source.party[0]
    hand=PcTwoHandedGrip.BOTH if weapon in (PcMeleeWeapon.GREATAXE,PcMeleeWeapon.FOOT_SPEAR) else PcWeaponHand.LEFT
    member=replace(member,pc=replace(member.pc,weapon_skill=1,strength=5,toughness=20),
        initial_weapon_hand=hand,combat_equipment=initial_weapon_items(weapon,hand),
        talents=(paid_talent(TalentId.CLEAVING_BLOW),) if talent else ())
    return replace(source,party=(member,),facts=replace(source.facts,outnumbering_bonus_approved=False))


def npc_source():
    source=make_pc_melee_party_scenario(pc_count=2,enemy_count=1,max_rounds=1)
    members=tuple(replace(m,pc=replace(m.pc,weapon_skill=1,strength=1,toughness=2),
        combat_equipment=initial_weapon_items(PcMeleeWeapon.STAFF,PcWeaponHand.LEFT)) for m in source.party)
    npc=GeneratedNpc(3,5,20,1,2,2,initial_generated_weapons(GeneratedWeapon.GREATAXE),
        ArmourLoadout(),defence=2,talents=(paid_talent(TalentId.CLEAVING_BLOW),))
    return replace(source,party=members,enemies=(npc.participant('minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


class CleavingBlowExecutionTests(TestCase):
    def execute(self,source,values):
        result=run_pc_melee_scenario(source,SequenceRandom(values+[10]*800))
        self.assertIsNone(result.unsupported)
        state=initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,state)
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)
        return result

    def test_pc_actual_two_handed_wound_staggers_other_enemies_once_without_an_action(self):
        result=self.execute(pc_source(),[1,10,10])
        starts=[s for s in result.steps if type(s.proof) is PcCleavingStartProof]
        self.assertEqual(len(starts),1)
        start=starts[0]
        self.assertEqual(start.proof.target_ids,('minion2','minion3'))
        self.assertEqual(start.proof.trigger.wounded_target_id,'minion1')
        waves=[s for s in result.steps if type(s.proof) is PcCleavingTargetProof]
        self.assertEqual(tuple(s.proof.request.target_id for s in waves),('minion2','minion3'))
        for step in waves: self.assertEqual(step.source.round_state,step.state.round_state)
        self.assertEqual(len(cleaving_wound_triggers(result.state)),1)
        self.assertIsNone(expected_cleaving_start(result.state))

    def test_actual_two_hand_grip_qualifies_but_one_handed_weapon_and_absent_talent_do_not(self):
        for weapon,talent,count in ((PcMeleeWeapon.FOOT_SPEAR,True,1),
                (PcMeleeWeapon.AXE,True,0),(PcMeleeWeapon.GREATAXE,False,0)):
            with self.subTest(weapon=weapon,talent=talent):
                result=self.execute(pc_source(weapon,talent=talent),[1,10,10])
                self.assertEqual(sum(type(s.proof) is PcCleavingStartProof for s in result.steps),count)

    def test_npc_wave_wounds_other_pc_but_never_retriggers_its_own_weapon(self):
        result=self.execute(npc_source(),[10]*4+[1]*3+[10,1,1])
        starts=[s.proof for s in result.steps if type(s.proof) is PcCleavingStartProof]
        self.assertEqual(len(starts),1)
        self.assertEqual((starts[0].trigger.actor_id,starts[0].trigger.wounded_target_id),('minion1','pc1'))
        self.assertEqual(starts[0].target_ids,('pc2',))
        self.assertEqual(len(cleaving_wound_triggers(result.state)),1)
        self.assertEqual(len(result.state.participant('pc2').injury.wounds),1)

    def test_duplicate_start_and_forged_wound_target_cannot_enter_the_journal(self):
        result=self.execute(pc_source(),[1,10,10])
        start=next(s for s in result.steps if type(s.proof) is PcCleavingStartProof)
        with self.assertRaises((ValueError,TypeError)): PcMeleeStep(start.state,start.proof)
        bad=replace(start.proof,trigger=replace(start.proof.trigger,wound_id='foreign:wound'))
        with self.assertRaises((ValueError,TypeError)): PcMeleeStep(start.source,bad)
        with self.assertRaises((ValueError,TypeError)):
            PcMeleeStep(start.source,replace(start.proof,target_ids=('minion3',)))
        end=next(s for s in result.steps if type(s.proof) is PcCleavingEndProof)
        with self.assertRaises((ValueError,TypeError)): PcMeleeStep(start.state,end.proof)

    def test_actual_primary_repeated_stagger_and_defenceless_wounds_also_trigger(self):
        # Prepared K1 rule sources test trigger classification independently
        # of native admission, which deliberately requires fresh NPCs.
        from types import SimpleNamespace
        from towr.domain.attack_models import ResilienceProfile
        from towr.domain.pc_blunderbuss_models import PcNearbyDecisions
        from towr.rules.kernel import resolve_kernel_attack
        baseline=self.execute(pc_source(),[1,10,10])
        attack=next(s.proof for s in baseline.steps if type(s.proof) is PcAttackProof)
        for condition in (Condition.STAGGERED,Condition.DEFENCELESS):
            with self.subTest(condition=condition):
                kernel=attack.request.kernel_request
                kernel=replace(kernel,target_state=replace(kernel.target_state,
                    conditions=kernel.target_state.conditions.with_condition(condition)),
                    attack=replace(kernel.attack,impact_spec=replace(kernel.attack.impact_spec,
                        resilience=ResilienceProfile(50))))
                resolution=resolve_kernel_attack(kernel,SequenceRandom([1,10,10]),decisions=PcNearbyDecisions())
                prepared=replace(attack,request=replace(attack.request,kernel_request=kernel),
                    execution=replace(attack.execution,resolution=resolution))
                view=SimpleNamespace(source=baseline.source,history=(prepared,))
                self.assertEqual(len(cleaving_wound_triggers(view)),1)

    def test_failed_attack_or_cancelled_lady_wound_never_starts_a_wave(self):
        result=self.execute(pc_source(),[10]*100)
        self.assertFalse(cleaving_wound_triggers(result.state))
        from tests.support.oath_sources import lady
        from tests.integration.test_oath_native import lady_context
        source=pc_source()
        target=GeneratedNpc(1,1,1,1,2,2,initial_generated_weapons(GeneratedWeapon.STAFF),ArmourLoadout(),
            defence=2,talents=(lady(free=True),),oath_context=lady_context(prebattle=True))
        source=replace(source,enemies=(target.participant('minion1'),*source.enemies[1:]))
        result=self.execute(source,[1,10])
        self.assertFalse(cleaving_wound_triggers(result.state))
        self.assertFalse(any(type(s.proof) is PcCleavingStartProof for s in result.steps))

    def test_actual_near_miss_is_completed_before_deciding_that_no_wave_exists(self):
        from towr.domain.pc_melee_models import PcFatePolicy,PcNearMissPolicy
        source=npc_source()
        first=replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,near_miss_policy=PcNearMissPolicy(1,0))
        source=replace(source,party=(first,source.party[1]))
        result=self.execute(source,[10]*4+[1]*3+[10,1,1])
        self.assertEqual(len(result.state.participant('pc1').injury.wounds),0)
        self.assertEqual(len(result.state.participant('pc1').fate.burns),1)
        self.assertFalse(cleaving_wound_triggers(result.state))

    def test_two_held_swords_are_not_a_two_handed_weapon(self):
        from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
        source=pc_source(PcMeleeWeapon.SWORD)
        member=replace(source.party[0],combat_equipment=(
            PcWeaponItem('left',PcMeleeWeapon.SWORD,PcItemLocation.HELD,PcWeaponHand.LEFT),
            PcWeaponItem('right',PcMeleeWeapon.SWORD,PcItemLocation.HELD,PcWeaponHand.RIGHT)))
        result=self.execute(replace(source,party=(member,)),[1,10,10])
        self.assertFalse(cleaving_wound_triggers(result.state))

    def test_two_hand_shooting_counts_primary_and_immediate_secondary_weapon_wounds(self):
        from tests.integration.test_pc_battlefield_blunderbuss import scene,FirstMissesThenOnes
        source=scene(npc_weapons=(GeneratedWeapon.STAFF,)*3,pc_shooters=True)
        second=replace(source.party[1],pc=replace(source.party[1].pc,strength=5),
            talents=(paid_talent(TalentId.CLEAVING_BLOW),))
        source=replace(source,party=(source.party[0],second))
        result=run_pc_melee_scenario(source,FirstMissesThenOnes())
        self.assertIsNone(result.unsupported)
        triggers=cleaving_wound_triggers(result.state)
        self.assertEqual(len(triggers),2)
        self.assertEqual({t.wounded_target_id for t in triggers},{'minion2','minion3'})
        starts=[s.proof for s in result.steps if type(s.proof) is PcCleavingStartProof]
        self.assertEqual(tuple(s.trigger for s in starts),triggers)
        self.assertEqual(sum(type(s.proof) is PcCleavingEndProof for s in result.steps),2)
        self.assertTrue(all(not s.target_ids for s in starts))
        self.assertEqual(result.executed_actions,2)

    def test_close_range_is_centred_on_owner_not_the_primary_shooting_target(self):
        from tests.integration.test_pc_battlefield_blunderbuss import scene,FirstMissesThenOnes
        source=scene(npc_weapons=(GeneratedWeapon.STAFF,)*3,pc_shooters=True)
        first=replace(source.party[0],pc=replace(source.party[0].pc,strength=5),
            talents=(paid_talent(TalentId.CLEAVING_BLOW),))
        source=replace(source,party=(first,source.party[1]))
        result=run_pc_melee_scenario(source,FirstMissesThenOnes())
        start=next(s.proof for s in result.steps if type(s.proof) is PcCleavingStartProof)
        self.assertEqual(start.target_ids,())
        from towr.domain.pc_blunderbuss_models import PcBlunderbussTargetProof
        self.assertEqual(tuple(s.proof.request.target_id for s in result.steps
            if type(s.proof) is PcBlunderbussTargetProof)[:2],('minion2','minion3'))

    def test_actual_second_wave_wound_applies_brewguard_focus_to_its_real_owner(self):
        from towr.domain.pc_npc_catalog import create_pc_book_npc,PcBookNpcProfile
        from towr.domain.pc_npc_distraction_models import PcNpcCleavingDistractionSource
        source=make_pc_melee_party_scenario(pc_count=2,enemy_count=3,max_rounds=1)
        party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.GREATAXE,
            weapon_skill=1,strength=5,toughness=20),initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=initial_weapon_items(PcMeleeWeapon.GREATAXE,PcTwoHandedGrip.BOTH),
            talents=(paid_talent(TalentId.CLEAVING_BLOW),)) for m in source.party)
        guard=create_pc_book_npc(PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,'minion3')
        source=replace(source,party=party,enemies=(*source.enemies[:2],guard),
            facts=replace(source.facts,outnumbering_bonus_approved=False))
        result=self.execute(source,[1,10,10]*2)
        cause,=result.state.npc_distractions
        self.assertIs(type(cause),PcNpcCleavingDistractionSource)
        self.assertEqual((cause.actor_id,cause.focus_actor_id),('minion3','pc2'))
        self.assertEqual(result.state.enemy('minion3').state.injury.wounds,1)
