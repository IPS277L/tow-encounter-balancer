"""Actual K1 shot with prepared secondary contexts, not a claimed native prefix."""
from copy import copy
from dataclasses import replace
import unittest

from tests.integration.test_pc_battlefield_blunderbuss import scene
from towr.domain.armour_models import ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.injury_models import (
    CharacterInjuryState,WoundRecord,WoundEntryId,WoundRestriction,WoundRestrictionEffect,WoundEffectDuration,
)
from towr.domain.pc_battlefield_models import with_actor_placement
from towr.domain.pc_blunderbuss_models import pc_blunderbuss_snapshot
from towr.domain.pc_briarroot_models import PcBriarrootBinding
from towr.domain.pc_melee_result_models import initial_pc_melee_state,build_pc_melee_attack,PcAttackProof
from towr.domain.pc_npc_ranged_models import complete_pc_npc_ranged_shot
from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
from towr.domain.turn_models import (
    CombatTurnStartRequest,CombatActionSlotRequest,CombatActionDeclaration,CombatActionKind,ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot
from towr.rules.test_resolution import RerollAllFailures


class Ones:
    def randint(self,lower,upper):
        if (lower,upper)!=(1,10):raise AssertionError('expected d10')
        return 1


def prepared_shot():
    source=scene(npc_weapons=(GeneratedWeapon.BLUNDERBUSS,GeneratedWeapon.STAFF))
    npc=source.enemies[1].definition.generated_components
    bearer=replace(npc,armour=replace(npc.armour,shield=ShieldKind.BRIARROOT)).participant('minion2')
    source=replace(source,enemies=(source.enemies[0],bearer))
    state=initial_pc_melee_state(source)
    clock=replace(state.round_state,completed_turn_entity_ids=source.pc_activation_order)
    clock=start_combat_turn(CombatTurnStartRequest('prepared:start',clock,'minion1')).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('prepared:slot',clock,'minion1',
        CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD)).state
    state=replace(state,round_state=clock)
    intent=build_pc_attack_weapon_intent(state)
    request,protection=build_pc_melee_attack(state,weapon_intent=intent)
    result=execute_attack_action(request,Ones(),decisions=RerollAllFailures())
    shot=complete_pc_npc_ranged_shot(state,request,request,result)
    proof=PcAttackProof(request,prepare_protection(protection),result,None,
        npc_ranged_shot=shot,weapon_intent=intent)
    return state,proof


def prepared_injury(state,actor,injury):
    view=copy(state)
    object.__setattr__(view,'party',tuple(replace(member,injury=injury)
        if member.actor_id==actor else member for member in state.party))
    return view


class PcBlunderbussReactionSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state,cls.shot=prepared_shot()

    def impact(self,state,actor='pc2'):
        snapshot=pc_blunderbuss_snapshot(state,self.shot)
        return next(target.impact for target in snapshot.request.targets if target.target_id==actor)

    def test_once_this_round_is_taken_from_the_actual_spatial_bank(self):
        baseline=self.impact(self.state)
        self.assertTrue(baseline.can_target_leave_zone)
        self.assertFalse(baseline.target_has_given_ground_this_round)
        view=copy(self.state)
        object.__setattr__(view,'battlefield',replace(self.state.battlefield,
            spatial=replace(self.state.battlefield.spatial,gave_ground_entity_ids=('pc2',))))
        actual=self.impact(view)
        self.assertFalse(actual.can_target_leave_zone)
        self.assertTrue(actual.target_has_given_ground_this_round)

    def test_a_personal_difficult_terrain_wound_blocks_the_secondary_route(self):
        body=CharacterInjuryState((WoundRecord(1,WoundEntryId.LEG_SPASM,9,(9,),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                WoundEffectDuration.UNTIL_TREATED),))
        actual=self.impact(prepared_injury(self.state,'pc2',body))
        self.assertFalse(actual.can_target_leave_zone)
        self.assertFalse(actual.target_has_given_ground_this_round)

    def test_an_actual_held_weapon_binding_blocks_the_secondary_route(self):
        member=self.state.participant('pc2')
        body=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.BURDENED))
        view=prepared_injury(self.state,'pc2',body)
        binding=PcBriarrootBinding('prepared:briarroot','minion2','pc2',member.weapon_inventory.active_item_id,
            'prepared:captured-attack',0)
        object.__setattr__(view,'briarroot_bindings',(binding,))
        before=view.battlefield
        close=tuple(pair[1] if pair[0]=='pc2' else pair[0] for pair in before.close_pairs if 'pc2' in pair)
        object.__setattr__(view,'battlefield',with_actor_placement(before,'pc2',
            before.spatial.placement_for('pc2').zone_id,close_to_ids=(*close,'minion2')))
        self.assertFalse(self.impact(view).can_target_leave_zone)

    def test_friendly_fire_keeps_its_actual_shooter_as_the_reaction_source(self):
        # The nearby creature belongs to the shooter's side. Its presence in
        # the real Close links is not an Opposed primary Attack against an ally.
        view=copy(self.state)
        before=view.battlefield
        close=tuple(pair[1] if pair[0]=='minion2' else pair[0] for pair in before.close_pairs if 'minion2' in pair)
        object.__setattr__(view,'battlefield',with_actor_placement(before,'minion2',
            before.spatial.placement_for('minion2').zone_id,close_to_ids=(*close,'pc1')))
        self.assertTrue(self.impact(view,'minion2').can_target_leave_zone)

    def test_close_shooter_is_an_actual_nearby_victim_without_an_invented_away_actor(self):
        from towr.domain.pc_give_ground_models import pc_give_ground_context
        # Isolate the secondary source query, without claiming a legal Close
        # 2H shot: that primary would be rejected by the ordinary Range owner.
        view=copy(self.state)
        before=view.battlefield
        object.__setattr__(view,'battlefield',with_actor_placement(before,'minion1',
            before.spatial.placement_for('minion1').zone_id,close_to_ids=('pc1',)))
        snapshot=pc_blunderbuss_snapshot(view,self.shot)
        impact=next(target.impact for target in snapshot.request.targets
            if target.target_id=='minion1')
        self.assertTrue(impact.can_target_leave_zone)
        self.assertFalse(impact.target_has_given_ground_this_round)
        with self.assertRaises(ValueError):
            pc_give_ground_context(view,'minion1','minion1')


if __name__=='__main__':
    unittest.main()
