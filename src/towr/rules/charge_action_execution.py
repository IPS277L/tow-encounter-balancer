from __future__ import annotations

from dataclasses import replace

from towr.domain.charge_models import (
    ChargeActionExecutionRequest,
    ChargeActionExecutionResult,
    DifficultTerrainChargeActionExecutionRequest,
    DifficultTerrainChargeActionExecutionResult,
    LongChargeActionExecutionRequest,
    LongChargeActionExecutionResult,
    LongChargeOutcome,
)
from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.movement_models import MovementSpeed
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ManoeuvreKind,
)
from towr.rules.dice import RandomSource
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.kernel import ResolutionDecisionProvider, resolve_kernel_attack
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.test_resolution import resolve_test


CHARGE_ACTION_EXECUTION_RULE_ID = (
    "RULE-COMBAT-014:charge-action-execution"
)
CHARGE_MELEE_BONUS_RULE_ID = "RULE-COMBAT-009:charge-melee-bonus"
DIFFICULT_TERRAIN_CHARGE_ACTION_EXECUTION_RULE_ID = (
    "RULE-COMBAT-014:difficult-terrain-charge-action-execution"
)
LONG_CHARGE_ACTION_EXECUTION_RULE_ID = (
    "RULE-COMBAT-014:long-charge-action-execution"
)


def execute_charge_action(
    request: ChargeActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> ChargeActionExecutionResult:
    """Move to a Medium Range enemy and resolve the Charge attack."""
    if request.rule_id != CHARGE_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Charge request uses an unknown source rule")
    if request.melee_bonus_rule_id != CHARGE_MELEE_BONUS_RULE_ID:
        raise ValueError("Charge request uses an unknown Melee bonus rule")

    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.CHARGE
    ):
        raise ValueError("only a Charge Manoeuvre slot can use this executor")
    if slot.executed:
        raise ValueError("the Charge action slot has already been executed")

    if request.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Charge")
    if request.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    if request.actor_began_turn_in_enemy_close_range:
        raise ValueError("Charge cannot begin in Close Range of an enemy")
    if not request.reaches_target_close_range:
        raise ValueError("Charge movement must reach Close Range of the target")
    if request.crosses_obstacle:
        raise ValueError("Charge cannot cross a blocking obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError(
            "Difficult Terrain requires its Athletics movement phase"
        )

    spatial_state = request.spatial_state
    actor = spatial_state.placement_for(request.actor_id)
    target = spatial_state.placement_for(request.target_id)
    if not spatial_state.graph.are_adjacent(actor.zone_id, target.zone_id):
        raise ValueError("base Charge target must be at Medium Range")
    for entity_id in request.path_entity_ids:
        crossed = spatial_state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Charge cannot pass through an enemy")

    attack = request.kernel_request.attack
    if not attack.is_close_range:
        raise ValueError("Charge attack must resolve at Close Range")
    actor_is_staggered = request.actor_conditions.has(Condition.STAGGERED)
    if attack.attacker_is_staggered is not actor_is_staggered:
        raise ValueError("Charge attack has stale attacker Staggered state")
    if any(
        modifier.rule_id == request.melee_bonus_rule_id
        for modifier in attack.attacker_test.dice_modifiers
    ):
        raise ValueError("Charge Melee bonus is already present")

    melee_bonus = None
    prepared_kernel_request = request.kernel_request
    if request.attack_skill is Skill.MELEE:
        melee_bonus = DiceModifier(
            rule_id=request.melee_bonus_rule_id,
            amount=1,
        )
        prepared_attacker_test = replace(
            attack.attacker_test,
            dice_modifiers=(
                *attack.attacker_test.dice_modifiers,
                melee_bonus,
            ),
        )
        prepared_kernel_request = replace(
            request.kernel_request,
            attack=replace(
                attack,
                attacker_test=prepared_attacker_test,
            ),
        )

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=target.zone_id,
        )
        if placement.entity_id == request.actor_id
        else placement
        for placement in spatial_state.placements
    )
    updated_spatial_state = replace(
        spatial_state,
        placements=updated_placements,
    )

    resolution = resolve_kernel_attack(
        prepared_kernel_request,
        rng,
        decisions=decisions,
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=CHARGE_ACTION_EXECUTION_RULE_ID,
            source_request_id=request.id,
            result_request_id=resolution.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )

    applied_rule_ids = [
        CHARGE_ACTION_EXECUTION_RULE_ID,
        ZONE_GRAPH_RULE_ID,
    ]
    if melee_bonus is not None:
        applied_rule_ids.append(melee_bonus.rule_id)
    return ChargeActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        actor_id=request.actor_id,
        target_id=request.target_id,
        slot_index=request.slot_index,
        speed=request.speed,
        attack_skill=request.attack_skill,
        origin_zone_id=actor.zone_id,
        destination_zone_id=target.zone_id,
        target_in_close_range=True,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=spatial_state,
        spatial_state=updated_spatial_state,
        slot=executed_slot,
        source_kernel_request=request.kernel_request,
        kernel_request=prepared_kernel_request,
        resolution=resolution,
        melee_bonus=melee_bonus,
        applied_rule_ids=tuple(applied_rule_ids),
    )


