"""Finite generated-NPC Shields and source-bound paid recovery.

A one-handed shot can retain its Shield. Reload needs the second hand: the
actual item is dropped, stays at its physical position, then can be recovered
with a real standard Recover when its hand is free and its chosen gun loaded. No replacement Shield
is created by the next turn, a reload receipt or a source profile identifier.
"""
from __future__ import annotations

from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.armour_models import ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState,CharacterInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range
from towr.domain.pc_mount_models import PcMountedState
from towr.domain.pc_npc_resilience_models import npc_equipment_resilience, npc_mount_resilience_source
from towr.domain.talent_armour_bane_models import ArmourBaneApplication
from towr.domain.pc_npc_ranged_models import (
    pc_npc_ranged_weapon, initial_pc_npc_weapon_inventories, npc_ranged_weapon_from_unit,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange, ranged_weapon_combat_profile
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionTarget,
    RecoverMode, RecoverObjectInteractionFollowUp, RecoverStandardChoice,
)
from towr.domain.reload_models import ReloadableWeaponState, reload_approach_id
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import CombatActionKind
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation, WeaponUnitState
from towr.domain.weapon_catalog import weapon_profile

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_npc_champion_models import NpcChampionBody


NPC_SHIELD_DROP_RULE_ID = 'RULE-EQUIPMENT-006:npc-shield-reload-drop'


class NpcShieldLocation(str, Enum):
    HELD = 'held'
    DROPPED = 'dropped'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(f'{label} requires an exact nonempty identifier')


@dataclass(frozen=True, slots=True)
class NpcShieldGroundPosition:
    zone_id: str
    initial_close_actor_ids: tuple[str, ...]

    def __post_init__(self):
        _identifier(self.zone_id, 'Shield ground Zone')
        if (type(self.initial_close_actor_ids) is not tuple
                or len(set(self.initial_close_actor_ids)) != len(self.initial_close_actor_ids)):
            raise TypeError('Shield ground position requires its distinct Close actor tuple')
        for actor in self.initial_close_actor_ids:
            _identifier(actor, 'Shield Close actor')


@dataclass(frozen=True, slots=True)
class PcNpcShieldState:
    actor_id: str
    item_id: str
    kind: ShieldKind
    location: NpcShieldLocation
    ground: NpcShieldGroundPosition | None = field(default=None, kw_only=True)

    def __post_init__(self):
        _identifier(self.actor_id, 'Shield owner')
        _identifier(self.item_id, 'Shield item')
        if self.item_id != self.actor_id+':shield':
            raise ValueError('NPC Shield must retain its one source-owned item instance')
        if type(self.kind) is not ShieldKind or type(self.location) is not NpcShieldLocation:
            raise TypeError('NPC Shield requires its exact kind and location')
        if self.location is NpcShieldLocation.DROPPED:
            if type(self.ground) is not NpcShieldGroundPosition:
                raise TypeError('a dropped Shield requires its exact physical ground position')
            replace(self.ground)
        elif self.ground is not None:
            raise ValueError('a held Shield cannot retain a ground position')

    @property
    def marker_id(self):
        return self.item_id+':ground'


def _same(actual, expected, message):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual != expected:
        raise ValueError(message)
    validate_pc_melee_source_types(actual, expected)


def _shield_transition(previous, current, *, picked_up):
    if type(previous) is not PcNpcShieldState or type(current) is not PcNpcShieldState:
        raise TypeError('NPC Shield transition requires its exact before/after item states')
    replace(previous); replace(current)
    if ((previous.actor_id, previous.item_id, previous.kind)
            != (current.actor_id, current.item_id, current.kind)):
        raise ValueError('NPC Shield transition changed physical ownership or kind')
    if (previous.location is not (NpcShieldLocation.DROPPED if picked_up else NpcShieldLocation.HELD)
            or current.location is not (NpcShieldLocation.HELD if picked_up else NpcShieldLocation.DROPPED)):
        raise ValueError('NPC Shield transition repeats or reverses the required physical change')


def _free_shield_hand(enemy,champion_body=None):
    return _free_shield_grip(enemy.state.weapon_inventory,enemy.state.tool_inventory,champion_body)


