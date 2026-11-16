"""Source-bound compact magic observations, independent of native RNG execution."""
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
from towr.adapters.pc_melee_json import (parse_pc_melee_simulation_request,
    encode_pc_melee_simulation_result, validate_pc_melee_simulation_document)
from towr.domain.pc_magic_source_models import PcWizardProfile, PcSpellId
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord,
    PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount,
    PcAllyRecoverActionCount, PcMagicCount, validate_magic_counts,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def magic_source():
    source = automatic_source(pc_count=3, enemy_count=2, rounds=3)
    party = []
    for index, member in enumerate(source.party):
        wizard = (PcWizardProfile('human',3,5,1,('elementalism',),
            (PcSpellId.LIGHTNING_BLAST, PcSpellId.FIRE_BREATH),True) if index < 2 else None)
        party.append(replace(member,wizard=wizard))
    return replace(source,party=tuple(party),
        facts=replace(source.facts,daylight_confirmed=True))


def magic_counts(first=(2,1,1,0), second=(1,1,0,0)):
    return (PcMagicCount('pc1',*first),PcMagicCount('pc2',*second))


def observed_result():
    request = PcMeleeSimulationRequest(magic_source(),42,2)
    records = tuple(PcMeleeTrialRecord(
        request.scenario,index,request.seed_for(index),PcMeleeOutcome.OBJECTIVE_ACHIEVED,
        6,3,2,(),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcHelpActionCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in request.scenario.party),
        zero_npc_exit_counts(request.scenario),zero_npc_help_counts(request.scenario),
        zero_npc_extra_attack_counts(request.scenario),zero_npc_recover_counts(request.scenario),
        zero_npc_warped_form_counts(request.scenario),magic_counts=rows)
        for index,rows in enumerate((magic_counts(),magic_counts((0,0,0,0),(2,1,1,0)))))
    return PcMeleeSimulationResult(request,records)


class PcMagicStatisticsTests(unittest.TestCase):
    def test_zero_inclusive_actor_rows_sum_without_retaining_journals(self):
        result = observed_result()
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(summary.magic_counts,magic_counts((2,1,1,0),(3,2,1,0)))
        self.assertEqual((summary.total_casting_action_count,summary.total_spell_cast_count,
            summary.total_miscast_count,summary.total_unsupported_miscast_count),(5,3,2,0))
        self.assertEqual(result.records[1].magic_counts[0],PcMagicCount('pc1',0,0,0,0))
        self.assertFalse(hasattr(summary,'records'))
        self.assertEqual(replace(summary),summary)

    def test_wizard_sources_require_complete_order_and_non_wizards_require_none(self):
        source = magic_source()
        rows = magic_counts((0,0,0,0),(0,0,0,0))
        for invalid in (None,(),list(rows),tuple(reversed(rows)),rows[:1],
                (rows[0],rows[0]),(*rows,PcMagicCount('pc3',0,0,0,0))):
            with self.subTest(invalid=invalid),self.assertRaises((TypeError,ValueError)):
                validate_magic_counts(invalid,source,trials=1,actions=0,
                    started_rounds=1,unsupported_trials=0)
        plain = automatic_source()
        validate_magic_counts(None,plain,trials=1,actions=0,started_rounds=1,unsupported_trials=0)
        for invalid in ((),rows):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                validate_magic_counts(invalid,plain,trials=1,actions=0,
                    started_rounds=1,unsupported_trials=0)

    def test_actual_actions_turns_and_unsupported_outcomes_have_distinct_budgets(self):
        source = magic_source()
        for rows, actions, rounds, unsupported, text in (
            (magic_counts(),2,3,0,'action'),
            (magic_counts((4,1,1,0),(0,0,0,0)),8,3,0,'turn'),
            (magic_counts((1,1,4,0),(0,0,0,0)),8,3,0,'turn'),
            (magic_counts((1,1,1,1),(1,1,1,1)),8,3,1,'unsupported'),
        ):
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,text):
                validate_magic_counts(rows,source,trials=1,actions=actions,
                    started_rounds=rounds,unsupported_trials=unsupported)
        validate_magic_counts(magic_counts((2,1,2,1),(1,1,0,0)),source,
            trials=1,actions=5,started_rounds=3,unsupported_trials=1)

    def test_casting_shares_the_actor_budget_with_actual_help_recover_and_potions(self):
        result = observed_result()
        record = result.records[0]
        with self.assertRaisesRegex(ValueError,'same actor turn'):
            replace(record,help_action_counts=(PcHelpActionCount('pc1',2),
                PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)))
        summary = summarize_pc_melee_simulation(result)
        with self.assertRaisesRegex(ValueError,'same actor turn'):
            replace(summary,help_action_trial_count=2,help_action_counts=(
                PcHelpActionCount('pc1',5),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)))
        with self.assertRaisesRegex(ValueError,'unsupported'):
            replace(record,magic_counts=magic_counts((2,1,1,1),(1,1,0,0)))

    def test_exact_counts_and_cached_sources_are_readmitted(self):
        for row in (('',0,0,0,0),('pc',True,0,0,0),('pc',1.0,0,0,0),
                ('pc',1,2,0,0),('pc',1,1,0,1),('pc',1,0,-1,0)):
            with self.subTest(row=row),self.assertRaises((TypeError,ValueError)):
                PcMagicCount(*row)
        record = deepcopy(observed_result().records[0])
        object.__setattr__(record.magic_counts[0],'casting_actions',True)
        with self.assertRaises(TypeError):
            replace(record)

    def test_current_wire_requires_magic_counts_only_for_wizard_sources(self):
        result = observed_result()
        summary = summarize_pc_melee_simulation(result)
        document = dict(schema_version='1',kind='pc_melee_simulation',request_id='magic-stats',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(result.source_request.scenario),
            simulation=dict(master_seed='42',trials=2),execution=dict(mode='sequential'))
        command = parse_pc_melee_simulation_request(json.dumps(document))
        report = json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(report['summary']['magic_counts'],[
            dict(actor_id='pc1',casting_actions=2,spell_casts=1,miscasts=1,unsupported_miscasts=0),
            dict(actor_id='pc2',casting_actions=3,spell_casts=2,miscasts=1,unsupported_miscasts=0)])
        invalid = deepcopy(report)
        invalid['summary'].pop('magic_counts')
        with self.assertRaises(ValidationError):
            validate_pc_melee_simulation_document(invalid,'result')
        no_wizards = deepcopy(report)
        for member in no_wizards['request']['scenario']['party']:
            member.pop('wizard',None)
        with self.assertRaises(ValidationError):
            validate_pc_melee_simulation_document(no_wizards,'result')
        no_wizards['summary'].pop('magic_counts')
        validate_pc_melee_simulation_document(no_wizards,'result')


if __name__ == '__main__':
    unittest.main()
