"""Physical instrument preparation for original PC/generated NPC owners.

The native owner binds this receipt to its committed action. Dropped tools
require its actual paid standard Recover; this planner supplies no free pickup,
new action, restored weapon resource or refreshed creature state.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.pc_npc_shield_models import PcNpcShieldState
from towr.domain.tool_inventory_models import (
    ToolInventoryState, initial_tool_inventory, validate_tool_equipment_hands,
)
from towr.domain.turn_models import CombatRoundState
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponInventoryState, WeaponItemLocation

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('musician equipment requires exact nonempty actor/item/action identifiers')


def _hands(grip):
    return (() if grip is None else (WeaponGrip.LEFT, WeaponGrip.RIGHT)
        if grip is WeaponGrip.BOTH else (grip,))


def _participant(value):
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState
    if type(value) not in (PcMeleeParticipantState, NpcParticipantSnapshot):
        raise TypeError('musician equipment requires its full exact native participant snapshot')
    replace(value)
    body = value if type(value) is PcMeleeParticipantState else value.state
    if type(body.tool_inventory) is not ToolInventoryState or type(body.weapon_inventory) is not WeaponInventoryState:
        raise TypeError('musician equipment requires its actual physical tool and weapon banks')
    replace(body.tool_inventory)
    replace(body.weapon_inventory)
    validate_tool_equipment_hands(body.tool_inventory, body.weapon_inventory)
    return body


@dataclass(frozen=True, slots=True)
class PcMusicianEquipmentProof:
    actor_id: str
    action_id: str
    round_state: CombatRoundState
    history_index: int
    item_id: str | None
    pickup: bool
    previous: PcMeleeParticipantState | NpcParticipantSnapshot
    state: PcMeleeParticipantState | NpcParticipantSnapshot
    previous_npc_shield: PcNpcShieldState | None
    npc_shield: PcNpcShieldState | None
    previous_battlefield: PcBattlefieldState | None
    battlefield: PcBattlefieldState | None

    def __post_init__(self):
        _identifier(self.actor_id)
        _identifier(self.action_id)
        if self.item_id is not None:
            _identifier(self.item_id)
        if type(self.pickup) is not bool:
            raise TypeError('musician pickup requires its exact paid-interaction selection')
        if self.pickup and self.item_id is None:
            raise ValueError('a paid tool pickup must name its actual dropped instrument')
        if type(self.history_index) is not int or self.history_index < 0:
            raise ValueError('musician equipment requires its actual nonnegative journal position')
        if type(self.round_state) is not CombatRoundState:
            raise TypeError('musician equipment requires its complete actual clock')
        replace(self.round_state)
        if self.round_state.active_turn is None or self.round_state.active_turn.actor_id != self.actor_id:
            raise ValueError('musician equipment belongs to another actual active actor')
        before, after = _participant(self.previous), _participant(self.state)
        if type(self.previous) is not type(self.state) or before.actor_id != self.actor_id or after.actor_id != self.actor_id:
            raise ValueError('musician equipment cannot change its actual participant identity or role')
        for item in (self.previous_npc_shield, self.npc_shield):
            if item is not None:
                if type(item) is not PcNpcShieldState or item.actor_id != self.actor_id:
                    raise TypeError('musician equipment requires its exact source-owned NPC Shield')
                replace(item)
        for battlefield in (self.previous_battlefield, self.battlefield):
            if battlefield is not None:
                if type(battlefield) is not PcBattlefieldState:
                    raise TypeError('musician equipment requires its exact physical battlefield')
                replace(battlefield)
        # All physical weapon resources and membership survive an incidental
        # hand arrangement. Shield release has its separate source-owned bank.
        from towr.domain.weapon_equip_models import WeaponEquipTransition
        WeaponEquipTransition(self.actor_id, self.round_state.round_number,
            replace(before.weapon_inventory, shield_hand=after.weapon_inventory.shield_hand),
            after.weapon_inventory)
        if before.weapon_inventory.active_item_id != after.weapon_inventory.active_item_id:
            raise ValueError('preparing music cannot change the selected physical weapon')
        for old, new in zip(before.tool_inventory.items, after.tool_inventory.items, strict=True):
            if (old.source, old.id, old.initial_actor_id, old.source_item_id) != (
                    new.source, new.id, new.initial_actor_id, new.source_item_id):
                raise ValueError('musician equipment cannot rewrite its physical tool sources')
        if not self.changes_equipment:
            raise ValueError('unchanged musician equipment needs no physical receipt')

    @property
    def previous_tools(self):
        return _participant(self.previous).tool_inventory

    @property
    def tools(self):
        return _participant(self.state).tool_inventory

    @property
    def previous_weapons(self):
        return _participant(self.previous).weapon_inventory

    @property
    def weapons(self):
        return _participant(self.state).weapon_inventory

    @property
    def changes_equipment(self):
        before, after = _participant(self.previous), _participant(self.state)
        return (before.tool_inventory != after.tool_inventory or before.weapon_inventory != after.weapon_inventory)


def _body(state, actor):
    if actor in state.source.pc_activation_order:
        value = state.participant(actor)
    elif actor in state.source.npc_activation_order:
        value = state.enemy(actor)
        if value.definition.generated_components is None:
            return None
    else:
        raise ValueError('only an original PC or generated NPC owns musician equipment')
    _participant(value)
    return value


def _usable(value):
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState
    if type(value) is not PcMeleeParticipantState:
        return (WeaponGrip.LEFT, WeaponGrip.RIGHT), set()
    from towr.domain.pc_heavy_wound_models import usable_hands, injured_hands
    return (tuple(WeaponGrip(side.value) for side in usable_hands(value)),
        {WeaponGrip(side.value) for side in injured_hands(value)})


def _tool_sources(state, actor, value):
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState
    sources = (state.source.participant(actor).pc.tools if type(value) is PcMeleeParticipantState
        else value.definition.generated_components.tools)
    from towr.domain.pc_tool_models import _tool_origins
    _tool_origins(_participant(value).tool_inventory, initial_tool_inventory(actor, sources))


def _touched(before_tools, tools, before_weapons, weapons):
    return {hand for before, after in (*zip(before_tools.items, tools.items, strict=True),
        *zip(before_weapons.items, weapons.items, strict=True))
        if (before.location, before.grip) != (after.location, after.grip)
        for grip in (before.grip, after.grip) for hand in _hands(grip)} | (
        set() if before_weapons.shield_hand is weapons.shield_hand else set(_hands(before_weapons.shield_hand)))


def plan_musician_equipment(state, actor_id: str, item_id: str | None, *, pickup=False
        ) -> PcMusicianEquipmentProof | None:
    _identifier(actor_id)
    if item_id is not None:
        _identifier(item_id)
    if type(pickup) is not bool:
        raise TypeError('musician pickup requires an exact boolean')
    if pickup and item_id is None:
        raise ValueError('tool pickup requires its actual dropped item ID')
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id != actor_id or state.pending or state.pending_wound is not None
            or state.magic_pending is not None):
        return None
    value = _body(state, actor_id)
    if value is None:
        return None
    body = _participant(value)
    injury = body.injury
    if ((getattr(injury, 'dead', False) or getattr(injury, 'defeated', False))
            or injury.conditions.has(Condition.DEFENCELESS)
            or actor_id in state.exited_npc_ids):
        return None
    _tool_sources(state, actor_id, value)
    before_tools, before_weapons = body.tool_inventory, body.weapon_inventory
    usable, injured = _usable(value)
    if not usable:
        return None
    tools, weapons = before_tools, before_weapons
    selected = None
    if item_id is not None:
        try:
            selected = tools.item(item_id)
        except KeyError:
            raise ValueError('music preparation must name an actual source-owned tool') from None
        if pickup:
            from towr.domain.pc_tool_models import actor_tool_zone
            if (selected.location is not WeaponItemLocation.DROPPED
                    or selected.dropped_zone_id != actor_tool_zone(state, actor_id)):
                return None
        elif selected.location is WeaponItemLocation.DROPPED:
            return None
        if selected.location is WeaponItemLocation.HELD and all(hand in usable for hand in selected.occupied_hands):
            return None
        if selected.hands_required == 2:
            if len(usable) != 2:
                return None
            grip = WeaponGrip.BOTH
        else:
            def cost(hand):
                conflicts = sum(hand in _hands(item.grip) for item in weapons.items
                    if item.location is WeaponItemLocation.HELD)
                return hand in injured, hand is weapons.shield_hand, conflicts, hand is WeaponGrip.RIGHT
            grip = min(usable, key=cost) if usable else None
            if grip is None:
                return None
        occupied = set(_hands(grip))
        trapped = {binding.weapon_id for binding in getattr(state, 'briarroot_bindings', ())
            if binding.attacker_id == actor_id}
        if any(item.id in trapped and item.location is WeaponItemLocation.HELD
                and occupied.intersection(_hands(item.grip)) for item in weapons.items):
            return None
        weapon_items = tuple(replace(item, location=WeaponItemLocation.CARRIED, grip=None)
            if item.location is WeaponItemLocation.HELD and occupied.intersection(_hands(item.grip)) else item
            for item in weapons.items)
        tools = replace(tools, items=tuple(
            replace(item, location=WeaponItemLocation.HELD, grip=grip, dropped_zone_id=None)
            if item.id == selected.id else replace(item, location=WeaponItemLocation.CARRIED, grip=None)
            if item.location is WeaponItemLocation.HELD and occupied.intersection(item.occupied_hands)
            else item for item in tools.items))
        weapons = replace(weapons, items=weapon_items,
            shield_hand=None if weapons.shield_hand in occupied else weapons.shield_hand)
    else:
        tools = replace(tools, items=tuple(replace(item, location=WeaponItemLocation.CARRIED, grip=None)
            if item.location is WeaponItemLocation.HELD else item for item in tools.items))
    if tools == before_tools and weapons == before_weapons:
        return None
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState, pc_melee_action_id
    previous_npc_shield = npc_shield = None
    battlefield = state.battlefield
    touched = _touched(before_tools, tools, before_weapons, weapons)
    if type(value) is PcMeleeParticipantState:
        shield = value.shield
        if before_weapons.shield_hand is not weapons.shield_hand:
            from towr.domain.pc_shield_models import (
                PcShieldGroundPosition, PcShieldLocation, PcShieldState,
                _add_shield_marker, _shield_actors, _shield_ground,
            )
            ground = (_shield_ground(state, actor_id) if battlefield is not None else
                PcShieldGroundPosition(state.source.facts.zone_id, _shield_actors(state)))
            shield = PcShieldState(PcShieldLocation.DROPPED, None, ground=ground)
            battlefield = _add_shield_marker(battlefield, actor_id, shield)
        from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use, critical_for_action
        from towr.domain.pc_weapon_inventory import pc_hand, replace_pc_member
        hand = pc_hand(WeaponGrip.BOTH if len(touched) == 2 else next(iter(touched))) if touched else None
        from towr.domain.turn_models import CombatActionKind
        injury = (critical_for_action(value, CombatActionKind.RECOVER, used_hand=hand) if pickup
            else critical_for_incidental_hand_use(value, hand))
        updated = replace_pc_member(value, tool_inventory=tools, weapon_inventory=weapons, shield=shield, injury=injury)
    else:
        from towr.domain.pc_npc_shield_models import (
            NpcShieldLocation, _add_marker, _drop_position, _resilience_witness, _with_shield, npc_shield_item,
        )
        previous_npc_shield = npc_shield = npc_shield_item(state, actor_id)
        updated = value
        if before_weapons.shield_hand is not weapons.shield_hand:
            if npc_shield is None or npc_shield.location is not NpcShieldLocation.HELD:
                raise ValueError('music preparation cannot invent or release a source-less NPC Shield')
            npc_shield = replace(npc_shield, location=NpcShieldLocation.DROPPED, ground=_drop_position(state, actor_id))
            battlefield = _add_marker(battlefield, npc_shield)
            updated = _with_shield(value, False, **_resilience_witness(state, actor_id))
        from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
        updated = replace(updated, state=replace(updated.state, tool_inventory=tools, weapon_inventory=weapons,
            wields_weapon=any(item.location is WeaponItemLocation.HELD for item in weapons.items),
            available_attack_ids=npc_inventory_attack_ids(updated.definition, weapons)))
    return PcMusicianEquipmentProof(actor_id, pc_melee_action_id(state, actor_id), state.round_state,
        len(state.history), item_id, pickup, value, updated, previous_npc_shield, npc_shield,
        state.battlefield, battlefield)


def project_musician_equipment(state, proof: PcMusicianEquipmentProof,
        expected_item_id: str | None, *, pickup=False) -> dict:
    if type(proof) is not PcMusicianEquipmentProof:
        raise TypeError('music equipment requires its exact physical receipt')
    replace(proof)
    expected = plan_musician_equipment(state, proof.actor_id, expected_item_id, pickup=pickup)
    if expected is None or proof != expected:
        raise ValueError('music equipment differs from its actual full plan, source, hands or clock')
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState, validate_pc_melee_source_types
    validate_pc_melee_source_types(proof, expected)
    if type(proof.state) is PcMeleeParticipantState:
        return dict(party=tuple(proof.state if member.actor_id == proof.actor_id else member for member in state.party),
            battlefield=proof.battlefield)
    return dict(enemies=tuple(proof.state if enemy.state.actor_id == proof.actor_id else enemy for enemy in state.enemies),
        battlefield=proof.battlefield, npc_shields=tuple(proof.npc_shield
            if item.actor_id == proof.actor_id else item for item in state.npc_shields))
