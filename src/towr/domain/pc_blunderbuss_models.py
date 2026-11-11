"""Complete ordered nearby impacts for the admitted initial NPC cluster."""
from dataclasses import dataclass, replace

from towr.domain.pc_melee_models import PcBlunderbussNearby
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.resolution_models import (
    IdentifiedStaggerTarget, NearbyTargetsStaggerRequest,
    NearbyTargetsStaggerResolutionRequest, NearbyTargetsStaggerResolutionResult,
    StaggerImpactRequest, TargetInjuryPolicy,
)


@dataclass(frozen=True, slots=True)
class PcBlunderbussSnapshot:
    cluster: PcBlunderbussNearby
    request: NearbyTargetsStaggerResolutionRequest

    def __post_init__(self):
        if type(self.cluster) is not PcBlunderbussNearby or type(self.request) is not NearbyTargetsStaggerResolutionRequest:
            raise TypeError('HIT snapshot requires its exact cluster source and ordered request')
        replace(self.cluster)
        replace(self.request)


@dataclass(frozen=True, slots=True)
class PcBlunderbussNearbyProof:
    request: NearbyTargetsStaggerResolutionRequest
    result: NearbyTargetsStaggerResolutionResult
    defeat_decisions: tuple[MinionDefeatDecision, ...]

    def __post_init__(self):
        if (type(self.request) is not NearbyTargetsStaggerResolutionRequest
                or type(self.result) is not NearbyTargetsStaggerResolutionResult
                or type(self.defeat_decisions) is not tuple
                or any(type(d) is not MinionDefeatDecision for d in self.defeat_decisions)):
            raise TypeError('nearby proof requires its exact request, results and ordered GM acknowledgements')
        replace(self.request)
        replace(self.result)
        for decision in self.defeat_decisions:
            replace(decision)


class PcNearbyDecisions:
    def choose_repeated_stagger(self, *, request, allowed_choices):
        if StaggerChoice.SUFFER_WOUND not in allowed_choices:
            raise ValueError('nearby impact requires the admitted suffer-Wound strategy')
        return StaggerChoice.SUFFER_WOUND


class _NoRolls:
    def randint(self, lower, upper):
        raise ValueError('numeric Minion nearby impacts cannot invent a dice roll')


def _request(source, primary, order, injuries, approached):
    ids = tuple(actor for actor in order if actor != primary and not injuries[actor].defeated)
    if any(actor in approached for actor in ids):
        raise ValueError('nearby snapshot cannot include a creature that left the initial cluster')
    return NearbyTargetsStaggerResolutionRequest(source.resolution_id+':nearby', source, primary,
        tuple(IdentifiedStaggerTarget(actor, StaggerImpactRequest(
            source.resolution_id+':nearby:'+actor, actor, TargetInjuryPolicy.MINION,
            injuries[actor], False, False)) for actor in ids))


def pc_blunderbuss_snapshot(state, attack):
    shot = attack.ranged_shot
    if (shot is None or shot.execution.previous_weapon_state.weapon_id is not RangedWeaponId.BLUNDERBUSS
            or attack.execution.resolution.attack.outcome is not AttackOutcome.HIT):
        return None
    policy = state.source.blunderbuss_nearby
    if policy is None:
        raise ValueError('HIT snapshot requires its admitted cluster')
    source, = tuple(f for f in attack.execution.resolution.follow_ups if type(f) is NearbyTargetsStaggerRequest)
    return PcBlunderbussSnapshot(policy, _request(source, attack.request.target_id, policy.target_priority,
        {e.state.actor_id:e.state.injury for e in state.enemies}, state.approached_npc_ids))


def canonical_pc_nearby_proof(scenario, attack, request):
    """Only numeric Minions are admitted; every resulting Wound is acknowledged here."""
    from towr.rules.secondary_target_resolution import resolve_nearby_targets_stagger
    result = resolve_nearby_targets_stagger(request, _NoRolls(), decisions=PcNearbyDecisions())
    participant = scenario.participant(attack.request.actor_id)
    decisions = tuple(participant.defeat_decision(target.target_id) for target in result.targets
        if target.impact.profile_wound is not None and target.impact.profile_wound.state_change.defeated)
    return PcBlunderbussNearbyProof(request, result, decisions)


def build_pc_blunderbuss_nearby(state):
    from towr.domain.pc_melee_result_models import PcAttackProof
    if (state.pending_wound is not None or not state.pending
            or type(state.pending[0]) is not NearbyTargetsStaggerRequest):
        raise ValueError('no actual nearby trigger is ready')
    source = state.pending[0]
    attack = next((p for p in reversed(state.history) if type(p) is PcAttackProof
        and p.request.kernel_request.id == source.resolution_id), None)
    if attack is None or state.source.blunderbuss_nearby is None:
        raise ValueError('nearby trigger lacks its admitted full PC shot')
    if attack.nearby_snapshot is None or attack.nearby_snapshot.request.source != source:
        raise ValueError('nearby trigger lost its committed HIT snapshot')
    return attack.nearby_snapshot.request


