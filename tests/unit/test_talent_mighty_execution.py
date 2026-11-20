"""Mighty Blow through real actor preparation and native attack/Help receipts.

Only the explicitly named Condition-boundary test prepares a local snapshot;
it does not claim a preceding native history. The Help test executes a genuine
legal prefix with canonical clock/action receipts, without claiming battle end.
"""
from dataclasses import replace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario,make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_help_models import (
    build_pc_help_action,pc_help_beneficiary_weapon,pc_help_weapon_use,pc_selected_help_policy,
)
from towr.domain.pc_melee_models import (
    PcHelpPolicy,PcHelpTarget,PcMeleePolicy,PcMeleeWeapon,PcTwoHandedGrip,PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcFateDecline,PcHelpProof,PcMeleeStep,_pc_test,initial_pc_melee_state,
    pc_melee_action_declaration,pc_melee_action_id,
)
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import DiceModifier,Skill
from towr.domain.turn_models import (
    ActionSlotGrant,CombatActionKind,CombatActionSlotRequest,CombatTurnStartRequest,
)
from towr.domain.weapon_effect_preparation import (
    FLAIL_STAGGERED_RULE_ID,GREATAXE_MELEE_RULE_ID,MORNING_STAR_STAGGERED_RULE_ID,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario
from towr.rules.help_resolution import execute_help_action
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot,start_combat_turn


MIGHTY=(paid_talent(TalentId.MIGHTY_BLOW),)


def member_with_weapon(member,weapon,*,mighty=True):
    hand=PcTwoHandedGrip.BOTH if pc_weapon_requires_two_hands(weapon) else PcWeaponHand.LEFT
    return replace(member,pc=replace(member.pc,weapon=weapon,weapon_skill=3,strength=4,
        toughness=20,agility=1,athletics=2),initial_weapon_hand=hand,
        combat_equipment=initial_weapon_items(weapon,hand),talents=MIGHTY if mighty else ())


def source(*,pc_weapon=PcMeleeWeapon.GREATAXE,pc_mighty=True,npc_mighty=True):
    initial=make_pc_melee_scenario(weapon=pc_weapon,enemy_count=1,max_rounds=1)
    member=member_with_weapon(initial.party[0],pc_weapon,mighty=pc_mighty)
    npc=GeneratedNpc(3,4,20,1,4,2,initial_generated_weapons(GeneratedWeapon.FLAIL),
        ArmourLoadout(),defence=4,talents=MIGHTY if npc_mighty else ())
    return replace(initial,party=(member,),enemies=(npc.participant('minion1'),))


def append_step(state,proof,steps):
    step=PcMeleeStep(state,proof)
    steps.append(step)
    return apply_pc_melee_step(state,step)


class MightyExecutionTests(unittest.TestCase):
    def test_real_pc_greataxe_and_newly_staggered_npc_flail_use_the_actual_talent_source(self):
        scenario=source()
        # First HIT actually Staggers the high-Resilience NPC. Its immediately
        # following Flail Attack must use that real new Condition, not a fixture.
        rng=ScriptedD10([1,1,1]+[10]*9)
        result=run_pc_melee_scenario(scenario,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        attacks=[step for step in result.steps if type(step.proof) is PcAttackProof]
        self.assertEqual(len(attacks),2)
        pc,npc=attacks
        self.assertEqual((pc.proof.request.actor_id,npc.proof.request.actor_id),('pc','minion1'))
        self.assertEqual(pc.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertNotIn(GREATAXE_MELEE_RULE_ID,
            [mod.rule_id for mod in pc.proof.request.kernel_request.attack.attacker_test.dice_modifiers])
        self.assertTrue(npc.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(npc.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertNotIn(FLAIL_STAGGERED_RULE_ID,
            [mod.rule_id for mod in npc.proof.request.kernel_request.attack.attacker_test.dice_modifiers])
        self.assertEqual(result.source.party[0].talents,MIGHTY)
        self.assertEqual(result.source.enemies[0].definition.generated_components.talents,MIGHTY)
        self.assertEqual(result.state.party[0].fate,scenario.party[0].fate)
        self.assertFalse(hasattr(result.state.enemies[0].state,'fate'))
        replay=initial_pc_melee_state(scenario)
        for step in result.steps:
            replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)
        # The literal real receipts cannot be laundered through a source that
        # no longer owns the Talent, even though all raw characteristics agree.
        with self.assertRaises((TypeError,ValueError)):
            changed=replace(scenario,party=(replace(scenario.party[0],talents=()),))
            PcMeleeStep(replace(pc.source,source=changed),pc.proof)
        with self.assertRaises((TypeError,ValueError)):
            component=scenario.enemies[0].definition.generated_components
            changed=replace(scenario,enemies=(replace(component,talents=()).participant('minion1'),))
            PcMeleeStep(replace(npc.source,source=changed),npc.proof)

    def test_real_melee_help_prefix_uses_full_held_two_handed_source_and_replays(self):
        scenario=make_pc_melee_party_scenario(pc_count=2,enemy_count=1,max_rounds=1)
        helper=member_with_weapon(scenario.party[0],PcMeleeWeapon.GREATAXE)
        helper=replace(helper,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.ATTACK,Skill.MELEE))
        scenario=replace(scenario,party=(helper,scenario.party[1]))
        state=initial_pc_melee_state(scenario)
        steps=[]
        state=append_step(state,start_combat_turn(CombatTurnStartRequest(
            pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1')),steps)
        state=append_step(state,reserve_combat_action_slot(CombatActionSlotRequest(
            pc_melee_action_id(state,'pc1')+':reserve',state.round_state,'pc1',
            pc_melee_action_declaration(state),ActionSlotGrant.STANDARD)),steps)
        request=build_pc_help_action(state)
        self.assertEqual(request.help_test.dice_modifiers,())
        self.assertIs(request.help_skill,Skill.MELEE)
        rng=ScriptedD10([1,1,1])
        execution=execute_help_action(request,rng)
        rng.assert_exhausted()
        proof=PcHelpProof(request,execution,
            PcFateDecline('pc1',request.help_test.id,'test',helper.fate_policy),
            weapon_use=pc_help_weapon_use(state),
            beneficiary_weapon_item_id=pc_help_beneficiary_weapon(state,pc_selected_help_policy(state)))
        state=append_step(state,proof,steps)
        self.assertEqual(execution.bonus.bonus_dice,3)
        self.assertIs(execution.slot.declaration.kind,CombatActionKind.HELP)
        self.assertEqual(proof.weapon_use.kind,PcMeleeWeapon.GREATAXE)
        self.assertEqual(state.source.party[0].talents,MIGHTY)
        replay=initial_pc_melee_state(scenario)
        for step in steps:
            replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,state)
        with self.assertRaises(ValueError):
            PcMeleeStep(state,proof)

    def test_source_bound_melee_protection_removes_only_its_actual_weapon_penalty(self):
        for owned,expected in ((True,()),(False,(DiceModifier(GREATAXE_MELEE_RULE_ID,-1),))):
            with self.subTest(owned=owned):
                state=initial_pc_melee_state(source(pc_mighty=owned))
                request=_pc_test(state,'pc','prepared:close-shooting',Skill.MELEE,
                    oppose_attack=True,incoming_attack_skill=Skill.SHOOTING)
                self.assertEqual(request.dice_modifiers,expected)
                self.assertEqual(request.profile.base_dice,3)
                self.assertEqual(state.source.party[0].talents,MIGHTY if owned else ())

    def test_external_melee_and_defence_penalties_survive_actual_actor_preparation(self):
        state=initial_pc_melee_state(source())
        external=DiceModifier('external:injury-or-condition',-1)
        for skill in (Skill.MELEE,Skill.DEFENCE):
            with self.subTest(skill=skill):
                request=_pc_test(state,'pc','prepared:external:'+skill.value,skill,(external,),
                    oppose_attack=skill is Skill.DEFENCE,incoming_attack_skill=Skill.MELEE)
                self.assertEqual(request.dice_modifiers,(external,))
                rng=ScriptedD10([1,1])
                test=resolve_test(request,rng)
                rng.assert_exhausted()
                self.assertEqual(test.trace.rolled_dice,2)

    def test_explicit_condition_boundary_keeps_one_handed_penalty_but_removes_flail_penalty(self):
        # A local Test-preparation boundary only: no preceding Staggered
        # application or complete native battle is claimed for these snapshots.
        for weapon,expected in ((PcMeleeWeapon.MORNING_STAR,
                (DiceModifier(MORNING_STAR_STAGGERED_RULE_ID,-1),)),
                (PcMeleeWeapon.FLAIL,())):
            with self.subTest(weapon=weapon):
                state=initial_pc_melee_state(source(pc_weapon=weapon))
                member=state.party[0]
                member=replace(member,injury=replace(member.injury,
                    conditions=ConditionState(frozenset((Condition.STAGGERED,)))))
                prepared=replace(state,party=(member,))
                request=_pc_test(prepared,'pc','prepared:staggered',Skill.MELEE)
                self.assertEqual(request.dice_modifiers,expected)


if __name__=='__main__':
    unittest.main()
