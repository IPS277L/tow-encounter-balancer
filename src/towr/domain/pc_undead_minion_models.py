"""Admit the Undead Minion packet only from a real mount component (GM168)."""
from towr.domain.pc_actor_models import pc_companion
from towr.domain.pc_mount_models import CombatMount
from towr.domain.undead_minion_models import UndeadMinionSource


def pc_undead_minion_source(state, actor):
    row = pc_companion(state, actor)
    if row is None:
        return None
    mount = next(mount for mount in state.mounts if mount.actor_id == row.rider_id)
    return UndeadMinionSource(actor) if mount.mount is CombatMount.SKELETAL_STEED else None