def _free_shield_grip(inventory,tools,champion_body=None):
    if inventory is None:
        return None
    occupied = {hand for item in inventory.items if item.location is WeaponItemLocation.HELD
        for hand in ((WeaponGrip.LEFT,WeaponGrip.RIGHT)
            if item.grip is WeaponGrip.BOTH else (item.grip,))}
    occupied.update(tools.occupied_hands)
    available=(WeaponGrip.RIGHT,WeaponGrip.LEFT)
    if champion_body is not None:
        from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands
        usable=usable_hands(champion_body);injured=injured_hands(champion_body)
        available=tuple(hand for hand in available if hand.value in {side.value for side in usable})
        available=tuple(sorted(available,key=lambda hand: hand.value in {side.value for side in injured}))
    return next((hand for hand in available if hand not in occupied),None)


def _source_unit_witness(enemy, unit):
    if type(unit) is not WeaponUnitState:
        raise TypeError('NPC Shield weapon witness requires its exact physical unit')
    replace(unit)
    inventory = enemy.state.weapon_inventory
    actual = None if inventory is None else next((item for item in inventory.items if item.id == unit.id),None)
    if actual is None:
        raise ValueError('NPC Shield weapon does not belong to its actual physical inventory')
    _same(unit,actual,'NPC Shield weapon detached from its complete physical unit')


def _pickup_weapon_witness(enemy):
    inventory = enemy.state.weapon_inventory
    unit = None if inventory is None else inventory.active
    if unit is None or unit.location is not WeaponItemLocation.HELD:
        return None
    if unit.reload is not None:
        return unit.reload if unit.reload.loaded else None
    return unit


def _with_shield(enemy, held, *, mount_source, armour_bane_sources, injury=None,champion_body=None):
    if type(enemy) is not NpcParticipantSnapshot or type(held) is not bool:
        raise TypeError('NPC Shield equipment projection requires its exact participant and bool')
    replace(enemy)
    if champion_body is not None:
        from towr.domain.pc_npc_champion_models import NpcChampionBody
        if type(champion_body) is not NpcChampionBody or champion_body.actor_id!=enemy.state.actor_id:
            raise TypeError('Champion Shield source requires this actor exact anatomy')
        replace(champion_body)
        if champion_body.weapon_inventory!=enemy.state.weapon_inventory:
            raise ValueError('Champion Shield anatomy changed the actual physical inventory')
    elif type(enemy.state.injury) is CharacterInjuryState:
        raise ValueError('Champion Shield transition requires its actual anatomical witness')
    if enemy.state.holds_shield is held:
        raise ValueError('NPC Shield equipment is already in the requested state')
    from towr.domain.pc_armour_bane_models import armour_bane_resilience_from_sources
    from towr.domain.pc_heavy_wound_models import usable_hands
    working=enemy.state.holds_shield and (champion_body is None or
        enemy.state.weapon_inventory.shield_hand.value in {side.value for side in usable_hands(champion_body)})
    before_base = npc_equipment_resilience(enemy.definition, enemy.state.actor_id,
        shield_held=working, mount_source=mount_source)
    before = armour_bane_resilience_from_sources(before_base, armour_bane_sources)
    for application in armour_bane_sources:
        if application.target_id != enemy.state.actor_id:
            raise ValueError('NPC Shield resilience retained another actor Armour Bane source')
    _same(enemy.state.current_resilience,before,
        'NPC Shield source differs from its actual equipment, mount and Armour Bane provenance')
    after_base = npc_equipment_resilience(enemy.definition, enemy.state.actor_id,
        shield_held=held, mount_source=mount_source)
    resilience = armour_bane_resilience_from_sources(after_base, armour_bane_sources)
    inventory = enemy.state.weapon_inventory
    if inventory is None:
        raise ValueError('NPC Shield transition requires its actual physical weapon inventory')
    if (inventory.shield_hand is not None) is not enemy.state.holds_shield:
        raise ValueError('NPC held Shield differs from its actual occupied inventory hand')
    shield_hand = None
    if held:
        shield_hand = _free_shield_hand(enemy,champion_body)
        if shield_hand is None:
            raise ValueError('NPC Shield pickup requires an actual free hand')
    return replace(enemy, state=replace(enemy.state, holds_shield=held,
        weapon_inventory=replace(inventory,shield_hand=shield_hand),
        current_resilience=resilience,
        injury=enemy.state.injury if injury is None else injury))


def _held_weapon_witness(enemy, weapon):
    inventory = enemy.state.weapon_inventory
    item = inventory.active if inventory is not None else None
    identifier = weapon.id if type(weapon) is WeaponUnitState else weapon.weapon_instance_id
    if (item is None or item.location is not WeaponItemLocation.HELD or identifier != item.id):
        raise ValueError('NPC Shield needs the actually selected held weapon instance')
    if type(weapon) is WeaponUnitState:
        _source_unit_witness(enemy,weapon)
    else:
        _same(weapon,npc_ranged_weapon_from_unit(item),
            'NPC Shield weapon detached from the full physical K1 state')


