"""Immutable authored input for the first PC melee encounter (ADR-0065)."""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import ConditionState
from towr.domain.fate_models import (
    FateBurnRecord, FateRefreshRecord, FateSessionState, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,validate_pc_npc_help_policies
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy,validate_pc_npc_grudge_policies
from towr.domain.pc_npc_blood_rage_policy_models import validate_pc_npc_blood_rage_policy
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,validate_pc_flagellant_policies
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill, TestProfile
from towr.domain.turn_models import CombatSide
from towr.domain.pc_hit_condition_models import validate_pc_hit_effects


class PcMeleeWeapon(str, Enum):
    STAFF = "staff"
    SWORD = "sword"
    DAGGER = "dagger"
    AXE = "axe"
    WARHAMMER = "warhammer"
    MORNING_STAR = "morning_star"
    PICKAXE = "pickaxe"
    FLAIL = "flail"
    BILLHOOK = "billhook"
    HALBERD = "halberd"
    GLAIVE = "glaive"
    GREATAXE = "greataxe"
    GREATHAMMER = "greathammer"


class PcMeleePolicy(str, Enum):
    ATTACK_OR_RECOVER_SELF = "attack_or_recover_self"
    HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF = "help_ally_or_attack_or_recover_self"
    RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF = "recover_ally_or_attack_or_recover_self"


@dataclass(frozen=True, slots=True)
class PcAllyRecoverPolicy:
    beneficiary_id: str

    def __post_init__(self) -> None:
        _identifier(self.beneficiary_id,"ally Recover beneficiary")


class PcHelpTarget(str, Enum):
    MELEE_ATTACK = "melee_attack"
    FIRST_INCOMING_PROTECTION = "first_incoming_protection"


@dataclass(frozen=True, slots=True)
class PcHelpPolicy:
    beneficiary_id: str
    target: PcHelpTarget
    protection_skill: Skill | None

    def __post_init__(self) -> None:
        _identifier(self.beneficiary_id,"Help beneficiary")
        _typed(self.target,PcHelpTarget,"Help target")
        if self.target is PcHelpTarget.MELEE_ATTACK:
            if self.protection_skill is not None:
                raise ValueError("Melee Attack Help cannot carry a Protection skill")
        else:
            _typed(self.protection_skill,Skill,"Help Protection skill")
            if self.protection_skill not in (Skill.DEFENCE,Skill.ATHLETICS):
                raise ValueError("Protection Help requires Defence or Athletics")


class PcFatePolicy(str, Enum):
    DECLINE_OPTIONAL_FATE = "decline_optional_fate"
    CONFIGURED = "configured"


@dataclass(frozen=True, slots=True)
class PcNearMissPolicy:
    minimum_table_total: int
    minimum_rating_to_keep: int

    def __post_init__(self) -> None:
        _integer(self.minimum_table_total, "Near Miss table threshold", minimum=1)
        _integer(self.minimum_rating_to_keep, "Near Miss Fate reserve", minimum=0)


@dataclass(frozen=True, slots=True)
class PcGloriousPolicy:
    skills: tuple[Skill, ...]
    maximum_initial_successes: int
    minimum_remaining_spends: int

    def __post_init__(self) -> None:
        skills = _ordered(self.skills, "Glorious skills")
        if not skills or len(set(skills)) != len(skills):
            raise ValueError("Glorious skills must be nonempty and unique")
        for skill in skills:
            _typed(skill, Skill, "Glorious skill")
            if skill not in (Skill.MELEE, Skill.DEFENCE, Skill.ATHLETICS, Skill.ENDURANCE):
                raise ValueError("Glorious skill is outside the PC melee boundary")
        _integer(self.maximum_initial_successes, "Glorious success threshold", minimum=0)
        _integer(self.minimum_remaining_spends, "Glorious session reserve", minimum=0)
        object.__setattr__(self,"skills",skills)


class PcRandomSidePolicy(str, Enum):
    D10_LOW_LEFT_HIGH_RIGHT = "d10_low_left_high_right"


class PcHeavyWoundPolicy(str, Enum):
    CONTINUE_FIGHTING = "continue_fighting"


class PcWeaponHand(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class PcTwoHandedGrip(str, Enum):
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class PcBackupWeaponPolicy:
    weapon: PcMeleeWeapon
    preferred_hand: PcWeaponHand

    def __post_init__(self) -> None:
        _typed(self.weapon,PcMeleeWeapon,"backup weapon")
        _typed(self.preferred_hand,PcWeaponHand,"backup preferred hand")
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        if pc_weapon_requires_two_hands(self.weapon):
            raise ValueError("backup weapon must be one-handed")


@dataclass(frozen=True, slots=True)
class PcMeleeDefinition:
    id: str
    weapon_skill: int
    strength: int
    toughness: int
    agility: int
    melee: int
    defence: int
    athletics: int
    endurance: int
    weapon: PcMeleeWeapon
    armour_bonus: int

    def __post_init__(self) -> None:
        _identifier(self.id, "PC definition")
        for name in ("weapon_skill", "strength", "toughness", "agility"):
            _integer(getattr(self, name), name, minimum=1)
        for characteristic, skill in (
            (self.weapon_skill, self.melee), (self.weapon_skill, self.defence),
            (self.agility, self.athletics), (self.toughness, self.endurance),
        ):
            TestProfile(characteristic, skill)
        _typed(self.weapon, PcMeleeWeapon, "PC weapon")
        _integer(self.armour_bonus, "PC armour bonus", minimum=0)

    @property
    def melee_profile(self) -> TestProfile:
        return TestProfile(self.weapon_skill, self.melee)

    @property
    def defence_profile(self) -> TestProfile:
        return TestProfile(self.weapon_skill, self.defence)

    @property
    def athletics_profile(self) -> TestProfile:
        return TestProfile(self.agility, self.athletics)

    @property
    def endurance_profile(self) -> TestProfile:
        return TestProfile(self.toughness, self.endurance)

    @property
    def resilience(self) -> ResilienceProfile:
        return ResilienceProfile(self.toughness, self.armour_bonus)


@dataclass(frozen=True, slots=True)
class PcMeleeFacts:
    zone_id: str
    all_opponents_close: bool
    targets_aware: bool
    all_combatants_included: bool
    unmounted: bool
    no_external_effects: bool
    no_terrain_modifiers: bool
    no_additional_abilities: bool
    no_ambush: bool
    outnumbering_bonus_approved: bool
    can_leave_zone: bool

    def __post_init__(self) -> None:
        _identifier(self.zone_id, "PC melee Zone")
        for name in (
            "all_opponents_close", "targets_aware", "all_combatants_included",
            "unmounted", "no_external_effects", "no_terrain_modifiers",
            "no_additional_abilities", "no_ambush", "outnumbering_bonus_approved",
            "can_leave_zone",
        ):
            value = getattr(self, name)
            _typed(value, bool, name)
            if name not in ("outnumbering_bonus_approved", "can_leave_zone") and not value:
                raise ValueError(f"unsupported PC melee fact: {name}")


@dataclass(frozen=True, slots=True)
class PcMeleeParticipant:
    actor_id: str
    pc: PcMeleeDefinition
    fate: FateSessionState
    policy: PcMeleePolicy
    fate_policy: PcFatePolicy
    random_side_policy: PcRandomSidePolicy
    heavy_wound_policy: PcHeavyWoundPolicy
    initial_weapon_hand: PcWeaponHand | PcTwoHandedGrip
    target_priority: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]
    near_miss_policy: PcNearMissPolicy | None
    glorious_policy: PcGloriousPolicy | None
    help_policy: PcHelpPolicy | None
    ally_recover_policy: PcAllyRecoverPolicy | None
    backup_weapon_policy: PcBackupWeaponPolicy | None

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "PC actor")
        _typed(self.pc, PcMeleeDefinition, "PC definition")
        replace(self.pc)
        _readmit_fate(self.fate, self.actor_id)
        for name, cls in (("policy", PcMeleePolicy), ("fate_policy", PcFatePolicy),
                          ("random_side_policy", PcRandomSidePolicy), ("heavy_wound_policy", PcHeavyWoundPolicy)):
            _typed(getattr(self, name), cls, name)
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        grip_type = PcTwoHandedGrip if pc_weapon_requires_two_hands(self.pc.weapon) else PcWeaponHand
        _typed(self.initial_weapon_hand,grip_type,"initial weapon grip")
        if self.backup_weapon_policy is not None:
            _typed(self.backup_weapon_policy,PcBackupWeaponPolicy,"backup weapon policy")
            replace(self.backup_weapon_policy)
            if grip_type is not PcTwoHandedGrip or self.pc.strength < 2:
                raise ValueError("backup requires a two-handed primary and Strength to carry two weapons")
        for value, cls in ((self.near_miss_policy,PcNearMissPolicy),(self.glorious_policy,PcGloriousPolicy)):
            if value is not None:
                _typed(value,cls,"Fate strategy")
                replace(value)
        if self.glorious_policy is not None:
            _canonical_tuple(self.glorious_policy.skills,"Glorious skills")
        configured = self.near_miss_policy is not None or self.glorious_policy is not None
        if configured != (self.fate_policy is PcFatePolicy.CONFIGURED):
            raise ValueError("configured Fate needs explicit criteria; decline requires null policies")
        if self.policy is PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF:
            _typed(self.help_policy,PcHelpPolicy,"Help strategy")
            replace(self.help_policy)
            if self.help_policy.beneficiary_id == self.actor_id:
                raise ValueError("Help requires another PC")
        elif self.help_policy is not None:
            raise ValueError("ordinary Attack/Recover cannot carry a Help strategy")
        if self.policy is PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF:
            _typed(self.ally_recover_policy,PcAllyRecoverPolicy,"ally Recover strategy")
            replace(self.ally_recover_policy)
            if self.ally_recover_policy.beneficiary_id == self.actor_id:
                raise ValueError("ally Recover requires another PC")
        elif self.ally_recover_policy is not None:
            raise ValueError("this action strategy cannot carry ally Recover criteria")
        targets = _ordered(self.target_priority, "PC target priority")
        for target in targets:
            _identifier(target, "PC target")
        if not targets or len(set(targets)) != len(targets):
            raise ValueError("PC target priority must be nonempty and unique")
        decisions = _ordered(self.defeat_decisions, "defeat decisions")
        for decision in decisions:
            _typed(decision, MinionDefeatDecision, "defeat decision")
            _identifier(decision.attacker_id, "defeat attacker")
            _identifier(decision.target_id, "defeat target")
            _typed(decision.disposition, NpcDefeatDisposition, "defeat disposition")
            _typed(decision.gm_approved, bool, "defeat approval")
            replace(decision)
            if decision.attacker_id != self.actor_id or not decision.gm_approved:
                raise ValueError("defeat decisions require their PC and explicit GM approval")
        if tuple(item.target_id for item in decisions) != targets:
            raise ValueError("defeat decisions must follow the full PC target priority")
        object.__setattr__(self, "target_priority", targets)
        object.__setattr__(self, "defeat_decisions", decisions)

    def defeat_decision(self, target_id: str) -> MinionDefeatDecision:
        _identifier(target_id, "defeat target")
        for decision in self.defeat_decisions:
            if decision.target_id == target_id:
                return decision
        raise ValueError("unknown PC melee defeat target")


