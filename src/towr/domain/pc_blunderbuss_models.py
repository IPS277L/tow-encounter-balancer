"""Complete ordered nearby impacts for the admitted initial NPC cluster."""
from dataclasses import dataclass, replace

from towr.domain.pc_melee_models import PcBlunderbussNearby
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_nearby
from towr.domain.pc_actor_models import (
    pc_active_actor_ids, pc_actor_injury, pc_actor_npc_snapshot, pc_actor_npc_update, pc_companion,
)
from towr.domain.resolution_models import (
    IdentifiedStaggerTarget, NearbyTargetsStaggerRequest,
    NearbyTargetsStaggerResolutionRequest, NearbyTargetsStaggerResolutionResult,
    StaggerImpactRequest, StaggerImpactResult, TargetInjuryPolicy,
)
from towr.domain.injury_models import (
    ProfileStateChangeRequest, MinionStaggerDefeatCause, MinionStaggerDefeatOutcome,
)


@dataclass(frozen=True, slots=True)
class PcBattlefieldNearbySource:
    actor_id: str
    battlefield: PcBattlefieldState
    target_ids: tuple[str, ...]

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('nearby shot requires its actual shooting actor')
        if type(self.battlefield) is not PcBattlefieldState:
            raise TypeError('nearby shot requires its actual spatial snapshot')
        replace(self.battlefield)
        if (type(self.target_ids) is not tuple or len(set(self.target_ids)) != len(self.target_ids)
                or any(type(actor) is not str or not actor.strip() for actor in self.target_ids)):
            raise TypeError('nearby shot retains exact ordered distinct actor IDs')
        self.battlefield.spatial.placement_for(self.actor_id)
        for actor in self.target_ids:
            self.battlefield.spatial.placement_for(actor)


@dataclass(frozen=True, slots=True)
class PcBlunderbussSnapshot:
    cluster: PcBlunderbussNearby | PcBattlefieldNearbySource
    request: NearbyTargetsStaggerResolutionRequest

    def __post_init__(self):
        if type(self.cluster) not in (PcBlunderbussNearby,PcBattlefieldNearbySource) or type(self.request) is not NearbyTargetsStaggerResolutionRequest:
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

    def choose_wound_negation(self, *, request, table_roll, options):
        return self._negation(options)

    def choose_profile_wound_negation(self, *, request, options):
        return self._negation(options)

    def _negation(self, options):
        from towr.domain.pc_oath_models import LadyWoundDecisions
        selected = LadyWoundDecisions(None)._choice(options)
        if options and selected is None:
            raise ValueError('nearby Wound cannot invent an unowned external negation policy')
        return selected


class _NoRolls:
    def randint(self, lower, upper):
        raise ValueError('numeric Minion nearby impacts cannot invent a dice roll')


def _request(source, primary, order, injuries, approached, negations=None):
    ids = tuple(actor for actor in order if actor != primary and not injuries[actor].defeated)
    if any(actor in approached for actor in ids):
        raise ValueError('nearby snapshot cannot include a creature that left the initial cluster')
    return NearbyTargetsStaggerResolutionRequest(source.resolution_id+':nearby', source, primary,
        tuple(IdentifiedStaggerTarget(actor, StaggerImpactRequest(
            source.resolution_id+':nearby:'+actor, actor, TargetInjuryPolicy.MINION,
            injuries[actor], False, False,wound_negation_options=(negations or {}).get(actor,()))) for actor in ids))


