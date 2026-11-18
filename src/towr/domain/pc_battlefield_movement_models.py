"""Source-bound incidental movement in the explicit open encounter battlefield."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState, WoundRestriction
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, FreeMovementResult, MovementSpeed
from towr.domain.pc_battlefield_models import (
    PcBattlefieldState, battlefield_range, build_pc_battlefield, with_actor_placement,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId, RangedWeaponRange, RangedWeaponHands, ranged_weapon_combat_profile,
)
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult,
    RecoverConditionTarget, RecoverMode, RecoverStandardChoice,
)
from towr.domain.reload_models import ranged_weapon_is_loaded
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatRoundAdvanceResult, CombatRoundState
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.spatial_resolution import start_next_spatial_round

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


def _rank(value):
    return tuple(RangedWeaponRange).index(value)


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('battlefield transition needs exact nonempty identifiers')


def _conditions(state, actor):
    return (state.participant(actor).injury.conditions if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury.conditions)


def _enemies(state, actor):
    if actor in state.source.pc_activation_order:
        live = {enemy.state.actor_id for enemy in state.live_enemies}
        return tuple(target for target in state.source.participant(actor).target_priority if target in live)
    if actor in state.source.enemy_activation_order:
        live = {member.actor_id for member in state.live_party}
        return tuple(target for target in state.source.enemy_target_priority if target in live)
    raise ValueError('battlefield actor must belong to the complete encounter')


def _has_close_enemy(state, actor):
    if state.battlefield is None:
        from towr.domain.pc_short_opening_models import pc_has_close_enemy
        return pc_has_close_enemy(state,actor)
    return any(battlefield_range(state.battlefield, actor, target) is RangedWeaponRange.CLOSE
        for target in _enemies(state, actor))


def pc_battlefield_allows_outnumbering(state: PcMeleeState, actor: str) -> bool:
    """Compare able participants in the actor's actual Zone, or the legacy arena."""
    def same_zone(actor_id):
        return (state.battlefield is None or state.battlefield.spatial.placement_for(actor_id).zone_id
            == state.battlefield.spatial.placement_for(actor).zone_id)
    party = sum(not member.injury.conditions.has(Condition.DEFENCELESS) and same_zone(member.actor_id)
        for member in state.live_party)
    enemies = sum(not enemy.state.injury.conditions.has(Condition.DEFENCELESS) and same_zone(enemy.state.actor_id)
        for enemy in state.live_enemies)
    if actor in state.source.pc_activation_order:
        return party > enemies
    if actor in state.source.enemy_activation_order:
        return enemies > party
    raise ValueError('outnumbering requires an actual encounter actor')


def _ranges(state, actor, weapon=None):
    """Return preferred min/max, legal max and whether Close shooting is allowed."""
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS, PC_THROWING_WEAPONS, PcMeleeWeapon
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_backup_weapon_models import pc_active_weapon
        selected = pc_active_weapon(state, actor) if weapon is None else weapon
        if selected in PC_THROWING_WEAPONS:
            from towr.domain.pc_potion_models import pc_effective_definition
            maximum=(RangedWeaponRange.MEDIUM if pc_effective_definition(state,actor).strength>=4
                else RangedWeaponRange.SHORT)
            return RangedWeaponRange.CLOSE,maximum,maximum,True
        if selected not in PC_RANGED_WEAPONS:
            maximum = (RangedWeaponRange.SHORT if selected in (
                PcMeleeWeapon.FOOT_SPEAR, PcMeleeWeapon.POLEARM) else RangedWeaponRange.CLOSE)
            return RangedWeaponRange.CLOSE, maximum, maximum, True
        profile = ranged_weapon_combat_profile(RangedWeaponId(selected.value))
    else:
        from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
        selected = pc_selected_npc_attack_profile(state, actor)
        if selected.skill is not Skill.SHOOTING:
            return selected.range_min, selected.range_max, selected.range_max, True
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
        profile = ranged_weapon_combat_profile(pc_npc_ranged_profile(state.enemy(actor).definition).weapon_id)
    maximum = profile.maximum_range or state.source.battlefield.two_handed_max_range
    if profile.hands is RangedWeaponHands.TWO_HANDED:
        maximum=min(maximum,state.source.battlefield.two_handed_max_range,key=_rank)
    preferred_max = min(profile.optimum_range_max, maximum, key=_rank)
    preferred_min = min(profile.optimum_range_min, preferred_max, key=_rank)
    return preferred_min, preferred_max, maximum, profile.optimum_range_min is RangedWeaponRange.CLOSE


