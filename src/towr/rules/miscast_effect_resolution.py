from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    EffectApplicationRequest,
    EffectClassification,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    DecisionOwner,
    FixedCharacterWoundRequest,
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
    WoundEntryId,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.miscast_effect_models import (
    MiscastArcaneSpillRequest,
    MiscastArcaneSpillResult,
    MiscastArcaneSightRequest,
    MiscastArcaneSightResult,
    MiscastArcaneSightTestContext,
    MiscastArcaneSightUntilMorrsliebFullRequest,
    MiscastCatastrophicDeathRequest,
    MiscastCatastrophicDeathResult,
    MiscastDaemonManifestationRequest,
    MiscastDaemonRiftRequest,
    MiscastDaemonRiftResult,
    MiscastEarsRingingRequest,
    MiscastEarsRingingResult,
    MiscastEarsRingingTargetResult,
    MiscastEffectTarget,
    MiscastFascinatingRiftCompulsionRequest,
    MiscastFascinatingRiftPortal,
    MiscastFascinatingRiftRequest,
    MiscastFascinatingRiftResult,
    MiscastFascinatingRiftWitness,
    MiscastFascinatingRiftWitnessOutcome,
    MiscastFascinatingRiftWitnessResult,
    MiscastFearedFoeIllusionDuration,
    MiscastFearedFoeIllusionEffectRequest,
    MiscastFearedFoeIllusionRequest,
    MiscastFearedFoeIllusionResult,
    MiscastFoodSpoilageApplicationRequest,
    MiscastFoodSpoiledRequest,
    MiscastFoodSpoiledResult,
    MiscastInternalDamageRequest,
    MiscastInternalDamageResult,
    MiscastFellowshipGrimUntilBatheRequest,
    MiscastHideousStenchChoice,
    MiscastHideousStenchOutcome,
    MiscastHideousStenchRequest,
    MiscastHideousStenchResult,
    MiscastHideousStenchTarget,
    MiscastHideousStenchTargetResult,
    MiscastMinorLoreEffectRequest,
    MiscastNauseatingWaveApplicationRequest,
    MiscastNauseatingWaveRequest,
    MiscastNauseatingWaveResult,
    MiscastNextTestPenaltyRequest,
    MiscastObjectsTransfigurationApplicationRequest,
    MiscastObjectsTransfiguredRequest,
    MiscastObjectsTransfiguredResult,
    MiscastRandomTransportRelocationRequest,
    MiscastRandomTransportRequest,
    MiscastRandomTransportResult,
    MiscastSenseOfLossApplicationRequest,
    MiscastSenseOfLossRequest,
    MiscastSenseOfLossResult,
    MiscastShadowChitteringRequest,
    MiscastShadowChitteringResult,
    MiscastShadowChitteringUntilMannsliebFullRequest,
    MiscastSpellRecastApplicationRequest,
    MiscastSpellRecastRequest,
    MiscastSpellRecastResult,
    MiscastSunlightBlindnessRequest,
    MiscastSunlightBlindnessResult,
    MiscastSunlightBlindnessUntilDowntimeRequest,
    MiscastTruthboundRequest,
    MiscastTruthboundResult,
    MiscastTruthboundUntilDowntimeRequest,
    MiscastUnnaturalWeatherApplicationRequest,
    MiscastUnnaturalWeatherRequest,
    MiscastUnnaturalWeatherResult,
    MiscastUnnaturalWindRequest,
    MiscastUnnaturalWindResult,
    MiscastUnnaturalWindTargetResult,
    MiscastZoneHazardRequest,
    MiscastZoneHazardResult,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest,
    GiveGroundRequest,
    TargetInjuryPolicy,
    TargetInjuryState,
    ZoneHazardPersistence,
    ZoneHazardRequest,
)
from towr.domain.test_models import (
    DiceModifier,
    QualityModifier,
    Skill,
    TestQuality,
)
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.dice import RandomSource
from towr.rules.effect_resolution import resolve_effect_application
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_character_wound,
    resolve_fixed_character_wound,
    resolve_profile_wound,
)
from towr.rules.stagger_impact_resolution import (
    StaggerImpactDecisionProvider,
    resolve_stagger_impact,
)
from towr.rules.test_resolution import TestDecisionProvider, resolve_test
from towr.rules.wound_effect_resolution import resolve_wound_effect


