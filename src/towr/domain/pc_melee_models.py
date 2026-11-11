"""Immutable authored input for the first PC melee encounter (ADR-0065)."""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.attack_models import ConditionImpactSpec, DamageProfile, ResilienceProfile, ProneBeforeGiveGroundSpec
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
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponHands, RangedWeaponId, RangedWeaponRange, ranged_weapon_combat_profile,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,validate_pc_npc_help_policies
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy,validate_pc_npc_grudge_policies
from towr.domain.pc_npc_blood_rage_policy_models import validate_pc_npc_blood_rage_policy
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,validate_pc_flagellant_policies
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy,validate_pc_warped_form_policies
from towr.domain.pc_npc_net_policy_models import PcNpcNetPolicy,validate_pc_npc_net_policies,NET_DEFINITION_ID
from towr.domain.pc_npc_pistol_source_models import (
    PC_NPC_PISTOL_DEFINITION_IDS, PcNpcPistolPolicy, validate_pc_npc_pistol_policies,
)
from towr.domain.pc_npc_close_shooting_models import (
    PcNpcCloseShootingProtectionPolicy, pc_close_shooting_protection_profile,
)
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
    PISTOL = "pistol"
    REPEATER_HANDBOW = "repeater_handbow"
    REPEATER_PISTOL = "repeater_pistol"
    SHORTBOW = "shortbow"
    WARBOW = "warbow"
    LONGBOW = "longbow"
    CROSSBOW = "crossbow"
    REPEATER_CROSSBOW = "repeater_crossbow"
    HANDGUN = "handgun"
    REPEATER_HANDGUN = "repeater_handgun"
    SLING = "sling"
    BLUNDERBUSS = "blunderbuss"
    HOCHLAND_LONG_RIFLE = "hochland_long_rifle"


PC_BOW_WEAPONS = (PcMeleeWeapon.SHORTBOW, PcMeleeWeapon.WARBOW, PcMeleeWeapon.LONGBOW)
PC_FREE_RELOAD_WEAPONS = (*PC_BOW_WEAPONS, PcMeleeWeapon.SLING)
PC_CROSSBOW_WEAPONS = (PcMeleeWeapon.CROSSBOW, PcMeleeWeapon.REPEATER_CROSSBOW)
PC_HANDGUN_WEAPONS = (PcMeleeWeapon.HANDGUN, PcMeleeWeapon.REPEATER_HANDGUN)
PC_TWO_HANDED_RANGED_WEAPONS = (*PC_BOW_WEAPONS, *PC_CROSSBOW_WEAPONS, *PC_HANDGUN_WEAPONS,
    PcMeleeWeapon.BLUNDERBUSS, PcMeleeWeapon.HOCHLAND_LONG_RIFLE)
PC_RANGED_WEAPONS = (PcMeleeWeapon.PISTOL, PcMeleeWeapon.REPEATER_HANDBOW,
    PcMeleeWeapon.REPEATER_PISTOL, *PC_TWO_HANDED_RANGED_WEAPONS, PcMeleeWeapon.SLING)


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
            if self.protection_skill not in (Skill.DEFENCE,Skill.ATHLETICS,Skill.MELEE):
                raise ValueError("Protection Help requires Defence, Athletics or Melee")


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
            if skill not in (Skill.MELEE, Skill.DEFENCE, Skill.ATHLETICS, Skill.ENDURANCE,
                    Skill.SHOOTING, Skill.DEXTERITY):
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


class PcShieldHandConflictPolicy(str, Enum):
    WEAPON_FIRST = "weapon_first"


class PcShieldRecoveryPolicy(str, Enum):
    RESTORE_BEFORE_ATTACK = "restore_before_attack"


@dataclass(frozen=True, slots=True)
class PcShieldLoadout:
    initial_hand: PcWeaponHand
    hand_conflict_policy: PcShieldHandConflictPolicy
    recovery_policy: PcShieldRecoveryPolicy

    def __post_init__(self) -> None:
        _typed(self.initial_hand, PcWeaponHand, "shield initial hand")
        _typed(self.hand_conflict_policy, PcShieldHandConflictPolicy, "shield hand conflict policy")
        _typed(self.recovery_policy, PcShieldRecoveryPolicy, "shield recovery policy")


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
        if pc_weapon_requires_two_hands(self.weapon) or self.weapon in PC_RANGED_WEAPONS:
            raise ValueError("backup weapon must be a supported one-handed melee weapon")


class PcRangedReloadHandPolicy(str, Enum):
    TWO_AVAILABLE_HANDS = "two_available_hands"


