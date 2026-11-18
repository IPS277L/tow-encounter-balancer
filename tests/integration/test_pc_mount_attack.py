"""Real paid mount-only Attack, Fate and post-Wound hand state."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from itertools import chain,repeat
import unittest

from tests.unit.test_pc_demigryph import reserved, Ones
from tests.helpers import SequenceRandom
from tests.integration.test_pc_two_handed_recover import scene, LiteralPrefixThenMisses
from tests.integration.test_pc_no_hand_recover import scene as ranged_no_hand_scene, prefix as no_hand_prefix
from tests.unit.test_generated_npc_ranged_execution import scene as ranged_scene,component as ranged_component
from tests.support.pc_melee_scripted import heavy_prefix
from towr.domain.fate_models import FateSpendKind
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedTalent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.pc_generated_talents import PcWildAttackProof
from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
from towr.domain.pc_mount_attack_models import PcMountedAttackMode
from towr.domain.pc_mount_models import RiderKind
from towr.domain.pc_mount_attack_models import PcMountAttackAbility
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
from towr.domain.pc_melee_models import PcMeleeWeapon,PcFatePolicy,PcGloriousPolicy
from towr.domain.pc_heavy_wound_models import usable_hands
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,initial_pc_melee_state
from towr.domain.test_models import Skill,InlineProfile
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class PcMountAttackIntegrationTests(unittest.TestCase):
    def test_weak_rider_uses_mount_as_the_one_paid_primary_attack(self):
        source=reserved(mount=CombatMount.HORSE).source
        pc=source.party[0]
        pc=replace(pc,pc=replace(pc.pc,weapon_skill=1,strength=1,weapon=PcMeleeWeapon.DAGGER))
        result=run_pc_melee_scenario(replace(source,party=(pc,)),Ones())
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertIs(attack.proof.mount_attack.ability,PcMountAttackAbility.HOOVES)
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.profile,InlineProfile(3,3,6))
        self.assertEqual(attack.proof.execution.actor_id,'pc1')
        self.assertEqual(len(attack.state.round_state.active_turn.action_slots),1)
        self.assertFalse(any(type(step.proof) is PcDemigryphStrikeProof for step in result.steps))
        with self.assertRaises(ValueError):
            PcMeleeStep(attack.source,replace(attack.proof,mount_attack=None))

    def test_real_unusable_arm_does_not_restore_two_handed_weapon_before_mount_attack(self):
        source=scene(rounds=2)
        pc=replace(source.party[0],mount=CombatMount.HORSE)
        source=replace(source,party=(pc,),facts=replace(source.facts,unmounted=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG))
        result=run_pc_melee_scenario(source,LiteralPrefixThenMisses(heavy_prefix(16)))
        attacks=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2]
        self.assertEqual(len(attacks),1)
        attack=attacks[0]
        self.assertEqual(len(usable_hands(attack.source.participant('pc1'))),1)
        self.assertIsNotNone(attack.proof.mount_attack)
        self.assertEqual(attack.state.participant('pc1').body_facts,attack.source.participant('pc1').body_facts)
        self.assertEqual(attack.state.participant('pc1').weapon_hand,attack.source.participant('pc1').weapon_hand)
        state=initial_pc_melee_state(source)
        for step in result.steps:state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_player_fate_can_apply_to_the_actual_mount_test(self):
        source=reserved(mount=CombatMount.HORSE).source
        pc=source.party[0]
        pc=replace(pc,pc=replace(pc.pc,weapon_skill=1,strength=1,weapon=PcMeleeWeapon.DAGGER),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.MELEE,),10,0))
        result=run_pc_melee_scenario(replace(source,party=(pc,)),
            SequenceRandom(chain([10,10,10,1,1,1],repeat(1))))
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertIsNotNone(attack.proof.mount_attack)
        self.assertIsNotNone(attack.proof.glorious)
        self.assertTrue(any(spend.kind is FateSpendKind.GLORIOUS_TEST
            for spend in result.state.participant('pc1').fate.spends))

    def test_npc_wild_price_retains_the_chosen_rider_mode_before_its_test(self):
        source=reserved(actor='minion1').source
        npc=GeneratedNpc(6,4,20,3,6,4,initial_generated_weapons(GeneratedWeapon.SWORD),ArmourLoadout(),defence=4,
            talents=(GeneratedTalent.WILD_ATTACK,),mount=CombatMount.DEMIGRYPH,
            rider_kind=RiderKind.HUMAN).participant('minion1')
        result=run_pc_melee_scenario(replace(source,enemies=(npc,)),Ones())
        price,=(step for step in result.steps if type(step.proof) is PcWildAttackProof)
        self.assertIs(price.proof.mount_intent.mode,PcMountedAttackMode.RIDER)
        self.assertEqual(price.proof.mount_intent.source_round,price.source.round_state)
        actual=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        self.assertIsNone(actual.mount_attack)
        self.assertIsNone(actual.glorious)
        self.assertTrue(any(modifier.quality.value=='glorious'
            for modifier in actual.request.kernel_request.attack.attacker_test.quality_modifiers))
        with self.assertRaises(ValueError):
            PcMeleeStep(price.source,replace(price.proof,mount_intent=None))

    def test_npc_mount_attack_preserves_its_unfired_pistol(self):
        source=ranged_scene(automatic=True)
        npc=replace(ranged_component(),mount=CombatMount.HORSE).participant('minion1')
        source=replace(source,enemies=(npc,),facts=replace(source.facts,unmounted=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG))
        result=run_pc_melee_scenario(source,Ones())
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        self.assertIsNotNone(attack.mount_attack)
        self.assertIsNone(attack.npc_ranged_shot)
        self.assertTrue(pc_npc_ranged_weapon(result.state,'minion1').loaded)

    def test_handless_shooter_uses_mount_without_consuming_or_reloading_the_pistol(self):
        source=ranged_no_hand_scene(endurance=10)
        pc=replace(source.party[0],mount=CombatMount.HORSE)
        source=replace(source,party=(pc,),max_rounds=2,
            facts=replace(source.facts,unmounted=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG))
        result=run_pc_melee_scenario(source,LiteralPrefixThenMisses(no_hand_prefix()))
        attack,=(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1' and step.source.round_state.round_number==2)
        self.assertEqual(usable_hands(attack.source.participant('pc1')),())
        self.assertIsNotNone(attack.proof.mount_attack)
        self.assertIsNone(attack.proof.ranged_shot)
        self.assertEqual(attack.source.participant('pc1').ranged,attack.state.participant('pc1').ranged)
        self.assertEqual(attack.source.participant('pc1').weapon_inventory,attack.state.participant('pc1').weapon_inventory)
        self.assertIsNone(result.unsupported)


if __name__=='__main__':unittest.main()
