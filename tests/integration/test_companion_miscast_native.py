"""Public mounted Wizard: actual Miscast snapshot precedes a new body."""
from dataclasses import replace
from unittest import TestCase, main

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_magic_models import PcMiscastRollProof
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_mount_retention_models import PcMountRetentionProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class CompanionMiscastNativeTests(TestCase):
    def test_wind_dismounts_actual_rider_without_retroactively_targeting_new_body(self):
        source=magic_scenario(reason=3,willpower=10,enemies=1)
        member=source.party[0]
        member=replace(member,mount=CombatMount.HORSE,pc=replace(member.pc,agility=4),
            talents=(*member.talents,paid_talent(TalentId.BACK_IN_THE_SADDLE)))
        source=replace(source,party=(member,),battlefield=PcBattlefieldSpec(R.CLOSE,R.LONG),
            facts=replace(source.facts,unmounted=False,can_leave_zone=True))
        # Three locked9; casting the completed spell adds one Miscast die.
        rng=ScriptedD10([9]*3+[5,5,5,6])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        rolled,=tuple(step for step in result.steps if type(step.proof) is PcMiscastRollProof)
        self.assertEqual(tuple(task.target_id for task in rolled.state.magic_pending.tasks),('pc1','minion1'))
        retention,=tuple(step for step in result.steps if type(step.proof) is PcMountRetentionProof)
        self.assertTrue(retention.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(retention.state.companions[0].snapshot.state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(retention.state.companions[0].snapshot.state.injury.wounds,0)
        state=initial_pc_melee_state(source)
        for step in result.steps: state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)


if __name__=='__main__': main()
