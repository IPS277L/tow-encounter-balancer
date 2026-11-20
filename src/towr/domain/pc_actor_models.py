"""Explicit actor queries for PCs, opposition NPCs and retained mount NPCs.

An allied NPC stays a profile NPC. Side does not imply a Character injury
table, Fate resource or membership of the original PC/enemy source rosters.
These helpers propose typed bank updates; the native owner admits receipts.
"""
from __future__ import annotations

from dataclasses import replace

from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState,injury_is_defeated
from towr.domain.pc_companion_models import PcMountCompanionState, _actor_id, _readmit_npc_snapshot
from towr.domain.pc_mount_models import PcMountedState
from towr.domain.turn_models import CombatSide
from towr.domain.weapon_inventory_models import WeaponInventoryState


def _companions(state) -> tuple[PcMountCompanionState, ...]:
    rows = state.companions
    if type(rows) is not tuple or any(type(row) is not PcMountCompanionState for row in rows):
        raise TypeError('companion actors require an exact ordered state bank')
    for row in rows:
        replace(row)
    if len({row.rider_id for row in rows}) != len(rows):
        raise ValueError('each rider owns exactly one actual mount companion')
    original_ids = (*state.source.pc_activation_order, *state.source.npc_activation_order)
    if any(row.snapshot.state.actor_id in original_ids for row in rows):
        raise ValueError('mount companion identity collides with an original actor')
    if any(row.rider_id not in original_ids for row in rows):
        raise ValueError('mount companion must retain its actual source rider')
    return rows


def pc_companion(state, actor: str) -> PcMountCompanionState | None:
    _actor_id(actor)
    return next((row for row in _companions(state) if row.snapshot.state.actor_id == actor), None)


def _original_npc(state, actor):
    snapshot = state.enemy(actor)
    _readmit_npc_snapshot(snapshot)
    source = next(row for row in state.source.npc_sources if row.state.actor_id == actor)
    if snapshot.definition != source.definition or snapshot.state.side is not source.state.side:
        raise ValueError('NPC actor changed its static definition or source side')
    return snapshot


def pc_actor_npc_snapshot(state, actor: str):
    _actor_id(actor)
    if actor in state.source.pc_activation_order:
        raise ValueError('a PC actor has no profile NPC snapshot')
    if actor in state.source.npc_activation_order:
        return _original_npc(state, actor)
    row = pc_companion(state, actor)
    if row is not None:
        return row.snapshot
    raise ValueError('actor does not belong to the actual encounter')


def pc_actor_is_pc(state, actor: str) -> bool:
    """Actual injury-role membership, independent of allied/opposing side."""
    _actor_id(actor)
    if actor in state.source.pc_activation_order:
        return True
    pc_actor_npc_snapshot(state, actor)
    return False


def pc_actor_side(state, actor: str) -> CombatSide:
    _actor_id(actor)
    if actor in state.source.pc_activation_order:
        state.participant(actor)
        return CombatSide.PLAYERS_AND_ALLIES
    if actor in state.source.npc_activation_order:
        return _original_npc(state, actor).state.side
    row = pc_companion(state, actor)
    if row is not None:
        return row.snapshot.state.side
    raise ValueError('actor does not belong to the actual encounter')


def pc_actor_injury(state, actor: str):
    _actor_id(actor)
    if actor in state.source.pc_activation_order:
        injury = state.participant(actor).injury
        if type(injury) is not CharacterInjuryState:
            raise TypeError('PC actor requires its exact CharacterInjuryState')
        replace(injury)
        return injury
    return pc_actor_npc_snapshot(state, actor).state.injury


def pc_actor_character_body(state,actor:str):
    """Anatomical view for a PC or actual NPC Champion, never a profile NPC."""
    if actor in state.source.pc_activation_order:
        return state.participant(actor)
    from towr.domain.pc_npc_champion_models import npc_champion_body
    return npc_champion_body(state,actor)


def pc_actor_inventory(state, actor: str):
    pc_actor_side(state, actor)  # Exact actor/source admission precedes the view.
    inventory = (state.participant(actor).weapon_inventory
        if actor in state.source.pc_activation_order else pc_actor_npc_snapshot(state, actor).state.weapon_inventory)
    if inventory is not None:
        if type(inventory) is not WeaponInventoryState:
            raise TypeError('actor inventory requires its exact actual typed source')
        replace(inventory)
    return inventory


def _detached_alive(state, row: PcMountCompanionState) -> bool:
    mounts = state.mounts
    if type(mounts) is not tuple or any(type(mount) is not PcMountedState for mount in mounts):
        raise TypeError('companion activity requires the actual typed mount bank')
    matches = tuple(mount for mount in mounts if mount.actor_id == row.rider_id)
    if len(matches) != 1:
        raise ValueError('companion activity requires its one actual rider mount state')
    mounted, = matches
    replace(mounted)
    return (row.retained_since_round is not None and not mounted.mounted
        and not injury_is_defeated(row.snapshot.state.injury))


def pc_companion_turn_eligible(state, actor: str) -> bool:
    row = pc_companion(state, actor)
    if row is None or not _detached_alive(state, row):
        return False
    current = state.round_state.round_number
    if type(current) is not int or current < 1:
        raise ValueError('companion turn requires the actual positive combat round')
    return current > row.retained_since_round


def pc_active_actor_ids(state, side: CombatSide | None = None) -> tuple[str, ...]:
    if side is not None and type(side) is not CombatSide:
        raise TypeError('actor side filter requires an exact CombatSide or None')
    companions = _companions(state)
    ordered = []
    for current_side in CombatSide:
        if side is not None and current_side is not side:
            continue
        order=(state.source.player_activation_order if current_side is CombatSide.PLAYERS_AND_ALLIES
            else state.source.enemy_activation_order)
        for actor in order:
            if pc_actor_side(state, actor) is current_side:
                injury = pc_actor_injury(state, actor)
                alive = not injury_is_defeated(injury) and actor not in state.exited_npc_ids
                if alive:
                    ordered.append(actor)
            # A dead/departed rider does not erase an independently living NPC.
            for row in companions:
                if (row.rider_id == actor and row.snapshot.state.side is current_side
                        and _detached_alive(state, row)):
                    ordered.append(row.snapshot.state.actor_id)
    return tuple(ordered)


def pc_opponent_ids(state, actor: str) -> tuple[str, ...]:
    side = pc_actor_side(state, actor)
    return pc_active_actor_ids(state,
        CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES)


def pc_actor_npc_update(state, actor: str, *, injury=None, snapshot=None) -> dict:
    if (injury is None) == (snapshot is None):
        raise ValueError('NPC bank update requires exactly one injury or complete snapshot')
    before = pc_actor_npc_snapshot(state, actor)
    if injury is not None:
        if type(injury) not in (ProfileInjuryState, CharacterInjuryState):
            raise TypeError('NPC bank update requires an exact typed injury state')
        replace(injury)
        after = replace(before, state=replace(before.state, injury=injury))
    else:
        after = snapshot
    _readmit_npc_snapshot(after)
    if (after.definition != before.definition or after.state.actor_id != actor
            or after.state.definition_id != before.state.definition_id or after.state.side is not before.state.side):
        raise ValueError('NPC bank update changed actual identity, static source or side')
    companion = pc_companion(state, actor)
    if companion is not None:
        return dict(companions=tuple(replace(row, snapshot=after) if row.rider_id == companion.rider_id else row
            for row in state.companions))
    return dict(enemies=tuple(after if row.state.actor_id == actor else row for row in state.enemies))
