"""Ordinary Brawn weapons and mounted Traits through real K1/native execution."""
from dataclasses import replace
import json
import unittest

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from towr.domain.armour_models import ArmourLoadout
from towr.domain.attack_models import ConditionImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleePolicy, PcMeleeWeapon as W, PcWeaponHand as H,
    PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy,
)
from towr.domain.pc_melee_result_models import PcAttackProof, initial_pc_melee_state, build_pc_melee_attack
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.test_models import Skill
from towr.domain.weapon_inventory_models import WeaponItemSource, WeaponItemLocation as L, WeaponGrip as G
from towr.domain.weapon_use_models import WeaponUse
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action


class Ones:
    def randint(self, low, high):
        if (low,high)!=(1,10):
            raise AssertionError('these battles use d10 only')
        return 1


class Tens(Ones):
    def randint(self, low, high):
        super().randint(low,high)
        return 10


def physical(kind, *, id='weapon', grip=G.LEFT):
    return WeaponItemSource(id,kind,L.HELD if grip is not None else L.CARRIED,grip)


def scene(*, player=W.UNARMED, npc_weapon=None, rounds=2, npc_strength=1,
        player_items=None, player_shield=False, automatic=False,player_ranged=None):
    source=make_pc_melee_scenario(max_rounds=rounds)
    member=source.party[0]
    equipment=(() if player is W.UNARMED else (PcWeaponItem('weapon',player,PcItemLocation.HELD,H.LEFT),))
    if player_items is not None:
        equipment=player_items
    pc=replace(member.pc,weapon=player,strength=3,toughness=20,
        melee=6,defence=6,athletics=4,endurance=6,
        brawn=6 if player in (W.UNARMED,W.KNUCKLEDUSTERS) else None,ranged=player_ranged)
    shield=(PcShieldLoadout(H.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if player_shield else None)
    member=replace(member,pc=pc,combat_equipment=equipment,shield=shield,
        initial_weapon_hand=None if player is W.UNARMED else H.LEFT,
        policy=PcMeleePolicy.AUTOMATIC_COMBAT if automatic else PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE)
    weapons=() if npc_weapon is None else (physical(npc_weapon),)
    npc=GeneratedNpc(1,npc_strength,20,1,2,2,weapons,ArmourLoadout(),defence=2,
        brawn=2 if npc_weapon in (None,W.KNUCKLEDUSTERS) else None)
    return replace(source,party=(member,),enemies=(npc.participant('minion1'),))


def attacks(result, actor):
    return tuple(step for step in result.steps if type(step.proof) is PcAttackProof
        and step.proof.request.actor_id==actor)


class BrawnWeaponExecutionTests(unittest.TestCase):
    def run_native(self, source, rng=None):
        result=run_pc_melee_scenario(source,rng or Tens())
        self.assertIsNone(result.unsupported)
        current=initial_pc_melee_state(source)
        for step in result.steps:
            current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def test_unarmed_both_roles_use_brawn_and_repeated_stagger_causes_a_real_wound(self):
        result=self.run_native(scene(),Ones())
        outgoing=attacks(result,'pc')
        self.assertEqual(len(outgoing),2)
        self.assertEqual(result.state.enemy('minion1').state.injury.wounds,1)
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)
        self.assertEqual(outgoing[0].state.enemy('minion1').state.injury.wounds,0)
        self.assertTrue(outgoing[0].state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        for step in (*outgoing,*attacks(result,'minion1')):
            intent=step.proof.weapon_intent
            self.assertIs(intent.attack_skill,Skill.BRAWN)
            self.assertIsInstance(step.proof.request.kernel_request.attack.impact_spec,ConditionImpactSpec)
            self.assertIsNone(intent.attack_use.primary_item_id)
            self.assertEqual(intent.attack_use.used_hands,())
            self.assertIn(intent.protection_skill,(Skill.ATHLETICS,Skill.ENDURANCE))
        self.assertEqual(result.state.participant('pc').weapon_inventory.items,())
        self.assertEqual(result.state.enemy('minion1').state.weapon_inventory.items,())

    def test_prepared_defenceless_target_receives_only_the_unarmed_condition_from_real_k1(self):
        result=self.run_native(scene(rounds=1))
        attack=attacks(result,'pc')[0]
        enemy=attack.source.enemy('minion1')
        prepared=replace(attack.source,enemies=(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.DEFENCELESS)))),))
        request,protection=build_pc_melee_attack(prepared)
        self.assertIsNone(protection.selected_skill)
        execution=execute_attack_action(request,Ones())
        self.assertIsNone(execution.resolution.attack.defender_test)
        self.assertEqual(execution.resolution.target_state.wounds,0)
        self.assertTrue(execution.resolution.target_state.conditions.has(Condition.STAGGERED))
        # This is a real action at an explicit local preparation boundary, not
        # a fabricated encounter history asserting how Defenceless was gained.

    def test_player_knuckledusters_use_strength_minus_one_and_one_actual_hand(self):
        result=self.run_native(scene(player=W.KNUCKLEDUSTERS,rounds=1),Ones())
        attack=attacks(result,'pc')[0].proof
        self.assertIs(attack.weapon_intent.attack_skill,Skill.BRAWN)
        self.assertEqual(attack.request.kernel_request.attack.impact_spec.damage.base,2)
        self.assertEqual(attack.weapon_intent.attack_use.used_hands,(G.LEFT,))
        incoming=attacks(result,'minion1')[0].proof
        self.assertIn(incoming.weapon_intent.protection_skill,(Skill.ATHLETICS,Skill.ENDURANCE))

    def test_sword_or_shield_can_defend_while_knuckledusters_cannot_supply_defence(self):
        for defender in ('bare','sword','shield'):
            with self.subTest(defender=defender):
                items=(PcWeaponItem('knuckles',W.KNUCKLEDUSTERS,PcItemLocation.HELD,H.LEFT),)
                if defender=='sword':
                    items+=(PcWeaponItem('sword',W.SWORD,PcItemLocation.HELD,H.RIGHT),)
                result=self.run_native(scene(player=W.KNUCKLEDUSTERS,npc_weapon=W.STAFF,rounds=1,
                    player_items=items,player_shield=defender=='shield'),Ones())
                incoming=attacks(result,'minion1')[0].proof.weapon_intent
                if defender=='bare':
                    self.assertIs(incoming.protection_skill,Skill.ATHLETICS)
                    self.assertIsNone(incoming.protection_use)
                else:
                    self.assertIs(incoming.protection_skill,Skill.DEFENCE)
                    use=incoming.protection_use
                    self.assertEqual(tuple(item.source_item_id for item in use.implements),
                        ('sword',) if defender=='sword' else ())
                    self.assertEqual(use.shield_used,defender=='shield')

    def test_generated_knuckledusters_keep_brawn_damage_and_use_athletics_against_melee(self):
        result=self.run_native(scene(player=W.SWORD,npc_weapon=W.KNUCKLEDUSTERS,
            npc_strength=25,rounds=1),Ones())
        outgoing=attacks(result,'pc')[0].proof
        self.assertIs(outgoing.weapon_intent.protection_skill,Skill.ATHLETICS)
        incoming=attacks(result,'minion1')[0].proof
        self.assertIs(incoming.weapon_intent.attack_skill,Skill.BRAWN)
        self.assertIs(incoming.weapon_intent.attack_use.kind,W.KNUCKLEDUSTERS)
        self.assertEqual(incoming.request.kernel_request.attack.impact_spec.damage.base,24)
        self.assertEqual(incoming.weapon_intent.attack_use.used_hands,(G.LEFT,))

    def test_player_cavalry_weapons_apply_traits_only_to_an_actual_mounted_charge(self):
        from towr.domain.weapon_effect_preparation import CAVALRY_SPEAR_CHARGE_RULE_ID,LANCE_CHARGE_RULE_ID,LANCE_DAMAGE_RULE_ID
        for kind,rule in ((W.CAVALRY_SPEAR,CAVALRY_SPEAR_CHARGE_RULE_ID),(W.LANCE,LANCE_CHARGE_RULE_ID)):
            for mounted in (False,True):
                with self.subTest(kind=kind,mounted=mounted):
                    source=scene(player=kind,npc_weapon=W.STAFF,rounds=1,automatic=True)
                    member=replace(source.party[0],pc=replace(source.party[0].pc,weapon_skill=6,strength=6),
                        mount=CombatMount.HORSE if mounted else None)
                    source=replace(source,party=(member,),facts=replace(source.facts,
                        all_opponents_close=False,can_leave_zone=True,unmounted=not mounted),
                        battlefield=PcBattlefieldSpec(R.MEDIUM,R.LONG))
                    result=self.run_native(source)
                    attack=attacks(result,'pc')[0].proof
                    self.assertIsNone(attack.mount_attack)
                    self.assertTrue(any(type(step.proof) is PcBattlefieldChargeProof for step in result.steps))
                    modifiers=attack.request.kernel_request.attack.attacker_test.dice_modifiers
                    self.assertEqual(sum(mod.amount for mod in modifiers if mod.rule_id==rule),int(mounted))
                    impact=attack.request.kernel_request.attack.impact_spec
                    self.assertEqual(impact.damage.base,6+int(kind is W.LANCE))
                    self.assertEqual(sum(mod.amount for mod in impact.damage_modifiers if mod.rule_id==LANCE_DAMAGE_RULE_ID),
                        int(mounted and kind is W.LANCE))

    def test_generated_lance_mounted_charge_uses_the_same_trait_owner(self):
        from towr.domain.weapon_effect_preparation import LANCE_CHARGE_RULE_ID,LANCE_DAMAGE_RULE_ID
        source=make_pc_bow_scenario(weapon=W.LONGBOW,max_rounds=1,backup=False,
            ballistic_skill=1,shooting=2,npc_toughness=20)
        member=replace(source.party[0],pc=replace(source.party[0].pc,toughness=20),
            policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        npc=GeneratedNpc(6,6,20,1,6,2,(physical(W.LANCE),),ArmourLoadout(),
            defence=6,mount=CombatMount.HORSE)
        source=replace(source,party=(member,),enemies=(npc.participant('minion1'),),
            short_range_opening=None,facts=replace(source.facts,can_leave_zone=True,unmounted=False),
            battlefield=PcBattlefieldSpec(R.MEDIUM,R.LONG))
        result=self.run_native(source)
        attack=attacks(result,'minion1')[0].proof
        self.assertIsNone(attack.mount_attack)
        self.assertTrue(any(type(step.proof) is PcBattlefieldChargeProof and step.proof.actor_id=='minion1'
            for step in result.steps))
        actual=attack.request.kernel_request.attack
        self.assertEqual(sum(mod.amount for mod in actual.attacker_test.dice_modifiers if mod.rule_id==LANCE_CHARGE_RULE_ID),1)
        self.assertEqual(sum(mod.amount for mod in actual.impact_spec.damage_modifiers if mod.rule_id==LANCE_DAMAGE_RULE_ID),1)

    def test_lance_cannot_combine_the_other_held_weapon_into_its_attack(self):
        items=(PcWeaponItem('lance',W.LANCE,PcItemLocation.HELD,H.LEFT),
            PcWeaponItem('sword',W.SWORD,PcItemLocation.HELD,H.RIGHT))
        result=self.run_native(scene(player=W.LANCE,npc_weapon=W.STAFF,player_items=items,rounds=1))
        use=attacks(result,'pc')[0].proof.weapon_intent.attack_use
        self.assertEqual(tuple(unit.source_item_id for unit in use.inventory.items),('lance','sword'))
        self.assertEqual(use.contributor_item_ids,())
        other=next(unit for unit in use.inventory.items if unit.id!=use.primary_item_id)
        with self.assertRaises(ValueError):
            WeaponUse(use.actor_id,use.inventory,use.primary_item_id,(other.id,),use.usable_hands)

    def test_automatic_unarmed_choice_keeps_real_items_resources_and_carrying(self):
        items=(PcWeaponItem('sword',W.SWORD,PcItemLocation.HELD,H.LEFT),
            PcWeaponItem('pistol',W.PISTOL,PcItemLocation.CARRIED,None,initially_loaded=False),
            PcWeaponItem('staff',W.STAFF,PcItemLocation.CARRIED,None))
        source=scene(player=W.SWORD,npc_weapon=W.STAFF,player_items=items,rounds=1,automatic=True,
            player_ranged=pistol_profile(ballistic_skill=1,shooting=2))
        member=source.party[0]
        member=replace(member,pc=replace(member.pc,weapon_skill=1,melee=2,strength=2,brawn=6,
            ranged=pistol_profile(ballistic_skill=1,shooting=2)))
        source=replace(source,party=(member,))
        before=initial_pc_melee_state(source).participant('pc').weapon_inventory
        result=self.run_native(source)
        attack=attacks(result,'pc')[0]
        self.assertIsNone(attack.proof.weapon_intent.attack_use.primary_item_id)
        self.assertIsNone(attack.source.participant('pc').weapon_inventory.active_item_id)
        self.assertFalse(attack.source.participant('pc').using_backup_weapon)
        self.assertEqual(attack.source.participant('pc').weapon_inventory.items,before.items)
        self.assertTrue(attack.source.participant('pc').injury.conditions.has(Condition.BURDENED))
        self.assertEqual(result.state.participant('pc').weapon_inventory.items,before.items)
        from towr.domain.armour_models import ShieldKind
        from towr.domain.generated_npc_models import GeneratedRangedFacts
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        from towr.domain.pc_npc_shield_models import PcNpcShieldDropProof
        source=scene(player=W.SWORD,npc_weapon=W.STAFF,rounds=1)
        member=source.party[0]
        member=replace(member,pc=replace(member.pc,weapon_skill=6,defence=6,
            endurance=1,athletics=1,agility=1))
        npc=GeneratedNpc(1,6,20,1,2,2,(WeaponItemSource('gun',W.PISTOL,L.HELD,G.LEFT,initially_loaded=True),),
            ArmourLoadout(shield=ShieldKind.SHIELD),defence=2,brawn=6,
            ranged=GeneratedRangedFacts(1,2,3,4,True,True,True))
        source=replace(source,party=(member,),enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),))
        initial=initial_pc_melee_state(source).enemy('minion1').state.weapon_inventory
        result=self.run_native(source)
        actual=attacks(result,'minion1')[0]
        self.assertIsNone(actual.proof.weapon_intent.attack_use.primary_item_id)
        self.assertEqual(actual.source.enemy('minion1').state.weapon_inventory.items,initial.items)
        self.assertTrue(result.state.enemy('minion1').state.holds_shield)
        self.assertIsNone(actual.proof.npc_ranged_shot)
        self.assertFalse(any(type(step.proof) is PcNpcShieldDropProof for step in result.steps))

    def test_zero_weapon_dynamic_search_has_executable_native_replays(self):
        from tests.integration.test_generated_equipment_json import equipment_request
        from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request,execute_dynamic_encounter,encode_dynamic_encounter_result
        from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
        raw=equipment_request()
        raw['party'][0]['equipment']['weapons']=[]
        raw['party'][0]['equipment']['armour']=[]
        raw['party'][0]['skills']['brawn']=4
        raw['search_space'].update(weapon_count=[0],brawn=[4],endurance=[4],shield=[None])
        command=parse_dynamic_encounter_request(json.dumps(raw))
        result=execute_dynamic_encounter(command)
        report=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(report['total_trials'],2)
        self.assertEqual(report['source_request'],raw)
        for row in report['explored']+report['validations']:
            self.assertEqual(row['npcs'][0]['weapons'],[])
            native=parse_pc_melee_simulation_request(json.dumps(row['replay']))
            self.assertIs(native.request.scenario.party[0].pc.weapon,W.UNARMED)
            self.run_native(native.request.scenario)

    def test_prepared_arm_losses_leave_unarmed_legal_and_keep_internal_injury_price(self):
        from towr.domain.injury_models import (
            WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,
            WoundConditionEffect,WoundEffectDuration,
        )
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind,usable_hands
        from towr.domain.pc_melee_result_models import PcMeleeStep
        from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
        from towr.domain.pc_tactical_models import select_pc_tactic
        from towr.domain.turn_models import CombatActionKind
        from towr.rules.protection_preparation import prepare_protection
        result=self.run_native(scene(rounds=1))
        attack=attacks(result,'pc')[0]
        member=attack.source.participant('pc')
        injury=replace(member.injury,wounds=(
            WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(6,10),effect_resolved=True),
            WoundRecord(2,WoundEntryId.SEVERED_ARM,20,(10,10),effect_resolved=True),
            WoundRecord(3,WoundEntryId.INTERNAL_INJURY,14,(7,7),effect_resolved=True)),
            conditions=member.injury.conditions.with_condition(Condition.DRAINED),
            active_wound_effects=(
                WoundConditionEffect(3,Condition.DRAINED,WoundEffectDuration.UNTIL_HEALED),
                WoundRestrictionEffect(3,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED)))
        body=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,H.LEFT),PcBodyFact(PcBodyFactKind.LOST_ARM,2,H.RIGHT))
        member=replace(member,injury=injury,body_facts=body)
        prepared=replace(attack.source,party=(member,))
        self.assertEqual(usable_hands(member),())
        intent=build_pc_attack_weapon_intent(prepared)
        self.assertIsNone(intent.attack_use.primary_item_id)
        self.assertEqual(intent.attack_use.used_hands,())
        self.assertEqual(intent.attack_use.usable_hands,())
        request,protection=build_pc_melee_attack(prepared,weapon_intent=intent)
        execution=execute_attack_action(request,Tens())
        proof=replace(attack.proof,request=request,protection=prepare_protection(protection),
            execution=execution,weapon_intent=intent)
        after=PcMeleeStep(prepared,proof).state
        self.assertTrue(after.participant('pc').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(tuple(effect.wound_sequence for effect in after.participant('pc').injury.active_wound_effects
            if type(effect) is WoundConditionEffect and effect.condition is Condition.CRITICALLY_INJURED),(3,))
        self.assertEqual(after.participant('pc').body_facts,body)
        # Prepared body boundary only: no earlier physical-drop history is
        # asserted. Without a known Brawn capability the existing fallback stays.
        ordinary=self.run_native(scene(player=W.SWORD,npc_weapon=W.STAFF,rounds=1,automatic=True))
        before=attacks(ordinary,'pc')[0].source
        ordinary_member=replace(before.participant('pc'),injury=injury,body_facts=body)
        self.assertIs(select_pc_tactic(replace(before,party=(ordinary_member,)),'pc').action,CombatActionKind.RECOVER)

    def test_two_players_supply_real_body_brawn_and_endurance_help(self):
        from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
        from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget
        from towr.domain.pc_melee_result_models import PcHelpProof
        for helped_skill in (Skill.BRAWN,Skill.ENDURANCE):
            with self.subTest(helped_skill=helped_skill):
                source=make_pc_melee_party_scenario(pc_count=2,enemy_count=1,max_rounds=1)
                party=tuple(replace(member,
                    pc=replace(member.pc,weapon=W.UNARMED,weapon_skill=1,melee=2,
                        strength=(2 if index==1 and helped_skill is Skill.BRAWN else 1),
                        toughness=(20 if helped_skill is Skill.BRAWN else 6 if index==0 else 3),
                        brawn=6,endurance=6),initial_weapon_hand=None,combat_equipment=(),
                    policy=PcMeleePolicy.AUTOMATIC_COMBAT) for index,member in enumerate(source.party))
                if helped_skill is Skill.BRAWN:
                    # An explicit native Help choice checks its rule/receipt;
                    # the automatic Endurance case below checks the selector.
                    helper=replace(party[0],policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                        help_policy=PcHelpPolicy('pc2',PcHelpTarget.ATTACK,Skill.BRAWN))
                    recipient=replace(party[1],pc=replace(party[1].pc,weapon=W.KNUCKLEDUSTERS),
                        initial_weapon_hand=H.LEFT,policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
                        combat_equipment=(PcWeaponItem('knuckles',W.KNUCKLEDUSTERS,PcItemLocation.HELD,H.LEFT),))
                    party=(helper,recipient)
                npc=GeneratedNpc(1,1 if helped_skill is Skill.BRAWN else 6,20,6,2,6,(),
                    ArmourLoadout(),defence=2,brawn=6)
                source=replace(source,party=party,enemies=(npc.participant('minion1'),),
                    enemy_target_priority=('pc2','pc1'))
                result=self.run_native(source,Ones())
                helper=next(step.proof for step in result.steps if type(step.proof) is PcHelpProof)
                self.assertIs(helper.request.help_skill,helped_skill)
                self.assertEqual(helper.request.beneficiary_id,'pc2')
                self.assertGreater(helper.execution.bonus.bonus_dice,0)
                if helped_skill is Skill.BRAWN:
                    self.assertIs(helper.weapon_use.kind,W.UNARMED)
                    self.assertIsNone(helper.weapon_use.primary_item_id)
                    self.assertEqual(helper.weapon_use.used_hands,())
                else:
                    self.assertIsNone(helper.weapon_use)
                recipient=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and (step.proof.request.actor_id=='pc2' if helped_skill is Skill.BRAWN
                        else step.proof.request.target_id=='pc2'))
                self.assertTrue(any(application.source_request.help==helper.execution
                    for application in recipient.help_applications))


if __name__=='__main__':
    unittest.main()
