"""A real own-turn blast death finishes mandatory work and its actual turn."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.support.magic_weapon_battles import magic_battle
from tests.support.oath_sources import with_native_outcome_owner
from towr.domain.attack_models import AttackOutcome
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcTurnEndProof,
    PcWoundCompletionProof, initial_pc_melee_state,
)
from towr.domain.pc_weapon_area_models import PcWeaponAreaEndProof, PcWeaponHazardProof
from towr.domain.pc_weapon_models import PcMeleeWeapon
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario
import towr.domain.talent_actor_models as admission


class PcOwnTurnFatalWoundTests(unittest.TestCase):
    def test_blast_self_hazard_death_closes_real_turn_after_all_area_victims(self):
        # Admission only; every die, Hazard, Wound, action and clock is real.
        with patch.object(admission, 'PC_EXECUTABLE_TALENTS',
                admission.PC_EXECUTABLE_TALENTS | {TalentId.HONOUR_BOUND}):
            source = with_native_outcome_owner(magic_battle('staff', count=3,
                rounds=1, distance='short'), fate=0)
            member = source.party[0]
            member = replace(member, pc=replace(member.pc,
                weapon=PcMeleeWeapon.BLASTING_CHARGE, ballistic_skill=1, throwing=1),
                combat_equipment=(replace(member.combat_equipment[0],
                    weapon=PcMeleeWeapon.BLASTING_CHARGE),))
            source = replace(source, party=(member,), battlefield=PcBattlefieldSpec(
                RangedWeaponRange.SHORT, RangedWeaponRange.LONG))
            # The sole Throwing die is an ordinary success. Failed physical
            # Hazard dice and the fatal Wound roll follow; Fate cannot fund an
            # outcome grant. No raw failed Attack is promoted into a hit.
            result = run_pc_melee_scenario(source, SequenceRandom([1] + [10] * 300))
            actor = member.actor_id
            attack = next(step for step in result.steps if type(step.proof) is PcAttackProof)
            self.assertIs(attack.proof.execution.resolution.attack.outcome, AttackOutcome.HIT)
            self.assertGreater(attack.proof.execution.resolution.attack.attacker_test.successes, 0)
            hazards = [step for step in result.steps if type(step.proof) is PcWeaponHazardProof]
            self.assertEqual({step.proof.request.actor_id for step in hazards},
                {actor, *source.enemy_activation_order})
            self_hazard = next(step for step in hazards if step.proof.request.actor_id == actor)
            self.assertEqual(self_hazard.proof.test.successes, 0)
            self.assertIsNone(self_hazard.proof.test.honour_bound)
            fatal = next(step for step in result.steps if type(step.proof) is PcWoundCompletionProof
                and step.proof.completion.state.dead)
            self.assertEqual(fatal.state.round_state.active_turn.actor_id, actor)
            self.assertNotIn(actor, fatal.state.round_state.excluded_turn_entity_ids)
            wave_end = next(step for step in result.steps if type(step.proof) is PcWeaponAreaEndProof)
            end = result.steps[-1]
            self.assertIs(type(end.proof), PcTurnEndProof)
            self.assertLess(result.steps.index(wave_end), result.steps.index(end))
            self.assertEqual(end.source.round_state.active_turn.action_slots,
                attack.state.round_state.active_turn.action_slots)
            self.assertEqual(len(end.proof.result.completed_turn.action_slots), 1)
            self.assertTrue(end.proof.result.completed_turn.action_slots[0].executed)
            self.assertIsNone(end.proof.critical)
            self.assertIsNone(end.proof.fate_decline)
            self.assertIsNone(result.state.round_state.active_turn)
            self.assertIn(actor, result.state.round_state.completed_turn_entity_ids)
            self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
            self.assertTrue(result.state.participant(actor).injury.dead)
            self.assertEqual(result.state.participant(actor).fate, member.fate)
            self.assertIsNone(result.state.pending_wound)
            self.assertFalse(result.state.pending)
            state = initial_pc_melee_state(source)
            for step in result.steps:
                self.assertEqual(step.source, state)
                state = PcMeleeStep(state, step.proof).state
            self.assertEqual(state, result.state)
            with self.assertRaisesRegex(ValueError, 'end phase|TurnEnd|turn end'):
                replace(result, steps=result.steps[:-1])


if __name__ == '__main__':
    unittest.main()
