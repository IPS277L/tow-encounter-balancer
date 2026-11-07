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
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition


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
class PcNpcWaveDistractionSource:
    """Brewguard W1 caused by a real non-Attack Warped Form wave."""

    actor_id: str
    focus_actor_id: str
    wave_id: str
    profile_change: ProfileStateChangeRequest

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in
                (self.actor_id,self.focus_actor_id,self.wave_id)):
            raise TypeError('wave distraction requires exact nonempty source/focus IDs')
        if self.actor_id==self.focus_actor_id or not _first_wound(self.profile_change):
            raise ValueError('wave distraction requires another causer and exact first Brute Wound')
        replace(self.profile_change)


@dataclass(frozen=True,slots=True)
class PcNpcDistractionExpiredProof:
    source: PcNpcDistractionSource | PcNpcGrudgeDistractionSource | PcNpcWaveDistractionSource
    death_source_id: str

    def __post_init__(self):
        if type(self.source) not in (PcNpcDistractionSource,PcNpcGrudgeDistractionSource,PcNpcWaveDistractionSource):
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


def wave_distraction_from_profile_wound(source,activation,ack):
    """Called only for the actual target-scoped wave profile acknowledgement."""
    from towr.domain.pc_warped_form_models import PcWarpedFormActivationProof,PcWarpedFormProfileProof
    if type(activation) is not PcWarpedFormActivationProof or type(ack) is not PcWarpedFormProfileProof:
        raise TypeError('wave distraction requires exact activation and profile proofs')
    replace(activation)
    replace(ack)
    enemy=source.enemy(ack.target_id)
    if enemy.definition.id!=BREWGUARD_DEFINITION_ID or not _first_wound(ack.source):
        return None
    validate_pc_book_npc_definition(enemy.definition)
    causer=source.enemy(activation.actor_id)
    validate_pc_book_npc_definition(causer.definition)
    if (causer.definition.id!='pc-book-npc:skin_wolf' or ack.activation_id!=activation.activation_id
            or ack.target_id not in activation.target_ids or ack.decision is not None):
        raise ValueError('Brewguard wave distraction changed its actual causer or first Wound')
    return PcNpcWaveDistractionSource(ack.target_id,activation.actor_id,activation.activation_id,ack.source)


def _wave_receipt(history,ack):
    """Find the real activation/target receipt immediately preceding this ACK."""
    from towr.domain.pc_warped_form_models import (
        PcWarpedFormActivationProof,PcWarpedFormTargetProof,PcWarpedFormProfileProof,PcWarpedFormEndProof,
    )
    if type(ack) is not PcWarpedFormProfileProof:
        raise TypeError('wave profile source requires its exact acknowledgement')
    replace(ack)
    activation=None
    target=None
    acknowledged=False
    for proof in history:
        if type(proof) is PcWarpedFormActivationProof:
            activation=proof
            target=None
            acknowledged=False
        elif type(proof) is PcWarpedFormTargetProof:
            target=proof
            acknowledged=False
        elif type(proof) is PcWarpedFormProfileProof:
            acknowledged=True
        elif type(proof) is PcWarpedFormEndProof:
            activation=None
            target=None
    if (activation is None or target is None or acknowledged
            or ack.activation_id!=activation.activation_id or target.activation_id!=activation.activation_id
            or target.request.target_id!=ack.target_id or ack.target_id not in activation.target_ids
            or target.result.profile_wound is None or target.result.profile_wound.state_change!=ack.source):
        raise ValueError('wave profile ACK lacks its actual activation/target/Wound receipt')
    replace(activation)
    replace(target)
    return activation,target


def ordered_npc_distractions(source,causes):
    actors={enemy.state.actor_id for enemy in source.enemies}
    for cause in causes:
        if type(cause) not in (PcNpcDistractionSource,PcNpcGrudgeDistractionSource,PcNpcWaveDistractionSource):
            raise TypeError('NPC distraction requires an exact typed cause')
        replace(cause)
        focus_ids=actors if type(cause) is PcNpcWaveDistractionSource else source.pc_activation_order
        if cause.actor_id not in actors or cause.focus_actor_id not in focus_ids:
            raise ValueError('NPC distraction source/focus must belong to the complete scenario')
    by_actor={cause.actor_id:cause for cause in causes}
    if len(by_actor)!=len(causes):
        raise ValueError('an NPC cannot own several simultaneous distraction sources')
    return tuple(by_actor[enemy.state.actor_id] for enemy in source.enemies
        if enemy.state.actor_id in by_actor)


def _confirmed_death_source(history,actor):
    from towr.domain.pc_melee_result_models import (
        PcWoundCompletionProof,PcTurnEndProof,PcIncapacitatedTurnEndProof,PcProfileWoundProof,PcAttackProof,
    )
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
    for index in range(len(history)-1,-1,-1):
        proof=history[index]
        if type(proof) in (PcProfileWoundProof,PcWarpedFormProfileProof):
            decision=proof.decision
            if (type(decision) is not MinionDefeatDecision or decision.target_id!=actor
                    or not proof.source.defeated or decision.disposition is not NpcDefeatDisposition.KILLED
                    or type(decision.gm_approved) is not bool or not decision.gm_approved):
                continue
            replace(decision)
            if type(proof) is PcWarpedFormProfileProof:
                activation,target=_wave_receipt(history[:index],proof)
                if decision.attacker_id!=activation.actor_id or proof.target_id!=actor:
                    raise ValueError('NPC focus death has a detached wave disposition')
                return activation.activation_id+':'+actor+':defeat'
            attack=next((item for item in reversed(history[:index]) if type(item) is PcAttackProof),None)
            if (attack is None or attack.request.actor_id!=decision.attacker_id
                    or attack.request.target_id!=actor or attack.execution.resolution.profile_wound is None
                    or attack.execution.resolution.profile_wound.state_change!=proof.source):
                raise ValueError('NPC focus death has a detached Attack disposition')
            return attack.execution.request_id+':defeat'

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
        if type(cause) is PcNpcWaveDistractionSource:
            # Defeat alone does not establish death: surrendered/knocked out lives.
            source_id=_confirmed_death_source(state.history,cause.focus_actor_id)
            if source_id is None:
                continue
            if not state.enemy(cause.focus_actor_id).state.injury.defeated:
                raise ValueError('NPC focus death proof disagrees with its actual injury')
        else:
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
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
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
        elif type(proof) is PcWarpedFormProfileProof:
            activation,_=_wave_receipt(state.history[:index],proof)
            cause=wave_distraction_from_profile_wound(state.source,activation,proof)
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
        if type(cause) not in (PcNpcDistractionSource,PcNpcGrudgeDistractionSource,PcNpcWaveDistractionSource):
            raise TypeError('NPC distraction bank requires exact typed sources')
        replace(cause)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    validate_pc_melee_source_types(state.npc_distractions,expected)
    actors={cause.actor_id for cause in expected}
    for enemy in state.enemies:
        if (enemy.definition.id in supported
                and enemy.state.injury.conditions.has(Condition.DISTRACTED)!=(enemy.state.actor_id in actors)):
            raise ValueError('NPC Distracted flag differs from its source/focus bank')