def pc_battlefield_attack_available(state: PcMeleeState, actor: str, target: str,
        *, weapon=None) -> bool:
    """Range eligibility only; actual tests/hands/charge still belong to their owners."""
    if state.source.battlefield is None:
        return True
    if state.battlefield is None:
        raise ValueError('configured battlefield must retain its actual spatial state')
    if target not in _enemies(state, actor):
        return False
    _, _, maximum, allows_close = _ranges(state, actor, weapon)
    actual = battlefield_range(state.battlefield, actor, target)
    return (_rank(actual) <= _rank(maximum)
        and (allows_close or not _has_close_enemy(state, actor)))


def _zone_distance(graph, first, second):
    if first == second:
        return 0
    seen = {first}
    queue = deque(((first, 0),))
    while queue:
        current, count = queue.popleft()
        for adjacent in graph.adjacent_zone_ids(current):
            if adjacent in seen:
                continue
            if adjacent == second:
                return count+1
            seen.add(adjacent)
            queue.append((adjacent, count+1))
    raise ValueError('battlefield route requires connected Zones')


@dataclass(frozen=True, slots=True)
class PcBattlefieldMoveProof:
    actor_id: str
    action_id: str
    target_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    actor_conditions: ConditionState
    speed: MovementSpeed
    close_to_ids: tuple[str, ...]
    movement_request: FreeMovementRequest | None
    movement_result: FreeMovementResult | None
    state: PcBattlefieldState

    def __post_init__(self):
        for value in (self.actor_id, self.action_id, self.target_id):
            _identifier(value)
        if (type(self.source_round) is not CombatRoundState or type(self.previous) is not PcBattlefieldState
                or type(self.state) is not PcBattlefieldState or type(self.actor_conditions) is not ConditionState
                or type(self.speed) is not MovementSpeed):
            raise TypeError('movement proof requires exact round, battlefield, Conditions and Speed')
        replace(self.source_round); replace(self.previous); replace(self.state)
        turn = self.source_round.active_turn
        if (turn is None or turn.actor_id != self.actor_id or turn.action_slots
                or self.source_round.round_number != self.previous.spatial.round_number):
            raise ValueError('movement belongs to its active unreserved turn and spatial round')
        if type(self.close_to_ids) is not tuple or self.close_to_ids not in ((), (self.target_id,)):
            raise ValueError('movement declares only its one chosen Close target')
        if self.actor_conditions.has(Condition.DEFENCELESS):
            raise ValueError('Defenceless forbids movement')
        if self.movement_request is None:
            if self.movement_result is not None:
                raise ValueError('within-Zone approach is distinct from a K1 Zone move')
            distance=battlefield_range(self.previous,self.actor_id,self.target_id)
            if not ((distance is RangedWeaponRange.SHORT and self.close_to_ids==(self.target_id,))
                    or (distance is RangedWeaponRange.CLOSE and not self.close_to_ids)):
                raise ValueError('within-Zone reposition must bind actual Short/Close separation')
            spatial = self.previous.spatial
            destination = spatial.placement_for(self.actor_id).zone_id
        else:
            if type(self.movement_request) is not FreeMovementRequest or type(self.movement_result) is not FreeMovementResult:
                raise TypeError('cross-Zone movement requires its complete K1 source and result')
            request = self.movement_request
            replace(request)
            if (request.id != self.action_id or request.actor_id != self.actor_id
                    or request.round_state != self.source_round or request.state != self.previous.spatial
                    or request.actor_conditions != self.actor_conditions or request.speed is not self.speed
                    or self.movement_result != resolve_free_movement(request)):
                raise ValueError('movement changed its actual K1 source, route, Conditions or result')
            spatial = self.movement_result.state
            destination = request.destination_zone_id
        expected = with_actor_placement(replace(self.previous, spatial=spatial),
            self.actor_id, destination, close_to_ids=self.close_to_ids)
        if self.state != expected:
            raise ValueError('movement changed another placement, Close link or usage')