@dataclass(frozen=True, slots=True)
class PcNpcShieldDropProof:
    source_id: str
    history_index: int
    previous: PcNpcShieldState
    state: PcNpcShieldState
    weapon: ReloadableWeaponState | WeaponUnitState
    previous_enemy: NpcParticipantSnapshot
    enemy: NpcParticipantSnapshot
    rule_id: str = NPC_SHIELD_DROP_RULE_ID
    mount_source: PcMountedState | None = field(kw_only=True)
    armour_bane_sources: tuple[ArmourBaneApplication,...] = field(kw_only=True)
    champion_body: NpcChampionBody | None = field(default=None,kw_only=True)

    @property
    def actor_id(self):
        return self.previous.actor_id

    def __post_init__(self):
        _identifier(self.source_id, 'Shield drop source')
        if type(self.history_index) is not int or self.history_index < 0:
            raise ValueError('Shield drop history index must be an exact nonnegative integer')
        _shield_transition(self.previous, self.state, picked_up=False)
        if type(self.weapon) not in (ReloadableWeaponState,WeaponUnitState):
            raise TypeError('Shield drop requires its actual Reload or physical weapon witness')
        if type(self.weapon) is ReloadableWeaponState and self.weapon.loaded:
            raise ValueError('Reload Shield drop requires its actual unloaded weapon')
        replace(self.weapon)
        if type(self.rule_id) is not str or self.rule_id != NPC_SHIELD_DROP_RULE_ID:
            raise ValueError('NPC Shield drop must retain its equipment rule')
        if type(self.previous_enemy) is not NpcParticipantSnapshot or type(self.enemy) is not NpcParticipantSnapshot:
            raise TypeError('NPC Shield drop requires exact participant snapshots')
        if self.previous_enemy.state.actor_id != self.actor_id:
            raise ValueError('Shield drop must retain its actual NPC participant')
        if type(self.weapon) is WeaponUnitState:
            _source_unit_witness(self.previous_enemy,self.weapon)
            profile = weapon_profile(self.weapon.kind)
            if (self.weapon.location not in (WeaponItemLocation.HELD,WeaponItemLocation.CARRIED)
                    or not (profile.variable_grip or profile.hands is RangedWeaponHands.TWO_HANDED)):
                raise ValueError('weapon-first Shield release requires an actual potential two-handed use')
        else:
            _held_weapon_witness(self.previous_enemy,self.weapon)
        _same(self.enemy, _with_shield(self.previous_enemy, False,
            mount_source=self.mount_source,armour_bane_sources=self.armour_bane_sources,champion_body=self.champion_body),
            'NPC Shield drop changed something besides held Shield and its Resilience source')


def _standard_injury(before, result,champion_body=None):
    if type(before) not in (ProfileInjuryState,CharacterInjuryState):
        raise TypeError('NPC Shield Recover requires its exact actual injury')
    conditions = before.conditions
    for change in result.resolution.condition_changes:
        for condition in change.removed_conditions:
            conditions=conditions.without_condition(condition)
    injury=replace(before,conditions=conditions)
    if champion_body is not None:
        from towr.domain.pc_heavy_wound_models import critical_for_action
        from towr.domain.pc_melee_models import PcWeaponHand
        hand=_free_shield_hand_from_body(champion_body)
        priced=critical_for_action(champion_body,CombatActionKind.RECOVER,
            removes_prone=before.conditions.has(Condition.PRONE) and not injury.conditions.has(Condition.PRONE),
            used_hand=None if hand is None else PcWeaponHand(hand.value))
        new=tuple(effect for effect in priced.active_wound_effects if effect not in champion_body.injury.active_wound_effects)
        injury=replace(injury,active_wound_effects=(*injury.active_wound_effects,*(effect for effect in new if effect not in injury.active_wound_effects)),
            conditions=injury.conditions.with_condition(Condition.CRITICALLY_INJURED) if new else injury.conditions)
    return injury


def _free_shield_hand_from_body(body):
    return _free_shield_grip(body.weapon_inventory,body.tool_inventory,body)