def validate_pc_blunderbuss_history(state):
    """Bind committed snapshots and completion to the actual ordered shot journal.

    This small bank covers only the restricted Short scene's numeric Minions;
    their injury producers are ordinary attacks, miss Staggered, and this wave.
    """
    from towr.domain.pc_melee_result_models import (
        PcAttackProof, PcAttackerStaggerProof, PcProfileWoundProof, validate_pc_melee_source_types,
    )
    from towr.domain.pc_short_opening_models import PcNpcApproachProof
    policy = state.source.blunderbuss_nearby
    if policy is None:
        if any(type(p) is PcBlunderbussNearbyProof for p in state.history):
            raise ValueError('nearby receipt requires its source cluster')
        return
    injuries = {e.state.actor_id:e.state.injury for e in state.source.enemies}
    approached = set()
    opened = None
    ack = None
    last_attack = None
    for proof in state.history:
        if opened is not None:
            if ack is not None:
                attack, _ = opened
                expected_ack = PcProfileWoundProof(ack, state.source.participant(attack.request.actor_id)
                    .defeat_decision(attack.request.target_id) if ack.defeated else None)
                if type(proof) is not PcProfileWoundProof or proof != expected_ack:
                    raise ValueError('primary Wound acknowledgement must precede nearby effects')
                validate_pc_melee_source_types(proof, expected_ack)
                ack = None
                continue
            if type(proof) is not PcBlunderbussNearbyProof:
                raise ValueError('nearby effects cannot be skipped before ordinary continuation')
            attack, request = opened
            expected = canonical_pc_nearby_proof(state.source, attack, request)
            if proof != expected:
                raise ValueError('nearby receipt changed the committed targets, state, result or GM decisions')
            validate_pc_melee_source_types(proof, expected)
            for target in proof.result.targets:
                injuries[target.target_id] = target.impact.state
            opened = None
            continue
        if type(proof) is PcBlunderbussNearbyProof:
            raise ValueError('nearby receipt has no unique unconsumed HIT trigger')
        if type(proof) is PcNpcApproachProof:
            approached.add(proof.actor_id)
        elif type(proof) is PcAttackerStaggerProof:
            if last_attack is not None and last_attack.request.actor_id in injuries:
                actor = last_attack.request.actor_id
                injuries[actor] = replace(injuries[actor],
                    conditions=injuries[actor].conditions.with_condition(Condition.STAGGERED))
        elif type(proof) is PcAttackProof:
            last_attack = proof
            result = proof.execution.resolution
            sources = tuple(f for f in result.follow_ups if type(f) is NearbyTargetsStaggerRequest)
            shot = proof.ranged_shot
            blunderbuss = (shot is not None and
                shot.execution.previous_weapon_state.weapon_id is RangedWeaponId.BLUNDERBUSS)
            hit = result.attack.outcome is AttackOutcome.HIT
            if sources and (not blunderbuss or not hit):
                raise ValueError('nearby trigger requires its actual Blunderbuss HIT')
            if not (blunderbuss and hit) and proof.nearby_snapshot is not None:
                raise ValueError('only a Blunderbuss HIT can commit a nearby snapshot')
            if blunderbuss and hit:
                source = NearbyTargetsStaggerRequest(proof.request.kernel_request.id,
                    BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
                if sources != (source,) or any(not injuries[a].defeated for a in approached):
                    raise ValueError('shot changed its one HIT trigger or actual Short premises')
                request = _request(source, proof.request.target_id, policy.target_priority, injuries, approached)
                expected_snapshot = PcBlunderbussSnapshot(policy, request)
                if proof.nearby_snapshot != expected_snapshot:
                    raise ValueError('HIT snapshot changed its committed cluster source, order or states')
                validate_pc_melee_source_types(proof.nearby_snapshot, expected_snapshot)
                opened = (proof, proof.nearby_snapshot.request)
                ack = result.profile_wound.state_change if result.profile_wound is not None else None
            if proof.request.target_id in injuries:
                injuries[proof.request.target_id] = result.target_state
    expected_pending = (opened[1].source,) if opened is not None else ()
    actual_pending = tuple(p for p in state.pending if type(p) is NearbyTargetsStaggerRequest)
    if actual_pending != expected_pending:
        raise ValueError('nearby trigger was lost, forged or completed twice')
    if any(e.state.injury != injuries[e.state.actor_id] for e in state.enemies):
        raise ValueError('numeric NPC injury bank differs from actual attacks and nearby receipts')


def project_pc_blunderbuss_nearby(state, proof):
    from towr.domain.pc_melee_result_models import PcAttackProof, validate_pc_melee_source_types
    request = build_pc_blunderbuss_nearby(state)
    attack = next(p for p in reversed(state.history) if type(p) is PcAttackProof
        and p.request.kernel_request.id == request.source.resolution_id)
    expected = canonical_pc_nearby_proof(state.source, attack, request)
    if proof != expected:
        raise ValueError('nearby effects changed their actual request, result or ordered acknowledgements')
    validate_pc_melee_source_types(proof, expected)
    results = {target.target_id:target.impact.state for target in proof.result.targets}
    enemies = tuple(replace(e,state=replace(e.state,injury=results[e.state.actor_id]))
        if e.state.actor_id in results else e for e in state.enemies)
    combat = state.round_state
    excluded = list(combat.excluded_turn_entity_ids)
    for target in proof.result.targets:
        if target.impact.state.defeated and target.target_id not in (*combat.completed_turn_entity_ids,*excluded):
            excluded.append(target.target_id)
    return replace(state, history=(*state.history,proof), enemies=enemies,
        round_state=replace(combat,excluded_turn_entity_ids=tuple(excluded)),
        pending=state.pending[1:], pending_actor_id=state.pending_actor_id if state.pending[1:] else None)
