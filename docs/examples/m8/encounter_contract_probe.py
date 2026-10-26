"""ADR-0037 admission and substrate probe, not an encounter runner.

Authored three-actor fixtures; PG1.4 Rules pp112,114,118-123,190 and
Magic pp156-157,162; GM1.1 Allies and Antagonists pp91-92.
No tests imports, private helpers, future API emulation or automatic tactics.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from random import getstate

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.cowardly_flight_casting_models import (
    BATTLE_MAGIC_LORE_ID, CastingCasterDefinition, CowardlyFlightCastingFacts,
    CowardlyFlightCastingPolicy,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState, WoundConditionSourceSnapshot
from towr.domain.magic_models import COWARDLY_FLIGHT_SPELL_DEFINITION, WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_attack_preparation_models import (
    NpcAttackPreparationRequest, NpcAttackProfile, NpcProtectedAttackPreparationResult,
)
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest, NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import NpcMagicActorPolicy, NpcMagicScenario, NpcMagicScenarioFacts
from towr.domain.npc_magic_scene_models import (
    NpcMagicBrokenPlan, NpcMagicBrokenPlanKind, NpcMagicGiveGroundPlan, NpcMagicPairRange,
    NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey, NpcMagicZoneRange,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest, NpcRosterAttackState
from towr.domain.npc_roster_casting_completion_models import (
    NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult,
)
from towr.domain.npc_roster_casting_models import (
    NpcCastingWizardState, NpcRosterCastingRequest, NpcRosterCastingResult,
    NpcRosterCastingState, NpcRosterCastingTargetContext,
)
from towr.domain.npc_roster_champion_attack_models import (
    NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult,
)
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import GiveGroundResolutionRequest, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnStartRequest, ImproviseKind,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_attack_execution import execute_npc_roster_attack, apply_npc_roster_attack_result
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class ScriptedDice:
    def __init__(self, values: tuple[int, ...]) -> None:
        self.values = values
        self.calls = 0

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (1, 10) and self.calls < len(self.values), 'unexpected RNG call'
        value = self.values[self.calls]
        self.calls += 1
        assert low <= value <= high
        return value

    def exhausted(self) -> None:
        assert self.calls == len(self.values), 'unused scripted dice'


def initial(*, wizard_side: CombatSide = CombatSide.PLAYERS_AND_ALLIES) -> NpcRosterCastingState:
    """All profiles authored; same Zone means Short, explicitly no Close foes.

    The arena has a legal adjacent empty shelter. No armour/shield, reload,
    hidden equipment or special NPC traits; numeric profiles are not a named NPC.
    """
    provenance = 'example:ADR-0037:authored'
    shot = NpcAttackProfile('shot', provenance, Skill.SHOOTING, InlineProfile(3, 3), DamageProfile(3),
                            RangedWeaponRange.SHORT, RangedWeaponRange.LONG, RangedWeaponHands.TWO_HANDED)
    protection = (NpcProtectionProfile(provenance, Skill.ATHLETICS, InlineProfile(3, 3)),)
    wizard = NpcDefinition('authored:wizard', provenance, TargetInjuryPolicy.CHAMPION, None,
                           ResilienceProfile(4), (), protection)
    minion = NpcDefinition('authored:archer', provenance, TargetInjuryPolicy.MINION, 1,
                           ResilienceProfile(3), (shot,), protection)
    opposing_side = next(side for side in CombatSide if side is not wizard_side)
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definition, NpcParticipantState(
        actor, definition.id, side, CharacterInjuryState() if actor == 'wizard' else ProfileInjuryState(0, 1),
        () if actor == 'wizard' else ('shot',), definition.resilience, actor != 'wizard', False,
    )) for actor, definition, side in (
        ('wizard', wizard, wizard_side), ('ally', minion, wizard_side), ('enemy', minion, opposing_side))))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = SpatialBattleState(ZoneGraph(('arena', 'shelter'), (ZoneConnection('arena', 'shelter'),)),
        tuple(SpatialEntityPlacement(p.entity_id, p.side.value, 'arena') for p in roster.turn_participants))
    return NpcRosterCastingState(roster, NpcCastingWizardState(
        'wizard', CastingCasterDefinition('authored:caster', provenance, 2, InlineProfile(3, 3)),
        WizardMagicState()), combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState('probe:day', 'wizard')))


def admitted_scenario() -> NpcMagicScenario:
    """Fresh two-Zone authored scene; no future frame coverage is promised."""
    state = initial()
    normal = MovementSpeed.NORMAL
    willpower = InlineProfile(3, 3)
    knocked_out = NpcDefeatDisposition.KNOCKED_OUT
    actors = (
        NpcMagicActorPolicy('wizard', willpower, normal, (), (), None,
                           CowardlyFlightCastingPolicy.CAST_WHEN_READY, ('arena', 'shelter')),
        NpcMagicActorPolicy('ally', willpower, normal, ('enemy',),
                           (MinionDefeatDecision('ally', 'enemy', knocked_out, True),), 'shot', None, ()),
        NpcMagicActorPolicy('enemy', willpower, normal, ('wizard', 'ally'),
                           (MinionDefeatDecision('enemy', 'ally', knocked_out, True),), 'shot', None, ()),
    )
    route = NpcMagicRouteFacts((), False, False)
    frame = NpcMagicSceneFrame(NpcMagicSceneKey(state.spatial_state.placements, ('wizard', 'ally', 'enemy')),
        (NpcMagicPairRange('wizard', 'enemy', RangedWeaponRange.SHORT, False, False),
         NpcMagicPairRange('ally', 'enemy', RangedWeaponRange.SHORT, False, False)),
        (NpcMagicZoneRange('arena', RangedWeaponRange.SHORT), NpcMagicZoneRange('shelter', RangedWeaponRange.MEDIUM)),
        (NpcMagicGiveGroundPlan('enemy', True, 'shelter', route, False),),
        tuple(NpcMagicBrokenPlan(actor.actor_id, NpcMagicBrokenPlanKind.FREE_MOVE_RECOVER,
              ('shelter',), route, None, None, True) for actor in actors))
    facts = NpcMagicScenarioFacts(
        authored_wizard_profile=True, targets_aware=True, clear_line_of_sight=True,
        all_combatants_included=True, unmounted_combatants_only=True, no_additional_rules=True,
        no_other_test_modifiers=True, no_cover_or_concealment=True, no_terrain_or_obstacles=True,
        no_external_scene_changes=True, no_external_condition_sources=True, ammunition_sufficient=True,
        requires_reload_action=False, knows_battle_magic=True, spell_memorised=True, no_bulky_items=True,
        no_casting_opposition=True, no_mixing_winds=True, no_potency_modifiers=True, no_effect_immunities=True,
    )
    return NpcMagicScenario('probe:scenario', state, facts, ('wizard', 'ally', 'enemy'), actors, (frame,),
        CombatSide.PLAYERS_AND_ALLIES, NpcDefeatObjective(('enemy',)), 3, StaggerChoice.SUFFER_WOUND,
        COWARDLY_FLIGHT_SPELL_DEFINITION)


def activation(state: NpcRosterCastingState, actor: str, kind: CombatActionKind) -> NpcRosterCastingState:
    """One explicit start/slot, with the existing scheduler enforcing side order."""
    identifier = f'probe:{state.round_state.round_number}:{actor}'
    combat = start_combat_turn(CombatTurnStartRequest(identifier + ':start', state.round_state, actor)).state
    declaration = (CombatActionDeclaration(kind, improvise_kind=ImproviseKind.SPELL,
        improvise_approach_id=BATTLE_MAGIC_LORE_ID) if kind is CombatActionKind.IMPROVISE
        else CombatActionDeclaration(kind))
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        identifier + ':slot', combat, actor, declaration, ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat))


def attack_parts(
    state: NpcRosterCastingState, target_id: str,
) -> tuple[NpcProtectedAttackPreparationResult, AttackActionExecutionRequest]:
    """Supplied Short/awareness/route facts are only valid in this initial arena."""
    assert all(p.zone_id == 'arena' for p in state.spatial_state.placements)
    actor, target = state.roster.participant('enemy'), state.roster.participant(target_id)
    prepared = prepare_npc_attack(NpcAttackPreparationRequest(
        'probe:prepare', 'probe:attack', 'probe:attacker-test', actor.attack_snapshot('probe:snapshot'),
        'shot', target_id, RangedWeaponRange.SHORT, target.state.current_resilience,
        False, actor.state.injury.conditions.has(Condition.STAGGERED), False))
    protected = prepare_npc_attack_protection(prepared, ProtectionPreparationRequest(
        'probe:protect', target_id, prepared.attack, Skill.SHOOTING, True, False,
        target.state.wields_weapon, target.state.holds_shield, Skill.ATHLETICS,
        target.protection_options('probe:protection-test')))
    execution = AttackActionExecutionRequest('probe:shot', state.round_state, 'enemy', target_id, 1,
        KernelAttackRequest('probe:kernel', target_id, protected.attack, target.definition.injury_policy,
                            target.state.injury, True, False))
    return protected, execution


def incoming(wound_roll: int) -> tuple[NpcRosterCastingState, NpcRosterCastingState, int]:
    state = activation(initial(wizard_side=CombatSide.OPPOSITION), 'enemy', CombatActionKind.ATTACK)
    protected, execution = attack_parts(state, 'wizard')
    source = NpcRosterChampionAttackRequest(state, NpcChampionAttackRequest(state.champion_attack, protected, execution))
    rng = ScriptedDice((1, 2, 3, 10, 10, 10, wound_roll))
    attack = execute_npc_champion_attack(source.attack, rng)
    final = apply_npc_roster_champion_attack_result(state, NpcRosterChampionAttackResult(source, attack))
    rng.exhausted()
    assert state.consumed_execution_ids == () and not state.roster.participant('wizard').state.injury.wounds
    return state, final, rng.calls


def casting(
    state: NpcRosterCastingState, identifier: str, *, can_give_ground: bool,
) -> NpcRosterCastingRequest:
    # All twelve facts are explicit for this authored fixture. No name-to-rules inference.
    facts = CowardlyFlightCastingFacts(
        caster_can_cast=True, knows_battle_magic=True, spell_memorised=True,
        caster_unarmoured=True, no_bulky_items=True, no_casting_opposition=True,
        no_mixing_winds=True, no_other_test_modifiers=True, no_potency_modifiers=True,
        no_effect_immunities=True, all_zone_enemies_included=True, target_zone_within_long_range=True,
    )
    return prepare_npc_roster_casting(request_id=identifier, state=state, selected_zone_id='arena',
        targets=(NpcRosterCastingTargetContext('enemy', InlineProfile(3, 3), can_give_ground),),
        facts=facts, policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY)


def finish_turn(state: NpcRosterCastingState, actor: str, *, drained: bool = False) -> NpcRosterCastingState:
    sources = (WoundConditionSourceSnapshot(Condition.DRAINED, False),) if drained else ()
    source = NpcWoundTurnEndRequest('probe:end:' + actor, state, actor, sources)
    return apply_npc_wound_turn_end_result(state, end_npc_wound_turn(source))


def expect_rejection(call, kind: type[Exception], message: str) -> None:
    try:
        call()
    except kind as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError('expected rejection: ' + message)


def main() -> None:
    global_rng = getstate()
    scenario = admitted_scenario()
    assert scenario.initial_frame.key.placements == scenario.initial.spatial_state.placements
    future_key = NpcMagicSceneKey(tuple(replace(p, zone_id='shelter') if p.entity_id == 'enemy' else p
                                       for p in scenario.initial_frame.key.placements), ('wizard', 'ally', 'enemy'))
    assert scenario.frame_for(future_key) is None
    assert scenario.initial.round_state.active_turn is None and not scenario.initial.consumed_execution_ids
    print('SCENARIO ADMISSION: 3 actors; one initial frame; 0 d10; missing future frame remains explicit')
    original, wounded, calls = incoming(6)
    before = deepcopy(wounded)
    expiry, = wounded.wound_expiries
    assert expiry.deadline_round_number == 1 and expiry.actor_id == 'wizard'
    current = activation(finish_turn(wounded, 'enemy'), 'wizard', CombatActionKind.IMPROVISE)
    cast = casting(current, 'probe:wounded-cast', can_give_ground=True)
    rng = ScriptedDice((10, 10, 10))
    result = NpcRosterCastingResult(cast, execute_cowardly_flight_casting(cast.casting, rng))
    current = apply_npc_roster_casting_result(current, result)
    rng.exhausted()
    assert current.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED)
    final = finish_turn(current, 'wizard', drained=True)
    injury = final.roster.participant('wizard').state.injury
    assert not injury.conditions.has(Condition.DRAINED) and not final.wound_expiries
    assert injury.wounds == before.roster.participant('wizard').state.injury.wounds
    assert final.champion_attack.daily_wounds == wounded.champion_attack.daily_wounds
    assert final.wizard is current.wizard and wounded == before
    expect_rejection(lambda: apply_npc_roster_casting_result(final, result), ValueError, 'already been consumed')
    print(f'WOUND -> CAST -> END: {calls + rng.calls} d10; Drained expires; Wound/daily/magic/history retained')

    _, pending, calls = incoming(4)
    assert pending.champion_attack.pending is not None
    assert pending.champion_attack.pending.pending_follow_ups
    expect_rejection(lambda: finish_turn(pending, 'enemy'), ValueError, 'mandatory pending')
    print(f'WOUND STOP: {calls} d10; full Endurance follow-up retained; no end-turn or terminal outcome')

    # Independent default-order activation. Complete the real movement pending,
    # then end this Wizard turn; no intervening ally/enemy turns are invented.
    owner = activation(scenario.initial, 'wizard', CombatActionKind.IMPROVISE)
    cast = casting(owner, 'probe:curse', can_give_ground=True)
    rng = ScriptedDice((1, 2, 3, 10, 10, 10))
    result = NpcRosterCastingResult(cast, execute_cowardly_flight_casting(cast.casting, rng))
    pending = apply_npc_roster_casting_result(owner, result)
    assert rng.calls == 3 and pending.pending_movement is not None
    expect_rejection(lambda: finish_turn(pending, 'wizard'), ValueError, 'mandatory pending')
    effect = pending.pending_movement
    follow_up, = effect.pending_movements
    target = effect.source.targets[0]
    moved = resolve_give_ground(GiveGroundResolutionRequest(follow_up.request, effect.spatial_state,
        target.actor_id, 'shelter', target.injury.conditions, away_from_entity_id='wizard'))
    movement = complete_cowardly_flight_movement(follow_up, moved)
    completion = NpcRosterCastingCompletionRequest(pending,
        CowardlyFlightCastingCompletionRequest(effect, (movement,), moved.state))
    completed = NpcRosterCastingCompletionResult(completion,
        complete_cowardly_flight_casting(completion.completion, rng))
    current = apply_npc_roster_casting_completion(pending, completed)
    rng.exhausted()
    final = finish_turn(current, 'wizard')
    assert final.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN)
    assert not final.roster.participant('enemy').state.injury.defeated
    assert final.spatial_state.placement_for('enemy').zone_id == 'shelter'
    assert final.consumed_execution_ids == ('probe:curse',)
    assert final.champion_attack.daily_wounds == owner.champion_attack.daily_wounds
    assert final.spatial_state.placements != owner.spatial_state.placements
    assert scenario.frame_for(NpcMagicSceneKey(final.spatial_state.placements, ('wizard', 'ally', 'enemy'))) is None
    expect_rejection(lambda: apply_npc_roster_casting_completion(current, completed), ValueError, 'pending')
    print('CURSE -> GIVE GROUND -> WILLPOWER -> END: 6 d10; one receipt; Broken is not defeat; scene changed')

    cast = casting(owner, 'probe:miscast', can_give_ground=True)
    rng = ScriptedDice((9, 9, 9))
    result = NpcRosterCastingResult(cast, execute_cowardly_flight_casting(cast.casting, rng))
    pending = apply_npc_roster_casting_result(owner, result)
    rng.exhausted()
    assert pending.pending_miscast is not None and pending.wizard.magic_state.miscast_dice == 3
    assert pending.pending_miscast.post_test.decision is None
    expect_rejection(lambda: finish_turn(pending, 'wizard'), ValueError, 'mandatory pending')
    print('MISCAST STOP: 3 d10; full pool/source/receipt retained; no preparation, table or automatic desperate cast')

    state = activation(initial(wizard_side=CombatSide.OPPOSITION), 'enemy', CombatActionKind.ATTACK)
    protected, execution = attack_parts(state, 'ally')
    source = NpcRosterAttackExecutionRequest(NpcRosterAttackState(state.roster), protected, execution)
    before = deepcopy(state)
    rng = ScriptedDice((1, 2, 3, 10, 10, 10))
    attack = execute_npc_roster_attack(source, rng)
    lower = apply_npc_roster_attack_result(source.state, attack)
    rng.exhausted()
    assert lower.roster.participant('ally').state.injury.defeated and attack.pending_follow_ups
    expect_rejection(lambda: apply_npc_roster_attack_result(state, attack), TypeError, 'NpcRosterAttackState')
    assert state == before
    print('MINION HANDOFF GAP: 6 d10; M2 defeat/pending exists; Casting owner unchanged; bound adapter still needed')
    assert original.consumed_execution_ids == () and getstate() == global_rng
    print('32 scripted d10; public API only; sources/global RNG unchanged; no scenario runner or four-outcome claim')


if __name__ == '__main__':
    main()
