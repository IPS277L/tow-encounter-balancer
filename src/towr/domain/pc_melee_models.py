"""Immutable authored input for the first PC melee encounter (ADR-0065)."""
from dataclasses import dataclass, field, replace
from towr.domain.oath_context_models import OathBattleContext, validate_oath_context
from enum import Enum
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.battlefield_music_models import BattlefieldMusicAcoustics
from towr.domain.pc_single_combat_models import PcSingleCombatPair
from towr.domain.pc_mount_models import CombatMount, RiderKind, initial_pc_mounts
from towr.domain.armour_models import ArmourLoadout

from towr.domain.attack_models import ConditionImpactSpec, DamageProfile, ResilienceProfile, ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.pc_magic_source_models import PcWizardProfile
from towr.domain.talent_models import AcquiredTalent, TalentOwnerFacts, has_talent
from towr.domain.tool_inventory_models import ToolItemSource, initial_tool_inventory, validate_tool_equipment_hands
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
from towr.domain.pc_npc_ranged_source_models import (
    PC_NPC_RANGED_DEFINITION_IDS, PcNpcRangedPolicy, validate_pc_npc_ranged_policies,
)
from towr.domain.pc_npc_close_shooting_models import (
    PcNpcCloseShootingProtectionPolicy, pc_close_shooting_protection_profile,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill, TestProfile
from towr.domain.turn_models import CombatSide
from towr.domain.pc_hit_condition_models import validate_pc_hit_effects


from towr.domain.weapon_catalog import WeaponKind as PcMeleeWeapon
from towr.domain.weapon_inventory_models import (
    WeaponHand as PcWeaponHand, WeaponTwoHandedGrip as PcTwoHandedGrip,
)

# Source admission follows implemented owners, not the presence of a catalogue
# enum. New Magic/Throwing effects join this set only with full execution.
PC_EXECUTABLE_WEAPONS = (
    PcMeleeWeapon.UNARMED,
    PcMeleeWeapon.KNUCKLEDUSTERS,
    PcMeleeWeapon.CAVALRY_SPEAR,
    PcMeleeWeapon.LANCE,
    PcMeleeWeapon.STAFF,
    PcMeleeWeapon.SWORD,
    PcMeleeWeapon.DAGGER,
    PcMeleeWeapon.AXE,
    PcMeleeWeapon.WARHAMMER,
    PcMeleeWeapon.MORNING_STAR,
    PcMeleeWeapon.FOOT_SPEAR,
    PcMeleeWeapon.POLEARM,
    PcMeleeWeapon.PICKAXE,
    PcMeleeWeapon.FLAIL,
    PcMeleeWeapon.BILLHOOK,
    PcMeleeWeapon.HALBERD,
    PcMeleeWeapon.GLAIVE,
    PcMeleeWeapon.GREATAXE,
    PcMeleeWeapon.GREATSWORD,
    PcMeleeWeapon.GREATHAMMER,
    PcMeleeWeapon.PISTOL,
    PcMeleeWeapon.REPEATER_HANDBOW,
    PcMeleeWeapon.REPEATER_PISTOL,
    PcMeleeWeapon.SHORTBOW,
    PcMeleeWeapon.WARBOW,
    PcMeleeWeapon.LONGBOW,
    PcMeleeWeapon.CROSSBOW,
    PcMeleeWeapon.REPEATER_CROSSBOW,
    PcMeleeWeapon.HANDGUN,
    PcMeleeWeapon.REPEATER_HANDGUN,
    PcMeleeWeapon.SLING,
    PcMeleeWeapon.BLUNDERBUSS,
    PcMeleeWeapon.HOCHLAND_LONG_RIFLE,
    PcMeleeWeapon.WEIGHTED_NET,
    PcMeleeWeapon.ROCK,
    PcMeleeWeapon.THROWING_SPEAR,
    PcMeleeWeapon.THROWING_AXE,
    PcMeleeWeapon.THROWING_KNIVES,
    PcMeleeWeapon.OIL_FLASK,
    PcMeleeWeapon.BLASTING_CHARGE,
    PcMeleeWeapon.DRAGON_BOW,
    PcMeleeWeapon.DUELLIST_BLADES,
    PcMeleeWeapon.GROTARGGS_HAMMER,
    PcMeleeWeapon.HEADSMANS_AXE,
    PcMeleeWeapon.MORNING_STAR_OF_FRACASSE,
    PcMeleeWeapon.SCARAB_KNIFE,
    PcMeleeWeapon.TRICKSTER_BLADE,
    PcMeleeWeapon.UNWAVERING_SPEAR,
    PcMeleeWeapon.SWORD_OF_JUSTICE,
    PcMeleeWeapon.OGRE_PISTOL,
)


PC_THROWING_WEAPONS = (PcMeleeWeapon.ROCK,PcMeleeWeapon.THROWING_SPEAR,PcMeleeWeapon.THROWING_AXE,
    PcMeleeWeapon.WEIGHTED_NET,PcMeleeWeapon.THROWING_KNIVES,PcMeleeWeapon.OIL_FLASK,
    PcMeleeWeapon.BLASTING_CHARGE)
PC_BOW_WEAPONS = (PcMeleeWeapon.SHORTBOW, PcMeleeWeapon.WARBOW, PcMeleeWeapon.LONGBOW, PcMeleeWeapon.DRAGON_BOW)
PC_FREE_RELOAD_WEAPONS = (*PC_BOW_WEAPONS, PcMeleeWeapon.SLING)
PC_CROSSBOW_WEAPONS = (PcMeleeWeapon.CROSSBOW, PcMeleeWeapon.REPEATER_CROSSBOW)
PC_HANDGUN_WEAPONS = (PcMeleeWeapon.HANDGUN, PcMeleeWeapon.REPEATER_HANDGUN)
PC_TWO_HANDED_RANGED_WEAPONS = (*PC_BOW_WEAPONS, *PC_CROSSBOW_WEAPONS, *PC_HANDGUN_WEAPONS,
    PcMeleeWeapon.BLUNDERBUSS, PcMeleeWeapon.HOCHLAND_LONG_RIFLE)
PC_RANGED_WEAPONS = (PcMeleeWeapon.PISTOL, PcMeleeWeapon.REPEATER_HANDBOW,
    PcMeleeWeapon.REPEATER_PISTOL, PcMeleeWeapon.OGRE_PISTOL, *PC_TWO_HANDED_RANGED_WEAPONS, PcMeleeWeapon.SLING)


class PcMeleePolicy(str, Enum):
    ATTACK_OR_RECOVER_SELF = "attack_or_recover_self"
    AUTOMATIC_COMBAT = "automatic_combat"
    HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF = "help_ally_or_attack_or_recover_self"
    RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF = "recover_ally_or_attack_or_recover_self"


@dataclass(frozen=True, slots=True)
class PcAllyRecoverPolicy:
    beneficiary_id: str

    def __post_init__(self) -> None:
        _identifier(self.beneficiary_id,"ally Recover beneficiary")


class PcHelpTarget(str, Enum):
    ATTACK = "attack"
    FIRST_INCOMING_PROTECTION = "first_incoming_protection"


@dataclass(frozen=True, slots=True)
class PcHelpPolicy:
    beneficiary_id: str
    target: PcHelpTarget
    skill: Skill

    def __post_init__(self) -> None:
        _identifier(self.beneficiary_id,"Help beneficiary")
        _typed(self.target,PcHelpTarget,"Help target")
        _typed(self.skill,Skill,"Help Skill")
        if self.target is PcHelpTarget.ATTACK:
            if self.skill not in (Skill.MELEE,Skill.SHOOTING,Skill.THROWING,Skill.BRAWN):
                raise ValueError("Attack Help requires the actual Melee/Brawn/Shooting/Throwing Skill")
        else:
            if self.skill not in (Skill.DEFENCE,Skill.ATHLETICS,Skill.MELEE,Skill.ENDURANCE):
                raise ValueError("Protection Help requires Defence, Athletics, Endurance or Melee")


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
                    Skill.SHOOTING, Skill.DEXTERITY, Skill.WILLPOWER, Skill.LEADERSHIP, Skill.THROWING, Skill.BRAWN):
                raise ValueError("Glorious skill is outside the PC melee boundary")
        _integer(self.maximum_initial_successes, "Glorious success threshold", minimum=0)
        _integer(self.minimum_remaining_spends, "Glorious session reserve", minimum=0)
        object.__setattr__(self,"skills",skills)


