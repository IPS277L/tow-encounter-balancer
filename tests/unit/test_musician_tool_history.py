"""Exact tool history and Wound receipts over labelled preparation views.

Wound/position views isolate the physical source owner; they grant no combat
action or fabricated native replay. Actual end-to-end journals are integration
tests. Expected lost hands/objects/landing Zones are written explicitly here.
"""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.unit.test_musician_equipment import prepared, prepared_after, tool_id
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConsequence, WoundConsequenceRequest, WoundEntryId, WoundRecord
from towr.domain.pc_battlefield_models import PcAirspaceSpec, build_pc_battlefield, with_actor_placement
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_melee_result_models import PcBodyConsequenceProof, PcHandDropProof
from towr.domain.pc_musician_equipment_models import plan_musician_equipment
from towr.domain.pc_tool_models import (
    actor_tool_ground_zone, complete_pc_tool_equipment_proof,
    reconcile_native_tool_losses, validate_native_tools,
)
from towr.domain.tool_inventory_models import (
    ToolInventoryState, drop_tool, stow_tool,
)
from towr.domain.weapon_inventory_models import WeaponItemLocation as L


class PreparationView:
    def __init__(self,base,**values):
        self.base=base
        self.__dict__.update(values)
    def __getattr__(self,name):return getattr(self.base,name)
    def participant(self,actor):
        return next(member for member in self.party if member.actor_id==actor)
    def enemy(self,actor):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)


def pending_hand_drop(*,two_handed=False,table_total=12):
    state=prepared(held=not two_handed,hands=2 if two_handed else 1)
    if two_handed:
        equipment=plan_musician_equipment(state,'pc',tool_id(state))
        state=prepared_after(state,equipment)
    member=state.participant('pc')
    entry=WoundEntryId.SMASHED_HAND if table_total==12 else WoundEntryId.NICKED_ARM
    wound=WoundRecord(1,entry,table_total,(2,10) if table_total==12 else (4,),effect_resolved=True)
    member=replace(member,injury=replace(member.injury,wounds=(wound,)))
    source=WoundConsequenceRequest(1,WoundConsequence.DROP_RANDOM_HAND_ITEM,'RULE-HEALTH-004:wound-table')
    state=PreparationView(state,party=(member,),pending=(source,),pending_wound=None,pending_actor_id='pc')
    return state,PcHandDropProof(source,8,PcWeaponHand.RIGHT)


def changed_body(state,proof):
    from towr.domain._pc_heavy_wound_projection import body_consequence
    argument=(PcBodyConsequenceProof(proof.source,proof.die,proof.hand)
        if type(proof) is PcHandDropProof else proof)
    return body_consequence(state.participant('pc'),argument)


