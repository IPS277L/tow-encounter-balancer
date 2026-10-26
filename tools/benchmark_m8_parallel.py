"""Bounded M8 wall comparison; run python -m tools.benchmark_m8_parallel."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import gc
from hashlib import sha256
from multiprocessing import active_children
from pathlib import Path
import platform
from random import getstate
import shlex
from statistics import median
import subprocess
import sys
from time import perf_counter

from tools.m8_benchmark_fixtures import CASES, benchmark_request
from tools.profile_m8 import _instrumentation_idle, _write_report, trial_digest
from towr.simulation.npc_magic_models import SEED_SCHEME, NpcMagicSimulationRequest, NpcMagicSimulationResult
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


@dataclass(frozen=True, slots=True)
class WallComparison:
    result: NpcMagicSimulationResult
    summary: NpcMagicSimulationSummary
    # 0 is sequential; positive values are explicit pool worker limits.
    timings: tuple[tuple[int, tuple[float, ...]], ...]


def _settings(workers: tuple[int, ...], batch_size: int, repeats: int) -> None:
    if type(workers) is not tuple:
        raise TypeError("workers must be a tuple")
    if any(type(v) is not int for v in (*workers, batch_size, repeats)):
        raise TypeError("workers, batch_size and repeats must be integers")
    if not workers or any(v < 1 for v in (*workers, batch_size, repeats)) or len(set(workers)) != len(workers):
        raise ValueError("supply distinct positive workers and positive batch_size/repeats")


def measure_comparison(request: NpcMagicSimulationRequest, *, workers: tuple[int, ...],
                       batch_size: int, repeats: int) -> WallComparison:
    if not isinstance(request, NpcMagicSimulationRequest):
        raise TypeError("benchmark requires a magic simulation request")
    _settings(workers, batch_size, repeats)
    _instrumentation_idle()
    original, global_rng = deepcopy(request), getstate()
    children = {child.pid for child in active_children()}

    def verify(observed, source):
        result, summary = observed
        if result.source_request is not source or summary.source_request is not source or any(
                trial.source_scenario is not source.scenario for trial in result.trials):
            raise ValueError("benchmark result must retain the exact parent source")
        if request != original or getstate() != global_rng:
            raise ValueError("benchmark changed input or global RNG state")
        if {child.pid for child in active_children()} != children:
            raise ValueError("benchmark changed active children")

    warm_request = replace(request, trials=min(3, request.trials))
    warm_result = run_npc_magic_simulation(warm_request)
    verify((warm_result, summarize_npc_magic_simulation(warm_result)), warm_request)
    del warm_result, warm_request
    modes = (0, *workers)
    timings: dict[int, list[float]] = {mode: [] for mode in modes}
    reference = None
    for repeat in range(repeats):
        for mode in modes if repeat % 2 == 0 else modes[::-1]:
            gc.collect()
            _instrumentation_idle()
            start = perf_counter()
            result = (run_npc_magic_simulation(request) if mode == 0 else
                      run_npc_magic_simulation_parallel(request, workers=mode, batch_size=batch_size))
            summary = summarize_npc_magic_simulation(result)
            timings[mode].append(perf_counter() - start)
            observed = result, summary
            verify(observed, request)
            if reference is None:
                reference = observed
            elif observed != reference:
                raise ValueError("trial records or summaries differ between sequential/process runs")
            del observed, result, summary
    return WallComparison(*reference, tuple((mode, tuple(values)) for mode, values in timings.items()))


def source_digest(root: Path) -> str:
    """Sorted path+NUL+raw content hash; includes untracked production Python."""
    paths = sorted((*root.joinpath("src").rglob("*.py"), root / "tools/profile_m8.py",
                    root / "tools/m8_benchmark_fixtures.py", root / "tools/benchmark_m8_parallel.py"),
                   key=lambda path: path.relative_to(root).as_posix())
    digest = sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def render_report(measurements: tuple[WallComparison, ...], *, command: str, revision: str,
                  source_hash: str, batch_size: int) -> str:
    lines = ["# M8 sequential / spawn wall-clock comparison", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor() or 'not reported'}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Source/harness SHA-256: `{source_hash}`",
        f"Seed scheme: `{SEED_SCHEME}`; batch_size: {batch_size}", "",
        "```sh", "PYTHONPATH=src " + command, "```", "",
        "Method: [bounded comparison](m8-parallel-comparison-contract.md). Same authored fixtures as "
        "profile_m8: curse-routes and champion-pressure are three-actor combat cases; missing-departure "
        "is a separate zero-action/zero-draw unsupported control, not representative combat. "
        "Control is not averaged with combat. Unsupported trials stay included in N.", "",
        "Parent sequential warm-up min(3,N) per case. Mode order alternates sequential/workers in supplied order, then reversed. Each process call creates a fresh spawn pool; wall includes preflight, "
        "serialization, startup/imports, execution, collection, source validation/normalization and shutdown. "
        "Summary projection is inside timing. Fixtures/imports, snapshots, gc.collect, hashing, full records/summary "
        "equality and parent source identity checks are outside timing. Input/global RNG/active children unchanged. "
        "GC mode unchanged. No active tracemalloc/profiler (including sys.monitoring.PROFILER_ID). "
        "Child/total memory and RSS are not measured; CPU affinity/frequency and external OS load uncontrolled. "
        "Ratios are local observations, not guarantees, test thresholds, or a difficulty metric.", "",
        "Source manifest: all src/**/*.py plus tools/profile_m8.py, tools/m8_benchmark_fixtures.py and "
        "tools/benchmark_m8_parallel.py, including untracked files. Sort relative POSIX paths; hash each UTF-8 "
        "path + NUL + raw content SHA-256, then SHA-256 the concatenation. Must match before/after. "
        "Docs/tests/bytecode excluded; output is published atomically only after successful checks.", "",
        "| Case | N | Seed | Round budget | Mode | Wall repeats, s | Median, s | Sequential / mode |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    details = []
    for item in measurements:
        request = item.result.source_request
        case = request.scenario.id.rsplit(":", 1)[-1]
        sequential = median(item.timings[0][1])
        for mode, times in item.timings:
            label = "sequential" if mode == 0 else f"spawn, workers={mode}"
            lines.append(f"| {case} | {request.trials} | {request.master_seed} | {request.scenario.max_rounds} | "
                + label + " | " + ", ".join(f"{v:.6f}" for v in times)
                + f" | {median(times):.6f} | {sequential / median(times):.3f} |")
        counts = item.result.outcome_counts
        details.extend(["", f"## {case}", "", f"Trial-record SHA-256: `{trial_digest(item.result)}`", "",
            f"Outcomes (achieved/defeated/limit/unsupported): {counts.objective_achieved}/"
            f"{counts.perspective_defeated}/{counts.round_limit_reached}/{counts.unsupported_path}; "
            f"actions: {item.result.total_action_count}; started rounds: {item.result.total_started_round_count}; "
            f"completed rounds: {item.result.total_completed_round_count}.", "",
            f"All {sum(len(times) for _, times in item.timings)} measured full results/summaries equal; "
            "all records share the original parent scenario."])
    return "\n".join(lines + details) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--master-seed", type=int, default=20261026)
    parser.add_argument("--round-budget", type=int, default=4)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workers = tuple(args.workers)
    _settings(workers, args.batch_size, args.repeats)
    _instrumentation_idle()
    requests = tuple(benchmark_request(case, trials=args.trials, master_seed=args.master_seed,
                                      round_budget=args.round_budget) for case in CASES)
    root = Path(__file__).resolve().parents[1]
    before_hash = source_digest(root)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    changes = subprocess.run(["git", "status", "--porcelain", "--", "src", "tools"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
    if changes:
        revision += " (src/tools have uncommitted changes)"
    measurements = []
    for case, request in zip(CASES, requests):
        print(f"Comparing {case}: {args.trials} trials", flush=True)
        measurements.append(measure_comparison(request, workers=workers, batch_size=args.batch_size,
                                               repeats=args.repeats))
    command = shlex.join([sys.executable, "-m", "tools.benchmark_m8_parallel", "--trials", str(args.trials),
        "--master-seed", str(args.master_seed), "--round-budget", str(args.round_budget),
        "--workers", *map(str, workers), "--batch-size", str(args.batch_size), "--repeats", str(args.repeats),
        "--output", args.output.as_posix()])
    rendered = render_report(tuple(measurements), command=command, revision=revision,
                             source_hash=before_hash, batch_size=args.batch_size)
    if source_digest(root) != before_hash:
        raise RuntimeError("source files changed during measurement")
    _write_report(args.output, rendered)
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
