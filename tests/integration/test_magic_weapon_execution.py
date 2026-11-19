"""Magic weapon components through both roles, real action slots and replay."""
import unittest
from unittest.mock import patch

from tests.support.magic_weapon_battles import magic_battle, run_native
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSpendKind
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeOutcome
from towr.domain.test_models import TestQuality
from towr.domain.turn_models import CombatActionSlotResult
from towr.domain.weapon_effect_preparation import TRICKSTER_DEFENCE_RULE_ID
from towr.domain.weapon_quality_preparation import (
    DUELLIST_GRIM_RULE_ID, DUELLIST_GLORIOUS_RULE_ID, JUSTICE_SINGLE_COMBAT_RULE_ID,
)
from towr.domain.weapon_impact_preparation import JUSTICE_WOUND_DICE_RULE_ID


def attacks(result, actor=None):
    return tuple(step for step in result.steps if type(step.proof) is PcAttackProof
        and (actor is None or step.proof.request.actor_id == actor))


class MagicWeaponExecutionTests(unittest.TestCase):
    def test_duellist_trickster_and_justice_use_real_components_in_both_roles(self):
        for kind in ('duellist_blades', 'trickster_blade', 'sword_of_justice'):
            for npc_magic in (False, True):
                with self.subTest(kind=kind, npc_magic=npc_magic):
                    source = magic_battle(kind, npc_magic=npc_magic)
                    result = run_native(self, source)
                    actor = (source.enemy_activation_order if npc_magic else source.pc_activation_order)[0]
                    actual = attacks(result, actor)
                    self.assertTrue(actual)
                    self.assertTrue(all(step.proof.weapon_intent.attack_use.kind.value == kind
                        for step in actual))
                    self.assertTrue(all(step.proof.request.kernel_request.attack.impact_spec.magical_source
                        for step in actual))

    def test_duellist_second_attack_is_distinct_grim_then_glorious_with_no_fate_or_third(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_trial
        for npc_magic in (False, True):
            with self.subTest(npc_magic=npc_magic):
                source = magic_battle('duellist_blades', npc_magic=npc_magic)
                result = run_native(self, source)
                actor = (source.enemy_activation_order if npc_magic else source.pc_activation_order)[0]
                actual = attacks(result, actor)
                self.assertEqual(len(actual), 2)
                self.assertEqual(tuple(step.proof.execution.slot_index for step in actual), (1, 2))
                self.assertEqual(actual[0].proof.weapon_intent.attack_use.primary_item_id,
                    actual[1].proof.weapon_intent.attack_use.primary_item_id)
                self.assertEqual(tuple(tuple(modifier.rule_id for modifier in
                    step.proof.request.kernel_request.attack.attacker_test.quality_modifiers)
                    for step in actual), ((DUELLIST_GRIM_RULE_ID,), (DUELLIST_GLORIOUS_RULE_ID,)))
                self.assertIs(actual[0].proof.execution.resolution.attack.attacker_test.trace.quality, TestQuality.GRIM)
                self.assertIs(actual[1].proof.execution.resolution.attack.attacker_test.trace.quality, TestQuality.GLORIOUS)
                grant = actual[1].proof.execution.slot.duellist_blades
                self.assertEqual(grant.first_execution, actual[0].proof.execution.slot.execution)
                self.assertEqual(grant.weapon_use, actual[0].proof.weapon_intent.attack_use)
                self.assertEqual(grant.target_id, actual[1].proof.request.target_id)
                self.assertFalse(any(spend.kind is FateSpendKind.SECOND_ACTION
                    for member in result.state.party for spend in member.fate.spends))
                request = PcMeleeSimulationRequest(source, 42, 1)
                with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario', return_value=result):
                    record = run_pc_melee_trial(request, 0)
                self.assertEqual(record.executed_actions, result.executed_actions)
                # Both Duellist actions are paid; the ordinary opponent keeps
                # its own turn after a legal reaction avoids the second Wound.
                self.assertEqual(result.executed_actions, 3)
                if npc_magic:
                    self.assertEqual(record.npc_extra_attack_counts[0].count, 1)

    def test_trickster_defence_requires_held_usable_item_and_not_staggered(self):
        for npc_magic in (False, True):
            with self.subTest(npc_magic=npc_magic):
                source = magic_battle('trickster_blade', npc_magic=npc_magic)
                result = run_native(self, source)
                actor = (source.enemy_activation_order if npc_magic else source.pc_activation_order)[0]
                incoming = next(step for step in attacks(result) if step.proof.request.target_id == actor)
                test = incoming.proof.request.kernel_request.attack.defender_test
                self.assertEqual(tuple(modifier.amount for modifier in test.dice_modifiers
                    if modifier.rule_id == TRICKSTER_DEFENCE_RULE_ID), (1,))
                self.assertEqual(incoming.proof.weapon_intent.protection_use.item_ids,
                    (incoming.proof.weapon_intent.protection_use.inventory.active.id,))
        source = magic_battle('trickster_blade', npc_ws=6)
        result = run_native(self, source)
        incoming = next(step for step in attacks(result) if step.proof.request.target_id == 'pc')
        before = result.steps[result.steps.index(incoming)-1].state.participant('pc')
        self.assertTrue(before.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(any(modifier.rule_id == TRICKSTER_DEFENCE_RULE_ID
            for modifier in incoming.proof.request.kernel_request.attack.defender_test.dice_modifiers))

    def test_justice_single_combat_and_wounds_table_only_apply_to_their_real_targets(self):
        source = magic_battle('sword_of_justice')
        result = run_native(self, source)
        player = attacks(result, 'pc')[0].proof
        self.assertFalse(any(modifier.rule_id == JUSTICE_SINGLE_COMBAT_RULE_ID
            for modifier in player.request.kernel_request.attack.attacker_test.quality_modifiers))
        self.assertFalse(player.request.kernel_request.wound_dice_modifiers)
        source = magic_battle('sword_of_justice', npc_magic=True, pc_toughness=1, npc_ws=6)
        result = run_native(self, source)
        enemy = attacks(result, source.enemy_activation_order[0])[0].proof
        self.assertEqual(tuple(modifier.rule_id for modifier in
            enemy.request.kernel_request.attack.attacker_test.quality_modifiers), (JUSTICE_SINGLE_COMBAT_RULE_ID,))
        self.assertEqual(tuple((modifier.rule_id, modifier.amount)
            for modifier in enemy.request.kernel_request.wound_dice_modifiers), ((JUSTICE_WOUND_DICE_RULE_ID, 1),))
        self.assertIsNotNone(enemy.execution.resolution.pending_character_wound)
        source = magic_battle('sword_of_justice', npc_magic=True, count=2)
        result = run_native(self, source)
        enemy = attacks(result, source.enemy_activation_order[0])[0].proof
        self.assertFalse(any(modifier.rule_id == JUSTICE_SINGLE_COMBAT_RULE_ID
            for modifier in enemy.request.kernel_request.attack.attacker_test.quality_modifiers))

    def test_duellist_skips_dead_last_target_and_retargets_only_between_real_actions(self):
        source = magic_battle('duellist_blades', pc_strength=10, npc_toughness=1)
        result = run_native(self, source)
        self.assertEqual(len(attacks(result, 'pc')), 1)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertFalse(any(type(step.proof) is CombatActionSlotResult
            and step.proof.slot.duellist_blades is not None for step in result.steps))
        source = magic_battle('duellist_blades', count=2, pc_strength=10, npc_toughness=1)
        result = run_native(self, source)
        actual = attacks(result, 'pc')
        self.assertEqual(len(actual), 2)
        self.assertEqual(tuple(step.proof.request.target_id for step in actual), source.enemy_activation_order)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_actual_drained_from_scarab_suppresses_only_duellist_glorious(self):
        source = magic_battle('duellist_blades', npc_magic=True, pc_weapon='scarab_knife', pc_ws=8)
        result = run_native(self, source)
        actor = source.enemy_activation_order[0]
        actual = attacks(result, actor)
        self.assertEqual(len(actual), 2)
        before = result.steps[result.steps.index(actual[0])-1].state.enemy(actor).state.injury
        self.assertTrue(before.conditions.has(Condition.DRAINED))
        self.assertEqual(tuple(modifier.rule_id for modifier in
            actual[0].proof.request.kernel_request.attack.attacker_test.quality_modifiers), (DUELLIST_GRIM_RULE_ID,))
        self.assertFalse(any(modifier.rule_id == DUELLIST_GLORIOUS_RULE_ID
            for modifier in actual[1].proof.request.kernel_request.attack.attacker_test.quality_modifiers))


if __name__ == '__main__':
    unittest.main()
