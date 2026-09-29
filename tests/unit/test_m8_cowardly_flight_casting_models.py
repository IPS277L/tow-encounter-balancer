from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import CastingAttemptExecutionRequest
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.cowardly_flight_casting_models import (
    BATTLE_MAGIC_LORE_ID, CastingCasterDefinition, CowardlyFlightCastingFacts,
    CowardlyFlightCastingPolicy, CowardlyFlightCastingRequest, CowardlyFlightCastingTarget,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import CastingTestRequest, WizardMagicState
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph
from towr.domain.test_models import InlineProfile, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest, ImproviseKind,
)
from towr.rules.casting_action_execution import execute_casting_attempt
from towr.rules.cowardly_flight_resolution import COWARDLY_FLIGHT_SPELL_DEFINITION
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def casting_input():
    """Authored numeric profiles, not a book NPC or complete battle scenario."""
    allies, enemies = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    participants = tuple(CombatTurnParticipant(actor, side) for actor, side in (
        ("wizard", allies), ("friend", allies), ("second", enemies),
        ("first", enemies), ("distant", enemies),
    ))
    combat = start_combat_turn(CombatTurnStartRequest(
        "start", CombatRoundState(3, participants), "wizard")).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        "reserve", combat, "wizard", CombatActionDeclaration(
            CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
            improvise_approach_id=BATTLE_MAGIC_LORE_ID), ActionSlotGrant.STANDARD,
    )).state
    spatial = SpatialBattleState(ZoneGraph(("arena", "elsewhere", "empty")), tuple(
        SpatialEntityPlacement(p.entity_id, p.side.value,
                               "elsewhere" if p.entity_id == "distant" else "arena")
        for p in reversed(participants)
    ), round_number=3)
    return CowardlyFlightCastingRequest(
        "cast", CastingCasterDefinition("wizard-profile", "authored:Wizard", 2, InlineProfile(3, 3)),
        "wizard", combat, 1, WizardMagicState(), spatial, "arena",
        tuple(CowardlyFlightCastingTarget(actor, InlineProfile(3, 3), ProfileInjuryState(0, 1), False)
              for actor in ("second", "first")),
        CowardlyFlightCastingFacts(**{f.name: True for f in fields(CowardlyFlightCastingFacts)}),
        CowardlyFlightCastingPolicy.CAST_WHEN_READY,
    )


def with_declaration(source, declaration):
    turn = source.round_state.active_turn
    slot = replace(turn.action_slots[0], declaration=declaration)
    return replace(source.round_state, active_turn=replace(turn, action_slots=(slot,)))


