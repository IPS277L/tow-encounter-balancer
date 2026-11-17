"""Prepared automatic PC ranged choices; no fabricated complete battle journals."""
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import patch

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario,pistol_profile
from tests.support.pc_tactics_fixtures import tactical_snapshot
from towr.domain.pc_melee_models import (PcMeleePolicy,PcMeleeWeapon,PcRepeaterBonusPolicy,
    PcFatePolicy,PcGloriousPolicy,PcBackupWeaponPolicy,PcWeaponHand)
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
from towr.domain.pc_tactical_models import select_pc_tactic
from towr.domain.pc_ranged_advice import pc_fate_branches,pc_attack_value,ranged_action_choices
from towr.domain.condition_models import Condition
from towr.domain.exacting_test_models import ExactingTestProgress
from towr.domain.test_models import TestRequest,TestProfile,Skill,QualityModifier,TestQuality
from towr.domain.turn_models import CombatActionKind


def ranged_source(*,weapon=PcMeleeWeapon.PISTOL,backup=False,rounds=3,bs=4,shooting=5,
        ws=1,melee=2,strength=2,initiative=3,dexterity=5):
    source=make_pc_pistol_scenario(max_rounds=rounds)
    actor=source.party[0]
    profile=pistol_profile(ballistic_skill=bs,shooting=shooting,initiative=initiative,dexterity=dexterity)
    if weapon is not PcMeleeWeapon.PISTOL:
        profile=replace(profile,has_blackpowder_lore=None if weapon is PcMeleeWeapon.REPEATER_HANDBOW else True,
            has_blackpowder_kit=None if weapon is PcMeleeWeapon.REPEATER_HANDBOW else True,
            repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC)
    pc=replace(actor.pc,weapon=weapon,ranged=profile,weapon_skill=ws,melee=melee,strength=strength,toughness=20)
    items=(PcWeaponItem('gun',weapon,PcItemLocation.HELD,actor.initial_weapon_hand),)
    backup_policy=None
    if backup:
        items+= (PcWeaponItem('sword',PcMeleeWeapon.SWORD,PcItemLocation.CARRIED,None),)
        backup_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,actor.initial_weapon_hand)
    actor=replace(actor,pc=pc,policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=items,
        backup_weapon_policy=backup_policy)
    return replace(source,party=(actor,))


def empty(state):
    member=state.party[0];cycle='prepared:empty'
    weapon=replace(member.ranged,loaded=False,reload_cycle_id=cycle,
        reload_cycle_ids=(*member.ranged.reload_cycle_ids,cycle),exacting=ExactingTestProgress(cycle+':exacting',3))
    return replace(state,party=(replace(member,ranged=weapon),))


def shooting_help_source(*,helper_weapon=PcMeleeWeapon.REPEATER_PISTOL):
    from towr.domain.attack_models import ResilienceProfile
    from towr.domain.test_models import InlineProfile
    source=make_pc_pistol_scenario(pc_count=2,max_rounds=1)
    party=[]
    for index,member in enumerate(source.party):
        weapon=helper_weapon if index==0 else PcMeleeWeapon.PISTOL
        profile=pistol_profile(ballistic_skill=1 if index==0 else 6,shooting=6)
        if weapon is not PcMeleeWeapon.PISTOL:
            profile=replace(profile,repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC,
                has_blackpowder_lore=None if weapon is PcMeleeWeapon.REPEATER_HANDBOW else True,
                has_blackpowder_kit=None if weapon is PcMeleeWeapon.REPEATER_HANDBOW else True)
        party.append(replace(member,pc=replace(member.pc,weapon=weapon,ranged=profile,toughness=20),
            policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            combat_equipment=(PcWeaponItem('gun'+str(index),weapon,PcItemLocation.HELD,member.initial_weapon_hand),)))
    enemy=source.enemies[0];resilience=ResilienceProfile(20)
    enemy=replace(enemy,definition=replace(enemy.definition,resilience=resilience,
        protection=(replace(enemy.definition.protection[0],test_profile=InlineProfile(6,6)),)),
        state=replace(enemy.state,current_resilience=resilience))
    return replace(source,party=tuple(party),enemies=(enemy,))


