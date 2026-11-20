"""Physical NPC bases and zero-ledger Shield sources; no pending Bane policy."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_tactics_fixtures import automatic_source
from tests.unit.test_pc_npc_shield import view
from towr.domain.armour_models import ArmourLoadout,BodyArmour,HelmetKind,ShieldKind
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount,PcMountedState
from towr.domain.pc_npc_resilience_models import (
    npc_base_equipment_resilience,npc_current_resilience,npc_mount_resilience_source,
)
from towr.domain.pc_npc_shield_models import expected_npc_shield_drop
from towr.domain.turn_models import CombatActionKind


def selected_reload_drop(state):
    # The prepared fixture authors its selected Reload. Its source-equipment
    # proof is real; this helper makes no complete battle/tactical claim.
    with patch('towr.domain.pc_melee_result_models.pc_melee_selected_action',
            return_value=CombatActionKind.IMPROVISE):
        return expected_npc_shield_drop(state)


class PcNpcResilienceTests(unittest.TestCase):
    def test_equipment_base_is_original_body_helmet_shield_mount_and_barding(self):
        armour=ArmourLoadout((BodyArmour.METEORIC_IRON,),BodyArmour.METEORIC_IRON,
            HelmetKind.HUNT,ShieldKind.BRIARROOT,True)
        state=view(armour=armour,mount=CombatMount.HORSE)
        base=npc_base_equipment_resilience(state,'enemy')
        self.assertEqual(base,state.source.enemy('enemy').definition.resilience)
        self.assertEqual(base.bonus,7)
        self.assertTrue(base.mundane_armour_ward)
        self.assertEqual(npc_base_equipment_resilience(state,'enemy',shield_held=False).bonus,6)
        self.assertEqual(npc_base_equipment_resilience(state,'enemy',mounted=False).bonus,5)
        both=npc_base_equipment_resilience(state,'enemy',shield_held=False,mounted=False)
        self.assertEqual(both.bonus,4)
        self.assertTrue(both.mundane_armour_ward)
        self.assertEqual(npc_current_resilience(state,'enemy'),base)

    def test_zero_bonus_worn_helmet_stays_armoured_without_any_bane_receipt(self):
        state=view(armour=ArmourLoadout(helmet=HelmetKind.HELMET),shield=None)
        base=npc_current_resilience(state,'enemy')
        self.assertEqual(base.bonus,0)
        self.assertTrue(base.armoured)
        self.assertTrue(base.is_armoured)

    def test_authored_numeric_source_keeps_its_full_printed_profile(self):
        state=initial_pc_melee_state(automatic_source(pc_count=1))
        actor=state.source.enemies[0].state.actor_id
        self.assertEqual(npc_current_resilience(state,actor),state.source.enemy(actor).definition.resilience)
        for override in (dict(mounted=False),dict(shield_held=False)):
            with self.subTest(override=override),self.assertRaises(ValueError):
                npc_base_equipment_resilience(state,actor,**override)

    def test_shield_proof_requires_exact_mount_and_typed_empty_ledger_sources(self):
        state=view(mount=CombatMount.HORSE)
        proof=selected_reload_drop(state)
        self.assertEqual(proof.mount_source,PcMountedState('enemy',CombatMount.HORSE,True))
        self.assertEqual(proof.armour_bane_sources,())
        self.assertEqual(proof.enemy.state.current_resilience.bonus,
            proof.previous_enemy.state.current_resilience.bonus-1)
        for changes in (dict(mount_source=None),dict(mount_source=replace(proof.mount_source,actor_id='foreign')),
                dict(mount_source=replace(proof.mount_source,mounted=False)),dict(armour_bane_sources=[])):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(proof,**changes)
        forged=deepcopy(proof.mount_source)
        object.__setattr__(forged,'mounted',1)
        with self.assertRaises(TypeError):
            replace(proof,mount_source=forged)

    def test_missing_or_foreign_actual_mount_bank_is_not_repaired_from_source(self):
        for mounts in ((),[],(PcMountedState('foreign',CombatMount.HORSE,True),),
                (PcMountedState('enemy',CombatMount.ELVEN_STEED,True),)):
            state=view(mount=CombatMount.HORSE)
            state.mounts=mounts
            with self.subTest(mounts=mounts),self.assertRaises((TypeError,ValueError)):
                npc_mount_resilience_source(state,'enemy')

    def test_corrupt_previous_numeric_resilience_cannot_be_used_as_a_new_base(self):
        proof=selected_reload_drop(view(mount=CombatMount.HORSE))
        previous=replace(proof.previous_enemy,state=replace(proof.previous_enemy.state,
            current_resilience=replace(proof.previous_enemy.state.current_resilience,bonus=0)))
        with self.assertRaisesRegex(ValueError,'provenance'):
            replace(proof,previous_enemy=previous)


if __name__=='__main__':
    unittest.main()
