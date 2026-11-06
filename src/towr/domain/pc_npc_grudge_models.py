"""One encounter application for an explicitly declared Miner grudge."""
from dataclasses import dataclass,replace

from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.pc_npc_grudge_policy_models import (
    MINER_DEFINITION_ID,GRUDGES_TO_SETTLE_RULE_ID,PcNpcGrudgePolicy,
)
from towr.domain.test_models import DiceModifier


@dataclass(frozen=True,slots=True)
class PcNpcGrudgeDistractionSource:
    actor_id: str
    focus_actor_id: str
    encounter_id: str

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in
                (self.actor_id,self.focus_actor_id,self.encounter_id)):
            raise TypeError('grudge distraction requires exact source/focus IDs')
        if self.actor_id==self.focus_actor_id:
            raise ValueError('Miner grudge requires another enemy')


@dataclass(frozen=True,slots=True)
class PcNpcGrudgeEncounterProof:
    request_id: str
    policy: PcNpcGrudgePolicy

    def __post_init__(self):
        if type(self.request_id) is not str or not self.request_id.strip():
            raise TypeError('grudge encounter requires its exact request ID')
        if type(self.policy) is not PcNpcGrudgePolicy:
            raise TypeError('grudge encounter requires its exact source policy')
        replace(self.policy)


def grudge_distraction_from_encounter(source,proof):
    replace(proof)
    if proof.policy not in source.npc_grudge_policies:
        raise ValueError('grudge encounter does not belong to this complete source')
    enemy=source.enemy(proof.policy.actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if (enemy.definition.id!=MINER_DEFINITION_ID
            or proof.policy.focus_actor_id not in source.pc_activation_order
            or proof.request_id!=source.id+':grudge-encounter:'+proof.policy.actor_id):
        raise ValueError('grudge encounter changed its canonical Miner/focus/source ID')
    return PcNpcGrudgeDistractionSource(proof.policy.actor_id,proof.policy.focus_actor_id,proof.request_id)


def expected_pc_npc_grudge_encounter(state):
    """One deterministic source-roster queue, before the first combat turn."""
    if not state.source.npc_grudge_policies:
        return None
    applied={proof.policy.actor_id for proof in state.history if type(proof) is PcNpcGrudgeEncounterProof}
    policies={policy.actor_id:policy for policy in state.source.npc_grudge_policies}
    for enemy in state.source.enemies:
        actor=enemy.state.actor_id
        if actor not in policies or actor in applied:
            continue
        clock=state.round_state
        if (clock.round_number!=1 or clock.active_turn is not None or clock.completed_turn_entity_ids
                or clock.excluded_turn_entity_ids
                or any(type(proof) is not PcNpcGrudgeEncounterProof for proof in state.history)):
            raise ValueError('grudge encounter must precede the first ordinary combat phase')
        return PcNpcGrudgeEncounterProof(state.source.id+':grudge-encounter:'+actor,policies[actor])
    return None


def pc_npc_grudge_melee_modifiers(state,actor_id,target_id):
    """A relationship grants Melee dice, independently of current Distracted."""
    policy=next((policy for policy in state.source.npc_grudge_policies if policy.actor_id==actor_id),None)
    if policy is None or policy.focus_actor_id!=target_id:
        return ()
    enemy=state.enemy(actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id!=MINER_DEFINITION_ID:
        raise ValueError('grudge Melee bonus requires its canonical Miner')
    if state.participant(target_id).injury.dead:
        return ()
    return (DiceModifier(GRUDGES_TO_SETTLE_RULE_ID,1),)
