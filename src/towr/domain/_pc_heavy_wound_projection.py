"""Pure projections for the closed M12 consequences; no rule execution/RNG."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundChoice, WoundConditionEffect, WoundConsequence, WoundConsequenceRequest,
    WoundEffectDuration as Duration, WoundEnduranceFailure as Failure,
    WoundEnduranceTestRequest, WoundRestriction as Restriction, WoundRestrictionEffect,
)
from towr.domain.pc_heavy_wound_models import (
    PcBodyFact, PcBodyFactKind as Body, available_sides, usable_hands, preferred_weapon_hand,
    critical_for_incidental_hand_use,
)
from towr.domain.pc_melee_models import PcWeaponHand, PcTwoHandedGrip
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldState


def _drop_shield_in_hand(member, side):
    if (member.shield is not None and member.shield.location is PcShieldLocation.HELD
            and member.shield.hand is side):
        return replace(member,shield=PcShieldState(PcShieldLocation.DROPPED,None))
    return member


def heavy_wound_effect(raw, request):
    """Expected normative state/follow-ups for a completed 11--23 Wound."""
    from towr.domain.injury_models import WoundChoiceRequest
    wound = raw.state.wounds[-1]
    conditions = {11:((Condition.DEAFENED,Duration.UNTIL_TREATED),),
        13:((Condition.PRONE,Duration.UNTIL_REMOVED),),
        14:((Condition.DRAINED,Duration.UNTIL_HEALED),),
        15:((Condition.STAGGERED,Duration.UNTIL_HEALED),),
        16:((Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED),),
        17:((Condition.PRONE,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED),
            (Condition.BURDENED,Duration.UNTIL_HEALED)),
        18:((Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED),(Condition.BURDENED,Duration.UNTIL_HEALED),
            (Condition.DRAINED,Duration.UNTIL_HEALED)),
        19:((Condition.BLINDED,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED),
            (Condition.STAGGERED,Duration.UNTIL_HEALED)),
        20:((Condition.DEFENCELESS,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED)),
        21:((Condition.DEFENCELESS,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED)),
        22:((Condition.DEFENCELESS,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED)),
        23:((Condition.DEFENCELESS,Duration.UNTIL_TREATED),(Condition.CRITICALLY_INJURED,Duration.UNTIL_TREATED),
            (Condition.BLINDED,Duration.PERMANENT))}
    restrictions = {12:((Restriction.USING_INJURED_HAND_CAUSES_CRITICAL,Duration.UNTIL_TREATED),),
        13:((Restriction.REMOVING_PRONE_CAUSES_CRITICAL,Duration.UNTIL_TREATED),),
        14:((Restriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,Duration.UNTIL_TREATED),),
        15:((Restriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL,Duration.UNTIL_TREATED),),
        16:((Restriction.INJURED_ARM_UNUSABLE,Duration.UNTIL_HEALED),),
        20:((Restriction.ARM_LOST,Duration.PERMANENT),),
        21:((Restriction.LEG_LOST,Duration.PERMANENT),(Restriction.SPEED_IS_SLOW,Duration.PERMANENT)),
        22:((Restriction.PHYSICAL_STAGGER_BECOMES_WOUND,Duration.PERMANENT),)}
    effects = list(raw.state.active_wound_effects)
    updated_conditions = raw.state.conditions
    for condition,duration in conditions.get(wound.table_total,()):
        effects.append(WoundConditionEffect(wound.sequence,condition,duration))
        updated_conditions = updated_conditions.with_condition(condition)
    effects.extend(WoundRestrictionEffect(wound.sequence,restriction,duration)
        for restriction,duration in restrictions.get(wound.table_total,()))
    followups = ()
    failure = {11:Failure.LOSE_D10_TEETH,12:Failure.LOSE_RANDOM_FINGER,19:Failure.LOSE_RANDOM_EYE}
    if wound.table_total == 12:
        followups = (WoundConsequenceRequest(wound.sequence,WoundConsequence.DROP_RANDOM_HAND_ITEM,request.rule_id),)
    if wound.table_total in failure:
        followups += (WoundEnduranceTestRequest(request.id+':endurance',wound.sequence,wound.entry_id,
            failure[wound.table_total],request.rule_id),)
    consequence = {16:WoundConsequence.RANDOMISE_INJURED_ARM,20:WoundConsequence.RANDOMISE_SEVERED_ARM,
        21:WoundConsequence.RANDOMISE_SEVERED_LEG}
    if wound.table_total in consequence:
        followups = (WoundConsequenceRequest(wound.sequence,consequence[wound.table_total],request.rule_id),)
    if wound.table_total == 18:
        followups = (WoundChoiceRequest(wound.sequence,
            (WoundChoice.DROP_AND_CLUTCH_STOMACH,WoundChoice.BECOME_DEFENCELESS),request.rule_id),)
    return replace(raw.state,wounds=(*raw.state.wounds[:-1],replace(wound,effect_resolved=True)),
        conditions=updated_conditions,active_wound_effects=tuple(effects)),followups


def consequence_sides(member, request):
    kind = request.consequence
    excluded = {WoundConsequence.RANDOMISE_INJURED_ARM:(Body.LOST_ARM,),
        WoundConsequence.RANDOMISE_SEVERED_ARM:(Body.LOST_ARM,),
        WoundConsequence.RANDOMISE_SEVERED_LEG:(Body.LOST_LEG,),
        WoundConsequence.LOSE_RANDOM_EYE:(Body.LOST_EYE,),
        WoundConsequence.DROP_RANDOM_HAND_ITEM:(Body.LOST_ARM,)}
    if kind is WoundConsequence.LOSE_RANDOM_FINGER:
        return tuple(f.side for f in member.body_facts if f.kind is Body.INJURED_HAND
            and f.wound_sequence == request.wound_sequence)
    return available_sides(member,excluded[kind]) if kind in excluded else ()


def _side(request, member, die, actual):
    sides = consequence_sides(member,request)
    if len(sides) == 2:
        if type(die) is not int or not 1 <= die <= 10:
            raise TypeError('two-sided consequence requires its actual d10')
        expected = PcWeaponHand.LEFT if die <= 5 else PcWeaponHand.RIGHT
    else:
        if die is not None:
            raise ValueError('single eligible side cannot consume a random die')
        expected = sides[0] if sides else None
    if actual is not expected:
        raise ValueError('body consequence changed its actual eligible side/roll')
    return expected


def clutch_candidates(member):
    arms = available_sides(member,(Body.UNUSABLE_ARM,Body.LOST_ARM))
    existing = tuple(f.side for f in member.body_facts if f.kind is Body.CLUTCH_STOMACH and f.side in arms)
    return existing[:1] if existing else usable_hands(member)


def reconcile_clutch(member):
    facts = list(member.body_facts)
    clutches = [fact for fact in facts if fact.kind is Body.CLUTCH_STOMACH]
    blocked = {fact.side for fact in facts if fact.kind in (Body.UNUSABLE_ARM,Body.LOST_ARM)}
    for old in clutches:
        if old.side not in blocked:
            continue
        candidates = tuple(side for side in PcWeaponHand if side not in blocked)
        replacement = next((side for side in candidates if side is not member.weapon_hand),
            next(iter(candidates),None))
        facts.remove(old)
        if replacement is None:
            effect = WoundConditionEffect(old.wound_sequence,Condition.DEFENCELESS,Duration.UNTIL_REMOVED)
            injury = replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS),
                active_wound_effects=(*member.injury.active_wound_effects,effect)
                if effect not in member.injury.active_wound_effects else member.injury.active_wound_effects)
            member = replace(member,injury=injury)
        else:
            facts.append(replace(old,side=replacement))
            member = _drop_shield_in_hand(member,replacement)
            member = replace(member,injury=critical_for_incidental_hand_use(member,replacement))
            if member.weapon_hand is replacement or member.weapon_hand is PcTwoHandedGrip.BOTH:
                member = replace(member,weapon_hand=None)
    return replace(member,body_facts=tuple(facts))


def body_consequence(member, proof):
    request = proof.source
    if type(proof.count) is not int or proof.count < 1:
        raise TypeError('body consequence requires its exact integer count')
    kind = request.consequence
    if kind is WoundConsequence.LOSE_D10_TEETH:
        if type(proof.die) is not int or not 1 <= proof.die <= 10 or proof.count != proof.die or proof.side is not None:
            raise ValueError('teeth loss must preserve its one actual d10')
        fact = PcBodyFact(Body.LOST_TEETH,request.wound_sequence,None,proof.count)
    elif kind is WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH:
        candidates = clutch_candidates(member)
        side = next((side for side in candidates if side is not member.weapon_hand),next(iter(candidates),None))
        if side is None or proof.side is not side or proof.die is not None or proof.count != 1:
            raise ValueError('clutch must select an available hand under the chosen fighting policy')
        fact = PcBodyFact(Body.CLUTCH_STOMACH,request.wound_sequence,side)
        member = _drop_shield_in_hand(member,side)
        member = replace(member,weapon_hand=None if member.weapon_hand is side or member.weapon_hand is PcTwoHandedGrip.BOTH else member.weapon_hand,
            injury=critical_for_incidental_hand_use(member,side))
    else:
        side = _side(request,member,proof.die,proof.side)
        if proof.count != 1:
            raise ValueError('a sided consequence concerns exactly one body part')
        if kind is WoundConsequence.DROP_RANDOM_HAND_ITEM:
            member = _drop_shield_in_hand(member,side)
            member = replace(member,weapon_hand=None if member.weapon_hand is side or member.weapon_hand is PcTwoHandedGrip.BOTH else member.weapon_hand)
            if member.injury.wounds[request.wound_sequence-1].table_total != 12:
                return member
            if side is None:
                raise ValueError('a Smashed Hand requires an actual anatomical hand')
            fact = PcBodyFact(Body.INJURED_HAND,request.wound_sequence,side)
        else:
            mapping = {WoundConsequence.RANDOMISE_INJURED_ARM:Body.UNUSABLE_ARM,
                WoundConsequence.RANDOMISE_SEVERED_ARM:Body.LOST_ARM,
                WoundConsequence.RANDOMISE_SEVERED_LEG:Body.LOST_LEG,
                WoundConsequence.LOSE_RANDOM_EYE:Body.LOST_EYE,
                WoundConsequence.LOSE_RANDOM_FINGER:Body.LOST_FINGER}
            if side is None or kind not in mapping:
                raise ValueError('an anatomical consequence has no available actual target')
            fact = PcBodyFact(mapping[kind],request.wound_sequence,side)
            if (kind in (WoundConsequence.RANDOMISE_INJURED_ARM,WoundConsequence.RANDOMISE_SEVERED_ARM)
                    and member.shield is not None and member.shield.location is PcShieldLocation.HELD
                    and member.shield.hand is side):
                member = replace(member,shield=PcShieldState(PcShieldLocation.UNAVAILABLE,side))
            if kind is WoundConsequence.RANDOMISE_SEVERED_ARM and member.weapon_hand is side:
                member = replace(member,weapon_hand=None)
    if fact in member.body_facts:
        raise ValueError('anatomical consequence cannot be replayed')
    return reconcile_clutch(replace(member,body_facts=(*member.body_facts,fact)))
