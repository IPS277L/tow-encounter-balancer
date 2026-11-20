"""Typed Net throws and Recover at prepared independent-body boundaries.

These canonical source/body views do not assert native retention or tactical
admission. K1 throws/Recover use literal dice and keep actual physical Net IDs.
"""
from copy import copy, deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_weighted_net import source as net_source
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_active_actor_ids, pc_actor_inventory, pc_actor_npc_snapshot, pc_actor_npc_update, pc_actor_side
from towr.domain.pc_battlefield_models import with_actor_placement
from towr.domain.pc_briarroot_models import PcBriarrootBinding, BriarrootWeaponKind
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.pc_melee_result_models import PcAttackProof, PcFateDecline, PcMeleeState, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_mount_retention_models import _retained_battlefield
from towr.domain.pc_weighted_net_models import (
    PcNetLocation, PcNetReleaseProof, build_weighted_net_release, complete_weighted_net_throw,
    project_weighted_net_step, validate_weighted_net_bank, weighted_net_condition_sources,
    weighted_net_for_actor, weighted_net_item_close, weighted_net_profile,
    weighted_net_recovery_options, weighted_net_release_item, weighted_net_updates_from_attack,
    weighted_nets_after_equipment,
)
from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionTestOption
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy


def reserve(state, actor, kind):
    side = pc_actor_side(state, actor)
    opposite = CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES
    ids = (actor,*(candidate for candidate in pc_active_actor_ids(state) if candidate!=actor))
    clock = CombatRoundState(2, tuple(CombatTurnParticipant(candidate,pc_actor_side(state,candidate)) for candidate in ids),
        side_order=(side, opposite))
    clock = start_combat_turn(CombatTurnStartRequest('prepared:start:'+actor, clock, actor)).state
    state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve:'+actor,
        clock, actor, CombatActionDeclaration(kind), ActionSlotGrant.STANDARD)).state


def prepared(*, npcs=1):
    source = net_source(distance=RangedWeaponRange.CLOSE, npcs=npcs)
    member = replace(source.party[0], mount=CombatMount.HORSE)
    generated = replace(source.enemies[0].definition.generated_components, mount=CombatMount.HORSE)
    source = replace(source, party=(member,*source.party[1:]),
        enemies=(generated.participant(source.enemy_activation_order[0]),*source.enemies[1:]),
        facts=replace(source.facts, unmounted=False))
    initial = initial_pc_melee_state(source)
    state = Preparation(**{name:getattr(initial,name) for name in initial.__dataclass_fields__})
    state.companions = tuple(replace(row, retained_since_round=1) for row in initial.companions)
    state.mounts = tuple(replace(row, mounted=False) for row in initial.mounts)
    for body in state.companions:
        state.battlefield = _retained_battlefield(state.battlefield, body.rider_id,
            body.snapshot.state.actor_id, None)
    state.exited_npc_ids = ()
    return state


def throw(state, actor, target, *, hit=True, defenceless=False):
    reserve(state, actor, CombatActionKind.ATTACK)
    snapshot = pc_actor_npc_snapshot(state, target)
    injury = snapshot.state.injury
    if defenceless:
        injury = replace(injury, conditions=injury.conditions.with_condition(Condition.DEFENCELESS))
    profile = weighted_net_profile(2, 4, 3)
    identifier = 'prepared:net:'+actor+':'+target
    attack = AttackRequest(identifier, TestRequest(identifier+':throwing', profile.test_profile),
        None, profile.condition_impact, True, False)
    protection_profile, defender = npc_protection_test(state, target, actor, identifier+':protection',
        attack_skill=Skill.THROWING)
    protection = prepare_protection(ProtectionPreparationRequest(identifier+':prepared-protection',
        target, attack, Skill.THROWING, True, defenceless, False, False,
        None if defenceless else protection_profile.skill,
        (ProtectionTestOption(target, protection_profile.skill, defender),)))
    kernel = KernelAttackRequest(identifier+':kernel', target, protection.attack,
        snapshot.definition.injury_policy, injury, False, False)
    request = AttackActionExecutionRequest(identifier+':execute', state.round_state, actor, target, 1, kernel)
    defence_dice = 0 if protection.attack.defender_test is None else defender.profile.base_dice
    rng = ScriptedD10(([1,10] if hit else [10,10])+[10]*defence_dice)
    execution = execute_attack_action(request, rng)
    rng.assert_exhausted()
    landing = complete_weighted_net_throw(state, request, execution)
    inventory = pc_actor_inventory(state, actor)
    use = build_weapon_use(actor, inventory, inventory.active_item_id)
    intent = PcAttackWeaponIntent(request.id, actor, target, Skill.THROWING, use,
        protection_profile.skill, None, protection_profile)
    proof = PcAttackProof(request, protection, execution, None, weapon_intent=intent,
        weighted_net_landing=landing)
    following = copy(state)
    updates = weighted_net_updates_from_attack(state, request, execution, landing)
    updates.update(pc_actor_npc_update(state, target, injury=execution.resolution.target_state))
    updates = weighted_nets_after_equipment(state, proof, updates)
    for name,value in updates.items():
        setattr(following,name,value)
    following.history = (*state.history,proof)
    return following,proof


