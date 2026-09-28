"""Runnable typed M5 example; this text report is not a balance wire protocol."""

import argparse
from fractions import Fraction
import platform

from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.application.ranged_candidate_generation_models import (
    RangedCandidateGenerationRequest, RangedCandidateGenerationResult, RangedCompositionGroup,
)
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.application.ranged_staged_evaluation_service import evaluate_ranged_candidates_staged
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.ranged_staged_evaluation import ranged_continuation_candidate_ids
from towr.balance.ranged_staged_evaluation_models import RangedBalanceStage, RangedStagedEvaluationResult
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
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


def build_request() -> RangedCandidateGenerationRequest:
    # GM Guide 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, p97.
    # Numeric ranged excerpt only: no melee action or complete NPC catalogue.
    definition = NpcDefinition(
        "example:archer", "RULE-PROFILE-TALABEC-004", TargetInjuryPolicy.MINION, 1, ResilienceProfile(3, 1),
        (NpcAttackProfile("warbow", "RULE-PROFILE-TALABEC-004:warbow", Skill.SHOOTING,
                          InlineProfile(3, 3), DamageProfile(3), RangedWeaponRange.MEDIUM,
                          RangedWeaponRange.LONG, RangedWeaponHands.TWO_HANDED),),
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-004:protection", Skill.ATHLETICS, InlineProfile(3, 2)),),
    )
    perspective = CombatSide.PLAYERS_AND_ALLIES  # Side label; these actors are still Minions.
    opposition = CombatSide.OPPOSITION
    actor_specs = (("P1", perspective), ("P2", perspective),
                   ("A1", opposition), ("A2", opposition), ("B1", opposition))
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor_id, definition.id, side, ProfileInjuryState(0, 1), ("warbow",), definition.resilience, True, False,
    )) for actor_id, side in actor_specs))
    combat = CombatRoundState(1, roster.turn_participants, (perspective, opposition))
    current = NpcRoundRequest("example:reserve", NpcRosterAttackState(roster), combat,
                              tuple(actor_id for actor_id, _ in actor_specs), ())
    spatial = SpatialBattleState(
        ZoneGraph(("left", "right"), (ZoneConnection("left", "right"),)),
        tuple(SpatialEntityPlacement(actor_id, side.value, "left" if side is perspective else "right")
              for actor_id, side in actor_specs),
    )
    # Explicit authored example decisions, not approvals inferred by the generator.
    # GM Guide 1.1, Allies and Antagonists / Minions, p91: defeat is not necessarily death.
    policies = tuple(NpcRangedActorPolicy(
        actor_id, tuple(target for target, target_side in actor_specs if target_side is not side),
        tuple(MinionDefeatDecision(actor_id, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
              for target, target_side in actor_specs if target_side is not side),
    ) for actor_id, side in actor_specs)
    # These assertions apply to every generated composition and its full round budget.
    # PG 1.4, Rules / The Battlefield, p114: adjacency alone cannot prove visibility.
    facts = NpcRangedScenarioFacts(
        target_range=RangedWeaponRange.MEDIUM, has_enemy_in_close_range=False, targets_aware=True,
        clear_line_of_sight=True, stationary=True, unmodified_tests=True, no_additional_rules=True,
        ammunition_sufficient=True, requires_reload_action=False,
    )
    template = NpcRangedScenario(NpcRoundsRequest(current, spatial, 3), facts, policies,
                                 StaggerChoice.SUFFER_WOUND, perspective, NpcDefeatObjective(("A1", "A2", "B1")))
    return RangedCandidateGenerationRequest(
        template_scenario=template,
        groups=(RangedCompositionGroup("A", ("A1", "A2"), 0, 2), RangedCompositionGroup("B", ("B1",), 0, 1)),
        facts=facts, candidate_id_prefix="example", max_candidates=5, master_seed=42,
        stages=(RangedBalanceStage(8, 3), RangedBalanceStage(32, 2)), max_total_trials=136,
        window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    )


def format_report(generated: RangedCandidateGenerationResult, result: RangedStagedEvaluationResult) -> str:
    if result.source_request != generated.evaluation_request:
        raise ValueError("example report requires the exact generated evaluation input")
    source = generated.source_request
    window = source.window
    lines = [
        f"runtime: {platform.python_implementation()} {platform.python_version()}",
        f"seed: {source.master_seed}; scheme: {result.seed_scheme}",
        "scope: stationary numeric ranged Minions; fixed P1,P2; reserves A1,A2 / B1",
        f"round_budget: {source.template_scenario.initial.max_rounds}; perspective: {source.template_scenario.perspective_side.value}",
        f"window: [{window.minimum}, {window.maximum}]; target: {window.target}; final_top_k: {source.stages[-1].keep}",
        f"candidates: {source.candidate_count}; max_candidates: {source.max_candidates}",
        f"planned_trials: {source.planned_trials}; max_total_trials: {source.max_total_trials}",
    ]
    compositions = {}
    for candidate in generated.evaluation_request.candidates:
        actors = set(candidate.scenario.objective.target_actor_ids)
        compositions[candidate.candidate_id] = ",".join(
            f"{group.group_id}={sum(actor in actors for actor in group.actor_ids)}" for group in source.groups)
    for index, stage in enumerate(result.stage_reports):
        lines.append(f"stage {index + 1}: trials_per_candidate={stage.source_request.trials_per_candidate} "
                     f"keep={stage.source_request.top_k} total_trials={stage.total_trials}")
        for row in stage.candidates:
            assessment = row.assessment
            counts = assessment.summary.outcome_counts
            match = "unsupported" if assessment.window_match is None else "yes" if assessment.window_match else "no"
            lines.append(f"  {row.candidate_id} ({compositions[row.candidate_id]}): "
                         f"objective={counts.objective_achieved} side_defeated={counts.side_defeated} "
                         f"round_limit={counts.round_limit} unsupported_path={counts.unsupported_path} "
                         f"rate={assessment.objective_achieved_rate} window={match}")
        if index + 1 < len(source.stages):
            lines.append("  continue: " + (", ".join(ranged_continuation_candidate_ids(stage)) or "(none)"))
    lines.extend((f"status: {result.status.value}", f"actual_trials: {result.total_trials}",
                  "final_selected: " + (", ".join(result.selected_candidate_ids) or "(none)")))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("sequential", "process"), default="sequential")
    args = parser.parse_args()
    options = (SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL) if args.mode == "sequential"
               else SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=4))
    generated = generate_ranged_candidates(build_request())
    result = evaluate_ranged_candidates_staged(generated.evaluation_request, options)
    print(f"execution: {args.mode}" + (" workers=2 batch_size=4" if args.mode == "process" else ""))
    print(format_report(generated, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