@dataclass(frozen=True, slots=True)
class PcNpcShieldRecoverProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    previous: PcNpcShieldState
    state: PcNpcShieldState
    weapon: ReloadableWeaponState | WeaponUnitState
    previous_enemy: NpcParticipantSnapshot
    enemy: NpcParticipantSnapshot
    mount_source: PcMountedState | None = field(kw_only=True)
    armour_bane_sources: tuple[ArmourBaneApplication,...] = field(kw_only=True)
    champion_body: NpcChampionBody | None = field(default=None,kw_only=True)

    @property
    def actor_id(self):
        return self.previous.actor_id

    @property
    def previous_injury(self):
        return self.previous_enemy.state.injury

    @property
    def injury(self):
        return self.enemy.state.injury

    def __post_init__(self):
        _shield_transition(self.previous, self.state, picked_up=True)
        if type(self.request) is not RecoverActionExecutionRequest or type(self.result) is not RecoverActionExecutionResult:
            raise TypeError('NPC Shield pickup requires its exact paid Recover request and result')
        replace(self.request); replace(self.result)
        if type(self.weapon) not in (ReloadableWeaponState,WeaponUnitState):
            raise TypeError('Shield pickup needs its actual selected physical weapon witness')
        if (type(self.weapon) is ReloadableWeaponState and not self.weapon.loaded
                or type(self.weapon) is WeaponUnitState and self.weapon.reload is not None):
            raise ValueError('Shield pickup preserves genuine loaded K1 for every Exacting weapon')
        replace(self.weapon)
        if type(self.previous_enemy) is not NpcParticipantSnapshot or type(self.enemy) is not NpcParticipantSnapshot:
            raise TypeError('NPC Shield pickup requires exact participant snapshots')
        _held_weapon_witness(self.previous_enemy,self.weapon)
        if (self.request.actor_id != self.actor_id or self.request.mode is not RecoverMode.STANDARD
                or type(self.request.choice) is not RecoverStandardChoice
                or self.request.choice.mount is not None):
            raise ValueError('NPC Shield pickup requires this actor standard Recover')
        interaction = self.request.choice.object_interaction
        if (type(interaction) is not RecoverObjectInteractionFollowUp
                or interaction.actor_id != self.actor_id or interaction.object_id != self.previous.item_id
                or interaction.object_in_close_range is not True):
            raise ValueError('NPC Shield pickup must interact with its real nearby item')
        if (self.previous_enemy.state.actor_id != self.actor_id
                or self.request.actor_conditions != (self.previous_injury.conditions
                    if self.champion_body is None else self.champion_body.injury.conditions)):
            raise ValueError('NPC Shield Recover is detached from its actor or previous injury')
        for target in (self.request.choice.staggered_target, self.request.choice.prone_target):
            if target is not None and (target.entity_id != self.actor_id
                    or target.conditions != self.request.actor_conditions):
                raise ValueError('NPC Shield Recover uses only standard self condition benefits')
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        _same(self.result, expected_pc_standard_recover(self.request),
            'NPC Shield pickup changed its actual paid standard Recover receipt')
        _same(self.enemy, _with_shield(self.previous_enemy, True,
            injury=_standard_injury(self.previous_injury,self.result,self.champion_body),
            mount_source=self.mount_source,armour_bane_sources=self.armour_bane_sources,champion_body=self.champion_body),
            'NPC Shield pickup changed unrelated equipment, Resilience or injuries')


def initial_npc_shields(source):
    from towr.domain.generated_npc_models import validate_generated_definition
    result = []
    for enemy in source.npc_sources:
        components = enemy.definition.generated_components
        if components is None or components.armour.shield is None:
            continue
        validate_generated_definition(enemy.definition)
        actor = enemy.state.actor_id
        if enemy.state.holds_shield is not True:
            raise ValueError('fresh generated Shield source must actually hold its item')
        from towr.domain.generated_npc_models import generated_initial_weapon_inventory
        inventory = generated_initial_weapon_inventory(components,actor)
        if inventory.shield_hand is None:
            raise ValueError('fresh Shield source requires its actual free inventory hand')
        if enemy.state.weapon_inventory is not None:
            _same(enemy.state.weapon_inventory,inventory,'fresh NPC Shield changed its initial physical hand or items')
        result.append(PcNpcShieldState(actor, actor+':shield', components.armour.shield, NpcShieldLocation.HELD))
    return tuple(result)


def npc_shield_item(state, actor):
    if actor not in state.source.npc_activation_order:
        return None
    return next((item for item in state.npc_shields if item.actor_id == actor), None)


