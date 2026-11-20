"""Source-bound departure under the chosen retained-mount GM policy (C11).

A defeated rider is not necessarily dead. Only an actual acknowledged death
or exit receipt sends away this living animal; its HP and Conditions survive.
"""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, replace

from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.pc_companion_models import PcMountCompanionState
from towr.domain.pc_companion_policy_models import DismountedMountPolicy
from towr.domain.pc_mount_retention_models import actor_back_in_saddle_source
from towr.domain.pc_mount_models import PcMountedState
from towr.domain.talent_back_in_saddle_models import BackInSaddleSource
from towr.domain.turn_models import CombatRoundState


COMPANION_DEPARTURE_RULE_ID = 'RULE-MOUNT-001:gm-companion-departure'


def _id(value):
    if type(value) is not str or not value.strip():
        raise TypeError('companion departure requires an exact nonempty source identifier')


def _source_types():
    from towr.domain.pc_melee_result_models import (PcWoundCompletionProof, PcTurnEndProof,
        PcIncapacitatedTurnEndProof, PcProfileWoundProof, PcMinionStaggerDefeatProof)
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
    from towr.domain.pc_blunderbuss_models import PcBlunderbussProfileProof
    from towr.domain.pc_cleaving_blow_models import PcCleavingProfileProof,PcCleavingMinionDefeatProof
    from towr.domain.pc_npc_exit_models import PcNpcExitProof
    from towr.domain.pc_falling_models import PcFallingProof
    from towr.domain.pc_weapon_area_models import PcWeaponHazardProof
    return (PcWoundCompletionProof, PcTurnEndProof, PcIncapacitatedTurnEndProof,
        PcProfileWoundProof, PcMinionStaggerDefeatProof, PcWarpedFormProfileProof,
        PcBlunderbussProfileProof, PcCleavingProfileProof, PcCleavingMinionDefeatProof,
        PcNpcExitProof, PcFallingProof, PcWeaponHazardProof)


def _after_departure_battlefield(previous, actor, *, mounted=False):
    if type(previous) is not PcBattlefieldState:
        raise TypeError('companion departure requires its exact physical battlefield')
    replace(previous)
    present = any(row.entity_id == actor for row in previous.spatial.placements)
    if mounted:
        if present:
            raise ValueError('a mounted body cannot also keep a separate physical placement')
        return previous
    previous.spatial.placement_for(actor)
    spatial = previous.spatial
    return replace(previous, spatial=replace(spatial,
        placements=tuple(row for row in spatial.placements if row.entity_id != actor),
        gave_ground_entity_ids=tuple(value for value in spatial.gave_ground_entity_ids if value != actor),
        free_move_used_entity_ids=tuple(value for value in spatial.free_move_used_entity_ids if value != actor),
        difficult_terrain_tested_entity_ids=tuple(value for value in spatial.difficult_terrain_tested_entity_ids
            if value != actor)), close_pairs=tuple(pair for pair in previous.close_pairs if actor not in pair))


def _after_departure_round(previous, actor):
    if type(previous) is not CombatRoundState or type(previous.round_number) is not int:
        raise TypeError('companion departure requires its exact actual combat clock')
    replace(previous)
    known = tuple(row.entity_id for row in previous.participants)
    if actor not in known or actor in (*previous.completed_turn_entity_ids,*previous.excluded_turn_entity_ids):
        return previous
    # The original participant roster and every already completed turn survive.
    # A still-open body's paid receipts remain in history and in source_round.
    return replace(previous,
        active_turn=None if previous.active_turn is not None and previous.active_turn.actor_id == actor
            else previous.active_turn,
        excluded_turn_entity_ids=(*previous.excluded_turn_entity_ids,actor))


