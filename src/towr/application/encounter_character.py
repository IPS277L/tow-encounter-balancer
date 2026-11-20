"""Character facts compiled to the existing combat executor, without UI policies.

The first character-input slice starts a fresh session and a healthy battle.
Choices below are simulator tactics, not additional tabletop rules.
"""
from dataclasses import dataclass, field, replace
from towr.domain.oath_context_models import OathBattleContext, validate_oath_context

from towr.domain.fate_models import FateSessionState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import (
    PcMeleeDefinition, PcMeleeParticipant, PcMeleeWeapon, PC_RANGED_WEAPONS,
    PcMeleePolicy, PcFatePolicy, PcRandomSidePolicy, PcHeavyWoundPolicy,
    PcWeaponHand, PcTwoHandedGrip, PcShieldLoadout, PcShieldHandConflictPolicy,
    PcShieldRecoveryPolicy, PcGloriousPolicy, PcNearMissPolicy, PcBackupWeaponPolicy,
    PcRangedProfile,
)
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_mount_models import CombatMount,RiderKind
from towr.domain.armour_models import ArmourLoadout,body_resilience_bonus,helmet_resilience_bonus
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands, pc_weapon_supports_variable_grip
from towr.domain.test_models import Skill
from towr.domain.potion_models import ConsumableItem
from towr.domain.pc_magic_source_models import PcWizardProfile
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent, TalentOwnerFacts, has_talent
from towr.domain.tool_inventory_models import ToolItemSource


