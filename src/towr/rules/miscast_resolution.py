from __future__ import annotations

from dataclasses import replace

from towr.domain.magic_models import (
    MiscastPreparationRequest,
    MiscastPreparationResult,
    MiscastRollRequest,
    MiscastRollResult,
    MiscastTableEffectRequest,
    SpellCastRequest,
    WizardMagicState,
)
from towr.rules.dice import RandomSource
from towr.rules.miscast_table import lookup_miscast


def prepare_miscast(
    request: MiscastPreparationRequest,
) -> MiscastPreparationResult:
    spell = request.spell_to_cast
    bonus_dice = 1 if spell is not None else 0
    roll_request = replace(
        request.source,
        resolution_id=f"{request.id}:roll",
        bonus_dice=bonus_dice,
    )
    follow_ups: tuple[SpellCastRequest | MiscastRollRequest, ...]
    if spell is None:
        follow_ups = (roll_request,)
    else:
        follow_ups = (
            SpellCastRequest(
                resolution_id=f"{request.id}:cast-before-miscast",
                caster_id=request.source.target_id,
                spell_rule_id=spell.spell_rule_id,
                lore_id=spell.lore_id,
                casting_value=spell.casting_value,
                base_potency=request.state.latest_casting_roll_successes,
                rule_id=request.rule_id,
            ),
            roll_request,
        )
    return MiscastPreparationResult(
        request_id=request.id,
        target_id=request.source.target_id,
        state=replace(
            request.state,
            casting_successes=0,
            casting_lore_id=None,
            latest_casting_roll_successes=0,
        ),
        previous_casting_successes=request.state.casting_successes,
        follow_ups=follow_ups,
        applied_rule_ids=(request.rule_id,),
    )


def resolve_miscast_roll(
    request: MiscastRollRequest,
    state: WizardMagicState,
    rng: RandomSource,
) -> MiscastRollResult:
    if not isinstance(state, WizardMagicState):
        raise TypeError("state must be a WizardMagicState")
    if state.miscast_dice != request.pool_dice_count:
        raise ValueError("Miscast Pool state must match the roll request")
    if state.casting_lore_id is not None:
        raise ValueError(
            "the active Casting Test must be resolved before the Miscast roll"
        )

    values = tuple(rng.randint(1, 10) for _ in range(request.dice_count))
    total = sum(values)
    entry = lookup_miscast(total)
    effect_rule_id = f"RULE-MISCAST-TABLE:{entry.id.value}"
    effect_request = MiscastTableEffectRequest(
        resolution_id=f"{request.resolution_id}:effect",
        source_roll_id=request.resolution_id,
        target_id=request.target_id,
        entry=entry,
        roll_values=values,
        total=total,
        pool_dice_count=request.pool_dice_count,
        bonus_dice=request.bonus_dice,
        rule_id=effect_rule_id,
    )
    return MiscastRollResult(
        request_id=request.resolution_id,
        target_id=request.target_id,
        state=state,
        roll_values=values,
        total=total,
        entry=entry,
        effect_request=effect_request,
        applied_rule_ids=(request.rule_id, effect_rule_id),
    )
