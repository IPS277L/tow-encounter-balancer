"""Pure Bash sources from real K1 Brawn actions; no follow-up battle admission."""
from copy import copy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent, paid_talent
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import (
    AttackOutcome, AttackRequest, ConditionOnHitSpec, DamageImpactSpec, DamageProfile,
    ImpactOutcome, ProneBeforeGiveGroundSpec, ResilienceProfile,
)
from towr.domain.brawn_impact_models import BrawnAttackEffect, BrawnDisplacementImpactSpec
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice, StaggerOutcome
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import FirstStaggerWoundSpec, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.talent_bash_attack_models import BASH_ATTACK_RULE_ID, BashAttackGrant
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import QualityModifier, TestProfile, TestQuality, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatRoundState,
    CombatSide, CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_impact_preparation import prepare_weapon_impact
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, initial_weapon_inventory,
)
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.test_resolution import RerollAllFailures
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class _StaggerChoice:
    def __init__(self, choice):
        self.choice = choice

    def choose_repeated_stagger(self, **source):
        if self.choice not in source['allowed_choices']:
            raise AssertionError('test fixture selected an illegal repeated Staggered response')
        return self.choice


def brawn_source(*, kind=WeaponKind.UNARMED, profile=False, conditions=(),
        actor_side=CombatSide.PLAYERS_AND_ALLIES, values=(1, 10, 10, 10, 10, 10, 10),
        impact=None, secondary=(), repeated_choice=None, first_stagger_wound=False, glorious=False):
    """Execute a physical K1 action; the actual Talent is not runtime-admitted."""
    actor, target = 'actor', 'target'
    target_side = (CombatSide.OPPOSITION if actor_side is CombatSide.PLAYERS_AND_ALLIES
        else CombatSide.PLAYERS_AND_ALLIES)
    clock = CombatRoundState(1, (CombatTurnParticipant(actor, actor_side),
        CombatTurnParticipant(target, target_side)), side_order=(actor_side, target_side))
    clock = start_combat_turn(CombatTurnStartRequest('start', clock, actor)).state
    clock = reserve_combat_action_slot(CombatActionSlotRequest('reserve', clock, actor,
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)).state
    items = (() if kind is WeaponKind.UNARMED else (WeaponItemSource('item', kind,
        WeaponItemLocation.HELD, WeaponGrip.LEFT),))
    inventory = initial_weapon_inventory(actor, items)
    use = build_weapon_use(actor, inventory, None if not inventory.items else inventory.items[0].id)
    spec = prepare_weapon_impact(use, 5, ResilienceProfile(6)).impact_spec if impact is None else impact
    quality = (QualityModifier('test:glorious', TestQuality.GLORIOUS),) if glorious else ()
    attack = AttackRequest('attack', TestRequest('brawn', TestProfile(5, 5), quality_modifiers=quality),
        TestRequest('endurance', TestProfile(2, 4)), spec, True, False, secondary_effects=secondary)
    injury = (ProfileInjuryState(0, 3, ConditionState(frozenset(conditions))) if profile
        else CharacterInjuryState(conditions=ConditionState(frozenset(conditions))))
    kernel = KernelAttackRequest('kernel', target, attack,
        TargetInjuryPolicy.BRUTE if profile else TargetInjuryPolicy.PLAYER,
        injury, True, False, physical_attack=True,
        first_stagger_wound=(FirstStaggerWoundSpec('RULE-PROFILE-IMPERIAL-006:feel-no-pain')
            if first_stagger_wound else None))
    source = AttackActionExecutionRequest('action', clock, actor, target, 1, kernel)
    rng = ScriptedD10(values)
    decisions = _StaggerChoice(repeated_choice) if repeated_choice is not None else (
        RerollAllFailures() if glorious else None)
    execution = execute_attack_action(source, rng, decisions=decisions)
    rng.assert_exhausted()
    return source, execution, use


def grant(source):
    return BashAttackGrant(*source, paid_talent(TalentId.BASH_ATTACK))


