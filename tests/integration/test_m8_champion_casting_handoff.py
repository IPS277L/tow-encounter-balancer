from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_champion_attack import request as champion_request
from tests.unit.test_m8_npc_roster_casting import bound_request
from tests.integration.test_m2_npc_roster_preparation import protection_request
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.cowardly_flight_casting_models import BATTLE_MAGIC_LORE_ID, CastingCasterDefinition
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_casting_models import (
    NpcCastingWizardState, NpcRosterCastingState, NpcRosterCastingTargetContext, NpcRosterCastingResult,
)
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import (
    CombatActionDeclaration, CombatActionKind, ImproviseKind, ActionSlotGrant,
    CombatTurnEndRequest, CombatTurnStartRequest, CombatActionSlotRequest,
)
from towr.rules.turn_resolution import end_combat_turn, start_combat_turn, reserve_combat_action_slot
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result as apply_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting


def incoming_attack():
    """Authored unarmoured Champion with the same total Resilience as fixture."""
    attack = champion_request()
    target = attack.state.roster.participant(attack.execution.target_id)
    current_resilience = ResilienceProfile(4)
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, current_resilience=current_resilience))
                            if p is target else p for p in attack.state.roster.participants))
    prepared = prepare_npc_attack(replace(attack.preparation.npc_attack.source_request,
                                         target_resilience=current_resilience))
    protected = prepare_npc_attack_protection(prepared, protection_request(roster, prepared))
    attack = replace(attack, state=replace(attack.state, roster=roster), preparation=protected,
                     execution=replace(attack.execution, kernel_request=replace(
                         attack.execution.kernel_request, attack=protected.attack)))
    wizard = NpcCastingWizardState(attack.execution.target_id,
        CastingCasterDefinition('authored:caster', 'authored:Wizard', 2, InlineProfile(3, 3)),
        WizardMagicState(1, 1, BATTLE_MAGIC_LORE_ID, 1))
    spatial = SpatialBattleState(ZoneGraph(('arena',)), tuple(SpatialEntityPlacement(
        p.entity_id, p.side.value, 'arena') for p in attack.state.round_state.participants), round_number=1)
    state = NpcRosterCastingState(roster, wizard, attack.state.round_state, spatial,
                                  champion_attack=attack.state)
    return NpcRosterChampionAttackRequest(state, attack)


def wizard_turn(state):
    """Advance actual K1 turns; no end-turn effects are elided for the Wizard."""
    combat = end_combat_turn(CombatTurnEndRequest('end:attacker', state.round_state, 'brigand:0')).state
    combat = start_combat_turn(CombatTurnStartRequest('start:ally', combat, 'brigand:1')).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest('slot:ally', combat, 'brigand:1',
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state
    combat = execute_recover_action(RecoverActionExecutionRequest(
        'recover:ally', combat, 'brigand:1', ConditionState(), True, 1,
        RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState())), SequenceRandom(())).round_state
    combat = end_combat_turn(CombatTurnEndRequest('end:ally', combat, 'brigand:1')).state
    combat = start_combat_turn(CombatTurnStartRequest('start:wizard', combat, state.wizard.actor_id)).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest('slot:cast', combat, state.wizard.actor_id,
        CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                               improvise_approach_id=BATTLE_MAGIC_LORE_ID), ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=combat, champion_attack=replace(state.champion_attack, round_state=combat))


def prepare(state, request_id='after-injury:cast'):
    fixture = bound_request().casting
    return prepare_npc_roster_casting(request_id=request_id, state=state, selected_zone_id='arena',
        targets=tuple(NpcRosterCastingTargetContext(actor, InlineProfile(3, 3), False)
                      for actor in ('brigand:0', 'brigand:1')), facts=fixture.facts, policy=fixture.policy)