def _ready_actor(state, kind):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.npc_activation_order:
        return None
    if len(turn.action_slots) > 1 or (turn.action_slots
            and (turn.action_slots[0].executed or turn.action_slots[0].declaration.kind is not kind)):
        return None
    actor = turn.actor_id
    enemy = state.enemy(actor)
    inventory = enemy.state.weapon_inventory
    weapon = inventory.active if inventory is not None else None
    from towr.domain.pc_medical_models import effective_medical_injury
    injury=effective_medical_injury(state,actor)
    if (injury_is_defeated(enemy.state.injury) or actor in state.exited_npc_ids
            or not enemy.state.wields_weapon or weapon is None or weapon.location is not WeaponItemLocation.HELD
            or any(injury.conditions.has(condition)
                for condition in (Condition.BROKEN, Condition.DEFENCELESS))):
        return None
    return actor


def _actors(state):
    return (*state.source.pc_activation_order,
        *(actor for actor in state.source.npc_activation_order if actor not in state.exited_npc_ids))


def _drop_position(state, actor):
    if state.battlefield is None:
        if not state.source.facts.all_opponents_close:
            raise ValueError('stationary Shield geometry requires the explicit all-Close scene')
        return NpcShieldGroundPosition(state.source.facts.zone_id, _actors(state))
    from towr.domain.pc_battlefield_models import battlefield_is_midair, battlefield_ground_below
    if battlefield_is_midair(state.battlefield, actor):
        zone = state.battlefield.spatial.placement_for(actor).zone_id
        return NpcShieldGroundPosition(battlefield_ground_below(state.battlefield, zone), ())
    return NpcShieldGroundPosition(state.battlefield.spatial.placement_for(actor).zone_id,
        tuple(other for other in _actors(state) if other == actor or
            battlefield_range(state.battlefield, actor, other) is RangedWeaponRange.CLOSE))


def _drop_id(source, actor, index):
    return f'{source.id}:npc-shield:drop:{index}:{actor}'


def _resilience_witness(state,actor):
    from towr.domain.pc_armour_bane_models import armour_bane_applications
    return dict(mount_source=npc_mount_resilience_source(state,actor),
        armour_bane_sources=armour_bane_applications(state,actor),champion_body=_champion_body(state,actor))


def _champion_body(state,actor):
    if type(state.enemy(actor).state.injury) is not CharacterInjuryState:return None
    from towr.domain.pc_medical_models import medical_effective_body
    return medical_effective_body(state,actor)


def expected_npc_shield_drop(state):
    from towr.domain.pc_bash_attack_models import expected_bash_npc_shield_drop
    bash=expected_bash_npc_shield_drop(state)
    if bash is not None:return bash
    actor = _ready_actor(state,CombatActionKind.ATTACK) or _ready_actor(state,CombatActionKind.IMPROVISE)
    if actor is None:
        return None
    item = npc_shield_item(state,actor)
    if item is None or item.location is not NpcShieldLocation.HELD:
        return None
    from towr.domain.pc_npc_weapon_inventory import npc_shield_release_weapon
    selected = npc_shield_release_weapon(state)
    if selected is not None:
        enemy = state.enemy(actor)
        after = replace(item,location=NpcShieldLocation.DROPPED,ground=_drop_position(state,actor))
        index = len(state.history)
        witness = _resilience_witness(state,actor)
        return PcNpcShieldDropProof(_drop_id(state.source,actor,index),index,
            item,after,selected,enemy,_with_shield(enemy,False,**witness),**witness)
    if _ready_actor(state,CombatActionKind.IMPROVISE) is None:
        return None
    weapon = pc_npc_ranged_weapon(state, actor)
    if (item is None or item.location is not NpcShieldLocation.HELD
            or type(weapon) is not ReloadableWeaponState or weapon.loaded):
        return None
    if ranged_weapon_combat_profile(weapon.weapon_id).hands is not RangedWeaponHands.ONE_HANDED:
        raise ValueError('two-handed NPC weapon cannot acquire a Shield')
    turn = state.round_state.active_turn
    if turn.action_slots:
        if turn.action_slots[0].declaration.improvise_approach_id != reload_approach_id(weapon.weapon_instance_id):
            return None
    else:
        from towr.domain.pc_melee_result_models import pc_melee_selected_action
        if pc_melee_selected_action(state) is not CombatActionKind.IMPROVISE:
            return None
    enemy = state.enemy(actor)
    after = replace(item, location=NpcShieldLocation.DROPPED, ground=_drop_position(state, actor))
    index = len(state.history)
    witness = _resilience_witness(state,actor)
    return PcNpcShieldDropProof(_drop_id(state.source, actor, index), index,
        item, after, weapon, enemy, _with_shield(enemy, False,**witness),**witness)