class PcRepeaterBonusPolicy(str, Enum):
    WHEN_AVAILABLE = "when_available"
    NEVER = "never"


@dataclass(frozen=True, slots=True)
class PcAimSecondActionPolicy:
    minimum_remaining_session_spends: int

    def __post_init__(self) -> None:
        _integer(self.minimum_remaining_session_spends, "Aim Second Action session reserve", minimum=0)


@dataclass(frozen=True, slots=True)
class PcRangedProfile:
    ballistic_skill: int
    shooting: int
    initiative: int | None = None
    dexterity: int | None = None
    has_blackpowder_lore: bool | None = None
    has_blackpowder_kit: bool | None = None
    ammunition_supply_confirmed: bool = False
    initially_loaded: bool | None = None
    reload_hand_policy: PcRangedReloadHandPolicy | None = None
    repeater_bonus_policy: PcRepeaterBonusPolicy | None = field(default=None, kw_only=True)
    awareness: int | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for name in ("ballistic_skill", "shooting"):
            _integer(getattr(self, name), name, minimum=1)
        self.shooting_profile
        if (self.initiative is None) != (self.dexterity is None):
            raise ValueError("Reload characteristics and Skills must be supplied together")
        if self.initiative is not None:
            _integer(self.initiative, "initiative", minimum=1)
            _integer(self.dexterity, "dexterity", minimum=1)
            self.dexterity_profile
        for name in ("has_blackpowder_lore", "has_blackpowder_kit"):
            value = getattr(self, name)
            if value is not None:
                _typed(value, bool, name)
                if not value:
                    raise ValueError(f"ranged firearm source requires confirmed {name}")
        _typed(self.ammunition_supply_confirmed, bool, "ammunition_supply_confirmed")
        if not self.ammunition_supply_confirmed:
            raise ValueError("ranged source requires ammunition_supply_confirmed")
        if self.initially_loaded is not None:
            _typed(self.initially_loaded, bool, "initially_loaded")
            if not self.initially_loaded:
                raise ValueError("ranged source requires initially_loaded")
        if self.reload_hand_policy is not None:
            _typed(self.reload_hand_policy, PcRangedReloadHandPolicy, "ranged reload hand policy")
        if any(value is not None for value in (
                self.initiative, self.dexterity, self.initially_loaded, self.reload_hand_policy)):
            if self.initiative is None or self.dexterity is None:
                raise ValueError('Exacting source requires Initiative and Dexterity')
            _typed(self.initially_loaded, bool, 'initially_loaded')
            _typed(self.reload_hand_policy, PcRangedReloadHandPolicy, 'ranged reload hand policy')
        if self.repeater_bonus_policy is not None:
            _typed(self.repeater_bonus_policy, PcRepeaterBonusPolicy, "Repeater bonus policy")
        if self.awareness is not None:
            _integer(self.awareness, "Awareness", minimum=1)
            self.awareness_profile

    @property
    def shooting_profile(self) -> TestProfile:
        return TestProfile(self.ballistic_skill, self.shooting)

    @property
    def dexterity_profile(self) -> TestProfile:
        if self.initiative is None or self.dexterity is None:
            raise ValueError("free-reload bows have no authored Dexterity Test")
        return TestProfile(self.initiative, self.dexterity)


    @property
    def awareness_profile(self) -> TestProfile:
        if self.initiative is None or self.awareness is None:
            raise ValueError("Aim requires authored Initiative and Awareness")
        return TestProfile(self.initiative, self.awareness)


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
    ranged: PcRangedProfile | None = field(default=None, kw_only=True)

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
        if self.weapon in PC_RANGED_WEAPONS:
            _typed(self.ranged, PcRangedProfile, "PC ranged profile")
            replace(self.ranged)
            free_reload = self.weapon in PC_FREE_RELOAD_WEAPONS
            if self.weapon is PcMeleeWeapon.HOCHLAND_LONG_RIFLE:
                self.ranged.awareness_profile
            elif self.ranged.awareness is not None:
                raise ValueError('Awareness source is admitted only for Hochland')
            firearm = self.weapon in (PcMeleeWeapon.PISTOL, PcMeleeWeapon.REPEATER_PISTOL,
                *PC_HANDGUN_WEAPONS, PcMeleeWeapon.BLUNDERBUSS, PcMeleeWeapon.HOCHLAND_LONG_RIFLE)
            for name in ('has_blackpowder_lore', 'has_blackpowder_kit'):
                value = getattr(self.ranged, name)
                if (firearm and value is not True) or (not firearm and value is not None):
                    raise ValueError('Blackpowder Lore/kit are required only for firearm PC loadouts')
            if free_reload:
                if any(getattr(self.ranged, name) is not None for name in (
                        'initiative', 'dexterity', 'initially_loaded', 'reload_hand_policy',
                        'repeater_bonus_policy')):
                    raise ValueError('free-reload ranged source forbids Exacting/Repeater fields')
            else:
                self.ranged.dexterity_profile
                if self.ranged.initially_loaded is not True:
                    raise ValueError('Exacting ranged source requires an initially loaded weapon')
                _typed(self.ranged.reload_hand_policy, PcRangedReloadHandPolicy, 'ranged reload hand policy')
            if self.weapon in (PcMeleeWeapon.PISTOL, PcMeleeWeapon.CROSSBOW, PcMeleeWeapon.HANDGUN, PcMeleeWeapon.BLUNDERBUSS, PcMeleeWeapon.HOCHLAND_LONG_RIFLE):
                if self.ranged.repeater_bonus_policy is not None:
                    raise ValueError(f'ordinary {self.weapon.value.title()} cannot carry Repeater bonus policy')
            elif not free_reload:
                _typed(self.ranged.repeater_bonus_policy, PcRepeaterBonusPolicy, 'Repeater bonus policy')
        elif self.ranged is not None:
            raise ValueError("ranged profile requires an admitted ranged primary weapon")

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
            if name not in ("all_opponents_close", "outnumbering_bonus_approved", "can_leave_zone") and not value:
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
    shield: PcShieldLoadout | None = field(default=None, kw_only=True)
    close_shooting_protection_skill: Skill | None = field(default=None, kw_only=True)
    aim_second_action_policy: PcAimSecondActionPolicy | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "PC actor")
        _typed(self.pc, PcMeleeDefinition, "PC definition")
        replace(self.pc)
        _readmit_fate(self.fate, self.actor_id, allow_lucky=self.pc.weapon is PcMeleeWeapon.HOCHLAND_LONG_RIFLE)
        if self.close_shooting_protection_skill is not None:
            _typed(self.close_shooting_protection_skill, Skill, "PC Close Shooting Protection skill")
            if self.close_shooting_protection_skill not in (Skill.MELEE, Skill.ATHLETICS):
                raise ValueError("PC Close Shooting Protection choice requires Melee or Athletics")
        for name, cls in (("policy", PcMeleePolicy), ("fate_policy", PcFatePolicy),
                          ("random_side_policy", PcRandomSidePolicy), ("heavy_wound_policy", PcHeavyWoundPolicy)):
            _typed(getattr(self, name), cls, name)
        if self.pc.weapon in PC_RANGED_WEAPONS:
            if self.policy is not PcMeleePolicy.ATTACK_OR_RECOVER_SELF:
                raise ValueError("ranged PC requires ordinary Attack/self Recover policy")
            if any(value is not None for value in (self.help_policy, self.ally_recover_policy)):
                raise ValueError("ranged PC cannot carry Help or ally Recover")
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        grip_type = PcTwoHandedGrip if pc_weapon_requires_two_hands(self.pc.weapon) else PcWeaponHand
        _typed(self.initial_weapon_hand,grip_type,"initial weapon grip")
        if self.shield is not None:
            _typed(self.shield, PcShieldLoadout, "PC shield loadout")
            replace(self.shield)
            if self.pc.weapon not in (PcMeleeWeapon.DAGGER, PcMeleeWeapon.STAFF,
                    PcMeleeWeapon.AXE, PcMeleeWeapon.SWORD, PcMeleeWeapon.WARHAMMER,
                    PcMeleeWeapon.MORNING_STAR, PcMeleeWeapon.PISTOL,
                    PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL, PcMeleeWeapon.SLING):
                raise ValueError("shield requires a supported one-handed primary weapon")
            if self.shield.initial_hand is self.initial_weapon_hand:
                raise ValueError("shield and weapon require opposite initial hands")
            if self.backup_weapon_policy is not None and self.pc.weapon not in PC_RANGED_WEAPONS:
                raise ValueError("shield cannot carry a backup weapon policy")
        if self.backup_weapon_policy is not None:
            _typed(self.backup_weapon_policy,PcBackupWeaponPolicy,"backup weapon policy")
            replace(self.backup_weapon_policy)
            if (grip_type is not PcTwoHandedGrip and self.pc.weapon not in PC_RANGED_WEAPONS
                    or self.pc.strength < 2):
                raise ValueError("backup requires a two-handed or ranged primary and Strength to carry two weapons")
        for value, cls in ((self.near_miss_policy,PcNearMissPolicy),(self.glorious_policy,PcGloriousPolicy)):
            if value is not None:
                _typed(value,cls,"Fate strategy")
                replace(value)
        if self.glorious_policy is not None:
            _canonical_tuple(self.glorious_policy.skills,"Glorious skills")
        if self.aim_second_action_policy is not None:
            _typed(self.aim_second_action_policy, PcAimSecondActionPolicy, "Aim Second Action policy")
            replace(self.aim_second_action_policy)
            if self.pc.weapon is not PcMeleeWeapon.HOCHLAND_LONG_RIFLE:
                raise ValueError('Aim Second Action policy requires Hochland')
        configured = (self.near_miss_policy is not None or self.glorious_policy is not None
            or self.aim_second_action_policy is not None)
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
class PcShortRangeOpening:
    party_clustered_confirmed: bool
    npc_approach_clear_confirmed: bool

    def __post_init__(self) -> None:
        for name in ('party_clustered_confirmed', 'npc_approach_clear_confirmed'):
            _typed(getattr(self, name), bool, name)
            if not getattr(self, name):
                raise ValueError(f'Short opening requires {name}')


