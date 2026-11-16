from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import unittest

from tests.support.pc_tactics_fixtures import automatic_source, weak_helper_source, tactical_snapshot
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_melee_models import PcMeleePolicy, PcHelpTarget, PcFatePolicy, PcGloriousPolicy
from towr.domain.pc_melee_result_models import PcHelpProof, PcAttackProof, PcRecoverProof, PcMeleeOutcome
from towr.domain.pc_tactical_models import select_pc_tactic, _distribution
from towr.domain.test_models import TestProfile, TestRequest, DiceModifier, QualityModifier, TestQuality, InlineProfile, Skill
from towr.domain.fate_models import FateSpendFunding
from towr.domain.turn_models import CombatActionKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import (PcMeleeSimulationRequest, PcHelpActionCount, validate_help_counts,
    PcAllyRecoverActionCount, validate_automatic_action_budget)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def conditions(state, actor, *values):
    member = state.participant(actor)
    changed = replace(member, injury=replace(member.injury, conditions=ConditionState(frozenset(values))))
    return replace(state, party=tuple(changed if item.actor_id==actor else item for item in state.party))


class AutomaticMeleeTacticsTests(unittest.TestCase):
    def test_probability_inputs_use_canonical_minimum_cap_and_quality(self):
        normal = TestRequest('normal', TestProfile(2,5))
        self.assertEqual(_distribution(normal), (0.25,0.5,0.25))
        minimum = replace(normal, dice_modifiers=(DiceModifier('penalty',-9),))
        self.assertEqual(_distribution(minimum), (0.9,0.1))
        self.assertEqual(_distribution(replace(normal, dice_modifiers=(DiceModifier('bonus',99),))),
            (0.0625,0.25,0.375,0.25,0.0625))
        for quality, expected in ((TestQuality.GRIM,(0.5625,0.375,0.0625)),
                (TestQuality.GLORIOUS,(0.0625,0.375,0.5625))):
            self.assertEqual(_distribution(replace(normal,
                quality_modifiers=(QualityModifier('quality',quality),))), expected)

    def test_healthy_character_attacks_and_choice_is_frozen_and_repeatable(self):
        state = tactical_snapshot(automatic_source())
        original = state
        with patch('random.Random', side_effect=AssertionError('selector must not create RNG')):
            first = select_pc_tactic(state)
            self.assertEqual(select_pc_tactic(state), first)
        self.assertIs(first.action, CombatActionKind.ATTACK)
        self.assertEqual(first.target_id, 'minion1')
        self.assertEqual(state, original)
        with self.assertRaises(FrozenInstanceError):
            first.target_id = 'other'

    def test_target_choice_prefers_actual_staggered_minion_without_rewriting_priorities(self):
        source = automatic_source(enemy_count=2)
        # Make both enemies too tough for direct Wounds; repeated Staggered
        # gives one real defeat instead of merely staggering the fresh target.
        enemies = []
        for index, enemy in enumerate(source.enemies):
            resilience = replace(enemy.state.current_resilience, toughness=20)
            definition = replace(enemy.definition,resilience=resilience)
            enemies.append(replace(enemy,definition=definition,state=replace(enemy.state,
                current_resilience=resilience)))
        source = replace(source, enemies=tuple(enemies))
        state = tactical_snapshot(source)
        enemy = state.enemies[1]
        enemy = replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset((Condition.STAGGERED,))))))
        state = replace(state,enemies=(state.enemies[0],enemy))
        choice = select_pc_tactic(state)
        self.assertIs(choice.action, CombatActionKind.ATTACK)
        self.assertEqual(choice.target_id, 'minion2')
        self.assertEqual(source.party[0].target_priority, ('minion1','minion2'))

    def test_weak_attacker_selects_strong_later_ally_without_source_binding(self):
        source = weak_helper_source()
        choice = select_pc_tactic(tactical_snapshot(source))
        self.assertIs(choice.action, CombatActionKind.HELP)
        self.assertEqual(choice.target_id, 'pc2')
        self.assertIs(choice.help_policy.target, PcHelpTarget.MELEE_ATTACK)
        self.assertTrue(all(member.help_policy is None for member in source.party))

    def test_drained_beneficiary_and_deafened_helper_do_not_receive_fake_help(self):
        state = tactical_snapshot(weak_helper_source())
        for changed in (conditions(state,'pc2',Condition.DRAINED),
                conditions(state,'pc1',Condition.DEAFENED)):
            self.assertIsNot(select_pc_tactic(changed).action, CombatActionKind.HELP)
        finished = replace(state, round_state=replace(state.round_state,
            completed_turn_entity_ids=('pc2',)))
        self.assertIsNot(select_pc_tactic(finished).action, CombatActionKind.HELP)

    def test_help_is_not_chosen_when_the_recipient_attack_already_reaches_its_cap(self):
        source = weak_helper_source()
        ally = source.party[1]
        source = replace(source,party=(source.party[0],replace(ally,pc=replace(ally.pc,weapon_skill=1))))
        self.assertIs(select_pc_tactic(tactical_snapshot(source)).action,CombatActionKind.ATTACK)

    def test_self_readiness_and_helping_prone_ally_are_actual_recover_choices(self):
        state = tactical_snapshot(weak_helper_source())
        own = select_pc_tactic(conditions(state,'pc1',Condition.PRONE))
        self.assertIs(own.action, CombatActionKind.RECOVER)
        self.assertEqual(own.target_id,'pc1')
        ally = select_pc_tactic(conditions(state,'pc2',Condition.PRONE))
        self.assertIs(ally.action, CombatActionKind.RECOVER)
        self.assertEqual(ally.target_id,'pc2')

    def test_staggered_is_not_an_unconditional_recover_loop(self):
        source = automatic_source(pc_count=1)
        enemy = source.enemies[0]
        attack = replace(enemy.definition.attacks[0], damage=replace(enemy.definition.attacks[0].damage,base=30))
        definition = replace(enemy.definition, attacks=(attack,))
        source = replace(source,enemies=(replace(enemy,definition=definition),))
        state = conditions(tactical_snapshot(source),'pc1',Condition.STAGGERED)
        self.assertIs(select_pc_tactic(state).action,CombatActionKind.ATTACK)

    def test_protection_help_selects_actual_incoming_test_and_matching_skill(self):
        source = automatic_source()
        party = tuple(replace(member,pc=replace(member.pc,weapon_skill=1,melee=1,
            defence=1 if index==0 else 6,strength=1,toughness=10))
            for index,member in enumerate(source.party))
        enemy = source.enemies[0]
        definition = replace(enemy.definition,protection=(replace(enemy.definition.protection[0],
            test_profile=InlineProfile(8,6)),))
        source = replace(source,party=party,enemies=(replace(enemy,definition=definition),))
        choice = select_pc_tactic(tactical_snapshot(source,'pc2'))
        self.assertIs(choice.action,CombatActionKind.HELP)
        self.assertEqual(choice.target_id,'pc1')
        self.assertIs(choice.help_policy.target,PcHelpTarget.FIRST_INCOMING_PROTECTION)

    def test_literal_native_help_is_consumed_by_exact_attack_and_explained(self):
        source = weak_helper_source()
        values = [1]+[1]*8+[10]*6
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        help_proof = next(step.proof for step in result.steps if isinstance(step.proof,PcHelpProof))
        attack = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof))
        self.assertEqual(help_proof.request.beneficiary_id,'pc2')
        self.assertEqual(len(attack.help_applications),1)
        self.assertEqual(attack.help_applications[0].source_request.help,help_proof.execution)
        self.assertEqual(tuple(choice.action for choice in result.tactical_decisions),
            (CombatActionKind.HELP,CombatActionKind.ATTACK))
        record = run_pc_melee_trial(PcMeleeSimulationRequest(source,42,1),0,
            rng_factory=lambda _:ScriptedD10(values))
        self.assertEqual(tuple(item.count for item in record.help_action_counts),(1,0))

    def test_automatic_help_can_spend_only_its_helpers_actual_lucky_funding(self):
        source = weak_helper_source()
        helper = source.party[0]
        helper = replace(helper,fate=replace(helper.fate,rating=0,session_spend_limit=0,has_lucky=True),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0))
        source = replace(source,party=(helper,source.party[1]))
        rng = ScriptedD10([10,1]+[1]*8+[10]*6)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if isinstance(step.proof,PcHelpProof))
        self.assertIs(proof.glorious.spend.funding,FateSpendFunding.LUCKY_FREE)
        self.assertFalse(result.state.participant('pc1').fate.lucky_free_spend_available)
        self.assertEqual(result.state.participant('pc2').fate,source.party[1].fate)

    def test_native_ally_recover_after_an_actual_miss_has_source_bound_counts(self):
        source = weak_helper_source()
        strong = replace(source.party[1].pc,defence=1,toughness=10)
        weak = source.party[0].pc
        source = replace(source,party=(replace(source.party[0],pc=strong),replace(source.party[1],pc=weak)))
        values = [10]*7+[1]*6+[10]*2+[1]*6
        rng = ScriptedD10(values)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if isinstance(step.proof,PcRecoverProof))
        self.assertEqual(proof.result.source_request.actor_id,'pc2')
        self.assertEqual(tuple(change.entity_id for change in proof.result.resolution.condition_changes),('pc1',))
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        record = run_pc_melee_trial(PcMeleeSimulationRequest(source,42,1),0,
            rng_factory=lambda _:ScriptedD10(values))
        self.assertEqual(tuple(item.count for item in record.ally_recover_action_counts),(0,1))

    def test_single_pc_cannot_forge_help_counts_and_mode_has_a_closed_boundary(self):
        source = automatic_source(pc_count=1)
        with self.assertRaises(ValueError):
            validate_help_counts((PcHelpActionCount('pc1',1),),source,trials=1,
                help_trials=1,actions=1,started_rounds=1)
        with self.assertRaises(ValueError):
            replace(source,facts=replace(source.facts,all_opponents_close=False))
        with self.assertRaises(ValueError):
            replace(source.party[0],help_policy=object())

    def test_automatic_support_kinds_share_one_actor_turn_budget(self):
        source = automatic_source()
        with self.assertRaises(ValueError):
            validate_automatic_action_budget((PcHelpActionCount('pc1',0),PcHelpActionCount('pc2',1)),
                (PcAllyRecoverActionCount('pc1',0),PcAllyRecoverActionCount('pc2',1)),
                source,started_rounds=1)


if __name__ == '__main__':
    unittest.main()
