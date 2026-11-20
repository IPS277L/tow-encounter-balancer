"""Immutable initial mount bodies and source checks for the companion bank.

Mounted bodies are inactive NPC snapshots. They retain their own physical
source; creating this bank grants no retention, target, turn, Recover or Fate.
"""
from dataclasses import replace

from towr.domain.pc_companion_models import PcMountCompanionState,mount_companion_actor_id
from towr.domain.pc_mount_companion_sources import initial_mount_companion_snapshot
from towr.domain.pc_mount_models import initial_pc_mounts
from towr.domain.turn_models import CombatSide


def initial_pc_companions(source):
    mounts=initial_pc_mounts(source)
    if not mounts:return ()
    actors=(*source.pc_activation_order,*source.npc_activation_order)
    rows=[]
    for mount in mounts:
        rider=mount.actor_id
        actor=mount_companion_actor_id(rider)
        if actor in actors:
            raise ValueError('a mount companion identity collides with an initial participant')
        if rider in source.pc_activation_order:
            member=source.participant(rider)
            barding=member.armour is not None and member.armour.barding
            side=CombatSide.PLAYERS_AND_ALLIES
        else:
            member=source.enemy(rider).definition.generated_components
            barding=member.armour.barding
            side=CombatSide.OPPOSITION
        snapshot=initial_mount_companion_snapshot(actor,side,mount.mount,barding=barding)
        rows.append(PcMountCompanionState(rider,snapshot))
    if len({row.snapshot.state.actor_id for row in rows})!=len(rows):
        raise ValueError('mount companion identities must be unique')
    return tuple(rows)


def validate_pc_companions(state):
    rows=state.companions
    if type(rows) is not tuple or any(type(row) is not PcMountCompanionState for row in rows):
        raise TypeError('mount companion bank requires its exact source-ordered tuple')
    initial=initial_pc_companions(state.source)
    if tuple(row.rider_id for row in rows)!=tuple(row.rider_id for row in initial):
        raise ValueError('mount companion bank changed its complete initial source order')
    from towr.domain.pc_mount_retention_models import PcMountRetentionProof
    retained = {row.rider_id: None for row in initial}
    stored_usage = {row.rider_id: None for row in initial}
    departed = set()
    for index, proof in enumerate(state.history):
        from towr.domain.pc_companion_departure_models import PcCompanionDepartureProof
        if type(proof) is PcCompanionDepartureProof:
            replace(proof)
            from towr.domain.pc_mount_retention_models import actor_back_in_saddle_source
            if (index != proof.history_index or proof.rider_id not in retained or proof.rider_id in departed
                    or proof.source != actor_back_in_saddle_source(state,proof.rider_id)
                    or proof.source_history_index >= index
                    or proof.source_proof != state.history[proof.source_history_index]
                    or proof.previous.retained_since_round != retained[proof.rider_id]):
                raise ValueError('companion departure lost its actual body or confirmed rider prefix')
            retained[proof.rider_id]=None
            stored_usage[proof.rider_id]=None
            departed.add(proof.rider_id)
            continue
        from towr.domain.pc_back_in_saddle_models import BACK_IN_SADDLE_REMOUNT_PROOFS,PcBackInSaddleRecoverProof,_recover_receipt
        if type(proof) in BACK_IN_SADDLE_REMOUNT_PROOFS:
            replace(proof)
            if (index != proof.history_index or proof.actor_id not in retained or proof.actor_id in departed
                    or retained[proof.actor_id] != proof.previous_body.retained_since_round):
                raise ValueError('remount body lacks its actual retained companion prefix')
            from towr.domain.pc_mount_retention_models import actor_back_in_saddle_source
            if proof.source != actor_back_in_saddle_source(state, proof.actor_id):
                raise ValueError('remount changed its actual acquired Talent source')
            if type(proof) is PcBackInSaddleRecoverProof and (index == 0
                    or proof.recovery != _recover_receipt(state.history[index - 1])):
                raise ValueError('Recover remount lacks its actual preceding paid action')
            retained[proof.actor_id] = None
            stored_usage[proof.actor_id] = proof.body.stored_spatial_usage
            continue
        if type(proof) is not PcMountRetentionProof:
            continue
        replace(proof)
        if (index != proof.history_index or index == 0
                or proof.source_dismount != state.history[index - 1]
                or proof.source.actor_id not in retained or proof.source.actor_id in departed
                or retained[proof.source.actor_id] is not None):
            raise ValueError('retained mount lacks its one actual dismount history prefix')
        from towr.domain.pc_mount_retention_models import actor_back_in_saddle_source
        if proof.source != actor_back_in_saddle_source(state, proof.source.actor_id):
            raise ValueError('retained mount changed its actual acquired Talent source')
        retained[proof.source.actor_id] = proof.round_number
    for row,original in zip(rows,initial,strict=True):
        replace(row)
        actual,expected=row.snapshot,original.snapshot
        from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
        validate_pc_melee_source_types(actual.definition,expected.definition)
        if (actual.definition!=expected.definition or actual.state.actor_id!=expected.state.actor_id
                or actual.state.side is not expected.state.side):
            raise ValueError('mount companion changed its physical source, identity or side')
        from towr.domain.pc_npc_resilience_models import npc_current_resilience
        if actual.state.current_resilience != npc_current_resilience(state, actual.state.actor_id):
            raise ValueError('mount companion Resilience differs from its own equipment and actual losses')
        if row.retained_since_round != retained[row.rider_id]:
            raise ValueError('mount companion retention differs from its actual history')
        if row.stored_spatial_usage != stored_usage[row.rider_id]:
            raise ValueError('mount companion lost or changed its stored actual movement budgets')
        if row.retained_since_round is not None:
            if row.retained_since_round>state.round_state.round_number:
                raise ValueError('mount companion cannot retain from a future round')
            mount=next(mount for mount in state.mounts if mount.actor_id==row.rider_id)
            if mount.mounted:
                raise ValueError('a ridden mount cannot also be an active detached companion')
