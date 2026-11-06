"""Typed NPC Distracted sources and confirmed-focus-death expiry (M42/M43)."""
from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileStateChangeRequest
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.pc_npc_wound_models import _first_wound
from towr.domain.test_models import DiceModifier
from towr.domain.pc_npc_grudge_models import (PcNpcGrudgeDistractionSource,PcNpcGrudgeEncounterProof,
    grudge_distraction_from_encounter,expected_pc_npc_grudge_encounter)
from towr.domain.pc_npc_grudge_policy_models import MINER_DEFINITION_ID


BREWGUARD_DEFINITION_ID = 'pc-book-npc:dwarf_brewguard_warhammer'
BREWGUARD_DISTRACTED_RULE_ID = 'RULE-PROFILE-PEOPLES-003:first-wound-distracted'
DISTRACTED_TEST_RULE_ID = 'RULE-HEALTH-008:distracted'


@dataclass(frozen=True,slots=True)
class PcNpcDistractionSource:
    """Brewguard's actual first-Wound attacker source, distinct from an encounter."""

    actor_id: str
    focus_actor_id: str
    attack_id: str
    profile_change: ProfileStateChangeRequest

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in
                (self.actor_id,self.focus_actor_id,self.attack_id)):
            raise TypeError('NPC distraction requires exact nonempty source/focus IDs')
        if self.actor_id==self.focus_actor_id or not _first_wound(self.profile_change):
            raise ValueError('NPC distraction requires another attacker and exact first Brute Wound')


@dataclass(frozen=True,slots=True)
class PcNpcDistractionExpiredProof:
    source: PcNpcDistractionSource | PcNpcGrudgeDistractionSource
    death_source_id: str

    def __post_init__(self):
        if type(self.source) not in (PcNpcDistractionSource,PcNpcGrudgeDistractionSource):
            raise TypeError('distraction expiry requires its exact typed source')
        replace(self.source)
        if type(self.death_source_id) is not str or not self.death_source_id.strip():
            raise TypeError('distraction expiry requires its confirmed death source')


def distraction_from_profile_wound(source,attack,change):
    """Source IDs supplement the actual Attack/profile receipt, never replace it."""
    enemy=source.enemy(attack.request.target_id)
    if enemy.definition.id!=BREWGUARD_DEFINITION_ID or not _first_wound(change):
        return None
    validate_pc_book_npc_definition(enemy.definition)
    result=attack.execution.resolution.profile_wound
    if (attack.request.actor_id not in source.pc_activation_order or result is None
            or result.state_change!=change or attack.execution.target_id!=enemy.state.actor_id):
        raise ValueError('Brewguard distraction requires its actual attacker/profile Wound')
    return PcNpcDistractionSource(enemy.state.actor_id,attack.request.actor_id,
        attack.execution.request_id,change)


def ordered_npc_distractions(source,causes):
    actors={enemy.state.actor_id for enemy in source.enemies}
    if any(cause.actor_id not in actors or cause.focus_actor_id not in source.pc_activation_order for cause in causes):
        raise ValueError('NPC distraction source/focus must belong to the complete scenario')
    by_actor={cause.actor_id:cause for cause in causes}
    if len(by_actor)!=len(causes):
        raise ValueError('an NPC cannot own several simultaneous distraction sources')
    return tuple(by_actor[enemy.state.actor_id] for enemy in source.enemies
        if enemy.state.actor_id in by_actor)


def _confirmed_death_source(history,actor):
    from towr.domain.pc_melee_result_models import (
        PcWoundCompletionProof,PcTurnEndProof,PcIncapacitatedTurnEndProof,
    )
    for proof in reversed(history):
        if (type(proof) is PcWoundCompletionProof and proof.completion.state.dead
                and proof.completion.source_request.roll.source_request.target_id==actor):
            return proof.completion.request_id
        if (type(proof) in (PcTurnEndProof,PcIncapacitatedTurnEndProof)
                and proof.critical is not None and proof.critical.result.state.dead
                and proof.critical.result.source_request.actor_id==actor):
            return proof.result.request_id
    return None


