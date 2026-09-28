"""Internal shared scenario codec; no simulation envelope, RNG or execution."""
from dataclasses import asdict
from functools import partial

from towr.adapters.melee_json_errors import MeleeInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters._json_common import build_value
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


def parse_facts(data: dict) -> NpcMeleeScenarioFacts:
    return NpcMeleeScenarioFacts(**data)


def facts_document(facts: NpcMeleeScenarioFacts) -> dict:
    return asdict(facts)


def parse_scenario(data: dict, initial_id: str, round_budget: int, *,
                   path_prefix: str, error_type: type[MeleeInputError]) -> tuple[NpcMeleeScenario, tuple[str, ...]]:
    try:
        return _parse_scenario(data, initial_id, round_budget, path_prefix, error_type)
    except MeleeInputError:
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
            (NpcAttackProfile(attack["id"], attack["source_rule_id"], Skill.MELEE,
                InlineProfile(attack["dice"], attack["threshold"]), DamageProfile(attack["damage"]),
                Range.CLOSE, Range.CLOSE, Hands(attack["hands"])),),
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
    policies = tuple(build(f"{path_prefix}/actor_policies/{i}", NpcMeleeActorPolicy, p["actor_id"],
        tuple(t["target_id"] for t in p["targets"]),
        tuple(MinionDefeatDecision(p["actor_id"], t["target_id"], NpcDefeatDisposition(t["disposition"]), t["gm_approved"])
              for t in p["targets"]), p["outnumbering_bonus_approved"])
        for i, p in enumerate(data["actor_policies"]))
    scenario = build(path_prefix, NpcMeleeScenario,
        NpcRoundsRequest(current, spatial, round_budget), parse_facts(data["facts"]), policies,
        StaggerChoice(data["repeated_stagger_choice"]), CombatSide(data["perspective_side"]),
        NpcDefeatObjective(tuple(data["objective_target_ids"])))
    return scenario, tuple(definitions)


def scenario_document(scenario: NpcMeleeScenario, definition_order: tuple[str, ...]) -> dict:
    roster = scenario.initial.current.state.roster
    definitions = {p.definition.id: p.definition for p in roster.participants}
    profiles = []
    for identifier in definition_order:
        definition = definitions[identifier]
        attack, protection = definition.attacks[0], definition.protection[0]
        profiles.append({"id": identifier, "source_rule_id": definition.source_rule_id,
            "resilience": asdict(definition.resilience),
            "attack": {"id": attack.id, "source_rule_id": attack.source_rule_id, "dice": attack.test_profile.dice,
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
            "repeated_stagger_choice": scenario.repeated_stagger_choice.value,
            "actor_policies": [{"actor_id": p.actor_id, "outnumbering_bonus_approved": p.outnumbering_bonus_approved, "targets": [
                {"target_id": d.target_id, "disposition": d.disposition.value, "gm_approved": d.gm_approved}
                for d in p.defeat_decisions]} for p in scenario.actor_policies]}
