"""Prepared physical companions with real typed Attack/Protection executions.

These isolate atomic wrappers and do not claim a native detach/turn journal.
"""
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedRangedFacts, GeneratedWeapon
from towr.domain.pc_actor_models import pc_actor_npc_snapshot
from towr.domain.pc_armour_bane_models import (
    armour_bane_applications, armour_bane_attack_updates, build_armour_bane_application,
)
from towr.domain.pc_battlefield_models import _close_key
from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcMeleeState, PcAttackProof, initial_pc_melee_state, pc_melee_action_id, prepare_pc_weapon_kernel,
)
from towr.domain.pc_npc_ranged_models import prepare_pc_npc_ranged_shot
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_resilience_models import npc_base_equipment_resilience, npc_current_resilience
from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    CombatTurnStartRequest, CombatActionSlotRequest, CombatActionDeclaration, CombatActionKind, ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


class PreparedAttackView(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_base'), name)


def prepared(*, npc_actor=True, weapon=GeneratedWeapon.AXE, defenceless=False):
    source = mount_source()
    member = replace(source.party[0], pc=replace(source.party[0].pc, weapon=PcMeleeWeapon.AXE, strength=1),
        armour=ArmourLoadout(barding=True), talents=(paid_talent(TalentId.ARMOUR_BANE),))
    component = source.enemies[0].definition.generated_components
    ranged = (GeneratedRangedFacts(3, 4,  True, True, True)
        if weapon in (GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL) else None)
    component = replace(component, strength=1, weapons=initial_generated_weapons(weapon),
        armour=ArmourLoadout(barding=True), talents=(paid_talent(TalentId.ARMOUR_BANE),), ranged=ranged, initiative=3 if ranged is not None else None,dexterity=4 if ranged is not None else None)
    source = replace(source, party=(member,), enemies=(component.participant('minion1'),), max_rounds=2,
        npc_ranged_policies=(() if ranged is None else (pc_npc_ranged_policy_for_generated(component, 'minion1'),)))
    base = initial_pc_melee_state(source)
    actor, rider = ('minion1', 'pc1') if npc_actor else ('pc1', 'minion1')
    target = rider+':mount'
    rows = tuple(replace(row, retained_since_round=1) if row.rider_id == rider else row for row in base.companions)
    if defenceless:
        rows = tuple(replace(row, snapshot=replace(row.snapshot, state=replace(row.snapshot.state,
            injury=replace(row.snapshot.state.injury,
                conditions=row.snapshot.state.injury.conditions.with_condition(Condition.DEFENCELESS)))))
            if row.rider_id == rider else row for row in rows)
    origin = base.battlefield.spatial.placement_for(rider)
    battlefield = replace(base.battlefield, spatial=replace(base.battlefield.spatial,
        placements=(*base.battlefield.spatial.placements, SpatialEntityPlacement(target, origin.side_id, origin.zone_id))),
        close_pairs=(*base.battlefield.close_pairs, _close_key(target, rider), _close_key(target, actor)))
    clock = base.round_state
    if npc_actor:
        clock = replace(clock, completed_turn_entity_ids=source.pc_activation_order)
    clock = start_combat_turn(CombatTurnStartRequest('prepared:start', clock, actor)).state
    clock = reserve_combat_action_slot(CombatActionSlotRequest('prepared:slot', clock, actor,
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)).state
    view = PreparedAttackView(_base=base, **{name: getattr(base, name) for name in base.__dataclass_fields__})
    view.companions, view.battlefield, view.round_state = rows, battlefield, clock
    view.mounts = tuple(replace(row, mounted=False) if row.actor_id == rider else row for row in base.mounts)
    return view, actor, target


def attack_request(view, actor, target):
    identifier = pc_melee_action_id(view, actor)
    intent = build_pc_explicit_attack_weapon_intent(view, actor, target, identifier)
    kernel, protection = prepare_pc_weapon_kernel(view, intent, identifier)
    return (AttackActionExecutionRequest(identifier+':execute', view.round_state, actor, target, 1, kernel),
        protection, intent)


class CompanionAttackWrapperTests(unittest.TestCase):
    def test_barding_is_the_body_source_and_cannot_accept_rider_shield_or_mount_overrides(self):
        for npc_actor in (False, True):
            view, _, target = prepared(npc_actor=npc_actor)
            with self.subTest(npc_actor=npc_actor):
                base = npc_base_equipment_resilience(view, target)
                self.assertEqual((base.toughness, base.bonus, base.total), (3, 1, 4))
                self.assertTrue(base.is_armoured)
                for override in (dict(shield_held=False), dict(shield_held=True), dict(mounted=False), dict(mounted=True)):
                    with self.assertRaises(ValueError):
                        npc_base_equipment_resilience(view, target, **override)

    def test_real_axe_hit_updates_own_body_ledger_and_preserves_pending_injury_and_remount_loss(self):
        for npc_actor in (False, True):
            view, actor, target = prepared(npc_actor=npc_actor)
            with self.subTest(npc_actor=npc_actor):
                request, protection, intent = attack_request(view, actor, target)
                rng = ScriptedD10([1]*6)
                execution = execute_attack_action(request, rng)
                rng.assert_exhausted()
                application = build_armour_bane_application(view, request, execution, intent.attack_use)
                self.assertIsNotNone(application)
                self.assertEqual((application.before.total, application.after.total), (4, 3))
                pending = tuple(replace(row, snapshot=replace(row.snapshot, state=replace(row.snapshot.state,
                    injury=execution.resolution.target_state))) if row.snapshot.state.actor_id == target else row
                    for row in view.companions)
                updates = armour_bane_attack_updates(view, application, dict(companions=pending))
                changed = next(row for row in updates['companions'] if row.snapshot.state.actor_id == target)
                self.assertEqual(changed.snapshot.state.injury, execution.resolution.target_state)
                self.assertEqual(changed.snapshot.state.current_resilience, application.after)
                self.assertEqual(changed.snapshot.definition, pc_actor_npc_snapshot(view, target).definition)
                self.assertNotIn('enemies', updates)
                proof = PcAttackProof(request, prepare_protection(protection), execution, None,
                    weapon_intent=intent, armour_bane=application)
                after = copy(view)
                after.companions, after.history = updates['companions'], (proof,)
                self.assertEqual(armour_bane_applications(after, target), (application,))
                self.assertEqual(armour_bane_applications(after, changed.rider_id), ())
                self.assertEqual(npc_current_resilience(after, target), application.after)
                # Prepared remount/heal observations retain the actual body's
                # source and history; they are not a claimed native timeline.
                after.mounts = tuple(replace(row, mounted=True) if row.actor_id == changed.rider_id else row
                    for row in after.mounts)
                after.companions = tuple(replace(row, retained_since_round=None,
                    snapshot=replace(row.snapshot, state=replace(row.snapshot.state,
                        injury=replace(row.snapshot.state.injury,
                            conditions=row.snapshot.state.injury.conditions.without_condition(Condition.STAGGERED)))))
                    if row.snapshot.state.actor_id == target else row for row in after.companions)
                self.assertEqual(npc_current_resilience(after, target), application.after)
                self.assertEqual(initial_pc_melee_state(view.source).companions[0].snapshot.state.current_resilience.total, 4)
                after.history = (proof, proof)
                with self.assertRaises(ValueError):
                    armour_bane_applications(after, target)
                after.history = (replace(proof, armour_bane=None),)
                self.assertEqual(npc_current_resilience(after, target).total, 4)  # No trust in cached reduced R.

    def test_npc_pistol_preparation_uses_the_companions_committed_athletics_without_pc_fate(self):
        view, actor, target = prepared(weapon=GeneratedWeapon.PISTOL)
        request, protection, intent = attack_request(view, actor, target)
        self.assertIs(intent.protection_skill, Skill.ATHLETICS)
        self.assertEqual(request.kernel_request.attack.defender_test.profile.dice, 4)
        prepared_shot = prepare_pc_npc_ranged_shot(view, request)
        self.assertEqual(prepared_shot.source_request.attack.target_id, target)
        self.assertEqual(prepared_shot.source_request.attack.kernel_request.attack.defender_test,
            request.kernel_request.attack.defender_test)
        self.assertEqual(view.participant('pc1').fate, initial_pc_melee_state(view.source).participant('pc1').fate)
        self.assertIsNone(pc_actor_npc_snapshot(view, target).state.weapon_inventory)

    def test_shot_rejects_a_defender_profile_detached_from_its_actual_companion_source(self):
        view, actor, target = prepared(weapon=GeneratedWeapon.PISTOL)
        request, _, _ = attack_request(view, actor, target)
        defender = request.kernel_request.attack.defender_test
        forged = replace(request, kernel_request=replace(request.kernel_request,
            attack=replace(request.kernel_request.attack, defender_test=replace(defender,
                profile=replace(defender.profile, threshold=5)))))
        with self.assertRaisesRegex(ValueError, 'committed Protection'):
            prepare_pc_npc_ranged_shot(view, forged)

    def test_body_loss_ledger_rejects_an_application_from_another_attack(self):
        view, actor, target = prepared()
        request, protection, intent = attack_request(view, actor, target)
        execution = execute_attack_action(request, ScriptedD10([1]*6))
        application = build_armour_bane_application(view, request, execution, intent.attack_use)
        proof = PcAttackProof(request, prepare_protection(protection), execution, None,
            weapon_intent=intent, armour_bane=replace(application, attack_id='foreign:attack'))
        view.history = (proof,)
        with self.assertRaises(ValueError):
            armour_bane_applications(view, target)

    def test_profile_repeater_forecast_uses_actual_body_and_unopposed_defenceless_branch(self):
        for defenceless in (False, True):
            view, actor, target = prepared(weapon=GeneratedWeapon.REPEATER_PISTOL, defenceless=defenceless)
            with self.subTest(defenceless=defenceless):
                request, _, intent = attack_request(view, actor, target)
                preparation = prepare_pc_npc_ranged_shot(view, request)
                self.assertEqual(preparation.source_request.attack.target_id, target)
                ordinary = replace(request.kernel_request.attack.attacker_test, dice_modifiers=tuple(
                    row for row in request.kernel_request.attack.attacker_test.dice_modifiers
                    if row.rule_id != REPEATER_SHOOTING_BONUS_RULE_ID))
                actual = npc_repeater_bonus(view, actor, ordinary,
                    request.kernel_request.attack.defender_test, target, defender_skill=intent.protection_skill)
                self.assertIs(type(actual), bool)
                self.assertEqual(actual, preparation.source_request.uses_optional_reload_bonus)


if __name__ == '__main__':
    unittest.main()