@dataclass(frozen=True, slots=True)
class EncounterCharacter:
    """Input facts, distinct from per-trial state and controller configuration."""
    actor_id: str
    weapon_skill: int
    strength: int
    toughness: int
    agility: int
    melee: int
    defence: int
    athletics: int
    endurance: int
    weapon: PcMeleeWeapon
    armour: ArmourLoadout
    shield: bool
    weapon_hand: PcWeaponHand | None
    talents: tuple[AcquiredTalent, ...]
    fate: int
    backup_weapon_policy: PcBackupWeaponPolicy | None = field(default=None, kw_only=True)
    consumables: tuple[ConsumableItem, ...] = field(default=(), kw_only=True)
    wizard: PcWizardProfile | None = field(default=None, kw_only=True)
    armour_worn: bool | None = field(default=None, kw_only=True)
    talent_facts: TalentOwnerFacts | None = field(default=None,kw_only=True)
    ranged: PcRangedProfile | None = field(default=None,kw_only=True)
    combat_equipment: tuple[PcWeaponItem,...] | None = field(default=None,kw_only=True)
    mount: CombatMount | None = field(default=None,kw_only=True)
    rider_kind: RiderKind | None = field(default=None,kw_only=True)
    agilulf_code_confirmed: bool | None = field(default=None,kw_only=True)
    throwing: int | None = field(default=None,kw_only=True)
    brawn: int | None = field(default=None,kw_only=True)
    ballistic_skill: int | None = field(default=None,kw_only=True)
    fellowship: int | None = field(default=None,kw_only=True)
    leadership: int | None = field(default=None,kw_only=True)
    tools: tuple[ToolItemSource, ...] = field(default=(),kw_only=True)
    shield_hand: PcWeaponHand | None = field(default=None,kw_only=True)
    oath_context: OathBattleContext | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise ValueError('character actor ID is required')
        if type(self.armour) is not ArmourLoadout or type(self.shield) is not bool:
            raise TypeError('character requires typed armour and shield')
        replace(self.armour)
        if type(self.weapon) is not PcMeleeWeapon:
            raise ValueError('dynamic character input requires a typed supported weapon')
        kinds=(self.weapon,) if self.combat_equipment is None else tuple(item.weapon for item in self.combat_equipment)
        from towr.domain.weapon_capability_models import weapon_ranged_requirements
        if (weapon_ranged_requirements(kinds) is not None) != (self.ranged is not None):
            raise ValueError('Shooting facts must match the whole concrete weapon inventory')
        if self.ranged is not None:
            if type(self.ranged) is not PcRangedProfile:
                raise TypeError('ranged preparation requires its full typed profile')
            replace(self.ranged)
        if self.weapon is PcMeleeWeapon.UNARMED:
            if self.weapon_hand is not None:
                raise ValueError('Unarmed has no physical weapon hand')
        elif type(self.weapon_hand) is not PcWeaponHand:
            raise TypeError('weapon hand must be left or right')
        if self.shield_hand is not None and type(self.shield_hand) is not PcWeaponHand:
            raise TypeError('actual shield hand must be left or right')
        if self.shield_hand is not None and not self.shield:
            raise ValueError('a shield hand requires an actual held Shield')
        if (type(self.talents) is not tuple or any(type(t) is not AcquiredTalent for t in self.talents)):
            raise ValueError('talents require their complete shared acquisition source')
        if type(self.fate) is not int or self.fate < 0:
            raise ValueError('Fate rating must be a nonnegative integer')
        if has_talent(self.talents,TalentId.WIZARD) != (self.wizard is not None):
            raise ValueError('Wizard talent requires explicit matching magic facts')
        validate_oath_context(self.talents, self.oath_context)
        # Reuse the executor admission, including two-hand/shield restrictions.
        self._participant('admission', NpcDefeatDisposition.KILLED)

    def participant(self, session_id: str, disposition: NpcDefeatDisposition) -> PcMeleeParticipant:
        # Cached native facts must pass the same admission as parsed input.
        replace(self)
        return self._participant(session_id, disposition)

    def _participant(self, session_id: str, disposition: NpcDefeatDisposition) -> PcMeleeParticipant:
        pc = PcMeleeDefinition('character:' + self.actor_id, self.weapon_skill,
            self.strength, self.toughness, self.agility, self.melee, self.defence,
            self.athletics, self.endurance, self.weapon,
            body_resilience_bonus(self.armour)+helmet_resilience_bonus(self.armour),
            ranged=self.ranged,throwing=self.throwing,brawn=self.brawn,ballistic_skill=self.ballistic_skill,
            fellowship=self.fellowship,leadership=self.leadership,tools=self.tools)
        from towr.domain.pc_combat_equipment_models import PcItemLocation
        held=(None if self.combat_equipment is None else
            next((item for item in self.combat_equipment if item.location is PcItemLocation.HELD),None))
        both = (pc_weapon_requires_two_hands(self.weapon)
            or pc_weapon_supports_variable_grip(self.weapon) and held is not None
                and held.hand is PcTwoHandedGrip.BOTH)
        grip = PcTwoHandedGrip.BOTH if both else self.weapon_hand
        shield = None
        if self.shield:
            opposite = (self.shield_hand if self.shield_hand is not None else PcWeaponHand.RIGHT
                if self.weapon_hand in (None,PcWeaponHand.LEFT) else PcWeaponHand.LEFT)
            shield = PcShieldLoadout(opposite, PcShieldHandConflictPolicy.WEAPON_FIRST,
                PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
        return PcMeleeParticipant(self.actor_id, pc,
            FateSessionState(session_id, self.actor_id, self.fate, self.fate,
                has_lucky=has_talent(self.talents,TalentId.LUCKY)),
            PcMeleePolicy.AUTOMATIC_COMBAT, PcFatePolicy.CONFIGURED,
            PcRandomSidePolicy.D10_LOW_LEFT_HIGH_RIGHT, PcHeavyWoundPolicy.CONTINUE_FIGHTING,
            grip, ('generated-npc:1',),
            (MinionDefeatDecision(self.actor_id, 'generated-npc:1', disposition, True),),
            # Decide at the actual Wound/Test window using the current resource.
            PcNearMissPolicy(11, 0),
            PcGloriousPolicy((Skill.MELEE, Skill.DEFENCE, Skill.ATHLETICS, Skill.ENDURANCE,
                *((Skill.LEADERSHIP,) if has_talent(self.talents,TalentId.BATTLEFIELD_MUSICIAN)
                    and self.leadership is not None else ()),
                *((Skill.SHOOTING,Skill.DEXTERITY) if self.ranged is not None else ()),
                *((Skill.THROWING,) if self.throwing is not None else ()),
                *((Skill.BRAWN,) if self.brawn is not None else ()),
                *((Skill.WILLPOWER,) if self.wizard is not None else ())), 0, 0),
            None, None, self.backup_weapon_policy, shield=shield, consumables=self.consumables,
            wizard=self.wizard,armour_worn=self.armour_worn,talents=self.talents,talent_facts=self.talent_facts,
            combat_equipment=self.combat_equipment,mount=self.mount,armour=self.armour,
            rider_kind=self.rider_kind,agilulf_code_confirmed=self.agilulf_code_confirmed,
            oath_context=self.oath_context)
