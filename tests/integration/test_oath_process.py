"""One real spawn boundary for acquired Oaths and finite Lady/Fate receipts."""
from dataclasses import replace
from unittest import TestCase

from tests.integration.test_oath_native import native_source, LiteralD10
from tests.support.oath_sources import honour, lady, context, with_native_outcome_owner
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def literal_factory(seed):
    # Deterministic transport fixture, not a probability estimate.
    return LiteralD10()


class OathProcessTests(TestCase):
    def test_spawn_preserves_actual_resources_receipts_and_aggregates(self):
        gm = context(lady_prayer_before_battle_confirmed=True,
            unmitigated_success_scope_confirmed=True)
        source = native_source(pc_talents=(honour(), lady()), npc_talents=(honour(), lady()),
            pc_context=gm, npc_context=gm)
        pc = source.party[0]
        source = replace(source, party=(replace(pc, pc=replace(pc.pc, weapon_skill=1, melee=1)),))
        source = with_native_outcome_owner(source, gm_context=gm)
        request = PcMeleeSimulationRequest(source, 42, 2)
        sequential = run_pc_melee_simulation(request, rng_factory=literal_factory)
        parallel = run_pc_melee_simulation_parallel(request, workers=2,
            batch_size=1, rng_factory=literal_factory)
        self.assertEqual(parallel, sequential)
        summary = summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary, summarize_pc_melee_simulation(sequential))
        self.assertEqual(summary.oath_counts[0].unmitigated_activations, 2)
        self.assertEqual(summary.oath_counts[0].fate_spends, 2)
        self.assertEqual(summary.oath_counts[1].fate_spends, 0)
