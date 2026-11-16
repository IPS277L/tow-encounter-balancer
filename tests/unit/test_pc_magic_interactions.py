"""Actual Casting/Recover/Fate/injury interactions and explicit query snapshots."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_shield_scenarios import shield_loadout
from tests.support.pc_tactics_fixtures import tactical_snapshot
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (CharacterInjuryState, WoundRecord, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect, WoundConditionEffect, WoundEffectDuration)
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_magic_models import (PcCastingProof, PcMagicInterruptionProof, PcMagicCleanupProof,
    PcMiscastRollProof, PcMagicTaskKind, magic_hand, build_pc_casting_request, consume_magic_modifiers)
from towr.domain.pc_melee_models import (PcFatePolicy, PcGloriousPolicy, PcWeaponHand,
    PcMeleeWeapon, PcTwoHandedGrip, PcBackupWeaponPolicy)
from towr.domain.pc_melee_result_models import (PcAttackProof, PcRecoverProof, PcMeleeStep,
    PcBackupWeaponDrawProof, _pc_test)
from towr.domain.pc_potion_models import PcPotionRecoverProof
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def run_literal(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def with_healing(source):
    return replace(source,party=(replace(source.party[0],consumables=(
        ConsumableItem('healing',ConsumableKind.HEALING,1,None),)),*source.party[1:]))


class PcMagicInteractionTests(unittest.TestCase):
    def test_actual_recover_reduces_pool_then_one_skipped_casting_die_restores_it(self):
        # First Casting fails with one locked9. Two incoming hits cause Prone5;
        # its real Endurance fails, forcing a standard Recover on turn2.
        source = magic_scenario(rounds=2)
        values = [9,10]+[1,10]+[1,10,5]+[10]*10+[10]*4
        result = run_literal(source, values)
        recover = next(step for step in result.steps if type(step.proof) is PcRecoverProof)
        skipped = tuple(step for step in result.steps if type(step.proof) is PcMagicInterruptionProof)
        self.assertEqual(len(skipped),1)
        self.assertEqual(recover.source.party[0].magic.miscast_dice,1)
        self.assertEqual(recover.state.party[0].magic.miscast_dice,0)
        self.assertEqual(skipped[0].proof.result.source.amount,1)
        self.assertEqual(skipped[0].state.party[0].magic.miscast_dice,1)
        self.assertEqual(skipped[0].state.party[0].magic.casting_lore_id,'elementalism')
        self.assertEqual(skipped[0].state.party[0].magic.casting_successes,0)
        self.assertFalse(result.state.party[0].injury.conditions.has(Condition.PRONE))

    def test_potion_recover_is_also_one_skipped_casting_action_not_a_free_reset(self):
        source = with_healing(magic_scenario(rounds=2))
        result = run_literal(source,[9,10]+[1,10]+[1,10,6]+[10]*4)
        potion = next(step for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        skipped = tuple(step for step in result.steps if type(step.proof) is PcMagicInterruptionProof)
        self.assertEqual(len(skipped),1)
        self.assertTrue(potion.proof.after.injury.wounds[0].healed)
        self.assertEqual(potion.proof.after.magic.miscast_dice,0)
        self.assertEqual(skipped[0].state.party[0].magic.miscast_dice,1)
        self.assertEqual(skipped[0].state.party[0].magic.casting_lore_id,'elementalism')
        self.assertEqual(potion.proof.after.potions,())

    def test_defenceless_turn_without_slot_still_skips_once_and_resolves_actual_miscast(self):
        source = magic_scenario(enemies=6,rounds=2)
        values = ([9,10]+[1,10]+[1,10,1]+[1,10]+[1,10,1,1]+[1,10]
            +[1,10,10,10,2]+[1,1]+[1]*10+[10]*6)
        result = run_literal(source, values)
        skipped = tuple(step for step in result.steps if type(step.proof) is PcMagicInterruptionProof)
        self.assertEqual(len(skipped),1)
        self.assertEqual(skipped[0].source.round_state.active_turn.action_slots,())
        self.assertTrue(skipped[0].source.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertTrue(skipped[0].proof.source_action_id.endswith(':incapacitated'))
        self.assertEqual(sum(type(step.proof) is PcMiscastRollProof for step in result.steps),1)
        self.assertEqual(result.state.party[0].magic.miscast_dice,0)
        self.assertIsNone(result.state.party[0].magic.casting_lore_id)

    def test_armour_shield_and_worn_helmet_are_grim_but_fate_cannot_reroll_nine(self):
        for equipment in ('armour','shield','helmet'):
            source = magic_scenario(willpower=5,armour=int(equipment=='armour'))
            member = source.party[0]
            member = replace(member,fate=replace(member.fate,rating=1,session_spend_limit=1),
                fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.WILLPOWER,),2,0))
            if equipment == 'shield':
                member = replace(member,shield=shield_loadout(PcWeaponHand.RIGHT))
            elif equipment == 'helmet':
                member = replace(member,wizard=replace(member.wizard,armour_worn=True))
            source = replace(source,party=(member,))
            with self.subTest(equipment=equipment):
                result = run_literal(source,[1,9]+[10]*4)
                cast = next(step.proof for step in result.steps if type(step.proof) is PcCastingProof)
                self.assertTrue(any(q.quality is TestQuality.GRIM
                    for q in cast.request.casting_request.test.quality_modifiers))
                self.assertIsNotNone(cast.glorious)
                self.assertTrue(any(q.quality is TestQuality.GLORIOUS for q in cast.glorious.test.quality_modifiers))
                self.assertEqual(cast.execution.casting.test.trace.initial_values,(1,9))
                self.assertEqual(cast.execution.casting.test.trace.final_values,(1,9))
                self.assertEqual(cast.execution.casting.test.trace.rerolls,())
                self.assertEqual(result.state.party[0].magic.miscast_dice,1)
                self.assertEqual(result.state.party[0].fate.remaining_spends,0)

    def test_stench_next_test_penalties_are_consumed_by_actual_pc_and_npc_tests_only(self):
        result = run_literal(magic_scenario(),[9,9,6,7]+[10]*4)
        first = next(step for step in result.steps if type(step.proof) is PcAttackProof)
        before = tuple(modifier for modifier in first.source.magic_modifiers
            if modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY)
        self.assertEqual(tuple(modifier.target_id for modifier in before),('pc1','minion1','minion2'))
        self.assertEqual(consume_magic_modifiers(first.source.magic_modifiers,PcMagicCleanupProof('query-only')),
            first.source.magic_modifiers)
        self.assertEqual(tuple(modifier.target_id for modifier in first.state.magic_modifiers
            if modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY),('minion2',))
        self.assertFalse(any(modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY for modifier in result.state.magic_modifiers))
        self.assertEqual(tuple(modifier.target_id for modifier in result.state.magic_modifiers
            if modifier.kind is PcMagicTaskKind.FELLOWSHIP_GRIM),('pc1',))

    def test_daylight_blindness_survives_healing_or_expiry_of_an_independent_wound(self):
        prefix = [9,9,9,10]+[1,10]+[1,10,7]+[10]*10
        for healing in (False,True):
            source = magic_scenario(rounds=2)
            if healing:
                source = with_healing(source)
            values = prefix+([10,10] if not healing else [])+[10]*4
            with self.subTest(healing=healing):
                result = run_literal(source,values)
                self.assertTrue(result.state.party[0].injury.conditions.has(Condition.BLINDED))
                self.assertTrue(any(modifier.kind is PcMagicTaskKind.BLINDED for modifier in result.state.magic_modifiers))
                self.assertEqual(result.state.party[0].timed_wounds,())
                self.assertEqual(result.state.party[0].injury.wounds[0].healed,healing)
                self.assertFalse(any(q.quality is TestQuality.GRIM for q in
                    _pc_test(result.state,'pc1','mental-query',Skill.WILLPOWER).quality_modifiers))
                self.assertTrue(any(q.quality is TestQuality.GRIM for q in
                    _pc_test(result.state,'pc1','physical-query',Skill.MELEE).quality_modifiers))

    def test_wind_prone_survives_healing_when_wound_prone_blocked_standard_removal(self):
        source = with_healing(magic_scenario(reason=3,level=2,enemies=6,rounds=2))
        # Wind21 makes everyone Prone. Six hits then produce wounds1,2,17;
        # the ongoing17source prevents standard Recover from removing Prone.
        values = ([9]*3+[7]*3+[1,1,10]+[1,1,10,1]+[1,1,10]
            +[1,1,10,1,1]+[1,1,10]+[1,1,10,10,1,6]+[10]*18)
        result = run_literal(source,values)
        potion = next(step.proof for step in result.steps if type(step.proof) is PcPotionRecoverProof)
        self.assertIsNone(potion.result.source_request.choice.prone_target)
        self.assertTrue(potion.after.injury.wounds[-1].healed)
        self.assertTrue(potion.after.injury.conditions.has(Condition.PRONE))
        self.assertTrue(any(modifier.target_id == 'pc1' and modifier.kind is PcMagicTaskKind.PRONE
            for modifier in result.state.magic_modifiers))

    def test_actual_casting_with_only_injured_hand_retains_its_critical_source(self):
        source = magic_scenario(enemies=8,rounds=3)
        # Wound12left, failed finger-save, then Wound16right. Recover picks up
        # the Staff using the only remaining, injured hand; turn3 truly casts.
        values = ([10,10]+[1,10]+[1,10,1]+[1,10]+[1,10,1,1]+[1,10]
            +[1,10,1,1,10,1]+[10]*10+[1]+[10]*3+[1]+[10]*3+[4]*4+[10]
            +[1]*10+[10]*16+[1,1]+[1]*10+[10]*12)
        result = run_literal(source,values)
        cast = next(step for step in result.steps if type(step.proof) is PcCastingProof
            and step.source.round_state.round_number == 3)
        self.assertIs(magic_hand(cast.source,'pc1'),PcWeaponHand.LEFT)
        self.assertTrue(any(effect.wound_sequence == 3 and isinstance(effect,WoundConditionEffect)
            and effect.condition is Condition.CRITICALLY_INJURED
            for effect in cast.state.party[0].injury.active_wound_effects))

    def test_preparation_only_hand_queries_prefer_healthy_and_reject_no_usable_hand(self):
        # These are query snapshots, deliberately not invented native journals.
        state = tactical_snapshot(magic_scenario())
        injury = CharacterInjuryState((
            WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),
            WoundRecord(2,WoundEntryId.SLASHED_FOREARMS,16,(8,8),effect_resolved=True)),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_TREATED),))
        member = replace(state.party[0],injury=injury,
            body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),))
        state = replace(state,party=(member,))
        self.assertIs(magic_hand(state,'pc1'),PcWeaponHand.RIGHT)
        member = replace(member,body_facts=(*member.body_facts,
            PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,2,PcWeaponHand.RIGHT)))
        self.assertIs(magic_hand(replace(state,party=(member,)),'pc1'),PcWeaponHand.LEFT)
        injury = replace(injury,wounds=(*injury.wounds,
            WoundRecord(3,WoundEntryId.SEVERED_ARM,20,(10,10),effect_resolved=True)))
        member = replace(member,injury=injury,body_facts=(*member.body_facts,
            PcBodyFact(PcBodyFactKind.LOST_ARM,3,PcWeaponHand.LEFT)))
        unavailable = replace(state,party=(member,))
        self.assertIsNone(magic_hand(unavailable,'pc1'))
        with self.assertRaises(ValueError):
            build_pc_casting_request(unavailable)

    def test_one_healthy_hand_can_cast_after_two_handed_grip_becomes_unavailable(self):
        # Six attacks give wounds1,2,16 and disable the left arm. Wound16
        # leaves the caster able to act: Wound20 would additionally require
        # resolving its actual Defenceless cause before ordinary Casting.
        values = ([10,10]+[1,10]+[1,10,1]+[1,10]+[1,10,1,1]+[1,10]
            +[1,10,10,1,5,1]+[1,1]+[1]*10+[10]*24)
        for backup in (None,PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.RIGHT)):
            source = magic_scenario(enemies=6,rounds=2)
            member = source.party[0]
            source = replace(source,party=(replace(member,
                pc=replace(member.pc,weapon=PcMeleeWeapon.HALBERD),
                initial_weapon_hand=PcTwoHandedGrip.BOTH,backup_weapon_policy=backup),))
            with self.subTest(backup=backup):
                result = run_literal(source,values)
                cast = next(step for step in result.steps if type(step.proof) is PcCastingProof
                    and step.source.round_state.round_number == 2)
                self.assertIsNone(result.unsupported)
                self.assertIs(magic_hand(cast.source,'pc1'),PcWeaponHand.RIGHT)
                self.assertIs(cast.source.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
                self.assertFalse(result.state.party[0].using_backup_weapon)
                self.assertFalse(any(type(step.proof) is PcBackupWeaponDrawProof for step in result.steps))

    def test_native_cast_pending_and_full_proof_cannot_be_forged_or_replayed(self):
        result = run_literal(magic_scenario(),[1,1]+[10]*4)
        cast = next(step for step in result.steps if type(step.proof) is PcCastingProof)
        self.assertEqual(apply_pc_melee_step(cast.source,cast),cast.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(cast.state,cast)
        forged = deepcopy(cast.proof)
        object.__setattr__(forged.execution.casting.state,'casting_successes',True)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(cast.source,forged)
        following = result.steps[result.steps.index(cast)+1]
        pending = replace(cast.state.magic_pending,tasks=tuple(reversed(cast.state.magic_pending.tasks)))
        altered = replace(cast.state,magic_pending=pending)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(altered,following)


if __name__ == '__main__':
    unittest.main()
