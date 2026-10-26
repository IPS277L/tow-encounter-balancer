"""Authored inputs for the first ADR-0038 profiling baseline.

PG1.4 Rules / Combat p112, Battlefield and Actions pp114–119, Broken p122,
Magic / Casting and Miscasts pp156–157, Curse of Cowardly Flight p162;
GM1.1 Allies and Antagonists / Minions and Champions pp91–92.

These numeric profiles and explicit GM facts are experimental inputs, not named
book NPCs. Scene facts are supplied rather than inferred from graph adjacency.
The missing-departure case calibrates a technical stop, not combat difficulty.
"""
from dataclasses import replace

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.cowardly_flight_casting_models import CastingCasterDefinition, CowardlyFlightCastingPolicy
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import COWARDLY_FLIGHT_SPELL_DEFINITION, WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import NpcMagicActorPolicy, NpcMagicScenario, NpcMagicScenarioFacts
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind, NpcMagicGiveGroundPlan,
    NpcMagicPairRange, NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey, NpcMagicZoneRange,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcCastingWizardState, NpcRosterCastingState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


CASES = ('curse-routes', 'champion-pressure', 'missing-departure')


def benchmark_request(case: str, *, trials: int, master_seed: int,
                      round_budget: int) -> NpcMagicSimulationRequest:
    """Build one fresh, fully admitted authored scenario; execute no RNG or trial."""
    if not isinstance(case, str):
        raise TypeError('benchmark case must be a string')
    if case not in CASES:
        raise ValueError(f'unknown magic benchmark case: {case}')
    provenance = 'benchmark:ADR-0038:authored'
    shot = NpcAttackProfile('shot', provenance, Skill.SHOOTING, InlineProfile(3, 3), DamageProfile(3),
        RangedWeaponRange.SHORT, RangedWeaponRange.LONG, RangedWeaponHands.TWO_HANDED)
    protection = (NpcProtectionProfile(provenance, Skill.ATHLETICS, InlineProfile(3, 3)),)
    wizard = NpcDefinition('authored:wizard', provenance, TargetInjuryPolicy.CHAMPION, None,
        ResilienceProfile(4), (), protection)
    minion = NpcDefinition('authored:archer', provenance, TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3), (shot,), protection)
    players, opposition = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor_id, definition.id, side,
        CharacterInjuryState() if actor_id == 'wizard' else ProfileInjuryState(0, 1),
        () if actor_id == 'wizard' else ('shot',), definition.resilience, actor_id != 'wizard', False,
    )) for actor_id, definition, side in (
        ('wizard', wizard, players), ('ally', minion, players), ('enemy', minion, opposition))))
    combat = CombatRoundState(1, roster.turn_participants)
    graph = ZoneGraph(('arena', 'shelter', 'boundary'),
        (ZoneConnection('arena', 'shelter'), ZoneConnection('shelter', 'boundary')))
    # Independent spatial order exercises the complete archived placement keys.
    spatial = SpatialBattleState(graph, tuple(SpatialEntityPlacement(actor_id,
        roster.participant(actor_id).state.side.value, 'arena') for actor_id in ('enemy', 'wizard', 'ally')))
    state = NpcRosterCastingState(roster, NpcCastingWizardState('wizard', CastingCasterDefinition(
        'authored:caster', provenance, 2, InlineProfile(3, 3)), WizardMagicState()), combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState('benchmark:day', 'wizard')))
    enemy_targets = ('ally', 'wizard') if case == 'champion-pressure' else ('wizard', 'ally')
    actors = (
        NpcMagicActorPolicy('wizard', InlineProfile(3, 3), MovementSpeed.NORMAL, (), (), None,
            CowardlyFlightCastingPolicy.CAST_WHEN_READY, graph.zone_ids),
        NpcMagicActorPolicy('ally', InlineProfile(3, 3), MovementSpeed.NORMAL, ('enemy',),
            (MinionDefeatDecision('ally', 'enemy', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
        NpcMagicActorPolicy('enemy', InlineProfile(3, 3), MovementSpeed.NORMAL, enemy_targets,
            (MinionDefeatDecision('enemy', 'ally', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
    )
    route = NpcMagicRouteFacts((), False, False)
    frames = []
    # Distances and directed ordinary-Attack departure flags are authored facts.
    # A connected edge alone does not establish any of these approvals/routes.
    for live_ids in (('wizard', 'ally', 'enemy'), ('wizard', 'enemy')):
        for zone, distance, destination, can_leave in (
            ('arena', RangedWeaponRange.SHORT, 'shelter', (True, True, True)),
            ('shelter', RangedWeaponRange.MEDIUM, 'boundary', (False, False, True)),
            ('boundary', RangedWeaponRange.LONG, None, (False, False, False)),
        ):
            positions = tuple(replace(p, zone_id=zone) if p.entity_id == 'enemy' else p for p in spatial.placements)
            broken = (() if zone == 'arena' else (NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER,
                (), None, None, None, True),))
            frames.append(NpcMagicSceneFrame(NpcMagicSceneKey(positions, live_ids),
                tuple(NpcMagicPairRange(actor_id, 'enemy', distance, False, False)
                      for actor_id in ('wizard', 'ally') if actor_id in live_ids),
                (NpcMagicZoneRange('arena', RangedWeaponRange.SHORT),
                 NpcMagicZoneRange('shelter', RangedWeaponRange.MEDIUM),
                 NpcMagicZoneRange('boundary', RangedWeaponRange.LONG)),
                (NpcMagicGiveGroundPlan('enemy', destination is not None, destination,
                    route if destination else None, destination is None),), broken,
                tuple(NpcMagicAttackDeparture(actor.actor_id, flag)
                      for actor, flag in zip(actors, can_leave) if actor.actor_id in live_ids)))
    facts = NpcMagicScenarioFacts(
        authored_wizard_profile=True, targets_aware=True, clear_line_of_sight=True,
        all_combatants_included=True, unmounted_combatants_only=True, no_additional_rules=True,
        no_other_test_modifiers=True, no_cover_or_concealment=True, no_terrain_or_obstacles=True,
        no_external_scene_changes=True, no_external_condition_sources=True, ammunition_sufficient=True,
        requires_reload_action=False, knows_battle_magic=True, spell_memorised=True, no_bulky_items=True,
        no_casting_opposition=True, no_mixing_winds=True, no_potency_modifiers=True, no_effect_immunities=True,
    )
    order = ('wizard', 'ally', 'enemy')
    if case == 'missing-departure':
        order = ('ally', 'wizard', 'enemy')
        frames = [replace(frames[0], attack_departures=())]
    scenario = NpcMagicScenario(f'benchmark:magic:{case}', state, facts, order, actors, tuple(frames),
        players, NpcDefeatObjective(('enemy',)), round_budget,
        StaggerChoice.SUFFER_WOUND, COWARDLY_FLIGHT_SPELL_DEFINITION)
    return NpcMagicSimulationRequest(scenario, master_seed, trials)
