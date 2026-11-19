"""Real Prone-producing attacks followed by GM83 Headsman, never fake injury."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import (
    magic_battle, run_native, Threes, pc_after_horse_charge_source,
)
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    FixedWoundTableSelection, ProfileDecapitationCause, WoundEntryId, WoundRecordOrigin,
)
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleePolicy, PcFatePolicy, PcNearMissPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcWoundCompletionProof, PcProfileWoundProof,
)
from towr.domain.pc_npc_catalog import create_pc_book_npc, PcBookNpcProfile
from towr.domain.test_models import TestQuality
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome


def npc_headsman_source(*, near_miss=False):
    # A real Bear hit provides Prone immediately before the generated wielder's
    # turn. All actors begin healthy; the PC cannot Recover between NPC turns.
    source = magic_battle('headsmans_axe', npc_magic=True, count=2,
        pc_ws=1, npc_ws=6, rounds=1, fate=int(near_miss))
    bear = create_pc_book_npc(PcBookNpcProfile.BEAR_CRUSHING_WEIGHT,
        source.enemy_activation_order[0])
    member = replace(source.party[0], policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        fate_policy=PcFatePolicy.CONFIGURED if near_miss else PcFatePolicy.DECLINE_OPTIONAL_FATE,
        near_miss_policy=PcNearMissPolicy(24, 0) if near_miss else None, glorious_policy=None)
    return replace(source, party=(member,), enemies=(bear, source.enemies[1]),
        battlefield=None, facts=replace(source.facts, all_opponents_close=True, can_leave_zone=False))


def last_headsman_attack(result):
    return next(step for step in reversed(result.steps) if type(step.proof) is PcAttackProof
        and step.proof.weapon_intent.magic_context is not None
        and step.proof.weapon_intent.magic_context.headsman_execution)


class MagicWeaponHeadsmanTests(unittest.TestCase):
    def test_pc_charge_then_headsman_kills_minion_despite_explicit_knockout_policy(self):
        source = pc_after_horse_charge_source()
        result = run_native(self, source)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        strike = last_headsman_attack(result)
        proof = strike.proof
        self.assertEqual(proof.request.actor_id, source.pc_activation_order[1])
        before = strike.source.enemy(proof.request.target_id).state.injury
        self.assertTrue(before.conditions.has(Condition.PRONE))
        self.assertTrue(before.conditions.has(Condition.STAGGERED))
        self.assertEqual(before.wounds, 0)
        self.assertTrue(proof.execution.resolution.stagger.wound_requested)
        self.assertIs(proof.execution.resolution.attack.attacker_test.trace.quality, TestQuality.GRIM)
        self.assertIs(proof.request.kernel_request.fixed_character_wound.entry_id, WoundEntryId.DECAPITATION)
        wound = proof.execution.resolution.profile_wound
        self.assertEqual(wound.wounds_inflicted, 1)
        self.assertEqual(wound.state.defeat_cause,
            ProfileDecapitationCause(proof.request.kernel_request.id + ':wound', proof.request.target_id))
        ack = next(step.proof for step in result.steps if type(step.proof) is PcProfileWoundProof)
        self.assertIs(ack.decision.disposition, NpcDefeatDisposition.KILLED)
        self.assertTrue(all(decision.disposition is NpcDefeatDisposition.KNOCKED_OUT
            for member in source.party for decision in member.defeat_decisions))

    def test_npc_headsman_after_actual_bear_prone_decapitates_without_table_dice(self):
        source = npc_headsman_source()
        # One PC die + three failed Bear Protection dice, then actual Bear and
        # Headsman Tests. The fixed Wound consumes no 27+ sum or extra d10.
        rng = ScriptedD10([3] + [10] * 3 + [3] * 22)
        result = run_native(self, source, rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome, PcMeleeOutcome.PARTY_DEFEATED)
        strike = last_headsman_attack(result)
        self.assertEqual(strike.proof.request.actor_id, source.enemy_activation_order[1])
        self.assertTrue(strike.source.participant('pc').injury.conditions.has(Condition.PRONE))
        wound = strike.proof.execution.resolution.character_wound
        self.assertIs(type(wound.table_roll), FixedWoundTableSelection)
        self.assertEqual(wound.table_roll.values, ())
        self.assertEqual(wound.table_roll.dice, 0)
        record, = result.state.participant('pc').injury.wounds
        self.assertIs(record.entry_id, WoundEntryId.DECAPITATION)
        self.assertIs(record.origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(record.roll_values, ())
        self.assertEqual(result.state.participant('pc').daily_wounds.wound_count, 1)

    def test_player_near_miss_cancels_same_fixed_death_and_daily_registration(self):
        source = npc_headsman_source(near_miss=True)
        rng = ScriptedD10([3] + [10] * 3 + [3] * 22)
        result = run_native(self, source, rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        strike = last_headsman_attack(result)
        self.assertIs(type(strike.proof.execution.resolution.character_wound.table_roll), FixedWoundTableSelection)
        completion, = (step.proof.completion for step in result.steps
            if type(step.proof) is PcWoundCompletionProof)
        self.assertIs(completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertIs(completion.near_miss_application.cancelled_wound.entry_id, WoundEntryId.DECAPITATION)
        member = result.state.participant('pc')
        self.assertFalse(member.injury.dead)
        self.assertEqual(member.injury.wounds, ())
        self.assertEqual(member.daily_wounds.wound_count, 0)
        self.assertEqual(member.fate.rating, 0)

    def test_actual_prone_and_successful_headsman_first_stagger_do_not_invent_wound(self):
        source = npc_headsman_source()
        # Here the PC misses and is Staggered. The Bear's hit consumes that
        # second Staggered as a real superficial Wound; Headsman then adds the
        # next first Staggered to the still-Prone PC, causing no Decapitation.
        result = run_native(self, source, Threes())
        strike = last_headsman_attack(result)
        self.assertTrue(strike.proof.weapon_intent.magic_context.target_prone)
        self.assertIsNotNone(strike.proof.request.kernel_request.fixed_character_wound)
        self.assertIsNone(strike.proof.execution.resolution.character_wound)
        self.assertIsNone(strike.proof.execution.resolution.pending_character_wound)
        member = result.state.participant('pc')
        self.assertFalse(member.injury.dead)
        self.assertEqual(tuple(wound.entry_id for wound in member.injury.wounds),
            (WoundEntryId.SUPERFICIAL_INJURY,))


if __name__ == '__main__':
    unittest.main()
