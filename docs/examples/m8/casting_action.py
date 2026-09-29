"""Standalone production Casting example (ADR-0035), not a battle runner.

Authored numeric Wizard/Minion inputs, PG1.4 pp156-157 and p162.
Caller supplies activations and facts; no intermediate turns are simulated.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from random import getstate

from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import (
    BATTLE_MAGIC_LORE_ID, CastingCasterDefinition, CowardlyFlightCastingFacts,
    CowardlyFlightCastingPolicy, CowardlyFlightCastingRequest, CowardlyFlightCastingTarget,
)
from towr.domain.cowardly_flight_casting_result_models import (
    CowardlyFlightCastingResult, CowardlyFlightCastingStatus,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest, ImproviseKind,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class ScriptedDice:
    def __init__(self, values: tuple[int, ...]) -> None:
        self.values = values
        self.calls = 0

    def randint(self, start: int, end: int) -> int:
        assert (start, end) == (1, 10)
        assert self.calls < len(self.values), "unexpected RNG call"
        value = self.values[self.calls]
        self.calls += 1
        assert start <= value <= end
        return value


def activation(identifier: str, magic: WizardMagicState, round_number: int) -> CowardlyFlightCastingRequest:
    """Supply one ready action. This is explicitly not round continuation."""
    participants = (
        CombatTurnParticipant("wizard", CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant("first", CombatSide.OPPOSITION),
        CombatTurnParticipant("second", CombatSide.OPPOSITION),
    )
    combat = start_combat_turn(CombatTurnStartRequest(
        identifier + ":start", CombatRoundState(round_number, participants), "wizard")).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        identifier + ":slot", combat, "wizard", CombatActionDeclaration(
            CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
            improvise_approach_id=BATTLE_MAGIC_LORE_ID), ActionSlotGrant.STANDARD,
    )).state
    # Isolated arena: enemies factually cannot Give Ground. The separate empty
    # Zone is explicitly within Long range; graph adjacency does not infer Range.
    spatial = SpatialBattleState(ZoneGraph(("arena", "empty")), tuple(
        SpatialEntityPlacement(p.entity_id, p.side.value, "arena") for p in reversed(participants)
    ), round_number=round_number)
    return CowardlyFlightCastingRequest(
        id=identifier,
        caster=CastingCasterDefinition("authored-wizard", "example:Wizard-Level-2", 2, InlineProfile(3, 3)),
        actor_id="wizard", round_state=combat, slot_index=1, magic_state=magic,
        spatial_state=spatial, selected_zone_id="arena",
        targets=tuple(CowardlyFlightCastingTarget(actor, InlineProfile(3, 3), ProfileInjuryState(0, 1), False)
                      for actor in ("first", "second")),
        facts=CowardlyFlightCastingFacts(
            caster_can_cast=True, knows_battle_magic=True, spell_memorised=True,
            caster_unarmoured=True, no_bulky_items=True, no_casting_opposition=True,
            no_mixing_winds=True, no_other_test_modifiers=True, no_potency_modifiers=True,
            no_effect_immunities=True, all_zone_enemies_included=True, target_zone_within_long_range=True,
        ),
        policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY,
    )


def run(request: CowardlyFlightCastingRequest, values: tuple[int, ...]) -> CowardlyFlightCastingResult:
    before = deepcopy(request)
    rng = ScriptedDice(values)
    result = execute_cowardly_flight_casting(request, rng)
    assert rng.calls == len(values), "unused scripted dice"
    assert request == before and result.source is request
    assert result.spatial_state == request.spatial_state
    turn = result.round_state.active_turn
    assert turn is not None and turn.actor_id == request.actor_id
    assert len(turn.action_slots) == 1 and turn.action_slots[0].executed
    assert turn.action_slots[0].execution.id == request.id
    assert result.round_state.completed_turn_entity_ids == ()
    return result


def main() -> None:
    global_rng = getstate()
    request = activation("first-action", WizardMagicState(), 1)
    waiting = run(request, (1, 10, 10))
    assert waiting.status is CowardlyFlightCastingStatus.WAITING
    assert waiting.magic_state == WizardMagicState(0, 1, BATTLE_MAGIC_LORE_ID, 1)
    assert tuple(t.injury for t in waiting.targets) == tuple(t.injury for t in request.targets)
    print("WAIT: accumulated=1; pool=0; dice=3; receipt=first-action")

    # Caller has completed the intervening turns and supplies a new activation.
    following = activation("second-action", waiting.magic_state, 2)
    assert following.magic_state is waiting.magic_state
    cast = run(following, (1, 2, 10, 1, 2, 10, 10, 10, 10))
    assert cast.status is CowardlyFlightCastingStatus.SPELL_RESOLVED
    assert cast.post_test.decision.previous_casting_successes == 3
    assert cast.post_test.decision.base_potency == 2
    assert cast.magic_state == WizardMagicState()
    assert tuple(t.actor_id for t in cast.targets) == ("first", "second")
    assert cast.willpower.targets[0].resisted and not cast.willpower.targets[1].resisted
    assert cast.targets[1].injury.conditions.has(Condition.BROKEN)
    assert not cast.targets[1].injury.defeated
    print("CAST: accumulated_before=3; potency=2; first=resisted; second=Broken; dice=9; receipt=second-action")

    equal = run(activation("equal-pool", WizardMagicState(1), 3), (9, 1, 10))
    assert equal.status is CowardlyFlightCastingStatus.WAITING
    assert equal.magic_state.miscast_dice == 2 and equal.pending_miscast is None
    print("POOL == LEVEL: waiting; pool=2; accumulated=1; dice=3")

    trigger_request = activation("triggered", equal.magic_state, 4)
    triggered = run(trigger_request, (9, 1, 2))
    assert triggered.status is CowardlyFlightCastingStatus.MISCAST_REQUIRED
    assert triggered.magic_state == WizardMagicState(3, 3, BATTLE_MAGIC_LORE_ID, 2)
    assert triggered.pending_miscast is triggered.post_test.miscast_pool.roll_request
    assert triggered.pending_miscast.pool_dice_count == 3
    assert triggered.pending_miscast.bonus_dice == 0
    assert triggered.post_test.decision is None and triggered.spell is None
    print("POOL > LEVEL: miscast_required; pool=3; accumulated=3; pending retained; dice=3")

    held = WizardMagicState(0, 3, BATTLE_MAGIC_LORE_ID, 3)
    zero = run(activation("zero-potency", held, 5), (10, 10, 10))
    assert zero.status is CowardlyFlightCastingStatus.SPELL_RESOLVED
    assert zero.post_test.decision.base_potency == 0
    assert len(zero.targets) == len(zero.spell.targets) == 2
    assert zero.willpower.targets == () and zero.spell.follow_ups == ()
    print("ZERO POTENCY: spell_resolved; targets=2; Willpower Tests=0; dice=3")

    empty_request = replace(activation("empty-zone", WizardMagicState(), 6), selected_zone_id="empty", targets=())
    empty = run(empty_request, (1, 2, 3))
    assert empty.status is CowardlyFlightCastingStatus.SPELL_RESOLVED
    assert empty.targets == empty.willpower.targets == ()
    print("EMPTY ZONE: spell_resolved; targets=0; Willpower Tests=0; dice=3")

    no_dice = ScriptedDice(())
    for source, changes in (
        (request, {"round_state": waiting.round_state, "magic_state": waiting.magic_state}),
        (request, {"actor_id": "foreign"}),
        (trigger_request, {"magic_state": triggered.magic_state}),
    ):
        try:
            execute_cowardly_flight_casting(replace(source, **changes), no_dice)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid continuation was admitted")
    assert no_dice.calls == 0 and getstate() == global_rng
    print("24 scripted d10; one receipt per action; replay/actor/pending guards before RNG; inputs/global RNG unchanged")
    print("Scope: supplied activations; no full battle, Miscast resolution or next Broken turn")


if __name__ == "__main__":
    main()
