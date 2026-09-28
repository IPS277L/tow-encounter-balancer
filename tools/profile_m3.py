"""Reproducible developer benchmark for the admitted M3 scenario, not an app CLI."""

from __future__ import annotations

import argparse
import cProfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import gc
from hashlib import sha256
from io import StringIO
from pathlib import Path
import platform
import pstats
from statistics import median
import subprocess
import sys
from time import perf_counter
import tracemalloc

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_ranged_scenario_models import NpcRangedActorPolicy, NpcRangedScenario, NpcRangedScenarioFacts
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_ranged_models import SEED_SCHEME, NpcRangedSimulationRequest, NpcRangedSimulationResult
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation


CASES = ((1, 1), (2, 2), (3, 2))


def benchmark_request(sizes: tuple[int, int], *, trials: int, master_seed: int,
                      round_budget: int) -> NpcRangedSimulationRequest:
    """Numeric Warbow excerpt, GM Guide 1.1 / Brigands & Footpads p97.

    No test-module imports or full canonical Brigand claim. All facts/policies
    are fixed: Medium, awareness, stationary, Wound choice and GM-approved KO.
    """
    if sizes not in CASES:
        raise ValueError("benchmark supports only the declared 1x1, 2x2 and 3x2 cases")
    definition = NpcDefinition(
        "bench:archer", "RULE-PROFILE-TALABEC-004", TargetInjuryPolicy.MINION, 1, ResilienceProfile(3, 1),
        (NpcAttackProfile("warbow", "RULE-PROFILE-TALABEC-004:warbow", Skill.SHOOTING,
                          InlineProfile(3, 3), DamageProfile(3), Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),),
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-004:protection", Skill.ATHLETICS, InlineProfile(3, 2)),),
    )
    sides = tuple(CombatSide)
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        f"actor:{side_index}:{index}", definition.id, side, ProfileInjuryState(0, 1), ("warbow",),
        definition.resilience, True, False,
    )) for side_index, (side, size) in enumerate(zip(sides, sizes)) for index in range(size)))
    combat = CombatRoundState(1, roster.turn_participants, sides)
    current = NpcRoundRequest("benchmark:archers", NpcRosterAttackState(roster), combat,
                              tuple(p.entity_id for p in combat.participants), ())
    spatial = SpatialBattleState(ZoneGraph(("left", "right"), (ZoneConnection("left", "right"),)), tuple(
        SpatialEntityPlacement(p.state.actor_id, p.state.side.value,
                               "left" if p.state.side is sides[0] else "right") for p in roster.participants))
    policies = tuple(NpcRangedActorPolicy(actor.state.actor_id,
        tuple(p.state.actor_id for p in roster.participants if p.state.side is not actor.state.side),
        tuple(MinionDefeatDecision(actor.state.actor_id, p.state.actor_id, NpcDefeatDisposition.KNOCKED_OUT, True)
              for p in roster.participants if p.state.side is not actor.state.side)) for actor in roster.participants)
    scenario = NpcRangedScenario(
        NpcRoundsRequest(current, spatial, round_budget),
        NpcRangedScenarioFacts(target_range=Range.MEDIUM, has_enemy_in_close_range=False, targets_aware=True,
            clear_line_of_sight=True, stationary=True, unmodified_tests=True, no_additional_rules=True,
            ammunition_sufficient=True, requires_reload_action=False),
        policies, StaggerChoice.SUFFER_WOUND, sides[0],
        NpcDefeatObjective(tuple(p.state.actor_id for p in roster.participants if p.state.side is sides[1])),
    )
    return NpcRangedSimulationRequest(scenario, master_seed, trials)