@dataclass(frozen=True, slots=True)
class PcAdjacentNpcExitPolicy:
    """One declared clear adjacent exit from the fixed arena; no pursuit/return."""
    destination_zone_id: str
    path_clear_confirmed: bool
    fastest_route_confirmed: bool

    def __post_init__(self) -> None:
        _identifier(self.destination_zone_id,"NPC exit destination Zone")
        for value in (self.path_clear_confirmed,self.fastest_route_confirmed):
            _typed(value,bool,"NPC exit route confirmation")
            if not value:
                raise ValueError("NPC exit requires its clear, fastest adjacent route")


@dataclass(frozen=True, slots=True)
class PcMeleeScenario:
    id: str
    party: tuple[PcMeleeParticipant, ...]
    day_id: str
    enemies: tuple[NpcParticipantSnapshot, ...]
    facts: PcMeleeFacts
    pc_activation_order: tuple[str, ...]
    enemy_activation_order: tuple[str, ...]
    enemy_target_priority: tuple[str, ...]
    max_rounds: int
    npc_broken_exit_policy: PcAdjacentNpcExitPolicy | None
    npc_help_policies: tuple[PcNpcHelpPolicy, ...]
    npc_extra_attack_actor_ids: tuple[str, ...] = field(kw_only=True)
    npc_grudge_policies: tuple[PcNpcGrudgePolicy, ...] = field(kw_only=True)
    npc_blood_rage_actor_ids: tuple[str, ...] = field(kw_only=True)
    npc_flagellant_policies: tuple[PcFlagellantPolicy, ...] = field(kw_only=True)

    def __post_init__(self) -> None:
        for name in ("id", "day_id"):
            _identifier(getattr(self, name), name)
        _typed(self.facts, PcMeleeFacts, "PC melee facts")
        replace(self.facts)
        if self.npc_broken_exit_policy is not None:
            _typed(self.npc_broken_exit_policy,PcAdjacentNpcExitPolicy,"NPC Broken exit policy")
            replace(self.npc_broken_exit_policy)
            if self.npc_broken_exit_policy.destination_zone_id == self.facts.zone_id:
                raise ValueError("NPC exit must lead to a different adjacent Zone")
            if not self.facts.can_leave_zone:
                raise ValueError("NPC exit requires permission to leave the arena Zone")
        _integer(self.max_rounds, "max rounds", minimum=1)
        party = _ordered(self.party, "party")
        enemies = _ordered(self.enemies, "enemies")
        if not party or not enemies:
            raise ValueError("PC melee requires a nonempty party and Minions")
        pc_definitions = {}
        for member in party:
            _typed(member, PcMeleeParticipant, "PC participant")
            _canonical_tuple(member.target_priority, "PC target priority")
            _canonical_tuple(member.defeat_decisions, "PC defeat decisions")
            replace(member)
            if member.pc.id in pc_definitions and pc_definitions[member.pc.id] != member.pc:
                raise ValueError("conflicting PC definitions with the same ID")
            pc_definitions[member.pc.id] = member.pc
        definitions = {}
        for enemy in enemies:
            _readmit_profile_enemy(enemy)
            definition = enemy.definition
            if definition.id in definitions and definitions[definition.id] != definition:
                raise ValueError("conflicting Minion definitions with the same ID")
            definitions[definition.id] = definition
        pc_ids = tuple(member.actor_id for member in party)
        enemy_ids = tuple(enemy.state.actor_id for enemy in enemies)
        all_ids = (*pc_ids, *enemy_ids)
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("PC and Minion actor IDs must be distinct")
        for name, ids in (("pc_activation_order", pc_ids),
                          ("enemy_activation_order", enemy_ids), ("enemy_target_priority", pc_ids)):
            ordered = _ordered(getattr(self, name), name)
            for actor_id in ordered:
                _identifier(actor_id, name)
            if len(set(ordered)) != len(ordered) or set(ordered) != set(ids):
                raise ValueError(f"{name} must contain every member of its side exactly once")
            object.__setattr__(self, name, ordered)
        for member in party:
            if set(member.target_priority) != set(enemy_ids):
                raise ValueError("each PC target priority must include every Minion exactly once")
            if member.ally_recover_policy is not None and member.ally_recover_policy.beneficiary_id not in pc_ids:
                raise ValueError("ally Recover beneficiary must be in the PC party")
            if member.help_policy is not None:
                beneficiary_id = member.help_policy.beneficiary_id
                if beneficiary_id not in pc_ids:
                    raise ValueError("Help beneficiary must be in the PC party")
                beneficiary = next(other for other in party if other.actor_id == beneficiary_id)
                if beneficiary.policy is not PcMeleePolicy.ATTACK_OR_RECOVER_SELF:
                    raise ValueError("the first Help slice cannot target another helper")
                if (member.help_policy.target is PcHelpTarget.MELEE_ATTACK
                        and self.pc_activation_order.index(member.actor_id) >= self.pc_activation_order.index(beneficiary_id)):
                    raise ValueError("Help beneficiary must activate later in this round")
        object.__setattr__(self, "party", party)
        object.__setattr__(self, "enemies", enemies)
        validate_pc_npc_help_policies(self)
        validate_pc_npc_grudge_policies(self)
        validate_pc_npc_blood_rage_policy(self)
        validate_pc_flagellant_policies(self)
        _canonical_tuple(self.npc_extra_attack_actor_ids,"NPC extra Attack actors")
        for actor_id in self.npc_extra_attack_actor_ids:
            _identifier(actor_id,"NPC extra Attack actor")
            if actor_id not in enemy_ids or self.enemy(actor_id).definition.id!='pc-book-npc:bear_sweeping_claws':
                raise ValueError('NPC extra Attack requires a canonical Bear Sweeping Claws opponent')
        if len(set(self.npc_extra_attack_actor_ids))!=len(self.npc_extra_attack_actor_ids):
            raise ValueError('NPC extra Attack actors must be unique')

    def participant(self, actor_id: str) -> PcMeleeParticipant:
        _identifier(actor_id, "PC actor")
        for member in self.party:
            if member.actor_id == actor_id:
                return member
        raise ValueError("unknown PC melee participant")

    def enemy(self, actor_id: str) -> NpcParticipantSnapshot:
        _identifier(actor_id, "enemy actor")
        for enemy in self.enemies:
            if enemy.state.actor_id == actor_id:
                return enemy
        raise ValueError("unknown PC melee enemy")


