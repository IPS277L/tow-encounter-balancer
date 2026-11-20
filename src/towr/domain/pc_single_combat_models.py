"""Explicit GM-confirmed single-combat source, ADR-0140D."""
from towr.domain.pc_demigryph_models import pc_kernel_attack_types
from dataclasses import dataclass


@dataclass(frozen=True,slots=True)
class PcSingleCombatPair:
    actor_id: str
    target_id: str

    def __post_init__(self):
        for name in ('actor_id','target_id'):
            value=getattr(self,name)
            if type(value) is not str or not value.strip():
                raise TypeError('single combat needs exact nonempty actor identifiers')
        if self.actor_id==self.target_id:
            raise ValueError('single combat requires two different actors')


def single_combat_active(state,actor,target):
    """Observe a complete isolated duel or an uninterrupted explicit GM pair."""
    from towr.domain.pc_actor_models import pc_active_actor_ids
    live=set(pc_active_actor_ids(state))
    pair={actor,target}
    if not pair<=live:
        return False
    from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof,PcNpcHelpProof,PcRecoverProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    from towr.domain.pc_magic_models import PcCastingProof
    from towr.domain.pc_warped_form_models import PcWarpedFormActivationProof
    explicit=any({fact.actor_id,fact.target_id}==pair for fact in state.source.single_combat_pairs)
    if not explicit:
        if len(live)!=2 or state.pending or state.pending_wound is not None or state.magic_pending is not None:
            return False
        # A helper's death does not erase its already committed future Test
        # bonus. Do not label that still-funded attack an isolated duel.
        tested=set()
        for proof in state.history:
            if type(proof) in pc_kernel_attack_types():
                attack=proof.request.kernel_request.attack
                tested.add(attack.attacker_test.id)
                if attack.defender_test is not None:
                    tested.add(attack.defender_test.id)
        for proof in state.history:
            if type(proof) not in (PcHelpProof,PcNpcHelpProof):
                continue
            bonus=proof.execution.bonus
            if (proof.request.actor_id not in pair and bonus.beneficiary_id in pair
                    and bonus.beneficiary_test_id.startswith(
                        f'{state.source.id}:r{state.round_state.round_number}:')
                    and bonus.beneficiary_test_id not in tested):
                return False
        return True
    for proof in state.history:
        if type(proof) in pc_kernel_attack_types():
            actors={proof.request.actor_id,proof.request.target_id}
            if actors&pair and not actors<=pair:
                return False
            area=getattr(proof,'weapon_area',None)
            if area is not None:
                actors={proof.request.actor_id,*area.target_ids}
                if actors&pair and not actors<=pair:
                    return False
            nearby=getattr(proof,'nearby_snapshot',None)
            if nearby is not None:
                # A real nearby wave is external intervention even if the
                # primary opposed Test happened within the declared pair.
                actors={proof.request.actor_id,*nearby.cluster.target_ids}
                if actors&pair and not actors<=pair:
                    return False
        elif type(proof) in (PcHelpProof,PcNpcHelpProof):
            if {proof.request.actor_id,proof.request.beneficiary_id}&pair:
                return False
        elif type(proof) is PcRecoverProof:
            actors={proof.result.source_request.actor_id,*[
                change.entity_id for change in proof.result.resolution.condition_changes]}
            if actors&pair and not actors<=pair:
                return False
        elif type(proof) is PcCastingProof and proof.targets is not None:
            actors={proof.actor_id,*[victim.target_id for victim in proof.targets.targets]}
            if actors&pair and not actors<=pair:
                return False
        elif type(proof) is PcWarpedFormActivationProof:
            actors={proof.actor_id,*proof.target_ids}
            if actors&pair and not actors<=pair:
                return False
    return True
