"""Literal Blunderbuss waves, independently owned Lady resources and replay."""
from dataclasses import replace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.oath_sources import lady
from tests.support.pc_blunderbuss_scenarios import make_pc_blunderbuss_scenario
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.pc_blunderbuss_models import PcBlunderbussTargetProof
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_melee_result_models import PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_scene_feature_models import PcZoneFeatures
from towr.domain.pc_oath_models import actor_oath
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario


class OpeningHitsThenMisses:
    def __init__(self):
        self.prefix = [1,10,10,10,10,10,10] * 2
        self.calls = 0

    def randint(self, lower, upper):
        if (lower, upper) != (1, 10) or self.calls > 500:
            raise AssertionError('expected bounded literal d10 native battle')
        index = self.calls
        self.calls += 1
        return self.prefix[index] if index < len(self.prefix) else 10


class LadyNearbyNativeTests(unittest.TestCase):
    def _run(self, *, difficult):
        original = make_pc_blunderbuss_scenario(pc_count=2, enemy_count=3, max_rounds=1,
            npc_toughness=20)
        enemies = tuple(GeneratedNpc(2,2,20,2,4,5,
            initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(), defence=4,
            talents=(lady(free=True),), oath_context=OathBattleContext('gm:'+actor,True,
                lady_prayer_before_battle_confirmed=True)).participant(actor)
            for actor in original.enemy_activation_order)
        source = replace(original, enemies=enemies,short_range_opening=None,blunderbuss_nearby=None,
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG,
                zone_features=tuple(PcZoneFeatures(index,difficult_terrain=True)
                    for index in range(-3,4)) if difficult else ()),
            party=tuple(replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT) for member in original.party),
            facts=replace(original.facts,can_leave_zone=True))
        rng = OpeningHitsThenMisses()
        result = run_pc_melee_scenario(source, rng)
        waves = tuple(step for step in result.steps if type(step.proof) is PcBlunderbussTargetProof)
        self.assertEqual(len(waves), 4)
        for step in waves[2:]:
            target = step.proof
            self.assertEqual(target.result.profile_wound.wounds_inflicted,0)
            self.assertIsNotNone(target.result.profile_wound.negated_by_rule_id)
            self.assertTrue(target.result.state.conditions.has(Condition.STAGGERED))
            row = actor_oath(step.state,target.request.target_id)
            self.assertFalse(row.lady.available)
            self.assertEqual(len(row.lady_uses),1)
        for actor in source.enemy_activation_order:
            self.assertEqual(result.state.enemy(actor).state.injury.wounds,0)
        self.assertEqual(sum(not actor_oath(result.state,actor).lady.available
            for actor in source.enemy_activation_order),2)
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,replay)
            replay = PcMeleeStep(replay,step.proof).state
        self.assertEqual(replay,result.state)
        second = waves[2]
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(second.state,second.proof)
        return result

    def test_second_real_wave_cancels_each_owned_wound_and_replays_without_refilling_resources(self):
        self._run(difficult=True)

    def test_primary_npc_give_ground_hands_pending_wave_back_to_actual_pc_shooter(self):
        from towr.domain.pc_give_ground_models import PcGiveGroundProof
        result = self._run(difficult=False)
        self.assertTrue(any(type(step.proof) is PcGiveGroundProof for step in result.steps))


if __name__ == '__main__':
    unittest.main()
