"""Run from the repository root with PYTHONPATH=src."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.application.dynamic_encounter import DynamicEncounterRequest, NpcSearchSpace, search_dynamic_encounter
from towr.domain.generated_npc_models import GeneratedAbility
from towr.domain.minion_defeat_models import NpcDefeatDisposition


def main():
    parser = argparse.ArgumentParser(description='Generate new NPC configurations and evaluate complete battles.')
    parser.add_argument('--party-from', default='docs/examples/m10/pc-melee-simulation.request.json',
        help='Reuse only PCs/facts/day from an existing scenario; its enemies are discarded.')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--candidates', type=int, default=12)
    parser.add_argument('--trials', type=int, default=16)
    parser.add_argument('--finalist-trials', type=int, default=64)
    parser.add_argument('--top', type=int, default=3)
    parser.add_argument('--min-npcs', type=int, default=2)
    parser.add_argument('--max-npcs', type=int, default=2)
    parser.add_argument('--target-win-rate', type=float, default=.6)
    parser.add_argument('--target-rounds', type=float, default=3.)
    parser.add_argument('--max-rounds', type=int, default=8)
    parser.add_argument('--allow-authored-drained', action='store_true',
        help='Explicitly permit the authored on-hit Drained component; not a book talent grant.')
    args = parser.parse_args()
    party_source = parse_pc_melee_simulation_request(Path(args.party_from).read_bytes()).request.scenario
    space = NpcSearchSpace(abilities=((), (GeneratedAbility.DRAINED_ON_HIT,)) if args.allow_authored_drained else ((),))
    request = DynamicEncounterRequest(party_source.party, party_source.facts, party_source.day_id,
        space, args.min_npcs, args.max_npcs, args.target_win_rate, args.target_rounds, args.seed,
        args.candidates, args.trials, args.finalist_trials, args.top,
        args.candidates*args.trials + args.top*args.finalist_trials, args.max_rounds,
        NpcDefeatDisposition.KILLED)
    result = search_dynamic_encounter(request)

    def document(candidate):
        source = candidate.summary.source_request
        return dict(npcs=[asdict(n) for n in candidate.composition],
            win_rate=candidate.win_rate, win_interval_95=candidate.win_interval_95,
            mean_started_rounds=candidate.mean_started_rounds,
            rounds_interval_95=candidate.rounds_interval_95,
            outcomes=asdict(candidate.summary.outcome_counts), trials=candidate.summary.trials,
            replay=dict(schema_version='1', kind='pc_melee_simulation',
                request_id=source.scenario.id, ruleset='towr-pg1.4-gmg1.1',
                scenario=scenario_document(source.scenario),
                simulation=dict(master_seed=str(source.master_seed), trials=source.trials),
                execution=dict(mode='sequential')))

    print(json.dumps(dict(search_space=asdict(space), master_seed=request.master_seed,
        target_win_rate=request.target_win_rate, target_rounds=request.target_rounds,
        minimum_npcs=request.minimum_npcs, maximum_npcs=request.maximum_npcs,
        max_candidates=request.max_candidates, exploration_trials=request.exploration_trials,
        finalist_trials=request.finalist_trials, top_k=request.top_k, max_total_trials=request.max_total_trials,
        total_trials=result.total_trials, proposal_attempts=result.proposal_attempts,
        proposal_limit_reached=result.proposal_limit_reached,
        explored=[document(c) for c in result.explored],
        validations=[document(c) for c in result.validations],
        selected=[c.summary.source_request.scenario.id for c in result.finalists]), indent=2))


if __name__ == '__main__':
    main()
