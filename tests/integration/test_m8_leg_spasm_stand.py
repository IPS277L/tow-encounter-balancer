"""Actual Wound9 -> explicit stand, without enabling automatic continuation."""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate
import unittest

from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRestriction
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_leg_spasm_resolution import (
    stand_npc_roster_leg_spasm, apply_npc_roster_leg_spasm_stand,
)


class LegSpasmStandIntegrationTests(unittest.TestCase):
    def test_actual_wound_stand_preserves_full_owner_and_does_not_enable_runner(self):
        rng_before = getstate()
        for policy in (None, continuation_policy()):
            with self.subTest(opted=policy is not None):
                scenario = replace(admitted(wizard_side=CombatSide.OPPOSITION), miscast_continuation=policy)
                scenario_before = deepcopy(scenario)
                dice = Dice((1, 2, 3, 10, 10, 10, 9))
                stopped = run_npc_magic_scenario(scenario, dice)
                dice.exhausted()
                self.assertIs(stopped.unsupported.reason, NpcMagicUnsupportedReason.ACTOR_INJURY)
                old = stopped.current
                before = deepcopy(old)
                actor = old.wizard.actor_id
                injury = old.roster.participant(actor).state.injury
                self.assertIs(injury.wounds[0].entry_id, WoundEntryId.LEG_SPASM)
                self.assertTrue(injury.wounds[0].effect_resolved)
                self.assertIsNone(old.champion_attack.pending)
                self.assertEqual(len(old.champion_attack.daily_wounds.receipts), 1)
                with self.assertRaises(ValueError):
                    NpcRosterProneStandRequest('legacy:stand', old, actor, False, True)
                request = NpcRosterLegSpasmStandRequest('leg:stand', old, actor, False, True)
                result = stand_npc_roster_leg_spasm(request)
                final = apply_npc_roster_leg_spasm_stand(old, result)
                current = final.roster.participant(actor).state.injury
                self.assertEqual(current.wounds, injury.wounds)
                self.assertFalse(current.conditions.has(Condition.PRONE))
                self.assertEqual(len(current.active_wound_effects), 1)
                self.assertIs(current.active_wound_effects[0].restriction,
                              WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN)
                self.assertEqual(final.spatial_state, replace(old.spatial_state,
                    free_move_used_entity_ids=(*old.spatial_state.free_move_used_entity_ids, actor)))
                for field in fields(old):
                    if field.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                        self.assertEqual(getattr(final, field.name), getattr(old, field.name), field.name)
                self.assertEqual(final.champion_attack, replace(old.champion_attack, roster=final.roster))
                self.assertEqual(final.minion_attack, replace(old.minion_attack, roster=final.roster))
                self.assertEqual(final.roster, final.champion_attack.roster)
                self.assertEqual(final.roster, final.minion_attack.roster)
                self.assertEqual(old, before)
                self.assertEqual(scenario, scenario_before)
                # Explicit low-level completion does not grant action admission.
                self.assertIs(diagnose_npc_magic_unsupported(scenario, final, result.source.id).reason,
                              NpcMagicUnsupportedReason.ACTOR_INJURY)
                with self.assertRaises(ValueError):
                    validate_magic_step_policy(scenario, NpcMagicStep(result))
                with self.assertRaises(ValueError):
                    apply_npc_roster_leg_spasm_stand(final, result)
                again = Dice((1, 2, 3, 10, 10, 10, 9))
                self.assertEqual(run_npc_magic_scenario(scenario, again), stopped)
                again.exhausted()
        self.assertEqual(getstate(), rng_before)

    def test_other_actual_wounds_are_not_reinterpreted_as_leg_spasm(self):
        hit = (1, 2, 3, 10, 10, 10)
        scenario = replace(admitted(wizard_side=CombatSide.OPPOSITION),
                           miscast_continuation=continuation_policy())
        for entry, values in ((WoundEntryId.CRUSHED_RIB, (*hit, 10)),
                              (WoundEntryId.TORN_LEG, (*hit, 3, *((10,) * 9), *hit, 6, 7))):
            with self.subTest(entry=entry):
                dice = Dice(values)
                stopped = run_npc_magic_scenario(scenario, dice)
                dice.exhausted()
                old = stopped.current
                self.assertIs(old.roster.participant('wizard').state.injury.wounds[-1].entry_id, entry)
                before = deepcopy(old)
                with self.assertRaises(ValueError):
                    NpcRosterLegSpasmStandRequest('not:leg', old, 'wizard', False, True)
                self.assertEqual(old, before)


if __name__ == '__main__':
    unittest.main()
