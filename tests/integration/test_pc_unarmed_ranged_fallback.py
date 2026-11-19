"""A real automatic Unarmed choice must precede the held bow's Close stop."""
from dataclasses import replace
import json
import unittest

from tests.support.pc_bow_scenarios import bow_profile, make_pc_bow_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.armour_models import ArmourLoadout, BodyArmour
from towr.domain.attack_models import ConditionImpactSpec
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon as W, PcTwoHandedGrip, PcWeaponHand
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeOutcome, initial_pc_melee_state
from towr.domain.pc_potion_models import PcPotionRecoverProof
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.recover_models import RecoverMode
from towr.domain.pc_short_opening_models import PcRangedCloseUnsupported
from towr.domain.pc_tactical_models import select_pc_tactic
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill
from towr.domain.weapon_inventory_models import WeaponItemSource, WeaponItemLocation, WeaponGrip
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class Ones:
    def __init__(self):
        self.calls = 0

    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('this battle uses actual d10 only')
        self.calls += 1
        return 1


def scene():
    base = make_pc_melee_scenario(max_rounds=1)
    member = base.party[0]
    member = replace(member, pc=replace(member.pc, weapon=W.WARBOW,
        weapon_skill=5, strength=5, toughness=20, agility=4, melee=2, brawn=5,
        ranged=bow_profile(ballistic_skill=3, shooting=5), armour_bonus=2),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        fate=replace(member.fate, rating=1, session_spend_limit=1),
        armour=ArmourLoadout((BodyArmour.HEAVY,), BodyArmour.HEAVY), armour_worn=True,
        combat_equipment=(
            PcWeaponItem('bow', W.WARBOW, PcItemLocation.HELD, PcTwoHandedGrip.BOTH),
            PcWeaponItem('dagger', W.DAGGER, PcItemLocation.CARRIED, None)))
    # Resilience20 prevents a Dagger Damage shortcut; Brawn5 genuinely scores
    # better than Melee2, so the real selector chooses the Unarmed condition.
    opponent = GeneratedNpc(1, 1, 20, 1, 2, 2,
        (WeaponItemSource('staff', W.STAFF, WeaponItemLocation.HELD, WeaponGrip.LEFT),),
        ArmourLoadout(), defence=2).participant('minion1')
    return replace(base, party=(member,), enemies=(opponent,),
        facts=replace(base.facts, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG))


def roundtrip(source):
    document = dict(schema_version='1', kind='pc_melee_simulation', request_id='unarmed-bow',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))
    return parse_pc_melee_simulation_request(json.dumps(document)).request.scenario


