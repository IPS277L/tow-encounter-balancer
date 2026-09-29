"""Developer wall-clock comparison including fresh spawn startup and shutdown.

Run from the repository root: python -m tools.benchmark_m7_parallel --output ...
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import gc
from hashlib import sha256
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
from time import perf_counter
import tracemalloc

from tools.profile_m7 import CASES, benchmark_request, trial_digest
from towr.simulation.npc_mixed_models import SEED_SCHEME, NpcMixedSimulationRequest, NpcMixedSimulationResult
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


@dataclass(frozen=True, slots=True)
class WallComparison:
    result: NpcMixedSimulationResult
    summary: NpcMixedSimulationSummary
    # 0 denotes sequential; positive numbers are the explicit pool worker limit.
    timings: tuple[tuple[int, tuple[float, ...]], ...]


def measure_comparison(request: NpcMixedSimulationRequest, *, workers: tuple[int, ...],
                       batch_size: int, repeats: int) -> WallComparison:
    if not isinstance(request, NpcMixedSimulationRequest):
        raise TypeError("benchmark requires a mixed simulation request")
    if any(type(v) is not int or v < 1 for v in (*workers, batch_size, repeats)):
        raise ValueError("workers, batch_size and repeats must be positive integers")
    if not workers or len(set(workers)) != len(workers):
        raise ValueError("supply distinct worker counts")
    if tracemalloc.is_tracing() or sys.getprofile() is not None:
        raise RuntimeError("benchmark requires no active tracemalloc/profiler")
    run_npc_mixed_simulation(replace(request, trials=min(3, request.trials)))
    modes = (0, *workers)
    timings = {mode: [] for mode in modes}
    reference = None
    for repeat in range(repeats):
        # Alternate mode order to reduce a systematic first/last timing bias.
        for mode in modes if repeat % 2 == 0 else modes[::-1]:
            gc.collect()
            start = perf_counter()
            result = (run_npc_mixed_simulation(request) if mode == 0 else
                      run_npc_mixed_simulation_parallel(request, workers=mode, batch_size=batch_size))
            summary = summarize_npc_mixed_simulation(result)
            timings[mode].append(perf_counter() - start)
            if result.source_request is not request or summary.source_request is not request:
                raise ValueError("benchmark result must retain the exact source request")
            if reference is None:
                reference = result, summary
            elif (result, summary) != reference:
                raise ValueError("trial records or summaries differ between sequential/process runs")
    return WallComparison(*reference, tuple((mode, tuple(values)) for mode, values in timings.items()))


def source_digest(root: Path) -> str:
    """Fingerprint sources and both benchmark modules, including untracked files."""
    paths = sorted((*root.joinpath("src").rglob("*.py"), root / "tools" / "profile_m7.py",
                    root / "tools" / "benchmark_m7_parallel.py"),
                   key=lambda path: path.relative_to(root).as_posix())
    digest = sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--master-seed", type=int, default=20260929)
    parser.add_argument("--round-budget", type=int, default=5)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    requests = tuple(benchmark_request(case, trials=args.trials, master_seed=args.master_seed,
                                      round_budget=args.round_budget) for case in CASES)
    root = Path(__file__).resolve().parents[1]
    before_hash = source_digest(root)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    changes = subprocess.check_output(["git", "status", "--porcelain", "--", "src"], cwd=root, text=True).strip()
    if changes:
        revision += " (src has uncommitted changes)"
    command = (f'& "{sys.executable}" -m tools.benchmark_m7_parallel '
        f"--trials {args.trials} --master-seed {args.master_seed} --round-budget {args.round_budget} "
        f"--workers {' '.join(map(str, args.workers))} --batch-size {args.batch_size} --repeats {args.repeats} "
        f'--output "{args.output.as_posix()}"')
    lines = ["# M7 sequential / spawn wall-clock comparison", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor()}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Source/harness SHA-256: `{before_hash}`",
        f"Seed scheme: `{SEED_SCHEME}`", "",
        "```powershell", '$env:PYTHONPATH = "src"', command, "```", "",
        "Same fixtures as profile_m7: 2x1/3x2 with one bow; 2x2 with two bows. "
        "Fixed Close/Medium pairs, aware targets, stationary numeric Minions, explicit GM policies. "
        "Unsupported trials remain included as a separate technical outcome. Parent warm-up: min(3, trials). No persistent pool: every process timing "
        "includes serialization, spawn/imports, execution, collection, validation and shutdown. "
        "Summary projection is inside timing; fixture construction and equality checks are outside. "
        "Mode order alternates per repeat; gc.collect is outside timing. All full compact records "
        "and aggregate summaries are compared for equality. Source hash covers src/**/*.py, "
        "tools/profile_m7.py and tools/benchmark_m7_parallel.py and must match before/after. "
        "No cProfile/tracemalloc; child or total process memory is not measured. "
        "CPU affinity and external OS load are not controlled; ratios are observations on this host, not guarantees.", "",
        "| Case | Mode | Wall repeats, s | Median, s | Sequential / mode |",
        "| --- | --- | --- | --- | --- |"]
    details = []
    for case, request in zip(CASES, requests):
        print(f"Comparing {case[0]}x{case[1]}: {args.trials} trials", flush=True)
        measured = measure_comparison(request, workers=tuple(args.workers), batch_size=args.batch_size, repeats=args.repeats)
        sequential = median(measured.timings[0][1])
        for mode, times in measured.timings:
            label = "sequential" if mode == 0 else f"spawn, workers={mode}"
            lines.append(f"| {case[0]}x{case[1]} | {label} | " + ", ".join(f"{v:.6f}" for v in times)
                         + f" | {median(times):.6f} | {sequential / median(times):.3f} |")
        result = measured.result
        counts = result.outcome_counts
        details.extend(["", f"## {case[0]}x{case[1]}", "",
            f"Trial-record SHA-256: `{trial_digest(result)}`", "",
            f"Outcomes (achieved/defeated/limit/unsupported): {counts.objective_achieved}/{counts.side_defeated}/"
            f"{counts.round_limit}/{counts.unsupported_path}; attacks: {result.total_attack_count}; "
            f"visited rounds: {result.total_visited_round_count}."])
    if source_digest(root) != before_hash:
        raise RuntimeError("source files changed during measurement")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines + details) + "\n", encoding="utf-8")
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
