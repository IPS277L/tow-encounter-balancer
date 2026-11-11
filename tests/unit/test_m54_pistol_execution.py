"""Literal native Pistol journals prove ammunition, Exacting actions, and hands."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import with_pc_melee_brute
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from towr.domain.attack_models import AttackOutcome, MissConsequence, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcHandDropProof, PcHelpProof, PcMeleeOutcome, PcMeleeStep,
    PcRecoverProof,
)
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import CombatActionKind, ImproviseKind
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


SHOT_HIT = [1, 1, 1, 10, 10]
SHOT_MISS = [10, 10, 10, 1, 1]
NPC_MISS = [10, 10, 1, 1, 1]
NPC_HIT = [1, 1, 10, 10, 10]


def scene(*, rounds=1, enemies=1, durable=False, **kwargs):
    source = make_pc_pistol_scenario(enemy_count=enemies, max_rounds=rounds, **kwargs)
    source = replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False))
    if durable:
        for actor in source.enemy_activation_order:
            source = with_pc_melee_brute(source, actor, wound_limit=20)
    return source


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.ranged_shot is not None)


def incoming(result):
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.request.actor_id in result.source.enemy_activation_order)


def raw(step):
    return step.proof.execution.resolution.attack


def configured(source, skills):
    return replace(source, party=tuple(replace(member, fate_policy=PcFatePolicy.CONFIGURED,
        glorious_policy=PcGloriousPolicy(skills, 0, 0)) for member in source.party))


class PcPistolExecutionTests(unittest.TestCase):
    def test_loaded_close_hit_consumes_real_instance_and_terminal_needs_no_reload(self):
        result = execute(scene(), SHOT_HIT)
        shot, = shots(result)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertIs(raw(shot).outcome, AttackOutcome.HIT)
        self.assertTrue(shot.source.participant('pc1').ranged.loaded)
        self.assertFalse(shot.state.participant('pc1').ranged.loaded)
        self.assertEqual(shot.state.participant('pc1').ranged.weapon_instance_id, 'pc1:weapon')
        self.assertIs(shot.state.participant('pc1').ranged.weapon_id, RangedWeaponId.PISTOL)
        self.assertEqual(steps(result, PcRangedReloadProof), ())
        self.assertEqual(result.executed_actions, 1)
        preparation = shot.proof.ranged_shot.preparation
        self.assertIs(preparation.source_request.target_range, RangedWeaponRange.CLOSE)
        self.assertTrue(preparation.source_request.has_enemy_in_close_range)
        self.assertIs(shot.proof.protection.source_request.selected_skill, Skill.ATHLETICS)
        # Keep the NPC's authored choice: a real shield also makes its
        # already supplied Defence lawful against the same Close shot.
        source = scene()
        enemy = source.enemies[0]
        shield_resilience = replace(enemy.definition.resilience,
            bonus=enemy.definition.resilience.bonus+1)
        source = replace(source, enemies=(replace(enemy,
            definition=replace(enemy.definition, resilience=shield_resilience,protection=(replace(
                enemy.definition.protection[0], skill=Skill.DEFENCE),)),
            state=replace(enemy.state, current_resilience=shield_resilience,holds_shield=True)),))
        shield_result = execute(source, SHOT_HIT)
        shield_shot, = shots(shield_result)
        self.assertTrue(shield_shot.source.enemy('minion1').state.holds_shield)
        self.assertIs(shield_shot.proof.protection.source_request.selected_skill, Skill.DEFENCE)

    def test_close_miss_consumes_ammunition_and_staggers_its_actual_owner(self):
        result = execute(scene(), SHOT_MISS + NPC_MISS)
        shot, = shots(result)
        self.assertIs(raw(shot).outcome, AttackOutcome.MISS)
        self.assertIs(raw(shot).miss_consequence, MissConsequence.STAGGER_ATTACKER)
        self.assertFalse(result.state.participant('pc1').ranged.loaded)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.state.participant('pc1').ranged.exacting.accumulated_successes, 0)
        self.assertEqual(shot.proof.help_applications, ())

    def test_damage_five_ignores_actual_armour_without_mutating_resilience(self):
        source = scene()
        enemy = source.enemies[0]
        resilience = ResilienceProfile(3, 9)
        source = replace(source, enemies=(replace(enemy,
            definition=replace(enemy.definition, resilience=resilience),
            state=replace(enemy.state, current_resilience=resilience)),))
        result = execute(source, SHOT_HIT)
        shot, = shots(result)
        impact = raw(shot).impact_spec
        self.assertEqual(impact.damage.base, 5)
        self.assertTrue(impact.ignores_armour)
        self.assertEqual(impact.resilience, resilience)
        self.assertEqual(result.source.enemies[0].definition.resilience, resilience)
        self.assertIn('RULE-EQUIPMENT-004:ignores-armour',
            shot.proof.ranged_shot.preparation.applied_rule_ids)

    def test_shooting_uses_authored_bs_skill_and_no_melee_advantage(self):
        source = scene(ballistic_skill=2, shooting=6, pc_count=2)
        source = replace(source, facts=replace(source.facts,
            outnumbering_bonus_approved=True))
        result = execute(source, [1, 1, 10, 10])
        shot, = shots(result)
        test = raw(shot).attacker_test
        self.assertEqual((test.trace.rolled_dice, test.trace.threshold), (2, 6))
        self.assertEqual(test.trace.regular_dice_delta, 0)
        self.assertEqual(shot.proof.ranged_shot.execution.source_request.attack_skill, Skill.SHOOTING)

    def test_prone_target_penalizes_shooting_instead_of_granting_melee_bonus(self):
        source = book_pc_scenario(footpads=0, townsfolk=0, centigors=1,
            pc_count=2, max_rounds=1)
        pistol = scene().party[0].pc
        source = replace(source, party=tuple(replace(member, pc=replace(pistol,
            id=member.pc.id)) for member in source.party),
            facts=replace(source.facts, outnumbering_bonus_approved=False))
        result = execute(source, [1]*3 + [10]*4 + [1]*2 + [10]*4)
        first, shot = shots(result)
        self.assertTrue(shot.source.enemy('centigor1').state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(raw(shot).attacker_test.trace.rolled_dice, 2)
        self.assertEqual(raw(shot).attacker_test.trace.regular_dice_delta, -1)

    def test_reload_zero_partial_failure_and_completion_each_cost_one_action(self):
        source = scene(rounds=5, durable=True)
        result = execute(source, SHOT_HIT + NPC_MISS
            + [10, 10, 10] + NPC_MISS
            + [1, 1, 10] + NPC_MISS
            + [10, 10, 10] + NPC_MISS
            + [1, 10, 10] + NPC_MISS)
        reloads = steps(result, PcRangedReloadProof)
        self.assertEqual(len(shots(result)), 1)
        self.assertEqual(tuple(step.state.participant('pc1').ranged.exacting.accumulated_successes
            for step in reloads), (0, 2, 2, 3))
        self.assertEqual(tuple(step.state.participant('pc1').ranged.loaded for step in reloads),
            (False, False, False, True))
        self.assertEqual(result.executed_actions, 10)
        cycle = shots(result)[0].state.participant('pc1').ranged.reload_cycle_id
        self.assertTrue(all(step.state.participant('pc1').ranged.reload_cycle_id == cycle for step in reloads))
        for index, step in enumerate(reloads, 1):
            proof = step.proof
            self.assertEqual(len(proof.result.state.exacting.contributions), index)
            self.assertIs(proof.result.slot.declaration.kind, CombatActionKind.IMPROVISE)
            self.assertIs(proof.result.slot.declaration.improvise_kind, ImproviseKind.SKILL)
            self.assertTrue(proof.result.slot.executed)
            self.assertEqual(proof.result.exacting.test_result.trace.rolled_dice, 3)

    def test_completed_reload_fires_only_next_turn_and_opens_fresh_cycle(self):
        result = execute(scene(rounds=3, durable=True), SHOT_HIT + NPC_MISS
            + [1, 1, 1] + NPC_MISS + SHOT_HIT + NPC_MISS)
        first, second = shots(result)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual((first.source.round_state.round_number,
            reload.source.round_state.round_number, second.source.round_state.round_number), (1, 2, 3))
        self.assertEqual(result.executed_actions, 6)
        pistol = result.state.participant('pc1').ranged
        self.assertFalse(pistol.loaded)
        self.assertEqual(len(pistol.reload_cycle_ids), 2)
        self.assertNotEqual(*pistol.reload_cycle_ids)
        self.assertEqual(pistol.exacting.contributions, ())

    def test_reload_overshoot_retains_actual_successes_and_uses_initiative(self):
        result = execute(scene(rounds=2, durable=True, initiative=4, dexterity=6),
            SHOT_HIT + NPC_MISS + [6, 6, 6, 6] + NPC_MISS)
        reload, = steps(result, PcRangedReloadProof)
        test = reload.proof.result.exacting.test_result
        self.assertEqual((test.trace.rolled_dice, test.trace.threshold), (4, 6))
        self.assertEqual(reload.state.participant('pc1').ranged.exacting.accumulated_successes, 4)
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)

    def test_shooting_glorious_spends_current_fate_before_only_reroll(self):
        result = execute(configured(scene(), (Skill.SHOOTING,)),
            [10, 10, 10, 1, 1, 1, 10, 10])
        shot, = shots(result)
        test = raw(shot).attacker_test
        self.assertEqual((test.trace.initial_values, test.trace.final_values),
            ((10, 10, 10), (1, 1, 1)))
        self.assertIs(test.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(shot.proof.glorious.source_request.test,
            shot.proof.request.kernel_request.attack.attacker_test)
        self.assertEqual(len(result.state.participant('pc1').fate.spends), 1)
        self.assertIsNone(shot.proof.fate_decline)

    def test_reload_glorious_and_decline_bind_the_actual_dexterity_test(self):
        source = scene(rounds=2, durable=True)
        declined = execute(source, SHOT_HIT + NPC_MISS + [10, 10, 10] + NPC_MISS)
        active = execute(configured(source, (Skill.DEXTERITY,)),
            SHOT_HIT + NPC_MISS + [10, 10, 10, 1, 1, 1] + NPC_MISS)
        decline, = steps(declined, PcRangedReloadProof)
        reload, = steps(active, PcRangedReloadProof)
        self.assertIsNotNone(decline.proof.fate_decline)
        self.assertIsNone(decline.proof.glorious)
        self.assertEqual(reload.proof.glorious.source_request.test, reload.proof.request.dexterity_test)
        self.assertEqual(reload.proof.result.exacting.test_result.trace.initial_values, (10, 10, 10))
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)
        self.assertEqual(len(reload.state.participant('pc1').fate.spends), 1)
        self.assertEqual(len(reload.state.participant('pc1').ranged.exacting.contributions), 1)

    def test_shot_and_reload_reject_replay_missing_proof_alias_and_forged_refill(self):
        result = execute(scene(rounds=2, durable=True), SHOT_HIT + NPC_MISS
            + [1, 1, 1] + NPC_MISS)
        shot, = shots(result)
        reload, = steps(result, PcRangedReloadProof)
        for step in (shot, reload):
            self.assertEqual(apply_pc_melee_step(step.source, step), step.state)
            with self.assertRaises((TypeError, ValueError)):
                apply_pc_melee_step(step.state, step)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(shot.source, replace(shot.proof, ranged_shot=None))
        class IdAlias(str):
            pass
        forged = deepcopy(reload.proof)
        object.__setattr__(forged.request.weapon_state, 'weapon_instance_id', IdAlias('pc1:weapon'))
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(reload.source, forged)
        # Shape-valid raw snapshots cannot admit an ammunition reset without
        # rebuilding the actual history that consumed the loaded Pistol.
        following = result.steps[result.steps.index(shot) + 1]
        member = following.source.participant('pc1')
        forged_source = replace(following.source, party=(replace(member,
            ranged=shot.source.participant('pc1').ranged),))
        with self.assertRaises((TypeError, ValueError)):
            forged_step = PcMeleeStep(forged_source, following.proof)
            apply_pc_melee_step(forged_source, forged_step)

    def test_instances_and_repeated_trials_never_share_loaded_state(self):
        source = scene(rounds=1, enemies=2, pc_count=2, durable=True)
        script = SHOT_HIT + SHOT_HIT + NPC_MISS + NPC_MISS
        first = execute(source, script)
        second = execute(source, script)
        self.assertEqual(first, second)
        self.assertEqual(tuple(m.ranged.weapon_instance_id for m in first.state.party),
            ('pc1:weapon', 'pc2:weapon'))
        self.assertTrue(all(not m.ranged.loaded for m in first.state.party))
        self.assertIsNot(first.state.party[0].ranged, first.state.party[1].ranged)
        self.assertEqual(len(first.state.party[0].ranged.reload_cycle_ids), 1)
        self.assertNotEqual(first.state.party[0].ranged.reload_cycle_id,
            first.state.party[1].ranged.reload_cycle_id)

    def test_drop_and_recover_preserve_empty_instance_and_partial_progress(self):
        result = execute(scene(rounds=4, durable=True),
            SHOT_HIT + NPC_HIT + [8, 1] + NPC_MISS
            + [1, 10, 10] + NPC_HIT + [4, 4, 1] + NPC_MISS)
        self.assertEqual(len(steps(result, PcHandDropProof)), 2)
        first, second = steps(result, PcRecoverProof)
        self.assertEqual(first.source.participant('pc1').ranged,
            first.state.participant('pc1').ranged)
        self.assertEqual(second.source.participant('pc1').ranged,
            second.state.participant('pc1').ranged)
        self.assertEqual(first.state.participant('pc1').ranged.exacting.accumulated_successes, 0)
        self.assertEqual(second.state.participant('pc1').ranged.exacting.accumulated_successes, 1)
        self.assertFalse(second.state.participant('pc1').ranged.loaded)
        self.assertEqual(second.proof.result.source_request.choice.object_interaction.object_id, 'pc1:weapon')
        self.assertEqual(first.state.participant('pc1').ranged.reload_cycle_id,
            second.state.participant('pc1').ranged.reload_cycle_id)
        loaded = execute(scene(rounds=4, durable=True), SHOT_HIT + NPC_MISS
            + [1, 1, 1] + NPC_HIT + [8, 1] + NPC_MISS + SHOT_HIT + NPC_MISS)
        pickup, = steps(loaded, PcRecoverProof)
        self.assertTrue(pickup.source.participant('pc1').ranged.loaded)
        self.assertEqual(pickup.source.participant('pc1').ranged,
            pickup.state.participant('pc1').ranged)
        self.assertEqual(len(shots(loaded)), 2)

    def test_wound_ten_is_consumed_once_by_actual_reload_then_later_reload_is_normal(self):
        result = execute(scene(rounds=3, durable=True), SHOT_HIT + NPC_HIT + [10]
            + [1, 10, 10, 10] + NPC_MISS + [1, 1, 1] + NPC_MISS)
        first, second = steps(result, PcRangedReloadProof)
        self.assertTrue(first.source.participant('pc1').injury.conditions.has(Condition.DRAINED))
        self.assertIs(first.proof.result.exacting.test_result.trace.quality, TestQuality.GRIM)
        self.assertEqual(first.proof.result.exacting.test_result.trace.initial_values, (1, 10, 10))
        self.assertEqual(len(first.proof.result.exacting.test_result.trace.rerolls), 1)
        self.assertEqual(first.state.participant('pc1').ranged.exacting.accumulated_successes, 0)
        self.assertIs(second.proof.result.exacting.test_result.trace.quality, TestQuality.NORMAL)
        self.assertTrue(second.state.participant('pc1').ranged.loaded)

    def test_blinded_reload_uses_actual_grim_test_and_expires_before_next_shot(self):
        result = execute(scene(rounds=3, durable=True), SHOT_HIT + NPC_HIT + [7, 10, 10, 10]
            + [1, 1, 1, 1, 1, 1] + NPC_MISS + SHOT_HIT + NPC_MISS)
        reload, = steps(result, PcRangedReloadProof)
        self.assertTrue(reload.source.participant('pc1').injury.conditions.has(Condition.BLINDED))
        self.assertIs(reload.proof.result.exacting.test_result.trace.quality, TestQuality.GRIM)
        self.assertEqual(len(reload.proof.result.exacting.test_result.trace.rerolls), 3)
        self.assertFalse(shots(result)[1].source.participant('pc1').injury.conditions.has(Condition.BLINDED))
        self.assertIs(raw(shots(result)[1]).attacker_test.trace.quality, TestQuality.NORMAL)

    def test_unavailable_second_hand_allows_loaded_shot_then_stops_only_actual_reload(self):
        for total, wound_dice in ((16, [10, 1, 5, 10]), (18, [10, 1, 7])):
            # Reload finishes before the third NPC inflicts the heavy wound.
            # The next loaded shot uses the healthy left, then the following
            # own turn reaches the actual two-hand Reload boundary.
            script = (SHOT_HIT + NPC_MISS*3 + [1, 1, 1]
                + NPC_HIT + [1] + NPC_HIT + [1, 1] + NPC_HIT + wound_dice
                + SHOT_HIT + [1, 1, 1] + NPC_MISS*3)
            with self.subTest(total=total):
                result = execute(scene(rounds=4, enemies=3, durable=True), script)
                self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
                self.assertEqual(len(shots(result)), 2)
                self.assertEqual(len(steps(result, PcRangedReloadProof)), 1)
                self.assertEqual(result.unsupported.reason, 'ranged_reload_hands_unavailable')
                self.assertEqual(result.unsupported.table_total, total)
                self.assertEqual(result.unsupported.wound_sequence, 3)
                self.assertIn('pc1:weapon', result.unsupported.source_id)
                self.assertIn(result.state.participant('pc1').ranged.reload_cycle_id,
                    result.unsupported.source_id)
                self.assertEqual(result.state.round_state.round_number, 4)
                self.assertEqual(result.state.round_state.active_turn.action_slots, ())

    def test_injured_second_hand_reload_causes_actual_critical_without_forbidding_reload(self):
        result = execute(scene(rounds=2, enemies=3, durable=True),
            SHOT_HIT + NPC_HIT + [1] + NPC_HIT + [1, 1]
            + NPC_HIT + [1, 1, 10, 10, 1, 10, 10]
            + [1, 1, 1] + [1, 1, 1] + NPC_MISS*3)
        reload, = steps(result, PcRangedReloadProof)
        self.assertFalse(reload.source.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(reload.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(reload.state.participant('pc1').ranged.loaded)
        self.assertIsNone(result.unsupported)

    def test_wound_fourteen_and_fifteen_reload_trigger_real_nonrecover_critical(self):
        for total, dice in ((14, [10, 1, 3]), (15, [10, 1, 4])):
            # W15's ongoing Staggered cannot be cleared by ordinary Recover;
            # the actual Reload follows and causes its own Critical source.
            tail = [1, 1, 1] + [1, 1, 1] + NPC_MISS*3
            with self.subTest(total=total):
                result = execute(scene(rounds=2, enemies=3, durable=True),
                    SHOT_HIT + NPC_HIT + [1] + NPC_HIT + [1, 1]
                    + NPC_HIT + dice + tail)
                reload, = steps(result, PcRangedReloadProof)
                self.assertFalse(reload.source.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
                self.assertTrue(reload.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
                self.assertTrue(reload.state.participant('pc1').ranged.loaded)

    def test_mixed_party_melee_help_falls_back_to_attack_for_shooting_beneficiary(self):
        source = scene(pc_count=2, durable=True)
        helper = source.party[0]
        helper = replace(helper, pc=replace(helper.pc, weapon=PcMeleeWeapon.STAFF, ranged=None),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2', PcHelpTarget.MELEE_ATTACK, None))
        source = replace(source, party=(helper, source.party[1]))
        result = execute(source, SHOT_HIT + SHOT_HIT + NPC_MISS)
        self.assertEqual(steps(result, PcHelpProof), ())
        self.assertEqual(len(shots(result)), 1)
        self.assertEqual(shots(result)[0].proof.request.actor_id, 'pc2')
        self.assertEqual(shots(result)[0].proof.help_applications, ())
        self.assertEqual(raw(shots(result)[0]).attacker_test.trace.rolled_dice, 3)
        self.assertIsNone(result.state.participant('pc1').ranged)

    def test_protection_help_binds_pistol_owners_actual_incoming_defence_test(self):
        source = scene(pc_count=2, durable=True)
        helper = source.party[0]
        helper = replace(helper, pc=replace(helper.pc, weapon=PcMeleeWeapon.STAFF, ranged=None),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2', PcHelpTarget.FIRST_INCOMING_PROTECTION, Skill.DEFENCE))
        source = replace(source, party=(helper, source.party[1]),
            enemy_target_priority=('pc2', 'pc1'))
        result = execute(source, [1, 1, 1] + SHOT_HIT + [10, 10] + [1]*6)
        help_step, = steps(result, PcHelpProof)
        attack, = incoming(result)
        application, = attack.proof.help_applications
        self.assertEqual(application.source_request.help, help_step.proof.execution)
        self.assertIs(attack.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual(attack.proof.request.target_id, 'pc2')
        self.assertEqual(raw(attack).defender_test.trace.rolled_dice, 6)
        self.assertEqual(shots(result)[0].proof.help_applications, ())


if __name__ == '__main__':
    unittest.main()
