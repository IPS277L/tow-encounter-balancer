from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    ActiveWoundEffect,
    CharacterInjuryState,
    WoundChoice,
    WoundChoiceRequest,
    WoundChoiceResult,
    WoundConditionEffect,
    WoundConsequence,
    WoundConsequenceRequest,
    WoundEffectDuration,
    WoundEffectFollowUp,
    WoundEffectRequest,
    WoundEffectResult,
    WoundEnduranceFailure,
    WoundEnduranceTestRequest,
    WoundEnduranceTestResult,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.test_models import TestResult


@dataclass(frozen=True, slots=True)
class _ChoiceTemplate:
    options: tuple[WoundChoice, ...]


_FollowUpTemplate = WoundEnduranceFailure | WoundConsequence | _ChoiceTemplate


@dataclass(frozen=True, slots=True)
class WoundEffectSpec:
    conditions: tuple[tuple[Condition, WoundEffectDuration], ...] = ()
    restrictions: tuple[tuple[WoundRestriction, WoundEffectDuration], ...] = ()
    follow_ups: tuple[_FollowUpTemplate, ...] = ()


_EMPTY_SPEC = WoundEffectSpec()
_wound_effect_specs: dict[WoundEntryId, WoundEffectSpec] = {
    entry_id: _EMPTY_SPEC for entry_id in WoundEntryId
}
_wound_effect_specs.update(
    {
        WoundEntryId.NICKED_ARM: WoundEffectSpec(
            follow_ups=(WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM,)
        ),
        WoundEntryId.BATTERED_LEG: WoundEffectSpec(
            follow_ups=(WoundEnduranceFailure.FALL_PRONE,)
        ),
        WoundEntryId.STOMACH_BLOW: WoundEffectSpec(
            conditions=((Condition.DRAINED, WoundEffectDuration.END_OF_NEXT_TURN),)
        ),
        WoundEntryId.GASHED_BROW: WoundEffectSpec(
            follow_ups=(
                WoundEnduranceFailure.BLINDED_UNTIL_END_OF_NEXT_TURN,
            )
        ),
        WoundEntryId.SHAKING_GRIP: WoundEffectSpec(
            restrictions=((WoundRestriction.CANNOT_AIM, WoundEffectDuration.UNTIL_TREATED),),
            follow_ups=(WoundConsequence.DROP_RANDOM_HAND_ITEM,),
        ),
        WoundEntryId.LEG_SPASM: WoundEffectSpec(
            conditions=((Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),),
            restrictions=(
                (
                    WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                    WoundEffectDuration.UNTIL_TREATED,
                ),
            ),
        ),
        WoundEntryId.CRUSHED_RIB: WoundEffectSpec(
            conditions=((Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED),),
            restrictions=((WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST),),
        ),
        WoundEntryId.EARS_RINGING: WoundEffectSpec(
            conditions=((Condition.DEAFENED, WoundEffectDuration.UNTIL_TREATED),),
            follow_ups=(WoundEnduranceFailure.LOSE_D10_TEETH,),
        ),
        WoundEntryId.SMASHED_HAND: WoundEffectSpec(
            restrictions=(
                (
                    WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED,
                ),
            ),
            follow_ups=(
                WoundConsequence.DROP_RANDOM_HAND_ITEM,
                WoundEnduranceFailure.LOSE_RANDOM_FINGER,
            ),
        ),
        WoundEntryId.TORN_LEG: WoundEffectSpec(
            conditions=((Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),),
            restrictions=(
                (
                    WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED,
                ),
            ),
        ),
        WoundEntryId.INTERNAL_INJURY: WoundEffectSpec(
            conditions=((Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),),
            restrictions=(
                (
                    WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED,
                ),
            ),
        ),
        WoundEntryId.SCARRING_STRIKE: WoundEffectSpec(
            conditions=((Condition.STAGGERED, WoundEffectDuration.UNTIL_HEALED),),
            restrictions=(
                (
                    WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED,
                ),
            ),
        ),
        WoundEntryId.SLASHED_FOREARMS: WoundEffectSpec(
            conditions=(
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
            ),
            restrictions=(
                (
                    WoundRestriction.INJURED_ARM_UNUSABLE,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
            ),
            follow_ups=(WoundConsequence.RANDOMISE_INJURED_ARM,),
        ),
        WoundEntryId.SHATTERED_KNEE: WoundEffectSpec(
            conditions=(
                (Condition.PRONE, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
                (Condition.BURDENED, WoundEffectDuration.UNTIL_HEALED),
            )
        ),
        WoundEntryId.SPILLING_GUTS: WoundEffectSpec(
            conditions=(
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
                (Condition.BURDENED, WoundEffectDuration.UNTIL_HEALED),
                (Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),
            ),
            follow_ups=(
                _ChoiceTemplate(
                    (
                        WoundChoice.DROP_AND_CLUTCH_STOMACH,
                        WoundChoice.BECOME_DEFENCELESS,
                    )
                ),
            ),
        ),
        WoundEntryId.BLACKING_OUT: WoundEffectSpec(
            conditions=(
                (Condition.BLINDED, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
                (Condition.STAGGERED, WoundEffectDuration.UNTIL_HEALED),
            ),
            follow_ups=(WoundEnduranceFailure.LOSE_RANDOM_EYE,),
        ),
        WoundEntryId.SEVERED_ARM: WoundEffectSpec(
            conditions=(
                (Condition.DEFENCELESS, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
            ),
            restrictions=((WoundRestriction.ARM_LOST, WoundEffectDuration.PERMANENT),),
            follow_ups=(WoundConsequence.RANDOMISE_SEVERED_ARM,),
        ),
        WoundEntryId.SEVERED_LEG: WoundEffectSpec(
            conditions=(
                (Condition.DEFENCELESS, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
            ),
            restrictions=(
                (WoundRestriction.LEG_LOST, WoundEffectDuration.PERMANENT),
                (WoundRestriction.SPEED_IS_SLOW, WoundEffectDuration.PERMANENT),
            ),
            follow_ups=(WoundConsequence.RANDOMISE_SEVERED_LEG,),
        ),
        WoundEntryId.RUPTURED_ORGANS: WoundEffectSpec(
            conditions=(
                (Condition.DEFENCELESS, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
            ),
            restrictions=(
                (
                    WoundRestriction.PHYSICAL_STAGGER_BECOMES_WOUND,
                    WoundEffectDuration.PERMANENT,
                ),
            ),
        ),
        WoundEntryId.RUINED_EYES: WoundEffectSpec(
            conditions=(
                (Condition.DEFENCELESS, WoundEffectDuration.UNTIL_TREATED),
                (Condition.CRITICALLY_INJURED, WoundEffectDuration.UNTIL_TREATED),
                (Condition.BLINDED, WoundEffectDuration.PERMANENT),
            )
        ),
    }
)
WOUND_EFFECT_SPECS: Mapping[WoundEntryId, WoundEffectSpec] = MappingProxyType(
    _wound_effect_specs
)

_FAILURE_CONSEQUENCES: Mapping[WoundEnduranceFailure, WoundConsequence] = (
    MappingProxyType(
        {
            WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM: (
                WoundConsequence.DROP_RANDOM_HAND_ITEM
            ),
            WoundEnduranceFailure.LOSE_D10_TEETH: WoundConsequence.LOSE_D10_TEETH,
            WoundEnduranceFailure.LOSE_RANDOM_FINGER: (
                WoundConsequence.LOSE_RANDOM_FINGER
            ),
            WoundEnduranceFailure.LOSE_RANDOM_EYE: (
                WoundConsequence.LOSE_RANDOM_EYE
            ),
        }
    )
)


def resolve_wound_effect(
    request: WoundEffectRequest,
    state: CharacterInjuryState,
) -> WoundEffectResult:
    wound = _validate_wound(request.wound_sequence, request.entry_id, state)
    if wound.effect_resolved:
        raise ValueError("Wound effect has already been resolved")

    spec = WOUND_EFFECT_SPECS[request.entry_id]
    effects: list[ActiveWoundEffect] = list(state.active_wound_effects)
    conditions = state.conditions
    for condition, duration in spec.conditions:
        effect = WoundConditionEffect(request.wound_sequence, condition, duration)
        effects.append(effect)
        conditions = conditions.with_condition(condition)
    for restriction, duration in spec.restrictions:
        effects.append(
            WoundRestrictionEffect(
                request.wound_sequence,
                restriction,
                duration,
            )
        )

    wounds = list(state.wounds)
    wounds[request.wound_sequence - 1] = replace(wound, effect_resolved=True)
    updated_state = CharacterInjuryState(
        wounds=tuple(wounds),
        conditions=conditions,
        active_wound_effects=tuple(effects),
        dead=state.dead,
    )
    follow_ups = tuple(
        _build_follow_up(request, template) for template in spec.follow_ups
    )
    return WoundEffectResult(
        request=request,
        state=updated_state,
        follow_ups=follow_ups,
        applied_rule_ids=(request.rule_id,),
    )


def resolve_wound_endurance_test(
    request: WoundEnduranceTestRequest,
    state: CharacterInjuryState,
    test: TestResult,
) -> WoundEnduranceTestResult:
    _validate_wound(request.wound_sequence, request.entry_id, state)
    if test.trace.request_id != request.test_id:
        raise ValueError("Endurance Test result does not match its request")
    if test.succeeded:
        return WoundEnduranceTestResult(request, state, True, ())

    condition_effect = _failed_test_condition(request)
    if condition_effect is not None:
        updated_state = _with_added_effect(state, condition_effect)
        return WoundEnduranceTestResult(request, updated_state, False, ())

    consequence = _FAILURE_CONSEQUENCES[request.failure]
    follow_up = WoundConsequenceRequest(
        request.wound_sequence,
        consequence,
        request.rule_id,
    )
    return WoundEnduranceTestResult(request, state, False, (follow_up,))


def resolve_wound_choice(
    request: WoundChoiceRequest,
    state: CharacterInjuryState,
    selected: WoundChoice,
) -> WoundChoiceResult:
    _validate_wound(request.wound_sequence, WoundEntryId.SPILLING_GUTS, state)
    if not isinstance(selected, WoundChoice):
        raise TypeError("selected choice must be a WoundChoice")
    if selected not in request.options:
        raise ValueError("selected Wound choice is not available")
    if selected is WoundChoice.BECOME_DEFENCELESS:
        effect = WoundConditionEffect(
            request.wound_sequence,
            Condition.DEFENCELESS,
            WoundEffectDuration.UNTIL_REMOVED,
        )
        return WoundChoiceResult(
            request,
            _with_added_effect(state, effect),
            selected,
            (),
        )
    follow_up = WoundConsequenceRequest(
        request.wound_sequence,
        WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH,
        request.rule_id,
    )
    return WoundChoiceResult(request, state, selected, (follow_up,))


def _build_follow_up(
    request: WoundEffectRequest,
    template: _FollowUpTemplate,
) -> WoundEffectFollowUp:
    if isinstance(template, WoundEnduranceFailure):
        return WoundEnduranceTestRequest(
            test_id=f"{request.id}:endurance",
            wound_sequence=request.wound_sequence,
            entry_id=request.entry_id,
            failure=template,
            rule_id=request.rule_id,
        )
    if isinstance(template, WoundConsequence):
        return WoundConsequenceRequest(
            request.wound_sequence,
            template,
            request.rule_id,
        )
    return WoundChoiceRequest(
        request.wound_sequence,
        template.options,
        request.rule_id,
    )


def _failed_test_condition(
    request: WoundEnduranceTestRequest,
) -> WoundConditionEffect | None:
    if request.failure is WoundEnduranceFailure.FALL_PRONE:
        return WoundConditionEffect(
            request.wound_sequence,
            Condition.PRONE,
            WoundEffectDuration.UNTIL_REMOVED,
        )
    if request.failure is WoundEnduranceFailure.BLINDED_UNTIL_END_OF_NEXT_TURN:
        return WoundConditionEffect(
            request.wound_sequence,
            Condition.BLINDED,
            WoundEffectDuration.END_OF_NEXT_TURN,
        )
    return None


def _with_added_effect(
    state: CharacterInjuryState,
    effect: WoundConditionEffect,
) -> CharacterInjuryState:
    effects = state.active_wound_effects
    if effect not in effects:
        effects = (*effects, effect)
    return CharacterInjuryState(
        wounds=state.wounds,
        conditions=state.conditions.with_condition(effect.condition),
        active_wound_effects=effects,
        dead=state.dead,
    )


def _validate_wound(
    sequence: int,
    entry_id: WoundEntryId,
    state: CharacterInjuryState,
) -> WoundRecord:
    if sequence > len(state.wounds):
        raise ValueError("Wound effect refers to a missing Wound")
    wound = state.wounds[sequence - 1]
    if wound.sequence != sequence or wound.entry_id is not entry_id:
        raise ValueError("Wound effect does not match the recorded Wound")
    return wound
