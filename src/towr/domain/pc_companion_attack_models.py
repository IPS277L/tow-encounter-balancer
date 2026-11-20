"""Authenticate a retained NPC body's ordinary physical Attack continuation.

An allied profile NPC is never a PC Fate owner. The actual kernel journal and
its consumed acknowledgements identify the pending body (or missed attacker).
"""
from towr.domain.attack_models import AttackOutcome
from towr.domain.pc_actor_models import pc_companion
from towr.domain.pc_demigryph_models import pc_kernel_attack_types, pc_kernel_resolution


def kernel_condition_actor(state, attack):
    """Natural mount Tests use that body's Conditions, with the rider's slot."""
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    from towr.domain.pc_companion_models import mount_companion_actor_id
    if type(attack) not in pc_kernel_attack_types():
        raise TypeError('attack Condition owner requires its exact physical kernel receipt')
    actor = attack.request.actor_id
    if type(attack) is PcDemigryphStrikeProof or getattr(attack, 'mount_attack', None) is not None:
        body = mount_companion_actor_id(actor)
        if pc_companion(state, body) is None:
            raise ValueError('natural mount Test lacks its actual source body')
        return body
    return actor


def companion_attack_pending_owner(state):
    if not state.pending or state.pending_wound is not None:
        return None
    actual = next(((index, proof) for index, proof in reversed(tuple(enumerate(state.history)))
        if type(proof) in pc_kernel_attack_types()), None)
    if actual is None:
        return None
    index, attack = actual
    target = attack.request.target_id
    result = pc_kernel_resolution(attack)
    owner = target if result.attack.outcome is AttackOutcome.HIT else kernel_condition_actor(state, attack)
    if pc_companion(state, target) is None and pc_companion(state, owner) is None:
        return None
    if owner != state.pending_actor_id:
        return None
    from towr.domain.pc_melee_result_models import PcAttackerStaggerProof, PcProfileWoundProof, PcMinionStaggerDefeatProof
    queue = result.follow_ups
    for proof in state.history[index+1:]:
        if type(proof) in (PcAttackerStaggerProof, PcProfileWoundProof, PcMinionStaggerDefeatProof):
            if not queue or proof.source != queue[0]:
                return None
            queue = queue[1:]
    return owner if state.pending == queue else None
