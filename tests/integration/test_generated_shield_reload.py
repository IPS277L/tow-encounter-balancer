"""Real generated NPC Shoot→Reload→paid Shield Recover→Shoot owner path."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.armour_models import ArmourLoadout, BodyArmour, HelmetKind, ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.pc_melee_models import PcMeleePolicy, PcFatePolicy, PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof, pc_npc_ranged_weapon
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_shield_models import (
    PcNpcShieldDropProof, PcNpcShieldRecoverProof, NpcShieldLocation,
)
from towr.domain.turn_models import CombatActionKind
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def scene(*, shield=ShieldKind.SHIELD, weapon=GeneratedWeapon.PISTOL, helmet_only=False):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=8)
    member = source.party[0]
    member = replace(member, policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE, near_miss_policy=None, glorious_policy=None,
        pc=replace(member.pc, weapon=PcMeleeWeapon.STAFF, weapon_skill=10, strength=1,
            toughness=20, agility=10, melee=1, defence=6, athletics=6))
    armour = (ArmourLoadout(helmet=HelmetKind.HELMET, shield=shield) if helmet_only else
        ArmourLoadout((BodyArmour.METEORIC_IRON,), BodyArmour.METEORIC_IRON,
            HelmetKind.HUNT, shield))
    firearm = weapon is not GeneratedWeapon.REPEATER_HANDBOW
    npc = GeneratedNpc(1, 1, 20, 10, 2, 6, initial_generated_weapons(weapon), armour, defence=2,
        ranged=GeneratedRangedFacts(1, 2,    True,
            True if firearm else None, True if firearm else None), initiative=6, dexterity=6)
    actor = source.enemy_activation_order[0]
    return replace(source, party=(member,), enemies=(npc.participant(actor),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc, actor),))


class GeneratedShieldReloadIntegrationTests(unittest.TestCase):
    def execute(self, source):
        result = run_pc_melee_scenario(source, Random(42))
        self.assertIsNone(result.unsupported)
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        return result

    def test_real_pistol_cycle_drops_then_pays_recover_before_next_shot(self):
        for shield in ShieldKind:
            with self.subTest(shield=shield):
                source = scene(shield=shield)
                result = self.execute(source)
                actor = source.enemy_activation_order[0]
                shots = [(index, step) for index, step in enumerate(result.steps)
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id == actor]
                drops = [(index, step) for index, step in enumerate(result.steps)
                    if type(step.proof) is PcNpcShieldDropProof]
                pickups = [(index, step) for index, step in enumerate(result.steps)
                    if type(step.proof) is PcNpcShieldRecoverProof]
                self.assertGreaterEqual(len(shots), 2)
                self.assertGreaterEqual(len(drops), 1)
                self.assertGreaterEqual(len(pickups), 1)
                first_shot = shots[0][0]
                first_drop, drop_step = drops[0]
                first_pickup, pickup_step = pickups[0]
                next_shot = next(index for index, _ in shots if index > first_pickup)
                self.assertLess(first_shot, first_drop)
                self.assertLess(first_drop, first_pickup)
                self.assertLess(first_pickup, next_shot)
                reloads = [step for step in result.steps[first_drop+1:first_pickup]
                    if type(step.proof) is PcNpcRangedReloadProof]
                self.assertTrue(reloads)
                self.assertTrue(reloads[-1].proof.result.state.loaded)
                self.assertTrue(all(not step.source.enemy(actor).state.holds_shield for step in reloads))
                self.assertTrue(drop_step.source.enemy(actor).state.holds_shield)
                self.assertFalse(drop_step.state.enemy(actor).state.holds_shield)
                self.assertFalse(pickup_step.source.enemy(actor).state.holds_shield)
                self.assertTrue(pickup_step.state.enemy(actor).state.holds_shield)
                receipt = pickup_step.proof.result.slot
                self.assertTrue(receipt.executed)
                self.assertIs(receipt.declaration.kind, CombatActionKind.RECOVER)
                self.assertNotEqual(pickup_step.proof.request.round_state.round_number,
                    result.steps[next_shot].proof.execution.slot.execution.round_number)
                self.assertIs(drop_step.proof.previous.kind, shield)
                self.assertEqual(drop_step.proof.state.item_id, pickup_step.proof.state.item_id)
                self.assertIs(pickup_step.proof.state.location, NpcShieldLocation.HELD)
                for step in (drop_step, pickup_step):
                    before = step.source.enemy(actor).state.current_resilience
                    after = step.state.enemy(actor).state.current_resilience
                    self.assertEqual(after.bonus-before.bonus, -1 if step is drop_step else 1)
                    self.assertEqual(after.toughness, before.toughness)
                    self.assertTrue(after.mundane_armour_ward)
                    self.assertEqual(step.state.enemy(actor).definition.generated_components.armour,
                        source.enemies[0].definition.generated_components.armour)
                with self.assertRaises(ValueError):
                    PcMeleeStep(drop_step.state, drop_step.proof)
                with self.assertRaises(ValueError):
                    PcMeleeStep(pickup_step.state, pickup_step.proof)
                forged = deepcopy(pickup_step.proof)
                object.__setattr__(forged.state, 'item_id', actor+':replacement-shield')
                with self.assertRaises((TypeError, ValueError)):
                    PcMeleeStep(pickup_step.source, forged)

    def test_helmet_only_stays_armoured_while_shield_is_on_the_ground(self):
        result = self.execute(scene(helmet_only=True))
        dropped = next(step for step in result.steps if type(step.proof) is PcNpcShieldDropProof)
        actor = dropped.proof.actor_id
        resilience = dropped.state.enemy(actor).state.current_resilience
        self.assertEqual(resilience.bonus, 0)
        self.assertTrue(resilience.is_armoured)
        self.assertIs(resilience.armoured, True)


if __name__ == '__main__':
    unittest.main()
