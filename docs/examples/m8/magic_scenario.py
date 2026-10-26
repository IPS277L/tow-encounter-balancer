"""Standalone public API example of the audited ADR-0037 encounter boundary.

Numeric profiles and GM facts are authored, not named book NPCs.
PG1.4 Rules pp112,118-119,122,190; Magic pp156-157,162. GM1.1 pp91-92.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from random import getstate

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
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
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcCastingWizardState, NpcRosterCastingState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


@dataclass(slots=True)
class ScriptedDice:
    values: tuple[int, ...]
    calls: int = 0

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (1, 10) and self.calls < len(self.values), 'unexpected RNG draw'
        value = self.values[self.calls]
        self.calls += 1
        assert low <= value <= high
        return value


def authored_scenario(*, wizard_side: CombatSide = CombatSide.PLAYERS_AND_ALLIES) -> NpcMagicScenario:
    """Three fixed actors, explicit frames, ordinary bows and one memorised Curse.

    No armour/shield/reload, hidden actors, additional rules or external causes.
    Same Zone explicitly means Short here. The ordered facts below are authored;
    no range, route or departure availability is discovered from the graph.
    """
    provenance = 'example:ADR-0037:authored'
    shot = NpcAttackProfile('shot', provenance, Skill.SHOOTING, InlineProfile(3, 3), DamageProfile(3),
        Range.SHORT, Range.LONG, RangedWeaponHands.TWO_HANDED)
    protection = (NpcProtectionProfile(provenance, Skill.ATHLETICS, InlineProfile(3, 3)),)
    wizard = NpcDefinition('authored:wizard', provenance, TargetInjuryPolicy.CHAMPION, None,
        ResilienceProfile(4), (), protection)
    minion = NpcDefinition('authored:archer', provenance, TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3), (shot,), protection)
    opposite = next(side for side in CombatSide if side is not wizard_side)
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor, definition.id, side, CharacterInjuryState() if actor == 'wizard' else ProfileInjuryState(0, 1),
        () if actor == 'wizard' else ('shot',), definition.resilience, actor != 'wizard', False,
    )) for actor, definition, side in (
        ('wizard', wizard, wizard_side), ('ally', minion, wizard_side), ('enemy', minion, opposite))))
    combat = CombatRoundState(1, roster.turn_participants)
    graph = ZoneGraph(('arena', 'shelter', 'boundary'),
        (ZoneConnection('arena', 'shelter'), ZoneConnection('shelter', 'boundary')))
    # Spatial order deliberately differs from roster/activation order.
    spatial = SpatialBattleState(graph, tuple(SpatialEntityPlacement(actor,
        roster.participant(actor).state.side.value, 'arena') for actor in ('enemy', 'wizard', 'ally')))
    state = NpcRosterCastingState(roster, NpcCastingWizardState('wizard', CastingCasterDefinition(
        'authored:caster', provenance, 2, InlineProfile(3, 3)), WizardMagicState()), combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState('example:day', 'wizard')))
    actors = (
        NpcMagicActorPolicy('wizard', InlineProfile(3, 3), MovementSpeed.NORMAL, (), (), None,
            CowardlyFlightCastingPolicy.CAST_WHEN_READY, graph.zone_ids),
        NpcMagicActorPolicy('ally', InlineProfile(3, 3), MovementSpeed.NORMAL, ('enemy',),
            (MinionDefeatDecision('ally', 'enemy', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
        NpcMagicActorPolicy('enemy', InlineProfile(3, 3), MovementSpeed.NORMAL, ('wizard', 'ally'),
            (MinionDefeatDecision('enemy', 'ally', NpcDefeatDisposition.KNOCKED_OUT, True),), 'shot', None, ()),
    )
    route = NpcMagicRouteFacts((), False, False)
    frames = []
    for zone, distance, destination, departures in (
        ('arena', Range.SHORT, 'shelter', (True, True, True)),
        ('shelter', Range.MEDIUM, 'boundary', (False, False, True)),
        ('boundary', Range.LONG, None, (False, False, False)),
    ):
        positions = tuple(replace(p, zone_id=zone) if p.entity_id == 'enemy' else p for p in spatial.placements)
        broken = (() if zone == 'arena' else (NpcMagicBrokenPlan('enemy', NpcMagicBrokenPlanKind.SAFE_RECOVER,
            (), None, None, None, True),))
        frames.append(NpcMagicSceneFrame(NpcMagicSceneKey(positions, ('wizard', 'ally', 'enemy')),
            (NpcMagicPairRange('wizard', 'enemy', distance, False, False),
             NpcMagicPairRange('ally', 'enemy', distance, False, False)),
            (NpcMagicZoneRange('arena', Range.SHORT), NpcMagicZoneRange('shelter', Range.MEDIUM),
             NpcMagicZoneRange('boundary', Range.LONG)),
            (NpcMagicGiveGroundPlan('enemy', destination is not None, destination,
                route if destination else None, destination is None),), broken,
            tuple(NpcMagicAttackDeparture(actor.actor_id, can_leave) for actor, can_leave in zip(actors, departures))))
    facts = NpcMagicScenarioFacts(
        authored_wizard_profile=True, targets_aware=True, clear_line_of_sight=True,
        all_combatants_included=True, unmounted_combatants_only=True, no_additional_rules=True,
        no_other_test_modifiers=True, no_cover_or_concealment=True, no_terrain_or_obstacles=True,
        no_external_scene_changes=True, no_external_condition_sources=True, ammunition_sufficient=True,
        requires_reload_action=False, knows_battle_magic=True, spell_memorised=True, no_bulky_items=True,
        no_casting_opposition=True, no_mixing_winds=True, no_potency_modifiers=True, no_effect_immunities=True,
    )
    return NpcMagicScenario('example:magic', state, facts, ('wizard', 'ally', 'enemy'), actors, tuple(frames),
        wizard_side, NpcDefeatObjective(('enemy',)), 3, StaggerChoice.SUFFER_WOUND, COWARDLY_FLIGHT_SPELL_DEFINITION)


def main() -> None:
    global_rng = getstate()
    source = authored_scenario()
    opposite = replace(source, perspective_side=CombatSide.OPPOSITION, objective=NpcDefeatObjective(('wizard', 'ally')))
    missing_frame = replace(source, scene_frames=(source.initial_frame,))
    missing_departure = replace(source, scene_frames=(replace(source.initial_frame, attack_departures=()),))
    wounded = authored_scenario(wizard_side=CombatSide.OPPOSITION)
    cases = (
        ('OBJECTIVE', source, (10, 10, 10, 1, 2, 3, 10, 10, 10), Outcome.OBJECTIVE_ACHIEVED),
        ('PERSPECTIVE', opposite, (10, 10, 10, 1, 2, 3, 10, 10, 10), Outcome.PERSPECTIVE_DEFEATED),
        ('LIMIT', replace(source, max_rounds=2), (10,) * 30, Outcome.ROUND_LIMIT_REACHED),
        ('MISCAST', source, (9, 9, 9), Outcome.UNSUPPORTED_PATH),
        ('CURSE RECOVER', replace(source, max_rounds=1),
            (1, 2, 3, 10, 10, 10) + (10,) * 6 + (1, 2, 3), Outcome.ROUND_LIMIT_REACHED),
        ('WOUND EXPIRY', source,
            (10,) * 9 + (1, 2, 3, 10, 10, 10, 6) + (10,) * 3 + (1, 2, 3, 10, 10, 10), Outcome.OBJECTIVE_ACHIEVED),
        ('WOUND STOP', wounded, (1, 2, 3, 10, 10, 10, 4), Outcome.UNSUPPORTED_PATH),
        ('MISSING FRAME', missing_frame, (1, 2, 3, 10, 10, 10), Outcome.UNSUPPORTED_PATH),
        ('MISSING DEPARTURE', missing_departure, (10,) * 3, Outcome.UNSUPPORTED_PATH),
    )
    for label, scenario, values, outcome in cases:
        before = deepcopy(scenario)
        rng = ScriptedDice(values)
        result = run_npc_magic_scenario(scenario, rng)
        assert rng.calls == len(values) and result.outcome is outcome
        assert result.source is scenario and scenario == before
        current = result.current
        assert current.minion_attack.roster == current.champion_attack.roster == current.roster
        assert current.champion_attack.round_state == current.round_state
        assert len(current.roster.participants) == len(current.spatial_state.placements) == 3
        assert current.round_state.round_number == current.spatial_state.round_number
        if label in ('OBJECTIVE', 'PERSPECTIVE'):
            assert result.executed_actions == 2 and current.pending_minion_attack is None
            assert len(current.minion_attack.acknowledged_defeat_execution_ids) == 1
            assert current.round_state.active_turn is None and result.completed_rounds == 1
        elif label == 'LIMIT':
            assert (result.started_rounds, result.completed_rounds, result.executed_actions) == (2, 2, 6)
        elif label == 'MISCAST':
            assert result.unsupported.reason is Reason.MISCAST_PREPARATION and current.pending_miscast is not None
            assert current.wizard.magic_state.miscast_dice == 3
        elif label == 'CURSE RECOVER':
            enemy = current.roster.participant('enemy').state.injury
            assert not enemy.conditions.has(Condition.BROKEN) and not enemy.defeated
            assert current.spatial_state.placement_for('enemy').zone_id == 'shelter'
            assert current.spatial_state.gave_ground_entity_ids == ('enemy',)
        elif label == 'WOUND EXPIRY':
            wizard = current.roster.participant('wizard').state.injury
            assert not wizard.conditions.has(Condition.DRAINED) and not current.wound_expiries
            assert len(wizard.wounds) == len(current.champion_attack.daily_wounds.receipts) == 1
            assert any(r.expired_attack_ids for r in current.wound_turn_end_receipts)
        elif label == 'WOUND STOP':
            assert result.unsupported.reason is Reason.WOUND_EFFECT and current.champion_attack.pending is not None
            assert len(current.champion_attack.daily_wounds.receipts) == 1
        elif label == 'MISSING FRAME':
            assert result.unsupported.reason is Reason.MISSING_SCENE and current.pending_movement is None
            assert current.spatial_state.placement_for('enemy').zone_id == 'shelter'
        else:
            assert result.unsupported.reason is Reason.MISSING_ROUTE and result.unsupported.missing_actor_ids == ('enemy',)
            assert not current.round_state.active_turn.action_slots[0].executed
        stop = result.unsupported.reason.value if result.unsupported else '-'
        print(f'{label}: {rng.calls} d10; {result.outcome.value}; rounds {result.started_rounds}/{result.completed_rounds}; '
              f'actions {result.executed_actions}; stop {stop}')
    assert getstate() == global_rng
    print('107 scripted d10; public API only; full owners/sources/global RNG preserved; no post-battle recovery')


if __name__ == '__main__':
    main()
