"""Reproducible allocation experiments on inexpensive, known synthetic truths.

No battle simulation, product default or performance claim about the game UI.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from tools.search_allocation import Oracle, Plan, evaluate, fixtures, run_search


ROOT = Path(__file__).resolve().parents[1]


def source_digest(paths):
    digest = sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['case'],row['budget_scale'],row['pool_size'],row['policy'])].append(row)
    summaries = []
    for (case,budget,pool,policy),group in sorted(groups.items()):
        n = len(group)
        summary = dict(case=case,budget_scale=budget,pool_size=pool,policy=policy,runs=n)
        for key in ('coverage_win','coverage_joint','final_win_hit','final_joint_hit',
                'missing_recommendation','unsupported_risk_selected','win_band_certified',
                'cs_covers_truth_at_all_recorded_looks'):
            summary[key+'_count'] = sum(r[key] for r in group)
        for key in ('penalized_error','penalized_regret','trials','search_work',
                'confirmation_work','unspent_work','unused_confirmation_reserve','unknown_trials','round_limit_trials'):
            summary['mean_'+key] = sum(r[key] for r in group)/n
        summaries.append(summary)
    paired = []
    pairs = defaultdict(dict)
    for row in rows:
        pairs[(row['case'],row['budget_scale'],row['pool_size'],row['seed'])][row['policy']] = row
    aggregated = defaultdict(list)
    for (case,budget,pool,seed),pair in pairs.items():
        a,b = pair['uniform'],pair['racing']
        aggregated[(case,budget,pool)].append(dict(
            delta=b['penalized_error']-a['penalized_error'],
            better=b['penalized_error']<a['penalized_error']-1e-12,
            worse=b['penalized_error']>a['penalized_error']+1e-12,
            win_hit_delta=int(b['final_win_hit'])-int(a['final_win_hit'])))
    for (case,budget,pool),values in sorted(aggregated.items()):
        paired.append(dict(case=case,budget_scale=budget,pool_size=pool,runs=len(values),
            mean_error_delta=sum(v['delta'] for v in values)/len(values),
            better=sum(v['better'] for v in values),worse=sum(v['worse'] for v in values),
            win_hit_delta=sum(v['win_hit_delta'] for v in values)))
    return summaries,paired


def benchmark(*, seeds=range(64), budgets=(112,256,512), pools=(6,12,24), on_case=None):
    began = perf_counter()
    game_hash = source_digest((ROOT/'src').rglob('*.py'))
    laboratory_hash = source_digest((ROOT/'tools'/name for name in
        ('search_allocation.py','benchmark_search_allocation.py')))
    scenarios = fixtures()
    rows = []
    for fixture in scenarios:
        for seed in seeds:
            oracle = Oracle(fixture,seed)
            proposals = oracle.proposal_pool()
            for budget in budgets:
                for pool_size in pools:
                    pool = proposals[:pool_size]
                    if len(pool) != pool_size:
                        raise ValueError('pool exceeds fixture space')
                    plan = Plan(budget*max(a.cost for a in proposals))
                    for policy in ('uniform','racing'):
                        result = run_search(pool,oracle.draw,plan,policy=policy,
                            target=fixture.target,target_rounds=fixture.target_rounds)
                        rows.append(dict(case=fixture.name,seed=seed,budget_scale=budget,
                            pool_size=pool_size,policy=policy,work_cap=plan.work_budget,
                            **evaluate(fixture,result)))
        if on_case:
            on_case(fixture.name,len(rows),perf_counter()-began)
    assert source_digest((ROOT/'src').rglob('*.py')) == game_hash
    summary,paired = summarize(rows)
    return dict(kind='synthetic_search_allocation_experiment',created_utc=datetime.now(timezone.utc).isoformat(),
        game_source_sha256=game_hash,laboratory_sha256=laboratory_hash,
        seed_indices=list(seeds),budgets=list(budgets),pools=list(pools),
        seconds=perf_counter()-began,fixtures=[asdict(f) for f in scenarios],
        rows=rows,summary=summary,paired_uniform_to_racing=paired)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=64,help='Count of deterministic replicate seeds, from zero.')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    if args.seeds < 1:
        parser.error('--seeds must be positive')
    result = benchmark(seeds=range(args.seeds),on_case=lambda name,n,seconds:
        print(f'{name}: {n} searches completed / {seconds:.2f}s',flush=True))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Total: {len(result["rows"])} searches / {result["seconds"]:.2f}s',flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
