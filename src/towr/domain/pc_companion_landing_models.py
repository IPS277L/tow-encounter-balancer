"""Wounded Pegasus landing at its next actual turn (GM176, ADR141 C16).

The original body W1 receipt owns the obligation. Changing between a ridden
body and a retained creature does not create a new wound or restart its clock.
Landing spends physical free movement; it is not Falling or another action.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.injury_models import ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest, ProfileWoundResult
from towr.domain.pc_battlefield_models import (
    PcBattlefieldState, battlefield_is_midair, battlefield_ground_below, with_actor_placement,
)
from towr.domain.pc_companion_models import PcMountCompanionState
from towr.domain.pc_mount_companion_sources import MountCompanionProfile
from towr.domain.pc_mount_models import CombatMount, PcMountedState
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.turn_models import CombatRoundState, CombatTurnStartRequest, CombatTurnStartResult, CombatTurnState


COMPANION_LANDING_RULE_ID = 'BOOK-GM-GUIDE:1.1:p176:pegasus-wound-landing'


def _same(actual, expected, message):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual != expected:
        raise ValueError(message)
    validate_pc_melee_source_types(actual, expected)


def _turn_start(source):
    if (type(source) is not CombatTurnStartResult or type(source.state) is not CombatRoundState
            or type(source.turn) is not CombatTurnState):
        raise TypeError('landing clock requires its exact actual turn-start receipt')
    replace(source.state); replace(source.turn)
    if source.state.active_turn != source.turn:
        raise ValueError('landing clock lost its actual started turn')
    from towr.rules.turn_resolution import start_combat_turn
    expected = start_combat_turn(CombatTurnStartRequest(source.request_id,
        replace(source.state, active_turn=None), source.turn.actor_id))
    _same(source, expected, 'landing clock is not its actual canonical turn start')


def _bound_wound(receipt, producer, body_id):
    """Return only a genuine source-bound own Brute0→1 Wound result."""
    from towr.domain.pc_melee_result_models import PcProfileWoundProof
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types, pc_kernel_resolution
    from towr.domain.pc_blunderbuss_models import PcBlunderbussProfileProof, PcBlunderbussTargetProof
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof, PcWarpedFormTargetProof
    from towr.domain.pc_cleaving_blow_models import PcCleavingProfileProof, PcCleavingTargetProof
    from towr.domain.pc_weapon_area_models import PcWeaponHazardProof
    from towr.domain.pc_magic_models import PcMagicEffectProof
    from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind
    from towr.domain.resolution_models import StaggerImpactResult
    change = None
    if type(receipt) is PcProfileWoundProof:
        if type(producer) not in pc_kernel_attack_types() or producer.request.target_id != body_id:
            return None
        result = pc_kernel_resolution(producer).profile_wound
        request = producer.request.kernel_request
        previous, policy = request.target_state, request.target_policy
        change = receipt.source
    elif type(receipt) is PcBlunderbussProfileProof:
        if (type(producer) is not PcBlunderbussTargetProof or receipt.target_id != body_id
                or producer.request.target_id != body_id or producer.resolution_id != receipt.resolution_id):
            return None
        result, previous, policy = producer.result.profile_wound, producer.request.target_state, producer.request.target_policy
        change = receipt.source
    elif type(receipt) is PcWarpedFormProfileProof:
        if (type(producer) is not PcWarpedFormTargetProof or receipt.target_id != body_id
                or producer.request.target_id != body_id or producer.activation_id != receipt.activation_id):
            return None
        result, previous, policy = producer.result.profile_wound, producer.request.target_state, producer.request.target_policy
        change = receipt.source
    elif type(receipt) is PcCleavingProfileProof:
        if (type(producer) is not PcCleavingTargetProof or receipt.target_id != body_id
                or producer.request.target_id != body_id or producer.wave_id != receipt.wave_id):
            return None
        result, previous, policy = producer.result.profile_wound, producer.request.target_state, producer.request.target_policy
        change = receipt.source
    elif type(receipt) is PcWeaponHazardProof:
        if receipt.request.actor_id != body_id or type(producer) is not PcWeaponHazardProof or receipt != producer:
            return None
        result, previous, policy = receipt.result.profile_wound, receipt.request.target_injury, receipt.request.target_policy
    elif type(receipt) is PcMagicEffectProof:
        if (type(producer) is not PcMagicEffectProof or receipt != producer
                or type(receipt.task) is not PcMagicTask or receipt.task.target_id != body_id):
            return None
        replace(receipt.task)
        if type(receipt.result) is ProfileWoundResult:
            if (receipt.task.kind not in (PcMagicTaskKind.DAMAGE, PcMagicTaskKind.FIXED_EARS,
                    PcMagicTaskKind.RANDOM_WOUND)
                    or receipt.result.request_id != receipt.task.id+':wound'):
                return None
            result = receipt.result
        elif type(receipt.result) is StaggerImpactResult:
            if (receipt.task.kind not in (PcMagicTaskKind.DAMAGE, PcMagicTaskKind.STAGGER)
                    or receipt.result.request_id != receipt.task.id):
                return None
            result = receipt.result.profile_wound
        else:
            return None
        if result is None:
            return None
        previous = receipt.previous_injury
        if type(previous) is not ProfileInjuryState:
            raise TypeError('a companion magic W1 must preserve its exact own previous injury')
        policy = TargetInjuryPolicy.BRUTE
        if receipt.decision is not None and result is not None and not result.state.defeated:
            raise ValueError('a surviving Pegasus magic W1 cannot invent a defeat decision')
    else:
        return None
    if result is None:
        return None
    if (type(result) is not ProfileWoundResult or type(result.state_change) is not ProfileStateChangeRequest
            or type(previous) is not ProfileInjuryState or type(result.state) is not ProfileInjuryState):
        raise TypeError('Pegasus landing requires the exact own profile Wound source and result')
    replace(result); replace(result.state_change); replace(previous); replace(result.state)
    actual = result.state_change
    if change is not None:
        _same(change, actual, 'landing W1 acknowledgement changed its actual producing Wound')
        if receipt.decision is not None:
            raise ValueError('a surviving Pegasus W1 cannot invent a defeat decision')
    if (type(actual.previous_wounds) is not int or type(actual.current_wounds) is not int
            or type(actual.defeated) is not bool or type(actual.npc_type) is not ProfileNpcType):
        raise TypeError('landing W1 needs exact profile-change fields')
    if (policy is not TargetInjuryPolicy.BRUTE or actual.npc_type is not ProfileNpcType.BRUTE
            or actual.previous_wounds != 0 or actual.current_wounds != 1 or actual.defeated
            or previous.wounds != 0 or previous.wound_limit != 2 or previous.defeated
            or result.state.wounds != 1 or result.state.wound_limit != 2 or result.state.defeated):
        return None
    return result


def _wound_events(history, body_id):
    from towr.domain.pc_melee_result_models import PcProfileWoundProof
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types
    from towr.domain.pc_blunderbuss_models import PcBlunderbussProfileProof, PcBlunderbussTargetProof
    from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof, PcWarpedFormTargetProof
    from towr.domain.pc_cleaving_blow_models import PcCleavingProfileProof, PcCleavingTargetProof
    from towr.domain.pc_weapon_area_models import PcWeaponHazardProof
    from towr.domain.pc_magic_models import PcMagicEffectProof
    events = []
    for index, receipt in enumerate(history):
        producer_index = None
        if type(receipt) is PcProfileWoundProof:
            producer_index = next((i for i in range(index-1, -1, -1)
                if type(history[i]) in pc_kernel_attack_types()), None)
        elif type(receipt) is PcBlunderbussProfileProof:
            producer_index = next((i for i in range(index-1, -1, -1)
                if type(history[i]) is PcBlunderbussTargetProof
                and history[i].resolution_id == receipt.resolution_id
                and history[i].request.target_id == receipt.target_id), None)
        elif type(receipt) is PcWarpedFormProfileProof:
            producer_index = next((i for i in range(index-1, -1, -1)
                if type(history[i]) is PcWarpedFormTargetProof
                and history[i].activation_id == receipt.activation_id
                and history[i].request.target_id == receipt.target_id), None)
        elif type(receipt) is PcCleavingProfileProof:
            producer_index = next((i for i in range(index-1, -1, -1)
                if type(history[i]) is PcCleavingTargetProof
                and history[i].wave_id == receipt.wave_id
                and history[i].request.target_id == receipt.target_id), None)
        elif type(receipt) in (PcWeaponHazardProof, PcMagicEffectProof):
            producer_index = index
        if producer_index is not None and _bound_wound(receipt, history[producer_index], body_id) is not None:
            events.append((index, receipt, producer_index, history[producer_index]))
    return tuple(events)


def _first_body_turn(history, wound_index, rider_id, body_id):
    from towr.domain.pc_mount_models import PcDismountProof
    from towr.domain.pc_mount_retention_models import PcMountRetentionProof
    from towr.domain.pc_back_in_saddle_models import BACK_IN_SADDLE_REMOUNT_PROOFS
    mounted, retained = True, False
    for index, receipt in enumerate(history):
        if type(receipt) is PcDismountProof and receipt.actor_id == rider_id:
            mounted = False
        elif type(receipt) is PcMountRetentionProof and receipt.source.actor_id == rider_id:
            retained = True
        elif type(receipt) in BACK_IN_SADDLE_REMOUNT_PROOFS and receipt.actor_id == rider_id:
            mounted, retained = True, False
        if index > wound_index and type(receipt) is CombatTurnStartResult:
            owner = rider_id if mounted else body_id if retained else None
            if receipt.turn.actor_id == owner:
                _turn_start(receipt)
                return index, receipt
    return None


def _landing_battlefield(before, actor):
    if not battlefield_is_midair(before, actor):
        raise ValueError('landing requires its actual airborne physical actor')
    if actor in before.spatial.free_move_used_entity_ids:
        raise ValueError('mandatory landing requires this actual turn\'s unspent free movement')
    origin = before.spatial.placement_for(actor).zone_id
    after = with_actor_placement(before, actor, battlefield_ground_below(before, origin))
    return replace(after, spatial=replace(after.spatial,
        free_move_used_entity_ids=(*before.spatial.free_move_used_entity_ids, actor)))


@dataclass(frozen=True, slots=True)
class PcCompanionLandingProof:
    actor_id: str
    source_body: PcMountCompanionState
    profile: MountCompanionProfile
    mount_source: PcMountedState
    wound_receipt_index: int
    wound_receipt: object
    wound_producer_index: int
    wound_producer: object
    turn_start_index: int
    turn_start: CombatTurnStartResult
    source_round: CombatRoundState
    history_index: int
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState
    rule_id: str = COMPANION_LANDING_RULE_ID

    @property
    def body_id(self): return self.source_body.snapshot.state.actor_id

    @property
    def rider_id(self): return self.source_body.rider_id

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('landing requires its exact physical actor identifier')
        for value, kind in ((self.source_body, PcMountCompanionState), (self.profile, MountCompanionProfile),
                (self.mount_source, PcMountedState), (self.source_round, CombatRoundState),
                (self.previous_battlefield, PcBattlefieldState), (self.battlefield, PcBattlefieldState)):
            if type(value) is not kind:
                raise TypeError('landing requires exact body, mount, clock and geometry sources')
            replace(value)
        if (type(self.rule_id) is not str or self.rule_id != COMPANION_LANDING_RULE_ID
                or self.profile.kind is not CombatMount.PEGASUS or self.mount_source.mount is not CombatMount.PEGASUS
                or self.mount_source.actor_id != self.rider_id):
            raise ValueError('landing requires this real Pegasus and its exact GM176 rule')
        _same(self.source_body.snapshot.definition, self.profile.definition,
            'landing changed the own canonical Pegasus body')
        injury = self.source_body.snapshot.state.injury
        if injury.wounds != 1 or injury.defeated:
            raise ValueError('only the surviving W1 Pegasus owes this landing')
        owner = self.rider_id if self.mount_source.mounted else self.body_id
        if (self.actor_id != owner or (self.mount_source.mounted and self.source_body.retained_since_round is not None)
                or (not self.mount_source.mounted and self.source_body.retained_since_round is None)):
            raise ValueError('landing changed the actual mounted/detached physical owner')
        indices = (self.wound_producer_index, self.wound_receipt_index, self.turn_start_index, self.history_index)
        if any(type(index) is not int or index < 0 for index in indices):
            raise TypeError('landing provenance requires exact nonnegative history positions')
        if not self.wound_producer_index <= self.wound_receipt_index < self.turn_start_index < self.history_index:
            raise ValueError('landing clock must follow the actual own W1 receipt')
        if _bound_wound(self.wound_receipt, self.wound_producer, self.body_id) is None:
            raise ValueError('landing cannot replace the actual own W1 producing receipt')
        _turn_start(self.turn_start)
        if (self.source_round.active_turn is None or self.source_round.active_turn.actor_id != self.actor_id
                or self.turn_start.turn.actor_id != self.actor_id
                or self.turn_start.state.round_number != self.source_round.round_number
                or self.previous_battlefield.spatial.round_number != self.source_round.round_number):
            raise ValueError('landing must use the actual post-W1 owner turn and spatial round')
        _same(self.battlefield, _landing_battlefield(self.previous_battlefield, self.actor_id),
            'landing changed position, Close links or more than its one free movement')


def expected_companion_landing(state):
    if (state.battlefield is None or state.source.battlefield is None or state.source.battlefield.airspace is None
            or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or state.round_state.active_turn is None):
        return None
    if type(state.history) is not tuple:
        raise TypeError('landing requires its exact actual ordered history')
    completed = set()
    for index, receipt in enumerate(state.history):
        if type(receipt) is PcCompanionLandingProof:
            replace(receipt)
            if (receipt.history_index != index or receipt.wound_receipt != state.history[receipt.wound_receipt_index]
                    or receipt.wound_producer != state.history[receipt.wound_producer_index]
                    or receipt.turn_start != state.history[receipt.turn_start_index]):
                raise ValueError('landing history changed its original body W1 or actual turn start')
            key = receipt.body_id, receipt.wound_receipt_index
            if key in completed:
                raise ValueError('the same Pegasus wound cannot require two landings')
            completed.add(key)
    from towr.domain.pc_companion_effect_models import companion_profile
    for body in state.companions:
        injury = body.snapshot.state.injury
        if injury.wounds != 1 or injury.defeated:
            continue
        mount = next(row for row in state.mounts if row.actor_id == body.rider_id)
        if mount.mount is not CombatMount.PEGASUS or (not mount.mounted and body.retained_since_round is None):
            continue
        actor = body.rider_id if mount.mounted else body.snapshot.state.actor_id
        if actor != state.round_state.active_turn.actor_id or not battlefield_is_midair(state.battlefield, actor):
            continue
        events = _wound_events(state.history, body.snapshot.state.actor_id)
        if not events:
            continue  # A prepared HP observation is not an actual W1/clock source.
        wound_index, wound, producer_index, producer = events[-1]
        if (body.snapshot.state.actor_id, wound_index) in completed:
            continue
        clock = _first_body_turn(state.history, wound_index, body.rider_id, body.snapshot.state.actor_id)
        if clock is None:
            continue
        clock_index, turn_start = clock
        if (turn_start.turn.actor_id != actor or turn_start.state.round_number != state.round_state.round_number):
            raise ValueError('an overdue Pegasus landing cannot restart on a different owner turn')
        return PcCompanionLandingProof(actor, body, companion_profile(state, body.snapshot.state.actor_id), mount,
            wound_index, wound, producer_index, producer, clock_index, turn_start, state.round_state,
            len(state.history), state.battlefield, _landing_battlefield(state.battlefield, actor))
    return None


def project_companion_landing(state, proof):
    if type(proof) is not PcCompanionLandingProof:
        raise TypeError('Pegasus landing requires its exact typed receipt')
    replace(proof)
    _same(proof, expected_companion_landing(state),
        'Pegasus landing changed its actual wound, clock, body, geometry or once budget')
    return dict(battlefield=proof.battlefield)