def npc_shield_item_close(state, actor):
    item = npc_shield_item(state, actor)
    if item is None or item.location is not NpcShieldLocation.DROPPED:
        return False
    return (actor in item.ground.initial_close_actor_ids if state.battlefield is None else
        battlefield_range(state.battlefield, actor, item.marker_id) is RangedWeaponRange.CLOSE)


def build_npc_shield_pickup(state):
    actor = _ready_actor(state, CombatActionKind.RECOVER)
    if actor is None or not npc_shield_item_close(state, actor):
        return None
    enemy = state.enemy(actor)
    weapon = _pickup_weapon_witness(enemy)
    if weapon is None or _free_shield_hand(enemy,_champion_body(state,actor)) is None:
        return None
    item = npc_shield_item(state, actor)
    if enemy.state.holds_shield:
        raise ValueError('a dropped NPC Shield cannot already grant held protection')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action = pc_melee_action_id(state, actor)+':shield:recover'
    from towr.domain.pc_medical_models import effective_medical_injury
    effective=effective_medical_injury(state,actor)
    conditions=effective.conditions
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    target=lambda condition: (RecoverConditionTarget(actor,conditions,None)
        if conditions.has(condition) and (type(enemy.state.injury) is not CharacterInjuryState
            or not has_ongoing_condition(effective,condition)) else None)
    in_zone = (any(not state.participant(pc).injury.dead for pc in state.source.pc_activation_order)
        if state.battlefield is None else any(not state.participant(pc).injury.dead
            and state.battlefield.spatial.placement_for(pc).zone_id == state.battlefield.spatial.placement_for(actor).zone_id
            for pc in state.source.pc_activation_order))
    return RecoverActionExecutionRequest(action, state.round_state, actor, conditions, in_zone,
        1, RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState(),
            staggered_target=target(Condition.STAGGERED), prone_target=target(Condition.PRONE),
            object_interaction=RecoverObjectInteractionFollowUp(action+':pickup', actor, item.item_id, True)))


def complete_npc_shield_pickup(state, request, result):
    canonical = build_npc_shield_pickup(state)
    if canonical is None:
        raise ValueError('no actual nearby NPC Shield pickup with a free hand is available')
    _same(request, canonical, 'NPC Shield pickup changed its actual action source')
    item = npc_shield_item(state, request.actor_id)
    enemy = state.enemy(request.actor_id)
    witness = _resilience_witness(state,request.actor_id)
    injury = _standard_injury(enemy.state.injury,result,witness['champion_body'])
    return PcNpcShieldRecoverProof(request, result, item,
        replace(item, location=NpcShieldLocation.HELD, ground=None),
        _pickup_weapon_witness(enemy), enemy, _with_shield(enemy, True, injury=injury,**witness),**witness)


def _bank_update(state, item):
    if not any(previous.item_id == item.item_id for previous in state.npc_shields):
        raise ValueError('NPC Shield transition cannot invent an item outside its source bank')
    return tuple(item if previous.item_id == item.item_id else previous for previous in state.npc_shields)


def _add_marker(battlefield, item):
    if battlefield is None:
        return None
    if any(p.entity_id == item.marker_id for p in battlefield.spatial.placements):
        raise ValueError('NPC Shield already has its physical ground marker')
    placement = SpatialEntityPlacement(item.marker_id, 'objects', item.ground.zone_id)
    return replace(battlefield,spatial=replace(battlefield.spatial,
        placements=(*battlefield.spatial.placements, placement)),
        close_pairs=(*battlefield.close_pairs, *(tuple(sorted((item.marker_id, actor)))
            for actor in item.ground.initial_close_actor_ids)))


def _remove_marker(battlefield, item):
    if battlefield is None:
        return None
    marker = battlefield.spatial.placement_for(item.marker_id)
    if marker.side_id != 'objects' or marker.zone_id != item.ground.zone_id:
        raise ValueError('NPC Shield ground marker changed its physical item or position')
    return replace(battlefield,spatial=replace(battlefield.spatial,
        placements=tuple(p for p in battlefield.spatial.placements if p.entity_id != item.marker_id)),
        close_pairs=tuple(pair for pair in battlefield.close_pairs if item.marker_id not in pair))