def trial_digest(result: NpcRangedSimulationResult) -> str:
    rows = (f"{t.trial_index}|{t.seed}|{t.outcome.value}|{t.executed_attack_count}|{t.visited_round_count}"
            for t in result.trials)
    return sha256((SEED_SCHEME + "\n" + "\n".join(rows)).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Measurement:
    result: NpcRangedSimulationResult
    wall_seconds: tuple[float, ...]
    peak_python_bytes: int
    profile_cumulative: str
    profile_self: str
    profile_replace_callers: str


def measure(request: NpcRangedSimulationRequest, *, repeats: int = 3, top: int = 12) -> Measurement:
    if type(repeats) is not int or repeats < 1 or type(top) is not int or top < 1:
        raise ValueError("repeats and top must be positive integers")
    if tracemalloc.is_tracing() or sys.getprofile() is not None:
        raise RuntimeError("benchmark requires no active tracemalloc/profiler")
    # Imports, scenario construction and this small warm-up are outside measurement.
    run_npc_ranged_simulation(replace(request, trials=min(3, request.trials)))
    baseline = None
    timings = []
    for _ in range(repeats):
        gc.collect()
        start = perf_counter()
        observed = run_npc_ranged_simulation(request)
        timings.append(perf_counter() - start)
        if baseline is None:
            baseline = observed
        elif observed != baseline:
            raise ValueError("trial records changed between timing repeats")
        del observed

    gc.collect()
    tracemalloc.start()
    try:
        observed = run_npc_ranged_simulation(request)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    if observed != baseline:
        raise ValueError("trial records changed under tracemalloc")
    del observed

    gc.collect()
    profiler = cProfile.Profile()
    observed = profiler.runcall(run_npc_ranged_simulation, request)
    if observed != baseline:
        raise ValueError("trial records changed under cProfile")
    reports = []
    for order in ("cumulative", "tottime"):
        stream = StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(order).print_stats(top)
        reports.append(stream.getvalue().strip())
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_callers(r"dataclasses.py:.*\(replace\)")
    return Measurement(baseline, tuple(timings), peak, reports[0], reports[1], stream.getvalue().strip())


def render_report(measurements: tuple[Measurement, ...], *, command: str, revision: str) -> str:
    lines = ["# M3 sequential benchmark baseline", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor() or 'not reported'}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Seed scheme: `{SEED_SCHEME}`", "",
        "```powershell", '$env:PYTHONPATH = "src"', command, "```", "",
        "Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. "
        "Wall repeats, tracemalloc and cProfile are separate runs; all trial records are compared for equality. "
        "Peak is incremental traced Python allocation during one batch, not process RSS; "
        "pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.", "",
        "| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for item in measurements:
        result = item.result
        source = result.source_request
        roster = source.scenario.initial.current.state.roster
        sizes = tuple(sum(p.state.side is side for p in roster.participants) for side in CombatSide)
        counts = result.outcome_counts
        label = f"{sizes[0]}x{sizes[1]}"
        lines.append(f"| {label} | {source.trials} | {source.master_seed} | {source.scenario.initial.max_rounds} | "
            + ", ".join(f"{value:.6f}" for value in item.wall_seconds)
            + f" | {median(item.wall_seconds):.6f} | {item.peak_python_bytes / 1024:.1f} | "
            + f"{counts.objective_achieved}/{counts.side_defeated}/{counts.round_limit}/{counts.unsupported_path} | "
            + f"{result.total_attack_count} | {result.total_visited_round_count} |")
    for item in measurements:
        size = len(item.result.source_request.scenario.initial.current.actor_order)
        lines.extend(["", f"## Profile: {size} actors", "", f"Trial-record SHA-256: `{trial_digest(item.result)}`", "",
                      "Cumulative time:", "", "```text", item.profile_cumulative, "```", "",
                      "Self time:", "", "```text", item.profile_self, "```", "",
                      "dataclasses.replace callers:", "", "```text", item.profile_replace_callers, "```"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--master-seed", type=int, default=20260928)
    parser.add_argument("--round-budget", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Validate all requests before running any benchmark.
    requests = tuple(benchmark_request(case, trials=args.trials, master_seed=args.master_seed,
                                      round_budget=args.round_budget) for case in CASES)
    measurements = []
    for case, request in zip(CASES, requests):
        print(f"Measuring {case[0]}x{case[1]}: {args.trials} trials, {args.repeats} timing repeats", flush=True)
        measurements.append(measure(request, repeats=args.repeats, top=args.top))
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    source_changes = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip()
    if source_changes:
        revision += " (src has uncommitted changes)"
    command = (f"py -{sys.version_info.major}.{sys.version_info.minor} tools/profile_m3.py --trials {args.trials} --master-seed {args.master_seed} "
               f"--round-budget {args.round_budget} --repeats {args.repeats} --top {args.top} "
               f'--output "{args.output.as_posix()}"')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(tuple(measurements), command=command, revision=revision), encoding="utf-8")
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