class MissingMiscastHideousStenchDecisionError(RuntimeError):
    pass


class InvalidMiscastHideousStenchDecisionError(ValueError):
    pass


class MiscastHideousStenchDecisionProvider(Protocol):
    def choose_hideous_stench_response(
        self,
        *,
        request: MiscastHideousStenchRequest,
        target: MiscastHideousStenchTarget,
        owner: DecisionOwner,
        choices: tuple[MiscastHideousStenchChoice, ...],
    ) -> MiscastHideousStenchChoice: ...


def resolve_hideous_stench(
    request: MiscastHideousStenchRequest,
    *,
    decisions: MiscastHideousStenchDecisionProvider | None = None,
) -> MiscastHideousStenchResult:
    results = tuple(
        _resolve_hideous_stench_target(request, target, decisions)
        for target in request.targets
    )
    fellowship_penalty = MiscastFellowshipGrimUntilBatheRequest(
        resolution_id=f"{request.id}:fellowship-grim-until-bathe",
        target_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastHideousStenchResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        targets=results,
        fellowship_penalty=fellowship_penalty,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *(
                rule_id
                for result in results
                for rule_id in result.applied_rule_ids
            ),
        ),
    )


def resolve_spell_recast(
    request: MiscastSpellRecastRequest,
    rng: RandomSource,
) -> MiscastSpellRecastResult:
    selected_index = rng.randint(0, len(request.recent_spell_options) - 1)
    selected = request.recent_spell_options[selected_index]
    recast_request = MiscastSpellRecastApplicationRequest(
        resolution_id=f"{request.id}:recast",
        caster_id=request.source.target_id,
        source_option_id=selected.option_id,
        spell_rule_id=selected.spell_rule_id,
        potency=1,
        target_choice_owner=DecisionOwner.GM,
        rule_id=request.source.rule_id,
    )
    return MiscastSpellRecastResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        selected_index=selected_index,
        selected_option=selected,
        recast_request=recast_request,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_truthbound(
    request: MiscastTruthboundRequest,
) -> MiscastTruthboundResult:
    truthbound = MiscastTruthboundUntilDowntimeRequest(
        resolution_id=f"{request.id}:truthbound-until-downtime",
        caster_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastTruthboundResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        truthbound=truthbound,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_arcane_sight(
    request: MiscastArcaneSightRequest,
) -> MiscastArcaneSightResult:
    arcane_sight = MiscastArcaneSightUntilMorrsliebFullRequest(
        resolution_id=f"{request.id}:arcane-sight-until-morrslieb-full",
        caster_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastArcaneSightResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        arcane_sight=arcane_sight,
        applied_rule_ids=(request.source.rule_id,),
    )


def arcane_sight_quality_modifier(
    effect: MiscastArcaneSightUntilMorrsliebFullRequest,
    context: MiscastArcaneSightTestContext,
) -> QualityModifier:
    if not isinstance(
        effect,
        MiscastArcaneSightUntilMorrsliebFullRequest,
    ):
        raise TypeError("effect must be an Arcane Sight effect request")
    if not isinstance(context, MiscastArcaneSightTestContext):
        raise TypeError("context must be a MiscastArcaneSightTestContext")
    quality = (
        TestQuality.GRIM
        if context is MiscastArcaneSightTestContext.AFFECTED_NORMAL_AWARENESS
        else TestQuality.GLORIOUS
    )
    return QualityModifier(rule_id=effect.rule_id, quality=quality)


def resolve_feared_foe_illusion(
    request: MiscastFearedFoeIllusionRequest,
) -> MiscastFearedFoeIllusionResult:
    duration = (
        MiscastFearedFoeIllusionDuration.UNTIL_BATTLE_END
        if request.battle_active
        else MiscastFearedFoeIllusionDuration.MINUTES
    )
    illusion = MiscastFearedFoeIllusionEffectRequest(
        resolution_id=f"{request.id}:feared-foe-illusion",
        caster_id=request.source.target_id,
        feared_foe_reference_id=request.feared_foe_reference_id,
        duration=duration,
        duration_minutes=request.outside_battle_duration_minutes,
        rule_id=request.source.rule_id,
    )
    return MiscastFearedFoeIllusionResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        illusion=illusion,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_arcane_spill(
    request: MiscastArcaneSpillRequest,
    rng: RandomSource,
    *,
    decisions: StaggerImpactDecisionProvider | None = None,
) -> MiscastArcaneSpillResult:
    _ensure_active(request.stagger_impact.target_state)
    impact = resolve_stagger_impact(
        request.stagger_impact,
        rng,
        decisions=decisions,
    )
    lore_effect = MiscastMinorLoreEffectRequest(
        resolution_id=f"{request.id}:minor-lore-effect",
        caster_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastArcaneSpillResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        state=impact.state,
        stagger_impact=impact,
        lore_effect_request=lore_effect,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *impact.applied_rule_ids,
        ),
    )


