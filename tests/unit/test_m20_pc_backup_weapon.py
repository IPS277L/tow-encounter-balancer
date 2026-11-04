"""Literal native backup draws keep the active item, injury, clock and source history."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario,make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import usable_weapon_hand, usable_hands
from towr.domain.pc_melee_models import (PcBackupWeaponPolicy, PcMeleeWeapon, PcWeaponHand,
    PcTwoHandedGrip, PcFatePolicy, PcNearMissPolicy, PcMeleePolicy, PcHelpPolicy, PcHelpTarget)
from towr.domain.pc_backup_weapon_models import pc_active_weapon, pc_active_weapon_item_id
from towr.domain.pc_melee_result_models import (PcAttackProof, PcBackupWeaponDrawProof,
    PcRecoverProof, PcHelpProof, PcMeleeOutcome, PcMeleeStep, PcHandSwapProof, initial_pc_melee_state)
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.test_models import Skill
from towr.domain.turn_models import (CombatActionSlotRequest, CombatActionDeclaration,
    CombatActionKind, ActionSlotGrant)
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.turn_resolution import reserve_combat_action_slot


def source(*,enemies=3,rounds=2,weapon=PcMeleeWeapon.SWORD,preferred=PcWeaponHand.LEFT):
    scene = make_pc_melee_scenario(weapon=PcMeleeWeapon.PICKAXE,enemy_count=enemies,max_rounds=rounds)
    return replace(scene,party=(replace(scene.party[0],backup_weapon_policy=PcBackupWeaponPolicy(weapon,preferred)),))


def execute(scene,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(scene,rng)
    rng.assert_exhausted()
    return result


def draws(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcBackupWeaponDrawProof))


class PcBackupWeaponTests(unittest.TestCase):
    def test_native_arm_loss_draws_on_own_turn_and_uses_backup_sword_damage_and_defence(self):
        scene = source(enemies=5)
        # First kill prevents self Staggered, leaving Sword's eventual Defence bonus observable.
        result = execute(scene,[1]*3+[10]*2+heavy_prefix(16)[5:]
            +[10]*3+[1]*3+[1]*3+[10]*2+[1]*3+[10,10,10,1,1,1,1]*3)
        draw, = draws(result)
        self.assertEqual(draw.proof,PcBackupWeaponDrawProof('pc',PcTwoHandedGrip.BOTH,PcWeaponHand.RIGHT))
        self.assertEqual(draw.source.round_state.round_number,2)
        self.assertEqual(draw.source.round_state,draw.state.round_state)
        self.assertTrue(draw.state.party[0].using_backup_weapon)
        self.assertIs(pc_active_weapon(draw.state,'pc'),PcMeleeWeapon.SWORD)
        before = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='minion5' and step.source.round_state.round_number==1)
        self.assertIs(before.protection.source_request.selected_skill,Skill.ATHLETICS)
        own = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc' and step.source.round_state.round_number==2)
        self.assertEqual(own.execution.resolution.attack.impact_spec.damage.base,3)
        incoming = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id.startswith('minion') and step.source.round_state.round_number==2)
        self.assertTrue(all(attack.protection.source_request.selected_skill is Skill.DEFENCE for attack in incoming))
        self.assertTrue(all(attack.execution.resolution.attack.defender_test.trace.rolled_dice==4 for attack in incoming))
        self.assertEqual(result.executed_actions,9)

    def test_native_clutch_drops_primary_then_draws_backup_in_free_hand_without_recover(self):
        result = execute(source(),heavy_prefix(18)+[1]*3+[10]*2+[1]*3+[10,10,10,1,1,1]*2)
        draw, = draws(result)
        self.assertEqual(draw.proof,PcBackupWeaponDrawProof('pc',None,PcWeaponHand.RIGHT))
        self.assertFalse(any(isinstance(step.proof,PcRecoverProof) for step in result.steps))
        self.assertIsNone(result.unsupported)

    def test_defenceless_severed_arm_continues_empty_turn_and_critical_without_drawing(self):
        result = execute(source(),heavy_prefix(20)+[1]*3+[10]*9)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(draws(result),())
        self.assertFalse(result.state.party[0].using_backup_weapon)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(result.executed_actions,7)

    def test_backup_can_drop_and_recover_only_its_own_item_id(self):
        result = execute(source(rounds=3),heavy_prefix(16)
            +[10]*3+[1]*2+[1]*3+[1]*3+[10]*3+[1,1,1,5,10]
            +[10,10,10,1,1,1]*2+[1]*3+[10,10,10,1,1,1,1]*3)
        draw, = draws(result)
        recover, = tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))
        interaction = recover.proof.result.source_request.choice.object_interaction
        self.assertEqual(interaction.object_id,'pc:backup-weapon')
        self.assertEqual(pc_active_weapon_item_id(recover.source,'pc'),'pc:backup-weapon')
        self.assertIsNone(recover.source.party[0].weapon_hand)
        self.assertIs(recover.state.party[0].weapon_hand,PcWeaponHand.RIGHT)
        self.assertTrue(recover.state.party[0].using_backup_weapon)
        self.assertEqual(draws(result),(draw,))

    def test_smashed_hand_does_not_trigger_fallback_or_avoid_two_handed_critical_use(self):
        result = execute(source(),heavy_prefix(12)+[1]*3+[10,10,10,1,1,1]*3)
        self.assertEqual(draws(result),())
        self.assertFalse(result.state.party[0].using_backup_weapon)
        self.assertIs(result.state.party[0].weapon_hand,PcTwoHandedGrip.BOTH)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_near_miss_prevents_fallback_before_any_arm_consequence(self):
        scene = source(rounds=1)
        scene = replace(scene,party=(replace(scene.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(16,0)),))
        result = execute(scene,heavy_prefix(16)[:-1])
        self.assertEqual(draws(result),())
        self.assertIsNone(result.unsupported)
        self.assertEqual(result.state.party[0].body_facts,())
        self.assertEqual(result.state.party[0].fate.rating,2)

    def test_latest_zero_hand_cause_uses_wound_sequence_after_old_clutch_relocation(self):
        result = execute(source(enemies=4,rounds=1),heavy_prefix(18)
            +[1]*3+[10]*3+[1,1,4,10,1])
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(draws(result),())
        self.assertEqual(usable_hands(result.state.party[0]),())
        self.assertEqual((result.unsupported.wound_sequence,result.unsupported.table_total),(4,16))
        self.assertEqual(result.unsupported.source_id,'RULE-EQUIPMENT-002:pc:w4:two-handed-grip')
        self.assertEqual(tuple(fact.wound_sequence for fact in result.state.party[0].body_facts),(4,3))

    def test_active_backup_with_no_usable_hands_keeps_existing_one_handed_continuation(self):
        result = execute(source(),heavy_prefix(16)+[1]*3+[10]*2+[1]*3
            +[1]*3+[10]*4+[1,1,4,10,10]+[10]*3+[1]*3)
        self.assertEqual(len(draws(result)),1)
        self.assertTrue(result.state.party[0].using_backup_weapon)
        self.assertIsNone(usable_weapon_hand(result.state.party[0]))
        self.assertEqual(usable_hands(result.state.party[0]),())
        self.assertIsNone(result.unsupported)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_all_one_handed_backup_damage_profiles_replace_primary(self):
        for weapon,base in ((PcMeleeWeapon.STAFF,3),(PcMeleeWeapon.DAGGER,2),(PcMeleeWeapon.AXE,3),
                (PcMeleeWeapon.WARHAMMER,3),(PcMeleeWeapon.MORNING_STAR,4)):
            with self.subTest(weapon=weapon):
                result = execute(source(weapon=weapon),heavy_prefix(16)+[1]*3+[10]*2+[1]*3
                    +[10,10,10,1,1,1]*2)
                own = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
                    and step.proof.request.actor_id=='pc' and step.source.round_state.round_number==2)
                self.assertEqual(own.execution.resolution.attack.impact_spec.damage.base,base)
                self.assertIs(pc_active_weapon(result.state,'pc'),weapon)

    def test_incidental_draw_applies_actual_wound14_15_and_used_injured_hand12_critical(self):
        for total,side,hand,defence_dice in ((12,10,PcWeaponHand.LEFT,4),
                (14,1,PcWeaponHand.RIGHT,3),(15,1,PcWeaponHand.RIGHT,3)):
            with self.subTest(total=total):
                result = execute(source(enemies=4),heavy_prefix(total)
                    +[1]*3+[10]*3+[1,1,4,10,side]
                    +[1]*3+[10]*2+[1]*3+([10]*3+[1]*defence_dice)*3)
                draw, = draws(result)
                self.assertIs(draw.proof.hand,hand)
                critical_sources = tuple(effect.wound_sequence for effect in draw.state.party[0].injury.active_wound_effects
                    if isinstance(effect,WoundConditionEffect) and effect.condition is Condition.CRITICALLY_INJURED)
                self.assertIn(3,critical_sources)
                self.assertIn(4,critical_sources)

    def test_native_backup_weapon_is_used_for_subsequent_physical_help(self):
        scene = make_pc_melee_party_scenario(enemy_count=3,max_rounds=2)
        helper,beneficiary = scene.party
        scene = replace(scene,party=(replace(helper,pc=replace(helper.pc,weapon=PcMeleeWeapon.PICKAXE),
            initial_weapon_hand=PcTwoHandedGrip.BOTH,
            backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.MORNING_STAR,PcWeaponHand.LEFT),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None)),beneficiary))
        result = execute(scene,[10]*3+[10]*3+[1]*2+heavy_prefix(16)[5:]
            +[1]*3+[1]*3+[1]*6+[10]*2+[10,10,1,1,1]*2)
        draw, = draws(result)
        self.assertEqual(draw.proof.actor_id,'pc1')
        helped = tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))[-1]
        self.assertTrue(helped.source.participant('pc1').using_backup_weapon)
        self.assertIs(pc_active_weapon(helped.source,'pc1'),PcMeleeWeapon.MORNING_STAR)
        self.assertEqual(helped.proof.execution.help_test_result.trace.rolled_dice,3)

    def test_native_draw_requires_exact_source_once_and_cannot_be_skipped_or_hand_swapped(self):
        result = execute(source(),heavy_prefix(16)+[1]*3+[10]*2+[1]*3+[10,10,10,1,1,1,1]*2)
        draw, = draws(result)
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(draw.state,draw)
        for forged in (replace(draw.proof,actor_id='foreign'),replace(draw.proof,hand=PcWeaponHand.LEFT),
                replace(draw.proof,previous_hand=None)):
            with self.subTest(forged=forged),self.assertRaises(ValueError):
                PcMeleeStep(draw.source,forged)
        with self.assertRaises(ValueError):
            PcMeleeStep(draw.source,PcHandSwapProof(PcTwoHandedGrip.BOTH,PcWeaponHand.RIGHT))
        reservation = reserve_combat_action_slot(CombatActionSlotRequest('skip:reserve',draw.source.round_state,'pc',
            CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD))
        with self.assertRaises(ValueError):
            PcMeleeStep(draw.source,reservation)
        with self.assertRaises(ValueError):
            replace(result,steps=tuple(step for step in result.steps if step is not draw))
        with self.assertRaises(ValueError):
            replace(draw.state,party=(replace(draw.state.party[0],using_backup_weapon=False),))
        with self.assertRaises(TypeError):
            replace(draw.state.party[0],using_backup_weapon=1)
        foreign = deepcopy(draw)
        object.__setattr__(foreign.state.party[0],'weapon_hand',PcTwoHandedGrip.BOTH)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(draw.source,foreign)


if __name__ == '__main__':
    unittest.main()
