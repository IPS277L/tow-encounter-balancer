"""C20 actual outcomes retain their failed raw dice and finite session price."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.magic_weapon_battles import magic_battle
from tests.support.oath_sources import context, honour, with_native_outcome_owner
from tests.support.pc_tactics_fixtures import weak_helper_source
from tests.support.pc_magic_scenarios import magic_scenario
from towr.domain.attack_models import AttackOutcome
from towr.domain.fate_models import FateSpendKind, FateSpendFunding
from towr.domain.pc_melee_result_models import (
    initial_pc_melee_state, PcMeleeStep, PcAttackProof, PcHelpProof, PcEnduranceProof,
)
from towr.domain.pc_oath_models import actor_oath, oath_step_evidence, pc_honour_outcome_id
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_melee_models import PcGloriousPolicy
from towr.domain.pc_magic_models import PcCastingProof, PcMiscastRollProof
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_falling_models import PcFallingProof
from towr.domain.test_models import TestResult, Skill
from towr.domain.honour_bound_models import (
    HonourBoundUnmitigatedRequest, activate_honour_bound_unmitigated, grant_honour_bound_outcome,
)
from towr.rules.attack_resolution import _resolve_attack_after_tests
from towr.rules.kernel import _resolve_kernel_attack_after_test
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.domain.talent_catalog import TalentId


class Tens:
    def __init__(self):
        self.calls=0

    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('unexpected non-d10 draw')
        self.calls+=1
        if self.calls>500:
            raise AssertionError('short native scenario exhausted its literal-failure budget')
        return 10


def actual_tests(result):
    seen=set()
    for step in result.steps:
        for value in oath_step_evidence(step.proof):
            if type(value) is TestResult and value.trace.request_id not in seen:
                seen.add(value.trace.request_id)
                yield value


def grants(result):
    return tuple(value for value in actual_tests(result) if value.honour_bound is not None)


class HonourOutcomeNativeTests(unittest.TestCase):
    def assert_replays(self,source,result):
        state=initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,state)
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)

    def assert_actual_grant(self,source,result,test,*,free=False):
        raw=test.honour_bound.raw_test
        activation=test.honour_bound.activation
        actor=activation.state.actor_id
        initial=source.participant(actor).fate
        self.assertEqual(test.trace,raw.trace)
        self.assertEqual(test.successes,0)
        self.assertEqual(raw.successes,0)
        self.assertIsNone(raw.honour_bound)
        self.assertGreater(test.effective_successes,0)
        self.assertEqual(test.effective_successes,test.trace.rolled_dice+test.trace.success_delta)
        self.assertEqual(activation.spend.kind,FateSpendKind.HONOUR_BOUND_UNMITIGATED_SUCCESS)
        self.assertEqual(activation.spend.funding,FateSpendFunding.LUCKY_FREE if free else FateSpendFunding.SESSION_POOL)
        final=result.state.participant(actor).fate
        self.assertEqual(final.rating,initial.rating)
        self.assertEqual(final.burns,initial.burns)
        self.assertEqual(final.spends,(*initial.spends,activation.spend))
        self.assertEqual(len(actor_oath(result.state,actor).honour_uses),1)
        self.assertFalse(actor_oath(result.state,actor).honour.available)

    def forged_but_kernel_valid_attack(self,step,funder):
        """The low-level rule cannot infer the native Test's actual actor.

        Construct its canonical strike with a separately valid generic grant,
        so rejection must come from the native policy/actor source owner.
        """
        proof=step.proof
        state=step.source
        request=proof.request.kernel_request
        test_request=request.attack.attacker_test
        raw=proof.execution.resolution.attack.attacker_test
        row=actor_oath(state,funder)
        activation=activate_honour_bound_unmitigated(HonourBoundUnmitigatedRequest(
            pc_honour_outcome_id(state,funder,test_request.id),row.honour,row.context,
            state.participant(funder).fate,test_request,
            row.context.gm_confirmation_id+':maximum-legal-outcome',final_result=raw))
        grant=grant_honour_bound_outcome(activation)
        attack=_resolve_attack_after_tests(request.attack,grant,proof.execution.resolution.attack.defender_test)
        resolution=_resolve_kernel_attack_after_test(request,attack,Tens())
        return replace(proof,execution=replace(proof.execution,resolution=resolution))

    def test_failed_raw_attack_hits_and_wounds_without_rewriting_zero_successes(self):
        source=with_native_outcome_owner(magic_battle('staff',pc_ws=1,pc_strength=6,npc_toughness=3,rounds=1))
        result=run_pc_melee_scenario(source,Tens())
        actual=grants(result)
        self.assertEqual(len(actual),1)
        self.assert_actual_grant(source,result,actual[0])
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertIs(attack.execution.resolution.attack.outcome,AttackOutcome.HIT)
        self.assertEqual(attack.execution.resolution.profile_wound.wounds_inflicted,1)
        self.assertTrue(result.state.enemies[0].state.injury.defeated)
        self.assert_replays(source,result)

    def test_protection_total_success_blocks_an_attack_even_when_maximum_ties(self):
        original=magic_battle('staff',pc_ws=1,npc_ws=1,pc_strength=1,
            pc_toughness=20,npc_toughness=20,rounds=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,agility=1))
        npc=replace(original.enemies[0].definition.generated_components,agility=1,talents=(),talent_facts=None)
        original=replace(original,party=(member,),enemies=(npc.participant(original.enemy_activation_order[0]),))
        source=with_native_outcome_owner(original)
        rng=SequenceRandom([1,1,1,10])
        result=run_pc_melee_scenario(source,rng)
        actual=grants(result)
        self.assertEqual(len(actual),1)
        self.assert_actual_grant(source,result,actual[0])
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.enemy_activation_order[0])
        self.assertEqual(attack.execution.resolution.attack.attacker_test.successes,1)
        self.assertEqual(attack.execution.resolution.attack.defender_test.successes,0)
        self.assertIs(attack.execution.resolution.attack.outcome,AttackOutcome.MISS)
        self.assert_replays(source,result)

    def test_empty_pistol_reload_uses_explicit_progress_with_failed_raw_dice(self):
        original=magic_battle('pistol',npc_ws=1,npc_toughness=3,rounds=5)
        enemy=original.enemies[0]
        npc=replace(enemy.definition.generated_components,agility=1)
        original=replace(original,enemies=(npc.participant(enemy.state.actor_id),))
        member=replace(original.party[0],pc=replace(original.party[0].pc,
            ranged=replace(original.party[0].pc.ranged,dexterity=3)))
        equipment=(replace(member.combat_equipment[0],initially_loaded=False),*member.combat_equipment[1:])
        original=replace(original,party=(replace(member,combat_equipment=equipment),))
        source=with_native_outcome_owner(original)
        result=run_pc_melee_scenario(source,SequenceRandom([10]*7+[1]*100))
        reload=next(step.proof for step in result.steps if type(step.proof) is PcRangedReloadProof)
        test=reload.result.exacting.test_result
        self.assert_actual_grant(source,result,test)
        self.assertEqual(reload.result.exacting.contribution.successes,test.effective_successes)
        self.assertEqual(reload.result.exacting.progress.accumulated_successes,test.effective_successes)
        self.assertTrue(reload.result.state.loaded)
        self.assert_replays(source,result)

    def test_lucky_zero_rating_funds_the_real_first_spend_without_a_burn(self):
        source=with_native_outcome_owner(magic_battle('staff',pc_ws=1,pc_strength=6,npc_toughness=3,rounds=1),
            fate=0,lucky=True)
        result=run_pc_melee_scenario(source,Tens())
        actual=grants(result)
        self.assertEqual(len(actual),1)
        self.assert_actual_grant(source,result,actual[0],free=True)
        final=result.state.party[0].fate
        self.assertEqual(final.rating,0)
        self.assertEqual(final.remaining_spends,0)
        self.assertFalse(final.lucky_free_spend_available)
        self.assert_replays(source,result)

    def test_help_bonus_uses_the_confirmed_progress_and_retains_failed_raw_test(self):
        original=weak_helper_source()
        helper=replace(original.party[0],pc=replace(original.party[0].pc,melee=2))
        source=with_native_outcome_owner(replace(original,party=(helper,*original.party[1:])),actor='pc1')
        result=run_pc_melee_scenario(source,Tens())
        help=next(step.proof for step in result.steps if type(step.proof) is PcHelpProof)
        test=help.execution.help_test_result
        self.assert_actual_grant(source,result,test)
        self.assertEqual(help.execution.bonus.bonus_dice,test.effective_successes)
        self.assertEqual(help.execution.bonus.source_test_id,test.trace.request_id)
        self.assert_replays(source,result)

    def test_casting_progress_and_actual_nines_miscast_both_survive_the_override(self):
        source=with_native_outcome_owner(magic_scenario(reason=2,willpower=1,level=1,rounds=1,
            spells=(PcSpellId.LIGHTNING_BLAST,)))
        rng=SequenceRandom([9,9,3,4,6]+[10]*100)
        result=run_pc_melee_scenario(source,rng)
        cast=next(step.proof for step in result.steps if type(step.proof) is PcCastingProof)
        test=cast.execution.casting.test
        self.assert_actual_grant(source,result,test)
        self.assertEqual(test.trace.initial_values,(9,9))
        self.assertEqual(test.trace.final_values,(9,9))
        self.assertEqual(cast.execution.casting.latest_roll_successes,test.effective_successes)
        self.assertEqual(cast.execution.casting.miscast_dice_added,2)
        miscasts=[step.proof for step in result.steps if type(step.proof) is PcMiscastRollProof]
        self.assertEqual(len(miscasts),1)
        self.assertEqual(miscasts[0].request.pool_dice_count,2)
        self.assertEqual(miscasts[0].request.bonus_dice,1)  # Actual successful cast before the Miscast.
        self.assertEqual(miscasts[0].result.roll_values,(3,4,6))
        self.assertEqual(miscasts[0].result.total,13)
        self.assertIs(cast.spell_id,PcSpellId.LIGHTNING_BLAST)
        self.assert_replays(source,result)

    def test_unconfirmed_unfulfilled_barred_or_spent_oath_cannot_grant_an_outcome(self):
        for change in ({'unmitigated_success_scope_confirmed':False},
                {'combat_tests_fulfil_oath_confirmed':False}, {'in_good_standing_confirmed':False},
                {'honour_bound_used_this_session':True}):
            with self.subTest(change=change):
                source=with_native_outcome_owner(magic_battle('staff',rounds=1))
                member=source.party[0]
                # An explicit reserve disables the separate ordinary Glorious
                # option while preserving the current configured-Fate source.
                member=replace(member,oath_context=replace(member.oath_context,**change),
                    glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,2))
                source=replace(source,party=(member,))
                result=run_pc_melee_scenario(source,Tens())
                self.assertEqual(grants(result),())
                self.assertEqual(result.state.party[0].fate.spends,())
                self.assertEqual(result.state.party[0].fate.burns,())

    def test_generated_npc_never_receives_the_pc_fate_outcome(self):
        original=magic_battle('staff',rounds=1)
        enemy=original.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(honour(),),
            oath_context=replace(context(unmitigated_success_scope_confirmed=True),forbidden_attack_skills=()))
        source=replace(original,enemies=(npc.participant(enemy.state.actor_id),))
        result=run_pc_melee_scenario(source,Tens())
        self.assertEqual(grants(result),())
        self.assertFalse(hasattr(result.state.enemy(enemy.state.actor_id).state,'fate'))
        self.assertEqual(len(actor_oath(result.state,enemy.state.actor_id).honour_uses),1)
        self.assert_replays(source,result)

    def test_forbidden_attacks_and_advice_cannot_manufacture_a_funded_test(self):
        source=with_native_outcome_owner(magic_battle('staff',rounds=1))
        forbidden=(Skill.MELEE,Skill.BRAWN,Skill.SHOOTING,Skill.THROWING)
        member=replace(source.party[0],oath_context=replace(source.party[0].oath_context,
            forbidden_attack_skills=forbidden))
        enemy=source.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(honour(),),
            oath_context=replace(context(unmitigated_success_scope_confirmed=True),
                forbidden_attack_skills=forbidden))
        source=replace(source,party=(member,),enemies=(npc.participant(enemy.state.actor_id),))
        rng=Tens()
        result=run_pc_melee_scenario(source,rng)
        self.assertEqual(rng.calls,0)
        self.assertEqual(tuple(actual_tests(result)),())
        self.assertEqual(grants(result),())
        self.assertEqual(result.state.party[0].fate,member.fate)
        self.assertTrue(actor_oath(result.state,member.actor_id).honour.available)
        self.assertFalse(any(type(step.proof) is PcAttackProof for step in result.steps))
        self.assertEqual(result.executed_actions,2)
        self.assert_replays(source,result)

    def test_session_use_is_not_refilled_by_an_actual_later_round(self):
        source=with_native_outcome_owner(magic_battle('staff',pc_ws=1,pc_toughness=20,npc_toughness=20,rounds=3))
        result=run_pc_melee_scenario(source,Tens())
        self.assertEqual(len(grants(result)),1)
        self.assert_actual_grant(source,result,grants(result)[0])
        self.assertEqual(len(actor_oath(result.state,source.pc_activation_order[0]).honour_uses),1)
        self.assertGreater(len(tuple(actual_tests(result))),1)
        self.assert_replays(source,result)

    def test_real_wound_endurance_succeeds_without_erasing_the_accepted_wound(self):
        original=magic_battle('staff',pc_ws=1,npc_ws=6,pc_toughness=3,npc_toughness=20,rounds=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,agility=1,endurance=2))
        npc=replace(original.enemies[0].definition.generated_components,agility=1,strength=6,
            talents=(),talent_facts=None)
        source=with_native_outcome_owner(replace(original,party=(member,),
            enemies=(npc.participant(original.enemy_activation_order[0]),)))
        rng=SequenceRandom([1]*14+[4]+[10]*3)
        result=run_pc_melee_scenario(source,rng)
        endurance=next(step.proof for step in result.steps if type(step.proof) is PcEnduranceProof)
        self.assert_actual_grant(source,result,endurance.test)
        self.assertTrue(endurance.result.succeeded)
        self.assertEqual(endurance.result.follow_ups,())
        final=result.state.party[0]
        self.assertEqual(tuple(wound.table_total for wound in final.injury.wounds),(4,))
        self.assertEqual(final.daily_wounds.wound_count,1)
        self.assertIsNotNone(final.weapon_inventory.active)
        self.assert_replays(source,result)

    def test_actual_falling_hazard_preserves_its_wound_and_uses_own_test_outcome(self):
        from tests.integration.test_pc_falling_native import falling_source
        original=falling_source()
        battlefield=replace(original.battlefield,airspace=replace(original.battlefield.airspace,
            fall_hazard_rating=1))
        source=with_native_outcome_owner(replace(original,battlefield=battlefield))
        rng=SequenceRandom([1]*9+[9,10]+[10]*50)
        result=run_pc_melee_scenario(source,rng)
        falling=next(step.proof for step in result.steps if type(step.proof) is PcFallingProof)
        self.assert_actual_grant(source,result,falling.test)
        self.assertTrue(falling.result.avoided)
        self.assertEqual(falling.result.rating,1)
        self.assertEqual(falling.result.successes,falling.test.effective_successes)
        self.assertIsNone(falling.result.pending_character_wound)
        final=result.state.party[0]
        self.assertEqual(tuple(wound.table_total for wound in final.injury.wounds),(9,))
        self.assertEqual(final.daily_wounds.wound_count,1)
        self.assert_replays(source,result)

    def test_generic_grant_on_a_positive_raw_test_cannot_override_the_native_choice(self):
        source=with_native_outcome_owner(magic_battle('staff',pc_ws=1,pc_strength=6,npc_toughness=3,rounds=1))
        result=run_pc_melee_scenario(source,SequenceRandom([1]*100))
        step=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.pc_activation_order[0])
        self.assertGreater(step.proof.execution.resolution.attack.attacker_test.successes,0)
        self.assertIsNone(step.proof.execution.resolution.attack.attacker_test.honour_bound)
        forged=self.forged_but_kernel_valid_attack(step,source.pc_activation_order[0])
        with self.assertRaisesRegex(ValueError,'automatic failed-Test decision'):
            PcMeleeStep(step.source,forged)
        self.assertEqual(step.source.party[0].fate.spends,())

    def test_actual_npc_attack_cannot_spend_a_pc_grant_with_matching_raw_trace(self):
        original=magic_battle('staff',pc_ws=1,npc_ws=1,pc_strength=1,
            pc_toughness=20,npc_toughness=20,rounds=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,agility=1))
        npc=replace(original.enemies[0].definition.generated_components,agility=1,talents=(),talent_facts=None)
        source=with_native_outcome_owner(replace(original,party=(member,),
            enemies=(npc.participant(original.enemy_activation_order[0]),)))
        result=run_pc_melee_scenario(source,SequenceRandom([1,1,10,1]))
        step=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.enemy_activation_order[0])
        self.assertEqual(step.proof.execution.resolution.attack.attacker_test.successes,0)
        funder=source.pc_activation_order[0]
        self.assertTrue(actor_oath(step.source,funder).honour.available)
        forged=self.forged_but_kernel_valid_attack(step,funder)
        self.assertEqual(forged.execution.resolution.attack.attacker_test.trace,
            step.proof.execution.resolution.attack.attacker_test.trace)
        self.assertNotEqual(forged.request.actor_id,
            forged.execution.resolution.attack.attacker_test.honour_bound.activation.state.actor_id)
        with self.assertRaisesRegex(ValueError,"another actor's actual Test"):
            PcMeleeStep(step.source,forged)
        self.assertTrue(actor_oath(step.source,funder).honour.available)


if __name__=='__main__':
    unittest.main()
