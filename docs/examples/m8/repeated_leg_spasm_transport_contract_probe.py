"""ADR-0054 production generation and magic v4 against a finite inverse oracle.

Copy with generation_contract_probe.py, stationary_wound_runner.py,
magic_scenario.py and json/magic-{simulation,balance}-v3.request.json.
The independent inverse only accepts those complete fixtures plus three permissions.
Production commands, generated candidates and result encoding remain authoritative.
PG1.4 Rules116/119/122-123, Wounds190; GM1.1 Champions92. No new gameplay.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
from random import getstate
from unittest.mock import patch

from generation_contract_probe import authored_reserve, project
from magic_scenario import authored_scenario, ScriptedDice
from stationary_wound_runner import authored_input, ScriptedFactory
from towr.adapters import magic_balance_json as balance_wire
from towr.adapters import magic_simulation_json as simulation_wire
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import (
    NpcMagicMiscastContinuationPolicy, NpcMagicRepeatedLegSpasmPolicy as Repeated,
    NpcMagicStationaryWoundPolicy as Stationary,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandResult
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


FIELD = 'repeated_leg_spasm_continuation'
BASE_FIELD = 'stationary_wound_continuation'
POLICY = Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES
BASE = Stationary.LEG_SPASM_STAND_AND_CONTINUE
OPTIONS = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)
VECTORS = ((1, 0), (1, 1), (2, 0), (2, 1))


def rejected(operation, error=ValueError):
    try:
        operation()
    except error as caught:
        return caught
    raise AssertionError('expected rejection')


def definitions(source):
    return tuple(dict.fromkeys(p.definition.id for p in source.initial.roster.participants))


def policy_values(source):
    return source.miscast_continuation, source.stationary_wound_continuation, source.repeated_leg_spasm_continuation


def check_finite_policies(values):
    """Independent local oracle, not production admission."""
    miscast, stationary, repeated = values
    assert miscast is None or isinstance(miscast, NpcMagicMiscastContinuationPolicy)
    if miscast is not None:
        replace(miscast)
        replace(miscast.facts)
    assert stationary is None or isinstance(stationary, Stationary)
    assert repeated is None or isinstance(repeated, Repeated)
    assert repeated is None or stationary is BASE


def select(source, values):
    check_finite_policies(values)
    return replace(source, miscast_continuation=values[0], stationary_wound_continuation=values[1],
                   repeated_leg_spasm_continuation=values[2])


def assert_finite_family(template, assertions):
    # Both originals are type checked before str-Enum/value equality.
    check_finite_policies(policy_values(template))
    check_finite_policies(assertions)
    replace(template.facts)
    assert policy_values(template) == assertions


def miscast_wire(value):
    return None if value is None else {
        'choice': value.choice.value, 'facts': asdict(value.facts), 'prone_policy': value.prone_policy.value}


def proposed_wire(baseline, values, *, balance):
    check_finite_policies(values)
    document = deepcopy(baseline)
    document['schema_version'] = '4'
    targets = (document['reserve']['scenario'], document['generation']) if balance else (document['scenario'],)
    for target in targets:
        target['miscast_continuation'] = miscast_wire(values[0])
        target[BASE_FIELD] = None if values[1] is None else values[1].value
        target[FIELD] = None if values[2] is None else values[2].value
    return document


def finite_inverse(document, baseline_wire, original, miscast, *, balance):
    """Full-fixture oracle independent of the production v4 parser.

    Balance returns a native reserve, independent family assertions and the
    original parameter source. That source remains an unmodified v3 request;
    the actual opted generation request is admitted independently by parser4.
    """
    def read_node(node):
        raw_miscast = node['miscast_continuation']
        if raw_miscast is not None:
            assert type(raw_miscast) is dict and raw_miscast == miscast_wire(miscast)
            assert all(type(value) is bool for value in raw_miscast['facts'].values())
        raw_base, raw_repeat = node[BASE_FIELD], node[FIELD]  # Required even for null.
        assert raw_base is None or type(raw_base) is str and raw_base == BASE.value
        assert raw_repeat is None or type(raw_repeat) is str and raw_repeat == POLICY.value
        result = (None if raw_miscast is None else miscast,
                  None if raw_base is None else BASE, None if raw_repeat is None else POLICY)
        check_finite_policies(result)
        return result

    values = read_node(document['reserve']['scenario'] if balance else document['scenario'])
    if balance:
        assert read_node(document['generation']) == values
    expected = proposed_wire(baseline_wire, values, balance=balance)
    assert document == expected
    # Python equality aliases True and 1; the finite full-document oracle does
    # not. Object-key order is immaterial, all arrays and scalar types remain.
    assert json.dumps(document, sort_keys=True) == json.dumps(expected, sort_keys=True)
    if balance:
        template = select(original.generation_request.template_scenario, values)
        assert_finite_family(template, values)
        return template, values, original.generation_request
    return replace(original.request, scenario=select(original.request.scenario, values))


def genuine_legacy_documents():
    """Separate permission-free sources, authored before any selected source."""
    source, reserve = authored_scenario(), authored_reserve()
    simulation = MagicSimulationCommand('finite:legacy', NpcMagicSimulationRequest(source, 42, 1),
                                        OPTIONS, definitions(source))
    request = MagicCandidateGenerationRequest(reserve,
        (MagicCompositionGroup('first', ('E2', 'E1'), 1, 2), MagicCompositionGroup('second', ('E3',), 0, 1)),
        reserve.facts, reserve.scene_frames, 'finite:legacy', 4, 42, (MagicBalanceStage(1, 1),), 4,
        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
    balance = MagicBalanceCommand('finite:legacy', request, OPTIONS, definitions(reserve))
    return tuple((simulation_wire._request_document(replace(simulation, schema_version=version)),
                  balance_wire._request_document(replace(balance, schema_version=version))) for version in ('1', '2'))


def main():
    rng_before = getstate()
    directory = Path(__file__).resolve().parent / 'json'
    sim_wire = json.loads((directory / 'magic-simulation-v3.request.json').read_text(encoding='utf-8'))
    bal_wire = json.loads((directory / 'magic-balance-v3.request.json').read_text(encoding='utf-8'))
    simulation = simulation_wire.parse_magic_simulation_request(json.dumps(sim_wire))
    balance = balance_wire.parse_magic_balance_request(json.dumps(bal_wire))
    legacy = genuine_legacy_documents()
    sources = (sim_wire, bal_wire, simulation, balance, legacy)
    before = deepcopy(sources)
    miscast = simulation.request.scenario.miscast_continuation
    assert miscast is not None and balance.generation_request.miscast_continuation == miscast
    combinations = tuple((miscast if m else None, BASE if s else None, POLICY if r else None)
                         for m, s, r in product((False, True), repeat=3) if not r or s)
    assert len(combinations) == 6
    for m in (None, miscast):
        rejected(lambda: replace(simulation.request.scenario, miscast_continuation=m,
                                 stationary_wound_continuation=None, repeated_leg_spasm_continuation=POLICY))
    print('PERMISSIONS: six valid native combinations; two repeated-without-base combinations rejected; Miscast independent')

    with patch('random.Random', side_effect=AssertionError('no RNG during finite transport/projection')):
        roundtrips = 0
        for values in combinations:
            for is_balance, baseline, command, parser, error_type in (
                (False, sim_wire, simulation, simulation_wire.parse_magic_simulation_request, MagicSimulationInputError),
                (True, bal_wire, balance, balance_wire.parse_magic_balance_request, MagicBalanceInputError),
            ):
                proposed = proposed_wire(baseline, values, balance=is_balance)
                restored = finite_inverse(proposed, baseline, command, miscast, balance=is_balance)
                template = restored[0] if is_balance else restored.scenario
                expected = select(command.generation_request.template_scenario if is_balance else command.request.scenario, values)
                assert template == expected and policy_values(template) == values
                if is_balance:
                    assert restored[1] == values and restored[2] is command.generation_request
                    # Omission still means None; template opt-in cannot supply
                    # the independent family assertion implicitly.
                    if values[2] is not None:
                        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as count:
                            rejected(lambda: replace(restored[2], template_scenario=template,
                                miscast_continuation=values[0], stationary_wound_continuation=values[1]))
                            count.assert_not_called()
                else:
                    assert restored.master_seed == command.request.master_seed and restored.trials == command.request.trials
                    assert tuple(restored.seed_for(i) for i in range(restored.trials)) == tuple(
                        command.request.seed_for(i) for i in range(command.request.trials))
                actual = parser(json.dumps(proposed))
                actual_template = actual.generation_request.template_scenario if is_balance else actual.request.scenario
                assert actual_template == template
                assert actual.schema_version == '4'
                if is_balance:
                    family = actual.generation_request
                    assert (family.miscast_continuation, family.stationary_wound_continuation,
                            family.repeated_leg_spasm_continuation) == restored[1]
                    assert balance_wire._request_document(actual) == proposed
                else:
                    assert actual.request == restored
                    assert simulation_wire._request_document(actual) == proposed
                caught = rejected(lambda: parser(json.dumps(dict(proposed, schema_version='6'))), error_type)
                assert caught.code is RangedInputErrorCode.UNSUPPORTED_VERSION and caught.schema_version == '1'
                assert caught.request_id == baseline['request_id'] and caught.path == '/schema_version'
                roundtrips += 1
        assert roundtrips == 12
        print('PUBLIC v4: twelve parser/request-echo roundtrips match independent full-fixture inverses; exact sources/IDs/order/seeds/parameters')
        print('VERSION GUARD: unknown6 rejected with fallback1 and decoded request ID; no implicit downgrade')

        # The known fixture is checked in full: missing/null is not inheritance;
        # unrelated IDs/order/facts and independent family substitutions fail.
        selected_values = (miscast, BASE, POLICY)
        selected = proposed_wire(bal_wire, selected_values, balance=True)
        for mutate in (
            lambda d: d['generation'].pop(FIELD),
            lambda d: d['generation'].__setitem__(FIELD, None),
            lambda d: d['generation'].__setitem__(BASE_FIELD, None),
            lambda d: d['generation'].__setitem__('miscast_continuation', None),
            lambda d: d.__setitem__('request_id', 'foreign-same-shape'),
            lambda d: d['reserve']['scenario'].__setitem__(FIELD, True),
            lambda d: d['generation']['miscast_continuation']['facts'].__setitem__('all_combatants_in_roster', 1),
            lambda d: d['reserve']['scenario']['facts'].__setitem__('no_external_condition_sources', 1),
        ):
            wrong = deepcopy(selected)
            mutate(wrong)
            rejected(lambda: finite_inverse(wrong, bal_wire, balance, miscast, balance=True), (AssertionError, KeyError))
        selected_template = select(balance.generation_request.template_scenario, selected_values)
        for index in (0, 1, 2):
            foreign_values = list(selected_values)
            foreign_values[index] = None
            rejected(lambda: assert_finite_family(selected_template, tuple(foreign_values)), AssertionError)
        foreign = deepcopy(selected_template)
        object.__setattr__(foreign, FIELD, POLICY.value)
        assert foreign == selected_template
        rejected(lambda: assert_finite_family(foreign, selected_values), AssertionError)
        mismatch = deepcopy(selected)
        mismatch['generation'][FIELD] = None
        caught = rejected(lambda: balance_wire.parse_magic_balance_request(json.dumps(mismatch)), MagicBalanceInputError)
        assert caught.schema_version == '4' and caught.path == '/generation/' + FIELD
        print('SOURCE GUARDS: independent oracle rejects foreign IDs/types; production rejects missing independent family opt-in and exact v4 mismatch path')

        reserve = authored_reserve()
        projected_count = 0
        for opposite in (False, True):
            base = replace(reserve, perspective_side=CombatSide.OPPOSITION,
                           objective=NpcDefeatObjective(('wizard', 'ally'))) if opposite else reserve
            retained_vectors = (('wizard', 'ally', 'E1', 'E2', 'E3'),) if opposite else tuple(
                ('wizard', 'ally', *('E2', 'E1')[:first], *('E3',)[:second]) for first, second in VECTORS)
            for values in combinations:
                template = select(base, values)
                snapshot = deepcopy(template)
                assert_finite_family(template, values)
                groups = ((MagicCompositionGroup('opposite', ('ally',), 1, 1),) if opposite else
                    (MagicCompositionGroup('first', ('E2', 'E1'), 1, 2), MagicCompositionGroup('second', ('E3',), 0, 1)))
                family = MagicCandidateGenerationRequest(template, groups, template.facts, template.scene_frames,
                    f'finite:{opposite}', len(retained_vectors), 42, (MagicBalanceStage(1, 1),), len(retained_vectors),
                    ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)),
                    miscast_continuation=values[0], stationary_wound_continuation=values[1],
                    repeated_leg_spasm_continuation=values[2])
                generated = generation.generate_magic_candidates(family)
                assert generated.source_request is family
                assert generated.evaluation_request.master_seed == family.master_seed == 42
                assert len(generated.evaluation_request.candidates) == family.candidate_count == len(retained_vectors)
                assert generated.evaluation_request.planned_trials == family.planned_trials == len(retained_vectors)
                for index, retained in enumerate(retained_vectors):
                    candidate = generated.evaluation_request.candidates[index]
                    identifier = candidate.candidate_id
                    projected = project(template, set(retained), identifier, template.facts, template.scene_frames)
                    assert candidate.scenario == projected
                    assert policy_values(projected) == values and projected.id == identifier
                    assert projected.initial.roster.participants == tuple(p for p in template.initial.roster.participants
                        if p.state.actor_id in retained)
                    assert projected.activation_order == tuple(actor for actor in template.activation_order if actor in retained)
                    assert projected.initial.spatial_state.placements == tuple(p for p in template.initial.spatial_state.placements
                        if p.entity_id in retained)
                    assert projected.objective.target_actor_ids == tuple(actor for actor in template.objective.target_actor_ids
                        if actor in retained)
                    assert projected.facts == template.facts and projected.initial.wizard == template.initial.wizard
                    assert projected.spell == template.spell and projected.max_rounds == template.max_rounds
                    request = NpcMagicSimulationRequest(projected, 42, 2)
                    renamed = replace(request, scenario=replace(projected, id='other-local-id'))
                    assert tuple(request.seed_for(i) for i in range(2)) == tuple(renamed.seed_for(i) for i in range(2))
                    projected_count += 1
                assert template == snapshot
        assert projected_count == 30
        print('PRODUCTION GENERATION: thirty full-source subsets match manual projections; both perspectives/six policies; exact family permissions/C/budgets/seeds')

        for documents in (*legacy, (sim_wire, bal_wire)):
            for is_balance, original, parser, error_type in (
                (False, documents[0], simulation_wire.parse_magic_simulation_request, MagicSimulationInputError),
                (True, documents[1], balance_wire.parse_magic_balance_request, MagicBalanceInputError),
            ):
                parser(json.dumps(original))  # Genuine old baseline is admitted first.
                locations = ('reserve', 'generation') if is_balance else ('scenario',)
                for location in locations:
                    for value in (None, POLICY.value):
                        wrong = deepcopy(original)
                        target = wrong['reserve']['scenario'] if location == 'reserve' else wrong[location]
                        target[FIELD] = value
                        caught = rejected(lambda: parser(json.dumps(wrong)), error_type)
                        assert caught.schema_version == original['schema_version'] and caught.request_id == original['request_id']
        for version in ('1', '2', '3'):
            caught = rejected(lambda: scenario_document(selected_template, ('missing-definition',), schema_version=version))
            assert 'repeated Leg Spasm' in str(caught) and 'losslessly' in str(caught)
        print('LEGACY BOUNDARIES: JSON1/2/3 reject isolated new field even null and refuse lossless encoding; matching generation permission is explicit')

    # Real native execution, independent of the manual proposed wire oracle.
    source = replace(authored_input(), repeated_leg_spasm_continuation=POLICY)
    source_before = deepcopy(source)
    hit = (1, 2, 3, 10, 10, 10)
    values = (*hit, 9, *((10,) * 9), *hit, 4, 5, *((10,) * 24))
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(values) == 48 and result.outcome is NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
    first = next(step.result for step in result.steps if isinstance(step.result, NpcRosterLegSpasmStandResult))
    second = tuple(step.result for step in result.steps if isinstance(step.result, NpcRosterRepeatedLegSpasmStandResult))
    assert len(second) == 1 and second[0].source.previous_stand == first
    assert any(step.result == second[0].source.wound_attack for step in result.steps)
    request = NpcMagicSimulationRequest(source, 42, 1)
    records = run_npc_magic_simulation(request, rng_factory=ScriptedFactory((request.seed_for(0),), (values,)))
    summary = summarize_npc_magic_simulation(records)
    assert summary.source_request == request and summary.trials == 1
    assert records.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 0)
    assert (records.trials[0].executed_action_count, records.trials[0].completed_round_count) == (9, 3)
    command = MagicSimulationCommand('finite:actual-native', request, OPTIONS, definitions(source), '4')
    document = simulation_wire._request_document(command)
    assert simulation_wire.parse_magic_simulation_request(json.dumps(document)) == command
    encoded = json.loads(simulation_wire.encode_magic_simulation_result(command, summary))
    assert encoded['schema_version'] == '4' and encoded['request'] == document
    assert encoded['summary']['trials'] == summary.trials == 1
    for version in ('1', '2', '3'):
        caught = rejected(lambda: simulation_wire.encode_magic_simulation_result(replace(command, schema_version=version), summary))
        assert 'repeated Leg Spasm' in str(caught) and 'losslessly' in str(caught)

    balance_document = proposed_wire(bal_wire, (miscast, BASE, POLICY), balance=True)
    balance_command = balance_wire.parse_magic_balance_request(json.dumps(balance_document))
    balance_before = deepcopy(balance_command)
    balance_result = execute_magic_balance(balance_command)
    balance_output = json.loads(balance_wire.encode_magic_balance_result(balance_command, balance_result))
    assert balance_wire.parse_magic_balance_request(json.dumps(balance_output['request'])) == balance_command
    assert balance_output['schema_version'] == '4' and balance_output['request'] == balance_document
    assert balance_result.generation_result.source_request == balance_command.generation_request
    assert balance_result.evaluation_result.source_request == balance_result.generation_result.evaluation_request
    for report in balance_result.evaluation_result.stage_reports:
        for row in report.candidates:
            assert row.assessment.summary.source_request.scenario.repeated_leg_spasm_continuation is POLICY
    assert balance_result.evaluation_result.total_trials <= balance_result.evaluation_result.planned_trials
    assert balance_command == balance_before
    assert source == source_before and sources == before and getstate() == rng_before
    print('ACTUAL SIMULATION v4: 48 d10 journal with stand48 + stand52; independent 48 d10 summary; denominator1; full v4 result echo')
    print('ACTUAL BALANCE v4: standard seeded service completes bounded generation/stages; full request/report/summary permissions retained')
    print('96 scripted d10 plus standard seeded balance; input/global RNG unchanged; production generation and both v4 codecs implemented')


if __name__ == '__main__':
    main()
