"""ADR-0058 finite transport specification, using actual native ADR-0057.

Copy with crushed_rib_native.py, crushed_rib_owner.py,
generation_contract_probe.py, stationary_wound_runner.py and magic_scenario.py.
Manual projections/current6 JSON inverse below remain bounded fixture oracles for
balance; Simulation uses the production parser/encoder and CLI.
PG1.4 pp108,118,123,156-157,190; GM1.1 p92. No new gameplay.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
import json
from multiprocessing import active_children
import os
from random import getstate
from unittest.mock import patch

from crushed_rib_native import FIRST_TEN, NEW_FOUR_STREAM, POLICY, ScriptedFactory, direct
from crushed_rib_owner import enemy_first
from generation_contract_probe import authored_reserve, project
from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.adapters import magic_balance_json as balance_wire
from towr.adapters import magic_simulation_json as simulation_wire
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode
from towr.application import magic_candidate_generation as generation
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import (
    NpcMagicCrushedRibPolicy, NpcMagicMiscastContinuationPolicy,
    NpcMagicStationaryWoundPolicy as Stationary, NpcMagicRepeatedLegSpasmPolicy as Repeated,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.test_models import TestQuality
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


FIELDS = ('miscast_continuation', 'stationary_wound_continuation',
          'repeated_leg_spasm_continuation', 'crushed_rib_continuation')
WINDOW = ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1))
SEQUENTIAL = Options(Mode.SEQUENTIAL)


def rejected(operation, error=ValueError):
    try:
        operation()
    except error as caught:
        return caught
    raise AssertionError('expected rejection')


def definitions(source):
    return tuple(dict.fromkeys(p.definition.id for p in source.initial.roster.participants))


def policies(source):
    return tuple(getattr(source, field) for field in FIELDS)


def finite_policies(values):
    """Independent finite specification, with strict originals before equality."""
    miscast, stationary, repeated, crushed = values
    assert miscast is None or isinstance(miscast, NpcMagicMiscastContinuationPolicy)
    if miscast is not None:
        replace(miscast)
        replace(miscast.facts)
    assert stationary is None or isinstance(stationary, Stationary)
    assert repeated is None or isinstance(repeated, Repeated)
    assert crushed is None or isinstance(crushed, NpcMagicCrushedRibPolicy)
    assert repeated is None or stationary is Stationary.LEG_SPASM_STAND_AND_CONTINUE


def selected(base, values):
    finite_policies(values)
    return replace(base, **dict(zip(FIELDS, values, strict=True)))


def finite_family(template, values):
    finite_policies(policies(template))
    finite_policies(values)
    replace(template.facts)
    assert policies(template) == values


def policy_wire(values):
    finite_policies(values)
    miscast, *enums = values
    return (None if miscast is None else {'choice': miscast.choice.value,
        'facts': asdict(miscast.facts), 'prone_policy': miscast.prone_policy.value},
        *(None if enum is None else enum.value for enum in enums))


def proposed_document(baseline, values, *, balance):
    """Build a candidate v5 specification from an independently authored None v4."""
    document = deepcopy(baseline)
    document['schema_version'] = '6'
    nodes = (document['reserve']['scenario'], document['generation']) if balance else (document['scenario'],)
    for node in nodes:
        node.update(zip(FIELDS, policy_wire(values), strict=True))
    return document


def finite_inverse(document, baseline, original, miscast, *, balance):
    """Only this full fixture is understood; this does not call a future codec.

    Return an actual native scenario and independent family assertion. Balance
    parameters remain the original genuine None request, never a fictional58
    request or a temporary permission-stripped view of an opted source.
    """
    def read(node):
        raw = tuple(node[field] for field in FIELDS)  # Nullable is required.
        assert raw[0] is None or type(raw[0]) is dict and raw[0] == policy_wire((miscast, None, None, None))[0]
        if raw[0] is not None:
            assert all(type(value) is bool for value in raw[0]['facts'].values())
        constants = (Stationary.LEG_SPASM_STAND_AND_CONTINUE,
                     Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES, POLICY)
        for value, constant in zip(raw[1:], constants, strict=True):
            assert value is None or type(value) is str and value == constant.value
        values = (None if raw[0] is None else miscast,
                  *(None if value is None else constant for value, constant in zip(raw[1:], constants, strict=True)))
        finite_policies(values)
        return values

    values = read(document['reserve']['scenario'] if balance else document['scenario'])
    if balance:
        assert read(document['generation']) == values
    expected = proposed_document(baseline, values, balance=balance)
    # Canonical JSON also rejects bool/int aliases; arrays/order and every full
    # source field remain checked, rather than IDs or selected policy fields.
    assert json.dumps(document, sort_keys=True) == json.dumps(expected, sort_keys=True)
    base = original.template_scenario if balance else original.scenario
    source = selected(base, values)
    finite_family(source, values)
    return source, values, original


def reserve(*, opposite=False):
    base = enemy_first() if opposite else authored_reserve()
    return replace(base, activation_order=('E1', 'E2', 'E3', 'wizard', 'ally'), max_rounds=2)


def family(base):
    return MagicCandidateGenerationRequest(base,
        (MagicCompositionGroup('opponents', ('E1', 'E2', 'E3'), 1, 2),),
        base.facts, base.scene_frames, 'finite58', 2, 42,
        (MagicBalanceStage(1, 1),), 2, WINDOW)


def assert_projection(template, projected, retained, values):
    finite_family(projected, values)
    assert projected.initial.roster.participants == tuple(p for p in template.initial.roster.participants
        if p.state.actor_id in retained)
    assert projected.initial.spatial_state.placements == tuple(p for p in template.initial.spatial_state.placements
        if p.entity_id in retained)
    assert projected.initial.wizard == template.initial.wizard
    assert projected.facts == template.facts and projected.spell == template.spell
    assert projected.max_rounds == template.max_rounds and projected.perspective_side is template.perspective_side
    assert projected.activation_order == tuple(a for a in template.activation_order if a in retained)
    assert projected.objective.target_actor_ids == tuple(a for a in template.objective.target_actor_ids if a in retained)
    assert projected.initial.round_state.round_number == template.initial.round_state.round_number
    assert len(projected.scene_frames) == len(template.scene_frames)
    for original, frame in zip(template.scene_frames, projected.scene_frames, strict=True):
        assert frame.key.placements == tuple(p for p in original.key.placements if p.entity_id in retained)
        assert frame.key.live_actor_ids == tuple(a for a in original.key.live_actor_ids if a in retained)
        assert frame.pair_ranges == tuple(p for p in original.pair_ranges
            if p.first_actor_id in retained and p.second_actor_id in retained)
        assert frame.zone_ranges == original.zone_ranges
        assert frame.attack_departures == tuple(p for p in original.attack_departures if p.actor_id in retained)
        assert tuple(p.actor_id for p in frame.give_ground_plans) == tuple(p.actor_id for p in original.give_ground_plans if p.actor_id in retained)
        for plan in frame.give_ground_plans:
            prior = next(p for p in original.give_ground_plans if p.actor_id == plan.actor_id)
            expected_route = None if prior.route is None else replace(prior.route,
                path_entity_ids=tuple(a for a in prior.route.path_entity_ids if a in retained))
            assert plan == replace(prior, route=expected_route)
        assert frame.broken_plans == tuple(p for p in original.broken_plans if p.actor_id in retained)


def actual_subsets():
    sources = []
    for opposite in (False, True):
        template = selected(reserve(opposite=opposite), (None, None, None, POLICY))
        before = deepcopy(template)
        for count in (1, 2):
            retained = {'wizard', 'ally', *('E1', 'E2')[:count]}
            source = project(template, retained, f'finite58:{opposite}:{count}', template.facts, template.scene_frames)
            assert_projection(template, source, retained, policies(template))
            sources.append(source)
        assert template == before
    return tuple(sources)


def stream_for(source, *, pending=False):
    prefix = (10,) * 9 if source.perspective_side is CombatSide.PLAYERS_AND_ALLIES else ()
    count = len(source.initial.roster.participants)
    if pending:
        assert count == 4
        return (*prefix, *NEW_FOUR_STREAM)
    core = (*FIRST_TEN, 1, 9, 10, 9) if count == 3 else (*FIRST_TEN, 10, 10, 10, 1, 6, 10, 9)
    length = 32 if count == 3 else 44
    return (*prefix, *core, *((10,) * (length - len(prefix) - len(core))))


def consuming_results(result):
    return tuple(step.result for step in result.steps if (
        isinstance(step.result, NpcRosterCastingResult) and step.result.casting.crushed_rib is not None
        or isinstance(step.result, NpcRosterChampionAttackResult) and step.result.attack.crushed_rib is not None))


class UnreadableTuple(tuple):
    def __iter__(self):
        raise AssertionError('refused native permission reached family collection projection')


def main():
    global_rng = getstate()
    children = {child.pid for child in active_children()}
    # Genuine None controls precede every selected scenario. Public result
    # encoders provide genuine v4 request documents; no opted source is lowered.
    base = reserve()
    base_request = NpcMagicSimulationRequest(base, 42, 1)
    base_command = MagicSimulationCommand('finite58:simulation', base_request, SEQUENTIAL, definitions(base), '6')
    baseline_dice = []
    def baseline_factory(seed):
        dice = ScriptedDice((10,) * 54)
        baseline_dice.append(dice)
        return dice
    base_mass = run_npc_magic_simulation(base_request, rng_factory=baseline_factory)
    assert len(baseline_dice) == 1 and baseline_dice[0].calls == len(baseline_dice[0].values) == 54
    base_summary = summarize_npc_magic_simulation(base_mass)
    genuine_family = family(base)
    balance_command = MagicBalanceCommand('finite58:balance', genuine_family, SEQUENTIAL, definitions(base), '6')
    balance_result = execute_magic_balance(balance_command)
    baseline_sim = json.loads(simulation_wire.encode_magic_simulation_result(base_command, base_summary))['request']
    baseline_balance = json.loads(balance_wire.encode_magic_balance_result(balance_command, balance_result))['request']
    baseline_snapshot = deepcopy((base, base_command, genuine_family, balance_command, balance_result))
    miscast = authored_input(stationary=False, miscast=True).miscast_continuation
    combinations = tuple(product((None, miscast), (None, Stationary.LEG_SPASM_STAND_AND_CONTINUE),
        (None, Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES), (None, POLICY)))
    valid = tuple(values for values in combinations if values[2] is None or values[1] is not None)
    invalid = tuple(values for values in combinations if values not in valid)
    assert len(valid) == 12 and len(invalid) == 4
    for values in invalid:
        rejected(lambda: finite_policies(values), AssertionError)
    for is_balance, baseline, original, parser, error_type in (
        (False, baseline_sim, base_request, simulation_wire.parse_magic_simulation_request, MagicSimulationInputError),
        (True, baseline_balance, genuine_family, balance_wire.parse_magic_balance_request, MagicBalanceInputError),
    ):
        for values in valid:
            document = proposed_document(baseline, values, balance=is_balance)
            decoded = json.loads(json.dumps(document))  # stdlib specification only.
            restored, assertions, parameters = finite_inverse(decoded, baseline, original, miscast, balance=is_balance)
            assert restored == selected(base, values) and assertions == values and parameters is original
            if is_balance:
                command = parser(json.dumps(document))
                assert command.schema_version == '6'
                assert command.generation_request.crushed_rib_continuation is values[3]
                assert command.generation_request.template_scenario.crushed_rib_continuation is values[3]
            else:
                command = parser(json.dumps(document))
                assert command.schema_version == '6'
                assert policies(command.request.scenario) == values, (policies(command.request.scenario), values)
                assert simulation_wire.scenario_document(command.request.scenario, command.definition_order,
                    schema_version='6') == document['scenario']
        chosen = proposed_document(baseline, (None, None, None, POLICY), balance=is_balance)
        node_path = ('reserve', 'scenario') if is_balance else ('scenario',)
        def alter(document, field, value):
            node = document
            for part in node_path:
                node = node[part]
            node[field] = value
        for mutate in (
            lambda d: alter(d, 'scenario_id', 'foreign'),
            lambda d: alter(d, FIELDS[-1], True),
            lambda d: alter(d, FIELDS[-1], 'foreign'),
            lambda d: d['generation'].__setitem__(FIELDS[-1], None) if is_balance else d['scenario']['facts'].__setitem__('no_external_condition_sources', 1),
        ):
            foreign = deepcopy(chosen)
            mutate(foreign)
            rejected(lambda: finite_inverse(foreign, baseline, original, miscast, balance=is_balance), AssertionError)
        missing = deepcopy(chosen)
        node = missing['reserve']['scenario'] if is_balance else missing['scenario']
        del node[FIELDS[-1]]
        rejected(lambda: finite_inverse(missing, baseline, original, miscast, balance=is_balance), KeyError)
        if is_balance:
            for reserve_value, family_value in ((None, POLICY.value), (POLICY.value, None)):
                mismatch = deepcopy(chosen)
                mismatch['reserve']['scenario'][FIELDS[-1]] = reserve_value
                mismatch['generation'][FIELDS[-1]] = family_value
                rejected(lambda: finite_inverse(mismatch, baseline, original, miscast, balance=True), AssertionError)
    print('FINITE JSON5 SPEC: 24 full-fixture stdlib round-trips; 12 valid/4 invalid policy combinations; 12 Simulation5 and 12 Balance5 production parses')

    projected_count = 0
    for opposite in (False, True):
        fresh = reserve(opposite=opposite)
        for values in valid:
            template = selected(fresh, values)
            before = deepcopy(template)
            for count in (1, 2):
                retained = {'wizard', 'ally', *('E1', 'E2')[:count]}
                projected = project(template, retained, f'oracle58:{opposite}:{count}', template.facts, template.scene_frames)
                assert_projection(template, projected, retained, values)
                request = NpcMagicSimulationRequest(projected, 42, 2)
                renamed = replace(request, scenario=replace(projected, id='another-local-id'))
                assert tuple(request.seed_for(i) for i in range(2)) == tuple(renamed.seed_for(i) for i in range(2))
                projected_count += 1
            assert template == before
    assert projected_count == 48
    opposite_wizard = replace(authored_reserve(), perspective_side=CombatSide.OPPOSITION,
        objective=NpcDefeatObjective(('wizard', 'ally')))
    opposite_wizard = selected(opposite_wizard, (None, None, None, POLICY))
    all_ids = {p.state.actor_id for p in opposite_wizard.initial.roster.participants}
    full = project(opposite_wizard, all_ids, 'finite58:opposite-wizard', opposite_wizard.facts, opposite_wizard.scene_frames)
    assert_projection(opposite_wizard, full, all_ids, policies(opposite_wizard))
    assert full.initial.roster.participant('wizard').state.side is not full.perspective_side
    for values in ((None, None, None, None), (None, None, None, POLICY.value)):
        rejected(lambda: finite_family(opposite_wizard, values), (AssertionError, TypeError))
    raw = deepcopy(opposite_wizard)
    object.__setattr__(raw, FIELDS[-1], POLICY.value)
    assert raw == opposite_wizard
    rejected(lambda: finite_family(raw, policies(opposite_wizard)), AssertionError)
    sources = actual_subsets()
    sources_before = deepcopy(sources)
    print('MANUAL SUBSETS: 48 complete 3/4-actor projections, both CombatSide perspectives/all12 policies; separate full-five Wizard-opposite control; full source/facts/seeds retained; no generation58')
    direct_draws = 0
    for index, source in enumerate(sources):
        values = stream_for(source)
        result = direct(source, values)
        direct_draws += len(values)
        assert result.outcome is Outcome.ROUND_LIMIT_REACHED
        assert len(consuming_results(result)) == 1
        consumed = consuming_results(result)[0]
        if index % 2 == 0:
            assert isinstance(consumed, NpcRosterCastingResult)
            assert consumed.casting.crushed_rib.casting.test.trace.quality is TestQuality.GRIM
        else:
            assert isinstance(consumed, NpcRosterChampionAttackResult)
            assert consumed.attack.crushed_rib.test.trace.quality is TestQuality.GRIM
            assert any(isinstance(s.result, NpcRosterCastingResult)
                and s.result.casting.execution.casting.test.trace.quality is TestQuality.NORMAL for s in result.steps)
        consumed_index = next(i for i, step in enumerate(result.steps) if step.result is consumed)
        assert any(isinstance(s.result, NpcRosterChampionAttackResult)
            and s.result.attack.execution.resolution.attack.defender_test.trace.quality is TestQuality.NORMAL
            and s.result.attack.crushed_rib is None for s in result.steps[consumed_index + 1:])
    assert direct_draws == 152
    for source in (sources[1], sources[3]):
        values = stream_for(source, pending=True)
        result = direct(source, values)
        direct_draws += len(values)
        assert result.unsupported.reason is Reason.WOUND_EFFECT
        assert len(consuming_results(result)) == 1
        assert len(result.current.champion_attack.daily_wounds.receipts) == 2
        assert len(result.current.champion_attack.consumed_wound_roll_ids) == 2
    assert direct_draws == 193
    print('ACTUAL NATIVE57: four manual subsets use32/44d10 each; first10 -> actual Grim Casting/Protection once -> later normal Protection; new4 stops25/16d10 after both receipts persist')

    native_request = NpcMagicSimulationRequest(sources[3], 42, 2)
    native_request_before = deepcopy(native_request)
    seeds = tuple(native_request.seed_for(i) for i in range(2))
    streams = (stream_for(sources[3]), stream_for(sources[3], pending=True))
    sequential = run_npc_magic_simulation(native_request, rng_factory=ScriptedFactory(seeds, streams))
    spawned = run_npc_magic_simulation_parallel(native_request, workers=1, batch_size=1,
        rng_factory=ScriptedFactory(seeds, streams, os.getpid()))
    assert sequential == spawned
    native_summary = summarize_npc_magic_simulation(spawned)
    assert native_summary == summarize_npc_magic_simulation(sequential)
    assert tuple(record.seed for record in spawned.trials) == seeds
    assert all(record.source_scenario is native_request.scenario for record in spawned.trials)
    assert native_summary.trials == 2 and native_summary.outcome_counts.round_limit_reached == 1
    assert native_summary.outcome_counts.unsupported_path == 1
    print('ACTUAL SEQ/SPAWN: 60d10 each; exact compact records/summary/full source and indexed seeds; one limit +one unsupported remain in denominator2')

    candidates = tuple(MagicBalanceCandidate(source.id, source) for source in sources[2:])
    staged = MagicStagedEvaluationRequest(candidates, 42, (MagicBalanceStage(1, 1), MagicBalanceStage(2, 1)), 4, WINDOW)
    staged_before = deepcopy(staged)
    captured = []
    def execute(source, process=False, **kwargs):
        trial_seeds = tuple(source.seed_for(i) for i in range(source.trials))
        stream = stream_for(source.scenario)
        factory = ScriptedFactory(trial_seeds, (stream,) * source.trials, os.getpid() if process else None)
        result = (run_npc_magic_simulation_parallel(source, rng_factory=factory, **kwargs) if process
                  else run_npc_magic_simulation(source, rng_factory=factory))
        captured.append((result, len(stream) * source.trials))
        return result
    # Only RNG injection is patched; existing explicit-list stage orchestration,
    # actual runner, source validation and real process workers all execute.
    with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=execute), \
            patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda source, **kw: execute(source, True, **kw)):
        stage_seq = evaluate_magic_candidates_staged(staged, SEQUENTIAL)
        stage_spawn = evaluate_magic_candidates_staged(staged, Options(Mode.PROCESS, 1, 1))
    assert stage_seq == stage_spawn and stage_seq.total_trials == staged.planned_trials == 4
    assert len(stage_seq.stage_reports) == 2
    assert captured[0][0].trials == captured[2][0].trials[:1]
    for report in stage_seq.stage_reports:
        for row in report.candidates:
            source = next(c.scenario for c in candidates if c.candidate_id == row.candidate_id)
            assert row.assessment.source_request.scenario is source
            assert row.assessment.summary.source_request.scenario is source
            assert policies(source) == (None, None, None, POLICY)
    stage_draws = sum(count for _, count in captured)
    print(f'ACTUAL EXPLICIT-LIST STAGES: seq/spawn full reports equal; planned=actual4 each, stage1 rerun with shared seed prefix; {stage_draws}d10; candidate inputs are manual, not generated58')

    selected_base = selected(base, (None, None, None, POLICY))
    selected_family = replace(genuine_family, template_scenario=selected_base,
        crushed_rib_continuation=POLICY)
    actual_generated = generation.generate_magic_candidates(selected_family)
    assert actual_generated.source_request is selected_family
    assert len(actual_generated.evaluation_request.candidates) == 2
    assert tuple(len(c.scenario.initial.roster.participants)
        for c in actual_generated.evaluation_request.candidates) == (3, 4)
    assert all(c.scenario.crushed_rib_continuation is POLICY
        for c in actual_generated.evaluation_request.candidates)
    for template, family_value in ((selected_base, None), (base, POLICY)):
        error = rejected(lambda: replace(genuine_family, template_scenario=template,
            crushed_rib_continuation=family_value, groups=UnreadableTuple(genuine_family.groups)))
        assert 'explicit family' in str(error)
    forged = deepcopy(selected_family)
    object.__setattr__(forged.template_scenario, 'activation_order', ())
    rejected(lambda: generation.generate_magic_candidates(forged))
    rejected(lambda: replace(balance_result.generation_result, source_request=forged))
    raw = deepcopy(selected_base)
    object.__setattr__(raw, FIELDS[-1], POLICY.value)
    rejected(lambda: replace(genuine_family, template_scenario=raw), TypeError)
    for index in (0, -1):
        old = actual_generated.evaluation_request
        wrong_candidates = list(old.candidates)
        wrong = wrong_candidates[index]
        wrong_candidates[index] = replace(wrong, scenario=selected(wrong.scenario, (None, None, None, None)))
        detached = replace(old, candidates=tuple(wrong_candidates))
        error = rejected(lambda: replace(actual_generated, evaluation_request=detached))
        assert 'candidate' in str(error).lower()
    print('ACTUAL GENERATION58: matching Crushed Rib family generates ordered 3/4-actor subsets with permission preserved; mismatch and malformed first/last candidates reject before enumeration; original sources unchanged')
    print('CURRENT PRODUCTION WIRE: complete Crushed Rib policy retained in both families; selected source is never stripped')

    assert (base, base_command, genuine_family, balance_command, balance_result) == baseline_snapshot
    assert sources == sources_before and native_request == native_request_before and staged == staged_before
    assert getstate() == global_rng and {child.pid for child in active_children()} == children
    print(f'{54 + direct_draws + 120 + stage_draws} scripted d10 plus genuine seeded None balance; full inputs/global RNG unchanged; generation58/native57/Simulation6 parser/encoder/CLI/Balance6 parser/seq/spawn/stages are actual')


if __name__ == '__main__':
    main()
