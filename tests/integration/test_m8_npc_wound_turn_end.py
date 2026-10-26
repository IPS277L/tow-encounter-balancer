"""Real Wound/turn continuations through the full ADR-0036 owner."""
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack, wizard_turn, prepare
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard, wizard_recovery
from tests.integration.test_m8_npc_broken_run import from_owner
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


def end_wizard(state):
    request = NpcWoundTurnEndRequest('end:wizard', state, state.wizard.actor_id,
                                   (WoundConditionSourceSnapshot(Condition.DRAINED, False),))
    with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no end-turn Test')):
        return apply_npc_wound_turn_end_result(state, end_npc_wound_turn(request))


class NpcWoundTurnEndIntegrationTests(unittest.TestCase):
    def test_real_wound_then_cast_then_expiry_preserves_all_results(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
        owner = NpcRosterChampionAttackResult(source, attack).state
        caster = wizard_turn(owner)
        casting = prepare(caster)
        outcome = execute_cowardly_flight_casting(casting.casting, SequenceRandom((1, 2, 10, 1, 2, 10, 10, 10, 10)))
        current = NpcRosterCastingResult(casting, outcome).state
        final = end_wizard(current)
        self.assertEqual(final.wizard, current.wizard)
        self.assertTrue(final.roster.participant('brigand:1').state.injury.conditions.has(Condition.BROKEN))
        self.assertFalse(final.roster.participant(final.wizard.actor_id).state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.champion_attack.daily_wounds, owner.champion_attack.daily_wounds)
        self.assertEqual(final.consumed_execution_ids, current.consumed_execution_ids)
        self.assertEqual(final.wound_expiries, ())
        self.assertEqual(owner.wound_expiries, current.wound_expiries)

    def test_real_wound_broken_recover_then_expiry_does_not_heal_wound(self):
        _, _, owner = wounded_broken_wizard(0)
        recovered = execute_npc_broken_recover(wizard_recovery(owner), SequenceRandom((10,) * 20)).state
        before = recovered.roster.participant(recovered.wizard.actor_id).state.injury
        final = end_wizard(recovered)
        after = final.roster.participant(final.wizard.actor_id).state.injury
        self.assertEqual(after.wounds, before.wounds)
        self.assertEqual(after.conditions, before.conditions.without_condition(Condition.DRAINED))
        self.assertEqual(final.wizard.magic_state, recovered.wizard.magic_state)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 1)
        self.assertEqual(final.spatial_state, recovered.spatial_state)

    def test_real_wound_broken_run_then_expiry_leaves_broken_and_no_free_recover(self):
        _, _, owner = wounded_broken_wizard(0)
        ran = execute_npc_broken_run(from_owner(owner, owner.wizard.actor_id)).state
        final = end_wizard(ran)
        injury = final.roster.participant(final.wizard.actor_id).state.injury
        self.assertTrue(injury.conditions.has(Condition.BROKEN))
        self.assertFalse(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.spatial_state, ran.spatial_state)
        self.assertEqual(final.wizard, ran.wizard)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 1)
        self.assertEqual(final.consumed_execution_ids, ran.consumed_execution_ids)

    def test_actual_pending_casting_miscast_blocks_end(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        owner = wizard_turn(NpcRosterChampionAttackResult(source, attack).state)
        casting = prepare(owner)
        result = execute_cowardly_flight_casting(casting.casting, SequenceRandom((9, 9, 1)))
        current = NpcRosterCastingResult(casting, result).state
        self.assertIsNotNone(current.pending_miscast)
        with self.assertRaisesRegex(ValueError, 'mandatory pending'):
            NpcWoundTurnEndRequest('end', current, current.wizard.actor_id)


if __name__ == '__main__':
    unittest.main()
