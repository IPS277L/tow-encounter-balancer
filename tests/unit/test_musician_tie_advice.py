"""Finite Attack advice over explicit views and actual K1 music receipts.

The numeric encounter snapshots do not claim a native musician journal. Each
added music receipt is a real paid Leadership action; these tests inspect its
target-specific comparison effect without rolling hypothetical Attacks.
"""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from tests.unit.test_bash_attack_execution import pc_source
from tests.unit.test_battlefield_musician_resolution import action_request, listener
from tests.unit.test_generated_ranged_advice import source as generated_ranged_source
from tests.unit.test_pc_ranged_advice import ranged_source
from tests.unit.test_pc_throwing_inventory import prepared as throwing_view
from tests.unit.test_pc_weighted_net import source as net_source
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_side
from towr.domain.pc_bash_advice import bash_follow_up_value
from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus, pc_close_shooting_protection
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import _pc_test, initial_pc_melee_state
from towr.domain.pc_musician_effect_models import (
    PcMusicianActionProof, musician_defends_ties, pc_attack_success_wins,
)
from towr.domain.pc_ranged_advice import (
    _distribution_request_value, initial_fate_budget, pc_attack_value,
)
from towr.domain.pc_tactical_models import _impact_value, select_pc_tactic, stagger_attack_value
from towr.domain.pc_weapon_area_models import throwing_special_value
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import CombatSide
from towr.domain.weapon_catalog import WeaponKind
from towr.rules.battlefield_musician_resolution import execute_battlefield_musician_action


def music_proof(target, side=CombatSide.OPPOSITION):
    request=action_request(side=side,listeners=(listener(target,side=side),))
    rng=ScriptedD10([1,10])
    result=execute_battlefield_musician_action(request,rng)
    rng.assert_exhausted()
    return PcMusicianActionProof(result)


def with_music(state,target):
    return replace(state,history=(*state.history,music_proof(target,pc_actor_side(state,target))))


def throwing_tie_view(kind):
    return tactical_snapshot(net_source()) if kind is WeaponKind.WEIGHTED_NET else throwing_view(kind)


class MusicianTieComparisonTests(unittest.TestCase):
    def test_positive_tie_is_a_miss_but_strict_win_and_unopposed_success_are_preserved(self):
        tie=(0.,1.)
        self.assertEqual(_impact_value(tie,tie,1,20,1,False),.5)
        self.assertEqual(_impact_value(tie,tie,1,20,1,False,defender_wins_ties=True),0.)
        self.assertEqual(stagger_attack_value(tie,tie,False),.5)
        self.assertEqual(stagger_attack_value(tie,tie,False,defender_wins_ties=True),0.)
        for attack,defence in (((0.,0.,1.),tie),(tie,(1.,))):
            with self.subTest(attack=attack,defence=defence):
                self.assertEqual(_impact_value(attack,defence,1,20,1,False),
                    _impact_value(attack,defence,1,20,1,False,defender_wins_ties=True))
                self.assertEqual(stagger_attack_value(attack,defence,False),
                    stagger_attack_value(attack,defence,False,defender_wins_ties=True))

    def test_defensive_stance_values_the_new_successful_defence_but_never_double_zero(self):
        tie=(0.,1.)
        self.assertEqual(_impact_value(tie,tie,1,20,1,True,defensive_stance=True),1.)
        self.assertEqual(_impact_value(tie,tie,1,20,1,True,defensive_stance=True,
            defender_wins_ties=True),-.5)
        for protected in (False,True):
            with self.subTest(protected=protected):
                self.assertEqual(_impact_value((1.,),(1.,),1,20,1,True,
                    defensive_stance=True,defender_wins_ties=protected),0.)
                self.assertEqual(stagger_attack_value((1.,),(1.,),True,
                    defender_wins_ties=protected),0.)
                self.assertEqual(_impact_value((1.,),(1.,),100,1,1,False,
                    defenceless=True,defender_wins_ties=protected),0.)
                self.assertEqual(_impact_value(tie,(1.,),100,1,1,False,
                    defenceless=True,defender_wins_ties=protected),1.)

    def test_each_literal_comparison_agrees_with_runtime_and_keeps_the_actual_target(self):
        state=SimpleNamespace(history=(music_proof('protected'),))
        for target in ('protected','ordinary'):
            for attack in range(4):
                for defence in range(4):
                    with self.subTest(target=target,attack=attack,defence=defence):
                        wins=pc_attack_success_wins(state,'attacker',target,attack,defence)
                        value=_impact_value((0.,)*attack+(1.,),(0.,)*defence+(1.,),
                            100,1,1,False,defender_wins_ties=musician_defends_ties(state,target))
                        self.assertEqual(value,float(wins))