def expected_pc_battlefield_move(state: PcMeleeState) -> PcBattlefieldMoveProof | None:
    """One deterministic incidental positioning choice; no tactical/RNG recursion."""
    if (state.source.battlefield is None or state.pending or state.pending_wound is not None
            or state.magic_pending is not None or not state.live_party or not state.live_enemies):
        return None
    turn = state.round_state.active_turn
    if turn is None or turn.action_slots:
        return None
    from towr.domain.pc_battlefield_manoeuvre_models import proposed_pc_battlefield_manoeuvre
    from towr.domain.turn_models import ManoeuvreKind
    proposal=proposed_pc_battlefield_manoeuvre(state)
    if proposal is not None and proposal.kind is ManoeuvreKind.CHARGE:
        return None
    actor = turn.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        if usable_weapon_hand(state.participant(actor)) is None:
            return None  # A missing/unusable held weapon cannot supply a ranged shot.
    from towr.domain.pc_weighted_net_models import weighted_net_has_usable_attack
    if not weighted_net_has_usable_attack(state,actor):
        return None
    conditions = _conditions(state, actor)
    if any(conditions.has(condition) for condition in (Condition.DEFENCELESS, Condition.PRONE, Condition.BROKEN)):
        return None  # This approach policy recovers/follows mandatory work first.
    if any(type(proof) is PcBattlefieldMoveProof and proof.actor_id == actor
            and proof.source_round.round_number == state.round_state.round_number for proof in state.history):
        return None  # One positioning decision, not a fabricated K1 movement spend.
    close_enemy=_has_close_enemy(state,actor)
    targets = _enemies(state, actor)
    if not targets:
        return None
    low, high, _, allows_close = _ranges(state, actor)
    retreat=close_enemy and not allows_close
    if close_enemy and not retreat:
        return None
    if not retreat and any(_rank(low) <= _rank(battlefield_range(state.battlefield, actor, target)) <= _rank(high)
            for target in targets):
        return None
    target=(next(target for target in targets if battlefield_range(state.battlefield,actor,target)
        is RangedWeaponRange.CLOSE) if retreat else targets[0])
    previous = state.battlefield
    spatial = previous.spatial
    origin = spatial.placement_for(actor).zone_id
    target_zone = spatial.placement_for(target).zone_id
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action_id = pc_melee_action_id(state, actor)+':battlefield:move'
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    speed=pc_battlefield_actor_speed(state,actor)
    if retreat and high is RangedWeaponRange.SHORT:
        return PcBattlefieldMoveProof(actor,action_id,target,state.round_state,
            previous,conditions,speed,(),None,None,with_actor_placement(previous,actor,origin))
    if origin == target_zone and high is RangedWeaponRange.CLOSE:
        return PcBattlefieldMoveProof(actor, action_id, target, state.round_state,
            previous, conditions, speed, (target,), None, None,
            with_actor_placement(previous, actor, origin, close_to_ids=(target,)))
    if actor in spatial.free_move_used_entity_ids:
        return None
    def deviation(zone):
        distance = _zone_distance(spatial.graph, zone, target_zone)+1
        if distance == 1 and high is RangedWeaponRange.CLOSE:
            distance = 0  # Arriving at this chosen melee target establishes Close explicitly.
        return max(_rank(low)-distance, 0, distance-_rank(high))
    options=[]
    queue=deque(((origin,()),))
    while queue:
        current,route=queue.popleft()
        if len(route)==speed.free_move_zone_limit:
            continue
        for adjacent in spatial.graph.adjacent_zone_ids(current):
            if adjacent==origin or adjacent in route:
                continue
            extended=(*route,adjacent)
            options.append(extended)
            queue.append((adjacent,extended))
    route=min(options,key=lambda path:deviation(path[-1]))
    destination=route[-1]
    origin_deviation=(max(_rank(low),0,-_rank(high)) if retreat else deviation(origin))
    if deviation(destination) >= origin_deviation:
        return None
    request = FreeMovementRequest(action_id, state.round_state, spatial, actor,
        speed, conditions, route)
    result = resolve_free_movement(request)
    close = (target,) if destination == target_zone and high is RangedWeaponRange.CLOSE else ()
    after = with_actor_placement(replace(previous, spatial=result.state), actor,
        destination, close_to_ids=close)
    return PcBattlefieldMoveProof(actor, action_id, target, state.round_state,
        previous, conditions, speed, close, request, result, after)


def pc_battlefield_after_proof(current: PcBattlefieldState,proof) -> PcBattlefieldState:
    """Fold actual spatial receipts; shared by the owner and HIT snapshots."""
    from towr.domain.pc_battlefield_manoeuvre_models import BATTLEFIELD_MANOEUVRE_PROOFS
    from towr.domain.pc_weighted_net_models import NET_PROOFS
    for drop in getattr(proof,'weighted_net_drops',()):
        replace(drop)
        if drop.previous!=current:
            raise ValueError('Net drop changed its actual spatial prefix')
        current=drop.state
    landing=getattr(proof,'weighted_net_landing',None)
    if landing is not None:
        replace(landing)
        if landing.previous!=current:
            raise ValueError('Net throw changed its actual spatial prefix')
        current=landing.state
    if type(proof) in NET_PROOFS:
        replace(proof)
        if proof.previous!=current:
            raise ValueError('Net interaction changed its actual spatial prefix')
        return proof.state
    if type(proof) in (PcBattlefieldMoveProof,*BATTLEFIELD_MANOEUVRE_PROOFS):
        replace(proof)
        if proof.previous != current:
            raise ValueError('movement must extend the complete actual spatial prefix')
        return proof.state
    if type(proof) is CombatRoundAdvanceResult:
        return replace(current,spatial=start_next_spatial_round(current.spatial))
    return current