def validate_pc_melee_scenario_admission(scenario: PcMeleeScenario) -> None:
    """Re-admit canonical full input before execution, including nested values."""
    _typed(scenario, PcMeleeScenario, "PC melee scenario")
    for name in ("party", "enemies", "pc_activation_order", "enemy_activation_order", "enemy_target_priority"):
        _canonical_tuple(getattr(scenario, name), name)
    replace(scenario)


def _readmit_fate(fate: FateSessionState, actor_id: str) -> None:
    _typed(fate, FateSessionState, "PC Fate state")
    _typed(fate.has_lucky, bool, "Lucky fact")
    for name, cls in (("spends", FateSpendRecord), ("refreshes", FateRefreshRecord),
                      ("burns", FateBurnRecord)):
        for item in _canonical_tuple(getattr(fate, name), f"Fate {name}"):
            _typed(item, cls, f"Fate {name} record")
            replace(item)
    _canonical_tuple(fate.resource_event_ids, "Fate resource event order")
    replace(fate)
    if fate.actor_id != actor_id:
        raise ValueError("Fate belongs to another PC")
    if fate.has_lucky:
        raise ValueError("Lucky is outside the first PC melee scenario")


def _readmit_profile_enemy(enemy: NpcParticipantSnapshot) -> None:
    _typed(enemy, NpcParticipantSnapshot, "Minion snapshot")
    definition, state = enemy.definition, enemy.state
    _typed(definition, NpcDefinition, "Minion definition")
    _typed(state, NpcParticipantState, "Minion state")
    for value, name in ((definition.id, "Minion definition ID"),
                        (definition.source_rule_id, "Minion source rule"),
                        (state.actor_id, "Minion actor ID"),
                        (state.definition_id, "Minion state definition ID")):
        _identifier(value, name)
    _typed(definition.injury_policy, TargetInjuryPolicy, "Minion injury policy")
    _typed(state.side, CombatSide, "Minion side")
    if definition.injury_policy not in (TargetInjuryPolicy.MINION, TargetInjuryPolicy.BRUTE) or state.side is not CombatSide.OPPOSITION:
        raise ValueError("PC melee enemies must be opposition Minions or Brutes")
    _integer(definition.wound_limit, "NPC profile wound limit", minimum=1)
    _readmit_resilience(definition.resilience)
    _readmit_resilience(state.current_resilience)
    attacks = _canonical_tuple(definition.attacks, "Minion attacks")
    protection = _canonical_tuple(definition.protection, "Minion protection")
    if len(attacks) != 1 or len(protection) != 1:
        raise ValueError("Minion requires one Melee attack and one Protection profile")
    attack, defence = attacks[0], protection[0]
    _typed(attack, NpcAttackProfile, "Minion attack")
    _typed(defence, NpcProtectionProfile, "Minion Defence")
    for value, name in ((attack.id, "Minion attack ID"),
                        (attack.source_rule_id, "Minion attack source"),
                        (defence.source_rule_id, "Minion Defence source")):
        _identifier(value, name)
    _typed(attack.skill, Skill, "Minion attack Skill")
    _typed(defence.skill, Skill, "Minion Protection Skill")
    _typed(attack.range_min, RangedWeaponRange, "Minion minimum Range")
    _typed(attack.range_max, RangedWeaponRange, "Minion maximum Range")
    _readmit_inline(attack.test_profile,expected_pool_cap=(8
        if definition.id in ('pc-book-npc:minotaur_greataxe','pc-book-npc:bestigor_massive_axe') else None))
    _readmit_inline(defence.test_profile,expected_pool_cap=None)
    _typed(attack.damage, DamageProfile, "Minion Damage")
    replace(attack.damage)
    _canonical_tuple(attack.secondary_effects, "Minion secondary effects")
    validate_pc_hit_effects(attack.secondary_effects)
    replace(attack)
    replace(defence)
    _typed(attack.ignores_armour, bool, "Minion ignores armour")
    if attack.hands is not None:
        _typed(attack.hands, RangedWeaponHands, "Minion weapon hands")
    if (attack.skill is not Skill.MELEE
            or attack.range_min is not RangedWeaponRange.CLOSE
            or attack.range_max not in (RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT)
            or attack.damage.success_multiplier != 1 or attack.ignores_armour
            or defence.skill not in ((Skill.STEALTH,) if definition.id=='pc-book-npc:halfling_thief_dagger'
                else (Skill.DEFENCE,Skill.ATHLETICS))
            or attack.hands is None and defence.skill is not Skill.ATHLETICS):
        raise ValueError("unsupported Minion attack or Protection profile")
    injury = state.injury
    _typed(injury, ProfileInjuryState, "Minion injury")
    _typed(injury.conditions, ConditionState, "Minion Conditions")
    _typed(injury.conditions.conditions, frozenset, "Minion Condition set")
    replace(injury.conditions)
    replace(injury)
    _integer(injury.wounds, "NPC Wounds", minimum=0)
    _integer(injury.wound_limit, "NPC state wound limit", minimum=1)
    _typed(injury.defeated, bool, "NPC defeated flag")
    _typed(state.wields_weapon, bool, "NPC weapon eligibility")
    _typed(state.holds_shield, bool, "NPC shield eligibility")
    _canonical_tuple(state.available_attack_ids, "Minion available attacks")
    for attack_id in state.available_attack_ids:
        _identifier(attack_id, "available Minion attack ID")
    replace(state)
    replace(definition)
    replace(enemy)
    if (injury.wounds or injury.defeated or injury.defeat_cause is not None or injury.conditions.conditions
            or state.wields_weapon is not (attack.hands is not None)
            or state.holds_shield and attack.hands is not RangedWeaponHands.ONE_HANDED
            or state.current_resilience != definition.resilience
            or state.available_attack_ids != (attack.id,)):
        raise ValueError("PC melee requires fresh healthy NPCs and consistent armed/natural attacks and shield hands")
    from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
    validate_pc_book_npc_definition(definition)
    if definition.id.startswith('pc-book-npc:'):
        shield = definition.id in ('pc-book-npc:goblin_warrior_spear','pc-book-npc:night_goblin_spear',
            'pc-book-npc:ungor_spear','pc-book-npc:orc_boy_spear_shield','pc-book-npc:big_un_spear_shield',
            'pc-book-npc:centigor_spear','pc-book-npc:gor_axe_shield','pc-book-npc:empire_knight_lance_shield')
        if state.holds_shield is not shield:
            raise ValueError('book NPC shield state differs from its canonical combat loadout')


def _readmit_inline(profile: InlineProfile,*,expected_pool_cap: int | None) -> None:
    _typed(profile, InlineProfile, "Minion numeric profile")
    replace(profile)
    if profile.pool_cap is not None:
        _typed(profile.pool_cap,int,"NPC pool cap")
    if profile.pool_cap!=expected_pool_cap:
        raise ValueError("NPC pool cap differs from its admitted canonical attack/Protection source")


def _readmit_resilience(value: ResilienceProfile) -> None:
    _typed(value, ResilienceProfile, "Minion Resilience")
    replace(value)


def _typed(value, cls, name: str) -> None:
    if type(value) is not cls:
        raise TypeError(f"{name} must be {cls.__name__}")


def _identifier(value: str, name: str) -> None:
    _typed(value, str, name)
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _integer(value: int, name: str, *, minimum: int) -> None:
    _typed(value, int, name)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _ordered(value, name: str) -> tuple:
    if type(value) not in (tuple, list):
        raise TypeError(f"{name} must be an ordered list or tuple")
    return tuple(value)


def _canonical_tuple(value, name: str) -> tuple:
    _typed(value, tuple, name)
    return value
