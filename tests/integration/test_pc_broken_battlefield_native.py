"""Actual Demigryph/Fearsome/Give Ground causes Broken turns, without injection."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import magic_battle,run_native
from towr.domain.condition_models import Condition
from towr.domain.pc_broken_battlefield_models import (
    PcBrokenMoveProof,PcBrokenRunProof,PcBrokenBlockedProof,PcBrokenBlockReason,
)
from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
from towr.domain.pc_give_ground_models import PcGiveGroundProof,PcAfterGiveGroundProof
from towr.domain.pc_melee_result_models import PcAttackProof,PcRecoverProof,PcIncapacitatedTurnEndProof
from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof,PcBattlefieldMoveProof
from towr.domain.pc_mount_models import CombatMount,RiderKind,DEMIGRYPH_FEARSOME_RULE_ID
from towr.domain.pc_weapon_area_models import PcWeaponHazardProof,ABLAZE_HAZARD_RULE_ID
from towr.domain.weapon_catalog import WeaponKind


def mounted(source,actor):
    if actor in source.pc_activation_order:
        party=tuple(replace(member,mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN)
            if member.actor_id==actor else member for member in source.party)
        return replace(source,party=party,facts=replace(source.facts,unmounted=False))
    enemies=tuple(replace(enemy.definition.generated_components,mount=CombatMount.DEMIGRYPH,
        rider_kind=RiderKind.HUMAN).participant(actor) if enemy.state.actor_id==actor else enemy
        for enemy in source.enemies)
    return replace(source,enemies=enemies,facts=replace(source.facts,unmounted=False))


def injury(state,actor):
    return state.participant(actor).injury if actor in state.source.pc_activation_order else state.enemy(actor).state.injury


class BrokenBattlefieldNativeTests(unittest.TestCase):
    def test_fearsome_give_ground_leads_to_safe_standard_recover_in_both_roles(self):
        for npc_target in (False,True):
            with self.subTest(npc_target=npc_target):
                source=magic_battle('staff',pc_ws=6 if npc_target else 1,
                    npc_ws=1 if npc_target else 6,rounds=2)
                attacker='pc' if npc_target else 'generated-npc:1'
                target='generated-npc:1' if npc_target else 'pc'
                source=mounted(source,attacker)
                result=run_native(self,source)
                applied=[step for step in result.steps if type(step.proof) is PcAfterGiveGroundProof
                    and step.proof.result.state.conditions.has(Condition.BROKEN)]
                self.assertTrue(applied)
                broken=applied[0]
                self.assertEqual(broken.proof.request.rule_id,DEMIGRYPH_FEARSOME_RULE_ID)
                self.assertTrue(injury(broken.state,target).conditions.has(Condition.BROKEN))
                gg=next(step for step in result.steps if type(step.proof) is PcGiveGroundProof
                    and step.proof.actor_id==target)
                self.assertLess(result.steps.index(gg),result.steps.index(broken))
                recoveries=[step for step in result.steps[result.steps.index(broken)+1:]
                    if type(step.proof) in (PcRecoverProof,PcBattlefieldRecoverProof)
                    and (step.proof.result.source_request.actor_id if type(step.proof) is PcRecoverProof
                        else step.proof.request.actor_id)==target]
                self.assertTrue(recoveries)
                first=recoveries[0]
                self.assertEqual(first.proof.result.source_request.mode.value,'standard')
                self.assertTrue(injury(first.state,target).conditions.has(Condition.BROKEN))
                # No follow-up approach or Attack by the frightened target.
                self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id==target
                    for step in result.steps[result.steps.index(broken)+1:]))
                self.assertFalse(any(type(step.proof) is PcBattlefieldMoveProof and step.proof.actor_id==target
                    for step in result.steps[result.steps.index(broken)+1:]))
                self.assertEqual(result.executed_actions,4)
                # Wicked Claws belongs to its rider's one action, never a third slot.
                if npc_target:
                    self.assertTrue(any(type(step.proof) is PcDemigryphStrikeProof for step in result.steps))

    def test_real_broken_then_prone_in_an_unsafe_zone_blocks_turn_without_fake_action(self):
        for npc_target in (False,True):
            with self.subTest(npc_target=npc_target):
                source=magic_battle('staff',pc_ws=6 if npc_target else 1,
                    npc_ws=1 if npc_target else 6,players=2 if npc_target else 1,
                    count=1 if npc_target else 2,rounds=1 if npc_target else 2)
                attacker='pc' if npc_target else 'generated-npc:1'
                target='generated-npc:1' if npc_target else 'pc'
                source=mounted(source,attacker)
                result=run_native(self,source)
                blocked=next(step for step in result.steps if type(step.proof) is PcBrokenBlockedProof
                    and step.proof.actor_id==target)
                self.assertIs(blocked.proof.reason,PcBrokenBlockReason.PRONE)
                self.assertTrue(injury(blocked.source,target).conditions.has(Condition.BROKEN))
                self.assertTrue(injury(blocked.source,target).conditions.has(Condition.PRONE))
                self.assertEqual(blocked.source.round_state,blocked.state.round_state)
                self.assertEqual(blocked.state.round_state.active_turn.action_slots,())
                self.assertEqual(blocked.source.battlefield,blocked.state.battlefield)
                self.assertFalse(result.state.exited_npc_ids)
                self.assertEqual(result.executed_actions,2 if npc_target else 5)

    def test_blocked_burning_turn_still_resolves_actual_ablaze_hazard_before_turn_end(self):
        source=magic_battle('staff',pc_ws=1,npc_ws=6,count=3,rounds=2)
        source=mounted(source,'generated-npc:1')
        enemy=source.enemies[1]
        components=enemy.definition.generated_components
        oil=replace(components,weapons=(replace(components.weapons[0],kind=WeaponKind.OIL_FLASK),),
            throwing=5,ballistic_skill=6)
        source=replace(source,enemies=(source.enemies[0],oil.participant(enemy.state.actor_id),source.enemies[2]))
        result=run_native(self,source)
        blocked=next(step for step in result.steps if type(step.proof) is PcBrokenBlockedProof
            and step.proof.actor_id=='pc')
        self.assertTrue(injury(blocked.source,'pc').conditions.has(Condition.ABLAZE))
        self.assertTrue(injury(blocked.source,'pc').conditions.has(Condition.PRONE))
        hazard=next(step for step in result.steps[result.steps.index(blocked)+1:]
            if type(step.proof) is PcWeaponHazardProof and step.proof.request.actor_id=='pc'
            and step.proof.request.exposure.rule_id==ABLAZE_HAZARD_RULE_ID)
        ended=next(step for step in result.steps[result.steps.index(blocked)+1:]
            if type(step.proof) is PcIncapacitatedTurnEndProof)
        self.assertLess(result.steps.index(hazard),result.steps.index(ended))
        self.assertEqual(hazard.source.round_state.active_turn.action_slots,())
        self.assertEqual(hazard.source.round_state,hazard.state.round_state)
        self.assertTrue(injury(hazard.state,'pc').conditions.has(Condition.BROKEN))
        self.assertEqual(result.executed_actions,7)


if __name__=='__main__':
    unittest.main()
