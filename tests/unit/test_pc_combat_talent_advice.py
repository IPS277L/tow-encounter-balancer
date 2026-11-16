"""Finite advice, without hypothetical receipts, RNG or Fate expenditure."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_tactics_fixtures import automatic_source, weak_helper_source, tactical_snapshot
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedTalent
from towr.domain.pc_combat_talent_models import PcCombatTalent, TalentAcquisition
from towr.domain.pc_generated_talents import PcWildAttackProof, WILD_ATTACK_RULE_ID
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcHelpTarget, PcMeleeWeapon
from towr.domain.pc_melee_result_models import pc_melee_action_id
from towr.domain.pc_tactical_models import select_pc_tactic, _distribution
from towr.domain.pc_talent_advice import pc_test_distribution, pc_wild_test_variant, pc_wild_eligible
from towr.domain.test_models import (TestRequest, TestProfile, QualityModifier, TestQuality,
    Skill, InlineProfile, RerollLock, SuccessModifier)
from towr.domain.turn_models import CombatActionKind


def talented(source=None, *, fate=False, maximum=20, reserve=0, weapon=None):
    source = source or automatic_source()
    actor = source.party[0]
    actor = replace(actor, combat_talents=(PcCombatTalent(GeneratedTalent.WILD_ATTACK,
        TalentAcquisition.CREATION_FREE),),
        fate_policy=PcFatePolicy.CONFIGURED if fate else PcFatePolicy.DECLINE_OPTIONAL_FATE,
        glorious_policy=PcGloriousPolicy((Skill.MELEE,), maximum, reserve) if fate else None)
    if weapon is not None:
        actor = replace(actor, pc=replace(actor.pc, weapon=weapon))
    return replace(source, party=(actor, *source.party[1:]))


def with_conditions(state, actor, *conditions):
    member = state.participant(actor)
    member = replace(member, injury=replace(member.injury,
        conditions=ConditionState(frozenset(conditions))))
    return replace(state, party=tuple(member if item.actor_id == actor else item for item in state.party))


class FiniteFateAdviceTests(unittest.TestCase):
    def distribution(self, maximum, *, grim=False, source=None):
        state = tactical_snapshot(source or talented(fate=True, maximum=maximum))
        request = TestRequest('advice', TestProfile(2, 5), quality_modifiers=
            (QualityModifier('grim', TestQuality.GRIM),) if grim else ())
        return pc_test_distribution(state, 'pc1', Skill.MELEE, request)

    def test_normal_policy_is_conditional_on_initial_success_count(self):
        self.assertEqual(self.distribution(0), (0.0625, 0.625, 0.3125))
        self.assertEqual(self.distribution(1), (0.0625, 0.375, 0.5625))

    def test_grim_fate_cancels_reroll_instead_of_rerolling_failures(self):
        self.assertEqual(self.distribution(0, grim=True), (0.5625, 0.375, 0.0625))
        self.assertEqual(self.distribution(1, grim=True), (0.3125, 0.625, 0.0625))
        self.assertEqual(self.distribution(2, grim=True), (0.25, 0.5, 0.25))

    def test_budget_reserve_and_selected_skill_are_respected(self):
        source = talented(fate=True, reserve=3)
        self.assertEqual(self.distribution(20, source=source), (0.25, 0.5, 0.25))
        state = tactical_snapshot(talented(fate=True))
        self.assertEqual(pc_test_distribution(state, 'pc1', Skill.DEFENCE,
            TestRequest('defence', TestProfile(2, 5))), (0.25, 0.5, 0.25))

    def test_lucky_can_fund_fate_with_no_paid_session_pool(self):
        source = talented(fate=True)
        actor = source.party[0]
        source = replace(source, party=(replace(actor,
            fate=replace(actor.fate, rating=0, session_spend_limit=0, has_lucky=True)), *source.party[1:]))
        self.assertEqual(self.distribution(20, source=source), (0.0625, 0.375, 0.5625))
        actor = source.party[0]
        source = replace(source, party=(replace(actor, fate=replace(actor.fate, has_lucky=False)), *source.party[1:]))
        self.assertEqual(self.distribution(20, source=source), (0.25, 0.5, 0.25))

    def test_existing_glorious_has_no_second_fate_benefit_even_when_grim(self):
        state = tactical_snapshot(talented(fate=True))
        glorious = QualityModifier('already', TestQuality.GLORIOUS)
        for qualities in ((glorious,), (glorious, QualityModifier('grim', TestQuality.GRIM))):
            request = TestRequest('prepared', TestProfile(2, 5), quality_modifiers=qualities)
            self.assertEqual(pc_test_distribution(state, 'pc1', Skill.MELEE, request), _distribution(request))

    def test_advice_never_rolls_or_spends(self):
        state = tactical_snapshot(talented(fate=True))
        with patch('random.Random', side_effect=AssertionError('advice is finite')):
            first = pc_test_distribution(state, 'pc1', Skill.MELEE, TestRequest('test', TestProfile(2, 5)))
            self.assertEqual(first, pc_test_distribution(state, 'pc1', Skill.MELEE,
                TestRequest('test', TestProfile(2, 5))))
        self.assertEqual(state.participant('pc1').fate.spends, ())

    def test_success_modifier_does_not_change_initial_fate_policy_threshold(self):
        state = tactical_snapshot(talented(fate=True, maximum=0))
        request = TestRequest('free-success', TestProfile(2, 5),
            success_modifiers=(SuccessModifier('bonus', 1),))
        self.assertEqual(pc_test_distribution(state, 'pc1', Skill.MELEE, request),
            (0.0, 0.0625, 0.625, 0.3125))

    def test_locked_context_keeps_existing_distribution_without_new_fate_assumption(self):
        state = tactical_snapshot(talented(fate=True))
        request = TestRequest('locked', TestProfile(2, 5),
            quality_modifiers=(QualityModifier('grim', TestQuality.GRIM),),
            reroll_locks=(RerollLock('lock', 1),))
        self.assertEqual(pc_test_distribution(state, 'pc1', Skill.MELEE, request), _distribution(request))


class WildTacticalChoiceTests(unittest.TestCase):
    def test_morning_star_price_changes_pool_before_glorious_and_grim_cancel(self):
        request = TestRequest('morning-star', TestProfile(2, 5), quality_modifiers=
            (QualityModifier('grim', TestQuality.GRIM),))
        variant = pc_wild_test_variant(request, PcMeleeWeapon.MORNING_STAR, ConditionState())
        self.assertEqual(sum(mod.amount for mod in variant.dice_modifiers), -1)
        self.assertEqual(_distribution(variant), (0.5, 0.5))
        self.assertIn(QualityModifier(WILD_ATTACK_RULE_ID, TestQuality.GLORIOUS), variant.quality_modifiers)
        self.assertEqual(request.dice_modifiers, ())

    def test_no_incoming_risk_prefers_wild_attack(self):
        source = talented()
        source = replace(source, enemy_target_priority=('pc2', 'pc1'))
        choice = select_pc_tactic(tactical_snapshot(source))
        self.assertIs(choice.action, CombatActionKind.ATTACK)
        self.assertTrue(choice.wild_attack)

    def test_fate_equivalent_attack_and_help_prefer_no_voluntary_price(self):
        for source in (automatic_source(), weak_helper_source()):
            source = talented(source, fate=True)
            source = replace(source, enemy_target_priority=('pc2', 'pc1'))
            choice = select_pc_tactic(tactical_snapshot(source))
            self.assertFalse(choice.wild_attack)

    def test_help_can_use_wild_attack_with_creation_free_low_strength(self):
        source = talented(weak_helper_source())
        source = replace(source, enemy_target_priority=('pc2', 'pc1'))
        self.assertEqual(source.party[0].pc.strength, 1)
        choice = select_pc_tactic(tactical_snapshot(source))
        self.assertIs(choice.action, CombatActionKind.HELP)
        self.assertIs(choice.help_policy.target, PcHelpTarget.ATTACK)
        self.assertEqual(choice.target_id, 'pc2')
        self.assertTrue(choice.wild_attack)

    def test_stagger_and_drained_do_not_offer_new_wild_activation(self):
        state = tactical_snapshot(talented())
        for condition in (Condition.STAGGERED, Condition.DRAINED, Condition.DEFENCELESS):
            changed = with_conditions(state, 'pc1', condition)
            self.assertFalse(pc_wild_eligible(changed, 'pc1'))
            self.assertFalse(select_pc_tactic(changed).wild_attack)

    def test_sword_lost_defence_bonus_can_change_wild_decision(self):
        choices = []
        for weapon in (PcMeleeWeapon.STAFF, PcMeleeWeapon.SWORD):
            source = talented(weapon=weapon)
            enemy = source.enemies[0]
            attack = replace(enemy.definition.attacks[0], test_profile=InlineProfile(4, 5))
            source = replace(source, enemies=(replace(enemy,
                definition=replace(enemy.definition, attacks=(attack,))),))
            choices.append(select_pc_tactic(tactical_snapshot(source)))
        self.assertTrue(choices[0].wild_attack)
        self.assertFalse(choices[1].wild_attack)

    def test_defensive_stance_reduces_prospective_self_stagger_risk(self):
        source = talented()
        enemy = source.enemies[0]
        attack = replace(enemy.definition.attacks[0], test_profile=InlineProfile(2, 5),
            damage=replace(enemy.definition.attacks[0].damage, base=1))
        source = replace(source, enemies=(replace(enemy,
            definition=replace(enemy.definition, attacks=(attack,))),))
        self.assertFalse(select_pc_tactic(tactical_snapshot(source)).wild_attack)
        actor = source.party[0]
        actor = replace(actor, combat_talents=(*actor.combat_talents,
            PcCombatTalent(GeneratedTalent.DEFENSIVE_STANCE, TalentAcquisition.CREATION_FREE)))
        source = replace(source, party=(actor, *source.party[1:]))
        self.assertTrue(select_pc_tactic(tactical_snapshot(source)).wild_attack)

    def test_passive_stance_still_matters_while_drained(self):
        source = automatic_source(pc_count=1)
        actor = replace(source.party[0], pc=replace(source.party[0].pc,
            weapon_skill=1, melee=1, defence=7))
        enemy = source.enemies[0]
        attack = replace(enemy.definition.attacks[0], test_profile=InlineProfile(1, 5))
        source = replace(source, party=(actor,), enemies=(replace(enemy,
            definition=replace(enemy.definition, attacks=(attack,))),))
        def choice(value):
            return select_pc_tactic(with_conditions(tactical_snapshot(value), 'pc1',
                Condition.STAGGERED, Condition.DRAINED))
        self.assertIs(choice(source).action, CombatActionKind.RECOVER)
        actor = replace(actor, combat_talents=(PcCombatTalent(GeneratedTalent.DEFENSIVE_STANCE,
            TalentAcquisition.CREATION_FREE),))
        self.assertIs(choice(replace(source, party=(actor,))).action, CombatActionKind.ATTACK)

    def test_price_retains_immutable_selected_intent_after_stagger(self):
        source = talented(weak_helper_source())
        source = replace(source, enemy_target_priority=('pc2', 'pc1'))
        state = tactical_snapshot(source)
        intent = select_pc_tactic(state)
        self.assertTrue(intent.wild_attack)
        proof = PcWildAttackProof('pc1', pc_melee_action_id(state, 'pc1'), intent=intent)
        changed = with_conditions(replace(state, history=(*state.history, proof)), 'pc1', Condition.STAGGERED)
        self.assertIs(select_pc_tactic(changed), intent)
        self.assertIsNot(select_pc_tactic(changed, 'pc2'), intent)


if __name__ == '__main__':
    unittest.main()
