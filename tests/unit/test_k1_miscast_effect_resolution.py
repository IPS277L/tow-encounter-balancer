from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectClassification,
    EffectImmunity,
    StaggerChoice,
    StaggerOutcome,
)
from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateNearMissBurnRequest,
    FateSessionState,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    DecisionOwner,
    ProfileInjuryState,
    WoundEnduranceFailure,
    WoundEnduranceTestRequest,
    WoundEntryId,
    WoundNegationOption,
    WoundRecord,
    WoundRecordOrigin,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.magic_models import (
    MiscastTableEffectRequest,
    WizardMagicState,
)
from towr.domain.miscast_effect_models import (
    MiscastArcaneSpillRequest,
    MiscastArcaneSightRequest,
    MiscastArcaneSightTestContext,
    MiscastCatastrophicDeathRequest,
    MiscastCreatureMovementDirectionMode,
    MiscastDaemonHostilePurpose,
    MiscastDaemonInitialCourse,
    MiscastDaemonReturnTrigger,
    MiscastDaemonRiftRequest,
    MiscastEarsRingingRequest,
    MiscastEffectTarget,
    MiscastFascinatingRiftCloseTrigger,
    MiscastFascinatingRiftRangeLimit,
    MiscastFascinatingRiftRequest,
    MiscastFascinatingRiftWitness,
    MiscastFascinatingRiftWitnessOutcome,
    MiscastFearedFoeIllusionDuration,
    MiscastFearedFoeIllusionRequest,
    MiscastFoodPreservationExample,
    MiscastFoodSpoilageRangeLimit,
    MiscastFoodSpoiledRequest,
    MiscastFoodState,
    MiscastHideousStenchChoice,
    MiscastHideousStenchOutcome,
    MiscastHideousStenchRequest,
    MiscastHideousStenchTarget,
    MiscastIlluminationKind,
    MiscastInternalDamageRequest,
    MiscastNauseatingWaveRangeLimit,
    MiscastNauseatingWaveRequest,
    MiscastObjectSelectionMode,
    MiscastObjectsTransfiguredRequest,
    MiscastObjectTransfigurationOutcome,
    MiscastObjectTransfigurationRangeLimit,
    MiscastRandomTransportRange,
    MiscastRandomTransportRequest,
    MiscastRecentSpellOption,
    MiscastSenseOfLossRangeLimit,
    MiscastSenseOfLossRequest,
    MiscastShadowChitteringOrigin,
    MiscastShadowChitteringRecurrence,
    MiscastShadowChitteringRequest,
    MiscastSmallObjectExample,
    MiscastSpellRecastRequest,
    MiscastSunlightBlindnessRequest,
    MiscastTruthboundRequest,
    MiscastUnnaturalWeatherExample,
    MiscastUnnaturalWeatherRequest,
    MiscastUnnaturalWindRequest,
    MiscastZoneHazardRequest,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest,
    GiveGroundRequest,
    IdentifiedHazardTarget,
    StaggerImpactRequest,
    TargetInjuryPolicy,
    ZoneHazardPersistence,
    ZoneHazardResolutionRequest,
)
from towr.domain.test_models import (
    Characteristic,
    InlineProfile,
    Skill,
    TestQuality,
    TestRequest,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
    FixedCharacterWoundLifecycleCompletionRequest,
)
from towr.rules.miscast_effect_resolution import (
    InvalidMiscastHideousStenchDecisionError,
    MissingMiscastHideousStenchDecisionError,
    apply_ears_ringing_fixed_character_wound_completion,
    apply_internal_damage_character_wound_completion,
    arcane_sight_quality_modifier,
    resolve_arcane_spill,
    resolve_arcane_sight,
    resolve_catastrophic_death,
    resolve_daemon_rift,
    resolve_ears_ringing,
    resolve_fascinating_rift,
    resolve_feared_foe_illusion,
    resolve_food_spoiled,
    resolve_hideous_stench,
    resolve_internal_damage,
    resolve_nauseating_wave,
    resolve_objects_transfigured,
    resolve_random_transport,
    resolve_sense_of_loss,
    resolve_shadow_chittering,
    resolve_spell_recast,
    resolve_sunlight_blindness,
    resolve_truthbound,
    resolve_unnatural_weather,
    resolve_unnatural_wind,
    resolve_zone_hazard_effect,
)
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
    complete_fixed_character_wound_lifecycle,
)
from towr.rules.miscast_table import lookup_miscast
from towr.rules.zone_hazard_resolution import resolve_zone_hazard


def effect_request(
    values: tuple[int, ...],
    *,
    bonus_dice: int = 0,
) -> MiscastTableEffectRequest:
    total = sum(values)
    entry = lookup_miscast(total)
    return MiscastTableEffectRequest(
        resolution_id=f"miscast:{entry.id.value}:effect",
        source_roll_id="miscast:roll",
        target_id="wizard",
        entry=entry,
        roll_values=values,
        total=total,
        pool_dice_count=len(values) - bonus_dice,
        bonus_dice=bonus_dice,
        rule_id=f"RULE-MISCAST-TABLE:{entry.id.value}",
    )


def target(
    target_id: str,
    policy: TargetInjuryPolicy,
    state: CharacterInjuryState | ProfileInjuryState,
) -> MiscastEffectTarget:
    return MiscastEffectTarget(target_id, policy, state)


class FallProneDecision:
    def choose_repeated_stagger(self, **_: object) -> StaggerChoice:
        return StaggerChoice.FALL_PRONE


class UseFirstWoundNegation:
    def choose_wound_negation(self, **kwargs: object) -> str:
        options = kwargs["options"]
        assert isinstance(options, tuple)
        return options[0].rule_id


class HideousStenchDecisions:
    def __init__(self, choice: object) -> None:
        self.choice = choice
        self.calls: list[tuple[str, DecisionOwner]] = []

    def choose_hideous_stench_response(self, **kwargs: object) -> object:
        selected_target = kwargs["target"]
        owner = kwargs["owner"]
        assert isinstance(selected_target, MiscastHideousStenchTarget)
        assert isinstance(owner, DecisionOwner)
        self.calls.append((selected_target.target_id, owner))
        return self.choice


