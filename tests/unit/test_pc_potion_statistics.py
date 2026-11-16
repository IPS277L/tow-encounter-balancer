"""Source-bound aggregate spending observations, without inventing execution."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from jsonschema import ValidationError

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.pc_melee_fixtures import (
    zero_npc_exit_counts, zero_npc_help_counts, zero_npc_extra_attack_counts,
    zero_npc_recover_counts, zero_npc_warped_form_counts,
)
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import (
    parse_pc_melee_simulation_request, encode_pc_melee_simulation_result,
    validate_pc_melee_simulation_document,
)
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord,
    PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount,
    PcAllyRecoverActionCount, PcPotionUseCount, validate_potion_use_counts,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def potion_source():
    source = automatic_source(pc_count=2, enemy_count=2, rounds=3)
    return replace(source, party=(
        replace(source.party[0], consumables=(
            ConsumableItem('healing', ConsumableKind.HEALING, 2, None),
            ConsumableItem('strength', ConsumableKind.ENHANCEMENT, 2, 'strength'),
        )),
        replace(source.party[1], consumables=(
            ConsumableItem('healing', ConsumableKind.HEALING, 1, None),
        )),
    ))


def potion_counts(values):
    return tuple(PcPotionUseCount(actor, item, count) for (actor, item), count in zip(
        (('pc1', 'healing'), ('pc1', 'strength'), ('pc2', 'healing')), values, strict=True))


def observed_result():
    request = PcMeleeSimulationRequest(potion_source(), 42, 2)
    records = tuple(PcMeleeTrialRecord(
        request.scenario, index, request.seed_for(index), PcMeleeOutcome.OBJECTIVE_ACHIEVED,
        4, 2, 1, (),
        tuple(PcNearMissBurnCount(member.actor_id, 0) for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id, 0) for member in request.scenario.party),
        tuple(PcHelpActionCount(member.actor_id, 0) for member in request.scenario.party),
        tuple(PcAllyRecoverActionCount(member.actor_id, 0) for member in request.scenario.party),
        zero_npc_exit_counts(request.scenario), zero_npc_help_counts(request.scenario),
        zero_npc_extra_attack_counts(request.scenario), zero_npc_recover_counts(request.scenario),
        zero_npc_warped_form_counts(request.scenario), potion_use_counts=potion_counts(values),
    ) for index, values in enumerate(((1, 1, 0), (1, 0, 1))))
    return PcMeleeSimulationResult(request, records)


class PcPotionStatisticsTests(unittest.TestCase):
    def test_complete_observations_sum_by_actor_and_item_without_journals(self):
        result = observed_result()
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(summary.potion_use_counts, potion_counts((2, 1, 1)))
        self.assertEqual(summary.total_potion_use_count, 4)
        self.assertFalse(hasattr(summary, 'records'))
        self.assertEqual(result.records[0].potion_use_counts[-1].count, 0)
        self.assertEqual(replace(summary), summary)

    def test_inventory_requires_full_source_order_and_no_inventory_requires_none(self):
        source = potion_source()
        valid = potion_counts((0, 0, 0))
        for rows in (None, (), tuple(reversed(valid)), valid[:-1], (valid[0], valid[0], valid[2])):
            with self.subTest(rows=rows), self.assertRaises((TypeError, ValueError)):
                validate_potion_use_counts(rows, source, trials=1, actions=4, started_rounds=2)
        plain = automatic_source()
        validate_potion_use_counts(None, plain, trials=1, actions=0, started_rounds=1)
        for rows in ((), valid):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_potion_use_counts(rows, plain, trials=1, actions=4, started_rounds=2)

    def test_stock_actions_and_actor_turn_budgets_are_independent_bounds(self):
        source = potion_source()
        for values, actions, rounds, error in (
            ((3, 0, 0), 8, 3, 'stock'),
            ((0, 0, 2), 8, 3, 'stock'),
            ((1, 1, 1), 2, 3, 'executed'),
            ((1, 1, 0), 8, 1, 'turn'),
            ((0, 2, 0), 8, 3, 'once'),
        ):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, error):
                validate_potion_use_counts(potion_counts(values), source, trials=1,
                    actions=actions, started_rounds=rounds)
        validate_potion_use_counts(potion_counts((4, 0, 2)), source, trials=2,
            actions=8, started_rounds=4)

    def test_records_and_summaries_share_automatic_support_turns(self):
        result = observed_result()
        record = result.records[0]
        with self.assertRaisesRegex(ValueError, 'same actor turn'):
            replace(record, help_action_counts=(PcHelpActionCount('pc1', 1), PcHelpActionCount('pc2', 0)))
        summary = summarize_pc_melee_simulation(result)
        with self.assertRaises(ValueError):
            replace(summary, potion_use_counts=potion_counts((5, 0, 0)))
        with self.assertRaisesRegex(ValueError, 'same actor turn'):
            replace(summary, help_action_trial_count=2,
                help_action_counts=(PcHelpActionCount('pc1', 2), PcHelpActionCount('pc2', 0)))

    def test_counts_reject_coercion_and_cached_mutation(self):
        for actor, item, count in (('', 'p', 1), ('pc', '', 1), ('pc', 'p', True),
                                   ('pc', 'p', 1.0), ('pc', 'p', -1)):
            with self.subTest(count=count), self.assertRaises((TypeError, ValueError)):
                PcPotionUseCount(actor, item, count)
        record = deepcopy(observed_result().records[0])
        object.__setattr__(record.potion_use_counts[0], 'count', True)
        with self.assertRaises(TypeError):
            replace(record)

    def test_current_wire_requires_potion_counts_only_for_inventory_sources(self):
        result = observed_result()
        summary = summarize_pc_melee_simulation(result)
        document = dict(schema_version='1', kind='pc_melee_simulation', request_id='potions',
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(result.source_request.scenario),
            simulation=dict(master_seed='42', trials=2), execution=dict(mode='sequential'))
        command = parse_pc_melee_simulation_request(json.dumps(document))
        report = json.loads(encode_pc_melee_simulation_result(command, summary))
        self.assertEqual(report['summary']['potion_use_counts'], [
            dict(actor_id='pc1', item_id='healing', count=2),
            dict(actor_id='pc1', item_id='strength', count=1),
            dict(actor_id='pc2', item_id='healing', count=1),
        ])
        missing = deepcopy(report)
        missing['summary'].pop('potion_use_counts')
        with self.assertRaises(ValidationError):
            validate_pc_melee_simulation_document(missing, 'result')
        no_stock = deepcopy(report)
        for member in no_stock['request']['scenario']['party']:
            member.pop('consumables')
        with self.assertRaises(ValidationError):
            validate_pc_melee_simulation_document(no_stock, 'result')
        no_stock['summary'].pop('potion_use_counts')
        validate_pc_melee_simulation_document(no_stock, 'result')


if __name__ == '__main__':
    unittest.main()
