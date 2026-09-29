"""Reproducible developer benchmark for the admitted M7 scenario, not an app CLI."""

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
from towr.domain.npc_mixed_scenario_models import NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_mixed_models import SEED_SCHEME, NpcMixedSimulationRequest, NpcMixedSimulationResult
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


CASES = ((2, 1), (3, 2), (2, 2))


def benchmark_request(sizes: tuple[int, int], *, trials: int, master_seed: int,
                      round_budget: int) -> NpcMixedSimulationRequest:
    """Explicit numeric Footpad/Dagger and Brigand/Warbow, GM1.1 pp91,93,97.

    PG1.4 Equipment p94; Rules pp114,118-119. Stationary Close/Medium,
    aware targets, GM-approved outnumbering/KO, no movement, Wound choice.
    """
    if sizes not in CASES:
        raise ValueError("benchmark supports only the declared 2x1, 3x2 and 2x2 cases")
    two_archers = sizes == (2, 2)
    # Only the bow profile is used for Brigand: no Axe/Craven Opportunist path.
    melee = NpcDefinition(
        "footpad:dagger", "BOOK-GM-GUIDE:1.1:p97:footpad", TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3),
        (NpcAttackProfile("dagger", "BOOK-GM-GUIDE:1.1:p97:dagger", Skill.MELEE,
                          InlineProfile(3, 3), DamageProfile(2), Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),),
        (NpcProtectionProfile("BOOK-GM-GUIDE:1.1:p97:footpad:athletics", Skill.ATHLETICS, InlineProfile(3, 3)),),
    )
    bow = NpcDefinition(
        "brigand:warbow", "BOOK-GM-GUIDE:1.1:p97:brigand", TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3, 1),
        (NpcAttackProfile("warbow", "BOOK-GM-GUIDE:1.1:p97:warbow", Skill.SHOOTING,
                          InlineProfile(3, 3), DamageProfile(3), Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),),
        (NpcProtectionProfile("BOOK-GM-GUIDE:1.1:p97:brigand:athletics", Skill.ATHLETICS, InlineProfile(3, 2)),),
    )
    allies, opposition = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    # Both sides contain Minions, including the side called players_and_allies.
    actors = [("Pbow", allies, bow, "rear"), ("P1", allies, melee, "arena")]
    if sizes == (3, 2):
        actors.append(("P2", allies, melee, "arena"))
    actors.append(("E1", opposition, melee, "arena"))
    if sizes[1] == 2:
        actors.append(("E2", opposition, bow if two_archers else melee, "far" if two_archers else "arena"))
    roster = NpcRoster(tuple(NpcParticipantSnapshot(profile, NpcParticipantState(
        actor_id, profile.id, side, ProfileInjuryState(0, 1), (profile.attacks[0].id,),
        profile.resilience, True, False,
    )) for actor_id, side, profile, _ in actors))
    current = NpcRoundRequest("benchmark:mixed", NpcRosterAttackState(roster),
                              CombatRoundState(1, roster.turn_participants),
                              tuple(actor_id for actor_id, _, _, _ in actors), ())
    spatial = SpatialBattleState(
        ZoneGraph(("rear", "arena", "far"), (ZoneConnection("rear", "arena"),
                  ZoneConnection("arena", "far"), ZoneConnection("rear", "far"))),
        tuple(SpatialEntityPlacement(actor_id, side.value, zone) for actor_id, side, _, zone in actors),
    )
    # Authored reach facts: sharing a Zone alone does not establish Close.
    pairs = [("Pbow", "E1", Range.MEDIUM), ("P1", "E1", Range.CLOSE)]
    if sizes[1] == 2:
        pairs += [("Pbow", "E2", Range.MEDIUM),
                  ("P1", "E2", Range.MEDIUM if two_archers else Range.CLOSE)]
    if sizes == (3, 2):
        pairs += [("P2", "E1", Range.CLOSE), ("P2", "E2", Range.CLOSE)]
    facts = NpcMixedScenarioFacts(
        targets_aware=True, clear_line_of_sight=True, stationary=True,
        all_zone_combatants_included=True, unmounted_combatants_only=True, no_higher_ground=True,
        no_additional_rules=True, no_other_test_modifiers=True,
        ammunition_sufficient=True, requires_reload_action=False,
    )
    policies = tuple(NpcMixedActorPolicy(
        actor_id, tuple(target for target, target_side, _, _ in actors if target_side is not side),
        tuple(MinionDefeatDecision(actor_id, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
              for target, target_side, _, _ in actors if target_side is not side),
        outnumbering_bonus_approved=True, can_leave_zone=False,
    ) for actor_id, side, _, _ in actors)
    scenario = NpcMixedScenario(
        NpcRoundsRequest(current, spatial, round_budget), facts, tuple(NpcMixedPairRange(*pair) for pair in pairs), policies,
        StaggerChoice.SUFFER_WOUND, allies,
        NpcDefeatObjective(tuple(actor_id for actor_id, side, _, _ in actors if side is opposition)),
    )
    return NpcMixedSimulationRequest(scenario, master_seed, trials)


def trial_digest(result: NpcMixedSimulationResult) -> str:
    rows = (f"{t.trial_index}|{t.seed}|{t.outcome.value}|{t.executed_attack_count}|{t.visited_round_count}"
            for t in result.trials)
    return sha256((SEED_SCHEME + "\n" + "\n".join(rows)).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Measurement:
    result: NpcMixedSimulationResult
    summary: NpcMixedSimulationSummary
    wall_seconds: tuple[float, ...]
    peak_python_bytes: int
    profile_cumulative: str
    profile_self: str
    profile_replace_callers: str


def run_batch(request: NpcMixedSimulationRequest) -> tuple[NpcMixedSimulationResult, NpcMixedSimulationSummary]:
    result = run_npc_mixed_simulation(request)
    return result, summarize_npc_mixed_simulation(result)


def source_digest(root: Path) -> str:
    """Fingerprint actual Python sources and this harness, including untracked files."""
    paths = sorted((*root.joinpath("src").rglob("*.py"), root / "tools" / "profile_m7.py"),
                   key=lambda path: path.relative_to(root).as_posix())
    digest = sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def measure(request: NpcMixedSimulationRequest, *, repeats: int = 3, top: int = 12) -> Measurement:
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
    lines = ["# M7 sequential benchmark baseline", "",
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        f"Runtime: {platform.python_implementation()} {platform.python_version()}; {platform.platform()}",
        f"Processor: {platform.processor() or 'not reported'}; GC enabled: {gc.isenabled()}",
        f"Source revision: `{revision}`", f"Source/harness SHA-256: `{source_hash}`", f"Seed scheme: `{SEED_SCHEME}`", "",
        "```powershell", '$env:PYTHONPATH = "src"', command, "```", "",
        "Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. "
        "Wall repeats, tracemalloc and cProfile are separate runs; all trial records and aggregate summaries are compared for equality. Timed batch includes summary projection. "
        "Peak is incremental traced Python allocation during one batch, not process RSS; "
        "pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.", "",
        "Fixtures: 2x1 = Pbow@rear, P1/E1@arena; 3x2 = Pbow@rear, P1/P2/E1/E2@arena; "
        "2x2 = Pbow@rear, P1/E1@arena, E2bow@far. Side/actor order as listed (allies first); "
        "target priority is opposing roster order. All enemy pairs involving a bow are explicitly Medium, "
        "all other enemy pairs explicitly Close; rear/arena/far are mutually adjacent. "
        "Numeric profiles: Footpad Dagger 3d/3 Dam2 RES3 Athletics 3d/3; "
        "Brigand Warbow 3d/3 Dam3 RES4 Athletics 3d/2. GM1.1 Allies and Antagonists pp91,93,97; "
        "PG1.4 Equipment p94; Rules pp114,118-119. GM-approved KO/outnumbering, "
        "can_leave_zone=False, repeated Staggered chooses Wound. Aware, clear sight, stationary, "
        "unmounted, complete zone roster, no higher ground/other modifiers/additional rules, "
        "sufficient ammunition, no reload action. All four outcomes count; unsupported is a technical stop, "
        "not a defeat. These are fixed numeric projections, not full NPC catalogue support.", "",
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
    parser.add_argument("--master-seed", type=int, default=20260929)
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
    command = (f'& "{sys.executable}" tools/profile_m7.py --trials {args.trials} --master-seed {args.master_seed} '
               f"--round-budget {args.round_budget} --repeats {args.repeats} --top {args.top} "
               f'--output "{args.output.as_posix()}"')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(tuple(measurements), command=command, revision=revision, source_hash=before_hash), encoding="utf-8")
    print(f"Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
