"""C20 never funds multi-target harm by truncating ordinary weapon physics."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.magic_weapon_battles import magic_battle
from tests.support.oath_sources import with_native_outcome_owner
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSpendKind
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_oath_models import actor_oath
from towr.domain.pc_weapon_area_models import PcWeaponHazardProof
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def source():
    scenario = with_native_outcome_owner(magic_battle('staff',count=3,rounds=1,distance='short'))
    member = scenario.party[0]
    return replace(scenario,
        party=(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.BLASTING_CHARGE,
            ballistic_skill=1, throwing=1),
            combat_equipment=(replace(member.combat_equipment[0],weapon=PcMeleeWeapon.BLASTING_CHARGE),)),),
        short_range_opening=None,
        battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))


class HonourAreaScopeTests(unittest.TestCase):
    def test_failed_blast_uses_glorious_without_a_paid_multi_wound_override(self):
        scenario = source()
        result = run_pc_melee_scenario(scenario, SequenceRandom([10]*400))
        strike = next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id == scenario.party[0].actor_id)
        self.assertEqual(strike.execution.resolution.attack.attacker_test.successes,0)
        self.assertIsNone(strike.execution.resolution.attack.attacker_test.honour_bound)
        self.assertEqual(len(actor_oath(result.state,scenario.party[0].actor_id).honour_uses),1)
        self.assertFalse(any(spend.kind is FateSpendKind.HONOUR_BOUND_UNMITIGATED_SUCCESS
            for spend in result.state.party[0].fate.spends))
        # A missed Blast still has its ordinary, frozen exposed targets. The
        # exceptional outcome must neither remove those Hazards nor fund them.
        self.assertTrue(any(type(step.proof) is PcWeaponHazardProof for step in result.steps))

    def test_ordinary_success_keeps_all_actual_area_targets_and_wounds_without_fate(self):
        scenario = source()
        result = run_pc_melee_scenario(scenario,SequenceRandom([1]+[10]*400))
        hazards = tuple(step.proof for step in result.steps if type(step.proof) is PcWeaponHazardProof)
        self.assertEqual(len(hazards),3)
        self.assertEqual(tuple(enemy.state.injury.wounds for enemy in result.state.enemies),(1,1,1))
        self.assertFalse(result.state.party[0].fate.spends)
        self.assertFalse(result.state.party[0].fate.burns)
        self.assertEqual(result.state.party[0].fate.rating,scenario.party[0].fate.rating)
        replay = initial_pc_melee_state(scenario)
        for step in result.steps:
            self.assertEqual(step.source,replay)
            replay = PcMeleeStep(replay,step.proof).state
        self.assertEqual(replay,result.state)


if __name__ == '__main__':
    unittest.main()
