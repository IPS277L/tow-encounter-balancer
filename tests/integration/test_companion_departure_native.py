"""Actual mounted NPC defeat/GM acknowledgement before objective completion."""
from dataclasses import replace
from unittest import TestCase, main
from unittest.mock import patch

from tests.integration.test_back_in_saddle_ground_native import npc_ground_source
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain import talent_actor_models
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_companion_departure_models import PcCompanionDepartureProof
from towr.domain.pc_melee_result_models import PcMeleeStep, PcProfileWoundProof, initial_pc_melee_state
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def mounted_rider_defeat_source():
    source=npc_ground_source()
    member=source.party[0]
    member=replace(member,mount=None,pc=replace(member.pc,weapon_skill=5,strength=5),
        defeat_decisions=tuple(replace(item,disposition=NpcDefeatDisposition.KILLED)
            for item in member.defeat_decisions))
    npc=replace(source.enemies[0].definition.generated_components,weapon_skill=1,strength=1,
        toughness=1,agility=4,melee=2,athletics=2,defence=2)
    return replace(source,party=(member,),enemies=(npc.participant('minion1'),),
        battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG),facts=replace(source.facts,all_opponents_close=True))


class CompanionDepartureNativeTests(TestCase):
    def test_killed_mounted_rider_loses_only_its_living_mount_before_terminal_and_replays(self):
        with patch.object(talent_actor_models,'NPC_EXECUTABLE_TALENTS',
                talent_actor_models.NPC_EXECUTABLE_TALENTS | {TalentId.BACK_IN_THE_SADDLE}):
            source=mounted_rider_defeat_source()
            rng=ScriptedD10([1]*5+[10]*4)
            result=run_pc_melee_scenario(source,rng)
            rng.assert_exhausted()
            self.assertIsNone(result.unsupported)
            departure,=tuple(step for step in result.steps if type(step.proof) is PcCompanionDepartureProof)
            acknowledgement,=tuple(step for step in result.steps if type(step.proof) is PcProfileWoundProof)
            self.assertEqual(departure.proof.source_proof,acknowledgement.proof)
            self.assertEqual(departure.source.companions[0].snapshot,departure.state.companions[0].snapshot)
            self.assertEqual(departure.state.companions[0].snapshot.state.injury.wounds,0)
            self.assertFalse(departure.state.companions[0].snapshot.state.injury.defeated)
            self.assertFalse(departure.state.mounts[0].mounted)
            self.assertEqual(departure.state.party,departure.source.party)
            self.assertEqual(tuple(row.state.actor_id for row in departure.state.enemies),source.enemy_activation_order)
            self.assertEqual(result.state.enemy('minion1').state.current_resilience.total,1)
            with self.assertRaises(ValueError): PcMeleeStep(departure.state,departure.proof)
            state=initial_pc_melee_state(source)
            for step in result.steps: state=apply_pc_melee_step(state,step)
            self.assertEqual(state,result.state)


if __name__=='__main__': main()
