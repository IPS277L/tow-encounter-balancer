"""Full fresh magic scenario mapping shared by simulation and future balance.

This module neither supplies scene facts nor executes actions. Admission remains
in the existing typed scenario/scene constructors (ADR-0037/0043).
"""
from dataclasses import asdict
from functools import partial

from towr.adapters._json_common import build_value
from towr.adapters.magic_json_errors import MagicInputError, MagicSimulationInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.cowardly_flight_casting_models import CastingCasterDefinition, CowardlyFlightCastingPolicy
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import FormalSpellDefinition, SpellDuration, SpellRange, SpellTargetKind, WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import (
    NpcMagicActorPolicy, NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy,
    NpcMagicScenario, NpcMagicScenarioFacts,
)
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind,
    NpcMagicGiveGroundPlan, NpcMagicPairRange, NpcMagicRouteFacts,
    NpcMagicSceneFrame, NpcMagicSceneKey, NpcMagicZoneRange,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcCastingWizardState, NpcRosterCastingState
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


def parse_facts(data: dict) -> NpcMagicScenarioFacts:
    return NpcMagicScenarioFacts(**data)


def facts_document(facts: NpcMagicScenarioFacts) -> dict:
    return asdict(facts)


def _parse_route(data: dict | None) -> NpcMagicRouteFacts | None:
    return None if data is None else NpcMagicRouteFacts(
        tuple(data['path_entity_ids']), data['crosses_obstacle'], data['crosses_difficult_terrain'])


def parse_scene_frames(data: list, *, path_prefix: str,
                       error_type: type[MagicInputError]) -> tuple[NpcMagicSceneFrame, ...]:
    """Map every supplied frame, including unreachable and archived snapshots."""
    frames = []
    for index, raw in enumerate(data):
        path = f'{path_prefix}/{index}'
        try:
            frame = NpcMagicSceneFrame(
                NpcMagicSceneKey(tuple(SpatialEntityPlacement(**p) for p in raw['key']['placements']),
                                 tuple(raw['key']['live_actor_ids'])),
                tuple(NpcMagicPairRange(p['first_actor_id'], p['second_actor_id'], Range(p['target_range']),
                    p['first_range_approved_by_gm'], p['second_range_approved_by_gm']) for p in raw['pair_ranges']),
                tuple(NpcMagicZoneRange(p['zone_id'], Range(p['target_range'])) for p in raw['zone_ranges']),
                tuple(NpcMagicGiveGroundPlan(p['actor_id'], p['can_leave_zone'], p['destination_zone_id'],
                    _parse_route(p['route']), p['impossible_confirmed']) for p in raw['give_ground_plans']),
                tuple(NpcMagicBrokenPlan(p['actor_id'], NpcMagicBrokenPlanKind(p['kind']),
                    tuple(p['free_move_zone_ids']), _parse_route(p['free_move_route']), p['run_destination_zone_id'],
                    _parse_route(p['run_route']), p['fastest_route_confirmed']) for p in raw['broken_plans']),
                tuple(NpcMagicAttackDeparture(**p) for p in raw['attack_departures']))
        except (TypeError, ValueError) as error:
            raise error_type(Code.INVALID_INPUT, str(error), path=path) from error
        frames.append(frame)
    return tuple(frames)


def parse_scenario(data: dict, round_budget: int, *, path_prefix: str = '/scenario',
                   error_type: type[MagicInputError] = MagicSimulationInputError,
                   schema_version: str = '1',
                   ) -> tuple[NpcMagicScenario, tuple[str, ...]]:
    """Map a schema-checked scenario directly, without a fabricated envelope."""
    _require_schema_version(schema_version)
    try:
        return _parse_scenario(data, round_budget, path_prefix, error_type, schema_version)
    except MagicInputError as error:
        error.schema_version = schema_version
        raise
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix,
                         schema_version=schema_version) from error


def _require_schema_version(schema_version: str) -> None:
    if type(schema_version) is not str or schema_version not in ('1', '2'):
        raise ValueError('unsupported magic scenario schema version')


