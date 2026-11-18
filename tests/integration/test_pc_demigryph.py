"""Real native same-action mount strikes, player Fate and complete K1 queues."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.unit.test_pc_demigryph import reserved, Ones
from towr.domain.armour_models import ArmourLoadout
from towr.domain.attack_models import DamageProfile
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_demigryph_models import PcDemigryphIntentProof, PcDemigryphStrikeProof
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeStep, PcProfileWoundProof, PcWoundCompletionProof, initial_pc_melee_state,
)
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class PcDemigryphIntegrationTests(unittest.TestCase):
    def test_mount_wound_finishes_inside_one_paid_attack_and_full_native_replay(self):
        source = reserved().source
        result = run_pc_melee_scenario(source, Ones())
        self.assertEqual(result.outcome.value, 'objective_achieved')
        self.assertEqual(result.executed_actions, 1)
        intent, = (step for step in result.steps if type(step.proof) is PcDemigryphIntentProof)
        primary, = (step for step in result.steps if type(step.proof) is PcAttackProof)
        strike, = (step for step in result.steps if type(step.proof) is PcDemigryphStrikeProof)
        self.assertLess(result.steps.index(intent), result.steps.index(primary))
        self.assertEqual(strike.proof.request.parent_receipt, primary.proof.execution.slot.execution)
        self.assertEqual(strike.source.round_state, strike.state.round_state)
        self.assertEqual(len(strike.state.round_state.active_turn.action_slots), 1)
        self.assertTrue(strike.proof.resolution.profile_wound.state_change.defeated)
        self.assertEqual(sum(type(step.proof) is PcProfileWoundProof for step in result.steps), 1)
        state = initial_pc_melee_state(source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(strike.state, strike)
        changed = replace(strike.proof.request.kernel_request.attack.impact_spec, damage=DamageProfile(6))
        forged = replace(strike.proof.request, kernel_request=replace(strike.proof.request.kernel_request,
            attack=replace(strike.proof.request.kernel_request.attack, impact_spec=changed)))
        with self.assertRaises(ValueError):
            PcMeleeStep(strike.source, replace(strike.proof, request=forged))

    def test_generated_rider_claws_complete_their_own_player_wound_and_fate_window(self):
        source = reserved(actor='minion1').source
        pc = replace(source.party[0], pc=replace(source.party[0].pc, weapon_skill=1))
        npc = GeneratedNpc(6, 3, 20, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.SWORD), ArmourLoadout(), defence=6,
            mount=CombatMount.DEMIGRYPH, rider_kind=RiderKind.HUMAN).participant('minion1')
        result = run_pc_melee_scenario(replace(source, party=(pc,), enemies=(npc,)), Ones())
        self.assertIsNone(result.unsupported)
        self.assertEqual(result.executed_actions, 2)
        strikes = [step for step in result.steps if type(step.proof) is PcDemigryphStrikeProof]
        self.assertEqual([step.proof.request.actor_id for step in strikes], ['minion1'])
        pc_attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertIsNotNone(pc_attack.mount_attack)
        self.assertEqual(len(result.state.participant('pc1').injury.wounds), 2)
        completions = [step for step in result.steps if type(step.proof) is PcWoundCompletionProof]
        self.assertEqual(len(completions), 2)
        self.assertEqual(completions[-1].proof.completion.source_request.roll,
            strikes[-1].proof.resolution.pending_character_wound)
        self.assertFalse(result.state.pending)
        self.assertIsNone(result.state.pending_wound)

    def test_player_can_spend_real_fate_to_cancel_claws_grim_without_paying_another_action(self):
        source = reserved().source
        pc = replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,), 4, 0))
        result = run_pc_melee_scenario(replace(source, party=(pc,)), Ones())
        strike, = (step for step in result.steps if type(step.proof) is PcDemigryphStrikeProof)
        self.assertIsNotNone(strike.proof.glorious)
        self.assertEqual(strike.proof.glorious.previous_state, pc.fate)
        self.assertEqual(result.state.participant('pc1').fate.remaining_spends, pc.fate.remaining_spends-1)
        self.assertEqual(result.executed_actions, 1)
        with self.assertRaises(TypeError):
            PcMeleeStep(strike.source, replace(strike.proof, glorious=None))

    def test_charge_is_one_manoeuvre_without_the_optional_attack_action_pair(self):
        source = reserved().source
        source = replace(source, facts=replace(source.facts, all_opponents_close=False),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM, RangedWeaponRange.LONG))
        result = run_pc_melee_scenario(source, Ones())
        first = next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertIsNotNone(first.request.charge_movement)
        self.assertFalse(any(type(step.proof) is PcDemigryphStrikeProof for step in result.steps))
        self.assertFalse(any(type(step.proof) is PcDemigryphIntentProof for step in result.steps))


if __name__ == '__main__':
    unittest.main()
