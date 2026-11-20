"""Finite Shooting/Reload advice and prepared automatic PC Protection."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, GeneratedRangedFacts
from towr.domain.pc_generated_ranged_advice import (
    _repeater_choice, pc_close_shooting_protection, npc_repeater_bonus,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon, PcShieldLoadout,
    PcShieldHandConflictPolicy, PcShieldRecoveryPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import _pc_test, initial_pc_melee_state
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
from towr.domain.test_models import Skill, TestRequest, TestProfile


def source(*, weapon=GeneratedWeapon.REPEATER_PISTOL, rounds=3, initiative=1, dexterity=2):
    original=automatic_source(pc_count=1,enemy_count=1,rounds=rounds)
    member=replace(original.party[0],pc=replace(original.party[0].pc,
        weapon_skill=1,agility=1,melee=2,defence=2,athletics=2,toughness=20))
    firearm=weapon is not GeneratedWeapon.REPEATER_HANDBOW
    facts=GeneratedRangedFacts(1, 2,  True, True if firearm else None, True if firearm else None)
    npc=GeneratedNpc(2,3,3,2,3,3,initial_generated_weapons(weapon),light_loadout(light=False, shield=False),defence=3,ranged=facts, initiative=initiative,dexterity=dexterity)
    return replace(original,party=(member,),enemies=(npc.participant('minion1'),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),))


def conditions(state, actor, *values):
    member=state.participant(actor)
    updated=replace(member,injury=replace(member.injury,conditions=ConditionState(frozenset(values))))
    return replace(state,party=tuple(updated if m.actor_id==actor else m for m in state.party))


class ReloadHorizonTests(unittest.TestCase):
    def test_last_turn_can_choose_bonus_without_charging_future_reload(self):
        self.assertTrue(_repeater_choice(.2,.36,(1.0,),1))

    def test_expensive_reload_changes_choice_while_same_shot_values_stay_fixed(self):
        self.assertFalse(_repeater_choice(.2,.36,(1.0,),3))
        self.assertTrue(_repeater_choice(.2,.9,(0.0,0.0,0.0,1.0),3))

    def test_exact_tie_keeps_ready_ordinary_mode(self):
        for horizon in (1,2,3):
            self.assertFalse(_repeater_choice(.5,.5,(0.0,0.0,0.0,1.0),horizon))


class PreparedPcShootingProtectionTests(unittest.TestCase):
    def test_without_shield_high_melee_is_legal_but_defence_is_not(self):
        original=automatic_source(pc_count=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,
            melee=6,defence=6,athletics=2))
        state=tactical_snapshot(replace(original,party=(member,)))
        skill,test=pc_close_shooting_protection(state,'pc1','minion1','test')
        self.assertIs(skill,Skill.MELEE)
        self.assertEqual(test,_pc_test(state,'pc1','test',Skill.MELEE))

    def test_actual_shield_admits_defence_and_breaks_equal_melee_tie(self):
        original=automatic_source(pc_count=1)
        member=replace(original.party[0],shield=PcShieldLoadout(PcWeaponHand.RIGHT,
            PcShieldHandConflictPolicy.WEAPON_FIRST,PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK))
        state=tactical_snapshot(replace(original,party=(member,)))
        skill,_=pc_close_shooting_protection(state,'pc1','minion1','test')
        self.assertIs(skill,Skill.DEFENCE)

    def test_athletics_can_beat_melee(self):
        original=automatic_source(pc_count=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,
            weapon_skill=1,agility=4,melee=2,athletics=6))
        state=tactical_snapshot(replace(original,party=(member,)))
        self.assertIs(pc_close_shooting_protection(state,'pc1','minion1','test')[0],Skill.ATHLETICS)

    def test_available_fate_can_change_skill_even_without_combat_talent(self):
        original=automatic_source(pc_count=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,
            weapon_skill=2,agility=2,melee=4,athletics=5),
            fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),20,0))
        state=tactical_snapshot(replace(original,party=(member,)))
        self.assertEqual(member.talents,())
        self.assertIs(pc_close_shooting_protection(state,'pc1','minion1','test')[0],Skill.MELEE)
        unavailable=replace(member,fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,glorious_policy=None)
        plain=tactical_snapshot(replace(original,party=(unavailable,)))
        self.assertIs(pc_close_shooting_protection(plain,'pc1','minion1','test')[0],Skill.ATHLETICS)

    def test_prospective_stagger_recomputes_sword_bonus_without_changing_owner(self):
        original=automatic_source(pc_count=1)
        member=replace(original.party[0],pc=replace(original.party[0].pc,weapon=PcMeleeWeapon.SWORD),
            shield=PcShieldLoadout(PcWeaponHand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
                PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK))
        state=tactical_snapshot(replace(original,party=(member,)))
        _,fresh=pc_close_shooting_protection(state,'pc1','minion1','test')
        _,staggered=pc_close_shooting_protection(state,'pc1','minion1','test',
            conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        self.assertGreater(sum(m.amount for m in fresh.dice_modifiers),sum(m.amount for m in staggered.dice_modifiers))
        self.assertFalse(state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_advice_neither_rolls_nor_spends(self):
        state=tactical_snapshot(automatic_source(pc_count=1))
        old=state.participant('pc1').fate
        with patch('towr.rules.test_resolution.roll_test_initial',side_effect=AssertionError('no RNG')):
            pc_close_shooting_protection(state,'pc1','minion1','test')
        self.assertEqual(state.participant('pc1').fate,old)


class GeneratedNpcShootingModeTests(unittest.TestCase):
    def choose(self,scenario):
        state=tactical_snapshot(scenario)
        enemy=state.enemy('minion1')
        attacker=TestRequest('test',enemy.definition.attacks[0].test_profile)
        skill,defender=pc_close_shooting_protection(state,'pc1','minion1','defender')
        return npc_repeater_bonus(state,'minion1',attacker,defender,'pc1',defender_skill=skill)

    def test_real_ranged_facts_choose_both_modes_as_remaining_horizon_changes(self):
        self.assertFalse(self.choose(source(rounds=3)))
        self.assertTrue(self.choose(source(rounds=1)))

    def test_handbow_uses_same_finite_owner_and_pistol_has_no_optional_mode(self):
        self.assertTrue(self.choose(source(weapon=GeneratedWeapon.REPEATER_HANDBOW,rounds=1)))
        self.assertFalse(self.choose(source(weapon=GeneratedWeapon.PISTOL,rounds=1)))

    def test_drained_does_not_select_bonus(self):
        state=tactical_snapshot(source(rounds=1))
        enemy=state.enemy('minion1')
        updated=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset((Condition.DRAINED,))))))
        prepared=replace(state,enemies=(updated,))
        self.assertFalse(npc_repeater_bonus(prepared,'minion1',
            TestRequest('test',updated.definition.attacks[0].test_profile),None,'pc1'))

    def test_incoming_advice_uses_shooting_prone_penalty_without_melee_outnumbering(self):
        from towr.domain.pc_tactical_models import select_pc_tactic,_impact_value
        original=source(weapon=GeneratedWeapon.PISTOL,rounds=1)
        # An ally is the current NPC target; first PC can consider Recover
        # on that ally. This queries both actual Prone and removed-Prone facts.
        base=automatic_source(pc_count=2,enemy_count=1,rounds=1)
        party=(base.party[0],replace(base.party[1],pc=replace(base.party[1].pc,
            weapon_skill=1,agility=1,melee=2,defence=2,athletics=2,toughness=20)))
        original=replace(original,party=party,pc_activation_order=('pc1','pc2'),
            enemy_target_priority=('pc2','pc1'))
        state=conditions(tactical_snapshot(original),'pc2',Condition.PRONE)
        with patch('towr.domain.pc_tactical_models._impact_value',wraps=_impact_value) as impact:
            select_pc_tactic(state,'pc1')
        incoming=[call.args for call in impact.call_args_list if call.args[2]==5]
        self.assertTrue(incoming)
        distributions={tuple(round(p,8) for p in call[0]) for call in incoming}
        self.assertIn((.9,.1),distributions)  # BS1 - 1d -> lone minimum die succeeds only on1.
        self.assertIn((.8,.2),distributions)

    def test_incoming_advice_does_not_invent_a_shot_during_real_unloaded_cycle(self):
        from towr.engine.pc_melee_runner import run_pc_melee_scenario
        from towr.domain.pc_melee_result_models import PcAttackProof
        from towr.domain.pc_tactical_models import select_pc_tactic,_impact_value
        class Tens:
            def randint(self,a,b):
                assert (a,b)==(1,10)
                return 10
        result=run_pc_melee_scenario(source(weapon=GeneratedWeapon.PISTOL,rounds=1),Tens())
        shot=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.npc_ranged_shot is not None)
        self.assertFalse(pc_npc_ranged_weapon(shot.state,'minion1').loaded)
        with patch('towr.domain.pc_tactical_models._impact_value',wraps=_impact_value) as impact:
            select_pc_tactic(shot.state,'pc1')
        self.assertFalse([call for call in impact.call_args_list if call.args[2]==5])


if __name__=='__main__':
    unittest.main()
