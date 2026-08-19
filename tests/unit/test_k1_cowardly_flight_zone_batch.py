from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import (
    Condition,
    EffectClassification,
    EffectImmunity,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.magic_models import (
    IdentifiedSpellTarget,
    SpellCastRequest,
    SpellPotencyModifier,
    SpellTargetKind,
    SpellTargetPreflightRequest,
)
from towr.domain.resolution_models import (
    CowardlyFlightMovementCompletion,
    CowardlyFlightMovementFollowUp,
    CowardlyFlightSpellEffectRequest,
    CowardlyFlightWillpowerBatchRequest,
    CowardlyFlightWillpowerRequest,
    CowardlyFlightZoneBatchRequest,
    GiveGroundResolutionRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.rules.cowardly_flight_resolution import (
    COWARDLY_FLIGHT_RULE_ID,
    COWARDLY_FLIGHT_SPELL_DEFINITION,
    complete_cowardly_flight_movement,
    resolve_cowardly_flight_zone_batch,
    resolve_cowardly_flight_willpower_batch,
)
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.spell_cast_execution import resolve_spell_cast_targets
from towr.rules.spell_target_preflight import resolve_spell_target_preflight


def execution(
    targets: tuple[IdentifiedSpellTarget, ...],
):
    preflight = resolve_spell_target_preflight(
        SpellTargetPreflightRequest(
            id="wizard:cast:preflight",
            source=SpellCastRequest(
                resolution_id="wizard:cast",
                caster_id="wizard",
                spell_rule_id=COWARDLY_FLIGHT_RULE_ID,
                lore_id="lore:battle-magic",
                casting_value=3,
                base_potency=2,
                rule_id="RULE-MAGIC-004:cast-or-wait",
            ),
            definition=COWARDLY_FLIGHT_SPELL_DEFINITION,
            selected_target_id="zone:bridge",
            selected_target_kind=SpellTargetKind.ZONE,
            target_within_range=True,
            affected_targets=targets,
        )
    )
    assert preflight.execution_request is not None
    return resolve_spell_cast_targets(preflight.execution_request)


def context(effect, *, can_give_ground: bool = True, immunities=()):
    return CowardlyFlightSpellEffectRequest(
        source=effect,
        can_give_ground=can_give_ground,
        willpower_test=TestRequest(
            f"{effect.target_id}:willpower",
            InlineProfile(2, 5),
        ),
        target_state=CharacterInjuryState(),
        target_effect_immunities=immunities,
    )


def zone_batch(
    targets: tuple[IdentifiedSpellTarget, ...],
    *,
    can_give_ground: bool = True,
):
    source = execution(targets)
    return resolve_cowardly_flight_zone_batch(
        CowardlyFlightZoneBatchRequest(
            id="wizard:cast:zone-effects",
            source=source,
            contexts=tuple(
                context(effect, can_give_ground=can_give_ground)
                for effect in source.follow_ups
            ),
        )
    )


def spell_spatial_state(
    target_ids: tuple[str, ...],
    *,
    origin_zone_id: str = "zone:bridge",
) -> SpatialBattleState:
    destination_zone_ids = tuple(
        f"zone:retreat:{target_id}" for target_id in target_ids
    )
    return SpatialBattleState(
        graph=ZoneGraph(
            zone_ids=(origin_zone_id, *destination_zone_ids),
            connections=tuple(
                ZoneConnection(origin_zone_id, destination_zone_id)
                for destination_zone_id in destination_zone_ids
            ),
        ),
        placements=tuple(
            SpatialEntityPlacement(
                entity_id=target_id,
                side_id="enemies",
                zone_id=origin_zone_id,
            )
            for target_id in target_ids
        ),
    )


def movement_completions(
    follow_ups: tuple[CowardlyFlightMovementFollowUp, ...],
    *,
    origin_zone_id: str = "zone:bridge",
) -> tuple[tuple[CowardlyFlightMovementCompletion, ...], SpatialBattleState]:
    spatial_state = spell_spatial_state(
        tuple(item.target_id for item in follow_ups),
        origin_zone_id=origin_zone_id,
    )
    completions: list[CowardlyFlightMovementCompletion] = []
    for follow_up in follow_ups:
        resolution = resolve_give_ground(
            GiveGroundResolutionRequest(
                source=follow_up.request,
                state=spatial_state,
                mover_id=follow_up.target_id,
                destination_zone_id=f"zone:retreat:{follow_up.target_id}",
                mover_conditions=CharacterInjuryState().conditions,
            )
        )
        completions.append(
            complete_cowardly_flight_movement(follow_up, resolution)
        )
        spatial_state = resolution.state
    return tuple(completions), spatial_state


def movement_completion(
    follow_up: CowardlyFlightMovementFollowUp,
    *,
    origin_zone_id: str = "zone:bridge",
) -> CowardlyFlightMovementCompletion:
    completions, _ = movement_completions(
        (follow_up,),
        origin_zone_id=origin_zone_id,
    )
    return completions[0]


class K1CowardlyFlightZoneBatchTests(unittest.TestCase):
    def test_batch_restores_effect_order_from_unordered_contexts(self) -> None:
        source = execution(
            (
                IdentifiedSpellTarget("first"),
                IdentifiedSpellTarget(
                    "second",
                    potency_modifiers=(
                        SpellPotencyModifier(
                            "RULE-MAGIC-002:magic-resistance",
                            -1,
                        ),
                    ),
                ),
            )
        )
        first, second = source.follow_ups

        result = resolve_cowardly_flight_zone_batch(
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(context(second), context(first)),
            )
        )

        self.assertEqual(result.selected_zone_id, "zone:bridge")
        self.assertEqual(
            tuple(target.target_id for target in result.targets),
            ("first", "second"),
        )
        self.assertEqual(
            tuple(item.target_id for item in result.movement_follow_ups),
            ("first", "second"),
        )
        self.assertEqual(
            tuple(item.target_id for item in result.willpower_follow_ups),
            ("first", "second"),
        )
        willpower = result.targets[1].follow_ups[-1]
        assert isinstance(willpower, CowardlyFlightWillpowerRequest)
        self.assertEqual(willpower.potency, 1)

    def test_immunity_blocks_only_its_own_target(self) -> None:
        source = execution(
            (IdentifiedSpellTarget("undead"), IdentifiedSpellTarget("human"))
        )
        undead, human = source.follow_ups
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-psychological-immunity",
        )

        result = resolve_cowardly_flight_zone_batch(
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(
                    context(undead, immunities=(immunity,)),
                    context(human),
                ),
            )
        )

        self.assertTrue(result.targets[0].application.blocked)
        self.assertEqual(result.targets[0].follow_ups, ())
        self.assertFalse(result.targets[1].application.blocked)
        self.assertEqual(len(result.movement_follow_ups), 1)
        self.assertEqual(
            tuple(item.target_id for item in result.willpower_follow_ups),
            ("human",),
        )

    def test_zero_potency_target_needs_no_effect_context(self) -> None:
        source = execution(
            (
                IdentifiedSpellTarget(
                    "warded",
                    potency_modifiers=(
                        SpellPotencyModifier("RULE-MAGIC:strong-ward", -2),
                    ),
                ),
                IdentifiedSpellTarget("affected"),
            )
        )
        self.assertEqual(
            tuple(effect.target_id for effect in source.follow_ups),
            ("affected",),
        )

        result = resolve_cowardly_flight_zone_batch(
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(context(source.follow_ups[0]),),
            )
        )

        self.assertEqual(
            tuple(target.target_id for target in result.targets),
            ("affected",),
        )

    def test_empty_zone_accepts_empty_context_batch(self) -> None:
        source = execution(())

        result = resolve_cowardly_flight_zone_batch(
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(),
            )
        )

        self.assertEqual(result.selected_zone_id, "zone:bridge")
        self.assertEqual(result.targets, ())
        self.assertEqual(result.movement_follow_ups, ())
        self.assertEqual(result.willpower_follow_ups, ())

    def test_missing_or_extra_context_is_rejected(self) -> None:
        source = execution((IdentifiedSpellTarget("expected"),))
        expected = source.follow_ups[0]
        other_source = execution((IdentifiedSpellTarget("extra"),))
        extra = other_source.follow_ups[0]

        for contexts in ((), (context(expected), context(extra))):
            with self.subTest(contexts=contexts):
                with self.assertRaises(ValueError):
                    resolve_cowardly_flight_zone_batch(
                        CowardlyFlightZoneBatchRequest(
                            id="wizard:cast:zone-effects",
                            source=source,
                            contexts=contexts,
                        )
                    )

    def test_duplicate_context_target_or_test_id_is_rejected(self) -> None:
        source = execution(
            (IdentifiedSpellTarget("first"), IdentifiedSpellTarget("second"))
        )
        first, second = source.follow_ups
        duplicate_target = context(first)
        with self.assertRaises(ValueError):
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(duplicate_target, duplicate_target),
            )

        first_context = context(first)
        second_context = CowardlyFlightSpellEffectRequest(
            source=second,
            can_give_ground=True,
            willpower_test=first_context.willpower_test,
            target_state=CharacterInjuryState(),
        )
        with self.assertRaises(ValueError):
            CowardlyFlightZoneBatchRequest(
                id="wizard:cast:zone-effects",
                source=source,
                contexts=(first_context, second_context),
            )

    def test_context_must_reference_the_exact_source_effect(self) -> None:
        source = execution((IdentifiedSpellTarget("enemy"),))
        expected = source.follow_ups[0]
        forged = type(expected)(
            resolution_id="forged",
            source_cast_id=expected.source_cast_id,
            caster_id=expected.caster_id,
            spell_rule_id=expected.spell_rule_id,
            lore_id=expected.lore_id,
            target_id=expected.target_id,
            potency=expected.potency,
            rule_id=expected.rule_id,
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_zone_batch(
                CowardlyFlightZoneBatchRequest(
                    id="wizard:cast:zone-effects",
                    source=source,
                    contexts=(context(forged),),
                )
            )

    def test_other_spell_is_rejected_even_for_empty_batch(self) -> None:
        source = execution(())
        alien = type(source)(
            request_id=source.request_id,
            source_cast_id=source.source_cast_id,
            caster_id=source.caster_id,
            spell_rule_id="RULE-SPELL-002:fireball",
            lore_id=source.lore_id,
            selected_target_id=source.selected_target_id,
            targets=source.targets,
            follow_ups=source.follow_ups,
            applied_rule_ids=source.applied_rule_ids,
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_zone_batch(
                CowardlyFlightZoneBatchRequest(
                    id="wizard:cast:zone-effects",
                    source=alien,
                    contexts=(),
                )
            )


class K1CowardlyFlightWillpowerBatchTests(unittest.TestCase):
    def test_completed_movements_unlock_tests_in_affected_target_order(self) -> None:
        source = zone_batch(
            (IdentifiedSpellTarget("first"), IdentifiedSpellTarget("second"))
        )
        ordered_completions, final_spatial_state = movement_completions(
            source.movement_follow_ups
        )
        completions = tuple(reversed(ordered_completions))

        result = resolve_cowardly_flight_willpower_batch(
            CowardlyFlightWillpowerBatchRequest(
                id="wizard:cast:willpower-batch",
                source=source,
                spatial_state_after_movements=final_spatial_state,
                movement_completions=completions,
            ),
            SequenceRandom([10, 10, 1, 1]),
        )

        self.assertEqual(
            tuple(item.source.target_id for item in result.completed_movements),
            ("first", "second"),
        )
        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("first", "second"),
        )
        self.assertFalse(result.targets[0].resisted)
        self.assertTrue(result.targets[0].state.conditions.has(Condition.BROKEN))
        self.assertTrue(result.targets[1].resisted)
        self.assertEqual(result.source_batch_id, source.request_id)
        self.assertEqual(result.source_execution_id, source.source_execution_id)
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(result.selected_zone_id, "zone:bridge")
        self.assertEqual(result.spatial_state, final_spatial_state)

    def test_movements_must_form_one_ordered_spatial_state_chain(self) -> None:
        source = zone_batch(
            (IdentifiedSpellTarget("first"), IdentifiedSpellTarget("second"))
        )
        initial_state = spell_spatial_state(("first", "second"))
        independent_completions = []
        for follow_up in source.movement_follow_ups:
            resolution = resolve_give_ground(
                GiveGroundResolutionRequest(
                    source=follow_up.request,
                    state=initial_state,
                    mover_id=follow_up.target_id,
                    destination_zone_id=(
                        f"zone:retreat:{follow_up.target_id}"
                    ),
                    mover_conditions=CharacterInjuryState().conditions,
                )
            )
            independent_completions.append(
                complete_cowardly_flight_movement(follow_up, resolution)
            )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_willpower_batch(
                CowardlyFlightWillpowerBatchRequest(
                    id="wizard:cast:willpower-batch",
                    source=source,
                    spatial_state_after_movements=(
                        independent_completions[-1].resolution.state
                    ),
                    movement_completions=tuple(independent_completions),
                ),
                SequenceRandom([]),
            )

    def test_target_without_movement_still_takes_willpower_test(self) -> None:
        source = zone_batch(
            (IdentifiedSpellTarget("trapped"),),
            can_give_ground=False,
        )
        final_spatial_state = spell_spatial_state(("trapped",))

        result = resolve_cowardly_flight_willpower_batch(
            CowardlyFlightWillpowerBatchRequest(
                id="wizard:cast:willpower-batch",
                source=source,
                spatial_state_after_movements=final_spatial_state,
                movement_completions=(),
            ),
            SequenceRandom([1, 1]),
        )

        self.assertEqual(result.completed_movements, ())
        self.assertEqual(len(result.targets), 1)
        self.assertTrue(result.targets[0].resisted)

    def test_empty_zone_completes_without_movement_or_rng(self) -> None:
        source = zone_batch(())
        final_spatial_state = spell_spatial_state(())

        result = resolve_cowardly_flight_willpower_batch(
            CowardlyFlightWillpowerBatchRequest(
                id="wizard:cast:willpower-batch",
                source=source,
                spatial_state_after_movements=final_spatial_state,
                movement_completions=(),
            ),
            SequenceRandom([]),
        )

        self.assertEqual(result.completed_movements, ())
        self.assertEqual(result.targets, ())
        self.assertEqual(result.spell_rule_id, COWARDLY_FLIGHT_RULE_ID)

    def test_missing_extra_or_forged_movement_confirmation_is_rejected(self) -> None:
        source = zone_batch(
            (IdentifiedSpellTarget("first"), IdentifiedSpellTarget("second"))
        )
        expected, final_spatial_state = movement_completions(
            source.movement_follow_ups
        )
        unrelated = zone_batch((IdentifiedSpellTarget("extra"),))
        extra = movement_completion(unrelated.movement_follow_ups[0])
        original = source.movement_follow_ups[0]
        forged = movement_completion(
            CowardlyFlightMovementFollowUp(
                target_id="forged-target",
                request=original.request,
            )
        )

        for completions in (
            expected[:-1],
            (*expected, extra),
            (forged, expected[1]),
        ):
            with self.subTest(completions=completions):
                with self.assertRaises(ValueError):
                    resolve_cowardly_flight_willpower_batch(
                        CowardlyFlightWillpowerBatchRequest(
                            id="wizard:cast:willpower-batch",
                            source=source,
                            spatial_state_after_movements=final_spatial_state,
                            movement_completions=completions,
                        ),
                        SequenceRandom([]),
                    )

    def test_duplicate_movement_confirmation_is_rejected(self) -> None:
        source = zone_batch((IdentifiedSpellTarget("target"),))
        completion = movement_completion(source.movement_follow_ups[0])

        with self.assertRaises(ValueError):
            CowardlyFlightWillpowerBatchRequest(
                id="wizard:cast:willpower-batch",
                source=source,
                spatial_state_after_movements=completion.resolution.state,
                movement_completions=(completion, completion),
            )

    def test_movement_must_originate_in_the_selected_zone(self) -> None:
        source = zone_batch((IdentifiedSpellTarget("target"),))
        completion = movement_completion(
            source.movement_follow_ups[0],
            origin_zone_id="zone:not-the-spell-target",
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_willpower_batch(
                CowardlyFlightWillpowerBatchRequest(
                    id="wizard:cast:willpower-batch",
                    source=source,
                    spatial_state_after_movements=completion.resolution.state,
                    movement_completions=(completion,),
                ),
                SequenceRandom([]),
            )

    def test_forged_zone_queues_are_rejected_before_rng(self) -> None:
        source = zone_batch((IdentifiedSpellTarget("target"),))
        final_spatial_state = spell_spatial_state(("target",))
        fields = dict(
            request_id=source.request_id,
            source_execution_id=source.source_execution_id,
            caster_id=source.caster_id,
            spell_rule_id=source.spell_rule_id,
            lore_id=source.lore_id,
            selected_zone_id=source.selected_zone_id,
            targets=source.targets,
            movement_follow_ups=source.movement_follow_ups,
            willpower_follow_ups=source.willpower_follow_ups,
            applied_rule_ids=source.applied_rule_ids,
        )
        forged_sources = (
            type(source)(**{**fields, "movement_follow_ups": ()}),
            type(source)(**{**fields, "willpower_follow_ups": ()}),
        )

        for forged_source in forged_sources:
            with self.subTest(source=forged_source):
                with self.assertRaises(ValueError):
                    resolve_cowardly_flight_willpower_batch(
                        CowardlyFlightWillpowerBatchRequest(
                            id="wizard:cast:willpower-batch",
                            source=forged_source,
                            spatial_state_after_movements=final_spatial_state,
                            movement_completions=(),
                        ),
                        SequenceRandom([]),
                    )

    def test_duplicate_forged_zone_targets_are_rejected_before_rng(self) -> None:
        source = zone_batch(
            (IdentifiedSpellTarget("target"),),
            can_give_ground=False,
        )
        forged = type(source)(
            request_id=source.request_id,
            source_execution_id=source.source_execution_id,
            caster_id=source.caster_id,
            spell_rule_id=source.spell_rule_id,
            lore_id=source.lore_id,
            selected_zone_id=source.selected_zone_id,
            targets=(source.targets[0], source.targets[0]),
            movement_follow_ups=(),
            willpower_follow_ups=(
                source.willpower_follow_ups[0],
                source.willpower_follow_ups[0],
            ),
            applied_rule_ids=source.applied_rule_ids,
        )
        final_spatial_state = spell_spatial_state(("target",))

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_willpower_batch(
                CowardlyFlightWillpowerBatchRequest(
                    id="wizard:cast:willpower-batch",
                    source=forged,
                    spatial_state_after_movements=final_spatial_state,
                    movement_completions=(),
                ),
                SequenceRandom([]),
            )

    def test_other_spell_is_rejected_even_for_empty_batch(self) -> None:
        source = zone_batch(())
        final_spatial_state = spell_spatial_state(())
        alien = type(source)(
            request_id=source.request_id,
            source_execution_id=source.source_execution_id,
            caster_id=source.caster_id,
            spell_rule_id="RULE-SPELL-002:fireball",
            lore_id=source.lore_id,
            selected_zone_id=source.selected_zone_id,
            targets=source.targets,
            movement_follow_ups=source.movement_follow_ups,
            willpower_follow_ups=source.willpower_follow_ups,
            applied_rule_ids=source.applied_rule_ids,
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_willpower_batch(
                CowardlyFlightWillpowerBatchRequest(
                    id="wizard:cast:willpower-batch",
                    source=alien,
                    spatial_state_after_movements=final_spatial_state,
                    movement_completions=(),
                ),
                SequenceRandom([]),
            )


if __name__ == "__main__":
    unittest.main()