def release(state, actor, item):
    reserve(state, actor, CombatActionKind.RECOVER)
    request = build_weighted_net_release(state, item.bound_target_id, item.item_id)
    rng = ScriptedD10([1]*request.choice.test.profile.base_dice)
    result = execute_recover_action(request,rng)
    rng.assert_exhausted()
    after,battlefield = weighted_net_release_item(state,item.item_id,result)
    decline = (PcFateDecline(actor,request.choice.test.id,'test',state.source.participant(actor).fate_policy)
        if actor in state.source.pc_activation_order else None)
    proof = PcNetReleaseProof(request,result,item.item_id,item,after,state.battlefield,battlefield,decline)
    return proof,project_weighted_net_step(state,proof)


class CompanionWeightedNetTests(unittest.TestCase):
    def test_actual_hit_binds_own_body_for_both_sides_and_defenceless_still_has_no_wound(self):
        for npc in (False,True):
            for defenceless in (False,True):
                before = prepared()
                actor,target = ('minion1','pc1:mount') if npc else ('pc1','minion1:mount')
                after,proof = throw(before,actor,target,defenceless=defenceless)
                with self.subTest(npc=npc,defenceless=defenceless):
                    landing = proof.weighted_net_landing
                    self.assertEqual(landing.previous_item.item_id,landing.item.item_id)
                    self.assertIs(landing.item.location,PcNetLocation.BOUND)
                    self.assertEqual(landing.item.bound_target_id,target)
                    self.assertEqual(landing.item.binding.target_id,target)
                    self.assertTrue(pc_actor_npc_snapshot(after,target).state.injury.conditions.has(Condition.BURDENED))
                    self.assertEqual(pc_actor_npc_snapshot(after,target).state.injury.wounds,0)
                    self.assertIsNone(proof.execution.resolution.profile_wound)
                    self.assertIsNone(proof.execution.resolution.stagger)
                    self.assertEqual(after.source,before.source)
                    self.assertEqual(after.party[0].fate,before.party[0].fate)
                    validate_weighted_net_bank(after)

    def test_miss_freezes_one_marker_at_actual_body_position_not_later_rider_or_body_movement(self):
        for npc in (False,True):
            state = prepared()
            actor,target = ('minion1','pc1:mount') if npc else ('pc1','minion1:mount')
            after,proof = throw(state,actor,target,hit=False)
            item = proof.weighted_net_landing.item
            marker = after.battlefield.spatial.placement_for(item.marker_id)
            with self.subTest(npc=npc):
                self.assertIs(item.location,PcNetLocation.FREE)
                self.assertIn(target,item.ground.initial_close_actor_ids)
                self.assertEqual(marker.zone_id,state.battlefield.spatial.placement_for(target).zone_id)
                self.assertTrue(weighted_net_item_close(after,target,item.item_id))
                next_zone = after.battlefield.spatial.graph.adjacent_zone_ids(marker.zone_id)[0]
                after.battlefield = with_actor_placement(after.battlefield,target,next_zone)
                self.assertEqual(after.battlefield.spatial.placement_for(item.marker_id),marker)
                self.assertFalse(weighted_net_item_close(after,target,item.item_id))
                validate_weighted_net_bank(after)

    def test_existing_allied_actor_frees_body_using_own_brawn_and_preserves_own_fate_boundary(self):
        for npc in (False,True):
            state = prepared()
            thrower,target,helper = ('pc1','minion1:mount','minion1') if npc else ('minion1','pc1:mount','pc2')
            bound,_ = throw(state,thrower,target)
            item = weighted_net_for_actor(bound,thrower)
            proof,updates = release(bound,helper,item)
            with self.subTest(npc=npc):
                self.assertTrue(proof.result.resolution.removed)
                self.assertEqual(proof.request.actor_id,helper)
                self.assertEqual(proof.request.choice.target.entity_id,target)
                body = next(row for row in updates['companions'] if row.snapshot.state.actor_id==target)
                self.assertFalse(body.snapshot.state.injury.conditions.has(Condition.BURDENED))
                self.assertEqual(updates.get('enemies',bound.enemies),bound.enemies)
                self.assertEqual(proof.fate_decline is None,npc)
                self.assertIs(proof.item.location,PcNetLocation.FREE)
                self.assertEqual(proof.item.item_id,item.item_id)
                if npc:
                    self.assertNotIn('party',updates)

    def test_one_release_keeps_other_actual_net_and_independent_natural_weapon_restraint(self):
        state = prepared(npcs=2)
        first,_ = throw(state,'minion1','pc1:mount')
        both,_ = throw(first,'minion2','pc1:mount')
        item = weighted_net_for_actor(both,'minion1')
        proof,updates = release(both,'pc2',item)
        body = next(row for row in updates['companions'] if row.snapshot.state.actor_id=='pc1:mount')
        self.assertTrue(body.snapshot.state.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(len(weighted_net_condition_sources(both,'pc1:mount',bank=updates['weighted_nets'])),1)
        # Independent typed natural-weapon restraint is an explicit prepared
        # cause; its native Attack/Shield ownership is the Briarroot owner's job.
        single,_ = throw(prepared(),'minion1','pc1:mount')
        single.briarroot_bindings = (PcBriarrootBinding('prepared:vines','minion1','pc1:mount',
            'pc1:mount:natural','prepared:mounted-attack',0,kind=BriarrootWeaponKind.MOUNT_NATURAL),)
        _,updates = release(single,'pc2',weighted_net_for_actor(single,'minion1'))
        body = next(row for row in updates['companions'] if row.snapshot.state.actor_id=='pc1:mount')
        self.assertTrue(body.snapshot.state.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(single.briarroot_bindings[0].attacker_id,'pc1:mount')

    def test_enemy_helper_or_passive_body_cannot_gain_a_release_or_throw_policy(self):
        state,_ = throw(prepared(),'minion1','pc1:mount')
        item = weighted_net_for_actor(state,'minion1')
        reserve(state,'minion1',CombatActionKind.RECOVER)
        with self.assertRaises(ValueError):
            build_weighted_net_release(state,'pc1:mount',item.item_id)
        reserve(state,'pc1:mount',CombatActionKind.RECOVER)
        self.assertEqual(weighted_net_recovery_options(state,'pc1:mount'),())
        with self.assertRaises(ValueError):
            build_weighted_net_release(state,'pc1:mount',item.item_id)
        original = prepared()
        _,proof = throw(original,'pc1','minion1:mount')
        forged = deepcopy(proof.request)
        object.__setattr__(forged,'actor_id','pc1:mount')
        with self.assertRaises(ValueError):
            complete_weighted_net_throw(original,forged,proof.execution)
        with self.assertRaises(ValueError):
            complete_weighted_net_throw(original,proof.request,
                replace(proof.execution,target_id='foreign'))

    def test_existing_binding_keeps_its_full_source_while_unavailable_body_is_not_a_new_target(self):
        before = prepared()
        bound,proof = throw(before,'pc1','minion1:mount')
        erased = copy(bound)
        erased.history = ()
        with self.assertRaises(ValueError):
            validate_weighted_net_bank(erased)
        # The Net bank preserves a retained body's actual Condition source even
        # when its separate placement becomes unavailable to a future throw.
        # This validates storage only, not native permission to remount bound.
        hidden = copy(bound)
        hidden.mounts = tuple(replace(row,mounted=True) if row.actor_id=='minion1' else row
            for row in bound.mounts)
        validate_weighted_net_bank(hidden)
        for mounted in (False,True):
            unavailable = copy(before)
            if mounted:
                unavailable.mounts = tuple(replace(row,mounted=True) for row in before.mounts)
            else:
                unavailable.companions = tuple(replace(row,retained_since_round=None) for row in before.companions)
            with self.subTest(mounted=mounted), self.assertRaises(ValueError):
                complete_weighted_net_throw(unavailable,proof.request,proof.execution)
        malformed = deepcopy(bound)
        item = weighted_net_for_actor(malformed,'pc1')
        object.__setattr__(item,'bound_target_id','foreign')
        with self.assertRaises((TypeError,ValueError)):
            validate_weighted_net_bank(malformed)


if __name__=='__main__':
    unittest.main()