class MusicianToolHistoryTests(unittest.TestCase):
    def test_unjournaled_location_and_erased_equipment_receipts_are_rejected(self):
        state=prepared(held=True)
        member=state.participant('pc')
        item=member.tool_inventory.items[0]
        forged=replace(member,tool_inventory=member.tool_inventory.with_item(replace(item,location=L.CARRIED,grip=None)))
        with self.assertRaises(ValueError):
            validate_native_tools(PreparationView(state,party=(forged,)))
        with self.assertRaises(ValueError):
            replace(state,party=(forged,))
        carried=prepared()
        receipt=plan_musician_equipment(carried,'pc',tool_id(carried))
        after=prepared_after(carried,receipt)
        validate_native_tools(after)
        with self.assertRaises(ValueError):
            validate_native_tools(PreparationView(after,history=()))

    def test_reordered_duplicate_and_foreign_equipment_prefixes_are_rejected(self):
        state=prepared()
        receipt=plan_musician_equipment(state,'pc',tool_id(state))
        after=prepared_after(state,receipt)
        for history in ((receipt,receipt),(object(),receipt)):
            with self.subTest(history=history),self.assertRaises(ValueError):
                validate_native_tools(PreparationView(after,history=history))
        original=receipt.previous_tools.items[0]
        wrong=replace(original,source=replace(original.source,instrument_name='counterfeit'))
        bad=replace(receipt.previous,tool_inventory=ToolInventoryState((wrong,)))
        with self.assertRaises(ValueError):
            validate_native_tools(PreparationView(state,party=(bad,)))

    def test_completer_derives_one_actual_hand_loss_and_no_incidental_critical(self):
        state,proof=pending_hand_drop()
        before=deepcopy(state.participant('pc'))
        complete=complete_pc_tool_equipment_proof(state,proof)
        self.assertEqual(len(complete.tool_drops),1)
        drop,=complete.tool_drops
        self.assertEqual(drop.actor_id,'pc')
        self.assertEqual(drop.item_id,tool_id(state))
        self.assertEqual(drop.before,state.participant('pc').tool_inventory)
        self.assertIs(drop.after.items[0].location,L.DROPPED)
        self.assertEqual(drop.zone_id,'arena:zone:0')
        self.assertEqual(drop.after.items[0].dropped_zone_id,'arena:zone:0')
        self.assertIsNone(drop.after.items[0].grip)
        self.assertEqual(state.participant('pc'),before)
        self.assertIs(complete_pc_tool_equipment_proof(state,complete),complete)
        updates=reconcile_native_tool_losses(state,complete,{'party':(changed_body(state,complete),)})
        self.assertFalse(updates['party'][0].injury.conditions.has(Condition.CRITICALLY_INJURED))
        validate_native_tools(PreparationView(state,history=(*state.history,complete),**updates))

    def test_actual_two_handed_tool_falls_once_when_either_hand_is_lost(self):
        state,proof=pending_hand_drop(two_handed=True)
        complete=complete_pc_tool_equipment_proof(state,proof)
        self.assertEqual(len(complete.tool_drops),1)
        self.assertEqual(len(complete.tool_drops[0].after.items),1)
        updates=reconcile_native_tool_losses(state,complete,{'party':(changed_body(state,complete),)})
        validate_native_tools(PreparationView(state,history=(*state.history,complete),**updates))

    def test_unaffected_hand_and_carried_instrument_do_not_invent_a_drop(self):
        state,proof=pending_hand_drop()
        unaffected=replace(proof,die=1,hand=PcWeaponHand.LEFT)
        self.assertEqual(complete_pc_tool_equipment_proof(state,unaffected).tool_drops,())
        state=prepared()
        member=state.participant('pc')
        member=replace(member,injury=replace(member.injury,wounds=(
            WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),)))
        source=proof.source
        state=PreparationView(state,party=(member,),pending=(source,),pending_wound=None,pending_actor_id='pc')
        self.assertEqual(complete_pc_tool_equipment_proof(state,proof).tool_drops,())

    def test_projection_requires_exact_receipts_and_rejects_reapplication(self):
        state,proof=pending_hand_drop()
        after_body=changed_body(state,proof)
        with self.assertRaises(ValueError):
            reconcile_native_tool_losses(state,proof,{'party':(after_body,)})
        complete=complete_pc_tool_equipment_proof(state,proof)
        updates=reconcile_native_tool_losses(state,complete,{'party':(after_body,)})
        with self.assertRaises(ValueError):
            reconcile_native_tool_losses(state,complete,updates)
        with self.assertRaises(ValueError):
            validate_native_tools(PreparationView(state,history=(*state.history,complete,complete),**updates))

    def test_wrong_cached_transition_kind_zone_source_and_pending_target_are_rejected(self):
        state,proof=pending_hand_drop()
        bank=state.participant('pc').tool_inventory
        item=bank.items[0]
        for drops in ((stow_tool('pc',bank,item.id),),
                (drop_tool('pc',bank,item.id,actor_zone_id='arena:zone:1'),)):
            forged=replace(proof,tool_drops=drops)
            with self.subTest(drops=drops),self.assertRaises(ValueError):
                complete_pc_tool_equipment_proof(state,forged)
        for drops in (None,[],(True,)):
            with self.subTest(drops=drops),self.assertRaises(TypeError):
                complete_pc_tool_equipment_proof(state,replace(proof,tool_drops=drops))
        wrong=PreparationView(state,pending_actor_id='minion1')
        with self.assertRaises(ValueError):
            complete_pc_tool_equipment_proof(wrong,proof)
        with self.assertRaises(ValueError):
            complete_pc_tool_equipment_proof(PreparationView(state,pending=()),proof)

    def test_cached_frozen_drop_mutation_cannot_change_landing_zone(self):
        state,proof=pending_hand_drop()
        complete=deepcopy(complete_pc_tool_equipment_proof(state,proof))
        object.__setattr__(complete.tool_drops[0],'zone_id','forged-zone')
        with self.assertRaises(ValueError):
            complete_pc_tool_equipment_proof(state,complete)

    def test_ground_history_cannot_invent_a_zone_outside_its_actual_arena(self):
        state,proof=pending_hand_drop()
        bank=state.participant('pc').tool_inventory
        drop=drop_tool('pc',bank,tool_id(state),actor_zone_id='nonexistent-zone')
        forged=replace(proof,tool_drops=(drop,))
        member=replace(state.participant('pc'),tool_inventory=drop.after)
        with self.assertRaises(ValueError):
            validate_native_tools(PreparationView(state,party=(member,),history=(*state.history,forged)))

    def test_smashed_hand_body_proof_and_legacy_hand_proof_derive_the_same_physical_source(self):
        state,hand=pending_hand_drop()
        body=PcBodyConsequenceProof(hand.source,hand.die,hand.hand)
        self.assertEqual(complete_pc_tool_equipment_proof(state,hand).tool_drops,
            complete_pc_tool_equipment_proof(state,body).tool_drops)

    def test_relocated_clutch_drops_new_occupied_hand_instead_of_only_original_injury_hand(self):
        state=prepared(held=True)
        member=state.participant('pc')
        weapons=replace(member.weapon_inventory,items=tuple(replace(item,location=L.CARRIED,grip=None)
            for item in member.weapon_inventory.items))
        injury=replace(member.injury,wounds=(
            WoundRecord(1,WoundEntryId.SPILLING_GUTS,18,(8,10),effect_resolved=True),
            WoundRecord(2,WoundEntryId.SLASHED_FOREARMS,16,(6,10),effect_resolved=True)))
        member=replace(member,injury=injury,weapon_inventory=weapons,
            body_facts=(PcBodyFact(PcBodyFactKind.CLUTCH_STOMACH,1,PcWeaponHand.LEFT),))
        source=WoundConsequenceRequest(2,WoundConsequence.RANDOMISE_INJURED_ARM,'RULE-HEALTH-004:wound-table')
        state=PreparationView(state,party=(member,),pending=(source,),pending_wound=None,pending_actor_id='pc')
        proof=PcBodyConsequenceProof(source,1,PcWeaponHand.LEFT)
        complete=complete_pc_tool_equipment_proof(state,proof)
        self.assertEqual(len(complete.tool_drops),1)
        self.assertEqual(complete.tool_drops[0].item_id,tool_id(state))
        updates=reconcile_native_tool_losses(state,complete,{'party':(changed_body(state,complete),)})
        self.assertIn(PcBodyFact(PcBodyFactKind.CLUTCH_STOMACH,1,PcWeaponHand.RIGHT),updates['party'][0].body_facts)
        validate_native_tools(PreparationView(state,history=(complete,),**updates))

    def test_airborne_drop_freezes_ground_below_and_does_not_follow_later_actor_position(self):
        state,proof=pending_hand_drop()
        spec=replace(state.source.battlefield,airspace=PcAirspaceSpec())
        battlefield=build_pc_battlefield(spec,state.source.pc_activation_order,
            state.source.enemy_activation_order,state.source.facts.zone_id)
        battlefield=with_actor_placement(battlefield,'pc','arena:air:0')
        state=PreparationView(state,battlefield=battlefield)
        self.assertEqual(actor_tool_ground_zone(state,'pc'),'arena:zone:0')
        complete=complete_pc_tool_equipment_proof(state,proof)
        self.assertEqual(complete.tool_drops[0].zone_id,'arena:zone:0')
        updates=reconcile_native_tool_losses(state,complete,{'party':(changed_body(state,complete),)})
        moved=with_actor_placement(battlefield,'pc','arena:air:1')
        view=PreparationView(state,battlefield=moved,history=(*state.history,complete),**updates)
        validate_native_tools(view)
        self.assertEqual(view.participant('pc').tool_inventory.items[0].dropped_zone_id,'arena:zone:0')


if __name__=='__main__':
    unittest.main()
