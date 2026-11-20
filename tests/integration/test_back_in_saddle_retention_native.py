"""Native detach/fall consumer; public Talent cap deliberately stays closed.

Only fixture admission is widened while remaining companion consumers are
being connected. The battle, wound, detach, fall and replay are real.
"""
from dataclasses import replace
from unittest import TestCase, main
from unittest.mock import patch

from tests.integration.test_pc_falling_native import falling_source
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent
from towr.domain import talent_actor_models
from towr.domain.pc_battlefield_models import battlefield_is_midair
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.pc_melee_result_models import PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_mount_retention_models import PcMountRetentionProof
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


class NativeBackInSaddleRetentionTests(TestCase):
    def test_real_rider_wound_retains_airborne_pegasus_before_riders_fall_without_teleport(self):
        self.enterContext(patch.object(talent_actor_models, 'PC_EXECUTABLE_TALENTS',
            talent_actor_models.PC_EXECUTABLE_TALENTS | {TalentId.BACK_IN_THE_SADDLE}))
        battle = falling_source()
        member = replace(battle.party[0], talents=(free_talent(TalentId.ACROBATIC),
            free_talent(TalentId.BACK_IN_THE_SADDLE)))
        battle = replace(battle, party=(member,), battlefield=replace(battle.battlefield,
            airspace=replace(battle.battlefield.airspace, fall_hazard_rating=1)))
        rng = ScriptedD10([10, 10] + [1]*6 + [10, 9, 10])
        result = run_pc_melee_scenario(battle, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        retention, = tuple(step for step in result.steps if type(step.proof) is PcMountRetentionProof)
        fall, = tuple(step for step in result.steps if type(step.proof) is PcFallingProof)
        self.assertLess(result.steps.index(retention), result.steps.index(fall))
        self.assertTrue(battlefield_is_midair(retention.state.battlefield, 'pc1:mount'))
        self.assertTrue(battlefield_is_midair(fall.state.battlefield, 'pc1:mount'))
        self.assertFalse(battlefield_is_midair(fall.state.battlefield, 'pc1'))
        row, = result.state.companions
        self.assertEqual(row.snapshot.state.injury.wounds, 0)
        self.assertEqual(row.retained_since_round, 1)
        self.assertEqual(result.executed_actions, 2)
        self.assertFalse(any(participant.entity_id == 'pc1:mount'
            for participant in result.state.round_state.participants))
        state = initial_pc_melee_state(battle)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)
        with self.assertRaises(ValueError): PcMeleeStep(retention.state, retention.proof)


if __name__ == '__main__': main()
