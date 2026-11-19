"""Pre-price choices and source-forgery boundaries, using literal native runs."""
from dataclasses import replace
import unittest

from tests.unit.test_pc_combat_talent_execution import scenario, help_source
from tests.integration.test_shared_pc_inventory import two_sword_source
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedTalent
from towr.domain.pc_generated_talents import PcWildAttackProof
from towr.domain.pc_melee_result_models import PcAttackProof, PcHelpProof, PcMeleeStep, build_pc_melee_attack
from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent, weapon_use_hand
from towr.domain.weapon_inventory_models import WeaponGrip
from towr.domain.weapon_use_models import WeaponUse
from towr.engine.pc_melee_runner import run_pc_melee_scenario


class Tens:
    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('unexpected dice')
        return 10


class PcWeaponIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wild = run_pc_melee_scenario(scenario(npc_talents=(GeneratedTalent.WILD_ATTACK,)), Tens())
        cls.pc_wild = run_pc_melee_scenario(scenario(), Tens())
        cls.dual = run_pc_melee_scenario(two_sword_source(), Tens())

    def test_both_roles_reuse_the_exact_pre_price_choice(self):
        prices = tuple((result,step) for result in (self.pc_wild, self.wild) for step in result.steps
            if type(step.proof) is PcWildAttackProof)
        self.assertEqual(tuple(step.proof.actor_id for _,step in prices), ('pc1', 'minion1'))
        for result,step in prices:
            with self.subTest(actor=step.proof.actor_id):
                committed = step.proof.attack_weapon_intent
                self.assertEqual(build_pc_attack_weapon_intent(step.source), committed)
                self.assertIs(build_pc_attack_weapon_intent(step.state), committed)
                self.assertEqual(committed.attack_use.used_hands, (WeaponGrip.LEFT,))
                attack = next(item.proof for item in result.steps
                    if type(item.proof) is PcAttackProof
                    and item.proof.request.actor_id == step.proof.actor_id)
                self.assertIs(attack.weapon_intent, committed)
                self.assertTrue(attack.request.kernel_request.attack.attacker_is_staggered)
                with self.assertRaises(ValueError):
                    PcMeleeStep(step.source, replace(step.proof, attack_weapon_intent=None))

    def test_equivalent_sword_choice_and_nonphysical_metadata_cannot_be_substituted(self):
        step = next(step for step in self.dual.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc1')
        intent = step.proof.weapon_intent
        use = intent.attack_use
        other = next(item for item in use.inventory.items if item.id != use.primary_item_id)
        changed = (
            replace(intent, action_id='foreign'),
            replace(intent, target_id='foreign'),
            replace(intent, attack_use=replace(use, primary_item_id=other.id)),
            replace(intent, attack_use=replace(use, usable_hands=tuple(reversed(use.usable_hands)))),
        )
        for forged in changed:
            with self.subTest(forged=forged), self.assertRaises(ValueError):
                PcMeleeStep(step.source, replace(step.proof, weapon_intent=forged))

    def test_frozen_protection_keeps_both_swords_but_uses_current_staggered_modifiers(self):
        step = next(step for step in self.dual.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id == 'pc1')
        intent = step.proof.weapon_intent
        # Prepared boundary: price-independent source choice is unchanged while
        # Conditions change; this is not claimed as a complete native prefix.
        member = step.source.participant('pc1')
        member = replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.without_condition(Condition.STAGGERED)))
        prepared = replace(step.source, party=(member,))
        intent = build_pc_attack_weapon_intent(prepared)
        self.assertEqual(len(intent.protection_use.item_ids), 2)
        _, before = build_pc_melee_attack(prepared, weapon_intent=intent)
        staggered = replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.STAGGERED)))
        _, after = build_pc_melee_attack(replace(prepared, party=(staggered,)), weapon_intent=intent)
        self.assertEqual(sum(m.amount for m in before.options[0].test.dice_modifiers), 2)
        self.assertEqual(sum(m.amount for m in after.options[0].test.dice_modifiers), 0)
        self.assertEqual(intent.protection_use.used_hands, (WeaponGrip.LEFT, WeaponGrip.RIGHT))

    def test_missing_protection_and_changed_inventory_origin_are_rejected_by_replay(self):
        step = next(step for step in self.dual.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id == 'pc1')
        intent = step.proof.weapon_intent
        use = intent.protection_use
        # The native trace can choose a single Sword after it is Staggered.
        inventory = use.inventory
        item = inventory.items[0]
        changed_item = replace(item, source=replace(item.source, initial_grip=WeaponGrip.RIGHT))
        forged_inventory = replace(inventory, items=(changed_item, *inventory.items[1:]))
        for changed in (replace(intent, protection_use=None),
                replace(intent, protection_use=replace(use, inventory=forged_inventory))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                PcMeleeStep(step.source, replace(step.proof, weapon_intent=changed))

    def test_wild_help_uses_the_same_pre_price_item_and_rejects_another_hand(self):
        result = run_pc_melee_scenario(help_source(), Tens())
        price = next(step for step in result.steps if type(step.proof) is PcWildAttackProof)
        help_step = next(step for step in result.steps if type(step.proof) is PcHelpProof)
        self.assertIsNone(price.proof.attack_weapon_intent)
        self.assertIs(help_step.proof.weapon_use, price.proof.help_weapon_use)
        self.assertEqual(help_step.proof.weapon_use.used_hands, (WeaponGrip.LEFT,))
        with self.assertRaises(ValueError):
            PcMeleeStep(help_step.source, replace(help_step.proof, weapon_use=None))

    def test_weapon_use_hand_counts_additional_implement_and_shield_hands(self):
        step = next(step for step in self.dual.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc1')
        use = step.proof.weapon_intent.attack_use
        other = next(item for item in use.inventory.items if item.id != use.primary_item_id)
        dual = WeaponUse(use.actor_id, use.inventory, use.primary_item_id, (other.id,), use.usable_hands)
        from towr.domain.pc_melee_models import PcTwoHandedGrip
        self.assertIs(weapon_use_hand(dual), PcTwoHandedGrip.BOTH)
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        from towr.domain.weapon_use_models import WeaponProtectionUse
        from towr.domain.test_models import Skill
        shield_inventory = replace(use.inventory, shield_hand=other.grip,
            items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None)
                if item.id==other.id else item for item in use.inventory.items))
        protection = WeaponProtectionUse(use.actor_id,shield_inventory,Skill.DEFENCE,
            (use.primary_item_id,),True,use.usable_hands)
        self.assertIs(weapon_use_hand(protection), PcTwoHandedGrip.BOTH)
        self.assertIsNone(weapon_use_hand(None))

    def test_wild_dual_attack_retains_its_additional_damage_source_and_both_hands(self):
        from towr.domain.armour_models import ArmourLoadout, BodyArmour
        from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
        from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
        source = scenario()
        member = source.party[0]
        member = replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.SWORD),
            combat_equipment=(PcWeaponItem('sword',PcMeleeWeapon.SWORD,PcItemLocation.HELD,PcWeaponHand.LEFT),
                PcWeaponItem('axe',PcMeleeWeapon.AXE,PcItemLocation.HELD,PcWeaponHand.RIGHT)))
        npc = replace(source.enemies[0].definition.generated_components,
            armour=ArmourLoadout(body=(BodyArmour.LIGHT,),benefit=BodyArmour.LIGHT))
        source = replace(source, party=(member,), enemies=(npc.participant('minion1'),))
        result = run_pc_melee_scenario(source,Tens())
        price = next(step for step in result.steps if type(step.proof) is PcWildAttackProof)
        attack = next(step for step in result.steps if type(step.proof) is PcAttackProof)
        use = price.proof.attack_weapon_intent.attack_use
        self.assertEqual(tuple(use.inventory.item(identifier).source_item_id for identifier in use.item_ids),
            ('sword','axe'))
        self.assertEqual(use.used_hands,(WeaponGrip.LEFT,WeaponGrip.RIGHT))
        self.assertIs(attack.proof.weapon_intent,price.proof.attack_weapon_intent)
        modifiers = attack.proof.request.kernel_request.attack.impact_spec.damage_modifiers
        self.assertEqual(sum(mod.amount for mod in modifiers),1)


if __name__ == '__main__':
    unittest.main()