class PcRandomSidePolicy(str, Enum):
    D10_LOW_LEFT_HIGH_RIGHT = "d10_low_left_high_right"


class PcHeavyWoundPolicy(str, Enum):
    CONTINUE_FIGHTING = "continue_fighting"


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



@dataclass(frozen=True, slots=True)
class PcBackupWeaponPolicy:
    weapon: PcMeleeWeapon
    preferred_hand: PcWeaponHand

    def __post_init__(self) -> None:
        _typed(self.weapon,PcMeleeWeapon,"backup weapon")
        _typed(self.preferred_hand,PcWeaponHand,"backup preferred hand")
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        if (pc_weapon_requires_two_hands(self.weapon) or self.weapon in PC_RANGED_WEAPONS
                or self.weapon is PcMeleeWeapon.UNARMED):
            raise ValueError("backup weapon must be a supported one-handed melee weapon")


class PcRangedReloadHandPolicy(str, Enum):
    TWO_AVAILABLE_HANDS = "two_available_hands"


class PcRepeaterBonusPolicy(str, Enum):
    WHEN_AVAILABLE = "when_available"
    NEVER = "never"
    AUTOMATIC = "automatic"


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
    reload_hand_policy: PcRangedReloadHandPolicy | None = None
    repeater_bonus_policy: PcRepeaterBonusPolicy | None = field(default=None, kw_only=True)
    awareness: int | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for name in ("ballistic_skill", "shooting"):
            _integer(getattr(self, name), name, minimum=1)
        self.shooting_profile
        if self.dexterity is not None and self.initiative is None:
            raise ValueError("Dexterity requires Initiative")
        if self.initiative is not None:
            _integer(self.initiative, "initiative", minimum=1)
        if self.dexterity is not None:
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
        if self.reload_hand_policy is not None:
            _typed(self.reload_hand_policy, PcRangedReloadHandPolicy, "ranged reload hand policy")
        if any(value is not None for value in (
                self.dexterity, self.reload_hand_policy)):
            if self.initiative is None or self.dexterity is None:
                raise ValueError('Exacting source requires Initiative and Dexterity')
            _typed(self.reload_hand_policy, PcRangedReloadHandPolicy, 'ranged reload hand policy')
        if self.repeater_bonus_policy is not None:
            _typed(self.repeater_bonus_policy, PcRepeaterBonusPolicy, "Repeater bonus policy")
        if self.awareness is not None:
            _integer(self.awareness, "Awareness", minimum=1)
            self.awareness_profile
        elif self.initiative is not None and self.dexterity is None:
            raise ValueError('Initiative without Reload requires Awareness for Aim')

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
    throwing: int | None = field(default=None,kw_only=True)
    brawn: int | None = field(default=None,kw_only=True)
    ballistic_skill: int | None = field(default=None,kw_only=True)
    fellowship: int | None = field(default=None,kw_only=True)
    leadership: int | None = field(default=None,kw_only=True)
    tools: tuple[ToolItemSource, ...] = field(default=(),kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.id, "PC definition")
        initial_tool_inventory(self.id, self.tools)
        for name in ("weapon_skill", "strength", "toughness", "agility"):
            _integer(getattr(self, name), name, minimum=1)
        for characteristic, skill in (
            (self.weapon_skill, self.melee), (self.weapon_skill, self.defence),
            (self.agility, self.athletics), (self.toughness, self.endurance),
        ):
            TestProfile(characteristic, skill)
        if self.fellowship is not None:
            _integer(self.fellowship, 'Fellowship', minimum=1)
        if self.leadership is not None:
            self.leadership_profile
        _typed(self.weapon, PcMeleeWeapon, "PC weapon")
        if self.weapon not in PC_EXECUTABLE_WEAPONS:
            raise ValueError("this weapon requires its unfinished encounter effect owner")
        for name in ('throwing','brawn'):
            value=getattr(self,name)
            if value is not None:
                _integer(value,name,minimum=1)
                if name == 'brawn':
                    TestProfile(self.strength,value)
        if self.ballistic_skill is not None:
            _integer(self.ballistic_skill,'Throwing Ballistic Skill',minimum=1)
        if self.throwing is not None:
            if self.ballistic_skill is None:
                raise ValueError('Throwing requires its explicit Ballistic Skill')
            self.throwing_profile
        elif self.ballistic_skill is not None:
            raise ValueError('separate Ballistic Skill belongs to the Throwing source')
        if self.weapon in PC_THROWING_WEAPONS and self.throwing is None:
            raise ValueError('Throwing weapons require explicit BS and Throwing')
        if self.weapon in (PcMeleeWeapon.UNARMED,PcMeleeWeapon.KNUCKLEDUSTERS,PcMeleeWeapon.GROTARGGS_HAMMER) and self.brawn is None:
            raise ValueError('Unarmed and Knuckledusters require explicit Brawn')
        _integer(self.armour_bonus, "PC armour bonus", minimum=0)
        if self.ranged is not None:
            _typed(self.ranged,PcRangedProfile,'actor Shooting facts')
            replace(self.ranged)
            if self.ballistic_skill is not None and self.ballistic_skill!=self.ranged.ballistic_skill:
                raise ValueError('Shooting and Throwing must use the same Ballistic Skill')
        if self.weapon in PC_RANGED_WEAPONS:
            _typed(self.ranged, PcRangedProfile, "PC ranged profile")
            from towr.domain.weapon_capability_models import weapon_ranged_requirements
            requirements=weapon_ranged_requirements((self.weapon,))
            if requirements.requires_aim:
                self.ranged.awareness_profile
            if requirements.firearm and (self.ranged.has_blackpowder_lore is not True
                    or self.ranged.has_blackpowder_kit is not True):
                raise ValueError('a firearm requires actual Blackpowder Lore and Kit')
            if requirements.exacting:
                self.ranged.dexterity_profile
                _typed(self.ranged.reload_hand_policy, PcRangedReloadHandPolicy, 'ranged reload hand policy')
            if requirements.repeater:
                _typed(self.ranged.repeater_bonus_policy, PcRepeaterBonusPolicy, 'Repeater bonus policy')

    @property
    def melee_profile(self) -> TestProfile:
        return TestProfile(self.weapon_skill, self.melee)

    @property
    def throwing_profile(self) -> TestProfile:
        if self.throwing is None:
            raise ValueError('Throwing requires its explicit Skill source')
        return TestProfile(self.ballistic_skill,self.throwing)

    @property
    def brawn_profile(self) -> TestProfile:
        if self.brawn is None:
            raise ValueError('Brawn requires its explicit Skill source')
        return TestProfile(self.strength,self.brawn)

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
    def leadership_profile(self) -> TestProfile:
        if self.fellowship is None or self.leadership is None:
            raise ValueError('Leadership requires explicit Fellowship and Leadership ratings')
        return TestProfile(self.fellowship, self.leadership)

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
    daylight_confirmed: bool | None = field(default=None,kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.zone_id, "PC melee Zone")
        if self.daylight_confirmed is not None:
            _typed(self.daylight_confirmed,bool,'confirmed daylight premise')
            if not self.daylight_confirmed:
                raise ValueError('this optional environment premise requires confirmed daylight')
        for name in (
            "all_opponents_close", "targets_aware", "all_combatants_included",
            "unmounted", "no_external_effects", "no_terrain_modifiers",
            "no_additional_abilities", "no_ambush", "outnumbering_bonus_approved",
            "can_leave_zone",
        ):
            value = getattr(self, name)
            _typed(value, bool, name)
            if name not in ("all_opponents_close", "outnumbering_bonus_approved", "can_leave_zone", "unmounted") and not value:
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
    initial_weapon_hand: PcWeaponHand | PcTwoHandedGrip | None
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
    consumables: tuple[ConsumableItem, ...] = field(default=(), kw_only=True)
    wizard: PcWizardProfile | None = field(default=None, kw_only=True)
    armour_worn: bool | None = field(default=None, kw_only=True)
    talents: tuple[AcquiredTalent,...] = field(default=(),kw_only=True)
    talent_facts: TalentOwnerFacts | None = field(default=None,kw_only=True)
    oath_context: OathBattleContext | None = field(default=None,kw_only=True)
    combat_equipment: tuple[PcWeaponItem,...] | None = field(default=None,kw_only=True)
    mount: CombatMount | None = field(default=None,kw_only=True)
    armour: ArmourLoadout | None = field(default=None,kw_only=True)
    rider_kind: RiderKind | None = field(default=None,kw_only=True)
    agilulf_code_confirmed: bool | None = field(default=None,kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "PC actor")
        if self.mount is not None:
            _typed(self.mount,CombatMount,'trained mount component')
        _typed(self.pc, PcMeleeDefinition, "PC definition")
        replace(self.pc)
        if self.armour is not None:
            from towr.domain.armour_models import (ArmourLoadout,body_resilience_bonus,
                helmet_resilience_bonus,armour_is_worn,active_agilulf)
            _typed(self.armour,ArmourLoadout,'complete armour equipment')
            replace(self.armour)
            if self.pc.armour_bonus != body_resilience_bonus(self.armour)+helmet_resilience_bonus(self.armour):
                raise ValueError('PC armour bonus must match its complete item source')
            if (self.shield is not None) != (self.armour.shield is not None):
                raise ValueError('PC held Shield loadout must match its armour item source')
            if self.armour_worn is not None and self.armour_worn != armour_is_worn(self.armour):
                raise ValueError('PC worn armour fact must match its actual items')
            if self.armour.barding and self.mount is None:
                raise ValueError('Barding requires its actual compatible mount')
            from towr.domain.armour_models import BodyArmour
            if BodyArmour.AGILULF in self.armour.body:
                if self.agilulf_code_confirmed is not True:
                    raise ValueError('Agilulf requires explicit GM confirmation of the chivalric scene')
                if self.pc.weapon in (*PC_RANGED_WEAPONS,*PC_THROWING_WEAPONS):
                    raise ValueError('Agilulf forbids a ranged combat loadout under the chivalric code')
            elif self.agilulf_code_confirmed is not None:
                raise ValueError('Agilulf code confirmation belongs only to worn Agilulf armour')
        elif self.agilulf_code_confirmed is not None:
            raise ValueError('Agilulf code confirmation requires its actual armour source')
        from towr.domain.pc_mount_models import validate_mount_rider
        validate_mount_rider(self.mount,self.rider_kind)
        if self.armour_worn is not None:
            _typed(self.armour_worn,bool,'worn armour fact')
            if self.pc.armour_bonus > 0 and not self.armour_worn:
                raise ValueError('positive body armour cannot deny worn armour')
        if self.wizard is not None:
            if type(self.wizard) is not PcWizardProfile:
                raise TypeError('PC wizard source requires its typed complete profile')
            replace(self.wizard)
            if self.policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
                raise ValueError('PC magic currently requires automatic melee tactics')
        _readmit_fate(self.fate, self.actor_id)
        from towr.domain.talent_actor_models import validate_pc_talent_source
        validate_pc_talent_source(self)
        validate_oath_context(self.talents, self.oath_context)
        from towr.domain.talent_catalog import TalentId
        if any(value.id in (TalentId.DEFENSIVE_STANCE,TalentId.WILD_ATTACK)
                for value in self.talents) and self.policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            raise ValueError('PC combat Talents currently require automatic melee tactics')
        if type(self.consumables) is not tuple or any(type(item) is not ConsumableItem for item in self.consumables):
            raise TypeError('PC consumables require an ordered tuple of typed items')
        for item in self.consumables:
            replace(item)
            if (item.kind is ConsumableKind.ENHANCEMENT and item.characteristic not in
                    ('weapon_skill', 'strength', 'toughness', 'agility')):
                raise ValueError('this simulator supports Enhancement for WS/Strength/Toughness/Agility only')
        if len({item.id for item in self.consumables}) != len(self.consumables):
            raise ValueError('PC consumable instance IDs must be unique')
        if self.consumables and self.policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            raise ValueError('potion use currently requires automatic melee tactics')
        if self.close_shooting_protection_skill is not None:
            _typed(self.close_shooting_protection_skill, Skill, "PC Close Shooting Protection skill")
            if self.close_shooting_protection_skill not in (Skill.MELEE, Skill.ATHLETICS):
                raise ValueError("PC Close Shooting Protection choice requires Melee or Athletics")
        for name, cls in (("policy", PcMeleePolicy), ("fate_policy", PcFatePolicy),
                          ("random_side_policy", PcRandomSidePolicy), ("heavy_wound_policy", PcHeavyWoundPolicy)):
            _typed(getattr(self, name), cls, name)
        if self.pc.weapon in PC_RANGED_WEAPONS:
            if self.policy not in (PcMeleePolicy.ATTACK_OR_RECOVER_SELF,PcMeleePolicy.AUTOMATIC_COMBAT):
                raise ValueError("ranged PC requires ordinary Attack/self Recover policy")
            if any(value is not None for value in (self.help_policy, self.ally_recover_policy)):
                raise ValueError("ranged PC cannot carry Help or ally Recover")
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands, pc_weapon_supports_variable_grip
        variable_grip = pc_weapon_supports_variable_grip(self.pc.weapon)
        grip_type = (type(self.initial_weapon_hand) if variable_grip
            else PcTwoHandedGrip if pc_weapon_requires_two_hands(self.pc.weapon) else PcWeaponHand)
        if grip_type not in (PcWeaponHand, PcTwoHandedGrip):
            raise TypeError('variable weapon grip requires an exact one- or two-handed grip')
        if self.pc.weapon is PcMeleeWeapon.UNARMED:
            if self.initial_weapon_hand is not None:
                raise ValueError('Unarmed has no physical initial weapon hand')
        else:
            _typed(self.initial_weapon_hand,grip_type,"initial weapon grip")
        if self.shield is not None:
            _typed(self.shield, PcShieldLoadout, "PC shield loadout")
            replace(self.shield)
            if self.pc.weapon not in (PcMeleeWeapon.UNARMED,PcMeleeWeapon.KNUCKLEDUSTERS,
                    PcMeleeWeapon.CAVALRY_SPEAR,PcMeleeWeapon.LANCE,PcMeleeWeapon.DAGGER, PcMeleeWeapon.STAFF,
                    PcMeleeWeapon.AXE, PcMeleeWeapon.SWORD, PcMeleeWeapon.WARHAMMER,
                    PcMeleeWeapon.FOOT_SPEAR, PcMeleeWeapon.POLEARM,
                    PcMeleeWeapon.MORNING_STAR, PcMeleeWeapon.PISTOL,
                    PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL, PcMeleeWeapon.SLING,
                    PcMeleeWeapon.ROCK,PcMeleeWeapon.THROWING_SPEAR,PcMeleeWeapon.THROWING_AXE,
                    PcMeleeWeapon.THROWING_KNIVES,PcMeleeWeapon.OIL_FLASK,PcMeleeWeapon.BLASTING_CHARGE,
                    PcMeleeWeapon.MORNING_STAR_OF_FRACASSE,PcMeleeWeapon.SCARAB_KNIFE,
                    PcMeleeWeapon.TRICKSTER_BLADE,PcMeleeWeapon.SWORD_OF_JUSTICE,PcMeleeWeapon.OGRE_PISTOL):
                raise ValueError("shield requires a supported one-handed primary weapon")
            if self.initial_weapon_hand is PcTwoHandedGrip.BOTH or self.shield.initial_hand is self.initial_weapon_hand:
                raise ValueError("shield and weapon require opposite initial hands")
            if self.backup_weapon_policy is not None and self.pc.weapon not in PC_RANGED_WEAPONS:
                raise ValueError("shield cannot carry a backup weapon policy")
        if self.backup_weapon_policy is not None:
            _typed(self.backup_weapon_policy,PcBackupWeaponPolicy,"backup weapon policy")
            replace(self.backup_weapon_policy)
            if grip_type is not PcTwoHandedGrip and self.pc.weapon not in PC_RANGED_WEAPONS:
                raise ValueError("fixed backup policy requires a two-handed or ranged initial primary")
        for value, cls in ((self.near_miss_policy,PcNearMissPolicy),(self.glorious_policy,PcGloriousPolicy)):
            if value is not None:
                _typed(value,cls,"Fate strategy")
                replace(value)
        if self.glorious_policy is not None:
            _canonical_tuple(self.glorious_policy.skills,"Glorious skills")
        if self.aim_second_action_policy is not None:
            _typed(self.aim_second_action_policy, PcAimSecondActionPolicy, "Aim Second Action policy")
            replace(self.aim_second_action_policy)
            from towr.domain.pc_combat_equipment_models import pc_initial_weapon_kinds
            if PcMeleeWeapon.HOCHLAND_LONG_RIFLE not in pc_initial_weapon_kinds(self):
                raise ValueError('Aim Second Action policy requires Hochland')
        configured = (self.near_miss_policy is not None or self.glorious_policy is not None
            or self.aim_second_action_policy is not None
            or (self.fate_policy is PcFatePolicy.CONFIGURED and self.oath_context is not None
                and self.oath_context.unmitigated_success_scope_confirmed
                and has_talent(self.talents, TalentId.HONOUR_BOUND)))
        if configured != (self.fate_policy is PcFatePolicy.CONFIGURED):
            raise ValueError("configured Fate needs explicit criteria; decline requires null policies")
        if self.policy is PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF:
            _typed(self.help_policy,PcHelpPolicy,"Help strategy")
            replace(self.help_policy)
            if self.help_policy.skill is Skill.THROWING and self.pc.throwing is None:
                raise ValueError('Throwing Help requires its explicit BS/Throwing source')
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
        from towr.domain.pc_combat_equipment_models import validate_pc_combat_equipment
        validate_pc_combat_equipment(self)
        if self.pc.tools:
            from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
            weapons = initial_pc_weapon_inventory(self)
            tool_ids = {item.id for item in self.pc.tools}
            other_ids = {item.source_item_id for item in weapons.items} | {item.id for item in self.consumables}
            if tool_ids & other_ids:
                raise ValueError('tools, weapons and consumables require distinct source item IDs')
            validate_tool_equipment_hands(initial_tool_inventory(self.actor_id, self.pc.tools), weapons)
        if self.pc.ranged is not None and self.pc.ranged.repeater_bonus_policy is PcRepeaterBonusPolicy.AUTOMATIC:
            if self.policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
                raise ValueError('automatic Repeater mode requires automatic combat policy')
        if self.pc.weapon in PC_THROWING_WEAPONS and (self.policy is not PcMeleePolicy.AUTOMATIC_COMBAT
                or self.combat_equipment is None):
            raise ValueError('Throwing weapons require automatic decisions and their concrete source items')

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


