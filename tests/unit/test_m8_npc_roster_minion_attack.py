"""One source-bound ordinary M2 attack; no acknowledgement or battle loop."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest, NpcRosterAttackState
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest, NpcRosterMinionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatTurnStartRequest,
    ImproviseKind, ManoeuvreKind,
)
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack as execute
from towr.rules.npc_roster_minion_attack_resolution import apply_npc_roster_minion_attack_result as apply
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


def changed_roster(state, transform):
    roster = NpcRoster(tuple(transform(p) for p in state.roster.participants))
    return replace(state, roster=roster,
        minion_attack=None if state.minion_attack is None else replace(state.minion_attack, roster=roster),
        champion_attack=None if state.champion_attack is None else replace(state.champion_attack, roster=roster))


def begin(state, actor, kind=CombatActionKind.ATTACK):
    combat = start_combat_turn(CombatTurnStartRequest('start:' + actor, state.round_state, actor)).state
    declaration = (CombatActionDeclaration(kind, improvise_kind=ImproviseKind.SPELL, improvise_approach_id='lore:battle-magic')
                   if kind is CombatActionKind.IMPROVISE else
                   CombatActionDeclaration(kind, manoeuvre=ManoeuvreKind.RUN) if kind is CombatActionKind.MANOEUVRE else
                   CombatActionDeclaration(kind))
    combat = reserve_combat_action_slot(CombatActionSlotRequest('slot:' + actor, combat, actor,
        declaration, ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=combat,
                   champion_attack=None if state.champion_attack is None else replace(state.champion_attack, round_state=combat))


def parts(state, actor, target_id, identifier='minion:attack', *, target_range=Range.SHORT):
    attacker, target = state.roster.participant(actor), state.roster.participant(target_id)
    attack = attacker.definition.attacks[0]
    prepared = prepare_npc_attack(NpcAttackPreparationRequest(identifier + ':prepare', identifier + ':attack',
        identifier + ':attacker-test', attacker.attack_snapshot(identifier + ':snapshot'), attack.id,
        target_id, target_range, target.state.current_resilience, target_range is Range.CLOSE,
        attacker.state.injury.conditions.has(Condition.STAGGERED), False))
    protected = prepare_npc_attack_protection(prepared, ProtectionPreparationRequest(
        identifier + ':protect', target_id, prepared.attack, attack.skill, True,
        target.state.injury.conditions.has(Condition.DEFENCELESS), target.state.wields_weapon, target.state.holds_shield,
        Skill.ATHLETICS, target.protection_options(identifier + ':protection-test')))
    execution = AttackActionExecutionRequest(identifier, state.round_state, actor, target_id, 1,
        KernelAttackRequest(identifier + ':kernel', target_id, protected.attack, target.definition.injury_policy,
                            target.state.injury, True, target_id in state.spatial_state.gave_ground_entity_ids))
    return protected, execution


def request(state=None, *, melee=False, identifier='minion:attack'):
    state = scenario().initial_runtime_state if state is None else state
    if melee:
        def equip(p):
            if p.state.actor_id != 'ally': return p
            profile = replace(p.definition.attacks[0], skill=Skill.MELEE, range_min=Range.CLOSE,
                              range_max=Range.CLOSE, hands=Hands.ONE_HANDED)
            definition = replace(p.definition, id='authored:melee', attacks=(profile,))
            return replace(p, definition=definition, state=replace(p.state, definition_id=definition.id))
        state = changed_roster(state, equip)
    if state.round_state.active_turn is None:
        state = begin(state, 'ally')
    prepared, execution = parts(state, 'ally', 'enemy', identifier,
                                target_range=Range.CLOSE if melee else Range.SHORT)
    return NpcRosterMinionAttackRequest(state, NpcRosterAttackExecutionRequest(state.minion_attack, prepared, execution))


class RosterMinionAttackTests(unittest.TestCase):
    def test_runtime_bootstrap_is_pure_and_does_not_reset_an_admitted_source(self):
        source = scenario(); before = deepcopy(source)
        runtime = source.initial_runtime_state
        self.assertIsNone(source.initial.minion_attack)
        self.assertEqual(runtime.minion_attack, NpcRosterAttackState(source.initial.roster))
        self.assertIs(runtime.roster, source.initial.roster)
        self.assertEqual(runtime.consumed_execution_ids, ())
        self.assertEqual(source, before)
        self.assertEqual(source.initial_runtime_state, runtime)
        with self.assertRaisesRegex(ValueError, 'fresh'):
            replace(source, initial=runtime)

    def test_exactly_one_m2_attack_and_no_rng_or_execution_on_application(self):
        source = request(); before = deepcopy(source); global_rng = random.getstate()
        rng = Mock(wraps=SequenceRandom((1, 2, 3, 10, 10, 10)))
        from towr.rules.npc_roster_attack_execution import execute_npc_roster_attack
        with patch('towr.rules.npc_roster_minion_attack_resolution.execute_npc_roster_attack',
                   wraps=execute_npc_roster_attack) as lower:
            result = execute(source, rng)
            lower.assert_called_once()
        with patch('towr.rules.npc_roster_minion_attack_resolution.execute_npc_roster_attack',
                   side_effect=AssertionError('no repeated attack')):
            final = apply(source.state, result)
            self.assertEqual(final, result.state)
        self.assertEqual(rng.randint.call_count, 6)
        self.assertEqual(source, before)
        self.assertEqual(global_rng, random.getstate())
        self.assertEqual(final.consumed_execution_ids, ('minion:attack',))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('minion:attack',))
        self.assertIs(final.wizard, source.state.wizard)
        self.assertIs(final.spatial_state, source.state.spatial_state)
        self.assertEqual(final.champion_attack.daily_wounds, source.state.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_execution_ids, ())
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)

    def test_defeat_keeps_full_pending_no_acknowledgement_or_exclusion(self):
        source = request(); result = execute(source, SequenceRandom((1, 2, 3, 10, 10, 10)))
        final = apply(source.state, result)
        self.assertTrue(final.roster.participant('enemy').state.injury.defeated)
        self.assertIs(final.pending_minion_attack, result.attack)
        self.assertTrue(final.pending_minion_attack.pending_follow_ups)
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ())
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ())
        self.assertEqual(final.round_state.completed_turn_entity_ids, ())
        self.assertEqual(final.round_state.participants, source.state.round_state.participants)
        self.assertEqual(len(final.roster.participants), 3)

    def test_miss_and_first_stagger_need_no_pending(self):
        for dice, staggered in (((10,) * 6, False), ((1, 10, 10, 1, 10, 10), True)):
            with self.subTest(staggered=staggered):
                final = execute(request(), SequenceRandom(dice)).state
                self.assertIsNone(final.pending_minion_attack)
                self.assertEqual(final.roster.participant('enemy').state.injury.conditions.has(Condition.STAGGERED), staggered)

    def test_close_miss_applies_attacker_stagger_once(self):
        source = request(melee=True)
        final = execute(source, SequenceRandom((10,) * 6)).state
        self.assertTrue(final.roster.participant('ally').state.injury.conditions.has(Condition.STAGGERED))
        self.assertIsNone(final.pending_minion_attack)

    def test_repeated_stagger_retains_give_ground_without_spatial_execution(self):
        state = scenario().initial_runtime_state
        state = changed_roster(state, lambda p: replace(p, state=replace(p.state, injury=replace(p.state.injury,
            conditions=p.state.injury.conditions.with_condition(Condition.STAGGERED)))) if p.state.actor_id == 'enemy' else p)
        source = request(state)
        result = execute(source, SequenceRandom((1, 10, 10, 1, 10, 10)),
                         decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
        self.assertIs(result.state.pending_minion_attack, result.attack)
        self.assertEqual(result.state.spatial_state, source.state.spatial_state)
        self.assertEqual(result.state.minion_attack.consumed_give_ground_execution_ids, ())

    def test_broken_target_is_attackable_but_does_not_lose_broken(self):
        state = changed_roster(scenario().initial_runtime_state, lambda p: replace(p, state=replace(p.state,
            injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(Condition.BROKEN))))
            if p.state.actor_id == 'enemy' else p)
        final = execute(request(state), SequenceRandom((10,) * 6)).state
        self.assertTrue(final.roster.participant('enemy').state.injury.conditions.has(Condition.BROKEN))

    def test_stale_full_magic_spatial_history_and_replay_rejected(self):
        source = request(); result = execute(source, SequenceRandom((10,) * 6))
        for changes in ({'wizard': replace(source.state.wizard, magic_state=WizardMagicState(1))},
                        {'spatial_state': replace(source.state.spatial_state, free_move_used_entity_ids=('wizard',))},
                        {'consumed_execution_ids': ('other:action',)}):
            with self.assertRaisesRegex(ValueError, 'stale source'):
                apply(replace(source.state, **changes), result)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            apply(result.state, result)

    def test_bound_request_rejects_missing_owner_wrong_round_and_global_id_reuse(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'bound owner'):
            replace(source, state=replace(source.state, minion_attack=None))
        with self.assertRaisesRegex(ValueError, 'full current round'):
            replace(source, attack=replace(source.attack, execution=replace(source.attack.execution,
                state=replace(source.state.round_state, completed_turn_entity_ids=('wizard',)))))
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            replace(source, state=replace(source.state, consumed_execution_ids=('minion:attack',)))

    def test_given_ground_usage_cannot_be_reset_in_kernel(self):
        source = request()
        state = replace(source.state, spatial_state=replace(source.state.spatial_state, gave_ground_entity_ids=('enemy',)))
        with self.assertRaisesRegex(ValueError, 'stale Give Ground'):
            replace(source, state=state)

    def test_unexecuted_standard_active_slot_is_required(self):
        source = request()
        for combat in (replace(source.state.round_state, active_turn=None),
                       replace(source.state.round_state, active_turn=replace(
                           source.state.round_state.active_turn, action_slots=()))):
            state = replace(source.state, round_state=combat,
                            champion_attack=replace(source.state.champion_attack, round_state=combat))
            lower = replace(source.attack, execution=replace(source.attack.execution, state=combat))
            with self.assertRaisesRegex(ValueError, 'unexecuted standard Attack'):
                NpcRosterMinionAttackRequest(state, lower)

    def test_unsupported_conditions_rejected_before_attack_rng(self):
        for actor, condition in (('ally', Condition.DRAINED), ('enemy', Condition.DRAINED),
                                 ('enemy', Condition.BLINDED), ('enemy', Condition.ABLAZE)):
            state = changed_roster(scenario().initial_runtime_state, lambda p: replace(p, state=replace(p.state,
                injury=replace(p.state.injury, conditions=p.state.injury.conditions.with_condition(condition))))
                if p.state.actor_id == actor else p)
            with self.subTest(actor=actor, condition=condition), self.assertRaisesRegex(ValueError, 'unsupported actor/target'):
                request(state)

    def test_friendly_attack_rejected_by_magic_handoff(self):
        state = scenario(blocker=True).initial_runtime_state
        # Supplied isolated activation after the Players side completed.
        combat = replace(state.round_state, completed_turn_entity_ids=('wizard', 'ally'))
        state = replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat))
        state = begin(state, 'enemy')
        protected, execution = parts(state, 'enemy', 'blocker', target_range=Range.MEDIUM)
        lower = NpcRosterAttackExecutionRequest(state.minion_attack, protected, execution)
        with self.assertRaisesRegex(ValueError, 'hostile actors'):
            NpcRosterMinionAttackRequest(state, lower)

    def test_foreign_result_and_typed_boundaries(self):
        source = request(); result = execute(source, SequenceRandom((10,) * 6))
        with self.assertRaisesRegex(ValueError, 'complete bound source'):
            replace(result, source=request(identifier='another:attack'))
        for source_value in (None, source.attack):
            with self.assertRaises(TypeError): NpcRosterMinionAttackRequest(source_value, source.attack)
            with self.assertRaises(TypeError): execute(source_value, SequenceRandom(()))
        with self.assertRaises(TypeError): NpcRosterMinionAttackResult(source, None)
        with self.assertRaises(TypeError): apply(source.state, None)
        with self.assertRaises(FrozenInstanceError): source.state = None

    def test_root_binds_owner_roster_histories_and_full_pending(self):
        source = request(); result = execute(source, SequenceRandom((1, 2, 3, 10, 10, 10))); final = result.state
        with self.assertRaisesRegex(ValueError, 'current full roster'):
            replace(final, minion_attack=source.state.minion_attack)
        with self.assertRaisesRegex(ValueError, 'ordered attack history'):
            replace(final, consumed_execution_ids=())
        with self.assertRaisesRegex(ValueError, 'pending Minion'):
            replace(final, minion_attack=None)
        with self.assertRaisesRegex(ValueError, 'pending Minion'):
            replace(final, consumed_execution_ids=(*final.consumed_execution_ids, 'extra'))
        miss = execute(source, SequenceRandom((10,) * 6))
        with self.assertRaisesRegex(ValueError, 'follow-ups'):
            replace(miss.state, pending_minion_attack=miss.attack)
        with self.assertRaises(TypeError): replace(source.state, minion_attack=source.attack)
        with self.assertRaises(TypeError): replace(source.state, pending_minion_attack=False)

    def test_family_histories_remain_ordered_and_disjoint_without_reset(self):
        state = scenario().initial_runtime_state
        state = replace(state, consumed_execution_ids=('old:1', 'cast:old', 'old:2'),
            minion_attack=replace(state.minion_attack, consumed_execution_ids=('old:1', 'old:2'),
                                  acknowledged_defeat_execution_ids=('old:1',)))
        source = request(state); final = execute(source, SequenceRandom((10,) * 6)).state
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('old:1', 'old:2', 'minion:attack'))
        self.assertEqual(final.minion_attack.acknowledged_defeat_execution_ids, ('old:1',))
        with self.assertRaisesRegex(ValueError, 'ordered attack history'):
            replace(state, consumed_execution_ids=('old:2', 'old:1', 'cast:old'))
        with self.assertRaisesRegex(ValueError, 'cannot share'):
            replace(state, champion_attack=replace(state.champion_attack, consumed_execution_ids=('old:1',)))

    def test_pending_minion_attack_blocks_another_attack_and_turn_end(self):
        from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
        source = request(); final = execute(source, SequenceRandom((1, 2, 3, 10, 10, 10))).state
        with self.assertRaisesRegex(ValueError, 'mandatory pending'):
            replace(source, state=final)
        with self.assertRaisesRegex(ValueError, 'pending Minion attack'):
            NpcWoundTurnEndRequest('end', final, 'ally')

    def test_executor_failure_preserves_source_without_partial_handoff(self):
        source = request(); before = deepcopy(source)
        error = RuntimeError('dice source failed')
        rng = Mock(); rng.randint.side_effect = (1, error)
        with self.assertRaises(RuntimeError) as caught: execute(source, rng)
        self.assertIs(caught.exception, error)
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)

    def test_pending_blocks_casting_champion_broken_and_completion_entries(self):
        from tests.unit.test_m8_npc_champion_attack import request as champion_request
        from tests.unit.test_m8_npc_roster_casting import bound_request
        from tests.unit.test_m8_npc_roster_casting_completion import begin as pending_movement, completion_request
        from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
        from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest
        from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
        from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
        from towr.domain.npc_broken_run_models import NpcBrokenRunRequest
        from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
        from towr.domain.test_models import InlineProfile
        from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
        source = request(); final = execute(source, SequenceRandom((1, 2, 3, 10, 10, 10))).state
        cast = bound_request().casting
        _, _, movement_state, _ = pending_movement()
        completion = completion_request(movement_state).completion
        movement = FreeMovementRequest('broken:free-move', final.round_state, final.spatial_state, 'ally',
            MovementSpeed.NORMAL, final.roster.participant('ally').state.injury.conditions, ('middle',))
        constructors = (
            lambda: NpcRosterCastingRequest(final, cast),
            lambda: prepare_npc_roster_casting(request_id='cast', state=final, selected_zone_id='arena',
                                               targets=(), facts=cast.facts, policy=cast.policy),
            lambda: NpcRosterChampionAttackRequest(final, champion_request()),
            lambda: NpcRosterCastingCompletionRequest(final, completion),
            lambda: NpcBrokenRecoverRequest('broken', final, 'ally', InlineProfile(3, 3), None, True, True),
            lambda: NpcBrokenRunRequest('broken', final, 'ally', movement, 'shelter', (), False, False, True),
        )
        for constructor in constructors:
            with self.subTest(constructor=constructor), self.assertRaisesRegex(ValueError, 'pending Minion attack'):
                constructor()


if __name__ == '__main__':
    unittest.main()
