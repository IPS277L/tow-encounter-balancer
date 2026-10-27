"""Finite ADR-0043 mapping probe, not a production parser/encoder or Schema.

Keep magic_scenario.py, magic_simulation.py and magic_balance.py beside this file.
Only authored fixtures are mapped. --write-results refreshes runtime observations;
no argument reads fixtures without writing. Lexical/version/unknown-field/error
validation is future work; semantic checks below use public constructors.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
from multiprocessing import active_children
from pathlib import Path
from random import getstate
import json
import platform
import sys

from magic_simulation import authored_simulation_scenario
from magic_balance import build_request
from towr import __version__
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.cowardly_flight_casting_models import CastingCasterDefinition, CowardlyFlightCastingPolicy
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import FormalSpellDefinition, SpellTargetKind, SpellRange, SpellDuration, WizardMagicState
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
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, SEED_SCHEME
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation

DIRECTORY = Path(__file__).parent / 'json'
RULESET = 'towr-pg1.4-gmg1.1'


def profile_document(p):
    return {'dice': p.dice, 'threshold': p.threshold}


def route_document(r):
    return None if r is None else {'path_entity_ids': list(r.path_entity_ids),
        'crosses_obstacle': r.crosses_obstacle, 'crosses_difficult_terrain': r.crosses_difficult_terrain}


def frame_document(f):
    # asdict is used only for fixed leaf records containing no omitted state.
    return {'key': {'placements': [asdict(p) for p in f.key.placements], 'live_actor_ids': list(f.key.live_actor_ids)},
        'pair_ranges': [dict(asdict(p), target_range=p.target_range.value) for p in f.pair_ranges],
        'zone_ranges': [dict(asdict(p), target_range=p.target_range.value) for p in f.zone_ranges],
        'give_ground_plans': [dict(asdict(p), route=route_document(p.route)) for p in f.give_ground_plans],
        'broken_plans': [dict(asdict(p), kind=p.kind.value, free_move_zone_ids=list(p.free_move_zone_ids),
            free_move_route=route_document(p.free_move_route), run_route=route_document(p.run_route)) for p in f.broken_plans],
        'attack_departures': [asdict(p) for p in f.attack_departures]}


def scenario_document(s):
    """Inverse for the admitted fresh authored slice, not general serialization."""
    state = s.initial
    definitions = {p.definition.id: p.definition for p in state.roster.participants}
    wizard, caster = state.wizard, state.wizard.caster
    return {'scenario_id': s.id,
        'definitions': [{'id': d.id, 'source_rule_id': d.source_rule_id, 'injury_policy': d.injury_policy.value,
            'wound_limit': d.wound_limit, 'resilience': {'toughness': d.resilience.toughness, 'bonus': d.resilience.bonus},
            'attacks': [{'id': a.id, 'source_rule_id': a.source_rule_id, 'skill': a.skill.value,
                **profile_document(a.test_profile), 'damage': a.damage.base, 'range_min': a.range_min.value,
                'range_max': a.range_max.value, 'hands': a.hands.value} for a in d.attacks],
            'protection': [{'source_rule_id': p.source_rule_id, 'skill': p.skill.value, **profile_document(p.test_profile)}
                for p in d.protection]} for d in definitions.values()],
        'actors': [{'id': p.state.actor_id, 'definition_id': p.definition.id, 'side': p.state.side.value}
            for p in state.roster.participants],
        'battlefield': {'zone_ids': list(state.spatial_state.graph.zone_ids),
            'connections': [asdict(c) for c in state.spatial_state.graph.connections]},
        'placements': [asdict(p) for p in state.spatial_state.placements],
        'side_order': [side.value for side in state.round_state.side_order],
        'activation_order': list(s.activation_order), 'perspective_side': s.perspective_side.value,
        'objective_target_ids': list(s.objective.target_actor_ids), 'facts': asdict(s.facts),
        'wizard': {'actor_id': wizard.actor_id, 'caster': {'id': caster.id, 'source_rule_id': caster.source_rule_id,
            'wizard_level': caster.wizard_level, 'casting_profile': profile_document(caster.casting_profile)},
            'day_id': state.champion_attack.daily_wounds.day_id},
        'spell': {'rule_id': s.spell.rule_id, 'lore_id': s.spell.lore_id, 'casting_value': s.spell.casting_value,
            'target_kind': s.spell.target_kind.value, 'range': s.spell.range.value, 'duration': s.spell.duration.value},
        'scene_frames': [frame_document(f) for f in s.scene_frames],
        'repeated_stagger_choice': s.repeated_stagger_choice.value,
        'actor_policies': [{'actor_id': p.actor_id, 'willpower': profile_document(p.willpower_profile),
            'speed': p.speed.value, 'target_actor_ids': list(p.target_actor_ids),
            'defeat_decisions': [dict(asdict(d), disposition=d.disposition.value) for d in p.defeat_decisions],
            'attack_id': p.attack_id, 'casting_policy': p.casting_policy.value if p.casting_policy else None,
            'zone_priorities': list(p.zone_priorities)} for p in s.actors]}


def map_route(d):
    return None if d is None else NpcMagicRouteFacts(tuple(d['path_entity_ids']), d['crosses_obstacle'], d['crosses_difficult_terrain'])


def map_frames(frames):
    return tuple(NpcMagicSceneFrame(NpcMagicSceneKey(tuple(SpatialEntityPlacement(**p) for p in f['key']['placements']),
        tuple(f['key']['live_actor_ids'])),
        tuple(NpcMagicPairRange(p['first_actor_id'], p['second_actor_id'], Range(p['target_range']),
            p['first_range_approved_by_gm'], p['second_range_approved_by_gm']) for p in f['pair_ranges']),
        tuple(NpcMagicZoneRange(p['zone_id'], Range(p['target_range'])) for p in f['zone_ranges']),
        tuple(NpcMagicGiveGroundPlan(p['actor_id'], p['can_leave_zone'], p['destination_zone_id'], map_route(p['route']),
            p['impossible_confirmed']) for p in f['give_ground_plans']),
        tuple(NpcMagicBrokenPlan(p['actor_id'], NpcMagicBrokenPlanKind(p['kind']), tuple(p['free_move_zone_ids']),
            map_route(p['free_move_route']), p['run_destination_zone_id'], map_route(p['run_route']),
            p['fastest_route_confirmed']) for p in f['broken_plans']),
        tuple(NpcMagicAttackDeparture(**p) for p in f['attack_departures'])) for f in frames)


def map_scenario(d, rounds):
    """Known fixture fields -> public constructors; no strict JSON admission."""
    definitions = {}
    for v in d['definitions']:
        definitions[v['id']] = NpcDefinition(v['id'], v['source_rule_id'], TargetInjuryPolicy(v['injury_policy']),
            v['wound_limit'], ResilienceProfile(**v['resilience']), tuple(NpcAttackProfile(a['id'], a['source_rule_id'],
                Skill(a['skill']), InlineProfile(a['dice'], a['threshold']), DamageProfile(a['damage']),
                Range(a['range_min']), Range(a['range_max']), Hands(a['hands'])) for a in v['attacks']),
            tuple(NpcProtectionProfile(p['source_rule_id'], Skill(p['skill']), InlineProfile(p['dice'], p['threshold']))
                for p in v['protection']))
    wizard_id = d['wizard']['actor_id']
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definitions[a['definition_id']], NpcParticipantState(
        a['id'], a['definition_id'], CombatSide(a['side']),
        CharacterInjuryState() if a['id'] == wizard_id else ProfileInjuryState(0, 1),
        tuple(p.id for p in definitions[a['definition_id']].attacks), definitions[a['definition_id']].resilience,
        a['id'] != wizard_id, False)) for a in d['actors']))
    combat = CombatRoundState(1, roster.turn_participants, tuple(CombatSide(s) for s in d['side_order']))
    battlefield = d['battlefield']
    spatial = SpatialBattleState(ZoneGraph(tuple(battlefield['zone_ids']), tuple(ZoneConnection(**c)
        for c in battlefield['connections'])), tuple(SpatialEntityPlacement(**p) for p in d['placements']))
    c = d['wizard']['caster']
    wizard = NpcCastingWizardState(wizard_id, CastingCasterDefinition(c['id'], c['source_rule_id'], c['wizard_level'],
        InlineProfile(**c['casting_profile'])), WizardMagicState())
    initial = NpcRosterCastingState(roster, wizard, combat, spatial, champion_attack=NpcChampionAttackState(
        roster, combat, DailyWoundState(d['wizard']['day_id'], wizard_id)))
    actors = tuple(NpcMagicActorPolicy(p['actor_id'], InlineProfile(**p['willpower']), MovementSpeed(p['speed']),
        tuple(p['target_actor_ids']), tuple(MinionDefeatDecision(t['attacker_id'], t['target_id'],
            NpcDefeatDisposition(t['disposition']), t['gm_approved']) for t in p['defeat_decisions']), p['attack_id'],
        CowardlyFlightCastingPolicy(p['casting_policy']) if p['casting_policy'] else None, tuple(p['zone_priorities']))
        for p in d['actor_policies'])
    spell = d['spell']
    return NpcMagicScenario(d['scenario_id'], initial, NpcMagicScenarioFacts(**d['facts']), tuple(d['activation_order']),
        actors, map_frames(d['scene_frames']), CombatSide(d['perspective_side']), NpcDefeatObjective(tuple(d['objective_target_ids'])),
        rounds, StaggerChoice(d['repeated_stagger_choice']), FormalSpellDefinition(spell['rule_id'], spell['lore_id'],
            spell['casting_value'], SpellTargetKind(spell['target_kind']), SpellRange(spell['range']), SpellDuration(spell['duration'])))


def fraction_document(f):
    return {'numerator': f.numerator, 'denominator': f.denominator}


def execution_document(options):
    return {'mode': options.mode.value, **({'workers': options.workers, 'batch_size': options.batch_size}
        if options.mode is Mode.PROCESS else {})}


def map_execution(d):
    return Options(Mode(d['mode']), d.get('workers'), d.get('batch_size'))


def simulation_document(request, request_id):
    return {'schema_version': '1', 'kind': 'npc_magic_simulation', 'request_id': request_id, 'ruleset': RULESET,
        'simulation': {'master_seed': str(request.master_seed), 'trials': request.trials,
            'round_budget': request.scenario.max_rounds}, 'execution': {'mode': 'sequential'},
        'scenario': scenario_document(request.scenario)}


def balance_document(source, request_id='wire:magic:balance'):
    return {'schema_version': '1', 'kind': 'npc_magic_balance', 'request_id': request_id, 'ruleset': RULESET,
        'reserve': {'round_budget': source.template_scenario.max_rounds, 'scenario': scenario_document(source.template_scenario)},
        'generation': {'groups': [dict(asdict(g), actor_ids=list(g.actor_ids)) for g in source.groups],
            'facts': asdict(source.facts), 'scene_frames': [frame_document(f) for f in source.scene_frames],
            'candidate_id_prefix': source.candidate_id_prefix, 'max_candidates': source.max_candidates},
        'evaluation': {'master_seed': str(source.master_seed), 'stages': [asdict(s) for s in source.stages],
            'max_total_trials': source.max_total_trials, 'window': {k: fraction_document(getattr(source.window, k))
                for k in ('minimum', 'target', 'maximum')}}, 'execution': {'mode': 'sequential'}}


def map_balance(d):
    r, g, e = d['reserve'], d['generation'], d['evaluation']
    return MagicCandidateGenerationRequest(map_scenario(r['scenario'], r['round_budget']),
        tuple(MagicCompositionGroup(p['group_id'], tuple(p['actor_ids']), p['minimum_count'], p['maximum_count']) for p in g['groups']),
        NpcMagicScenarioFacts(**g['facts']), map_frames(g['scene_frames']), g['candidate_id_prefix'], g['max_candidates'],
        int(e['master_seed']), tuple(MagicBalanceStage(**s) for s in e['stages']), e['max_total_trials'],
        ObjectiveRateWindow(*(Fraction(**e['window'][k]) for k in ('minimum', 'target', 'maximum'))))


def compact_balance_request():
    source = build_request()
    template = replace(source.template_scenario, scene_frames=(source.template_scenario.initial_frame,))
    return replace(source, template_scenario=template, scene_frames=template.scene_frames,
        stages=(MagicBalanceStage(2, 2), MagicBalanceStage(4, 1)), max_total_trials=16)


def summary_document(s):
    return {'trials': s.trials, 'outcome_counts': asdict(s.outcome_counts), 'total_action_count': s.total_action_count,
        'total_started_round_count': s.total_started_round_count, 'total_completed_round_count': s.total_completed_round_count}


def generation_failure_document(bal):
    changed = deepcopy(bal)
    frame = deepcopy(changed['reserve']['scenario']['scene_frames'][0])
    for p in frame['key']['placements']:
        if p['entity_id'] in ('E2', 'E3'): p['zone_id'] = 'boundary'
    for p in frame['pair_ranges']:
        p['target_range'] = 'short' if p['second_actor_id'] == 'E1' else 'long'
    for p in frame['give_ground_plans']:
        if p['actor_id'] in ('E2', 'E3'):
            p.update(can_leave_zone=False, destination_zone_id=None, route=None, impossible_confirmed=True)
    frame['broken_plans'] = [{'actor_id': 'ally', 'kind': 'free_move_recover', 'free_move_zone_ids': ['shelter'],
        'free_move_route': {'path_entity_ids': [], 'crosses_obstacle': False, 'crosses_difficult_terrain': False},
        'run_destination_zone_id': None, 'run_route': None, 'fastest_route_confirmed': True}]
    changed['reserve']['scenario']['scene_frames'].append(frame)
    changed['generation']['scene_frames'] = deepcopy(changed['reserve']['scenario']['scene_frames'])
    return changed


def main():
    if sys.argv[1:] not in ([], ['--write-results']):
        raise SystemExit('usage: json_contract_probe.py [--write-results]')
    sim = json.loads((DIRECTORY / 'magic-simulation-v1.request.json').read_text(encoding='utf-8'))
    bal = json.loads((DIRECTORY / 'magic-balance-v1.request.json').read_text(encoding='utf-8'))
    before, rng_before, children_before = deepcopy((sim, bal)), getstate(), {c.pid for c in active_children()}
    scenario = map_scenario(sim['scenario'], sim['simulation']['round_budget'])
    assert scenario == authored_simulation_scenario() and scenario_document(scenario) == sim['scenario']
    source = map_balance(bal)
    assert source == compact_balance_request() and balance_document(source) == bal
    # External request ID does not supply or modify the domain scenario ID.
    assert sim['request_id'] != scenario.id
    request = NpcMagicSimulationRequest(scenario, int(sim['simulation']['master_seed']), sim['simulation']['trials'])
    assert simulation_document(request, sim['request_id']) == sim
    for options in (map_execution(sim['execution']), Options(Mode.PROCESS, 2, 3)):
        assert map_execution(execution_document(options)) == options
    typed_before = deepcopy((request, source))
    seq = run_npc_magic_simulation(request)
    proc = run_npc_magic_simulation_parallel(request, workers=2, batch_size=3)
    assert seq == proc
    summary = summarize_npc_magic_simulation(seq)
    generated = generate_magic_candidates(source)
    assert generated.source_request is source
    staged = evaluate_magic_candidates_staged(generated.evaluation_request, map_execution(bal['execution']))
    parallel = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
    assert staged == parallel
    negatives = []
    def negative_scenario(edit):
        d = deepcopy(sim['scenario']); edit(d)
        negatives.append(lambda: map_scenario(d, 4))
    negative_scenario(lambda d: d['facts'].update(targets_aware=False))
    negative_scenario(lambda d: d['spell'].update(casting_value=4))
    negative_scenario(lambda d: d['wizard'].update(actor_id='unknown'))
    negative_scenario(lambda d: d['wizard']['caster']['casting_profile'].update(dice=2))
    negative_scenario(lambda d: d['definitions'][1]['attacks'][0].update(skill='melee'))
    negative_scenario(lambda d: d['scene_frames'][0]['pair_ranges'].pop())
    negative_scenario(lambda d: d['scene_frames'][0]['key']['live_actor_ids'].pop())
    negative_scenario(lambda d: d['scene_frames'][-1]['key']['placements'].pop())
    negative_scenario(lambda d: d['actor_policies'][1]['defeat_decisions'][0].update(gm_approved=False))
    for edit in (lambda d: d['evaluation'].update(max_total_trials=15),
                 lambda d: d['generation'].update(max_candidates=3),
                 lambda d: d['generation']['groups'][0]['actor_ids'].append('wizard')):
        d = deepcopy(bal); edit(d)
        negatives.append(lambda d=d: map_balance(d))
    # Two individually valid frames, with only the family order changed.
    d = generation_failure_document(bal); d['generation']['scene_frames'].reverse()
    negatives.append(lambda d=d: map_balance(d))
    for construct in negatives:
        try: construct()
        except (TypeError, ValueError): pass
        else: raise AssertionError('invalid semantic fixture admitted')
    failing = map_balance(generation_failure_document(bal))
    assert failing.candidate_count == 4 and failing.planned_trials == 16
    try:
        generate_magic_candidates(failing)
    except MagicCandidateGenerationError as error:
        assert error.counts == (1, 0) and error.__cause__ is not None
    else: raise AssertionError('invalid projected subset skipped')
    assert (sim, bal) == before and (request, source) == typed_before and getstate() == rng_before
    assert {c.pid for c in active_children()} == children_before
    assert staged.total_trials <= source.planned_trials == 16
    runtime = {'package_version': __version__, 'python_implementation': platform.python_implementation(),
        'python_version': platform.python_version(), 'rng': 'random.Random'}
    simulation_output = {'schema_version': '1', 'kind': 'npc_magic_simulation_result', 'request': sim,
        'seed_scheme': SEED_SCHEME, 'runtime': runtime, 'summary': summary_document(summary)}
    vectors = list(product(*(range(g.minimum_count, g.maximum_count + 1) for g in source.groups)))
    reports = []
    for index, report in enumerate(staged.stage_reports):
        rows = []
        for row in report.candidates:
            a = row.assessment
            rows.append({'candidate_id': row.candidate_id, 'summary': summary_document(a.summary),
                'rates': {k: fraction_document(getattr(a, 'round_limit_rate' if k == 'round_limit_reached' else k + '_rate'))
                    for k in asdict(a.summary.outcome_counts)}, 'status': a.status.value, 'window_match': a.window_match})
        reports.append({'stage_index': index, 'trials_per_candidate': source.stages[index].trials_per_candidate,
            'keep': source.stages[index].keep, 'total_trials': report.total_trials, 'candidates': rows,
            'selected_candidate_ids': list(report.selected_candidate_ids), 'continuation_candidate_ids':
            list(magic_continuation_candidate_ids(report)) if index < len(source.stages)-1 else []})
    balance_output = {'schema_version': '1', 'kind': 'npc_magic_balance_result', 'request': bal,
        'seed_scheme': SEED_SCHEME, 'runtime': runtime, 'candidate_count': source.candidate_count,
        'planned_trials': source.planned_trials, 'total_trials': staged.total_trials,
        'candidates': [{'candidate_id': c.candidate_id, 'counts': list(v)} for c, v in
            zip(generated.evaluation_request.candidates, vectors, strict=True)], 'stage_reports': reports,
        'status': staged.status.value, 'selected_candidate_ids': list(staged.selected_candidate_ids)}
    for name, output in (('magic-simulation', simulation_output), ('magic-balance', balance_output)):
        encoded = json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        assert json.loads(encoded) == output
        if sys.argv[1:]: (DIRECTORY / (name + '-v1.result.json')).write_text(encoded, encoding='utf-8')
    print(f'exact fixture mapping; simulation {summary.trials} trials, balance planned/actual={source.planned_trials}/{staged.total_trials}')
    print(f'full sequential/process results equal; {len(negatives)} semantic rejections + generation failure; sources/global RNG/children unchanged')
    print('contract probe only: no Magic production Schema/parser/encoder/CLI or lexical validation')


if __name__ == '__main__':
    main()
