from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
)
from towr.domain.soporific_breath_models import (
    SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID,
    SOPORIFIC_BREATH_RULE_ID,
    SoporificBreathActionExecutionRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
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
from towr.rules.soporific_breath_action_execution import (
    execute_soporific_breath_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(
    *,
    actor_id: str = "forest-dragon",
    improvise_kind: ImproviseKind = ImproviseKind.ABILITY,
    approach_id: str = SOPORIFIC_BREATH_RULE_ID,
    produces_attack: bool = False,
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                actor_id,
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:start", state, actor_id)
    ).state
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:soporific-breath",
            state=state,
            actor_id=actor_id,
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
                SpatialEntityPlacement(
                    "forest-dragon",
                    "heroes",
                    "origin",
                ),
                SpatialEntityPlacement("fresh", "heroes", "target"),
                SpatialEntityPlacement("drained", "enemies", "target"),
            )
        ),
        round_number=1,
    )


def hazard_target(
    target_id: str,
    *,
    state: ProfileInjuryState | CharacterInjuryState | None = None,
    policy: TargetInjuryPolicy = TargetInjuryPolicy.BRUTE,
    dice: int = 1,
    skill: Skill = Skill.ENDURANCE,
    test_id: str | None = None,
) -> IdentifiedHazardTarget:
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest(
            test_id or f"soporific:{target_id}:endurance",
            InlineProfile(dice, 5),
        ),
        target_policy=policy,
        target_state=(
            state
            if state is not None
            else ProfileInjuryState(wounds=0, wound_limit=6)
        ),
        selected_avoidance_skill=skill,
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    spatial: SpatialBattleState | None = None,
    actor_id: str = "forest-dragon",
    actor_conditions: ConditionState | None = None,
    actor_ability_rule_ids: tuple[str, ...] = (SOPORIFIC_BREATH_RULE_ID,),
    target_zone_id: str = "target",
    target_zone_in_medium_range: bool = True,
    targets: tuple[IdentifiedHazardTarget, ...] | None = None,
    slot_index: int = 1,
) -> SoporificBreathActionExecutionRequest:
    return SoporificBreathActionExecutionRequest(
        id="soporific-breath:execute",
        round_state=(
            round_state
            if round_state is not None
            else active_round(actor_id=actor_id)
        ),
        spatial_state=spatial if spatial is not None else spatial_state(),
        actor_id=actor_id,
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
            else (
                hazard_target("fresh"),
                hazard_target(
                    "drained",
                    state=ProfileInjuryState(
                        wounds=0,
                        wound_limit=6,
                        conditions=ConditionState(
                            frozenset({Condition.DRAINED})
                        ),
                    ),
                ),
            )
        ),
    )


