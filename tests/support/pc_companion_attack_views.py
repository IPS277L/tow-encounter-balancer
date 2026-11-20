"""Explicit prepared bodies for physical kernel/continuation component checks.

Detachment/placement/Conditions are observed input facts here. These views do
not claim a native Dismount journal or bypass public Talent admission.
"""
from dataclasses import fields, replace
from types import SimpleNamespace

from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import _close_key
from towr.domain.pc_melee_result_models import PcMeleeState, initial_pc_melee_state, pc_melee_action_id
from towr.domain.pc_mount_models import CombatMount
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import CombatTurnStartRequest, CombatActionSlotRequest, CombatActionDeclaration, CombatActionKind, ActionSlotGrant
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


class CompanionAttackView(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies
    exited_npc_ids = PcMeleeState.exited_npc_ids


def prepared_companion_attack(*, npc_actor=True, kind=CombatMount.HORSE, staggered=False, npc_strength=3, source=None):
    if source is None:
        source=mount_source(kind)
        npc=replace(source.enemies[0].definition.generated_components,strength=npc_strength)
        source=replace(source,enemies=(npc.participant(source.enemy_activation_order[0]),))
    initial = initial_pc_melee_state(source)
    values = {field.name: getattr(initial, field.name) for field in fields(initial)}
    pc, npc = source.pc_activation_order[0], source.enemy_activation_order[0]
    actor, rider = (npc,pc) if npc_actor else (pc,npc)
    target = rider+':mount'
    rows=[]
    for row in initial.companions:
        if row.rider_id == rider:
            injury=row.snapshot.state.injury
            if staggered: injury=replace(injury,conditions=injury.conditions.with_condition(Condition.STAGGERED))
            row=replace(row,retained_since_round=1,
                snapshot=replace(row.snapshot,state=replace(row.snapshot.state,injury=injury)))
        rows.append(row)
    values['companions']=tuple(rows)
    values['mounts']=tuple(replace(row,mounted=False) if row.actor_id==rider else row for row in initial.mounts)
    spatial=initial.battlefield.spatial
    placement=spatial.placement_for(rider)
    values['battlefield']=replace(initial.battlefield,
        spatial=replace(spatial,placements=(*spatial.placements,
            SpatialEntityPlacement(target,placement.side_id,placement.zone_id))),
        close_pairs=(*initial.battlefield.close_pairs,_close_key(target,rider),_close_key(target,actor)))
    view=CompanionAttackView(**values)
    clock=replace(initial.round_state,completed_turn_entity_ids=(pc,) if npc_actor else ())
    identifier=pc_melee_action_id(view,actor)
    clock=start_combat_turn(CombatTurnStartRequest(identifier+':start',clock,actor)).state
    view.round_state=reserve_combat_action_slot(CombatActionSlotRequest(identifier+':reserve',clock,actor,
        CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD)).state
    return view,actor,target
