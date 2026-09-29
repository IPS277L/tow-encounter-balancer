"""ADR-0029 public sequential simulation/summary example, PYTHONPATH=src.

Uses the public constructors in the neighbouring scenario example. No tests,
private builders, contract-probe aggregation or custom simulation implementation.
"""
from copy import deepcopy
from dataclasses import fields
from fractions import Fraction
from random import getstate

from mixed_scenario import build_scenario
from towr.simulation.npc_mixed_models import SEED_SCHEME, NpcMixedSimulationRequest
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation


MASTER_SEED = 42
TRIALS = 8


def run_example(*, two_archers: bool) -> None:
    scenario = build_scenario(two_archers=two_archers)
    request = NpcMixedSimulationRequest(scenario, master_seed=MASTER_SEED, trials=TRIALS)
    before, global_rng = deepcopy(request), getstate()
    result = run_npc_mixed_simulation(request)
    summary = summarize_npc_mixed_simulation(result)
    repeated = run_npc_mixed_simulation(request)
    assert result == repeated and summary == summarize_npc_mixed_simulation(repeated)
    assert request == before and getstate() == global_rng
    assert result.source_request is request and summary.source_request is request
    assert tuple(trial.trial_index for trial in result.trials) == tuple(range(TRIALS))
    assert all(trial.seed == request.seed_for(trial.trial_index) for trial in result.trials)
    counts = summary.outcome_counts
    assert sum(getattr(counts, field.name) for field in fields(counts)) == TRIALS
    assert summary.total_attack_count == sum(trial.executed_attack_count for trial in result.trials)
    assert summary.total_visited_round_count == sum(trial.visited_round_count for trial in result.trials)
    assert {field.name for field in fields(summary)} == {
        'source_request', 'outcome_counts', 'total_attack_count', 'total_visited_round_count',
    }
    case = '2x2_two_archers' if two_archers else '3x2_one_archer'
    print(f"case: {case}; master_seed={MASTER_SEED}; trials={TRIALS}; round_budget={scenario.initial.max_rounds}")
    print("  actor_order=" + ','.join(scenario.initial.current.actor_order))
    print("  placements=" + ','.join(f"{p.entity_id}@{p.zone_id}" for p in scenario.initial.spatial_state.placements))
    print("  pairs=" + ','.join(f"{p.first_actor_id}/{p.second_actor_id}:{p.target_range.value}" for p in scenario.pair_ranges))
    print(f"  perspective={scenario.perspective_side.value}; objective={','.join(scenario.objective.target_actor_ids)}")
    for policy in scenario.actor_policies:
        print(f"  policy {policy.actor_id}: targets={','.join(policy.target_actor_ids)}; "
              f"outnumbering_approved={policy.outnumbering_bonus_approved}; can_leave_zone={policy.can_leave_zone}")
    print("  counts=" + ','.join(f"{field.name}:{getattr(counts, field.name)}" for field in fields(counts)))
    print(f"  total_attacks={summary.total_attack_count}; total_visited_rounds={summary.total_visited_round_count}")
    print(f"  mean_attacks={summary.mean_attack_count}; mean_visited_rounds={summary.mean_visited_round_count}")
    print(f"  observed_goal_share={Fraction(counts.objective_achieved, TRIALS)}; denominator=ALL {TRIALS} trials")
    for trial in result.trials:
        print(f"  trial {trial.trial_index}: seed={trial.seed:064x}; outcome={trial.outcome.value}; "
              f"attacks={trial.executed_attack_count}; visited_rounds={trial.visited_round_count}")
    print("  Full result and summary replay equal; input/global RNG unchanged; summary has no trial records")


def main() -> None:
    print(f"ADR-0029 sequential mixed simulation; seed_scheme={SEED_SCHEME}")
    print("sources: PG1.4 Rules pp112,118-119; GM1.1 Allies and Antagonists pp91,93,97")
    print("profiles: Footpad Dagger Close 3d/3 Dam2 RES3 Athletics 3d/3; Brigand Warbow Medium-Long 3d/3 Dam3 RES4 Athletics 3d/2")
    facts = build_scenario().facts
    print("facts: " + '; '.join(f"{field.name}={getattr(facts, field.name)}" for field in fields(facts)))
    print("decisions: every defeat knocked_out/GM-approved; repeated_stagger=suffer_wound; fixed Attack-only policy")
    run_example(two_archers=False)
    run_example(two_archers=True)
    print("32 trials executed including replays; counts above describe 8 trials per input, not pooled compositions")
    print("Visited rounds include interrupted last rounds; resume and terminal suffix add no extra round/Attack")
    print("Unsupported remains separate and inside the denominator; no conditional win rate or balance assessment")
    print("This small seeded sample demonstrates the API; its outcome counts are not a statistical test oracle")


if __name__ == '__main__':
    main()
