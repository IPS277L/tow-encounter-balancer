"""Finite M8 composition probe using public K1 APIs, not a battle simulator."""
from dataclasses import replace
from random import getstate

from towr.domain.action_execution_models import CastingAttemptExecutionRequest, CastingActionPostTestRequest
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import (
    CastingChoice, CastingDecisionRequest, CastingSpellSelection, CastingTestRequest,
    IdentifiedSpellTarget, MiscastPoolOutcome, MiscastPoolResolutionRequest,
    SpellTargetKind, SpellTargetPreflightRequest, WizardMagicState,
)
from towr.domain.resolution_models import (
    CowardlyFlightSpellEffectRequest, CowardlyFlightZoneBatchRequest,
    CowardlyFlightWillpowerBatchRequest,
)
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest, ImproviseKind,
)
from towr.rules.casting_action_execution import execute_casting_attempt, resolve_casting_action_post_test
from towr.rules.cowardly_flight_resolution import (
    COWARDLY_FLIGHT_SPELL_DEFINITION as SPELL, resolve_cowardly_flight_zone_batch,
    resolve_cowardly_flight_willpower_batch,
)
from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase
from towr.rules.spell_cast_execution import resolve_spell_cast_targets
from towr.rules.spell_target_preflight import resolve_spell_target_preflight
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


class ScriptedDice:
    def __init__(self, values):
        self.values = tuple(values)
        self.used = 0

    def randint(self, a, b):
        assert (a, b) == (1, 10)
        assert self.used < len(self.values), "unexpected RNG call"
        value = self.values[self.used]
        self.used += 1
        return value

    def exhausted(self):
        assert self.used == len(self.values)


def action(magic, label, round_number):
    """Caller supplies an activation; this probe does not advance a battle."""
    state = CombatRoundState(round_number, (
        CombatTurnParticipant("wizard", CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant("first", CombatSide.OPPOSITION),
        CombatTurnParticipant("second", CombatSide.OPPOSITION),
    ))
    state = start_combat_turn(CombatTurnStartRequest(label + ":turn", state, "wizard")).state
    state = reserve_combat_action_slot(CombatActionSlotRequest(
        label + ":slot", state, "wizard",
        CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                               improvise_approach_id=SPELL.lore_id), ActionSlotGrant.STANDARD,
    )).state
    return CastingAttemptExecutionRequest(label, state, "wizard", 1, CastingTestRequest(
        label + ":casting", "wizard", SPELL.lore_id,
        TestRequest(label + ":willpower", InlineProfile(3, 3)), magic,
    ))


def post_test(execution, level=2):
    identifier = execution.request_id + ":post-test"
    state = execution.casting.state
    triggered = False
    if execution.casting.follow_ups:
        # Pure projection for the required decision snapshot; no RNG or mutation.
        pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest(
            identifier + ":miscast-pool", execution.casting.follow_ups[0], state, level))
        state = pool.state
        triggered = pool.outcome is MiscastPoolOutcome.MISCAST_TRIGGERED
    decision = None
    if not triggered:
        ready = state.casting_successes >= SPELL.casting_value
        decision = CastingDecisionRequest(
            identifier + ":decision", "wizard", state, level,
            CastingChoice.CAST if ready else CastingChoice.WAIT,
            CastingSpellSelection(SPELL.rule_id, SPELL.lore_id, SPELL.casting_value) if ready else None,
        )
    return resolve_casting_action_post_test(CastingActionPostTestRequest(
        identifier, execution, level, decision))