def _parse_scenario(data, round_budget, path_prefix, error_type, schema_version):
    build = partial(build_value, error_type)
    definitions = {}
    for index, raw in enumerate(data['definitions']):
        path = f'{path_prefix}/definitions/{index}'
        if raw['id'] in definitions:
            raise error_type(Code.INVALID_INPUT, 'duplicate definition ID', path=path + '/id')
        try:
            definition = NpcDefinition(raw['id'], raw['source_rule_id'], TargetInjuryPolicy(raw['injury_policy']),
                raw['wound_limit'], ResilienceProfile(**raw['resilience']),
                tuple(NpcAttackProfile(a['id'], a['source_rule_id'], Skill(a['skill']),
                    InlineProfile(a['dice'], a['threshold']), DamageProfile(a['damage']),
                    Range(a['range_min']), Range(a['range_max']), Hands(a['hands'])) for a in raw['attacks']),
                tuple(NpcProtectionProfile(p['source_rule_id'], Skill(p['skill']), InlineProfile(p['dice'], p['threshold']))
                      for p in raw['protection']))
        except (TypeError, ValueError) as error:
            raise error_type(Code.INVALID_INPUT, str(error), path=path) from error
        definitions[definition.id] = definition
    wizard_data = data['wizard']
    wizard_id = wizard_data['actor_id']
    participants = []
    for index, raw in enumerate(data['actors']):
        path = f'{path_prefix}/actors/{index}'
        if raw['definition_id'] not in definitions:
            raise error_type(Code.INVALID_INPUT, 'unknown definition ID', path=path + '/definition_id')
        definition = definitions[raw['definition_id']]
        injury = CharacterInjuryState() if raw['id'] == wizard_id else ProfileInjuryState(0, 1)
        participant = build(path, NpcParticipantSnapshot, definition,
            NpcParticipantState(raw['id'], definition.id, CombatSide(raw['side']), injury,
                tuple(a.id for a in definition.attacks), definition.resilience, raw['id'] != wizard_id, False))
        participants.append(participant)
    if set(definitions) != {p.definition.id for p in participants}:
        raise error_type(Code.INVALID_INPUT, 'unused definition', path=f'{path_prefix}/definitions')
    roster = build(f'{path_prefix}/actors', NpcRoster, tuple(participants))
    combat = build(f'{path_prefix}/side_order', CombatRoundState, 1, roster.turn_participants,
                   tuple(CombatSide(s) for s in data['side_order']))
    field = data['battlefield']
    connections = tuple(build(f'{path_prefix}/battlefield/connections/{i}', ZoneConnection, **c)
                        for i, c in enumerate(field['connections']))
    graph = build(f'{path_prefix}/battlefield', ZoneGraph, tuple(field['zone_ids']), connections)
    placements = tuple(build(f'{path_prefix}/placements/{i}', SpatialEntityPlacement, **p)
                       for i, p in enumerate(data['placements']))
    spatial = build(f'{path_prefix}/placements', SpatialBattleState, graph, placements)
    caster_data = wizard_data['caster']
    caster = build(f'{path_prefix}/wizard/caster', CastingCasterDefinition,
        caster_data['id'], caster_data['source_rule_id'], caster_data['wizard_level'],
        InlineProfile(**caster_data['casting_profile']))
    wizard = build(f'{path_prefix}/wizard', NpcCastingWizardState, wizard_id, caster, WizardMagicState())
    champion = build(f'{path_prefix}/wizard/day_id', NpcChampionAttackState, roster, combat,
                     DailyWoundState(wizard_data['day_id'], wizard_id))
    initial = build(path_prefix, NpcRosterCastingState, roster, wizard, combat, spatial, champion_attack=champion)
    policies = []
    for index, raw in enumerate(data['actor_policies']):
        path = f'{path_prefix}/actor_policies/{index}'
        decisions = tuple(build(f'{path}/defeat_decisions/{i}', MinionDefeatDecision,
            d['attacker_id'], d['target_id'], NpcDefeatDisposition(d['disposition']), d['gm_approved'])
            for i, d in enumerate(raw['defeat_decisions']))
        policies.append(build(path, NpcMagicActorPolicy, raw['actor_id'], InlineProfile(**raw['willpower']),
            MovementSpeed(raw['speed']), tuple(raw['target_actor_ids']), decisions, raw['attack_id'],
            None if raw['casting_policy'] is None else CowardlyFlightCastingPolicy(raw['casting_policy']),
            tuple(raw['zone_priorities'])))
    spell = data['spell']
    spell_definition = build(f'{path_prefix}/spell', FormalSpellDefinition,
        spell['rule_id'], spell['lore_id'], spell['casting_value'], SpellTargetKind(spell['target_kind']),
        SpellRange(spell['range']), SpellDuration(spell['duration']))
    continuation = None
    if schema_version == '2' and data['miscast_continuation'] is not None:
        raw = data['miscast_continuation']
        path = f'{path_prefix}/miscast_continuation'
        continuation = build(path, NpcMagicMiscastContinuationPolicy,
            build(f'{path}/choice', NpcRosterMiscastPolicy, raw['choice']),
            build(f'{path}/facts', NpcRosterMiscastFacts, **raw['facts']),
            build(f'{path}/prone_policy', NpcMagicPronePolicy, raw['prone_policy']))
    scenario = build(path_prefix, NpcMagicScenario, data['scenario_id'], initial,
        build(f'{path_prefix}/facts', parse_facts, data['facts']), tuple(data['activation_order']), tuple(policies),
        parse_scene_frames(data['scene_frames'], path_prefix=f'{path_prefix}/scene_frames', error_type=error_type),
        CombatSide(data['perspective_side']), NpcDefeatObjective(tuple(data['objective_target_ids'])),
        round_budget, StaggerChoice(data['repeated_stagger_choice']), spell_definition,
        miscast_continuation=continuation)
    return scenario, tuple(definitions)


