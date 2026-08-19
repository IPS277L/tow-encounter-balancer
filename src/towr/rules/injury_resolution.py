from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundResult,
    FixedCharacterWoundRequest,
    FixedCharacterWoundResult,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    ProfileWoundRequest,
    ProfileWoundResult,
    WoundEffectRequest,
    WoundNegationOption,
    WoundRecord,
    WoundRecordOrigin,
    WoundTableRoll,
)
from towr.rules.dice import RandomSource
from towr.rules.wound_table import lookup_wound


class MissingWoundDecisionError(RuntimeError):
    pass


class InvalidWoundDecisionError(ValueError):
    pass


class WoundDecisionProvider(Protocol):
    def choose_wound_negation(
        self,
        *,
        request: CharacterWoundRequest,
        table_roll: WoundTableRoll,
        options: tuple[WoundNegationOption, ...],
    ) -> str | None: ...


def resolve_character_wound(
    request: CharacterWoundRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> CharacterWoundResult:
    if request.state.dead:
        raise ValueError("a dead character cannot suffer another Wound")
    if request.negation_options and decisions is None:
        raise MissingWoundDecisionError(
            "Wound negation options require an explicit WoundDecisionProvider"
        )

    dice_delta = sum(modifier.amount for modifier in request.dice_modifiers)
    dice = max(
        1,
        request.base_dice + request.state.untreated_wounds + dice_delta,
    )
    values = tuple(rng.randint(1, 10) for _ in range(dice))
    total = sum(values)
    entry = lookup_wound(total)
    table_roll = WoundTableRoll(
        dice=dice,
        values=values,
        total=total,
        entry=entry,
    )

    negated_by = _choose_negation(request, table_roll, decisions)
    modifier_rule_ids = tuple(item.rule_id for item in request.dice_modifiers)
    if negated_by is not None:
        return CharacterWoundResult(
            request_id=request.id,
            subject_type=request.subject_type,
            state=request.state,
            table_roll=table_roll,
            wound_accepted=False,
            negated_by_rule_id=negated_by,
            effect_request=None,
            applied_rule_ids=(*modifier_rule_ids, negated_by),
        )

    sequence = len(request.state.wounds) + 1
    wound = WoundRecord(
        sequence=sequence,
        entry_id=entry.id,
        table_total=total,
        roll_values=values,
    )
    conditions = request.state.conditions.without_condition(Condition.STAGGERED)
    state = CharacterInjuryState(
        wounds=(*request.state.wounds, wound),
        conditions=conditions,
        active_wound_effects=request.state.active_wound_effects,
        dead=entry.lethal,
    )
    return CharacterWoundResult(
        request_id=request.id,
        subject_type=request.subject_type,
        state=state,
        table_roll=table_roll,
        wound_accepted=True,
        negated_by_rule_id=None,
        effect_request=WoundEffectRequest(
            id=f"{request.id}:effect",
            wound_sequence=sequence,
            entry_id=entry.id,
            rule_id=f"RULE-WOUND-TABLE:{entry.id.value}",
        ),
        applied_rule_ids=modifier_rule_ids,
    )


def resolve_fixed_character_wound(
    request: FixedCharacterWoundRequest,
) -> FixedCharacterWoundResult:
    """Apply a named Wounds Table entry without inventing a dice roll."""

    if request.state.dead:
        raise ValueError("a dead character cannot suffer another Wound")
    entry = lookup_wound(request.table_total)
    if entry.id is not request.entry_id:
        raise ValueError("fixed Wound entry must match its table total")

    sequence = len(request.state.wounds) + 1
    wound = WoundRecord(
        sequence=sequence,
        entry_id=entry.id,
        table_total=request.table_total,
        roll_values=(),
        origin=WoundRecordOrigin.FIXED_ENTRY,
    )
    state = CharacterInjuryState(
        wounds=(*request.state.wounds, wound),
        conditions=request.state.conditions.without_condition(
            Condition.STAGGERED
        ),
        active_wound_effects=request.state.active_wound_effects,
        dead=entry.lethal,
    )
    return FixedCharacterWoundResult(
        request_id=request.id,
        subject_type=request.subject_type,
        state=state,
        entry=entry,
        effect_request=WoundEffectRequest(
            id=f"{request.id}:effect",
            wound_sequence=sequence,
            entry_id=entry.id,
            rule_id=f"RULE-WOUND-TABLE:{entry.id.value}",
        ),
        applied_rule_ids=(request.source_rule_id,),
    )


def resolve_profile_wound(request: ProfileWoundRequest) -> ProfileWoundResult:
    if request.state.defeated:
        raise ValueError("a defeated NPC cannot suffer another Wound")

    additional = sum(item.count for item in request.additional_wounds)
    wounds_requested = request.base_wounds + additional
    current_wounds = min(
        request.state.wound_limit,
        request.state.wounds + wounds_requested,
    )
    wounds_inflicted = current_wounds - request.state.wounds
    defeated = current_wounds >= request.state.wound_limit
    state = ProfileInjuryState(
        wounds=current_wounds,
        wound_limit=request.state.wound_limit,
        conditions=request.state.conditions.without_condition(Condition.STAGGERED),
        defeated=defeated,
    )
    state_change = ProfileStateChangeRequest(
        npc_type=request.npc_type,
        previous_wounds=request.state.wounds,
        current_wounds=current_wounds,
        defeated=defeated,
    )
    return ProfileWoundResult(
        request_id=request.id,
        state=state,
        wounds_requested=wounds_requested,
        wounds_inflicted=wounds_inflicted,
        state_change=state_change,
        applied_rule_ids=tuple(item.rule_id for item in request.additional_wounds),
    )


def _choose_negation(
    request: CharacterWoundRequest,
    table_roll: WoundTableRoll,
    decisions: WoundDecisionProvider | None,
) -> str | None:
    if not request.negation_options:
        return None
    assert decisions is not None
    selected = decisions.choose_wound_negation(
        request=request,
        table_roll=table_roll,
        options=request.negation_options,
    )
    if selected is None:
        return None
    if not isinstance(selected, str):
        raise InvalidWoundDecisionError(
            "a Wound negation decision must be a rule ID or None"
        )
    allowed = {option.rule_id for option in request.negation_options}
    if selected not in allowed:
        raise InvalidWoundDecisionError(
            f"Wound negation rule is not available: {selected}"
        )
    return selected
