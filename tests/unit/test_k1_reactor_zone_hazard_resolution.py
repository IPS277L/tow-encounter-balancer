from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    ProfileInjuryState,
    WoundNegationOption,
)
from towr.domain.resolution_models import (
    IdentifiedHazardTarget,
    ReactorZoneHazardRequest,
    ReactorZoneHazardResolutionRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import (
    InlineProfile,
    QualityModifier,
    Skill,
    TestQuality,
    TestRequest,
)
from towr.rules.reactor_zone_hazard_resolution import (
    resolve_reactor_zone_hazard,
)


class RecordingTestDecisions:
    def __init__(self) -> None:
        self.request_ids: list[str] = []

    def choose_glorious_rerolls(
        self,
        *,
        request: TestRequest,
        **_: object,
    ) -> tuple[int, ...]:
        self.request_ids.append(request.id)
        return ()


class RecordingWoundDecisions:
    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        self.request_ids: list[str] = []

    def choose_wound_negation(self, *, request, **_: object) -> str:
        self.request_ids.append(request.id)
        return self.rule_id


def source(
    *,
    failure_conditions: tuple[Condition, ...] = (),
) -> ReactorZoneHazardRequest:
    return ReactorZoneHazardRequest(
        resolution_id="giant-reaction",
        rating=3,
        avoidance_skill=Skill.ATHLETICS,
        rule_id="RULE-NPC:giant-unsteady",
        inflicts_wound=True,
        failure_conditions=failure_conditions,
    )


def target(
    target_id: str,
    *,
    test_id: str | None = None,
    policy: TargetInjuryPolicy = TargetInjuryPolicy.PLAYER,
    state=None,
    quality_modifiers: tuple[QualityModifier, ...] = (),
    wound_negation_options: tuple[WoundNegationOption, ...] = (),
) -> IdentifiedHazardTarget:
    if state is None:
        state = CharacterInjuryState()
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest(
            id=test_id or f"zone-hazard:{target_id}:test",
            profile=InlineProfile(3, 5),
            quality_modifiers=quality_modifiers,
        ),
        target_policy=policy,
        target_state=state,
        wound_negation_options=wound_negation_options,
    )


def batch(
    *targets: IdentifiedHazardTarget,
    reactor_target_id: str = "giant",
    hazard_source: ReactorZoneHazardRequest | None = None,
) -> ReactorZoneHazardResolutionRequest:
    return ReactorZoneHazardResolutionRequest(
        id="giant-zone-hazard",
        source=hazard_source or source(),
        reactor_target_id=reactor_target_id,
        targets=targets,
    )


class K1ReactorZoneHazardResolutionTests(unittest.TestCase):
    def test_targets_must_include_reactor_and_have_unique_ids(self) -> None:
        with self.assertRaises(ValueError):
            batch()
        with self.assertRaises(ValueError):
            batch(target("other"))
        with self.assertRaises(ValueError):
            batch(target("giant"), target("giant", test_id="other-test"))
        with self.assertRaises(ValueError):
            batch(
                target("giant", test_id="shared-test"),
                target("other", test_id="shared-test"),
            )

    def test_target_validates_injury_policy_before_execution(self) -> None:
        with self.assertRaises(TypeError):
            target(
                "giant",
                policy=TargetInjuryPolicy.MONSTROSITY,
                state=CharacterInjuryState(),
            )
        with self.assertRaises(ValueError):
            target(
                "minion",
                policy=TargetInjuryPolicy.MINION,
                state=ProfileInjuryState(wounds=0, wound_limit=2),
            )

    def test_targets_resolve_left_to_right_through_test_and_hazard(self) -> None:
        prone = ConditionState(frozenset({Condition.PRONE}))
        result = resolve_reactor_zone_hazard(
            batch(
                target("player"),
                target(
                    "giant",
                    policy=TargetInjuryPolicy.MONSTROSITY,
                    state=ProfileInjuryState(
                        wounds=0,
                        wound_limit=6,
                        conditions=prone,
                    ),
                ),
            ),
            SequenceRandom([1, 2, 10, 4, 10, 10, 10]),
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("player", "giant"),
        )
        player, giant = result.targets
        self.assertEqual(player.avoidance_test.trace.final_values, (1, 2, 10))
        self.assertEqual(player.hazard.shortfall, 1)
        assert player.hazard.character_wound is not None
        self.assertEqual(player.hazard.character_wound.table_roll.values, (4,))
        self.assertEqual(giant.avoidance_test.trace.final_values, (10, 10, 10))
        self.assertEqual(giant.hazard.shortfall, 3)
        self.assertEqual(giant.hazard.state.wounds, 3)
        self.assertTrue(giant.hazard.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.reactor_target_id, "giant")
        self.assertEqual(result.source_resolution_id, "giant-reaction")
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-NPC:giant-unsteady",),
        )

    def test_executor_forwards_test_and_wound_decisions(self) -> None:
        near_miss = WoundNegationOption("RULE-FATE:near-miss")
        test_decisions = RecordingTestDecisions()
        wound_decisions = RecordingWoundDecisions(near_miss.rule_id)
        result = resolve_reactor_zone_hazard(
            batch(
                target(
                    "giant",
                    policy=TargetInjuryPolicy.MONSTROSITY,
                    state=ProfileInjuryState(wounds=0, wound_limit=6),
                ),
                target(
                    "player",
                    quality_modifiers=(
                        QualityModifier(
                            "RULE-TEST:glorious",
                            TestQuality.GLORIOUS,
                        ),
                    ),
                    wound_negation_options=(near_miss,),
                ),
            ),
            SequenceRandom([1, 1, 1, 10, 10, 10, 1, 1, 1]),
            test_decisions=test_decisions,
            wound_decisions=wound_decisions,
        )

        player = result.targets[1]
        assert player.hazard.character_wound is not None
        self.assertFalse(player.hazard.character_wound.wound_accepted)
        self.assertEqual(player.hazard.state.wounds, ())
        self.assertEqual(
            test_decisions.request_ids,
            ["zone-hazard:player:test"],
        )
        self.assertEqual(
            wound_decisions.request_ids,
            ["giant-zone-hazard:player:hazard:wound"],
        )

    def test_failure_conditions_are_copied_to_every_exposure(self) -> None:
        result = resolve_reactor_zone_hazard(
            batch(
                target(
                    "giant",
                    policy=TargetInjuryPolicy.MONSTROSITY,
                    state=ProfileInjuryState(wounds=0, wound_limit=6),
                ),
                hazard_source=source(
                    failure_conditions=(Condition.DRAINED,),
                ),
            ),
            SequenceRandom([10, 10, 10]),
        )

        hazard = result.targets[0].hazard
        self.assertEqual(hazard.failure_conditions, (Condition.DRAINED,))
        self.assertTrue(hazard.state.conditions.has(Condition.DRAINED))
        self.assertIs(
            result.targets[0].exposure.avoidance_skill,
            Skill.ATHLETICS,
        )


if __name__ == "__main__":
    unittest.main()
