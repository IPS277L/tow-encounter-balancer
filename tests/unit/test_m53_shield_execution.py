"""Actual Shield journals bind protection, hand consequences, and one-item Recover."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_shield_scenarios import make_pc_shield_scenario, shield_loadout
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.pc_heavy_wound_models import PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon, PcNearMissPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBodyConsequenceProof, PcHandDropProof, PcHandSwapProof,
    PcHelpProof, PcMeleeStep, PcRecoverProof,
)
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldReleaseProof
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


PC_MISS = [10]*3+[1]*2
FIRST_HIT = [1]*2+[10]*3
LATER_HIT = [1]*2+[10]*4


def scene(*, enemies=1, rounds=1, **kwargs):
    source = make_pc_shield_scenario(enemy_count=enemies, max_rounds=rounds, **kwargs)
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False))


def book_scene(*, rounds=1, **counts):
    source = book_pc_scenario(footpads=counts.pop('footpads', 0), townsfolk=0,
        pc_count=counts.pop('pc_count', 1), max_rounds=rounds, **counts)
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False),
        party=tuple(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.SWORD),
            initial_weapon_hand=PcWeaponHand.RIGHT, shield=shield_loadout()) for member in source.party))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def incoming(result):
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.request.actor_id in result.source.enemy_activation_order)


def light_script(total, *, side=1, endurance_success=False):
    values = PC_MISS+FIRST_HIT+[total]
    if total == 4:
        values += [1, 10, 10] if endurance_success else [10]*3
    if total == 8 or total == 4 and not endurance_success:
        values += [side]
    return values


def heavy_script(total, *, side=1, endurance_success=True):
    # Three actual Wounds: superficial1, superficial2, then the heavy row.
    dice = [1, 1, total-2] if total <= 12 else [10, 1, total-11]
    values = PC_MISS+FIRST_HIT+[1]+LATER_HIT+[1, 1]+LATER_HIT+dice
    if total in (12, 16, 20):
        values += [side]
    if total == 12:
        values += [1, 10, 10] if endurance_success else [10]*3
    return values


def raw(step):
    return step.proof.execution.resolution.attack


class PcShieldExecutionTests(unittest.TestCase):
    def test_sword_trait_applies_to_actual_shield_defence_against_net(self):
        source = book_scene(net_goblins=1)
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc, strength=1)),))
        result = execute(source, [1, 10, 10]+[10]*3+[10]*2+[1]*4)
        attack, = incoming(result)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        trace = raw(attack).defender_test.trace
        self.assertEqual((trace.base_dice, trace.regular_dice_delta, trace.rolled_dice), (3, 1, 4))
        self.assertEqual(result.state.participant('pc1').shield.location, PcShieldLocation.HELD)

    def test_dropped_sword_retains_shield_defence_but_loses_sword_trait(self):
        source = book_scene(net_goblins=1, footpads=1)
        source = replace(source, enemy_activation_order=('footpad1', 'net_goblin1'))
        result = execute(source, [10]*3+[1]*3+[1]*3+[10]*3+[8, 10]+[10]*2+[1]*3)
        attack = incoming(result)[-1]
        member = attack.source.participant('pc1')
        self.assertIsNone(member.weapon_hand)
        self.assertIs(member.shield.location, PcShieldLocation.HELD)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(raw(attack).defender_test.trace.regular_dice_delta, 0)

    def test_dropped_shield_changes_actual_net_protection_to_athletics(self):
        source = book_scene(net_goblins=1, footpads=1)
        source = replace(source, enemy_activation_order=('footpad1', 'net_goblin1'))
        result = execute(source, [10]*3+[1]*3+[1]*3+[10]*3+[8, 1]+[10]*2+[1]*3)
        attack = incoming(result)[-1]
        self.assertIs(attack.source.participant('pc1').weapon_hand, PcWeaponHand.RIGHT)
        self.assertIs(attack.source.participant('pc1').shield.location, PcShieldLocation.DROPPED)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.ATHLETICS)

    def test_dynamic_resilience_uses_next_attack_without_rewriting_causing_hit(self):
        result = execute(scene(enemies=2), light_script(8)+[10]*2+[1]*4)
        first, second = incoming(result)
        self.assertEqual(raw(first).impact_spec.resilience.total, 4)
        self.assertTrue(raw(first).impact_spec.resilience.is_armoured)
        self.assertEqual(raw(first).effective_resilience, 4)
        self.assertEqual(raw(second).impact_spec.resilience.total, 3)
        self.assertFalse(raw(second).impact_spec.resilience.is_armoured)
        self.assertEqual(first.source.source.party[0].pc.armour_bonus, 0)

    def test_wound_eight_drops_only_item_in_actual_selected_hand(self):
        for side, hand in ((1, PcWeaponHand.LEFT), (10, PcWeaponHand.RIGHT)):
            with self.subTest(hand=hand):
                result = execute(scene(), light_script(8, side=side))
                drop, = steps(result, PcHandDropProof)
                self.assertIs(drop.proof.hand, hand)
                member = result.state.participant('pc')
                self.assertIs(member.shield.location,
                    PcShieldLocation.DROPPED if side == 1 else PcShieldLocation.HELD)
                self.assertEqual(member.weapon_hand, PcWeaponHand.RIGHT if side == 1 else None)
                self.assertEqual(member.shield.hand, None if side == 1 else PcWeaponHand.LEFT)

    def test_failed_wound_four_endurance_drops_selected_shield_or_weapon(self):
        for side in (1, 10):
            with self.subTest(side=side):
                result = execute(scene(), light_script(4, side=side))
                self.assertEqual(len(steps(result, PcHandDropProof)), 1)
                self.assertIs(result.state.participant('pc').shield.location,
                    PcShieldLocation.DROPPED if side == 1 else PcShieldLocation.HELD)

    def test_successful_wound_four_endurance_keeps_both_items(self):
        result = execute(scene(), light_script(4, endurance_success=True))
        self.assertEqual(steps(result, PcHandDropProof), ())
        self.assertIs(result.state.participant('pc').weapon_hand, PcWeaponHand.RIGHT)
        self.assertIs(result.state.participant('pc').shield.location, PcShieldLocation.HELD)

    def test_near_miss_prevents_light_drop_and_heavy_body_consequences(self):
        for total in (8, 12):
            source = scene(enemies=1 if total == 8 else 3)
            source = replace(source, party=(replace(source.party[0],
                fate_policy=PcFatePolicy.CONFIGURED, near_miss_policy=PcNearMissPolicy(total, 0)),))
            values = light_script(8)[:-1] if total == 8 else heavy_script(12)[:-4]
            with self.subTest(total=total):
                result = execute(source, values)
                member = result.state.participant('pc')
                self.assertIs(member.shield.location, PcShieldLocation.HELD)
                self.assertIs(member.weapon_hand, PcWeaponHand.RIGHT)
                self.assertEqual(steps(result, PcHandDropProof), ())
                self.assertEqual(member.body_facts, ())
                self.assertEqual(member.fate.rating, 2)

    def test_injured_shield_hand_is_not_used_for_pickup(self):
        result = execute(scene(enemies=3, rounds=2), heavy_script(12)
            +PC_MISS+([10]*2+[1]*3)*3)
        self.assertEqual(steps(result, PcRecoverProof), ())
        member = result.state.participant('pc')
        self.assertIs(member.shield.location, PcShieldLocation.DROPPED)
        self.assertFalse(member.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertIn(PcBodyFactKind.INJURED_HAND, tuple(f.kind for f in member.body_facts))

    def test_injured_weapon_hand_releases_shield_then_recovers_weapon_in_healthy_hand(self):
        result = execute(scene(enemies=3, rounds=2), heavy_script(12, side=10)
            +[10]*2+[1]*4+[10]*2+[1]*4+[10]*2+[1]*4)
        release, = steps(result, PcShieldReleaseProof)
        recover, = steps(result, PcRecoverProof)
        self.assertEqual(release.source.round_state.active_turn.actor_id, 'pc')
        self.assertIs(release.proof.hand, PcWeaponHand.LEFT)
        self.assertLess(result.steps.index(release), result.steps.index(recover))
        self.assertEqual(recover.proof.result.source_request.choice.object_interaction.object_id, 'pc:weapon')
        self.assertIs(recover.state.participant('pc').weapon_hand, PcWeaponHand.LEFT)
        self.assertIs(result.state.participant('pc').shield.location, PcShieldLocation.DROPPED)
        self.assertFalse(result.state.participant('pc').injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_free_shield_release_preserves_distinct_wound_fourteen_and_fifteen_action_triggers(self):
        for total, dice in ((14, [7, 7]), (15, [7, 8])):
            # W1, ongoing W14/15, then W12 in the weapon hand. Actual
            # Shield release precedes weapon Recover in the healthy left.
            values = (PC_MISS+FIRST_HIT+[1]+LATER_HIT+dice
                +[1]*2+[10]*3+[4, 4, 4, 10, 1, 10, 10]
                +[1]*3+([10]*2+[1]*3)*3)
            with self.subTest(total=total):
                result = execute(scene(enemies=3, rounds=2), values)
                release, = steps(result, PcShieldReleaseProof)
                recover, = steps(result, PcRecoverProof)
                def critical_sources(state):
                    return tuple(effect.wound_sequence
                        for effect in state.participant('pc').injury.active_wound_effects
                        if type(effect) is WoundConditionEffect
                        and effect.condition is Condition.CRITICALLY_INJURED)
                self.assertEqual(critical_sources(release.source), ())
                self.assertEqual(critical_sources(release.state), (2,) if total == 14 else ())
                self.assertEqual(critical_sources(recover.state), (2,))
                self.assertIs(recover.state.participant('pc').weapon_hand, PcWeaponHand.LEFT)

    def test_unusable_shield_arm_removes_protection_without_inventing_ground_pickup(self):
        result = execute(scene(enemies=4, rounds=2), heavy_script(16)+[10]*2+[1]*4
            +PC_MISS+[1]*3+([10]*2+[1]*3)*4)
        attack = incoming(result)[3]
        member = attack.source.participant('pc')
        self.assertIs(member.shield.location, PcShieldLocation.UNAVAILABLE)
        self.assertIs(member.shield.hand, PcWeaponHand.LEFT)
        self.assertEqual(raw(attack).impact_spec.resilience.total, 3)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(steps(result, PcShieldReleaseProof), ())
        self.assertEqual(steps(result, PcRecoverProof), ())
        self.assertIs(result.state.participant('pc').shield.location, PcShieldLocation.UNAVAILABLE)

    def test_unusable_weapon_arm_keeps_shield_until_own_turn_then_releases_and_swaps(self):
        result = execute(scene(enemies=4, rounds=2), heavy_script(16, side=10)
            +[10]*2+[1]*3+PC_MISS+[1]*3+([10]*2+[1]*3)*4)
        fourth = incoming(result)[3]
        self.assertIs(fourth.source.participant('pc').shield.location, PcShieldLocation.HELD)
        self.assertIs(fourth.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        release, = steps(result, PcShieldReleaseProof)
        swap, = steps(result, PcHandSwapProof)
        self.assertEqual(release.source.round_state.active_turn.actor_id, 'pc')
        self.assertEqual(release.source.round_state.round_number, 2)
        self.assertLess(result.steps.index(release), result.steps.index(swap))
        self.assertIs(result.state.participant('pc').weapon_hand, PcWeaponHand.LEFT)
        self.assertIs(result.state.participant('pc').shield.location, PcShieldLocation.DROPPED)
        for state in (fourth.source, release.state):
            with self.assertRaises((TypeError, ValueError)):
                PcMeleeStep(state, release.proof)
        for changes in ({'actor_id': 'other-pc'}, {'action_id': 'another-action'}, {'hand': PcWeaponHand.RIGHT}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                PcMeleeStep(release.source, replace(release.proof, **changes))

    def test_spilling_guts_drops_shield_to_clutch_without_third_hand_or_useless_recover(self):
        result = execute(scene(enemies=3, rounds=2), heavy_script(18)
            +PC_MISS+[1]*3+([10]*2+[1]*3)*3)
        member = result.state.participant('pc')
        self.assertIs(member.weapon_hand, PcWeaponHand.RIGHT)
        self.assertIs(member.shield.location, PcShieldLocation.DROPPED)
        clutch, = (fact for fact in member.body_facts if fact.kind is PcBodyFactKind.CLUTCH_STOMACH)
        self.assertIs(clutch.side, PcWeaponHand.LEFT)
        self.assertEqual(steps(result, PcRecoverProof), ())

    def test_lost_shield_arm_is_unavailable_and_defenceless_does_not_get_a_test(self):
        result = execute(scene(enemies=4), heavy_script(20)+[10]*2)
        attack = incoming(result)[-1]
        self.assertIs(attack.source.participant('pc').shield.location, PcShieldLocation.UNAVAILABLE)
        self.assertTrue(attack.source.participant('pc').injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(raw(attack).defender_test)
        self.assertIsNone(attack.proof.fate_decline)
        self.assertEqual(steps(result, PcShieldReleaseProof), ())

    def test_two_dropped_items_need_two_recovers_with_weapon_first_and_extra_shield_recover(self):
        # Both first-round Wounds drop one item. Round2 picks up weapon and
        # removes Staggered; round3 spends a distinct action solely on shield.
        result = execute(scene(enemies=2, rounds=3), light_script(8)
            +LATER_HIT+[4, 4, 10]
            +[10]*2+[1]*4+[10]*2+[1]*4
            +[10]*2+[1]*4+[10]*2+[1]*4)
        first, second = steps(result, PcRecoverProof)
        self.assertEqual(first.proof.result.source_request.choice.object_interaction.object_id, 'pc:weapon')
        self.assertEqual(second.proof.result.source_request.choice.object_interaction.object_id, 'pc:shield')
        self.assertIs(first.state.participant('pc').weapon_hand, PcWeaponHand.RIGHT)
        self.assertIs(first.state.participant('pc').shield.location, PcShieldLocation.DROPPED)
        self.assertFalse(second.source.participant('pc').injury.conditions.has(Condition.STAGGERED))
        self.assertIsNone(second.proof.result.source_request.choice.staggered_target)
        self.assertIs(second.state.participant('pc').shield.location, PcShieldLocation.HELD)
        self.assertEqual((first.source.round_state.round_number, second.source.round_state.round_number), (2, 3))

    def test_standard_recover_returns_shield_and_preserves_net_cause(self):
        source = book_scene(rounds=2, net_goblins=1, footpads=1)
        source = replace(source, enemy_activation_order=('footpad1', 'net_goblin1'))
        result = execute(source, [10]*3+[1]*3+[1]*3+[10]*3+[8, 1]+[1]*2+[10]*3
            +[10]*3+[1]*4+[10]*2+[1]*4)
        recover, = steps(result, PcRecoverProof)
        before, after = recover.source.participant('pc1'), recover.state.participant('pc1')
        self.assertEqual(recover.proof.result.source_request.choice.object_interaction.object_id, 'pc1:shield')
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(after.net_condition_sources, before.net_condition_sources)
        self.assertFalse(after.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(after.injury.wounds, before.injury.wounds)

    def test_drained_removes_sword_bonus_from_actual_shield_net_defence(self):
        source = book_scene(net_goblins=1, footpads=1)
        source = replace(source, enemy_activation_order=('footpad1', 'net_goblin1'))
        result = execute(source, [10]*3+[1]*3+[1]*3+[10]*3+[10]+[10]*2+[1]*6)
        attack = incoming(result)[-1]
        self.assertTrue(attack.source.participant('pc1').injury.conditions.has(Condition.DRAINED))
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(raw(attack).defender_test.trace.regular_dice_delta, 0)

    def test_help_binds_actual_shield_defence_against_net(self):
        source = book_scene(net_goblins=1, pc_count=2)
        source = replace(source, enemy_target_priority=('pc2', 'pc1'), party=(replace(source.party[0],
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2', PcHelpTarget.FIRST_INCOMING_PROTECTION, Skill.DEFENCE)), source.party[1]))
        result = execute(source, [1]*4+[10]*3+[1]*3+[10]*2+[1]*6)
        helper, = steps(result, PcHelpProof)
        attack, = incoming(result)
        application, = attack.proof.help_applications
        self.assertEqual(application.source_request.help, helper.proof.execution)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(raw(attack).defender_test.trace.rolled_dice, 6)

    def test_glorious_uses_actual_defence_fate_window_against_net(self):
        source = book_scene(net_goblins=1)
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc, strength=1), fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.DEFENCE,), 0, 0)),))
        result = execute(source, [1, 10, 10]+[10]*3+[1]*2+[10]*4+[1]*4)
        attack, = incoming(result)
        self.assertIsNotNone(attack.proof.glorious)
        self.assertEqual(len(result.state.participant('pc1').fate.spends), 1)
        self.assertEqual(raw(attack).defender_test.successes, 4)

    def test_shield_does_not_change_brawn_trample_endurance_skill(self):
        source = book_scene(great_stags=1)
        source = replace(source, npc_extra_attack_actor_ids=('great_stag1',))
        result = execute(source, [10]*3+[1]*5+[1]*4+[10]*3+[9]+[10]*6+[1]*3)
        _, trample = incoming(result)
        self.assertIs(trample.proof.protection.source_request.selected_skill, Skill.ENDURANCE)
        self.assertEqual(raw(trample).defender_test.trace.rolled_dice, 3)
        self.assertEqual(raw(trample).impact_spec.resilience.total, 4)

    def test_drop_and_pickup_receipts_reject_replay_and_equal_string_aliases(self):
        result = execute(scene(rounds=2), light_script(8)+[10]*2+[1]*4)
        for step in (*steps(result, PcHandDropProof), *steps(result, PcRecoverProof)):
            with self.subTest(proof=type(step.proof).__name__):
                self.assertEqual(apply_pc_melee_step(step.source, step), step.state)
                with self.assertRaises((TypeError, ValueError)):
                    apply_pc_melee_step(step.state, step)
        recover, = steps(result, PcRecoverProof)
        class IdAlias(str):
            pass
        forged = deepcopy(recover.proof)
        object.__setattr__(forged.result.source_request.choice.object_interaction, 'object_id', IdAlias('pc:shield'))
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(recover.source, forged)
        drop, = steps(result, PcHandDropProof)
        forged = deepcopy(drop.proof)
        object.__setattr__(forged, 'hand', 'left')
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(drop.source, forged)
        # Raw frozen snapshots also serve pure preparation tests. Actual
        # admission must reconstruct the prefix before accepting a step.
        following = result.steps[result.steps.index(drop)+1]
        original = following.source.participant('pc')
        forged_source = replace(following.source, party=(replace(original,
            shield=recover.state.participant('pc').shield),))
        forged_step = PcMeleeStep(forged_source, following.proof)
        with self.assertRaises((TypeError, ValueError)):
            apply_pc_melee_step(forged_source, forged_step)


if __name__ == '__main__':
    unittest.main()
