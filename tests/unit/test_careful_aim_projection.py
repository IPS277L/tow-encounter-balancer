"""Prepared injury/action boundaries; not a fabricated full battle journal."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.talent_sources import paid_talent
from tests.unit.test_pc_npc_aim import source as npc_source, prepared as npc_prepared, reserve as npc_reserve
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRecord, WoundEntryId
from towr.domain.pc_aim_models import PcAimProof, build_pc_aim, project_pc_aim_step
from towr.domain.pc_melee_result_models import initial_pc_melee_state, PcFateDecline
from towr.domain.pc_npc_aim_models import PcNpcAimProof, build_npc_aim, project_npc_aim_step
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.talent_careful_aim_models import careful_aim_application
from towr.domain.turn_models import CombatTurnStartRequest, CombatActionSlotRequest, CombatActionDeclaration, CombatActionKind, ActionSlotGrant
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


class CarefulAimProjectionTests(TestCase):
    def player(self, *, ongoing=False):
        scene = make_pc_hochland_scenario(use_second_action=False)
        source = replace(scene.party[0], talents=(paid_talent(TalentId.CAREFUL_AIM),),
            talent_facts=TalentOwnerFacts(reason=4))
        scene = replace(scene, party=(source,))
        state = initial_pc_melee_state(scene)
        actor = source.actor_id
        member = state.participant(actor)
        effects = (WoundConditionEffect(1, Condition.STAGGERED, WoundEffectDuration.UNTIL_HEALED),) if ongoing else ()
        wounds = (WoundRecord(1, WoundEntryId.SCARRING_STRIKE, 15, (7, 8), effect_resolved=True),) if ongoing else ()
        member = replace(member, injury=replace(member.injury, conditions=ConditionState(frozenset((
            Condition.STAGGERED, Condition.DRAINED))), active_wound_effects=effects, wounds=wounds))
        clock = start_combat_turn(CombatTurnStartRequest('prepared:start', state.round_state, actor)).state
        clock = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve', clock, actor,
            CombatActionDeclaration(CombatActionKind.AIM), ActionSlotGrant.STANDARD)).state
        return replace(state, party=(member,), round_state=clock), actor

    def test_player_removes_after_final_roll_without_changing_the_paid_aim(self):
        state, actor = self.player()
        request = build_pc_aim(state)
        execution = execute_aim_action(request, SequenceRandom([1]*10))
        application = careful_aim_application(state, execution)
        proof = PcAimProof(request, execution, PcFateDecline(actor, request.awareness_test.id, 'test', state.source.participant(actor).fate_policy),
            careful_aim=application)
        after = project_pc_aim_step(state, proof)
        self.assertIsNotNone(application)
        self.assertFalse(after.participant(actor).injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(after.participant(actor).injury.conditions.has(Condition.DRAINED))
        self.assertEqual(after.round_state, execution.round_state)
        self.assertEqual(after.history[-1].result.awareness_test_result, execution.awareness_test_result)
        with self.assertRaises(ValueError):
            project_pc_aim_step(state, replace(proof, careful_aim=None))
        with self.assertRaises(ValueError):
            project_pc_aim_step(after, proof)

    def test_failed_and_ongoing_staggered_remain(self):
        for ongoing, die in ((False, 10), (True, 1)):
            with self.subTest(ongoing=ongoing):
                state, actor = self.player(ongoing=ongoing)
                request = build_pc_aim(state)
                execution = execute_aim_action(request, SequenceRandom([die]*10))
                self.assertIsNone(careful_aim_application(state, execution))
                proof = PcAimProof(request, execution, PcFateDecline(actor, request.awareness_test.id, 'test', state.source.participant(actor).fate_policy))
                self.assertTrue(project_pc_aim_step(state, proof).participant(actor).injury.conditions.has(Condition.STAGGERED))

    def test_generated_npc_has_the_same_post_test_removal(self):
        scene = npc_source()
        generated = replace(scene.enemies[0].definition.generated_components,
            talents=(paid_talent(TalentId.CAREFUL_AIM),), talent_facts=TalentOwnerFacts(reason=4))
        scene = replace(scene, enemies=(generated.participant('minion1'),))
        state = npc_prepared(scene)
        enemy = state.enemies[0]
        injury = replace(enemy.state.injury,
            conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        state = replace(state, enemies=(replace(enemy, state=replace(enemy.state, injury=injury)),))
        state = npc_reserve(state, CombatActionKind.AIM)
        request = build_npc_aim(state)
        execution = execute_aim_action(request, SequenceRandom([1]*10))
        proof = PcNpcAimProof(request, execution, careful_aim=careful_aim_application(state, execution))
        after = project_npc_aim_step(state, proof)
        self.assertIsNotNone(proof.careful_aim)
        self.assertFalse(after.enemies[0].state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(after.round_state, execution.round_state)
        with self.assertRaises(ValueError):
            project_npc_aim_step(state, replace(proof, careful_aim=None))

    def test_injured_two_hand_use_keeps_the_new_critical_after_removal(self):
        from towr.domain.injury_models import WoundRestrictionEffect, WoundRestriction
        from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
        from towr.domain.pc_melee_models import PcWeaponHand
        state, actor = self.player()
        member = state.participant(actor)
        injury = replace(member.injury,
            wounds=(WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),))
        member = replace(member, injury=injury,
            body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),))
        state = replace(state, party=(member,))
        request = build_pc_aim(state)
        execution = execute_aim_action(request,SequenceRandom([1]*10))
        proof = PcAimProof(request,execution,PcFateDecline(actor,request.awareness_test.id,'test',
            state.source.participant(actor).fate_policy),careful_aim=careful_aim_application(state,execution))
        after = project_pc_aim_step(state,proof).participant(actor)
        self.assertFalse(after.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(after.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(after.body_facts,member.body_facts)

    def test_careful_aim_uses_the_final_fate_reroll_without_erasing_its_price(self):
        from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy
        from towr.domain.test_models import Skill
        from towr.engine.pc_melee_runner import _resolve_pc_test, _Decisions
        from towr.rules.aim_resolution import _complete_aim_action_after_test
        state,actor = self.player()
        source = state.source.participant(actor)
        source = replace(source,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.AWARENESS,),0,0))
        state = replace(state,source=replace(state.source,party=(source,)))
        request=build_pc_aim(state)
        test,decline,glorious,effective=_resolve_pc_test(state,actor,Skill.AWARENESS,
            request.awareness_test,SequenceRandom([10]*3+[1]*3),_Decisions())
        result=_complete_aim_action_after_test(replace(request,awareness_test=effective),test)
        proof=PcAimProof(request,result,decline,glorious=glorious,
            careful_aim=careful_aim_application(state,result))
        after=project_pc_aim_step(state,proof)
        self.assertIsNotNone(glorious)
        self.assertEqual(test.trace.initial_values,(10,10,10))
        self.assertEqual(test.trace.final_values,(1,1,1))
        self.assertFalse(after.participant(actor).injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(after.participant(actor).fate,glorious.state)

    def test_npc_awareness_has_only_one_actual_honour_modifier(self):
        from tests.support.oath_sources import honour, context
        from towr.domain.pc_oath_models import actor_oath
        from towr.domain.pc_melee_result_models import PcMeleeStep
        from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
        from towr.engine.pc_melee_runner import _Decisions
        scene=npc_source()
        generated=replace(scene.enemies[0].definition.generated_components,talents=(honour(),),
            oath_context=replace(context(),forbidden_attack_skills=()))
        state=npc_reserve(npc_prepared(replace(scene,enemies=(generated.participant('minion1'),))),CombatActionKind.AIM)
        request=build_npc_aim(state)
        self.assertEqual(sum(value.rule_id==HONOUR_BOUND_GLORIOUS_RULE_ID
            for value in request.awareness_test.quality_modifiers),1)
        result=execute_aim_action(request,SequenceRandom([1]*10),decisions=_Decisions())
        after=PcMeleeStep(state,PcNpcAimProof(request,result)).state
        self.assertEqual(len(actor_oath(after,'minion1').honour_uses),1)

    def test_actual_honour_outcome_keeps_raw_failed_aim_and_spends_fate_once(self):
        from tests.support.oath_sources import with_native_outcome_owner
        from towr.domain.pc_oath_models import initial_pc_oaths, actor_oath
        from towr.domain.pc_melee_result_models import PcMeleeStep
        from towr.domain.test_models import Skill
        from towr.engine.pc_melee_runner import _resolve_pc_test, _Decisions
        from towr.rules.aim_resolution import _complete_aim_action_after_test
        state,actor=self.player()
        source=with_native_outcome_owner(state.source)
        state=replace(state,source=source,oaths=initial_pc_oaths(source),
            party=(replace(state.participant(actor),fate=source.participant(actor).fate),))
        request=build_pc_aim(state)
        test,decline,glorious,effective=_resolve_pc_test(state,actor,Skill.AWARENESS,
            request.awareness_test,SequenceRandom([10]*10),_Decisions())
        result=_complete_aim_action_after_test(replace(request,awareness_test=effective),test)
        proof=PcAimProof(request,result,decline,glorious=glorious,
            careful_aim=careful_aim_application(state,result))
        after=PcMeleeStep(state,proof).state
        self.assertEqual(test.successes,0)
        self.assertEqual(result.bonus.bonus_dice,test.effective_successes)
        self.assertIsNotNone(proof.careful_aim)
        self.assertEqual(len(actor_oath(after,actor).honour_uses),1)
        self.assertEqual(len(after.participant(actor).fate.spends),1)
        self.assertFalse(after.participant(actor).fate.burns)
