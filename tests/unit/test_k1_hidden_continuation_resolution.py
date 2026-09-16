from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import loss_request
from tests.unit.test_k1_prepared_hidden_ranged_attack_resolution import (
    request as prepared_hidden_request,
)
from towr.domain.aim_models import AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_continuation_models import (
    HiddenOpportunityContinuationOutcome,
    MoveQuietlyHiddenAttackContinuationRequest,
)
from towr.domain.turn_models import (
    CombatActionDeclaration,
    CombatActionKind,
    ImproviseKind,
    ManoeuvreKind,
)
from towr.rules.aim_resolution import resolve_aim_follow_up
from towr.rules.hidden_attack_resolution import lose_move_quietly_hidden_attack
from towr.rules.hidden_continuation_resolution import continue_move_quietly_hidden_attack
from towr.rules.prepared_hidden_ranged_attack_resolution import execute_prepared_hidden_ranged_attack


def continuation_request(source=None):
    source = source or prepared_hidden_request(aim_values=(1, 10, 10))
    hidden = source.hidden_attack
    aim = source.prepared_attack.preparation.source_request.aim
    return MoveQuietlyHiddenAttackContinuationRequest(
        id="continue:hidden-after-aim",
        move_quietly=hidden.move_quietly,
        opportunity=hidden.opportunity,
        action=aim.slot.execution,
        spatial_state=hidden.spatial_state,
        hiding_position_id=hidden.hiding_position_id,
        position_revealed=False,
        consumed_opportunity_ids=hidden.consumed_opportunity_ids,
    )


