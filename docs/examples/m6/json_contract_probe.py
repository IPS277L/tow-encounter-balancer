"""Finite ADR-0027 mapping probe, NOT a strict parser, encoder or Schema validator.

Only the two authored fixtures are mapped. Production wire admission is future
work. --write-examples refreshes their observed result files with this runtime.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
from pathlib import Path
import json
import platform
import sys

from melee_scenario import build_scenario
from melee_balance import build_request
from towr import __version__
from towr.application.melee_candidate_generation import generate_melee_candidates
from towr.application.melee_candidate_generation_models import MeleeCandidateGenerationRequest, MeleeCompositionGroup
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.melee_staged_evaluation import melee_continuation_candidate_ids
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_melee_scenario_models import NpcMeleeActorPolicy, NpcMeleeScenario, NpcMeleeScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest, SEED_SCHEME
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation

DIRECTORY = Path(__file__).parent / "json"


def scenario_document(scenario):
    """Describe known typed fixtures; no lossless/unknown-field boundary guards."""
    definitions = {p.definition.id: p.definition for p in scenario.initial.current.state.roster.participants}
    return {
        "definitions": [{"id": d.id, "source_rule_id": d.source_rule_id, "resilience": asdict(d.resilience),
            "attack": {"id": d.attacks[0].id, "source_rule_id": d.attacks[0].source_rule_id,
                       "dice": d.attacks[0].test_profile.dice, "threshold": d.attacks[0].test_profile.threshold,
                       "damage": d.attacks[0].damage.base, "hands": d.attacks[0].hands.value},
            "protection": {"source_rule_id": d.protection[0].source_rule_id, "skill": d.protection[0].skill.value,
                           "dice": d.protection[0].test_profile.dice, "threshold": d.protection[0].test_profile.threshold}}
            for d in definitions.values()],
        "actors": [{"id": p.state.actor_id, "definition_id": p.definition.id, "side": p.state.side.value,
                    "zone_id": scenario.initial.spatial_state.placement_for(p.state.actor_id).zone_id}
                   for p in scenario.initial.current.state.roster.participants],
        "battlefield": {"zone_ids": list(scenario.initial.spatial_state.graph.zone_ids),
                        "connections": [asdict(c) for c in scenario.initial.spatial_state.graph.connections]},
        "side_order": [s.value for s in scenario.initial.current.round_state.side_order],
        "actor_order": list(scenario.initial.current.actor_order), "perspective_side": scenario.perspective_side.value,
        "objective_target_ids": list(scenario.objective.target_actor_ids), "facts": asdict(scenario.facts),
        "repeated_stagger_choice": scenario.repeated_stagger_choice.value,
        "actor_policies": [{"actor_id": p.actor_id, "outnumbering_bonus_approved": p.outnumbering_bonus_approved,
            "targets": [{"target_id": d.target_id, "disposition": d.disposition.value, "gm_approved": d.gm_approved}
                        for d in p.defeat_decisions]} for p in scenario.actor_policies],
    }


def map_scenario(data, initial_id, rounds):
    """Map fixture fields through public constructors, not arbitrary JSON admission."""
    definitions = {}
    for d in data["definitions"]:
        a, p = d["attack"], d["protection"]
        definitions[d["id"]] = NpcDefinition(d["id"], d["source_rule_id"], TargetInjuryPolicy.MINION, 1,
            ResilienceProfile(**d["resilience"]),
            (NpcAttackProfile(a["id"], a["source_rule_id"], Skill.MELEE, InlineProfile(a["dice"], a["threshold"]),
                              DamageProfile(a["damage"]), Range.CLOSE, Range.CLOSE, Hands(a["hands"])),),
            (NpcProtectionProfile(p["source_rule_id"], Skill(p["skill"]), InlineProfile(p["dice"], p["threshold"])),))
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definitions[a["definition_id"]], NpcParticipantState(
        a["id"], a["definition_id"], CombatSide(a["side"]), ProfileInjuryState(0, 1),
        (definitions[a["definition_id"]].attacks[0].id,), definitions[a["definition_id"]].resilience, True, False,
    )) for a in data["actors"]))
    current = NpcRoundRequest(initial_id, NpcRosterAttackState(roster), CombatRoundState(
        1, roster.turn_participants, tuple(CombatSide(s) for s in data["side_order"])), tuple(data["actor_order"]), ())
    spatial = SpatialBattleState(ZoneGraph(tuple(data["battlefield"]["zone_ids"]), tuple(
        ZoneConnection(**c) for c in data["battlefield"]["connections"])), tuple(
        SpatialEntityPlacement(a["id"], a["side"], a["zone_id"]) for a in data["actors"]))
    policies = tuple(NpcMeleeActorPolicy(p["actor_id"], tuple(t["target_id"] for t in p["targets"]), tuple(
        MinionDefeatDecision(p["actor_id"], t["target_id"], NpcDefeatDisposition(t["disposition"]), t["gm_approved"])
        for t in p["targets"]), p["outnumbering_bonus_approved"]) for p in data["actor_policies"])
    return NpcMeleeScenario(NpcRoundsRequest(current, spatial, rounds), NpcMeleeScenarioFacts(**data["facts"]), policies,
        StaggerChoice(data["repeated_stagger_choice"]), CombatSide(data["perspective_side"]),
        NpcDefeatObjective(tuple(data["objective_target_ids"])))


def map_balance(data):
    r, g, e = data["reserve"], data["generation"], data["evaluation"]
    return MeleeCandidateGenerationRequest(map_scenario(r["scenario"], r["initial_request_id"], r["round_budget"]),
        tuple(MeleeCompositionGroup(**v) for v in g["groups"]), NpcMeleeScenarioFacts(**g["facts"]),
        g["candidate_id_prefix"], g["max_candidates"], int(e["master_seed"]),
        tuple(MeleeBalanceStage(**v) for v in e["stages"]), e["max_total_trials"],
        ObjectiveRateWindow(*(Fraction(**e["window"][k]) for k in ("minimum", "target", "maximum"))))


def fraction_document(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def summary_document(summary):
    return {"trials": summary.trials, "outcome_counts": asdict(summary.outcome_counts),
            "total_attack_count": summary.total_attack_count, "total_visited_round_count": summary.total_visited_round_count,
            "mean_attack_count": summary.mean_attack_count, "mean_visited_round_count": summary.mean_visited_round_count}


def main():
    if sys.argv[1:] not in ([], ["--write-examples"]):
        raise SystemExit("usage: json_contract_probe.py [--write-examples]")
    sim = json.loads((DIRECTORY / "melee-simulation-v1.request.json").read_text(encoding="utf-8"))
    bal = json.loads((DIRECTORY / "melee-balance-v1.request.json").read_text(encoding="utf-8"))
    before = deepcopy((sim, bal))
    scenario = map_scenario(sim["scenario"], sim["request_id"], sim["simulation"]["round_budget"])
    assert scenario == build_scenario()
    assert scenario_document(scenario) == sim["scenario"]
    source = map_balance(bal)
    expected = replace(build_request(), stages=(MeleeBalanceStage(2, 2), MeleeBalanceStage(4, 1)), max_total_trials=18)
    assert source == expected and scenario_document(source.template_scenario) == bal["reserve"]["scenario"]
    sim_request = NpcMeleeSimulationRequest(scenario, int(sim["simulation"]["master_seed"]), sim["simulation"]["trials"])
    seq = run_npc_melee_simulation(sim_request)
    proc = run_npc_melee_simulation_parallel(sim_request, workers=2, batch_size=3)
    assert seq == proc
    summary = summarize_npc_melee_simulation(seq)
    generated = generate_melee_candidates(source)
    staged = evaluate_melee_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
    parallel = evaluate_melee_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
    assert staged == parallel
    # Finite semantic failures. Strict tokens/unknown fields/Schema/errors are
    # deliberately NOT implemented or claimed by this contract probe.
    negatives = []
    for field, value in (("all_opponents_in_close_range", False), ("all_zone_combatants_included", False)):
        changed = deepcopy(sim["scenario"]); changed["facts"][field] = value
        negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 3))
    changed = deepcopy(sim["scenario"]); changed["side_order"].reverse()
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 3))
    changed = deepcopy(sim["scenario"]); changed["actor_policies"][0]["targets"][0]["gm_approved"] = False
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 3))
    for field, value in (("max_candidates", 4), ("facts", dict(bal["generation"]["facts"], zone_id="exit"))):
        changed = deepcopy(bal); changed["generation"][field] = value
        negatives.append(lambda d=changed: map_balance(d))
    changed = deepcopy(bal); changed["evaluation"]["max_total_trials"] = 17
    negatives.append(lambda d=changed: map_balance(d))
    for construct in negatives:
        try: construct()
        except (TypeError, ValueError): pass
        else: raise AssertionError("invalid fixture admitted")
    assert (sim, bal) == before
    runtime = {"package_version": __version__, "python_implementation": platform.python_implementation(),
               "python_version": platform.python_version(), "rng": "random.Random"}
    simulation_output = {"schema_version": "1", "kind": "npc_melee_simulation_result", "request": sim,
                         "seed_scheme": SEED_SCHEME, "runtime": runtime, "summary": summary_document(summary)}
    vectors = [v for v in product(*(range(g.minimum_count, g.maximum_count+1) for g in source.groups)) if any(v)]
    reports = []
    for index, report in enumerate(staged.stage_reports):
        rows = []
        for row in report.candidates:
            a = row.assessment
            rows.append({"candidate_id": row.candidate_id, "summary": summary_document(a.summary),
                         "rates": {k: fraction_document(getattr(a, k+"_rate"))
                                   for k in asdict(a.summary.outcome_counts)},
                         "status": a.status.value, "window_match": a.window_match})
        reports.append({"stage_index": index, "trials_per_candidate": source.stages[index].trials_per_candidate,
                        "keep": source.stages[index].keep, "total_trials": report.total_trials, "candidates": rows,
                        "selected_candidate_ids": list(report.selected_candidate_ids), "continuation_candidate_ids":
                        list(melee_continuation_candidate_ids(report)) if index < len(source.stages)-1 else []})
    balance_output = {"schema_version": "1", "kind": "npc_melee_balance_result", "request": bal,
                      "seed_scheme": SEED_SCHEME, "runtime": runtime, "candidate_count": source.candidate_count,
                      "planned_trials": source.planned_trials, "total_trials": staged.total_trials,
                      "candidates": [{"candidate_id": c.candidate_id, "counts": list(v)}
                                     for c, v in zip(generated.evaluation_request.candidates, vectors, strict=True)],
                      "stage_reports": reports, "status": staged.status.value,
                      "selected_candidate_ids": list(staged.selected_candidate_ids)}
    for name, output in (("melee-simulation", simulation_output), ("melee-balance", balance_output)):
        encoded = json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        assert json.loads(encoded) == output
        if sys.argv[1:]: (DIRECTORY / (name + "-v1.result.json")).write_text(encoded, encoding="utf-8")
    print(f"exact fixture mapping; simulation {summary.trials} trials, balance planned/actual={source.planned_trials}/{staged.total_trials}")
    print(f"full sequential/process results equal; {len(negatives)} semantic rejections; sources unchanged")
    print("contract probe only: no Melee production Schema/parser/encoder/CLI or lexical validation")


if __name__ == "__main__":
    main()