@dataclass(frozen=True, slots=True)
class PcBlunderbussNearby:
    initial_npc_clustered_confirmed: bool
    target_priority: tuple[str, ...]

    def __post_init__(self) -> None:
        _typed(self.initial_npc_clustered_confirmed, bool, 'initial NPC cluster confirmation')
        if not self.initial_npc_clustered_confirmed:
            raise ValueError('Blunderbuss requires its confirmed initial NPC cluster')
        _canonical_tuple(self.target_priority, 'Blunderbuss target priority')
        for actor in self.target_priority:
            _identifier(actor, 'Blunderbuss nearby actor')
        if len(set(self.target_priority)) != len(self.target_priority):
            raise ValueError('Blunderbuss nearby targets cannot repeat')


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
    npc_warped_form_policies: tuple[PcWarpedFormPolicy, ...] = field(kw_only=True)
    npc_net_policies: tuple[PcNpcNetPolicy, ...] = field(default=(),kw_only=True)
    npc_pistol_policies: tuple[PcNpcPistolPolicy, ...] = field(default=(),kw_only=True)
    npc_close_shooting_protection_policies: tuple[PcNpcCloseShootingProtectionPolicy, ...] | None = field(default=None,kw_only=True)
    short_range_opening: PcShortRangeOpening | None = field(default=None,kw_only=True)
    blunderbuss_nearby: PcBlunderbussNearby | None = field(default=None,kw_only=True)

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
        has_ranged = any(member.pc.weapon in PC_RANGED_WEAPONS for member in party)
        close_shooting_profiles = {}
        policies = self.npc_close_shooting_protection_policies
        if policies is not None:
            _canonical_tuple(policies, 'NPC Close Shooting protection policies')
            if not policies:
                raise ValueError('NPC Close Shooting protection policies must be nonempty when supplied')
            if not has_ranged:
                raise ValueError('NPC Close Shooting protection policies require a ranged PC')
            for policy in policies:
                _typed(policy, PcNpcCloseShootingProtectionPolicy, 'NPC Close Shooting protection policy')
                replace(policy)
                if policy.actor_id in close_shooting_profiles:
                    raise ValueError('NPC Close Shooting protection actors must be unique')
                enemy = next((enemy for enemy in enemies if enemy.state.actor_id == policy.actor_id), None)
                if enemy is None:
                    raise ValueError('NPC Close Shooting protection actor must belong to the opposition')
                close_shooting_profiles[policy.actor_id] = pc_close_shooting_protection_profile(
                    enemy.definition, policy.skill)
        if has_ranged:
            for enemy in enemies:
                if enemy.state.actor_id in close_shooting_profiles:
                    continue
                skill = enemy.definition.protection[0].skill
                if skill is Skill.STEALTH:
                    from towr.domain.protection_models import HalflingStealthProtectionPermission
                    HalflingStealthProtectionPermission(enemy.state.actor_id,enemy.definition)
                    continue
                if skill is not Skill.ATHLETICS and not (
                        skill is Skill.DEFENCE and enemy.state.holds_shield):
                    raise ValueError("ranged opponents require Athletics, actual shield Defence or canonical Thief Stealth")
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
        validate_pc_npc_pistol_policies(self)
        validate_pc_npc_grudge_policies(self)
        validate_pc_npc_blood_rage_policy(self)
        validate_pc_flagellant_policies(self)
        validate_pc_warped_form_policies(self.npc_warped_form_policies,party,enemies)
        validate_pc_npc_net_policies(self.npc_net_policies,enemies)
        _canonical_tuple(self.npc_extra_attack_actor_ids,"NPC extra Attack actors")
        for actor_id in self.npc_extra_attack_actor_ids:
            _identifier(actor_id,"NPC extra Attack actor")
            if actor_id not in enemy_ids or self.enemy(actor_id).definition.id not in (
                    'pc-book-npc:bear_sweeping_claws','pc-book-npc:bear_crushing_weight','pc-book-npc:great_stag'):
                raise ValueError('NPC extra Attack requires a canonical Bear or Great Stag opponent')
        if len(set(self.npc_extra_attack_actor_ids))!=len(self.npc_extra_attack_actor_ids):
            raise ValueError('NPC extra Attack actors must be unique')
        has_blunderbuss = any(member.pc.weapon is PcMeleeWeapon.BLUNDERBUSS for member in party)
        if has_blunderbuss:
            _typed(self.blunderbuss_nearby, PcBlunderbussNearby, 'Blunderbuss nearby source')
            replace(self.blunderbuss_nearby)
            if set(self.blunderbuss_nearby.target_priority) != set(enemy_ids):
                raise ValueError('Blunderbuss nearby priority must include every NPC exactly once')
        elif self.blunderbuss_nearby is not None:
            raise ValueError('Blunderbuss nearby source requires a Blunderbuss PC')
        _validate_short_range_opening(self)

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


