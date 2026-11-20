"""Physical music plans over explicit native preparation snapshots.

These tests cover real immutable equipment, bodies and geometry. Preparation
snapshots do not claim to be executed combat journals; root integration owns
the committed action, paid Recover and complete replay admission.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_tactics_fixtures import tactical_snapshot
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.weapon_reload import execute_scripted_weapon_reload
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.injury_models import (
    WoundRecord, WoundEntryId, WoundRestrictionEffect, WoundRestriction, WoundEffectDuration,
)
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, PcMeleePolicy, PcWeaponHand, PcShieldLoadout,
    PcShieldHandConflictPolicy, PcShieldRecoveryPolicy,
)
from towr.domain.pc_musician_equipment_models import (
    PcMusicianEquipmentProof, plan_musician_equipment, project_musician_equipment,
)
from towr.domain.pc_npc_shield_models import NpcShieldLocation, validate_npc_shields, _free_shield_hand
from towr.domain.pc_npc_weapon_inventory import _plan as npc_weapon_plan
from towr.domain.pc_shield_models import PcShieldLocation, validate_pc_shields, pc_shield_recover_hand
from towr.domain.pc_tool_models import actor_tool_zone
from towr.domain.pc_weapon_inventory import pc_weapon_swap_hand, pc_weapon_swap_used
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.reload_models import begin_reload_cycle
from towr.domain.tool_inventory_models import ToolItemSource, ToolKind, initial_tool_inventory
from towr.domain.turn_models import CombatSide, CombatTurnState
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponItemLocation as L, weapon_reload_cycle_id


def instrument(*, hands=1, location=L.CARRIED, grip=None):
    return ToolItemSource('horn', ToolKind.MUSICIANS_GEAR, hands, location, grip, 'Marching instrument')


def prepared(*, hands=1, held=False, shield=False, generated=False, two_weapons=False, battlefield=True):
    scene = make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD)
    scene = replace(scene,party=tuple(replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        for member in scene.party))
    item = instrument(hands=hands, location=L.HELD if held else L.CARRIED,
        grip=G.BOTH if held and hands == 2 else G.RIGHT if held else None)
    if generated:
        npc = GeneratedNpc(3, 3, 4, 3, 4, 4,
            initial_generated_weapons(GeneratedWeapon.SWORD),
            ArmourLoadout(shield=ShieldKind.SHIELD if shield else None),
            defence=4, tools=(item,))
        scene = replace(scene, enemies=(npc.participant('minion1'),))
    else:
        member = scene.party[0]
        equipment = None
        if two_weapons:
            equipment = (PcWeaponItem('first', PcMeleeWeapon.SWORD, PcItemLocation.HELD, PcWeaponHand.LEFT),
                PcWeaponItem('second', PcMeleeWeapon.DAGGER, PcItemLocation.HELD, PcWeaponHand.RIGHT))
        member = replace(member, pc=replace(member.pc, tools=(item,)), combat_equipment=equipment,
            shield=(PcShieldLoadout(PcWeaponHand.RIGHT, PcShieldHandConflictPolicy.WEAPON_FIRST,
                PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if shield else None))
        scene = replace(scene, party=(member,))
    if battlefield:
        scene = replace(scene, facts=replace(scene.facts,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG))
    state = tactical_snapshot(scene, 'pc')
    if generated:
        state = replace(state, round_state=replace(state.round_state,
            active_turn=CombatTurnState('minion1', CombatSide.OPPOSITION),completed_turn_entity_ids=('pc',)))
    return state


def tool_id(state, actor='pc'):
    body = state.participant(actor) if actor == 'pc' else state.enemy(actor).state
    return body.tool_inventory.items[0].id


def with_unusable_arm(member, side):
    sequence=len(member.injury.wounds)+1
    wound=WoundRecord(sequence,WoundEntryId.SLASHED_FOREARMS,16,(6,10),effect_resolved=True)
    injury=replace(member.injury,wounds=(*member.injury.wounds,wound),
        active_wound_effects=(*member.injury.active_wound_effects,
            WoundRestrictionEffect(sequence,WoundRestriction.INJURED_ARM_UNUSABLE,WoundEffectDuration.UNTIL_HEALED)))
    return replace(member,injury=injury,body_facts=(*member.body_facts,
        PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,sequence,side)))


def prepared_member_view(state,member):
    """Explicit physical fixture; a changed tool pose is not a native journal."""
    class View:
        def __getattr__(self,name):return getattr(state,name)
        def participant(self,actor):
            return next(row for row in self.party if row.actor_id==actor)
        def enemy(self,actor):
            return next(row for row in self.enemies if row.state.actor_id==actor)
    view=View()
    if hasattr(member,'state'):
        view.enemies=tuple(member if row.state.actor_id==member.state.actor_id else row for row in state.enemies)
    else:
        view.party=tuple(member if row.actor_id==member.actor_id else row for row in state.party)
    return view


def prepared_after(state, proof):
    """Apply the exact proposal to a read-only fold view, without a fake replay."""
    updates = project_musician_equipment(state, proof, proof.item_id, pickup=proof.pickup)
    class View:
        def __getattr__(self, name):
            return updates[name] if name in updates else getattr(state, name)
        def participant(self, actor):
            return next(member for member in self.party if member.actor_id == actor)
        def enemy(self, actor):
            return next(enemy for enemy in self.enemies if enemy.state.actor_id == actor)
    view = View()
    view.history = (*state.history, proof)
    return view


class MusicianEquipmentTests(unittest.TestCase):
    def test_single_hand_instrument_uses_free_hand_without_touching_weapon_or_resources(self):
        state = prepared()
        before = deepcopy(state)
        proof = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(proof.tools.items[0].grip, G.RIGHT)
        self.assertEqual(proof.weapons, proof.previous_weapons)
        self.assertEqual(proof.state.injury, proof.previous.injury)
        self.assertEqual(proof.state.fate, proof.previous.fate)
        self.assertEqual(proof.round_state, state.round_state)
        self.assertEqual(state, before)
        self.assertEqual(proof.state.tool_inventory.items[0].source, state.source.party[0].pc.tools[0])

    def test_conflicting_weapon_only_is_stowed_and_selected_source_is_retained(self):
        state = prepared(two_weapons=True)
        proof = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(proof.tools.items[0].grip, G.LEFT)
        self.assertEqual(tuple(item.location for item in proof.weapons.items), (L.CARRIED, L.HELD))
        self.assertEqual(proof.weapons.active_item_id, proof.previous_weapons.active_item_id)
        for old, new in zip(proof.previous_weapons.items, proof.weapons.items):
            self.assertEqual(new, replace(old, location=new.location, grip=new.grip))

    def test_shield_is_kept_when_one_hand_suffices(self):
        state = prepared(shield=True)
        proof = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(proof.tools.items[0].grip, G.LEFT)
        self.assertEqual(proof.state.shield, proof.previous.shield)
        self.assertIs(proof.weapons.shield_hand, G.RIGHT)

    def test_two_handed_instrument_releases_real_pc_shield_and_marker(self):
        state = prepared(hands=2, shield=True)
        proof = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(proof.tools.items[0].grip, G.BOTH)
        self.assertIs(proof.state.shield.location, PcShieldLocation.DROPPED)
        self.assertIsNone(proof.weapons.shield_hand)
        self.assertEqual(proof.state.shield.ground.zone_id, actor_tool_zone(state, 'pc'))
        self.assertIsNotNone(proof.battlefield.spatial.placement_for('pc:shield:ground'))
        view = prepared_after(state, proof)
        validate_pc_shields(view)
        self.assertIsNone(pc_shield_recover_hand(view.participant('pc'), state=view))

    def test_stationary_scene_still_retains_real_shield_ground_source(self):
        state = prepared(hands=2, shield=True, battlefield=False)
        proof = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIsNone(proof.battlefield)
        self.assertEqual(proof.state.shield.ground.zone_id, state.source.facts.zone_id)
        validate_pc_shields(prepared_after(state, proof))

    def test_generated_two_handed_instrument_removes_shield_resilience_and_preserves_hp(self):
        state = prepared(hands=2, shield=True, generated=True)
        proof = plan_musician_equipment(state, 'minion1', tool_id(state, 'minion1'))
        self.assertIs(proof.npc_shield.location, NpcShieldLocation.DROPPED)
        self.assertIsNone(proof.weapons.shield_hand)
        self.assertFalse(proof.state.state.holds_shield)
        self.assertFalse(proof.state.state.wields_weapon)
        self.assertEqual(proof.state.state.injury, proof.previous.state.injury)
        self.assertEqual(proof.state.state.current_resilience.total,
            proof.previous.state.current_resilience.total-1)
        validate_npc_shields(prepared_after(state, proof))

    def test_cleanup_stows_tool_without_consuming_separate_weapon_swap_allowance(self):
        state = prepared(held=True)
        proof = plan_musician_equipment(state, 'pc', None)
        self.assertIs(proof.tools.items[0].location, L.CARRIED)
        self.assertEqual(proof.weapons, proof.previous_weapons)
        view = prepared_after(state, proof)
        self.assertFalse(pc_weapon_swap_used(view, 'pc'))
        self.assertIsNone(plan_musician_equipment(view, 'pc', None))

    def test_held_tool_hand_is_unavailable_to_weapon_grip_and_npc_shield_recovery(self):
        state = prepared(held=True)
        main = state.participant('pc').weapon_inventory.active_item_id
        self.assertIs(pc_weapon_swap_hand(state, 'pc', main), PcWeaponHand.LEFT)
        npc = prepared(held=True, generated=True)
        enemy = npc.enemy('minion1')
        self.assertIsNone(_free_shield_hand(enemy))
        item = enemy.state.weapon_inventory.active
        with self.assertRaises(ValueError):
            npc_weapon_plan(npc, 'minion1', item, G.RIGHT)
        with self.assertRaises(ValueError):
            npc_weapon_plan(npc, 'minion1', item, G.LEFT, reload=True)

    def test_healthy_hand_precedes_injured_hand_and_actual_injured_use_is_critical(self):
        state = prepared()
        member = state.participant('pc')
        injury = replace(member.injury,
            wounds=(WoundRecord(1, WoundEntryId.SMASHED_HAND, 12, (2,10), effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL, WoundEffectDuration.UNTIL_TREATED),))
        member = replace(member, injury=injury,
            body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),))
        state = replace(state, party=(member,))
        healthy = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(healthy.tools.items[0].grip, G.RIGHT)
        self.assertFalse(healthy.state.injury.conditions.has(Condition.CRITICALLY_INJURED))
        blocked = with_unusable_arm(member,PcWeaponHand.RIGHT)
        state = replace(state, party=(blocked,))
        injured = plan_musician_equipment(state, 'pc', tool_id(state))
        self.assertIs(injured.tools.items[0].grip, G.LEFT)
        self.assertTrue(injured.state.injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_two_hand_requirement_and_no_hands_do_not_create_usable_gear(self):
        state = prepared(hands=2)
        member = state.participant('pc')
        member = with_unusable_arm(member,PcWeaponHand.RIGHT)
        state = replace(state, party=(member,))
        self.assertIsNone(plan_musician_equipment(state, 'pc', tool_id(state)))
        held = prepared(held=True)
        member = held.participant('pc')
        for side in PcWeaponHand:
            member=with_unusable_arm(member,side)
        held = replace(held, party=(member,))
        self.assertIsNone(plan_musician_equipment(held, 'pc', None))

    def test_dropped_tool_is_not_freely_equipped_and_paid_pickup_requires_actual_zone(self):
        state = prepared()
        member = state.participant('pc')
        item = member.tool_inventory.items[0]
        dropped = replace(item, location=L.DROPPED, grip=None, dropped_zone_id=actor_tool_zone(state,'pc'))
        member = replace(member, tool_inventory=member.tool_inventory.with_item(dropped))
        state = prepared_member_view(state,member)
        self.assertIsNone(plan_musician_equipment(state, 'pc', item.id))
        proof = plan_musician_equipment(state, 'pc', item.id, pickup=True)
        self.assertTrue(proof.pickup)
        self.assertIs(proof.tools.items[0].location,L.HELD)
        self.assertIsNone(proof.tools.items[0].dropped_zone_id)
        elsewhere = replace(dropped, dropped_zone_id=state.source.facts.zone_id+':zone:1')
        member = replace(member, tool_inventory=member.tool_inventory.with_item(elsewhere))
        self.assertIsNone(plan_musician_equipment(prepared_member_view(state,member), 'pc', item.id,pickup=True))

    def test_full_source_clock_item_and_once_guards_reject_detached_receipts(self):
        state = prepared()
        proof = plan_musician_equipment(state,'pc',tool_id(state))
        for forged in (replace(proof, history_index=proof.history_index+1),
                replace(proof, action_id='foreign-action')):
            with self.subTest(forged=forged.action_id),self.assertRaises(ValueError):
                project_musician_equipment(state,forged,proof.item_id)
        with self.assertRaises(ValueError):
            project_musician_equipment(prepared_after(state,proof),proof,proof.item_id)
        with self.assertRaises(ValueError):
            plan_musician_equipment(state,'pc','foreign-tool')
        with self.assertRaises(TypeError):
            plan_musician_equipment(state,'pc',tool_id(state),pickup=1)
        self.assertIsNone(plan_musician_equipment(state,'minion1',None))

    def test_equipping_music_preserves_actual_partial_reload_history_and_all_weapon_units(self):
        from tests.unit.test_pc_weapon_inventory import source as pistol_source
        scene=pistol_source()
        member=scene.party[0]
        scene=replace(scene,party=(replace(member,pc=replace(member.pc,tools=(instrument(hands=2),))),))
        state=tactical_snapshot(scene,'pc1')
        member=state.participant('pc1')
        gun=member.weapon_inventory.active
        unloaded=begin_reload_cycle(gun.reload,weapon_reload_cycle_id(gun.id,1))
        partial=execute_scripted_weapon_reload(unloaded,actor='pc1').state
        self.assertFalse(partial.loaded)
        self.assertEqual(partial.exacting.accumulated_successes,1)
        inventory=member.weapon_inventory.with_item(replace(gun,reload=unloaded))
        inventory=inventory.with_item(replace(inventory.active,reload=partial))
        member=replace(member,weapon_inventory=inventory)
        class View:
            def __getattr__(self,name):return getattr(state,name)
            def participant(self,actor):
                if actor!='pc1':raise KeyError(actor)
                return member
        view=View()
        proof=plan_musician_equipment(view,'pc1',member.tool_inventory.items[0].id)
        self.assertEqual(tuple(item.id for item in proof.weapons.items),tuple(item.id for item in inventory.items))
        self.assertEqual(proof.weapons.active.reload,partial)
        self.assertEqual(proof.weapons.items[1],inventory.items[1])
        self.assertEqual(proof.state.fate,member.fate)
        forged=deepcopy(proof)
        object.__setattr__(forged.weapons.active,'reload',gun.reload)
        with self.assertRaises((TypeError,ValueError)):
            project_musician_equipment(view,forged,proof.item_id)

    def test_paid_pickup_has_recover_cost_instead_of_non_recover_critical(self):
        state=prepared()
        member=state.participant('pc')
        injury=replace(member.injury,
            wounds=(WoundRecord(1,WoundEntryId.INTERNAL_INJURY,14,(4,10),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,
                WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_HEALED),))
        member=replace(member,injury=injury)
        item=member.tool_inventory.items[0]
        tools=member.tool_inventory.with_item(replace(item,location=L.DROPPED,grip=None,
            dropped_zone_id=actor_tool_zone(state,'pc')))
        state=prepared_member_view(state,replace(member,tool_inventory=tools))
        proof=plan_musician_equipment(state,'pc',item.id,pickup=True)
        self.assertFalse(proof.state.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(proof.state.injury,member.injury)

    def test_paid_pickup_nested_receipt_preserves_shield_ground_history_for_both_sides(self):
        from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
        from towr.domain.magic_models import WizardMagicState
        from towr.domain.recover_models import (
            RecoverActionExecutionRequest,RecoverMode,RecoverObjectInteractionFollowUp,RecoverStandardChoice,
        )
        from towr.domain.turn_models import (
            ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
        )
        from towr.rules.recover_resolution import execute_recover_action
        from towr.rules.turn_resolution import reserve_combat_action_slot
        for generated in (False,True):
            with self.subTest(generated=generated):
                state=prepared(hands=2,shield=True,generated=generated)
                actor='minion1' if generated else 'pc'
                body=state.enemy(actor).state if generated else state.participant(actor)
                item=body.tool_inventory.items[0]
                tools=body.tool_inventory.with_item(replace(item,location=L.DROPPED,grip=None,
                    dropped_zone_id=actor_tool_zone(state,actor)))
                if generated:
                    enemy=state.enemy(actor)
                    state=prepared_member_view(state,replace(enemy,state=replace(body,tool_inventory=tools)))
                else:
                    state=prepared_member_view(state,replace(body,tool_inventory=tools))
                clock=reserve_combat_action_slot(CombatActionSlotRequest('music:pickup:reserve',state.round_state,
                    actor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
                state.round_state=clock
                equipment=plan_musician_equipment(state,actor,item.id,pickup=True)
                choice=RecoverStandardChoice(WizardMagicState(),object_interaction=
                    RecoverObjectInteractionFollowUp('music:pickup:interaction',actor,item.id,True))
                request=RecoverActionExecutionRequest('music:pickup:execute',clock,actor,body.injury.conditions,
                    True,1,RecoverMode.STANDARD,choice)
                rng=ScriptedD10([])
                result=execute_recover_action(request,rng)
                rng.assert_exhausted()
                nested=PcMusicianRecoverProof(result,equipment)
                view=prepared_after(state,equipment)
                view.history=(*state.history,nested)
                view.round_state=result.round_state
                self.assertTrue(result.slot.executed)
                (validate_npc_shields if generated else validate_pc_shields)(view)


if __name__ == '__main__':
    unittest.main()
