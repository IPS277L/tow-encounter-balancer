"""Profile one observed slow candidate from a dynamic benchmark artifact."""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
from random import Random
from time import perf_counter

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    artifact=json.loads(args.input.read_text('utf-8'))
    row=max(artifact['measurements'],key=lambda r:r['search_seconds']/r['result']['total_trials'])
    slowest=max(row['batches'],key=lambda b:b['seconds']/b['trials'])
    candidate=next(c for c in row['result']['explored']+row['result']['validations']
        if c['replay']['scenario']['id']==slowest['scenario_id'])
    source=parse_pc_melee_simulation_request(json.dumps(candidate['replay'])).request
    seed=source.seed_for(0)
    start=perf_counter()
    reference=run_pc_melee_scenario(source.scenario,Random(seed))
    wall=perf_counter()-start
    profiler=cProfile.Profile()
    start=perf_counter()
    observed=profiler.runcall(run_pc_melee_scenario,source.scenario,Random(seed))
    profile_wall=perf_counter()-start
    if observed!=reference:
        raise ValueError('profile changed the full native journal')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    profiler.dump_stats(str(args.output.with_suffix('.pstats')))
    stream=io.StringIO()
    stream.write(json.dumps(dict(case=row['source_request']['request_id'],scenario=source.scenario.id,
        seed=str(seed),wall_seconds=wall,profile_seconds=profile_wall,
        actions=reference.executed_actions,rounds=reference.started_rounds,
        full_journal_equal=True))+'\n')
    for order,top in (('cumulative',22),('tottime',15)):
        pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats(order).print_stats(top)
    pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats('cumulative').print_callers('select_pc_tactic')
    args.output.write_text(stream.getvalue(),encoding='utf-8')
    print(stream.getvalue())
    return 0


if __name__=='__main__':
    raise SystemExit(main())
