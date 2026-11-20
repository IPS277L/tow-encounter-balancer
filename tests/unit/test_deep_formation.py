"""Real held sources for both sides; native Charge covers the unmocked trigger."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_deep_formation_models import deep_formation_supports,DEEP_FORMATION_RULE_ID
from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcAttackProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange,RangedWeaponHands
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.domain.weapon_inventory_models import WeaponItemLocation


def source(*,holders=1,pc_holders=False):
    scene=automatic_source(pc_count=holders+1 if pc_holders else 1,
        enemy_count=1 if pc_holders else holders+1)
    if pc_holders:
        scene=replace(scene,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.FOOT_SPEAR),
            initial_weapon_hand=PcTwoHandedGrip.BOTH,talents=(paid_talent(TalentId.DEEP_FORMATION),))
            if index else member for index,member in enumerate(scene.party)))
    else:
        enemy=GeneratedNpc(3,3,4,3,4,4,initial_generated_weapons(GeneratedWeapon.FOOT_SPEAR,grip=RangedWeaponHands.TWO_HANDED),
            ArmourLoadout(),defence=4,talents=(paid_talent(TalentId.DEEP_FORMATION),))
        scene=replace(scene,enemies=tuple(enemy.participant(row.state.actor_id) if index else row
            for index,row in enumerate(scene.enemies)))
    return replace(scene,facts=replace(scene.facts,all_opponents_close=False,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))


def supports(state,defender='minion1',attacker='pc1',skill=Skill.MELEE):
    # Preparation-only boundary: the genuine Charge source/clock is checked by
    # the unmocked native history below and the existing manoeuvre tests.
    with patch('towr.domain.pc_battlefield_manoeuvre_models.current_pc_charge',
            return_value=SimpleNamespace(target_id=defender)):
        return deep_formation_supports(state,defender,attacker,skill)


class PreparationView:
    """Only a query snapshot, never admitted as an executed native journal."""
    def __init__(self,base,**changes):self.base=base;self.changes=changes
    def __getattr__(self,name):return self.changes[name] if name in self.changes else getattr(self.base,name)


class DeepFormationTests(unittest.TestCase):
    def test_each_npc_holder_has_one_exact_acquisition_and_held_source(self):
        state=initial_pc_melee_state(source(holders=2))
        rows=supports(state)
        self.assertEqual(tuple(row.holder_id for row in rows),('minion2','minion3'))
        self.assertEqual([row.modifier.amount for row in rows],[1,1])
        for row in rows:
            self.assertEqual(row.acquisition,state.source.enemy(row.holder_id).definition.generated_components.talents[0])
            self.assertEqual(row.weapon_use.inventory,state.enemy(row.holder_id).state.weapon_inventory)
        self.assertEqual(supports(state),rows)

    def test_pc_holders_support_another_pc_never_themselves(self):
        state=initial_pc_melee_state(source(holders=2,pc_holders=True))
        self.assertEqual(tuple(row.holder_id for row in supports(state,'pc1','minion1')),('pc2','pc3'))
        self.assertEqual(tuple(row.holder_id for row in supports(state,'pc2','minion1')),('pc3',))

    def test_no_charge_or_non_melee_or_friendly_attack_gives_no_bonus(self):
        state=initial_pc_melee_state(source())
        self.assertEqual(deep_formation_supports(state,'minion1','pc1',Skill.MELEE),())
        self.assertEqual(supports(state,skill=Skill.SHOOTING),())
        self.assertEqual(supports(state,skill=Skill.BRAWN),())
        self.assertEqual(supports(state,attacker='minion2'),())

    def test_same_zone_is_required_not_just_the_talent(self):
        state=initial_pc_melee_state(source())
        spatial=state.battlefield.spatial
        placements=tuple(replace(row,zone_id='arena:zone:2') if row.entity_id=='minion2' else row
            for row in spatial.placements)
        moved=PreparationView(state,battlefield=replace(state.battlefield,spatial=replace(spatial,placements=placements)))
        self.assertEqual(supports(moved),())

    def test_unusable_arm_cannot_support_with_a_two_handed_spear(self):
        from towr.domain.injury_models import CharacterInjuryState,WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration
        from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
        from towr.domain.pc_melee_models import PcWeaponHand
        state=initial_pc_melee_state(source(pc_holders=True))
        holder=state.party[1]
        injury=CharacterInjuryState((WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(8,8),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.INJURED_ARM_UNUSABLE,WoundEffectDuration.UNTIL_HEALED),))
        holder=replace(holder,injury=injury,body_facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),))
        state=replace(state,party=(state.party[0],holder))
        self.assertEqual(supports(state,'pc1','minion1'),())

    def test_original_allied_npc_supports_pc_without_becoming_a_pc(self):
        from tests.unit.test_c25_allied_npc_native import allied_source
        holder=source().enemies[1].definition.generated_components
        scene=allied_source(ally=holder)
        from towr.domain.pc_melee_models import PcMeleePolicy
        scene=replace(scene,party=tuple(replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT) for member in scene.party),
            facts=replace(scene.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))
        state=initial_pc_melee_state(scene)
        self.assertEqual(tuple(row.holder_id for row in supports(state,'pc','minion1')),('ally',))
        self.assertNotIn('ally',state.source.pc_activation_order)

    def test_pc_protection_uses_bonus_and_drained_filters_it(self):
        from towr.domain.turn_models import CombatTurnStartRequest
        from towr.domain.turn_models import CombatSide
        from towr.rules.turn_resolution import start_combat_turn
        from towr.domain.pc_melee_result_models import _pc_test
        state=initial_pc_melee_state(source(pc_holders=True))
        # Protection query only: a legal NPC clock, not a forged battle prefix.
        clock=replace(state.round_state,side_order=(CombatSide.OPPOSITION,CombatSide.PLAYERS_AND_ALLIES))
        clock=start_combat_turn(CombatTurnStartRequest('probe:start',clock,'minion1')).state
        state=PreparationView(state,round_state=clock)
        with patch('towr.domain.pc_battlefield_manoeuvre_models.current_pc_charge',
                return_value=SimpleNamespace(target_id='pc1',actor_id='minion1')):
            test=_pc_test(state,'pc1','probe:protection',Skill.DEFENCE,oppose_attack=True,incoming_attack_skill=Skill.MELEE)
            self.assertEqual(sum(mod.amount for mod in test.dice_modifiers if mod.rule_id.startswith(DEEP_FORMATION_RULE_ID)),1)
            member=state.party[0]
            drained=replace(member,injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
            view=PreparationView(replace(state.base,party=(drained,state.party[1])),round_state=clock)
            test=_pc_test(view,'pc1','probe:drained',Skill.DEFENCE,oppose_attack=True,incoming_attack_skill=Skill.MELEE)
            self.assertFalse(any(mod.rule_id.startswith(DEEP_FORMATION_RULE_ID) for mod in test.dice_modifiers))

    def test_generated_selection_and_current_native_json_roundtrip(self):
        import json
        from tests.unit.test_generated_npc_talent_generation import space,FixedChoices
        from tests.unit.test_c25_allied_npc_sources import native
        from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
        search=space(allowed_talents=(TalentId.DEEP_FORMATION,))
        npc=search.sample(FixedChoices(1))
        self.assertEqual(npc.talents,(paid_talent(TalentId.DEEP_FORMATION),))
        self.assertTrue(search.contains(npc))
        scene=source()
        decoded=parse_pc_melee_simulation_request(json.dumps(native(scene))).request.scenario
        self.assertEqual(decoded,scene)

    def test_carried_or_dropped_weapon_does_not_support(self):
        state=initial_pc_melee_state(source())
        holder=state.enemy('minion2')
        for location in (WeaponItemLocation.CARRIED,WeaponItemLocation.DROPPED):
            bank=holder.state.weapon_inventory
            items=tuple(replace(item,location=location,grip=None) for item in bank.items)
            inventory=replace(bank,items=items,active_item_id=None)
            altered=replace(holder,state=replace(holder.state,weapon_inventory=inventory,wields_weapon=False,
                available_attack_ids=()))
            view=replace(state,enemies=(state.enemies[0],altered))
            self.assertEqual(supports(view),())

    def test_drained_holder_still_supplies_a_passive_ally_bonus(self):
        state=initial_pc_melee_state(source())
        holder=state.enemy('minion2')
        injury=replace(holder.state.injury,conditions=holder.state.injury.conditions.with_condition(Condition.DRAINED))
        view=replace(state,enemies=(state.enemies[0],replace(holder,state=replace(holder.state,injury=injury))))
        self.assertEqual(len(supports(view)),1)

    def test_recipient_drained_removes_bonus_from_actual_npc_test(self):
        from towr.domain.pc_generated_equipment import npc_protection_test
        state=initial_pc_melee_state(source())
        target=state.enemies[0]
        injury=replace(target.state.injury,conditions=target.state.injury.conditions.with_condition(Condition.DRAINED))
        state=replace(state,enemies=(replace(target,state=replace(target.state,injury=injury)),state.enemies[1]))
        with patch('towr.domain.pc_battlefield_manoeuvre_models.current_pc_charge',
                return_value=SimpleNamespace(target_id='minion1')):
            _,test=npc_protection_test(state,'minion1','pc1','probe:defence')
        self.assertFalse(any(mod.rule_id.startswith(DEEP_FORMATION_RULE_ID) for mod in test.dice_modifiers))

    def test_unmocked_native_charge_has_bonus_and_replay_checks_its_full_source(self):
        from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
        from tests.integration.test_pc_battlefield_manoeuvre_native import Misses
        scene=source()
        result=run_pc_melee_scenario(scene,Misses())
        attacks=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1']
        self.assertEqual(len(attacks),1)
        attack=attacks[0].proof.request.kernel_request.attack
        self.assertIsNotNone(attacks[0].proof.request.charge_movement)
        self.assertEqual(tuple(mod.amount for mod in attack.defender_test.dice_modifiers
            if mod.rule_id.startswith(DEEP_FORMATION_RULE_ID)),(1,))
        self.assertEqual(deep_formation_supports(attacks[0].state,'minion1','pc1',Skill.MELEE),())
        from towr.domain.pc_melee_result_models import PcMeleeStep
        with self.assertRaises(ValueError):
            changed=replace(attack.defender_test,dice_modifiers=tuple(mod for mod in attack.defender_test.dice_modifiers
                if not mod.rule_id.startswith(DEEP_FORMATION_RULE_ID)))
            kernel=replace(attacks[0].proof.request.kernel_request,attack=replace(attack,defender_test=changed))
            proof=replace(attacks[0].proof,request=replace(attacks[0].proof.request,kernel_request=kernel))
            PcMeleeStep(attacks[0].source,proof)
        current=initial_pc_melee_state(scene)
        for step in result.steps:current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)


if __name__=='__main__':unittest.main()
