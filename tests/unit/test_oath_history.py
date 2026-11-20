"""Oath bank readmission from real native receipts, without resource resets."""
from dataclasses import replace
from unittest import TestCase

from tests.integration.test_oath_native import native_source, lady_context, LiteralD10
from tests.support.magic_weapon_battles import magic_battle
from tests.support.oath_sources import honour, lady, context, source as oath_source
from towr.domain.lady_blessing_models import record_lady_prayer
from towr.domain.pc_give_ground_models import PcAfterGiveGroundProof
from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof, PcBrokenRunProof
from towr.domain.pc_melee_result_models import initial_pc_melee_state, validate_pc_melee_state_shape
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_oath_history_models import fold_native_oaths
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario


class OathHistoryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        source=native_source(pc_talents=(honour(),),pc_context=context())
        member=source.party[0]
        source=replace(source,party=(replace(member,fate=replace(member.fate,rating=0,session_spend_limit=0)),))
        cls.glorious=run_pc_melee_scenario(source,LiteralD10())
        source=native_source(pc_talents=(lady(free=True),),pc_context=lady_context())
        cls.prayer=run_pc_melee_scenario(source,LiteralD10())
        source=magic_battle('scarab_knife',pc_strength=6,npc_toughness=3,rounds=1)
        enemy=source.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(lady(free=True),),
            oath_context=lady_context(prebattle=True))
        source=replace(source,enemies=(npc.participant(enemy.state.actor_id),))
        cls.cancelled=run_pc_melee_scenario(source,LiteralD10(1))

    def assert_bank_rejected(self,state,bank):
        with self.assertRaises((TypeError,ValueError)):
            validate_pc_melee_state_shape(replace(state,oaths=bank))

    def test_actual_complete_banks_are_canonical_without_replaying_world_rules(self):
        for result in (self.glorious,self.prayer,self.cancelled):
            with self.subTest(source=result.source.id):
                self.assertEqual(fold_native_oaths(result.source,result.state.history),result.state.oaths)
                validate_pc_melee_state_shape(result.state)

    def test_spent_glorious_and_lady_cannot_reset_to_the_actual_initial_bank(self):
        for result in (self.glorious,self.cancelled):
            with self.subTest(source=result.source.id):
                self.assert_bank_rejected(result.state,initial_pc_melee_state(result.source).oaths)

    def test_paid_prayer_cannot_disappear_and_unperformed_prayer_cannot_appear(self):
        result=self.prayer
        initial=initial_pc_melee_state(result.source)
        self.assert_bank_rejected(result.state,initial.oaths)
        row=initial.oaths[0]
        invented=replace(row,lady=record_lady_prayer(row.lady,'invented:prayer'))
        self.assert_bank_rejected(initial,(invented,))

    def test_uses_and_activation_header_cannot_be_inflated_or_replaced(self):
        state=self.glorious.state;row=state.oaths[0]
        for changed in (replace(row,honour_uses=(*row.honour_uses,*row.honour_uses)),
                replace(row,honour=replace(row.honour,activation_id='foreign:activation')),
                replace(row,context=replace(row.context,gm_confirmation_id='foreign:gm'))):
            with self.subTest(changed=changed):self.assert_bank_rejected(state,(changed,))

    def test_initial_used_session_resource_cannot_be_reopened_without_any_action(self):
        source=native_source(pc_talents=(honour(),),pc_context=context(honour_bound_used_this_session=True))
        state=initial_pc_melee_state(source);row=state.oaths[0]
        self.assert_bank_rejected(state,(replace(row,honour=replace(row.honour,activation_id=None)),))

    def test_actual_broken_loss_and_later_fleeing_breach_cannot_be_erased(self):
        from towr.domain.condition_models import Condition
        original=magic_battle('staff',pc_ws=6,npc_ws=1,rounds=2)
        gm=replace(context(lady_prayer_before_battle_confirmed=True,fleeing_breaks_oath=True),
            combat_tests_fulfil_oath_confirmed=False)
        member=replace(original.party[0],mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN)
        enemy=original.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(honour(),lady()),
            oath_context=gm,talent_facts=oath_source().talent_facts)
        source=replace(original,party=(member,),enemies=(npc.participant(enemy.state.actor_id),),
            facts=replace(original.facts,unmounted=False))
        result=run_pc_melee_scenario(source,LiteralD10(3))
        broken=next(step for step in result.steps if type(step.proof) is PcAfterGiveGroundProof
            and step.proof.result.state.conditions.has(Condition.BROKEN))
        fled=next(step for step in result.steps if type(step.proof) in (PcBrokenMoveProof,PcBrokenRunProof)
            and step.proof.actor_id==enemy.state.actor_id)
        for step in (broken,fled):
            self.assertEqual(fold_native_oaths(source,step.state.history),step.state.oaths)
            self.assert_bank_rejected(step.state,initial_pc_melee_state(source).oaths)
