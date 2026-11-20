"""Source-bound Rapid observations and shared action budgets, not MC accuracy."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.integration.test_talent_rapid_reload_json import pc_literal_dice, npc_literal_dice
from tests.unit.test_talent_rapid_reload_execution import pc_source, npc_source
from tests.support.pc_melee_scripted import ScriptedD10
from towr.simulation.pc_melee_models import (
    PcAimCount, PcAimCounts, PcMeleeSimulationRequest, validate_aim_counts,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_rapid_reload_statistics import (
    PcRapidReloadCount, rapid_reload_count_actors, validate_rapid_reload_counts,
    validate_npc_aim_counts, rapid_reload_count_by_actor,
)
from towr.simulation.pc_ranged_statistics import PcRangedCount, pc_ranged_count_actors


def validate(record, **changes):
    arguments=dict(trials=1,actions=record.executed_actions,started_rounds=record.started_rounds,
        pc_ranged_counts=record.pc_ranged_counts,npc_ranged_counts=record.npc_ranged_counts,
        aim_counts=record.aim,npc_aim_counts=record.npc_aim_counts,
        pc_extra_counts=record.pc_extra_attack_counts,npc_extra_counts=record.npc_extra_attack_counts)
    arguments.update(changes)
    validate_rapid_reload_counts(record.rapid_reload_counts,record.source_scenario,**arguments)


class RapidReloadStatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pc=run_pc_melee_simulation(PcMeleeSimulationRequest(pc_source(),42,1),rng_factory=pc_literal_dice)
        cls.npc=run_pc_melee_simulation(PcMeleeSimulationRequest(npc_source(),42,1),rng_factory=npc_literal_dice)

    def test_native_observations_count_only_the_actual_second_action_and_keep_source_order(self):
        for result,actor in ((self.pc,'pc1'),(self.npc,'minion1')):
            record=result.records[0]
            self.assertEqual(record.rapid_reload_counts,(PcRapidReloadCount(actor,1),))
            self.assertEqual(record.npc_extra_attack_counts[0].count,0)
            summary=summarize_pc_melee_simulation(result)
            self.assertEqual(summary.rapid_reload_counts,record.rapid_reload_counts)
            validate(record)
        both=replace(npc_source(),party=pc_source().party)
        self.assertEqual(rapid_reload_count_actors(both),('pc1','minion1'))
        self.assertEqual(pc_ranged_count_actors(both),('pc1',))
        zeros=(PcRapidReloadCount('pc1',0),PcRapidReloadCount('minion1',0))
        self.assertEqual(rapid_reload_count_by_actor(zeros,both),{'pc1':0,'minion1':0})
        with self.assertRaises(ValueError):
            rapid_reload_count_by_actor(zeros[::-1],both)

    def test_missing_foreign_duplicate_wrong_order_and_cached_counts_are_rejected(self):
        record=self.pc.records[0]
        for bad in (None,(),[],(PcRapidReloadCount('foreign',1),),
                record.rapid_reload_counts*2):
            with self.subTest(bad=bad),self.assertRaises((TypeError,ValueError)):
                replace(record,rapid_reload_counts=bad)
        bad=deepcopy(record.rapid_reload_counts)
        object.__setattr__(bad[0],'count',True)
        with self.assertRaises(TypeError):
            replace(record,rapid_reload_counts=bad)

    def test_count_cannot_borrow_reload_shot_aim_or_another_second_action(self):
        record=self.pc.records[0]
        for changes in (dict(actions=1),dict(started_rounds=0),dict(pc_ranged_counts=None),
                dict(pc_ranged_counts=(replace(record.pc_ranged_counts[0],reload_actions=0),)),
                dict(pc_ranged_counts=(replace(record.pc_ranged_counts[0],shots=0),)),
                dict(aim_counts=PcAimCounts((PcAimCount('pc1',1),),(PcAimCount('pc1',1),)))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate(record,**changes)
        with self.assertRaises(ValueError):
            replace(record,rapid_reload_counts=(PcRapidReloadCount('pc1',2),))

    def test_zero_counts_remain_mandatory_for_owners_without_a_granted_action(self):
        record=self.pc.records[0]
        ordinary=replace(record,executed_actions=2,
            pc_ranged_counts=(replace(record.pc_ranged_counts[0],shots=0),),
            rapid_reload_counts=(PcRapidReloadCount('pc1',0),))
        self.assertEqual(ordinary.rapid_reload_counts[0].count,0)
        without=replace(ordinary.source_scenario,party=(replace(ordinary.source_scenario.party[0],talents=()),))
        with self.assertRaises(ValueError):
            validate_rapid_reload_counts(ordinary.rapid_reload_counts,without,trials=1,actions=2,
                started_rounds=1,pc_ranged_counts=None,npc_ranged_counts=None)

    def test_generic_pc_aim_uses_awareness_without_granting_hochland_fate(self):
        source=pc_source(awareness=4)
        counts=PcAimCounts((PcAimCount('pc1',1),),(PcAimCount('pc1',0),))
        validate_aim_counts(counts,source,trials=1,actions=2,started_rounds=1,
            glorious_counts=self.pc.records[0].glorious_spend_counts)
        with self.assertRaises(ValueError):
            validate_aim_counts(replace(counts,second_action_spend_counts=(PcAimCount('pc1',1),)),
                source,trials=1,actions=3,started_rounds=1,
                glorious_counts=self.pc.records[0].glorious_spend_counts)

    def test_npc_aim_requires_its_own_awareness_and_has_no_fate_rows(self):
        source=npc_source(awareness=4)
        validate_npc_aim_counts((PcAimCount('minion1',1),),source,trials=1,actions=2,started_rounds=1)
        for bad in (None,(),(PcAimCount('pc1',1),),(PcAimCount('minion1',2),)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_npc_aim_counts(bad,source,trials=1,actions=2,started_rounds=1)
        with self.assertRaises(ValueError):
            validate_npc_aim_counts((PcAimCount('minion1',0),),npc_source(),trials=1,actions=0,started_rounds=1)

    def test_real_reload_then_aim_survives_pc_and_npc_aggregate_and_json(self):
        from tests.integration.test_talent_rapid_reload_json import command
        from tests.support.pc_pistol_scenarios import pistol_profile
        from tests.support.pc_weapon_sources import initial_weapon_items
        from towr.adapters.pc_melee_json import encode_pc_melee_simulation_result
        from towr.domain.generated_npc_models import GeneratedWeapon
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip,PcMeleePolicy
        from towr.domain.pc_battlefield_models import PcBattlefieldSpec
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated

        pc=pc_source(awareness=4)
        member=pc.party[0]
        weapon=PcMeleeWeapon.HOCHLAND_LONG_RIFLE
        member=replace(member,pc=replace(member.pc,weapon=weapon,
            ranged=replace(member.pc.ranged,initiative=4)),initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=initial_weapon_items(weapon,PcTwoHandedGrip.BOTH,initially_loaded=False))
        pc=replace(pc,party=(member,))

        npc=npc_source(awareness=4,weapon=GeneratedWeapon.HOCHLAND_LONG_RIFLE)
        components=npc.enemies[0].definition.generated_components
        components=replace(components,ranged=replace(components.ranged,initiative=4))
        member=npc.party[0]
        member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile()),
            combat_equipment=initial_weapon_items(PcMeleeWeapon.PISTOL,member.initial_weapon_hand,initially_loaded=True))
        npc=replace(npc,party=(member,),enemies=(components.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(components,'minion1'),),
            facts=replace(npc.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.SHORT))

        for source,values,actor in ((pc,[1]*4+[10]*9,'pc1'),
                (npc,[10]*6+[1]*4+[10]*4,'minion1')):
            with self.subTest(actor=actor):
                parsed=command(source)
                rng=ScriptedD10(values)
                def factory(seed):
                    return rng
                result=run_pc_melee_simulation(parsed.request,rng_factory=factory)
                rng.assert_exhausted()
                summary=summarize_pc_melee_simulation(result)
                self.assertEqual(summary.rapid_reload_counts,(PcRapidReloadCount(actor,1),))
                self.assertEqual(summary.total_action_count,3)
                if actor=='pc1':
                    self.assertEqual(summary.aim.action_counts,(PcAimCount(actor,1),))
                    self.assertEqual(summary.aim.total_second_action_spend_count,0)
                else:
                    self.assertEqual(summary.npc_aim_counts,(PcAimCount(actor,1),))
                    self.assertIsNone(summary.aim)
                encode_pc_melee_simulation_result(parsed,summary)


if __name__=='__main__':
    unittest.main()
