"""Small independent authored PC melee fixtures, without rule execution."""
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.fate_models import FateSessionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleePolicy, PcMeleeScenario,
    PcHeavyWoundPolicy, PcMeleeWeapon, PcRandomSidePolicy, PcWeaponHand, PcTwoHandedGrip, PcMeleeParticipant,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands


def make_pc_melee_scenario(*, weapon: PcMeleeWeapon = PcMeleeWeapon.STAFF,
                           enemy_count: int = 1, max_rounds: int = 3) -> PcMeleeScenario:
    """An authored healthy PC and ordinary numeric Minions, not a bestiary entry."""
    if type(enemy_count) is not int:
        raise TypeError("enemy_count must be an integer")
    if enemy_count < 1:
        raise ValueError("enemy_count must be positive")
    pc = PcMeleeDefinition("pc-profile", 3, 3, 3, 3, 5, 5, 4, 4, weapon, 0)
    enemies = []
    for index in range(enemy_count):
        actor_id = f"minion{index + 1}"
        attack = NpcAttackProfile("club", "authored:minion:club", Skill.MELEE,
            InlineProfile(2, 4), DamageProfile(3), RangedWeaponRange.CLOSE,
            RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED)
        definition = NpcDefinition("minion-profile", "authored:minion",
            TargetInjuryPolicy.MINION, 1, ResilienceProfile(3), (attack,),
            (NpcProtectionProfile("authored:minion:defence", Skill.DEFENCE, InlineProfile(2, 4)),))
        state = NpcParticipantState(actor_id, definition.id, CombatSide.OPPOSITION,
            ProfileInjuryState(0, 1), (attack.id,), definition.resilience, True, False)
        enemies.append(NpcParticipantSnapshot(definition, state))
    ids = tuple(enemy.state.actor_id for enemy in enemies)
    member = PcMeleeParticipant("pc", pc, FateSessionState("session", "pc", 3, 3),
        PcMeleePolicy.ATTACK_OR_RECOVER_SELF, PcFatePolicy.DECLINE_OPTIONAL_FATE,
        PcRandomSidePolicy.D10_LOW_LEFT_HIGH_RIGHT, PcHeavyWoundPolicy.CONTINUE_FIGHTING,
        PcTwoHandedGrip.BOTH if pc_weapon_requires_two_hands(weapon) else PcWeaponHand.LEFT, ids,
        tuple(MinionDefeatDecision("pc", target, NpcDefeatDisposition.KNOCKED_OUT, True) for target in ids),
        near_miss_policy=None,glorious_policy=None,help_policy=None,ally_recover_policy=None,backup_weapon_policy=None)
    return PcMeleeScenario("pc-melee", (member,), "day", tuple(enemies),
        PcMeleeFacts("arena", True, True, True, True, True, True, True, True, True, False),
        ("pc",), ids, ("pc",), max_rounds)


def make_pc_melee_party_scenario(*, pc_count: int = 2, enemy_count: int = 2,
                                max_rounds: int = 3) -> PcMeleeScenario:
    """Fresh independent PC bodies with authored identities and a shared scene."""
    from dataclasses import replace
    if type(pc_count) is not int or pc_count < 1:
        raise ValueError("pc_count must be a positive integer")
    source = make_pc_melee_scenario(enemy_count=enemy_count, max_rounds=max_rounds)
    base = source.party[0]
    party = []
    for index in range(pc_count):
        actor = f"pc{index + 1}"
        party.append(replace(base, actor_id=actor, pc=replace(base.pc, id=f"pc-profile{index + 1}"),
            fate=replace(base.fate, actor_id=actor),
            defeat_decisions=tuple(replace(d, attacker_id=actor) for d in base.defeat_decisions)))
    ids = tuple(m.actor_id for m in party)
    return replace(source, party=tuple(party), pc_activation_order=ids, enemy_target_priority=ids)


def replace_pc_melee_member(source: PcMeleeScenario, actor_id: str, **changes) -> PcMeleeScenario:
    """Replace an explicit member while preserving the independent party source."""
    from dataclasses import replace
    source.participant(actor_id)
    return replace(source, party=tuple(replace(m, **changes) if m.actor_id == actor_id else m for m in source.party))


def with_pc_melee_brute(source: PcMeleeScenario, actor_id: str, *, wound_limit: int = 3) -> PcMeleeScenario:
    """Author one static numeric Brute; retain its actor ID and all chosen orders."""
    from dataclasses import replace
    original = source.enemy(actor_id)
    definition = replace(original.definition,id=f"brute-profile:{wound_limit}",
        source_rule_id="authored:static-brute",injury_policy=TargetInjuryPolicy.BRUTE,wound_limit=wound_limit)
    state = replace(original.state,definition_id=definition.id,injury=ProfileInjuryState(0,wound_limit))
    enemy = NpcParticipantSnapshot(definition,state)
    return replace(source,enemies=tuple(enemy if item.state.actor_id == actor_id else item for item in source.enemies))


def make_pc_melee_mixed_scenario(*, pc_count: int = 2, minion_count: int = 1,
        brute_count: int = 1, brute_wound_limit: int = 3, max_rounds: int = 3) -> PcMeleeScenario:
    """Explicit mixed reserve with independent healthy profile states."""
    from dataclasses import replace
    for name,value in (("minion_count",minion_count),("brute_count",brute_count)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    source = make_pc_melee_party_scenario(pc_count=pc_count,enemy_count=minion_count+brute_count,max_rounds=max_rounds)
    old_ids = tuple(enemy.state.actor_id for enemy in source.enemies)
    ids = tuple(f"minion{i+1}" for i in range(minion_count))+tuple(f"brute{i+1}" for i in range(brute_count))
    mapping = dict(zip(old_ids,ids))
    enemies = tuple(replace(enemy,state=replace(enemy.state,actor_id=mapping[enemy.state.actor_id])) for enemy in source.enemies)
    party = tuple(replace(member,target_priority=tuple(mapping[target] for target in member.target_priority),
        defeat_decisions=tuple(replace(decision,target_id=mapping[decision.target_id]) for decision in member.defeat_decisions))
        for member in source.party)
    source = replace(source,enemies=enemies,party=party,enemy_activation_order=ids)
    for actor in ids[minion_count:]:
        source = with_pc_melee_brute(source,actor,wound_limit=brute_wound_limit)
    return source
