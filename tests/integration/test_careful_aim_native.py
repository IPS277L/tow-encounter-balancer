"""Real damage→Staggered→Aim→Attack histories on both sides, PG74/116."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.talent_sources import paid_talent
from towr.application.encounter_character import EncounterCharacter
from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID, AimFollowUpOutcome
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, GeneratedRangedFacts
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_aim_models import PcAimProof, PcAimConsumptionProof
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_models import PcMeleeWeapon, PcMeleePolicy, PcRangedProfile, PcRangedReloadHandPolicy, PcWeaponHand
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep, initial_pc_melee_state
from towr.domain.pc_npc_aim_models import PcNpcAimProof, PcNpcAimConsumptionProof
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def character(actor, weapon, *, careful=False):
    shooting = weapon is not PcMeleeWeapon.THROWING_KNIVES
    firearm = weapon is PcMeleeWeapon.PISTOL
    profile = (PcRangedProfile(1, 6 if firearm else 2, 
        ammunition_supply_confirmed=True, has_blackpowder_lore=True if firearm else None,
        has_blackpowder_kit=True if firearm else None,
        reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS if firearm else None) if shooting else None)
    return EncounterCharacter(actor, 1, 3, 10, 1, 2, 2, 2, 2, weapon, ArmourLoadout(), False,
        PcWeaponHand.LEFT, (paid_talent(TalentId.CAREFUL_AIM),) if careful else (), 0,
        ranged=profile, dexterity=2 if firearm else None, initiative=4 if careful else 1, awareness=10 if careful else None,
        combat_equipment=initial_weapon_items(weapon, PcWeaponHand.LEFT, None,
            initially_loaded=True if firearm else None),
        throwing=2 if not shooting else None, ballistic_skill=1 if not shooting else None,
        talent_facts=TalentOwnerFacts(reason=4) if careful else None)


def scene(*, npc_careful=False, throwing=True):
    base = make_pc_melee_party_scenario(pc_count=1 if npc_careful else 2, enemy_count=1, max_rounds=3)
    if npc_careful:
        characters = (character('pc1', PcMeleeWeapon.PISTOL),)
        kind = GeneratedWeapon.THROWING_KNIVES if throwing else GeneratedWeapon.SLING
        npc = GeneratedNpc(1, 3, 10, 1, 2, 2, initial_generated_weapons(kind), ArmourLoadout(), defence=2,
            initiative=4, awareness=6, throwing=2 if throwing else None, ballistic_skill=1 if throwing else None,
            ranged=None if throwing else GeneratedRangedFacts(1,2,True,None,None),
            talents=(paid_talent(TalentId.CAREFUL_AIM),), talent_facts=TalentOwnerFacts(reason=4))
    else:
        characters = (character('pc1', PcMeleeWeapon.PISTOL),
            character('pc2', PcMeleeWeapon.THROWING_KNIVES if throwing else PcMeleeWeapon.SLING, careful=True))
        npc = GeneratedNpc(1, 3, 10, 1, 2, 2, initial_generated_weapons(GeneratedWeapon.PISTOL),
            ArmourLoadout(), defence=2, initiative=1, ranged=GeneratedRangedFacts(1,6,True,True,True), dexterity=2)
    members = tuple(value.participant('careful:session', NpcDefeatDisposition.KILLED) for value in characters)
    return replace(base, party=members, enemies=(npc.participant('generated-npc:1'),),
        enemy_activation_order=('generated-npc:1',),
        enemy_target_priority=tuple(reversed(tuple(member.actor_id for member in members))),
        npc_ranged_policies=((pc_npc_ranged_policy_for_generated(npc,'generated-npc:1'),) if npc.ranged else ()),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG),
        facts=replace(base.facts, all_opponents_close=False, can_leave_zone=True,
            outnumbering_bonus_approved=False))


class CarefulAimNativeTests(TestCase):
    def execute(self, source, script):
        result=run_pc_melee_scenario(source,SequenceRandom(script+[10]*500))
        self.assertIsNone(result.unsupported)
        state=initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,state)
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)
        return result

    def assert_real_sequence(self, result, actor, aim_kind, consumption_kind, skill=Skill.THROWING):
        aims=tuple(step for step in result.steps if type(step.proof) is aim_kind
            and step.proof.request.actor_id==actor and step.proof.careful_aim is not None)
        self.assertTrue(aims, 'actual prior damage must produce a useful selected Careful Aim')
        aim=aims[0]
        self.assertTrue(aim.proof.result.awareness_test_result.succeeded)
        consumes=tuple(step.proof for step in result.steps if type(step.proof) is consumption_kind
            and step.proof.follow_up.source_request.aim==aim.proof.result)
        self.assertEqual(len(consumes),1)
        follow=consumes[0].follow_up
        self.assertIs(follow.outcome,AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
        self.assertIs(follow.source_request.attack_skill,skill)
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.id==follow.attack.id)
        bonuses=tuple(mod for mod in attack.request.kernel_request.attack.attacker_test.dice_modifiers
            if mod.rule_id==AIM_FOLLOW_UP_RULE_ID)
        self.assertEqual(len(bonuses),1)
        self.assertEqual(bonuses[0].amount,aim.proof.result.awareness_test_result.effective_successes)

    def test_pc_receives_real_staggered_and_aims_a_pure_throwing_inventory(self):
        result=self.execute(scene(),[10,10]+[1]*100)
        self.assert_real_sequence(result,'pc2',PcAimProof,PcAimConsumptionProof)

    def test_generated_npc_aims_and_consumes_throwing_bonus_after_a_real_hit(self):
        result=self.execute(scene(npc_careful=True),[1,10]+[1]*4+[10]*3+[1,1,10])
        self.assert_real_sequence(result,'generated-npc:1',PcNpcAimProof,PcNpcAimConsumptionProof)

    def test_pc_uses_the_same_talent_with_one_handed_shooting(self):
        result=self.execute(scene(throwing=False),[10,10]+[1]*100)
        self.assert_real_sequence(result,'pc2',PcAimProof,PcAimConsumptionProof,Skill.SHOOTING)

    def test_generated_npc_uses_the_same_talent_with_one_handed_shooting(self):
        result=self.execute(scene(npc_careful=True,throwing=False),[1,10]+[1]*4+[10]*30)
        self.assert_real_sequence(result,'generated-npc:1',PcNpcAimProof,PcNpcAimConsumptionProof,Skill.SHOOTING)

    def test_aimed_wound_settles_both_aim_and_actual_lady_consumption(self):
        from tests.support.oath_sources import lady
        from tests.integration.test_oath_native import lady_context
        from towr.domain.pc_oath_models import actor_oath, PcOathNegationAckProof
        source=scene()
        npc=replace(source.enemies[0].definition.generated_components,toughness=2,
            talents=(lady(free=True),),oath_context=lady_context(prebattle=True))
        source=replace(source,enemies=(npc.participant('generated-npc:1'),))
        # Both first attacks miss: the blessing must still be available for
        # the later aimed hit, rather than spent on pc2's opening attack.
        result=self.execute(source,[10,10,10,1]+[1]*100)
        self.assert_real_sequence(result,'pc2',PcAimProof,PcAimConsumptionProof)
        self.assertEqual(result.state.enemies[0].state.injury.wounds,0)
        self.assertEqual(len(actor_oath(result.state,'generated-npc:1').lady_uses),1)
        ack_index=next(index for index,step in enumerate(result.steps)
            if type(step.proof) is PcOathNegationAckProof)
        self.assertIs(type(result.steps[ack_index-1].proof),PcAimConsumptionProof)