def _profile_document(profile: InlineProfile) -> dict:
    return {'dice': profile.dice, 'threshold': profile.threshold}


def _route_document(route: NpcMagicRouteFacts | None) -> dict | None:
    return None if route is None else {'path_entity_ids': list(route.path_entity_ids),
        'crosses_obstacle': route.crosses_obstacle, 'crosses_difficult_terrain': route.crosses_difficult_terrain}


def scene_frames_document(frames: tuple[NpcMagicSceneFrame, ...]) -> list[dict]:
    return [{'key': {'placements': [asdict(p) for p in f.key.placements], 'live_actor_ids': list(f.key.live_actor_ids)},
        'pair_ranges': [dict(asdict(p), target_range=p.target_range.value) for p in f.pair_ranges],
        'zone_ranges': [dict(asdict(p), target_range=p.target_range.value) for p in f.zone_ranges],
        'give_ground_plans': [dict(asdict(p), route=_route_document(p.route)) for p in f.give_ground_plans],
        'broken_plans': [dict(asdict(p), kind=p.kind.value, free_move_zone_ids=list(p.free_move_zone_ids),
            free_move_route=_route_document(p.free_move_route), run_route=_route_document(p.run_route))
            for p in f.broken_plans], 'attack_departures': [asdict(p) for p in f.attack_departures]} for f in frames]


def scenario_document(scenario: NpcMagicScenario, definition_order: tuple[str, ...], *,
                      schema_version: str = '1') -> dict:
    """Project all wire fields; the boundary encoder reconstructs the full source."""
    _require_schema_version(schema_version)
    if schema_version == '1' and scenario.miscast_continuation is not None:
        raise ValueError('Miscast continuation opt-in cannot be represented losslessly by magic JSON v1')
    state = scenario.initial
    definitions = {p.definition.id: p.definition for p in state.roster.participants}
    wizard, caster = state.wizard, state.wizard.caster
    document = {'scenario_id': scenario.id,
        'definitions': [{'id': d.id, 'source_rule_id': d.source_rule_id, 'injury_policy': d.injury_policy.value,
            'wound_limit': d.wound_limit, 'resilience': {'toughness': d.resilience.toughness, 'bonus': d.resilience.bonus},
            'attacks': [{'id': a.id, 'source_rule_id': a.source_rule_id, 'skill': a.skill.value,
                **_profile_document(a.test_profile), 'damage': a.damage.base, 'range_min': a.range_min.value,
                'range_max': a.range_max.value, 'hands': a.hands.value} for a in d.attacks],
            'protection': [{'source_rule_id': p.source_rule_id, 'skill': p.skill.value,
                **_profile_document(p.test_profile)} for p in d.protection]}
            for d in (definitions[identifier] for identifier in definition_order)],
        'actors': [{'id': p.state.actor_id, 'definition_id': p.definition.id, 'side': p.state.side.value}
            for p in state.roster.participants],
        'battlefield': {'zone_ids': list(state.spatial_state.graph.zone_ids),
            'connections': [asdict(c) for c in state.spatial_state.graph.connections]},
        'placements': [asdict(p) for p in state.spatial_state.placements],
        'side_order': [side.value for side in state.round_state.side_order],
        'activation_order': list(scenario.activation_order), 'perspective_side': scenario.perspective_side.value,
        'objective_target_ids': list(scenario.objective.target_actor_ids), 'facts': facts_document(scenario.facts),
        'wizard': {'actor_id': wizard.actor_id, 'caster': {'id': caster.id, 'source_rule_id': caster.source_rule_id,
            'wizard_level': caster.wizard_level, 'casting_profile': _profile_document(caster.casting_profile)},
            'day_id': state.champion_attack.daily_wounds.day_id},
        'spell': {'rule_id': scenario.spell.rule_id, 'lore_id': scenario.spell.lore_id,
            'casting_value': scenario.spell.casting_value, 'target_kind': scenario.spell.target_kind.value,
            'range': scenario.spell.range.value, 'duration': scenario.spell.duration.value},
        'actor_policies': [{'actor_id': p.actor_id, 'willpower': _profile_document(p.willpower_profile),
            'speed': p.speed.value, 'target_actor_ids': list(p.target_actor_ids),
            'defeat_decisions': [dict(asdict(d), disposition=d.disposition.value) for d in p.defeat_decisions],
            'attack_id': p.attack_id, 'casting_policy': p.casting_policy.value if p.casting_policy else None,
            'zone_priorities': list(p.zone_priorities)} for p in scenario.actors],
        'scene_frames': scene_frames_document(scenario.scene_frames),
        'repeated_stagger_choice': scenario.repeated_stagger_choice.value}
    if schema_version == '2':
        policy = scenario.miscast_continuation
        document['miscast_continuation'] = None if policy is None else {
            'choice': policy.choice.value, 'facts': asdict(policy.facts),
            'prone_policy': policy.prone_policy.value}
    return document