def _validate_short_range_opening(scenario: PcMeleeScenario) -> None:
    opening = scenario.short_range_opening
    if opening is None:
        if not scenario.facts.all_opponents_close:
            raise ValueError('Short distance requires its explicit short_range_opening source')
        if any(member.pc.weapon in PC_RANGED_WEAPONS and
                ranged_weapon_combat_profile(RangedWeaponId(member.pc.weapon.value)).optimum_range_min
                is not RangedWeaponRange.CLOSE for member in scenario.party):
            raise ValueError('ranged weapons without Close optimum cannot begin in the all-Close encounter')
        return
    _typed(opening, PcShortRangeOpening, 'Short opening')
    replace(opening)
    if scenario.facts.all_opponents_close or scenario.facts.can_leave_zone:
        raise ValueError('Short opening requires non-Close initial opponents and no Zone exit')
    if scenario.npc_broken_exit_policy is not None:
        raise ValueError('Short opening cannot use an adjacent NPC exit')
    if scenario.npc_close_shooting_protection_policies is not None:
        raise ValueError('Short opening requires ordinary Athletics Protection without an override')
    if any((scenario.npc_help_policies, scenario.npc_extra_attack_actor_ids,
            scenario.npc_grudge_policies, scenario.npc_blood_rage_actor_ids,
            scenario.npc_flagellant_policies, scenario.npc_warped_form_policies,
            scenario.npc_net_policies, scenario.npc_pistol_policies)):
        raise ValueError('Short opening cannot carry NPC ability policies')
    if any(member.pc.weapon not in PC_RANGED_WEAPONS for member in scenario.party):
        raise ValueError('Short opening requires a ranged primary for every PC')
    for enemy in scenario.enemies:
        definition = enemy.definition
        attack = definition.attacks[0]
        if (definition.id.startswith('pc-book-npc:')
                or definition.injury_policy is not TargetInjuryPolicy.MINION
                or definition.wound_limit != 1 or len(definition.attacks) != 1
                or attack.skill is not Skill.MELEE
                or attack.range_min is not RangedWeaponRange.CLOSE
                or attack.range_max is not RangedWeaponRange.CLOSE
                or attack.condition_impact is not None or attack.secondary_effects
                or attack.ignores_armour or enemy.state.holds_shield
                or len(definition.protection) != 1
                or definition.protection[0].skill is not Skill.ATHLETICS):
            raise ValueError('Short opening requires simple authored Close Melee Minions and Athletics')