def expected_pc_npc_distraction_expiry(state):
    """Wait for the real Wound/Fate queue; raw lethal injury is not a death proof."""
    if state.pending or state.pending_wound is not None:
        return None
    for cause in state.npc_distractions:
        if not state.participant(cause.focus_actor_id).injury.dead:
            continue
        source_id=_confirmed_death_source(state.history,cause.focus_actor_id)
        if source_id is None:
            raise ValueError('focus death must belong to this completed journal prefix')
        return PcNpcDistractionExpiredProof(cause,source_id)
    return None


def pc_npc_distraction_test_modifiers(state,actor_id,target_id):
    if expected_pc_npc_grudge_encounter(state) is not None:
        raise ValueError('grudge encounter must precede Test preparation')
    if expected_pc_npc_distraction_expiry(state) is not None:
        raise ValueError('confirmed focus death must expire Distracted before Test preparation')
    cause=next((cause for cause in state.npc_distractions if cause.actor_id==actor_id),None)
    if cause is None or cause.focus_actor_id==target_id:
        return ()
    return (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),)


def validate_pc_npc_distractions(state):
    from towr.domain.pc_melee_result_models import PcAttackProof,PcProfileWoundProof
    if type(state.npc_distractions) is not tuple:
        raise TypeError('NPC distraction bank must be an exact tuple')
    supported=(BREWGUARD_DEFINITION_ID,MINER_DEFINITION_ID)
    if not any(enemy.definition.id in supported for enemy in state.enemies):
        if state.npc_distractions:
            raise ValueError('no admitted book source can own these distractions')
        return
    expected=[]
    attack=None
    encountered=[]
    selected={policy.actor_id for policy in state.source.npc_grudge_policies}
    encounter_order=tuple(enemy.state.actor_id for enemy in state.source.enemies if enemy.state.actor_id in selected)
    ordinary_started=False
    for index,proof in enumerate(state.history):
        if type(proof) is PcNpcGrudgeEncounterProof:
            if ordinary_started:
                raise ValueError('grudge encounter cannot be deferred into an ordinary combat phase')
            cause=grudge_distraction_from_encounter(state.source,proof)
            encountered.append(cause.actor_id)
            if tuple(encountered)!=encounter_order[:len(encountered)]:
                raise ValueError('grudge encounter changed its source order or was applied twice')
            expected.append(cause)
            continue
        if not ordinary_started and tuple(encountered)!=encounter_order:
            raise ValueError('ordinary combat cannot skip selected grudge encounters')
        ordinary_started=True
        if type(proof) is PcAttackProof:
            attack=proof
        elif type(proof) is PcProfileWoundProof:
            if attack is None:
                raise ValueError('profile ACK has no source Attack')
            cause=distraction_from_profile_wound(state.source,attack,proof.source)
            if cause is not None:
                expected.append(cause)
        elif type(proof) is PcNpcDistractionExpiredProof:
            replace(proof)
            if (proof.source not in expected or proof.death_source_id!=
                    _confirmed_death_source(state.history[:index],proof.source.focus_actor_id)):
                raise ValueError('distraction expiry is detached, duplicated or lacks confirmed death')
            expected.remove(proof.source)
    expected=ordered_npc_distractions(state.source,expected)
    if state.npc_distractions!=expected:
        raise ValueError('NPC distraction bank changed its actual Wound/expiry history')
    for cause in state.npc_distractions:
        if type(cause) not in (PcNpcDistractionSource,PcNpcGrudgeDistractionSource):
            raise TypeError('NPC distraction bank requires exact typed sources')
        replace(cause)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    validate_pc_melee_source_types(state.npc_distractions,expected)
    actors={cause.actor_id for cause in expected}
    for enemy in state.enemies:
        if (enemy.definition.id in supported
                and enemy.state.injury.conditions.has(Condition.DISTRACTED)!=(enemy.state.actor_id in actors)):
            raise ValueError('NPC Distracted flag differs from its source/focus bank')