class PcUnarmedRangedFallbackTests(unittest.TestCase):
    def test_automatic_bow_and_carried_dagger_can_choose_real_unarmed_and_replay(self):
        source = scene()
        parsed = roundtrip(source)
        self.assertEqual(parsed, source)
        rng = Ones()
        result = run_pc_melee_scenario(parsed, rng)
        self.assertIsNone(result.unsupported)
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        self.assertGreater(rng.calls, 0)
        swaps = tuple(step for step in result.steps if type(step.proof) is PcWeaponSwapProof)
        self.assertEqual(len(swaps), 1)
        swap = swaps[0]
        choice = select_pc_tactic(swap.source, 'pc')
        self.assertTrue(choice.unarmed_attack)
        self.assertIsNone(choice.weapon_item_id)
        self.assertEqual(swap.proof.intent, choice)
        # Unarmed can use a kick/headbutt. Selecting it does not require a
        # fictional stow/drop interaction for the actually held bow.
        self.assertFalse(swap.proof.changes_equipment)
        before = swap.source.participant('pc').weapon_inventory
        after = swap.state.participant('pc').weapon_inventory
        self.assertIs(before.active.kind, W.WARBOW)
        self.assertIs(before.active.grip, WeaponGrip.BOTH)
        self.assertIsNone(after.active_item_id)
        self.assertEqual(tuple(item.id for item in after.items), tuple(item.id for item in before.items))
        self.assertEqual(after.items, before.items)
        outgoing = tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc')
        self.assertEqual(len(outgoing), 1)
        attack = outgoing[0]
        self.assertIs(attack.weapon_intent.attack_skill, Skill.BRAWN)
        self.assertIsNone(attack.weapon_intent.attack_use.primary_item_id)
        self.assertEqual(attack.weapon_intent.attack_use.used_hands, ())
        self.assertIs(type(attack.request.kernel_request.attack.impact_spec), ConditionImpactSpec)
        self.assertIsNone(attack.ranged_shot)
        self.assertIsNone(attack.npc_ranged_shot)
        self.assertEqual(len(tuple(step for step in result.steps if type(step.proof) is PcAttackProof)), 2)
        self.assertEqual(result.state.participant('pc').fate, source.party[0].fate)
        self.assertEqual(result.source, source)
        current = initial_pc_melee_state(source)
        for step in result.steps:
            current = apply_pc_melee_step(current, step)
        self.assertEqual(current, result.state)
        self.assertEqual(replace(result), result)

    def test_manual_bow_policy_keeps_the_real_close_shooting_boundary(self):
        source = make_pc_bow_scenario(weapon=W.WARBOW, backup=False,
            max_rounds=2, npc_toughness=20)
        self.assertIs(source.party[0].policy, PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
        rng = Ones()
        result = run_pc_melee_scenario(source, rng)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertIs(type(result.unsupported), PcRangedCloseUnsupported)
        self.assertEqual(result.unsupported.actor_id, 'pc1')
        self.assertEqual(result.unsupported.round_number, 2)
        self.assertGreater(rng.calls, 0)
        self.assertFalse(any(type(step.proof) is PcWeaponSwapProof for step in result.steps))
        self.assertEqual(len(tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == 'pc1')), 1)
        self.assertEqual(result.state.participant('pc1').weapon_inventory,
            initial_pc_melee_state(source).participant('pc1').weapon_inventory)

    def test_ally_standard_potion_recover_preserves_unarmed_selection_and_held_bow(self):
        base = scene()
        template = base.party[0]
        ally = replace(template, actor_id='pc2', fate=replace(template.fate, actor_id='pc2'),
            pc=replace(template.pc, id='ally-profile', weapon=W.STAFF,
                weapon_skill=1, strength=1, melee=2, brawn=None, ranged=None, armour_bonus=0),
            initial_weapon_hand=PcWeaponHand.LEFT,
            armour=ArmourLoadout(), armour_worn=False,
            combat_equipment=(PcWeaponItem('staff', W.STAFF, PcItemLocation.HELD, PcWeaponHand.LEFT),),
            consumables=(ConsumableItem('enhancement', ConsumableKind.ENHANCEMENT, 1, 'weapon_skill'),),
            defeat_decisions=tuple(replace(decision, attacker_id='pc2') for decision in template.defeat_decisions))
        source = replace(base, party=(template, ally), max_rounds=4,
            pc_activation_order=('pc', 'pc2'), enemy_target_priority=('pc', 'pc2'))
        source = roundtrip(source)
        result = run_pc_melee_scenario(source, Ones())
        self.assertIsNone(result.unsupported)
        recoveries = tuple(step for step in result.steps if type(step.proof) is PcPotionRecoverProof
            and step.proof.actor_id == 'pc2')
        self.assertEqual(len(recoveries), 1)
        recovery = recoveries[0]
        before = recovery.source.participant('pc')
        after = recovery.state.participant('pc')
        self.assertIs(recovery.proof.result.source_request.mode, RecoverMode.STANDARD)
        self.assertEqual(recovery.proof.result.resolution.source.object_interaction.object_id, 'enhancement')
        self.assertIsNone(before.weapon_inventory.active_item_id)
        self.assertEqual(after.weapon_inventory, before.weapon_inventory)
        bow = next(item for item in after.weapon_inventory.items if item.source_item_id == 'bow')
        self.assertIs(bow.location, WeaponItemLocation.HELD)
        self.assertIs(bow.grip, WeaponGrip.BOTH)
        self.assertEqual(after.fate, source.party[0].fate)
        self.assertEqual(recovery.source.participant('pc2').weapon_inventory,
            recovery.state.participant('pc2').weapon_inventory)
        self.assertEqual(recovery.source.participant('pc2').potions[0].quantity, 1)
        self.assertFalse(recovery.state.participant('pc2').potions)
        self.assertIn('weapon_skill', recovery.state.participant('pc2').enhancements)
        current = initial_pc_melee_state(source)
        for step in result.steps:
            current = apply_pc_melee_step(current, step)
        self.assertEqual(current, result.state)
        self.assertEqual(replace(result), result)


if __name__ == '__main__':
    unittest.main()
