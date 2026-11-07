"""Source-bound Bestigor choices and one next-Attack entitlement from actual W1."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileNpcType, ProfileStateChangeRequest
from towr.domain.pc_npc_blood_rage_policy_models import (
    BESTIGOR_DEFINITION_ID, SKIN_WOLF_DEFINITION_ID, BESTIGOR_WOUND_GLORIOUS_RULE_ID,
)
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import QualityModifier, TestQuality
from towr.domain.turn_models import CombatActionKind


@dataclass(frozen=True, slots=True)
class PcNpcBloodRageProof:
    actor_id: str
    action_id: str

    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in (self.actor_id, self.action_id)):
            raise TypeError('Blood Rage requires exact actor and Attack action IDs')


@dataclass(frozen=True, slots=True)
class PcBestigorGloriousSource:
    actor_id: str
    wound_attack_id: str
    profile_change: ProfileStateChangeRequest

    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in (self.actor_id, self.wound_attack_id)):
            raise TypeError('Bestigor Glorious requires exact actor and Wounding Attack IDs')
        change = self.profile_change
        if type(change) is not ProfileStateChangeRequest:
            raise TypeError('Bestigor Glorious requires its actual profile change')
        replace(change)
        if (type(change.npc_type) is not ProfileNpcType or change.npc_type is not ProfileNpcType.BRUTE
                or type(change.previous_wounds) is not int or change.previous_wounds != 0
                or type(change.current_wounds) is not int or change.current_wounds != 1
                or type(change.defeated) is not bool or change.defeated):
            raise ValueError('Bestigor Glorious requires the living Brute0-to-1 change')


@dataclass(frozen=True, slots=True)
class PcBestigorWaveGloriousSource:
    """One next-Attack entitlement from an actual non-Attack wave W1."""

    actor_id: str
    wave_id: str
    profile_change: ProfileStateChangeRequest

    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in (self.actor_id,self.wave_id)):
            raise TypeError('Bestigor wave Glorious requires exact actor and wave IDs')
        from towr.domain.pc_npc_wound_models import _first_wound
        if not _first_wound(self.profile_change):
            raise ValueError('Bestigor wave Glorious requires its living Brute0-to-1 change')
        replace(self.profile_change)


def expected_pc_npc_blood_rage(state):
    """Only a selected actor's reserved, unexecuted Attack may acquire Staggered."""
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.npc_blood_rage_actor_ids
            or state.pending or state.pending_wound is not None or not turn.action_slots
            or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK
            or not state.live_party):
        return None
    enemy = state.enemy(turn.actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id not in (BESTIGOR_DEFINITION_ID,SKIN_WOLF_DEFINITION_ID):
        raise ValueError('Blood Rage choice requires its canonical Bestigor or Skin Wolf')
    if enemy.state.injury.defeated or enemy.state.injury.conditions.has(Condition.STAGGERED):
        return None
    return PcNpcBloodRageProof(turn.actor_id, pc_melee_action_id(state, turn.actor_id))


def pc_bestigor_glorious_source(state, actor_id):
    """Replay the ACK/Attack prefix; remaining W1 alone never grants a new charge."""
    from towr.domain.pc_melee_result_models import PcAttackProof, PcProfileWoundProof
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
    if actor_id not in state.source.enemy_activation_order:
        return None
    enemy = state.enemy(actor_id)
    if enemy.definition.id != BESTIGOR_DEFINITION_ID:
        return None
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.state.injury.defeated:
        return None
    last_attack = None
    entitlement = None
    for index,proof in enumerate(state.history):
        if type(proof) is PcAttackProof:
            last_attack = proof
            if proof.request.actor_id == actor_id:
                entitlement = None
        elif (type(proof) is PcProfileWoundProof and last_attack is not None
                and last_attack.request.target_id == actor_id
                and proof.source.previous_wounds == 0 and proof.source.current_wounds == 1):
            wound = last_attack.execution.resolution.profile_wound
            if wound is None or proof.source != wound.state_change:
                raise ValueError('Bestigor Glorious detached from its actual profile-Wound ACK')
            entitlement = PcBestigorGloriousSource(actor_id, last_attack.request.id, proof.source)
        elif (type(proof) is PcWarpedFormProfileProof and proof.target_id==actor_id
                and proof.source.previous_wounds==0 and proof.source.current_wounds==1):
            from towr.domain.pc_npc_distraction_models import _wave_receipt
            activation,_=_wave_receipt(state.history[:index],proof)
            if proof.decision is not None:
                raise ValueError('living Bestigor W1 cannot carry a defeat disposition')
            entitlement=PcBestigorWaveGloriousSource(actor_id,activation.activation_id,proof.source)
    return entitlement


def pc_bestigor_attack_quality(state, actor_id):
    if pc_bestigor_glorious_source(state, actor_id) is None:
        return ()
    return (QualityModifier(BESTIGOR_WOUND_GLORIOUS_RULE_ID, TestQuality.GLORIOUS),)