class ChampionCastingHandoffTests(unittest.TestCase):
    def test_stomach_wound_then_cast_preserves_magic_daily_wounds_and_both_histories(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
        transfer = NpcRosterChampionAttackResult(source, attack)
        state = apply_attack(source.state, transfer)
        self.assertIs(state.wizard, source.state.wizard)
        self.assertIs(state.spatial_state, source.state.spatial_state)
        self.assertIsNone(state.champion_attack.pending)
        self.assertEqual(state.champion_attack.daily_wounds.wound_count, 1)
        current = wizard_turn(state)
        casting = prepare(current)
        outcome = execute_cowardly_flight_casting(casting.casting, SequenceRandom((1, 2, 10, 1, 2, 10, 10, 10, 10)))
        result = NpcRosterCastingResult(casting, outcome)
        final = apply_npc_roster_casting_result(current, result)
        self.assertEqual(final.wizard.magic_state, WizardMagicState(1))
        self.assertEqual(final.roster.participant(final.wizard.actor_id).state.injury, attack.resolution.target_state)
        self.assertTrue(final.roster.participant(final.wizard.actor_id).state.injury.conditions.has(Condition.DRAINED))
        self.assertTrue(final.roster.participant('brigand:1').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertEqual(final.champion_attack.daily_wounds, state.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, state.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id, 'after-injury:cast'))
        self.assertEqual(final.champion_attack.consumed_execution_ids, (source.attack.execution.id,))

    def test_unresolved_endurance_drop_blocks_casting_before_rng(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        state = apply_attack(source.state, NpcRosterChampionAttackResult(source, attack))
        self.assertIs(state.champion_attack.pending, attack)
        self.assertIs(state.wizard, source.state.wizard)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no RNG')):
            with self.assertRaisesRegex(ValueError, 'pending Champion attack'):
                prepare(state)

    def test_miscast_blocks_attack_dispatch_and_preserves_owner_history(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        state = wizard_turn(apply_attack(source.state, NpcRosterChampionAttackResult(source, attack)))
        casting = prepare(state)
        outcome = execute_cowardly_flight_casting(casting.casting, SequenceRandom((9, 9, 1)))
        final = apply_npc_roster_casting_result(state, NpcRosterCastingResult(casting, outcome))
        self.assertIs(final.pending_miscast, outcome)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(final.champion_attack.consumed_execution_ids, (source.attack.execution.id,))
        with self.assertRaisesRegex(ValueError, 'pending Miscast'):
            NpcRosterChampionAttackRequest(final, source.attack)

    def test_handoff_rejects_stale_magic_spatial_replay_and_wrong_source(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        result = NpcRosterChampionAttackResult(source, attack)
        with self.assertRaisesRegex(ValueError, 'stale source'):
            apply_attack(replace(source.state, wizard=replace(source.state.wizard, magic_state=WizardMagicState())), result)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            apply_attack(apply_attack(source.state, result), result)
        with self.assertRaisesRegex(ValueError, 'bound source'):
            replace(result, source=replace(source, attack=replace(source.attack,
                    execution=replace(source.attack.execution, id='another'))))
        with self.assertRaisesRegex(ValueError, 'bound owner'):
            replace(source, state=replace(source.state, champion_attack=None))
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            replace(source, state=replace(source.state, consumed_execution_ids=(source.attack.execution.id,)))
        current = wizard_turn(result.state)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            prepare(current, request_id=source.attack.execution.id)

    def test_owner_and_round_cannot_be_updated_independently(self):
        source = incoming_attack()
        with self.assertRaisesRegex(ValueError, 'current caster/roster/round'):
            replace(source.state, round_state=replace(source.state.round_state, round_number=2),
                    spatial_state=replace(source.state.spatial_state, round_number=2))

    def test_bound_attack_history_cannot_be_dropped_from_casting_state(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        state = NpcRosterChampionAttackResult(source, attack).state
        with self.assertRaisesRegex(ValueError, 'retain all bound Champion attack'):
            replace(state, consumed_execution_ids=())

    def test_handoff_is_pure_and_preserves_the_bound_source(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        result = NpcRosterChampionAttackResult(source, attack)
        with patch('towr.rules.npc_champion_attack_execution.execute_attack_action',
                   side_effect=AssertionError('no new attack')):
            state = apply_attack(source.state, result)
        self.assertEqual(source.state.consumed_execution_ids, ())
        self.assertEqual(state.champion_attack.consumed_execution_ids, (source.attack.execution.id,))
        for argument in (None, source.attack):
            with self.assertRaises(TypeError):
                apply_attack(source.state, argument)


if __name__ == '__main__':
    unittest.main()
