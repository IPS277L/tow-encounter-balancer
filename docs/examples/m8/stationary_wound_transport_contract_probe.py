"""Finite ADR-0051 proposal, NOT a v3 parser or production family admission.

Copy with generation_contract_probe.py, magic_scenario.py, opted_miscast.py
and stationary_wound_runner.py. Genuine legacy v2 echoes are prepared before
opted sources. No opted source is stripped to cross an old transport boundary.
Finite mappings assert the entire baseline document, including ordered arrays;
they do not implement general JSON validation. No probability claims.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import json
from random import getstate

from generation_contract_probe import authored_reserve, project
from magic_scenario import ScriptedDice
from opted_miscast import opted_scenario
from stationary_wound_runner import authored_input
from towr.adapters.magic_balance_json import encode_magic_balance_result, parse_magic_balance_request
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.magic_simulation_json import encode_magic_simulation_result, parse_magic_simulation_request
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import (
    NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy, NpcMagicStationaryWoundPolicy as Stationary,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


FIELD = 'stationary_wound_continuation'
POLICY = Stationary.LEG_SPASM_STAND_AND_CONTINUE
VECTORS = ((1, 0), (1, 1), (2, 0), (2, 1))
WINDOW = ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1))
OPTIONS = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)


def rejected(operation, error=ValueError):
    try:
        operation()
    except error:
        return
    raise AssertionError('expected rejection')


def policy_wire(value):
    return None if value is None else {'choice': value.choice.value, 'facts': asdict(value.facts),
                                      'prone_policy': value.prone_policy.value}


def read_finite_policies(document):
    """Explicit mapping for these finite examples, not a proposed validator."""
    raw = document[FIELD]  # Required even when null.
    assert raw is None or type(raw) is str and raw == POLICY.value
    stationary = None if raw is None else Stationary(raw)
    raw_miscast = document['miscast_continuation']
    if raw_miscast is None:
        return None, stationary
    assert set(raw_miscast) == {'choice', 'facts', 'prone_policy'}
    facts = raw_miscast['facts']
    assert set(facts) == {'all_combatants_in_roster', 'no_external_short_range_creatures',
                         'unmounted_combatants_only', 'no_effect_immunities', 'no_cross_zone_close'}
    assert all(type(value) is bool for value in facts.values())
    return NpcMagicMiscastContinuationPolicy(NpcRosterMiscastPolicy(raw_miscast['choice']),
        NpcRosterMiscastFacts(**facts), NpcMagicPronePolicy(raw_miscast['prone_policy'])), stationary


def assert_finite_family(template, miscast, stationary):
    """Proposed pre-projection assertions, explicitly not production admission."""
    assert template.stationary_wound_continuation is None or isinstance(
        template.stationary_wound_continuation, Stationary)
    assert template.miscast_continuation is None or isinstance(
        template.miscast_continuation, NpcMagicMiscastContinuationPolicy)
    assert stationary is None or isinstance(stationary, Stationary)
    assert miscast is None or isinstance(miscast, NpcMagicMiscastContinuationPolicy)
    assert template.miscast_continuation == miscast
    assert template.stationary_wound_continuation == stationary


def proposed_wire(baseline, miscast, stationary, *, balance):
    result = deepcopy(baseline)
    result['schema_version'] = '3'
    scenario = result['reserve']['scenario'] if balance else result['scenario']
    scenario['miscast_continuation'] = policy_wire(miscast)
    scenario[FIELD] = None if stationary is None else stationary.value
    if balance:
        result['generation']['miscast_continuation'] = policy_wire(miscast)
        result['generation'][FIELD] = scenario[FIELD]
    return result


def restore_finite(document, baseline_wire, baseline_command, *, balance):
    """Only the full baseline fixtures plus two independent policies are mapped.

    Never removes fields and never submits a downgraded opted document to a
    production parser. Complete equality below constrains every other field.
    """
    node = document['reserve']['scenario'] if balance else document['scenario']
    miscast, stationary = read_finite_policies(node)
    assert document == proposed_wire(baseline_wire, miscast, stationary, balance=balance)
    if balance:
        assert read_finite_policies(document['generation']) == (miscast, stationary)
        original = baseline_command.generation_request
        template = replace(original.template_scenario, miscast_continuation=miscast,
                           stationary_wound_continuation=stationary)
        assert_finite_family(template, miscast, stationary)
        # Current production generation cannot represent the new field. Keep
        # its complete unchanged numeric/facts/order specification separately.
        return original, template, miscast, stationary
    return replace(baseline_command.request,
        scenario=replace(baseline_command.request.scenario, miscast_continuation=miscast,
                         stationary_wound_continuation=stationary))


def definitions(source):
    return tuple(dict.fromkeys(p.definition.id for p in source.initial.roster.participants))


def legacy_fixture(opposite):
    source = replace(authored_reserve(), max_rounds=1)
    groups = (MagicCompositionGroup('first', ('E2', 'E1'), 1, 2),
              MagicCompositionGroup('second', ('E3',), 0, 1))
    if opposite:
        source = replace(source, perspective_side=CombatSide.OPPOSITION,
                         objective=NpcDefeatObjective(('wizard', 'ally')))
        groups = (MagicCompositionGroup('ally', ('ally',), 1, 1),)
    generation = MagicCandidateGenerationRequest(source, groups, source.facts, source.scene_frames,
        'finite:opposite' if opposite else 'finite:friendly', 4, 42, (MagicBalanceStage(1, 1),), 4, WINDOW)
    simulation = MagicSimulationCommand('finite:simulation', NpcMagicSimulationRequest(source, 42, 1),
                                        OPTIONS, definitions(source), '2')
    balance = MagicBalanceCommand('finite:balance', generation, OPTIONS, definitions(source), '2')
    summary = summarize_npc_magic_simulation(run_npc_magic_simulation(simulation.request))
    balance_result = execute_magic_balance(balance)
    sim_wire = json.loads(encode_magic_simulation_result(simulation, summary))['request']
    bal_wire = json.loads(encode_magic_balance_result(balance, balance_result))['request']
    sim_v1 = json.loads(encode_magic_simulation_result(replace(simulation, schema_version='1'), summary))['request']
    bal_v1 = json.loads(encode_magic_balance_result(replace(balance, schema_version='1'), balance_result))['request']
    assert parse_magic_simulation_request(json.dumps(sim_wire)) == simulation
    assert parse_magic_balance_request(json.dumps(bal_wire)) == balance
    assert parse_magic_simulation_request(json.dumps(sim_v1)) == replace(simulation, schema_version='1')
    assert parse_magic_balance_request(json.dumps(bal_v1)) == replace(balance, schema_version='1')
    return simulation, balance, sim_wire, bal_wire, sim_v1, bal_v1


def main():
    rng_before = getstate()
    # Construct genuine complete v2 fixtures before any opted source exists.
    fixtures = tuple(legacy_fixture(opposite) for opposite in (False, True))
    before = deepcopy(fixtures)
    miscast_policy = opted_scenario().miscast_continuation
    projection_count = wire_count = 0
    staged_candidates = []
    for opposite, (simulation, balance, sim_base, bal_base, sim_v1, bal_v1) in zip((False, True), fixtures, strict=True):
        original = balance.generation_request
        baseline_candidates = generate_magic_candidates(original).evaluation_request.candidates
        vectors = ((1,),) if opposite else VECTORS
        for miscast in (None, miscast_policy):
            for stationary in (None, POLICY):
                template = replace(original.template_scenario, miscast_continuation=miscast,
                                   stationary_wound_continuation=stationary)
                assert_finite_family(template, miscast, stationary)
                rejected(lambda: assert_finite_family(template, miscast, POLICY if stationary is None else None), AssertionError)
                rejected(lambda: assert_finite_family(template, miscast_policy if miscast is None else None, stationary), AssertionError)
                rejected(lambda: assert_finite_family(template, miscast, POLICY.value), AssertionError)
                template_before = deepcopy(template)
                forged = deepcopy(template)
                object.__setattr__(forged, FIELD, POLICY.value)
                rejected(lambda: assert_finite_family(forged, miscast, POLICY), AssertionError)
                forged_miscast = deepcopy(template)
                object.__setattr__(forged_miscast, 'miscast_continuation', policy_wire(miscast_policy))
                rejected(lambda: assert_finite_family(forged_miscast, miscast_policy, stationary), AssertionError)
                assert template == template_before
                if stationary is not None:
                    rejected(lambda: replace(original, template_scenario=template, miscast_continuation=miscast))
                else:
                    assert generate_magic_candidates(replace(original, template_scenario=template,
                        miscast_continuation=miscast)).source_request.template_scenario == template
                for is_balance, base, v1_base, command, parser, error in (
                    (False, sim_base, sim_v1, simulation, parse_magic_simulation_request, MagicSimulationInputError),
                    (True, bal_base, bal_v1, balance, parse_magic_balance_request, MagicBalanceInputError)):
                    document = proposed_wire(base, miscast, stationary, balance=is_balance)
                    untouched = deepcopy(document)
                    transported = json.loads(json.dumps(document))
                    restored = restore_finite(transported, base, command, balance=is_balance)
                    if is_balance:
                        assert restored == (original, template, miscast, stationary)
                    else:
                        assert restored == replace(simulation.request, scenario=template)
                    assert transported == untouched == document
                    rejected(lambda: parser(json.dumps(document)), error)  # v3 not implemented.
                    old_version = deepcopy(document)
                    old_version['schema_version'] = '2'
                    rejected(lambda: parser(json.dumps(old_version)), error)
                    # Isolate the new forbidden field: genuine v1 contains no
                    # Miscast field whose presence could mask this rejection.
                    old_v1 = deepcopy(v1_base)
                    v1_node = old_v1['reserve']['scenario'] if is_balance else old_v1['scenario']
                    assert 'miscast_continuation' not in v1_node and FIELD not in v1_node
                    v1_node[FIELD] = None if stationary is None else stationary.value
                    rejected(lambda: parser(json.dumps(old_v1)), error)
                    if is_balance:
                        family_v1 = deepcopy(v1_base)
                        family_v1['generation'][FIELD] = None if stationary is None else stationary.value
                        rejected(lambda: parser(json.dumps(family_v1)), error)
                    missing = deepcopy(document)
                    node = missing['reserve']['scenario'] if is_balance else missing['scenario']
                    del node[FIELD]
                    rejected(lambda: restore_finite(missing, base, command, balance=is_balance), KeyError)
                    if is_balance:
                        mismatch = deepcopy(document)
                        mismatch['generation'][FIELD] = POLICY.value if stationary is None else None
                        rejected(lambda: restore_finite(mismatch, base, command, balance=True), AssertionError)
                    wire_count += 1
                for counts, baseline in zip(vectors, baseline_candidates, strict=True):
                    variable = {i for group in original.groups for i in group.actor_ids}
                    retained = {p.state.actor_id for p in template.initial.roster.participants
                                if p.state.actor_id not in variable}
                    retained.update(i for group, count in zip(original.groups, counts, strict=True)
                                    for i in group.actor_ids[:count])
                    projected = project(template, retained, baseline.candidate_id, original.facts, original.scene_frames)
                    assert projected == replace(baseline.scenario, miscast_continuation=miscast,
                                                stationary_wound_continuation=stationary)
                    source = NpcMagicSimulationRequest(projected, original.master_seed, 2)
                    reference = NpcMagicSimulationRequest(baseline.scenario, original.master_seed, 2)
                    assert tuple(source.seed_for(i) for i in range(2)) == tuple(reference.seed_for(i) for i in range(2))
                    projection_count += 1
                    if not opposite and counts == (1, 0):
                        staged_candidates.append(MagicBalanceCandidate(f'policy:{len(staged_candidates)}', projected))
    assert projection_count == 20 and wire_count == 16
    print('Finite proposed v3: 16 complete simulation/balance mappings; four independent policy combinations; both perspectives')
    print('Manual family projection: 20 full-source subsets (4 friendly + 1 opposite) x 4 policies; IDs/orders/frames/seeds exact')
    print('Required nullable fields and separate family equality checked before projection; raw enum strings rejected by finite assertions')
    print('Production: stationary generation rejected; JSON v1/v2 extra fields rejected even null; v3 unsupported')

    staged = MagicStagedEvaluationRequest(tuple(staged_candidates), 42, (MagicBalanceStage(1, 4),), 4, WINDOW)
    staged_before = deepcopy(staged)
    report = evaluate_magic_candidates_staged(staged, OPTIONS)
    assert report.source_request is staged and staged == staged_before
    assert report.total_trials == 4 and len(report.stage_reports) == 1
    rows = report.stage_reports[0].candidates
    for candidate, row in zip(staged.candidates, rows, strict=True):
        assert row.candidate_id == candidate.candidate_id
        assert row.assessment.source_request.scenario == candidate.scenario
        assert row.assessment.summary.source_request == row.assessment.source_request
        assert row.assessment.summary.trials == 1
    print('Public native staged service: four manual subset candidates -> one stage -> four complete source-bound rows; denominator 4')

    # Real stationary effect and legacy controls through the current native API.
    # Explicit scripts are finite execution evidence, not a sampling experiment.
    draws = 0
    for miscast in (False, True):
        for stationary in (False, True):
            source = authored_input(stationary=stationary, miscast=miscast)
            source_before = deepcopy(source)
            hit = (1, 2, 3, 10, 10, 10)
            positive = (*hit, 9, *((10,) * 9), *hit, 1, 5, *((10,) * 24)) if stationary else (*hit, 9)
            scripts = (positive, (*hit, 10))
            request = NpcMagicSimulationRequest(source, 42, 2)
            seeds = tuple(request.seed_for(i) for i in range(2))
            dice = []
            def factory(seed):
                value = ScriptedDice(scripts[seeds.index(seed)])
                dice.append(value)
                return value
            result = run_npc_magic_simulation(request, rng_factory=factory)
            assert source == source_before and result.source_request is request
            assert tuple(d.calls for d in dice) == tuple(map(len, scripts))
            assert all(trial.source_scenario is source for trial in result.trials)
            summary = summarize_npc_magic_simulation(result)
            assessment = assess_magic_candidate(request, summary, WINDOW)
            foreign = replace(request, scenario=replace(source,
                stationary_wound_continuation=None if stationary else POLICY))
            assert foreign.scenario.id == source.id
            rejected(lambda: assess_magic_candidate(foreign, summary, WINDOW))
            assert summary.trials == 2 and assessment.window_match is None
            assert summary.outcome_counts == NpcMagicOutcomeCounts(0, 0, int(stationary), 2 - int(stationary))
            assert assessment.unsupported_path_rate == (Fraction(1, 2) if stationary else Fraction(1))
            if stationary:
                for version in ('1', '2'):
                    command = MagicSimulationCommand('finite:lossless', request, OPTIONS, definitions(source), version)
                    rejected(lambda: encode_magic_simulation_result(command, summary))
            draws += sum(d.calls for d in dice)
    assert draws == 138
    print('Native scripted controls: 8 trials / 138 d10; opted round-limit + unsupported, None two unsupported; denominator 2 per source')
    print('Production v1/v2 encoders reject full opted sources; no stripped opted source or downgraded document used')
    assert fixtures == before and getstate() == rng_before
    print('Inputs/global RNG unchanged; finite proposal only, no production v3 codec/schema/CLI/generator implementation')


if __name__ == '__main__':
    main()
