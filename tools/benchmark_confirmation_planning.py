"""Paired developer experiment: CS32 versus preplanned fixed-n precision."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime,timezone
import json
from pathlib import Path
from time import perf_counter

from tools.benchmark_search_allocation import ROOT, source_digest
from tools.search_allocation import Oracle, Plan, evaluate, fixtures, run_search


def benchmark(*, seeds=range(64), budgets=(112,256,512,1024), pools=(6,12,24), on_case=None):
    began = perf_counter()
    seeds = tuple(seeds)
    game_hash = source_digest((ROOT/'src').rglob('*.py'))
    lab_hash = source_digest(ROOT/'tools'/name for name in
        ('search_allocation.py','benchmark_search_allocation.py','benchmark_confirmation_planning.py'))
    scenarios = fixtures()
    rows = []
    for fixture in scenarios:
        for seed in seeds:
            oracle = Oracle(fixture,seed)
            proposals = oracle.proposal_pool()
            for budget in budgets:
                plan = Plan(budget*max(a.cost for a in proposals))
                for size in pools:
                    pool = proposals[:size]
                    if len(pool)!=size:raise ValueError('pool exceeds fixture space')
                    for protocol,precision in (('cs32',None),('fixed_precision',.1)):
                        result = run_search(pool,oracle.draw,plan,policy='uniform',target=fixture.target,
                            target_rounds=fixture.target_rounds,precision=precision)
                        metrics = evaluate(fixture,result)
                        frozen = result.final_plan
                        rows.append(dict(case=fixture.name,seed=seed,budget_scale=budget,pool_size=size,
                            protocol=protocol,work_cap=plan.work_budget,
                            confirmation_plan=asdict(frozen) if frozen else None,
                            requested_precision_feasible=(not frozen.budget_limited if frozen and frozen.finalist_ids else None),
                            observed_selected_precision_met=(metrics['selected_interval_width']<=.2+1e-12
                                if metrics['selected_interval_width'] is not None else False),
                            **metrics))
        if on_case:on_case(fixture.name,len(rows),perf_counter()-began)
    assert source_digest((ROOT/'src').rglob('*.py'))==game_hash
    groups=defaultdict(list)
    for row in rows:groups[(row['case'],row['budget_scale'],row['pool_size'],row['protocol'])].append(row)
    summary=[]
    for (case,budget,size,protocol),values in sorted(groups.items()):
        n=len(values)
        intervals=[r['selected_interval_width'] for r in values if r['selected_interval_width'] is not None]
        summary.append(dict(case=case,budget_scale=budget,pool_size=size,protocol=protocol,runs=n,
            coverage_win=sum(r['coverage_win'] for r in values),
            win_hits=sum(r['final_win_hit'] for r in values),joint_hits=sum(r['final_joint_hit'] for r in values),
            missing=sum(r['missing_recommendation'] for r in values),unsafe=sum(r['unsupported_risk_selected'] for r in values),
            certificates=sum(r['win_band_certified'] for r in values),
            requested_precision_feasible=sum(r['requested_precision_feasible'] is True for r in values),
            observed_selected_precision_met=sum(r['observed_selected_precision_met'] for r in values),
            confirmation_runs=sum(r['confirmation_work']>0 for r in values),
            confirmation_bound_failures=sum(not r['confirmation_covers_truth'] for r in values),
            mean_penalized_error=sum(r['penalized_error'] for r in values)/n,
            mean_penalized_regret=sum(r['penalized_regret'] for r in values)/n,
            mean_interval_width_if_selected=sum(intervals)/len(intervals) if intervals else None,
            interval_denominator=len(intervals),mean_search_work=sum(r['search_work'] for r in values)/n,
            mean_confirmation_work=sum(r['confirmation_work'] for r in values)/n,
            mean_unspent_work=sum(r['unspent_work'] for r in values)/n))
    return dict(kind='synthetic_fixed_confirmation_experiment',created_utc=datetime.now(timezone.utc).isoformat(),
        game_source_sha256=game_hash,laboratory_sha256=lab_hash,seconds=perf_counter()-began,
        seeds=list(seeds),budgets=list(budgets),pools=list(pools),requested_half_width=.1,
        fixtures=[asdict(f) for f in scenarios],rows=rows,summary=summary)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=64)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.seeds<1:parser.error('--seeds must be positive')
    result=benchmark(seeds=range(args.seeds),on_case=lambda case,n,t:print(f'{case}: {n} searches / {t:.2f}s',flush=True))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Total: {len(result["rows"])} searches / {result["seconds"]:.2f}s',flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