def pc_blunderbuss_snapshot(state, attack):
    from towr.domain.pc_oath_models import pc_oath_wound_options
    shot = attack.ranged_shot or attack.npc_ranged_shot
    if (shot is None or shot.execution.previous_weapon_state.weapon_id is not RangedWeaponId.BLUNDERBUSS
            or attack.execution.resolution.attack.outcome is not AttackOutcome.HIT):
        return None
    if state.battlefield is not None:
        targets = battlefield_nearby(state.battlefield,attack.request.target_id,
            pc_active_actor_ids(state))
        source, = tuple(f for f in attack.execution.resolution.follow_ups if type(f) is NearbyTargetsStaggerRequest)
        identified = []
        from towr.domain.pc_give_ground_models import pc_give_ground_context
        from towr.domain.pc_undead_minion_models import pc_undead_minion_source
        from towr.domain.undead_minion_models import (
            undead_minion_stagger_defeat_spec, undead_minion_effect_immunities,
        )
        from towr.domain.talent_injury_models import hardy_wound_dice_modifiers
        from towr.domain.talent_actor_models import actor_acquired_talents
        for actor in targets:
            pc = actor in state.source.pc_activation_order
            injury = pc_actor_injury(state,actor)
            policy = TargetInjuryPolicy.PLAYER if pc else pc_actor_npc_snapshot(state,actor).definition.injury_policy
            ground=pc_give_ground_context(state,actor,attack.request.actor_id,allow_friendly_source=True)
            undead=pc_undead_minion_source(state,actor)
            wound_modifiers=(hardy_wound_dice_modifiers(actor_acquired_talents(state,actor))
                if policy in (TargetInjuryPolicy.PLAYER,TargetInjuryPolicy.CHAMPION) else ())
            identified.append(IdentifiedStaggerTarget(actor,StaggerImpactRequest(
                source.resolution_id+':nearby:'+actor,actor,policy,injury,
                ground.can_leave,ground.given_this_round,wound_dice_modifiers=wound_modifiers,
                wound_negation_options=pc_oath_wound_options(state,actor),
                minion_stagger_defeat=undead_minion_stagger_defeat_spec(undead,actor),
                target_effect_immunities=undead_minion_effect_immunities(undead,actor))))
        return PcBlunderbussSnapshot(PcBattlefieldNearbySource(attack.request.actor_id,
            state.battlefield,targets),NearbyTargetsStaggerResolutionRequest(
                source.resolution_id+':nearby',source,attack.request.target_id,tuple(identified)))
    policy = state.source.blunderbuss_nearby
    if policy is None:
        raise ValueError('HIT snapshot requires its admitted cluster')
    source, = tuple(f for f in attack.execution.resolution.follow_ups if type(f) is NearbyTargetsStaggerRequest)
    return PcBlunderbussSnapshot(policy, _request(source, attack.request.target_id, policy.target_priority,
        {e.state.actor_id:e.state.injury for e in state.enemies}, state.approached_npc_ids,
        {actor:pc_oath_wound_options(state,actor) for actor in policy.target_priority}))


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


def _nearby_oath_prefix_step(bank, proof):
    """Retain just the Lady resource needed by the stationary HIT snapshot.

    The native owner authenticates each proof; this narrow history guard must
    still reconstruct the resource at the shot, rather than use its final value.
    """
    if not bank:
        return bank
    from towr.domain.pc_oath_models import PcLadyPrayerProof, oath_step_evidence, lady_wound_rule
    from towr.domain.injury_models import CharacterWoundResult, ProfileWoundResult
    from towr.domain.lady_blessing_models import record_lady_wound_negation, record_lady_broken_gain
    from towr.domain.pc_melee_result_models import PcAttackProof
    bank = dict(bank)
    if type(proof) is PcLadyPrayerProof:
        actor = proof.result.blessing.actor_id
        if actor in bank:
            if proof.result.source_request.blessing != bank[actor]:
                raise ValueError('nearby prayer history replaced its actual acquired resource prefix')
            bank[actor] = proof.result.blessing
    for result in oath_step_evidence(proof):
        if type(result) not in (CharacterWoundResult, ProfileWoundResult):
            continue
        actor = next((actor for actor in bank
            if result.negated_by_rule_id == lady_wound_rule(actor)), None)
        if actor is not None and bank[actor].negated_wound_id != result.request_id:
            bank[actor] = record_lady_wound_negation(bank[actor], result.request_id)
    if type(proof) is PcAttackProof and proof.request.target_id in bank:
        actor = proof.request.target_id
        before = proof.request.kernel_request.target_state.conditions
        after = proof.execution.resolution.target_state.conditions
        if not before.has(Condition.BROKEN) and after.has(Condition.BROKEN):
            bank[actor] = record_lady_broken_gain(bank[actor], actor, before, after)
    return bank


def _nearby_oath_options(bank):
    from towr.domain.injury_models import WoundNegationOption
    from towr.domain.pc_oath_models import lady_wound_rule
    return {actor:(WoundNegationOption(lady_wound_rule(actor)),) if grant.available else ()
        for actor,grant in bank.items()}


