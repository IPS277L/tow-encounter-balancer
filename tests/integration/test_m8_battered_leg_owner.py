from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_battered_leg_owner import request
from tests.integration.test_m8_champion_casting_handoff import wizard_turn, prepare
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_battered_leg_resolution import execute_npc_roster_battered_leg
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result


class BatteredLegOwnerIntegrationTests(unittest.TestCase):
    def test_success_preserves_witness_through_actual_normal_casting(self):
        resolved = execute_npc_roster_battered_leg(request(), SequenceRandom((1, 10)))
        state = wizard_turn(resolved.state)
        casting = prepare(state)
        actual = execute_cowardly_flight_casting(casting.casting,
            SequenceRandom((1, 2, 10, 1, 2, 10, 10, 10, 10)))
        result = NpcRosterCastingResult(casting, actual)
        final = apply_npc_roster_casting_result(state, result)
        self.assertEqual(final.battered_leg_receipt, resolved.state.battered_leg_receipt)
        self.assertEqual(final.roster.participant(final.wizard.actor_id).state.injury,
                         resolved.endurance.wound_result.state)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids,
                         resolved.state.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.consumed_execution_ids[:-1], resolved.state.consumed_execution_ids)

    def test_failure_preserves_prone_instead_of_admitting_an_unsupported_cast(self):
        resolved = execute_npc_roster_battered_leg(request(), SequenceRandom((10, 10)))
        with self.assertRaisesRegex(ValueError, 'unsupported Wound effects'):
            prepare(wizard_turn(resolved.state))
