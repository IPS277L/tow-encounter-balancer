"""Decision-local reuse retains complete forecast identity and advice inputs."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass,replace
import gc
import unittest
from unittest.mock import Mock,patch
import weakref

from tests.support.pc_tactics_fixtures import automatic_source,tactical_snapshot
from tests.unit.test_pc_ranged_advice import shooting_help_source
from towr.domain.pc_melee_models import PcMeleeWeapon,PcRepeaterBonusPolicy
from towr.domain.pc_tactical_models import _IncomingRiskMemo,select_pc_tactic
from towr.domain.turn_models import CombatActionKind


@dataclass(frozen=True)
class Forecast:
    label: str


class DecisionLocalRiskReuseTests(unittest.TestCase):
    def test_identical_forecast_and_arguments_reuse_even_zero_result(self):
        calculate=Mock(return_value=0.0)
        memo=_IncomingRiskMemo(calculate)
        forecast=Forecast('current')
        self.assertEqual(memo(forecast,'pc1'),0.0)
        self.assertEqual(memo(forecast,'pc1'),0.0)
        calculate.assert_called_once_with(forecast,'pc1',0,False,False,None,False)

    def test_all_advice_inputs_and_distinct_equal_forecasts_are_separate(self):
        calculate=Mock(return_value=0.25)
        memo=_IncomingRiskMemo(calculate)
        forecast=Forecast('current')
        changes=({},dict(protection_bonus=1),dict(prone_removed=True),
            dict(stagger_removed=True),dict(enhancement='toughness'),dict(stagger_added=True))
        for kwargs in changes:
            memo(forecast,'pc1',**kwargs)
            memo(forecast,'pc1',**kwargs)
        memo(forecast,'pc2')
        equal_forecast=Forecast('current')
        self.assertEqual(equal_forecast,forecast)
        self.assertIsNot(equal_forecast,forecast)
        memo(equal_forecast,'pc1')
        self.assertEqual(calculate.call_count,8)

    def test_forecast_reference_lives_only_as_long_as_its_decision_memo(self):
        memo=_IncomingRiskMemo(lambda *args:0.0)
        forecast=Forecast('temporary prepared view')
        ref=weakref.ref(forecast)
        memo(forecast,'pc1')
        del forecast
        gc.collect()
        self.assertIsNotNone(ref())
        del memo
        gc.collect()
        self.assertIsNone(ref())

    def test_failed_evaluation_is_not_cached_as_a_success(self):
        calculate=Mock(side_effect=(ValueError('source guard'),0.5))
        memo=_IncomingRiskMemo(calculate)
        forecast=Forecast('current')
        with self.assertRaisesRegex(ValueError,'source guard'):
            memo(forecast,'pc1')
        self.assertEqual(memo(forecast,'pc1'),0.5)
        self.assertEqual(calculate.call_count,2)

    def test_each_selector_call_has_an_independent_memo_and_preserves_input(self):
        state=tactical_snapshot(automatic_source())
        before=deepcopy(state)
        with patch('towr.domain.pc_tactical_models._IncomingRiskMemo',wraps=_IncomingRiskMemo) as memo,\
                patch('random.Random.randint',side_effect=AssertionError('advisor consumed RNG')):
            first=select_pc_tactic(state)
            second=select_pc_tactic(state)
        self.assertEqual(first,second)
        self.assertEqual(state,before)
        self.assertEqual(memo.call_count,2)

    def test_ranged_help_reuses_immediate_attack_values_but_keeps_bonus_modes_separate(self):
        from towr.domain.pc_ranged_advice import pc_attack_value
        source=shooting_help_source()
        beneficiary=source.party[1]
        weapon=PcMeleeWeapon.REPEATER_HANDBOW
        beneficiary=replace(beneficiary,
            pc=replace(beneficiary.pc,weapon=weapon,ranged=replace(beneficiary.pc.ranged,
                has_blackpowder_lore=None,has_blackpowder_kit=None,
                repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC)),
            combat_equipment=(replace(beneficiary.combat_equipment[0],weapon=weapon),))
        state=tactical_snapshot(replace(source,party=(source.party[0],beneficiary)),'pc1')
        observations=[]
        def observe(view,actor,**options):
            if not options.get('allow_empty',False):
                observations.append((actor,options['extra'],options['enhancement'],options['wild'],
                    view.participant(actor).weapon_inventory.active_item_id,options['bonus']))
            return pc_attack_value(view,actor,**options)
        with patch('towr.domain.pc_ranged_advice.pc_attack_value',side_effect=observe):
            choice=select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.HELP)
        self.assertTrue(any(key[1]>0 for key in observations))
        self.assertEqual({key[-1] for key in observations if key[0]=='pc2'},{False,True})
        self.assertTrue(all(count==1 for count in Counter(observations).values()))


if __name__=='__main__':
    unittest.main()