class K1SoporificBreathActionExecutionTests(unittest.TestCase):
    def test_zone_resolves_fresh_and_repeated_drained_in_order(self) -> None:
        source = request()

        result = execute_soporific_breath_action(
            source,
            SequenceRandom([10, 10]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.zone_hazard.targets),
            ("fresh", "drained"),
        )
        fresh, drained = result.zone_hazard.targets
        assert fresh.hazard is not None
        assert drained.hazard is not None
        self.assertEqual(fresh.hazard.state.wounds, 2)
        self.assertEqual(
            fresh.hazard.failure_conditions,
            (Condition.DRAINED,),
        )
        self.assertTrue(fresh.hazard.state.conditions.has(Condition.DRAINED))
        self.assertFalse(
            fresh.hazard.state.conditions.has(Condition.DEFENCELESS)
        )
        self.assertEqual(drained.hazard.state.wounds, 2)
        self.assertEqual(
            drained.hazard.failure_conditions,
            (Condition.DEFENCELESS,),
        )
        self.assertTrue(
            drained.hazard.state.conditions.has(Condition.DEFENCELESS)
        )
        self.assertEqual(result.spatial_state, source.spatial_state)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(
            receipt.executor_rule_id,
            SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID,
        )
        ended = end_combat_turn(
            CombatTurnEndRequest(
                "turn:end",
                result.round_state,
                "forest-dragon",
            )
        )
        self.assertEqual(ended.completed_turn.actor_id, "forest-dragon")

    def test_wound_drained_precedes_breath_replacement(self) -> None:
        spatial = spatial_state(
            (
                SpatialEntityPlacement(
                    "forest-dragon",
                    "heroes",
                    "origin",
                ),
                SpatialEntityPlacement("player", "heroes", "target"),
            )
        )
        result = execute_soporific_breath_action(
            request(
                spatial=spatial,
                targets=(
                    hazard_target(
                        "player",
                        state=CharacterInjuryState(),
                        policy=TargetInjuryPolicy.PLAYER,
                    ),
                ),
            ),
            SequenceRandom([10, 3, 3]),
        )

        hazard = result.zone_hazard.targets[0].hazard
        assert hazard is not None
        self.assertTrue(hazard.state.conditions.has(Condition.DRAINED))
        self.assertTrue(hazard.state.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(
            hazard.failure_conditions,
            (Condition.DEFENCELESS,),
        )

    def test_mounted_wood_elf_uses_explicit_inherited_ability_snapshot(
        self,
    ) -> None:
        spatial = spatial_state(
            (
                SpatialEntityPlacement("wood-elf", "heroes", "target"),
                SpatialEntityPlacement("enemy", "enemies", "target"),
            )
        )
        result = execute_soporific_breath_action(
            request(
                round_state=active_round(actor_id="wood-elf"),
                spatial=spatial,
                actor_id="wood-elf",
                targets=(
                    hazard_target("wood-elf", dice=2),
                    hazard_target("enemy", dice=2),
                ),
            ),
            SequenceRandom([1, 2, 1, 2]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.zone_hazard.targets),
            ("wood-elf", "enemy"),
        )
        self.assertTrue(
            all(
                item.hazard is not None and item.hazard.avoided
                for item in result.zone_hazard.targets
            )
        )

    def test_empty_zone_completes_without_rng(self) -> None:
        result = execute_soporific_breath_action(
            request(target_zone_id="empty", targets=()),
            SequenceRandom([]),
        )

        self.assertEqual(result.zone_hazard.targets, ())
        self.assertTrue(result.slot.executed)
        self.assertIn(SOPORIFIC_BREATH_RULE_ID, result.applied_rule_ids)

    def test_targets_must_exactly_match_zone_placement_order(self) -> None:
        invalid_targets = (
            (hazard_target("fresh"),),
            (hazard_target("drained"), hazard_target("fresh")),
            (
                hazard_target("fresh"),
                hazard_target("drained"),
                hazard_target("extra"),
            ),
            (
                hazard_target("fresh", test_id="duplicate:test"),
                hazard_target("drained", test_id="duplicate:test"),
            ),
        )
        for targets in invalid_targets:
            with self.subTest(targets=targets):
                with self.assertRaises(ValueError):
                    execute_soporific_breath_action(
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
                    hazard_target("fresh", skill=Skill.ATHLETICS),
                    hazard_target("drained"),
                )
            ),
        )
        for source in invalid_requests:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_soporific_breath_action(
                        source,
                        SequenceRandom([]),
                    )

    def test_only_matching_non_attack_ability_slot_can_execute(self) -> None:
        invalid_rounds = (
            active_round(improvise_kind=ImproviseKind.SKILL),
            active_round(approach_id="RULE-NPC-020:swamp-breath"),
            active_round(produces_attack=True),
        )
        for state in invalid_rounds:
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    execute_soporific_breath_action(
                        request(round_state=state),
                        SequenceRandom([]),
                    )
        with self.assertRaises(ValueError):
            execute_soporific_breath_action(
                replace(request(), rule_id="RULE-NPC-018:forged"),
                SequenceRandom([]),
            )

    def test_slot_is_atomic_ordered_and_executed_once(self) -> None:
        source = request()
        result = execute_soporific_breath_action(
            source,
            SequenceRandom([1, 2, 1]),
        )
        with self.assertRaises(ValueError):
            execute_soporific_breath_action(
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
                            "forest-dragon",
                            CombatSide.PLAYERS_AND_ALLIES,
                        ),
                        CombatTurnParticipant(
                            "enemy",
                            CombatSide.OPPOSITION,
                        ),
                    ),
                ),
                "forest-dragon",
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:first",
                state,
                "forest-dragon",
                CombatActionDeclaration(CombatActionKind.AIM),
                ActionSlotGrant.STANDARD,
            )
        ).state
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                "slot:second",
                state,
                "forest-dragon",
                CombatActionDeclaration(
                    CombatActionKind.IMPROVISE,
                    improvise_kind=ImproviseKind.ABILITY,
                    improvise_approach_id=SOPORIFIC_BREATH_RULE_ID,
                ),
                ActionSlotGrant.FATE,
            )
        ).state
        with self.assertRaises(ValueError):
            execute_soporific_breath_action(
                request(round_state=state, slot_index=2),
                SequenceRandom([]),
            )

    def test_result_rejects_condition_batch_receipt_and_spatial_forgery(
        self,
    ) -> None:
        result = execute_soporific_breath_action(
            request(),
            SequenceRandom([10, 10]),
        )
        fresh, drained = result.zone_hazard.targets

        with self.assertRaises(ValueError):
            replace(result, target_zone_id="empty")
        with self.assertRaises(ValueError):
            replace(
                result,
                zone_hazard=replace(
                    result.zone_hazard,
                    targets=(drained, fresh),
                ),
            )
        assert fresh.hazard is not None
        with self.assertRaises(ValueError):
            replace(
                result,
                zone_hazard=replace(
                    result.zone_hazard,
                    targets=(
                        replace(
                            fresh,
                            hazard=replace(
                                fresh.hazard,
                                failure_conditions=(Condition.DEFENCELESS,),
                            ),
                        ),
                        drained,
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
                    free_move_used_entity_ids=("forest-dragon",),
                ),
            )
        with self.assertRaises(ValueError):
            replace(
                result,
                applied_rule_ids=(SOPORIFIC_BREATH_RULE_ID,),
            )


if __name__ == "__main__":
    unittest.main()
