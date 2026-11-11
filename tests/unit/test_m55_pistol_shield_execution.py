"""Literal Pistol/shield journals prove reload priority and actual equipment."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m54_pistol_execution import (
    NPC_HIT, NPC_MISS, SHOT_HIT, configured, execute, incoming, raw,
    scene as pistol_scene, shots, steps,
)
from towr.domain.attack_models import DamageProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.pc_heavy_wound_models import PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy, PcMeleeWeapon,
    PcNearMissPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcHandDropProof, PcHandSwapProof, PcHelpProof,
    PcMeleeOutcome, PcMeleeStep, PcRecoverProof,
)
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldReleaseProof
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step


def scene(*, rounds=1, enemies=1, durable=True, **kwargs):
    source = pistol_scene(rounds=rounds, enemies=enemies, durable=durable, **kwargs)
    party = tuple(replace(member, initial_weapon_hand=PcWeaponHand.RIGHT,
        shield=shield_loadout()) for member in source.party)
    # Strong authored blows guarantee one Wound when a scripted hit lands,
    # independently of the shield's actual +1 Resilience.
    enemies = tuple(replace(enemy, definition=replace(enemy.definition,
        attacks=tuple(replace(attack, damage=DamageProfile(10))
            for attack in enemy.definition.attacks))) for enemy in source.enemies)
    return replace(source, party=party, enemies=enemies)


def critical_sources(state):
    return tuple(effect.wound_sequence for effect in state.participant('pc1').injury.active_wound_effects
        if type(effect) is WoundConditionEffect and effect.condition is Condition.CRITICALLY_INJURED)


def book_scene(*, pc_count=1, **counts):
    source = book_pc_scenario(footpads=counts.pop('footpads', 0), townsfolk=0,
        pc_count=pc_count, max_rounds=1, **counts)
    pistol = scene().party[0].pc
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False),
        party=tuple(replace(member, pc=replace(pistol, id=member.pc.id),
            initial_weapon_hand=PcWeaponHand.RIGHT, shield=shield_loadout()) for member in source.party))


def recover_object(step):
    interaction = step.proof.result.source_request.choice.object_interaction
    return None if interaction is None else interaction.object_id


def heavy_hits(total, *, side=1):
    values = NPC_HIT + [1] + NPC_HIT + [1, 1] + NPC_HIT
    values += [1, 1, 10] if total == 12 else [10, 1, total-11]
    if total in (12, 16, 20):
        values += [side]
    if total == 12:
        values += [1, 10, 10]
    return values


class PcPistolShieldExecutionTests(unittest.TestCase):
    def test_full_cycle_reloads_before_distinct_shield_recover_and_next_shot(self):
        result = execute(scene(rounds=4), SHOT_HIT + NPC_MISS
            + [1, 1, 1] + NPC_MISS + NPC_MISS + SHOT_HIT + NPC_MISS)
        first, second = shots(result)
        release, = steps(result, PcShieldReleaseProof)
        reload, = steps(result, PcRangedReloadProof)
        recover, = steps(result, PcRecoverProof)
        self.assertEqual(tuple(step.source.round_state.round_number
            for step in (first, release, reload, recover, second)), (1, 2, 2, 3, 4))
        self.assertEqual(recover_object(recover), 'pc1:shield')
        self.assertIs(release.source.participant('pc1').shield.location, PcShieldLocation.HELD)
        self.assertIs(reload.source.participant('pc1').shield.location, PcShieldLocation.DROPPED)
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)
        self.assertIs(reload.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)
        self.assertIs(second.source.participant('pc1').shield.location, PcShieldLocation.HELD)
        self.assertEqual(recover.source.participant('pc1').ranged, recover.state.participant('pc1').ranged)
        self.assertEqual(result.executed_actions, 8)
        self.assertEqual(len(second.source.round_state.active_turn.action_slots), 1)
        self.assertEqual(tuple(raw(step).impact_spec.resilience.total for step in incoming(result)),
            (4, 3, 4, 4))
        self.assertEqual(tuple(raw(step).defender_test.trace.regular_dice_delta for step in incoming(result)),
            (0, 0, 0, 0))

    def test_partial_zero_and_overshoot_reload_never_pick_up_shield_between_tests(self):
        result = execute(scene(rounds=5, initiative=4), SHOT_HIT + NPC_MISS
            + [1, 10, 10, 10] + NPC_MISS + [10]*4 + NPC_MISS
            + [1]*4 + NPC_MISS + NPC_MISS)
        reloads = steps(result, PcRangedReloadProof)
        recover, = steps(result, PcRecoverProof)
        self.assertEqual(tuple(step.state.participant('pc1').ranged.exacting.accumulated_successes
            for step in reloads), (1, 1, 5))
        self.assertTrue(all(step.state.participant('pc1').shield.location is PcShieldLocation.DROPPED
            for step in reloads))
        self.assertEqual(len(steps(result, PcShieldReleaseProof)), 1)
        self.assertEqual(recover.source.round_state.round_number, 5)
        self.assertEqual(recover_object(recover), 'pc1:shield')
        self.assertEqual(len(shots(result)), 1)

    def test_prone_recover_precedes_release_and_does_not_incidentally_pick_up_empty_guns_shield(self):
        result = execute(scene(rounds=6), SHOT_HIT + NPC_HIT + [9]
            + NPC_MISS + [1, 10, 10] + NPC_HIT + [4, 5]
            + NPC_MISS + [1, 1, 1] + NPC_MISS + NPC_MISS)
        first, second, third = steps(result, PcRecoverProof)
        release, = steps(result, PcShieldReleaseProof)
        self.assertEqual(tuple(step.source.round_state.round_number
            for step in (first, release, second, third)), (2, 3, 4, 6))
        self.assertIs(first.source.participant('pc1').shield.location, PcShieldLocation.HELD)
        self.assertEqual((recover_object(first), recover_object(second), recover_object(third)),
            (None, None, 'pc1:shield'))
        self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(second.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(second.state.participant('pc1').ranged.loaded)
        self.assertIs(second.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_forced_drop_preserves_empty_gun_and_weapon_pickup_precedes_reload(self):
        result = execute(scene(rounds=4), SHOT_HIT + NPC_HIT + [8, 10]
            + NPC_MISS + [1, 1, 1] + NPC_MISS + NPC_MISS)
        pickup, shield = steps(result, PcRecoverProof)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual((recover_object(pickup), recover_object(shield)), ('pc1:weapon', 'pc1:shield'))
        self.assertEqual(tuple(step.source.round_state.round_number for step in (pickup, reload, shield)),
            (2, 3, 4))
        self.assertIs(pickup.state.participant('pc1').shield.location, PcShieldLocation.HELD)
        self.assertFalse(pickup.state.participant('pc1').ranged.loaded)
        self.assertEqual(pickup.source.participant('pc1').ranged, pickup.state.participant('pc1').ranged)
        self.assertEqual(len(steps(result, PcHandDropProof)), 1)

    def test_loaded_weapon_and_shield_drops_require_distinct_recovers_without_reload(self):
        # Both items fall after Reload has completed. The loaded gun is
        # recovered first, then the shield, without a second reload cycle.
        result = execute(scene(rounds=4, enemies=2), SHOT_HIT + NPC_MISS*2
            + [1, 1, 1] + NPC_HIT + [8, 10] + NPC_HIT + [4, 4, 1]
            + NPC_MISS*2 + NPC_MISS*2)
        recovers = steps(result, PcRecoverProof)
        self.assertEqual(tuple(recover_object(step) for step in recovers), ('pc1:weapon', 'pc1:shield'))
        self.assertTrue(all(step.source.participant('pc1').ranged.loaded for step in recovers))
        self.assertEqual(len(steps(result, PcRangedReloadProof)), 1)
        self.assertEqual(len(steps(result, PcShieldReleaseProof)), 1)

    def test_wound_twelve_reload_uses_injured_hand_but_does_not_restore_shield_to_it(self):
        result = execute(scene(rounds=2, enemies=3), SHOT_HIT + heavy_hits(12)
            + [1, 1, 1] + [1, 1, 1] + NPC_MISS*3)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual(critical_sources(reload.source), ())
        self.assertEqual(critical_sources(reload.state), (3,))
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)
        self.assertIs(reload.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)
        self.assertEqual(steps(result, PcRecoverProof), ())
        self.assertEqual(steps(result, PcShieldReleaseProof), ())
        self.assertIn(PcBodyFactKind.INJURED_HAND,
            tuple(f.kind for f in reload.state.participant('pc1').body_facts))

    def test_injured_weapon_hand_releases_shield_for_healthy_pickup_before_two_hand_reload(self):
        result = execute(scene(rounds=3, enemies=3), SHOT_HIT + heavy_hits(12, side=10)
            + NPC_MISS*3 + [1, 1, 1] + [1, 1, 1] + NPC_MISS*3)
        release, = steps(result, PcShieldReleaseProof)
        recover, = steps(result, PcRecoverProof)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual(recover_object(recover), 'pc1:weapon')
        self.assertEqual(tuple(step.source.round_state.round_number for step in (release, recover, reload)),
            (2, 2, 3))
        self.assertIs(recover.state.participant('pc1').weapon_hand, PcWeaponHand.LEFT)
        self.assertEqual(critical_sources(recover.state), ())
        self.assertEqual(critical_sources(reload.state), (3,))
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)
        self.assertIs(reload.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_reload_release_preserves_distinct_wound_fourteen_and_fifteen_critical_triggers(self):
        for total in (14, 15):
            with self.subTest(total=total):
                result = execute(scene(rounds=2, enemies=3), SHOT_HIT + heavy_hits(total)
                    + [1, 1, 1] + [1, 1, 1] + NPC_MISS*3)
                release, = steps(result, PcShieldReleaseProof)
                reload, = steps(result, PcRangedReloadProof)
                self.assertEqual(critical_sources(release.source), ())
                self.assertEqual(critical_sources(release.state), (3,) if total == 14 else ())
                self.assertEqual(critical_sources(reload.state), (3,))
                self.assertTrue(reload.state.participant('pc1').ranged.loaded)
                self.assertEqual(len(steps(result, PcRecoverProof)), 0)

    def test_loaded_one_hand_shot_survives_heavy_wound_until_actual_reload_boundary(self):
        for total in (16, 18):
            with self.subTest(total=total):
                result = execute(scene(rounds=5, enemies=3), SHOT_HIT + NPC_MISS*3
                    + [1, 1, 1] + NPC_MISS*3 + heavy_hits(total, side=10)
                    + SHOT_HIT + [1, 1, 1] + NPC_MISS*3)
                self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
                self.assertEqual(len(shots(result)), 2)
                self.assertEqual(len(steps(result, PcRangedReloadProof)), 1)
                self.assertEqual(result.unsupported.reason, 'ranged_reload_hands_unavailable')
                self.assertEqual(result.unsupported.table_total, total)
                self.assertEqual(result.state.round_state.round_number, 5)
                self.assertEqual(result.state.round_state.active_turn.action_slots, ())
                self.assertIn(result.state.participant('pc1').ranged.reload_cycle_id,
                    result.unsupported.source_id)
                last_shot = shots(result)[1]
                self.assertTrue(last_shot.source.participant('pc1').ranged.loaded)
                self.assertIs(last_shot.source.participant('pc1').shield.location, PcShieldLocation.DROPPED)
                if total == 16:
                    self.assertEqual(len(steps(result, PcHandSwapProof)), 1)
                    self.assertEqual(len(steps(result, PcShieldReleaseProof)), 2)

    def test_lost_shield_arm_is_unavailable_defenceless_without_ground_pickup(self):
        result = execute(scene(rounds=3, enemies=3), SHOT_HIT + NPC_MISS*3
            + [1, 1, 1] + NPC_MISS*3 + heavy_hits(20))
        member = result.state.participant('pc1')
        self.assertIs(member.shield.location, PcShieldLocation.UNAVAILABLE)
        self.assertIs(member.shield.hand, PcWeaponHand.LEFT)
        self.assertTrue(member.injury.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(tuple(recover_object(step) for step in steps(result, PcRecoverProof)), ('pc1:shield',))
        self.assertEqual(len(steps(result, PcShieldReleaseProof)), 1)

    def test_reload_fate_consumes_only_actual_dexterity_test_and_keeps_shield_dropped(self):
        source = configured(scene(rounds=3), (Skill.DEXTERITY,))
        result = execute(source, SHOT_HIT + NPC_MISS + [10]*3 + [1]*3 + NPC_MISS + NPC_MISS)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual(reload.proof.glorious.source_request.test, reload.proof.request.dexterity_test)
        self.assertIs(reload.proof.result.exacting.test_result.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(len(reload.state.participant('pc1').fate.spends), 1)
        self.assertEqual(len(reload.state.participant('pc1').ranged.exacting.contributions), 1)
        self.assertIs(reload.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_wound_ten_grim_is_consumed_by_reload_not_free_shield_release(self):
        result = execute(scene(rounds=3), SHOT_HIT + NPC_HIT + [10]
            + [1, 10, 10, 10] + NPC_MISS + [1, 1, 1] + NPC_MISS)
        release, = steps(result, PcShieldReleaseProof)
        first, second = steps(result, PcRangedReloadProof)
        self.assertEqual(release.source.participant('pc1').injury, release.state.participant('pc1').injury)
        self.assertIs(first.proof.result.exacting.test_result.trace.quality, TestQuality.GRIM)
        self.assertIs(second.proof.result.exacting.test_result.trace.quality, TestQuality.NORMAL)
        self.assertEqual(first.state.participant('pc1').ranged.exacting.accumulated_successes, 0)
        self.assertTrue(second.state.participant('pc1').ranged.loaded)

    def test_terminal_shot_does_not_release_reload_or_recover_shield(self):
        result = execute(scene(durable=False), SHOT_HIT)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions, 1)
        self.assertEqual(steps(result, PcShieldReleaseProof), ())
        self.assertEqual(steps(result, PcRangedReloadProof), ())
        self.assertEqual(steps(result, PcRecoverProof), ())
        self.assertIs(result.state.participant('pc1').shield.location, PcShieldLocation.HELD)

    def test_near_miss_cancels_wound_drop_before_any_shield_equipment_consequence(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0],
            fate_policy=PcFatePolicy.CONFIGURED, near_miss_policy=PcNearMissPolicy(8, 0)),))
        result = execute(source, SHOT_HIT + NPC_HIT + [8])
        member = result.state.participant('pc1')
        self.assertIs(member.shield.location, PcShieldLocation.HELD)
        self.assertIs(member.weapon_hand, PcWeaponHand.RIGHT)
        self.assertFalse(member.ranged.loaded)
        self.assertEqual(member.body_facts, ())
        self.assertEqual(steps(result, PcHandDropProof), ())
        self.assertEqual(steps(result, PcShieldReleaseProof), ())
        self.assertEqual(member.fate.rating, 2)

    def test_actual_net_defence_uses_shield_without_sword_trait_then_drop_selects_athletics(self):
        held = execute(book_scene(net_goblins=1), [10]*3 + [1]*3 + [10]*2 + [1]*3)
        attack, = incoming(held)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(raw(attack).defender_test.trace.regular_dice_delta, 0)
        self.assertIs(attack.source.participant('pc1').shield.location, PcShieldLocation.HELD)
        source = book_scene(net_goblins=1, footpads=1)
        source = replace(source, enemy_activation_order=('footpad1', 'net_goblin1'))
        dropped = execute(source, [10]*3 + [1]*3 + [1]*3 + [10]*3 + [8, 1]
            + [10]*2 + [1]*3)
        footpad, net = incoming(dropped)
        self.assertEqual(raw(footpad).impact_spec.resilience.total, 4)
        # Net has a Condition impact, so it has no numeric Resilience.
        self.assertIs(net.proof.protection.source_request.selected_skill, Skill.ATHLETICS)
        self.assertIs(net.source.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_protection_help_binds_pistol_owners_actual_shield_defence_against_net(self):
        source = book_scene(pc_count=2, net_goblins=1)
        helper = source.party[0]
        helper = replace(helper, pc=replace(helper.pc, weapon=PcMeleeWeapon.SWORD, ranged=None),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2', PcHelpTarget.FIRST_INCOMING_PROTECTION, Skill.DEFENCE))
        source = replace(source, party=(helper, source.party[1]), enemy_target_priority=('pc2', 'pc1'))
        result = execute(source, [1]*4 + [10]*3 + [1]*3 + [10]*2 + [1]*6)
        help_step, = steps(result, PcHelpProof)
        attack, = incoming(result)
        application, = attack.proof.help_applications
        self.assertEqual(application.source_request.help, help_step.proof.execution)
        self.assertEqual(attack.proof.request.target_id, 'pc2')
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(raw(attack).defender_test.trace.rolled_dice, 6)
        self.assertEqual(shots(result)[0].proof.help_applications, ())

    def test_shield_does_not_replace_trample_endurance_with_defence(self):
        source = book_scene(great_stags=1)
        source = replace(source, npc_extra_attack_actor_ids=('great_stag1',))
        result = execute(source, [10]*3 + [1]*5 + [1]*4 + [10]*3 + [9]
            + [10]*6 + [1]*3)
        _, trample = incoming(result)
        self.assertIs(trample.proof.protection.source_request.selected_skill, Skill.ENDURANCE)
        self.assertEqual(raw(trample).impact_spec.resilience.total, 4)
        self.assertEqual(raw(trample).defender_test.trace.rolled_dice, 3)

    def test_release_reload_pickup_reject_replay_aliases_and_forged_restoration(self):
        result = execute(scene(rounds=3), SHOT_HIT + NPC_MISS
            + [1, 1, 1] + NPC_MISS + NPC_MISS)
        release, = steps(result, PcShieldReleaseProof)
        reload, = steps(result, PcRangedReloadProof)
        recover, = steps(result, PcRecoverProof)
        for step in (release, reload, recover):
            self.assertEqual(apply_pc_melee_step(step.source, step), step.state)
            with self.assertRaises((TypeError, ValueError)):
                apply_pc_melee_step(step.state, step)
        for changes in ({'actor_id': 'other'}, {'hand': PcWeaponHand.RIGHT}, {'action_id': 'unrelated'}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                PcMeleeStep(release.source, replace(release.proof, **changes))
        forged = deepcopy(recover.proof)
        object.__setattr__(forged.result.source_request.choice.object_interaction, 'object_id', 'pc1:weapon')
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(recover.source, forged)
        following = result.steps[result.steps.index(reload)+1]
        member = following.source.participant('pc1')
        forged_source = replace(following.source, party=(replace(member,
            shield=recover.state.participant('pc1').shield),))
        with self.assertRaises((TypeError, ValueError)):
            apply_pc_melee_step(forged_source, PcMeleeStep(forged_source, following.proof))


if __name__ == '__main__':
    unittest.main()
