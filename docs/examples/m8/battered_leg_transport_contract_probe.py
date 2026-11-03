"""ADR-0062 actual generation/JSON6 checked against finite fixture oracles.

Copy with magic_scenario.py, generation_contract_probe.py and
battered_leg_native.py. Manual subsets and JSON6 inverse below are bounded
fixture oracles, separate from production generation62 and codecs6 below.
PG1.4 pp68-70,121,123,190; GM1.1 p92. Numeric profiles/facts are authored.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
import json
from random import getstate

from battered_leg_native import ScriptedFactory
from generation_contract_probe import authored_reserve, project
from magic_scenario import ScriptedDice
from towr.adapters import magic_balance_json as balance_wire, magic_simulation_json as simulation_wire
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.application import magic_candidate_generation as generation
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy as Battered, NpcMagicCrushedRibPolicy as Crushed,
    NpcMagicMiscastContinuationPolicy as Miscast, NpcMagicPronePolicy,
    NpcMagicRepeatedLegSpasmPolicy as Repeated, NpcMagicStationaryWoundPolicy as Stationary,
    validate_npc_magic_scenario_admission,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


FIELDS = ('miscast_continuation', 'stationary_wound_continuation',
          'repeated_leg_spasm_continuation', 'crushed_rib_continuation', 'battered_leg_continuation')
MISCAST = Miscast(NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
    NpcRosterMiscastFacts(True, True, True, True, True), NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)
VALUES = (MISCAST, Stationary.LEG_SPASM_STAND_AND_CONTINUE,
          Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES, Crushed.NEXT_TEST_WITH_JOURNAL_WITNESSES,
          Battered(InlineProfile(2, 5)))
SEQUENTIAL = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)
FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)


def refused(operation, error_type=ValueError, fragment=None):
    try:
        operation()
    except error_type as error:
        if fragment is not None:
            assert fragment in str(error), str(error)
        return
    raise AssertionError('expected refusal')


def reserve(opposite=False):
    source = replace(authored_reserve(), activation_order=('E1', 'wizard', 'ally', 'E2', 'E3'), max_rounds=1)
    if not opposite:
        return source
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, side=(CombatSide.OPPOSITION
        if p.state.side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES)))
        for p in source.initial.roster.participants))
    combat = CombatRoundState(1, roster.turn_participants)
    def positions(values):
        return tuple(replace(p, side_id=roster.participant(p.entity_id).state.side.value) for p in values)
    initial = replace(source.initial, roster=roster, round_state=combat,
        spatial_state=replace(source.initial.spatial_state, placements=positions(source.initial.spatial_state.placements)),
        champion_attack=replace(source.initial.champion_attack, roster=roster, round_state=combat))
    return replace(source, initial=initial, perspective_side=CombatSide.OPPOSITION,
        scene_frames=tuple(replace(frame, key=replace(frame.key, placements=positions(frame.key.placements)))
                           for frame in source.scene_frames))


def family(source, groups=None, *, policies=None):
    # This is an explicit assertion, never implicit inheritance from source.
    values = (None,) * 5 if policies is None else policies
    return MagicCandidateGenerationRequest(source,
        (MagicCompositionGroup('enemies', ('E1', 'E2', 'E3'), 1, 2),) if groups is None else groups,
        source.facts, source.scene_frames, 'finite62', 2, 42, (MagicBalanceStage(1, 1),), 2,
        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)),
        **dict(zip(FIELDS, values, strict=True)))


def definitions(source):
    return tuple(dict.fromkeys(p.definition.id for p in source.initial.roster.participants))


def select(source, values):
    return replace(source, **dict(zip(FIELDS, values, strict=True)))


def finite_family(source, values):
    """Manual assertion on these admitted fixtures, not future preflight62."""
    validate_npc_magic_scenario_admission(source)
    selected = select(source, values)  # Read original typed profiles before equality.
    assert selected == source, 'manual family must match complete policy/profile'


def policy_document(values):
    miscast, stationary, repeated, crushed, battered = values
    return (None if miscast is None else {'choice': miscast.choice.value,
        'facts': asdict(miscast.facts), 'prone_policy': miscast.prone_policy.value},
        *(None if value is None else value.value for value in (stationary, repeated, crushed)),
        None if battered is None else {'endurance_profile': {
            'dice': battered.endurance_profile.dice, 'threshold': battered.endurance_profile.threshold},
            'prone_policy': None if battered.prone_policy is None else battered.prone_policy.value})


def proposed_document(baseline, values, balance):
    """Explicit proposal, starting with an independently authored genuine None6."""
    result = deepcopy(baseline)
    result['schema_version'] = '6'
    nodes = (result['reserve']['scenario'], result['generation']) if balance else (result['scenario'],)
    for node in nodes:
        node.update(zip(FIELDS, policy_document(values), strict=True))
    return result


def finite_inverse(document, baseline, original, balance):
    """Understand this fixture's full JSON6 proposal, never downgrade a source."""
    def read(node):
        raw = tuple(node[field] for field in FIELDS)  # All five nullable fields required.
        values = []
        for index, value in enumerate(raw[:4]):
            if value is None:
                values.append(None)
            elif index == 0:
                assert type(value) is dict and json.dumps(value, sort_keys=True) == json.dumps(policy_document(VALUES)[0], sort_keys=True)
                values.append(MISCAST)
            else:
                assert type(value) is str and value == VALUES[index].value
                values.append(VALUES[index])
        value = raw[4]
        if value is not None:
            assert type(value) is dict and set(value) == {'endurance_profile', 'prone_policy'}
            profile = value['endurance_profile']
            assert type(profile) is dict and set(profile) == {'dice', 'threshold'}
            assert type(profile['dice']) is int and type(profile['threshold']) is int
            prone = value['prone_policy']
            assert prone is None or type(prone) is str and prone == 'self_stand_when_safe'
            value = Battered(InlineProfile(profile['dice'], profile['threshold']),
                None if prone is None else NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)
        return (*values, value)
    values = read(document['reserve']['scenario'] if balance else document['scenario'])
    if balance:
        assert read(document['generation']) == values, 'manual family profile mismatch'
    assert json.dumps(document, sort_keys=True) == json.dumps(proposed_document(baseline, values, balance), sort_keys=True)
    source = select(original, values)
    finite_family(source, values)
    return source, values


