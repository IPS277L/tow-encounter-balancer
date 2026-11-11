"""Literal Crossbow volley and explicitly focused PC-to-K1 Reload binding."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_crossbow_scenarios import crossbow_profile, make_pc_crossbow_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRecord, WoundRecordOrigin
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import (
    PC_CROSSBOW_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS, PcFatePolicy,
    PcGloriousPolicy, PcMeleeWeapon, PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcMeleeOutcome, PcMeleeStep,
    build_pc_melee_attack, pc_melee_round_participants,
)
from towr.domain.pc_ranged_models import (
    PcRangedReloadProof, build_pc_ranged_reload, complete_pc_ranged_shot,
    prepare_pc_ranged_shot, ranged_reload_declaration,
)
from towr.domain.pc_short_opening_models import PcNpcApproachProof, pc_has_close_enemy
from towr.domain.ranged_weapon_attack_preparation_models import ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.test_models import Skill, TestProfile, TestQuality
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionSlotRequest, CombatRoundAdvanceRequest, CombatTurnStartRequest,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import advance_combat_round, reserve_combat_action_slot, start_combat_turn


CROSSBOW = PcMeleeWeapon.CROSSBOW
REPEATER = PcMeleeWeapon.REPEATER_CROSSBOW
WHEN = PcRepeaterBonusPolicy.WHEN_AVAILABLE
NEVER = PcRepeaterBonusPolicy.NEVER
NPC_MISS = [10,10,1,1,1]
NPC_HIT = [1,1,10,10,10]
SWORD_HIT = [1,1,1,10,10]


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


def shot_values(*, bonus=False, hit=False):
    if bonus:
        return [1,1,1,1,10,10] if hit else [10,10,10,10,1,1]
    return [1,1,1,10,10] if hit else [10,10,10,1,1]


def focused_next_pc_turn(result):
    """Legal clock after the real first round; caller tests an alternative action.

    This is not a fresh encounter following the automatic backup strategy.
    The real shot/approach histories and owned charge source are retained.
    """
    state = result.state
    advanced = advance_combat_round(CombatRoundAdvanceRequest('focused:advance',
        state.round_state,pc_melee_round_participants(state))).state
    started = start_combat_turn(CombatTurnStartRequest('focused:pc1:start',advanced,'pc1')).state
    return replace(state,round_state=started)


class PcCrossbowTests(unittest.TestCase):
    def test_two_exact_rows_hit_or_miss_spend_only_the_selected_profile_cycle(self):
        self.assertEqual(PC_CROSSBOW_WEAPONS,(CROSSBOW,REPEATER))
        self.assertEqual(tuple(w for w in PC_TWO_HANDED_RANGED_WEAPONS if w in PC_CROSSBOW_WEAPONS),(CROSSBOW,REPEATER))
        for weapon,mode,target in ((CROSSBOW,None,2),(REPEATER,WHEN,3),(REPEATER,NEVER,None)):
            for hit in (False,True):
                with self.subTest(weapon=weapon,mode=mode,hit=hit):
                    source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                        max_rounds=1,npc_toughness=20)
                    result = execute(source,shot_values(bonus=mode is WHEN,hit=hit)+NPC_MISS)
                    shot, = shots(result)
                    self.assertIs(raw(shot).outcome,AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertIs(raw(shot).miss_consequence,MissConsequence.NONE)
                    owner = shot.state.participant('pc1').ranged
                    preparation = shot.proof.ranged_shot.preparation.source_request
                    self.assertEqual(preparation.uses_optional_reload_bonus,mode is WHEN)
                    self.assertEqual(owner.loaded,target is None)
                    if target is None:
                        self.assertEqual(owner,shot.source.participant('pc1').ranged)
                        self.assertEqual(owner.reload_cycle_ids,())
                        self.assertIsNone(owner.exacting)
                        self.assertIsNone(preparation.next_reload_cycle_id)
                    else:
                        self.assertEqual(owner.required_successes,target)
                        self.assertEqual(owner.reload_cycle_ids,(preparation.next_reload_cycle_id,))
                        self.assertEqual(owner.exacting.accumulated_successes,0)
                    self.assertEqual(steps(result,PcRangedReloadProof),())
                    self.assertEqual(result.executed_actions,2)

    def test_only_plain_crossbow_gets_one_armoured_damage_bonus_from_explicit_source(self):
        for weapon,mode in ((CROSSBOW,None),(REPEATER,WHEN),(REPEATER,NEVER)):
            for armoured in (True,False):
                with self.subTest(weapon=weapon,mode=mode,armoured=armoured):
                    source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                        max_rounds=1,npc_toughness=3,npc_armour_bonus=3,npc_armoured=armoured)
                    values = [1,10,10,10,10,10] if mode is WHEN else [1,10,10,10,10]
                    result = execute(source,values+NPC_MISS)
                    shot, = shots(result)
                    attack = raw(shot)
                    self.assertEqual(attack.impact_spec.damage.base,4)
                    self.assertFalse(attack.impact_spec.ignores_armour)
                    self.assertEqual(attack.effective_resilience,6)
                    trait = tuple(modifier for modifier in attack.impact_spec.damage_modifiers
                        if modifier.rule_id==ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID)
                    expected = (1,) if weapon is CROSSBOW and armoured else ()
                    self.assertEqual(tuple(modifier.amount for modifier in trait),expected)
                    self.assertEqual(attack.damage,6 if expected else 5)
                    prepared = shot.proof.ranged_shot.preparation.profile_attack.kernel_request.attack
                    self.assertEqual(prepared.impact_spec.damage_modifiers,attack.impact_spec.damage_modifiers)

    def test_drained_focused_shot_keeps_damage_trait_but_declines_repeater_dice_and_cycle(self):
        # Real scene history supplies the initial shot context. The altered
        # Conditions below are a focused preparation, not a public fresh trial.
        for weapon,mode in ((CROSSBOW,None),(REPEATER,WHEN)):
            source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                max_rounds=1,npc_toughness=20,npc_armour_bonus=3,npc_armoured=True)
            result = execute(source,shot_values(bonus=mode is WHEN)+NPC_MISS)
            state = shots(result)[0].source
            member = state.party[0]
            state = replace(state,party=(replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
            request,_ = build_pc_melee_attack(state)
            test = request.kernel_request.attack.attacker_test
            self.assertFalse(any(modifier.amount>0 for modifier in test.dice_modifiers))
            rng = ScriptedD10([1,1,1,10,10])
            execution = execute_attack_action(request,rng)
            rng.assert_exhausted()
            proof = complete_pc_ranged_shot(state,request,request,execution)
            self.assertFalse(proof.preparation.source_request.uses_optional_reload_bonus)
            if weapon is CROSSBOW:
                self.assertEqual(tuple(modifier.amount for modifier in request.kernel_request.attack.impact_spec.damage_modifiers),(1,))
                self.assertFalse(proof.execution.weapon_state.loaded)
                self.assertEqual(proof.execution.weapon_state.required_successes,2)
            else:
                self.assertEqual(request.kernel_request.attack.impact_spec.damage_modifiers,())
                self.assertTrue(proof.execution.weapon_state.loaded)
                self.assertEqual(proof.execution.weapon_state.reload_cycle_ids,())
                self.assertIsNone(proof.preparation.source_request.next_reload_cycle_id)

    def test_repeater_bonus_choice_precedes_glorious_and_obeys_normal_cap(self):
        source = make_pc_crossbow_scenario(weapon=REPEATER,repeater_bonus_policy=WHEN,
            max_rounds=1,ballistic_skill=1,npc_toughness=20)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source,[10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(1,1,2,2))
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual((trace.initial_values,trace.final_values),((10,10),(1,1)))
        modifier, = tuple(modifier for modifier in shot.proof.request.kernel_request.attack.attacker_test.dice_modifiers
            if modifier.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID)
        self.assertFalse(modifier.bypasses_pool_cap)
        self.assertEqual(modifier.amount,1)
        self.assertTrue(shot.proof.ranged_shot.preparation.source_request.uses_optional_reload_bonus)
        self.assertFalse(result.state.participant('pc1').ranged.loaded)
        self.assertEqual(result.state.participant('pc1').ranged.required_successes,3)

    def test_real_approach_draws_even_loaded_primary_and_retains_all_charge_history(self):
        for weapon,mode,loaded in ((CROSSBOW,None,False),(REPEATER,WHEN,False),(REPEATER,NEVER,True)):
            with self.subTest(weapon=weapon,mode=mode):
                source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                    max_rounds=2,npc_armoured=True)
                result = execute(source,shot_values(bonus=mode is WHEN)+NPC_MISS+SWORD_HIT)
                draw, = steps(result,PcBackupWeaponDrawProof)
                self.assertEqual(draw.source.round_state.active_turn.actor_id,'pc1')
                self.assertEqual(draw.source.round_state.round_number,2)
                self.assertIs(draw.source.participant('pc1').weapon_hand,PcTwoHandedGrip.BOTH)
                owner = draw.source.participant('pc1').ranged
                self.assertEqual(owner.loaded,loaded)
                self.assertEqual(owner,draw.state.participant('pc1').ranged)
                self.assertEqual(owner,result.state.participant('pc1').ranged)
                self.assertEqual(steps(result,PcRangedReloadProof),())
                self.assertEqual(len(steps(result,PcNpcApproachProof)),1)
                melee = steps(result,PcAttackProof)[-1]
                self.assertIsNone(melee.proof.ranged_shot)
                self.assertEqual(raw(melee).impact_spec.damage.base,3)
                self.assertEqual(raw(melee).impact_spec.damage_modifiers,())
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(result.executed_actions,3)

    def test_loaded_or_empty_no_backup_stop_is_real_close_boundary_without_fake_wound(self):
        for weapon,mode in ((CROSSBOW,None),(REPEATER,WHEN),(REPEATER,NEVER)):
            with self.subTest(weapon=weapon,mode=mode):
                source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                    backup=False,max_rounds=3)
                result = execute(source,shot_values(bonus=mode is WHEN)+NPC_MISS)
                self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
                self.assertEqual(result.executed_actions,2)
                self.assertEqual(result.state.round_state.round_number,2)
                self.assertEqual(result.state.round_state.active_turn.action_slots,())
                self.assertEqual(result.state.party[0].injury.wounds,())
                self.assertFalse(hasattr(result.unsupported,'wound_sequence'))
                self.assertEqual(steps(result,PcRangedReloadProof),())

    def test_full_preparation_rejects_missing_replayed_and_doubled_damage_proofs(self):
        for weapon,mode in ((CROSSBOW,None),(REPEATER,NEVER)):
            source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                max_rounds=1,npc_toughness=20,npc_armour_bonus=3,npc_armoured=True)
            result = execute(source,shot_values()+NPC_MISS)
            shot, = shots(result)
            self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,replace(shot.proof,ranged_shot=None))
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(shot.state,shot)
            proof = deepcopy(shot.proof)
            object.__setattr__(proof.ranged_shot.preparation.source_request.weapon_state,
                'weapon_instance_id','other-actor:weapon')
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,proof)
            if weapon is CROSSBOW:
                proof = deepcopy(shot.proof)
                impact = proof.request.kernel_request.attack.impact_spec
                self.assertEqual(len(impact.damage_modifiers),1)
                object.__setattr__(impact,'damage_modifiers',impact.damage_modifiers*2)
                with self.assertRaises((TypeError,ValueError)):
                    PcMeleeStep(shot.source,proof)

    def test_focused_reload_binds_actual_two_or_three_target_and_explicit_dexterity_source(self):
        for weapon,mode,target,values in ((CROSSBOW,None,2,[1,1,10,10]),
                (REPEATER,WHEN,3,[1,1,1,10])):
            with self.subTest(weapon=weapon):
                source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
                    max_rounds=1,initiative=4,dexterity=5)
                result = execute(source,shot_values(bonus=mode is WHEN)+NPC_MISS)
                state = focused_next_pc_turn(result)
                self.assertTrue(pc_has_close_enemy(state,'pc1'))
                self.assertFalse(state.party[0].ranged.loaded)
                declaration = ranged_reload_declaration(state,'pc1')
                clock = reserve_combat_action_slot(CombatActionSlotRequest('focused:reserve',
                    state.round_state,'pc1',declaration,ActionSlotGrant.STANDARD)).state
                state = replace(state,round_state=clock)
                request = build_pc_ranged_reload(state)
                self.assertIs(request.weapon_state,state.party[0].ranged)
                self.assertEqual(request.weapon_state.required_successes,target)
                self.assertEqual(request.dexterity_test.profile,TestProfile(4,5))
                rng = ScriptedD10(values)
                reloaded = execute_reload_action(request,rng)
                rng.assert_exhausted()
                self.assertTrue(reloaded.completed)
                self.assertTrue(reloaded.state.loaded)
                self.assertEqual(reloaded.state.reload_cycle_id,state.party[0].ranged.reload_cycle_id)
                self.assertEqual(reloaded.state.reload_cycle_ids,state.party[0].ranged.reload_cycle_ids)
                self.assertTrue(reloaded.slot.executed)
                with self.assertRaises((TypeError,ValueError)):
                    replace(request.weapon_state,required_successes=3 if target==2 else 2)
                member = replace(state.party[0],ranged=reloaded.state)
                still_close = replace(state,party=(member,),round_state=reloaded.round_state)
                with self.assertRaises((TypeError,ValueError)):
                    build_pc_melee_attack(still_close)

    def test_focused_loaded_two_handed_shot_cannot_use_only_one_arm(self):
        for weapon,mode in ((CROSSBOW,None),(REPEATER,NEVER)):
            source = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,max_rounds=1)
            result = execute(source,shot_values()+NPC_MISS)
            shot, = shots(result)
            state = shot.source
            member = state.party[0]
            wound = WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(),effect_resolved=True,
                origin=WoundRecordOrigin.FIXED_ENTRY)
            member = replace(member,injury=replace(member.injury,wounds=(wound,)),
                body_facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),))
            blocked = replace(state,party=(member,))
            self.assertTrue(blocked.party[0].ranged.loaded)
            with self.assertRaises((TypeError,ValueError)):
                prepare_pc_ranged_shot(blocked,shot.proof.request)

    def test_actual_wound_sixteen_uses_healthy_backup_and_mandatory_critical_test(self):
        source = make_pc_crossbow_scenario(weapon=REPEATER,repeater_bonus_policy=NEVER,
            enemy_count=3,max_rounds=2)
        first_round = shot_values()+NPC_HIT+[1]+NPC_HIT+[1,1]+NPC_HIT+[10,1,5,10]
        result = execute(source,first_round+SWORD_HIT+[1,1,1]+[10,10,1,1,1,1]*2)
        draw, = steps(result,PcBackupWeaponDrawProof)
        self.assertIs(draw.proof.hand,PcWeaponHand.LEFT)
        self.assertEqual(draw.source.participant('pc1').injury.wounds[-1].table_total,16)
        self.assertTrue(draw.source.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(result.state.party[0].ranged.loaded)
        self.assertEqual(result.state.party[0].ranged.reload_cycle_ids,())
        self.assertEqual(len(shots(result)),1)
        self.assertEqual(steps(result,PcRangedReloadProof),())

    def test_two_actors_keep_distinct_regular_empty_and_repeater_loaded_instances(self):
        source = make_pc_crossbow_scenario(pc_count=2,enemy_count=2,max_rounds=1)
        first,second = source.party
        second = replace(second,pc=replace(second.pc,weapon=REPEATER,
            ranged=crossbow_profile(weapon=REPEATER,repeater_bonus_policy=NEVER)))
        source = replace(source,party=(first,second))
        result = execute(source,shot_values()*2+NPC_MISS*2)
        a,b = (member.ranged for member in result.state.party)
        self.assertNotEqual(a.weapon_instance_id,b.weapon_instance_id)
        self.assertIsNot(a,b)
        self.assertFalse(a.loaded)
        self.assertEqual(a.required_successes,2)
        self.assertEqual(len(a.reload_cycle_ids),1)
        self.assertTrue(b.loaded)
        self.assertEqual(b.reload_cycle_ids,())


if __name__=='__main__':
    unittest.main()
