"""Source-bound stand/remount at the actual steed (PG73/124, ADR141 C15)."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState, WoundConditionEffect, WoundEffectDuration, WoundRestriction
from towr.domain.movement_models import FreeMoveProneRemovalRequest, FreeMoveProneRemovalResult, ProneRemovalTargetKind
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update, pc_opponent_ids
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range, _close_key
from towr.domain.pc_companion_models import PcMountCompanionState
from towr.domain.pc_mount_models import PcMountedState
from towr.domain.pc_mount_retention_models import actor_back_in_saddle_source
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_back_in_saddle_models import BackInSaddleSource
from towr.domain.turn_models import CombatRoundState
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.domain.recover_models import RecoverActionExecutionResult, RecoverConditionTarget, RecoverMountFollowUp
from towr.domain.talent_back_in_saddle_models import BACK_IN_SADDLE_RULE_ID
from towr.domain.pc_companion_usage_models import capture_companion_usage


def _remounted_body(row, battlefield):
    return replace(row, retained_since_round=None,
        stored_spatial_usage=capture_companion_usage(battlefield, row.snapshot.state.actor_id))


def available_remount(state, actor):
    source = actor_back_in_saddle_source(state, actor)
    if source is None or state.battlefield is None:
        return None
    row = next(row for row in state.companions if row.rider_id == actor)
    mount = next(mount for mount in state.mounts if mount.actor_id == actor)
    if mount.mounted or row.retained_since_round is None:
        return None
    body, rider = row.snapshot.state.injury, pc_actor_injury(state, actor)
    if (body.defeated or any(body.conditions.has(c) for c in (Condition.PRONE, Condition.DEFENCELESS))
            or getattr(rider, 'dead', False) or getattr(rider, 'defeated', False)
            or any(rider.conditions.has(c) for c in (Condition.DEFENCELESS, Condition.BROKEN))):
        return None
    if battlefield_range(state.battlefield, actor, source.mount_id) is not RangedWeaponRange.CLOSE:
        return None
    if type(rider) is CharacterInjuryState:
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        if has_ongoing_condition(rider, Condition.PRONE):
            return None
    return source, row, mount


def configure_back_in_saddle_recover(state, actor, action_id, choice):
    available = available_remount(state, actor)
    if available is None:
        return choice
    source, _, _ = available
    injury = pc_actor_injury(state, actor)
    prone = injury.conditions.has(Condition.PRONE)
    # PG118 still permits either mounting or removing another creature's Prone.
    # The PG73 waiver applies to this rider's own combined stand/remount only.
    return replace(choice, prone_target=RecoverConditionTarget(actor, injury.conditions, None) if prone else None,
        mount=RecoverMountFollowUp(action_id+':remount', actor, source.mount_id, True, False,
            rule_id=BACK_IN_SADDLE_RULE_ID), back_in_saddle_source=source if prone else None)


def _mounted_battlefield(before, actor, companion, *, spend_free_move):
    spatial = before.spatial
    free = tuple(entity for entity in spatial.free_move_used_entity_ids if entity != companion)
    if spend_free_move:
        if actor in free:
            raise ValueError('remount cannot spend free movement twice')
        free = (*free, actor)
    neighbours = tuple(second if first == companion else first for first, second in before.close_pairs
        if companion in (first, second) and actor not in (first, second))
    pairs = tuple(pair for pair in before.close_pairs if companion not in pair and actor not in pair)
    pairs = (*pairs, *(_close_key(actor, other) for other in neighbours))
    return replace(before, spatial=replace(spatial,
        placements=tuple(row for row in spatial.placements if row.entity_id != companion),
        free_move_used_entity_ids=free,
        gave_ground_entity_ids=tuple(entity for entity in spatial.gave_ground_entity_ids if entity != companion),
        difficult_terrain_tested_entity_ids=tuple(entity for entity in spatial.difficult_terrain_tested_entity_ids
            if entity != companion)), close_pairs=pairs)


@dataclass(frozen=True, slots=True)
class PcBackInSaddleMoveProof:
    source: BackInSaddleSource
    source_round: CombatRoundState
    history_index: int
    previous_mount: PcMountedState
    mount: PcMountedState
    previous_body: PcMountCompanionState
    body: PcMountCompanionState
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState
    previous_injury: CharacterInjuryState | ProfileInjuryState
    injury: CharacterInjuryState | ProfileInjuryState
    stand_request: FreeMoveProneRemovalRequest | None
    stand_result: FreeMoveProneRemovalResult | None

    @property
    def actor_id(self): return self.source.actor_id

    def __post_init__(self):
        for value, cls in ((self.source, BackInSaddleSource), (self.source_round, CombatRoundState),
                (self.previous_mount, PcMountedState), (self.mount, PcMountedState),
                (self.previous_body, PcMountCompanionState), (self.body, PcMountCompanionState),
                (self.previous_battlefield, PcBattlefieldState), (self.battlefield, PcBattlefieldState)):
            if type(value) is not cls:
                raise TypeError('stand/remount requires its exact source, body, clock and spatial witnesses')
            replace(value)
        if type(self.history_index) is not int or self.history_index < 0:
            raise ValueError('stand/remount requires its actual nonnegative history position')
        if (type(self.previous_injury) not in (CharacterInjuryState, ProfileInjuryState)
                or type(self.injury) is not type(self.previous_injury)):
            raise TypeError('stand/remount requires the rider\'s exact actual injury type')
        replace(self.previous_injury); replace(self.injury)
        if self.source_round.active_turn is None or self.source_round.active_turn.actor_id != self.actor_id:
            raise ValueError('stand/remount belongs to another actual turn actor')
        if (self.previous_mount.actor_id != self.actor_id or self.previous_mount.mounted
                or self.mount != replace(self.previous_mount, mounted=True)
                or self.previous_body.rider_id != self.actor_id
                or self.previous_body.snapshot.state.actor_id != self.source.mount_id
                or self.previous_body.retained_since_round is None
                or self.body != _remounted_body(self.previous_body, self.previous_battlefield)):
            raise ValueError('stand/remount may neither create nor heal or replace a mount')
        if self.battlefield != _mounted_battlefield(self.previous_battlefield,
                self.actor_id, self.source.mount_id, spend_free_move=True):
            raise ValueError('stand/remount must spend one free move in place')
        if (self.stand_request is None) != (self.stand_result is None):
            raise ValueError('stand/remount must preserve the actual standing request and result together')
        if self.stand_request is not None:
            if type(self.stand_request) is not FreeMoveProneRemovalRequest or type(self.stand_result) is not FreeMoveProneRemovalResult:
                raise TypeError('stand/remount requires its exact K1 Prone removal witnesses')
            replace(self.stand_request); replace(self.stand_result)
            if self.stand_result != resolve_free_move_prone_removal(self.stand_request):
                raise ValueError('stand/remount changed its actual standing benefit or budget')


def expected_back_in_saddle_move(state):
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots or state.pending or state.pending_wound is not None
            or state.battlefield is None
            or turn.actor_id in state.battlefield.spatial.free_move_used_entity_ids):
        return None
    actor = turn.actor_id
    if actor not in (*state.source.pc_activation_order, *state.source.enemy_activation_order):
        return None
    available = available_remount(state, actor)
    if available is None:
        return None
    source, row, mount = available
    before = pc_actor_injury(state, actor)
    injury, request, result = before, None, None
    if before.conditions.has(Condition.PRONE):
        close_enemy = any(battlefield_range(state.battlefield, actor, enemy) is RangedWeaponRange.CLOSE
            for enemy in pc_opponent_ids(state, actor))
        if close_enemy:
            return None  # PG116 still requires Recover with a Close enemy.
        request = FreeMoveProneRemovalRequest(state.source.id+':back-in-saddle:'+str(len(state.history)),
            state.round_state, state.battlefield.spatial, actor, ProneRemovalTargetKind.SELF,
            actor, before.conditions, None, close_enemy)
        result = resolve_free_move_prone_removal(request)
        injury = replace(before, conditions=result.target_conditions)
        if type(injury) is CharacterInjuryState:
            from towr.domain.pc_heavy_wound_models import add_critical, restriction_sources
            injury = replace(injury, active_wound_effects=tuple(effect for effect in injury.active_wound_effects
                if not (type(effect) is WoundConditionEffect and effect.condition is Condition.PRONE
                    and effect.duration is WoundEffectDuration.UNTIL_REMOVED)))
            injury = add_critical(injury, restriction_sources(before, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL))
    return PcBackInSaddleMoveProof(source, state.round_state, len(state.history), mount,
        replace(mount, mounted=True), row, _remounted_body(row, state.battlefield), state.battlefield,
        _mounted_battlefield(state.battlefield, actor, source.mount_id, spend_free_move=True),
        before, injury, request, result)


def project_back_in_saddle_move(state, proof):
    if type(proof) is not PcBackInSaddleMoveProof or proof != expected_back_in_saddle_move(state):
        raise ValueError('stand/remount changed its actual source, physical readiness or once budget')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types, _party_update
    validate_pc_melee_source_types(proof, expected_back_in_saddle_move(state))
    actor = proof.actor_id
    updates = (dict(party=_party_update(state, actor, injury=proof.injury))
        if actor in state.source.pc_activation_order else pc_actor_npc_update(state, actor, injury=proof.injury))
    if actor in state.source.enemy_activation_order:
        from towr.domain.pc_npc_resilience_models import npc_current_resilience
        updates['enemies'] = tuple(replace(row, state=replace(row.state,
            current_resilience=npc_current_resilience(state, actor, mounted=True))) if row.state.actor_id == actor else row
            for row in updates['enemies'])
    excluded = state.round_state.excluded_turn_entity_ids
    mount_id = proof.source.mount_id
    if (mount_id in tuple(p.entity_id for p in state.round_state.participants)
            and mount_id not in (*state.round_state.completed_turn_entity_ids, *excluded)):
        excluded = (*excluded, mount_id)
    return dict(**updates, mounts=tuple(proof.mount if row.actor_id == actor else row for row in state.mounts),
        companions=tuple(proof.body if row.rider_id == actor else row for row in state.companions),
        battlefield=proof.battlefield, round_state=replace(state.round_state, excluded_turn_entity_ids=excluded))


@dataclass(frozen=True, slots=True)
class PcBackInSaddleRecoverProof:
    source: BackInSaddleSource
    recovery: RecoverActionExecutionResult
    history_index: int
    previous_mount: PcMountedState
    mount: PcMountedState
    previous_body: PcMountCompanionState
    body: PcMountCompanionState
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState

    @property
    def actor_id(self): return self.source.actor_id

    def __post_init__(self):
        for value, cls in ((self.source, BackInSaddleSource), (self.recovery, RecoverActionExecutionResult),
                (self.previous_mount, PcMountedState), (self.mount, PcMountedState),
                (self.previous_body, PcMountCompanionState), (self.body, PcMountCompanionState),
                (self.previous_battlefield, PcBattlefieldState), (self.battlefield, PcBattlefieldState)):
            if type(value) is not cls:
                raise TypeError('Recover remount requires exact source, action, body and spatial witnesses')
            replace(value)
        if type(self.history_index) is not int or self.history_index < 1:
            raise ValueError('Recover remount requires its actual nonnegative history position')
        follow = self.recovery.resolution.mount_follow_up
        if (follow is None or follow.actor_id != self.actor_id or follow.mount_id != self.source.mount_id
                or follow.rule_id != BACK_IN_SADDLE_RULE_ID
                or self.previous_mount.actor_id != self.actor_id or self.previous_mount.mounted
                or self.mount != replace(self.previous_mount, mounted=True)
                or self.previous_body.rider_id != self.actor_id
                or self.previous_body.snapshot.state.actor_id != self.source.mount_id
                or self.previous_body.retained_since_round is None
                or self.body != _remounted_body(self.previous_body, self.previous_battlefield)):
            raise ValueError('Recover remount must consume its actual mount follow-up without healing the body')
        if self.battlefield != _mounted_battlefield(self.previous_battlefield,
                self.actor_id, self.source.mount_id, spend_free_move=False):
            raise ValueError('Recover remount cannot spend movement or change the physical scene')


def _recover_receipt(proof):
    from towr.domain.pc_melee_result_models import PcRecoverProof
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
    from towr.domain.pc_potion_models import PcPotionRecoverProof
    from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
    return proof.result if type(proof) in (PcRecoverProof, PcBattlefieldRecoverProof,
        PcPotionRecoverProof, PcScarabHealingProof) else None


def expected_back_in_saddle_recover(state):
    if not state.history or state.pending or state.pending_wound is not None:
        return None
    recovery = _recover_receipt(state.history[-1])
    if recovery is None or recovery.resolution.mount_follow_up is None:
        return None
    actor = recovery.source_request.actor_id
    available = available_remount(state, actor)
    if available is None or pc_actor_injury(state, actor).conditions.has(Condition.PRONE):
        raise ValueError('paid remount lost its actual physical rider or mount readiness')
    source, row, mount = available
    return PcBackInSaddleRecoverProof(source, recovery, len(state.history), mount,
        replace(mount, mounted=True), row, _remounted_body(row, state.battlefield), state.battlefield,
        _mounted_battlefield(state.battlefield, actor, source.mount_id, spend_free_move=False))


def project_back_in_saddle_recover(state, proof):
    expected = expected_back_in_saddle_recover(state)
    if type(proof) is not PcBackInSaddleRecoverProof or proof != expected:
        raise ValueError('Recover remount changed its actual paid follow-up or physical prefix')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    validate_pc_melee_source_types(proof, expected)
    actor = proof.actor_id
    excluded = state.round_state.excluded_turn_entity_ids
    companion = proof.source.mount_id
    if (companion in tuple(p.entity_id for p in state.round_state.participants)
            and companion not in (*excluded, *state.round_state.completed_turn_entity_ids)):
        excluded = (*excluded, companion)
    updates = dict(mounts=tuple(proof.mount if row.actor_id == actor else row for row in state.mounts),
        companions=tuple(proof.body if row.rider_id == actor else row for row in state.companions),
        battlefield=proof.battlefield, round_state=replace(state.round_state, excluded_turn_entity_ids=excluded))
    if actor in state.source.enemy_activation_order:
        from towr.domain.pc_npc_resilience_models import npc_current_resilience
        updates['enemies'] = tuple(replace(row, state=replace(row.state,
            current_resilience=npc_current_resilience(state, actor, mounted=True))) if row.state.actor_id == actor else row
            for row in state.enemies)
    return updates


BACK_IN_SADDLE_REMOUNT_PROOFS = (PcBackInSaddleMoveProof, PcBackInSaddleRecoverProof)