def validate_pc_battlefield_history(state: PcMeleeState) -> None:
    from towr.domain.pc_battlefield_manoeuvre_models import BATTLEFIELD_MANOEUVRE_PROOFS
    if state.source.battlefield is None:
        if state.battlefield is not None or any(type(p) in (PcBattlefieldMoveProof,*BATTLEFIELD_MANOEUVRE_PROOFS)
                for p in state.history):
            raise ValueError('legacy encounter cannot acquire battlefield state or movement')
        return
    expected = build_pc_battlefield(state.source.battlefield, state.source.pc_activation_order,
        state.source.enemy_activation_order, state.source.facts.zone_id)
    for proof in state.history:
        expected=pc_battlefield_after_proof(expected,proof)
    if (type(state.battlefield) is not PcBattlefieldState or state.battlefield != expected
            or state.battlefield.spatial.round_number != state.round_state.round_number):
        raise ValueError('battlefield differs from its source, movement history or round usage')


def pc_battlefield_npc_recover_selected(state: PcMeleeState) -> bool:
    if state.round_state.active_turn is None:
        return False
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.enemy_activation_order:
        return False
    from towr.domain.pc_weighted_net_models import weighted_net_actor_waits
    net_wait=weighted_net_actor_waits(state,actor)
    if state.source.battlefield is None and not net_wait:
        return False
    conditions = _conditions(state, actor)
    if conditions.has(Condition.DEFENCELESS):
        return False
    if conditions.has(Condition.PRONE):
        return True  # Stand before the existing empty-weapon Reload cycle.
    if net_wait:
        return True
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    weapon = pc_npc_ranged_weapon(state, actor)
    if weapon is not None and not ranged_weapon_is_loaded(weapon):
        return False  # The existing real Reload action remains available.
    from towr.domain.pc_battlefield_manoeuvre_models import proposed_pc_battlefield_manoeuvre
    if proposed_pc_battlefield_manoeuvre(state) is not None:
        return False
    return not any(
        pc_battlefield_attack_available(state, actor, target) for target in _enemies(state, actor))


def build_pc_battlefield_npc_recover(state: PcMeleeState) -> RecoverActionExecutionRequest:
    if not pc_battlefield_npc_recover_selected(state):
        raise ValueError('no actual battlefield NPC Recover is selected')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = state.round_state.active_turn.actor_id
    conditions = state.enemy(actor).state.injury.conditions
    def target(condition):
        return RecoverConditionTarget(actor, conditions, None) if conditions.has(condition) else None
    return RecoverActionExecutionRequest(pc_melee_action_id(state, actor)+':battlefield:recover',
        state.round_state, actor, conditions, _has_close_enemy(state, actor), 1,
        RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState(),
            staggered_target=target(Condition.STAGGERED), prone_target=target(Condition.PRONE)))


def battlefield_recovered_injury(before, result):
    conditions = before.conditions
    for change in result.resolution.condition_changes:
        conditions = change.conditions
    return replace(before, conditions=conditions)


@dataclass(frozen=True, slots=True)
class PcBattlefieldRecoverProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    previous_injury: ProfileInjuryState
    injury: ProfileInjuryState

    @property
    def actor_id(self):
        return self.request.actor_id

    def __post_init__(self):
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        if (type(self.request) is not RecoverActionExecutionRequest
                or type(self.result) is not RecoverActionExecutionResult
                or type(self.previous_injury) is not ProfileInjuryState or type(self.injury) is not ProfileInjuryState):
            raise TypeError('battlefield Recover requires exact action and profile injury witnesses')
        replace(self.request)
        if (self.request.actor_conditions != self.previous_injury.conditions
                or self.result != expected_pc_standard_recover(self.request)
                or self.request.choice.object_interaction is not None
                or self.injury != battlefield_recovered_injury(self.previous_injury, self.result)):
            raise ValueError('battlefield Recover changed its source, receipt or non-healing benefits')