def resolve_internal_damage(
    request: MiscastInternalDamageRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> MiscastInternalDamageResult:
    _ensure_active(request.caster.state)
    if request.caster.policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }:
        assert isinstance(request.caster.state, CharacterInjuryState)
        wound = resolve_character_wound(
            CharacterWoundRequest(
                id=f"{request.id}:wound",
                state=request.caster.state,
                subject_type=_character_type(request.caster.policy),
                dice_modifiers=request.wound_dice_modifiers,
                negation_options=request.wound_negation_options,
            ),
            rng,
            decisions=decisions,
        )
        wound_effect = (
            resolve_wound_effect(wound.effect_request, wound.state)
            if wound.effect_request is not None
            else None
        )
        state = wound_effect.state if wound_effect is not None else wound.state
        return MiscastInternalDamageResult(
            request_id=request.id,
            caster_id=request.caster.target_id,
            magic_state=_clear_pool(request.magic_state),
            state=state,
            character_wound=wound,
            wound_effect=wound_effect,
            profile_wound=None,
            consume_wound_negation=(
                ConsumeWoundNegationRequest(
                    resolution_id=request.id,
                    rule_id=wound.negated_by_rule_id,
                )
                if wound.negated_by_rule_id is not None
                else None
            ),
            applied_rule_ids=_unique_rule_ids(
                request.source.rule_id,
                *wound.applied_rule_ids,
                *(
                    wound_effect.applied_rule_ids
                    if wound_effect is not None
                    else ()
                ),
            ),
        )

    assert isinstance(request.caster.state, ProfileInjuryState)
    wound = resolve_profile_wound(
        ProfileWoundRequest(
            id=f"{request.id}:wound",
            npc_type=_profile_type(request.caster.policy),
            state=request.caster.state,
            additional_wounds=request.additional_profile_wounds,
        )
    )
    return MiscastInternalDamageResult(
        request_id=request.id,
        caster_id=request.caster.target_id,
        magic_state=_clear_pool(request.magic_state),
        state=wound.state,
        character_wound=None,
        wound_effect=None,
        profile_wound=wound,
        consume_wound_negation=None,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *wound.applied_rule_ids,
        ),
    )


def resolve_ears_ringing(
    request: MiscastEarsRingingRequest,
) -> MiscastEarsRingingResult:
    results = tuple(
        _resolve_ears_ringing_target(request, target)
        for target in request.targets
    )
    return MiscastEarsRingingResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        targets=results,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *(
                rule_id
                for result in results
                for rule_id in result.applied_rule_ids
            ),
        ),
    )