class MusicianPreparedAdviceTests(unittest.TestCase):
    def test_melee_shooting_brawn_and_unarmed_read_the_real_recipient(self):
        ordinary=tactical_snapshot(automatic_source(pc_count=1))
        unarmed_source=pc_source(melee=False)
        unarmed=unarmed_source.party[0]
        unarmed=replace(unarmed,pc=replace(unarmed.pc,weapon=PcMeleeWeapon.UNARMED,brawn=4),
            initial_weapon_hand=None,combat_equipment=())
        contexts=(
            ('melee',ordinary,'pc1'),
            ('shooting',tactical_snapshot(ranged_source(rounds=1)),'pc1'),
            ('brawn',initial_pc_melee_state(pc_source()),'pc'),
            ('unarmed',tactical_snapshot(replace(unarmed_source,party=(unarmed,)),actor='pc'),'pc'),
            ('throwing',throwing_view(WeaponKind.THROWING_SPEAR),'pc'),
        )
        for name,state,actor in contexts:
            with self.subTest(mode=name):
                before=pc_attack_value(state,actor)
                after=pc_attack_value(with_music(state,'minion1'),actor)
                self.assertEqual(before[1],after[1])
                self.assertGreater(before[0],after[0])
                self.assertEqual(state.history,())

    def test_tactical_melee_target_selection_does_not_apply_one_ally_buff_to_every_enemy(self):
        state=tactical_snapshot(automatic_source(pc_count=1,enemy_count=2))
        self.assertEqual(select_pc_tactic(state).target_id,'minion1')
        self.assertEqual(select_pc_tactic(with_music(state,'minion1')).target_id,'minion2')

    def test_defensive_incoming_risk_forwards_only_the_protected_pc_source(self):
        state=tactical_snapshot(automatic_source(pc_count=1))
        member=state.party[0]
        state=replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.STAGGERED))),))
        protected=with_music(state,'pc1')
        with patch('towr.domain.pc_tactical_models._impact_value',wraps=_impact_value) as score:
            select_pc_tactic(protected)
        flags=tuple(call.kwargs.get('defender_wins_ties',False) for call in score.call_args_list)
        self.assertIn(True,flags)
        self.assertIn(False,flags)
        self.assertFalse(musician_defends_ties(protected,'minion1'))

    def test_branch_values_keep_fate_budget_and_respect_shooting_and_net_ties(self):
        for state,actor,skill in (
            (tactical_snapshot(ranged_source(rounds=1)),'pc1',Skill.SHOOTING),
            (throwing_tie_view(WeaponKind.WEIGHTED_NET),'pc1',Skill.THROWING),
        ):
            with self.subTest(skill=skill):
                request=_pc_test(state,actor,'advice:branch',skill)
                budget=initial_fate_budget(state,actor)
                before=_distribution_request_value(state,actor,request,skill,'minion1',budget=budget)
                after=_distribution_request_value(with_music(state,'minion1'),actor,request,skill,'minion1',budget=budget)
                self.assertEqual(tuple(row[1:] for row in before),tuple(row[1:] for row in after))
                self.assertGreater(sum(value*chance for value,_,chance in before),
                    sum(value*chance for value,_,chance in after))

    def test_bash_needs_a_winning_parent_and_its_own_winning_continuation(self):
        state=initial_pc_melee_state(pc_source())
        protected=with_music(state,'minion1')
        tie=(0.,1.)
        self.assertGreater(bash_follow_up_value(state,'pc','minion1',tie,tie),0.)
        self.assertEqual(bash_follow_up_value(protected,'pc','minion1',tie,tie),0.)
        before=bash_follow_up_value(state,'pc','minion1',(0.,0.,1.),tie)
        after=bash_follow_up_value(protected,'pc','minion1',(0.,0.,1.),tie)
        self.assertGreater(before,after)
        self.assertGreater(after,0.)

    def test_rock_net_oil_and_blast_tie_branches_use_the_actual_primary_target(self):
        for kind in (WeaponKind.ROCK,WeaponKind.WEIGHTED_NET,WeaponKind.OIL_FLASK,WeaponKind.BLASTING_CHARGE):
            state=throwing_tie_view(kind)
            actor='pc1' if kind is WeaponKind.WEIGHTED_NET else 'pc'
            protected=with_music(state,'minion1')
            with self.subTest(kind=kind):
                before=throwing_special_value(state,actor,'minion1',kind,(0.,1.),(0.,1.))
                after=throwing_special_value(protected,actor,'minion1',kind,(0.,1.),(0.,1.))
                if kind in (WeaponKind.ROCK,WeaponKind.WEIGHTED_NET):
                    self.assertGreater(before,0.)
                    self.assertEqual(after,0.)
                else:
                    self.assertNotEqual(before,after)

    def test_generated_repeater_current_and_future_shots_forward_the_pc_recipient(self):
        state=tactical_snapshot(generated_ranged_source(rounds=1))
        protected=with_music(state,'pc1')
        enemy=state.enemy('minion1')
        attacker=TestRequest('advice:generated-shot',enemy.definition.attacks[0].test_profile)
        skill,defender=pc_close_shooting_protection(state,'pc1','minion1','advice:protection')
        with patch('towr.domain.pc_tactical_models._impact_value',wraps=_impact_value) as score:
            npc_repeater_bonus(protected,'minion1',attacker,defender,'pc1',defender_skill=skill)
        self.assertEqual(len(score.call_args_list),4)
        self.assertTrue(all(call.kwargs['defender_wins_ties'] for call in score.call_args_list))


if __name__=='__main__':unittest.main()
