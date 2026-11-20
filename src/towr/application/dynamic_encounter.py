"""Budgeted adaptive generation of new NPC configurations, then Monte Carlo.

The simulator is injected. Neither NPC identity nor a supplied enemy reserve
defines the search space. Existing JSON families are unchanged.
"""
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from hashlib import sha256
from math import exp, isfinite, log, sqrt
from random import Random

from towr.application.generated_oath_sources import GeneratedOathSource, OATH_TALENT_IDS, merge_oath_facts, matches_oath_source
from towr.application.ranged_simulation_models import SimulationExecutionMode,SimulationExecutionOptions
from towr.domain.generated_npc_models import (GeneratedNpc,GeneratedWeapon,GeneratedAbility,
    TalentId,generated_talent_acquisition,generated_talent_requirements_met,GeneratedRangedFacts,GENERATED_RANGED_WEAPONS,
    generated_weapon_allows_shield,generated_weapon_grips,GENERATED_VARIABLE_GRIP_WEAPONS,
    GENERATED_TWO_HANDED_RANGED_WEAPONS,GENERATED_CLOSE_WEAPONS,GENERATED_PHYSICAL_WEAPONS,GENERATED_ORDINARY_WEAPONS,
    GENERATED_NON_CLOSE_RANGED_WEAPONS)
from towr.domain.armour_models import ArmourLoadout,BodyArmour,HelmetKind,ShieldKind
from towr.domain.talent_models import TalentOwnerFacts, TalentLoreFact
from towr.domain.talent_catalog import TalentEquipmentRequirement
from towr.domain.tool_inventory_models import ToolItemSource, ToolKind
from towr.domain.weapon_catalog import WeaponKind,WeaponGroup,weapon_profile,weapon_printed_damage
from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation,WeaponGrip,weapon_reload_target
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponId,ranged_weapon_combat_profile
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.battlefield_music_models import BattlefieldMusicAcoustics
from towr.domain.pc_single_combat_models import PcSingleCombatPair
from towr.domain.talent_actor_models import GENERATED_TALENT_POOL
from towr.domain.pc_mount_models import CombatMount,RiderKind
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeFacts, PcMeleeParticipant, PcMeleeScenario, PC_RANGED_WEAPONS
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


@dataclass(frozen=True, slots=True)
class NumericCompositionSample:
    """Generated numeric sources and their actual freedom/change counts."""
    composition: tuple[GeneratedNpc, ...]
    bias: float
    variable_fields: int
    changed_members: int


def _sample_numeric_value(values: tuple[int, ...], rng: Random, bias: float) -> int:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    if bias == 0:
        return rng.choice(ordered)
    weights = tuple(exp(log(9)*bias*i/(len(ordered)-1)) for i in range(len(ordered)))
    ticket = rng.random()*sum(weights)
    for value, weight in zip(ordered, weights):
        if ticket < weight:
            return value
        ticket -= weight
    return ordered[-1]


