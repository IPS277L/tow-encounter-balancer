"""Reproducible developer benchmark for the admitted M6 scenario, not an app CLI."""

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
from towr.domain.npc_melee_scenario_models import NpcMeleeActorPolicy, NpcMeleeScenario, NpcMeleeScenarioFacts
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_melee_models import SEED_SCHEME, NpcMeleeSimulationRequest, NpcMeleeSimulationResult
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


CASES = ((1, 1), (2, 2), (3, 2))


def benchmark_request(sizes: tuple[int, int], *, trials: int, master_seed: int,
                      round_budget: int) -> NpcMeleeSimulationRequest:
    """Footpad, GM Guide 1.1 / Allies and Antagonists / Footpad p97.

    Explicit stationary Close, aware opponents, ordinary outnumbering approved
    by the GM, Wound choice and GM-approved KO. Lurker is outside battle.
    """
    if sizes not in CASES:
        raise ValueError("benchmark supports only the declared 1x1, 2x2 and 3x2 cases")
    definition = NpcDefinition(
        "bench:footpad", "RULE-PROFILE-TALABEC-005", TargetInjuryPolicy.MINION, 1, ResilienceProfile(3),
        (NpcAttackProfile("dagger", "RULE-PROFILE-TALABEC-005:dagger", Skill.MELEE,
                          InlineProfile(3, 3), DamageProfile(2), Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),),
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-005:protection", Skill.ATHLETICS, InlineProfile(3, 3)),),
    )
    sides = tuple(CombatSide)
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        f"actor:{side_index}:{index}", definition.id, side, ProfileInjuryState(0, 1), ("dagger",),
        definition.resilience, True, False,
    )) for side_index, (side, size) in enumerate(zip(sides, sizes)) for index in range(size)))
    combat = CombatRoundState(1, roster.turn_participants, sides)
    current = NpcRoundRequest("benchmark:footpads", NpcRosterAttackState(roster), combat,
                              tuple(p.entity_id for p in combat.participants), ())
    spatial = SpatialBattleState(ZoneGraph(("arena", "exit"), (ZoneConnection("arena", "exit"),)), tuple(
        SpatialEntityPlacement(p.state.actor_id, p.state.side.value,
                               "arena") for p in roster.participants))
    policies = tuple(NpcMeleeActorPolicy(actor.state.actor_id,
        tuple(p.state.actor_id for p in roster.participants if p.state.side is not actor.state.side),
        tuple(MinionDefeatDecision(actor.state.actor_id, p.state.actor_id, NpcDefeatDisposition.KNOCKED_OUT, True)
              for p in roster.participants if p.state.side is not actor.state.side), outnumbering_bonus_approved=True) for actor in roster.participants)
    scenario = NpcMeleeScenario(
        NpcRoundsRequest(current, spatial, round_budget),
        NpcMeleeScenarioFacts(zone_id="arena", all_opponents_in_close_range=True, targets_aware=True,
            clear_line_of_sight=True, stationary=True, all_zone_combatants_included=True,
            unmounted_combatants_only=True, no_higher_ground=True, no_additional_rules=True,
            no_other_test_modifiers=True, can_leave_zone=True),
        policies, StaggerChoice.SUFFER_WOUND, sides[0],
        NpcDefeatObjective(tuple(p.state.actor_id for p in roster.participants if p.state.side is sides[1])),
    )
    return NpcMeleeSimulationRequest(scenario, master_seed, trials)


