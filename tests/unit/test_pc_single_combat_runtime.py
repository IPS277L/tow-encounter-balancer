"""Single-combat queries on actual native Attack/Help prefixes (ADR-0140D)."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import magic_battle,run_native
from tests.support.pc_magic_scenarios import magic_scenario
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_magic_models import PcCastingProof
from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget,PcMeleePolicy
from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof,initial_pc_melee_state
from towr.domain.pc_single_combat_models import PcSingleCombatPair,single_combat_active
from towr.domain.test_models import Skill
from towr.domain.weapon_quality_preparation import JUSTICE_SINGLE_COMBAT_RULE_ID


class PcSingleCombatRuntimeTests(unittest.TestCase):
    def test_a_confirmed_three_actor_pair_is_undirected_until_real_external_attack(self):
        source=magic_battle('sword_of_justice',npc_magic=True,count=2)
        actor=source.enemy_activation_order[0]
        source=replace(source,single_combat_pairs=(PcSingleCombatPair(actor,'pc'),))
        initial=initial_pc_melee_state(source)
        self.assertTrue(single_combat_active(initial,actor,'pc'))
        self.assertTrue(single_combat_active(initial,'pc',actor))
        result=run_native(self,source)
        own=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==actor)
        self.assertTrue(any(mod.rule_id==JUSTICE_SINGLE_COMBAT_RULE_ID
            for mod in own.proof.request.kernel_request.attack.attacker_test.quality_modifiers))
        outsider=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.enemy_activation_order[1])
        self.assertFalse(single_combat_active(outsider.state,actor,'pc'))

    def test_an_interrupted_explicit_pair_does_not_revive_when_only_two_survive(self):
        source=magic_battle('sword_of_justice',npc_magic=True,count=2,npc_toughness=1)
        actor,outsider=source.enemy_activation_order
        member=replace(source.party[0],target_priority=(outsider,actor),
            defeat_decisions=tuple(reversed(source.party[0].defeat_decisions)))
        source=replace(source,party=(member,),single_combat_pairs=(PcSingleCombatPair(actor,'pc'),))
        result=run_native(self,source)
        self.assertTrue(result.state.enemy(outsider).state.injury.defeated)
        self.assertFalse(result.state.enemy(actor).state.injury.defeated)
        self.assertEqual(len(result.state.live_party)+len(result.state.live_enemies),2)
        self.assertFalse(single_combat_active(result.state,actor,'pc'))

    def test_real_help_to_a_duel_member_permanently_interrupts_the_pair(self):
        source=magic_battle('sword_of_justice',players=2)
        helper,member=source.party
        member=replace(member,policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
        helper=replace(helper,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy(member.actor_id,PcHelpTarget.ATTACK,Skill.MELEE))
        enemy=source.enemy_activation_order[0]
        source=replace(source,party=(helper,member),battlefield=None,
            facts=replace(source.facts,all_opponents_close=True,can_leave_zone=False),
            single_combat_pairs=(PcSingleCombatPair(member.actor_id,enemy),))
        self.assertTrue(single_combat_active(initial_pc_melee_state(source),member.actor_id,enemy))
        result=run_native(self,source)
        help_step=next(step for step in result.steps if type(step.proof) is PcHelpProof)
        self.assertFalse(single_combat_active(help_step.state,member.actor_id,enemy))
        member_step=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==member.actor_id)
        self.assertFalse(single_combat_active(member_step.state,member.actor_id,enemy))

    def test_an_offensive_spell_from_a_real_outsider_interrupts_the_pair(self):
        source=magic_scenario(pc_count=2,enemies=1,reason=4,willpower=5,
            spells=(PcSpellId.LIGHTNING_BLAST,))
        mage,member=source.party
        enemy=source.enemy_activation_order[0]
        source=replace(source,single_combat_pairs=(PcSingleCombatPair(member.actor_id,enemy),))
        self.assertTrue(single_combat_active(initial_pc_melee_state(source),member.actor_id,enemy))
        result=run_native(self,source)
        casting=next(step for step in result.steps if type(step.proof) is PcCastingProof
            and step.proof.actor_id==mage.actor_id and step.proof.targets is not None)
        self.assertFalse(single_combat_active(casting.state,member.actor_id,enemy))


if __name__=='__main__':
    unittest.main()
