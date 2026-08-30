from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.resolution_models import (
    HazardResolutionRequest,
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
    ZoneHazardResolutionRequest,
)
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.test_resolution import resolve_test
from towr.rules.troll_hazards import (
    TROLL_HAG_SWAMP_BREATH_RULE_ID,
    TROLL_VOMIT_RULE_ID,
    troll_hag_swamp_breath_hazard,
    troll_vomit_hazard,
)
from towr.rules.zone_hazard_resolution import resolve_zone_hazard


def target(target_id: str) -> IdentifiedHazardTarget:
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest(
            id=f"swamp-breath:{target_id}:test",
            profile=InlineProfile(3, 5),
        ),
        target_policy=TargetInjuryPolicy.BRUTE,
        target_state=ProfileInjuryState(wounds=0, wound_limit=6),
    )


class K1TrollHazardTests(unittest.TestCase):
    def test_vomit_factory_normalizes_the_book_hazard(self) -> None:
        exposure = troll_vomit_hazard(
            "troll:vomit",
            "troll:vomit:endurance",
        )

        self.assertEqual(exposure.rating, 3)
        self.assertIs(exposure.avoidance_skill, Skill.ENDURANCE)
        self.assertTrue(exposure.inflicts_wound)
        self.assertEqual(exposure.failure_conditions, ())
        self.assertEqual(exposure.rule_id, TROLL_VOMIT_RULE_ID)

    def test_vomit_uses_shortfall_as_profile_wounds(self) -> None:
        exposure = troll_vomit_hazard(
            "troll:vomit",
            "troll:vomit:endurance",
        )
        avoidance_test = resolve_test(
            TestRequest(
                id=exposure.test_id,
                profile=InlineProfile(2, 5),
            ),
            SequenceRandom([1, 10]),
        )

        result = resolve_hazard(
            HazardResolutionRequest(
                id="troll:vomit:hazard",
                target_id="hero",
                exposure=exposure,
                avoidance_test=avoidance_test,
                target_policy=TargetInjuryPolicy.BRUTE,
                target_state=ProfileInjuryState(wounds=0, wound_limit=6),
            ),
            SequenceRandom([]),
        )

        self.assertFalse(result.avoided)
        self.assertEqual(result.successes, 1)
        self.assertEqual(result.shortfall, 2)
        self.assertEqual(result.state.wounds, 2)
        self.assertEqual(result.failure_conditions, ())

    def test_swamp_breath_factory_normalizes_the_book_hazard(self) -> None:
        source = troll_hag_swamp_breath_hazard("troll-hag:swamp-breath")

        self.assertEqual(source.rating, 3)
        self.assertIs(source.avoidance_skill, Skill.ENDURANCE)
        self.assertTrue(source.inflicts_wound)
        self.assertEqual(source.failure_conditions, ())
        self.assertEqual(source.rule_id, TROLL_HAG_SWAMP_BREATH_RULE_ID)

    def test_swamp_breath_resolves_selected_zone_in_stable_order(self) -> None:
        result = resolve_zone_hazard(
            ZoneHazardResolutionRequest(
                id="troll-hag:swamp-breath:zone",
                source=troll_hag_swamp_breath_hazard(
                    "troll-hag:swamp-breath"
                ),
                targets=(target("resists"), target("fails")),
            ),
            SequenceRandom([1, 2, 3, 10, 10, 10]),
        )

        resists, fails = result.targets
        assert resists.hazard is not None
        assert fails.hazard is not None
        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("resists", "fails"),
        )
        self.assertTrue(resists.hazard.avoided)
        self.assertEqual(resists.hazard.state.wounds, 0)
        self.assertFalse(fails.hazard.avoided)
        self.assertEqual(fails.hazard.shortfall, 3)
        self.assertEqual(fails.hazard.state.wounds, 3)


if __name__ == "__main__":
    unittest.main()