class K1ArcaneSpillTests(unittest.TestCase):
    def test_arcane_spill_uses_common_repeated_stagger_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((5, 6))
        state = CharacterInjuryState(
            conditions=ConditionState({Condition.STAGGERED})
        )
        result = resolve_arcane_spill(
            MiscastArcaneSpillRequest(
                id="arcane-spill",
                source=source,
                magic_state=WizardMagicState(miscast_dice=2),
                stagger_impact=StaggerImpactRequest(
                    id="arcane-spill:wizard",
                    target_id="wizard",
                    target_policy=TargetInjuryPolicy.PLAYER,
                    target_state=state,
                    can_target_leave_zone=True,
                    target_has_given_ground_this_round=False,
                ),
            ),
            SequenceRandom([]),
            decisions=FallProneDecision(),
        )

        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertIs(
            result.stagger_impact.stagger.outcome,
            StaggerOutcome.FELL_PRONE,
        )
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(
            result.lore_effect_request.caster_id,
            "wizard",
        )
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))


class K1HideousStenchTests(unittest.TestCase):
    def test_resolves_each_target_choice_and_caster_fellowship_effect(
        self,
    ) -> None:
        source = effect_request((6, 7))
        decisions = HideousStenchDecisions(
            MiscastHideousStenchChoice.GIVE_GROUND
        )
        result = resolve_hideous_stench(
            MiscastHideousStenchRequest(
                id="hideous-stench",
                source=source,
                magic_state=WizardMagicState(miscast_dice=2),
                targets=(
                    MiscastHideousStenchTarget("guard", True),
                    MiscastHideousStenchTarget("trapped", False),
                ),
            ),
            decisions=decisions,
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("guard", "trapped"),
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        moving, trapped = result.targets
        self.assertIs(
            moving.outcome,
            MiscastHideousStenchOutcome.GIVE_GROUND_REQUESTED,
        )
        self.assertIs(moving.decision_owner, DecisionOwner.TARGET)
        self.assertIsInstance(moving.follow_ups[0], GiveGroundRequest)
        self.assertEqual(decisions.calls, [("guard", DecisionOwner.TARGET)])

        self.assertIs(
            trapped.outcome,
            MiscastHideousStenchOutcome.NEXT_TEST_PENALTY_APPLIED,
        )
        self.assertIsNone(trapped.decision_owner)
        penalty = trapped.follow_ups[0]
        self.assertEqual(penalty.target_id, "trapped")
        self.assertEqual(penalty.modifier.amount, -1)

        fellowship = result.fellowship_penalty
        self.assertEqual(fellowship.target_id, "wizard")
        self.assertIs(
            fellowship.characteristic,
            Characteristic.FELLOWSHIP,
        )
        self.assertIs(fellowship.modifier.quality, TestQuality.GRIM)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_no_nearby_targets_still_applies_caster_fellowship_effect(
        self,
    ) -> None:
        source = effect_request((6, 7))
        result = resolve_hideous_stench(
            MiscastHideousStenchRequest(
                id="hideous-stench",
                source=source,
                magic_state=WizardMagicState(miscast_dice=2),
            )
        )

        self.assertEqual(result.targets, ())
        self.assertEqual(result.fellowship_penalty.target_id, "wizard")
        self.assertEqual(result.magic_state.miscast_dice, 0)

    def test_requires_valid_decision_and_unique_target_ids(self) -> None:
        source = effect_request((6, 7))
        request = MiscastHideousStenchRequest(
            id="hideous-stench",
            source=source,
            magic_state=WizardMagicState(miscast_dice=2),
            targets=(MiscastHideousStenchTarget("guard", True),),
        )
        with self.assertRaises(MissingMiscastHideousStenchDecisionError):
            resolve_hideous_stench(request)
        with self.assertRaises(InvalidMiscastHideousStenchDecisionError):
            resolve_hideous_stench(
                request,
                decisions=HideousStenchDecisions("invalid"),
            )
        with self.assertRaises(ValueError):
            MiscastHideousStenchRequest(
                id="duplicate-target",
                source=source,
                magic_state=WizardMagicState(miscast_dice=2),
                targets=(
                    MiscastHideousStenchTarget("guard", True),
                    MiscastHideousStenchTarget("guard", False),
                ),
            )


class K1SpellRecastTests(unittest.TestCase):
    def test_selects_stable_recent_option_and_defers_gm_target(self) -> None:
        source = effect_request((7, 8, 8))
        options = (
            MiscastRecentSpellOption("cast-1", "RULE-SPELL:fireball"),
            MiscastRecentSpellOption("cast-2", "RULE-SPELL:shield"),
            MiscastRecentSpellOption("cast-3", "RULE-SPELL:healing"),
        )
        result = resolve_spell_recast(
            MiscastSpellRecastRequest(
                id="spell-recast",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                recent_spell_options=options,
            ),
            SequenceRandom([1]),
        )

        self.assertEqual(result.selected_index, 1)
        self.assertIs(result.selected_option, options[1])
        self.assertEqual(result.recast_request.source_option_id, "cast-2")
        self.assertEqual(
            result.recast_request.spell_rule_id,
            "RULE-SPELL:shield",
        )
        self.assertEqual(result.recast_request.potency, 1)
        self.assertIs(
            result.recast_request.target_choice_owner,
            DecisionOwner.GM,
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_requires_non_empty_snapshot_with_unique_option_ids(self) -> None:
        source = effect_request((7, 8, 8))
        with self.assertRaises(ValueError):
            MiscastSpellRecastRequest(
                id="no-recent-spell",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                recent_spell_options=(),
            )
        with self.assertRaises(ValueError):
            MiscastSpellRecastRequest(
                id="duplicate-options",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                recent_spell_options=(
                    MiscastRecentSpellOption("cast-1", "RULE-SPELL:a"),
                    MiscastRecentSpellOption("cast-1", "RULE-SPELL:b"),
                ),
            )


class K1TruthboundTests(unittest.TestCase):
    def test_creates_caster_effect_until_downtime_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((8, 8, 9))
        result = resolve_truthbound(
            MiscastTruthboundRequest(
                id="truthbound",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
            )
        )

        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(result.truthbound.caster_id, "wizard")
        self.assertEqual(result.truthbound.rule_id, source.rule_id)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))


