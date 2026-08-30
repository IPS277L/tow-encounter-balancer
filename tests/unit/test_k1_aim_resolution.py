from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.aim_models import (
    AIM_ACTION_RULE_ID,
    AIM_FOLLOW_UP_RULE_ID,
    AimActionExecutionRequest,
    AimFollowUpOutcome,
    AimFollowUpRequest,
)
from towr.domain.attack_models import (
    AttackRequest,
    DamageImpactSpec,
    DamageProfile,
    ResilienceProfile,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
)
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
            CombatTurnParticipant("enemy:other", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
    ).state


def reserve_action(
    state: CombatRoundState,
    kind: CombatActionKind,
    *,
    grant: ActionSlotGrant = ActionSlotGrant.STANDARD,
) -> CombatRoundState:
    turn = state.active_turn
    assert turn is not None
    slot_index = len(turn.action_slots) + 1
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{slot_index}",
            state=state,
            actor_id="hero",
            declaration=CombatActionDeclaration(kind),
            grant=grant,
            grant_rule_id=(
                "RULE-ABILITY:test-extra-action"
                if grant is ActionSlotGrant.ABILITY
                else None
            ),
        )
    ).state


def aim_request(
    state: CombatRoundState,
    *,
    target_id: str = "enemy",
    skill: Skill = Skill.AWARENESS,
    profile: TestProfile = TestProfile(3, 5),
) -> AimActionExecutionRequest:
    return AimActionExecutionRequest(
        id="aim:execute",
        round_state=state,
        actor_id="hero",
        target_id=target_id,
        slot_index=1,
        awareness_test=TestRequest("aim:awareness", profile),
        awareness_skill=skill,
    )


def completed_aim(*, values: tuple[int, ...] = (1, 5, 10)):
    state = reserve_action(active_round(), CombatActionKind.AIM)
    return execute_aim_action(aim_request(state), SequenceRandom(values))


def attack_execution_request(
    *,
    state: CombatRoundState | None = None,
    slot_index: int = 1,
    target_id: str = "enemy",
    attacker_profile: TestProfile = TestProfile(3, 5),
    existing_modifiers: tuple[DiceModifier, ...] = (),
) -> AttackActionExecutionRequest:
    attack_state = state
    if attack_state is None:
        attack_state = reserve_action(active_round(), CombatActionKind.ATTACK)
    return AttackActionExecutionRequest(
        id="attack:execute",
        state=attack_state,
        actor_id="hero",
        target_id=target_id,
        slot_index=slot_index,
        kernel_request=KernelAttackRequest(
            id="attack:kernel",
            target_id=target_id,
            attack=AttackRequest(
                id="attack:request",
                attacker_test=TestRequest(
                    "attack:test",
                    attacker_profile,
                    dice_modifiers=existing_modifiers,
                ),
                defender_test=None,
                impact_spec=DamageImpactSpec(
                    damage=DamageProfile(3),
                    resilience=ResilienceProfile(toughness=4, bonus=1),
                ),
                is_close_range=False,
                attacker_is_staggered=False,
            ),
            target_policy=TargetInjuryPolicy.PLAYER,
            target_state=CharacterInjuryState(),
            can_target_leave_zone=True,
            target_has_given_ground_this_round=False,
        ),
    )


def follow_up_request(
    aim,
    *,
    attack: AttackActionExecutionRequest | None = None,
    skill: Skill | None = None,
    kind: CombatActionKind = CombatActionKind.ATTACK,
) -> AimFollowUpRequest:
    action = attack
    next_action_id = action.id if action is not None else "action:next"
    return AimFollowUpRequest(
        id="aim:follow-up",
        aim=aim,
        actor_id="hero",
        next_action_id=next_action_id,
        declaration=CombatActionDeclaration(kind),
        attack_skill=skill,
        attack=action,
    )


