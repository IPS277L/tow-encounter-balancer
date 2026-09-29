"""Finite ADR-0034 mapping probe, NOT a strict parser, encoder or Schema validator.

Only the two authored fixtures are mapped. Production wire admission is future
work. --write-examples refreshes their observed result files with this runtime.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
from multiprocessing import active_children
from random import getstate
from pathlib import Path
import json
import platform
import sys

from mixed_scenario import build_scenario
from mixed_balance import build_request
from towr import __version__
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
from towr.application.mixed_candidate_generation_models import MixedCandidateGenerationRequest, MixedCompositionGroup
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.mixed_staged_evaluation import mixed_continuation_candidate_ids
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_mixed_scenario_models import NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts
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
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest, SEED_SCHEME
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation

DIRECTORY = Path(__file__).parent / "json"


def scenario_document(scenario):
    """Describe known typed fixtures; no lossless/unknown-field boundary guards."""
    definitions = {p.definition.id: p.definition for p in scenario.initial.current.state.roster.participants}
    return {
        "definitions": [{"id": d.id, "source_rule_id": d.source_rule_id, "resilience": asdict(d.resilience),
            "attack": {"id": d.attacks[0].id, "source_rule_id": d.attacks[0].source_rule_id,
                       "skill": d.attacks[0].skill.value, "range_min": d.attacks[0].range_min.value,
                       "range_max": d.attacks[0].range_max.value, "dice": d.attacks[0].test_profile.dice, "threshold": d.attacks[0].test_profile.threshold,
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
        "pair_ranges": [dict(first_actor_id=p.first_actor_id, second_actor_id=p.second_actor_id,
                             target_range=p.target_range.value) for p in scenario.pair_ranges],
        "repeated_stagger_choice": scenario.repeated_stagger_choice.value,
        "actor_policies": [{"actor_id": p.actor_id, "outnumbering_bonus_approved": p.outnumbering_bonus_approved,
            "can_leave_zone": p.can_leave_zone,
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
            (NpcAttackProfile(a["id"], a["source_rule_id"], Skill(a["skill"]), InlineProfile(a["dice"], a["threshold"]),
                              DamageProfile(a["damage"]), Range(a["range_min"]), Range(a["range_max"]), Hands(a["hands"])),),
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
    policies = tuple(NpcMixedActorPolicy(p["actor_id"], tuple(t["target_id"] for t in p["targets"]), tuple(
        MinionDefeatDecision(p["actor_id"], t["target_id"], NpcDefeatDisposition(t["disposition"]), t["gm_approved"])
        for t in p["targets"]), p["outnumbering_bonus_approved"], p["can_leave_zone"]) for p in data["actor_policies"])
    return NpcMixedScenario(NpcRoundsRequest(current, spatial, rounds), NpcMixedScenarioFacts(**data["facts"]), map_pairs(data["pair_ranges"]), policies,
        StaggerChoice(data["repeated_stagger_choice"]), CombatSide(data["perspective_side"]),
        NpcDefeatObjective(tuple(data["objective_target_ids"])))


def map_pairs(data):
    return tuple(NpcMixedPairRange(p["first_actor_id"], p["second_actor_id"], Range(p["target_range"])) for p in data)


def map_balance(data):
    r, g, e = data["reserve"], data["generation"], data["evaluation"]
    return MixedCandidateGenerationRequest(map_scenario(r["scenario"], r["initial_request_id"], r["round_budget"]),
        tuple(MixedCompositionGroup(**v) for v in g["groups"]), NpcMixedScenarioFacts(**g["facts"]),
        map_pairs(g["pair_ranges"]), g["candidate_id_prefix"], g["max_candidates"], int(e["master_seed"]),
        tuple(MixedBalanceStage(**v) for v in e["stages"]), e["max_total_trials"],
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
    sim = json.loads((DIRECTORY / "mixed-simulation-v1.request.json").read_text(encoding="utf-8"))
    bal = json.loads((DIRECTORY / "mixed-balance-v1.request.json").read_text(encoding="utf-8"))
    before = deepcopy((sim, bal))
    rng_before, children_before = getstate(), {c.pid for c in active_children()}
    scenario = map_scenario(sim["scenario"], sim["request_id"], sim["simulation"]["round_budget"])
    assert scenario == build_scenario()
    assert scenario_document(scenario) == sim["scenario"]
    source = map_balance(bal)
    expected = replace(build_request(), stages=(MixedBalanceStage(2, 2), MixedBalanceStage(4, 1)), max_total_trials=16)
    assert source == expected and scenario_document(source.template_scenario) == bal["reserve"]["scenario"]
    sim_request = NpcMixedSimulationRequest(scenario, int(sim["simulation"]["master_seed"]), sim["simulation"]["trials"])
    seq = run_npc_mixed_simulation(sim_request)
    proc = run_npc_mixed_simulation_parallel(sim_request, workers=2, batch_size=3)
    assert seq == proc
    summary = summarize_npc_mixed_simulation(seq)
    generated = generate_mixed_candidates(source)
    staged = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
    parallel = evaluate_mixed_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
    assert staged == parallel
    # Finite semantic failures. Strict tokens/unknown fields/Schema/errors are
    # deliberately NOT implemented or claimed by this contract probe.
    negatives = []
    for field in ("targets_aware", "all_zone_combatants_included", "ammunition_sufficient"):
        changed = deepcopy(sim["scenario"]); changed["facts"][field] = False
        negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    changed = deepcopy(sim["scenario"]); changed["side_order"].reverse()
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    changed = deepcopy(sim["scenario"]); changed["actor_policies"][0]["targets"][0]["gm_approved"] = False
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    for pairs in (sim["scenario"]["pair_ranges"][:-1], sim["scenario"]["pair_ranges"] * 2):
        changed = deepcopy(sim["scenario"]); changed["pair_ranges"] = pairs
        negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    changed = deepcopy(sim["scenario"]); changed["definitions"][0]["attack"]["hands"] = "1h"
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    changed = deepcopy(sim["scenario"]); changed["definitions"][0]["protection"]["skill"] = "defence"
    negatives.append(lambda d=changed: map_scenario(d, sim["request_id"], 2))
    changed = deepcopy(bal); changed["generation"]["max_candidates"] = 3
    negatives.append(lambda d=changed: map_balance(d))
    changed = deepcopy(bal); changed["evaluation"]["max_total_trials"] = 15
    negatives.append(lambda d=changed: map_balance(d))
    changed = deepcopy(bal); changed["generation"]["pair_ranges"].reverse()
    negatives.append(lambda d=changed: map_balance(d))
    for construct in negatives:
        try: construct()
        except (TypeError, ValueError): pass
        else: raise AssertionError("invalid fixture admitted")
    # Arithmetic preflight succeeds; construction must reject the (0, 1)
    # subset whose Melee actors lack an initial Close enemy. No silent skip.
    changed = deepcopy(bal)
    changed["generation"]["groups"][0]["minimum_count"] = 0
    changed["generation"]["max_candidates"] = 5
    changed["evaluation"]["max_total_trials"] = 18
    invalid_subset = map_balance(changed)
    assert invalid_subset.candidate_count == 5 and invalid_subset.planned_trials == 18
    try:
        generate_mixed_candidates(invalid_subset)
    except MixedCandidateGenerationError as error:
        assert error.counts == (0, 1) and error.__cause__ is not None
    else:
        raise AssertionError("invalid subset skipped")
    assert (sim, bal) == before
    assert getstate() == rng_before and {c.pid for c in active_children()} == children_before
    assert staged.total_trials <= source.planned_trials == 16
    runtime = {"package_version": __version__, "python_implementation": platform.python_implementation(),
               "python_version": platform.python_version(), "rng": "random.Random"}
    simulation_output = {"schema_version": "1", "kind": "npc_mixed_simulation_result", "request": sim,
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
                        list(mixed_continuation_candidate_ids(report)) if index < len(source.stages)-1 else []})
    balance_output = {"schema_version": "1", "kind": "npc_mixed_balance_result", "request": bal,
                      "seed_scheme": SEED_SCHEME, "runtime": runtime, "candidate_count": source.candidate_count,
                      "planned_trials": source.planned_trials, "total_trials": staged.total_trials,
                      "candidates": [{"candidate_id": c.candidate_id, "counts": list(v)}
                                     for c, v in zip(generated.evaluation_request.candidates, vectors, strict=True)],
                      "stage_reports": reports, "status": staged.status.value,
                      "selected_candidate_ids": list(staged.selected_candidate_ids)}
    for name, output in (("mixed-simulation", simulation_output), ("mixed-balance", balance_output)):
        encoded = json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        assert json.loads(encoded) == output
        if sys.argv[1:]: (DIRECTORY / (name + "-v1.result.json")).write_text(encoded, encoding="utf-8")
    print(f"exact fixture mapping; simulation {summary.trials} trials, balance planned/actual={source.planned_trials}/{staged.total_trials}")
    print(f"full sequential/process results equal; {len(negatives)} semantic rejections + generation failure; sources/global RNG/children unchanged")
    print("contract probe only: no Mixed production Schema/parser/encoder/CLI or lexical validation")


if __name__ == "__main__":
    main()
