import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m2_npc_roster_attack_execution import request
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import GiveGroundRequest, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result, execute_npc_roster_attack
from towr.rules.turn_resolution import end_combat_turn, reserve_combat_action_slot, start_combat_turn


def next_attack(state, combat_round, actor_id, target_id, prefix):
    actor, target = state.roster.participant(actor_id), state.roster.participant(target_id)
    started = start_combat_turn(CombatTurnStartRequest(prefix + ":start", combat_round, actor_id)).state
    reserved = reserve_combat_action_slot(CombatActionSlotRequest(
        prefix + ":slot", started, actor_id, CombatActionDeclaration(CombatActionKind.ATTACK),
        ActionSlotGrant.STANDARD,
    )).state
    npc = prepare_npc_attack(NpcAttackPreparationRequest(
        id=prefix + ":prepare", attack_id=prefix + ":attack", attacker_test_id=prefix + ":test",
        snapshot=actor.attack_snapshot(prefix + ":snapshot"), selected_attack_id="axe", target_id=target_id,
        target_range=RangedWeaponRange.CLOSE, target_resilience=target.state.current_resilience,
        has_enemy_in_close_range=True, attacker_is_staggered=actor.state.injury.conditions.has(Condition.STAGGERED),
        range_approved_by_gm=False,
    ))
    prepared = prepare_npc_attack_protection(npc, ProtectionPreparationRequest(
        id=prefix + ":protect", defender_id=target_id, attack=npc.attack, attack_skill=npc.selected_profile.skill,
        defender_is_aware=True, defender_is_defenceless=target.state.injury.conditions.has(Condition.DEFENCELESS),
        defender_wields_weapon=target.state.wields_weapon, defender_holds_shield=target.state.holds_shield,
        selected_skill=Skill.ATHLETICS, options=target.protection_options(prefix + ":protection-test"),
    ))
    kernel = KernelAttackRequest(prefix + ":kernel", target_id, prepared.attack,
        TargetInjuryPolicy.MINION, target.state.injury, True, False)
    return NpcRosterAttackExecutionRequest(state, prepared,
        AttackActionExecutionRequest(prefix + ":execution", reserved, actor_id, target_id, 1, kernel))


class M2NpcRosterAttackTurnsTests(unittest.TestCase):
    def test_close_miss_is_visible_when_next_actor_attacks_and_give_ground_remains_pending(self):
        state = request().state
        # The roster may retain other actors; this scenario explicitly selects two participants.
        combat_round = CombatRoundState(1, participants=tuple(
            state.roster.participant(actor).turn_participant for actor in ("brigand:0", "brigand:2")))
        first = next_attack(state, combat_round, "brigand:0", "brigand:2", "first")
        rng = SequenceRandom([10] * 6 + [1, 10, 10, 10, 10, 10, 7])
        result = execute_npc_roster_attack(first, rng)
        current = apply_npc_roster_attack_result(state, result)
        self.assertTrue(current.roster.participant("brigand:0").state.injury.conditions.has(Condition.STAGGERED))
        ended = end_combat_turn(CombatTurnEndRequest("first:end", result.execution.state, "brigand:0")).state
        second = next_attack(current, ended, "brigand:2", "brigand:0", "second")
        self.assertIs(second.execution.kernel_request.target_state,
                      current.roster.participant("brigand:0").state.injury)
        response = execute_npc_roster_attack(second, rng, decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
        final = apply_npc_roster_attack_result(current, response)
        self.assertEqual(final.consumed_execution_ids, ("first:execution", "second:execution"))
        self.assertEqual(len(response.pending_follow_ups), 1)
        self.assertIsInstance(response.pending_follow_ups[0], GiveGroundRequest)
        self.assertEqual(final.roster.participant("brigand:0").state.injury.wounds, 0)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertEqual(response.execution.slot.execution.actor_id, "brigand:2")
        with self.assertRaisesRegex(ValueError, "already consumed"):
            apply_npc_roster_attack_result(final, result)

    def test_defeated_target_cannot_act_using_returned_roster(self):
        state = request().state
        combat_round = CombatRoundState(1, participants=tuple(
            state.roster.participant(actor).turn_participant for actor in ("brigand:0", "brigand:2")))
        first = next_attack(state, combat_round, "brigand:0", "brigand:2", "first")
        result = execute_npc_roster_attack(first, SequenceRandom([1, 2, 10, 10, 10, 10]))
        current = apply_npc_roster_attack_result(state, result)
        ended = end_combat_turn(CombatTurnEndRequest("first:end", result.execution.state, "brigand:0")).state
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "defeated"):
            execute_npc_roster_attack(next_attack(current, ended, "brigand:2", "brigand:0", "second"), rng)
        rng.randint.assert_not_called()