def trial_digest(result: NpcMeleeSimulationResult) -> str:
    rows = (f"{t.trial_index}|{t.seed}|{t.outcome.value}|{t.executed_attack_count}|{t.visited_round_count}"
            for t in result.trials)
    return sha256((SEED_SCHEME + "\n" + "\n".join(rows)).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Measurement:
    result: NpcMeleeSimulationResult
    summary: NpcMeleeSimulationSummary
    wall_seconds: tuple[float, ...]
    peak_python_bytes: int
    profile_cumulative: str
    profile_self: str
    profile_replace_callers: str


def run_batch(request: NpcMeleeSimulationRequest) -> tuple[NpcMeleeSimulationResult, NpcMeleeSimulationSummary]:
    result = run_npc_melee_simulation(request)
    return result, summarize_npc_melee_simulation(result)


def source_digest(root: Path) -> str:
    """Fingerprint actual Python sources and this harness, including untracked files."""
    paths = sorted((*root.joinpath("src").rglob("*.py"), root / "tools" / "profile_m6.py"),
                   key=lambda path: path.relative_to(root).as_posix())
    digest = sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def measure(request: NpcMeleeSimulationRequest, *, repeats: int = 3, top: int = 12) -> Measurement:
    if type(repeats) is not int or repeats < 1 or type(top) is not int or top < 1:
        raise ValueError("repeats and top must be positive integers")
    if tracemalloc.is_tracing() or sys.getprofile() is not None:
        raise RuntimeError("benchmark requires no active tracemalloc/profiler")
    # Imports, scenario construction and this small warm-up are outside measurement.
    run_batch(replace(request, trials=min(3, request.trials)))
    baseline = None
    timings = []
    for _ in range(repeats):
        gc.collect()
        start = perf_counter()
        observed = run_batch(request)
        timings.append(perf_counter() - start)
        if baseline is None:
            baseline = observed
        elif observed != baseline:
            raise ValueError("trial records changed between timing repeats")
        del observed

    gc.collect()
    tracemalloc.start()
    try:
        observed = run_batch(request)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    if observed != baseline:
        raise ValueError("trial records changed under tracemalloc")
    del observed

    gc.collect()
    profiler = cProfile.Profile()
    observed = profiler.runcall(run_batch, request)
    if observed != baseline:
        raise ValueError("trial records changed under cProfile")
    reports = []
    for order in ("cumulative", "tottime"):
        stream = StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(order).print_stats(top)
        reports.append(stream.getvalue().strip())
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_callers(r"dataclasses.py:.*\(replace\)")
    return Measurement(baseline[0], baseline[1], tuple(timings), peak, reports[0], reports[1], stream.getvalue().strip())


def render_report(measurements: tuple[Measurement, ...], *, command: str, revision: str, source_hash: str) -> str:
    lines = ["# M6 sequential benchmark baseline", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor() or 'not reported'}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Source/harness SHA-256: `{source_hash}`", f"Seed scheme: `{SEED_SCHEME}`", "",
        "```powershell", '$env:PYTHONPATH = "src"', command, "```", "",
        "Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. "
        "Wall repeats, tracemalloc and cProfile are separate runs; all trial records and aggregate summaries are compared for equality. Timed batch includes summary projection. "
        "Peak is incremental traced Python allocation during one batch, not process RSS; "
        "pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.", "",
        "| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for item in measurements:
        result = item.result
        source = result.source_request
        roster = source.scenario.initial.current.state.roster
        sizes = tuple(sum(p.state.side is side for p in roster.participants) for side in CombatSide)
        counts = item.summary.outcome_counts
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
    root = Path(__file__).resolve().parents[1]
    before_hash = source_digest(root)
    measurements = []
    for case, request in zip(CASES, requests):
        print(f"Measuring {case[0]}x{case[1]}: {args.trials} trials, {args.repeats} timing repeats", flush=True)
        measurements.append(measure(request, repeats=args.repeats, top=args.top))
    if source_digest(root) != before_hash:
        raise RuntimeError("source files changed during measurement")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    source_changes = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip()
    if source_changes:
        revision += " (src has uncommitted changes)"
    command = (f"py -{sys.version_info.major}.{sys.version_info.minor} tools/profile_m6.py --trials {args.trials} --master-seed {args.master_seed} "
               f"--round-budget {args.round_budget} --repeats {args.repeats} --top {args.top} "
               f'--output "{args.output.as_posix()}"')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(tuple(measurements), command=command, revision=revision, source_hash=before_hash), encoding="utf-8")
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
