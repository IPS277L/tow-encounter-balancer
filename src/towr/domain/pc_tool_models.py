"""Physical tool banks shared by native player and generated NPC actors."""
from dataclasses import replace

from towr.domain.tool_inventory_models import (
    ToolInventoryState, ToolInventoryTransition, ToolInventoryTransitionKind,
    initial_tool_inventory, drop_tool, validate_tool_equipment_hands,
)
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation


def actor_tools(state, actor):
    from towr.domain.pc_actor_models import pc_actor_is_pc, pc_actor_npc_snapshot
    return (state.participant(actor).tool_inventory if pc_actor_is_pc(state, actor)
        else pc_actor_npc_snapshot(state, actor).state.tool_inventory)


def actor_tool_zone(state, actor):
    return (state.source.facts.zone_id if state.battlefield is None else
        state.battlefield.spatial.placement_for(actor).zone_id)


def actor_tool_ground_zone(state, actor):
    zone = actor_tool_zone(state, actor)
    if state.battlefield is None:
        return zone
    from towr.domain.pc_battlefield_models import battlefield_is_midair,battlefield_ground_below
    return battlefield_ground_below(state.battlefield,zone) if battlefield_is_midair(
        state.battlefield,zone,zone=True) else zone


def validate_native_tools(state):
    """Fold exact physical receipts, then readmit immutable origins and hands.

    Tools are trappings, not extra weapons in the PG92 weapon-count limit.
    No generic bulk/weight is inferred from a one/two-handed instrument.
    """
    from towr.domain.pc_melee_result_models import PcHandDropProof, PcBodyConsequenceProof
    from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
    from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
    if any(row.snapshot.state.tool_inventory != ToolInventoryState() for row in state.companions):
        raise ValueError('passive mount bodies cannot acquire tool items outside their actual source')
    initial={member.actor_id:initial_tool_inventory(member.actor_id,
        state.source.participant(member.actor_id).pc.tools) for member in state.party}
    initial.update({enemy.state.actor_id:initial_tool_inventory(enemy.state.actor_id,
        () if enemy.definition.generated_components is None else enemy.definition.generated_components.tools)
        for enemy in state.enemies})
    bank=dict(initial)
    for index,proof in enumerate(state.history):
        equipment=(proof.equipment if type(proof) is PcMusicianRecoverProof else
            proof if type(proof) is PcMusicianEquipmentProof else None)
        if equipment is not None:
            replace(proof)
            replace(equipment)
            actor=equipment.actor_id
            if (actor not in bank or equipment.history_index!=index
                    or equipment.previous_tools!=bank[actor]):
                raise ValueError('tool equipment lost its actual source-owned journal prefix')
            _tool_origins(equipment.tools,initial[actor])
            bank[actor]=equipment.tools
        if type(proof) in (PcHandDropProof,PcBodyConsequenceProof):
            for drop in _readmit_tool_drops(proof.tool_drops):
                actor=drop.actor_id
                if actor not in state.source.pc_activation_order or drop.before!=bank[actor]:
                    raise ValueError('tool drop changed its actual owner or previous physical inventory')
                _tool_origins(drop.after,initial[actor])
                bank[actor]=drop.after
    for body in (*state.party,*(enemy.state for enemy in state.enemies)):
        _tool_origins(body.tool_inventory,initial[body.actor_id])
        if body.tool_inventory!=bank[body.actor_id]:
            raise ValueError('tool positions differ from the actual source and physical receipt history')
        for item in body.tool_inventory.items:
            if item.location is not WeaponItemLocation.DROPPED:
                continue
            if state.battlefield is None:
                valid=item.dropped_zone_id==state.source.facts.zone_id
            else:
                from towr.domain.pc_battlefield_models import battlefield_is_midair
                valid=(state.battlefield.spatial.graph.contains(item.dropped_zone_id)
                    and not battlefield_is_midair(state.battlefield,item.dropped_zone_id,zone=True))
            if not valid:
                raise ValueError('a dropped tool requires its actual supported ground Zone')
        if body.weapon_inventory is not None:
            validate_tool_equipment_hands(body.tool_inventory,body.weapon_inventory)


def _tool_origins(actual, expected):
    if type(actual) is not ToolInventoryState:
        raise TypeError('native tools require their complete physical bank')
    replace(actual)
    def origin(item):
        return item.id, item.source, item.initial_actor_id, item.source_item_id
    if tuple(map(origin, actual.items)) != tuple(map(origin, expected.items)):
        raise ValueError('native tools changed their complete immutable source membership')