def execute_difficult_terrain_charge_action(
    request: DifficultTerrainChargeActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> DifficultTerrainChargeActionExecutionResult:
    """Attack after consuming one proven Difficult Terrain crossing."""
    if request.rule_id != DIFFICULT_TERRAIN_CHARGE_ACTION_EXECUTION_RULE_ID:
        raise ValueError("terrain Charge uses an unknown source rule")
    source = request.charge_action
    traversal = request.terrain_traversal
    if source.melee_bonus_rule_id != CHARGE_MELEE_BONUS_RULE_ID:
        raise ValueError("Charge request uses an unknown Melee bonus rule")

    turn = request.round_state.active_turn
    assert turn is not None
    if source.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: source.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[source.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.CHARGE
    ):
        raise ValueError("only a Charge Manoeuvre slot can use this executor")
    if slot.executed:
        raise ValueError("the Charge action slot has already been executed")

    if source.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Charge")
    if source.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if source.actor_began_turn_in_enemy_close_range:
        raise ValueError("Charge cannot begin in Close Range of an enemy")
    if not source.reaches_target_close_range:
        raise ValueError("Charge movement must reach Close Range of the target")

    attack = source.kernel_request.attack
    if not attack.is_close_range:
        raise ValueError("Charge attack must resolve at Close Range")
    actor_is_staggered = traversal.conditions.has(Condition.STAGGERED)
    if attack.attacker_is_staggered is not actor_is_staggered:
        raise ValueError("Charge attack has stale post-terrain Staggered state")
    if any(
        modifier.rule_id == source.melee_bonus_rule_id
        for modifier in attack.attacker_test.dice_modifiers
    ):
        raise ValueError("Charge Melee bonus is already present")

    melee_bonus = None
    prepared_kernel_request = source.kernel_request
    if source.attack_skill is Skill.MELEE:
        melee_bonus = DiceModifier(
            rule_id=source.melee_bonus_rule_id,
            amount=1,
        )
        prepared_kernel_request = replace(
            source.kernel_request,
            attack=replace(
                attack,
                attacker_test=replace(
                    attack.attacker_test,
                    dice_modifiers=(
                        *attack.attacker_test.dice_modifiers,
                        melee_bonus,
                    ),
                ),
            ),
        )

    resolution = resolve_kernel_attack(
        prepared_kernel_request,
        rng,
        decisions=decisions,
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=resolution.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == source.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )
    return DifficultTerrainChargeActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        charge_action_request=source,
        terrain_traversal=traversal,
        actor_id=source.actor_id,
        target_id=source.target_id,
        slot_index=source.slot_index,
        speed=source.speed,
        attack_skill=source.attack_skill,
        origin_zone_id=traversal.origin_zone_id,
        destination_zone_id=traversal.destination_zone_id,
        target_in_close_range=True,
        previous_conditions=source.actor_conditions,
        conditions=traversal.conditions,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=request.spatial_state,
        spatial_state=request.spatial_state,
        slot=executed_slot,
        source_kernel_request=source.kernel_request,
        kernel_request=prepared_kernel_request,
        resolution=resolution,
        melee_bonus=melee_bonus,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    CHARGE_ACTION_EXECUTION_RULE_ID,
                    *traversal.applied_rule_ids,
                    *(
                        (melee_bonus.rule_id,)
                        if melee_bonus is not None
                        else ()
                    ),
                )
            )
        ),
    )


