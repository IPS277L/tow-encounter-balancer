"""Wild Attack on actual immediate Bash, with finite local advice boundaries."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.unit.test_bash_attack_execution import pc_source, npc_source
from towr.domain.condition_models import Condition
from towr.domain.pc_bash_attack_models import build_pc_bash_strike
from towr.domain.pc_bash_wild_attack import expected_bash_wild_attack
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_generated_talents import (
    PcWildAttackProof, WILD_ATTACK_RULE_ID, expected_wild_attack, pending_wild_attack,
)
from towr.domain.pc_immediate_attack_models import PcBashDecisionProof, PcImmediateStrikeProof
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcMeleePolicy, PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import QualityModifier, Skill, TestQuality
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponItemLocation as L
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def pc_wild_source(*, fate=False):
    source = pc_source()
    row = source.party[0]
    row = replace(row, talents=(*row.talents, paid_talent(TalentId.WILD_ATTACK)),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        fate_policy=PcFatePolicy.CONFIGURED if fate else row.fate_policy,
        glorious_policy=PcGloriousPolicy((Skill.MELEE,),20,0) if fate else None)
    return replace(source, party=(row,))


def npc_wild_source():
    """The real preceding Net HIT gives Burdened, leaving NPC free of Staggered."""
    source = npc_source()
    row = source.party[0]
    row = replace(row, pc=replace(row.pc, weapon=W.WEIGHTED_NET, ballistic_skill=3, throwing=5),
        combat_equipment=(PcWeaponItem('net',W.WEIGHTED_NET,L.HELD,PcTwoHandedGrip.BOTH),),
        initial_weapon_hand=PcTwoHandedGrip.BOTH, policy=PcMeleePolicy.AUTOMATIC_COMBAT)
    components = source.enemies[0].definition.generated_components
    components = replace(components, talents=(*components.talents, paid_talent(TalentId.WILD_ATTACK)))
    return replace(source, party=(row,), enemies=(components.participant('minion1'),))


class _PreparedActorConditions:
    """A local query boundary; no invented native journal of these Conditions."""
    def __init__(self, previous, actor, condition):
        self.previous, self.actor, self.condition = previous, actor, condition

    def __getattr__(self, name):
        return getattr(self.previous,name)

    def participant(self, actor):
        member = self.previous.participant(actor)
        return replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(self.condition))) if actor == self.actor else member


class BashWildAttackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = pc_wild_source()
        rng = ScriptedD10([1]*5+[10]*2+[1]*3+[10]*2)
        cls.pc_result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()

    def assert_replays(self, result):
        state = initial_pc_melee_state(result.source)
        for step in result.steps:
            state = apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def assert_paid_strike(self, result, actor):
        price, = tuple(step for step in result.steps if type(step.proof) is PcWildAttackProof)
        strike, = tuple(step for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        self.assertEqual(price.proof.action_id,strike.proof.request.id)
        self.assertEqual(price.proof.attack_weapon_intent,strike.proof.weapon_intent)
        self.assertEqual(price.proof.intent.target_id,strike.proof.request.target_id)
        self.assertEqual(price.proof.attack_weapon_intent.attack_use,
            strike.proof.request.decision.selection.use)
        self.assertEqual(price.source.round_state,price.state.round_state)
        before = (price.source.participant(actor).injury if actor == 'pc'
            else price.source.enemy(actor).state.injury)
        after = (price.state.participant(actor).injury if actor == 'pc'
            else price.state.enemy(actor).state.injury)
        self.assertFalse(before.conditions.has(Condition.STAGGERED))
        self.assertTrue(after.conditions.has(Condition.STAGGERED))
        self.assertEqual(pending_wild_attack(price.state),price.proof)
        self.assertIsNone(expected_wild_attack(price.state))
        self.assertIsNone(pending_wild_attack(strike.state))
        test = strike.proof.resolution.attack.attacker_test
        self.assertIs(test.trace.quality,TestQuality.GLORIOUS)
        self.assertIn(WILD_ATTACK_RULE_ID,test.trace.applied_rule_ids)
        self.assertEqual(len(strike.state.round_state.active_turn.action_slots),1)
        self.assert_replays(result)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(price.state,price.proof)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(price.source,replace(price.proof,action_id=price.proof.action_id+':foreign'))

    def test_actual_pc_price_improves_only_the_committed_immediate_melee(self):
        result = self.pc_result
        self.assert_paid_strike(result,'pc')
        primary, = tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertIs(primary.weapon_intent.attack_skill,Skill.BRAWN)
        self.assertNotIn(WILD_ATTACK_RULE_ID,primary.execution.resolution.attack.attacker_test.trace.applied_rule_ids)
        self.assertEqual(result.executed_actions,1)

    def test_actual_npc_price_follows_its_first_brawn_stagger_without_another_action(self):
        rng = ScriptedD10([1]*3+[10] + [1]*5+[10]*20 + [1]+[10]*3)
        result = run_pc_melee_scenario(npc_wild_source(),rng)
        rng.assert_exhausted()
        self.assert_paid_strike(result,'minion1')
        self.assertEqual(result.executed_actions,2)
        self.assertTrue(result.state.participant('pc').injury.conditions.has(Condition.PRONE))

    def test_fate_can_supply_same_quality_without_paying_a_redundant_stagger(self):
        rng = ScriptedD10([1]*5+[10]*2+[1]*3+[10]*2)
        result = run_pc_melee_scenario(pc_wild_source(fate=True),rng)
        rng.assert_exhausted()
        self.assertFalse(any(type(step.proof) is PcWildAttackProof for step in result.steps))
        self.assertTrue(any(type(step.proof) is PcImmediateStrikeProof for step in result.steps))
        self.assertFalse(result.state.participant('pc').injury.conditions.has(Condition.STAGGERED))
        self.assert_replays(result)

    def test_prepared_existing_grim_and_glorious_have_no_marginal_second_glorious_benefit(self):
        price, = tuple(step for step in self.pc_result.steps if type(step.proof) is PcWildAttackProof)
        request, protection = build_pc_bash_strike(price.source)
        test = replace(request.kernel_request.attack.attacker_test,quality_modifiers=(
            QualityModifier('prepared:grim',TestQuality.GRIM),
            QualityModifier('prepared:glorious',TestQuality.GLORIOUS)))
        request = replace(request,kernel_request=replace(request.kernel_request,
            attack=replace(request.kernel_request.attack,attacker_test=test)))
        with patch('towr.domain.pc_bash_attack_models.build_pc_bash_strike',return_value=(request,protection)):
            self.assertIsNone(expected_bash_wild_attack(price.source))
        # Cancelling actual Grim is useful; the former no-benefit case is not
        # a blanket refusal to use Wild against a Grim Melee Test.
        test = replace(test,quality_modifiers=(QualityModifier('prepared:grim',TestQuality.GRIM),))
        request = replace(request,kernel_request=replace(request.kernel_request,
            attack=replace(request.kernel_request.attack,attacker_test=test)))
        with patch('towr.domain.pc_bash_attack_models.build_pc_bash_strike',return_value=(request,protection)):
            self.assertIsNotNone(expected_bash_wild_attack(price.source))

    def test_prepared_staggered_or_drained_actor_does_not_pay_a_second_price(self):
        price, = tuple(step for step in self.pc_result.steps if type(step.proof) is PcWildAttackProof)
        for condition in (Condition.STAGGERED,Condition.DRAINED):
            with self.subTest(condition=condition):
                view = _PreparedActorConditions(price.source,'pc',condition)
                self.assertIsNone(expected_bash_wild_attack(view))


if __name__ == '__main__':
    unittest.main()