@dataclass(frozen=True, slots=True)
class PcCompanionDepartureProof:
    source: BackInSaddleSource
    history_index: int
    source_history_index: int
    source_proof: object
    source_id: str
    previous: PcMountCompanionState
    state: PcMountCompanionState
    previous_mount: PcMountedState
    mount: PcMountedState
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState
    source_round: CombatRoundState
    round_state: CombatRoundState

    @property
    def actor_id(self):
        return self.source.mount_id

    @property
    def rider_id(self):
        return self.source.actor_id

    @property
    def applied_rule_ids(self):
        return (COMPANION_DEPARTURE_RULE_ID,)

    def __post_init__(self):
        if type(self.source) is not BackInSaddleSource:
            raise TypeError('companion departure requires its actual acquired Back in the Saddle source')
        replace(self.source)
        _id(self.source_id)
        if (type(self.history_index) is not int or type(self.source_history_index) is not int
                or not 0 <= self.source_history_index < self.history_index):
            raise ValueError('companion departure must follow its exact earlier history receipt')
        if type(self.source_proof) not in _source_types():
            raise TypeError('companion departure cannot invent a death or exit proof family')
        replace(self.source_proof)
        for row in (self.previous,self.state):
            if type(row) is not PcMountCompanionState:
                raise TypeError('companion departure requires its complete exact body before and after')
            replace(row)
        for row in (self.previous_mount,self.mount):
            if type(row) is not PcMountedState:
                raise TypeError('companion departure requires its exact actual rider mount witnesses')
            replace(row)
        if (self.previous_mount.actor_id != self.rider_id
                or self.mount != replace(self.previous_mount,mounted=False)):
            raise ValueError('departure must remove only this rider\'s actual mount')
        if (self.previous.rider_id != self.rider_id
                or self.previous.snapshot.state.actor_id != self.actor_id
                or not self.previous_mount.mounted and self.previous.retained_since_round is None
                or injury_is_defeated(self.previous.snapshot.state.injury)
                or self.state != replace(self.previous,retained_since_round=None,stored_spatial_usage=None)):
            raise ValueError('departure must preserve this living ridden/retained body and clear only its local presence')
        if self.battlefield != _after_departure_battlefield(self.previous_battlefield,self.actor_id,
                mounted=self.previous_mount.mounted):
            raise ValueError('departure changed other physical placements, Close links or movement budgets')
        if self.round_state != _after_departure_round(self.source_round,self.actor_id):
            raise ValueError('departure changed another actor, a completed turn or the actual combat clock')
        from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
        validate_pc_melee_source_types(self.state,
            replace(self.previous,retained_since_round=None,stored_spatial_usage=None))
        validate_pc_melee_source_types(self.battlefield,
            _after_departure_battlefield(self.previous_battlefield,self.actor_id,mounted=self.previous_mount.mounted))
        validate_pc_melee_source_types(self.round_state,_after_departure_round(self.source_round,self.actor_id))


def _killed(decision,rider):
    from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
    if decision is None:
        return False
    if type(decision) is not MinionDefeatDecision:
        raise TypeError('confirmed NPC death requires its exact acknowledged disposition')
    replace(decision)
    return decision.target_id == rider and decision.gm_approved and decision.disposition is NpcDefeatDisposition.KILLED


def _cleaving_target(history, acknowledgement):
    """The shared owner binds the exact still-open wave and target receipt."""
    from towr.domain.pc_cleaving_blow_models import cleaving_wave_receipt
    return cleaving_wave_receipt(history, acknowledgement)


