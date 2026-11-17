"""Dynamic-search measurements from current public character inputs.

Developer harness, not an application API or a claim of representative balance.
Exact inputs, outputs and unsupported replay samples are saved for inspection.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from functools import wraps
from hashlib import sha256
import json
from pathlib import Path
import platform
from random import Random
import sys
from time import perf_counter
from unittest.mock import patch

from towr.adapters.dynamic_encounter_json import (DynamicEncounterInputError,parse_dynamic_encounter_request,
    encode_dynamic_encounter_result,scenario_document)
from towr.application.dynamic_encounter import search_dynamic_encounter
import towr.application.dynamic_encounter as app
from towr.application.ranged_simulation_models import SimulationExecutionMode
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_process import PcMeleeProcessSession


ROOT=Path(__file__).resolve().parents[1]
CASES=('melee','mixed','mixed-magic')


@contextmanager
def _capture_proposals():
    """Observe private parent-process proposals without touching their RNG/result."""
    original=app._propose
    events=[]
    seen=set()

    @wraps(original)
    def observed(request,explored,rng,operation):
        proposal=original(request,explored,rng,operation)
        duplicate=proposal.composition in seen
        seen.add(proposal.composition)
        events.append(dict(attempt=len(events)+1,requested=proposal.requested.value,
            applied=proposal.applied.value,npc_count=len(proposal.composition),duplicate=duplicate))
        return proposal

    with patch.object(app,'_propose',new=observed):
        yield events


def _proposal_statistics(events):
    """Count actual attempts, including duplicates and unavailable-operation fallbacks."""
    operations=tuple(operation.value for operation in app._ProposalOperation)
    requested=Counter(event['requested'] for event in events)
    applied=Counter(event['applied'] for event in events)
    fallback_paths=Counter(event['requested']+'->'+event['applied'] for event in events
        if event['requested']!=event['applied'])
    duplicates=sum(event['duplicate'] for event in events)
    return dict(attempts=len(events),accepted=len(events)-duplicates,duplicates=duplicates,
        requested={operation:requested[operation] for operation in operations},
        applied={operation:applied[operation] for operation in operations},
        fallbacks=sum(fallback_paths.values()),fallback_paths=dict(sorted(fallback_paths.items())))


def _joint_target_statistics(report):
    """Describe point-estimate transitions, never true-probability coverage."""
    def key(candidate):
        return json.dumps(candidate['npcs'],sort_keys=True,separators=(',',':'))

    def partition(candidates):
        counts=dict(both=0,win_only=0,rounds_only=0,neither=0,unsupported=0)
        for candidate in candidates:
            assessment=candidate['target_assessment']
            if assessment['status']=='unsupported':name='unsupported'
            elif assessment['status']=='within_targets':name='both'
            elif assessment['status']=='outside_targets':
                name=('win_only' if assessment['win_rate_in_range'] else
                    'rounds_only' if assessment['started_rounds_in_range'] else 'neither')
            else:raise ValueError('unknown target assessment status')
            counts[name]+=1
        return dict(candidates=len(candidates),**counts)

    explored={key(c):c for c in report['explored']}
    if len(explored)!=len(report['explored']):
        raise ValueError('joint diagnostics require unique explored compositions')
    validations=report['validations']
    if len({key(c) for c in validations})!=len(validations):
        raise ValueError('joint diagnostics require unique validation compositions')
    transitions=[]
    for final in validations:
        initial=explored.get(key(final))
        if initial is None:
            raise ValueError('validation has no complete matching explored composition')
        transitions.append(dict(exploration_id=initial['replay']['scenario']['id'],
            validation_id=final['replay']['scenario']['id'],
            exploration_status=initial['target_assessment']['status'],
            validation_status=final['target_assessment']['status'],
            exploration_win_rate=initial['win_rate'],validation_win_rate=final['win_rate'],
            exploration_mean_started_rounds=initial['mean_started_rounds'],
            validation_mean_started_rounds=final['mean_started_rounds']))
    found=any(t['validation_status']=='within_targets' for t in transitions)
    if report['target_match_found']!=found:
        raise ValueError('joint diagnostics differ from the public validation match flag')
    return dict(basis='point_estimates',explored=partition(report['explored']),
        validations=partition(validations),
        screening_matches_revalidated=sum(t['exploration_status']=='within_targets' for t in transitions),
        retained_matches=sum(t['exploration_status']==t['validation_status']=='within_targets' for t in transitions),
        newly_observed_validation_matches=sum(t['exploration_status']!='within_targets' and
            t['validation_status']=='within_targets' for t in transitions),
        target_match_found=found,transitions=transitions)


def benchmark_input(case,seed,*,candidates=4,exploration=4,finalists=2,validation=16,
        minimum_npcs=1,maximum_npcs=5):
    if case not in CASES:raise ValueError('unknown benchmark case')
    folder=ROOT/'docs/examples/dynamic'
    name='search.request.json' if case=='melee' else 'pc-ranged.request.json'
    document=json.loads((folder/name).read_text('utf-8'))
    if case=='mixed-magic':
        mage=json.loads((folder/'elemental-mage.request.json').read_text('utf-8'))['party'][0]
        mage['actor_id']='mage'
        document['party'].append(mage)
    document['request_id']=f'benchmark:{case}:{seed}'
    document['npc_count']=dict(minimum=minimum_npcs,maximum=maximum_npcs)
    document['max_rounds']=15
    document['targets']=dict(win_rate=dict(numerator=1,denominator=2),
        started_rounds=dict(numerator=5,denominator=1))
    document['search'].update(master_seed=str(seed),max_candidates=candidates,
        exploration_trials=exploration,top_k=finalists,finalist_trials=validation,
        max_total_trials=candidates*exploration+finalists*validation)
    return document


def measure(document,*,unsupported_samples=3,on_batch_complete=None,on_trial_complete=None,
        failure_output=None):
    command=parse_dynamic_encounter_request(json.dumps(document))
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        with PcMeleeProcessSession(workers=command.execution.workers,
                batch_size=command.execution.batch_size) as session:
            return _measure(document,command,unsupported_samples=unsupported_samples,
                on_batch_complete=on_batch_complete,on_trial_complete=on_trial_complete,
                failure_output=failure_output,process_session=session)
    return _measure(document,command,unsupported_samples=unsupported_samples,
        on_batch_complete=on_batch_complete,on_trial_complete=on_trial_complete,failure_output=failure_output)


def _measure(document,command,*,unsupported_samples,on_batch_complete,on_trial_complete,
        failure_output,process_session=None):
    batches=[];stopped=[]
    def simulator(source):
        begin=perf_counter()
        completed=set()
        def observed(record):
            completed.add(record.trial_index)
            if on_trial_complete is not None:
                on_trial_complete(source,record)
        try:
            observer=dict(on_trial_complete=observed) if failure_output is not None or on_trial_complete is not None else {}
            result=(run_pc_melee_simulation(source,**observer) if process_session is None
                else process_session.run(source,**observer))
        except Exception as error:
            if failure_output is not None:
                next_index=next((i for i in range(source.trials) if i not in completed),source.trials)
                replay=dict(schema_version='1',kind='pc_melee_simulation',request_id=source.scenario.id,
                    ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source.scenario),
                    simulation=dict(master_seed=str(source.master_seed),trials=source.trials),
                    execution=dict(mode='sequential'))
                diagnostic=dict(source_request=deepcopy(document),replay=replay,
                    completed_trial_count=len(completed),completed_trial_indices=sorted(completed),
                    next_trial_index=next_index,
                    next_trial_seed=str(source.seed_for(next_index)) if next_index<source.trials else None,
                    completed_batches=list(batches),error_type=type(error).__name__,error=str(error),
                    error_notes=list(getattr(error,'__notes__',())))
                path=Path(failure_output);path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2),encoding='utf-8')
            raise
        summary=summarize_pc_melee_simulation(result)
        batches.append(dict(scenario_id=source.scenario.id,npcs=len(source.scenario.enemies),
            seconds=perf_counter()-begin,trials=source.trials,actions=summary.total_action_count,
            outcomes=asdict(summary.outcome_counts)))
        if on_batch_complete is not None:
            on_batch_complete(batches[-1])
        stopped.extend((source,record) for record in result.records
            if record.outcome is PcMeleeOutcome.UNSUPPORTED_PATH)
        return summary
    with _capture_proposals() as proposal_events:
        begin=perf_counter()
        result=search_dynamic_encounter(command.request,simulator=simulator)
        if process_session is not None:
            process_session.close()
        seconds=perf_counter()-begin
    proposal_metrics=_proposal_statistics(proposal_events)
    if (proposal_metrics['attempts']!=result.proposal_attempts
            or proposal_metrics['accepted']!=len(result.explored)):
        raise ValueError('proposal telemetry differs from completed search accounting')
    proposal_metrics['events']=[dict(event) for event in proposal_events]
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
        unsupported_observations=[dict(scenario_id=source.scenario.id,trial_index=record.trial_index,
            seed=str(record.seed),started_rounds=record.started_rounds,completed_rounds=record.completed_rounds)
            for source,record in stopped],
        unsupported_replay_count=len(samples),batches=batches,result=report,proposal_metrics=proposal_metrics,
        joint_target_metrics=_joint_target_statistics(report))


def source_digest():
    digest=sha256()
    for path in sorted((ROOT/'src').rglob('*.py')):
        digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    input_group=parser.add_mutually_exclusive_group()
    input_group.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    input_group.add_argument('--requests',nargs='+',type=Path,
        help='Measure exact exported JSON requests, preserving all plan/seed/count settings.')
    parser.add_argument('--seeds',nargs='+',type=int)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidates',type=int)
    parser.add_argument('--exploration',type=int)
    parser.add_argument('--finalists',type=int)
    parser.add_argument('--validation',type=int)
    parser.add_argument('--minimum-npcs',type=int)
    parser.add_argument('--maximum-npcs',type=int)
    parser.add_argument('--unsupported-samples',type=int,default=3,
        help='Maximum diagnostic unsupported replays per request; zero disables extra battles.')
    args=parser.parse_args(argv)
    if args.unsupported_samples<0:
        parser.error('--unsupported-samples must be nonnegative')
    plan_names=('candidates','exploration','finalists','validation','minimum_npcs','maximum_npcs')
    overrides={name:getattr(args,name) for name in plan_names
        if getattr(args,name) is not None}
    if args.requests and (overrides or args.seeds is not None):
        parser.error('--requests cannot be combined with seed, plan or count overrides')
    try:
        # Admit the entire series before spending its first simulation.
        if args.requests:
            documents=[]
            for path in args.requests:
                raw=path.read_text('utf-8')
                parse_dynamic_encounter_request(raw)
                documents.append(json.loads(raw))
        else:
            documents=[benchmark_input(case,seed,**overrides)
                for case in args.cases for seed in (args.seeds or [42,101])]
            for document in documents:
                parse_dynamic_encounter_request(json.dumps(document))
    except (OSError,ValueError,TypeError,DynamicEncounterInputError) as error:
        parser.error(str(error))
    artifact=dict(created_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,
        platform=platform.platform(),processor=platform.processor(),source_sha256=source_digest(),
        harness_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),measurements=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    for document in documents:
        print(document['request_id']+': starting',flush=True)
        completed_by_candidate={}
        def trial_complete(source,record):
            indices=completed_by_candidate.setdefault(source.scenario.id,set())
            indices.add(record.trial_index)
            completed=len(indices)
            if completed%8==0 or completed==source.trials:
                print(f'  {source.scenario.id}: {completed}/{source.trials} trials',flush=True)
        row=measure(document,unsupported_samples=args.unsupported_samples,
            failure_output=args.output.with_suffix('.failure.json'),
            on_trial_complete=trial_complete,
            on_batch_complete=lambda batch:print(f'  {batch["scenario_id"]}: '
                f'{batch["npcs"]} NPC / {batch["trials"]} trials / '
                f'{batch["outcomes"]["objective_achieved"]} wins / {batch["seconds"]:.2f}s',flush=True))
        artifact['measurements'].append(row)
        args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'{document["request_id"]}: {row["search_seconds"]:.3f}s / '
            f'{row["result"]["total_trials"]} trials; '
            f'unsupported={row["unsupported_trial_count"]}',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