def resolve_random_transport(
    request: MiscastRandomTransportRequest,
    rng: RandomSource,
) -> MiscastRandomTransportResult:
    selected_index = rng.randint(
        0,
        len(request.eligible_destination_zone_ids) - 1,
    )
    destination = request.eligible_destination_zone_ids[selected_index]
    relocation = MiscastRandomTransportRelocationRequest(
        resolution_id=f"{request.id}:relocation",
        caster_id=request.source.target_id,
        origin_zone_id=request.origin_zone_id,
        destination_zone_id=destination,
        rule_id=request.source.rule_id,
    )
    return MiscastRandomTransportResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        selected_index=selected_index,
        selected_destination_zone_id=destination,
        relocation=relocation,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_food_spoiled(
    request: MiscastFoodSpoiledRequest,
) -> MiscastFoodSpoiledResult:
    food_spoilage = MiscastFoodSpoilageApplicationRequest(
        resolution_id=f"{request.id}:food-spoilage",
        caster_id=request.source.target_id,
        area_anchor_target_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastFoodSpoiledResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        food_spoilage=food_spoilage,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_objects_transfigured(
    request: MiscastObjectsTransfiguredRequest,
    rng: RandomSource,
) -> MiscastObjectsTransfiguredResult:
    object_count_roll = rng.randint(1, 10)
    transfiguration = MiscastObjectsTransfigurationApplicationRequest(
        resolution_id=f"{request.id}:transfiguration",
        caster_id=request.source.target_id,
        area_anchor_target_id=request.source.target_id,
        requested_object_count=object_count_roll,
        rule_id=request.source.rule_id,
    )
    return MiscastObjectsTransfiguredResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        object_count_roll=object_count_roll,
        transfiguration=transfiguration,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_nauseating_wave(
    request: MiscastNauseatingWaveRequest,
) -> MiscastNauseatingWaveResult:
    nausea = MiscastNauseatingWaveApplicationRequest(
        resolution_id=f"{request.id}:nausea",
        caster_id=request.source.target_id,
        affected_target_ids=request.target_ids,
        rule_id=request.source.rule_id,
    )
    return MiscastNauseatingWaveResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        nausea=nausea,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_sense_of_loss(
    request: MiscastSenseOfLossRequest,
) -> MiscastSenseOfLossResult:
    sense_of_loss = MiscastSenseOfLossApplicationRequest(
        resolution_id=f"{request.id}:sense-of-loss",
        caster_id=request.source.target_id,
        affected_target_ids=request.target_ids,
        rule_id=request.source.rule_id,
    )
    return MiscastSenseOfLossResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        sense_of_loss=sense_of_loss,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_shadow_chittering(
    request: MiscastShadowChitteringRequest,
) -> MiscastShadowChitteringResult:
    chittering = MiscastShadowChitteringUntilMannsliebFullRequest(
        resolution_id=f"{request.id}:until-mannslieb-full",
        listener_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastShadowChitteringResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        chittering=chittering,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_unnatural_weather(
    request: MiscastUnnaturalWeatherRequest,
) -> MiscastUnnaturalWeatherResult:
    weather_change = MiscastUnnaturalWeatherApplicationRequest(
        resolution_id=f"{request.id}:weather-change",
        caster_id=request.source.target_id,
        local_area_anchor_target_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastUnnaturalWeatherResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        weather_change=weather_change,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_sunlight_blindness(
    request: MiscastSunlightBlindnessRequest,
) -> MiscastSunlightBlindnessResult:
    blindness = MiscastSunlightBlindnessUntilDowntimeRequest(
        resolution_id=f"{request.id}:sunlight-blindness",
        caster_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastSunlightBlindnessResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        blindness=blindness,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_unnatural_wind(
    request: MiscastUnnaturalWindRequest,
) -> MiscastUnnaturalWindResult:
    results = tuple(
        _resolve_unnatural_wind_target(request, target)
        for target in request.targets
    )
    return MiscastUnnaturalWindResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        targets=results,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *(
                rule_id
                for result in results
                for rule_id in result.applied_rule_ids
            ),
        ),
    )


def resolve_zone_hazard_effect(
    request: MiscastZoneHazardRequest,
) -> MiscastZoneHazardResult:
    hazard = ZoneHazardRequest(
        resolution_id=f"{request.id}:zone-hazard",
        rating=len(request.source.roll_values),
        avoidance_skill=Skill.ENDURANCE,
        alternative_avoidance_skills=(Skill.ATHLETICS,),
        rule_id=request.source.rule_id,
        inflicts_wound=True,
        failure_conditions=(),
        persistence=ZoneHazardPersistence.UNTIL_BATTLE_END,
        zone_anchor_target_id=request.source.target_id,
    )
    return MiscastZoneHazardResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        zone_hazard=hazard,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_daemon_rift(
    request: MiscastDaemonRiftRequest,
) -> MiscastDaemonRiftResult:
    manifestation = MiscastDaemonManifestationRequest(
        resolution_id=f"{request.id}:daemon-manifestation",
        caster_id=request.source.target_id,
        rift_anchor_target_id=request.source.target_id,
        rule_id=request.source.rule_id,
    )
    return MiscastDaemonRiftResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        daemon_manifestation=manifestation,
        applied_rule_ids=(request.source.rule_id,),
    )


def resolve_fascinating_rift(
    request: MiscastFascinatingRiftRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> MiscastFascinatingRiftResult:
    portal = MiscastFascinatingRiftPortal(
        resolution_id=f"{request.id}:portal",
        caster_id=request.source.target_id,
        zone_id=request.selected_zone_id,
        rule_id=request.source.rule_id,
    )
    witnesses = tuple(
        _resolve_fascinating_rift_witness(
            request,
            portal,
            witness,
            rng,
            decisions,
        )
        for witness in request.witnesses
    )
    return MiscastFascinatingRiftResult(
        request_id=request.id,
        caster_id=request.source.target_id,
        magic_state=_clear_pool(request.magic_state),
        portal=portal,
        witnesses=witnesses,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *(
                rule_id
                for witness in witnesses
                for rule_id in witness.applied_rule_ids
            ),
        ),
    )


def resolve_catastrophic_death(
    request: MiscastCatastrophicDeathRequest,
) -> MiscastCatastrophicDeathResult:
    _ensure_active(request.caster.state)
    if isinstance(request.caster.state, CharacterInjuryState):
        state: TargetInjuryState = replace(request.caster.state, dead=True)
    else:
        state = replace(
            request.caster.state,
            wounds=request.caster.state.wound_limit,
            defeated=True,
        )
    return MiscastCatastrophicDeathResult(
        request_id=request.id,
        caster_id=request.caster.target_id,
        magic_state=_clear_pool(request.magic_state),
        state=state,
        dead=True,
        body_destroyed=True,
        can_be_reanimated=False,
        applied_rule_ids=(request.source.rule_id,),
    )


def _resolve_fascinating_rift_witness(
    request: MiscastFascinatingRiftRequest,
    portal: MiscastFascinatingRiftPortal,
    witness: MiscastFascinatingRiftWitness,
    rng: RandomSource,
    decisions: TestDecisionProvider | None,
) -> MiscastFascinatingRiftWitnessResult:
    application = resolve_effect_application(
        EffectApplicationRequest(
            id=f"{request.id}:{witness.target_id}:source",
            source_rule_id=request.source.rule_id,
            classification=EffectClassification.PSYCHOLOGICAL,
            immunities=witness.effect_immunities,
        )
    )
    if application.blocked:
        return MiscastFascinatingRiftWitnessResult(
            target_id=witness.target_id,
            outcome=MiscastFascinatingRiftWitnessOutcome.IMMUNE,
            source_application=application,
            willpower_test=None,
            compulsion=None,
            applied_rule_ids=application.applied_rule_ids,
        )

    test_request = replace(
        witness.willpower_test,
        dice_modifiers=(
            *witness.willpower_test.dice_modifiers,
            DiceModifier(request.source.rule_id, -1),
        ),
    )
    test = resolve_test(test_request, rng, decisions=decisions)
    if test.successes:
        return MiscastFascinatingRiftWitnessResult(
            target_id=witness.target_id,
            outcome=MiscastFascinatingRiftWitnessOutcome.RESISTED,
            source_application=application,
            willpower_test=test,
            compulsion=None,
            applied_rule_ids=_unique_rule_ids(
                *application.applied_rule_ids,
                *test.trace.applied_rule_ids,
            ),
        )

    compulsion = MiscastFascinatingRiftCompulsionRequest(
        resolution_id=f"{request.id}:{witness.target_id}:compulsion",
        target_id=witness.target_id,
        portal_id=portal.resolution_id,
        rule_id=request.source.rule_id,
    )
    return MiscastFascinatingRiftWitnessResult(
        target_id=witness.target_id,
        outcome=MiscastFascinatingRiftWitnessOutcome.COMPELLED_TO_ENTER,
        source_application=application,
        willpower_test=test,
        compulsion=compulsion,
        applied_rule_ids=_unique_rule_ids(
            *application.applied_rule_ids,
            *test.trace.applied_rule_ids,
        ),
    )


def _resolve_ears_ringing_target(
    request: MiscastEarsRingingRequest,
    target: MiscastEffectTarget,
) -> MiscastEarsRingingTargetResult:
    _ensure_active(target.state)
    if target.policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }:
        assert isinstance(target.state, CharacterInjuryState)
        wound = resolve_fixed_character_wound(
            FixedCharacterWoundRequest(
                id=f"{request.id}:{target.target_id}:wound",
                state=target.state,
                entry_id=WoundEntryId.EARS_RINGING,
                table_total=11,
                source_rule_id=request.source.rule_id,
                subject_type=_character_type(target.policy),
            )
        )
        effect = resolve_wound_effect(wound.effect_request, wound.state)
        return MiscastEarsRingingTargetResult(
            target_id=target.target_id,
            state=effect.state,
            fixed_character_wound=wound,
            wound_effect=effect,
            profile_wound=None,
            applied_rule_ids=_unique_rule_ids(
                *wound.applied_rule_ids,
                *effect.applied_rule_ids,
            ),
        )

    assert isinstance(target.state, ProfileInjuryState)
    wound = resolve_profile_wound(
        ProfileWoundRequest(
            id=f"{request.id}:{target.target_id}:wound",
            npc_type=_profile_type(target.policy),
            state=target.state,
        )
    )
    return MiscastEarsRingingTargetResult(
        target_id=target.target_id,
        state=wound.state,
        fixed_character_wound=None,
        wound_effect=None,
        profile_wound=wound,
        applied_rule_ids=_unique_rule_ids(
            request.source.rule_id,
            *wound.applied_rule_ids,
        ),
    )