def validate_pc_blunderbuss_history(state):
    """Bind committed snapshots and completion to the actual ordered shot journal.

    This small bank covers only the restricted Short scene's numeric Minions;
    their injury producers are ordinary attacks, miss Staggered, and this wave.
    """
    from towr.domain.pc_melee_result_models import (
        PcAttackProof, PcAttackerStaggerProof, PcProfileWoundProof, validate_pc_melee_source_types,
    )
    from towr.domain.pc_short_opening_models import PcNpcApproachProof
    if state.source.battlefield is not None:
        validate_pc_battlefield_blunderbuss_history(state)
        return
    policy = state.source.blunderbuss_nearby
    if policy is None:
        if any(type(p) is PcBlunderbussNearbyProof for p in state.history):
            raise ValueError('nearby receipt requires its source cluster')
        return
    injuries = {e.state.actor_id:e.state.injury for e in state.source.enemies}
    from towr.domain.pc_oath_models import initial_pc_oaths, PcOathNegationAckProof
    oath_bank = {row.actor_id:row.lady for row in initial_pc_oaths(state.source) if row.lady is not None}
    approached = set()
    opened = None
    ack = None
    last_attack = None
    for index, proof in enumerate(state.history):
        if index:
            oath_bank = _nearby_oath_prefix_step(oath_bank,state.history[index-1])
        if opened is not None:
            if type(proof) is PcOathNegationAckProof:
                attack, _ = opened
                if proof.source not in attack.execution.resolution.follow_ups:
                    raise ValueError('nearby primary negation ACK replaced its actual preceding Wound')
                continue
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
                request = _request(source, proof.request.target_id, policy.target_priority, injuries, approached,
                    _nearby_oath_options(oath_bank))
                expected_snapshot = PcBlunderbussSnapshot(policy, request)
                if proof.nearby_snapshot != expected_snapshot:
                    raise ValueError('HIT snapshot changed its committed cluster source, order or states')
                validate_pc_melee_source_types(proof.nearby_snapshot, expected_snapshot)
                opened = (proof, proof.nearby_snapshot.request)
                ack = (result.profile_wound.state_change if result.profile_wound is not None
                    and result.profile_wound.wounds_inflicted > 0 else None)
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


@dataclass(frozen=True, slots=True)
class PcBlunderbussTargetProof:
    resolution_id: str
    request: StaggerImpactRequest
    result: StaggerImpactResult

    def __post_init__(self):
        if type(self.resolution_id) is not str or not self.resolution_id.strip():
            raise TypeError('nearby target requires its actual source resolution')
        if type(self.request) is not StaggerImpactRequest or type(self.result) is not StaggerImpactResult:
            raise TypeError('nearby target requires its exact Stagger impact and receipt')
        replace(self.request); replace(self.result)


@dataclass(frozen=True, slots=True)
class PcBlunderbussProfileProof:
    resolution_id: str
    target_id: str
    source: ProfileStateChangeRequest
    decision: MinionDefeatDecision | None

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.resolution_id,self.target_id)):
            raise TypeError('nearby NPC acknowledgement requires exact source and target IDs')
        if type(self.source) is not ProfileStateChangeRequest:
            raise TypeError('nearby NPC acknowledgement requires its actual profile change')
        replace(self.source)
        if self.decision is not None:
            if type(self.decision) is not MinionDefeatDecision:
                raise TypeError('nearby NPC disposition must be a typed GM source')
            replace(self.decision)


@dataclass(frozen=True, slots=True)
class PcBlunderbussMinionDefeatProof:
    resolution_id: str
    target_id: str
    source: MinionStaggerDefeatCause

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.resolution_id,self.target_id)):
            raise TypeError('nearby destruction requires its exact resolution and target IDs')
        if type(self.source) is not MinionStaggerDefeatCause:
            raise TypeError('nearby destruction requires its exact typed non-Wound cause')
        replace(self.source)
        if self.source.target_id!=self.target_id or self.source.outcome is not MinionStaggerDefeatOutcome.DESTROYED:
            raise ValueError('nearby destruction cannot become a different target or fleeing outcome')


@dataclass(frozen=True, slots=True)
class PcBlunderbussEndProof:
    resolution_id: str

    def __post_init__(self):
        if type(self.resolution_id) is not str or not self.resolution_id.strip():
            raise TypeError('nearby completion requires its actual source resolution')


BATTLEFIELD_NEARBY_PROOFS = (PcBlunderbussTargetProof,PcBlunderbussProfileProof,
    PcBlunderbussMinionDefeatProof,PcBlunderbussEndProof)


def current_pc_blunderbuss_wave(state):
    from towr.domain.pc_melee_result_models import PcAttackProof
    for proof in reversed(state.history):
        if type(proof) is PcBlunderbussEndProof:
            return None
        if (type(proof) is PcAttackProof and proof.nearby_snapshot is not None
                and type(proof.nearby_snapshot.cluster) is PcBattlefieldNearbySource):
            return proof
    return None


