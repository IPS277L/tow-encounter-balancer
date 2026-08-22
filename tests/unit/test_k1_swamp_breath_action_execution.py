from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.resolution_models import (
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.swamp_breath_models import (
    SWAMP_BREATH_ACTION_EXECUTION_RULE_ID,
    TROLL_HAG_SWAMP_BREATH_RULE_ID,
    SwampBreathActionExecutionRequest,
)
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
)
from towr.rules.swamp_breath_action_execution import (
    execute_swamp_breath_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(
    *,
    improvise_kind: ImproviseKind = ImproviseKind.ABILITY,
    approach_id: str = TROLL_HAG_SWAMP_BREATH_RULE_ID,
    produces_attack: bool = False,
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "troll-hag",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:start", state, "troll-hag")
    ).state
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:swamp-breath",
            state=state,
            actor_id="troll-hag",
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=improvise_kind,
                improvise_approach_id=approach_id,
                improvise_produces_attack=produces_attack,
            ),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def spatial_state(
    placements: tuple[SpatialEntityPlacement, ...] | None = None,
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=ZoneGraph(
            zone_ids=("origin", "target", "empty"),
            connections=(ZoneConnection("origin", "target"),),
        ),
        placements=(
            placements
            if placements is not None
            else (
                SpatialEntityPlacement("troll-hag", "heroes", "origin"),
                SpatialEntityPlacement("ally", "heroes", "target"),
                SpatialEntityPlacement("enemy", "enemies", "target"),
            )
        ),
        round_number=1,
    )


def hazard_target(
    target_id: str,
    *,
    dice: int = 3,
    skill: Skill = Skill.ENDURANCE,
    test_id: str | None = None,
) -> IdentifiedHazardTarget:
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest(
            test_id or f"swamp-breath:{target_id}:endurance",
            InlineProfile(dice, 5),
        ),
        target_policy=TargetInjuryPolicy.BRUTE,
        target_state=ProfileInjuryState(wounds=0, wound_limit=6),
        selected_avoidance_skill=skill,
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    spatial: SpatialBattleState | None = None,
    actor_conditions: ConditionState | None = None,
    actor_ability_rule_ids: tuple[str, ...] = (
        TROLL_HAG_SWAMP_BREATH_RULE_ID,
    ),
    target_zone_id: str = "target",
    target_zone_in_medium_range: bool = True,
    targets: tuple[IdentifiedHazardTarget, ...] | None = None,
    slot_index: int = 1,
) -> SwampBreathActionExecutionRequest:
    return SwampBreathActionExecutionRequest(
        id="swamp-breath:execute",
        round_state=round_state if round_state is not None else active_round(),
        spatial_state=spatial if spatial is not None else spatial_state(),
        actor_id="troll-hag",
        actor_conditions=(
            actor_conditions
            if actor_conditions is not None
            else ConditionState()
        ),
        actor_ability_rule_ids=actor_ability_rule_ids,
        slot_index=slot_index,
        target_zone_id=target_zone_id,
        target_zone_in_medium_range=target_zone_in_medium_range,
        targets=(
            targets
            if targets is not None
            else (hazard_target("ally"), hazard_target("enemy", dice=2))
        ),
    )