class CowardlyFlightCastingAdmissionTests(unittest.TestCase):
    def test_fresh_input_uses_reusable_definition_and_exact_participant_order(self):
        source = casting_input()
        self.assertNotEqual(source.caster.id, source.actor_id)
        self.assertEqual(tuple(t.actor_id for t in source.targets), ("second", "first"))
        self.assertEqual(source.policy, CowardlyFlightCastingPolicy.CAST_WHEN_READY)
        self.assertEqual(BATTLE_MAGIC_LORE_ID, COWARDLY_FLIGHT_SPELL_DEFINITION.lore_id)

    def test_models_are_frozen_slotted_and_copy_ordered_input(self):
        source = casting_input()
        targets = list(source.targets)
        admitted = replace(source, targets=targets)
        targets.clear()
        self.assertEqual(admitted, source)
        for model in (source, source.caster, source.facts, source.targets[0]):
            with self.subTest(model=type(model).__name__):
                self.assertFalse(hasattr(model, "__dict__"))
                field = fields(model)[0].name
                with self.assertRaises(FrozenInstanceError):
                    setattr(model, field, getattr(model, field))

    def test_admission_is_pure_and_does_not_invoke_execution_or_rng(self):
        source = casting_input()
        original, rng_state = deepcopy(source), random.getstate()
        with patch('towr.rules.casting_action_execution.execute_casting_attempt',
                   side_effect=AssertionError("must not execute")), patch(
                   'towr.rules.test_resolution.resolve_test', side_effect=AssertionError("must not roll")), patch(
                   'random.Random.randint', side_effect=AssertionError("must not use RNG")):
            self.assertEqual(replace(source), source)
            with self.assertRaisesRegex(ValueError, "targets must match"):
                replace(source, targets=())
        self.assertEqual(source, original)
        self.assertEqual(random.getstate(), rng_state)

    def test_every_fact_requires_true_explicit_boolean(self):
        facts = casting_input().facts
        for field in fields(facts):
            with self.subTest(fact=field.name):
                with self.assertRaisesRegex(ValueError, field.name):
                    replace(facts, **{field.name: False})
                for bad in (None, 1, "true"):
                    with self.assertRaises(TypeError):
                        replace(facts, **{field.name: bad})

    def test_wrong_request_types_and_string_policy_are_rejected(self):
        source = casting_input()
        for field in ("caster", "round_state", "magic_state", "spatial_state", "facts", "policy"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(source, **{field: None})
        with self.assertRaises(TypeError):
            replace(source, policy="cast_when_ready")

    def test_identifiers_must_be_nonblank_strings(self):
        source = casting_input()
        for model, names in ((source, ("id", "actor_id", "selected_zone_id")),
                             (source.caster, ("id", "source_rule_id")),
                             (source.targets[0], ("actor_id",))):
            for name in names:
                for bad, error in ((" ", ValueError), (1, TypeError)):
                    with self.subTest(field=name, bad=bad), self.assertRaises(error):
                        replace(model, **{name: bad})

    def test_wizard_level_range_and_bool_guard(self):
        source = casting_input()
        for level in range(1, 5):
            caster = replace(source.caster, wizard_level=level)
            self.assertEqual(replace(source, caster=caster).caster.wizard_level, level)
        for bad, error in ((0, ValueError), (5, ValueError), (True, TypeError), (2.0, TypeError)):
            with self.subTest(level=bad), self.assertRaises(error):
                replace(source.caster, wizard_level=bad)

    def test_only_inline_profiles_without_custom_caps_are_supported(self):
        source = casting_input()
        for model, name in ((source.caster, "casting_profile"), (source.targets[0], "willpower_profile")):
            with self.subTest(field=name):
                with self.assertRaises(TypeError):
                    replace(model, **{name: TestProfile(3, 3)})
                with self.assertRaises(ValueError):
                    replace(model, **{name: InlineProfile(3, 3, 6)})

    def test_only_healthy_minion_targets_without_conditions_are_admitted(self):
        target = casting_input().targets[0]
        for injury in (ProfileInjuryState(0, 2), ProfileInjuryState(1, 1, defeated=True),
                       ProfileInjuryState(0, 1, ConditionState((Condition.BROKEN,))),
                       ProfileInjuryState(0, 1, ConditionState((Condition.STAGGERED,)))):
            with self.subTest(injury=injury), self.assertRaises(ValueError):
                replace(target, injury=injury)
        with self.assertRaises(TypeError):
            replace(target, injury=None)

    def test_give_ground_cannot_be_suppressed_implicitly(self):
        target = casting_input().targets[0]
        with self.assertRaises(ValueError):
            replace(target, can_give_ground=True)
        for bad in (0, None, "false"):
            with self.assertRaises(TypeError):
                replace(target, can_give_ground=bad)

    def test_wait_state_and_threshold_equality_are_valid_but_pending_miscast_is_not(self):
        source = casting_input()
        for successes in (0, 1, 3, 8):
            magic = WizardMagicState(2, successes, BATTLE_MAGIC_LORE_ID, min(successes, 2))
            self.assertIs(replace(source, magic_state=magic).magic_state, magic)
        with self.assertRaisesRegex(ValueError, "mandatory Miscast"):
            replace(source, magic_state=WizardMagicState(3, 1, BATTLE_MAGIC_LORE_ID, 1))
        with self.assertRaisesRegex(ValueError, "active Casting Lore"):
            replace(source, magic_state=WizardMagicState(0, 0, "lore:illusion"))

    def test_wrong_actor_or_absent_turn_is_rejected(self):
        source = casting_input()
        for actor in ("friend", "first", "foreign"):
            with self.assertRaisesRegex(ValueError, "own the active turn"):
                replace(source, actor_id=actor)
        with self.assertRaisesRegex(ValueError, "own the active turn"):
            replace(source, round_state=replace(source.round_state, active_turn=None))

    def test_only_one_reserved_standard_first_slot_is_admitted(self):
        source = casting_input()
        for bad, error in ((True, TypeError), (1.0, TypeError), (0, ValueError), (2, ValueError)):
            with self.subTest(slot=bad), self.assertRaises(error):
                replace(source, slot_index=bad)
        empty = replace(source.round_state, active_turn=replace(source.round_state.active_turn, action_slots=()))
        second = reserve_combat_action_slot(CombatActionSlotRequest(
            "extra", source.round_state, source.actor_id,
            CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.ABILITY,
            grant_rule_id="authored:extra-action")).state
        for combat in (empty, second):
            with self.assertRaisesRegex(ValueError, "exactly one reserved"):
                replace(source, round_state=combat)

    def test_spell_declaration_must_match_lore_kind_and_not_produce_attack(self):
        source = casting_input()
        spell = source.round_state.active_turn.action_slots[0].declaration
        for declaration in (CombatActionDeclaration(CombatActionKind.ATTACK),
                            replace(spell, improvise_kind=ImproviseKind.SKILL),
                            replace(spell, improvise_approach_id="lore:illusion"),
                            replace(spell, improvise_produces_attack=True)):
            with self.subTest(declaration=declaration), self.assertRaisesRegex(ValueError, "spell Improvise"):
                replace(source, round_state=with_declaration(source, declaration))

    def test_real_executed_slot_cannot_be_admitted_again(self):
        source = casting_input()
        execution = execute_casting_attempt(CastingAttemptExecutionRequest(
            "execution", source.round_state, source.actor_id, source.slot_index, CastingTestRequest(
                "test", source.actor_id, BATTLE_MAGIC_LORE_ID,
                TestRequest("willpower", source.caster.casting_profile), source.magic_state,
            )), SequenceRandom([1, 2, 10]))
        with self.assertRaisesRegex(ValueError, "unexecuted standard slot"):
            replace(source, round_state=execution.state, magic_state=execution.casting.state)

    def test_spatial_round_zone_and_sides_must_match(self):
        source = casting_input()
        with self.assertRaisesRegex(ValueError, "another round"):
            replace(source, spatial_state=replace(source.spatial_state, round_number=2))
        with self.assertRaisesRegex(ValueError, "selected Zone"):
            replace(source, selected_zone_id="missing")
        spatial = source.spatial_state
        for index in range(len(spatial.placements)):
            placements = list(spatial.placements)
            placements[index] = replace(placements[index], side_id="foreign")
            with self.assertRaisesRegex(ValueError, "spatial side"):
                replace(source, spatial_state=replace(spatial, placements=placements))

    def test_all_round_participants_require_exact_spatial_coverage(self):
        source = casting_input()
        spatial = source.spatial_state
        for placements in (spatial.placements[:-1], spatial.placements + (
                SpatialEntityPlacement("foreign", "opposition", "arena"),)):
            with self.assertRaisesRegex(ValueError, "match round participants exactly"):
                replace(source, spatial_state=replace(spatial, placements=placements))

    def test_missing_duplicate_reversed_foreign_and_friendly_targets_rejected(self):
        source = casting_input()
        first, second = source.targets
        for targets in ((), (first,), (first, first), (second, first),
                        (first, second, replace(first, actor_id="distant")),
                        (replace(first, actor_id="friend"), second),
                        (replace(first, actor_id="wizard"), second),
                        (replace(first, actor_id="foreign"), second)):
            with self.subTest(targets=targets), self.assertRaisesRegex(ValueError, "targets must match"):
                replace(source, targets=targets)

    def test_unordered_or_untyped_target_inputs_rejected(self):
        source = casting_input()
        for targets in (set(source.targets), iter(source.targets), "first", None, ("second", "first")):
            with self.assertRaises(TypeError):
                replace(source, targets=targets)

    def test_empty_zone_and_distant_zone_are_valid_without_inferred_range(self):
        source = casting_input()
        self.assertEqual(replace(source, selected_zone_id="empty", targets=()).targets, ())
        distant = replace(source.targets[0], actor_id="distant")
        self.assertEqual(replace(source, selected_zone_id="elsewhere", targets=(distant,)).targets, (distant,))

    def test_completed_and_excluded_turns_do_not_silently_hide_enemies(self):
        source = casting_input()
        combat = replace(source.round_state, completed_turn_entity_ids=("friend", "first"),
                         excluded_turn_entity_ids=("second",))
        self.assertEqual(replace(source, round_state=combat).targets, source.targets)
        with self.assertRaisesRegex(ValueError, "targets must match"):
            replace(source, round_state=combat, targets=(source.targets[1],))

    def test_opposition_caster_filters_by_its_own_side(self):
        source = casting_input()
        combat = replace(source.round_state, active_turn=None,
                         completed_turn_entity_ids=("wizard", "friend"))
        combat = start_combat_turn(CombatTurnStartRequest("enemy-turn", combat, "first")).state
        declaration = source.round_state.active_turn.action_slots[0].declaration
        combat = reserve_combat_action_slot(CombatActionSlotRequest(
            "enemy-slot", combat, "first", declaration, ActionSlotGrant.STANDARD)).state
        targets = tuple(replace(source.targets[0], actor_id=actor) for actor in ("wizard", "friend"))
        self.assertEqual(replace(source, actor_id="first", round_state=combat, targets=targets).targets, targets)

    def test_spatial_turn_history_is_preserved_without_reset(self):
        source = casting_input()
        spatial = replace(source.spatial_state, gave_ground_entity_ids=("first",),
                          free_move_used_entity_ids=("wizard",),
                          difficult_terrain_tested_entity_ids=("wizard",))
        self.assertIs(replace(source, spatial_state=spatial).spatial_state, spatial)


if __name__ == "__main__":
    unittest.main()
