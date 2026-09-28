from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_blunderbuss import request as primary_request
from tests.unit.test_m2_npc_attack_controller import candidate as ordinary_candidate
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition
from towr.domain.exacting_test_models import ExactingTestProgress, ExactingTestContribution
from towr.domain.npc_attack_selection_models import NpcAttackCandidateRejection as Rejection, NpcAttackSelectionBlock as Block
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome, NpcRoundResult
from towr.domain.npc_round_weapon_models import NpcRoundWeaponState, NpcBlunderbussCandidateContext
from towr.domain.npc_rounds_models import NpcRoundsRequest, NpcRoundsResult
from towr.domain.npc_rounds_summary_models import NpcRoundsSummary
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine import npc_attack_controller as controller
from towr.engine.npc_round_coordinator import run_npc_round
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.rules import attack_action_execution as attack_executor


def request(*, roster=None, reserved=False):
    base = primary_request(roster=roster)
    current = replace(base.current, weapons=(NpcRoundWeaponState("brigand:0", base.attack_profile_id, base.weapon_state),))
    if not reserved:
        current = replace(current, round_state=replace(current.round_state, active_turn=None))
    return current


def candidate(source, *, identifier="shot", distance=Range.SHORT):
    binding = source.round_context.weapons[0]
    return replace(ordinary_candidate(source.state, identifier, attack=binding.attack_profile_id),
        target_range=distance, blunderbuss=NpcBlunderbussCandidateContext(
            binding.weapon_state.weapon_instance_id, "shot:reload", True, 3))


class Candidates:
    def __init__(self, *, distance=Range.SHORT, ordinary=False):
        self.distance, self.ordinary = distance, ordinary
        self.contexts = []

    def get_candidates(self, source):
        self.contexts.append(source)
        if source.actor_id == "brigand:0":
            return replace(source, candidates=(candidate(source, distance=self.distance),))
        if self.ordinary and source.actor_id == "brigand:1":
            return replace(source, candidates=(ordinary_candidate(source.state, "ordinary", target_id="brigand:3", attack="warbow"),))
        return source