class BashAttackSourceTests(unittest.TestCase):
    def test_unarmed_first_stagger_grants_for_each_side_without_a_new_slot_or_roll(self):
        for side in CombatSide:
            with self.subTest(side=side):
                source = brawn_source(actor_side=side, profile=side is CombatSide.PLAYERS_AND_ALLIES)
                result = grant(source)
                self.assertEqual((result.id, result.actor_id, result.target_id, result.round_number, result.rule_id),
                    ('action:bash-attack', 'actor', 'target', 1, BASH_ATTACK_RULE_ID))
                self.assertIs(result.source_request, source[0])
                self.assertIs(result.source_execution, source[1])
                self.assertIs(result.weapon_use, source[2])
                self.assertIs(source[1].resolution.stagger.outcome, StaggerOutcome.CONDITION_ADDED)
                self.assertEqual(len(source[1].state.active_turn.action_slots), 1)
                self.assertFalse(source[0].state.active_turn.action_slots[0].executed)
                self.assertTrue(source[1].slot.executed)
                self.assertEqual(pickle.loads(pickle.dumps(result)), result)
                with self.assertRaises(FrozenInstanceError):
                    result.talent = free_talent(TalentId.BASH_ATTACK)

    def test_knuckledusters_uses_real_damage_comparison_then_first_stagger(self):
        source = brawn_source(kind=WeaponKind.KNUCKLEDUSTERS, profile=True)
        result = grant(source)
        self.assertEqual(result.weapon_use.kind, WeaponKind.KNUCKLEDUSTERS)
        self.assertEqual((source[1].resolution.attack.damage, source[1].resolution.attack.effective_resilience), (5, 6))
        self.assertIs(source[1].resolution.attack.impact, ImpactOutcome.STAGGERED)
        self.assertEqual(source[1].resolution.target_state.wounds, 0)
        self.assertIsNone(source[1].resolution.replacement_impact)

    def test_actual_glorious_completed_test_revalidates_recorded_rerolls(self):
        source = brawn_source(glorious=True, values=(1, 10, 10, 10, 10, 1, 10, 10, 10, 10, 10))
        result = grant(source)
        self.assertEqual(len(result.source_execution.resolution.attack.attacker_test.trace.rerolls), 4)
        self.assertEqual(result.source_execution.resolution.attack.attacker_test.successes, 2)
        request, execution, use = source
        bad_trace = replace(execution.resolution.attack.attacker_test.trace,
            rerolls=execution.resolution.attack.attacker_test.trace.rerolls[1:])
        forged = replace(execution, resolution=replace(execution.resolution,
            attack=replace(execution.resolution.attack,
                attacker_test=replace(execution.resolution.attack.attacker_test, trace=bad_trace))))
        with self.assertRaises(ValueError):
            grant((request, forged, use))

    def test_secondary_prone_and_conditions_do_not_erase_a_real_new_stagger(self):
        source = brawn_source(kind=WeaponKind.KNUCKLEDUSTERS, profile=True,
            secondary=(ProneBeforeGiveGroundSpec('test:charge-prone'),
                ConditionOnHitSpec(Condition.DRAINED, 'test:actual-on-hit')))
        result = grant(source)
        self.assertEqual(result.source_execution.resolution.target_state.conditions.conditions,
            frozenset((Condition.STAGGERED, Condition.PRONE, Condition.DRAINED)))

    def test_miss_and_numeric_wound_cannot_grant_bash(self):
        miss = brawn_source(values=(10, 10, 10, 10, 10, 1, 1))
        self.assertIs(miss[1].resolution.attack.outcome, AttackOutcome.MISS)
        wound = brawn_source(kind=WeaponKind.KNUCKLEDUSTERS, profile=True,
            values=(1, 1, 1, 1, 1, 10, 10))
        self.assertIs(wound[1].resolution.attack.impact, ImpactOutcome.WOUND)
        for source in (miss, wound):
            with self.subTest(outcome=source[1].resolution.attack.outcome), self.assertRaises(ValueError):
                grant(source)

    def test_all_repeated_stagger_results_are_not_new_stagger(self):
        outcomes = (StaggerOutcome.GAVE_GROUND, StaggerOutcome.FELL_PRONE, StaggerOutcome.WOUND_REQUESTED)
        for choice, outcome in zip(StaggerChoice, outcomes):
            source = brawn_source(profile=True, conditions=(Condition.STAGGERED,), repeated_choice=choice)
            with self.subTest(choice=choice):
                self.assertIs(source[1].resolution.stagger.outcome, outcome)
                with self.assertRaises(ValueError):
                    grant(source)

    def test_first_stagger_wound_replacement_and_shove_dismount_do_not_grant(self):
        replaced = brawn_source(kind=WeaponKind.KNUCKLEDUSTERS, profile=True, first_stagger_wound=True)
        self.assertEqual(replaced[1].resolution.target_state.wounds, 1)
        self.assertIs(replaced[1].resolution.stagger.outcome, StaggerOutcome.WOUND_REQUESTED)
        for source in (replaced, *(brawn_source(impact=BrawnDisplacementImpactSpec(effect, 'actor'))
                for effect in (BrawnAttackEffect.SHOVE, BrawnAttackEffect.DISMOUNT))):
            with self.subTest(impact=source[0].kernel_request.attack.impact_spec), self.assertRaises(ValueError):
                grant(source)

    def test_other_weapon_or_talent_and_foreign_actor_source_are_rejected(self):
        source = brawn_source()
        with self.assertRaises(ValueError):
            BashAttackGrant(*source, paid_talent(TalentId.MIGHTY_BLOW))
        with self.assertRaises(TypeError):
            BashAttackGrant(*source, TalentId.BASH_ATTACK)
        with self.assertRaises(ValueError):
            grant((source[0], source[1], replace(source[2], actor_id='foreign')))
        sword = brawn_source(kind=WeaponKind.SWORD, profile=True)
        with self.assertRaises(ValueError):
            grant(sword)
        # The source is an Unarmed condition impact, not a physical Knuckles hit.
        knuckles = brawn_source(kind=WeaponKind.KNUCKLEDUSTERS, profile=True)
        with self.assertRaises(ValueError):
            grant((source[0], source[1], knuckles[2]))

    def test_foreign_request_kernel_attack_and_receipt_ids_cannot_authorise_grant(self):
        request, execution, use = brawn_source()
        for changed in (replace(request, id='foreign'),
                replace(request, kernel_request=replace(request.kernel_request, id='foreign')),
                replace(request, kernel_request=replace(request.kernel_request,
                    attack=replace(request.kernel_request.attack, id='foreign')))):
            with self.subTest(request=changed), self.assertRaises(ValueError):
                grant((changed, execution, use))
        # Frozen constructor guards already reject detached clock receipts.
        with self.assertRaises(ValueError):
            replace(execution, request_id='foreign')

    def test_erased_forged_or_duplicate_stagger_receipts_are_rejected(self):
        request, execution, use = brawn_source()
        resolution = execution.resolution
        forged = (
            replace(resolution, stagger=None),
            replace(resolution, stagger=replace(resolution.stagger, request_id='foreign')),
            replace(resolution, target_state=request.kernel_request.target_state),
            replace(resolution, condition_applications=resolution.condition_applications * 2),
            replace(resolution, follow_ups=(resolution.stagger,)),
            replace(resolution, attack=replace(resolution.attack, success_margin=10)),
        )
        for changed in forged:
            with self.subTest(resolution=changed), self.assertRaises(ValueError):
                grant((request, replace(execution, resolution=changed), use))

    def test_forged_test_counters_raw_outcome_and_source_types_do_not_compare_equal(self):
        request, execution, use = brawn_source()
        trace = execution.resolution.attack.attacker_test.trace
        for changed in (replace(trace, successes=True), replace(trace, successes=2),
                replace(trace, initial_values=(1,) * 5)):
            attack = replace(execution.resolution.attack,
                attacker_test=replace(execution.resolution.attack.attacker_test, trace=changed))
            with self.subTest(trace=changed), self.assertRaises((TypeError, ValueError)):
                grant((request, replace(execution, resolution=replace(execution.resolution, attack=attack)), use))
        for changed in (replace(execution.resolution.attack, outcome='hit'),
                replace(execution.resolution.attack, tie_break_applied=0)):
            with self.subTest(attack=changed), self.assertRaises((TypeError, ValueError)):
                grant((request, replace(execution, resolution=replace(execution.resolution, attack=changed)), use))
        malformed = copy(request)
        object.__setattr__(malformed, 'slot_index', True)
        with self.assertRaises(TypeError):
            grant((malformed, execution, use))
        with self.assertRaises(TypeError):
            BashAttackGrant(request, execution.resolution, use, paid_talent(TalentId.BASH_ATTACK))


if __name__ == '__main__':
    unittest.main()
