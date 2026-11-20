"""Bind common acquisition facts to the real initial PC/NPC source.

The derived prerequisite view never reads temporary battle Conditions. Optional
facts may supply additional characteristics, but cannot overwrite a printed
base characteristic already present in the actor definition.
"""
from dataclasses import replace

from towr.domain.talent_catalog import TalentId, TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent, TalentLoreFact, TalentOwnerFacts, has_talent, talent_purchases, validate_acquired_talents,
)


# These sets describe connected owners, not a catalog of permitted statblocks.
# Expand only with real execution, source and once-only consumers.
PC_EXECUTABLE_TALENTS = frozenset((TalentId.LUCKY, TalentId.WIZARD,
    TalentId.DEFENSIVE_STANCE, TalentId.WILD_ATTACK,TalentId.MIGHTY_BLOW,TalentId.HARDY,
    TalentId.RAPID_RELOAD,TalentId.ARMOUR_BANE,TalentId.ALLIES_IN_ARMS,TalentId.BASH_ATTACK,TalentId.ACROBATIC,
    TalentId.BACK_IN_THE_SADDLE,TalentId.BATTLEFIELD_MUSICIAN,
    TalentId.HONOUR_BOUND,TalentId.BLESSINGS_OF_THE_LADY,TalentId.CAREFUL_AIM,TalentId.CLEAVING_BLOW,TalentId.COMBAT_SURGEON,TalentId.DEEP_FORMATION))
NPC_EXECUTABLE_TALENTS = frozenset((TalentId.MAGIC_RESISTANCE,
    TalentId.DEFENSIVE_STANCE, TalentId.WILD_ATTACK,TalentId.MIGHTY_BLOW,TalentId.RAPID_RELOAD,TalentId.ARMOUR_BANE,TalentId.ALLIES_IN_ARMS,TalentId.BASH_ATTACK,TalentId.ACROBATIC,
    TalentId.BACK_IN_THE_SADDLE,TalentId.BATTLEFIELD_MUSICIAN,
    TalentId.HONOUR_BOUND,TalentId.BLESSINGS_OF_THE_LADY,TalentId.CAREFUL_AIM,TalentId.CLEAVING_BLOW,TalentId.COMBAT_SURGEON,TalentId.DEEP_FORMATION))
GENERATED_TALENT_POOL = tuple(talent for talent in (
    TalentId.MAGIC_RESISTANCE,TalentId.DEFENSIVE_STANCE,TalentId.WILD_ATTACK,
    TalentId.MIGHTY_BLOW,TalentId.RAPID_RELOAD,TalentId.ARMOUR_BANE,TalentId.ALLIES_IN_ARMS,TalentId.BASH_ATTACK,TalentId.ACROBATIC,
    TalentId.BACK_IN_THE_SADDLE,TalentId.BATTLEFIELD_MUSICIAN,TalentId.CAREFUL_AIM,TalentId.CLEAVING_BLOW,TalentId.COMBAT_SURGEON,TalentId.DEEP_FORMATION) if talent in NPC_EXECUTABLE_TALENTS)


def talent_facts_for_actor(facts: TalentOwnerFacts | None, *, weapon_skill: int,
        strength: int, toughness: int, agility: int, ballistic_skill: int | None = None,
        initiative: int | None = None, reason: int | None = None,
        fellowship: int | None = None, medical=None) -> TalentOwnerFacts:
    if facts is None:
        facts = TalentOwnerFacts()
    if type(facts) is not TalentOwnerFacts:
        raise TypeError('Talent acquisition requires its exact initial actor facts')
    replace(facts)
    updates = {}
    if medical is not None:
        from towr.domain.medical_preparation_models import MedicalPreparationFacts
        if type(medical) is not MedicalPreparationFacts:
            raise TypeError('medical knowledge requires its actual initial preparation source')
        replace(medical)
        anatomy=next((lore for lore in facts.lores if lore.id=='anatomy'),None)
        if anatomy is not None and (anatomy.magic or not medical.anatomy_lore):
            raise ValueError('actual medical knowledge contradicts the initial Anatomy Lore facts')
        if medical.anatomy_lore and anatomy is None:
            updates['lores']=(*facts.lores,TalentLoreFact('anatomy'))
    for name, actual in (('weapon_skill', weapon_skill), ('strength', strength),
            ('toughness', toughness), ('agility', agility), ('ballistic_skill', ballistic_skill),
            ('initiative', initiative), ('reason', reason), ('fellowship', fellowship)):
        if actual is None:
            continue
        supplied = getattr(facts, name)
        if supplied is not None and supplied != actual:
            raise ValueError('Talent prerequisite facts differ from the initial ' + name)
        updates[name] = actual
    return replace(facts, **updates)