class M2NpcBlunderbussRoundTests(unittest.TestCase):
    def test_hit_miss_and_medium_range_have_one_execution_and_persistent_weapon_transition(self):
        for hit, distance, dice in ((True, Range.SHORT, [1, 2, 10, 10, 10, 10, 10, 10]),
                                    (False, Range.SHORT, [10] * 8), (False, Range.MEDIUM, [10] * 5)):
            with self.subTest(hit=hit, distance=distance):
                source = request()
                before = deepcopy(source)
                provider = Candidates(distance=distance)
                rng = Mock(wraps=SequenceRandom([*dice, 7]))
                with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
                    result = run_npc_round(source, provider, rng)
                self.assertEqual(kernel.call_count, 1)
                self.assertEqual(rng.randint.call_count, len(dice))
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.executed_attack_count, 1)
                attack, = (s for s in result.steps if isinstance(s, NpcBlunderbussAttackExecutionResult))
                self.assertIs(result.weapons[0].weapon_state, attack.weapon_state)
                self.assertFalse(result.weapons[0].weapon_state.loaded)
                self.assertEqual(result.continuation.weapons, result.weapons)
                self.assertEqual(result.state.consumed_execution_ids, (attack.primary_attack.attack.request_id,))
                self.assertIs(result.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS if hit else NpcRoundOutcome.SELECTION_BLOCKED)
                self.assertEqual(source, before)
                if not hit:
                    self.assertEqual(provider.contexts[-1].round_context.weapons, result.weapons)
                    self.assertEqual(result.round_state.completed_turn_entity_ids, ("brigand:0",))

    def test_ordered_selection_rejects_foreign_weapon_and_preserves_ordinary_guard(self):
        current = request(reserved=True)
        source = current.selection_context(current.state, current.round_state)
        good = candidate(source)
        bad = replace(good, id="foreign", blunderbuss=replace(good.blunderbuss, weapon_instance_id="foreign"))
        unsupported = replace(good, id="ordinary", blunderbuss=None)
        supplied = replace(source, candidates=(bad, unsupported, good))
        result = controller.select_npc_attack(supplied)
        self.assertEqual(tuple(r.reason for r in result.rejected), (Rejection.WEAPON_CONTEXT, Rejection.UNSUPPORTED_EFFECTS))
        self.assertIs(result.selected_candidate, good)
        self.assertEqual(result.execution_request.current, current)
        for changed in (None, replace(current, id="other"), replace(current, weapons=())):
            with self.assertRaisesRegex(ValueError, "round/weapon"):
                controller.require_current_npc_attack_selection(result, current.state, current.round_state,
                    pending_follow_ups=(), round_context=changed)
        self.assertIs(controller.require_current_npc_attack_selection(result, current.state, current.round_state,
            pending_follow_ups=(), round_context=current), result.execution_request)

    def test_unloaded_lore_range_close_enemy_and_reused_reload_reject_before_rng(self):
        fresh = request(reserved=True)
        miss = run_npc_round(fresh, Candidates(), SequenceRandom([10] * 8))
        for unloaded in (False, True):
            current = replace(fresh, weapons=miss.weapons) if unloaded else fresh
            source = current.selection_context(current.state, current.round_state)
            good = candidate(source)
            variants = (good,) if unloaded else (
                replace(good, blunderbuss=replace(good.blunderbuss, has_blackpowder_lore=False)),
                replace(good, target_range=Range.LONG), replace(good, has_enemy_in_close_range=True),
            )
            for variant in variants:
                with self.subTest(unloaded=unloaded, candidate=variant):
                    result = controller.select_npc_attack(replace(source, candidates=(variant,)))
                    self.assertIs(result.blocked_reason, Block.NO_CANDIDATE)
                    self.assertEqual(result.rejected[0].reason, Rejection.WEAPON_CONTEXT)
        weapon = fresh.weapons[0]
        progress = ExactingTestProgress("shot:reload:exacting", 3, (ExactingTestContribution("reload", "reload:test", "brigand:0", 3),))
        weapon = replace(weapon, weapon_state=replace(weapon.weapon_state, reload_cycle_ids=("shot:reload",),
            reload_cycle_id="shot:reload", exacting=progress))
        current = replace(fresh, weapons=(weapon,))
        provider = Candidates()
        rng = Mock()
        stopped = run_npc_round(current, provider, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
        rng.randint.assert_not_called()

    def test_actor_conditions_pending_and_provider_snapshot_guards(self):
        source = request()
        for condition, block in ((Condition.BROKEN, Block.ACTOR_BROKEN), (Condition.DEFENCELESS, Block.ACTOR_DEFENCELESS)):
            injury = source.state.roster.participant("brigand:0").state.injury
            changed = replace(source, state=change_participant(source.state, 0,
                injury=replace(injury, conditions=injury.conditions.with_condition(condition))))
            rng = Mock()
            stopped = run_npc_round(changed, Candidates(), rng)
            self.assertIs(stopped.blocked_selection.blocked_reason, block)
            rng.randint.assert_not_called()
        provider, rng = Mock(), Mock()
        pending = replace(source, pending_follow_ups=(GiveGroundRequest("external"),))
        stopped = run_npc_round(pending, provider, rng)
        self.assertEqual(stopped.steps, ())
        self.assertEqual(stopped.continuation, pending)
        provider.get_candidates.assert_not_called()
        provider.get_candidates.side_effect = lambda context: replace(context, round_context=replace(context.round_context, weapons=()))
        with self.assertRaisesRegex(ValueError, "provider changed"):
            run_npc_round(source, provider, rng)
        rng.randint.assert_not_called()

    def test_journal_rejects_missing_selection_repeated_attack_foreign_weapon_and_post_stop_steps(self):
        source = request()
        result = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10, 10, 10]))
        for steps in (result.steps[:-2] + result.steps[-1:], result.steps + result.steps[-1:], result.steps[:-1]):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                replace(result, steps=steps)
        wrong_weapon = replace(source.weapons[0], weapon_state=replace(source.weapons[0].weapon_state, weapon_instance_id="foreign"))
        with self.assertRaises(ValueError):
            replace(result, source_request=replace(source, weapons=(wrong_weapon,)))
        self.assertEqual(replace(result).continuation, result.continuation)
        with self.assertRaises(FrozenInstanceError):
            result.steps = ()

    def test_weapon_contracts_reject_duplicate_wrong_owner_and_unknown_profile(self):
        source = request()
        binding, = source.weapons
        for weapons in ((binding, binding), (replace(binding, actor_id="brigand:1"),),
                        (replace(binding, attack_profile_id="absent"),)):
            with self.subTest(weapons=weapons), self.assertRaises(ValueError):
                replace(source, weapons=weapons)
        with self.assertRaises(TypeError):
            replace(source, weapons=(object(),))
        with self.assertRaises(TypeError):
            NpcBlunderbussCandidateContext("weapon", "reload", "yes", 3)
        with self.assertRaises(ValueError):
            NpcBlunderbussCandidateContext("weapon", "reload", True, 0)

    def test_mixed_round_runner_and_summary_count_each_attack_once_and_keep_unloaded_weapon(self):
        from tests.unit.test_m2_npc_nearby_give_ground import spatial_context
        from tests.unit.test_m2_npc_blunderbuss_give_ground import context as completed_context

        source = request()
        # Only the graph/placements are used; round ownership and sources still come from the runner request.
        spatial = spatial_context(completed_context().completion.source_request.chain.batch)
        provider = Candidates(ordinary=True)
        adapter = Mock()
        adapter.get_candidates.side_effect = lambda current, spatial: provider.get_candidates(current)
        next_round = Mock()
        rng = Mock(wraps=SequenceRandom([10] * 14))
        result = run_npc_rounds(NpcRoundsRequest(source, spatial, 2), adapter, next_round, rng)
        self.assertIsInstance(result, NpcRoundsResult)
        self.assertEqual(result.rounds[0].executed_attack_count, 2)
        self.assertEqual(NpcRoundsSummary(result).executed_attack_count, 2)
        self.assertFalse(result.current.weapons[0].weapon_state.loaded)
        next_round.get_next_round.assert_not_called()
        self.assertEqual(rng.randint.call_count, 14)
        stopped_provider = Mock()
        stopped_provider.get_candidates.side_effect = lambda context: context
        resumed = run_npc_round(result.current, stopped_provider, Mock())
        self.assertEqual(resumed.executed_attack_count, 0)
        self.assertEqual(resumed.weapons, result.current.weapons)
