"""Real Recover results preserve independent item causes in pure snapshots.

Net preparation contexts follow the existing bounded Net tests. Briarroot's
independent cause comes from an actually executed opposed Attack, not a label.
"""
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_briarroot import actual_attack,react
from tests.unit.test_pc_weighted_net import source,context,bound_item
from towr.domain.armour_models import ArmourLoadout,BodyArmour
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcFateDecline
from towr.domain.pc_weighted_net_models import (
    PcNetLocation,PcNetReleaseProof,build_weighted_net_release,weighted_net_release_item,
    project_weighted_net_step,_release_target_injury,
)
from towr.domain.turn_models import CombatActionKind
from towr.domain.turn_models import (
    CombatTurnStartRequest,CombatActionSlotRequest,CombatActionDeclaration,ActionSlotGrant,
)
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def prepared_net(*,npc=False,body=None):
    scenario=source()
    actor='minion1' if npc else 'pc2'
    if body is not None:
        strength=2 if body is BodyArmour.HEAVY else 3
        armour=ArmourLoadout((body,),body)
        if npc:
            components=replace(scenario.enemies[0].definition.generated_components,
                strength=strength,armour=armour)
            scenario=replace(scenario,enemies=(components.participant(actor),))
        else:
            member=scenario.participant(actor)
            member=replace(member,pc=replace(member.pc,strength=strength,
                armour_bonus=2 if body is BodyArmour.HEAVY else 3),armour=armour,armour_worn=True)
            scenario=replace(scenario,party=tuple(member if item.actor_id==actor else item
                for item in scenario.party))
    if npc:
        prepared=context(scenario,actor='pc2',kind=None)
        # Pure preparation at the NPC side's turn; no fabricated execution
        # receipts or claim that this isolated snapshot is a native journal.
        clock=replace(prepared.round_state,active_turn=None,
            completed_turn_entity_ids=scenario.pc_activation_order)
        clock=start_combat_turn(CombatTurnStartRequest('npc:start',clock,actor)).state
        prepared.round_state=reserve_combat_action_slot(CombatActionSlotRequest('npc:recover',
            clock,actor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    else:
        prepared=context(scenario,actor=actor,kind=CombatActionKind.RECOVER)
    owner='pc1' if npc else 'minion1'
    item=next(item for item in prepared.weighted_nets if item.owner_id==owner)
    bound=bound_item(item,actor,1)
    prepared.weighted_nets=tuple(bound if other.item_id==item.item_id else other
        for other in prepared.weighted_nets)
    if npc:
        enemy=prepared.enemy(actor)
        prepared.enemies=(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.BURDENED)))),)
    else:
        member=prepared.participant(actor)
        prepared.party=tuple(replace(member,net_condition_sources=(bound.binding,),
            injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.BURDENED)))
            if other.actor_id==actor else other for other in prepared.party)
    return prepared,bound,actor


def release(prepared,item,actor,values):
    request=build_weighted_net_release(prepared,actor,item.item_id)
    rng=ScriptedD10(values)
    result=execute_recover_action(request,rng)
    rng.assert_exhausted()
    after,battlefield=weighted_net_release_item(prepared,item.item_id,result)
    decline=(PcFateDecline(actor,request.choice.test.id,'test',
        prepared.source.participant(actor).fate_policy)
        if actor in prepared.source.pc_activation_order else None)
    proof=PcNetReleaseProof(request,result,item.item_id,item,after,prepared.battlefield,battlefield,decline)
    updates=project_weighted_net_step(prepared,proof)
    injury=(next(member.injury for member in updates['party'] if member.actor_id==actor)
        if actor in prepared.source.pc_activation_order else
        next(enemy.state.injury for enemy in updates['enemies'] if enemy.state.actor_id==actor))
    return injury,updates


class ArmourNetConditionsTests(unittest.TestCase):
    def test_successful_last_net_release_keeps_heavy_and_plate_burden_for_both_sides(self):
        for npc in (False,True):
            for body,values in ((BodyArmour.HEAVY,[1,1]),(BodyArmour.FULL_PLATE,[1,1,1])):
                with self.subTest(npc=npc,body=body):
                    prepared,item,actor=prepared_net(npc=npc,body=body)
                    injury,updates=release(prepared,item,actor,values)
                    self.assertTrue(injury.conditions.has(Condition.BURDENED))
                    self.assertFalse(any(item.location is PcNetLocation.BOUND for item in updates['weighted_nets']))

    def test_successful_last_net_release_removes_a_pure_net_cause_for_both_sides(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                prepared,item,actor=prepared_net(npc=npc)
                injury,_=release(prepared,item,actor,[1,1,1])
                self.assertFalse(injury.conditions.has(Condition.BURDENED))

    def test_last_net_cleanup_keeps_an_actual_independent_briarroot_binding(self):
        attack,_=actual_attack()
        state,_=react(attack)
        injury=_release_target_injury(state,'pc',())
        self.assertTrue(injury.conditions.has(Condition.BURDENED))
        self.assertEqual(len(state.briarroot_bindings),1)


if __name__=='__main__':
    unittest.main()
