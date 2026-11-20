"""Prepared role/queue projection with genuine K1 actions, no AI journal claim."""
from copy import copy
from dataclasses import replace
from unittest import TestCase, main

from tests.support.pc_companion_attack_views import prepared_companion_attack
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.domain.injury_models import MinionStaggerDefeatOutcome
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_companion_attack_models import companion_attack_pending_owner
from towr.domain.pc_companion_effect_models import companion_profile_wound_injury
from towr.domain.pc_melee_result_models import PcAttackProof, PcAttackerStaggerProof, PcProfileWoundProof, PcMinionStaggerDefeatProof, pc_melee_action_id, prepare_pc_weapon_kernel
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
from towr.domain._pc_melee_projection import _kernel_impact_updates
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection


def attack(view,actor,target,values,*,unarmed=False):
    identifier=pc_melee_action_id(view,actor)
    if unarmed:
        from towr.domain.pc_actor_models import pc_actor_inventory
        from towr.domain.weapon_use_models import build_weapon_use
        intent=build_pc_explicit_attack_weapon_intent(view,actor,target,identifier,
            weapon_use=build_weapon_use(actor,pc_actor_inventory(view,actor),None))
    else:
        intent=build_pc_explicit_attack_weapon_intent(view,actor,target,identifier)
    kernel,protection=prepare_pc_weapon_kernel(view,intent,identifier)
    request=AttackActionExecutionRequest(identifier+':execute',view.round_state,actor,target,1,kernel)
    rng=ScriptedD10(values)
    result=execute_attack_action(request,rng)
    rng.assert_exhausted()
    proof=PcAttackProof(request,prepare_protection(protection),result,None,None,weapon_intent=intent)
    pc_actor=actor if actor in view.source.pc_activation_order else None
    member=None if pc_actor is None else view.participant(pc_actor)
    updates=_kernel_impact_updates(view,request,result.resolution,pc_actor,
        None if member is None else member.fate,None if member is None else member.injury)
    following=copy(view)
    for key,value in updates.items(): setattr(following,key,value)
    following.round_state=result.state
    following.history=(*view.history,proof)
    return following,proof


class CompanionAttackProjectionTests(TestCase):
    def test_actual_wound_updates_only_the_correct_npc_body_on_both_sides(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                before,actor,target=prepared_companion_attack(npc_actor=npc,kind=CombatMount.DEMIGRYPH)
                after,proof=attack(before,actor,target,[1]*3+[10]*4)
                self.assertEqual(pc_actor_injury(after,target).wounds,1)
                self.assertEqual(after.party,before.party)
                self.assertEqual(after.enemies,before.enemies)
                self.assertEqual(after.pending_actor_id,target)
                self.assertEqual(companion_attack_pending_owner(after),target)
                change=proof.execution.resolution.profile_wound.state_change
                self.assertTrue(companion_profile_wound_injury(after,target,change).conditions.has(Condition.DRAINED))
                forged=copy(after); forged.pending_actor_id=actor
                self.assertIsNone(companion_attack_pending_owner(forged))
                forged=copy(after); forged.pending=(replace(change,current_wounds=2),)
                self.assertIsNone(companion_attack_pending_owner(forged))

    def test_missed_npc_attack_owns_its_stagger_queue_without_any_pc_fate(self):
        before,actor,target=prepared_companion_attack()
        after,proof=attack(before,actor,target,[10]*3+[1]*4)
        self.assertEqual(after.companions,before.companions)
        self.assertEqual(after.party,before.party)
        self.assertEqual(after.pending_actor_id,actor)
        self.assertEqual(companion_attack_pending_owner(after),actor)
        self.assertFalse(pc_actor_injury(after,actor).conditions.has(Condition.STAGGERED))
        acknowledgement=PcAttackerStaggerProof(after.pending[0])
        consumed=copy(after); consumed.history=(*after.history,acknowledgement); consumed.pending=()
        self.assertIsNone(companion_attack_pending_owner(consumed))
        self.assertIsNone(proof.fate_decline)
        self.assertIsNone(proof.glorious)

    def test_repeated_stagger_destroys_only_the_undead_body_without_a_wound(self):
        before,actor,target=prepared_companion_attack(kind=CombatMount.SKELETAL_STEED,staggered=True,npc_strength=1)
        after,proof=attack(before,actor,target,[1,10,10]+[10]*4)
        result=proof.execution.resolution
        self.assertIs(result.minion_stagger_defeat.cause.outcome,MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual(pc_actor_injury(after,target).wounds,0)
        self.assertTrue(pc_actor_injury(after,target).defeated)
        self.assertIsNone(result.profile_wound)
        self.assertEqual(after.party,before.party)
        self.assertEqual(after.enemies,before.enemies)
        self.assertEqual(companion_attack_pending_owner(after),target)
        forged=copy(after)
        forged.history=(*after.history,PcMinionStaggerDefeatProof(after.pending[0]),
            PcMinionStaggerDefeatProof(after.pending[0]))
        self.assertIsNone(companion_attack_pending_owner(forged))

    def test_immediate_bash_uses_its_real_brawn_grant_without_pc_fate_or_another_slot(self):
        from tests.unit.test_bash_attack_execution import npc_source
        from towr.domain.pc_battlefield_models import PcBattlefieldSpec
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
        from towr.domain.pc_bash_attack_models import expected_bash_decision, build_pc_bash_strike
        from towr.engine.pc_melee_runner import _execute_immediate_strike, _Decisions
        source=npc_source()
        pc=replace(source.party[0],mount=CombatMount.HORSE,policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        source=replace(source,party=(pc,),battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG),
            facts=replace(source.facts,unmounted=False,can_leave_zone=True))
        view,actor,target=prepared_companion_attack(source=source)
        staged,parent=attack(view,actor,target,[1]*5+[10]*4,unarmed=True)
        self.assertTrue(pc_actor_injury(staged,target).conditions.has(Condition.STAGGERED))
        decision=expected_bash_decision(staged)
        self.assertIsNotNone(decision.selection)
        staged.history=(*staged.history,decision)
        request,protection=build_pc_bash_strike(staged)
        rng=ScriptedD10([1]+[10]*4)
        proof=_execute_immediate_strike(staged,request,protection,rng,_Decisions())
        rng.assert_exhausted()
        self.assertIsNone(proof.fate_decline)
        self.assertIsNone(proof.glorious)
        self.assertIsNotNone(proof.resolution.profile_wound)
        self.assertEqual(proof.request.source_round,parent.execution.state)
        self.assertEqual(proof.execution.state,parent.execution.state)
        self.assertEqual(len(proof.execution.state.active_turn.action_slots),1)


if __name__=='__main__': main()
