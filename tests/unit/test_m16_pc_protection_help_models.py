"""Explicit Help target/skill admission and fixed-party count projections."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_protection_help_scenarios import active_protection_help_source
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest,PcMeleeCompositionGroup,project_pc_melee_candidate,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from fractions import Fraction


class PcProtectionHelpModelTests(unittest.TestCase):
    def test_target_and_skill_are_explicit_correlated_and_exactly_typed(self):
        for target in ('first_incoming_protection',True,None):
            with self.assertRaises(TypeError):
                PcHelpPolicy('pc2',target,Skill.DEFENCE)
        for skill in (None,'defence',True,Skill.SHOOTING,Skill.ENDURANCE):
            with self.assertRaises((TypeError,ValueError)):
                PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,skill)
        with self.assertRaises(ValueError):
            PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,Skill.DEFENCE)
        with self.assertRaises(TypeError):
            PcHelpPolicy('pc2')
        for skill in (Skill.DEFENCE,Skill.ATHLETICS,Skill.MELEE):
            self.assertIs(PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,skill).protection_skill,skill)

    def test_protection_beneficiary_can_act_before_helper_but_remains_an_ordinary_ally(self):
        source = active_protection_help_source()
        changed = replace(source,pc_activation_order=('pc2','pc1'))
        self.assertEqual(changed.party[0].help_policy.beneficiary_id,'pc2')
        with self.assertRaises(ValueError):
            member = replace(source.party[0],help_policy=PcHelpPolicy('pc1',
                PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE))
            replace(source,party=(member,source.party[1]))
        with self.assertRaises(ValueError):
            replace(changed,party=(replace(changed.party[0],help_policy=PcHelpPolicy('pc2',
                PcHelpTarget.MELEE_ATTACK,None)),changed.party[1]))

    def test_cached_enum_aliases_are_refused_before_simulation_or_count_search(self):
        source = active_protection_help_source()
        for field,text in (('target','first_incoming_protection'),('protection_skill','defence')):
            forged = deepcopy(source)
            alias = Enum('ForeignString',{'VALUE':text},type=str).VALUE
            object.__setattr__(forged.party[0].help_policy,field,alias)
            self.assertEqual(forged,source)
            with self.assertRaises(TypeError):
                PcMeleeSimulationRequest(forged,42,1)

    def test_generation_keeps_full_help_choice_when_the_first_enemy_is_removed(self):
        source = active_protection_help_source()
        request = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,1,2,2,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        candidate = project_pc_melee_candidate(request,(0,1)).scenario
        self.assertEqual(candidate.enemy_activation_order,('brute1',))
        self.assertEqual(candidate.party[0].help_policy,source.party[0].help_policy)
        self.assertEqual(candidate.enemy_target_priority,source.enemy_target_priority)
        self.assertEqual(tuple(member.fate for member in candidate.party),tuple(member.fate for member in source.party))


if __name__=='__main__':
    unittest.main()