@dataclass(frozen=True, slots=True)
class NpcSearchSpace:
    """Finite allowed values; no Cartesian grid is materialized."""
    weapon_skill: tuple[int, ...] = (2, 3, 4)
    strength: tuple[int, ...] = (2, 3, 4)
    toughness: tuple[int, ...] = (2, 3, 4)
    agility: tuple[int, ...] = (2, 3, 4)
    melee: tuple[int, ...] = (3, 4, 5)
    athletics: tuple[int, ...] = (3, 4, 5)
    defence: tuple[int, ...] = (3, 4, 5)
    weapon: tuple[GeneratedWeapon, ...] = GENERATED_CLOSE_WEAPONS
    weapon_count: tuple[int, ...] = (1,2,3)
    initial_loaded: tuple[bool, ...] = (True,)
    scarab_initial_charges: tuple[int, ...] = (0,)
    ogre_fit_confirmed: bool | None = None
    armour: tuple[BodyArmour | None, ...] = (None,BodyArmour.LIGHT,BodyArmour.HEAVY,BodyArmour.FULL_PLATE)
    secondary_armour: tuple[BodyArmour | None, ...] = (None,)
    helmet: tuple[HelmetKind | None, ...] = (None,)
    shield: tuple[ShieldKind | None, ...] = (None,ShieldKind.SHIELD)
    barding: tuple[bool, ...] = (False,)
    abilities: tuple[tuple[GeneratedAbility, ...], ...] = ((),)
    allowed_talents: tuple[TalentId,...] = GENERATED_TALENT_POOL
    allowed_oath_sources: tuple[GeneratedOathSource,...] = ()
    ballistic_skill: tuple[int, ...] = (2, 3, 4)
    shooting: tuple[int, ...] = (3, 4, 5)
    initiative: tuple[int, ...] = (2, 3, 4)
    fellowship: tuple[int, ...] = (2, 3, 4)
    leadership: tuple[int, ...] = (3, 4, 5)
    musician_instrument_hands: tuple[int, ...] = (1, 2)
    dexterity: tuple[int, ...] = (3, 4, 5)
    awareness: tuple[int, ...] = (3, 4, 5)
    weapon_grip: tuple[RangedWeaponHands, ...] = (
        RangedWeaponHands.ONE_HANDED, RangedWeaponHands.TWO_HANDED)
    mount: tuple[CombatMount | None, ...] = (None,)
    throwing: tuple[int, ...] = (3,4,5)
    brawn: tuple[int, ...] = (3,4,5)
    endurance: tuple[int, ...] = (3,4,5)
    rider_kind: tuple[RiderKind, ...] = tuple(RiderKind)
    agilulf_code_confirmed: bool | None = None

    def __post_init__(self):
        if (type(self.allowed_oath_sources) is not tuple
                or any(type(source) is not GeneratedOathSource for source in self.allowed_oath_sources)
                or len(set(self.allowed_oath_sources)) != len(self.allowed_oath_sources)):
            raise ValueError('allowed_oath_sources requires distinct exact declared acquisition/GM bundles')
        for source in self.allowed_oath_sources:
            replace(source)
            for name in ('weapon_skill','strength','toughness','agility','ballistic_skill','initiative','fellowship'):
                declared=getattr(source.talent_facts,name)
                if declared is not None and declared not in getattr(self,name):
                    raise ValueError('allowed Oath source characteristic is outside the numeric search space: '+name)
        if (type(self.musician_instrument_hands) is not tuple or not self.musician_instrument_hands
                or any(type(value) is not int or value not in (1,2) for value in self.musician_instrument_hands)
                or len(set(self.musician_instrument_hands)) != len(self.musician_instrument_hands)):
            raise ValueError('musician_instrument_hands requires distinct exact one/two-hand GM choices')
        for name in ('weapon','weapon_count','initial_loaded','scarab_initial_charges'):
            choices=getattr(self,name)
            if type(choices) is not tuple or not choices or len(set(choices)) != len(choices):
                raise ValueError(name+' requires nonempty distinct tuple choices')
        if any(type(value) is not GeneratedWeapon or value is GeneratedWeapon.UNARMED for value in self.weapon):
            raise ValueError('weapon choices must be supported typed weapons')
        if any(type(value) is not int or value < 0 for value in self.weapon_count):
            raise ValueError('weapon_count choices must be exact nonnegative integers')
        if any(type(value) is not int or value < 0 for value in self.scarab_initial_charges):
            raise ValueError('Scarab charges must be exact nonnegative integers')
        if self.ogre_fit_confirmed is not None and type(self.ogre_fit_confirmed) is not bool:
            raise TypeError('Ogre Pistol fit confirmation must be an exact bool or None')
        if GeneratedWeapon.OGRE_PISTOL in self.weapon:
            if self.ogre_fit_confirmed is not True:
                raise ValueError('Ogre Pistol pool requires explicit GM confirmation of fit')
        elif self.ogre_fit_confirmed is not None:
            raise ValueError('Ogre fit confirmation requires an actual Ogre Pistol pool')
        if any(type(value) is not bool for value in self.initial_loaded):
            raise ValueError('initial_loaded choices must be exact booleans')
        if (type(self.rider_kind) is not tuple or not self.rider_kind
                or any(type(kind) is not RiderKind for kind in self.rider_kind)
                or len(set(self.rider_kind)) != len(self.rider_kind)):
            raise ValueError('rider_kind requires nonempty distinct typed ancestry choices')
        if self.agilulf_code_confirmed is not None and type(self.agilulf_code_confirmed) is not bool:
            raise TypeError('Agilulf scene confirmation must be an exact bool or None')
        if (type(self.weapon_grip) is not tuple or not self.weapon_grip
                or any(type(grip) is not RangedWeaponHands for grip in self.weapon_grip)
                or len(set(self.weapon_grip)) != len(self.weapon_grip)):
            raise ValueError('weapon_grip requires nonempty distinct typed hand choices')
        if (type(self.allowed_talents) is not tuple
                or any(type(t) is not TalentId for t in self.allowed_talents)
                or len(set(self.allowed_talents)) != len(self.allowed_talents)):
            raise ValueError('allowed_talents requires unique supported Talents; empty disables generation')
        if set(self.allowed_talents) & OATH_TALENT_IDS:
            raise ValueError('Honour Bound/Lady require allowed_oath_sources, not a bare allowed_talents identity')
        from towr.domain.talent_actor_models import NPC_EXECUTABLE_TALENTS
        if not set(self.allowed_talents) <= NPC_EXECUTABLE_TALENTS:
            raise ValueError('allowed_talents includes a Talent without its connected NPC execution owner')
        if any(not {talent.id for talent in source.talents} <= NPC_EXECUTABLE_TALENTS
                for source in self.allowed_oath_sources):
            raise ValueError('allowed Oath source includes a Talent without its connected NPC execution owner')
        for name in (*self._ordinary_names(), *self._ranged_names(), 'awareness','throwing','fellowship','leadership'):
            choices = getattr(self,name)
            if type(choices) is not tuple or not choices or len(set(choices)) != len(choices):
                raise ValueError(f'{name} requires nonempty distinct tuple choices')
            for value in choices:
                if name in ('weapon_skill','strength','toughness','agility','ballistic_skill','initiative','fellowship'):
                    if type(value) is not int or value < 1:
                        raise ValueError(f'{name} choices must be positive integers')
                elif name in ('melee','athletics','defence','shooting','dexterity','awareness','throwing','brawn','endurance','leadership'):
                    if type(value) is not int or not 2 <= value <= 6:
                        raise ValueError(f'{name} choices must be integers in 2..6')
                elif name == 'weapon' and type(value) is not GeneratedWeapon:
                    raise ValueError('weapon choices must be supported typed weapons')
                elif name in ('armour','secondary_armour') and value is not None and type(value) is not BodyArmour:
                    raise ValueError('body armour choices require typed items or None')
                elif name == 'helmet' and value is not None and type(value) is not HelmetKind:
                    raise ValueError('helmet choices require typed items or None')
                elif name == 'shield' and value is not None and type(value) is not ShieldKind:
                    raise ValueError('shield choices require typed items or None')
                elif name == 'barding' and type(value) is not bool:
                    raise ValueError('Barding choices must be exact booleans')
                elif name == 'mount' and value is not None and type(value) is not CombatMount:
                    raise ValueError('mount choices require supported typed components or None')
                elif name == 'abilities':
                    if (type(value) is not tuple or any(type(a) is not GeneratedAbility for a in value)
                            or len(set(value)) != len(value)):
                        raise ValueError('ability groups must be unique supported typed tuples')
        equipment_branches = tuple((weapon,grip) for weapon in self.weapon
            for grip in self._weapon_grips(weapon))
        if (any(not generated_weapon_allows_shield(weapon,grip) for weapon,grip in equipment_branches)
                and None not in self.shield and max(self.weapon_count) == 1):
            raise ValueError('two-handed pool items need a no-Shield or carried-item branch')
        if any(shield is not None for shield in self.shield) and not any(generated_weapon_allows_shield(weapon,grip)
                for weapon,grip in equipment_branches) and max(self.weapon_count)>0:
            raise ValueError('Shield choice has no admissible one-handed weapon')
        if all(weapon_printed_damage(WeaponKind(weapon.value),strength=1) is None for weapon in self.weapon) and () not in self.abilities:
            raise ValueError('non-Damage proposals need an admitted empty Damage-secondary group')
        if 0 in self.weapon_count and () not in self.abilities:
            raise ValueError('Unarmed proposal needs an admitted empty Damage-secondary group')
        if all(weapon_printed_damage(WeaponKind(weapon.value),strength=1) is None for weapon in self.weapon) and any(self.abilities):
            raise ValueError('Damage-secondary choices have no admissible numeric weapon')
        if any(not self._body_choices(weapon) for weapon in self.weapon):
            raise ValueError('each weapon choice requires an admissible body-armour combination')
        if any(not any(self._secondary_choices(body,weapon) for weapon in self.weapon)
                for body in self.armour):
            raise ValueError('each body armour choice requires an admissible secondary layer')
        if any(not any(layer in self._secondary_choices(body,weapon)
                    for body in self.armour for weapon in self.weapon)
                for layer in self.secondary_armour):
            raise ValueError('secondary armour choice has no admissible body armour')
        if (BodyArmour.AGILULF in (*self.armour,*self.secondary_armour)
                ) != (self.agilulf_code_confirmed is True):
            raise ValueError('worn Agilulf choice requires its explicit confirmed chivalric scene')
        if self.agilulf_code_confirmed is False:
            raise ValueError('an unconfirmed chivalric scene cannot enable an Agilulf proposal')
        if None in self.mount and False not in self.barding:
            raise ValueError('unmounted choices require an admissible no-Barding loadout')
        if True in self.barding and not any(mount is not None for mount in self.mount):
            raise ValueError('Barding choice has no admissible mounted participant')
        if any(not self._rider_choices(mount) for mount in self.mount):
            raise ValueError('mount choice has no admissible explicit rider ancestry')

    @staticmethod
    def _ranged_names(weapons=None):
        if weapons is None:
            return ('ballistic_skill','shooting','initiative','dexterity')
        requirements=weapon_ranged_requirements(tuple(item.kind for item in weapons))
        if requirements is None:
            return ()
        two_handed=any(GeneratedWeapon(item.kind.value) in GENERATED_TWO_HANDED_RANGED_WEAPONS
            for item in weapons)
        return (('ballistic_skill','shooting')
            + (('initiative',) if requirements.exacting or two_handed else ())
            + (('dexterity',) if requirements.exacting else ())
            + (('awareness',) if two_handed else ()))

    @staticmethod
    def _ordinary_names():
        return ('weapon_skill','strength','toughness','agility','melee','athletics','defence',
            'armour','secondary_armour','helmet','shield','barding','abilities','mount','brawn','endurance')

    def _secondary_choices(self, body, weapon=None):
        choices=[]
        for layer in self.secondary_armour:
            if max(self.weapon_count)>0 and not any(self._initial_grips(kind,shield,
                    chivalric=BodyArmour.AGILULF in (body,layer))
                    for kind in self.weapon for shield in self.shield):
                continue
            # A one-item proposal must be able to select this exact pool member.
            if (max(self.weapon_count)==1 and weapon is not None
                    and BodyArmour.AGILULF in (body,layer)
                    and weapon_profile(WeaponKind(weapon.value)).group in (WeaponGroup.SHOOTING,WeaponGroup.THROWING)):
                continue
            try:
                ArmourLoadout(tuple(item for item in (body,layer) if item is not None),body)
            except (ValueError,TypeError):
                continue
            choices.append(layer)
        return tuple(choices)

    def _body_choices(self, weapon=None):
        return tuple(body for body in self.armour if self._secondary_choices(body,weapon))

    def _rider_choices(self, mount):
        if mount is CombatMount.DEMIGRYPH:
            return tuple(kind for kind in self.rider_kind if kind is RiderKind.HUMAN)
        if mount is CombatMount.PEGASUS:
            return tuple(kind for kind in self.rider_kind if kind in (RiderKind.HUMAN,RiderKind.ELF))
        return (None,)

    @staticmethod
    def _source_facts(npc):
        return {**{name:getattr(npc,name) for name in NpcSearchSpace._ordinary_names()
                if name not in ('armour','secondary_armour','helmet','shield','barding')},
            'armour':npc.armour.benefit,
            'secondary_armour':next((body for body in npc.armour.body
                if body is not npc.armour.benefit),None),
            'helmet':npc.armour.helmet,'shield':npc.armour.shield,'barding':npc.armour.barding}

    def _weapon_grips(self, weapon):
        return (self.weapon_grip if weapon in GENERATED_VARIABLE_GRIP_WEAPONS
            else generated_weapon_grips(weapon))

    def _initial_grips(self,kind,shield,*,chivalric=False):
        if chivalric and weapon_profile(WeaponKind(kind.value)).group in (WeaponGroup.SHOOTING,WeaponGroup.THROWING):
            return ()
        profile=weapon_profile(WeaponKind(kind.value))
        grips=(tuple(WeaponGrip.BOTH if grip is RangedWeaponHands.TWO_HANDED else WeaponGrip.LEFT
                for grip in self.weapon_grip) if profile.variable_grip else
            (WeaponGrip.BOTH,) if profile.hands is RangedWeaponHands.TWO_HANDED else (WeaponGrip.LEFT,))
        return tuple(grip for grip in grips if shield is None or grip is not WeaponGrip.BOTH)

    @staticmethod
    def _has_throwing(weapons):
        return any(weapon_profile(item.kind).group is WeaponGroup.THROWING for item in weapons)

    def _pose(self,items,shield,*,chivalric=False):
        """Choose a legal initial pose, retaining physical IDs and charges."""
        if not items:
            return ()
        primary=next((item for item in items if item.initial_location is WeaponItemLocation.HELD
            and self._initial_grips(GeneratedWeapon(item.kind.value),shield,chivalric=chivalric)),None)
        if primary is None:
            primary=next((item for item in items
                if self._initial_grips(GeneratedWeapon(item.kind.value),shield,chivalric=chivalric)),None)
        if primary is None:
            raise ValueError('inventory has no legal initially selected implement')
        grips=self._initial_grips(GeneratedWeapon(primary.kind.value),shield,chivalric=chivalric)
        grip=(primary.initial_grip if primary.initial_grip in grips or
            primary.initial_grip is WeaponGrip.RIGHT and WeaponGrip.LEFT in grips else grips[0])
        used={WeaponGrip.LEFT,WeaponGrip.RIGHT} if grip is WeaponGrip.BOTH else {grip}
        if shield is not None:
            used.add(WeaponGrip.LEFT if grip is WeaponGrip.RIGHT else WeaponGrip.RIGHT)
        result=[]
        # The first HELD source is the primary, even when an old primary was removed.
        ordered=(primary,)+tuple(item for item in items if item is not primary)
        for item in ordered:
            if item is primary:
                current=replace(item,initial_location=WeaponItemLocation.HELD,initial_grip=grip)
            else:
                single=next((hand for hand in (WeaponGrip.LEFT,WeaponGrip.RIGHT) if hand not in used),None)
                can_hold=(single is not None and WeaponGrip.LEFT in self._initial_grips(
                    GeneratedWeapon(item.kind.value),None,chivalric=chivalric))
                current=replace(item,initial_location=WeaponItemLocation.HELD if can_hold else WeaponItemLocation.CARRIED,
                    initial_grip=single if can_hold else None)
                if can_hold:
                    used.add(single)
            result.append(current)
        return tuple(result)

    def _build(self,facts,weapons,talents=(),ranged_values=None,*,throwing=None,ballistic_skill=None,rider_kind=None,
               talent_facts=None,tools=(),fellowship=None,leadership=None,oath_context=None):
        requirements=weapon_ranged_requirements(tuple(item.kind for item in weapons))
        names=self._ranged_names(weapons)
        values={name:(ranged_values[name] if ranged_values is not None and name in ranged_values
                and ranged_values[name] is not None else getattr(self,name)[0]) for name in names}
        if ballistic_skill is not None and 'ballistic_skill' in values:
            values['ballistic_skill']=ballistic_skill
        ranged=(None if requirements is None else GeneratedRangedFacts(
            values['ballistic_skill'],values['shooting'],values.get('initiative'),values.get('dexterity'),
            True,True if requirements.firearm else None,True if requirements.firearm else None,
            awareness=values.get('awareness')))
        has_throwing=self._has_throwing(weapons)
        throwing=(self.throwing[0] if throwing is None else throwing) if has_throwing else None
        ballistic_skill=((ranged.ballistic_skill if ranged is not None else
            self.ballistic_skill[0] if ballistic_skill is None else ballistic_skill) if has_throwing else None)
        main,secondary=facts['armour'],facts['secondary_armour']
        armour=ArmourLoadout(tuple(body for body in (main,secondary) if body is not None),main,
            facts['helmet'],facts['shield'],facts['barding'])
        ordinary={name:value for name,value in facts.items()
            if name not in ('armour','secondary_armour','helmet','shield','barding')}
        rider_choices=self._rider_choices(facts['mount'])
        rider_kind=rider_kind if rider_kind in rider_choices else rider_choices[0]
        return GeneratedNpc(**ordinary,weapons=weapons,armour=armour,talents=talents,ranged=ranged,
            throwing=throwing,ballistic_skill=ballistic_skill,rider_kind=rider_kind,
            talent_facts=talent_facts,tools=tools,fellowship=fellowship,leadership=leadership,oath_context=oath_context,
            agilulf_code_confirmed=self.agilulf_code_confirmed if BodyArmour.AGILULF in armour.body else None)

    def _musician_bundle(self,weapons,*,tools=(),talent_facts=None,fellowship=None,leadership=None,rng=None):
        """Propose explicit independent sources for a new paid music purchase.

        This is generation, not recovery of missing runtime gear from a flag.
        Existing instruments/Lore/actual ratings are retained unchanged.
        """
        choose=lambda values: values[0] if rng is None else rng.choice(values)
        if not tools:
            occupied={item.id for item in weapons}
            identifier='musicians-gear'
            index=1
            while identifier in occupied:
                identifier='musicians-gear:'+str(index)
                index+=1
            tools=(ToolItemSource(identifier,ToolKind.MUSICIANS_GEAR,
                choose(self.musician_instrument_hands),WeaponItemLocation.CARRIED,None),)
        facts=talent_facts or TalentOwnerFacts()
        music=next((lore for lore in facts.lores if lore.id=='music'),None)
        if music is not None and music.magic:
            raise ValueError('Music instrument use requires ordinary Music Lore, not a magic Lore alias')
        fellowship=(facts.fellowship if facts.fellowship is not None else choose(self.fellowship)
            ) if fellowship is None else fellowship
        leadership=choose(self.leadership) if leadership is None else leadership
        facts=replace(facts,fellowship=fellowship,
            lores=facts.lores if music is not None else (*facts.lores,TalentLoreFact('music',False)),
            equipment=facts.equipment if TalentEquipmentRequirement.MUSICIANS_GEAR in facts.equipment
                else (*facts.equipment,TalentEquipmentRequirement.MUSICIANS_GEAR))
        return dict(tools=tools,talent_facts=facts,fellowship=fellowship,leadership=leadership)

    def sample(self,rng:Random)->GeneratedNpc:
        oath=(rng.choice((None,*self.allowed_oath_sources)) if self.allowed_oath_sources else None)
        facts={name:rng.choice(getattr(self,name)) for name in self._ordinary_names()
            if name not in ('shield','mount','abilities','armour','secondary_armour','barding')}
        if oath is not None:
            for name in ('weapon_skill','strength','toughness','agility'):
                declared=getattr(oath.talent_facts,name)
                if declared is not None:
                    facts[name]=declared
        facts['mount']=self.mount[0] if len(self.mount)==1 else rng.choice(self.mount)
        bodies=self._body_choices()
        facts['armour']=rng.choice(bodies)
        facts['secondary_armour']=rng.choice(self._secondary_choices(facts['armour']))
        chivalric=BodyArmour.AGILULF in (facts['armour'],facts['secondary_armour'])
        count=rng.choice(self.weapon_count)
        shields=tuple(shield for shield in self.shield if not count or any(
            self._initial_grips(kind,shield,chivalric=chivalric) for kind in self.weapon))
        facts['shield']=rng.choice(shields)
        if count:
            primary=rng.choice(tuple(kind for kind in self.weapon
                if self._initial_grips(kind,facts['shield'],chivalric=chivalric)))
            grip=rng.choice(self._initial_grips(primary,facts['shield'],chivalric=chivalric))
            kinds=(primary,)+tuple(rng.choice(self.weapon) for _ in range(count-1))
        else:
            grip=None
            kinds=()
        if () not in self.abilities and all(
                weapon_printed_damage(WeaponKind(kind.value),strength=1) is None for kind in kinds):
            # Every chosen ability group needs a genuine numeric implement.
            # This selects a legal proposal before source construction; it
            # never silently removes an ability from an admitted character.
            numeric=tuple(kind for kind in self.weapon
                if weapon_printed_damage(WeaponKind(kind.value),strength=1) is not None
                and (count>1 or self._initial_grips(kind,facts['shield'],chivalric=chivalric)))
            if not numeric:
                raise ValueError('Damage-secondary proposal has no compatible numeric implement')
            selected=rng.choice(numeric)
            if count==1:
                kinds=(selected,)
                grip=rng.choice(self._initial_grips(selected,facts['shield'],chivalric=chivalric))
            else:
                kinds=(*kinds[:-1],selected)
        items=tuple(WeaponItemSource('item:'+str(index+1),WeaponKind(kind.value),
            WeaponItemLocation.HELD if index==0 else WeaponItemLocation.CARRIED,grip if index==0 else None,
            initially_loaded=rng.choice(self.initial_loaded) if weapon_reload_target(WeaponKind(kind.value)) is not None else None,
            initial_charges=rng.choice(self.scarab_initial_charges) if kind is GeneratedWeapon.SCARAB_KNIFE else 0,
            gm_fit_confirmed=self.ogre_fit_confirmed if kind is GeneratedWeapon.OGRE_PISTOL else None)
            for index,kind in enumerate(kinds))
        weapons=self._pose(items,facts['shield'],chivalric=chivalric)
        facts['abilities']=rng.choice(((),) if all(weapon_printed_damage(WeaponKind(kind.value),strength=1) is None for kind in kinds) else self.abilities)
        facts['barding']=rng.choice(tuple(value for value in self.barding if not value or facts['mount'] is not None))
        riders=self._rider_choices(facts['mount'])
        ranged_values={name:rng.choice(getattr(self,name)) for name in self._ranged_names(weapons)}
        if oath is not None:
            for name in ('ballistic_skill','initiative'):
                declared=getattr(oath.talent_facts,name)
                if declared is not None and name in ranged_values:
                    ranged_values[name]=declared
        talent_facts=(TalentOwnerFacts(fellowship=(oath.talent_facts.fellowship
                if oath is not None and oath.talent_facts.fellowship is not None else rng.choice(self.fellowship)))
            if TalentId.ALLIES_IN_ARMS in self.allowed_talents else None)
        if oath is not None:
            talent_facts=merge_oath_facts(talent_facts,oath.talent_facts)
        selected_music=TalentId.BATTLEFIELD_MUSICIAN in self.allowed_talents and bool(rng.randrange(2))
        talents=tuple(generated_talent_acquisition(t) for t in self.allowed_talents if (
            t is TalentId.BATTLEFIELD_MUSICIAN and selected_music) or (t is not TalentId.BATTLEFIELD_MUSICIAN and generated_talent_requirements_met(t,
            weapon_skill=facts['weapon_skill'],strength=facts['strength'],agility=facts['agility'],
            ballistic_skill=ranged_values.get('ballistic_skill'),
            fellowship=None if talent_facts is None else talent_facts.fellowship) and rng.randrange(2)))
        music=(self._musician_bundle(weapons,talent_facts=talent_facts,rng=rng)
            if selected_music else dict(talent_facts=talent_facts))
        talents=(*talents,*(oath.talents if oath is not None else ()))
        return self._build(facts,weapons,talents,ranged_values,
            oath_context=None if oath is None else oath.context,
            throwing=rng.choice(self.throwing) if self._has_throwing(weapons) else None,
            ballistic_skill=(ranged_values.get('ballistic_skill',oath.talent_facts.ballistic_skill
                if oath is not None and oath.talent_facts.ballistic_skill is not None else rng.choice(self.ballistic_skill))
                if self._has_throwing(weapons) else None),rider_kind=rng.choice(riders),**music)

    def mutate(self,npc:GeneratedNpc,rng:Random)->GeneratedNpc:
        if type(npc) is not GeneratedNpc or not self.contains(npc):
            raise ValueError('mutation requires an admitted member of this component space')
        facts=self._source_facts(npc)
        ranged_values=None if npc.ranged is None else {
            name:getattr(npc.ranged,name) for name in self._ranged_names(npc.weapons)}
        variable=[]
        def admit(label,newfacts=facts,items=None,**kwargs):
            try:
                weapons=npc.weapons if items is None else items
                if label in ('weapon','grip','add','remove','shield','armour','secondary_armour'):
                    weapons=self._pose(weapons,newfacts['shield'],chivalric=BodyArmour.AGILULF in (
                        newfacts['armour'],newfacts['secondary_armour']))
                candidate=self._build(newfacts,weapons,npc.talents,ranged_values,
                    throwing=npc.throwing,ballistic_skill=npc.ballistic_skill,rider_kind=npc.rider_kind,
                    talent_facts=npc.talent_facts,tools=npc.tools,fellowship=npc.fellowship,
                    leadership=npc.leadership,oath_context=npc.oath_context,**kwargs)
                if candidate!=npc and self.contains(candidate):
                    variable.append(candidate)
            except (ValueError,TypeError):
                pass
        for name in self._ordinary_names():
            if name in ('brawn','endurance') and getattr(npc,name) is None:
                continue
            for value in getattr(self,name):
                if value!=facts[name]:
                    admit(name,facts|{name:value})
        for index,item in enumerate(npc.weapons):
            for kind in self.weapon:
                if kind.value!=item.kind.value:
                    loaded=(item.initially_loaded if item.initially_loaded in self.initial_loaded else self.initial_loaded[0]
                        ) if weapon_reload_target(WeaponKind(kind.value)) is not None else None
                    new=WeaponItemSource(item.id,WeaponKind(kind.value),WeaponItemLocation.CARRIED,None,initially_loaded=loaded,
                        initial_charges=self.scarab_initial_charges[0] if kind is GeneratedWeapon.SCARAB_KNIFE else 0,
                        gm_fit_confirmed=self.ogre_fit_confirmed if kind is GeneratedWeapon.OGRE_PISTOL else None)
                    admit('weapon',items=npc.weapons[:index]+(new,)+npc.weapons[index+1:])
            if item.kind is WeaponKind.SCARAB_KNIFE:
                for charges in self.scarab_initial_charges:
                    if charges != item.initial_charges:
                        admit('scarab',items=npc.weapons[:index]+(replace(item,initial_charges=charges),)+npc.weapons[index+1:])
            if item.initially_loaded is not None:
                for loaded in self.initial_loaded:
                    if loaded is not item.initially_loaded:
                        admit('charge',items=npc.weapons[:index]+(replace(item,initially_loaded=loaded),)+npc.weapons[index+1:])
            if item.initial_location is WeaponItemLocation.HELD and weapon_profile(item.kind).variable_grip:
                for grip in self._initial_grips(GeneratedWeapon(item.kind.value),facts['shield']):
                    if grip is not item.initial_grip:
                        admit('grip',items=npc.weapons[:index]+(replace(item,initial_grip=grip),)+npc.weapons[index+1:])
        size=len(npc.weapons)
        for count in self.weapon_count:
            if count>size:
                # One finite add proposal per pool kind, without a Cartesian loadout grid.
                next_id=max((int(item.id.split(':')[1]) for item in npc.weapons
                    if item.id.startswith('item:') and item.id[5:].isdigit()),default=0)+1
                for kind in self.weapon:
                    added=tuple(WeaponItemSource('item:'+str(next_id+i),WeaponKind(kind.value),WeaponItemLocation.CARRIED,None,
                        initially_loaded=self.initial_loaded[0] if weapon_reload_target(WeaponKind(kind.value)) is not None else None,
                        initial_charges=self.scarab_initial_charges[0] if kind is GeneratedWeapon.SCARAB_KNIFE else 0,
                        gm_fit_confirmed=self.ogre_fit_confirmed if kind is GeneratedWeapon.OGRE_PISTOL else None)
                        for i in range(count-size))
                    admit('add',items=npc.weapons+added)
            elif count<size:
                for start in range(size-count+1):
                    admit('remove',items=npc.weapons[:start]+npc.weapons[start+size-count:])
        for kind in self._rider_choices(npc.mount):
            if kind is not npc.rider_kind:
                variable.append(replace(npc,rider_kind=kind))
        if npc.ranged is not None:
            for name in self._ranged_names(npc.weapons):
                for value in getattr(self,name):
                    if value!=getattr(npc.ranged,name):
                        changes={'ranged':replace(npc.ranged,**{name:value})}
                        if name=='ballistic_skill' and npc.ballistic_skill is not None:
                            changes['ballistic_skill']=value
                        # The current source was admitted above. A proposed
                        # lower BS may invalidate an owned Talent; omit that
                        # neighbour without repairing the submitted source.
                        try:
                            variable.append(replace(npc,**changes))
                        except (ValueError,TypeError):
                            pass
        if self._has_throwing(npc.weapons):
            for value in self.throwing:
                if value!=npc.throwing:
                    variable.append(replace(npc,throwing=value))
            if npc.ranged is None:
                for value in self.ballistic_skill:
                    if value!=npc.ballistic_skill:
                        try:
                            variable.append(replace(npc,ballistic_skill=value))
                        except (ValueError,TypeError):
                            pass
        fellowship=None if npc.talent_facts is None else npc.talent_facts.fellowship
        if TalentId.ALLIES_IN_ARMS in self.allowed_talents or fellowship is not None or npc.fellowship is not None:
            for value in self.fellowship:
                if value != fellowship:
                    try:
                        changes=dict(talent_facts=replace(npc.talent_facts or TalentOwnerFacts(),fellowship=value))
                        if npc.fellowship is not None:
                            changes['fellowship']=value
                        variable.append(replace(npc,**changes))
                    except (ValueError,TypeError):
                        pass
        if npc.leadership is not None:
            for value in self.leadership:
                if value!=npc.leadership:
                    variable.append(replace(npc,leadership=value))
        for index,item in enumerate(npc.tools):
            for hands in self.musician_instrument_hands:
                if hands!=item.hands_required:
                    try:
                        grip=(None if item.initial_location is WeaponItemLocation.CARRIED else
                            WeaponGrip.BOTH if hands==2 else WeaponGrip.LEFT)
                        tool=replace(item,hands_required=hands,initial_grip=grip)
                        variable.append(replace(npc,tools=npc.tools[:index]+(tool,)+npc.tools[index+1:]))
                    except (ValueError,TypeError):
                        pass
        for talent in self.allowed_talents:
            owned={entry.id:entry for entry in npc.talents}
            selected=(*tuple(owned.get(t) or generated_talent_acquisition(t)
                for t in self.allowed_talents if (t in owned)!=(t is talent)),
                *(entry for entry in npc.talents if entry.id in OATH_TALENT_IDS))
            # Readmit the full acquisitions, including explicit creation-free
            # waivers, rather than reinterpreting an existing source as paid.
            try:
                music=(self._musician_bundle(npc.weapons,tools=npc.tools,talent_facts=npc.talent_facts,
                    fellowship=npc.fellowship,leadership=npc.leadership)
                    if talent is TalentId.BATTLEFIELD_MUSICIAN and talent not in owned else {})
                variable.append(replace(npc,talents=selected,**music))
            except (ValueError,TypeError):
                pass
        if self.allowed_oath_sources or npc.oath_context is not None:
            ordinary=tuple(entry for entry in npc.talents if entry.id not in OATH_TALENT_IDS)
            for oath in (None,*self.allowed_oath_sources):
                try:
                    candidate=replace(npc,talents=(*ordinary,*(oath.talents if oath is not None else ())),
                        oath_context=None if oath is None else oath.context,
                        talent_facts=npc.talent_facts if oath is None else merge_oath_facts(npc.talent_facts,oath.talent_facts))
                    if candidate!=npc and self.contains(candidate):
                        variable.append(candidate)
                except (ValueError,TypeError):
                    pass
            variable=[candidate for candidate in variable if self.contains(candidate)]
        return rng.choice(variable) if variable else npc

    def contains(self,npc:GeneratedNpc)->bool:
        if type(npc) is not GeneratedNpc:
            return False
        try:
            replace(npc)
        except (ValueError,TypeError):
            return False
        facts=self._source_facts(npc)
        return (all(facts[name] in getattr(self,name) or name in ('brawn','endurance')
                and getattr(npc,name) is None for name in self._ordinary_names())
            and len(npc.weapons) in self.weapon_count
            and all(GeneratedWeapon(item.kind.value) in self.weapon and item.quantity==1
                and (item.initially_loaded is None or item.initially_loaded in self.initial_loaded)
                and (item.kind is not WeaponKind.SCARAB_KNIFE or item.initial_charges in self.scarab_initial_charges)
                and (item.kind is not WeaponKind.OGRE_PISTOL or item.gm_fit_confirmed is self.ogre_fit_confirmed)
                and (not weapon_profile(item.kind).variable_grip or item.initial_grip is None
                    or (RangedWeaponHands.TWO_HANDED if item.initial_grip is WeaponGrip.BOTH
                        else RangedWeaponHands.ONE_HANDED) in self.weapon_grip) for item in npc.weapons)
            and npc.rider_kind in self._rider_choices(npc.mount)
            and (not self._has_throwing(npc.weapons) or npc.throwing in self.throwing
                and (npc.ranged is not None or npc.ballistic_skill in self.ballistic_skill))
            and (npc.ranged is None or all(getattr(npc.ranged,name) in getattr(self,name)
                for name in self._ranged_names(npc.weapons)))
            and (npc.ranged is None or npc.ranged.awareness is None
                or 'awareness' in self._ranged_names(npc.weapons) and npc.ranged.awareness in self.awareness)
            and (npc.talent_facts is None or npc.talent_facts.fellowship is None
                or npc.talent_facts.fellowship in self.fellowship)
            and (npc.fellowship is None or npc.fellowship in self.fellowship)
            and (npc.leadership is None or npc.leadership in self.leadership)
            and all(item.kind is ToolKind.MUSICIANS_GEAR
                and item.hands_required in self.musician_instrument_hands for item in npc.tools)
            and (TalentId.BATTLEFIELD_MUSICIAN not in {entry.id for entry in npc.talents}
                or bool(npc.tools) and npc.fellowship is not None and npc.leadership is not None
                and npc.talent_facts is not None
                and TalentLoreFact('music',False) in npc.talent_facts.lores)
            and {entry.id for entry in npc.talents if entry.id not in OATH_TALENT_IDS}<=set(self.allowed_talents)
            and ((npc.oath_context is None and not any(entry.id in OATH_TALENT_IDS for entry in npc.talents))
                or any(matches_oath_source(npc,source) for source in self.allowed_oath_sources)))

    def resample_numeric(self,composition:tuple[GeneratedNpc,...],rng:Random,*,bias:float=0.)->NumericCompositionSample:
        """Resample ratings only; preserve every physical source and its readiness."""
        if type(bias) not in (int,float) or not -1<=bias<=1 or not isfinite(bias):
            raise ValueError('numeric sampling bias must be finite in -1..1, excluding bool')
        if type(composition) is not tuple or not composition or any(not self.contains(member) for member in composition):
            raise ValueError('numeric sampling requires a nonempty admitted composition tuple')
        members=[]
        variable_fields=0
        for member in composition:
            current=member
            ranged_names=self._ranged_names(member.weapons)
            names=('weapon_skill','strength','toughness','agility','melee','athletics','defence')
            names+=(('brawn',) if member.brawn is not None else ())
            names+=(('endurance',) if member.endurance is not None else ())
            names+=(('throwing',) if self._has_throwing(member.weapons) else ())
            names+=(('ballistic_skill',) if self._has_throwing(member.weapons) and not ranged_names else ())
            names+=ranged_names
            if member.leadership is not None:
                names+=('leadership',)
            if (TalentId.ALLIES_IN_ARMS in self.allowed_talents
                    or member.talent_facts is not None and member.talent_facts.fellowship is not None
                    or member.fellowship is not None):
                names+=('fellowship',)
            for name in names:
                candidates={}
                for value in getattr(self,name):
                    try:
                        if name=='fellowship':
                            changes=dict(talent_facts=replace(current.talent_facts or TalentOwnerFacts(),fellowship=value))
                            if current.fellowship is not None:
                                changes['fellowship']=value
                            candidate=replace(current,**changes)
                        elif name in ranged_names:
                            changes={'ranged':replace(current.ranged,**{name:value})}
                            if name=='ballistic_skill' and current.ballistic_skill is not None:
                                changes['ballistic_skill']=value
                            candidate=replace(current,**changes)
                        else:
                            candidate=replace(current,**{name:value})
                    except ValueError:
                        continue
                    candidates[value]=candidate
                if len(candidates)>1:
                    variable_fields+=1
                current=candidates[_sample_numeric_value(tuple(candidates),rng,float(bias))]
            members.append(current)
        result=tuple(members)
        return NumericCompositionSample(result,float(bias),variable_fields,sum(a!=b for a,b in zip(composition,result)))