def main():
    global_rng = getstate()
    combinations = tuple(tuple(value if enabled else None for value, enabled in zip(VALUES, flags, strict=True))
                         for flags in product((False, True), repeat=5))
    valid = tuple(values for values in combinations if values[2] is None or values[1] is not None)
    invalid = tuple(values for values in combinations if values not in valid)
    assert (len(valid), len(invalid)) == (24, 8)
    manual_subsets = round_trips = actual_candidates = matched_candidates = 0
    for opposite in (False, True):
        original = reserve(opposite)
        before = deepcopy(original)
        order = definitions(original)
        request = family(original)
        commands = (MagicSimulationCommand('finite62:simulation', NpcMagicSimulationRequest(original, 42, 2),
                                          SEQUENTIAL, order, '6'),
                    MagicBalanceCommand('finite62:balance', request, SEQUENTIAL, order, '6'))
        baselines = (simulation_wire._request_document(commands[0]), balance_wire._request_document(commands[1]))
        for command, baseline, parser in zip(commands, baselines,
                (simulation_wire.parse_magic_simulation_request, balance_wire.parse_magic_balance_request), strict=True):
            assert parser(json.dumps(baseline)) == command
        generated = generation.generate_magic_candidates(request)
        for candidate in generated.evaluation_request.candidates:
            retained = {p.state.actor_id for p in candidate.scenario.initial.roster.participants}
            manual = project(original, retained, candidate.scenario.id, original.facts, original.scene_frames)
            assert manual == candidate.scenario and manual.battered_leg_continuation is None
            actual_candidates += 1
        for values in invalid:
            refused(lambda: select(original, values))
        for values in valid:
            selected = select(original, values)
            selected_before = deepcopy(selected)
            finite_family(selected, values)
            actual_family = family(selected, policies=values)
            actual = generation.generate_magic_candidates(actual_family)
            for balance, baseline in zip((False, True), baselines, strict=True):
                proposed = proposed_document(baseline, values, balance)
                restored, restored_values = finite_inverse(json.loads(json.dumps(proposed)), baseline, original, balance)
                assert restored == selected and restored_values == values and proposed['schema_version'] == '6'
                parser = balance_wire.parse_magic_balance_request if balance else simulation_wire.parse_magic_simulation_request
                mapper = balance_wire._request_document if balance else simulation_wire._request_document
                parsed = parser(json.dumps(proposed))
                parsed_source = parsed.generation_request.template_scenario if balance else parsed.request.scenario
                assert parsed.schema_version == '6' and parsed_source == restored
                assert mapper(parsed) == proposed
                if balance:
                    assert tuple(getattr(parsed.generation_request, field) for field in FIELDS) == restored_values
                round_trips += 1
            for size in (1, 2):
                retained = {'wizard', 'ally', *('E1', 'E2')[:size]}
                candidate = actual.evaluation_request.candidates[size - 1]
                projected = project(selected, retained, candidate.scenario.id, selected.facts, selected.scene_frames)
                assert projected == candidate.scenario
                assert tuple(getattr(projected, field) for field in FIELDS) == values
                assert len(projected.initial.roster.participants) == size + 2
                assert projected.objective.target_actor_ids == tuple(
                    actor for actor in selected.objective.target_actor_ids if actor in retained)
                assert projected.initial.roster.participant('wizard').state.side is projected.perspective_side
                validate_npc_magic_scenario_admission(projected)
                manual_subsets += 1
                matched_candidates += 1
            assert selected == selected_before
        assert original == before
    assert (actual_candidates, manual_subsets, round_trips, matched_candidates) == (4, 96, 96, 96)
    print('PRODUCTION62: 24valid/8invalid permissions; 96 full-source JSON6 parses/echoes and 96 actual3/4-actor candidates match independent manual oracles across both sides; 4 genuine None controls retained')

    base = reserve(True)
    chosen_values = (None, None, None, None, VALUES[4])
    selected = select(base, chosen_values)
    opposite_wizard = replace(reserve(), perspective_side=CombatSide.OPPOSITION,
        objective=NpcDefeatObjective(('wizard', 'ally')))
    fixed_support = (MagicCompositionGroup('support', ('ally',), 1, 1),)
    full_family = family(opposite_wizard, fixed_support)
    full_generated = generation.generate_magic_candidates(full_family)
    assert len(full_generated.evaluation_request.candidates) == 1
    all_ids = {p.state.actor_id for p in opposite_wizard.initial.roster.participants}
    full_candidate = full_generated.evaluation_request.candidates[0]
    assert full_candidate.scenario == project(opposite_wizard, all_ids, full_candidate.scenario.id,
        opposite_wizard.facts, opposite_wizard.scene_frames)
    assert len(full_candidate.scenario.initial.roster.participants) == 5
    full_source = select(opposite_wizard, chosen_values)
    full_matching = generation.generate_magic_candidates(family(full_source, fixed_support, policies=chosen_values))
    assert full_matching.evaluation_request.candidates[0].scenario == project(full_source, all_ids,
        full_matching.evaluation_request.candidates[0].scenario.id, full_source.facts, full_source.scene_frames)
    assert full_source.initial.roster.participant('wizard').state.side is not full_source.perspective_side
    full_commands = (MagicSimulationCommand('finite62:opposite:sim',
        NpcMagicSimulationRequest(opposite_wizard, 42, 2), SEQUENTIAL, definitions(opposite_wizard), '6'),
        MagicBalanceCommand('finite62:opposite:balance', full_family, SEQUENTIAL, definitions(opposite_wizard), '6'))
    for balance, command, mapper in ((False, full_commands[0], simulation_wire._request_document),
                                    (True, full_commands[1], balance_wire._request_document)):
        baseline = mapper(command)
        restored, _ = finite_inverse(proposed_document(baseline, chosen_values, balance), baseline, opposite_wizard, balance)
        assert restored == full_source and len(restored.initial.roster.participants) == 5
        parser = balance_wire.parse_magic_balance_request if balance else simulation_wire.parse_magic_simulation_request
        parsed = parser(json.dumps(proposed_document(baseline, chosen_values, balance)))
        assert (parsed.generation_request.template_scenario if balance else parsed.request.scenario) == restored
    print('WIZARD-OPPOSITE CONTROL: all five actors retained; actual None and matching-profile candidates plus 2 production JSON6 parses agree with full-source oracle; fixed Minions retained')
    class Unreadable(list):
        def __iter__(self):
            raise AssertionError('no collection traversal before existing generation refusal')
    refused(lambda: family(selected, Unreadable()), ValueError, 'Battered Leg')
    print('SOURCE GUARDS: missing family assertion refused before collections; current6 retains full authored profile')

    baseline = simulation_wire._request_document(MagicSimulationCommand('finite62:negative',
        NpcMagicSimulationRequest(base, 42, 2), SEQUENTIAL, definitions(base), '6'))
    proposed = proposed_document(baseline, chosen_values, False)
    assert simulation_wire.parse_magic_simulation_request(json.dumps(proposed)).schema_version == '6'
    for profile in ({'dice': True, 'threshold': 5}, {'dice': 2.0, 'threshold': 5},
                    {'dice': 0, 'threshold': 5}, {'dice': 2, 'threshold': 0},
                    {'dice': 2, 'threshold': 11}, {'dice': 2, 'threshold': 5, 'pool_cap': 4}):
        bad = deepcopy(proposed)
        bad['scenario']['battered_leg_continuation'] = {'endurance_profile': profile, 'prone_policy': None}
        refused(lambda: finite_inverse(bad, baseline, base, False), (AssertionError, TypeError, ValueError))
        refused(lambda: simulation_wire.parse_magic_simulation_request(json.dumps(bad)), MagicSimulationInputError)
    wrong = deepcopy(proposed)
    wrong['scenario']['definitions'][0]['source_rule_id'] = 'different:source'
    refused(lambda: finite_inverse(wrong, baseline, base, False), AssertionError)
    balance_baseline = balance_wire._request_document(MagicBalanceCommand('finite62:mismatch', family(base),
        SEQUENTIAL, definitions(base), '6'))
    for name, value in (('threshold', 4), ('dice', 3)):
        mismatched = proposed_document(balance_baseline, chosen_values, True)
        mismatched['generation']['battered_leg_continuation']['endurance_profile'][name] = value
        refused(lambda: finite_inverse(mismatched, balance_baseline, base, True), AssertionError)
        refused(lambda: balance_wire.parse_magic_balance_request(json.dumps(mismatched)), MagicBalanceInputError)
    for balance, baseline in ((False, baseline), (True, balance_baseline)):
        missing = proposed_document(baseline, chosen_values, balance)
        node = missing['generation'] if balance else missing['scenario']
        del node['battered_leg_continuation']
        refused(lambda: finite_inverse(missing, baseline, base, balance), KeyError)
    baseline = simulation_wire._request_document(MagicSimulationCommand('finite62:negative',
        NpcMagicSimulationRequest(base, 42, 2), SEQUENTIAL, definitions(base), '6'))
    refused(lambda: finite_family(selected, (*chosen_values[:4], Battered(InlineProfile(2, 4)))), AssertionError)
    for dice in (1, 11):
        values = (*chosen_values[:4], Battered(InlineProfile(dice, 5)))
        restored, _ = finite_inverse(proposed_document(baseline, values, False), baseline, base, False)
        assert restored.battered_leg_continuation.endurance_profile.dice == dice
    print('PROFILE CONTRACT: production6 rejects raw/bool/float/cap and family dice/threshold mismatches; full-fixture oracle rejects source substitution; authored1d/5 and11d/5 retained')

    draws = 0
    sources = []
    for opposite in (False, True):
        template = select(reserve(opposite), chosen_values)
        for size in (1, 2):
            source = project(template, {'wizard', 'ally', *('E1', 'E2')[:size]},
                f'finite62:native:{opposite}:{size}', template.facts, template.scene_frames)
            for success in (True, False):
                # A side completes its actors before the other side: allied
                # Wizard WAIT + ally miss precede E1 when Wizard is on side1.
                prefix = () if opposite else (10,) * 9
                remaining = 9 + 6 * (size - 1) if opposite else 6 * (size - 1)
                values = (*prefix, *FIRST_FIVE, *((1, 10) if success else (10, 10)),
                    *((10,) * (remaining if success else 0)))
                dice = ScriptedDice(values)
                before = deepcopy(source)
                result = run_npc_magic_scenario(source, dice)
                assert dice.calls == len(values) and source == before, (
                    opposite, size, success, dice.calls, len(values), result.outcome, result.unsupported)
                completed = tuple(s for s in result.steps if isinstance(s.result, NpcRosterBatteredLegResult))
                assert len(completed) == 1 and completed[0].result.endurance.test_result.succeeded is success
                assert completed[0].result.source.endurance_profile == VALUES[4].endurance_profile
                assert result.current.battered_leg_receipt == completed[0].after.battered_leg_receipt
                if success or not opposite and size == 1:
                    assert result.outcome is Outcome.ROUND_LIMIT_REACHED
                else:
                    assert result.unsupported.reason is (Reason.ACTOR_INJURY
                        if opposite and size == 1 else Reason.TARGET_INJURY)
                draws += dice.calls
            sources.append(source)
    one_die = replace(sources[2], battered_leg_continuation=Battered(InlineProfile(1, 5)))
    dice = ScriptedDice((*FIRST_FIVE, 5, *((10,) * 9)))
    actual = run_npc_magic_scenario(one_die, dice)
    assert dice.calls == 17 and actual.outcome is Outcome.ROUND_LIMIT_REACHED
    completion = next(step.result for step in actual.steps if isinstance(step.result, NpcRosterBatteredLegResult))
    assert completion.endurance.test_result.succeeded and completion.endurance.test_result.trace.threshold == 5
    draws += dice.calls
    full_dice = ScriptedDice((*((10,) * 9), *FIRST_FIVE, 1, 10, *((10,) * 12)))
    full_actual = run_npc_magic_scenario(full_source, full_dice)
    assert full_dice.calls == 30 and full_actual.outcome is Outcome.ROUND_LIMIT_REACHED
    assert len(full_actual.current.roster.participants) == 5
    assert full_actual.current.battered_leg_receipt.endurance.request.endurance_test.profile == VALUES[4].endurance_profile
    draws += full_dice.calls
    print('ACTUAL NATIVE61: 8 success/failure paths on manual3/4-actor subsets, both sides, exact profile/receipt; normal1d/5 succeeds on5 without a prototype-only threshold rule')

    simulation = NpcMagicSimulationRequest(sources[2], 42, 2)
    simulation_before = deepcopy(simulation)
    streams = ((*FIRST_FIVE, 1, 10, *((10,) * 9)), (*FIRST_FIVE, 10, 10))
    factory = ScriptedFactory(tuple(simulation.seed_for(i) for i in range(2)), streams)
    sequential = run_npc_magic_simulation(simulation, rng_factory=factory)
    spawned = run_npc_magic_simulation_parallel(simulation, workers=2, batch_size=1, rng_factory=factory)
    assert simulation == simulation_before
    assert sequential == spawned and sequential.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
    assert summarize_npc_magic_simulation(sequential) == summarize_npc_magic_simulation(spawned)
    assert summarize_npc_magic_simulation(spawned).trials == 2
    assert all(t.source_scenario is simulation.scenario for t in spawned.trials)
    command6 = MagicSimulationCommand('finite62:actual:simulation', simulation, SEQUENTIAL,
        definitions(simulation.scenario), '6')
    encoded6 = json.loads(simulation_wire.encode_magic_simulation_result(command6,
        summarize_npc_magic_simulation(sequential)))
    assert simulation_wire.parse_magic_simulation_request(json.dumps(encoded6['request'])) == command6
    balance6 = MagicBalanceCommand('finite62:actual:balance', family(selected, policies=chosen_values),
        SEQUENTIAL, definitions(selected), '6')
    balance_before = deepcopy(balance6)
    balance_result = execute_magic_balance(balance6)
    assert balance6 == balance_before
    balance_encoded = json.loads(balance_wire.encode_magic_balance_result(balance6, balance_result))
    assert balance_wire.parse_magic_balance_request(json.dumps(balance_encoded['request'])) == balance6
    assert balance_encoded['total_trials'] == 2 and balance_encoded['schema_version'] == '6'
    draws += 2 * sum(map(len, streams))
    assert getstate() == global_rng and draws == 239
    print('PRODUCTION RESULTS6: full simulation request/summary echo and seeded balance generation/stage/report echo reconstruct exact commands; balance2trials retained separately from scripted draw count')
    print('239 scripted d10; actual generation62/JSON6 plus native61 sequential/real spawn preserve source/seeds/denominator2 and global RNG; independent finite oracles remain separate')


if __name__ == '__main__':
    main()
