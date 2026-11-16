"""Concrete inventory boundaries and full automatic runner journals.

Prepared snapshots isolate drop/pickup/swap/hand boundaries. Native tests below
also execute actual actions and wounds, then replay every step.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_tactics_fixtures import tactical_snapshot
from towr.domain.condition_models import Condition
from towr.domain.pc_combat_equipment_models import (
    PcItemLocation,PcWeaponItem,PcWeaponInventoryState,validate_pc_weapon_inventory,
)
from towr.domain.pc_melee_models import (
    PcMeleePolicy,PcMeleeWeapon,PcWeaponHand,PcBackupWeaponPolicy,
    PcShieldLoadout,PcShieldHandConflictPolicy,PcShieldRecoveryPolicy,
)
from towr.domain.pc_tactical_models import PcTacticalChoice
from towr.domain.pc_weapon_inventory import (
    initial_pc_weapon_inventory,sync_pc_weapon_inventory,pc_weapon_inventory_view,
    pc_weapon_pickup_view,pc_weapon_pickup_member,pc_weapon_swap_hand,
    expected_pc_weapon_swap,apply_pc_weapon_swap,pending_pc_weapon_swap,pc_weapon_swap_used,
)
from towr.domain.turn_models import CombatActionKind


def participant(*,shield=False):
    member=make_pc_pistol_scenario(pc_count=1).party[0]
    items=(PcWeaponItem('gun:owned',PcMeleeWeapon.PISTOL,PcItemLocation.HELD,PcWeaponHand.LEFT),
        PcWeaponItem('sword:owned',PcMeleeWeapon.SWORD,PcItemLocation.CARRIED,None))
    return replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT),
        combat_equipment=items,shield=(PcShieldLoadout(PcWeaponHand.RIGHT,
            PcShieldHandConflictPolicy.WEAPON_FIRST,PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
            if shield else None))


def source(*,shield=False):
    scene=make_pc_pistol_scenario(pc_count=1)
    return replace(scene,party=(participant(shield=shield),))


def prepared(*,shield=False):
    return tactical_snapshot(source(shield=shield),'pc1')


def planned(state,item_id):
    return PcTacticalChoice('pc1',CombatActionKind.ATTACK,'minion1',None,1.0,'prepared:weapon',
        weapon_item_id=item_id)


class PcWeaponItemSourceTests(unittest.TestCase):
    def test_exact_item_types_and_hand_location_are_required(self):
        item=participant().combat_equipment[0]
        for changes in ({'id':True},{'weapon':'pistol'},{'location':'held'},
                {'location':PcItemLocation.CARRIED},{'hand':True},{'hand':None}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(item,**changes)
        carried=replace(item,location=PcItemLocation.CARRIED,hand=None)
        self.assertIsNone(carried.hand)
        self.assertEqual(carried.id,item.id)

    def test_inventory_has_ordered_unique_members_and_only_active_can_be_held(self):
        gun,sword=participant().combat_equipment
        for items,active in (([gun,sword],gun.id),((gun,gun),gun.id),((gun,sword),'foreign'),
                ((gun,replace(sword,location=PcItemLocation.HELD,hand=PcWeaponHand.RIGHT)),gun.id),
                ((gun,sword),sword.id)):
            with self.subTest(items=items,active=active),self.assertRaises((TypeError,ValueError)):
                PcWeaponInventoryState(items,active)

    def test_source_rederives_primary_backup_grip_and_membership(self):
        member=participant()
        self.assertEqual(initial_pc_weapon_inventory(member).items,member.combat_equipment)
        gun,sword=member.combat_equipment
        for changes in ({'combat_equipment':member.combat_equipment[::-1]},
                {'combat_equipment':(replace(gun,weapon=PcMeleeWeapon.REPEATER_PISTOL),sword)},
                {'combat_equipment':(replace(gun,hand=PcWeaponHand.RIGHT),sword)},
                {'combat_equipment':(gun,)},{'backup_weapon_policy':None},
                {'policy':PcMeleePolicy.ATTACK_OR_RECOVER_SELF},{'combat_equipment':None}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(member,**changes)


class PcWeaponInventoryBoundaryTests(unittest.TestCase):
    def test_actual_hand_drop_and_recover_sync_only_the_active_item(self):
        state=prepared();member=state.participant('pc1');source_member=state.source.party[0]
        dropped=sync_pc_weapon_inventory(member,replace(member,weapon_hand=None),source_member)
        self.assertIs(dropped.weapon_inventory.active.location,PcItemLocation.DROPPED)
        self.assertIs(dropped.weapon_inventory.items[1].location,PcItemLocation.CARRIED)
        restored=sync_pc_weapon_inventory(dropped,replace(dropped,weapon_hand=PcWeaponHand.RIGHT),source_member)
        self.assertIs(restored.weapon_inventory.active.location,PcItemLocation.HELD)
        self.assertIs(restored.weapon_inventory.active.hand,PcWeaponHand.RIGHT)
        self.assertEqual(restored.weapon_inventory.items[1],member.weapon_inventory.items[1])

    def test_carry_forecast_is_pure_and_dropped_target_requires_recover(self):
        state=prepared();member=state.participant('pc1')
        view=pc_weapon_inventory_view(state,'pc1','sword:owned')
        self.assertTrue(view.participant('pc1').using_backup_weapon)
        self.assertIs(view.participant('pc1').weapon_inventory.items[0].location,PcItemLocation.CARRIED)
        self.assertEqual(state.participant('pc1'),member)
        dropped=replace(member.weapon_inventory,items=(member.weapon_inventory.items[0],
            replace(member.weapon_inventory.items[1],location=PcItemLocation.DROPPED)))
        state=replace(state,party=(replace(member,weapon_inventory=dropped),))
        self.assertIsNone(pc_weapon_inventory_view(state,'pc1','sword:owned'))
        after=pc_weapon_pickup_view(state,'pc1','sword:owned')
        self.assertIs(after.participant('pc1').weapon_inventory.active.location,PcItemLocation.HELD)
        self.assertIs(state.participant('pc1').weapon_inventory.items[1].location,PcItemLocation.DROPPED)

    def test_swap_retains_committed_choice_and_cannot_repeat_this_turn(self):
        state=prepared();choice=planned(state,'sword:owned')
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=choice):
            proof=expected_pc_weapon_swap(state)
            after_member=apply_pc_weapon_swap(state,proof)
            after=replace(state,party=(after_member,),history=(*state.history,proof))
            self.assertEqual(pending_pc_weapon_swap(after,'pc1').intent,choice)
            self.assertIsNone(pending_pc_weapon_swap(after,'other'))
            self.assertTrue(pc_weapon_swap_used(after,'pc1'))
            self.assertIsNone(expected_pc_weapon_swap(after))
            with self.assertRaises(ValueError):apply_pc_weapon_swap(after,proof)
            from towr.domain.turn_models import CombatActionSlot,CombatActionDeclaration,ActionSlotGrant
            reserved=replace(after,round_state=replace(after.round_state,active_turn=replace(
                after.round_state.active_turn,action_slots=(CombatActionSlot(1,
                    CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD),))))
            self.assertEqual(pending_pc_weapon_swap(reserved,'pc1').intent,choice)
        self.assertIs(after_member.ranged,state.participant('pc1').ranged)
        self.assertIs(after_member.fate,state.participant('pc1').fate)
        self.assertEqual(after_member.potions,state.participant('pc1').potions)

    def test_second_turn_reverse_keeps_partial_ranged_cycle_and_actual_identity(self):
        from towr.domain.exacting_test_models import ExactingTestProgress,ExactingTestContribution
        state=prepared();member=state.participant('pc1')
        progress=ExactingTestProgress('prepared:cycle:exacting',3,
            (ExactingTestContribution('r','t','pc1',1),))
        weapon=replace(member.ranged,loaded=False,reload_cycle_id='prepared:cycle',
            reload_cycle_ids=('prepared:cycle',),exacting=progress)
        state=replace(state,party=(replace(member,ranged=weapon),))
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=planned(state,'sword:owned')):
            proof=expected_pc_weapon_swap(state);after_member=apply_pc_weapon_swap(state,proof)
        later=replace(state,round_state=replace(state.round_state,round_number=2),
            party=(after_member,),history=(*state.history,proof))
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=planned(later,'gun:owned')):
            reverse=expected_pc_weapon_swap(later);restored=apply_pc_weapon_swap(later,reverse)
        self.assertFalse(restored.using_backup_weapon)
        self.assertIs(restored.ranged,weapon)
        self.assertFalse(restored.ranged.loaded)
        self.assertEqual(restored.ranged.exacting.accumulated_successes,1)
        self.assertEqual(restored.weapon_inventory.active.id,'gun:owned')

    def test_switch_from_dropped_primary_never_stows_it_or_makes_free_return(self):
        state=prepared();member=state.participant('pc1')
        dropped=sync_pc_weapon_inventory(member,replace(member,weapon_hand=None),state.source.party[0])
        state=replace(state,party=(dropped,))
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=planned(state,'sword:owned')):
            proof=expected_pc_weapon_swap(state);after=apply_pc_weapon_swap(state,proof)
        self.assertIs(after.weapon_inventory.items[0].location,PcItemLocation.DROPPED)
        next_state=replace(state,round_state=replace(state.round_state,round_number=2),party=(after,))
        self.assertIsNone(pc_weapon_inventory_view(next_state,'pc1','gun:owned'))
        recovered=pc_weapon_pickup_member(next_state,'pc1','gun:owned')
        self.assertEqual(recovered.weapon_inventory.active.id,'gun:owned')
        self.assertIs(recovered.weapon_inventory.items[1].location,PcItemLocation.CARRIED)

    def test_actor_membership_mirror_and_inactive_drop_are_not_interchangeable(self):
        state=prepared();member=state.participant('pc1');source_member=state.source.party[0]
        for changes in ({'actor_id':'foreign'},{'using_backup_weapon':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_pc_weapon_inventory(replace(member,**changes),source_member)
        changed=replace(member.weapon_inventory,items=(member.weapon_inventory.items[0],
            replace(member.weapon_inventory.items[1],weapon=PcMeleeWeapon.AXE)))
        with self.assertRaises(ValueError):
            validate_pc_weapon_inventory(replace(member,weapon_inventory=changed),source_member)

    def test_swap_proof_rejects_foreign_action_hand_and_changed_committed_target(self):
        state=prepared();choice=planned(state,'sword:owned')
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=choice):
            proof=expected_pc_weapon_swap(state)
            wrong_hand=replace(proof.state,items=tuple(replace(item,hand=PcWeaponHand.RIGHT)
                if item.id=='sword:owned' else item for item in proof.state.items))
            for forged in (replace(proof,action_id='foreign'),replace(proof,state=wrong_hand),
                    replace(proof,intent=replace(choice,target_id='foreign-target'))):
                with self.subTest(forged=forged),self.assertRaises(ValueError):
                    apply_pc_weapon_swap(state,forged)

    def test_swap_adds_actual_other_action_critical_and_preserves_ongoing_condition(self):
        from towr.domain.injury_models import WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration
        for entry,total,restriction in ((WoundEntryId.INTERNAL_INJURY,14,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL),
                (WoundEntryId.SCARRING_STRIKE,15,WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL)):
            state=prepared();member=state.participant('pc1')
            injury=replace(member.injury,wounds=(WoundRecord(1,entry,total,(7,total-7),effect_resolved=True),),
                conditions=member.injury.conditions.with_condition(Condition.STAGGERED),
                active_wound_effects=(WoundRestrictionEffect(1,restriction,WoundEffectDuration.UNTIL_TREATED),))
            state=replace(state,party=(replace(member,injury=injury),))
            with self.subTest(entry=entry),patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=planned(state,'sword:owned')):
                proof=expected_pc_weapon_swap(state);changed=apply_pc_weapon_swap(state,proof)
                self.assertTrue(changed.injury.conditions.has(Condition.CRITICALLY_INJURED))
                self.assertTrue(changed.injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(changed.fate,member.fate)
                self.assertEqual(changed.ranged,member.ranged)

    def test_recover_stow_price_occurs_only_when_another_weapon_was_actually_held(self):
        from towr.domain.injury_models import WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration
        state=prepared();member=state.participant('pc1')
        injury=replace(member.injury,wounds=(WoundRecord(1,WoundEntryId.INTERNAL_INJURY,14,(7,7),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),))
        inventory=replace(member.weapon_inventory,items=(member.weapon_inventory.items[0],
            replace(member.weapon_inventory.items[1],location=PcItemLocation.DROPPED)))
        member=replace(member,injury=injury,weapon_inventory=inventory)
        held_state=replace(state,party=(member,))
        picked=pc_weapon_pickup_member(held_state,'pc1','sword:owned')
        self.assertTrue(picked.injury.conditions.has(Condition.CRITICALLY_INJURED))
        empty=sync_pc_weapon_inventory(member,replace(member,weapon_hand=None),state.source.party[0])
        picked=pc_weapon_pickup_member(replace(state,party=(empty,)),'pc1','sword:owned')
        self.assertFalse(picked.injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_injured_primary_hand_prefers_healthy_shield_hand_before_a_critical_swap(self):
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.injury_models import WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration
        state=prepared(shield=True);member=state.participant('pc1')
        injury=replace(member.injury,wounds=(WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),))
        member=replace(member,injury=injury,body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),))
        state=replace(state,party=(member,))
        self.assertIs(pc_weapon_swap_hand(state,'pc1','sword:owned'),PcWeaponHand.RIGHT)
        view=pc_weapon_inventory_view(state,'pc1','sword:owned')
        self.assertIs(view.participant('pc1').weapon_hand,PcWeaponHand.RIGHT)
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=planned(state,'sword:owned')):
            self.assertIsNone(expected_pc_weapon_swap(state))
        self.assertEqual(state.participant('pc1').shield,member.shield)


class PcWeaponInventoryNativeTests(unittest.TestCase):
    def execute(self,scene,values):
        from tests.support.pc_melee_scripted import ScriptedD10
        from towr.domain.pc_melee_result_models import initial_pc_melee_state
        from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
        rng=ScriptedD10(values)
        result=run_pc_melee_scenario(scene,rng)
        rng.assert_exhausted()
        replay=initial_pc_melee_state(scene)
        for step in result.steps:
            replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)
        return result

    def test_actual_controller_can_switch_before_first_attack_without_spending_the_loaded_gun(self):
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_melee_result_models import PcAttackProof
        scene=source();member=scene.party[0]
        # A poor shot makes the carried Sword preferable even while loaded.
        member=replace(member,pc=replace(member.pc,ranged=replace(member.pc.ranged,shooting=1)))
        scene=replace(scene,party=(member,))
        result=self.execute(scene,[10]*50)
        swaps=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertEqual(len(swaps),1)
        swap=swaps[0]
        self.assertEqual((swap.source.round_state.round_number,swap.proof.previous.active_item_id,
            swap.proof.state.active_item_id),(1,'gun:owned','sword:owned'))
        self.assertEqual(swap.source.round_state,swap.state.round_state)
        self.assertTrue(result.state.party[0].ranged.loaded)
        self.assertEqual(result.executed_actions,10)
        self.assertFalse(any(step.proof.ranged_shot is not None for step in result.steps
            if type(step.proof) is PcAttackProof))
        self.assertIs(result.state.party[0].weapon_inventory.items[0].location,PcItemLocation.CARRIED)

    def test_actual_controller_reverses_after_target_changes_and_keeps_the_same_gun(self):
        from towr.domain.attack_models import ResilienceProfile
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_melee_result_models import PcAttackProof
        scene=make_pc_pistol_scenario(pc_count=1,enemy_count=2,max_rounds=2)
        member=participant()
        member=replace(member,pc=replace(member.pc,toughness=20),
            target_priority=scene.party[0].target_priority,defeat_decisions=scene.party[0].defeat_decisions)
        enemies=[]
        for index,enemy in enumerate(scene.enemies):
            resilience=ResilienceProfile(1,0 if index==0 else 10)
            definition_id=f'authored:inventory-target:{index}'
            enemies.append(replace(enemy,definition=replace(enemy.definition,id=definition_id,resilience=resilience),
                state=replace(enemy.state,definition_id=definition_id,current_resilience=resilience)))
        scene=replace(scene,party=(member,),enemies=tuple(enemies))
        result=self.execute(scene,[1,1,1,10,10,1,1,10,10,10,10,1,1,1,10,10])
        swaps=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertEqual([(s.proof.previous.active_item_id,s.proof.state.active_item_id) for s in swaps],
            [('gun:owned','sword:owned'),('sword:owned','gun:owned')])
        self.assertEqual([s.source.round_state.round_number for s in swaps],[1,2])
        self.assertEqual(swaps[1].source.party[0].ranged,swaps[1].state.party[0].ranged)
        self.assertTrue(swaps[1].state.party[0].ranged.loaded)
        shots=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.ranged_shot is not None)
        self.assertEqual(len(shots),1)
        self.assertEqual(shots[0].source.party[0].weapon_inventory.active_item_id,'gun:owned')
        self.assertFalse(result.state.party[0].ranged.loaded)
        self.assertEqual(result.executed_actions,3)

    def test_actual_shield_release_reload_recover_shoot_uses_distinct_actions(self):
        from towr.domain.test_models import InlineProfile
        from towr.domain.attack_models import DamageProfile
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        from towr.domain.pc_shield_models import PcShieldReleaseProof,PcShieldLocation
        from towr.domain.pc_melee_result_models import PcRecoverProof,PcAttackProof
        scene=source(shield=True);member=scene.party[0]
        member=replace(member,pc=replace(member.pc,toughness=20,
            ranged=replace(member.pc.ranged,initiative=6,dexterity=6)),
            backup_weapon_policy=None,combat_equipment=member.combat_equipment[:1])
        enemy=scene.enemies[0]
        attack=replace(enemy.definition.attacks[0],test_profile=InlineProfile(1,2),damage=DamageProfile(1))
        enemy=replace(enemy,definition=replace(enemy.definition,attacks=(attack,)))
        scene=replace(scene,max_rounds=4,party=(member,),enemies=(enemy,))
        result=self.execute(scene,[10]*9+[1]*6+[10]*17)
        release,=tuple(step for step in result.steps if type(step.proof) is PcShieldReleaseProof)
        reload,=tuple(step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        recover,=tuple(step for step in result.steps if type(step.proof) is PcRecoverProof)
        shots=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.ranged_shot is not None)
        self.assertEqual([step.source.round_state.round_number for step in
            (shots[0],release,reload,recover,shots[1])],[1,2,2,3,4])
        self.assertIs(reload.source.party[0].shield.location,PcShieldLocation.DROPPED)
        self.assertIs(recover.state.party[0].shield.location,PcShieldLocation.HELD)
        self.assertEqual(result.executed_actions,8)

    def wounded_scene(self):
        from towr.domain.attack_models import ResilienceProfile,DamageProfile
        scene=make_pc_pistol_scenario(pc_count=1,enemy_count=2,max_rounds=2)
        member=participant()
        member=replace(member,pc=replace(member.pc,ranged=replace(member.pc.ranged,ballistic_skill=6,shooting=6)),
            target_priority=scene.party[0].target_priority,defeat_decisions=scene.party[0].defeat_decisions)
        enemies=[]
        for enemy in scene.enemies:
            resilience=ResilienceProfile(1,10)
            attack=replace(enemy.definition.attacks[0],damage=DamageProfile(30))
            enemies.append(replace(enemy,definition=replace(enemy.definition,resilience=resilience,attacks=(attack,)),
                state=replace(enemy.state,current_resilience=resilience)))
        return replace(scene,party=(member,),enemies=tuple(enemies),
            facts=replace(scene.facts,outnumbering_bonus_approved=False))

    def test_actual_smashed_hand_drops_only_gun_and_draws_backup_in_the_healthy_hand(self):
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_melee_result_models import PcTurnEndProof
        values=[10]*8+[1,1]+[10]*3+[1]+[1,1]+[10]*3+[2,10,1]+[1]*3+[10]*15
        result=self.execute(self.wounded_scene(),values)
        swap,=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertIs(swap.proof.previous.active.location,PcItemLocation.DROPPED)
        self.assertIs(swap.state.party[0].weapon_hand,PcWeaponHand.RIGHT)
        self.assertIs(result.state.party[0].weapon_inventory.items[0].location,PcItemLocation.DROPPED)
        self.assertFalse(result.state.party[0].ranged.loaded)
        self.assertEqual(result.state.party[0].injury.wounds[1].table_total,12)
        self.assertFalse(any(step.proof.critical is not None for step in result.steps if type(step.proof) is PcTurnEndProof))

    def test_actual_internal_injury_swap_and_attack_share_one_mandatory_critical_test(self):
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_melee_result_models import PcTurnEndProof
        from towr.domain.injury_models import WoundConditionEffect
        values=[10]*8+[1,1]+[10]*3+[1]+[1,1]+[10]*3+[7,7]+[10]*5+[1]*3+[10]*10
        result=self.execute(self.wounded_scene(),values)
        swap,=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertFalse(swap.source.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(swap.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(swap.state.party[0].injury.conditions.has(Condition.DRAINED))
        critical=tuple(effect.wound_sequence for effect in swap.state.party[0].injury.active_wound_effects
            if type(effect) is WoundConditionEffect and effect.condition is Condition.CRITICALLY_INJURED)
        self.assertEqual(critical,(2,))
        ends=tuple(step.proof.critical for step in result.steps if type(step.proof) is PcTurnEndProof
            and step.proof.critical is not None)
        self.assertEqual(len(ends),1)
        self.assertEqual(result.executed_actions,6)

    def test_actual_recover_picks_dropped_gun_stowing_backup_without_reloading_it(self):
        from towr.domain.pc_melee_result_models import PcRecoverProof
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        scene=replace(self.wounded_scene(),max_rounds=3)
        values=[10]*8+[1,1]+[10]*3+[1]+[1,1]+[10]*3+[2,10,1]+[1]*3+[10]*25

        def advice(state,actor_id=None):
            actor=actor_id or state.round_state.active_turn.actor_id
            round_number=state.round_state.round_number
            if round_number==3:
                return PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,1.0,
                    'scripted:recover-owned-gun',pickup_item_id='gun:owned')
            return PcTacticalChoice(actor,CombatActionKind.ATTACK,'minion1',None,1.0,
                'scripted:shoot-then-backup',weapon_item_id='gun:owned' if round_number==1 else 'sword:owned')

        with patch('towr.domain.pc_tactical_models.select_pc_tactic',side_effect=advice):
            result=self.execute(scene,values)
        recover,=tuple(step for step in result.steps if type(step.proof) is PcRecoverProof)
        before,after=recover.source.party[0],recover.state.party[0]
        self.assertIs(before.weapon_inventory.items[0].location,PcItemLocation.DROPPED)
        self.assertEqual(before.weapon_inventory.active_item_id,'sword:owned')
        self.assertEqual(after.weapon_inventory.active_item_id,'gun:owned')
        self.assertIs(after.weapon_inventory.items[0].location,PcItemLocation.HELD)
        self.assertIs(after.weapon_inventory.items[1].location,PcItemLocation.CARRIED)
        self.assertEqual(before.ranged,after.ranged)
        self.assertFalse(after.ranged.loaded)
        self.assertEqual(after.ranged.exacting.accumulated_successes,0)
        self.assertEqual(sum(type(step.proof) is PcWeaponSwapProof for step in result.steps),1)
        self.assertEqual(result.executed_actions,9)

    def test_actual_healing_restores_reload_hand_then_reverses_to_the_same_partial_cycle(self):
        from towr.domain.pc_potion_models import PcPotionSelection,PcPotionRecoverProof
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_heavy_wound_models import usable_hands,PcBodyFactKind
        from towr.domain.potion_models import ConsumableItem,ConsumableKind
        scene=replace(self.wounded_scene(),max_rounds=6)
        member=replace(scene.party[0],consumables=(ConsumableItem('heal',ConsumableKind.HEALING,1,None),))
        scene=replace(scene,party=(member,))
        # R1 spent gun; R2 one Reload success, then actual W1/W18. R3 melee
        # and successful mandatory Critical test; R4 potion; R5 finishes Reload.
        values=([10]*18+[1,10,10]+[1,1]+[10]*3+[1]+[1,1]+[10]*3+[9,9]
            +[10]*5+[1]*3+[10]*22+[1,1,10]+[10]*28)

        def advice(state,actor_id=None):
            actor=actor_id or state.round_state.active_turn.actor_id
            round_number=state.round_state.round_number
            action,target,extra=CombatActionKind.ATTACK,'minion1',{}
            if round_number in (2,5):
                action,target=CombatActionKind.IMPROVISE,None
                extra['ranged_reload']=True
            if round_number==4:
                action,target=CombatActionKind.RECOVER,actor
                extra['potion']=PcPotionSelection('heal',2,PcWeaponHand.LEFT)
            else:
                extra['weapon_item_id']='sword:owned' if round_number==3 else 'gun:owned'
            return PcTacticalChoice(actor,action,target,None,1.0,'scripted:healing-return',**extra)

        with patch('towr.domain.pc_tactical_models.select_pc_tactic',side_effect=advice):
            result=self.execute(scene,values)
        potion,=tuple(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        reloads=tuple(step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        swaps=tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        before,after=potion.source.party[0],potion.state.party[0]
        self.assertEqual(len(usable_hands(before)),1)
        self.assertEqual(len(usable_hands(after)),2)
        self.assertTrue(any(fact.kind is PcBodyFactKind.CLUTCH_STOMACH for fact in before.body_facts))
        self.assertTrue(after.injury.wounds[1].healed)
        self.assertEqual(after.potions,())
        self.assertEqual([(step.source.round_state.round_number,step.proof.state.active_item_id) for step in swaps],
            [(3,'sword:owned'),(5,'gun:owned')])
        partial=reloads[0].state.party[0].ranged
        self.assertEqual(partial.exacting.accumulated_successes,1)
        self.assertEqual(before.ranged,partial)
        self.assertEqual(after.ranged,partial)
        self.assertEqual(swaps[1].source.party[0].ranged,swaps[1].state.party[0].ranged)
        resumed=reloads[1].proof.result
        self.assertEqual(resumed.previous_state,partial)
        self.assertTrue(resumed.state.loaded)
        self.assertEqual(resumed.state.weapon_instance_id,partial.weapon_instance_id)
        self.assertEqual(resumed.state.reload_cycle_id,partial.reload_cycle_id)
        self.assertEqual(result.executed_actions,18)


if __name__=='__main__':
    unittest.main()