def validate_pc_talent_source(member) -> None:
    ranged = member.pc.ranged
    wizard = member.wizard
    supplied = member.talent_facts
    if wizard is not None:
        supplied = TalentOwnerFacts() if supplied is None else supplied
        if type(supplied) is not TalentOwnerFacts:
            raise TypeError('Wizard acquisition needs its actual typed owner facts')
        origin = TalentOrigin(wizard.origin)
        allowed = ((TalentOrigin.HUMAN,TalentOrigin.EMPIRE_HUMAN,TalentOrigin.BRETONNIAN_HUMAN)
            if origin is TalentOrigin.HUMAN else (origin,))
        if supplied.origin is not None and supplied.origin not in allowed:
            raise ValueError('Wizard and Talent acquisition disagree on actual Origin')
        lores = list(supplied.lores)
        for lore_id in wizard.lores:
            known = next((lore for lore in lores if lore.id == lore_id),None)
            if known is not None and not known.magic:
                raise ValueError('Wizard Magic Lore cannot be classified as ordinary knowledge')
            if known is None:
                lores.append(TalentLoreFact(lore_id,True))
        supplied = replace(supplied,origin=origin if supplied.origin is None else supplied.origin,
            lores=tuple(lores))
    facts = talent_facts_for_actor(supplied,
        weapon_skill=member.pc.weapon_skill, strength=member.pc.strength,
        toughness=member.pc.toughness, agility=member.pc.agility,
        ballistic_skill=member.pc.ballistic_skill if ranged is None else ranged.ballistic_skill,
        initiative=member.pc.initiative,
        reason=member.pc.reason, fellowship=member.pc.fellowship,medical=member.pc.medical)
    validate_acquired_talents(member.talents, facts)
    unsupported = {entry.id for entry in member.talents} - PC_EXECUTABLE_TALENTS
    if unsupported:
        raise ValueError('PC Talent execution is not connected: ' + ', '.join(sorted(t.value for t in unsupported)))
    if member.fate.has_lucky != has_talent(member.talents, TalentId.LUCKY):
        raise ValueError('Lucky funding must match the actual acquired Talent')
    if (wizard is not None) != has_talent(member.talents, TalentId.WIZARD):
        raise ValueError('Wizard Casting source must match the actual acquired Talent')
    if wizard is not None and wizard.wizard_level != talent_purchases(member.talents, TalentId.WIZARD):
        raise ValueError('Wizard Level must equal the number of actual Talent acquisitions')


def validate_generated_talent_source(npc) -> None:
    ranged = npc.ranged
    facts = talent_facts_for_actor(npc.talent_facts,
        weapon_skill=npc.weapon_skill, strength=npc.strength, toughness=npc.toughness,
        agility=npc.agility, ballistic_skill=npc.ballistic_skill if ranged is None else ranged.ballistic_skill,
        initiative=npc.initiative, reason=npc.reason, fellowship=npc.fellowship,medical=npc.medical)
    validate_acquired_talents(npc.talents, facts)
    unsupported = {entry.id for entry in npc.talents} - NPC_EXECUTABLE_TALENTS
    if unsupported:
        raise ValueError('NPC Talent execution is not connected: ' + ', '.join(sorted(t.value for t in unsupported)))


def npc_definition_acquired_talents(definition) -> tuple[AcquiredTalent, ...]:
    """Read the common complete source, including authored Champion profiles."""
    from towr.domain.npc_roster_models import NpcDefinition
    if type(definition) is not NpcDefinition:
        raise TypeError('NPC Talent query requires its exact complete definition')
    replace(definition)
    return definition.talents


def validate_npc_definition_talent_scope(definition, allowed: frozenset[TalentId]) -> None:
    if (definition.generated_components is None and any(talent.id in (
            TalentId.HONOUR_BOUND, TalentId.BLESSINGS_OF_THE_LADY)
            for talent in npc_definition_acquired_talents(definition))):
        raise ValueError('NPC oath Talents require their complete generated source and explicit GM context')
    """Admit a concrete execution owner's effects, not descriptive ownership."""
    if type(allowed) is not frozenset or any(type(value) is not TalentId for value in allowed):
        raise TypeError('NPC Talent execution scope requires an exact frozenset of typed IDs')
    talents = npc_definition_acquired_talents(definition)
    unsupported = {value.id for value in talents} - allowed
    if unsupported:
        raise ValueError('NPC Talent execution is not connected in this owner: '
            + ', '.join(sorted(value.value for value in unsupported)))


def actor_acquired_talents(state, actor_id: str) -> tuple[AcquiredTalent, ...]:
    if actor_id in state.source.pc_activation_order:
        return state.source.participant(actor_id).talents
    if actor_id in state.source.npc_activation_order:
        return npc_definition_acquired_talents(state.enemy(actor_id).definition)
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    return npc_definition_acquired_talents(pc_actor_npc_snapshot(state, actor_id).definition)


def actor_has_talent(state, actor_id: str, talent: TalentId) -> bool:
    return has_talent(actor_acquired_talents(state, actor_id), talent)
