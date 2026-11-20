"""One real Lady Near Miss without Fate, PG1.4 III74/V112.

Cancellation precedes Wound effects/profile follow-ups and daily registration.
The owner must bind target_id and the complete actual pending Wound source;
an arbitrary Wound id is not sufficient authorisation. No actor profile is
converted into a character and no previously applied effects are rewound.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, CharacterWoundResult,
    FixedCharacterWoundRequest, FixedCharacterWoundResult,
    AdditionalProfileWound, ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest,
    ProfileWoundRequest, ProfileWoundResult,
    validate_character_wound_result_provenance, validate_fixed_character_wound_result_provenance,
)
from towr.domain.lady_blessing_models import (
    LadyBlessingState, _id, _state, record_lady_wound_negation,
)


LADY_NEGATION_RULE_ID = 'RULE-TALENT-002:lady-near-miss'
_CHARACTER_PAIRS = {CharacterWoundRequest: CharacterWoundResult,
    FixedCharacterWoundRequest: FixedCharacterWoundResult}


def _injury(injury):
    if type(injury) not in (CharacterInjuryState, ProfileInjuryState):
        raise TypeError('Lady Near Miss requires its exact original injury type')
    replace(injury)
    conditions = injury.conditions
    if (type(conditions) is not ConditionState or type(conditions.conditions) is not frozenset
            or any(type(value) is not Condition for value in conditions.conditions)):
        raise TypeError('Lady Near Miss retains exact immutable Conditions')
    replace(conditions)
    if type(injury) is ProfileInjuryState:
        if (type(injury.wounds) is not int or type(injury.wound_limit) is not int
                or type(injury.defeated) is not bool):
            raise TypeError('Lady profile Wounds retain exact integer HP and bool defeat')
    elif type(injury.wounds) is not tuple or type(injury.active_wound_effects) is not tuple:
        raise TypeError('Lady character Wounds retain immutable injury histories')
    else:
        for wound in injury.wounds:
            replace(wound)
        for effect in injury.active_wound_effects:
            replace(effect)


def _rules(rules):
    if type(rules) is not tuple:
        raise TypeError('Lady Near Miss retains its actual immutable Rule sources')
    for rule in rules:
        _id(rule)


def _profile_state(request, requested):
    if requested == 0:
        # A negated Wound does not provide adrenaline/remove existing Staggered.
        return request.state
    wounds = min(request.state.wound_limit, request.state.wounds + requested)
    return ProfileInjuryState(wounds, request.state.wound_limit,
        request.state.conditions.without_condition(Condition.STAGGERED),
        wounds >= request.state.wound_limit or request.decapitation_cause is not None,
        request.decapitation_cause)


def _profile_source(request, result):
    if type(request) is not ProfileWoundRequest or type(result) is not ProfileWoundResult:
        raise TypeError('Lady profile cancellation requires the exact actual profile Wound pair')
    replace(request)
    if type(request.npc_type) is not ProfileNpcType or type(request.additional_wounds) is not tuple:
        raise TypeError('Lady profile cancellation retains exact typed profile and extra Wounds')
    for extra in request.additional_wounds:
        if type(extra) is not AdditionalProfileWound:
            raise TypeError('Lady cancellation retains the actual additional Wound sources')
        replace(extra)
    _injury(request.state)
    _injury(result.state)
    _rules(result.applied_rule_ids)
    change = result.state_change
    if (type(change) is not ProfileStateChangeRequest or type(change.npc_type) is not ProfileNpcType
            or type(change.previous_wounds) is not int or type(change.current_wounds) is not int
            or type(change.defeated) is not bool or type(result.wounds_requested) is not int
            or type(result.wounds_inflicted) is not int):
        raise TypeError('Lady cancellation retains exact actual profile Wound change values')
    if request.state.defeated:
        raise ValueError('an already defeated profile has no new Wound to negate')
    requested = request.base_wounds + sum(item.count for item in request.additional_wounds)
    injury = _profile_state(request, requested)
    expected = ProfileWoundResult(request.id, injury, requested,
        injury.wounds - request.state.wounds,
        ProfileStateChangeRequest(request.npc_type, request.state.wounds, injury.wounds, injury.defeated),
        (*tuple(item.rule_id for item in request.additional_wounds),
            *((request.decapitation_cause.rule_id,) if request.decapitation_cause is not None else ())))
    if result != expected or type(result.wounds_inflicted) is not int or result.wounds_inflicted < 1:
        raise ValueError('Lady cancellation cannot replace or invent an actual profile Wound')
    return requested


@dataclass(frozen=True, slots=True)
class LadyWoundNegationRequest:
    id: str
    target_id: str
    blessing: LadyBlessingState
    wound_request: CharacterWoundRequest | FixedCharacterWoundRequest | ProfileWoundRequest
    wound_result: CharacterWoundResult | FixedCharacterWoundResult | ProfileWoundResult

    def __post_init__(self):
        _id(self.id)
        _id(self.target_id)
        _state(self.blessing)
        if self.target_id != self.blessing.actor_id:
            raise ValueError('Lady blessing cannot cancel another actor\'s Wound')
        if not self.blessing.available:
            raise ValueError('Lady cancellation requires an active unused blessing')
        kind = type(self.wound_request)
        if kind in _CHARACTER_PAIRS:
            if type(self.wound_result) is not _CHARACTER_PAIRS[kind]:
                raise TypeError('Lady character cancellation needs its actual matching typed Wound result')
            replace(self.wound_request)
            _injury(self.wound_request.state)
            _injury(self.wound_result.state)
            _rules(self.wound_result.applied_rule_ids)
            if kind is CharacterWoundRequest and type(self.wound_result.wound_accepted) is not bool:
                raise TypeError('Lady cancellation retains the actual bool Wound acceptance')
            validator = (validate_character_wound_result_provenance if kind is CharacterWoundRequest
                else validate_fixed_character_wound_result_provenance)
            validator(self.wound_request, self.wound_result)
            if ((kind is CharacterWoundRequest and not self.wound_result.wound_accepted)
                    or self.wound_result.effect_request is None):
                raise ValueError('Lady Near Miss requires a newly accepted Wound before its effects')
        elif kind is ProfileWoundRequest:
            _profile_source(self.wound_request, self.wound_result)
            cause = self.wound_request.decapitation_cause
            if cause is not None and cause.target_id != self.target_id:
                raise ValueError('Lady cancellation cannot replace another actor\'s Decapitation source')
        else:
            raise TypeError('Lady Near Miss requires an actual supported Wound, not a Condition or defeat')


def _negation_values(request):
    if type(request) is not LadyWoundNegationRequest:
        raise TypeError('Lady cancellation requires its exact complete source')
    replace(request)
    blessing = record_lady_wound_negation(request.blessing, request.wound_request.id)
    if type(request.wound_request) is ProfileWoundRequest:
        # Cancel one requested Wound before clamping at a profile's Wound limit.
        # A second simultaneous Wound still exists even for a one-Wound Minion.
        remaining = _profile_source(request.wound_request, request.wound_result) - 1
        injury = _profile_state(request.wound_request, remaining)
    else:
        remaining, injury = 0, request.wound_request.state
    rules = tuple(dict.fromkeys((*request.wound_result.applied_rule_ids, LADY_NEGATION_RULE_ID)))
    return blessing, injury, remaining, rules


@dataclass(frozen=True, slots=True)
class LadyWoundNegationResult:
    source_request: LadyWoundNegationRequest
    blessing: LadyBlessingState
    injury: CharacterInjuryState | ProfileInjuryState
    remaining_wounds_requested: int
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self):
        expected = _negation_values(self.source_request)
        _state(self.blessing)
        if (type(self.injury) not in (CharacterInjuryState, ProfileInjuryState)
                or type(self.remaining_wounds_requested) is not int
                or type(self.applied_rule_ids) is not tuple):
            raise TypeError('Lady cancellation retains its exact injury, count and Rule receipts')
        _injury(self.injury)
        if (self.blessing, self.injury, self.remaining_wounds_requested, self.applied_rule_ids) != expected:
            raise ValueError('Lady Near Miss result changed its Wound, blessing or remaining consequences')


def negate_lady_wound(request: LadyWoundNegationRequest) -> LadyWoundNegationResult:
    """Consume once, preserve unnegated Wounds; no RNG, Fate or HP reset."""
    return LadyWoundNegationResult(request, *_negation_values(request))