def _resolve_unnatural_wind_target(
    request: MiscastUnnaturalWindRequest,
    target: MiscastEffectTarget,
) -> MiscastUnnaturalWindTargetResult:
    _ensure_active(target.state)
    if target.policy is TargetInjuryPolicy.MONSTROSITY:
        return MiscastUnnaturalWindTargetResult(
            target_id=target.target_id,
            state=target.state,
            excluded_as_monstrosity=True,
            condition_application=None,
            applied_rule_ids=(request.source.rule_id,),
        )

    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:{target.target_id}:prone",
            state=target.state.conditions,
            condition=Condition.PRONE,
            source_rule_id=request.source.rule_id,
        )
    )
    return MiscastUnnaturalWindTargetResult(
        target_id=target.target_id,
        state=replace(target.state, conditions=application.state),
        excluded_as_monstrosity=False,
        condition_application=application,
        applied_rule_ids=application.applied_rule_ids,
    )


def _resolve_hideous_stench_target(
    request: MiscastHideousStenchRequest,
    target: MiscastHideousStenchTarget,
    decisions: MiscastHideousStenchDecisionProvider | None,
) -> MiscastHideousStenchTargetResult:
    choices = (
        (
            MiscastHideousStenchChoice.GIVE_GROUND,
            MiscastHideousStenchChoice.SUFFER_NEXT_TEST_PENALTY,
        )
        if target.can_give_ground
        else (MiscastHideousStenchChoice.SUFFER_NEXT_TEST_PENALTY,)
    )
    selected = _choose_hideous_stench_response(
        request,
        target,
        choices,
        decisions,
    )
    if selected is MiscastHideousStenchChoice.GIVE_GROUND:
        follow_ups = (
            GiveGroundRequest(
                resolution_id=(
                    f"{request.id}:{target.target_id}:give-ground"
                ),
                rule_id=request.source.rule_id,
            ),
        )
        outcome = MiscastHideousStenchOutcome.GIVE_GROUND_REQUESTED
    else:
        follow_ups = (
            MiscastNextTestPenaltyRequest(
                resolution_id=(
                    f"{request.id}:{target.target_id}:next-test-penalty"
                ),
                target_id=target.target_id,
                rule_id=request.source.rule_id,
            ),
        )
        outcome = MiscastHideousStenchOutcome.NEXT_TEST_PENALTY_APPLIED
    return MiscastHideousStenchTargetResult(
        target_id=target.target_id,
        outcome=outcome,
        decision_owner=(
            DecisionOwner.TARGET if len(choices) > 1 else None
        ),
        allowed_choices=choices,
        selected_choice=selected,
        follow_ups=follow_ups,
        applied_rule_ids=(request.source.rule_id,),
    )