class K1SwampBreathActionExecutionTests(unittest.TestCase):
    def test_every_zone_creature_resolves_in_placement_order(self) -> None:
        source = request()

        result = execute_swamp_breath_action(
            source,
            SequenceRandom([1, 2, 3, 10, 10]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.zone_hazard.targets),
            ("ally", "enemy"),
        )
        ally, enemy = result.zone_hazard.targets
        self.assertIsNotNone(ally.hazard)
        self.assertIsNotNone(enemy.hazard)
        assert ally.hazard is not None
        assert enemy.hazard is not None
        self.assertTrue(ally.hazard.avoided)
        self.assertEqual(ally.hazard.state.wounds, 0)
        self.assertFalse(enemy.hazard.avoided)
        self.assertEqual(enemy.hazard.shortfall, 3)
        self.assertEqual(enemy.hazard.state.wounds, 3)
        self.assertEqual(result.spatial_state, source.spatial_state)
        self.assertTrue(result.slot.executed)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(
            receipt.executor_rule_id,
            SWAMP_BREATH_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            receipt.result_request_id,
            result.zone_hazard.request_id,
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "troll-hag")
        )
        self.assertEqual(ended.completed_turn.actor_id, "troll-hag")

    def test_actor_is_included_when_present_in_target_zone(self) -> None:
        spatial = spatial_state(
            (
                SpatialEntityPlacement(
                    "troll-hag",
                    "heroes",
                    "target",
                ),
                SpatialEntityPlacement("enemy", "enemies", "target"),
            )
        )
        result = execute_swamp_breath_action(
            request(
                spatial=spatial,
                targets=(
                    hazard_target("troll-hag"),
                    hazard_target("enemy"),
                ),
            ),
            SequenceRandom([1, 2, 3, 1, 2, 3]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.zone_hazard.targets),
            ("troll-hag", "enemy"),
        )

    def test_empty_zone_completes_without_rng(self) -> None:
        result = execute_swamp_breath_action(
            request(target_zone_id="empty", targets=()),
            SequenceRandom([]),
        )

        self.assertEqual(result.zone_hazard.targets, ())
        self.assertTrue(result.slot.executed)
        self.assertIn(
            TROLL_HAG_SWAMP_BREATH_RULE_ID,
            result.applied_rule_ids,
        )

    def test_targets_must_exactly_match_zone_placement_order(self) -> None:
        invalid_targets = (
            (hazard_target("ally"),),
            (hazard_target("enemy"), hazard_target("ally")),
            (
                hazard_target("ally"),
                hazard_target("enemy"),
                hazard_target("extra"),
            ),
            (
                hazard_target("ally", test_id="duplicate:test"),
                hazard_target("enemy", test_id="duplicate:test"),
            ),
        )
        for targets in invalid_targets:
            with self.subTest(targets=targets):
                with self.assertRaises(ValueError):
                    execute_swamp_breath_action(
                        request(targets=targets),
                        SequenceRandom([]),
                    )

    def test_ability_actor_range_and_skill_preflight_before_rng(self) -> None:
        invalid_requests = (
            request(actor_ability_rule_ids=()),
            request(target_zone_in_medium_range=False),
            request(
                actor_conditions=ConditionState(
                    frozenset({Condition.STAGGERED})
                )
            ),
            request(
                actor_conditions=ConditionState(
                    frozenset({Condition.DEFENCELESS})
                )
            ),
            request(
                targets=(
                    hazard_target("ally", skill=Skill.ATHLETICS),
                    hazard_target("enemy"),
                )
            ),
        )
        for source in invalid_requests:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_swamp_breath_action(source, SequenceRandom([]))

    def test_only_matching_non_attack_ability_slot_can_execute(self) -> None:
        invalid_rounds = (
            active_round(improvise_kind=ImproviseKind.SKILL),
            active_round(approach_id="RULE-NPC-019:troll-vomit"),
            active_round(produces_attack=True),
        )
        for state in invalid_rounds:
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    execute_swamp_breath_action(
                        request(round_state=state),
                        SequenceRandom([]),
                    )
        with self.assertRaises(ValueError):
            execute_swamp_breath_action(
                replace(request(), rule_id="RULE-NPC-020:forged"),
                SequenceRandom([]),
            )

    def test_slot_is_atomic_ordered_and_executed_once(self) -> None:
        source = request()
        result = execute_swamp_breath_action(
            source,
            SequenceRandom([1, 2, 3, 1, 2]),
        )
        with self.assertRaises(ValueError):
            execute_swamp_breath_action(
                replace(source, round_state=result.round_state),
                SequenceRandom([]),
            )

        state = start_combat_turn(
            CombatTurnStartRequest(
                "turn:ordered:start",
                CombatRoundState(
                    round_number=1,
                    participants=(
                        CombatTurnParticipant(
                            "troll-hag",
                            CombatSide.PLAYERS_AND_ALLIES,
                        ),
                        CombatTurnParticipant(
                            "enemy",
                            CombatSide.OPPOSITION,
                        ),
                    ),
                ),
                "troll-hag",
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:first",
                state,
                "troll-hag",
                CombatActionDeclaration(CombatActionKind.AIM),
                ActionSlotGrant.STANDARD,
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:second",
                state,
                "troll-hag",
                CombatActionDeclaration(
                    CombatActionKind.IMPROVISE,
                    improvise_kind=ImproviseKind.ABILITY,
                    improvise_approach_id=(
                        TROLL_HAG_SWAMP_BREATH_RULE_ID
                    ),
                ),
                ActionSlotGrant.FATE,
            )
        ).state
        with self.assertRaises(ValueError):
            execute_swamp_breath_action(
                request(round_state=state, slot_index=2),
                SequenceRandom([]),
            )

    def test_result_rejects_zone_batch_receipt_and_spatial_forgery(self) -> None:
        result = execute_swamp_breath_action(
            request(),
            SequenceRandom([1, 2, 3, 10, 10]),
        )
        ally, enemy = result.zone_hazard.targets

        with self.assertRaises(ValueError):
            replace(result, target_zone_id="empty")
        with self.assertRaises(ValueError):
            replace(
                result,
                zone_hazard=replace(
                    result.zone_hazard,
                    targets=(enemy, ally),
                ),
            )
        assert ally.hazard is not None
        assert enemy.hazard is not None
        with self.assertRaises(ValueError):
            replace(
                result,
                zone_hazard=replace(
                    result.zone_hazard,
                    targets=(
                        replace(
                            ally,
                            hazard=replace(
                                ally.hazard,
                                state=enemy.hazard.state,
                            ),
                        ),
                        enemy,
                    ),
                ),
            )
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            replace(
                result,
                spatial_state=replace(
                    result.spatial_state,
                    free_move_used_entity_ids=("troll-hag",),
                ),
            )
        with self.assertRaises(ValueError):
            replace(
                result,
                applied_rule_ids=(TROLL_HAG_SWAMP_BREATH_RULE_ID,),
            )


if __name__ == "__main__":
    unittest.main()