def automatic_npc_search_space(party: tuple[PcMeleeParticipant, ...], *,
        battlefield: PcBattlefieldSpec | None = None) -> NpcSearchSpace:
    """A bounded search envelope around the party, not a book NPC stat limit.

    The battle targets rank sampled compositions; they do not prescribe a
    monotonic stat multiplier. No authored abilities are granted implicitly.
    """
    if not party:
        raise ValueError('automatic NPC space needs a party')
    if battlefield is not None:
        if type(battlefield) is not PcBattlefieldSpec:
            raise TypeError('automatic NPC space requires an exact battlefield spec or None')
        replace(battlefield)
    choices = {}
    for name in ('weapon_skill', 'strength', 'toughness', 'agility', 'melee', 'defence', 'athletics','endurance'):
        values = [getattr(p.pc, name) for p in party]
        floor, ceiling = (2, 6) if name in ('melee', 'defence', 'athletics','endurance') else (1, 10)
        low = max(floor, min(ceiling, min(values) - 1))
        high = max(low, min(ceiling, max(values) + 1))
        choices[name] = tuple(range(low, high + 1))
    # Include useful resistance near a mage's ordinary Lightning potency;
    # the physical-only envelope otherwise misses these candidate profiles.
    from towr.domain.pc_magic_source_models import PcSpellId
    toughness = set(choices['toughness'])
    for member in party:
        if member.wizard is not None and PcSpellId.LIGHTNING_BLAST in member.wizard.memorised_spells:
            pivot = min(10,4+(member.wizard.reason*member.wizard.willpower+9)//10)
            toughness.update((max(1,pivot-1),pivot))
    choices['toughness'] = tuple(sorted(toughness))
    for name in ('throwing','brawn'):
        values = [getattr(member.pc,name) for member in party if getattr(member.pc,name) is not None]
        if values:
            low,high = max(2,min(6,min(values)-1)),max(2,min(6,max(values)+1))
            choices[name] = tuple(range(low,high+1))
    fellowship=[member.pc.fellowship if member.pc.fellowship is not None else member.talent_facts.fellowship
        for member in party if member.pc.fellowship is not None
            or member.talent_facts is not None and member.talent_facts.fellowship is not None]
    if fellowship:
        low=max(1,min(10,min(fellowship)-1))
        high=max(low,min(10,max(fellowship)+1))
        choices['fellowship']=tuple(range(low,high+1))
    leadership=[member.pc.leadership for member in party if member.pc.leadership is not None]
    if leadership:
        low,high=max(2,min(6,min(leadership)-1)),max(2,min(6,max(leadership)+1))
        choices['leadership']=tuple(range(low,high+1))
    # Melee-only parties have no BS/I/Shooting/Dexterity facts. Use the
    # explicit starting envelope rather than pretending their WS/Ag are those
    # characteristics. Where an admitted PC source supplies ranged facts,
    # centre each corresponding range around those actual values.
    for name in ('ballistic_skill','shooting','initiative','dexterity','awareness'):
        values=[getattr(member.pc.ranged,name) for member in party
            if member.pc.ranged is not None and getattr(member.pc.ranged,name) is not None]
        if name == 'ballistic_skill':
            values.extend(member.pc.ballistic_skill for member in party
                if member.pc.ballistic_skill is not None)
        if values:
            floor,ceiling=(2,6) if name in ('shooting','dexterity','awareness') else (1,10)
            low=max(floor,min(ceiling,min(values)-1))
            high=max(low,min(ceiling,max(values)+1))
            choices[name]=tuple(range(low,high+1))
    choices['weapon'] = GENERATED_ORDINARY_WEAPONS if battlefield is not None else GENERATED_CLOSE_WEAPONS
    choices['mount'] = ((None,CombatMount.HORSE,CombatMount.BRETONNIAN_WARHORSE,CombatMount.ELVEN_STEED)
        if battlefield is not None else (None,))
    choices['helmet'] = (None,HelmetKind.HELMET)
    choices['barding'] = (False,True) if battlefield is not None else (False,)
    return NpcSearchSpace(**choices)


@dataclass(frozen=True, slots=True)
class DynamicEncounterRequest:
    party: tuple[PcMeleeParticipant, ...]
    facts: PcMeleeFacts
    day_id: str
    space: NpcSearchSpace
    minimum_npcs: int
    maximum_npcs: int
    target_win_rate: float
    target_rounds: float
    master_seed: int
    max_candidates: int
    exploration_trials: int
    finalist_trials: int
    top_k: int
    max_total_trials: int
    max_rounds: int
    defeat_disposition: NpcDefeatDisposition
    battlefield: PcBattlefieldSpec | None = field(default=None,kw_only=True)
    music_acoustics: BattlefieldMusicAcoustics | None = field(default=None,kw_only=True)
    single_combat_pairs: tuple[PcSingleCombatPair,...] = field(default=(),kw_only=True)

    def __post_init__(self):
        if type(self.party) is not tuple or not self.party or any(type(p) is not PcMeleeParticipant for p in self.party):
            raise TypeError('party must be a nonempty tuple of typed PC participants')
        if len({p.actor_id for p in self.party}) != len(self.party):
            raise ValueError('party actor IDs must be unique')
        if type(self.facts) is not PcMeleeFacts or type(self.space) is not NpcSearchSpace:
            raise TypeError('generation requires typed facts and search space')
        replace(self.facts)
        replace(self.space)
        if self.music_acoustics is not None:
            if type(self.music_acoustics) is not BattlefieldMusicAcoustics:
                raise TypeError('dynamic music acoustics require exact GM facts or None')
            replace(self.music_acoustics)
        if self.battlefield is None:
            if any(mount is not None for mount in self.space.mount) or any(
                    member.mount is not None for member in self.party):
                raise ValueError('mounted dynamic encounters require an explicit battlefield')
            if not self.facts.all_opponents_close or self.facts.can_leave_zone:
                raise ValueError('stationary dynamic request requires the all-Close arena')
            if any(weapon in GENERATED_NON_CLOSE_RANGED_WEAPONS for weapon in self.space.weapon):
                raise ValueError('non-Close generated Shooting requires an explicit battlefield')
            if any(p.pc.weapon in PC_RANGED_WEAPONS and p.pc.weapon.value not in
                    ('pistol','repeater_pistol','repeater_handbow') for p in self.party):
                raise ValueError('stationary dynamic request requires supported Close ranged PCs')
        else:
            if type(self.battlefield) is not PcBattlefieldSpec:
                raise TypeError('dynamic battlefield must be an exact PcBattlefieldSpec or None')
            replace(self.battlefield)
        if type(self.day_id) is not str or not self.day_id.strip():
            raise ValueError('day ID is required')
        if type(self.defeat_disposition) is not NpcDefeatDisposition:
            raise TypeError('an explicit GM defeat disposition is required')
        if (self.defeat_disposition is NpcDefeatDisposition.DISARMED_AND_SURRENDERED
                and BodyArmour.AGILULF in (*self.space.armour,*self.space.secondary_armour)):
            raise ValueError('Agilulf cannot be generated with a surrendered/captive defeat disposition')
        for name in ('minimum_npcs', 'maximum_npcs', 'max_candidates', 'exploration_trials',
                'finalist_trials', 'top_k', 'max_total_trials', 'max_rounds'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        if self.minimum_npcs > self.maximum_npcs or self.top_k > self.max_candidates:
            raise ValueError('count bounds/top_k are inconsistent')
        from towr.domain.pc_melee_models import validate_pc_single_combat_pairs
        validate_pc_single_combat_pairs(self.single_combat_pairs,
            tuple(member.actor_id for member in self.party),
            tuple(f'generated-npc:{index+1}' for index in range(self.minimum_npcs)))
        from towr.domain.pc_scene_feature_models import validate_scene_visibility_actors
        validate_scene_visibility_actors(self.battlefield,(*tuple(member.actor_id for member in self.party),
            *tuple(f'generated-npc:{index+1}' for index in range(self.minimum_npcs))))
        if type(self.master_seed) is not int or not 0 <= self.master_seed < 2**64:
            raise ValueError('master seed must fit uint64')
        for name in ('target_win_rate', 'target_rounds'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError('targets must be finite numbers')
        if not 0 <= self.target_win_rate <= 1 or not 1 <= self.target_rounds <= self.max_rounds:
            raise ValueError('targets are outside encounter bounds')
        if self.max_candidates*self.exploration_trials + self.top_k*self.finalist_trials > self.max_total_trials:
            raise ValueError('search and independent validation exceed the trial budget')
        # Validate the actual execution bridge before spending any simulation budget.
        self.scenario(tuple(self.space.sample(Random(0)) for _ in range(self.maximum_npcs)), 'preflight')

    def scenario(self, composition: tuple[GeneratedNpc, ...], candidate_id: str) -> PcMeleeScenario:
        actors = tuple(f'generated-npc:{i+1}' for i in range(len(composition)))
        if set(actors) & {p.actor_id for p in self.party}:
            raise ValueError('generated actor IDs collide with party IDs')
        party = tuple(replace(p, target_priority=actors,
            defeat_decisions=tuple(MinionDefeatDecision(p.actor_id, a, self.defeat_disposition, True) for a in actors))
            for p in self.party)
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        actual_facts = replace(self.facts, unmounted=not any(
            member.mount is not None for member in party)
            and not any(npc.mount is not None for npc in composition))
        return PcMeleeScenario(candidate_id, party, self.day_id,
            tuple(n.participant(a) for n, a in zip(composition, actors)), actual_facts,
            tuple(p.actor_id for p in party), actors, tuple(p.actor_id for p in party), self.max_rounds,
            None, (), npc_extra_attack_actor_ids=(), npc_grudge_policies=(), npc_blood_rage_actor_ids=(),
            npc_flagellant_policies=(), npc_warped_form_policies=(),
            npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
                for npc,actor in zip(composition,actors) if npc.ranged is not None),
            battlefield=self.battlefield,music_acoustics=self.music_acoustics,
            single_combat_pairs=self.single_combat_pairs)


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    composition: tuple[GeneratedNpc, ...]
    summary: PcMeleeSimulationSummary

    def __post_init__(self):
        if type(self.composition) is not tuple or not self.composition or any(type(n) is not GeneratedNpc for n in self.composition):
            raise TypeError('candidate requires a nonempty typed composition')
        if type(self.summary) is not PcMeleeSimulationSummary:
            raise TypeError('candidate requires its typed aggregate')
        replace(self.summary)
        enemies = self.summary.source_request.scenario.enemies
        if len(enemies) != len(self.composition) or any(
                npc.participant(enemy.state.actor_id) != enemy for npc, enemy in zip(self.composition, enemies)):
            raise ValueError('candidate components do not match the complete executable source')

    @property
    def win_rate(self):
        return self.summary.outcome_counts.objective_achieved / self.summary.trials

    @property
    def mean_started_rounds(self):
        return self.summary.total_started_round_count / self.summary.trials

    @property
    def win_interval_95(self):
        """Wilson interval; conditional on this fixed candidate and tactics."""
        n, p, z = self.summary.trials, self.win_rate, 1.959963984540054
        denominator = 1 + z*z/n
        center = (p + z*z/(2*n))/denominator
        half = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
        return max(0., center-half), min(1., center+half)

    @property
    def rounds_interval_95(self):
        """Conservative Hoeffding bound for started rounds, including censored trials."""
        maximum = self.summary.source_request.scenario.max_rounds
        half = (maximum-1)*sqrt(log(40)/(2*self.summary.trials))
        return max(1., self.mean_started_rounds-half), min(float(maximum), self.mean_started_rounds+half)


@dataclass(frozen=True, slots=True)
class DynamicEncounterResult:
    source: DynamicEncounterRequest
    explored: tuple[GeneratedCandidate, ...]
    validations: tuple[GeneratedCandidate, ...]
    total_trials: int
    proposal_attempts: int
    proposal_limit_reached: bool

    @property
    def finalists(self):
        return tuple(c for c in self.validations if not c.summary.outcome_counts.unsupported_path)

    @property
    def target_match_found(self):
        return any(assess_dynamic_candidate(self.source,c).status is DynamicTargetStatus.WITHIN_TARGETS
            for c in self.finalists)


WIN_RATE_TOLERANCE = .1
STARTED_ROUNDS_TOLERANCE = 1.


class DynamicTargetStatus(str, Enum):
    WITHIN_TARGETS = 'within_targets'
    OUTSIDE_TARGETS = 'outside_targets'
    UNSUPPORTED = 'unsupported'


@dataclass(frozen=True, slots=True)
class DynamicTargetAssessment:
    """Point estimates under the current trial/tactics budget, not certification."""
    status: DynamicTargetStatus
    win_rate_in_range: bool
    started_rounds_in_range: bool
    win_rate_deviation: float
    started_rounds_deviation: float
    normalized_max_deviation: float
    normalized_total_deviation: float


def assess_dynamic_targets(target_win_rate, target_rounds, win_rate, mean_started_rounds,
        unsupported_path) -> DynamicTargetAssessment:
    values = (target_win_rate,target_rounds,win_rate,mean_started_rounds)
    if (any(type(v) not in (int,float) or not isfinite(v) for v in values)
            or not 0 <= target_win_rate <= 1 or not 0 <= win_rate <= 1
            or target_rounds < 1 or mean_started_rounds < 1
            or type(unsupported_path) is not int or unsupported_path < 0):
        raise ValueError('joint target assessment requires finite admitted aggregates')
    win_error = abs(win_rate-target_win_rate)
    rounds_error = abs(mean_started_rounds-target_rounds)
    # One numerical convention for both inclusion and ranking. Rounding only
    # removes floating arithmetic noise at 1e-12 of a tolerance unit.
    def normalized(error,tolerance):
        value = error/tolerance
        return 1. if abs(value-1) <= 1e-12 else round(value,12)
    win_distance = normalized(win_error,WIN_RATE_TOLERANCE)
    round_distance = normalized(rounds_error,STARTED_ROUNDS_TOLERANCE)
    win_match,round_match = win_distance <= 1,round_distance <= 1
    status = (DynamicTargetStatus.UNSUPPORTED if unsupported_path else
        DynamicTargetStatus.WITHIN_TARGETS if win_match and round_match else
        DynamicTargetStatus.OUTSIDE_TARGETS)
    return DynamicTargetAssessment(status,win_match,round_match,win_error,rounds_error,
        max(win_distance,round_distance),win_distance+round_distance)


def assess_dynamic_candidate(request, candidate) -> DynamicTargetAssessment:
    return assess_dynamic_targets(request.target_win_rate,request.target_rounds,
        candidate.win_rate,candidate.mean_started_rounds,candidate.summary.outcome_counts.unsupported_path)


def _seed(master: int, stage: str, index: int) -> int:
    return int.from_bytes(sha256(f'towr:dynamic:v1:{master}:{stage}:{index}'.encode()).digest()[:8], 'big')


def _score(request, candidate):
    assessment = assess_dynamic_candidate(request,candidate)
    return (assessment.status is DynamicTargetStatus.UNSUPPORTED,
        assessment.normalized_max_deviation,assessment.normalized_total_deviation)


def _directed_count_parent(request, explored):
    """Advance an observed win-rate plateau without pruning any count range.

    This only chooses a proposal parent. Final ranking uses the joint-target
    score; independent trials must check whether the proposed resize helped.
    """
    eligible = [c for c in explored if not c.summary.outcome_counts.unsupported_path]
    if not eligible:
        return None
    best = min(eligible, key=lambda c: _score(request, c))
    if best.win_rate == request.target_win_rate:
        return None
    plateau = [c for c in eligible if c.win_rate == best.win_rate]
    if best.win_rate > request.target_win_rate:
        parent = max(plateau, key=lambda c: len(c.composition))
        return parent if len(parent.composition) < request.maximum_npcs else None
    parent = min(plateau, key=lambda c: len(c.composition))
    return parent if len(parent.composition) > request.minimum_npcs else None


class _ProposalOperation(str, Enum):
    COUNT = 'count'
    COMPONENT = 'component'
    RESTART = 'restart'


@dataclass(frozen=True, slots=True)
class _Proposal:
    requested: _ProposalOperation
    applied: _ProposalOperation
    composition: tuple[GeneratedNpc, ...]


def _select_proposal_operation(request: DynamicEncounterRequest, explored_count: int,
        attempt_number: int, rng: Random) -> _ProposalOperation:
    if explored_count and rng.random() < .7:
        return (_ProposalOperation.COUNT
            if request.minimum_npcs != request.maximum_npcs and explored_count % 2
            else _ProposalOperation.COMPONENT)
    return _ProposalOperation.RESTART


def _propose(request: DynamicEncounterRequest, explored: list[GeneratedCandidate],
        rng: Random, operation: _ProposalOperation) -> _Proposal:
    if type(operation) is not _ProposalOperation:
        raise TypeError('proposal operation must be typed')
    if operation is _ProposalOperation.RESTART:
        composition = tuple(request.space.sample(rng)
            for _ in range(rng.randint(request.minimum_npcs, request.maximum_npcs)))
        return _Proposal(operation, operation, composition)
    if not explored:
        raise ValueError('adaptive proposal requires observations')
    elite = sorted(explored, key=lambda candidate: _score(request, candidate))[:max(1, request.top_k)]
    composition = list(rng.choice(elite).composition)
    parent = (_directed_count_parent(request, explored)
        if operation is _ProposalOperation.COUNT and request.minimum_npcs != request.maximum_npcs else None)
    if parent is not None:
        composition = list(parent.composition)
        if parent.win_rate > request.target_win_rate:
            composition.append(request.space.sample(rng))
        else:
            composition.pop(rng.randrange(len(composition)))
        applied = _ProposalOperation.COUNT
    else:
        index = rng.randrange(len(composition))
        composition[index] = request.space.mutate(composition[index], rng)
        applied = _ProposalOperation.COMPONENT
    return _Proposal(operation, applied, tuple(composition))


def validate_dynamic_encounter_result(result: DynamicEncounterResult) -> None:
    """Check the complete source, stage seeds, selection and accounting without trials."""
    if type(result) is not DynamicEncounterResult or type(result.source) is not DynamicEncounterRequest:
        raise TypeError('expected a typed dynamic result and source')
    request = replace(result.source)
    if type(result.explored) is not tuple or not 1 <= len(result.explored) <= request.max_candidates:
        raise ValueError('explored candidates exceed the source bounds')
    compositions = tuple(c.composition for c in result.explored)
    if len(set(compositions)) != len(compositions):
        raise ValueError('exploration contains duplicate compositions')

    def check(candidate, stage, index, trials):
        if type(candidate) is not GeneratedCandidate:
            raise TypeError('observations must be typed generated candidates')
        replace(candidate)
        if not request.minimum_npcs <= len(candidate.composition) <= request.maximum_npcs:
            raise ValueError('candidate count is outside the search space')
        for npc in candidate.composition:
            if not request.space.contains(npc):
                raise ValueError('candidate component is outside the search space')
        expected = PcMeleeSimulationRequest(request.scenario(candidate.composition, f'dynamic:{stage}:{index}'),
            _seed(request.master_seed, stage, index), trials)
        if candidate.summary.source_request != expected:
            raise ValueError('candidate source/seed/stage differs from generation source')

    for i, candidate in enumerate(result.explored):
        check(candidate, 'explore', i, request.exploration_trials)
    eligible = [c for c in sorted(result.explored, key=lambda c: _score(request, c))
        if not c.summary.outcome_counts.unsupported_path][:request.top_k]
    if type(result.validations) is not tuple or len(result.validations) != len(eligible):
        raise ValueError('validation must cover the selected exploration finalists')
    indices = {c.composition: i for i, c in enumerate(eligible)}
    if set(c.composition for c in result.validations) != set(indices):
        raise ValueError('validation compositions differ from exploration finalists')
    for candidate in result.validations:
        check(candidate, 'validate', indices[candidate.composition], request.finalist_trials)
    ranked = tuple(sorted(result.validations, key=lambda c: (_score(request, c), indices[c.composition])))
    if result.validations != ranked:
        raise ValueError('validation ranking is inconsistent')
    expected_total = len(result.explored)*request.exploration_trials + len(result.validations)*request.finalist_trials
    if type(result.total_trials) is not int or result.total_trials != expected_total or expected_total > request.max_total_trials:
        raise ValueError('trial accounting differs from executed observations/budget')
    limit = request.max_candidates*30
    if type(result.proposal_attempts) is not int or not len(result.explored) <= result.proposal_attempts <= limit:
        raise ValueError('proposal accounting is outside the budget')
    expected_limit = result.proposal_attempts == limit and len(result.explored) < request.max_candidates
    if type(result.proposal_limit_reached) is not bool or result.proposal_limit_reached != expected_limit:
        raise ValueError('proposal limit flag is inconsistent')


class DynamicEncounterCancelled(Exception):
    """Explicit interruption; no partial encounter report is returned."""


class DynamicProgressPhase(str, Enum):
    GENERATING = 'generating'
    SIMULATING = 'simulating'
    CANDIDATE_COMPLETE = 'candidate_complete'
    SELECTING = 'selecting'
    COMPLETE = 'complete'


@dataclass(frozen=True, slots=True)
class DynamicEncounterProgress:
    """Transient observations, not a partial result or a battle journal."""
    phase: DynamicProgressPhase
    stage: str | None
    candidate_number: int
    candidate_count: int
    npc_count: int
    completed_trials: int
    trial_count: int
    total_completed_trials: int
    trial_budget: int
    wins: int
    unsupported_trials: int

    def __post_init__(self):
        if type(self.phase) is not DynamicProgressPhase or self.stage not in (None, 'explore', 'validate'):
            raise ValueError('invalid progress phase/stage')
        for field in fields(self):
            if field.name in ('phase', 'stage'):
                continue
            if type(getattr(self, field.name)) is not int or getattr(self, field.name) < 0:
                raise ValueError('progress counters must be nonnegative integers')
        if (self.completed_trials > self.trial_count
                or self.wins + self.unsupported_trials > self.completed_trials
                or not self.completed_trials <= self.total_completed_trials <= self.trial_budget
                or self.candidate_number > self.candidate_count):
            raise ValueError('inconsistent progress counters')

    @property
    def win_rate(self):
        return self.wins / self.completed_trials if self.completed_trials else None


def search_dynamic_encounter(request: DynamicEncounterRequest, simulator=None, *,
        cancel_requested=None,on_progress=None,execution: SimulationExecutionOptions | None=None) -> DynamicEncounterResult:
    """Preserve ordered adaptive search while a process pool runs its trials."""
    if execution is not None:
        if not isinstance(execution,SimulationExecutionOptions):
            raise TypeError('execution requires typed simulation options')
        replace(execution)
        if simulator is not None:
            raise ValueError('custom simulator and execution options cannot be combined')
        if execution.mode is SimulationExecutionMode.PROCESS and execution.batch_size!=1:
            raise ValueError('dynamic process execution requires one-trial batches')
    if execution is not None and execution.mode is SimulationExecutionMode.PROCESS:
        from towr.simulation.pc_melee_process import PcMeleeProcessSession,PcMeleeSimulationCancelled
        try:
            with PcMeleeProcessSession(workers=execution.workers,batch_size=execution.batch_size,
                    cancel_requested=cancel_requested) as session:
                return _search_dynamic_encounter(request,cancel_requested=cancel_requested,
                    on_progress=on_progress,process_session=session)
        except PcMeleeSimulationCancelled as error:
            raise DynamicEncounterCancelled('dynamic encounter search cancelled') from error
    return _search_dynamic_encounter(request,simulator,cancel_requested=cancel_requested,
        on_progress=on_progress)


def _search_dynamic_encounter(request: DynamicEncounterRequest, simulator=None, *,
        cancel_requested=None,on_progress=None,process_session=None) -> DynamicEncounterResult:
    """Explore random restarts and local mutations, then independently validate.

    Ranking: no unsupported observations, worst normalized joint deviation,
    total normalized deviation, proposal order. Point matches are not certified.
    """
    if type(request) is not DynamicEncounterRequest:
        raise TypeError('expected a DynamicEncounterRequest')
    replace(request)
    if cancel_requested is not None and not callable(cancel_requested):
        raise TypeError('cancel_requested must be callable')
    if on_progress is not None and not callable(on_progress):
        raise TypeError('on_progress must be callable')

    def checkpoint():
        if cancel_requested is not None and cancel_requested():
            raise DynamicEncounterCancelled('dynamic encounter search cancelled')

    completed_total = 0

    def emit(phase, stage=None, number=0, count=0, npc_count=0, completed=0, trials=0, wins=0, unsupported=0):
        checkpoint()
        if on_progress is not None:
            on_progress(DynamicEncounterProgress(phase, stage, number, count, npc_count,
                completed, trials, completed_total + completed, request.max_total_trials, wins, unsupported))
        checkpoint()

    checkpoint()
    default_simulator = simulator is None
    if default_simulator:
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        from towr.domain.pc_melee_result_models import PcMeleeOutcome
        if process_session is None:
            class InterruptibleRandom(Random):
                def randint(self, start, end):
                    checkpoint()
                    return super().randint(start, end)

            rng_factory = Random if cancel_requested is None else InterruptibleRandom
    elif not callable(simulator):
        raise TypeError('simulator must be callable')
    rng = Random(_seed(request.master_seed, 'proposals', 0))
    explored, seen = [], set()

    def score(candidate):
        return _score(request, candidate)

    def evaluate(composition, stage, index, candidate_count):
        nonlocal completed_total
        checkpoint()
        scenario = request.scenario(composition, f'dynamic:{stage}:{index}')
        trials = request.exploration_trials if stage == 'explore' else request.finalist_trials
        source = PcMeleeSimulationRequest(scenario, _seed(request.master_seed, stage, index), trials)
        emit(DynamicProgressPhase.SIMULATING, stage, index+1, candidate_count, len(composition), trials=trials)
        completed, wins, unsupported = 0, 0, 0

        def observed(record):
            nonlocal completed, wins, unsupported
            completed += 1
            wins += int(record.outcome is PcMeleeOutcome.OBJECTIVE_ACHIEVED)
            unsupported += int(record.outcome is PcMeleeOutcome.UNSUPPORTED_PATH)
            emit(DynamicProgressPhase.SIMULATING, stage, index+1, candidate_count,
                len(composition), completed, trials, wins, unsupported)

        if default_simulator:
            if process_session is None:
                result=run_pc_melee_simulation(source,rng_factory=rng_factory,
                    on_trial_complete=observed if on_progress is not None else None)
            else:
                result=process_session.run(source,
                    on_trial_complete=observed if on_progress is not None else None)
            summary = summarize_pc_melee_simulation(result)
        else:
            summary = simulator(source)
        checkpoint()
        if type(summary) is not PcMeleeSimulationSummary:
            raise TypeError('simulator must return a typed aggregate')
        replace(summary)
        if summary.source_request != source:
            raise ValueError('simulator returned another candidate/seed/trial source')
        candidate = GeneratedCandidate(composition, summary)
        emit(DynamicProgressPhase.CANDIDATE_COMPLETE, stage, index+1, candidate_count,
            len(composition), trials, trials, summary.outcome_counts.objective_achieved,
            summary.outcome_counts.unsupported_path)
        completed_total += trials
        return candidate

    attempts, limit = 0, request.max_candidates*30
    announced_candidate = -1
    while len(explored) < request.max_candidates and attempts < limit:
        checkpoint()
        if announced_candidate != len(explored):
            announced_candidate = len(explored)
            emit(DynamicProgressPhase.GENERATING, 'explore', len(explored)+1, request.max_candidates)
        attempts += 1
        operation = _select_proposal_operation(request, len(explored), attempts, rng)
        composition = _propose(request, explored, rng, operation).composition
        if composition in seen:
            continue
        seen.add(composition)
        explored.append(evaluate(composition, 'explore', len(explored), request.max_candidates))
    emit(DynamicProgressPhase.SELECTING)
    eligible = [c for c in sorted(explored, key=score) if not c.summary.outcome_counts.unsupported_path]
    chosen = eligible[:request.top_k]
    validated = [evaluate(c.composition, 'validate', i, len(chosen)) for i, c in enumerate(chosen)]
    # Failed validation remains visible in explored/validation observations, never a selected recommendation.
    finalists = tuple(sorted(validated, key=score))
    total = len(explored)*request.exploration_trials + len(validated)*request.finalist_trials
    checkpoint()
    result = DynamicEncounterResult(request, tuple(explored), finalists, total, attempts,
        attempts == limit and len(explored) < request.max_candidates)
    emit(DynamicProgressPhase.COMPLETE)
    return result
