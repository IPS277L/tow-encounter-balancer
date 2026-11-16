"""Sequential dynamic-search measurements from current public character inputs.

Developer harness, not an application API or a claim of representative balance.
Exact inputs, outputs and unsupported replay samples are saved for inspection.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
from random import Random
import sys
from time import perf_counter

from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request,encode_dynamic_encounter_result
from towr.application.dynamic_encounter import search_dynamic_encounter
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


ROOT=Path(__file__).resolve().parents[1]
CASES=('melee','mixed','mixed-magic')


def benchmark_input(case,seed,*,candidates=4,exploration=4,finalists=2,validation=16):
    if case not in CASES:raise ValueError('unknown benchmark case')
    folder=ROOT/'docs/examples/dynamic'
    name='search.request.json' if case=='melee' else 'pc-ranged.request.json'
    document=json.loads((folder/name).read_text('utf-8'))
    if case=='mixed-magic':
        mage=json.loads((folder/'elemental-mage.request.json').read_text('utf-8'))['party'][0]
        mage['actor_id']='mage'
        document['party'].append(mage)
    document['request_id']=f'benchmark:{case}:{seed}'
    document['npc_count']=dict(minimum=1,maximum=5)
    document['max_rounds']=15
    document['targets']=dict(win_rate=dict(numerator=1,denominator=2),
        started_rounds=dict(numerator=5,denominator=1))
    document['search'].update(master_seed=str(seed),max_candidates=candidates,
        exploration_trials=exploration,top_k=finalists,finalist_trials=validation,
        max_total_trials=candidates*exploration+finalists*validation)
    return document


def measure(document,*,unsupported_samples=3):
    command=parse_dynamic_encounter_request(json.dumps(document))
    batches=[];stopped=[]
    def simulator(source):
        begin=perf_counter()
        result=run_pc_melee_simulation(source)
        summary=summarize_pc_melee_simulation(result)
        batches.append(dict(scenario_id=source.scenario.id,npcs=len(source.scenario.enemies),
            seconds=perf_counter()-begin,trials=source.trials,actions=summary.total_action_count,
            outcomes=asdict(summary.outcome_counts)))
        stopped.extend((source,record) for record in result.records
            if record.outcome is PcMeleeOutcome.UNSUPPORTED_PATH)
        return summary
    begin=perf_counter()
    result=search_dynamic_encounter(command.request,simulator=simulator)
    seconds=perf_counter()-begin
    encoded_begin=perf_counter()
    report=json.loads(encode_dynamic_encounter_result(command,result))
    encode_seconds=perf_counter()-encoded_begin
    samples=[]
    replay_begin=perf_counter()
    for source,record in stopped[:unsupported_samples]:
        battle=run_pc_melee_scenario(source.scenario,Random(record.seed))
        if battle.outcome is not record.outcome or battle.unsupported is None:
            raise ValueError('unsupported replay differs from the observed trial')
        samples.append(dict(scenario_id=source.scenario.id,trial_index=record.trial_index,
            seed=str(record.seed),stop=asdict(battle.unsupported)))
    return dict(source_request=deepcopy(document),search_seconds=seconds,
        encode_seconds=encode_seconds,unsupported_replay_seconds=perf_counter()-replay_begin,
        unsupported_trial_count=len(stopped),unsupported_samples=samples,
        batches=batches,result=report)


def source_digest():
    digest=sha256()
    for path in sorted((ROOT/'src').rglob('*.py')):
        digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    parser.add_argument('--seeds',nargs='+',type=int,default=[42,101])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if any(not 0<=seed<2**64 for seed in args.seeds):parser.error('seeds must fit uint64')
    artifact=dict(created_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,
        platform=platform.platform(),processor=platform.processor(),source_sha256=source_digest(),
        harness_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),measurements=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for case in args.cases:
        for seed in args.seeds:
            print(f'{case} seed={seed}: starting',flush=True)
            row=measure(benchmark_input(case,seed))
            artifact['measurements'].append(row)
            args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{case} seed={seed}: {row["search_seconds"]:.3f}s / '
                f'{row["result"]["total_trials"]} trials; '
                f'unsupported={row["unsupported_trial_count"]}',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