def _confirmation(state,rider):
    """Return the precise acknowledged source; raw injury never establishes it."""
    from towr.domain.pc_melee_result_models import (PcWoundCompletionProof,PcTurnEndProof,
        PcIncapacitatedTurnEndProof,PcProfileWoundProof,PcMinionStaggerDefeatProof)
    from towr.domain.pc_npc_distraction_models import _confirmed_death_source
    from towr.domain.pc_npc_exit_models import PcNpcExitProof
    from towr.domain.pc_falling_models import PcFallingProof
    from towr.domain.pc_weapon_area_models import PcWeaponHazardProof
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
    from towr.domain.pc_blunderbuss_models import PcBlunderbussProfileProof,PcBlunderbussTargetProof
    from towr.domain.pc_cleaving_blow_models import PcCleavingProfileProof,PcCleavingMinionDefeatProof
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types,pc_kernel_resolution
    from towr.domain.minion_defeat_models import NpcDefeatDisposition
    injury = pc_actor_injury(state,rider)
    pc = rider in state.source.pc_activation_order
    if type(injury.dead if type(injury) is CharacterInjuryState else injury.defeated) is not bool:
        raise TypeError('departure must retain the exact rider death/defeat boolean')
    dead = injury.dead if type(injury) is CharacterInjuryState else injury.defeated
    for index in range(len(state.history)-1,-1,-1):
        proof = state.history[index]
        if type(proof) is PcNpcExitProof and proof.request.actor_id == rider:
            replace(proof)
            if rider in state.exited_npc_ids:
                return index,proof,proof.request.id
        if type(proof) is PcMinionStaggerDefeatProof and proof.source.target_id == rider and not pc:
            from towr.domain.injury_models import MinionStaggerDefeatOutcome
            replace(proof.source)
            if not dead or proof.source.outcome is not MinionStaggerDefeatOutcome.FLED:
                continue
            attack = next((item for item in reversed(state.history[:index])
                if type(item) in pc_kernel_attack_types()),None)
            result = None if attack is None else pc_kernel_resolution(attack).minion_stagger_defeat
            if (attack is None or attack.request.target_id != rider or result is None
                    or result.cause != proof.source or not result.state.defeated):
                raise ValueError('rider flight lacks its actual acknowledged Attack source')
            from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
            spec = pc_npc_stagger_defeat_spec(state.source.enemy(rider).definition)
            if spec is None or attack.request.kernel_request.minion_stagger_defeat != spec:
                raise ValueError('rider flight lacks its actual printed fleeing source')
            return index,proof,proof.source.source_id
        if type(proof) is PcCleavingMinionDefeatProof and proof.target_id == rider and not pc:
            from towr.domain.injury_models import MinionStaggerDefeatOutcome
            replace(proof.source)
            if not dead or proof.source.outcome is not MinionStaggerDefeatOutcome.FLED:
                continue
            _, target = _cleaving_target(state.history[:index], proof)
            from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
            spec = pc_npc_stagger_defeat_spec(state.source.enemy(rider).definition)
            if (spec is None or target.request.minion_stagger_defeat != spec
                    or not target.result.minion_stagger_defeat.state.defeated):
                raise ValueError('Cleaving rider flight lacks its actual printed fleeing source')
            return index,proof,proof.source.source_id
        if not dead:
            continue
        prefix = state.history[:index+1]
        if type(proof) is PcWoundCompletionProof and pc:
            completion = proof.completion
            replace(completion)
            if (type(completion.state.dead) is not bool
                    or completion.source_request.roll.source_request.target_id != rider or not completion.state.dead):
                continue
            source_id = completion.request_id
        elif type(proof) in (PcTurnEndProof,PcIncapacitatedTurnEndProof) and pc:
            critical = proof.critical
            if critical is None:
                continue
            replace(critical.result)
            if critical.result.source_request.actor_id != rider or not critical.result.state.dead:
                continue
            source_id = proof.result.request_id
        elif type(proof) in (PcProfileWoundProof,PcWarpedFormProfileProof) and not pc:
            replace(proof.source)
            if not proof.source.defeated or not _killed(proof.decision,rider):
                continue
            source_id = _confirmed_death_source(prefix,rider)
            if source_id is None:
                raise ValueError('rider death acknowledgement lacks its actual Attack/wave source')
            if type(proof) is PcProfileWoundProof:
                attack = next(item for item in reversed(state.history[:index])
                    if type(item) in pc_kernel_attack_types())
                from towr.domain.pc_magic_weapon_models import pc_profile_wound_decision
                expected_decision = pc_profile_wound_decision(state,attack)
            else:
                from towr.domain.pc_npc_distraction_models import _wave_receipt
                activation,_ = _wave_receipt(state.history[:index],proof)
                policy = next(policy for policy in state.source.npc_warped_form_policies
                    if policy.actor_id == activation.actor_id)
                expected_decision = next(decision for decision in policy.npc_defeat_decisions
                    if decision.target_id == rider)
            if proof.decision != expected_decision:
                raise ValueError('rider death changed its actual committed defeat disposition')
        elif type(proof) in (PcFallingProof,PcWeaponHazardProof) and not pc:
            if (proof.request.actor_id != rider or proof.npc_disposition is not NpcDefeatDisposition.KILLED
                    or proof.result is None or proof.result.profile_wound is None or not proof.result.state.defeated):
                continue
            if proof.fate_decline is not None or proof.glorious is not None:
                raise ValueError('NPC death cannot invent a PC Fate window')
            if proof.request.target_policy is not state.source.enemy(rider).definition.injury_policy:
                raise ValueError('NPC Hazard death changed its actual source injury policy')
            from towr.domain.pc_falling_models import falling_npc_disposition
            if falling_npc_disposition(state.source,rider) is not NpcDefeatDisposition.KILLED:
                raise ValueError('Hazard departure changed the actual agreed NPC disposition')
            from towr.domain.pc_melee_result_models import _test_result
            _test_result(proof.request.avoidance_test,proof.test)
            if type(proof) is PcFallingProof:
                from towr.domain.pc_falling_models import _canonical_hazard
            else:
                from towr.domain.pc_weapon_area_models import _canonical_hazard
            _canonical_hazard(proof.request,proof.test,proof.result)
            return index,proof,proof.request.id+':defeat'
        elif type(proof) is PcBlunderbussProfileProof and not pc:
            replace(proof)
            if proof.target_id != rider or not proof.source.defeated or not _killed(proof.decision,rider):
                continue
            target = next((item for item in reversed(state.history[:index])
                if type(item) is PcBlunderbussTargetProof and item.resolution_id == proof.resolution_id),None)
            attack = next((item for item in reversed(state.history[:index])
                if type(item) in pc_kernel_attack_types() and item.request.kernel_request.id == proof.resolution_id),None)
            if (target is None or attack is None or target.request.target_id != rider
                    or target.result.profile_wound is None or target.result.profile_wound.state_change != proof.source
                    or proof.decision.attacker_id != attack.request.actor_id):
                raise ValueError('nearby rider death acknowledgement changed its actual shot/target source')
            if (attack.request.actor_id not in state.source.pc_activation_order or proof.decision !=
                    state.source.participant(attack.request.actor_id).defeat_decision(rider)):
                raise ValueError('nearby rider death changed its actual committed disposition')
            return index,proof,proof.resolution_id+':'+rider+':defeat'
        elif type(proof) is PcCleavingProfileProof and not pc:
            replace(proof)
            if proof.target_id != rider or not proof.source.defeated or not _killed(proof.decision,rider):
                continue
            wave, target = _cleaving_target(state.history[:index], proof)
            actor = wave.trigger.actor_id
            if (actor not in state.source.pc_activation_order or proof.decision !=
                    state.source.participant(actor).defeat_decision(rider)
                    or not target.result.profile_wound.state.defeated):
                raise ValueError('Cleaving rider death changed its actual committed disposition')
            return index,proof,proof.wave_id+':'+rider+':defeat'
        else:
            continue
        if _confirmed_death_source(prefix,rider) != source_id:
            raise ValueError('companion departure lacks its confirmed final rider death receipt')
        return index,proof,source_id
    return None