class K1ArcaneSightTests(unittest.TestCase):
    def test_creates_effect_and_maps_explicit_test_context(self) -> None:
        source = effect_request((9, 9, 9))
        result = resolve_arcane_sight(
            MiscastArcaneSightRequest(
                id="arcane-sight",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
            )
        )

        self.assertEqual(result.arcane_sight.caster_id, "wizard")
        self.assertEqual(result.magic_state.miscast_dice, 0)
        normal = arcane_sight_quality_modifier(
            result.arcane_sight,
            MiscastArcaneSightTestContext.AFFECTED_NORMAL_AWARENESS,
        )
        magical = arcane_sight_quality_modifier(
            result.arcane_sight,
            MiscastArcaneSightTestContext.DETECT_MAGICAL_PHENOMENA,
        )
        self.assertIs(normal.quality, TestQuality.GRIM)
        self.assertIs(magical.quality, TestQuality.GLORIOUS)
        self.assertEqual(normal.rule_id, source.rule_id)
        self.assertEqual(magical.rule_id, source.rule_id)

    def test_modifier_requires_explicit_arcane_sight_context(self) -> None:
        source = effect_request((9, 9, 9))
        effect = resolve_arcane_sight(
            MiscastArcaneSightRequest(
                id="arcane-sight",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
            )
        ).arcane_sight

        with self.assertRaises(TypeError):
            arcane_sight_quality_modifier(effect, "ordinary-awareness")


class K1FearedFoeIllusionTests(unittest.TestCase):
    def test_battle_illusion_uses_prepared_reference_until_battle_end(
        self,
    ) -> None:
        source = effect_request((9, 10, 10))
        result = resolve_feared_foe_illusion(
            MiscastFearedFoeIllusionRequest(
                id="feared-foe-illusion",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                feared_foe_reference_id="narrative:caster-greatest-fear",
                battle_active=True,
            )
        )

        self.assertEqual(
            result.illusion.feared_foe_reference_id,
            "narrative:caster-greatest-fear",
        )
        self.assertIs(
            result.illusion.duration,
            MiscastFearedFoeIllusionDuration.UNTIL_BATTLE_END,
        )
        self.assertIsNone(result.illusion.duration_minutes)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_outside_battle_requires_explicit_positive_minutes(self) -> None:
        source = effect_request((9, 10, 10))
        result = resolve_feared_foe_illusion(
            MiscastFearedFoeIllusionRequest(
                id="feared-foe-illusion",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                feared_foe_reference_id="narrative:caster-greatest-fear",
                battle_active=False,
                outside_battle_duration_minutes=4,
            )
        )

        self.assertIs(
            result.illusion.duration,
            MiscastFearedFoeIllusionDuration.MINUTES,
        )
        self.assertEqual(result.illusion.duration_minutes, 4)
        with self.assertRaises(ValueError):
            MiscastFearedFoeIllusionRequest(
                id="missing-duration",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                feared_foe_reference_id="narrative:fear",
                battle_active=False,
            )
        with self.assertRaises(ValueError):
            MiscastFearedFoeIllusionRequest(
                id="unexpected-duration",
                source=source,
                magic_state=WizardMagicState(miscast_dice=3),
                feared_foe_reference_id="narrative:fear",
                battle_active=True,
                outside_battle_duration_minutes=4,
            )


class K1InternalDamageTests(unittest.TestCase):
    def test_character_rolls_then_completion_resolves_effect(
        self,
    ) -> None:
        source = effect_request((8, 8, 8, 8))
        state = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    sequence=1,
                    entry_id=WoundEntryId.SUPERFICIAL_INJURY,
                    table_total=1,
                    roll_values=(1,),
                    effect_resolved=True,
                ),
            )
        )
        result = resolve_internal_damage(
            MiscastInternalDamageRequest(
                id="internal-damage",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.PLAYER,
                    state,
                ),
            ),
            SequenceRandom([5, 6]),
        )

        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertIsNotNone(result.character_wound)
        assert result.character_wound is not None
        self.assertEqual(result.character_wound.table_roll.dice, 2)
        self.assertIs(
            result.character_wound.table_roll.entry.id,
            WoundEntryId.EARS_RINGING,
        )
        self.assertIsNone(result.wound_effect)
        self.assertIsNotNone(result.pending_character_wound)
        self.assertFalse(result.state.conditions.has(Condition.DEAFENED))

        assert result.pending_character_wound is not None
        completion = complete_character_wound_lifecycle(
            CharacterWoundLifecycleCompletionRequest(
                id="internal-damage:complete-wound",
                roll=result.pending_character_wound,
                current_state=result.state,
                daily_wounds=DailyWoundState("day:1", "wizard"),
                daily_registration_id="internal-damage:daily-wound",
            )
        )
        completed = apply_internal_damage_character_wound_completion(
            result,
            completion,
        )

        self.assertIsNone(completed.pending_character_wound)
        self.assertIs(completed.character_wound_completion, completion)
        self.assertIsNotNone(completed.wound_effect)
        self.assertTrue(completed.state.conditions.has(Condition.DEAFENED))
        self.assertEqual(completed.magic_state.miscast_dice, 0)

    def test_profile_npc_suffers_one_profile_wound_without_rng(self) -> None:
        source = effect_request((8, 8, 8, 8))
        result = resolve_internal_damage(
            MiscastInternalDamageRequest(
                id="internal-damage",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.BRUTE,
                    ProfileInjuryState(wounds=0, wound_limit=2),
                ),
            ),
            SequenceRandom([]),
        )

        self.assertIsNone(result.character_wound)
        self.assertIsNotNone(result.profile_wound)
        self.assertIsNone(result.pending_character_wound)
        self.assertEqual(result.state.wounds, 1)
        self.assertEqual(result.magic_state.miscast_dice, 0)

    def test_player_can_use_near_miss_before_internal_damage_completion(
        self,
    ) -> None:
        initial = CharacterInjuryState()
        result = resolve_internal_damage(
            MiscastInternalDamageRequest(
                id="internal-damage",
                source=effect_request((8, 8, 8, 8)),
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.PLAYER,
                    initial,
                ),
            ),
            SequenceRandom([6]),
        )

        assert result.pending_character_wound is not None
        wound_id = result.pending_character_wound.source_request.wound.id
        completion = complete_character_wound_lifecycle(
            CharacterWoundLifecycleCompletionRequest(
                id="internal-damage:complete-near-miss",
                roll=result.pending_character_wound,
                current_state=result.state,
                daily_wounds=DailyWoundState("day:1", "wizard"),
                near_miss=FateNearMissBurnRequest(
                    id="internal-damage:burn-fate",
                    state=FateSessionState(
                        session_id="session:1",
                        actor_id="wizard",
                        rating=1,
                        session_spend_limit=1,
                    ),
                    wound_negation=ConsumeWoundNegationRequest(
                        resolution_id=wound_id,
                        rule_id=FATE_NEAR_MISS_RULE_ID,
                    ),
                ),
            )
        )
        completed = apply_internal_damage_character_wound_completion(
            result,
            completion,
        )

        self.assertEqual(completed.state, initial)
        self.assertIsNone(completed.wound_effect)
        self.assertIsNone(completion.daily_registration)
        self.assertIsNotNone(completion.near_miss_application)
        self.assertEqual(completed.magic_state.miscast_dice, 0)

    def test_character_can_resolve_an_explicit_wound_negation(self) -> None:
        source = effect_request((8, 8, 8, 8))
        initial = CharacterInjuryState()
        result = resolve_internal_damage(
            MiscastInternalDamageRequest(
                id="internal-damage",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.PLAYER,
                    initial,
                ),
                wound_negation_options=(
                    WoundNegationOption("RULE-ABILITY:negate-wound"),
                ),
            ),
            SequenceRandom([5]),
            decisions=UseFirstWoundNegation(),
        )

        self.assertEqual(result.state, initial)
        self.assertIsNone(result.wound_effect)
        self.assertIsNotNone(result.pending_character_wound)
        self.assertIsNotNone(result.consume_wound_negation)
        assert result.consume_wound_negation is not None
        self.assertEqual(
            result.consume_wound_negation.rule_id,
            "RULE-ABILITY:negate-wound",
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)

        assert result.pending_character_wound is not None
        completion = complete_character_wound_lifecycle(
            CharacterWoundLifecycleCompletionRequest(
                id="internal-damage:complete-negated-wound",
                roll=result.pending_character_wound,
                current_state=result.state,
                daily_wounds=DailyWoundState("day:1", "wizard"),
            )
        )
        completed = apply_internal_damage_character_wound_completion(
            result,
            completion,
        )
        self.assertEqual(completed.state, initial)
        self.assertIsNone(completed.pending_character_wound)
        self.assertIs(completed.character_wound_completion, completion)

        with self.assertRaises(ValueError):
            apply_internal_damage_character_wound_completion(
                completed,
                completion,
            )


