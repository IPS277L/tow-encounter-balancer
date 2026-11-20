"""Oath Attack restrictions filter optional Bash and mounted Abilities early."""
from dataclasses import replace
from itertools import chain, repeat
import unittest

from tests.helpers import SequenceRandom
from tests.support.oath_sources import context, honour
from tests.unit.test_bash_attack_execution import pc_source, npc_source
from towr.domain.pc_bash_advice import bash_follow_up_value
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_demigryph_models import PcDemigryphIntentProof, PcDemigryphStrikeProof
from towr.domain.pc_immediate_attack_models import PcBashDecisionProof, PcImmediateStrikeProof
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeStep, initial_pc_melee_state, _pc_test,
)
from towr.domain.pc_mount_attack_models import (
    available_pc_attack_mount, pc_best_mount_attack, prepare_pc_mounted_attack,
)
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def forbids_melee(source,actor,*,mount=None):
    gm=replace(context(),forbidden_attack_skills=(Skill.MELEE,),
        honour_bound_used_this_session=True)
    rider=dict(mount=mount,rider_kind=RiderKind.HUMAN) if mount is CombatMount.DEMIGRYPH else dict(mount=mount)
    changes=dict(facts=replace(source.facts,unmounted=mount is None))
    if mount is not None:
        changes.update(battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG),
            facts=replace(source.facts,unmounted=False,can_leave_zone=True),
            party=tuple(replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT) for member in source.party))
    if actor in source.pc_activation_order:
        member=source.participant(actor)
        member=replace(member,talents=(*member.talents,honour()),oath_context=gm,**rider)
        if mount is not None:
            member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        changes['party']=tuple(member if item.actor_id==actor else item for item in source.party)
    else:
        components=source.enemies[0].definition.generated_components
        components=replace(components,talents=(*components.talents,honour()),oath_context=gm,**rider)
        changes['enemies']=(components.participant(actor),)
    return replace(source,**changes)


class OathAttackDependenciesTests(unittest.TestCase):
    def execute(self,source,values):
        result=run_pc_melee_scenario(source,SequenceRandom(chain(values,repeat(10))))
        self.assertIsNone(result.unsupported)
        state=initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,state)
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)
        return result

    def assert_declined_bash(self,result,actor):
        decision,=tuple(step.proof for step in result.steps if type(step.proof) is PcBashDecisionProof)
        self.assertEqual(decision.grant.actor_id,actor)
        self.assertIsNone(decision.selection)
        parent=result.steps[decision.source_index].proof
        self.assertIs(parent.weapon_intent.attack_skill,Skill.BRAWN)
        self.assertTrue(parent.execution.resolution.stagger)
        self.assertFalse(any(type(step.proof) is PcImmediateStrikeProof for step in result.steps))

    def test_pc_real_brawn_settles_bash_as_declined_without_forbidden_melee(self):
        source=forbids_melee(pc_source(),'pc')
        state=initial_pc_melee_state(source)
        self.assertEqual(bash_follow_up_value(state,'pc','minion1',(0.,1.),(1.,)),0.)
        # The prohibition concerns Attacks; Melee remains a legitimate Test
        # for Protection or Help and keeps the real source ratings.
        defence=_pc_test(state,'pc','legal:protection',Skill.MELEE,oppose_attack=True,
            incoming_attack_skill=Skill.SHOOTING)
        self.assertEqual(defence.profile,source.party[0].pc.melee_profile)
        result=self.execute(source,[1]*5+[10]*2)
        self.assert_declined_bash(result,'pc')

    def test_generated_npc_real_brawn_declines_optional_melee(self):
        source=forbids_melee(npc_source(),'minion1')
        result=self.execute(source,[1,10,10]+[1]*5)
        self.assert_declined_bash(result,'minion1')

    def test_pc_demigryph_ability_and_optional_claws_are_not_selected(self):
        source=forbids_melee(pc_source(),'pc',mount=CombatMount.DEMIGRYPH)
        self.assert_mount_banned(source,'pc')
        result=self.execute(source,[1]*5+[10]*2)
        self.assert_declined_bash(result,'pc')
        self.assert_no_mount_attacks(result,'pc')

    def test_generated_npc_keeps_legal_brawn_instead_of_forbidden_mount_melee(self):
        source=forbids_melee(npc_source(),'minion1',mount=CombatMount.DEMIGRYPH)
        self.assert_mount_banned(source,'minion1')
        result=self.execute(source,[1,10,10]+[1]*5)
        self.assert_declined_bash(result,'minion1')
        self.assert_no_mount_attacks(result,'minion1')

    def assert_mount_banned(self,source,actor):
        state=initial_pc_melee_state(source)
        self.assertIsNone(available_pc_attack_mount(state,actor))
        self.assertEqual(pc_best_mount_attack(state,actor),(0.,None))
        target=source.enemy_activation_order[0] if actor in source.pc_activation_order else source.pc_activation_order[0]
        with self.assertRaisesRegex(ValueError,'GM-confirmed oath'):
            prepare_pc_mounted_attack(state,actor,target,'illegal:mount')

    def assert_no_mount_attacks(self,result,actor):
        self.assertFalse(any(type(step.proof) in (PcDemigryphIntentProof,PcDemigryphStrikeProof)
            for step in result.steps))
        attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==actor]
        self.assertTrue(attacks)
        self.assertTrue(all(proof.mount_attack is None and proof.weapon_intent.attack_skill is Skill.BRAWN
            for proof in attacks))


if __name__=='__main__':unittest.main()