class FiniteFateForecastTests(unittest.TestCase):
    def state(self):
        source=ranged_source()
        actor=source.party[0]
        actor=replace(actor,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,Skill.DEXTERITY),0,0),
            fate=replace(actor.fate,rating=1,session_spend_limit=1,has_lucky=False))
        return tactical_snapshot(replace(source,party=(actor,)),'pc1')

    def test_one_future_spend_consumes_budget_in_its_own_initial_roll_branch(self):
        state=self.state();request=TestRequest('prepared',TestProfile(2,5))
        branches=pc_fate_branches(state,'pc1',Skill.SHOOTING,request,(1,False))
        self.assertAlmostEqual(sum(chance for _,_,chance in branches),1)
        self.assertAlmostEqual(sum(chance for _,budget,chance in branches if budget==(0,False)),.25)
        self.assertAlmostEqual(sum(successes*chance for successes,_,chance in branches),1.25)
        for _,budget,_ in branches:
            if budget!=(0,False):continue
            later=pc_fate_branches(state,'pc1',Skill.SHOOTING,request,budget)
            self.assertTrue(all(after==(0,False) for _,after,_ in later))
            self.assertAlmostEqual(sum(s*p for s,_,p in later),1)

    def test_lucky_budget_is_used_once_even_with_zero_paid_pool(self):
        state=self.state();request=TestRequest('prepared',TestProfile(1,5))
        branches=pc_fate_branches(state,'pc1',Skill.SHOOTING,request,(0,True))
        self.assertAlmostEqual(sum(p for _,budget,p in branches if budget==(0,False)),.5)
        self.assertAlmostEqual(sum(s*p for s,_,p in branches),.75)

    def test_glorious_grim_cancellation_does_not_spend_again(self):
        state=self.state();request=TestRequest('prepared',TestProfile(2,5),
            quality_modifiers=(QualityModifier('trait',TestQuality.GLORIOUS),QualityModifier('grim',TestQuality.GRIM)))
        branches=pc_fate_branches(state,'pc1',Skill.SHOOTING,request,(1,False))
        self.assertTrue(all(budget==(1,False) for _,budget,_ in branches))
        self.assertAlmostEqual(sum(s*p for s,_,p in branches),1)

    def test_minimum_die_rule_uses_exact_one_before_any_fate_reroll(self):
        from towr.domain.test_models import DiceModifier
        state=self.state()
        request=TestRequest('prepared:min',TestProfile(1,6),dice_modifiers=(DiceModifier('penalty',-2),))
        branches=pc_fate_branches(state,'pc1',Skill.SHOOTING,request,(1,False))
        self.assertAlmostEqual(sum(s*p for s,_,p in branches),.19)

    def test_forecast_has_no_real_rng_or_resource_spend(self):
        state=self.state();request=TestRequest('prepared',TestProfile(2,5))
        with patch('towr.rules.test_resolution.roll_test_initial',side_effect=AssertionError('no RNG')):
            pc_fate_branches(state,'pc1',Skill.SHOOTING,request,(1,False))
        self.assertEqual(state.party[0].fate.spends,())