def expected_companion_departure(state):
    scene = state.source.battlefield
    if (scene is None or scene.dismounted_mount_policy is not DismountedMountPolicy.WAIT_AND_RECOVER
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):
        return None
    replace(scene)
    if type(state.companions) is not tuple or type(state.history) is not tuple:
        raise TypeError('companion departure requires exact ordered body/history banks')
    for row in state.companions:
        if type(row) is not PcMountCompanionState:
            raise TypeError('companion departure requires its exact body bank')
        replace(row)
        actor = row.snapshot.state.actor_id
        if (injury_is_defeated(row.snapshot.state.injury) or any(type(proof) is PcCompanionDepartureProof
                and proof.actor_id == actor for proof in state.history)):
            continue
        from towr.domain.pc_companion_effect_models import companion_profile
        companion_profile(state,row.snapshot.state.actor_id)
        mount = next(mount for mount in state.mounts if mount.actor_id == row.rider_id)
        replace(mount)
        if not mount.mounted and row.retained_since_round is None:
            continue
        source = actor_back_in_saddle_source(state,row.rider_id)
        if source is None:
            continue
        confirmation = _confirmation(state,row.rider_id)
        if confirmation is None:
            continue
        index,proof,source_id = confirmation
        return PcCompanionDepartureProof(source,len(state.history),index,proof,source_id,row,
            replace(row,retained_since_round=None,stored_spatial_usage=None),mount,replace(mount,mounted=False),
            state.battlefield,_after_departure_battlefield(state.battlefield,actor,mounted=mount.mounted),state.round_state,
            _after_departure_round(state.round_state,actor))
    return None


def project_companion_departure(state,proof):
    if type(proof) is not PcCompanionDepartureProof:
        raise TypeError('companion departure requires its exact typed proof')
    replace(proof)
    expected = expected_companion_departure(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if expected is None or proof != expected:
        raise ValueError('companion departure changed its actual acquired source, confirmation, body or clock')
    validate_pc_melee_source_types(proof,expected)
    updates = dict(companions=tuple(proof.state if row.rider_id == proof.rider_id else row for row in state.companions),
        mounts=tuple(proof.mount if row.actor_id == proof.rider_id else row for row in state.mounts),
        battlefield=proof.battlefield,round_state=proof.round_state)
    if proof.rider_id in state.source.npc_activation_order:
        from towr.domain.pc_npc_resilience_models import npc_current_resilience
        resilience = npc_current_resilience(state,proof.rider_id,mounted=False)
        updates['enemies'] = tuple(replace(row,state=replace(row.state,current_resilience=resilience))
            if row.state.actor_id == proof.rider_id else row for row in state.enemies)
    return updates
