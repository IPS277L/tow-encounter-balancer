"""Source-bound result of the narrow ADR-0035 Casting composition.

Guards validate recorded normal rolls and phase links without invoking rules
or RNG. Returned states are projections, not separately supplied snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.action_execution_models import CastingAttemptExecutionResult, CastingActionPostTestResult
from towr.domain.condition_models import Condition, ConditionApplicationResult, EffectApplicationResult
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingRequest
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import (
    COWARDLY_FLIGHT_SPELL_DEFINITION as SPELL,
    CastingChoice, CastingDecisionResult, CastingTestResult, IdentifiedSpellTarget,
    MiscastPoolIncreaseRequest, MiscastPoolIncreaseSourceKind, MiscastPoolOutcome,
    MiscastPoolResolutionResult, MiscastRollRequest, SpellCastRequest,
    SpellCastExecutionRequest, SpellCastExecutionResult, SpellCastTargetResult,
    SpellEffectApplicationRequest, SpellPotencyResult, SpellTargetPreflightOutcome,
    SpellTargetPreflightResult, WizardMagicState,
)
from towr.domain.resolution_models import (
    CowardlyFlightMovementCompletion, CowardlyFlightMovementFollowUp, GiveGroundRequest,
    CowardlyFlightResult, CowardlyFlightWillpowerRequest, CowardlyFlightWillpowerResult,
    CowardlyFlightWillpowerBatchResult, CowardlyFlightZoneBatchResult,
)
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import InlineProfile, RollTrace, TestQuality, TestRequest, TestResult
from towr.domain.turn_models import CombatRoundState


class CowardlyFlightCastingStatus(str, Enum):
    WAITING = "waiting"
    MOVEMENT_REQUIRED = "movement_required"
    SPELL_RESOLVED = "spell_resolved"
    MISCAST_REQUIRED = "miscast_required"


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingTargetState:
    actor_id: str
    injury: ProfileInjuryState

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str):
            raise TypeError("target actor_id must be a string")
        if not self.actor_id.strip():
            raise ValueError("target actor_id must not be empty")
        if not isinstance(self.injury, ProfileInjuryState):
            raise TypeError("target injury must be a ProfileInjuryState")


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingResult:
    source: CowardlyFlightCastingRequest
    execution: CastingAttemptExecutionResult
    post_test: CastingActionPostTestResult
    status: CowardlyFlightCastingStatus
    preflight: SpellTargetPreflightResult | None = None
    spell: SpellCastExecutionResult | None = None
    zone: CowardlyFlightZoneBatchResult | None = None
    willpower: CowardlyFlightWillpowerBatchResult | None = None

    def __post_init__(self) -> None:
        for value, kind in ((self.source, CowardlyFlightCastingRequest),
                            (self.execution, CastingAttemptExecutionResult),
                            (self.post_test, CastingActionPostTestResult),
                            (self.status, CowardlyFlightCastingStatus)):
            if not isinstance(value, kind):
                raise TypeError(f"Casting result requires {kind.__name__}")
        _validate_casting(self)
        _validate_post_test(self)
        if self.status in (CowardlyFlightCastingStatus.SPELL_RESOLVED,
                           CowardlyFlightCastingStatus.MOVEMENT_REQUIRED):
            for value, kind in ((self.preflight, SpellTargetPreflightResult),
                                (self.spell, SpellCastExecutionResult),
                                (self.zone, CowardlyFlightZoneBatchResult)):
                if not isinstance(value, kind):
                    raise TypeError(f"resolved spell requires {kind.__name__}")
            if self.status is CowardlyFlightCastingStatus.SPELL_RESOLVED:
                if not isinstance(self.willpower, CowardlyFlightWillpowerBatchResult):
                    raise TypeError("resolved spell requires CowardlyFlightWillpowerBatchResult")
            elif self.willpower is not None:
                raise ValueError("pending movement cannot contain Willpower results")
            _validate_spell(self)
        elif any(v is not None for v in (self.preflight, self.spell, self.zone, self.willpower)):
            raise ValueError("WAIT/Miscast cannot contain spell phases")

    @property
    def round_state(self) -> CombatRoundState:
        return self.execution.state

    @property
    def magic_state(self) -> WizardMagicState:
        return self.post_test.state

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source.spatial_state if self.willpower is None else self.willpower.spatial_state

    @property
    def pending_movements(self) -> tuple[CowardlyFlightMovementFollowUp, ...]:
        return (self.zone.movement_follow_ups
                if self.status is CowardlyFlightCastingStatus.MOVEMENT_REQUIRED else ())

    @property
    def pending_miscast(self) -> MiscastRollRequest | None:
        pool = self.post_test.miscast_pool
        return None if pool is None else pool.roll_request

    @property
    def targets(self) -> tuple[CowardlyFlightCastingTargetState, ...]:
        states = {} if self.willpower is None else {t.target_id: t.state for t in self.willpower.targets}
        return tuple(CowardlyFlightCastingTargetState(t.actor_id, states.get(t.actor_id, t.injury))
                     for t in self.source.targets)


def _equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"Casting result {label} does not match its source")


def _normal_test(test: TestResult, identifier: str, profile: InlineProfile,
                 rule_ids: tuple[str, ...] = ()) -> None:
    if not isinstance(test, TestResult) or not isinstance(test.trace, RollTrace):
        raise TypeError("Casting composition requires a typed TestResult/RollTrace")
    values = test.trace.initial_values
    if (not isinstance(values, tuple) or len(values) != profile.dice
            or any(type(v) is not int or not 1 <= v <= 10 for v in values)):
        raise ValueError("Casting composition requires the exact normal d10 pool")
    successes = sum(v <= profile.threshold for v in values)
    _equal(test.trace, RollTrace(
        identifier, profile.dice, profile.maximum_dice, 0, 0, profile.dice, profile.dice,
        profile.threshold, False, TestQuality.NORMAL, values, (), values,
        successes, 0, successes, rule_ids,
    ), "normal Test trace/profile")


def _validate_casting(result: CowardlyFlightCastingResult) -> None:
    source, execution = result.source, result.execution
    casting = execution.casting
    _equal(execution.previous_state, source.round_state, "previous round")
    _equal((execution.request_id, execution.actor_id, execution.slot_index),
           (source.id, source.actor_id, source.slot_index), "action identity")
    _normal_test(casting.test, source.id + ":willpower", source.caster.casting_profile,
                 ("RULE-MAGIC-003:rule-of-nine",))
    added = casting.test.trace.final_values.count(9)
    follow_ups = () if not added else (MiscastPoolIncreaseRequest(
        source.id + ":casting:rule-of-nine", source.actor_id, added,
        MiscastPoolIncreaseSourceKind.TEST, source.id + ":willpower",
        "RULE-MAGIC-004:casting-test", "RULE-MAGIC-003:rule-of-nine",
    ),)
    _equal(casting, CastingTestResult(
        source.id + ":casting", source.actor_id, SPELL.lore_id, casting.test,
        replace(source.magic_state, casting_lore_id=SPELL.lore_id,
                casting_successes=source.magic_state.casting_successes + casting.test.successes,
                latest_casting_roll_successes=casting.test.successes),
        source.magic_state.casting_successes, casting.test.successes, added, follow_ups,
        ("RULE-MAGIC-004:casting-test", "RULE-MAGIC-003:rule-of-nine"),
    ), "Casting Test/state/follow-ups")
    _equal(execution.applied_rule_ids, ("RULE-COMBAT-004:casting-improvise-execution",), "action rules")


def _validate_post_test(result: CowardlyFlightCastingResult) -> None:
    source, execution = result.source, result.execution
    casting = execution.casting
    identifier = source.id + ":post-test"
    state = replace(casting.state, miscast_dice=source.magic_state.miscast_dice + casting.miscast_dice_added)
    triggered = state.miscast_dice > source.caster.wizard_level
    pool = None
    if casting.miscast_dice_added:
        roll = None if not triggered else MiscastRollRequest(
            identifier + ":miscast-pool", casting.follow_ups[0].resolution_id,
            source.actor_id, state.miscast_dice, rule_id="RULE-MAGIC-004:miscast-pool")
        pool = MiscastPoolResolutionResult(
            identifier + ":miscast-pool", source.actor_id, state, source.magic_state.miscast_dice,
            casting.miscast_dice_added,
            MiscastPoolOutcome.MISCAST_TRIGGERED if triggered else MiscastPoolOutcome.ACCUMULATED,
            roll, ("RULE-MAGIC-004:casting-test", "RULE-MAGIC-003:rule-of-nine", "RULE-MAGIC-004:miscast-pool"),
        )
    decision = None
    if triggered:
        expected_status = CowardlyFlightCastingStatus.MISCAST_REQUIRED
    else:
        ready = state.casting_successes >= SPELL.casting_value
        expected_status = (CowardlyFlightCastingStatus.SPELL_RESOLVED if ready
                           else CowardlyFlightCastingStatus.WAITING)
        if (ready and casting.latest_roll_successes > 0
                and any(t.can_give_ground for t in source.targets)
                and result.status is CowardlyFlightCastingStatus.MOVEMENT_REQUIRED):
            expected_status = CowardlyFlightCastingStatus.MOVEMENT_REQUIRED
        cast = () if not ready else (SpellCastRequest(
            identifier + ":decision:cast", source.actor_id, SPELL.rule_id, SPELL.lore_id,
            SPELL.casting_value, casting.latest_roll_successes, "RULE-MAGIC-004:cast-or-wait"),)
        previous = state.casting_successes
        if ready:
            state = WizardMagicState(miscast_dice=state.miscast_dice)
        decision = CastingDecisionResult(
            identifier + ":decision", source.actor_id, CastingChoice.CAST if ready else CastingChoice.WAIT,
            state, previous, casting.latest_roll_successes if ready else None, cast,
            ("RULE-MAGIC-004:cast-or-wait",),
        )
    _equal(result.status, expected_status, "branch")
    rules = ("RULE-COMBAT-004:casting-post-test", *(pool.applied_rule_ids if pool else ()),
             *(decision.applied_rule_ids if decision else ()))
    _equal(result.post_test, CastingActionPostTestResult(
        identifier, execution, source.caster.wizard_level, state, pool, decision,
        tuple(dict.fromkeys(rules)),
    ), "post-Test source/state/decision")


def _validate_spell(result: CowardlyFlightCastingResult) -> None:
    source = result.source
    cast = result.post_test.decision.follow_ups[0]
    preflight_id = source.id + ":preflight"
    execution_id = preflight_id + ":targets"
    _equal(result.preflight, SpellTargetPreflightResult(
        preflight_id, cast.resolution_id, source.selected_zone_id, SpellTargetPreflightOutcome.READY,
        SPELL, SpellCastExecutionRequest(execution_id, cast, source.selected_zone_id,
                                       tuple(IdentifiedSpellTarget(t.actor_id) for t in source.targets)),
        ("RULE-MAGIC-005:spell-schema", SPELL.rule_id),
    ), "spell preflight")
    potency = cast.base_potency
    effects = []
    spell_targets = []
    zone_targets = []
    willpower_requests = []
    movement_requests = []
    for index, target in enumerate(source.targets):
        prefix = f"{execution_id}:target:{index}"
        effect = None
        if potency:
            effect = SpellEffectApplicationRequest(
                prefix + ":effect", cast.resolution_id, source.actor_id, SPELL.rule_id,
                SPELL.lore_id, target.actor_id, potency, SPELL.rule_id)
            effects.append(effect)
            application = EffectApplicationResult(
                effect.resolution_id + f":{target.actor_id}:source", False,
                SPELL.rule_id, None, (SPELL.rule_id,))
            willpower = CowardlyFlightWillpowerRequest(
                effect.resolution_id + f":{target.actor_id}:willpower", target.actor_id, potency,
                TestRequest(effect.resolution_id + ":willpower", target.willpower_profile),
                target.injury, application, SPELL.rule_id)
            willpower_requests.append(willpower)
            movements = ()
            if target.can_give_ground:
                movement = GiveGroundRequest(
                    effect.resolution_id + f":{target.actor_id}:give-ground", SPELL.rule_id)
                movements = (movement,)
                movement_requests.append(CowardlyFlightMovementFollowUp(target.actor_id, movement))
            zone_targets.append(CowardlyFlightResult(
                effect.resolution_id, target.actor_id, application, (*movements, willpower)))
        spell_targets.append(SpellCastTargetResult(target.actor_id, SpellPotencyResult(
            prefix + ":potency", SPELL.rule_id, target.actor_id, potency, 0, potency, potency > 0, ()), effect))
    spell_rules = ("RULE-MAGIC-002:target-scoped-potency",)
    _equal(result.spell, SpellCastExecutionResult(
        execution_id, cast.resolution_id, source.actor_id, SPELL.rule_id, SPELL.lore_id,
        source.selected_zone_id, tuple(spell_targets), tuple(effects), spell_rules,
    ), "spell target source/Potency/order")
    zone_rules = (*spell_rules, SPELL.rule_id)
    _equal(result.zone, CowardlyFlightZoneBatchResult(
        source.id + ":zone", execution_id, source.actor_id, SPELL.rule_id, SPELL.lore_id,
        source.selected_zone_id, tuple(zone_targets), tuple(movement_requests), tuple(willpower_requests), zone_rules,
    ), "Zone source/effects/contexts")
    if result.status is CowardlyFlightCastingStatus.MOVEMENT_REQUIRED:
        if not movement_requests:
            raise ValueError("pending movement requires a positive Give Ground effect")
        return
    batch = result.willpower
    validate_cowardly_flight_casting_movements(result, batch.completed_movements, batch.spatial_state)
    movements_by_target = {item.source.target_id: item.resolution for item in batch.completed_movements}
    if not isinstance(batch.targets, tuple) or len(batch.targets) != len(willpower_requests):
        raise ValueError("Willpower results must match positive effect targets exactly")
    for request, resolved in zip(willpower_requests, batch.targets):
        movement = movements_by_target.get(request.target_id)
        if movement is not None:
            request = replace(request, target_state=replace(request.target_state, conditions=movement.conditions))
        if not isinstance(resolved, CowardlyFlightWillpowerResult):
            raise TypeError("Willpower result must be typed")
        _normal_test(resolved.test, request.test.id, request.test.profile)
        resisted = resolved.test.successes >= request.potency
        state = request.target_state
        application = None
        if not resisted:
            state = replace(state, conditions=state.conditions.with_condition(Condition.BROKEN))
            application = ConditionApplicationResult(
                request.id + ":broken", state.conditions, Condition.BROKEN,
                request.target_state.conditions.has(Condition.BROKEN), False,
                SPELL.rule_id, None, (SPELL.rule_id,))
        _equal(resolved, CowardlyFlightWillpowerResult(
            request.id, request.target_id, resolved.test, resisted, state, application, (SPELL.rule_id,),
        ), "Willpower source/state/Broken")
    _equal(batch, CowardlyFlightWillpowerBatchResult(
        source.id + ":willpower-batch", result.zone.request_id, execution_id, source.actor_id,
        SPELL.rule_id, SPELL.lore_id, source.selected_zone_id, batch.spatial_state,
        batch.completed_movements, batch.targets,
        tuple(dict.fromkeys((*zone_rules, *(rule_id for item in batch.completed_movements
                                           for rule_id in item.resolution.applied_rule_ids)))),
    ), "Willpower batch source/spatial")


def validate_cowardly_flight_casting_movements(
    casting: CowardlyFlightCastingResult,
    completions: tuple[CowardlyFlightMovementCompletion, ...],
    final_spatial: SpatialBattleState,
) -> None:
    """Validate the complete ordered movement chain against the Casting source.

    No movement, Test or route selection occurs here. PG1.4 pp119, 162.
    Full GiveGround source requests are mandatory at this M8 boundary.
    """
    if not isinstance(completions, tuple) or not all(
        isinstance(c, CowardlyFlightMovementCompletion) for c in completions
    ):
        raise TypeError("Casting movements must be a tuple of typed completions")
    if not isinstance(final_spatial, SpatialBattleState):
        raise TypeError("Casting movement completion requires typed final spatial state")
    if tuple(c.source for c in completions) != casting.zone.movement_follow_ups:
        raise ValueError("Casting movements must match every pending follow-up in order")
    spatial = casting.source.spatial_state
    targets = {t.actor_id: t for t in casting.source.targets}
    for completion in completions:
        movement = completion.resolution
        request = movement.source_request
        if request is None:
            raise ValueError("Casting movement requires its complete source request")
        target = targets[completion.source.target_id]
        if (request.state != spatial or request.away_from_entity_id != casting.source.actor_id
                or request.mover_conditions != target.injury.conditions
                or movement.origin_zone_id != casting.source.selected_zone_id):
            raise ValueError("Casting movement source/spatial/caster/Conditions differ")
        if (request.mover_id in spatial.gave_ground_entity_ids
                or request.mover_conditions.has(Condition.PRONE)
                or request.mover_conditions.has(Condition.DEFENCELESS)
                or request.crosses_obstacle or request.crosses_difficult_terrain):
            raise ValueError("Casting movement is unavailable in the current round/route")
        mover = spatial.placement_for(request.mover_id)
        if any(spatial.placement_for(i).side_id != mover.side_id for i in request.path_entity_ids):
            raise ValueError("Casting movement cannot cross an enemy")
        # Distances validate the recorded direction; they do not select a route.
        distances = {spatial.placement_for(casting.source.actor_id).zone_id: 0}
        frontier = list(distances)
        for zone_id in frontier:
            for adjacent in spatial.graph.adjacent_zone_ids(zone_id):
                if adjacent not in distances:
                    distances[adjacent] = distances[zone_id] + 1
                    frontier.append(adjacent)
        origin = distances.get(mover.zone_id)
        destination = distances.get(request.destination_zone_id)
        if origin is None or destination is None or destination <= origin:
            raise ValueError("Casting Give Ground must move away from the caster")
        expected_rules = tuple(dict.fromkeys((
            request.source.rule_id, "RULE-COMBAT-011:zones-and-ranges", "RULE-COMBAT-015:give-ground")))
        _equal(movement.applied_rule_ids, expected_rules, "movement trace")
        spatial = movement.state
    _equal(final_spatial, spatial, "final movement state")
