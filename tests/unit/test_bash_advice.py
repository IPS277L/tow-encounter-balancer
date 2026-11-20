"""Deterministic bounded Bash advice uses actual equipment without spending it."""
from dataclasses import replace
import unittest

from tests.unit.test_bash_attack_execution import pc_source
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_bash_advice import bash_follow_up_value
from towr.domain.pc_ranged_advice import pc_attack_value
from towr.domain.condition_models import Condition


class BashAdviceTests(unittest.TestCase):
    def test_real_melee_follow_up_increases_brawn_value_without_changing_source(self):
        source=pc_source()
        state=initial_pc_melee_state(source)
        without=initial_pc_melee_state(replace(source,party=(replace(source.party[0],talents=()),)))
        value=pc_attack_value(state,'pc')
        baseline=pc_attack_value(without,'pc')
        self.assertEqual(value[1],baseline[1])
        self.assertGreater(value[0],baseline[0])
        self.assertEqual(state,initial_pc_melee_state(source))
        self.assertEqual(state.history,())

    def test_no_available_melee_or_no_new_stagger_gives_no_imaginary_attack(self):
        no_weapon=initial_pc_melee_state(pc_source(melee=False))
        self.assertEqual(bash_follow_up_value(no_weapon,'pc','minion1',(0.,1.),(1.,)),0.)
        source=pc_source()
        enemy=source.enemies[0]
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED))))
        # Prepared tactical boundary, not an invented initial battle/journal.
        state=replace(initial_pc_melee_state(source),enemies=(enemy,))
        self.assertEqual(bash_follow_up_value(state,'pc','minion1',(0.,1.),(1.,)),0.)

    def test_a_parent_damage_wound_is_not_valued_as_first_stagger(self):
        state=initial_pc_melee_state(pc_source())
        self.assertEqual(bash_follow_up_value(state,'pc','minion1',(0.,1.),(1.,),
            parent_damage=(100,1,20)),0.)
        self.assertGreater(bash_follow_up_value(state,'pc','minion1',(0.,1.),(1.,),
            parent_damage=(1,1,20)),0.)


if __name__=='__main__':unittest.main()