def spell_effect(post, rng, target_ids=("first", "second")):
    source = post.decision.follow_ups[0]
    preflight = resolve_spell_target_preflight(SpellTargetPreflightRequest(
        source.resolution_id + ":schema", source, SPELL, "arena", SpellTargetKind.ZONE, True,
        tuple(IdentifiedSpellTarget(actor) for actor in target_ids),
    ))
    execution = resolve_spell_cast_targets(preflight.execution_request)
    contexts = tuple(CowardlyFlightSpellEffectRequest(
        effect, False, TestRequest(effect.resolution_id + ":willpower", InlineProfile(3, 3)),
        ProfileInjuryState(0, 1),
    ) for effect in execution.follow_ups)
    batch = resolve_cowardly_flight_zone_batch(CowardlyFlightZoneBatchRequest(
        source.resolution_id + ":zone", execution, contexts))
    assert not batch.movement_follow_ups
    spatial = SpatialBattleState(ZoneGraph(("arena", "elsewhere"), ()), (
        SpatialEntityPlacement("wizard", CombatSide.PLAYERS_AND_ALLIES.value, "arena"),
        *(SpatialEntityPlacement(actor, CombatSide.OPPOSITION.value,
                                 "arena" if actor in target_ids else "elsewhere")
          for actor in ("first", "second")),
    ))
    result = resolve_cowardly_flight_willpower_batch(CowardlyFlightWillpowerBatchRequest(
        source.resolution_id + ":willpower-batch", batch, spatial, ()), rng)
    return execution, result


def main():
    before = getstate()
    fresh = WizardMagicState()
    request = action(fresh, "first-action", 1)
    dice = ScriptedDice([1, 10, 10])
    first = execute_casting_attempt(request, dice)
    wait = post_test(first)
    assert wait.decision.choice is CastingChoice.WAIT and wait.state.casting_successes == 1
    assert first.slot.executed and fresh == WizardMagicState()
    dice.exhausted()

    # A later caller-supplied action receives the returned magic snapshot unchanged.
    dice = ScriptedDice([1, 2, 10, 1, 2, 10, 10, 10, 10])
    second = execute_casting_attempt(action(wait.state, "second-action", 2), dice)
    cast = post_test(second)
    assert cast.decision.previous_casting_successes == 3
    assert cast.decision.base_potency == 2 and cast.state.casting_lore_id is None
    _, effects = spell_effect(cast, dice)
    assert effects.targets[0].resisted and not effects.targets[1].resisted
    assert effects.targets[1].state.conditions.has(Condition.BROKEN)
    assert effects.spatial_state.placement_for("second").zone_id == "arena"
    dice.exhausted()

    # Existing accumulated successes may have been deliberately held by the caller.
    held = WizardMagicState(casting_successes=3, casting_lore_id=SPELL.lore_id,
                            latest_casting_roll_successes=3)
    dice = ScriptedDice([10, 10, 10])
    zero = post_test(execute_casting_attempt(action(held, "zero-potency", 3), dice))
    targets, effects = spell_effect(zero, dice)
    assert zero.decision.base_potency == 0 and len(targets.targets) == 2
    assert not targets.follow_ups and not effects.targets
    dice.exhausted()

    dice = ScriptedDice([1, 2, 3])
    empty = post_test(execute_casting_attempt(action(fresh, "empty-zone", 1), dice))
    targets, effects = spell_effect(empty, dice, ())
    assert not targets.targets and not effects.targets
    dice.exhausted()

    for old_pool in (1, 2):
        dice = ScriptedDice([9, 1, 10])
        outcome = post_test(execute_casting_attempt(action(
            WizardMagicState(miscast_dice=old_pool), f"pool-{old_pool}", 1), dice))
        assert outcome.state.miscast_dice == old_pool + 1
        if old_pool == 1:
            assert outcome.decision.choice is CastingChoice.WAIT
            assert outcome.miscast_pool.roll_request is None
        else:
            assert outcome.decision is None
            assert outcome.miscast_pool.roll_request.pool_dice_count == 3
            assert outcome.state.casting_successes == 1
            # Required Miscast remains pending; no table roll, reset or battle continuation.
        dice.exhausted()

    for change in ({"state": first.state}, {"actor_id": "first"}):
        dice = ScriptedDice([])
        try:
            execute_casting_attempt(replace(request, **change), dice)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid action accepted")
        dice.exhausted()
    assert getstate() == before
    print("Casting action receipt; WAIT -> CAST; accumulated 3 / Potency 2; resisted/Broken: OK")
    print("Zero Potency, empty Zone, pool == Level / > Level, pre-RNG replay/actor guards: OK")
    print("24 scripted dice; input/global RNG unchanged; mandatory Miscast retained, not resolved")
    print("Public K1 composition only; no M8 admission/executor or full magic battle simulation")


if __name__ == "__main__":
    main()
