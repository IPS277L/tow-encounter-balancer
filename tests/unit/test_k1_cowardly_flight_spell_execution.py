from __future__ import annotations

import unittest

from towr.domain.condition_models import EffectClassification, EffectImmunity
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.magic_models import (
    IdentifiedSpellTarget,
    SpellCastExecutionRequest,
    SpellCastRequest,
    SpellEffectApplicationRequest,
    SpellPotencyModifier,
)
from towr.domain.resolution_models import (
    CowardlyFlightSpellEffectRequest,
    CowardlyFlightWillpowerRequest,
    GiveGroundRequest,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.rules.cowardly_flight_resolution import (
    COWARDLY_FLIGHT_RULE_ID,
    resolve_cowardly_flight_spell_effect,
)
from towr.rules.spell_cast_execution import resolve_spell_cast_targets


def cast_effect(
    *,
    base_potency: int = 2,
    modifiers: tuple[SpellPotencyModifier, ...] = (),
) -> SpellEffectApplicationRequest:
    execution = resolve_spell_cast_targets(
        SpellCastExecutionRequest(
            id="wizard:cast:targets",
            source=SpellCastRequest(
                resolution_id="wizard:cast",
                caster_id="wizard",
                spell_rule_id=COWARDLY_FLIGHT_RULE_ID,
                lore_id="lore:battle-magic",
                casting_value=3,
                base_potency=base_potency,
                rule_id="RULE-MAGIC-004:cast-or-wait",
            ),
            selected_target_id="zone:bridge",
            targets=(
                IdentifiedSpellTarget(
                    "enemy",
                    potency_modifiers=modifiers,
                ),
            ),
        )
    )
    return execution.follow_ups[0]


def execution_request(
    source: SpellEffectApplicationRequest,
    *,
    can_give_ground: bool = True,
    immunities: tuple[EffectImmunity, ...] = (),
) -> CowardlyFlightSpellEffectRequest:
    return CowardlyFlightSpellEffectRequest(
        source=source,
        can_give_ground=can_give_ground,
        willpower_test=TestRequest(
            "wizard:cast:enemy:willpower",
            InlineProfile(2, 5),
        ),
        target_state=CharacterInjuryState(),
        target_effect_immunities=immunities,
    )


class K1CowardlyFlightSpellExecutionTests(unittest.TestCase):
    def test_prepared_effect_enters_existing_spell_reducer(self) -> None:
        source = cast_effect()

        result = resolve_cowardly_flight_spell_effect(
            execution_request(source)
        )

        self.assertEqual(result.request_id, source.resolution_id)
        self.assertEqual(result.target_id, "enemy")
        self.assertEqual(len(result.follow_ups), 2)
        self.assertIsInstance(result.follow_ups[0], GiveGroundRequest)
        willpower = result.follow_ups[1]
        self.assertIsInstance(willpower, CowardlyFlightWillpowerRequest)
        assert isinstance(willpower, CowardlyFlightWillpowerRequest)
        self.assertEqual(willpower.potency, 2)
        self.assertEqual(willpower.target_id, "enemy")

    def test_target_modifier_becomes_willpower_potency(self) -> None:
        source = cast_effect(
            base_potency=3,
            modifiers=(
                SpellPotencyModifier("RULE-MAGIC-002:magic-resistance", -1),
            ),
        )

        result = resolve_cowardly_flight_spell_effect(
            execution_request(source, can_give_ground=False)
        )

        self.assertEqual(len(result.follow_ups), 1)
        willpower = result.follow_ups[0]
        assert isinstance(willpower, CowardlyFlightWillpowerRequest)
        self.assertEqual(willpower.potency, 2)

    def test_psychological_immunity_still_blocks_both_consequences(self) -> None:
        source = cast_effect()
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-psychological-immunity",
        )

        result = resolve_cowardly_flight_spell_effect(
            execution_request(source, immunities=(immunity,))
        )

        self.assertTrue(result.application.blocked)
        self.assertEqual(result.follow_ups, ())

    def test_adapter_rejects_a_different_spell_rule(self) -> None:
        source = SpellEffectApplicationRequest(
            resolution_id="wizard:cast:target:effect",
            source_cast_id="wizard:cast",
            caster_id="wizard",
            spell_rule_id="RULE-SPELL-002:fireball",
            lore_id="lore:battle-magic",
            target_id="enemy",
            potency=2,
            rule_id="RULE-SPELL-002:fireball",
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_spell_effect(execution_request(source))

    def test_adapter_rejects_mismatched_effect_rule_id(self) -> None:
        source = SpellEffectApplicationRequest(
            resolution_id="wizard:cast:target:effect",
            source_cast_id="wizard:cast",
            caster_id="wizard",
            spell_rule_id=COWARDLY_FLIGHT_RULE_ID,
            lore_id="lore:battle-magic",
            target_id="enemy",
            potency=2,
            rule_id="RULE-MAGIC:wrong-source",
        )

        with self.assertRaises(ValueError):
            resolve_cowardly_flight_spell_effect(execution_request(source))


if __name__ == "__main__":
    unittest.main()
