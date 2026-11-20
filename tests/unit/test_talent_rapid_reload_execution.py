"""Real Rapid Reload journals and canonical native prefixes for both sides."""
from dataclasses import replace
import unittest

from tests.support.armour_fixtures import light_loadout
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.talent_sources import paid_talent
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.pc_aim_models import PcAimProof, build_pc_aim, current_pc_aim
from towr.domain.pc_melee_models import PcMeleePolicy, PcShortRangeOpening
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcFateDecline, PcMeleeStep, initial_pc_melee_state,
    pc_melee_action_declaration, pc_melee_action_id,
)
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_rapid_reload_models import (
    actor_moved_this_turn, build_pc_rapid_reload_second_action, rapid_reload_options,
)
from towr.domain.pc_ranged_models import PcRangedReloadProof, build_pc_ranged_reload
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionKind, CombatActionSlotRequest, CombatActionSlotResult,
    CombatTurnStartRequest,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def pc_source(*, rounds=1, awareness=None):
    source = make_pc_pistol_scenario(max_rounds=rounds, ballistic_skill=4, dexterity=5)
    member = source.party[0]
    member = replace(member, pc=replace(member.pc, toughness=20,
        awareness=awareness),
        talents=(paid_talent(TalentId.RAPID_RELOAD),),
        combat_equipment=tuple(replace(item, initially_loaded=False) for item in member.combat_equipment))
    return replace(source, party=(member,), facts=replace(source.facts, outnumbering_bonus_approved=False,
        all_opponents_close=awareness is None,can_leave_zone=False),
        short_range_opening=PcShortRangeOpening(True,True) if awareness is not None else None)


