"""PC Talent facts and literal native price/reaction receipts (PG73/74/81).

Full runs use continuous literal d10 input. Explicitly named prepared snapshots
exercise local reducer/query boundaries, not fabricated complete battles.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from tests.support.talent_sources import paid_talent, free_talent
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, weak_helper_source
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent, TalentAcquisitionPhase, TalentFunding
from towr.domain.pc_generated_talents import (
    PcWildAttackProof, PcDefensiveStanceProof, expected_wild_attack,
    pending_wild_attack, expected_defensive_stance, actor_stagger_removable,
    WILD_ATTACK_RULE_ID,
)
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon, PcFatePolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcHelpProof, PcAttackerStaggerProof, PcMeleeStep,
    initial_pc_melee_state,
)
from towr.domain.pc_tactical_models import select_pc_tactic
from towr.domain.test_models import TestQuality, Skill
from towr.domain.turn_models import CombatActionKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def scenario(*, talents=(paid_talent(TalentId.WILD_ATTACK),), rounds=1, defensive=False,
        npc_talents=()):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=rounds)
    member = source.party[0]
    member = replace(member,
        pc=replace(member.pc, weapon_skill=3, melee=1 if defensive else 5,
            defence=6, strength=1 if defensive else 4, toughness=20,
            weapon=PcMeleeWeapon.STAFF),
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,
        near_miss_policy=None, glorious_policy=None,
        talents=talents)
    npc = GeneratedNpc(3 if npc_talents else 1, 4 if npc_talents else 1,
        20, 1, 2, 2, initial_generated_weapons(GeneratedWeapon.STAFF), light_loadout(light=False, shield=False),
        defence=2,  talents=npc_talents)
    return replace(source, party=(member,), enemies=(npc.participant('minion1'),))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def attacks(result, actor):
    return tuple(step.proof for step in steps(result, PcAttackProof)
        if step.proof.request.actor_id == actor)


def stance_result(*, defender_rolls=(1, 1, 1)):
    source = scenario(talents=(paid_talent(TalentId.DEFENSIVE_STANCE),), defensive=True)
    return source, execute(source, [10, 10, 10, 1, 10, *defender_rolls])


def help_source():
    source = weak_helper_source()
    helper = replace(source.party[0], fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,
        near_miss_policy=None, glorious_policy=None,
        talents=(free_talent(TalentId.WILD_ATTACK),))
    # The helper is not the enemy's intended victim. Its real free-creation
    # Talent makes the one-die Melee Help worth the voluntary Staggered risk.
    return replace(source, party=(helper, source.party[1]), enemy_target_priority=('pc2', 'pc1'))


class PcCombatTalentSourceTests(unittest.TestCase):
    def test_earned_requirements_and_explicit_free_creation_are_distinct_facts(self):
        member = scenario().party[0]
        for talent, lowered in ((TalentId.WILD_ATTACK, {'strength': 3}),
                (TalentId.DEFENSIVE_STANCE, {'weapon_skill': 2})):
            pc = replace(member.pc, **lowered)
            with self.subTest(talent=talent):
                with self.assertRaises(ValueError):
                    replace(member, pc=pc, talents=(paid_talent(talent),))
                free = free_talent(talent)
                admitted = replace(member, pc=pc, talents=(free,))
                acquisition, = admitted.talents[0].acquisitions
                self.assertIs(acquisition.phase, TalentAcquisitionPhase.CREATION)
                self.assertIs(acquisition.funding, TalentFunding.FREE)
                self.assertEqual(admitted.pc, pc)

    def test_single_acquisitions_reject_duplicate_provenance_and_untyped_ranks(self):
        member = scenario().party[0]
        earned = paid_talent(TalentId.WILD_ATTACK)
        free = free_talent(TalentId.WILD_ATTACK)
        for values in ((earned, earned), (earned, free)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(member, talents=values)
        for values in ([earned], (TalentId.WILD_ATTACK,), (1,), (True,)):
            with self.subTest(values=values), self.assertRaises(TypeError):
                replace(member, talents=values)
        for acquisitions in ('xp', 1, True):
            with self.subTest(acquisitions=acquisitions), self.assertRaises(TypeError):
                AcquiredTalent(TalentId.WILD_ATTACK, acquisitions)
        with self.assertRaises(ValueError):
            replace(earned, acquisitions=earned.acquisitions * 2)

    def test_unsupported_pc_talent_and_nonautomatic_policy_are_rejected(self):
        member = scenario().party[0]
        # The common ownership model accepts59 IDs. An unimplemented battle
        # effect must still be rejected by the actor's actual admission.
        with self.assertRaises(ValueError):
            replace(member, talents=(free_talent(TalentId.FEIGNED_FLIGHT),))
        for talent in ('wild_attack', 1):
            with self.subTest(talent=talent), self.assertRaises(TypeError):
                replace(member, talents=(talent,))
        with self.assertRaises(ValueError):
            replace(scenario().party[0], policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)


class PcCombatTalentExecutionTests(unittest.TestCase):
    def assert_replays(self, result):
        state = initial_pc_melee_state(result.source)
        for step in result.steps:
            state = apply_pc_melee_step(state, step)
        self.assertEqual(state, result.state)

    def test_wild_price_is_before_actual_melee_rerolls_and_spends_no_fate_or_action(self):
        source = scenario()
        result = execute(source, [10] * 11)
        price, = steps(result, PcWildAttackProof)
        self.assertEqual(price.proof.actor_id, 'pc1')
        self.assertTrue(price.proof.intent.wild_attack)
        self.assertIs(price.proof.intent.action, CombatActionKind.ATTACK)
        self.assertEqual(price.proof.intent.target_id, 'minion1')
        self.assertFalse(price.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(price.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(select_pc_tactic(price.state, 'pc1'), price.proof.intent)
        attack, = attacks(result, 'pc1')
        test = attack.execution.resolution.attack.attacker_test
        self.assertIs(test.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual((test.trace.rolled_dice, len(test.trace.rerolls)), (3, 3))
        self.assertEqual(test.trace.initial_values, (10, 10, 10))
        self.assertTrue(attack.request.kernel_request.attack.attacker_is_staggered)
        self.assertEqual([q.rule_id for q in attack.request.kernel_request.attack.attacker_test.quality_modifiers],
            [WILD_ATTACK_RULE_ID])
        self.assertIsNone(attack.glorious)
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(result.state.party[0].fate, source.party[0].fate)
        self.assertIsNone(pending_wild_attack(result.state))
        incoming, = attacks(result, 'minion1')
        self.assertIs(incoming.execution.resolution.attack.attacker_test.trace.quality, TestQuality.NORMAL)
        self.assertIs(incoming.execution.resolution.attack.defender_test.trace.quality, TestQuality.NORMAL)
        self.assert_replays(result)

    def test_melee_help_pays_once_keeps_committed_recipient_and_supplies_exact_ordinary_attack(self):
        source = help_source()
        result = execute(source, [10, 1] + [1] * 8 + [10] * 6)
        price, = steps(result, PcWildAttackProof)
        help_step, = steps(result, PcHelpProof)
        proof = help_step.proof
        self.assertIs(price.proof.intent.action, CombatActionKind.HELP)
        self.assertEqual(price.proof.intent.target_id, 'pc2')
        self.assertEqual(select_pc_tactic(price.state, 'pc1'), price.proof.intent)
        self.assertEqual(proof.request.beneficiary_id, 'pc2')
        self.assertIs(proof.request.help_skill, Skill.MELEE)
        self.assertIs(proof.execution.help_test_result.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(proof.execution.help_test_result.trace.initial_values, (10,))
        self.assertEqual(proof.execution.help_test_result.trace.final_values, (1,))
        self.assertIsNone(proof.glorious)
        self.assertIsNone(pending_wild_attack(help_step.state))
        attack, = attacks(result, 'pc2')
        self.assertIs(attack.execution.resolution.attack.attacker_test.trace.quality, TestQuality.NORMAL)
        self.assertEqual(len(attack.help_applications), 1)
        self.assertEqual(attack.help_applications[0].source_request.help, proof.execution)
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(result.state.party[0].fate, source.party[0].fate)
        for changed in (replace(price.proof.intent, target_id='pc1'),
                replace(price.proof.intent, help_policy=replace(price.proof.intent.help_policy,
                    beneficiary_id='pc1'))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                PcMeleeStep(price.source, replace(price.proof, intent=changed))
        with self.assertRaises(ValueError):
            PcMeleeStep(help_step.state, proof)
        self.assert_replays(result)

    def test_wild_preserves_available_lucky_and_grim_cancels_actual_rerolls(self):
        from towr.domain.pc_melee_models import PcGloriousPolicy
        from towr.domain.test_models import QualityModifier
        from towr.domain.pc_melee_result_models import _pc_test
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        from towr.engine.pc_melee_runner import _resolve_pc_test, _Decisions

        source=scenario()
        member=source.party[0]
        member=replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0),
            fate=replace(member.fate,has_lucky=True),
            talents=(*member.talents,free_talent(TalentId.LUCKY)))
        npc=replace(source.enemies[0].definition.generated_components,toughness=5)
        source=replace(source,party=(member,),enemies=(npc.participant('minion1'),))
        result=execute(source,[10]*11)
        price,=steps(result,PcWildAttackProof)
        attack,=attacks(result,'pc1')
        self.assertIsNone(attack.glorious)
        self.assertEqual(result.state.party[0].fate,member.fate)
        self.assertTrue(result.state.party[0].fate.lucky_free_spend_available)
        self.assert_replays(result)

        # Prepared Test boundary: a separate Grim source cancels the paid
        # Talent quality. This is not a fabricated complete combat journal.
        request=_pc_test(price.state,'pc1','prepared:grim',Skill.MELEE)
        request=replace(request,quality_modifiers=(*request.quality_modifiers,
            QualityModifier('prepared:grim-source',TestQuality.GRIM)))
        rng=ScriptedD10([10,10,10])
        test,decline,glorious,effective=_resolve_pc_test(price.state,'pc1',Skill.MELEE,
            request,rng,_Decisions())
        rng.assert_exhausted()
        self.assertIs(test.trace.quality,TestQuality.NORMAL)
        self.assertEqual(test.trace.rerolls,())
        self.assertIsNone(glorious)
        self.assertEqual(validate_pc_test_fate(price.state,'pc1',Skill.MELEE,
            effective,test,decline,glorious)[1],member.fate)

    def test_price_proof_rejects_wrong_actor_action_missing_intent_repeat_and_skipping(self):
        result = execute(scenario(), [10] * 11)
        price, = steps(result, PcWildAttackProof)
        for changes in ({'actor_id': 'other', 'intent': None},
                {'action_id': 'other'}, {'intent': None}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                PcMeleeStep(price.source, replace(price.proof, **changes))
        with self.assertRaises(ValueError):
            PcMeleeStep(price.state, price.proof)
        with self.assertRaisesRegex(ValueError, 'paid Wild Attack'):
            PcMeleeStep(price.state, result.steps[-1].proof)
        with self.assertRaises(ValueError):
            PcMeleeStep(result.state, price.proof)

    def test_wrong_committed_target_and_nonmelee_intent_are_not_accepted(self):
        result = execute(scenario(), [10] * 11)
        price, = steps(result, PcWildAttackProof)
        forged = replace(price.proof, intent=replace(price.proof.intent, target_id='another'))
        with self.assertRaises(ValueError):
            PcMeleeStep(price.source, forged)
        for action in (CombatActionKind.RECOVER, CombatActionKind.IMPROVISE):
            with self.subTest(action=action), self.assertRaises(ValueError):
                replace(price.proof, intent=replace(price.proof.intent, action=action))

    def test_prepared_drained_staggered_or_dead_actor_cannot_pay_again(self):
        result = execute(scenario(), [10] * 11)
        before = steps(result, PcWildAttackProof)[0].source
        for condition in (Condition.DRAINED, Condition.STAGGERED):
            member = replace(before.party[0], injury=replace(before.party[0].injury,
                conditions=ConditionState(frozenset((condition,)))))
            snapshot = replace(before, party=(member,))
            with self.subTest(condition=condition):
                self.assertIsNone(expected_wild_attack(snapshot))
        member = replace(before.party[0], injury=replace(before.party[0].injury, dead=True))
        self.assertIsNone(expected_wild_attack(replace(before, party=(member,))))

    def test_prepared_injured_hands_charge_critical_only_for_actual_attack_or_help(self):
        from towr.domain.injury_models import (
            WoundRecord, WoundEntryId, WoundConditionEffect, WoundEffectDuration,
            WoundRestrictionEffect, WoundRestriction,
        )
        from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
        from towr.domain.pc_melee_models import PcWeaponHand
        cases = ((scenario(), [10] * 11, PcAttackProof),
            (help_source(), [10, 1] + [1] * 8 + [10] * 6, PcHelpProof))
        for source, values, kind in cases:
            with self.subTest(actual_test=kind.__name__):
                result = execute(source, values)
                price, = steps(result, PcWildAttackProof)
                member = price.source.party[0]
                injury = replace(member.injury, wounds=(
                    WoundRecord(1, WoundEntryId.SMASHED_HAND, 12, (2, 10), effect_resolved=True),
                    WoundRecord(2, WoundEntryId.SMASHED_HAND, 12, (3, 9), effect_resolved=True)),
                    active_wound_effects=tuple(WoundRestrictionEffect(sequence,
                        WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                        WoundEffectDuration.UNTIL_TREATED) for sequence in (1, 2)))
                member = replace(member, injury=injury, body_facts=(
                    PcBodyFact(PcBodyFactKind.INJURED_HAND, 1, PcWeaponHand.LEFT),
                    PcBodyFact(PcBodyFactKind.INJURED_HAND, 2, PcWeaponHand.RIGHT)))
                # Prepared body snapshot: only the reducer transitions below
                # are asserted; this does not invent earlier Wound receipts.
                prepared = replace(price.source, party=(member, *price.source.party[1:]))
                selected = expected_wild_attack(prepared)
                self.assertIsNotNone(selected)
                paid = PcMeleeStep(prepared, selected).state
                self.assertEqual(paid.party[0].body_facts, member.body_facts)
                self.assertEqual(paid.party[0].injury.active_wound_effects, injury.active_wound_effects)
                self.assertFalse(paid.party[0].injury.conditions.has(Condition.CRITICALLY_INJURED))
                actual = steps(result, kind)[0].proof
                after = PcMeleeStep(paid, actual).state
                critical = tuple(effect.wound_sequence for effect in after.party[0].injury.active_wound_effects
                    if type(effect) is WoundConditionEffect and effect.condition is Condition.CRITICALLY_INJURED)
                self.assertEqual(critical, (1,))

    def test_prepared_internal_injury_blocks_wild_but_actual_attack_retains_critical(self):
        from towr.domain.injury_models import (
            WoundRecord, WoundEntryId, WoundConditionEffect, WoundEffectDuration,
            WoundRestrictionEffect, WoundRestriction,
        )
        result = execute(scenario(talents=(paid_talent(TalentId.DEFENSIVE_STANCE),)), [10] * 8)
        attack = steps(result, PcAttackProof)[0]
        member = attack.source.party[0]
        injury = replace(member.injury,
            wounds=(WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (7, 7), effect_resolved=True),),
            conditions=ConditionState(frozenset((Condition.DRAINED,))),
            active_wound_effects=(WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),
                WoundRestrictionEffect(1, WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,
                    WoundEffectDuration.UNTIL_TREATED)))
        # A local Wound14 preparation, with both earned Talents; no full
        # native Wound history is claimed for this reducer boundary check.
        source_member = replace(attack.source.source.party[0], talents=(
            paid_talent(TalentId.DEFENSIVE_STANCE), paid_talent(TalentId.WILD_ATTACK)))
        prepared = replace(attack.source,
            source=replace(attack.source.source, party=(source_member,)),
            party=(replace(member, injury=injury),))
        self.assertIsNone(expected_wild_attack(prepared))
        self.assertFalse(select_pc_tactic(prepared, 'pc1').wild_attack)
        after = PcMeleeStep(prepared, attack.proof).state
        critical = tuple(effect.wound_sequence for effect in after.party[0].injury.active_wound_effects
            if type(effect) is WoundConditionEffect and effect.condition is Condition.CRITICALLY_INJURED)
        self.assertEqual(critical, (1,))

    def test_successful_pc_defence_trades_fresh_attacker_stagger_without_extra_action(self):
        source, result = stance_result()
        stance, = steps(result, PcDefensiveStanceProof)
        self.assertEqual((stance.proof.actor_id, stance.proof.attacker_id), ('pc1', 'minion1'))
        self.assertIs(stance.source.pending[0], stance.proof.source)
        self.assertTrue(stance.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.pending)
        attack, = attacks(result, 'minion1')
        self.assertIs(attack.protection.source_request.selected_skill, Skill.DEFENCE)
        self.assertEqual((attack.execution.resolution.attack.attacker_test.successes,
            attack.execution.resolution.attack.defender_test.successes), (0, 3))
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(result.state.party[0].fate, source.party[0].fate)
        self.assert_replays(result)

    def test_zero_against_zero_is_not_successful_defence_and_keeps_own_stagger(self):
        _, result = stance_result(defender_rolls=(10, 10, 10))
        self.assertFalse(steps(result, PcDefensiveStanceProof))
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))

    def test_already_staggered_npc_attacker_cannot_fund_pc_stance(self):
        source = scenario(talents=(paid_talent(TalentId.DEFENSIVE_STANCE),), defensive=True,
            npc_talents=(paid_talent(TalentId.WILD_ATTACK),))
        # The PC misses into three Protection dice, then the NPC pays Wild.
        # Its failed Glorious attack cannot supply a new missed-attack Staggered.
        result = execute(source, [10, 10, 10, 1, 1, 1] + [10] * 6 + [1] * 3)
        self.assertFalse(steps(result, PcDefensiveStanceProof))
        price, = steps(result, PcWildAttackProof)
        self.assertEqual(price.proof.actor_id, 'minion1')
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_stance_rejects_other_actor_source_repeat_and_default_miss_application(self):
        _, result = stance_result()
        stance, = steps(result, PcDefensiveStanceProof)
        for altered in (replace(stance.proof, actor_id='other'),
                replace(stance.proof, attacker_id='other'),
                replace(stance.proof, source=replace(stance.proof.source, attack_id='other'))):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                PcMeleeStep(stance.source, altered)
        with self.assertRaises(ValueError):
            PcMeleeStep(stance.state, stance.proof)
        with self.assertRaisesRegex(ValueError, 'selected Defensive Stance'):
            PcMeleeStep(stance.source, PcAttackerStaggerProof(stance.proof.source))

    def test_prepared_drained_keeps_passive_stance_but_ongoing_wound_stagger_cannot_be_removed(self):
        from towr.domain.injury_models import (
            WoundRecord, WoundEntryId, WoundConditionEffect, WoundEffectDuration,
        )
        _, result = stance_result()
        stance, = steps(result, PcDefensiveStanceProof)
        member = stance.source.party[0]
        member = replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
        prepared = replace(stance.source, party=(member,))
        self.assertEqual(expected_defensive_stance(prepared), stance.proof)
        # This local snapshot carries the actual ongoing Condition source15.
        # It is intentionally not presented as a complete Wound-history run.
        member = replace(member, injury=replace(member.injury,
            wounds=(WoundRecord(1, WoundEntryId.SCARRING_STRIKE, 15, (7, 8), effect_resolved=True),),
            active_wound_effects=(WoundConditionEffect(1, Condition.STAGGERED,
                WoundEffectDuration.UNTIL_HEALED),)))
        prepared = replace(prepared, party=(member,))
        self.assertFalse(actor_stagger_removable(prepared, 'pc1'))
        self.assertIsNone(expected_defensive_stance(prepared))


if __name__ == '__main__':
    unittest.main()
