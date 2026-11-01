"""ADR-0054 actual generated repeated stands and spawned staged evaluations.

Copy with repeated_leg_spasm_runner.py, stationary_wound_runner.py and
magic_scenario.py. All reserve profiles/frames are explicit authored inputs;
no tests, private rulebook files, JSON decoder or inferred routes are used.
PG1.4 Rules116/119/122-123, Wounds190; GM1.1 Champions92. No probability claim.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
import os
from random import getstate
from unittest.mock import patch

from magic_scenario import ScriptedDice
from repeated_leg_spasm_runner import authored_repeated, HIT
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationStatus
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.condition_models import Condition
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import NpcMagicRepeatedLegSpasmPolicy as Repeated
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


POLICY = Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES


def authored_family():
    """Wizard4 plus a second allied archer; both real 3/4-actor subsets vary."""
    base = authored_repeated(miscast=True)
    ally = base.initial.roster.participant('ally')
    roster = NpcRoster((*base.initial.roster.participants,
        replace(ally, state=replace(ally.state, actor_id='ally2'))))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = replace(base.initial.spatial_state, placements=(*base.initial.spatial_state.placements,
        replace(base.initial.spatial_state.placement_for('ally'), entity_id='ally2')))
    initial = replace(base.initial, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=NpcChampionAttackState(roster, combat, base.initial.champion_attack.daily_wounds))
    ally_policy = base.policy_for('ally')
    actors = tuple(replace(p, target_actor_ids=(*p.target_actor_ids, 'ally2'),
        defeat_decisions=(*p.defeat_decisions, replace(p.defeat_decisions[0], target_id='ally2')))
        if p.actor_id == 'enemy' else p for p in base.actors)
    actors = (*actors, replace(ally_policy, actor_id='ally2', defeat_decisions=tuple(
        replace(d, attacker_id='ally2') for d in ally_policy.defeat_decisions)))
    frames = tuple(replace(frame, key=replace(frame.key,
        placements=(*frame.key.placements, replace(next(p for p in frame.key.placements
            if p.entity_id == 'ally'), entity_id='ally2')),
        live_actor_ids=(*frame.key.live_actor_ids, 'ally2')),
        pair_ranges=(*frame.pair_ranges, *(replace(p, first_actor_id='ally2')
            for p in frame.pair_ranges if p.first_actor_id == 'ally')),
        attack_departures=(*frame.attack_departures, replace(next(d for d in frame.attack_departures
            if d.actor_id == 'ally'), actor_id='ally2'))) for frame in base.scene_frames)
    template = replace(base, initial=initial, actors=actors, scene_frames=frames,
        activation_order=(*base.activation_order, 'ally2'), perspective_side=CombatSide.PLAYERS_AND_ALLIES,
        objective=NpcDefeatObjective(('wizard', 'ally', 'ally2')))
    return MagicCandidateGenerationRequest(template,
        (MagicCompositionGroup('allies', ('ally', 'ally2'), 1, 2),), template.facts, template.scene_frames,
        'generated:repeated', 2, 42, (MagicBalanceStage(2, 1), MagicBalanceStage(4, 1)), 8,
        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)), template.miscast_continuation,
        template.stationary_wound_continuation, template.repeated_leg_spasm_continuation)


def script(actor_count, kind='normal'):
    if kind == 'wound10':
        return (*HIT, 10)
    tail = (10,) * (3 + 6 * (actor_count - 2))
    prefix = (*HIT, 9, *tail, *HIT, 4, 5, *tail)
    if kind == 'six':
        return (*prefix, *HIT, 1, 2, 3, *tail)
    if kind == 'third9':
        return (*prefix, *HIT, 3, 3, 3)
    return (*prefix, *((10,) * (6 + len(tail))))


def child_rng(seed, *, actor_count, seeds, mixed, parent_pid):
    """Importable injected RNG factory; assertions execute in actual workers."""
    assert os.getpid() != parent_pid, 'generated process trial must execute in child'
    return ScriptedDice(script(actor_count, 'wound10' if mixed and seeds.index(seed) == 1 else 'normal'))


def assert_sources(report, generated):
    assert report.source_request is generated.evaluation_request
    originals = {candidate.candidate_id: candidate.scenario for candidate in generated.evaluation_request.candidates}
    for stage in report.stage_reports:
        for row in stage.candidates:
            assessment = row.assessment
            request = assessment.source_request
            assert request.scenario is originals[row.candidate_id]
            assert request.scenario.repeated_leg_spasm_continuation is POLICY
            assert request.scenario.stationary_wound_continuation is generated.source_request.stationary_wound_continuation
            assert request.scenario.miscast_continuation == generated.source_request.miscast_continuation
            assert assessment.summary.source_request is request and assessment.summary.trials == request.trials


def staged_pair(generated, *, mixed):
    sequential_runner = evaluation.run_npc_magic_simulation
    process_runner = evaluation.run_npc_magic_simulation_parallel
    captures, draws = [], []

    def sequential(source):
        seeds = tuple(source.seed_for(i) for i in range(source.trials))
        dice_instances = []
        def rng(seed):
            dice = ScriptedDice(script(len(source.scenario.activation_order),
                'wound10' if mixed and seeds.index(seed) == 1 else 'normal'))
            dice_instances.append(dice)
            return dice
        result = sequential_runner(source, rng_factory=rng)
        assert len(dice_instances) == source.trials
        assert all(dice.calls == len(dice.values) for dice in dice_instances)
        draws.append(sum(dice.calls for dice in dice_instances))
        captures.append(result)
        return result

    def process(source, **kwargs):
        return process_runner(source, rng_factory=partial(child_rng,
            actor_count=len(source.scenario.activation_order),
            seeds=tuple(source.seed_for(i) for i in range(source.trials)), mixed=mixed,
            parent_pid=os.getpid()), **kwargs)

    with (patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential) as seq_calls,
          patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=process) as proc_calls):
        sequential_report = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        process_report = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 1, 2))
    assert sequential_report == process_report
    assert [call.args[0] for call in seq_calls.call_args_list] == [call.args[0] for call in proc_calls.call_args_list]
    assert_sources(sequential_report, generated)
    assert_sources(process_report, generated)
    if mixed:
        assert sequential_report.status is MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES
        assert (sequential_report.total_trials, sequential_report.planned_trials) == (4, 8)
        for row in sequential_report.stage_reports[0].candidates:
            assert row.assessment.summary.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
            assert row.assessment.summary.trials == 2 and row.assessment.unsupported_path_rate == Fraction(1, 2)
    else:
        assert sequential_report.status is MagicStagedEvaluationStatus.COMPLETED
        assert (sequential_report.total_trials, sequential_report.planned_trials) == (8, 8)
        assert [run.source_request.trials for run in captures] == [2, 2, 4]
        first = next(run for run in captures[:2] if run.source_request.scenario is captures[-1].source_request.scenario)
        assert tuple(t.seed for t in first.trials) == tuple(t.seed for t in captures[-1].trials[:2])
    for run in captures:
        assert all(trial.source_scenario is run.source_request.scenario for trial in run.trials)
        assert tuple(t.seed for t in run.trials) == tuple(run.source_request.seed_for(i) for i in range(run.source_request.trials))
    # Identical deterministic requests/scripts and exact reports in both modes.
    return sum(draws) * 2


def main():
    rng_before = getstate()
    source = authored_family()
    before = deepcopy(source)
    generated = generate_magic_candidates(source)
    generated_before = deepcopy(generated)
    assert generated.source_request is source and (source.candidate_count, source.planned_trials) == (2, 8)
    assert tuple(c.candidate_id for c in generated.evaluation_request.candidates) == (
        'generated:repeated:counts:1', 'generated:repeated:counts:2')
    direct_draws = 0
    for candidate in generated.evaluation_request.candidates:
        actor_count = len(candidate.scenario.activation_order)
        assert actor_count in (3, 4) and candidate.scenario.repeated_leg_spasm_continuation is POLICY
        counts = []
        for kind in ('normal', 'six', 'third9'):
            dice = ScriptedDice(script(actor_count, kind))
            result = run_npc_magic_scenario(candidate.scenario, dice)
            assert dice.calls == len(dice.values)
            direct_draws += dice.calls
            counts.append(dice.calls)
            assert result.source is candidate.scenario
            first = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
            repeated = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult))
            assert len(first) == len(repeated) == 1
            assert repeated[0].source.previous_stand == first[0]
            assert any(s.result == repeated[0].source.wound_attack for s in result.steps)
            injury = result.current.roster.participant('wizard').state.injury
            if kind == 'third9':
                assert result.unsupported.reason is Reason.ACTOR_INJURY
                assert tuple(w.table_total for w in injury.wounds) == (9, 9, 9)
            else:
                assert result.outcome is Outcome.ROUND_LIMIT_REACHED
                assert (result.executed_actions, result.completed_rounds) == (3 * actor_count, 3)
                assert tuple(w.table_total for w in injury.wounds) == ((9, 9, 6) if kind == 'six' else (9, 9))
                assert not injury.conditions.has(Condition.PRONE) and not injury.conditions.has(Condition.DRAINED)
                assert len(injury.active_wound_effects) == 2 and not result.current.wound_expiries
                assert len(result.current.champion_attack.daily_wounds.receipts) == (3 if kind == 'six' else 2)
                assert sum(len(end.expired_sources) for end in result.current.wound_turn_end_receipts) == int(kind == 'six')
        assert counts == ([48, 51, 42] if actor_count == 3 else [66, 69, 54])
        print(f'GENERATED {actor_count} actors: repeat/post6/third9 = {counts}; exact prior stand/attack witnesses; one repeat only')
    assert direct_draws == 330
    full_draws = staged_pair(generated, mixed=False)
    mixed_draws = staged_pair(generated, mixed=True)
    print(f'STAGED sequential/spawn: full-source parity; full rerun budget8/8 and seed prefix; {full_draws} scripted d10')
    print(f'MIXED sequential/spawn: round-limit + Wound10 unsupported; denominator2 per candidate; actual/planned4/8; {mixed_draws} scripted d10')
    assert source == before and generated == generated_before and getstate() == rng_before
    print(f'{direct_draws + full_draws + mixed_draws} scripted d10 total; production generation; immutable sources/global RNG; real child PID checked')


if __name__ == '__main__':
    main()
