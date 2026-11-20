"""Source-separated fixed NPC ally observations on a tiny actual trial."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_c24_champion_native import champion_scenario
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.turn_models import CombatSide
from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
from towr.simulation.pc_npc_ally_statistics import PcNpcAllyCount
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult
from towr.simulation.pc_melee_simulation import run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def source_with_ally():
    source=champion_scenario(rounds=1)
    npc=replace(source.enemies[0].definition.generated_components,injury_policy=TargetInjuryPolicy.MINION)
    return replace(source,npc_allies=(npc.participant('ally',side=CombatSide.PLAYERS_AND_ALLIES),),
        enemy_target_priority=('pc','ally'),npc_defeat_decisions=(
            MinionDefeatDecision('minion1','ally',NpcDefeatDisposition.KNOCKED_OUT,True),))


class NpcAllyStatisticsTests(unittest.TestCase):
    def test_paired_mount_capacity_applies_to_each_paid_action(self):
        from towr.domain.pc_mount_models import CombatMount,RiderKind
        from towr.simulation.pc_npc_ally_statistics import validate_npc_ally_counts
        source=source_with_ally()
        npc=replace(source.npc_allies[0].definition.generated_components,
            mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN)
        from towr.domain.pc_battlefield_models import PcBattlefieldSpec
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        from towr.domain.pc_melee_models import PcMeleePolicy
        source=replace(source,npc_allies=(npc.participant('ally',side=CombatSide.PLAYERS_AND_ALLIES),),
            party=tuple(replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT) for member in source.party),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG),
            facts=replace(source.facts,unmounted=False,can_leave_zone=True))
        validate_npc_ally_counts((PcNpcAllyCount('ally',2,4,0,0,0),),source,
            trials=1,started_rounds=1,actions=2)
        with self.assertRaises(ValueError):
            validate_npc_ally_counts((PcNpcAllyCount('ally',2,5,0,0,0),),source,
                trials=1,started_rounds=1,actions=2)

    def test_tiny_actual_trial_summary_and_wire_keep_ally_separate(self):
        source=source_with_ally()
        request=PcMeleeSimulationRequest(source,42,1)
        record=run_pc_melee_trial(request,0,rng_factory=lambda seed:SequenceRandom([10]*150))
        expected=(PcNpcAllyCount('ally',1,1,0,0,0),)
        self.assertEqual(record.npc_ally_counts,expected)
        self.assertEqual(tuple(row.actor_id for row in record.npc_recover_action_counts),('minion1',))
        self.assertEqual(tuple(row.actor_id for row in record.glorious_spend_counts),('pc',))
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,(record,)))
        self.assertEqual(summary.npc_ally_counts,expected)
        from towr.adapters.pc_melee_json import _summary
        self.assertEqual(_summary(summary)['npc_ally_counts'],[dict(actor_id='ally',actions=1,
            attacks=1,recover_actions=0,defeated=0,wounds=0)])
        for rows in (None,(),(replace(expected[0],actor_id='pc'),)):
            with self.subTest(rows=rows),self.assertRaises((TypeError,ValueError)):
                replace(record,npc_ally_counts=rows)
        with self.assertRaises((TypeError,ValueError)):
            replace(record,npc_ally_counts=(replace(expected[0],defeated=2),))

    def test_exact_counts_and_missing_source_are_rejected(self):
        with self.assertRaises(TypeError):PcNpcAllyCount('ally',True,1,0,0,0)
        with self.assertRaises(ValueError):PcNpcAllyCount('ally',0,0,1,0,0)
        from towr.simulation.pc_npc_ally_statistics import validate_npc_ally_counts
        with self.assertRaises(ValueError):
            validate_npc_ally_counts((PcNpcAllyCount('ally',0,0,0,0,0),),champion_scenario(),
                trials=1,started_rounds=1,actions=1)


if __name__=='__main__':unittest.main()
