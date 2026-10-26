"""Real Casting/Wound transitions keep the attached Minion ledger in sync."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario import scenario, PLAYERS, OPPOSITION
from tests.unit.test_m8_npc_roster_minion_attack import begin, changed_roster, parts, request
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_broken_run_models import NpcBrokenRunRequest
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatActionKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack, apply_npc_roster_minion_attack_result
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
from towr.rules.spatial_resolution import resolve_give_ground


def cast_request(state, identifier='cast'):
    # Authored clear arena with one adjacent legal escape; no extra modifiers.
    return prepare_npc_roster_casting(request_id=identifier, state=state, selected_zone_id='arena',
        targets=(NpcRosterCastingTargetContext('enemy', InlineProfile(3, 3), True),),
        facts=CowardlyFlightCastingFacts(True, True, True, True, True, True, True, True, True, True, True, True),
        policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY)


def cast(state, dice, identifier='cast'):
    source = cast_request(state, identifier)
    result = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, SequenceRandom(dice)))
    return apply_npc_roster_casting_result(state, result)


def end(state, actor, drained=False):
    sources = (WoundConditionSourceSnapshot(Condition.DRAINED, False),) if drained else ()
    return apply_npc_wound_turn_end_result(state, end_npc_wound_turn(
        NpcWoundTurnEndRequest('end:' + actor, state, actor, sources)))


def wounded_owner(row=6):
    source = begin(scenario(wizard_side=OPPOSITION).initial_runtime_state, 'enemy')
    protected, execution = parts(source, 'enemy', 'wizard', 'incoming')
    bound = NpcRosterChampionAttackRequest(source, NpcChampionAttackRequest(source.champion_attack, protected, execution))
    result = NpcRosterChampionAttackResult(bound, execute_npc_champion_attack(bound.attack,
        SequenceRandom((1, 2, 3, 10, 10, 10, row))))
    return apply_npc_roster_champion_attack_result(source, result)


class MinionHandoffIntegrationTests(unittest.TestCase):
    def test_real_wait_cast_then_minion_defeat_preserves_active_cast_without_skipped_die(self):
        source = begin(scenario().initial_runtime_state, 'wizard', CombatActionKind.IMPROVISE)
        current = cast(source, (1, 10, 10), 'cast:wait')
        self.assertEqual(current.minion_attack.roster, current.roster)
        self.assertEqual(current.wizard.magic_state.casting_successes, 1)
        current = begin(end(current, 'wizard'), 'ally')
        result = execute_npc_roster_minion_attack(request(current), SequenceRandom((1, 2, 3, 10, 10, 10)))
        final = apply_npc_roster_minion_attack_result(current, result)
        self.assertIs(final.wizard, current.wizard)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 0)
        self.assertEqual(final.consumed_execution_ids, ('cast:wait', 'minion:attack'))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('minion:attack',))
        self.assertIs(final.pending_minion_attack, result.attack)

    def test_real_curse_movement_and_broken_target_then_minion_attack(self):
        source = begin(scenario(blocker=True).initial_runtime_state, 'wizard', CombatActionKind.IMPROVISE)
        pending = cast(source, (1, 2, 3))
        self.assertEqual(pending.minion_attack.roster, pending.roster)
        spell = pending.pending_movement; movement_request, = spell.pending_movements
        movement = resolve_give_ground(GiveGroundResolutionRequest(movement_request.request, spell.spatial_state,
            'enemy', 'middle', spell.source.targets[0].injury.conditions, away_from_entity_id='wizard'))
        completion = NpcRosterCastingCompletionRequest(pending, CowardlyFlightCastingCompletionRequest(spell,
            (complete_cowardly_flight_movement(movement_request, movement),), movement.state))
        completed = NpcRosterCastingCompletionResult(completion,
            complete_cowardly_flight_casting(completion.completion, SequenceRandom((10, 10, 10))))
        current = apply_npc_roster_casting_completion(pending, completed)
        self.assertEqual(current.minion_attack.roster, current.roster)
        self.assertTrue(current.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))
        current = begin(end(current, 'wizard'), 'ally')
        protected, execution = parts(current, 'ally', 'enemy', target_range=Range.MEDIUM)
        from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
        bound = NpcRosterMinionAttackRequest(current, NpcRosterAttackExecutionRequest(current.minion_attack, protected, execution))
        result = execute_npc_roster_minion_attack(bound, SequenceRandom((1, 2, 3, 10, 10, 10)))
        final = apply_npc_roster_minion_attack_result(current, result)
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('enemy',))
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertTrue(final.roster.participant('enemy').state.injury.defeated)
        self.assertIs(final.pending_minion_attack, result.attack)
        self.assertNotIn('enemy', {p.entity_id for p in final.casting_spatial_state.placements})
        self.assertEqual(final.casting_spatial_state.gave_ground_entity_ids, ())
        self.assertEqual(final.consumed_execution_ids, ('cast', 'minion:attack'))

    def test_champion_wound_minion_miss_cast_and_expiry_preserve_both_ledgers(self):
        wounded = wounded_owner()
        self.assertEqual(wounded.minion_attack.roster, wounded.roster)
        current = begin(end(wounded, 'enemy'), 'ally')
        attack = execute_npc_roster_minion_attack(request(current), SequenceRandom((10,) * 6))
        current = apply_npc_roster_minion_attack_result(current, attack)
        self.assertEqual(current.wound_expiries, wounded.wound_expiries)
        self.assertEqual(current.champion_attack.daily_wounds, wounded.champion_attack.daily_wounds)
        current = begin(end(current, 'ally'), 'wizard', CombatActionKind.IMPROVISE)
        current = cast(current, (10, 10, 10), 'cast:wounded')
        final = end(current, 'wizard', drained=True)
        self.assertEqual(final.minion_attack.roster, final.roster)
        injury = final.roster.participant('wizard').state.injury
        self.assertFalse(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(injury.wounds, wounded.roster.participant('wizard').state.injury.wounds)
        self.assertEqual(final.champion_attack.daily_wounds, wounded.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, wounded.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.champion_attack.consumed_execution_ids, ('incoming',))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('minion:attack',))
        self.assertEqual(final.consumed_execution_ids, ('incoming', 'minion:attack', 'cast:wounded'))

    def test_broken_recover_updates_child_roster_for_success_and_failure(self):
        for dice, remains in (((1, 2, 3), False), ((10, 10, 10), True)):
            owner = changed_roster(scenario().initial_runtime_state, lambda p: replace(p, state=replace(p.state,
                injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(Condition.BROKEN))))
                if p.state.actor_id == 'wizard' else p)
            owner = begin(owner, 'wizard', CombatActionKind.RECOVER)
            movement = FreeMovementRequest('broken:free-move', owner.round_state, owner.spatial_state, 'wizard',
                MovementSpeed.NORMAL, owner.roster.participant('wizard').state.injury.conditions, ('middle',))
            result = execute_npc_broken_recover(NpcBrokenRecoverRequest('broken', owner, 'wizard', InlineProfile(3, 3),
                movement, True, True), SequenceRandom(dice))
            final = result.state
            self.assertEqual(final.minion_attack.roster, final.roster)
            self.assertEqual(final.roster.participant('wizard').state.injury.conditions.has(Condition.BROKEN), remains)
            self.assertEqual(final.minion_attack.consumed_execution_ids, ())

    def test_broken_run_preserves_child_and_interruption_pending_blocks_attack(self):
        owner = changed_roster(scenario(blocker=True).initial_runtime_state, lambda p: replace(p, state=replace(p.state,
            injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(Condition.BROKEN))))
            if p.state.actor_id == 'wizard' else p)
        owner = replace(owner, wizard=replace(owner.wizard, magic_state=WizardMagicState(2, 1, 'lore:battle-magic', 1)))
        owner = begin(owner, 'wizard', CombatActionKind.MANOEUVRE)
        movement = FreeMovementRequest('broken-run:free-move', owner.round_state, owner.spatial_state, 'wizard',
            MovementSpeed.NORMAL, owner.roster.participant('wizard').state.injury.conditions, ('middle',))
        final = execute_npc_broken_run(NpcBrokenRunRequest('broken-run', owner, 'wizard', movement,
            'shelter', (), False, False, True)).state
        self.assertIs(final.minion_attack, owner.minion_attack)
        self.assertIsNotNone(final.pending_interruption)
        with self.assertRaisesRegex(ValueError, 'mandatory pending'):
            replace(request(), state=final)

    def test_other_mandatory_pending_blocks_minion_dispatch_and_cannot_coexist(self):
        normal = request()
        caster = begin(scenario().initial_runtime_state, 'wizard', CombatActionKind.IMPROVISE)
        states = (cast(caster, (9, 9, 9)), cast(caster, (1, 2, 3)), wounded_owner(4))
        defeated = execute_npc_roster_minion_attack(normal, SequenceRandom((1, 2, 3, 10, 10, 10))).state
        for pending in states:
            with self.assertRaisesRegex(ValueError, 'mandatory pending'):
                replace(normal, state=pending)
            for name in ('pending_miscast', 'pending_movement'):
                value = getattr(pending, name)
                if value is not None:
                    with self.assertRaisesRegex(ValueError, 'cannot coexist'):
                        replace(defeated, **{name: value})


if __name__ == '__main__':
    unittest.main()
