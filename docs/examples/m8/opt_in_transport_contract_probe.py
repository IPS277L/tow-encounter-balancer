"""Finite ADR-0047 generation and simulation-v2 transport proof.

Copy with magic_scenario.py, opted_miscast.py and generation_contract_probe.py.
Simulation uses the public v2 parser and encoder with complete opted sources.
Balance v2 still uses a finite manual mapping: its temporary legacy view is
never executed or presented as an opt-in result. Native opted generation uses
the public ADR-0047 API. The manual balance mapping is not a validator for
untrusted documents. No probability claim follows from these authored fixtures.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import json
from random import getstate

from generation_contract_probe import authored_reserve, project
from magic_scenario import ScriptedDice, authored_scenario
from opted_miscast import opted_scenario
from towr.adapters.magic_balance_json import encode_magic_balance_result, parse_magic_balance_request
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.magic_simulation_json import encode_magic_simulation_result, parse_magic_simulation_request
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy, NpcRosterUnnaturalWindResult
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


def policy_document(policy):
    # Explicit finite mapping of the agreed three fields, not a wire API.
    return None if policy is None else {
        'choice': policy.choice.value, 'facts': asdict(policy.facts),
        'prone_policy': policy.prone_policy.value,
    }


def policy_value(document):
    return None if document is None else NpcMagicMiscastContinuationPolicy(
        NpcRosterMiscastPolicy(document['choice']), NpcRosterMiscastFacts(**document['facts']),
        NpcMagicPronePolicy(document['prone_policy']))


def definitions(scenario):
    return tuple(dict.fromkeys(p.definition.id for p in scenario.initial.roster.participants))


def rejected(label, operation, error_type=ValueError):
    try:
        operation()
    except error_type:
        return
    raise AssertionError(f'{label} was not rejected')


def main():
    rng_before = getstate()
    options = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)
    window = ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1))
    legacy = replace(authored_scenario(), max_rounds=1)
    policy = opted_scenario().miscast_continuation
    simulation = MagicSimulationCommand('probe:simulation', NpcMagicSimulationRequest(legacy, 42, 1),
                                        options, definitions(legacy))
    reserve = replace(authored_reserve(), max_rounds=1)
    generation = MagicCandidateGenerationRequest(reserve,
        (MagicCompositionGroup('first', ('E2', 'E1'), 1, 2), MagicCompositionGroup('second', ('E3',), 0, 1)),
        replace(reserve.facts), tuple(reserve.scene_frames), 'probe', 4, 42,
        (MagicBalanceStage(1, 1),), 4, window)
    balance = MagicBalanceCommand('probe:balance', generation, options, definitions(reserve))
    before = deepcopy((simulation, balance, policy))
    # These are genuinely legacy inputs, before any opted source exists.
    legacy_summary = summarize_npc_magic_simulation(run_npc_magic_simulation(simulation.request))
    sim_echo = json.loads(encode_magic_simulation_result(simulation, legacy_summary))['request']
    legacy_balance = execute_magic_balance(balance)
    bal_echo = json.loads(encode_magic_balance_result(balance, legacy_balance))['request']
    assert parse_magic_simulation_request(json.dumps(sim_echo)) == simulation
    assert parse_magic_balance_request(json.dumps(bal_echo)) == balance
    print('Public v1 request echoes: genuine legacy simulation 1 trial; legacy balance 4 trials; exact sources')

    restored_opted = None
    for value in (None, policy):
        sim_doc, bal_doc = deepcopy(sim_echo), deepcopy(bal_echo)
        sim_doc['schema_version'] = bal_doc['schema_version'] = '2'
        sim_doc['scenario']['miscast_continuation'] = policy_document(value)
        bal_doc['reserve']['scenario']['miscast_continuation'] = policy_document(value)
        bal_doc['generation']['miscast_continuation'] = policy_document(value)
        documents_before = deepcopy((sim_doc, bal_doc))
        sim_wire, bal_wire = json.loads(json.dumps(sim_doc)), json.loads(json.dumps(bal_doc))
        assert (sim_wire, bal_wire) == documents_before
        sim_command = parse_magic_simulation_request(json.dumps(sim_wire))
        reserve_policy = policy_value(bal_wire['reserve']['scenario'].pop('miscast_continuation'))
        family_policy = policy_value(bal_wire['generation'].pop('miscast_continuation'))
        assert sim_command.request.scenario.miscast_continuation == reserve_policy == family_policy == value
        # Local structural legacy views only: restore the saved policy BEFORE use.
        bal_wire['schema_version'] = '1'
        bal_base = parse_magic_balance_request(json.dumps(bal_wire))
        assert bal_base == balance  # all orders/seed/options/budgets
        restored = sim_command.request
        assert sim_command == replace(simulation, schema_version='2',
            request=replace(simulation.request, scenario=replace(legacy, miscast_continuation=value)))
        sim_summary = summarize_npc_magic_simulation(run_npc_magic_simulation(restored))
        sim_result = json.loads(encode_magic_simulation_result(sim_command, sim_summary))
        assert sim_result['schema_version'] == '2' and sim_result['request'] == sim_doc
        assert parse_magic_simulation_request(json.dumps(sim_result['request'])) == sim_command
        restored_reserve = replace(bal_base.generation_request.template_scenario,
                                   miscast_continuation=reserve_policy)
        assert restored == replace(simulation.request, scenario=replace(legacy, miscast_continuation=value))
        assert restored_reserve == replace(reserve, miscast_continuation=value)
        assert bal_base.generation_request.facts == generation.facts
        assert bal_base.generation_request.scene_frames == generation.scene_frames
        assert (sim_doc, bal_doc) == documents_before
        rejected('balance parser has no v2 yet', lambda: parse_magic_balance_request(json.dumps(bal_doc)),
                 MagicBalanceInputError)
        for document, parser, error in ((sim_doc, parse_magic_simulation_request, MagicSimulationInputError),
                                       (bal_doc, parse_magic_balance_request, MagicBalanceInputError)):
            v1_extra = deepcopy(document)
            v1_extra['schema_version'] = '1'
            rejected('v1 has no policy field, even null', lambda: parser(json.dumps(v1_extra)), error)
        if value is not None:
            restored_opted = restored
        print(f'Public simulation v2 / manual balance v2 round-trip: {"null" if value is None else "explicit policy"}; '
              'complete source/orders/seed/budgets preserved')

    assert restored_opted is not None
    opted_reserve = replace(reserve, miscast_continuation=policy)
    generated = generate_magic_candidates(generation)
    opted_family = replace(generation, template_scenario=opted_reserve,
                           miscast_continuation=policy)
    opted_generated = generate_magic_candidates(opted_family)
    assert opted_generated.source_request is opted_family
    counts_list = ((1, 0), (1, 1), (2, 0), (2, 1))
    for counts, candidate, actual in zip(counts_list, generated.evaluation_request.candidates,
                                        opted_generated.evaluation_request.candidates, strict=True):
        retained = {'wizard', 'ally', *(actor for group, count in zip(generation.groups, counts)
                                       for actor in group.actor_ids[:count])}
        projected = project(opted_reserve, retained, candidate.candidate_id, generation.facts,
                            generation.scene_frames)
        assert projected == replace(candidate.scenario, miscast_continuation=policy)
        assert actual.scenario == projected and actual.candidate_id == candidate.candidate_id
        assert actual.scenario.miscast_continuation is opted_family.miscast_continuation
        assert projected.miscast_continuation == policy
        original_request = NpcMagicSimulationRequest(candidate.scenario, 42, 1)
        opted_request = replace(original_request, scenario=projected)
        assert original_request.seed_for(0) == opted_request.seed_for(0)
    print('Four native opted subsets equal manual/full legacy projections + exact family policy; IDs and seeds unchanged')
    changed_candidate = replace(generated.evaluation_request.candidates[0],
        scenario=replace(generated.evaluation_request.candidates[0].scenario, miscast_continuation=policy))
    changed_evaluation = replace(generated.evaluation_request,
        candidates=(changed_candidate, *generated.evaluation_request.candidates[1:]))
    rejected('same-ID candidate with different policy',
             lambda: replace(generated, evaluation_request=changed_evaluation))

    opposite = replace(reserve, perspective_side=CombatSide.OPPOSITION,
                       objective=NpcDefeatObjective(('wizard', 'ally')))
    opposite_generation = replace(generation, template_scenario=opposite,
        groups=(MagicCompositionGroup('ally', ('ally',), 1, 1),))
    opposite_candidate = generate_magic_candidates(opposite_generation).evaluation_request.candidates[0]
    opposite_opted = replace(opposite, miscast_continuation=policy)
    opposite_family = replace(opposite_generation, template_scenario=opposite_opted,
                              miscast_continuation=policy)
    opposite_actual = generate_magic_candidates(opposite_family).evaluation_request.candidates[0]
    retained = {p.state.actor_id for p in opposite.initial.roster.participants}
    assert project(opposite_opted, retained, opposite_candidate.candidate_id, generation.facts,
                   generation.scene_frames) == replace(opposite_candidate.scenario, miscast_continuation=policy)
    assert opposite_actual.scenario == replace(opposite_candidate.scenario, miscast_continuation=policy)
    print('Opposite perspective native projection preserves fixed Wizard, full policy and complete source')

    rejected('native generation without separate family opt-in',
             lambda: replace(generation, template_scenario=opted_reserve))
    opted_command = replace(simulation, request=restored_opted)
    opted_result = run_npc_magic_simulation(restored_opted,
        rng_factory=lambda seed: ScriptedDice((9, 9, 9, 7, 7, 7) + (10,) * 10))
    opted_summary = summarize_npc_magic_simulation(opted_result)
    opted_v2 = replace(opted_command, schema_version='2')
    opted_echo = json.loads(encode_magic_simulation_result(opted_v2, opted_summary))['request']
    assert parse_magic_simulation_request(json.dumps(opted_echo)) == opted_v2
    rejected('v1 encoder cannot discard opted source',
             lambda: encode_magic_simulation_result(opted_command, opted_summary))
    rejected('same-ID None summary substitution',
             lambda: assess_magic_candidate(restored_opted, legacy_summary, window))
    rejected('same-ID opted summary relabelled legacy',
             lambda: assess_magic_candidate(simulation.request, opted_summary, window))
    dice = ScriptedDice((9, 9, 9, 7, 7, 7) + (10,) * 10)
    trace = run_npc_magic_scenario(restored_opted.scenario, dice)
    assert dice.calls == 16 and sum(isinstance(s.result, NpcRosterUnnaturalWindResult) for s in trace.steps) == 1
    assert trace.source == restored_opted.scenario
    trial = opted_result.trials[0]
    assert trial.source_scenario == trace.source and trial.outcome == trace.outcome
    assert (trial.executed_action_count, trial.started_round_count, trial.completed_round_count) == (
        trace.executed_actions, trace.started_rounds, trace.completed_rounds)
    print('Restored opted source: actual Wind trace 16 d10 + matching independent trial 16 d10; no probabilities')
    print('V1/no-family-opt-in guards and same-ID full-source substitution guards remain effective')
    assert (simulation, balance, policy) == before and getstate() == rng_before
    print('Inputs/global RNG unchanged; public native generation and simulation v2 verified; balance v2 still manual')


if __name__ == '__main__':
    main()
