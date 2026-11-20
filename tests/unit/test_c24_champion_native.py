"""Real NPC Champion table Wounds and anatomical sources, without PC Fate."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario,make_pc_melee_party_scenario
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.pc_melee_result_models import (PcMeleeStep,PcWoundCompletionProof,
    PcEnduranceProof,PcIncapacitatedTurnEndProof,initial_pc_melee_state)
from towr.domain.pc_npc_champion_models import npc_champion_body,PcNpcChampionRecoverProof
from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import PcBodyFactKind
from towr.domain.weapon_inventory_models import WeaponItemLocation
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def champion_scenario(*,party_size=1,rounds=1,weapon=GeneratedWeapon.STAFF,shield=False):
    source=(make_pc_melee_scenario(max_rounds=rounds) if party_size==1 else
        make_pc_melee_party_scenario(pc_count=party_size,enemy_count=1,max_rounds=rounds))
    npc=GeneratedNpc(2,3,3,2,4,4,initial_generated_weapons(weapon),
        ArmourLoadout(shield=ShieldKind.SHIELD if shield else None),
        defence=4,injury_policy=TargetInjuryPolicy.CHAMPION,endurance=4)
    return replace(source,enemies=(npc.participant('minion1'),))


class ChampionNativeTests(unittest.TestCase):
    def run_script(self,source,values):
        result=run_pc_melee_scenario(source,SequenceRandom([*values,*([10]*800)]))
        self.assertIsNone(result.unsupported)
        # Each result replays all proofs from the original complete source.
        self.assertEqual(replace(result),result)
        return result

    def test_actual_character_wound_daily_receipt_and_no_fate(self):
        result=self.run_script(champion_scenario(),[1,1,1,10,10,1])
        state=result.state
        body=npc_champion_body(state,'minion1')
        self.assertIs(type(body.injury),CharacterInjuryState)
        self.assertEqual([w.table_total for w in body.injury.wounds],[1])
        self.assertEqual(body.daily_wounds.wound_count,1)
        self.assertFalse(body.injury.dead)
        self.assertFalse(hasattr(body,'fate'))
        completion=next(s.proof for s in result.steps if type(s.proof) is PcWoundCompletionProof)
        self.assertIsNone(completion.fate_decline)
        self.assertIsNone(completion.completion.fate_burn)
        self.assertFalse(completion.completion.source_request.roll.near_miss_eligible)

    def test_real_endurance_followup_has_no_fate(self):
        result=self.run_script(champion_scenario(),[1,1,1,10,10,5])
        proofs=[s.proof for s in result.steps if type(s.proof) is PcEnduranceProof]
        self.assertEqual(len(proofs),1)
        self.assertIsNone(proofs[0].fate_decline)
        self.assertIsNone(proofs[0].glorious)
        body=npc_champion_body(result.state,'minion1')
        self.assertEqual(body.injury.wounds[0].table_total,5)

    def test_foreign_or_repeated_completion_cannot_replay(self):
        result=self.run_script(champion_scenario(),[1,1,1,10,10,1])
        step=next(s for s in result.steps if type(s.proof) is PcWoundCompletionProof)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(step.state,step.proof)
        foreign=replace(step.proof.completion.source_request.roll.source_request,target_id='foreign')
        with self.assertRaises((TypeError,ValueError)):
            request=replace(step.proof.completion.source_request,
                roll=replace(step.proof.completion.source_request.roll,source_request=foreign))
            completion=replace(step.proof.completion,source_request=request)
            PcMeleeStep(step.source,replace(step.proof,completion=completion))

    def test_metadata_bank_cannot_disappear_or_change_owner(self):
        state=initial_pc_melee_state(champion_scenario())
        with self.assertRaises(ValueError): replace(state,npc_champions=())
        with self.assertRaises((TypeError,ValueError)):
            row=replace(state.npc_champions[0],actor_id='foreign')
            replace(state,npc_champions=(row,))

    def test_injured_arm_stops_two_handed_attack_and_preserves_critical_end(self):
        source=champion_scenario(party_size=2)
        result=self.run_script(source,[1]*4+[10]*2+[1]+[1]*4+[10]*2+[8,8,1])
        body=npc_champion_body(result.state,'minion1')
        self.assertEqual([w.table_total for w in body.injury.wounds],[1,16])
        self.assertTrue(any(f.kind is PcBodyFactKind.UNUSABLE_ARM for f in body.body_facts))
        self.assertTrue(any(type(s.proof) is PcNpcChampionRecoverProof for s in result.steps))
        self.assertTrue(body.injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(body.injury.dead)
        self.assertIsNotNone(result.steps[-1].proof.critical)
        self.assertIsNone(result.steps[-1].proof.critical.fate_decline)

    def test_defenceless_champion_has_real_actionless_critical_death(self):
        result=self.run_script(champion_scenario(party_size=2),
            [1]*4+[10]*2+[1]+[1]*4+[10]*2+[10,10,1])
        body=npc_champion_body(result.state,'minion1')
        self.assertEqual(body.injury.wounds[-1].table_total,20)
        self.assertTrue(body.injury.dead)
        end=result.steps[-1]
        self.assertIs(type(end.proof),PcIncapacitatedTurnEndProof)
        self.assertEqual(end.source.round_state.active_turn.action_slots,())
        self.assertIsNotNone(end.proof.critical)
        self.assertIsNone(end.proof.critical.fate_decline)
        self.assertTrue(all(i.location is WeaponItemLocation.DROPPED for i in body.weapon_inventory.items))

    def test_shield_loss_keeps_actual_physical_wound_receipt(self):
        result=self.run_script(champion_scenario(party_size=2,weapon=GeneratedWeapon.AXE,shield=True),
            [1]*4+[10]*2+[1]+[1]*4+[10]*2+[6,6,10])
        from towr.domain.pc_npc_shield_models import NpcShieldLocation
        drop=next(s.proof for s in result.steps if getattr(s.proof,'npc_shield_drop',None) is not None)
        self.assertIs(drop.npc_shield_drop.state.location,NpcShieldLocation.DROPPED)
        self.assertEqual(drop.npc_shield_drop.source.wound_sequence,2)
        self.assertEqual(drop.npc_shield_drop.actor_id,'minion1')
        from towr.domain.pc_npc_shield_models import PcNpcShieldRecoverProof
        pickup=next(s.proof for s in result.steps if type(s.proof) is PcNpcShieldRecoverProof)
        self.assertIs(result.state.npc_shields[0].location,NpcShieldLocation.HELD)
        self.assertEqual(pickup.actor_id,'minion1')
        self.assertTrue(pickup.injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_next_protection_really_uses_and_consumes_crushed_rib_grim(self):
        source=champion_scenario(party_size=3)
        values=[1]*4+[10]*2+[1]+[1]*4+[10]*2+[5,5]
        result=self.run_script(source,values)
        from towr.domain.pc_melee_result_models import PcAttackProof
        from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
        from towr.domain.test_models import TestQuality
        attacks=[s for s in result.steps if type(s.proof) is PcAttackProof]
        defence=attacks[2].proof.request.kernel_request.attack.defender_test
        self.assertTrue(any(q.rule_id==CRUSHED_RIB_TEST_RULE_ID and q.quality is TestQuality.GRIM
            for q in defence.quality_modifiers))
        from towr.domain.injury_models import WoundRestriction,WoundRestrictionEffect
        self.assertFalse(any(type(e) is WoundRestrictionEffect and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM
            for e in attacks[2].state.enemy('minion1').state.injury.active_wound_effects))

    def test_shared_champion_aim_and_reload_tests_keep_body_modifiers(self):
        from towr.domain.generated_npc_models import GeneratedRangedFacts
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        source=champion_scenario(party_size=2)
        npc=replace(source.enemies[0].definition.generated_components,
            weapons=initial_generated_weapons(GeneratedWeapon.PISTOL),
            ranged=GeneratedRangedFacts(3,4,True,True,True),initiative=3,dexterity=4,awareness=4)
        source=replace(source,enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),))
        result=self.run_script(source,[1]*4+[10]*2+[1]+[1]*4+[10]*2+[5,5])
        completed=[s for s in result.steps if type(s.proof) is PcWoundCompletionProof][-1]
        from towr.domain.pc_npc_aim_models import _awareness_test
        from towr.domain.pc_npc_ranged_models import npc_ranged_reload_test,npc_ranged_hands_available
        from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
        for test in (_awareness_test(completed.state,'minion1','pc1','probe:awareness'),
                npc_ranged_reload_test(completed.state,'minion1','probe:dexterity')):
            self.assertTrue(any(q.rule_id==CRUSHED_RIB_TEST_RULE_ID for q in test.quality_modifiers))
        self.assertTrue(npc_ranged_hands_available(completed.state,'minion1',reload=True))

    def test_actual_reload_uses_injured_other_hand_and_triggers_critical(self):
        from towr.domain.generated_npc_models import GeneratedRangedFacts
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
        source=champion_scenario(party_size=2,rounds=2)
        npc=replace(source.enemies[0].definition.generated_components,
            weapons=initial_generated_weapons(GeneratedWeapon.PISTOL),
            ranged=GeneratedRangedFacts(3,4,True,True,True),initiative=3,dexterity=4,awareness=4)
        source=replace(source,enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),))
        result=self.run_script(source,[1]*4+[10]*2+[1]+[1]*4+[10]*2+[6,6,10])
        reload=next(s for s in result.steps if type(s.proof) is PcNpcRangedReloadProof)
        self.assertFalse(reload.source.enemy('minion1').state.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(reload.state.enemy('minion1').state.injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_all_table_rows_keep_actual_character_history(self):
        for row in range(1,24):
            with self.subTest(row=row):
                count=1 if row<=10 else 2 if row<=20 else 3
                values=[]
                for index in range(count):
                    total=row if index==count-1 else index+1
                    wound_dice=([total] if index==0 else [total//2,total-total//2]
                        if index==1 else [7,7,total-14])
                    values.extend([1]*(3+int(count>1))+[10]*2+wound_dice)
                result=run_pc_melee_scenario(champion_scenario(party_size=count),
                    SequenceRandom(values+[10]*700))
                self.assertIsNone(result.unsupported)
                body=npc_champion_body(result.state,'minion1')
                self.assertEqual(body.injury.wounds[-1].table_total,row)
                self.assertTrue(all(w.effect_resolved for w in body.injury.wounds))
                self.assertEqual(body.daily_wounds.wound_count,count)

    def test_temporary_stomach_condition_expires_at_actual_champion_end(self):
        result=self.run_script(champion_scenario(),[1,1,1,10,10,6])
        completion=next(s for s in result.steps if type(s.proof) is PcWoundCompletionProof)
        self.assertTrue(completion.state.enemy('minion1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(completion.state.npc_champions[0].timed_wounds),1)
        body=npc_champion_body(result.state,'minion1')
        self.assertFalse(body.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(body.timed_wounds,())

    def test_daily_receipt_cannot_be_erased_after_actual_wound(self):
        result=self.run_script(champion_scenario(),[1,1,1,10,10,1])
        row=result.state.npc_champions[0]
        with self.assertRaises(ValueError):
            replace(result.state,npc_champions=(replace(row,daily_wounds=replace(row.daily_wounds,receipts=())),))


if __name__=='__main__': unittest.main()