def next_pc_blunderbuss_target(state):
    attack = current_pc_blunderbuss_wave(state)
    if attack is None or state.pending_wound is not None:
        return None
    snapshot = attack.nearby_snapshot
    if state.pending not in ((),(snapshot.request.source,)):
        return None
    resolution_id = attack.request.kernel_request.id
    completed = tuple(proof.request.target_id for proof in state.history
        if type(proof) is PcBlunderbussTargetProof and proof.resolution_id==resolution_id)
    ids = snapshot.cluster.target_ids
    if completed != ids[:len(completed)]:
        raise ValueError('nearby impacts changed their committed target order')
    if len(completed)==len(ids):
        return None
    request = snapshot.request.targets[len(completed)].impact
    injury = pc_actor_injury(state,request.target_id)
    if request.target_state != injury:
        raise ValueError('nearby target injury detached from its committed HIT snapshot')
    return request


def pc_blunderbuss_pending_npc_target(state):
    attack = current_pc_blunderbuss_wave(state)
    if attack is None:
        return None
    target = next((proof for proof in reversed(state.history) if type(proof) is PcBlunderbussTargetProof
        and proof.resolution_id==attack.request.kernel_request.id),None)
    if (target is not None and target.request.target_policy is not TargetInjuryPolicy.PLAYER
            and state.pending_actor_id==target.request.target_id and state.pending_wound is None
            and state.pending and _nearby_pending_suffix(target.result.follow_ups,state.pending)):
        if target.result.minion_stagger_defeat is not None:
            from towr.domain.pc_undead_minion_models import pc_undead_minion_source
            from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec
            undead=pc_undead_minion_source(state,target.request.target_id)
            expected=undead_minion_stagger_defeat_spec(undead,target.request.target_id)
            if expected is None or target.request.minion_stagger_defeat!=expected:
                raise ValueError('nearby non-Wound destruction requires this actual Undead companion source')
        return target
    return None


def _nearby_pending_suffix(original, pending):
    from towr.domain.resolution_models import ConsumeWoundNegationRequest
    removed = len(original)-len(pending)
    return removed >= 0 and original[removed:]==pending and all(
        type(item) is ConsumeWoundNegationRequest for item in original[:removed])


def pc_blunderbuss_profile_decision(state,target):
    attack = current_pc_blunderbuss_wave(state)
    change = target.result.profile_wound.state_change
    if pc_companion(state,target.request.target_id) is not None:
        return None  # A detached animal has profile defeat, not the rider's PC disposition.
    if change.defeated and attack.request.actor_id in state.source.pc_activation_order:
        return state.source.participant(attack.request.actor_id).defeat_decision(target.request.target_id)
    # An NPC's friendly-fire profile defeat does not invent killed/knocked_out
    # or a GM disposition. K1 defeat/exclusion is sufficient in this scene.
    return None


def project_pc_battlefield_nearby(state,proof):
    from towr.domain.pc_melee_result_models import _party_update,validate_pc_melee_source_types
    from towr.domain.pc_warped_form_models import canonical_warped_form_impact
    replace(proof)
    attack = current_pc_blunderbuss_wave(state)
    if attack is None or proof.resolution_id != attack.request.kernel_request.id:
        raise ValueError('nearby continuation requires its unique open shot')
    def same(actual,expected):
        if actual!=expected:
            raise ValueError('nearby impact changed its actual source, result or continuation')
        validate_pc_melee_source_types(actual,expected)
    def finish(**changes):
        pending=changes.get('pending',state.pending)
        wound=changes.get('pending_wound',state.pending_wound)
        if not pending and wound is None:
            changes['pending_actor_id']=None
        return replace(state,history=(*state.history,proof),**changes)
    if type(proof) is PcBlunderbussTargetProof:
        request=next_pc_blunderbuss_target(state)
        if request is None:
            raise ValueError('nearby target cannot skip pending consequences or invent a target')
        same(proof.request,request)
        canonical=canonical_warped_form_impact(request,proof.result)
        same(proof.result,canonical)
        target=request.target_id
        changes=dict(pending=canonical.follow_ups,pending_wound=canonical.pending_character_wound,
            pending_actor_id=target if canonical.follow_ups or canonical.pending_character_wound is not None else None)
        if target in state.source.pc_activation_order:
            changes['party']=_party_update(state,target,injury=canonical.state)
        else:
            changes.update(pc_actor_npc_update(state,target,injury=canonical.state))
        return finish(**changes)
    if type(proof) is PcBlunderbussEndProof:
        if (state.pending_wound is not None or state.pending not in ((),(attack.nearby_snapshot.request.source,))
                or next_pc_blunderbuss_target(state) is not None):
            raise ValueError('nearby completion omitted a target or its mandatory consequences')
        return finish(pending=())
    target=pc_blunderbuss_pending_npc_target(state)
    if type(proof) is PcBlunderbussMinionDefeatProof:
        if target is None or target.result.minion_stagger_defeat is None:
            raise ValueError('nearby destruction requires its actual non-Wound Minion result')
        defeat=target.result.minion_stagger_defeat
        replace(defeat)
        same(proof,PcBlunderbussMinionDefeatProof(proof.resolution_id,target.request.target_id,defeat.cause))
        same(state.pending,(proof.source,))
        same(pc_actor_injury(state,proof.target_id),defeat.state)
        combat=state.round_state
        if (proof.target_id in tuple(participant.entity_id for participant in combat.participants)
                and proof.target_id not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids)):
            combat=replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,proof.target_id))
        return finish(pending=(),round_state=combat)
    if type(proof) is not PcBlunderbussProfileProof or target is None or target.result.profile_wound is None:
        raise ValueError('nearby NPC acknowledgement requires its actual profile Wound')
    expected=PcBlunderbussProfileProof(proof.resolution_id,target.request.target_id,
        target.result.profile_wound.state_change,pc_blunderbuss_profile_decision(state,target))
    same(proof,expected)
    same(state.pending,(proof.source,))
    combat=state.round_state
    if (proof.source.defeated and proof.target_id in tuple(participant.entity_id for participant in combat.participants)
            and proof.target_id not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids)):
        combat=replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,proof.target_id))
    updates=dict(pending=(),round_state=combat)
    if pc_companion(state,proof.target_id) is not None:
        from towr.domain.pc_companion_effect_models import companion_profile_wound_injury
        updates.update(pc_actor_npc_update(state,proof.target_id,
            injury=companion_profile_wound_injury(state,proof.target_id,proof.source)))
    return finish(**updates)


