from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundResult,
    FixedCharacterWoundRequest,
    FixedCharacterWoundResult,
    FixedWoundTableSelection,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    ProfileWoundRequest,
    ProfileWoundResult,
    WoundEffectRequest,
    WoundNegationOption,
    WoundRecord,
    WoundRecordOrigin,
    WoundTableRoll,
    wound_adrenaline_conditions,
    _expected_profile_wound_result,
    _validate_profile_wound_source,
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
        table_roll: WoundTableRoll | FixedWoundTableSelection,
        options: tuple[WoundNegationOption, ...],
    ) -> str | None: ...

    def choose_profile_wound_negation(self, *, request: ProfileWoundRequest,
            options: tuple[WoundNegationOption, ...]) -> str | None: ...


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

    if request.fixed_entry is not None:
        entry = lookup_wound(request.fixed_entry.table_total)
        table_roll = FixedWoundTableSelection(request.fixed_entry, entry)
        values, total = table_roll.values, table_roll.total
    else:
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
    if request.fixed_entry is not None:
        modifier_rule_ids = (*modifier_rule_ids, request.fixed_entry.rule_id)
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
        origin=(WoundRecordOrigin.FIXED_ENTRY if request.fixed_entry is not None
            else WoundRecordOrigin.TABLE_ROLL),
    )
    conditions = wound_adrenaline_conditions(request.state)
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
        conditions=wound_adrenaline_conditions(request.state),
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


def resolve_profile_wound(request: ProfileWoundRequest, *,
        decisions: WoundDecisionProvider | None = None) -> ProfileWoundResult:
    _validate_profile_wound_source(request)
    selected = None
    if request.negation_options:
        selector = getattr(decisions, 'choose_profile_wound_negation', None)
        if not callable(selector):
            raise MissingWoundDecisionError('profile Wound negation requires an explicit decision provider')
        selected = selector(request=request, options=request.negation_options)
        if selected is not None and (type(selected) is not str
                or selected not in {option.rule_id for option in request.negation_options}):
            raise InvalidWoundDecisionError('profile Wound negation selected an unavailable Rule ID')
    return _expected_profile_wound_result(request, selected)


def _choose_negation(
    request: CharacterWoundRequest,
    table_roll: WoundTableRoll | FixedWoundTableSelection,
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