def _readmit_tool_drops(drops):
    if type(drops) is not tuple or any(type(drop) is not ToolInventoryTransition for drop in drops):
        raise TypeError('tool drops require an exact tuple of actual physical transitions')
    for drop in drops:
        replace(drop)
        if drop.kind is not ToolInventoryTransitionKind.DROP:
            raise ValueError('a Wound tool receipt must be its actual involuntary drop')
    return drops


def _expected_pc_tool_drops(state,proof):
    """Derive a Wound's tool losses from its real pending target and body result.

    This pure preparation has no RNG and applies no additional hand action.
    Source order fixes multiple drops; a two-handed tool remains one object.
    """
    from towr.domain.pc_melee_result_models import PcHandDropProof, PcBodyConsequenceProof
    from towr.domain.injury_models import WoundConsequence,WoundConsequenceRequest
    from towr.domain.pc_heavy_wound_models import PcBodyFactKind
    if type(proof) not in (PcHandDropProof,PcBodyConsequenceProof):
        return ()
    if type(proof.source) is not WoundConsequenceRequest:
        raise TypeError('tool losses require their exact typed Wound consequence')
    replace(proof.source)
    if state.pending_wound is not None or not state.pending or state.pending[0]!=proof.source:
        raise ValueError('tool losses require the next actual mandatory Wound consequence')
    actor=state.pending_actor_id
    if actor not in state.source.pc_activation_order:
        raise ValueError('anatomical tool loss requires its actual PC injury owner')
    before=state.participant(actor)
    if not before.tool_inventory.items:
        return ()
    if proof.source.wound_sequence>len(before.injury.wounds):
        raise ValueError('tool losses require their actual recorded Wound sequence')
    from towr.domain._pc_heavy_wound_projection import body_consequence
    argument=(PcBodyConsequenceProof(proof.source,proof.die,proof.hand)
        if type(proof) is PcHandDropProof else proof)
    after=body_consequence(before,argument)
    sides=[]
    if proof.source.consequence in (WoundConsequence.DROP_RANDOM_HAND_ITEM,
            WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH,
            WoundConsequence.RANDOMISE_SEVERED_ARM):
        side=proof.hand if type(proof) is PcHandDropProof else proof.side
        if side is not None:
            sides.append(WeaponGrip(side.value))
    sides.extend(WeaponGrip(fact.side.value) for fact in after.body_facts
        if fact.kind is PcBodyFactKind.CLUTCH_STOMACH and fact not in before.body_facts)
    inventory=before.tool_inventory
    drops=[]
    for item in tuple(inventory.items):
        if item.location is WeaponItemLocation.HELD and any(side in item.occupied_hands for side in sides):
            drop=drop_tool(actor,inventory,item.id,actor_zone_id=actor_tool_ground_zone(state,actor))
            drops.append(drop)
            inventory=drop.after
    return tuple(drops)


def complete_pc_tool_equipment_proof(state,proof):
    """Attach exact physical losses once, rejecting conflicting cached receipts."""
    from towr.domain.pc_melee_result_models import PcHandDropProof,PcBodyConsequenceProof
    if type(proof) not in (PcHandDropProof,PcBodyConsequenceProof):
        return proof
    actual=_readmit_tool_drops(proof.tool_drops)
    expected=_expected_pc_tool_drops(state,proof)
    if actual and actual!=expected:
        raise ValueError('attached tool drops differ from this actual Wound and body source')
    return proof if actual==expected else replace(proof,tool_drops=expected)


def reconcile_native_tool_losses(state,proof,updates):
    """Apply only the exact previously witnessed losses to the proposed body."""
    from towr.domain.pc_melee_result_models import PcHandDropProof,PcBodyConsequenceProof
    if type(proof) not in (PcHandDropProof,PcBodyConsequenceProof):
        return updates
    actual=_readmit_tool_drops(proof.tool_drops)
    expected=_expected_pc_tool_drops(state,proof)
    if actual!=expected:
        raise ValueError('Wound tool drop changed its complete actual physical receipts')
    if not actual:
        return updates
    actor=state.pending_actor_id
    party=updates.get('party',state.party)
    changed=[]
    for member in party:
        if member.actor_id==actor:
            if member.tool_inventory!=actual[0].before:
                raise ValueError('Wound tool drop was applied twice or detached from its actual prefix')
            member=replace(member,tool_inventory=actual[-1].after)
        changed.append(member)
    return dict(updates,party=tuple(changed))