def validate_pc_battlefield_blunderbuss_history(state):
    """Retain the spatial HIT source and ordered per-target lifecycle cursors."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_battlefield_models import build_pc_battlefield
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_after_proof
    spatial=build_pc_battlefield(state.source.battlefield,state.source.pc_activation_order,
        state.source.enemy_activation_order,state.source.facts.zone_id)
    opened=None
    completed=[]
    for proof in state.history:
        spatial=pc_battlefield_after_proof(spatial,proof)
        if type(proof) is PcAttackProof:
            if opened is not None:
                raise ValueError('another Attack skipped the open nearby wave')
            snapshot=proof.nearby_snapshot
            shot=proof.ranged_shot or proof.npc_ranged_shot
            blunderbuss=(shot is not None and shot.execution.previous_weapon_state.weapon_id is RangedWeaponId.BLUNDERBUSS)
            hit=proof.execution.resolution.attack.outcome is AttackOutcome.HIT
            if snapshot is None:
                if blunderbuss and hit:
                    raise ValueError('Blunderbuss HIT omitted its committed actual nearby snapshot')
                continue
            if not(blunderbuss and hit) or type(snapshot.cluster) is not PcBattlefieldNearbySource:
                raise ValueError('actual battlefield nearby source requires a Blunderbuss HIT')
            replace(snapshot)
            source=NearbyTargetsStaggerRequest(proof.request.kernel_request.id,BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
            if (snapshot.cluster.actor_id!=proof.request.actor_id or snapshot.cluster.battlefield!=spatial
                    or snapshot.request.source!=source or snapshot.request.primary_target_id!=proof.request.target_id
                    or tuple(target.target_id for target in snapshot.request.targets)!=snapshot.cluster.target_ids
                    or snapshot.cluster.target_ids!=battlefield_nearby(spatial,proof.request.target_id,snapshot.cluster.target_ids)):
                raise ValueError('nearby snapshot changed its shooting actor, spatial source or exact Close links')
            opened=proof
            completed=[]
        elif type(proof) in BATTLEFIELD_NEARBY_PROOFS:
            if opened is None or proof.resolution_id!=opened.request.kernel_request.id:
                raise ValueError('nearby continuation has no unique actual shot')
            replace(proof)
            if type(proof) is PcBlunderbussTargetProof:
                ids=opened.nearby_snapshot.cluster.target_ids
                if len(completed)==len(ids) or proof.request!=opened.nearby_snapshot.request.targets[len(completed)].impact:
                    raise ValueError('nearby target changed its committed order or injury source')
                completed.append(proof.request.target_id)
            elif type(proof) is PcBlunderbussEndProof:
                if tuple(completed)!=opened.nearby_snapshot.cluster.target_ids:
                    raise ValueError('nearby completion lost a target')
                opened=None
    nearby=tuple(value for value in state.pending if type(value) is NearbyTargetsStaggerRequest)
    expected=((opened.nearby_snapshot.request.source,) if opened is not None and not completed else ())
    if nearby!=expected:
        raise ValueError('nearby trigger was lost, forged or completed twice')
