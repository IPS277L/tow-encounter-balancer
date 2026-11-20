"""Original allied NPCs retain actual role, side, health and Test sources."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedRangedFacts
from towr.domain.injury_models import CharacterInjuryState,ProfileInjuryState,WoundEntryId
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleePolicy,PcHelpPolicy,PcHelpTarget,PcMeleeWeapon
from towr.domain.pc_melee_result_models import (PcAttackProof,PcHelpProof,PcMeleeStep,PcMeleeOutcome,
    PcFateDecline,PcWoundCompletionProof,initial_pc_melee_state,pc_melee_action_id)
from towr.domain.pc_actor_models import pc_actor_side,pc_actor_injury,pc_opponent_ids
from towr.domain.pc_npc_champion_models import npc_champion_body
from towr.domain.pc_medical_models import (PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,
    PcMedicalSuppressionProof,build_medical_treatment,complete_medical_treatment,
    expected_medical_treatment_application,expected_medical_suppression,complete_medical_suppression)
from towr.domain.pc_medical_tactics import expected_medical_intent
from towr.domain.pc_medical_equipment_models import expected_medical_preparation
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.talent_catalog import TalentId
from towr.domain.weapon_inventory_models import WeaponItemLocation,WeaponGrip,WeaponItemSource
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import (CombatSide,CombatActionKind,CombatTurnStartRequest,
    CombatActionDeclaration,CombatActionSlotRequest,ActionSlotGrant)
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot
from towr.rules.test_resolution import resolve_test
from towr.rules.recover_resolution import apply_recover_wound_treatment
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def ally_npc(*,champion=True,doctor=False,weapon=GeneratedWeapon.STAFF,shield=False):
    changes={}
    if doctor:
        changes=dict(reason=3,recall=5,initiative=3,dexterity=5,brawn=4,
            medical=MedicalPreparationFacts(True,True,False),talents=(paid_talent(TalentId.COMBAT_SURGEON),),
            tools=(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,2,WeaponItemLocation.HELD,WeaponGrip.BOTH),))
    weapons=((WeaponItemSource('staff',WeaponKind.STAFF,WeaponItemLocation.CARRIED,None),)
        if doctor else initial_generated_weapons(weapon))
    return GeneratedNpc(2,3,3,2,4,4,weapons,ArmourLoadout(shield=ShieldKind.SHIELD if shield else None),defence=4,
        injury_policy=TargetInjuryPolicy.CHAMPION if champion else TargetInjuryPolicy.MINION,
        endurance=4 if champion else None,**changes)


def allied_source(*,ally=None,rounds=1,enemy_count=1,ally_first=False):
    source=make_pc_melee_scenario(max_rounds=rounds,enemy_count=enemy_count)
    ally=(ally_npc() if ally is None else ally).participant('ally',side=CombatSide.PLAYERS_AND_ALLIES)
    decisions=tuple(MinionDefeatDecision('ally',enemy.state.actor_id,NpcDefeatDisposition.KNOCKED_OUT,True)
        for enemy in source.enemies if enemy.definition.injury_policy is not TargetInjuryPolicy.CHAMPION)
    if ally.definition.injury_policy is not TargetInjuryPolicy.CHAMPION:
        decisions+=tuple(MinionDefeatDecision(enemy.state.actor_id,'ally',NpcDefeatDisposition.KNOCKED_OUT,True)
            for enemy in source.enemies)
    enemies=tuple(replace(enemy,definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0],skill=Skill.ATHLETICS),))) for enemy in source.enemies)
    return replace(source,enemies=enemies,npc_allies=(ally,),enemy_target_priority=('ally','pc'),
        player_side_activation_order=('ally','pc') if ally_first else ('pc','ally'),
        npc_defeat_decisions=decisions,facts=replace(source.facts,outnumbering_bonus_approved=False))


def add_boundary_wound(state,target,*,entry=WoundEntryId.INTERNAL_INJURY,total=14):
    """A real fixed-entry clinical boundary, without claiming an invented Attack."""
    from towr.domain.injury_models import CharacterWoundRequest,CharacterWoundType,FixedWoundSelection
    from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleRollRequest,CharacterWoundLifecycleCompletionRequest
    from towr.rules.wound_lifecycle_resolution import roll_character_wound_lifecycle,complete_character_wound_lifecycle
    is_pc=target in state.source.pc_activation_order
    injury=pc_actor_injury(state,target)
    daily=state.participant(target).daily_wounds if is_pc else npc_champion_body(state,target).daily_wounds
    roll=roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest('boundary:wound',target,
        CharacterWoundRequest('boundary:wound:roll',injury,CharacterWoundType.PLAYER if is_pc else CharacterWoundType.CHAMPION,
            fixed_entry=FixedWoundSelection(entry,total,'gm:clinical-boundary'))),SequenceRandom([]))
    completed=complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest('boundary:wound:complete',
        roll,roll.wound_result.state,daily,daily_registration_id='boundary:wound:daily'))
    if is_pc:
        return replace(state,party=tuple(replace(member,injury=completed.state,daily_wounds=completed.daily_wounds)
            if member.actor_id==target else member for member in state.party),history=(PcWoundCompletionProof(completed,None),))
    return replace(state,enemies=tuple(replace(enemy,state=replace(enemy.state,injury=completed.state))
        if enemy.state.actor_id==target else enemy for enemy in state.enemies),
        npc_champions=tuple(replace(row,daily_wounds=completed.daily_wounds) if row.actor_id==target else row
            for row in state.npc_champions),history=(PcWoundCompletionProof(completed,None),))


def treat_boundary(state,doctor,target):
    clock=start_combat_turn(CombatTurnStartRequest(pc_melee_action_id(state,doctor)+':start',state.round_state,doctor)).state
    state=replace(state,round_state=clock)
    # Exercise the legal clinical action, independently of whether bounded
    # automatic advice prefers it over this fixture's available Attack.
    from towr.domain.pc_medical_tactics import medical_actions,PcMedicalIntentProof,MedicalActionKind
    choice=next(choice for choice in medical_actions(state,doctor)
        if choice.target_id==target and choice.kind is MedicalActionKind.TREATMENT)
    intent=PcMedicalIntentProof(doctor,pc_melee_action_id(state,doctor),choice)
    state=PcMeleeStep(state,intent).state
    equipment=expected_medical_preparation(state)
    if equipment is not None:state=PcMeleeStep(state,equipment).state
    reserved=reserve_combat_action_slot(CombatActionSlotRequest(pc_melee_action_id(state,doctor)+':reserve',
        state.round_state,doctor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD))
    state=PcMeleeStep(state,reserved).state
    request=build_medical_treatment(state,target,1)
    treatment=PcMedicalTreatmentProof(request,complete_medical_treatment(request))
    state=PcMeleeStep(state,treatment).state
    state=PcMeleeStep(state,PcMedicalTreatmentApplicationProof(
        apply_recover_wound_treatment(expected_medical_treatment_application(state)))).state
    suppression=expected_medical_suppression(state)
    test=resolve_test(suppression.recall_test,SequenceRandom([1]*12))
    decline=(PcFateDecline(doctor,suppression.recall_test.id,'test',state.source.participant(doctor).fate_policy)
        if doctor in state.source.pc_activation_order else None)
    proof=PcMedicalSuppressionProof(suppression,complete_medical_suppression(suppression,test),decline)
    return PcMeleeStep(state,proof),treatment


class AlliedNpcNativeTests(unittest.TestCase):
    def run_and_replay(self,source,values):
        result=run_pc_melee_scenario(source,SequenceRandom([*values,*([10]*1000)]))
        self.assertIsNone(result.unsupported)
        self.assertEqual(replace(result),result)
        state=initial_pc_melee_state(source)
        for step in result.steps:state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        return result

    def test_actual_allied_champion_wound_and_npc_pair_have_no_fate(self):
        result=self.run_and_replay(allied_source(),[10]*3+[1]*2+[10]*2+[1]*2+[1]*2+[10]*2+[1])
        attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof]
        self.assertEqual([(p.request.actor_id,p.request.target_id) for p in attacks],
            [('pc','minion1'),('ally','minion1'),('minion1','ally')])
        for proof in attacks[1:]:self.assertIsNone(proof.fate_decline);self.assertIsNone(proof.glorious)
        body=npc_champion_body(result.state,'ally')
        self.assertEqual([w.table_total for w in body.injury.wounds],[1])
        self.assertEqual(body.daily_wounds.wound_count,1)
        self.assertFalse(hasattr(body,'fate'))
        self.assertIs(pc_actor_side(result.state,'ally'),CombatSide.PLAYERS_AND_ALLIES)
        self.assertEqual(pc_opponent_ids(result.state,'ally'),('minion1',))

    def test_player_order_is_explicit_and_allied_minion_keeps_profile_health(self):
        source=allied_source(ally=ally_npc(champion=False),ally_first=True,rounds=2)
        result=self.run_and_replay(source,[])
        from towr.domain.turn_models import CombatTurnStartResult
        turns=[step.proof.turn.actor_id for step in result.steps if type(step.proof) is CombatTurnStartResult]
        self.assertEqual(turns,['ally','pc','minion1']*2)
        self.assertIs(type(result.state.enemy('ally').state.injury),ProfileInjuryState)
        self.assertEqual(result.started_rounds,2)

    def test_hostile_npc_can_defeat_allied_minion_without_defeating_live_pc(self):
        source=allied_source(ally=ally_npc(champion=False))
        result=self.run_and_replay(source,[10]*3+[1]*2+[10]*2+[1]*2+[1]*2+[10]*2)
        self.assertTrue(result.state.enemy('ally').state.injury.defeated)
        self.assertFalse(result.state.participant('pc').injury.dead)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        from towr.domain.pc_melee_result_models import PcProfileWoundProof
        acknowledgement=next(step.proof for step in result.steps if type(step.proof) is PcProfileWoundProof
            and step.proof.decision is not None and step.proof.decision.target_id=='ally')
        self.assertEqual(acknowledgement.decision.attacker_id,'minion1')
        self.assertEqual(acknowledgement.decision.disposition,NpcDefeatDisposition.KNOCKED_OUT)

    def test_explicit_pc_help_applies_to_allied_npc_exact_attack(self):
        source=allied_source()
        member=replace(source.party[0],policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('ally',PcHelpTarget.ATTACK,Skill.MELEE))
        result=self.run_and_replay(replace(source,party=(member,)),[])
        helped=next(step.proof for step in result.steps if type(step.proof) is PcHelpProof)
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='ally')
        self.assertEqual(helped.request.beneficiary_id,'ally')
        self.assertEqual(len(attack.help_applications),1)
        self.assertEqual(attack.help_applications[0].source_request.help,helped.execution)
        self.assertIsNone(attack.fate_decline)

    def test_allied_npc_ordinary_help_reaches_pc_future_test_without_fate(self):
        helper=GeneratedNpc(1,1,20,1,2,2,initial_generated_weapons(GeneratedWeapon.STAFF),ArmourLoadout(),
            defence=2,fellowship=4,talents=(paid_talent(TalentId.ALLIES_IN_ARMS),))
        source=allied_source(ally=helper,ally_first=True,rounds=2)
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,weapon_skill=6,melee=6,
            defence=6,strength=1,toughness=20)),))
        result=self.run_and_replay(source,[])
        helped=next(step.proof for step in result.steps if type(step.proof) is PcHelpProof
            and step.proof.request.actor_id=='ally')
        self.assertEqual(helped.request.beneficiary_id,'pc')
        self.assertIsNone(helped.fate_decline);self.assertIsNone(helped.glorious)
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.kernel_request.attack.attacker_test.id==helped.execution.bonus.beneficiary_test_id)
        self.assertEqual(attack.help_applications[0].source_request.help,helped.execution)

    def test_allied_champion_help_preserves_actual_next_test_grim(self):
        from towr.domain.pc_npc_normal_help_models import npc_help_test
        from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
        from towr.domain.test_models import TestQuality
        state=add_boundary_wound(initial_pc_melee_state(allied_source()),'ally',
            entry=WoundEntryId.CRUSHED_RIB,total=10)
        test=npc_help_test(state,'ally','boundary:help-test',Skill.MELEE)
        self.assertTrue(any(mod.rule_id==CRUSHED_RIB_TEST_RULE_ID and mod.quality is TestQuality.GRIM
            for mod in test.quality_modifiers))

    def test_automatic_pc_help_can_choose_allied_npc_and_bind_its_test(self):
        helper_ally=replace(ally_npc(),weapon_skill=6,melee=6,strength=1,toughness=20)
        source=allied_source(ally=helper_ally,rounds=2)
        member=source.party[0]
        member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            pc=replace(member.pc,weapon_skill=1,melee=2,defence=2,strength=1,toughness=20,fellowship=4),
            talents=(paid_talent(TalentId.ALLIES_IN_ARMS),))
        from towr.domain.attack_models import ResilienceProfile
        enemy=source.enemies[0];resilience=ResilienceProfile(20)
        enemy=replace(enemy,definition=replace(enemy.definition,resilience=resilience),
            state=replace(enemy.state,current_resilience=resilience))
        source=replace(source,party=(member,),enemies=(enemy,))
        result=self.run_and_replay(source,[])
        helped=next(step.proof for step in result.steps if type(step.proof) is PcHelpProof
            and step.proof.request.actor_id=='pc' and step.proof.request.beneficiary_id=='ally')
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.kernel_request.attack.attacker_test.id==helped.execution.bonus.beneficiary_test_id)
        self.assertEqual(attack.help_applications[0].source_request.help,helped.execution)
        self.assertIsNone(attack.fate_decline)

    def test_allied_npc_doctor_treats_pc_without_gaining_or_spending_fate(self):
        source=allied_source(ally=ally_npc(doctor=True,champion=False),ally_first=True)
        state=add_boundary_wound(initial_pc_melee_state(source),'pc')
        original=state.participant('pc').fate
        step,treatment=treat_boundary(state,'ally','pc')
        self.assertTrue(step.state.participant('pc').injury.wounds[0].treated)
        self.assertFalse(step.state.participant('pc').injury.wounds[0].healed)
        self.assertEqual(step.state.participant('pc').fate,original)
        self.assertIsNone(treatment.decline);self.assertIsNone(step.proof.decline)
        self.assertEqual(step.proof.result.suppression.target_id,'pc')

    def test_pc_doctor_treats_allied_champion_as_character_patient(self):
        source=allied_source();member=source.party[0]
        pc=replace(member.pc,weapon=PcMeleeWeapon.UNARMED,brawn=4,reason=3,recall=5,initiative=3,dexterity=5,
            medical=MedicalPreparationFacts(True,True,False),
            tools=(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,2,WeaponItemLocation.HELD,WeaponGrip.BOTH),))
        member=replace(member,pc=pc,policy=PcMeleePolicy.AUTOMATIC_COMBAT,initial_weapon_hand=None,combat_equipment=(),
            talents=(paid_talent(TalentId.COMBAT_SURGEON),))
        state=add_boundary_wound(initial_pc_melee_state(replace(source,party=(member,))),'ally')
        step,_=treat_boundary(state,'pc','ally')
        injury=step.state.enemy('ally').state.injury
        self.assertIs(type(injury),CharacterInjuryState)
        self.assertTrue(injury.wounds[0].treated);self.assertFalse(injury.wounds[0].healed)
        self.assertEqual(step.proof.result.suppression.target_id,'ally')

    def test_all_pc_dead_is_defeat_while_allied_npc_survives(self):
        source=allied_source(enemy_count=3)
        member=source.party[0]
        from towr.domain.fate_models import FateSessionState
        member=replace(member,pc=replace(member.pc,weapon_skill=1,melee=2,defence=2,toughness=1,agility=1,
            athletics=2,endurance=2),fate=FateSessionState('session','pc',0,0))
        source=replace(source,party=(member,),enemy_target_priority=('pc','ally'))
        values=[10]+[1]*2+[10]*2+[1]*2+[1]*2+[10]+[1]+[1]*2+[10]+[1,1]+[1]*2+[10]+[10,10,10]
        result=self.run_and_replay(source,values)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertTrue(result.state.participant('pc').injury.dead)
        self.assertFalse(result.state.enemy('ally').state.injury.dead)

    def test_spatial_allied_npc_moves_toward_hostile_side(self):
        from towr.domain.pc_battlefield_models import PcBattlefieldSpec
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        source=allied_source(rounds=2)
        source=replace(source,party=(replace(source.party[0],policy=PcMeleePolicy.AUTOMATIC_COMBAT),),
            facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))
        result=self.run_and_replay(source,[])
        spatial=result.state.battlefield.spatial
        self.assertEqual(set(p.entity_id for p in spatial.placements),{'pc','ally','minion1'})
        self.assertTrue(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id=='ally'
            and step.proof.request.target_id=='minion1' for step in result.steps))

    def test_shooting_uses_allied_npc_shield_protection_without_pc_fate(self):
        source=allied_source(ally=ally_npc(weapon=GeneratedWeapon.SWORD,shield=True))
        gunner=GeneratedNpc(2,3,3,2,4,4,initial_generated_weapons(GeneratedWeapon.PISTOL),ArmourLoadout(),
            defence=4,initiative=3,dexterity=4,ranged=GeneratedRangedFacts(3,5,True,True,True))
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        source=replace(source,enemies=(gunner.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(gunner,'minion1'),))
        result=self.run_and_replay(source,[])
        shot=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        self.assertEqual(shot.request.target_id,'ally')
        self.assertIsNotNone(shot.npc_ranged_shot)
        self.assertIsNone(shot.fate_decline);self.assertIsNone(shot.glorious)
        self.assertTrue(shot.protection.source_request.defender_holds_shield)


if __name__=='__main__':unittest.main()
