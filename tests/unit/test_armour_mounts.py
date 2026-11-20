"""Literal mounted armour exceptions and source-bound current capability queries.

Small views isolate these pure queries. The native owner is responsible for
actual Attack/movement receipts, source readmission and dismount replay.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from types import SimpleNamespace
import unittest

from towr.domain.armour_models import (
    ArmourLoadout, BodyArmour, BARDING_AGILITY_RULE_ID,
    FULL_PLATE_ARMOUR_AGILITY_RULE_ID, armour_test_modifiers,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.attack_models import (
    AttackRequest, ConditionAfterGiveGroundSpec, DamageImpactSpec, DamageProfile,
    ProneBeforeGiveGroundSpec, ResilienceProfile,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.movement_models import MovementSpeed
from towr.domain.pc_mount_models import (
    CombatMount, RiderKind, PcMountedState, HORSE_NOBLE_STEED_RULE_ID,
    PEGASUS_KNIGHTS_RULE_ID, ELVEN_STEED_RULE_ID, expected_pc_dismount,
    initial_pc_mounts, mount_resilience_bonus, mount_source_resilience_bonus,
    mounted_armour_test_exemptions, mounted_can_fly, mounted_give_ground_broken,
    mounted_test_modifiers, pc_mount_speed, pc_mounted_attack_effects,
    updated_pc_mounts, validate_mount_rider, validate_pc_mounts,
    DEMIGRYPH_FEARSOME_RULE_ID, SKELETAL_STEED_FRIGHTENING_RULE_ID,
)
from towr.domain.resolution_models import (
    TargetInjuryPolicy, KernelAttackRequest, GiveGroundRequest, ConditionAfterGiveGroundRequest,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.condition_effect_resolution import resolve_condition_after_give_ground
from tests.helpers import SequenceRandom
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_melee_result_models import initial_pc_melee_state


def mounted_view(mount=CombatMount.HORSE, *, rider_kind=None,
        armour=None, mounted=True, actor='rider', prone=False,
        target_policy=TargetInjuryPolicy.MINION):
    """One explicit rider source, usable on either side of the bank query."""
    facts = SimpleNamespace(actor_id=actor, mount=mount, rider_kind=rider_kind,
        armour=ArmourLoadout() if armour is None else armour)
    other = SimpleNamespace(actor_id='other', mount=None, rider_kind=None,
        armour=ArmourLoadout())
    party = (facts,) if actor == 'rider' else (other,)
    components = facts if actor == 'enemy' else other
    enemy = SimpleNamespace(definition=SimpleNamespace(generated_components=components,
        injury_policy=target_policy), state=SimpleNamespace(actor_id='enemy',
        injury=ProfileInjuryState(0, 1, conditions=ConditionState(
            frozenset((Condition.PRONE,)) if prone and actor == 'enemy' else frozenset()))))
    source = SimpleNamespace(id='mount-armour', party=party, enemies=(enemy,),
        pc_activation_order=('rider',), enemy_activation_order=('enemy',), battlefield=object(),
        participant=lambda queried: party[0])
    injury = CharacterInjuryState(conditions=ConditionState(
        frozenset((Condition.PRONE,)) if prone and actor == 'rider' else frozenset()))
    return SimpleNamespace(source=source, enemy=lambda queried: enemy,
        participant=lambda queried: SimpleNamespace(injury=injury),
        mounts=(() if mount is None else (PcMountedState(actor, mount, mounted),)),
        companions=(), pending=(), pending_wound=None, history=())


class ArmourMountTests(unittest.TestCase):
    def test_source_resilience_is_printed_and_not_barding(self):
        self.assertEqual(mount_source_resilience_bonus(None), 0)
        for mount in CombatMount:
            with self.subTest(mount=mount):
                self.assertEqual(mount_source_resilience_bonus(mount),
                    2 if mount is CombatMount.DEMIGRYPH else 1)
        for malformed in ('horse', 1, False):
            with self.subTest(malformed=malformed), self.assertRaises(TypeError):
                mount_source_resilience_bonus(malformed)

    def test_rider_eligibility_requires_exact_applicable_facts(self):
        for mount, kind in ((None, None), (CombatMount.HORSE, None),
                (CombatMount.DEMIGRYPH, RiderKind.HUMAN),
                (CombatMount.PEGASUS, RiderKind.HUMAN),
                (CombatMount.PEGASUS, RiderKind.ELF)):
            validate_mount_rider(mount, kind)
        for mount, kind in ((CombatMount.DEMIGRYPH, None),
                (CombatMount.DEMIGRYPH, RiderKind.ELF),
                (CombatMount.DEMIGRYPH, RiderKind.OTHER),
                (CombatMount.PEGASUS, None), (CombatMount.PEGASUS, RiderKind.OTHER),
                (CombatMount.HORSE, RiderKind.HUMAN), (None, RiderKind.HUMAN)):
            with self.subTest(mount=mount, kind=kind), self.assertRaises(ValueError):
                validate_mount_rider(mount, kind)
        for mount, kind in (('pegasus', RiderKind.HUMAN), (CombatMount.PEGASUS, 'human')):
            with self.assertRaises(TypeError):
                validate_mount_rider(mount, kind)

    def test_actual_barding_and_mount_bonus_drop_together_for_both_sides(self):
        for actor in ('rider', 'enemy'):
            for mount in CombatMount:
                kind = RiderKind.HUMAN if mount in (CombatMount.DEMIGRYPH, CombatMount.PEGASUS) else None
                for barding in (False, True):
                    state = mounted_view(mount, rider_kind=kind, actor=actor,
                        armour=ArmourLoadout(barding=barding))
                    with self.subTest(actor=actor, mount=mount, barding=barding):
                        self.assertEqual(mount_resilience_bonus(state, actor),
                            (2 if mount is CombatMount.DEMIGRYPH else 1) + int(barding))
                        state.mounts = (replace(state.mounts[0], mounted=False),)
                        self.assertEqual(mount_resilience_bonus(state, actor), 0)

    def test_barding_query_rejects_forged_equipment_and_mount_bank(self):
        state = mounted_view(armour=SimpleNamespace(barding=True))
        with self.assertRaises(TypeError):
            mount_resilience_bonus(state, 'rider')
        state = mounted_view()
        state.mounts = ()
        with self.assertRaises(ValueError):
            mount_resilience_bonus(state, 'rider')
        state.mounts = (PcMountedState('rider', CombatMount.ELVEN_STEED, True),)
        with self.assertRaises(ValueError):
            mounted_can_fly(state, 'rider')

    def test_literal_bretonnian_exception_preserves_full_plate_penalty(self):
        heavy = ArmourLoadout((BodyArmour.HEAVY,), BodyArmour.HEAVY, barding=True)
        plate = ArmourLoadout((BodyArmour.FULL_PLATE,), BodyArmour.FULL_PLATE, barding=True)
        state = mounted_view(CombatMount.BRETONNIAN_WARHORSE, armour=heavy)
        plain = mounted_armour_test_exemptions(state, 'rider', Skill.ATHLETICS)
        self.assertEqual(tuple(m.amount for m in armour_test_modifiers(heavy, Skill.ATHLETICS, **plain)), (-1, -1))
        for context in ({'oppose_attack': True}, {'control_mount': True}):
            exemption = mounted_armour_test_exemptions(state, 'rider', Skill.ATHLETICS, **context)
            self.assertEqual(armour_test_modifiers(heavy, Skill.ATHLETICS, **exemption), ())
            self.assertEqual(tuple((m.rule_id, m.amount) for m in
                armour_test_modifiers(plate, Skill.ATHLETICS, **exemption)),
                ((FULL_PLATE_ARMOUR_AGILITY_RULE_ID, -1),))

    def test_demigryph_cancels_body_penalty_but_not_barding(self):
        for body in (BodyArmour.HEAVY, BodyArmour.FULL_PLATE):
            armour = ArmourLoadout((body,), body, barding=True)
            state = mounted_view(CombatMount.DEMIGRYPH, rider_kind=RiderKind.HUMAN, armour=armour)
            exemption = mounted_armour_test_exemptions(state, 'rider', Skill.STEALTH)
            self.assertEqual(tuple((m.rule_id, m.amount) for m in
                armour_test_modifiers(armour, Skill.STEALTH, **exemption)),
                ((BARDING_AGILITY_RULE_ID, -1),))
            self.assertEqual(armour_test_modifiers(armour, Skill.DEXTERITY, **exemption), ())
            state.mounts = (replace(state.mounts[0], mounted=False),)
            exemption = mounted_armour_test_exemptions(state, 'rider', Skill.ATHLETICS)
            self.assertEqual(tuple(m.amount for m in armour_test_modifiers(armour,
                Skill.ATHLETICS, **exemption)), (-1,))

    def test_elven_athletics_bonus_is_contextual_and_disappears_on_dismount(self):
        state = mounted_view(CombatMount.ELVEN_STEED)
        for skill in Skill:
            for context in ({}, {'oppose_attack': True}, {'control_mount': True}):
                actual = mounted_test_modifiers(state, 'rider', skill, **context)
                self.assertEqual(tuple((m.rule_id, m.amount) for m in actual),
                    ((ELVEN_STEED_RULE_ID, 1),) if skill is Skill.ATHLETICS and context else ())
        state.mounts = (replace(state.mounts[0], mounted=False),)
        self.assertEqual(mounted_test_modifiers(state, 'rider', Skill.ATHLETICS, oppose_attack=True), ())

    def test_contexts_require_real_bools_and_skills(self):
        state = mounted_view()
        for helper in (mounted_armour_test_exemptions, mounted_test_modifiers):
            for field in ('oppose_attack', 'control_mount'):
                with self.assertRaises(TypeError):
                    helper(state, 'rider', Skill.ATHLETICS, **{field: 1})
            with self.assertRaises(TypeError):
                helper(state, 'rider', 'athletics')

    def test_pegasus_flight_and_charge_are_separate_from_horse_monstrosity_limit(self):
        pegasus = mounted_view(CombatMount.PEGASUS, rider_kind=RiderKind.ELF,
            target_policy=TargetInjuryPolicy.MONSTROSITY)
        self.assertTrue(mounted_can_fly(pegasus, 'rider'))
        effect, = pc_mounted_attack_effects(pegasus, 'rider', 'enemy', is_charge=True)
        self.assertEqual(effect.rule_id, PEGASUS_KNIGHTS_RULE_ID)
        self.assertTrue(effect.affects_monstrosities)
        horse = mounted_view(target_policy=TargetInjuryPolicy.MONSTROSITY)
        self.assertFalse(mounted_can_fly(horse, 'rider'))
        self.assertEqual(pc_mounted_attack_effects(horse, 'rider', 'enemy', is_charge=True), ())
        horse = mounted_view()
        effect, = pc_mounted_attack_effects(horse, 'rider', 'enemy', is_charge=True)
        self.assertEqual(effect.rule_id, HORSE_NOBLE_STEED_RULE_ID)
        self.assertFalse(effect.affects_monstrosities)

    def test_fearsome_and_frightening_keep_their_distinct_skills(self):
        demigryph = mounted_view(CombatMount.DEMIGRYPH, rider_kind=RiderKind.HUMAN)
        skeleton = mounted_view(CombatMount.SKELETAL_STEED)
        for skill in Skill:
            self.assertTrue(mounted_give_ground_broken(demigryph, 'rider', skill))
            self.assertEqual(mounted_give_ground_broken(skeleton, 'rider', skill),
                skill in (Skill.MELEE, Skill.BRAWN))
        self.assertFalse(any(type(effect) is ProneBeforeGiveGroundSpec for effect in
            pc_mounted_attack_effects(demigryph, 'rider', 'enemy', is_charge=True)))
        skeleton.mounts = (replace(skeleton.mounts[0], mounted=False),)
        self.assertFalse(mounted_give_ground_broken(skeleton, 'rider', Skill.MELEE))

    def test_prone_dismount_proof_removes_current_bonus_and_capabilities(self):
        state = mounted_view(CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN,
            armour=ArmourLoadout(barding=True), prone=True)
        self.assertEqual(initial_pc_mounts(state.source), state.mounts)
        proof = expected_pc_dismount(state)
        self.assertIsNotNone(proof)
        state.mounts = updated_pc_mounts(state, proof)
        state.history = (proof,)
        validate_pc_mounts(state)
        self.assertEqual(mount_resilience_bonus(state, 'rider'), 0)
        self.assertFalse(mounted_can_fly(state, 'rider'))
        self.assertEqual(pc_mount_speed(state, 'rider', MovementSpeed.NORMAL), MovementSpeed.NORMAL)
        self.assertIsNone(expected_pc_dismount(state))

    def test_source_rechecks_reject_forged_rider_eligibility(self):
        state = mounted_view(CombatMount.PEGASUS, rider_kind=RiderKind.OTHER)
        with self.assertRaises(ValueError):
            initial_pc_mounts(state.source)
        with self.assertRaises(ValueError):
            mounted_can_fly(state, 'rider')

    def test_mounted_fearsome_is_executed_by_the_actual_k1_give_ground_follow_up(self):
        original = automatic_source(pc_count=1, enemy_count=1)
        npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(),
            defence=4, mount=CombatMount.DEMIGRYPH, rider_kind=RiderKind.HUMAN)
        source = replace(original, enemies=(npc.participant('minion1'),),
            facts=replace(original.facts, unmounted=False, can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG))
        state = initial_pc_melee_state(source)
        effects = pc_mounted_attack_effects(state, 'minion1', 'pc1', is_charge=False, attack_skill=Skill.MELEE)
        self.assertEqual(effects, (ConditionAfterGiveGroundSpec(Condition.BROKEN, DEMIGRYPH_FEARSOME_RULE_ID),))
        target = replace(state.participant('pc1').injury,
            conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        attack = AttackRequest('mounted-attack', TestRequest('mounted-test', TestProfile(1, 4)), None,
            DamageImpactSpec(DamageProfile(0), ResilienceProfile(10)), True, False,
            secondary_effects=effects)
        request = KernelAttackRequest('mounted-kernel', 'pc1', attack,
            TargetInjuryPolicy.PLAYER, target, True, False)
        class GiveGround:
            def choose_repeated_stagger(self, **kwargs):
                return StaggerChoice.GIVE_GROUND
            def choose_wound_negation(self, **kwargs):
                return None
        result = resolve_kernel_attack(request, SequenceRandom([1]), decisions=GiveGround())
        self.assertIs(type(result.follow_ups[0]), GiveGroundRequest)
        self.assertIs(type(result.follow_ups[1]), ConditionAfterGiveGroundRequest)
        applied = resolve_condition_after_give_ground(result.follow_ups[1], result.target_state)
        self.assertTrue(applied.state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.applied_secondary_rule_ids, (DEMIGRYPH_FEARSOME_RULE_ID,))

    def test_skeletal_frightening_uses_the_real_skill_and_respects_fearsome_immunity(self):
        state = mounted_view(CombatMount.SKELETAL_STEED)
        for skill in (Skill.MELEE, Skill.BRAWN):
            effects = pc_mounted_attack_effects(state, 'rider', 'enemy', is_charge=False, attack_skill=skill)
            self.assertEqual(effects, (ConditionAfterGiveGroundSpec(Condition.BROKEN,
                SKELETAL_STEED_FRIGHTENING_RULE_ID),))
        self.assertEqual(pc_mounted_attack_effects(state, 'rider', 'enemy',
            is_charge=False, attack_skill=Skill.SHOOTING), ())
        enemy_source = state.enemy('enemy').definition.generated_components
        enemy_source.mount, enemy_source.rider_kind = CombatMount.DEMIGRYPH, RiderKind.HUMAN
        state.mounts = (*state.mounts, PcMountedState('enemy', CombatMount.DEMIGRYPH, True))
        self.assertEqual(pc_mounted_attack_effects(state, 'rider', 'enemy',
            is_charge=False, attack_skill=Skill.MELEE), ())


if __name__ == '__main__':
    unittest.main()
