"""Reproducible sequential M8 baseline; developer harness, not an app CLI."""
from __future__ import annotations

import argparse
import cProfile
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import gc
from hashlib import sha256
from io import StringIO
from pathlib import Path
import platform
import pstats
from random import getstate
import shlex
from statistics import median
import subprocess
import sys
from tempfile import NamedTemporaryFile
from time import perf_counter
import tracemalloc

from tools.m8_benchmark_fixtures import CASES, benchmark_request
from towr.simulation.npc_magic_models import SEED_SCHEME, NpcMagicSimulationRequest, NpcMagicSimulationResult
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def trial_digest(result: NpcMagicSimulationResult) -> str:
    rows = (f"{t.trial_index}|{t.seed}|{t.outcome.value}|{t.executed_action_count}|"
            f"{t.started_round_count}|{t.completed_round_count}" for t in result.trials)
    return sha256((SEED_SCHEME + "\n" + "\n".join(rows)).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Measurement:
    result: NpcMagicSimulationResult
    summary: NpcMagicSimulationSummary
    wall_seconds: tuple[float, ...]
    peak_python_bytes: int
    profile_cumulative: str
    profile_self: str
    profile_replace_callers: str


def run_batch(request: NpcMagicSimulationRequest) -> tuple[NpcMagicSimulationResult, NpcMagicSimulationSummary]:
    result = run_npc_magic_simulation(request)
    return result, summarize_npc_magic_simulation(result)


def source_digest(root: Path) -> str:
    """Hash actual production Python plus both harness files, including untracked."""
    paths = sorted((*root.joinpath("src").rglob("*.py"), root / "tools/profile_m8.py",
                    root / "tools/m8_benchmark_fixtures.py"), key=lambda p: p.relative_to(root).as_posix())
    digest = sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _settings(repeats: int, top: int) -> None:
    for value, name in ((repeats, "repeats"), (top, "top")):
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer")
        if value < 1:
            raise ValueError(f"{name} must be positive")


def _instrumentation_idle() -> None:
    # Python 3.12+ cProfile may own the monitoring slot without getprofile().
    monitoring = getattr(sys, "monitoring", None)
    profiler_owned = monitoring is not None and monitoring.get_tool(monitoring.PROFILER_ID) is not None
    if tracemalloc.is_tracing() or sys.getprofile() is not None or profiler_owned:
        raise RuntimeError("benchmark requires no active tracemalloc/profiler")


def measure(request: NpcMagicSimulationRequest, *, repeats: int = 3, top: int = 12) -> Measurement:
    if not isinstance(request, NpcMagicSimulationRequest):
        raise TypeError("magic benchmark requires its typed simulation request")
    _settings(repeats, top)
    _instrumentation_idle()
    original, global_rng = deepcopy(request), getstate()
    run_batch(replace(request, trials=min(3, request.trials)))
    baseline = None
    timings = []

    def verify(observed):
        if observed[0].source_request != request or observed[1].source_request != request:
            raise ValueError("measurement returned a foreign source request")
        if baseline is not None and observed != baseline:
            raise ValueError("trial records or aggregate summary changed between measurement runs")
        if request != original or getstate() != global_rng:
            raise ValueError("benchmark changed input or global RNG state")

    for _ in range(repeats):
        gc.collect()
        start = perf_counter()
        observed = run_batch(request)
        timings.append(perf_counter() - start)
        verify(observed)
        if baseline is None:
            baseline = observed
        del observed

    gc.collect()
    tracemalloc.start()
    try:
        observed = run_batch(request)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    verify(observed)
    del observed

    gc.collect()
    profiler = cProfile.Profile()
    observed = profiler.runcall(run_batch, request)
    verify(observed)
    reports = []
    for order in ("cumulative", "tottime"):
        stream = StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(order).print_stats(top)
        reports.append(stream.getvalue().strip())
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_callers(r"dataclasses.py:.*\(replace\)")
    return Measurement(baseline[0], baseline[1], tuple(timings), peak,
                       reports[0], reports[1], stream.getvalue().strip())


def render_report(measurements: tuple[Measurement, ...], *, command: str, revision: str, source_hash: str) -> str:
    lines = ["# M8 sequential magic baseline", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor() or 'not reported'}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Source/harness SHA-256: `{source_hash}`",
        f"Seed scheme: `{SEED_SCHEME}`", "", "```sh", "PYTHONPATH=src " + command, "```", "",
        "Contract: [bounded profiling](m8-profiling-contract.md). All profiles/facts are authored numeric inputs, "
        "not named book NPCs. Three actors: Wizard Level2 Casting/Willpower3d/3 RES4, ally/enemy "
        "Shooting3d/3 Dam3 RES3 Athletics3d/3. No additional rules, reload, terrain, opposition or hidden actors. "
        "Explicit ranges and directed approvals, repeated Staggered chooses Wound and GM-approved KO. "
        "Enemy positions arena/shelter/boundary have Short/Medium/Long pair ranges; six frames include archived ally. "
        "Curse Give Ground routes arena -> shelter -> boundary, followed by safe Broken Recover. "
        "curse-routes targets Wizard then ally; champion-pressure targets ally then Wizard. "
        "missing-departure activates ally first without departure facts: a zero-action control, not representative combat.", "",
        "Warm-up min(3,N) per case. Fixture/imports, input snapshot, gc.collect, hashing and equality are outside timing. "
        "Wall includes production sequential batch plus summary. Separate tracemalloc and cProfile runs must preserve "
        "all records and summary; input/global RNG unchanged. Peak is incremental traced Python allocation, "
        "not process RSS; existing fixture/reference result excluded. Profiled times are not ordinary wall times; "
        "cumulative rows overlap and must not be summed. GC mode is unchanged.", "",
        "All four outcomes count; unsupported is a technical stop, not defeat/draw. No filtering or difficulty metric. "
        "Control timings are not averaged with combat cases. CPU affinity/frequency and external OS load are uncontrolled. "
        "No process startup/serialization, other workloads/hosts/runtimes or speedup claims are measured.", "",
        "| Case | Trials | Seed | Round budget | Wall seconds | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Actions | Started | Completed |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for item in measurements:
        request = item.result.source_request
        counts = item.summary.outcome_counts
        label = request.scenario.id.rsplit(":", 1)[-1]
        lines.append(f"| {label} | {request.trials} | {request.master_seed} | {request.scenario.max_rounds} | "
            + ", ".join(f"{value:.6f}" for value in item.wall_seconds)
            + f" | {median(item.wall_seconds):.6f} | {item.peak_python_bytes / 1024:.1f} | "
            + f"{counts.objective_achieved}/{counts.perspective_defeated}/{counts.round_limit_reached}/{counts.unsupported_path} | "
            + f"{item.result.total_action_count} | {item.result.total_started_round_count} | {item.result.total_completed_round_count} |")
    for item in measurements:
        label = item.result.source_request.scenario.id.rsplit(":", 1)[-1]
        lines.extend(["", f"## Profile: {label}", "",
            f"Trial-record SHA-256: `{trial_digest(item.result)}`", "",
            "Cumulative time:", "", "```text", item.profile_cumulative, "```", "",
            "Self time:", "", "```text", item.profile_self, "```", "",
            "dataclasses.replace callers:", "", "```text", item.profile_replace_callers, "```"])
    return "\n".join(lines) + "\n"


def _write_report(output: Path, text: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                prefix=".profile_m8-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--master-seed", type=int, default=20261026)
    parser.add_argument("--round-budget", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _settings(args.repeats, args.top)
    _instrumentation_idle()
    requests = tuple(benchmark_request(case, trials=args.trials, master_seed=args.master_seed,
                                      round_budget=args.round_budget) for case in CASES)
    root = Path(__file__).resolve().parents[1]
    before_hash = source_digest(root)
    measurements = []
    for case, request in zip(CASES, requests):
        print(f"Measuring {case}: {args.trials} trials, {args.repeats} timing repeats", flush=True)
        measurements.append(measure(request, repeats=args.repeats, top=args.top))
    if source_digest(root) != before_hash:
        raise RuntimeError("source files changed during measurement")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    changes = subprocess.run(["git", "status", "--porcelain", "--", "src", "tools"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
    if changes:
        revision += " (src/tools have uncommitted changes)"
    command = shlex.join([sys.executable, "-m", "tools.profile_m8", "--trials", str(args.trials),
        "--master-seed", str(args.master_seed), "--round-budget", str(args.round_budget),
        "--repeats", str(args.repeats), "--top", str(args.top), "--output", args.output.as_posix()])
    rendered = render_report(tuple(measurements), command=command, revision=revision, source_hash=before_hash)
    _write_report(args.output, rendered)
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