def npc_shield_drop_updates(state, proof):
    if type(proof) is not PcNpcShieldDropProof:
        raise TypeError('NPC Shield drop requires its exact proof')
    replace(proof)
    _same(proof, expected_npc_shield_drop(state), 'NPC Shield drop differs from this current weapon or Reload window')
    return dict(npc_shields=_bank_update(state, proof.state),
        enemies=tuple(proof.enemy if enemy.state.actor_id == proof.actor_id else enemy for enemy in state.enemies),
        battlefield=_add_marker(state.battlefield, proof.state))


def npc_shield_pickup_updates(state, proof):
    if type(proof) is not PcNpcShieldRecoverProof:
        raise TypeError('NPC Shield pickup requires its exact proof')
    replace(proof)
    expected = complete_npc_shield_pickup(state, proof.request, proof.result)
    _same(proof, expected, 'NPC Shield pickup differs from this actual paid action/item')
    return dict(npc_shields=_bank_update(state, proof.state), round_state=proof.result.round_state,
        enemies=tuple(proof.enemy if enemy.state.actor_id == proof.actor_id else enemy for enemy in state.enemies),
        battlefield=_remove_marker(state.battlefield, proof.previous))


def validate_npc_shields(state):
    """Fold physical receipts, retaining item membership and real loaded witnesses.

    The action owner additionally checks each proof against its complete actual
    prefix. This bank check catches erased/reordered receipts and fake mirrors.
    """
    initial = initial_npc_shields(state.source)
    if type(state.npc_shields) is not tuple or len(state.npc_shields) != len(initial):
        raise TypeError('NPC Shield bank must retain its exact source-ordered tuple')
    bank = {item.actor_id: item for item in initial}
    units = {(enemy.state.actor_id,item.id):item
        for enemy in initial_pc_npc_weapon_inventories(state.source)
        if enemy.state.weapon_inventory is not None for item in enemy.state.weapon_inventory.items}
    weapons = {key:npc_ranged_weapon_from_unit(item) for key,item in units.items()}
    from towr.domain.pc_melee_result_models import PcAttackProof,PcHandDropProof,PcBodyConsequenceProof,PcWoundCompletionProof
    from towr.domain.pc_npc_champion_models import NpcChampionShieldDrop
    from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
    from towr.domain.pc_mount_models import PcDismountProof
    from towr.domain.pc_armour_bane_models import armour_bane_applications
    mount_sources={enemy.state.actor_id:(None if enemy.definition.generated_components is None
        or enemy.definition.generated_components.mount is None else PcMountedState(
            enemy.state.actor_id,enemy.definition.generated_components.mount,True))
        for enemy in state.source.npc_sources}
    ledgers={}
    preceding_attacks=set()
    wound_target=None
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
    from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
    from towr.domain.pc_medical_equipment_models import PcMedicalEquipmentProof,PcMedicalToolRecoverProof
    for index, proof in enumerate(state.history):
        if type(proof) is PcWoundCompletionProof:
            wound_target=proof.completion.source_request.roll.source_request.target_id
        if type(proof) in (PcHandDropProof,PcBodyConsequenceProof) and proof.npc_shield_drop is not None:
            loss=proof.npc_shield_drop
            if type(loss) is not NpcChampionShieldDrop:
                raise TypeError('Champion Shield loss needs its exact attached physical receipt')
            replace(loss)
            actor=loss.actor_id
            from towr.domain.resolution_models import TargetInjuryPolicy
            if (actor not in bank or actor!=wound_target or loss.source!=proof.source
                    or state.source.enemy(actor).definition.injury_policy is not TargetInjuryPolicy.CHAMPION):
                raise ValueError('Champion Shield loss changed its actual Wound patient or consequence')
            _same(loss.previous,bank[actor],'Champion Shield loss detached from its physical prefix')
            bank[actor]=loss.state
        if type(proof) in (PcMusicianRecoverProof,PcMedicalEquipmentProof,PcMedicalToolRecoverProof):
            replace(proof)
            proof=proof.equipment
        if type(proof) is PcMusicianEquipmentProof and proof.actor_id in bank:
            replace(proof)
            actor=proof.actor_id
            _same(proof.previous_npc_shield,bank[actor],
                'music Shield release detached from its actual source prefix')
            if proof.previous_npc_shield!=proof.npc_shield:
                if proof.history_index!=index:
                    raise ValueError('music Shield release changed its actual journal position')
                _shield_transition(proof.previous_npc_shield,proof.npc_shield,picked_up=False)
                _same(proof.previous.definition,state.source.enemy(actor).definition,
                    'music Shield release replaced its actual NPC definition')
                bank[actor]=proof.npc_shield
        if type(proof) in (PcAttackProof,PcImmediateStrikeProof):
            preceding_attacks.add(proof.request.id)
        if type(proof) is PcDismountProof and proof.actor_id in mount_sources:
            _same(proof.previous,mount_sources[proof.actor_id],
                'NPC Shield mount history differs from its actual source prefix')
            mount_sources[proof.actor_id]=proof.state
        if type(proof) is PcAttackProof and proof.npc_ranged_shot is not None:
            shot = proof.npc_ranged_shot.execution
            weapons[(shot.source_request.attack.actor_id,shot.weapon_state.weapon_instance_id)] = shot.weapon_state
            continue
        if type(proof) is PcNpcRangedReloadProof:
            weapons[(proof.request.actor_id,proof.result.state.weapon_instance_id)] = proof.result.state
            continue
        if type(proof) not in (PcNpcShieldDropProof, PcNpcShieldRecoverProof):
            continue
        replace(proof)
        actor = proof.actor_id
        if actor not in bank:
            raise ValueError('NPC Shield receipt invented a source-less item')
        if actor not in ledgers:
            ledgers[actor]=armour_bane_applications(state,actor)
        _same(proof.armour_bane_sources,tuple(application for application in ledgers[actor]
            if application.attack_id in preceding_attacks),
            'NPC Shield receipt changed its actual preceding Armour Bane sources')
        _same(proof.mount_source,mount_sources[actor],
            'NPC Shield receipt changed its actual preceding mount source')
        _same(proof.previous, bank[actor], 'NPC Shield receipt detached from its physical item prefix')
        if type(proof.weapon) is WeaponUnitState:
            key = actor,proof.weapon.id
            original = units.get(key)
            if original is None:
                raise ValueError('NPC Shield receipt invented a foreign physical weapon')
            _same(proof.weapon.source,original.source,'NPC Shield receipt changed its immutable weapon source')
            if (proof.weapon.initial_actor_id,proof.weapon.source_item_id,proof.weapon.unit_index) != (
                    original.initial_actor_id,original.source_item_id,original.unit_index):
                raise ValueError('NPC Shield receipt changed its physical weapon origin')
            _same(npc_ranged_weapon_from_unit(proof.weapon),weapons.get(key),
                'NPC Shield physical weapon detached from the actual resource prefix')
        else:
            _same(proof.weapon, weapons.get((actor,proof.weapon.weapon_instance_id)),
                'NPC Shield receipt detached from the actual reload prefix')
        _same(proof.previous_enemy.definition, state.source.enemy(actor).definition,
            'NPC Shield receipt replaced its source definition')
        if type(proof) is PcNpcShieldDropProof and (proof.history_index != index
                or proof.source_id != _drop_id(state.source, actor, index)):
            raise ValueError('NPC Shield drop changed its source history position')
        bank[actor] = proof.state
    expected = tuple(bank[item.actor_id] for item in initial)
    _same(state.npc_shields, expected, 'NPC Shield bank differs from its actual physical receipts')
    for item in state.npc_shields:
        if type(item) is not PcNpcShieldState:
            raise TypeError('NPC Shield bank requires exact typed states')
        replace(item)
        _same(npc_mount_resilience_source(state,item.actor_id),mount_sources[item.actor_id],
            'NPC Shield bank differs from its actual mount history')
        if state.enemy(item.actor_id).state.holds_shield is not (item.location is NpcShieldLocation.HELD):
            raise ValueError('NPC held Shield differs from its actual physical item state')
        inventory = state.enemy(item.actor_id).state.weapon_inventory
        if inventory is None or (inventory.shield_hand is not None) is not (item.location is NpcShieldLocation.HELD):
            raise ValueError('NPC Shield item differs from its actual occupied inventory hand')
        if state.battlefield is not None:
            markers = tuple(p for p in state.battlefield.spatial.placements if p.entity_id == item.marker_id)
            if item.location is NpcShieldLocation.DROPPED:
                if len(markers) != 1 or markers[0].side_id != 'objects' or markers[0].zone_id != item.ground.zone_id:
                    raise ValueError('dropped NPC Shield lost or moved its actual ground marker')
            elif markers:
                raise ValueError('held NPC Shield cannot retain a ground marker')