class K1EarsRingingTests(unittest.TestCase):
    def test_fixed_wound_preserves_target_order_and_does_not_fake_roll(
        self,
    ) -> None:
        source = effect_request((9, 9, 9, 9))
        result = resolve_ears_ringing(
            MiscastEarsRingingRequest(
                id="ears-ringing",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(
                    target(
                        "wizard",
                        TargetInjuryPolicy.PLAYER,
                        CharacterInjuryState(
                            conditions=ConditionState(
                                {Condition.STAGGERED}
                            )
                        ),
                    ),
                    target(
                        "guard",
                        TargetInjuryPolicy.BRUTE,
                        ProfileInjuryState(wounds=0, wound_limit=2),
                    ),
                ),
            )
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("wizard", "guard"),
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        caster = result.targets[0]
        assert caster.fixed_character_wound is not None
        record = caster.fixed_character_wound.state.wounds[-1]
        self.assertIs(record.entry_id, WoundEntryId.EARS_RINGING)
        self.assertIs(record.origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(record.roll_values, ())
        self.assertFalse(caster.state.conditions.has(Condition.DEAFENED))
        self.assertFalse(caster.state.conditions.has(Condition.STAGGERED))
        self.assertIsNone(caster.wound_effect)
        self.assertIsNotNone(caster.pending_fixed_character_wound)

        assert caster.pending_fixed_character_wound is not None
        completion = complete_fixed_character_wound_lifecycle(
            FixedCharacterWoundLifecycleCompletionRequest(
                id="ears-ringing:wizard:complete-wound",
                pending=caster.pending_fixed_character_wound,
                current_state=caster.state,
                daily_wounds=DailyWoundState("day:1", "wizard"),
                daily_registration_id="ears-ringing:wizard:daily-wound",
            )
        )
        completed_result = (
            apply_ears_ringing_fixed_character_wound_completion(
                result,
                "wizard",
                completion,
            )
        )
        completed_caster = completed_result.targets[0]
        self.assertIsNone(completed_caster.pending_fixed_character_wound)
        self.assertIs(
            completed_caster.fixed_character_wound_completion,
            completion,
        )
        self.assertTrue(
            completed_caster.state.conditions.has(Condition.DEAFENED)
        )
        assert completed_caster.wound_effect is not None
        follow_up = completed_caster.wound_effect.follow_ups[0]
        self.assertIsInstance(follow_up, WoundEnduranceTestRequest)
        assert isinstance(follow_up, WoundEnduranceTestRequest)
        self.assertIs(follow_up.failure, WoundEnduranceFailure.LOSE_D10_TEETH)
        self.assertEqual(completion.daily_wounds.wound_count, 1)
        self.assertEqual(completed_result.magic_state.miscast_dice, 0)

        guard = result.targets[1]
        self.assertIsNotNone(guard.profile_wound)
        self.assertEqual(guard.state.wounds, 1)
        self.assertFalse(guard.state.conditions.has(Condition.DEAFENED))
        self.assertIsNone(guard.pending_fixed_character_wound)

    def test_fixed_completion_is_target_bound_and_consumed_once(self) -> None:
        result = resolve_ears_ringing(
            MiscastEarsRingingRequest(
                id="ears-ringing",
                source=effect_request((9, 9, 9, 9)),
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(
                    target(
                        "wizard",
                        TargetInjuryPolicy.PLAYER,
                        CharacterInjuryState(),
                    ),
                ),
            )
        )
        pending = result.targets[0].pending_fixed_character_wound
        assert pending is not None
        completion = complete_fixed_character_wound_lifecycle(
            FixedCharacterWoundLifecycleCompletionRequest(
                id="ears-ringing:wizard:complete-wound",
                pending=pending,
                current_state=result.targets[0].state,
                daily_wounds=DailyWoundState("day:1", "wizard"),
                daily_registration_id="ears-ringing:wizard:daily-wound",
            )
        )

        with self.assertRaises(ValueError):
            apply_ears_ringing_fixed_character_wound_completion(
                result,
                "other",
                completion,
            )
        completed = apply_ears_ringing_fixed_character_wound_completion(
            result,
            "wizard",
            completion,
        )
        with self.assertRaises(ValueError):
            apply_ears_ringing_fixed_character_wound_completion(
                completed,
                "wizard",
                completion,
            )

    def test_targets_must_be_unique_and_start_with_caster(self) -> None:
        source = effect_request((9, 9, 9, 9))
        wizard = target(
            "wizard",
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(),
        )
        other = target(
            "other",
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(),
        )

        with self.assertRaises(ValueError):
            MiscastEarsRingingRequest(
                id="missing-caster-first",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(other, wizard),
            )
        with self.assertRaises(ValueError):
            MiscastEarsRingingRequest(
                id="duplicate-target",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(wizard, wizard),
            )


class K1SenseOfLossTests(unittest.TestCase):
    def test_preserves_medium_range_targets_without_inventory_loss(
        self,
    ) -> None:
        source = effect_request((2,))
        result = resolve_sense_of_loss(
            MiscastSenseOfLossRequest(
                id="sense-of-loss",
                source=source,
                magic_state=WizardMagicState(miscast_dice=1),
                target_ids=("guard", "ally"),
            )
        )

        effect = result.sense_of_loss
        self.assertEqual(effect.affected_target_ids, ("guard", "ally"))
        self.assertIs(effect.range_limit, MiscastSenseOfLossRangeLimit.MEDIUM)
        self.assertTrue(effect.causes_sudden_sense_of_loss)
        self.assertFalse(effect.can_identify_what_was_misplaced)
        self.assertFalse(effect.removes_inventory_items)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_allows_empty_snapshot_but_rejects_duplicate_targets(self) -> None:
        source = effect_request((1,))
        empty = MiscastSenseOfLossRequest(
            id="empty-sense-of-loss",
            source=source,
            magic_state=WizardMagicState(miscast_dice=1),
            target_ids=(),
        )
        self.assertEqual(
            resolve_sense_of_loss(empty).sense_of_loss.affected_target_ids,
            (),
        )

        with self.assertRaises(ValueError):
            MiscastSenseOfLossRequest(
                id="duplicate-sense-of-loss",
                source=source,
                magic_state=WizardMagicState(miscast_dice=1),
                target_ids=("guard", "guard"),
            )


class K1NauseatingWaveTests(unittest.TestCase):
    def test_preserves_stable_short_range_targets_without_other_effect(
        self,
    ) -> None:
        source = effect_request((1, 1, 1, 1))
        result = resolve_nauseating_wave(
            MiscastNauseatingWaveRequest(
                id="nauseating-wave",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                target_ids=("guard", "ally"),
            )
        )

        effect = result.nausea
        self.assertEqual(effect.affected_target_ids, ("guard", "ally"))
        self.assertIs(effect.range_limit, MiscastNauseatingWaveRangeLimit.SHORT)
        self.assertTrue(effect.causes_sudden_nausea)
        self.assertFalse(effect.has_other_effect)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_allows_empty_snapshot_but_rejects_duplicate_targets(self) -> None:
        source = effect_request((1, 1, 1, 1))
        empty = MiscastNauseatingWaveRequest(
            id="empty-nauseating-wave",
            source=source,
            magic_state=WizardMagicState(miscast_dice=4),
            target_ids=(),
        )
        self.assertEqual(resolve_nauseating_wave(empty).nausea.affected_target_ids, ())

        with self.assertRaises(ValueError):
            MiscastNauseatingWaveRequest(
                id="duplicate-nauseating-wave",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                target_ids=("guard", "guard"),
            )


class K1ObjectsTransfiguredTests(unittest.TestCase):
    def test_rolls_object_count_and_creates_random_spatial_follow_up(
        self,
    ) -> None:
        source = effect_request((1, 1, 1, 2))
        result = resolve_objects_transfigured(
            MiscastObjectsTransfiguredRequest(
                id="objects-transfigured",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            ),
            SequenceRandom([7]),
        )

        effect = result.transfiguration
        self.assertEqual(result.object_count_roll, 7)
        self.assertEqual(effect.requested_object_count, 7)
        self.assertEqual(effect.area_anchor_target_id, "wizard")
        self.assertIs(
            effect.range_limit,
            MiscastObjectTransfigurationRangeLimit.SHORT,
        )
        self.assertIs(
            effect.object_selection_mode,
            MiscastObjectSelectionMode.RANDOM_SMALL_OBJECTS,
        )
        self.assertEqual(
            effect.object_examples,
            (
                MiscastSmallObjectExample.COINS,
                MiscastSmallObjectExample.HALF_BURNED_CANDLE,
                MiscastSmallObjectExample.OLD_KEY,
            ),
        )
        self.assertFalse(effect.object_examples_are_exhaustive)
        self.assertIs(
            effect.transfiguration_outcome,
            MiscastObjectTransfigurationOutcome.VARIOUS_SMALL_CREATURES,
        )
        self.assertIs(effect.creature_choice_owner, DecisionOwner.GM)
        self.assertIs(
            effect.movement_direction_mode,
            MiscastCreatureMovementDirectionMode.RANDOM,
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_rejects_a_different_miscast_entry(self) -> None:
        with self.assertRaises(ValueError):
            MiscastObjectsTransfiguredRequest(
                id="objects-transfigured",
                source=effect_request((1, 2, 2, 2)),
                magic_state=WizardMagicState(miscast_dice=4),
            )


class K1ShadowChitteringTests(unittest.TestCase):
    def test_creates_caster_effect_until_mannslieb_full_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((1, 2, 2, 2))
        result = resolve_shadow_chittering(
            MiscastShadowChitteringRequest(
                id="shadow-chittering",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        effect = result.chittering
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(effect.listener_id, "wizard")
        self.assertIs(
            effect.sound_origin,
            MiscastShadowChitteringOrigin.NEARBY_SHADOW,
        )
        self.assertIs(
            effect.recurrence,
            MiscastShadowChitteringRecurrence
            .FREQUENT_AND_ENTIRELY_UNPREDICTABLE,
        )
        self.assertFalse(effect.rule_defines_mechanical_consequences)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_rejects_a_different_miscast_entry(self) -> None:
        with self.assertRaises(ValueError):
            MiscastShadowChitteringRequest(
                id="shadow-chittering",
                source=effect_request((2, 2, 2, 3)),
                magic_state=WizardMagicState(miscast_dice=4),
            )


class K1FoodSpoiledTests(unittest.TestCase):
    def test_spoils_fresh_food_in_long_range_and_clears_pool(self) -> None:
        source = effect_request((2, 2, 2, 3))
        result = resolve_food_spoiled(
            MiscastFoodSpoiledRequest(
                id="food-spoiled",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        effect = result.food_spoilage
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(effect.area_anchor_target_id, "wizard")
        self.assertIs(effect.range_limit, MiscastFoodSpoilageRangeLimit.LONG)
        self.assertEqual(effect.spoiled_food_states, (MiscastFoodState.FRESH,))
        self.assertEqual(
            effect.palatable_food_states,
            (MiscastFoodState.PRESERVED,),
        )
        self.assertEqual(
            effect.preservation_examples,
            (
                MiscastFoodPreservationExample.DRIED,
                MiscastFoodPreservationExample.SALTED,
                MiscastFoodPreservationExample.PICKLED,
            ),
        )
        self.assertFalse(effect.preservation_examples_are_exhaustive)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_rejects_a_different_miscast_entry(self) -> None:
        with self.assertRaises(ValueError):
            MiscastFoodSpoiledRequest(
                id="food-spoiled",
                source=effect_request((3, 4, 4, 4)),
                magic_state=WizardMagicState(miscast_dice=4),
            )


class K1UnnaturalWeatherTests(unittest.TestCase):
    def test_creates_gm_owned_local_weather_effect_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((3, 4, 4, 4))
        result = resolve_unnatural_weather(
            MiscastUnnaturalWeatherRequest(
                id="unnatural-weather",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        effect = result.weather_change
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(effect.local_area_anchor_target_id, "wizard")
        self.assertIs(effect.affected_area_choice_owner, DecisionOwner.GM)
        self.assertIs(effect.weather_choice_owner, DecisionOwner.GM)
        self.assertEqual(
            effect.book_examples,
            (
                MiscastUnnaturalWeatherExample.MALEFIC_STORM_FROM_CLEAR_SKIES,
                MiscastUnnaturalWeatherExample.FRIGID_SNOW_IN_SOMMERZEIT,
            ),
        )
        self.assertFalse(effect.book_examples_are_exhaustive)
        self.assertFalse(effect.rule_defines_exact_area)
        self.assertFalse(effect.rule_defines_duration)
        self.assertFalse(effect.rule_defines_mechanical_consequences)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_rejects_a_different_miscast_entry(self) -> None:
        with self.assertRaises(ValueError):
            MiscastUnnaturalWeatherRequest(
                id="unnatural-weather",
                source=effect_request((4, 4, 4, 5)),
                magic_state=WizardMagicState(miscast_dice=4),
            )


class K1RandomTransportTests(unittest.TestCase):
    def test_selects_stable_medium_range_destination_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((4, 4, 4, 5))
        result = resolve_random_transport(
            MiscastRandomTransportRequest(
                id="random-transport",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                origin_zone_id="zone:centre",
                eligible_destination_zone_ids=(
                    "zone:north",
                    "zone:east",
                    "zone:south",
                ),
            ),
            SequenceRandom([1]),
        )

        self.assertEqual(result.selected_index, 1)
        self.assertEqual(result.selected_destination_zone_id, "zone:east")
        self.assertEqual(result.relocation.caster_id, "wizard")
        self.assertEqual(result.relocation.origin_zone_id, "zone:centre")
        self.assertEqual(result.relocation.destination_zone_id, "zone:east")
        self.assertIs(
            result.relocation.destination_range,
            MiscastRandomTransportRange.MEDIUM,
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_requires_nonempty_unique_destinations_outside_origin(
        self,
    ) -> None:
        source = effect_request((4, 4, 4, 5))
        common = {
            "id": "random-transport",
            "source": source,
            "magic_state": WizardMagicState(miscast_dice=4),
            "origin_zone_id": "zone:centre",
        }
        with self.assertRaises(ValueError):
            MiscastRandomTransportRequest(
                **common,
                eligible_destination_zone_ids=(),
            )
        with self.assertRaises(ValueError):
            MiscastRandomTransportRequest(
                **common,
                eligible_destination_zone_ids=("zone:north", "zone:north"),
            )
        with self.assertRaises(ValueError):
            MiscastRandomTransportRequest(
                **common,
                eligible_destination_zone_ids=("zone:centre",),
            )


class K1SunlightBlindnessTests(unittest.TestCase):
    def test_creates_caster_effect_until_downtime_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((4, 5, 5, 6))
        result = resolve_sunlight_blindness(
            MiscastSunlightBlindnessRequest(
                id="sunlight-blindness",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        effect = result.blindness
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(effect.caster_id, "wizard")
        self.assertEqual(
            effect.unusable_illumination,
            (
                MiscastIlluminationKind.SUNLIGHT,
                MiscastIlluminationKind.OTHER_NATURAL_LIGHT,
            ),
        )
        self.assertEqual(
            effect.usable_illumination,
            (
                MiscastIlluminationKind.TORCHLIGHT,
                MiscastIlluminationKind.OTHER_ARTIFICIAL_LIGHT,
                MiscastIlluminationKind.ARCANE_ILLUMINATION,
            ),
        )
        self.assertTrue(effect.otherwise_treat_as_dead_of_night)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))


class K1UnnaturalWindTests(unittest.TestCase):
    def test_targets_fall_prone_in_order_except_monstrosities(self) -> None:
        source = effect_request((5, 5, 6, 6))
        result = resolve_unnatural_wind(
            MiscastUnnaturalWindRequest(
                id="unnatural-wind",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(
                    target(
                        "wizard",
                        TargetInjuryPolicy.PLAYER,
                        CharacterInjuryState(),
                    ),
                    target(
                        "guard",
                        TargetInjuryPolicy.BRUTE,
                        ProfileInjuryState(
                            wounds=0,
                            wound_limit=2,
                            conditions=ConditionState({Condition.PRONE}),
                        ),
                    ),
                    target(
                        "dragon",
                        TargetInjuryPolicy.MONSTROSITY,
                        ProfileInjuryState(wounds=0, wound_limit=3),
                    ),
                ),
            )
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("wizard", "guard", "dragon"),
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        wizard, guard, dragon = result.targets
        self.assertTrue(wizard.state.conditions.has(Condition.PRONE))
        self.assertFalse(wizard.excluded_as_monstrosity)
        self.assertIsNotNone(wizard.condition_application)
        assert guard.condition_application is not None
        self.assertTrue(guard.condition_application.was_already_present)
        self.assertTrue(dragon.excluded_as_monstrosity)
        self.assertIsNone(dragon.condition_application)
        self.assertFalse(dragon.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_targets_must_be_unique_and_start_with_caster(self) -> None:
        source = effect_request((5, 5, 6, 6))
        wizard = target(
            "wizard",
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(),
        )
        other = target(
            "other",
            TargetInjuryPolicy.CHAMPION,
            CharacterInjuryState(),
        )

        with self.assertRaises(ValueError):
            MiscastUnnaturalWindRequest(
                id="missing-caster-first",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(other, wizard),
            )
        with self.assertRaises(ValueError):
            MiscastUnnaturalWindRequest(
                id="duplicate-target",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                targets=(wizard, wizard),
            )


class K1ZoneHazardMiscastTests(unittest.TestCase):
    def test_creates_battle_hazard_from_all_dice_and_clears_pool(self) -> None:
        source = effect_request((6, 6, 7, 7, 7), bonus_dice=1)
        result = resolve_zone_hazard_effect(
            MiscastZoneHazardRequest(
                id="zone-hazard-miscast",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        hazard = result.zone_hazard
        self.assertEqual(hazard.rating, 5)
        self.assertEqual(
            hazard.avoidance_skills,
            (Skill.ENDURANCE, Skill.ATHLETICS),
        )
        self.assertIs(
            hazard.persistence,
            ZoneHazardPersistence.UNTIL_BATTLE_END,
        )
        self.assertEqual(hazard.zone_anchor_target_id, "wizard")
        self.assertTrue(hazard.inflicts_wound)
        self.assertEqual(hazard.failure_conditions, ())
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_common_zone_pipeline_requires_and_uses_each_target_choice(
        self,
    ) -> None:
        source = effect_request((8, 8, 8, 9))
        hazard = resolve_zone_hazard_effect(
            MiscastZoneHazardRequest(
                id="zone-hazard-miscast",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        ).zone_hazard
        target_without_choice = IdentifiedHazardTarget(
            target_id="guard",
            avoidance_test=TestRequest(
                id="guard:avoid-hazard",
                profile=InlineProfile(4, 10),
            ),
            target_policy=TargetInjuryPolicy.BRUTE,
            target_state=ProfileInjuryState(wounds=0, wound_limit=4),
        )
        with self.assertRaises(ValueError):
            ZoneHazardResolutionRequest(
                id="zone-hazard:resolve",
                source=hazard,
                targets=(target_without_choice,),
            )

        invalid_target = IdentifiedHazardTarget(
            target_id="guard",
            avoidance_test=target_without_choice.avoidance_test,
            target_policy=target_without_choice.target_policy,
            target_state=target_without_choice.target_state,
            selected_avoidance_skill=Skill.WILLPOWER,
        )
        with self.assertRaises(ValueError):
            ZoneHazardResolutionRequest(
                id="zone-hazard:resolve",
                source=hazard,
                targets=(invalid_target,),
            )

        chosen_target = IdentifiedHazardTarget(
            target_id="guard",
            avoidance_test=target_without_choice.avoidance_test,
            target_policy=target_without_choice.target_policy,
            target_state=target_without_choice.target_state,
            selected_avoidance_skill=Skill.ATHLETICS,
        )
        result = resolve_zone_hazard(
            ZoneHazardResolutionRequest(
                id="zone-hazard:resolve",
                source=hazard,
                targets=(chosen_target,),
            ),
            SequenceRandom([1, 1, 1, 1]),
        )

        resolved = result.targets[0]
        self.assertIs(resolved.exposure.avoidance_skill, Skill.ATHLETICS)
        assert resolved.hazard is not None
        self.assertTrue(resolved.hazard.avoided)


class K1DaemonRiftTests(unittest.TestCase):
    def test_creates_gm_owned_hostile_daemon_follow_up_and_clears_pool(
        self,
    ) -> None:
        source = effect_request((9, 9, 9, 10))
        result = resolve_daemon_rift(
            MiscastDaemonRiftRequest(
                id="daemon-rift",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
            )
        )

        manifestation = result.daemon_manifestation
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(manifestation.caster_id, "wizard")
        self.assertEqual(manifestation.rift_anchor_target_id, "wizard")
        self.assertIs(manifestation.nature_choice_owner, DecisionOwner.GM)
        self.assertIs(manifestation.stat_block_choice_owner, DecisionOwner.GM)
        self.assertIs(manifestation.placement_choice_owner, DecisionOwner.GM)
        self.assertIs(
            manifestation.initial_course_choice_owner,
            DecisionOwner.GM,
        )
        self.assertTrue(manifestation.hostile_to_caster_and_allies)
        self.assertEqual(
            manifestation.hostile_purpose_options,
            (
                MiscastDaemonHostilePurpose.BEGUILE,
                MiscastDaemonHostilePurpose.CORRUPT,
                MiscastDaemonHostilePurpose.DESTROY,
            ),
        )
        self.assertEqual(
            manifestation.initial_course_options,
            (
                MiscastDaemonInitialCourse.ACT_IMMEDIATELY,
                MiscastDaemonInitialCourse.FLEE_AND_PLOT,
            ),
        )
        self.assertEqual(
            manifestation.return_to_chaos_triggers,
            (
                MiscastDaemonReturnTrigger.DAEMON_DESTROYED,
                MiscastDaemonReturnTrigger.CASTER_DESTROYED,
            ),
        )
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))


class K1FascinatingRiftTests(unittest.TestCase):
    def test_resolves_witnesses_in_order_and_creates_portal_lifecycle(
        self,
    ) -> None:
        source = effect_request((9, 9, 10, 10))
        result = resolve_fascinating_rift(
            MiscastFascinatingRiftRequest(
                id="fascinating-rift",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                selected_zone_id="zone:gate",
                witnesses=(
                    MiscastFascinatingRiftWitness(
                        target_id="wizard",
                        willpower_test=TestRequest(
                            "wizard:willpower",
                            InlineProfile(2, 5),
                        ),
                    ),
                    MiscastFascinatingRiftWitness(
                        target_id="guard",
                        willpower_test=TestRequest(
                            "guard:willpower",
                            InlineProfile(2, 5),
                        ),
                    ),
                ),
            ),
            SequenceRandom([1, 10]),
        )

        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertEqual(result.portal.zone_id, "zone:gate")
        self.assertIs(result.portal.zone_choice_owner, DecisionOwner.GM)
        self.assertIs(
            result.portal.range_limit,
            MiscastFascinatingRiftRangeLimit.LONG,
        )
        self.assertEqual(
            result.portal.close_triggers,
            (
                MiscastFascinatingRiftCloseTrigger.SOMEONE_ENTERED,
                MiscastFascinatingRiftCloseTrigger.SOMETHING_EMERGED,
            ),
        )
        self.assertEqual(
            tuple(item.target_id for item in result.witnesses),
            ("wizard", "guard"),
        )
        wizard, guard = result.witnesses
        self.assertIs(
            wizard.outcome,
            MiscastFascinatingRiftWitnessOutcome.RESISTED,
        )
        assert wizard.willpower_test is not None
        self.assertEqual(wizard.willpower_test.trace.regular_dice_delta, -1)
        self.assertEqual(wizard.willpower_test.trace.rolled_dice, 1)
        self.assertIsNone(wizard.compulsion)
        self.assertIs(
            guard.outcome,
            MiscastFascinatingRiftWitnessOutcome.COMPELLED_TO_ENTER,
        )
        assert guard.compulsion is not None
        self.assertEqual(guard.compulsion.portal_id, result.portal.resolution_id)
        self.assertTrue(guard.compulsion.must_attempt_to_enter)
        self.assertTrue(guard.compulsion.restraint_prevents_entry)
        self.assertFalse(guard.compulsion.restraint_ends_compulsion)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_psychological_immunity_blocks_test_without_consuming_rng(
        self,
    ) -> None:
        source = effect_request((9, 9, 10, 10))
        immunity_rule = "RULE-NPC:undead-psychological-immunity"
        result = resolve_fascinating_rift(
            MiscastFascinatingRiftRequest(
                id="fascinating-rift",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                selected_zone_id="zone:crypt",
                witnesses=(
                    MiscastFascinatingRiftWitness(
                        target_id="skeleton",
                        willpower_test=TestRequest(
                            "skeleton:willpower",
                            InlineProfile(2, 5),
                        ),
                        effect_immunities=(
                            EffectImmunity(
                                EffectClassification.PSYCHOLOGICAL,
                                immunity_rule,
                            ),
                        ),
                    ),
                ),
            ),
            SequenceRandom([]),
        )

        witness = result.witnesses[0]
        self.assertIs(
            witness.outcome,
            MiscastFascinatingRiftWitnessOutcome.IMMUNE,
        )
        self.assertIsNone(witness.willpower_test)
        self.assertIsNone(witness.compulsion)
        self.assertEqual(witness.applied_rule_ids, (immunity_rule,))
        self.assertEqual(
            result.applied_rule_ids,
            (source.rule_id, immunity_rule),
        )

    def test_rejects_duplicate_witness_or_test_ids(self) -> None:
        source = effect_request((9, 9, 10, 10))
        witness = MiscastFascinatingRiftWitness(
            target_id="wizard",
            willpower_test=TestRequest(
                "wizard:willpower",
                InlineProfile(2, 5),
            ),
        )
        with self.assertRaises(ValueError):
            MiscastFascinatingRiftRequest(
                id="duplicate-witness",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                selected_zone_id="zone:gate",
                witnesses=(witness, witness),
            )

        with self.assertRaises(ValueError):
            MiscastFascinatingRiftRequest(
                id="duplicate-test",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                selected_zone_id="zone:gate",
                witnesses=(
                    witness,
                    MiscastFascinatingRiftWitness(
                        target_id="guard",
                        willpower_test=witness.willpower_test,
                    ),
                ),
            )


class K1CatastrophicDeathTests(unittest.TestCase):
    def test_character_dies_without_an_invented_wound_roll(self) -> None:
        source = effect_request((10, 10, 10, 10))
        result = resolve_catastrophic_death(
            MiscastCatastrophicDeathRequest(
                id="catastrophic-death",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.PLAYER,
                    CharacterInjuryState(),
                ),
            )
        )

        self.assertTrue(result.state.dead)
        self.assertTrue(result.body_destroyed)
        self.assertFalse(result.can_be_reanimated)
        self.assertEqual(result.magic_state.miscast_dice, 0)

    def test_profile_caster_is_defeated_and_marked_dead(self) -> None:
        source = effect_request((10, 10, 10, 10))
        result = resolve_catastrophic_death(
            MiscastCatastrophicDeathRequest(
                id="catastrophic-death",
                source=source,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=target(
                    "wizard",
                    TargetInjuryPolicy.MONSTROSITY,
                    ProfileInjuryState(wounds=1, wound_limit=3),
                ),
            )
        )

        self.assertTrue(result.state.defeated)
        self.assertEqual(result.state.wounds, 3)
        self.assertTrue(result.dead)
        self.assertFalse(result.can_be_reanimated)


class K1MiscastEffectValidationTests(unittest.TestCase):
    def test_effect_rejects_wrong_entry_or_pool_snapshot(self) -> None:
        internal = effect_request((8, 8, 8, 8))
        caster = target(
            "wizard",
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(),
        )
        with self.assertRaises(ValueError):
            MiscastCatastrophicDeathRequest(
                id="wrong-entry",
                source=internal,
                magic_state=WizardMagicState(miscast_dice=4),
                caster=caster,
            )
        with self.assertRaises(ValueError):
            MiscastInternalDamageRequest(
                id="wrong-pool",
                source=internal,
                magic_state=WizardMagicState(miscast_dice=3),
                caster=caster,
            )

    def test_wound_record_origin_rejects_invented_or_missing_dice(self) -> None:
        with self.assertRaises(ValueError):
            WoundRecord(
                sequence=1,
                entry_id=WoundEntryId.EARS_RINGING,
                table_total=11,
                roll_values=(10, 1),
                origin=WoundRecordOrigin.FIXED_ENTRY,
            )
        with self.assertRaises(ValueError):
            WoundRecord(
                sequence=1,
                entry_id=WoundEntryId.EARS_RINGING,
                table_total=11,
                roll_values=(),
                origin=WoundRecordOrigin.TABLE_ROLL,
            )


if __name__ == "__main__":
    unittest.main()