class RangedActionChoiceTests(unittest.TestCase):
    def test_ready_ranged_actor_selects_real_shooting_with_concrete_item(self):
        state=tactical_snapshot(ranged_source(),'pc1')
        choice=select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.ATTACK)
        self.assertEqual(choice.weapon_item_id,'gun')
        self.assertFalse(choice.ranged_bonus)
        self.assertFalse(choice.ranged_reload)

    def test_empty_pistol_can_select_reload_and_not_an_empty_shot(self):
        state=empty(tactical_snapshot(ranged_source(),'pc1'))
        choice=select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.IMPROVISE)
        self.assertTrue(choice.ranged_reload)
        self.assertEqual(choice.weapon_item_id,'gun')
        self.assertEqual(pc_attack_value(state,'pc1'),(0.0,None))

    def test_empty_pistol_with_one_hand_exposes_reload_boundary_without_empty_recover_loop(self):
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.injury_models import WoundRecord,WoundEntryId
        from towr.domain.pc_ranged_models import pc_ranged_unsupported
        state=empty(tactical_snapshot(ranged_source(),'pc1'));member=state.party[0]
        injury=replace(member.injury,wounds=(WoundRecord(1,WoundEntryId.SEVERED_ARM,20,(10,10),effect_resolved=True),))
        member=replace(member,injury=injury,body_facts=(PcBodyFact(PcBodyFactKind.LOST_ARM,1,PcWeaponHand.RIGHT),))
        state=replace(state,party=(member,))
        choice=select_pc_tactic(state)
        self.assertTrue(choice.ranged_reload)
        self.assertEqual(choice.weapon_item_id,'gun')
        self.assertEqual(pc_ranged_unsupported(state).reason,'ranged_reload_hands_unavailable')
        # A useful standard Recover still precedes that boundary.
        staggered=replace(member,injury=replace(injury,conditions=injury.conditions.with_condition(Condition.STAGGERED)))
        state=replace(state,party=(staggered,))
        self.assertIs(select_pc_tactic(state).action,CombatActionKind.RECOVER)
        self.assertIsNone(pc_ranged_unsupported(state))

    def test_no_hands_and_no_pickup_uses_standard_recover(self):
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.injury_models import WoundRecord,WoundEntryId
        from towr.domain.pc_ranged_models import pc_ranged_unsupported
        state=tactical_snapshot(ranged_source(),'pc1');member=state.party[0]
        wounds=tuple(WoundRecord(n,WoundEntryId.SEVERED_ARM,20,(10,10),effect_resolved=True) for n in (1,2))
        facts=tuple(PcBodyFact(PcBodyFactKind.LOST_ARM,n,side)
            for n,side in enumerate((PcWeaponHand.LEFT,PcWeaponHand.RIGHT),1))
        inventory=replace(member.weapon_inventory,items=tuple(replace(item,location=PcItemLocation.DROPPED,hand=None)
            for item in member.weapon_inventory.items))
        member=replace(member,injury=replace(member.injury,wounds=wounds),body_facts=facts,
            weapon_hand=None,weapon_inventory=inventory)
        state=replace(state,party=(member,))
        self.assertIs(select_pc_tactic(state).action,CombatActionKind.RECOVER)
        self.assertEqual(select_pc_tactic(state).reason,'recover_without_usable_hands')
        self.assertIsNone(pc_ranged_unsupported(state))

    def test_slashed_arm_and_clutch_block_carried_backup_in_both_wound_orders(self):
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind,usable_hands
        from towr.domain.injury_models import WoundRecord,WoundEntryId
        from towr.domain.pc_ranged_models import pc_ranged_unsupported
        from towr.domain.pc_weapon_inventory import expected_pc_weapon_swap,pc_weapon_pickup_view
        for order,loaded,backup_location,weapon in product(((16,18),(18,16)),(True,False),
                (PcItemLocation.CARRIED,PcItemLocation.DROPPED),
                (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL,PcMeleeWeapon.REPEATER_HANDBOW)):
            with self.subTest(order=order,loaded=loaded,backup_location=backup_location,weapon=weapon):
                state=tactical_snapshot(ranged_source(backup=True,weapon=weapon),'pc1');member=state.party[0]
                if not loaded:
                    state=empty(state);member=state.party[0]
                entries={16:WoundEntryId.SLASHED_FOREARMS,18:WoundEntryId.SPILLING_GUTS}
                wounds=tuple(WoundRecord(n,entries[total],total,(total//2,)*2,effect_resolved=True)
                    for n,total in enumerate(order,1))
                facts=tuple(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM if total==16 else PcBodyFactKind.CLUTCH_STOMACH,
                    n,PcWeaponHand.RIGHT if total==16 else PcWeaponHand.LEFT)
                    for n,total in enumerate(order,1))
                gun,sword=member.weapon_inventory.items
                sword=replace(sword,location=backup_location)
                inventory=replace(member.weapon_inventory,items=(replace(gun,location=PcItemLocation.DROPPED,hand=None),sword))
                member=replace(member,injury=replace(member.injury,wounds=wounds),body_facts=facts,
                    weapon_hand=None,weapon_inventory=inventory)
                state=replace(state,party=(member,))
                self.assertEqual(usable_hands(member),())
                self.assertIs(member.ranged.loaded,loaded)
                self.assertIsNone(pc_weapon_inventory_view(state,'pc1',sword.id))
                self.assertIsNone(pc_weapon_pickup_view(state,'pc1',gun.id))
                self.assertIsNone(expected_pc_weapon_swap(state))
                self.assertIsNone(pc_ranged_unsupported(state))
                choice=select_pc_tactic(state)
                self.assertIs(choice.action,CombatActionKind.RECOVER)
                self.assertFalse(choice.ranged_reload)
                self.assertIsNone(choice.weapon_item_id)
                self.assertIsNone(choice.pickup_item_id)

    def test_one_remaining_hand_still_permits_carried_melee_backup(self):
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.injury_models import WoundRecord,WoundEntryId
        from towr.domain.pc_ranged_models import pc_ranged_unsupported
        state=empty(tactical_snapshot(ranged_source(backup=True,ws=4,melee=6),'pc1'));member=state.party[0]
        injury=replace(member.injury,wounds=(WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(8,8),effect_resolved=True),))
        member=replace(member,injury=injury,
            body_facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),))
        state=replace(state,party=(member,))
        self.assertIsNotNone(pc_weapon_inventory_view(state,'pc1','sword'))
        choice=select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.ATTACK)
        self.assertEqual(choice.weapon_item_id,'sword')
        self.assertFalse(choice.ranged_reload)
        self.assertIsNone(pc_ranged_unsupported(state))

    def test_shield_release_pins_reload_through_reservation_and_clears_after_its_test(self):
        from tests.support.pc_shield_scenarios import shield_loadout
        from tests.support.pc_melee_scripted import ScriptedD10
        from towr.domain.pc_shield_models import expected_pc_shield_release,PcShieldLocation
        from towr.domain.pc_weapon_inventory import pending_pc_weapon_swap
        from towr.domain.pc_melee_result_models import pc_melee_action_declaration,PcFateDecline
        from towr.domain._pc_melee_projection import project_pc_step
        from towr.domain.pc_ranged_models import build_pc_ranged_reload,PcRangedReloadProof
        from towr.domain.reload_models import _complete_reload_action_after_test
        from towr.domain.turn_models import CombatActionSlotRequest,ActionSlotGrant
        from towr.rules.turn_resolution import reserve_combat_action_slot
        from towr.rules.test_resolution import resolve_test
        source=ranged_source(bs=6,shooting=6)
        source=replace(source,party=(replace(source.party[0],shield=shield_loadout(PcWeaponHand.RIGHT)),))
        state=empty(tactical_snapshot(source,'pc1'))
        choice=select_pc_tactic(state)
        self.assertTrue(choice.ranged_reload)
        release=expected_pc_shield_release(state)
        self.assertEqual(release.intent,choice)
        state=project_pc_step(state,release)
        self.assertIs(state.party[0].shield.location,PcShieldLocation.DROPPED)
        # Replanning would prefer returning the Shield or another action.
        # Price and reservation must reuse the exact selected Reload instead.
        with patch('towr.domain.pc_ranged_advice.ranged_action_choices',side_effect=AssertionError('replanned after price')):
            self.assertEqual(select_pc_tactic(state),choice)
            declaration=pc_melee_action_declaration(state)
            reserved=reserve_combat_action_slot(CombatActionSlotRequest(release.action_id.removesuffix(':shield:release')+':reserve',
                state.round_state,'pc1',declaration,ActionSlotGrant.STANDARD))
            state=project_pc_step(state,reserved)
            self.assertEqual(select_pc_tactic(state),choice)
            request=build_pc_ranged_reload(state)
            rng=ScriptedD10([1,1,1])
            test=resolve_test(request.dexterity_test,rng)
            result=_complete_reload_action_after_test(request,test)
            decline=PcFateDecline('pc1',request.dexterity_test.id,'test',source.party[0].fate_policy)
            state=project_pc_step(state,PcRangedReloadProof(request,result,decline))
        rng.assert_exhausted()
        self.assertTrue(state.party[0].ranged.loaded)
        self.assertIsNone(pending_pc_weapon_swap(state))

    def test_healthy_melee_alternative_can_beat_reload_without_fixed_fallback(self):
        state=empty(tactical_snapshot(ranged_source(backup=True,ws=5,melee=6,strength=4),'pc1'))
        choice=select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.ATTACK)
        self.assertEqual(choice.weapon_item_id,'sword')
        self.assertFalse(choice.ranged_reload)
        self.assertEqual(state.party[0].weapon_inventory.active_item_id,'gun')

    def test_carried_loaded_pistol_can_be_selected_again_after_melee(self):
        state=tactical_snapshot(ranged_source(backup=True,rounds=1,bs=6,shooting=6,ws=1,melee=2),'pc1')
        view=pc_weapon_inventory_view(state,'pc1','sword')
        choice=select_pc_tactic(view)
        self.assertIs(choice.action,CombatActionKind.ATTACK)
        self.assertEqual(choice.weapon_item_id,'gun')
        self.assertTrue(view.party[0].ranged.loaded)
        self.assertEqual(view.party[0].weapon_inventory.active_item_id,'sword')

    def test_carried_melee_wild_attack_is_compared_with_its_prepared_item(self):
        from towr.domain.pc_combat_talent_models import PcCombatTalent,TalentAcquisition
        from towr.domain.generated_npc_models import GeneratedTalent
        source=ranged_source(backup=True,bs=1,shooting=1,ws=4,melee=5,strength=4)
        actor=replace(source.party[0],combat_talents=(PcCombatTalent(GeneratedTalent.WILD_ATTACK,
            TalentAcquisition.CREATION_FREE),))
        state=tactical_snapshot(replace(source,party=(actor,)),'pc1')
        options=ranged_action_choices(state,'pc1')
        self.assertTrue(any(c.wild_attack and c.weapon_item_id=='sword' for c in options))
        self.assertFalse(any(c.wild_attack and c.weapon_item_id=='gun' for c in options))
        # Once melee is active it still uses the finite weapon comparison;
        # the old melee-only branch must not bypass it with an unbound intent.
        view=pc_weapon_inventory_view(state,'pc1','sword')
        self.assertEqual(select_pc_tactic(view).weapon_item_id,'sword')
        self.assertFalse(state.party[0].injury.conditions.has(Condition.STAGGERED))

    def test_last_turn_repeaters_can_choose_bonus_but_drained_cannot(self):
        for weapon in (PcMeleeWeapon.REPEATER_PISTOL,PcMeleeWeapon.REPEATER_HANDBOW):
            state=tactical_snapshot(ranged_source(weapon=weapon,rounds=1,bs=2,shooting=3),'pc1')
            choice=select_pc_tactic(state)
            with self.subTest(weapon=weapon):self.assertTrue(choice.ranged_bonus)
            member=state.party[0]
            state=replace(state,party=(replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
            self.assertFalse(select_pc_tactic(state).ranged_bonus)

    def test_shield_drop_and_restore_cost_can_change_reload_to_melee(self):
        from tests.support.pc_shield_scenarios import shield_loadout
        source=ranged_source(backup=True,bs=6,shooting=6,ws=1,melee=2)
        without=empty(tactical_snapshot(source,'pc1'))
        self.assertTrue(select_pc_tactic(without).ranged_reload)
        actor=replace(source.party[0],shield=shield_loadout(PcWeaponHand.RIGHT))
        with_shield=empty(tactical_snapshot(replace(source,party=(actor,)),'pc1'))
        choice=select_pc_tactic(with_shield)
        self.assertIs(choice.action,CombatActionKind.ATTACK)
        self.assertEqual(choice.weapon_item_id,'sword')

    def test_dropped_inactive_gun_requires_recover_not_free_swap(self):
        state=tactical_snapshot(ranged_source(backup=True,rounds=2,bs=6,shooting=6,ws=1,melee=2),'pc1')
        view=pc_weapon_inventory_view(state,'pc1','sword')
        member=view.party[0]
        items=tuple(replace(item,location=PcItemLocation.DROPPED) if item.id=='gun' else item
            for item in member.weapon_inventory.items)
        member=replace(member,weapon_inventory=replace(member.weapon_inventory,items=items))
        prepared=replace(view,party=(member,))
        choice=select_pc_tactic(prepared)
        self.assertIs(choice.action,CombatActionKind.RECOVER)
        self.assertEqual(choice.pickup_item_id,'gun')
        self.assertEqual(choice.weapon_item_id,'sword')
        self.assertEqual(prepared.party[0].weapon_inventory.items[0].location,PcItemLocation.DROPPED)
        unloaded=empty(prepared)
        empty_choice=select_pc_tactic(unloaded)
        self.assertIs(empty_choice.action,CombatActionKind.ATTACK)
        self.assertEqual(empty_choice.weapon_item_id,'sword')
        loaded_pickup=next(c for c in ranged_action_choices(prepared,'pc1') if c.pickup_item_id=='gun')
        empty_pickup=next(c for c in ranged_action_choices(unloaded,'pc1') if c.pickup_item_id=='gun')
        self.assertLess(empty_pickup.utility,loaded_pickup.utility)

    def test_shooting_help_bonus_compares_its_real_future_reload_price(self):
        from towr.domain.pc_ranged_advice import pc_help_mode_values
        values=[]
        for rounds in (1,3):
            state=tactical_snapshot(ranged_source(weapon=PcMeleeWeapon.REPEATER_PISTOL,
                rounds=rounds,bs=2,shooting=5),'pc1')
            request=TestRequest('prepared:help',state.source.party[0].pc.ranged.shooting_profile)
            options=pc_help_mode_values(state,'pc1',Skill.SHOOTING,request,lambda n:.1*n)
            values.append(max(options,key=lambda item:item[1])[0])
            self.assertTrue(state.party[0].ranged.loaded)
        self.assertEqual(values,[True,False])

    def test_actual_forward_plan_can_select_shooting_help_with_optional_test_bonus(self):
        for weapon,bonus in ((PcMeleeWeapon.PISTOL,False),(PcMeleeWeapon.REPEATER_PISTOL,True),
                (PcMeleeWeapon.REPEATER_HANDBOW,True)):
            state=tactical_snapshot(shooting_help_source(helper_weapon=weapon),'pc1')
            choice=select_pc_tactic(state)
            with self.subTest(weapon=weapon):
                self.assertIs(choice.action,CombatActionKind.HELP)
                self.assertIs(choice.help_policy.skill,Skill.SHOOTING)
                self.assertEqual(choice.target_id,'pc2')
                self.assertEqual(choice.weapon_item_id,'gun0')
                self.assertEqual(choice.ranged_bonus,bonus)

    def test_ordinary_bonus_cap_tie_keeps_ready_without_price(self):
        state=tactical_snapshot(ranged_source(weapon=PcMeleeWeapon.REPEATER_PISTOL,rounds=1),'pc1')
        from towr.domain.pc_ranged_advice import _distribution_request_value
        with patch('towr.domain.pc_ranged_advice._distribution_request_value',return_value=((.5,(0,False),1.0),)):
            choices=ranged_action_choices(state,'pc1')
        best=max(choices,key=lambda choice:choice.utility)
        self.assertFalse(best.ranged_bonus)


if __name__=='__main__':unittest.main()