def validate_pc_melee_scenario_admission(scenario: PcMeleeScenario) -> None:
    """Re-admit canonical full input before execution, including nested values."""
    _typed(scenario, PcMeleeScenario, "PC melee scenario")
    for name in ("party", "enemies", "pc_activation_order", "enemy_activation_order", "enemy_target_priority"):
        _canonical_tuple(getattr(scenario, name), name)
    replace(scenario)


def _readmit_fate(fate: FateSessionState, actor_id: str, *, allow_lucky: bool = False) -> None:
    _typed(allow_lucky, bool, "Lucky admission")
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
    if fate.has_lucky and not allow_lucky:
        raise ValueError("Lucky is admitted only for Hochland in the current PC scenario")


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
    great_stag = definition.id == 'pc-book-npc:great_stag'
    net_goblin = definition.id == NET_DEFINITION_ID
    npc_pistol = definition.id in PC_NPC_PISTOL_DEFINITION_IDS
    if len(attacks) != (2 if great_stag or net_goblin else 1) or len(protection) != 1:
        raise ValueError("NPC requires one primary Melee attack and one Protection; only canonical Stag/Net loadouts have a second profile")
    if (definition.id.startswith('pc-book-npc:') and not net_goblin
            and (definition.resilience.armoured is not None or state.current_resilience.armoured is not None)):
        raise ValueError('explicit armoured metadata on a canonical NPC requires the Net loadout')
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
        if definition.id in ('pc-book-npc:minotaur_greataxe','pc-book-npc:bestigor_massive_axe',
            'pc-book-npc:bear_crushing_weight')
        else 6 if definition.id=='pc-book-npc:imperial_ogre_greathammer' else None))
    _readmit_inline(defence.test_profile,expected_pool_cap=None)
    _typed(attack.damage, DamageProfile, "Minion Damage")
    replace(attack.damage)
    _canonical_tuple(attack.secondary_effects, "Minion secondary effects")
    validate_pc_hit_effects(attack.secondary_effects)
    if (any(type(effect) is ProneBeforeGiveGroundSpec for effect in attack.secondary_effects)
            and definition.id!='pc-book-npc:bear_crushing_weight'):
        raise ValueError('pre-Stagger Prone requires canonical Bear Crushing Weight')
    replace(attack)
    replace(defence)
    _typed(attack.ignores_armour, bool, "Minion ignores armour")
    if attack.hands is not None:
        _typed(attack.hands, RangedWeaponHands, "Minion weapon hands")
    if (attack.skill is not (Skill.SHOOTING if npc_pistol else Skill.MELEE)
            or attack.range_min is not RangedWeaponRange.CLOSE
            or attack.range_max not in ((RangedWeaponRange.SHORT,RangedWeaponRange.MEDIUM)
                if npc_pistol else (RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT))
            or attack.damage.success_multiplier != 1 or attack.ignores_armour is not npc_pistol
            or defence.skill not in ((Skill.STEALTH,) if definition.id=='pc-book-npc:halfling_thief_dagger'
                else (Skill.DEFENCE,Skill.ATHLETICS))
            or attack.hands is None and defence.skill is not Skill.ATHLETICS):
        raise ValueError("unsupported Minion attack or Protection profile")
    if great_stag:
        trample = attacks[1]
        _typed(trample,NpcAttackProfile,"Great Stag Trample profile")
        _identifier(trample.id,"Trample attack ID")
        _identifier(trample.source_rule_id,"Trample source Rule ID")
        _typed(trample.skill,Skill,"Trample Skill")
        _readmit_inline(trample.test_profile,expected_pool_cap=None)
        _typed(trample.damage,DamageProfile,"Trample Damage")
        replace(trample.damage)
        _typed(trample.range_min,RangedWeaponRange,"Trample minimum range")
        _typed(trample.range_max,RangedWeaponRange,"Trample maximum range")
        _typed(trample.ignores_armour,bool,"Trample ignores armour")
        _canonical_tuple(trample.secondary_effects,"Trample secondary effects")
        if (trample.skill is not Skill.BRAWN or trample.range_min is not RangedWeaponRange.CLOSE
                or trample.range_max is not RangedWeaponRange.CLOSE or trample.hands is not None
                or trample.ignores_armour or trample.secondary_effects or trample.damage.success_multiplier!=1):
            raise ValueError('Great Stag Trample requires its natural Brawn Close Damage profile')
        replace(trample)
    if net_goblin:
        net = attacks[1]
        _typed(net,NpcAttackProfile,'Weighted Net profile')
        _readmit_inline(net.test_profile,expected_pool_cap=6)
        _typed(net.condition_impact,ConditionImpactSpec,'Weighted Net primary Condition')
        replace(net.condition_impact)
        replace(net)
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
            or state.available_attack_ids != tuple(profile.id for profile in attacks)):
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
