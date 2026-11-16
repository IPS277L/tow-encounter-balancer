"""Character facts compiled to the existing combat executor, without UI policies.

The first character-input slice starts a fresh session and a healthy battle.
Choices below are simulator tactics, not additional tabletop rules.
"""
from dataclasses import dataclass, field, replace
from enum import Enum

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
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
from towr.domain.test_models import Skill
from towr.domain.potion_models import ConsumableItem
from towr.domain.pc_magic_source_models import PcWizardProfile
from towr.domain.pc_combat_talent_models import PcCombatTalent


class EncounterArmour(str, Enum):
    NONE = 'none'
    LIGHT = 'light'


class EncounterTalent(str, Enum):
    LUCKY = 'lucky'
    WIZARD = 'wizard'
    DEFENSIVE_STANCE='defensive_stance'
    WILD_ATTACK='wild_attack'


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
    armour: EncounterArmour
    shield: bool
    weapon_hand: PcWeaponHand
    talents: tuple[EncounterTalent, ...]
    fate: int
    backup_weapon_policy: PcBackupWeaponPolicy | None = field(default=None, kw_only=True)
    consumables: tuple[ConsumableItem, ...] = field(default=(), kw_only=True)
    wizard: PcWizardProfile | None = field(default=None, kw_only=True)
    armour_worn: bool | None = field(default=None, kw_only=True)
    combat_talents: tuple[PcCombatTalent,...] = field(default=(),kw_only=True)
    ranged: PcRangedProfile | None = field(default=None,kw_only=True)
    combat_equipment: tuple[PcWeaponItem,...] | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise ValueError('character actor ID is required')
        if type(self.armour) is not EncounterArmour or type(self.shield) is not bool:
            raise TypeError('character requires typed armour and shield')
        if type(self.weapon) is not PcMeleeWeapon or (self.weapon in PC_RANGED_WEAPONS
                and self.weapon not in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL,
                    PcMeleeWeapon.REPEATER_HANDBOW)):
            raise ValueError('dynamic character input requires melee or supported Close ranged weapon')
        if (self.weapon in PC_RANGED_WEAPONS) != (self.ranged is not None):
            raise ValueError('ranged preparation must match the initial ranged weapon')
        if self.ranged is not None:
            if type(self.ranged) is not PcRangedProfile:
                raise TypeError('ranged preparation requires its full typed profile')
            replace(self.ranged)
        if type(self.weapon_hand) is not PcWeaponHand:
            raise TypeError('weapon hand must be left or right')
        if (type(self.talents) is not tuple or any(type(t) is not EncounterTalent for t in self.talents)
                or len(set(self.talents)) != len(self.talents)):
            raise ValueError('talents must be a unique tuple of supported talents')
        if type(self.fate) is not int or self.fate < 0:
            raise ValueError('Fate rating must be a nonnegative integer')
        if (EncounterTalent.WIZARD in self.talents) != (self.wizard is not None):
            raise ValueError('Wizard talent requires explicit matching magic facts')
        if type(self.combat_talents) is not tuple or any(type(t) is not PcCombatTalent for t in self.combat_talents):
            raise TypeError('combat Talent facts must be an ordered typed tuple')
        for fact in self.combat_talents:
            replace(fact)
        selected={t.value for t in self.talents if t in (EncounterTalent.DEFENSIVE_STANCE,EncounterTalent.WILD_ATTACK)}
        if selected != {t.talent.value for t in self.combat_talents}:
            raise ValueError('combat Talent tags must match their complete acquisition facts')
        # Reuse the executor admission, including two-hand/shield restrictions.
        self._participant('admission', NpcDefeatDisposition.KILLED)

    def participant(self, session_id: str, disposition: NpcDefeatDisposition) -> PcMeleeParticipant:
        # Cached native facts must pass the same admission as parsed input.
        replace(self)
        return self._participant(session_id, disposition)

    def _participant(self, session_id: str, disposition: NpcDefeatDisposition) -> PcMeleeParticipant:
        pc = PcMeleeDefinition('character:' + self.actor_id, self.weapon_skill,
            self.strength, self.toughness, self.agility, self.melee, self.defence,
            self.athletics, self.endurance, self.weapon, int(self.armour is EncounterArmour.LIGHT),
            ranged=self.ranged)
        grip = PcTwoHandedGrip.BOTH if pc_weapon_requires_two_hands(self.weapon) else self.weapon_hand
        shield = None
        if self.shield:
            opposite = PcWeaponHand.RIGHT if self.weapon_hand is PcWeaponHand.LEFT else PcWeaponHand.LEFT
            shield = PcShieldLoadout(opposite, PcShieldHandConflictPolicy.WEAPON_FIRST,
                PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
        return PcMeleeParticipant(self.actor_id, pc,
            FateSessionState(session_id, self.actor_id, self.fate, self.fate,
                has_lucky=EncounterTalent.LUCKY in self.talents),
            PcMeleePolicy.AUTOMATIC_COMBAT, PcFatePolicy.CONFIGURED,
            PcRandomSidePolicy.D10_LOW_LEFT_HIGH_RIGHT, PcHeavyWoundPolicy.CONTINUE_FIGHTING,
            grip, ('generated-npc:1',),
            (MinionDefeatDecision(self.actor_id, 'generated-npc:1', disposition, True),),
            # Decide at the actual Wound/Test window using the current resource.
            PcNearMissPolicy(11, 0),
            PcGloriousPolicy((Skill.MELEE, Skill.DEFENCE, Skill.ATHLETICS, Skill.ENDURANCE,
                *((Skill.SHOOTING,Skill.DEXTERITY) if self.ranged is not None else ()),
                *((Skill.WILLPOWER,) if self.wizard is not None else ())), 0, 0),
            None, None, self.backup_weapon_policy, shield=shield, consumables=self.consumables,
            wizard=self.wizard,armour_worn=self.armour_worn,combat_talents=self.combat_talents,
            combat_equipment=self.combat_equipment)
