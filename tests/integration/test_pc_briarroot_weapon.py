"""Actual Wound drops and atomic standard Recover retain finite equipment."""
from dataclasses import replace
from itertools import chain, repeat
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_pc_briarroot import actual_attack
from towr.domain.pc_briarroot_models import PcBriarrootProof
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.condition_models import StaggerChoice
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponDropProof
from towr.domain.pc_melee_result_models import (
    PcHandDropProof, PcMeleeStep, PcRecoverProof, initial_pc_melee_state,
    PcAttackProof,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class PcBriarrootWeaponIntegrationTests(unittest.TestCase):
    def test_actual_binding_excludes_give_ground_from_repeated_stagger_for_both_attack_builders(self):
        for mounted in (False,True):
            for shield_kind in (ShieldKind.BRIARROOT,ShieldKind.SHIELD):
                with self.subTest(mounted=mounted,shield=shield_kind):
                    setup,_=actual_attack(inventory=True,spatial=True)
                    source=setup.source
                    member=source.party[0]
                    member=replace(member,pc=replace(member.pc,toughness=20,
                        weapon=PcMeleeWeapon.DAGGER if mounted else member.pc.weapon,
                        weapon_skill=1 if mounted else member.pc.weapon_skill,
                        strength=1 if mounted else member.pc.strength),
                        mount=CombatMount.HORSE if mounted else None,
                        combat_equipment=((replace(member.combat_equipment[0],weapon=PcMeleeWeapon.DAGGER),)
                            if mounted else member.combat_equipment))
                    npc=replace(source.enemies[0].definition.generated_components,
                        armour=ArmourLoadout(shield=shield_kind),mount=CombatMount.HORSE if mounted else None)
                    source=replace(source,party=(member,),enemies=(npc.participant('minion1'),),
                        facts=replace(source.facts,unmounted=not mounted))
                    values=([10]*3+[1]*2+[1]*3+[10]+[1] if mounted else
                        [10]*3+[1]*2+[1]*2+[10]*3+[1])
                    result=run_pc_melee_scenario(source,SequenceRandom(values))
                    attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
                        and step.proof.request.actor_id=='minion1')
                    self.assertEqual(attack.proof.mount_attack is not None,mounted)
                    stagger=attack.proof.execution.resolution.stagger
                    self.assertIsNotNone(stagger)
                    self.assertIn(StaggerChoice.SUFFER_WOUND,stagger.allowed_choices)
                    self.assertIn(StaggerChoice.FALL_PRONE,stagger.allowed_choices)
                    self.assertEqual(StaggerChoice.GIVE_GROUND in stagger.allowed_choices,
                        shield_kind is ShieldKind.SHIELD)
                    self.assertEqual(attack.proof.request.kernel_request.can_target_leave_zone,
                        shield_kind is ShieldKind.SHIELD)
                    state=initial_pc_melee_state(source)
                    for step in result.steps:state=apply_pc_melee_step(state,step)
                    self.assertEqual(state,result.state)

    def test_actual_wound_drop_then_paid_recover_has_one_atomic_physical_receipt(self):
        setup, _ = actual_attack(inventory=True, spatial=True)
        # Cause a direct damaging Wound: an automatic PC now legally chooses
        # Prone instead of a Wound from repeated Staggered when bound in Close.
        npc = replace(setup.source.enemies[0].definition.generated_components,
            strength=3, brawn=None)
        source = replace(setup.source, max_rounds=2, enemies=(npc.participant('minion1'),))
        result = run_pc_melee_scenario(source, SequenceRandom(chain(
            [10, 10, 10, 1, 1, 1, 1, 10, 10, 10, 8, 1], repeat(1))))
        loss, = (step for step in result.steps if type(step.proof) is PcBriarrootWeaponDropProof)
        recover, = (step for step in result.steps if type(step.proof) is PcRecoverProof)
        index = result.steps.index(loss)
        self.assertIs(type(result.steps[index-1].proof), PcHandDropProof)
        self.assertIs(type(result.steps[index+1].proof), PcBriarrootProof)
        self.assertEqual(loss.source.round_state, loss.state.round_state)
        self.assertIsNone(loss.state.participant('pc').weapon_hand)
        item, = loss.state.briarroot_dropped_weapons
        self.assertIsNotNone(item.ground)
        receipt = recover.proof.briarroot_weapon_pickup
        self.assertEqual(receipt.previous_item, item)
        self.assertEqual(receipt.action_id, recover.proof.result.request_id)
        self.assertIsNone(recover.state.briarroot_dropped_weapons[0].ground)
        self.assertIsNotNone(recover.state.participant('pc').weapon_hand)
        self.assertTrue(recover.state.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(result.executed_actions, 4)
        state = initial_pc_melee_state(source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)
        with self.assertRaises(ValueError):
            PcMeleeStep(recover.source, replace(recover.proof, briarroot_weapon_pickup=None))
        with self.assertRaises(ValueError):
            apply_pc_melee_step(recover.state, recover)


if __name__ == '__main__':
    unittest.main()