def _choose_hideous_stench_response(
    request: MiscastHideousStenchRequest,
    target: MiscastHideousStenchTarget,
    choices: tuple[MiscastHideousStenchChoice, ...],
    decisions: MiscastHideousStenchDecisionProvider | None,
) -> MiscastHideousStenchChoice:
    if len(choices) == 1:
        return choices[0]
    if decisions is None:
        raise MissingMiscastHideousStenchDecisionError(
            "Hideous Stench requires an explicit target decision"
        )
    selected = decisions.choose_hideous_stench_response(
        request=request,
        target=target,
        owner=DecisionOwner.TARGET,
        choices=choices,
    )
    if (
        not isinstance(selected, MiscastHideousStenchChoice)
        or selected not in choices
    ):
        raise InvalidMiscastHideousStenchDecisionError(
            "Hideous Stench decision must be one of the available choices"
        )
    return selected


def _character_type(policy: TargetInjuryPolicy) -> CharacterWoundType:
    return {
        TargetInjuryPolicy.PLAYER: CharacterWoundType.PLAYER,
        TargetInjuryPolicy.CHAMPION: CharacterWoundType.CHAMPION,
    }[policy]


def _profile_type(policy: TargetInjuryPolicy) -> ProfileNpcType:
    return {
        TargetInjuryPolicy.MINION: ProfileNpcType.MINION,
        TargetInjuryPolicy.BRUTE: ProfileNpcType.BRUTE,
        TargetInjuryPolicy.MONSTROSITY: ProfileNpcType.MONSTROSITY,
    }[policy]


def _ensure_active(state: TargetInjuryState) -> None:
    if isinstance(state, CharacterInjuryState) and state.dead:
        raise ValueError("a dead caster or target cannot resolve a Miscast")
    if isinstance(state, ProfileInjuryState) and state.defeated:
        raise ValueError("a defeated caster or target cannot resolve a Miscast")


def _clear_pool(state: WizardMagicState) -> WizardMagicState:
    return replace(state, miscast_dice=0)


def _unique_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))
