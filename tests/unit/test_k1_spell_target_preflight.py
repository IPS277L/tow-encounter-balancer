from __future__ import annotations

import unittest

from towr.domain.magic_models import (
    FormalSpellDefinition,
    IdentifiedSpellTarget,
    SpellCastRequest,
    SpellDuration,
    SpellRange,
    SpellTargetKind,
    SpellTargetPreflightOutcome,
    SpellTargetPreflightRequest,
)
from towr.rules.cowardly_flight_resolution import (
    COWARDLY_FLIGHT_RULE_ID,
    COWARDLY_FLIGHT_SPELL_DEFINITION,
)
from towr.rules.spell_cast_execution import resolve_spell_cast_targets
from towr.rules.spell_target_preflight import resolve_spell_target_preflight


def cast_request(
    *,
    spell_rule_id: str = COWARDLY_FLIGHT_RULE_ID,
    lore_id: str = "lore:battle-magic",
    casting_value: int = 3,
) -> SpellCastRequest:
    return SpellCastRequest(
        resolution_id="wizard:cast",
        caster_id="wizard",
        spell_rule_id=spell_rule_id,
        lore_id=lore_id,
        casting_value=casting_value,
        base_potency=2,
        rule_id="RULE-MAGIC-004:cast-or-wait",
    )


def preflight_request(
    *,
    source: SpellCastRequest | None = None,
    selected_target_kind: SpellTargetKind = SpellTargetKind.ZONE,
    target_within_range: bool = True,
    targets: tuple[IdentifiedSpellTarget, ...] = (
        IdentifiedSpellTarget("first-enemy"),
        IdentifiedSpellTarget("second-enemy"),
    ),
) -> SpellTargetPreflightRequest:
    return SpellTargetPreflightRequest(
        id="wizard:cast:preflight",
        source=source or cast_request(),
        definition=COWARDLY_FLIGHT_SPELL_DEFINITION,
        selected_target_id="zone:bridge",
        selected_target_kind=selected_target_kind,
        target_within_range=target_within_range,
        affected_targets=targets,
    )


class K1SpellTargetPreflightTests(unittest.TestCase):
    def test_cowardly_flight_definition_matches_page_162(self) -> None:
        definition = COWARDLY_FLIGHT_SPELL_DEFINITION

        self.assertEqual(definition.rule_id, COWARDLY_FLIGHT_RULE_ID)
        self.assertEqual(definition.casting_value, 3)
        self.assertIs(definition.target_kind, SpellTargetKind.ZONE)
        self.assertIs(definition.range, SpellRange.LONG)
        self.assertIs(definition.duration, SpellDuration.INSTANT)

    def test_valid_zone_preflight_preserves_affected_target_order(self) -> None:
        result = resolve_spell_target_preflight(preflight_request())

        self.assertIs(result.outcome, SpellTargetPreflightOutcome.READY)
        self.assertEqual(result.selected_target_id, "zone:bridge")
        self.assertIsNotNone(result.execution_request)
        assert result.execution_request is not None
        self.assertEqual(
            tuple(target.target_id for target in result.execution_request.targets),
            ("first-enemy", "second-enemy"),
        )

    def test_valid_empty_zone_has_no_affected_spell_targets(self) -> None:
        preflight = resolve_spell_target_preflight(
            preflight_request(targets=())
        )

        self.assertIs(preflight.outcome, SpellTargetPreflightOutcome.READY)
        assert preflight.execution_request is not None
        execution = resolve_spell_cast_targets(preflight.execution_request)
        self.assertEqual(execution.targets, ())
        self.assertEqual(execution.follow_ups, ())

    def test_invalid_target_kind_closes_before_target_execution(self) -> None:
        result = resolve_spell_target_preflight(
            preflight_request(selected_target_kind=SpellTargetKind.CREATURE)
        )

        self.assertIs(
            result.outcome,
            SpellTargetPreflightOutcome.INVALID_TARGET_KIND,
        )
        self.assertIsNone(result.execution_request)

    def test_out_of_range_zone_closes_before_target_execution(self) -> None:
        result = resolve_spell_target_preflight(
            preflight_request(target_within_range=False)
        )

        self.assertIs(result.outcome, SpellTargetPreflightOutcome.OUT_OF_RANGE)
        self.assertIsNone(result.execution_request)

    def test_cast_must_match_definition_rule_lore_and_cv(self) -> None:
        mismatches = (
            cast_request(spell_rule_id="RULE-SPELL-002:fireball"),
            cast_request(lore_id="lore:elementalism"),
            cast_request(casting_value=4),
        )

        for source in mismatches:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    resolve_spell_target_preflight(
                        preflight_request(source=source)
                    )

    def test_affected_target_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            preflight_request(
                targets=(
                    IdentifiedSpellTarget("same"),
                    IdentifiedSpellTarget("same"),
                )
            )

    def test_definition_fields_are_typed(self) -> None:
        with self.assertRaises(TypeError):
            FormalSpellDefinition(
                rule_id=COWARDLY_FLIGHT_RULE_ID,
                lore_id="lore:battle-magic",
                casting_value=3,
                target_kind="zone",  # type: ignore[arg-type]
                range=SpellRange.LONG,
                duration=SpellDuration.INSTANT,
            )


if __name__ == "__main__":
    unittest.main()
