"""Pure source-preserving PC scenario codec, without execution or RNG."""
from dataclasses import asdict
from enum import Enum
from functools import partial

from towr.adapters._json_common import build_value
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.fate_models import (
    FateBurnKind, FateBurnRecord, FateRefreshRecord, FateSessionState,
    FateSpendFunding, FateSpendKind, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcNearMissPolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcAllyRecoverPolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleeParticipant, PcMeleePolicy, PcMeleeScenario,
    PcMeleeWeapon, PcRandomSidePolicy, PcHeavyWoundPolicy, PcWeaponHand, validate_pc_melee_scenario_admission,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {name: _plain(child) for name, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(child) for child in value]
    return value


def parse_facts(data: dict) -> PcMeleeFacts:
    return PcMeleeFacts(**data)


def facts_document(facts: PcMeleeFacts) -> dict:
    return asdict(facts)


def parse_scenario(data: dict, *, path_prefix: str, error_type: type[PcMeleeInputError]) -> PcMeleeScenario:
    try:
        return _parse_scenario(data, path_prefix=path_prefix, error_type=error_type)
    except PcMeleeInputError:
        raise
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix) from error


def _parse_participant(data, *, path_prefix, error_type):
    build = partial(build_value, error_type)
    pc_raw = dict(data["pc"])
    pc_raw["weapon"] = PcMeleeWeapon(pc_raw["weapon"])
    pc = build(path_prefix + "/pc", PcMeleeDefinition, **pc_raw)
    fate_raw = dict(data["fate"])
    fate_raw["spends"] = tuple(build(f"{path_prefix}/fate/spends/{index}", FateSpendRecord,
        **dict(record, kind=FateSpendKind(record["kind"]), funding=FateSpendFunding(record["funding"])))
        for index, record in enumerate(fate_raw["spends"]))
    fate_raw["refreshes"] = tuple(build(f"{path_prefix}/fate/refreshes/{index}", FateRefreshRecord, **record)
        for index, record in enumerate(fate_raw["refreshes"]))
    fate_raw["burns"] = tuple(build(f"{path_prefix}/fate/burns/{index}", FateBurnRecord,
        **dict(record, kind=FateBurnKind(record["kind"]))) for index, record in enumerate(fate_raw["burns"]))
    fate_raw["resource_event_ids"] = tuple(fate_raw["resource_event_ids"])
    fate = build(path_prefix + "/fate", FateSessionState, **fate_raw)
    near_miss = (None if data["near_miss_policy"] is None else
        build(path_prefix + "/near_miss_policy", PcNearMissPolicy, **data["near_miss_policy"]))
    glorious = (None if data["glorious_policy"] is None else
        build(path_prefix + "/glorious_policy", PcGloriousPolicy,
            **dict(data["glorious_policy"],skills=tuple(Skill(value)
                for value in data["glorious_policy"]["skills"]))))
    help_policy = (None if data["help_policy"] is None else
        build(path_prefix + "/help_policy", PcHelpPolicy,
            **dict(data["help_policy"],target=PcHelpTarget(data["help_policy"]["target"]),
                protection_skill=(None if data["help_policy"]["protection_skill"] is None else
                    Skill(data["help_policy"]["protection_skill"])))))
    ally_recover_policy = (None if data["ally_recover_policy"] is None else
        build(path_prefix + "/ally_recover_policy",PcAllyRecoverPolicy,**data["ally_recover_policy"]))
    return build(path_prefix, PcMeleeParticipant, data["actor_id"], pc, fate,
        PcMeleePolicy(data["policy"]), PcFatePolicy(data["fate_policy"]),
        PcRandomSidePolicy(data["random_side_policy"]), PcHeavyWoundPolicy(data["heavy_wound_policy"]),
        PcWeaponHand(data["initial_weapon_hand"]),
        tuple(data["target_priority"]),
        tuple(build(f"{path_prefix}/defeat_decisions/{index}", MinionDefeatDecision,
            **dict(record, disposition=NpcDefeatDisposition(record["disposition"])))
            for index, record in enumerate(data["defeat_decisions"])),
        near_miss_policy=near_miss,glorious_policy=glorious,help_policy=help_policy,
        ally_recover_policy=ally_recover_policy)


def _parse_scenario(data, *, path_prefix, error_type):
    build = partial(build_value, error_type)
    party = tuple(_parse_participant(member, path_prefix=f"{path_prefix}/party/{index}", error_type=error_type)
                  for index, member in enumerate(data["party"]))
    enemies = []
    for index, enemy in enumerate(data["enemies"]):
        path = f"{path_prefix}/enemies/{index}"
        definition_raw = enemy["definition"]
        attack_raw = definition_raw["attack"]
        protection_raw = definition_raw["protection"]
        attack = build(path + "/definition/attack", NpcAttackProfile,
            attack_raw["id"], attack_raw["source_rule_id"], Skill.MELEE,
            InlineProfile(**attack_raw["test_profile"]), DamageProfile(**attack_raw["damage"]),
            RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, RangedWeaponHands(attack_raw["hands"]))
        resilience = build(path + "/definition/resilience", ResilienceProfile, **definition_raw["resilience"])
        definition = build(path + "/definition", NpcDefinition,
            definition_raw["id"], definition_raw["source_rule_id"],
            TargetInjuryPolicy(definition_raw["injury_policy"]), definition_raw["wound_limit"],
            resilience, (attack,), (NpcProtectionProfile(protection_raw["source_rule_id"],
                Skill.DEFENCE, InlineProfile(**protection_raw["test_profile"])),))
        state = build(path, NpcParticipantState, enemy["actor_id"], definition.id,
            CombatSide.OPPOSITION, ProfileInjuryState(0, definition.wound_limit), (attack.id,), resilience, True, False)
        enemies.append(NpcParticipantSnapshot(definition, state))
    return build(path_prefix, PcMeleeScenario, data["id"], party,
        data["day_id"], tuple(enemies), build(path_prefix + "/facts", PcMeleeFacts, **data["facts"]),
        tuple(data["pc_activation_order"]), tuple(data["enemy_activation_order"]),
        tuple(data["enemy_target_priority"]), data["max_rounds"])


def scenario_document(scenario: PcMeleeScenario) -> dict:
    validate_pc_melee_scenario_admission(scenario)
    enemies = []
    for enemy in scenario.enemies:
        definition = enemy.definition
        attack, protection = definition.attacks[0], definition.protection[0]
        enemies.append({"actor_id": enemy.state.actor_id, "definition": {
            "id": definition.id, "source_rule_id": definition.source_rule_id,
            "injury_policy": definition.injury_policy.value, "wound_limit": definition.wound_limit,
            "resilience": asdict(definition.resilience),
            "attack": {"id": attack.id, "source_rule_id": attack.source_rule_id,
                "test_profile": asdict(attack.test_profile), "damage": asdict(attack.damage),
                "hands": attack.hands.value},
            "protection": {"source_rule_id": protection.source_rule_id,
                "test_profile": asdict(protection.test_profile)}}})
    return {"id": scenario.id, "party": _plain([asdict(member) for member in scenario.party]),
        "day_id": scenario.day_id, "enemies": enemies,
        "facts": facts_document(scenario.facts),
        "pc_activation_order": list(scenario.pc_activation_order),
        "enemy_activation_order": list(scenario.enemy_activation_order),
        "enemy_target_priority": list(scenario.enemy_target_priority),
        "max_rounds": scenario.max_rounds}