def execute_long_charge_action(
    request: LongChargeActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> LongChargeActionExecutionResult:
    """Test Athletics for a two-Zone Charge, then attack or stop short."""
    if request.rule_id != LONG_CHARGE_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Long Charge request uses an unknown source rule")
    if request.melee_bonus_rule_id != CHARGE_MELEE_BONUS_RULE_ID:
        raise ValueError("Long Charge request uses an unknown Melee bonus rule")

    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.CHARGE
    ):
        raise ValueError("only a Charge Manoeuvre slot can use this executor")
    if slot.executed:
        raise ValueError("the Charge action slot has already been executed")

    if request.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Charge")
    if request.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    if request.actor_began_turn_in_enemy_close_range:
        raise ValueError("Charge cannot begin in Close Range of an enemy")
    if not request.reaches_target_close_range:
        raise ValueError(
            "successful Long Charge must reach Close Range of the target"
        )
    if (
        request.actor_id
        in request.spatial_state.difficult_terrain_tested_entity_ids
    ):
        raise ValueError(
            "Long Charge Athletics is unavailable after a Difficult Terrain Test"
        )
    if request.crosses_obstacle:
        raise ValueError("Long Charge cannot cross a blocking obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError(
            "Long Charge Athletics cannot also resolve Difficult Terrain"
        )

    spatial_state = request.spatial_state
    actor = spatial_state.placement_for(request.actor_id)
    target = spatial_state.placement_for(request.target_id)
    graph = spatial_state.graph
    if graph.are_adjacent(actor.zone_id, target.zone_id):
        raise ValueError("Long Charge target must be at Long, not Medium Range")
    if not graph.are_adjacent(
        actor.zone_id,
        request.intermediate_zone_id,
    ) or not graph.are_adjacent(
        request.intermediate_zone_id,
        target.zone_id,
    ):
        raise ValueError("Long Charge route must cross exactly two Zone links")
    for entity_id in request.path_entity_ids:
        crossed = spatial_state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Long Charge cannot pass through an enemy")

    attack = request.kernel_request.attack
    if not attack.is_close_range:
        raise ValueError("Long Charge attack must resolve at Close Range")
    actor_is_staggered = request.actor_conditions.has(Condition.STAGGERED)
    if attack.attacker_is_staggered is not actor_is_staggered:
        raise ValueError("Long Charge attack has stale attacker Staggered state")
    if any(
        modifier.rule_id == request.melee_bonus_rule_id
        for modifier in attack.attacker_test.dice_modifiers
    ):
        raise ValueError("Charge Melee bonus is already present")

    athletics_result = resolve_test(
        request.athletics_test,
        rng,
        decisions=decisions,
    )
    stagger_application = None
    conditions = request.actor_conditions
    melee_bonus = None
    prepared_kernel_request = request.kernel_request
    resolution = None

    if athletics_result.succeeded:
        outcome = LongChargeOutcome.REACHED_TARGET_AND_ATTACKED
        final_zone_id = target.zone_id
        if request.attack_skill is Skill.MELEE:
            melee_bonus = DiceModifier(
                rule_id=request.melee_bonus_rule_id,
                amount=1,
            )
            prepared_attacker_test = replace(
                attack.attacker_test,
                dice_modifiers=(
                    *attack.attacker_test.dice_modifiers,
                    melee_bonus,
                ),
            )
            prepared_kernel_request = replace(
                request.kernel_request,
                attack=replace(
                    attack,
                    attacker_test=prepared_attacker_test,
                ),
            )
    else:
        final_zone_id = request.intermediate_zone_id

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=final_zone_id,
        )
        if placement.entity_id == request.actor_id
        else placement
        for placement in spatial_state.placements
    )
    updated_spatial_state = replace(
        spatial_state,
        placements=updated_placements,
    )

    if athletics_result.succeeded:
        resolution = resolve_kernel_attack(
            prepared_kernel_request,
            rng,
            decisions=decisions,
        )
        receipt_result_id = resolution.request_id
    else:
        stagger_application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{request.id}:staggered",
                state=request.actor_conditions,
                condition=Condition.STAGGERED,
                source_rule_id=request.rule_id,
            )
        )
        conditions = stagger_application.state
        outcome = (
            LongChargeOutcome.STOPPED_SHORT_ALREADY_STAGGERED
            if stagger_application.was_already_present
            else LongChargeOutcome.STOPPED_SHORT_STAGGERED
        )
        receipt_result_id = request.id
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=LONG_CHARGE_ACTION_EXECUTION_RULE_ID,
            source_request_id=request.id,
            result_request_id=receipt_result_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )

    return LongChargeActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        actor_id=request.actor_id,
        target_id=request.target_id,
        slot_index=request.slot_index,
        speed=request.speed,
        athletics_skill=request.skill,
        attack_skill=request.attack_skill,
        athletics_test_request=request.athletics_test,
        athletics_test_result=athletics_result,
        outcome=outcome,
        origin_zone_id=actor.zone_id,
        intermediate_zone_id=request.intermediate_zone_id,
        target_zone_id=target.zone_id,
        target_in_close_range=athletics_result.succeeded,
        previous_conditions=request.actor_conditions,
        conditions=conditions,
        stagger_application=stagger_application,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=spatial_state,
        spatial_state=updated_spatial_state,
        slot=executed_slot,
        source_kernel_request=request.kernel_request,
        kernel_request=prepared_kernel_request,
        resolution=resolution,
        melee_bonus=melee_bonus,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    LONG_CHARGE_ACTION_EXECUTION_RULE_ID,
                    ZONE_GRAPH_RULE_ID,
                    *athletics_result.trace.applied_rule_ids,
                    *(
                        stagger_application.applied_rule_ids
                        if stagger_application is not None
                        else ()
                    ),
                    *(
                        (melee_bonus.rule_id,)
                        if melee_bonus is not None
                        else ()
                    ),
                )
            )
        ),
    )