class K1HiddenContinuationResolutionTests(unittest.TestCase):
    def test_non_attacking_actions_preserve_opportunity_without_new_receipt(self):
        source = continuation_request()
        declarations = (
            CombatActionDeclaration(CombatActionKind.AIM),
            CombatActionDeclaration(CombatActionKind.HELP),
            CombatActionDeclaration(CombatActionKind.RECOVER),
            CombatActionDeclaration(CombatActionKind.MANOEUVRE,
                                    manoeuvre=ManoeuvreKind.MOVE_CAREFULLY),
            CombatActionDeclaration(CombatActionKind.IMPROVISE,
                                    improvise_kind=ImproviseKind.SKILL,
                                    improvise_approach_id="reload:weapon"),
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                request = replace(source, action=replace(source.action, declaration=declaration))
                result = continue_move_quietly_hidden_attack(request)
                self.assertIs(result.outcome, HiddenOpportunityContinuationOutcome.PRESERVED)
                self.assertIsNone(result.loss_reason)
                self.assertIs(result.remaining_opportunity, source.opportunity)
                self.assertEqual(result.consumed_opportunity_ids, ("hidden:older",))
                self.assertIs(result.source_request.action, request.action)
                self.assertIs(result.source_request.spatial_state, request.spatial_state)
                self.assertIn(source.action.executor_rule_id, result.applied_rule_ids)

    def test_moved_position_or_explicit_reveal_loses_once(self):
        source = continuation_request()
        moved = replace(source.spatial_state, placements=tuple(
            replace(p, zone_id="zone:d") if p.entity_id == source.opportunity.actor_id else p
            for p in source.spatial_state.placements
        ))
        cases = (
            ({"spatial_state": moved}, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
            ({"hiding_position_id": None}, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
            ({"hiding_position_id": "other"}, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
            ({"position_revealed": True}, HiddenAttackOpportunityLossReason.POSITION_REVEALED),
            ({"spatial_state": moved, "position_revealed": True},
             HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                result = continue_move_quietly_hidden_attack(replace(source, **changes))
                self.assertIs(result.outcome, HiddenOpportunityContinuationOutcome.LOST)
                self.assertIs(result.loss_reason, reason)
                self.assertIsNone(result.remaining_opportunity)
                self.assertEqual(result.consumed_opportunity_ids,
                                 ("hidden:older", source.opportunity.id))
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    replace(source, consumed_opportunity_ids=result.consumed_opportunity_ids)

    def test_legacy_non_attack_loss_no_longer_consumes_stationary_opportunity(self):
        for kind in (CombatActionKind.AIM, CombatActionKind.HELP, CombatActionKind.RECOVER):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, "continuation contract"):
                    loss_request(kind=kind)
                result = lose_move_quietly_hidden_attack(
                    loss_request(kind=kind, hiding_position_id=None)
                )
                self.assertIs(result.reason, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION)

    def test_attacks_charge_and_attacking_improvise_cannot_be_preserved(self):
        source = continuation_request()
        for declaration in (
            CombatActionDeclaration(CombatActionKind.ATTACK),
            CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.CHARGE),
            CombatActionDeclaration(CombatActionKind.IMPROVISE,
                                    improvise_kind=ImproviseKind.SKILL,
                                    improvise_approach_id="attack:skill",
                                    improvise_produces_attack=True),
        ):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(ValueError, "non-attacking"):
                    replace(source, action=replace(source.action, declaration=declaration))

    def test_stale_receipts_sources_rounds_and_invalid_facts_are_rejected(self):
        source = continuation_request()
        for changes in (
            {"action": None},
            {"action": replace(source.action, actor_id="scout")},
            {"action": replace(source.action, round_number=3)},
            {"action": source.move_quietly.slot.execution,
             "spatial_state": source.move_quietly.spatial_state},
            {"opportunity": replace(source.opportunity, id="foreign")},
            {"id": source.action.id}, {"rule_id": "foreign"},
            {"position_revealed": 1}, {"position_revealed": None},
            {"consumed_opportunity_ids": ("same", "same")},
            {"consumed_opportunity_ids": "invalid"},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)

    def test_result_outcome_consumption_and_trace_are_closed(self):
        source = continuation_request()
        preserved = continue_move_quietly_hidden_attack(source)
        lost = continue_move_quietly_hidden_attack(replace(source, position_revealed=True))
        for result, changes in (
            (preserved, {"request_id": "foreign"}),
            (preserved, {"outcome": HiddenOpportunityContinuationOutcome.LOST}),
            (preserved, {"loss_reason": HiddenAttackOpportunityLossReason.POSITION_REVEALED}),
            (preserved, {"consumed_opportunity_ids": lost.consumed_opportunity_ids}),
            (lost, {"consumed_opportunity_ids": preserved.consumed_opportunity_ids}),
            (lost, {"previous_consumed_opportunity_ids": ()}),
            (lost, {"applied_rule_ids": (lost.rule_id,)}),
            (lost, {"applied_rule_ids": (*lost.applied_rule_ids, "invented")}),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)

    def test_move_quietly_next_round_aim_then_hidden_shot_uses_continuous_chain(self):
        for aim_values in ((1, 10, 10), (10, 10, 10)):
            with self.subTest(aim_values=aim_values):
                source = prepared_hidden_request(aim_values=aim_values)
                continuation = continue_move_quietly_hidden_attack(continuation_request(source))
                self.assertLess(source.hidden_attack.move_quietly.round_state.round_number,
                                continuation.source_request.action.round_number)
                chained = replace(source, hidden_attack=replace(
                    source.hidden_attack,
                    opportunity=continuation.remaining_opportunity,
                    consumed_opportunity_ids=continuation.consumed_opportunity_ids,
                ))
                count = 3 if aim_values[0] == 1 else 2
                rng = SequenceRandom([10] * count + [7])
                result = execute_prepared_hidden_ranged_attack(chained, rng)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.consumed_opportunity_ids,
                                 ("hidden:older", continuation.remaining_opportunity.id))
                self.assertEqual(result.consumed_aim_follow_up_ids, (
                    "aim:older", chained.prepared_attack.preparation.aim_follow_up.request_id,
                ))
                self.assertEqual(sum(s.executed for s in result.ranged_attack.attack.state.active_turn.action_slots), 2)
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    replace(chained.hidden_attack, consumed_opportunity_ids=result.consumed_opportunity_ids)

    def test_aim_still_loses_its_bonus_when_next_action_is_not_attack(self):
        source = prepared_hidden_request(aim_values=(1, 10, 10))
        aim = source.prepared_attack.preparation.source_request.aim
        result = resolve_aim_follow_up(AimFollowUpRequest(
            id="aim:lost-to-help", aim=aim, actor_id="hero", next_action_id="help:next",
            declaration=CombatActionDeclaration(CombatActionKind.HELP),
        ))
        self.assertIs(result.outcome, AimFollowUpOutcome.LOST)


if __name__ == "__main__":
    unittest.main()
