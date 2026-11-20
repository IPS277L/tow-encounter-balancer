"""Actual Oil/Blast victims and mandatory fire Hazards, PG96/122.

The Attack freezes geometry. Each exposed creature then owns its real Test,
Wound and Fate window; no second combat action or synthetic Damage is added.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.attack_models import AttackOutcome, HazardImpactSpec
from towr.domain.condition_models import Condition, ConditionApplicationResult
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, ProfileInjuryState, WoundDiceModifier,
    ProfileNpcType, ProfileStateChangeRequest, ProfileWoundResult, WoundNegationOption,
)
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range
from towr.domain.pc_actor_models import (
    pc_active_actor_ids, pc_actor_injury, pc_actor_npc_snapshot, pc_actor_npc_update,
    pc_actor_side, pc_companion,
)
from towr.domain.resolution_models import (
    HazardExposureRequest, HazardResolutionRequest, HazardResolutionResult, TargetInjuryPolicy,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill, TestRequest, TestResult
from towr.domain.turn_models import CombatRoundState
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_impact_preparation import OIL_IMPACT_RULE_ID, BLAST_IMPACT_RULE_ID
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleRollRequest, CharacterWoundLifecycleCompletionResult,
)

ABLAZE_HAZARD_RULE_ID = 'RULE-HEALTH-008:ablaze-hazard'


def expected_area_primary_resolution(kernel, attack):
    from towr.domain.pc_hit_condition_models import pc_pre_stagger_target
    from towr.domain.resolution_models import ResolutionResult,ConditionImpactResult,AttackerStaggerRequest
    from towr.domain.attack_models import MissConsequence
    from towr.domain.weapon_impact_preparation import is_blast_impact,is_oil_impact
    target,rules=pc_pre_stagger_target(kernel,attack.outcome)
    if attack.outcome is AttackOutcome.MISS:
        return ResolutionResult(kernel.id,attack,None,target,None,None,None,None,None,
            (AttackerStaggerRequest(kernel.attack.id),) if attack.miss_consequence is MissConsequence.STAGGER_ATTACKER else (),
            applied_secondary_rule_ids=rules)
    if is_blast_impact(kernel.attack.impact_spec):
        from towr.rules.kernel import _resolve_hazard_impact
        result=_resolve_hazard_impact(replace(kernel,target_state=target),attack,kernel.attack.impact_spec)
        return replace(result,applied_secondary_rule_ids=rules)
    if not is_oil_impact(kernel.attack.impact_spec):
        raise ValueError('area primary requires its exact Oil/Blast source')
    application=ConditionApplicationResult(kernel.id+':condition-impact',target.conditions.with_condition(Condition.ABLAZE),
        Condition.ABLAZE,target.conditions.has(Condition.ABLAZE),False,OIL_IMPACT_RULE_ID,None,(OIL_IMPACT_RULE_ID,))
    return ResolutionResult(kernel.id,attack,ConditionImpactResult(application),
        replace(target,conditions=application.state),None,None,None,None,None,(),
        condition_applications=(application,),applied_secondary_rule_ids=rules)


def _same(actual, expected, message):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual != expected:
        raise ValueError(message)
    validate_pc_melee_source_types(actual, expected)


def _injury(state, actor):
    return pc_actor_injury(state, actor)


def _alive(state, actor):
    return actor in pc_active_actor_ids(state)


@dataclass(frozen=True, slots=True)
class PcWeaponAreaSnapshot:
    action_id: str
    attacker_id: str
    target_id: str
    weapon: WeaponKind
    hit: bool
    battlefield: PcBattlefieldState | None
    target_ids: tuple[str, ...]


def weapon_area_snapshot(state, request, execution, use):
    if use is None or use.kind not in (WeaponKind.OIL_FLASK, WeaponKind.BLASTING_CHARGE):
        return None
    hit = execution.resolution.attack.outcome is AttackOutcome.HIT
    centre = request.target_id if hit else request.actor_id
    return PcWeaponAreaSnapshot(request.id, request.actor_id, request.target_id,
        use.kind, hit, state.battlefield,weapon_area_target_ids(state,use.kind,centre,hit=hit))


def weapon_area_target_ids(state,kind,centre,*,hit=True):
    actors = pc_active_actor_ids(state)
    targets = []
    for actor in actors:
        if kind is WeaponKind.OIL_FLASK and not hit:
            continue
        if state.battlefield is None:
            affected = True  # The explicit stationary source is one all-Close Zone.
        elif kind is WeaponKind.OIL_FLASK:
            affected = actor == centre or battlefield_range(state.battlefield, centre, actor) is RangedWeaponRange.CLOSE
        else:
            affected = state.battlefield.spatial.placement_for(actor).zone_id == state.battlefield.spatial.placement_for(centre).zone_id
        if affected:
            targets.append(actor)
    return tuple(targets)


def throwing_special_value(state,actor,target,kind,attacker,defender):
    """Bounded expected progress/risk; only real victims and supplied Skills.

    Oil uses a two-turn fire horizon. This is advice, never a combat result or
    another Monte Carlo sample. Blast's miss and friendly casualties count.
    """
    from towr.domain.pc_tactical_models import stagger_attack_value,_distribution
    from towr.domain.pc_musician_effect_models import musician_defends_ties,pc_attack_success_wins
    hit=sum(chance*other for successes,chance in enumerate(attacker)
        for opposed,other in enumerate(defender)
        if pc_attack_success_wins(state,actor,target,successes,opposed))
    conditions=_injury(state,target).conditions
    if kind is WeaponKind.ROCK:
        return stagger_attack_value(attacker,defender,conditions.has(Condition.STAGGERED),
            defender_wins_ties=musician_defends_ties(state,target))
    if kind is WeaponKind.WEIGHTED_NET:
        return .2*hit if not conditions.has(Condition.BURDENED) else 0.0
    if kind not in (WeaponKind.OIL_FLASK,WeaponKind.BLASTING_CHARGE):
        return None
    def expected_loss(victim,rating):
        from towr.domain.pc_falling_models import prepare_hazard_avoidance
        from towr.domain.pc_talent_advice import pc_test_distribution
        exposure=HazardExposureRequest('tactics:weapon-area','tactics:weapon-area:endurance',
            rating,Skill.ENDURANCE,ABLAZE_HAZARD_RULE_ID,True,())
        request=prepare_hazard_avoidance(state,victim,exposure,environmental=kind is WeaponKind.OIL_FLASK)
        distribution=(pc_test_distribution(state,victim,Skill.ENDURANCE,request,include_policy=True)
            if victim in state.source.pc_activation_order else _distribution(request))
        body=_injury(state,victim)
        if type(body) is ProfileInjuryState:
            return sum(chance*min(max(0,rating-successes),body.wound_limit-body.wounds)
                for successes,chance in enumerate(distribution))
        return sum(chance*min(1.5,max(0,rating-successes)*.7)
            for successes,chance in enumerate(distribution))
    side=pc_actor_side(state,actor)
    def score(centre,hit):
        total=0.0
        for victim in weapon_area_target_ids(state,kind,centre,hit=hit):
            if kind is WeaponKind.OIL_FLASK and _injury(state,victim).conditions.has(Condition.ABLAZE):
                continue
            opponent=pc_actor_side(state,victim) is not side
            loss=expected_loss(victim,2 if kind is WeaponKind.OIL_FLASK else 3)
            total+=(1.0 if opponent else -1.0)*loss*(2 if kind is WeaponKind.OIL_FLASK else 1)
        return total
    return hit*score(target,True)+(1-hit)*score(actor,False)


@dataclass(frozen=True, slots=True)
class PcWeaponAreaConditionProof:
    action_id: str
    actor_id: str
    application: ConditionApplicationResult


@dataclass(frozen=True, slots=True)
class PcWeaponAreaEndProof:
    action_id: str


@dataclass(frozen=True, slots=True)
class PcWeaponHazardRequest:
    id: str
    event_id: str
    actor_id: str
    exposure: HazardExposureRequest
    avoidance_test: TestRequest
    previous_injury: CharacterInjuryState | ProfileInjuryState
    target_injury: CharacterInjuryState | ProfileInjuryState
    target_policy: TargetInjuryPolicy
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(default=(),kw_only=True)
    wound_negation_options: tuple[WoundNegationOption, ...] = field(default=(),kw_only=True)
    periodic_clock: CombatRoundState | None = field(default=None,kw_only=True)

    def __post_init__(self):
        from towr.domain.injury_models import WoundNegationOption
        if type(self.wound_negation_options) is not tuple or any(
                type(option) is not WoundNegationOption for option in self.wound_negation_options):
            raise TypeError('weapon Hazard retains exact current-owner Wound negation options')
        for option in self.wound_negation_options:
            replace(option)
        if self.periodic_clock is not None:
            if type(self.periodic_clock) is not CombatRoundState:
                raise TypeError('body periodic Hazard requires its exact actual combat clock')
            replace(self.periodic_clock)
            if self.periodic_clock.active_turn is None:
                raise ValueError('body periodic Hazard requires its actual end-phase owner')


@dataclass(frozen=True, slots=True)
class PcWeaponHazardProof:
    request: PcWeaponHazardRequest
    test: TestResult
    result: HazardResolutionResult
    fate_decline: object = None
    glorious: object = None
    npc_disposition: object = None


@dataclass(frozen=True, slots=True)
class PcWeaponHazardCompletionProof:
    source_id: str
    completion: CharacterWoundLifecycleCompletionResult
    result: HazardResolutionResult


def current_weapon_area(state):
    from towr.domain.pc_melee_result_models import PcAttackProof
    closed = {proof.action_id for proof in state.history if type(proof) is PcWeaponAreaEndProof}
    for proof in state.history:
        if type(proof) is PcAttackProof and proof.weapon_area is not None:
            if proof.weapon_area.action_id not in closed:
                return proof.weapon_area
    return None


def _remaining_area_targets(state, area):
    used = {proof.actor_id for proof in state.history if type(proof) is PcWeaponAreaConditionProof
        and proof.action_id == area.action_id}
    used.update(proof.request.actor_id for proof in state.history if type(proof) is PcWeaponHazardProof
        and proof.request.event_id == area.action_id)
    if area.weapon is WeaponKind.OIL_FLASK and area.hit:
        used.add(area.target_id)  # K1 already applied this exact primary condition.
    live = frozenset(pc_active_actor_ids(state))
    return tuple(actor for actor in area.target_ids if actor not in used and actor in live)


def _hazard_request(state, actor, event, rating, rule):
    from towr.domain.pc_falling_models import prepare_hazard_avoidance
    from towr.domain.pc_melee_result_models import pc_after_test
    identifier = event + ':exposure:' + str(len(actor)) + ':' + actor
    exposure = HazardExposureRequest(identifier, identifier + ':endurance', rating,
        Skill.ENDURANCE, rule, True, ())
    test = prepare_hazard_avoidance(state, actor, exposure,environmental=rule==ABLAZE_HAZARD_RULE_ID)
    injury = _injury(state, actor)
    pc = actor in state.source.pc_activation_order
    from towr.domain.talent_injury_models import hardy_wound_dice_modifiers
    from towr.domain.pc_oath_models import pc_oath_wound_options
    return PcWeaponHazardRequest(identifier, event, actor, exposure, test, injury,
        pc_after_test(state, actor) if pc else injury,
        TargetInjuryPolicy.PLAYER if pc else pc_actor_npc_snapshot(state,actor).definition.injury_policy,
        wound_dice_modifiers=hardy_wound_dice_modifiers(state.source.participant(actor).talents) if pc else (),
        wound_negation_options=pc_oath_wound_options(state,actor))


def expected_weapon_area_step(state):
    if state.pending_wound is not None:
        return None
    if any(type(pending) is not HazardExposureRequest for pending in state.pending):
        return None
    area = current_weapon_area(state)
    if area is None:
        return None
    targets = _remaining_area_targets(state, area)
    if not targets:
        return PcWeaponAreaEndProof(area.action_id)
    actor = targets[0]
    if area.weapon is WeaponKind.BLASTING_CHARGE:
        return _hazard_request(state, actor, area.action_id, 3, BLAST_IMPACT_RULE_ID)
    injury = _injury(state, actor)
    application = ConditionApplicationResult(area.action_id + ':nearby-ablaze:' + actor,
        injury.conditions.with_condition(Condition.ABLAZE), Condition.ABLAZE,
        injury.conditions.has(Condition.ABLAZE), False, OIL_IMPACT_RULE_ID, None, (OIL_IMPACT_RULE_ID,))
    return PcWeaponAreaConditionProof(area.action_id, actor, application)


def expected_ablaze_hazard(state):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None or current_weapon_area(state) is not None:
        return None
    turn = state.round_state.active_turn
    if turn is None or any(not slot.executed for slot in turn.action_slots):
        return None
    actor = turn.actor_id
    if not turn.action_slots and not _injury(state, actor).conditions.has(Condition.DEFENCELESS):
        from towr.domain.pc_broken_battlefield_models import pc_broken_turn_blocked
        from towr.domain.pc_companion_turn_models import expected_companion_wait
        if not pc_broken_turn_blocked(state) and expected_companion_wait(state) is None:
            return None
    from towr.domain.pc_demigryph_models import build_pc_demigryph_strike
    from towr.domain.pc_aim_models import build_pc_aim_second_action
    from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
    from towr.domain.pc_duellist_models import build_pc_duellist_second_action
    from towr.domain.pc_rapid_reload_models import build_pc_rapid_reload_second_action
    if pc_companion(state, actor) is None:
        if (build_pc_demigryph_strike(state) is not None or build_pc_aim_second_action(state) is not None
                or build_pc_npc_extra_attack_slot(state) is not None or build_pc_duellist_second_action(state) is not None
                or build_pc_rapid_reload_second_action(state) is not None):
            return None
    # A mounted body keeps its own HP and ongoing effects. The paid turn is
    # still the rider's; the animal receives no extra action or Fate window.
    bodies = tuple(row.snapshot.state.actor_id for row in state.companions
        if row.rider_id == actor and any(mount.actor_id == actor and mount.mounted for mount in state.mounts))
    for victim in (actor, *bodies):
        if (_injury(state, victim).dead if victim in state.source.pc_activation_order
                else _injury(state, victim).defeated):
            continue
        if not _injury(state, victim).conditions.has(Condition.ABLAZE):
            continue
        event = f'{state.source.id}:r{state.round_state.round_number}:{victim}:ablaze'
        if any(type(proof) is PcWeaponHazardProof and proof.request.event_id == event for proof in state.history):
            continue
        request = _hazard_request(state, victim, event, 2, ABLAZE_HAZARD_RULE_ID)
        return replace(request, periodic_clock=state.round_state) if pc_companion(state, victim) is not None else request
    return None


def weapon_hazard_resolution_request(request, test):
    return HazardResolutionRequest(request.id, request.actor_id, request.exposure, test,
        request.target_policy, request.target_injury,wound_dice_modifiers=request.wound_dice_modifiers,
        wound_negation_options=request.wound_negation_options)


def weapon_hazard_completion(state):
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    done = {proof.source_id for proof in state.history if type(proof) is PcWeaponHazardCompletionProof}
    for proof in state.history:
        if type(proof) is not PcWeaponHazardProof or proof.request.id in done:
            continue
        pending = proof.result.pending_character_wound
        if pending is None:
            continue
        completion = next((item.completion for item in state.history if type(item) is PcWoundCompletionProof
            and item.completion.source_request.roll == pending), None)
        if completion is not None:
            from towr.rules.hazard_resolution import apply_hazard_character_wound_completion
            return PcWeaponHazardCompletionProof(proof.request.id, completion,
                apply_hazard_character_wound_completion(proof.result, completion))
    return None


def _canonical_hazard(request, test, result):
    if type(result) is not HazardResolutionResult:
        raise TypeError('weapon Hazard needs its actual typed result')
    rating = request.exposure.rating
    shortfall = max(0, rating - test.effective_successes)
    injury = request.target_injury
    rule = request.exposure.rule_id
    from towr.domain.resolution_models import ConsumeWoundNegationRequest
    selected = request.wound_negation_options[0].rule_id if request.wound_negation_options else None
    consumed = (ConsumeWoundNegationRequest(request.id,selected),) if selected is not None else ()
    if not shortfall:
        expected = HazardResolutionResult(request.id, injury, True, test.effective_successes, rating, 0,
            None, None, None, (), (), (rule,))
    elif request.target_policy is TargetInjuryPolicy.PLAYER:
        pending = result.pending_character_wound
        if pending is None:
            raise ValueError('failed weapon Hazard must retain the real PC Wound lifecycle')
        replace(pending)
        expected_source = CharacterWoundLifecycleRollRequest(request.id + ':wound-lifecycle', request.actor_id,
            CharacterWoundRequest(request.id + ':wound', injury, base_dice=shortfall,
                dice_modifiers=request.wound_dice_modifiers,negation_options=request.wound_negation_options))
        _same(pending.source_request, expected_source, 'Hazard Wound changed its source/shortfall')
        if pending.wound_result.negated_by_rule_id != selected:
            raise ValueError('weapon Hazard changed its actual automatic negation choice')
        expected = HazardResolutionResult(request.id, pending.wound_result.state, False, test.effective_successes,
            rating, shortfall, pending.wound_result, None, None, (), consumed, (rule,),
            pending_character_wound=pending, deferred_failure_exposure=request.exposure)
    else:
        from towr.domain.injury_models import ProfileWoundRequest, _expected_profile_wound_result
        source = ProfileWoundRequest(request.id + ':wound', ProfileNpcType(request.target_policy.value),injury,
            base_wounds=shortfall,negation_options=request.wound_negation_options)
        profile = _expected_profile_wound_result(source,selected)
        wounded = profile.state
        changes = (profile.state_change,) if profile.wounds_inflicted else ()
        expected = HazardResolutionResult(request.id, wounded, False, test.effective_successes, rating, shortfall,
            None, None, profile, (), (*consumed,*changes), (rule,))
    _same(result, expected, 'weapon Hazard changed its actual Test/Wound/outcome')


def _with_injury(state, actor, injury, *, fate=None):
    if actor in state.source.pc_activation_order:
        return dict(party=tuple(replace(member, injury=injury, fate=member.fate if fate is None else fate)
            if member.actor_id == actor else member for member in state.party))
    if fate is not None:
        raise ValueError('a profile NPC cannot receive PC Fate')
    return pc_actor_npc_update(state,actor,injury=injury)


def project_weapon_area_step(state, proof):
    if type(proof) is PcWeaponHazardCompletionProof:
        expected = weapon_hazard_completion(state)
        _same(proof, expected, 'weapon Hazard completion was skipped, forged or repeated')
        return {}
    expected = expected_weapon_area_step(state)
    if expected is None:
        expected = expected_ablaze_hazard(state)
    if type(proof) in (PcWeaponAreaConditionProof, PcWeaponAreaEndProof):
        _same(proof, expected, 'weapon area changed its frozen victims/order/Condition')
        if type(proof) is PcWeaponAreaEndProof:
            return dict(pending=()) if state.pending else {}
        injury = _injury(state, proof.actor_id)
        return _with_injury(state, proof.actor_id, replace(injury, conditions=proof.application.state))
    if type(proof) is not PcWeaponHazardProof:
        raise TypeError('weapon area needs its exact source-bound receipt')
    _same(proof.request, expected, 'weapon Hazard changed its source/geometry/turn/body')
    request = expected
    actor = request.actor_id
    pc = actor in state.source.pc_activation_order
    fate = None
    if pc:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        _, fate = validate_pc_test_fate(state, actor, Skill.ENDURANCE, request.avoidance_test,
            proof.test, proof.fate_decline, proof.glorious)
        if proof.npc_disposition is not None:
            raise ValueError('PC Hazard cannot invent an NPC disposition')
    else:
        from towr.domain.pc_melee_result_models import _test_result
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC Hazard cannot spend PC Fate')
        _test_result(request.avoidance_test, proof.test)
    _canonical_hazard(request, proof.test, proof.result)
    injury = proof.result.state
    if pc_companion(state, actor) is not None:
        from towr.domain.pc_companion_effect_models import companion_profile, companion_wound_band_injury
        injury = companion_wound_band_injury(companion_profile(state, actor), injury)
    updates = _with_injury(state, actor, injury, fate=fate)
    updates['pending'] = tuple(item for item in state.pending if type(item) is not HazardExposureRequest)
    if pc:
        updates['pending_wound'] = proof.result.pending_character_wound
        if proof.result.pending_character_wound is not None:
            updates['pending_actor_id'] = actor
    else:
        from towr.domain.pc_falling_models import falling_npc_disposition
        disposition = (falling_npc_disposition(state.source, actor)
            if proof.result.profile_wound is not None and pc_companion(state,actor) is None else None)
        if proof.npc_disposition is not disposition:
            raise ValueError('NPC Hazard requires its actual agreed GM disposition')
        if proof.result.state.defeated:
            clock = state.round_state
            if (actor in tuple(participant.entity_id for participant in clock.participants)
                    and actor not in (*clock.completed_turn_entity_ids, *clock.excluded_turn_entity_ids)):
                updates['round_state'] = replace(clock,
                    active_turn=None if clock.active_turn is not None and clock.active_turn.actor_id == actor else clock.active_turn,
                    excluded_turn_entity_ids=(*clock.excluded_turn_entity_ids, actor))
    from towr.domain.pc_magic_models import consume_magic_modifiers
    updates['magic_modifiers'] = consume_magic_modifiers(state.magic_modifiers, proof)
    return updates


WEAPON_AREA_PROOFS = (PcWeaponAreaConditionProof, PcWeaponAreaEndProof,
    PcWeaponHazardProof, PcWeaponHazardCompletionProof)


def validate_weapon_area_scene(source):
    from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
    from towr.domain.pc_falling_models import falling_npc_disposition
    area_kinds = (WeaponKind.OIL_FLASK, WeaponKind.BLASTING_CHARGE,WeaponKind.DRAGON_BOW)
    has_area = any(unit.kind in area_kinds for member in source.party
        for unit in initial_pc_weapon_inventory(member).items)
    has_area = has_area or any(item.kind in area_kinds for enemy in source.enemies
        if enemy.definition.generated_components is not None for item in enemy.definition.generated_components.weapons)
    if not has_area:
        return
    for enemy in source.enemies:
        if enemy.definition.generated_components is None:
            raise ValueError('weapon area needs full generated NPC skill and injury sources')
        if not any(profile.skill is Skill.ENDURANCE for profile in enemy.definition.protection):
            raise ValueError('Oil/Blast/fire scene requires actual NPC Endurance, never an invented default')
        falling_npc_disposition(source, enemy.state.actor_id)