def validate_pc_single_combat_pairs(pairs, pc_actor_ids, npc_actor_ids):
    """Source admission; orientation is preserved but pair meaning is unordered."""
    if type(pairs) is not tuple or any(type(pair) is not PcSingleCombatPair for pair in pairs):
        raise TypeError('single combat pairs require an exact tuple of typed GM facts')
    pc_ids,npc_ids=set(pc_actor_ids),set(npc_actor_ids)
    used=set()
    for pair in pairs:
        replace(pair)
        if not ((pair.actor_id in pc_ids and pair.target_id in npc_ids)
                or (pair.actor_id in npc_ids and pair.target_id in pc_ids)):
            raise ValueError('single combat pairs require actual opposing actors in this scene')
        if used.intersection((pair.actor_id,pair.target_id)):
            raise ValueError('single combat pairs cannot duplicate or overlap actors')
        used.update((pair.actor_id,pair.target_id))


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
    npc_ranged_policies: tuple[PcNpcRangedPolicy, ...] = field(default=(),kw_only=True)
    npc_close_shooting_protection_policies: tuple[PcNpcCloseShootingProtectionPolicy, ...] | None = field(default=None,kw_only=True)
    short_range_opening: PcShortRangeOpening | None = field(default=None,kw_only=True)
    blunderbuss_nearby: PcBlunderbussNearby | None = field(default=None,kw_only=True)
    battlefield: PcBattlefieldSpec | None = field(default=None,kw_only=True)
    music_acoustics: BattlefieldMusicAcoustics | None = field(default=None,kw_only=True)
    single_combat_pairs: tuple[PcSingleCombatPair,...] = field(default=(),kw_only=True)

    def __post_init__(self) -> None:
        for name in ("id", "day_id"):
            _identifier(getattr(self, name), name)
        _typed(self.facts, PcMeleeFacts, "PC melee facts")
        replace(self.facts)
        if self.music_acoustics is not None:
            _typed(self.music_acoustics, BattlefieldMusicAcoustics, 'music acoustic facts')
            replace(self.music_acoustics)
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
        validate_pc_single_combat_pairs(self.single_combat_pairs,
            tuple(member.actor_id for member in party),tuple(enemy.state.actor_id for enemy in enemies))
        definitions = {}
        for enemy in enemies:
            _readmit_profile_enemy(enemy)
            definition = enemy.definition
            if definition.id in definitions and definitions[definition.id] != definition:
                raise ValueError("conflicting Minion definitions with the same ID")
            definitions[definition.id] = definition
        from towr.domain.pc_combat_equipment_models import pc_initial_weapon_kinds
        has_ranged = any(kind in (*PC_RANGED_WEAPONS,*PC_THROWING_WEAPONS)
            for member in party for kind in pc_initial_weapon_kinds(member))
        if any(member.pc.weapon is PcMeleeWeapon.UNARMED
                or PcMeleeWeapon.KNUCKLEDUSTERS in pc_initial_weapon_kinds(member) for member in party):
            for enemy in enemies:
                if not any(profile.skill in (Skill.ATHLETICS,Skill.ENDURANCE)
                        for profile in enemy.definition.protection):
                    raise ValueError('Brawn opponents require explicit Athletics or Endurance Protection facts')
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
                if enemy.definition.generated_components is not None:
                    continue
                if enemy.state.actor_id in close_shooting_profiles:
                    continue
                skill = enemy.definition.protection[0].skill
                if skill is Skill.STEALTH:
                    from towr.domain.protection_models import HalflingStealthProtectionPermission
                    HalflingStealthProtectionPermission(enemy.state.actor_id,enemy.definition)
                    continue
                if skill is not Skill.ATHLETICS and not (
                        skill is Skill.DEFENCE and enemy.state.holds_shield):
                    raise ValueError("Shooting/Throwing opponents require Athletics, actual shield Defence or canonical Thief Stealth")
        pc_ids = tuple(member.actor_id for member in party)
        enemy_ids = tuple(enemy.state.actor_id for enemy in enemies)
        all_ids = (*pc_ids, *enemy_ids)
        if self.music_acoustics is not None and self.music_acoustics.blocked_zone_pairs:
            if self.battlefield is None:
                raise ValueError('acoustic barriers need actual distinct battlefield Zones')
            from towr.domain.pc_battlefield_models import build_pc_battlefield
            graph = build_pc_battlefield(self.battlefield, pc_ids, enemy_ids, self.facts.zone_id).spatial.graph
            if any(not graph.contains(self.facts.zone_id + ':' + key)
                    for pair in self.music_acoustics.blocked_zone_pairs for key in pair):
                raise ValueError('acoustic barrier references an absent battlefield Zone')
        from towr.domain.pc_scene_feature_models import validate_scene_visibility_actors
        validate_scene_visibility_actors(self.battlefield,all_ids)
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
                if (member.help_policy.target is PcHelpTarget.ATTACK
                        and self.pc_activation_order.index(member.actor_id) >= self.pc_activation_order.index(beneficiary_id)):
                    raise ValueError("Help beneficiary must activate later in this round")
        object.__setattr__(self, "party", party)
        object.__setattr__(self, "enemies", enemies)
        from towr.domain.pc_tactical_models import validate_automatic_combat_scenario
        validate_automatic_combat_scenario(self)
        validate_pc_npc_help_policies(self)
        validate_pc_npc_ranged_policies(self)
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
        has_blunderbuss = any(PcMeleeWeapon.BLUNDERBUSS in pc_initial_weapon_kinds(member) for member in party)
        if self.battlefield is not None:
            if self.blunderbuss_nearby is not None:
                raise ValueError('battlefield Blunderbuss uses actual Close relations instead of a legacy cluster')
        elif has_blunderbuss:
            _typed(self.blunderbuss_nearby, PcBlunderbussNearby, 'Blunderbuss nearby source')
            replace(self.blunderbuss_nearby)
            if set(self.blunderbuss_nearby.target_priority) != set(enemy_ids):
                raise ValueError('Blunderbuss nearby priority must include every NPC exactly once')
        elif self.blunderbuss_nearby is not None:
            raise ValueError('Blunderbuss nearby source requires a Blunderbuss PC')
        _validate_short_range_opening(self)
        from towr.domain.pc_falling_models import validate_pc_falling_scene
        validate_pc_falling_scene(self)
        from towr.domain.pc_weapon_area_models import validate_weapon_area_scene
        validate_weapon_area_scene(self)
        from towr.domain.pc_armour_models import validate_agilulf_defeat_policies
        validate_agilulf_defeat_policies(self)

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
    if scenario.facts.unmounted != (not initial_pc_mounts(scenario)):
        raise ValueError('initial unmounted fact must match the complete actual mount source')
    if scenario.battlefield is not None:
        _typed(scenario.battlefield, PcBattlefieldSpec, 'battlefield source')
        replace(scenario.battlefield)
        if scenario.short_range_opening is not None:
            raise ValueError('battlefield and legacy Short opening are different explicit scene sources')
        if scenario.facts.all_opponents_close != (scenario.battlefield.initial_range is RangedWeaponRange.CLOSE):
            raise ValueError('initial Close facts must match the actual battlefield source')
        if not scenario.facts.can_leave_zone:
            raise ValueError('the open battlefield must retain legal movement between its Zones')
        if any(member.policy is not PcMeleePolicy.AUTOMATIC_COMBAT for member in scenario.party):
            raise ValueError('the battlefield requires automatic participant decisions')
        if (any(enemy.definition.id.startswith('pc-book-npc:') for enemy in scenario.enemies)
                or scenario.npc_broken_exit_policy is not None or scenario.npc_help_policies
                or scenario.npc_extra_attack_actor_ids or scenario.npc_grudge_policies
                or scenario.npc_blood_rage_actor_ids or scenario.npc_flagellant_policies
                or scenario.npc_warped_form_policies or scenario.npc_net_policies):
            raise ValueError('the open battlefield currently requires ordinary/generated opponents without canonical tactical policies')
        return
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
            scenario.npc_net_policies, scenario.npc_ranged_policies)):
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
    if definition.generated_components is not None:
        from towr.domain.generated_npc_models import GeneratedNpc,validate_generated_definition
        _typed(definition.generated_components,GeneratedNpc,'complete generated source')
        validate_generated_definition(definition)
        expected=definition.generated_components.participant(state.actor_id)
        expected=replace(expected,definition=replace(expected.definition,id=definition.id),
            state=replace(expected.state,definition_id=definition.id))
        from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
        validate_pc_book_npc_definition(definition)
        from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
        if enemy!=expected:
            raise ValueError('generated NPC must retain its complete fresh item/profile source')
        validate_pc_melee_source_types(enemy,expected)
        return
    # The legacy authored-profile owner has no item-sourced Talent execution.
    # Its descriptive source may contain acquisitions; admission must reject
    # them rather than silently treating them as generated components.
    from towr.domain.talent_actor_models import validate_npc_definition_talent_scope
    validate_npc_definition_talent_scope(definition,frozenset())
    great_stag = definition.id == 'pc-book-npc:great_stag'
    net_goblin = definition.id == NET_DEFINITION_ID
    generated = definition.generated_components is not None
    if definition.resilience.mundane_armour_ward or state.current_resilience.mundane_armour_ward:
        from towr.domain.armour_models import BodyArmour
        if not generated or definition.generated_components.armour.benefit is not BodyArmour.METEORIC_IRON:
            raise ValueError('Meteoric protection requires its complete generated armour item source')
    generated_net = generated and definition.generated_components.weapon.value == 'weighted_net'
    npc_ranged = (definition.id in PC_NPC_RANGED_DEFINITION_IDS
        or (generated and definition.generated_components.ranged is not None))
    expected_ignores_armour=npc_ranged
    if generated and npc_ranged:
        from towr.domain.ranged_weapon_profiles import RangedWeaponId,ranged_weapon_combat_profile
        expected_ignores_armour=ranged_weapon_combat_profile(
            RangedWeaponId(definition.generated_components.weapon.value)).ignores_armour
    if (len(attacks) != (2 if great_stag or net_goblin else 1)
            or len(protection) != (2 if generated else 1)):
        raise ValueError("NPC requires one primary attack and one Protection; complete generated components allow two Protections, canonical Stag/Net allow a second attack")
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
    if generated:
        _typed(protection[1],NpcProtectionProfile,'generated alternate Protection')
        _readmit_inline(protection[1].test_profile,expected_pool_cap=None)
        replace(protection[1])
    if generated_net:
        if attack.damage is not None:
            raise ValueError('Weighted Net cannot invent a Damage profile')
        _typed(attack.condition_impact,ConditionImpactSpec,'Weighted Net condition impact')
        replace(attack.condition_impact)
    else:
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
    if (attack.skill is not (Skill.THROWING if generated_net else Skill.SHOOTING if npc_ranged else Skill.MELEE)
            or (not (generated and (npc_ranged or generated_net)) and (attack.range_min is not RangedWeaponRange.CLOSE
                or attack.range_max not in ((RangedWeaponRange.SHORT,RangedWeaponRange.MEDIUM)
                    if npc_ranged else (RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT))))
            or (not generated_net and attack.damage.success_multiplier != 1) or attack.ignores_armour is not expected_ignores_armour
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
    from towr.domain.armour_models import armour_burden_sources
    expected_initial_conditions=(frozenset((Condition.BURDENED,)) if generated
        and armour_burden_sources(definition.generated_components.armour,definition.generated_components.strength)
        else frozenset())
    if (injury.wounds or injury.defeated or injury.defeat_cause is not None
            or injury.conditions.conditions != expected_initial_conditions
            or state.wields_weapon is not (attack.hands is not None)
            or state.holds_shield and attack.hands is not RangedWeaponHands.ONE_HANDED
            or state.current_resilience != definition.resilience
            or state.available_attack_ids != tuple(profile.id for profile in attacks)):
        raise ValueError("PC melee requires fresh healthy NPCs and consistent armed/natural attacks and shield hands")
    if generated and state.holds_shield is not definition.generated_components.shield:
        raise ValueError('NPC Shield state must match its generated equipment source')
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