def npc_source(*, rounds=1, awareness=None, weapon=GeneratedWeapon.PISTOL):
    source = make_pc_melee_party_scenario(pc_count=1,enemy_count=1,max_rounds=rounds)
    firearm=weapon is not GeneratedWeapon.REPEATER_HANDBOW
    ranged = GeneratedRangedFacts(4, 4,  True, True if firearm else None, True if firearm else None)
    npc = GeneratedNpc(2, 2, 20, 3, 3, 3,
        initial_generated_weapons(weapon, initially_loaded=False),
        light_loadout(light=False, shield=False), defence=3, ranged=ranged,dexterity=5,
        talents=(paid_talent(TalentId.RAPID_RELOAD),), initiative=3, awareness=awareness)
    member = source.party[0]
    return replace(source, party=(replace(member, pc=replace(member.pc,toughness=20)),),
        enemies=(npc.participant('minion1'),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def consume(state, proof, steps):
    step = PcMeleeStep(state, proof)
    steps.append(step)
    return step.state


def pc_reload_prefix(source, values):
    """Execute an actual first PC Reload; no projected snapshots are forged."""
    state = initial_pc_melee_state(source)
    steps = []
    state = consume(state, start_combat_turn(CombatTurnStartRequest(
        pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1')), steps)
    from towr.domain.pc_battlefield_movement_models import expected_pc_action_positioning
    positioning=expected_pc_action_positioning(state)
    if positioning is not None:
        state=consume(state,positioning,steps)
    state = consume(state, reserve_combat_action_slot(CombatActionSlotRequest(
        pc_melee_action_id(state,'pc1')+':reserve',state.round_state,'pc1',
        pc_melee_action_declaration(state),ActionSlotGrant.STANDARD)), steps)
    request = build_pc_ranged_reload(state)
    rng = ScriptedD10(values)
    result = execute_reload_action(request, rng)
    rng.assert_exhausted()
    state = consume(state, PcRangedReloadProof(request,result,
        PcFateDecline('pc1',request.dexterity_test.id,'test',source.party[0].fate_policy)), steps)
    return state, steps


class RapidReloadExecutionTests(unittest.TestCase):
    def assert_replays(self, source, steps, expected):
        state = initial_pc_melee_state(source)
        for step in steps:
            state = apply_pc_melee_step(state,step)
        self.assertEqual(state,expected)

    def test_pc_actual_reload_immediately_shoots_once_with_same_item_and_replays(self):
        source = pc_source()
        rng = ScriptedD10([1,1,1]+[10]*11)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        reload = next(step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        shot = next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertEqual(shot.proof.request.slot_index,2)
        self.assertEqual(shot.proof.weapon_intent.attack_use.primary_item_id,
            reload.proof.result.state.weapon_instance_id)
        self.assertEqual(result.executed_actions,3)
        self.assertEqual(len(shot.proof.execution.state.active_turn.action_slots),2)
        self.assert_replays(source,result.steps,result.state)
        reservation = next(step for step in result.steps if type(step.proof) is CombatActionSlotResult
            and step.proof.slot.rapid_reload is not None)
        with self.assertRaises(ValueError):
            PcMeleeStep(reservation.state,reservation.proof)
        changed = replace(source,party=(replace(source.party[0],talents=()),))
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(replace(reservation.source,source=changed),reservation.proof)

    def test_generated_npc_actual_reload_shoots_without_fate_and_replays(self):
        source = npc_source()
        rng = ScriptedD10([10]*6+[1,1,1]+[10]*7)
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        reload = next(step for step in result.steps if type(step.proof) is PcNpcRangedReloadProof)
        shot = next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        self.assertEqual(shot.proof.request.slot_index,2)
        self.assertEqual(shot.proof.weapon_intent.attack_use.primary_item_id,
            reload.proof.result.state.weapon_instance_id)
        self.assertEqual(result.executed_actions,3)
        self.assertFalse(hasattr(result.state.enemy('minion1').state,'fate'))
        self.assert_replays(source,result.steps,result.state)

    def test_partial_success_native_aim_is_legal_and_cannot_enable_an_unloaded_attack(self):
        source = pc_source(awareness=4)
        state, steps = pc_reload_prefix(source,[1,10,10])
        options = rapid_reload_options(state)
        self.assertTrue(options)
        self.assertTrue(all(option.declaration.kind is CombatActionKind.AIM for option in options))
        self.assertIsNone(build_pc_rapid_reload_second_action(state))
        state = consume(state,reserve_combat_action_slot(options[0]),steps)
        request = build_pc_aim(state)
        self.assertEqual(request.slot_index,2)
        rng = ScriptedD10([1,1,1])
        result = execute_aim_action(request,rng)
        rng.assert_exhausted()
        state = consume(state,PcAimProof(request,result,
            PcFateDecline('pc1',request.awareness_test.id,'test',source.party[0].fate_policy)),steps)
        self.assertIsNotNone(current_pc_aim(state,'pc1'))
        self.assertFalse(state.participant('pc1').ranged.loaded)
        self.assert_replays(source,steps,state)

    def test_zero_success_and_absent_awareness_provide_no_partial_followup(self):
        for values in ([10,10,10],[1,10,10]):
            with self.subTest(values=values):
                state, steps = pc_reload_prefix(pc_source(),values)
                self.assertEqual(rapid_reload_options(state),())
                self.assertIsNone(build_pc_rapid_reload_second_action(state))

    def test_real_staggered_npc_completes_reload_without_a_second_action(self):
        source=npc_source()
        # Actual PC hit causes Staggered without a Wound against Toughness20.
        rng=ScriptedD10([1]*3+[10]*3+[1]*3)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        reload=next(step for step in result.steps if type(step.proof) is PcNpcRangedReloadProof)
        self.assertTrue(reload.proof.result.completed)
        self.assertEqual(rapid_reload_options(reload.state),())
        self.assertFalse(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1' for step in result.steps))
        self.assert_replays(source,result.steps,result.state)

    def test_real_incidental_movement_then_successful_reload_cannot_grant_action2(self):
        source=pc_source(rounds=2)
        source=replace(source,party=(replace(source.party[0],policy=PcMeleePolicy.AUTOMATIC_COMBAT),),
            facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.MEDIUM,RangedWeaponRange.LONG))
        state,steps=pc_reload_prefix(source,[1,1,1])
        self.assertTrue(actor_moved_this_turn(state,'pc1'))
        self.assertTrue(steps[-1].proof.result.completed)
        self.assertEqual(rapid_reload_options(state),())
        self.assertIsNone(build_pc_rapid_reload_second_action(state))
        self.assert_replays(source,steps,state)

    def test_generated_npc_partial_aim_uses_actual_awareness_and_keeps_first_slot(self):
        from tests.support.pc_pistol_scenarios import pistol_profile
        from tests.support.pc_weapon_sources import initial_weapon_items
        from towr.domain.pc_melee_models import PcMeleeWeapon
        from towr.domain.pc_npc_aim_models import PcNpcAimProof,build_npc_aim,current_npc_aim
        source=npc_source(awareness=4)
        member=source.party[0]
        member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile(), initiative=3, dexterity=4),
            combat_equipment=initial_weapon_items(PcMeleeWeapon.PISTOL,member.initial_weapon_hand,
                initially_loaded=True))
        source=replace(source,party=(member,),
            facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG))
        rng=ScriptedD10([10]*6+[1,10,10])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        index=next(i for i,step in enumerate(result.steps) if type(step.proof) is PcNpcRangedReloadProof)
        state=result.steps[index].state
        steps=list(result.steps[:index+1])
        options=rapid_reload_options(state)
        self.assertTrue(options)
        self.assertTrue(all(option.declaration.kind is CombatActionKind.AIM for option in options))
        state=consume(state,reserve_combat_action_slot(options[0]),steps)
        request=build_npc_aim(state)
        self.assertEqual(request.awareness_test.profile.base_dice,3)
        self.assertEqual(request.awareness_test.profile.threshold,4)
        rng=ScriptedD10([1,1,1])
        aimed=execute_aim_action(request,rng)
        rng.assert_exhausted()
        first=state.round_state.active_turn.action_slots[0]
        state=consume(state,PcNpcAimProof(request,aimed),steps)
        self.assertEqual(state.round_state.active_turn.action_slots[0],first)
        self.assertIsNotNone(current_npc_aim(state,'minion1'))
        self.assert_replays(source,steps,state)

    def test_generated_repeaters_commit_their_second_shot_mode_before_its_test(self):
        from towr.domain.ranged_weapon_profiles import ranged_weapon_reload_profile,RangedWeaponId
        for weapon,bonus in ((GeneratedWeapon.REPEATER_PISTOL,2),(GeneratedWeapon.REPEATER_HANDBOW,1)):
            with self.subTest(weapon=weapon):
                source=npc_source(weapon=weapon)
                self.assertEqual(ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_shooting_bonus_dice,bonus)
                rng=ScriptedD10([10]*6+[1]*3+[10]*(7+bonus))
                result=run_pc_melee_scenario(source,rng)
                rng.assert_exhausted()
                reservation=next(step for step in result.steps if type(step.proof) is CombatActionSlotResult
                    and step.proof.slot.rapid_reload is not None)
                self.assertTrue(reservation.proof.slot.rapid_reload.ranged_bonus)
                shot=next(step for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id=='minion1')
                self.assertEqual(shot.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4+bonus)
                self.assertTrue(shot.proof.npc_ranged_shot.preparation.source_request.uses_optional_reload_bonus)
                self.assert_replays(source,result.steps,result.state)

    def test_real_pc_reload_source_is_valued_as_reload_plus_shot_in_last_turn(self):
        from towr.domain.pc_ranged_advice import ranged_action_choices
        source=pc_source()
        _,rapid_steps=pc_reload_prefix(source,[1,1,1])
        rapid=rapid_steps[-1].source
        ordinary_source=replace(source,party=(replace(source.party[0],talents=()),))
        _,ordinary_steps=pc_reload_prefix(ordinary_source,[1,1,1])
        ordinary=ordinary_steps[-1].source
        rapid_choices=tuple(c for c in ranged_action_choices(rapid,'pc1') if c.ranged_reload)
        ordinary_choices=tuple(c for c in ranged_action_choices(ordinary,'pc1') if c.ranged_reload)
        self.assertTrue(rapid_choices)
        self.assertEqual(max(c.utility for c in ordinary_choices),0.0)
        self.assertGreater(max(c.utility for c in rapid_choices),0.0)

    def test_aim_after_partial_reload_is_lost_by_a_real_next_reload_receipt(self):
        # This combines the actual native Aim prefix with a separate lawful
        # K1 next-turn Reload owner. It does not claim a complete PC round2.
        from tests.unit.test_k1_reload_resolution import reload_request
        from towr.domain.aim_models import AimFollowUpOutcome
        from towr.domain.pc_aim_models import _consumption
        source=pc_source(awareness=4)
        state,steps=pc_reload_prefix(source,[1,10,10])
        state=consume(state,reserve_combat_action_slot(rapid_reload_options(state)[0]),steps)
        aimed_request=build_pc_aim(state)
        aimed=execute_aim_action(aimed_request,ScriptedD10([1,1,1]))
        state=consume(state,PcAimProof(aimed_request,aimed,
            PcFateDecline('pc1',aimed_request.awareness_test.id,'test',source.party[0].fate_policy)),steps)
        request=reload_request(state.participant('pc1').ranged,actor_id='pc1',action_number=2)
        reloaded=execute_reload_action(request,ScriptedD10([1,1,1]))
        proof=PcRangedReloadProof(request,reloaded,
            PcFateDecline('pc1',request.dexterity_test.id,'test',source.party[0].fate_policy))
        consumed=_consumption(aimed,proof,reloaded.slot.execution)
        self.assertIs(consumed.follow_up.outcome,AimFollowUpOutcome.LOST)
        self.assertIsNone(consumed.follow_up.modifier)

    def test_native_partial_aim_never_inflates_the_forecast_after_another_reload(self):
        from towr.domain.pc_ranged_advice import ranged_action_choices
        source=pc_source(awareness=4,rounds=2)
        state,steps=pc_reload_prefix(source,[1,10,10])
        before=state
        state=consume(state,reserve_combat_action_slot(rapid_reload_options(state)[0]),steps)
        request=build_pc_aim(state)
        result=execute_aim_action(request,ScriptedD10([1,1,1]))
        state=consume(state,PcAimProof(request,result,
            PcFateDecline('pc1',request.awareness_test.id,'test',source.party[0].fate_policy)),steps)
        self.assertEqual(current_pc_aim(state,'pc1').bonus.bonus_dice,3)
        # These are explicitly future-action forecasts from genuine prefixes,
        # not an assertion that action3 exists in either current turn.
        def reload_value(current):
            choices=ranged_action_choices(current,'pc1',_future_turn=True,_horizon=1)
            return next(choice.utility for choice in choices if choice.ranged_reload)
        self.assertEqual(reload_value(state),reload_value(before))
        self.assertGreater(reload_value(before),0.0)

    def test_hochland_reload_aim_is_two_actions_and_forecast_accounts_for_ordinary_aim_cost(self):
        from tests.support.pc_weapon_sources import initial_weapon_items
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip
        from towr.domain.pc_ranged_advice import ranged_action_choices
        source=pc_source(rounds=2,awareness=4)
        member=source.party[0]
        weapon=PcMeleeWeapon.HOCHLAND_LONG_RIFLE
        member=replace(member,pc=replace(member.pc,weapon=weapon,
            initiative=4),initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=initial_weapon_items(weapon,PcTwoHandedGrip.BOTH,initially_loaded=False))
        source=replace(source,party=(member,))
        state,steps=pc_reload_prefix(source,[1]*4)
        self.assertTrue(state.participant('pc1').ranged.loaded)
        followup=build_pc_rapid_reload_second_action(state)
        self.assertIs(followup.declaration.kind,CombatActionKind.AIM)
        before_reload=steps[-1].source
        ordinary_source=replace(source,party=(replace(member,talents=()),))
        _,ordinary_steps=pc_reload_prefix(ordinary_source,[1]*4)
        def reload_value(current):
            return next(c.utility for c in ranged_action_choices(current,'pc1') if c.ranged_reload)
        self.assertEqual(reload_value(ordinary_steps[-1].source),0.0)
        self.assertGreater(reload_value(before_reload),0.0)
        state=consume(state,reserve_combat_action_slot(followup),steps)
        request=build_pc_aim(state)
        aimed=execute_aim_action(request,ScriptedD10([10]*4))
        state=consume(state,PcAimProof(request,aimed,
            PcFateDecline('pc1',request.awareness_test.id,'test',member.fate_policy)),steps)
        self.assertEqual(len(state.round_state.active_turn.action_slots),2)
        self.assertEqual(rapid_reload_options(state),())
        self.assertIsNotNone(current_pc_aim(state,'pc1'))
        self.assert_replays(source,steps,state)


if __name__ == '__main__':
    unittest.main()