class K1AimActionExecutionTests(unittest.TestCase):
    def test_aim_executes_awareness_and_completes_reserved_slot(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.AIM)

        result = execute_aim_action(
            aim_request(state),
            SequenceRandom([1, 5, 10]),
        )

        self.assertEqual(result.awareness_test_result.successes, 2)
        self.assertEqual(result.bonus.bonus_dice, 2)
        self.assertEqual(result.bonus.target_id, "enemy")
        self.assertTrue(result.bonus.extreme_range_requires_gm_approval)
        self.assertTrue(result.slot.executed)
        self.assertEqual(result.round_state.active_turn.action_slots[0], result.slot)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(receipt.source_request_id, "aim:execute")
        self.assertEqual(receipt.result_request_id, "aim:awareness")
        self.assertIn(AIM_ACTION_RULE_ID, result.applied_rule_ids)

    def test_failed_awareness_still_completes_aim_with_zero_bonus(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.AIM)

        result = execute_aim_action(
            aim_request(state),
            SequenceRandom([8, 9, 10]),
        )

        self.assertEqual(result.awareness_test_result.successes, 0)
        self.assertEqual(result.bonus.bonus_dice, 0)
        self.assertTrue(result.slot.executed)

    def test_aim_requires_awareness_enemy_and_matching_slot(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.AIM)
        with self.assertRaises(ValueError):
            aim_request(state, target_id="ally")
        with self.assertRaises(ValueError):
            aim_request(state, skill=Skill.SHOOTING)

        attack_state = reserve_action(active_round(), CombatActionKind.ATTACK)
        with self.assertRaises(ValueError):
            execute_aim_action(
                aim_request(attack_state),
                SequenceRandom([1, 1, 1]),
            )

    def test_turn_cannot_end_with_unexecuted_aim(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.AIM)
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "hero"))

        completed = execute_aim_action(
            aim_request(state),
            SequenceRandom([8, 9, 10]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", completed.round_state, "hero")
        )
        self.assertIsNone(ended.state.active_turn)


class K1AimFollowUpTests(unittest.TestCase):
    def test_next_shooting_attack_same_target_receives_bonus_and_normal_cap(self) -> None:
        aim = completed_aim(values=(1, 2, 3))
        attack_state = reserve_action(
            aim.round_state,
            CombatActionKind.ATTACK,
            grant=ActionSlotGrant.ABILITY,
        )
        attack = attack_execution_request(
            state=attack_state,
            slot_index=2,
            attacker_profile=TestProfile(2, 5),
        )

        follow_up = resolve_aim_follow_up(
            follow_up_request(aim, attack=attack, skill=Skill.SHOOTING)
        )

        self.assertIs(
            follow_up.outcome,
            AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK,
        )
        self.assertEqual(follow_up.modifier.amount, 3)
        self.assertFalse(follow_up.modifier.bypasses_pool_cap)
        self.assertIn(AIM_FOLLOW_UP_RULE_ID, follow_up.applied_rule_ids)
        self.assertIsNot(follow_up.attack, attack)
        resolved = execute_attack_action(
            follow_up.attack,
            SequenceRandom([1, 5, 10, 10]),
        )
        trace = resolved.resolution.attack.attacker_test.trace
        self.assertEqual(trace.regular_dice_delta, 3)
        self.assertEqual(trace.rolled_dice, 4)

    def test_throwing_is_ranged_and_zero_bonus_is_consumed_without_modifier(self) -> None:
        aim = completed_aim(values=(8, 9, 10))
        attack = attack_execution_request()

        result = resolve_aim_follow_up(
            follow_up_request(aim, attack=attack, skill=Skill.THROWING)
        )

        self.assertIs(
            result.outcome,
            AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK,
        )
        self.assertIsNone(result.modifier)
        self.assertIs(result.attack, attack)

    def test_wrong_target_or_melee_attack_loses_bonus_without_changing_attack(self) -> None:
        aim = completed_aim()
        cases = (
            (attack_execution_request(target_id="enemy:other"), Skill.SHOOTING),
            (attack_execution_request(), Skill.MELEE),
        )
        for attack, skill in cases:
            with self.subTest(skill=skill, target=attack.target_id):
                result = resolve_aim_follow_up(
                    follow_up_request(aim, attack=attack, skill=skill)
                )
                self.assertIs(result.outcome, AimFollowUpOutcome.LOST)
                self.assertIs(result.attack, attack)
                self.assertIsNone(result.modifier)

    def test_any_non_attack_action_loses_bonus(self) -> None:
        aim = completed_aim()

        result = resolve_aim_follow_up(
            follow_up_request(aim, kind=CombatActionKind.HELP)
        )

        self.assertIs(result.outcome, AimFollowUpOutcome.LOST)
        self.assertIsNone(result.attack)
        self.assertIsNone(result.modifier)

    def test_follow_up_rejects_wrong_actor_and_duplicate_application(self) -> None:
        aim = completed_aim()
        attack = attack_execution_request()
        with self.assertRaises(ValueError):
            AimFollowUpRequest(
                id="aim:follow-up",
                aim=aim,
                actor_id="enemy",
                next_action_id=attack.id,
                declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
                attack_skill=Skill.SHOOTING,
                attack=attack,
            )

        duplicate = attack_execution_request(
            existing_modifiers=(DiceModifier(AIM_FOLLOW_UP_RULE_ID, 1),)
        )
        with self.assertRaises(ValueError):
            resolve_aim_follow_up(
                follow_up_request(
                    aim,
                    attack=duplicate,
                    skill=Skill.SHOOTING,
                )
            )

    def test_follow_up_result_rejects_forged_outcome(self) -> None:
        aim = completed_aim()
        attack = attack_execution_request()
        result = resolve_aim_follow_up(
            follow_up_request(aim, attack=attack, skill=Skill.SHOOTING)
        )

        with self.assertRaises(ValueError):
            replace(result, outcome=AimFollowUpOutcome.LOST)


if __name__ == "__main__":
    unittest.main()
