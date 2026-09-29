"""Internal shared scenario codec; no simulation envelope, RNG or execution."""
from dataclasses import asdict
from functools import partial

from towr.adapters.mixed_json_errors import MixedInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters._json_common import build_value
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


def parse_facts(data: dict) -> NpcMixedScenarioFacts:
    return NpcMixedScenarioFacts(**data)


def facts_document(facts: NpcMixedScenarioFacts) -> dict:
    return asdict(facts)


def parse_pair_ranges(data: list, *, path_prefix: str,
                      error_type: type[MixedInputError]) -> tuple[NpcMixedPairRange, ...]:
    return tuple(build_value(error_type, f"{path_prefix}/{i}", NpcMixedPairRange,
        p["first_actor_id"], p["second_actor_id"], Range(p["target_range"]))
        for i, p in enumerate(data))


def pair_ranges_document(pairs: tuple[NpcMixedPairRange, ...]) -> list[dict]:
    return [{"first_actor_id": p.first_actor_id, "second_actor_id": p.second_actor_id,
             "target_range": p.target_range.value} for p in pairs]


def parse_scenario(data: dict, initial_id: str, round_budget: int, *,
                   path_prefix: str, error_type: type[MixedInputError]) -> tuple[NpcMixedScenario, tuple[str, ...]]:
    try:
        return _parse_scenario(data, initial_id, round_budget, path_prefix, error_type)
    except MixedInputError:
        raise
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix) from error


def _parse_scenario(data, initial_id, round_budget, path_prefix, error_type):
    build = partial(build_value, error_type)
    definitions = {}
    for index, raw in enumerate(data["definitions"]):
        path = f"{path_prefix}/definitions/{index}"
        if raw["id"] in definitions:
            raise error_type(Code.INVALID_INPUT, "duplicate definition ID", path=path + "/id")
        attack, protection = raw["attack"], raw["protection"]
        definitions[raw["id"]] = build(path, NpcDefinition, raw["id"], raw["source_rule_id"],
            TargetInjuryPolicy.MINION, 1, ResilienceProfile(**raw["resilience"]),
            (NpcAttackProfile(attack["id"], attack["source_rule_id"], Skill(attack["skill"]),
                InlineProfile(attack["dice"], attack["threshold"]), DamageProfile(attack["damage"]),
                Range(attack["range_min"]), Range(attack["range_max"]), Hands(attack["hands"])),),
            (NpcProtectionProfile(protection["source_rule_id"], Skill(protection["skill"]),
                InlineProfile(protection["dice"], protection["threshold"])),))
    participants = []
    for index, actor in enumerate(data["actors"]):
        if actor["definition_id"] not in definitions:
            raise error_type(Code.INVALID_INPUT, "unknown definition ID",
                                             path=f"{path_prefix}/actors/{index}/definition_id")
        definition = definitions[actor["definition_id"]]
        participants.append(NpcParticipantSnapshot(definition, NpcParticipantState(
            actor["id"], definition.id, CombatSide(actor["side"]), ProfileInjuryState(0, 1),
            (definition.attacks[0].id,), definition.resilience, True, False)))
    if set(definitions) != {p.definition.id for p in participants}:
        raise error_type(Code.INVALID_INPUT, "unused definition", path=f"{path_prefix}/definitions")
    roster = build(f"{path_prefix}/actors", NpcRoster, tuple(participants))
    combat = build(f"{path_prefix}/side_order", CombatRoundState, 1, roster.turn_participants,
                    tuple(CombatSide(s) for s in data["side_order"]))
    current = build(f"{path_prefix}/actor_order", NpcRoundRequest, initial_id, NpcRosterAttackState(roster),
                     combat, tuple(data["actor_order"]), ())
    field = data["battlefield"]
    connections = tuple(build(f"{path_prefix}/battlefield/connections/{i}", ZoneConnection, **c)
                        for i, c in enumerate(field["connections"]))
    graph = build(f"{path_prefix}/battlefield", ZoneGraph, tuple(field["zone_ids"]), connections)
    spatial = build(f"{path_prefix}/actors", SpatialBattleState, graph,
        tuple(SpatialEntityPlacement(a["id"], a["side"], a["zone_id"]) for a in data["actors"]))
    policies = tuple(build(f"{path_prefix}/actor_policies/{i}", NpcMixedActorPolicy, p["actor_id"],
        tuple(t["target_id"] for t in p["targets"]),
        tuple(MinionDefeatDecision(p["actor_id"], t["target_id"], NpcDefeatDisposition(t["disposition"]), t["gm_approved"])
              for t in p["targets"]), p["outnumbering_bonus_approved"], p["can_leave_zone"])
        for i, p in enumerate(data["actor_policies"]))
    pairs = parse_pair_ranges(data["pair_ranges"], path_prefix=f"{path_prefix}/pair_ranges", error_type=error_type)
    scenario = build(path_prefix, NpcMixedScenario,
        NpcRoundsRequest(current, spatial, round_budget), parse_facts(data["facts"]), pairs, policies,
        StaggerChoice(data["repeated_stagger_choice"]), CombatSide(data["perspective_side"]),
        NpcDefeatObjective(tuple(data["objective_target_ids"])))
    return scenario, tuple(definitions)


def scenario_document(scenario: NpcMixedScenario, definition_order: tuple[str, ...]) -> dict:
    roster = scenario.initial.current.state.roster
    definitions = {p.definition.id: p.definition for p in roster.participants}
    profiles = []
    for identifier in definition_order:
        definition = definitions[identifier]
        attack, protection = definition.attacks[0], definition.protection[0]
        profiles.append({"id": identifier, "source_rule_id": definition.source_rule_id,
            "resilience": asdict(definition.resilience),
            "attack": {"id": attack.id, "source_rule_id": attack.source_rule_id,
                       "skill": attack.skill.value, "range_min": attack.range_min.value,
                       "range_max": attack.range_max.value, "dice": attack.test_profile.dice,
                       "threshold": attack.test_profile.threshold, "damage": attack.damage.base, "hands": attack.hands.value},
            "protection": {"source_rule_id": protection.source_rule_id, "skill": protection.skill.value, "dice": protection.test_profile.dice,
                           "threshold": protection.test_profile.threshold}})
    spatial = scenario.initial.spatial_state
    facts = facts_document(scenario.facts)
    return {"definitions": profiles,
            "actors": [{"id": p.state.actor_id, "definition_id": p.definition.id, "side": p.state.side.value,
                        "zone_id": spatial.placement_for(p.state.actor_id).zone_id} for p in roster.participants],
            "battlefield": {"zone_ids": list(spatial.graph.zone_ids),
                            "connections": [asdict(c) for c in spatial.graph.connections]},
            "side_order": [s.value for s in scenario.initial.current.round_state.side_order],
            "actor_order": list(scenario.initial.current.actor_order), "perspective_side": scenario.perspective_side.value,
            "objective_target_ids": list(scenario.objective.target_actor_ids), "facts": facts,
            "pair_ranges": pair_ranges_document(scenario.pair_ranges),
            "repeated_stagger_choice": scenario.repeated_stagger_choice.value,
            "actor_policies": [{"actor_id": p.actor_id, "outnumbering_bonus_approved": p.outnumbering_bonus_approved,
                                "can_leave_zone": p.can_leave_zone, "targets": [
                {"target_id": d.target_id, "disposition": d.disposition.value, "gm_approved": d.gm_approved}
                for d in p.defeat_decisions]} for p in scenario.actor_policies]}
