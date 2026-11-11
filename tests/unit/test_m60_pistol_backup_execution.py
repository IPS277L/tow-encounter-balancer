"""Literal Pistol-to-melee journals preserve the real gun and draw boundary."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.unit.test_m54_pistol_execution import (
    NPC_HIT, NPC_MISS, SHOT_HIT, configured, execute, incoming, raw, shots, steps,
)
from tests.unit.test_m55_pistol_shield_execution import (
    critical_sources, heavy_hits, recover_object, scene as shield_scene,
)
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from towr.domain.condition_models import Condition
from towr.domain.pc_backup_weapon_models import pc_active_weapon, pc_active_weapon_item_id
from towr.domain.pc_heavy_wound_models import usable_hands
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcHelpProof, PcMeleeOutcome, PcMeleeStep,
    PcRecoverProof, initial_pc_melee_state,
)
from towr.domain.pc_ranged_models import (
    PcRangedReloadProof, build_pc_ranged_reload, prepare_pc_ranged_shot,
)
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldReleaseProof
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.rules.turn_resolution import reserve_combat_action_slot


SWORD_DEFENCE_MISS = [10, 10, 1, 1, 1, 1]
MELEE_HIT = [1, 1, 1, 10, 10]


def scene(*, shield=False, weapon=PcMeleeWeapon.SWORD, preferred=PcWeaponHand.LEFT, **kwargs):
    source = shield_scene(**kwargs)
    return replace(source, party=tuple(replace(member,
        shield=member.shield if shield else None,
        backup_weapon_policy=PcBackupWeaponPolicy(weapon, preferred)) for member in source.party))


def own_melee(result):
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.request.actor_id == 'pc1' and step.proof.ranged_shot is None)


class PcPistolBackupExecutionTests(unittest.TestCase):
    def test_two_usable_hands_keep_partial_reload_instead_of_drawing(self):
        result = execute(scene(rounds=3), SHOT_HIT + NPC_MISS
            + [1, 10, 10] + NPC_MISS + [10]*3 + NPC_MISS)
        self.assertEqual(steps(result, PcBackupWeaponDrawProof), ())
        self.assertEqual(len(shots(result)), 1)
        self.assertEqual(len(steps(result, PcRangedReloadProof)), 2)
        self.assertEqual(result.state.participant('pc1').ranged.exacting.accumulated_successes, 1)
        self.assertIs(pc_active_weapon(result.state, 'pc1'), PcMeleeWeapon.PISTOL)

    def test_terminal_loaded_shot_needs_neither_reload_nor_backup(self):
        result = execute(scene(durable=False), SHOT_HIT)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions, 1)
        self.assertEqual(steps(result, PcBackupWeaponDrawProof), ())
        self.assertEqual(steps(result, PcRangedReloadProof), ())

    def test_empty_gun_draws_after_actual_arm_loss_or_clutch_and_keeps_gun_history(self):
        for total in (16, 18):
            for shield in (False, True):
                with self.subTest(total=total, shield=shield):
                    defence = SWORD_DEFENCE_MISS if total == 16 else NPC_MISS
                    result = execute(scene(rounds=2, enemies=3, shield=shield),
                        SHOT_HIT + heavy_hits(total, side=10)
                        + MELEE_HIT + [1]*3 + defence*3)
                    draw, = steps(result, PcBackupWeaponDrawProof)
                    attack, = own_melee(result)
                    self.assertEqual(draw.source.round_state.round_number, 2)
                    self.assertEqual(draw.source.round_state, draw.state.round_state)
                    self.assertIs(draw.proof.previous_hand, PcWeaponHand.RIGHT)
                    self.assertIs(draw.proof.hand, PcWeaponHand.LEFT if total == 16 else PcWeaponHand.RIGHT)
                    self.assertTrue(draw.state.participant('pc1').using_backup_weapon)
                    self.assertEqual(draw.source.participant('pc1').ranged, draw.state.participant('pc1').ranged)
                    self.assertEqual(draw.state.participant('pc1').ranged, result.state.participant('pc1').ranged)
                    self.assertEqual(pc_active_weapon_item_id(result.state, 'pc1'), 'pc1:backup-weapon')
                    self.assertEqual(raw(attack).attacker_test.trace.threshold, 5)
                    self.assertEqual(raw(attack).impact_spec.damage.base, 3)
                    self.assertFalse(raw(attack).impact_spec.ignores_armour)
                    self.assertEqual(steps(result, PcRangedReloadProof), ())
                    self.assertEqual(steps(result, PcRecoverProof), ())
                    self.assertIsNone(result.unsupported)
                    self.assertTrue(all(raw(step).defender_test.trace.rolled_dice == (4 if total == 16 else 3)
                        for step in incoming(result) if step.source.round_state.round_number == 2))
                    releases = steps(result, PcShieldReleaseProof)
                    self.assertEqual(len(releases), int(shield and total == 16))
                    if releases:
                        release, = releases
                        self.assertLess(result.steps.index(release), result.steps.index(draw))
                        self.assertIs(draw.source.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_empty_dropped_gun_is_not_picked_up_before_healthy_shield_hand_draw(self):
        result = execute(scene(rounds=2, enemies=3, shield=True), SHOT_HIT
            + NPC_HIT + [8, 10] + NPC_HIT + [1, 1]
            + NPC_HIT + [10, 1, 5, 10]
            + MELEE_HIT + [1]*3 + SWORD_DEFENCE_MISS*3)
        draw, = steps(result, PcBackupWeaponDrawProof)
        release, = steps(result, PcShieldReleaseProof)
        self.assertIsNone(draw.proof.previous_hand)
        self.assertIs(draw.proof.hand, PcWeaponHand.LEFT)
        self.assertLess(result.steps.index(release), result.steps.index(draw))
        self.assertEqual(steps(result, PcRecoverProof), ())
        self.assertEqual(draw.state.participant('pc1').ranged, result.state.participant('pc1').ranged)

    def test_loaded_one_hand_shot_precedes_irreversible_fallback_next_turn(self):
        for total in (16, 18):
            with self.subTest(total=total):
                defence = SWORD_DEFENCE_MISS if total == 16 else NPC_MISS
                result = execute(scene(rounds=5, enemies=3, shield=True),
                    SHOT_HIT + NPC_MISS*3 + [1]*3 + NPC_MISS*3
                    + heavy_hits(total, side=10) + SHOT_HIT + [1]*3 + NPC_MISS*3
                    + MELEE_HIT + [1]*3 + defence*3)
                draw, = steps(result, PcBackupWeaponDrawProof)
                final_shot = shots(result)[1]
                self.assertEqual(len(shots(result)), 2)
                self.assertEqual(final_shot.source.round_state.round_number, 4)
                self.assertEqual(draw.source.round_state.round_number, 5)
                self.assertEqual(len(steps(result, PcRangedReloadProof)), 1)
                self.assertEqual(final_shot.state.participant('pc1').ranged,
                    result.state.participant('pc1').ranged)
                self.assertIsNone(result.unsupported)

    def test_dropped_backup_recovers_its_own_item_and_never_recovers_empty_pistol(self):
        result = execute(scene(rounds=3, enemies=3), SHOT_HIT + heavy_hits(16, side=10)
            + MELEE_HIT + [1]*3 + [1, 1] + [10]*4 + [1, 1, 1, 5, 1]
            + NPC_MISS*2 + [1]*3 + SWORD_DEFENCE_MISS*3)
        draw, = steps(result, PcBackupWeaponDrawProof)
        recover, = steps(result, PcRecoverProof)
        self.assertEqual(recover_object(recover), 'pc1:backup-weapon')
        self.assertIsNone(recover.source.participant('pc1').weapon_hand)
        self.assertIs(recover.state.participant('pc1').weapon_hand, PcWeaponHand.LEFT)
        self.assertTrue(recover.state.participant('pc1').using_backup_weapon)
        self.assertEqual(draw.state.participant('pc1').ranged, result.state.participant('pc1').ranged)
        self.assertEqual(steps(result, PcRangedReloadProof), ())
        interaction = recover.proof.result.source_request.choice.object_interaction
        self.assertEqual(interaction.object_id, pc_active_weapon_item_id(recover.source, 'pc1'))
        # A forged pickup of the retained, empty primary cannot become a return
        # to Shooting or silently substitute the active physical item.
        foreign = deepcopy(recover)
        object.__setattr__(foreign.proof.result.source_request.choice.object_interaction,
            'object_id', 'pc1:weapon')
        with self.assertRaises(ValueError):
            apply_pc_melee_step(recover.source, foreign)

    def test_injured_but_usable_hand_reloads_without_premature_backup(self):
        result = execute(scene(rounds=2, enemies=3, shield=True),
            SHOT_HIT + heavy_hits(12) + [1]*3 + [1]*3 + NPC_MISS*3)
        reload, = steps(result, PcRangedReloadProof)
        self.assertEqual(steps(result, PcBackupWeaponDrawProof), ())
        self.assertEqual(critical_sources(reload.state), (3,))
        self.assertTrue(result.state.participant('pc1').ranged.loaded)

    def test_actual_draw_preserves_distinct_wound_twelve_fourteen_fifteen_critical_sources(self):
        for total in (12, 14, 15):
            with self.subTest(total=total):
                defence = SWORD_DEFENCE_MISS if total == 12 else NPC_MISS
                result = execute(scene(rounds=2, enemies=4, preferred=PcWeaponHand.RIGHT),
                    SHOT_HIT + heavy_hits(total, side=10)
                    + NPC_HIT + [1, 1, 4, 10, 1]
                    + MELEE_HIT + [1]*3 + defence*4)
                draw, = steps(result, PcBackupWeaponDrawProof)
                self.assertIs(draw.proof.hand, PcWeaponHand.RIGHT)
                self.assertIn(3, critical_sources(draw.state))
                self.assertIn(4, critical_sources(draw.state))
                self.assertEqual(draw.source.round_state, draw.state.round_state)

    def test_all_six_one_handed_backup_damage_profiles_replace_the_pistol(self):
        for weapon, damage in ((PcMeleeWeapon.STAFF, 3), (PcMeleeWeapon.DAGGER, 2),
                (PcMeleeWeapon.AXE, 3), (PcMeleeWeapon.SWORD, 3),
                (PcMeleeWeapon.WARHAMMER, 3), (PcMeleeWeapon.MORNING_STAR, 4)):
            with self.subTest(weapon=weapon):
                defence = SWORD_DEFENCE_MISS if weapon is PcMeleeWeapon.SWORD else NPC_MISS
                result = execute(scene(rounds=2, enemies=3, weapon=weapon),
                    SHOT_HIT + heavy_hits(16, side=10) + MELEE_HIT + [1]*3 + defence*3)
                attack, = own_melee(result)
                self.assertEqual(raw(attack).impact_spec.damage.base, damage)
                self.assertIs(pc_active_weapon(result.state, 'pc1'), weapon)
                self.assertEqual(len(steps(result, PcBackupWeaponDrawProof)), 1)

    def test_glorious_uses_actual_melee_after_draw_without_spending_on_shooting(self):
        result = execute(configured(scene(rounds=2, enemies=3), (Skill.MELEE,)),
            SHOT_HIT + heavy_hits(16, side=10)
            + [10]*3 + [1]*3 + [10]*2 + [1]*3 + SWORD_DEFENCE_MISS*3)
        attack, = own_melee(result)
        self.assertIsNotNone(attack.proof.glorious)
        self.assertIsNone(shots(result)[0].proof.glorious)
        self.assertEqual(attack.proof.glorious.source_request.test.profile.skill, 5)

    def test_draw_has_no_test_and_preserves_wound_ten_for_actual_melee_once(self):
        result = execute(scene(rounds=2, enemies=4), SHOT_HIT + heavy_hits(16, side=10)
            + NPC_HIT + [1, 1, 1, 7] + [1]*6 + [10]*2 + [1]*3 + NPC_MISS*4)
        draw, = steps(result, PcBackupWeaponDrawProof)
        attack, = own_melee(result)
        self.assertEqual(draw.source.participant('pc1').injury.active_wound_effects,
            draw.state.participant('pc1').injury.active_wound_effects)
        self.assertIs(raw(attack).attacker_test.trace.quality, TestQuality.GRIM)
        self.assertEqual(len(raw(attack).attacker_test.trace.rerolls), 3)
        self.assertTrue(all(raw(step).defender_test.trace.quality is TestQuality.NORMAL
            for step in incoming(result) if step.source.round_state.round_number == 2))

    def test_earlier_ally_helps_only_after_actual_melee_draw_without_anticipating_it(self):
        source = scene(rounds=3, enemies=3, pc_count=2)
        primary, helper = source.party
        helper = replace(helper, pc=replace(helper.pc, weapon=PcMeleeWeapon.SWORD, ranged=None),
            backup_weapon_policy=None,
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc1', PcHelpTarget.MELEE_ATTACK, None))
        source = replace(source, party=(primary, helper), pc_activation_order=('pc2', 'pc1'))
        result = execute(source, MELEE_HIT + SHOT_HIT + heavy_hits(16, side=10)
            + MELEE_HIT + MELEE_HIT + [1]*3 + SWORD_DEFENCE_MISS*3
            + [1]*3 + [1]*6 + [10]*2 + [1]*3 + SWORD_DEFENCE_MISS*3)
        draw, = steps(result, PcBackupWeaponDrawProof)
        help_step, = steps(result, PcHelpProof)
        self.assertEqual(draw.source.round_state.round_number, 2)
        self.assertEqual(help_step.source.round_state.round_number, 3)
        self.assertEqual(help_step.proof.execution.bonus.beneficiary_id, 'pc1')
        own = own_melee(result)
        self.assertEqual(tuple(raw(step).attacker_test.trace.rolled_dice for step in own), (3, 6))
        self.assertEqual(len(own[1].proof.help_applications), 1)

    def test_melee_backup_ignores_shooting_override_and_retains_thief_stealth(self):
        for profile in ('trooper', 'thief'):
            with self.subTest(profile=profile):
                source = book_pc_scenario(footpads=0, townsfolk=0, pc_count=1,
                    max_rounds=2, **({'troopers': 4} if profile == 'trooper' else {'thieves': 4}))
                member = source.party[0]
                pistol = scene().party[0]
                # Thief's printed Damage1 needs low actual Toughness for a
                # guaranteed Wound. Its full canonical definition stays exact.
                pc = replace(pistol.pc, toughness=1) if profile == 'thief' else pistol.pc
                source = replace(source,
                    party=(replace(member, pc=pc, initial_weapon_hand=PcWeaponHand.RIGHT,
                        backup_weapon_policy=pistol.backup_weapon_policy),),
                    facts=replace(source.facts, outnumbering_bonus_approved=False),
                    npc_close_shooting_protection_policies=tuple(
                        PcNpcCloseShootingProtectionPolicy(actor, Skill.ATHLETICS)
                        for actor in source.enemy_activation_order) if profile == 'trooper' else None)
                npc_dice = 3 if profile == 'trooper' else 2
                npc_hit = [1]*npc_dice + [10]*3
                npc_miss = [10]*npc_dice + [1]*4
                result = execute(source, [1]*3 + [10]*3
                    + npc_hit + [1] + npc_hit + [1, 1]
                    + npc_hit + [10, 1, 5, 10]
                    + [1]*3 + [10]*3 + [1]*(3 if profile == 'trooper' else 1)
                    + npc_miss*2)
                attack, = own_melee(result)
                before, = shots(result)
                self.assertEqual(len(steps(result, PcBackupWeaponDrawProof)), 1)
                self.assertIs(before.proof.protection.source_request.selected_skill,
                    Skill.ATHLETICS if profile == 'trooper' else Skill.STEALTH)
                self.assertIs(attack.proof.protection.source_request.selected_skill,
                    Skill.DEFENCE if profile == 'trooper' else Skill.STEALTH)
                self.assertEqual(raw(attack).defender_test.trace.threshold,
                    4 if profile == 'trooper' else 5)
                self.assertEqual(raw(attack).impact_spec.damage.base, 3)
                self.assertFalse(raw(attack).impact_spec.ignores_armour)

    def test_zero_hands_and_defenceless_never_manufacture_a_draw(self):
        result = execute(scene(rounds=2, enemies=4), SHOT_HIT + heavy_hits(18)
            + NPC_HIT + [1, 1, 4, 10, 10])
        self.assertEqual(steps(result, PcBackupWeaponDrawProof), ())
        self.assertEqual(usable_hands(result.state.participant('pc1')), ())
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual((result.unsupported.wound_sequence, result.unsupported.table_total), (4, 16))
        result = execute(scene(rounds=2, enemies=3),
            SHOT_HIT + heavy_hits(20) + [1]*3 + [10]*6)
        self.assertEqual(steps(result, PcBackupWeaponDrawProof), ())
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.DEFENCELESS))
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)

    def test_draw_is_source_bound_unreserved_once_and_cannot_restore_pistol_actions(self):
        result = execute(scene(rounds=2, enemies=3), SHOT_HIT + heavy_hits(16, side=10)
            + MELEE_HIT + [1]*3 + SWORD_DEFENCE_MISS*3)
        draw, = steps(result, PcBackupWeaponDrawProof)
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current, step)
        self.assertEqual(current, result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(draw.state, draw)
        for proof in (replace(draw.proof, actor_id='foreign'),
                replace(draw.proof, previous_hand=None), replace(draw.proof, hand=PcWeaponHand.RIGHT)):
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                PcMeleeStep(draw.source, proof)
        reservation = reserve_combat_action_slot(CombatActionSlotRequest('skip:reserve',
            draw.source.round_state, 'pc1', CombatActionDeclaration(CombatActionKind.ATTACK),
            ActionSlotGrant.STANDARD))
        with self.assertRaises(ValueError):
            PcMeleeStep(draw.source, reservation)
        with self.assertRaises(ValueError):
            replace(result, steps=tuple(step for step in result.steps if step is not draw))
        with self.assertRaises(ValueError):
            build_pc_ranged_reload(draw.state)
        with self.assertRaises(ValueError):
            prepare_pc_ranged_shot(draw.state, shots(result)[0].proof.request)
        foreign = deepcopy(draw)
        object.__setattr__(foreign.state.participant('pc1'), 'using_backup_weapon', False)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(draw.source, foreign)


if __name__ == '__main__':
    unittest.main()
