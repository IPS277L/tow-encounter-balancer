"""Literal close Shooting opposition, full book profiles, and source admission."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m54_pistol_execution import configured, execute, incoming, raw, shots, steps
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcProfileWoundProof, build_pc_melee_attack, initial_pc_melee_state,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy
from towr.domain.pc_pistol_models import PcPistolReloadProof
from towr.domain.protection_models import CLOSE_RANGED_MELEE_RULE_ID
from towr.domain.test_models import DiceModifier, Skill, TestQuality
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn


PROFILES = (
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD, 'troopers', 'trooper1', 3, 3, 3, 4),
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR, 'spear_troopers', 'spear_trooper1', 3, 3, 3, 4),
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE, 'empire_knights', 'empire_knight1', 4, 4, 2, 4),
    (PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER, 'wolf_knights', 'wolf_knight1', 4, 4, 2, 3),
)


def close_shooting_scene(profile=PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,
        skill=Skill.MELEE, *, rounds=1, pc_count=1, melee_actor_ids=()):
    """Fresh canonical NPCs; policy and Pistol source enter in one transaction."""
    _, keyword, _, _, _, _, _ = next(row for row in PROFILES if row[0] is profile)
    source = book_pc_scenario(footpads=0, townsfolk=0, pc_count=pc_count,
        max_rounds=rounds, **{keyword: 1})
    party = tuple(member if member.actor_id in melee_actor_ids else replace(member,
        pc=replace(member.pc, weapon=PcMeleeWeapon.PISTOL, pistol=pistol_profile()))
        for member in source.party)
    return replace(source, party=party,
        facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_close_shooting_protection_policies=tuple(
            PcNpcCloseShootingProtectionPolicy(enemy.state.actor_id, skill) for enemy in source.enemies))


def prepared_state(source):
    state = initial_pc_melee_state(source)
    combat = start_combat_turn(CombatTurnStartRequest('fixture:pc:start', state.round_state, 'pc1')).state
    return replace(state, round_state=combat)


class CloseShootingExecutionTests(unittest.TestCase):
    def test_four_canonical_loadouts_use_selected_melee_with_no_counterattack(self):
        for profile, _, actor, dice, threshold, _, _ in PROFILES:
            with self.subTest(profile=profile):
                source = close_shooting_scene(profile)
                # The shot hits; a surviving Knight makes its distinct own attack and misses.
                script = [1, 1, 1] + [10]*dice
                if dice == 4:
                    script += [10]*4 + [1, 1, 1]
                result = execute(source, script)
                shot, = shots(result)
                preparation = shot.proof.protection.source_request
                defender = raw(shot).defender_test
                self.assertIs(preparation.selected_skill, Skill.MELEE)
                self.assertEqual((defender.trace.rolled_dice, defender.trace.threshold,
                    defender.trace.pool_cap), (dice, threshold, dice*2))
                self.assertIn(CLOSE_RANGED_MELEE_RULE_ID, shot.proof.protection.applied_rule_ids)
                self.assertEqual(shot.source.enemy(actor).definition, source.enemy(actor).definition)
                self.assertEqual(result.state.participant('pc1').injury.wounds, ())
                self.assertEqual(result.executed_actions, 2 if dice == 4 else 1)

    def test_four_canonical_loadouts_use_printed_athletics_with_true_characteristic_cap(self):
        for profile, _, _, attack_dice, _, dice, _ in PROFILES:
            with self.subTest(profile=profile):
                script = [1, 1, 1] + [10]*dice
                if attack_dice == 4:
                    script += [10]*4 + [1, 1, 1]
                result = execute(close_shooting_scene(profile, Skill.ATHLETICS), script)
                shot, = shots(result)
                defender = raw(shot).defender_test
                self.assertIs(shot.proof.protection.source_request.selected_skill, Skill.ATHLETICS)
                self.assertEqual((defender.trace.base_dice, defender.trace.rolled_dice,
                    defender.trace.threshold, defender.trace.pool_cap), (dice, dice, 3, 6))
                self.assertEqual(defender.trace.regular_dice_delta, 0)
                self.assertNotIn(CLOSE_RANGED_MELEE_RULE_ID, shot.proof.protection.applied_rule_ids)

    def test_knight_athletics_cap_six_is_preserved_by_actual_test_source(self):
        state = prepared_state(close_shooting_scene(skill=Skill.ATHLETICS))
        _, protection = build_pc_melee_attack(state)
        test = protection.options[0].test
        # K1 boundary: even a supplied rule bonus caps at actual Ag3*2, not printed2d*2.
        test = replace(test, dice_modifiers=(DiceModifier('fixture:explicit-cap-probe', 8),))
        result = resolve_test(test, SequenceRandom([1]*6))
        self.assertEqual((result.trace.base_dice, result.trace.pool_cap, result.trace.rolled_dice), (2, 6, 6))

    def test_equal_successes_hit_but_both_fail_does_not(self):
        for attacker, defender, hit in (([1,10,10], [1,10,10], True),
                ([10]*3, [10]*3, False)):
            with self.subTest(hit=hit):
                script = attacker + defender
                if not hit:
                    script += [10]*3 + [1]*3
                result = execute(close_shooting_scene(PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD), script)
                shot, = shots(result)
                self.assertIs(raw(shot).outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(result.executed_actions, 1 if hit else 2)
                self.assertEqual(result.state.participant('pc1').injury.wounds, ())

    def test_winning_melee_defender_does_not_damage_or_take_an_extra_action(self):
        result = execute(close_shooting_scene(PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR),
            [10]*3 + [1]*3 + [10]*3 + [1]*3)
        shot, = shots(result)
        self.assertIs(raw(shot).outcome, AttackOutcome.MISS)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(shot.state.participant('pc1').injury.wounds, ())
        self.assertEqual(len(incoming(result)), 1)
        self.assertEqual(result.executed_actions, 2)

    def test_mixed_party_keeps_original_defence_against_melee_attack(self):
        source = close_shooting_scene(PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,
            pc_count=2, melee_actor_ids=('pc2',))
        result = execute(source, [1]*3 + [10]*4 + [1]*3 + [10]*4)
        pistol, melee = steps(result, PcAttackProof)
        self.assertIs(pistol.proof.protection.source_request.selected_skill, Skill.MELEE)
        self.assertIs(melee.proof.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual((raw(pistol).defender_test.trace.threshold,
            raw(melee).defender_test.trace.threshold), (4, 3))
        self.assertEqual(result.executed_actions, 2)
        self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_shooting_and_defensive_melee_do_not_gain_outnumber_or_weapon_traits(self):
        source = close_shooting_scene(pc_count=2)
        source = replace(source, facts=replace(source.facts, outnumbering_bonus_approved=True))
        result = execute(source, [1]*3 + [10]*4 + [1]*3 + [10]*4)
        for shot in shots(result):
            attack = raw(shot)
            self.assertEqual(attack.attacker_test.trace.rolled_dice, 3)
            self.assertEqual(attack.defender_test.trace.rolled_dice, 4)
            self.assertEqual(attack.defender_test.trace.regular_dice_delta, 0)
            self.assertEqual(shot.proof.request.kernel_request.attack.defender_test.dice_modifiers, ())

    def test_both_knights_keep_wound_one_drained_then_second_wound_defeat(self):
        for profile in (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE, PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER):
            for skill, dice in ((Skill.MELEE,4),(Skill.ATHLETICS,2)):
                with self.subTest(profile=profile,skill=skill):
                    source = close_shooting_scene(profile,skill,rounds=3)
                    result = execute(source, [1]*3 + [10]*dice + [10]*4 + [1]*3
                        + [1]*3 + [10]*4 + [1]*3 + [1]*3 + [10]*dice)
                    first, second = shots(result)
                    actor = source.enemies[0].state.actor_id
                    first_ack = steps(result,PcProfileWoundProof)[0]
                    self.assertTrue(first_ack.state.enemy(actor).state.injury.conditions.has(Condition.DRAINED))
                    self.assertTrue(second.source.enemy(actor).state.injury.conditions.has(Condition.DRAINED))
                    self.assertEqual(raw(second).defender_test.trace.regular_dice_delta, 0)
                    self.assertEqual(raw(second).defender_test.trace.rolled_dice, dice)
                    self.assertTrue(result.state.enemy(actor).state.injury.defeated)
                    self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                    self.assertEqual(len(steps(result,PcPistolReloadProof)),1)
                    self.assertEqual(result.executed_actions,5)

    def test_prone_preparation_penalizes_shooting_without_defensive_melee_bonus(self):
        state = prepared_state(close_shooting_scene())
        enemy = state.enemies[0]
        injury = replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.PRONE))
        enemy = replace(enemy,state=replace(enemy.state,injury=injury))
        state = replace(state,enemies=(enemy,))
        request, protection = build_pc_melee_attack(state)
        self.assertEqual(tuple((m.rule_id,m.amount) for m in request.kernel_request.attack.attacker_test.dice_modifiers),
            (('RULE-HEALTH-008:prone-shooting',-1),))
        self.assertEqual(protection.options[0].test.dice_modifiers,())

    def test_defenceless_preparation_does_not_restore_opposition(self):
        state = prepared_state(close_shooting_scene())
        enemy = state.enemies[0]
        injury = replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.DEFENCELESS))
        state = replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=injury)),))
        request, protection = build_pc_melee_attack(state)
        self.assertIsNone(protection.selected_skill)
        self.assertEqual(protection.options,())
        self.assertIsNone(request.kernel_request.attack.defender_test)

    def test_terminal_shot_needs_no_reload_or_npc_reaction(self):
        result = execute(close_shooting_scene(PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR),
            [1]*3+[10]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,1)
        self.assertEqual(incoming(result),())
        self.assertEqual(steps(result,PcPistolReloadProof),())

    def test_shooting_fate_keeps_actual_opposition_source_without_duplicate_defender_test(self):
        source = configured(close_shooting_scene(),(Skill.SHOOTING,))
        result = execute(source,[10]*3+[1]*3+[10]*4+[10]*4+[1]*3)
        shot, = shots(result)
        self.assertIs(raw(shot).attacker_test.trace.quality,TestQuality.GLORIOUS)
        self.assertIs(raw(shot).defender_test.trace.quality,TestQuality.NORMAL)
        self.assertEqual(raw(shot).defender_test.trace.initial_values,(10,10,10,10))
        self.assertIs(shot.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertEqual(len(result.state.participant('pc1').fate.spends),1)
        self.assertEqual(result.executed_actions,2)

    def test_full_source_admission_rejects_replay_policy_swap_and_profile_alias(self):
        result = execute(close_shooting_scene(PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR),
            [1]*3+[10]*3)
        shot, = shots(result)
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(shot.state,shot)
        class SkillAlias(str,Enum):
            MELEE='melee'
        for field in ('policy','skill','profile'):
            forged = deepcopy(shot)
            if field=='policy':
                object.__setattr__(forged.source.source.npc_close_shooting_protection_policies[0], 'skill',Skill.ATHLETICS)
            elif field=='skill':
                object.__setattr__(forged.proof.protection.source_request,'selected_skill',SkillAlias.MELEE)
            else:
                object.__setattr__(forged.proof.protection.source_request.options[0].test.profile,'threshold',4)
            with self.subTest(field=field), self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(forged.source,forged)


if __name__ == '__main__':
    unittest.main()
