"""Literal native Oath actions/resources and replay, never Monte Carlo scores."""
from dataclasses import replace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.oath_sources import honour, lady, context, source as oath_source
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.pc_melee_result_models import (
    initial_pc_melee_state, PcMeleeStep, PcWoundCompletionProof, PcAttackProof,
)
from towr.domain.pc_oath_models import (
    PcLadyPrayerProof, PcOathNegationAckProof, actor_oath, lady_prayer_selected, oath_step_evidence,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import TestResult
from towr.domain.turn_models import CombatTurnStartResult
from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
from towr.domain.pc_magic_weapon_models import PcScarabChargeProof
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof, PcBrokenRunProof
from towr.domain.pc_give_ground_models import PcAfterGiveGroundProof
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponItemSource, WeaponItemLocation
from towr.domain.test_models import Skill
from tests.support.magic_weapon_battles import magic_battle
from towr.engine.pc_melee_runner import run_pc_melee_scenario


class LiteralD10:
    def __init__(self, value=10):
        self.value=value
        self.calls=[]

    def randint(self, low, high):
        if (low,high)!=(1,10):
            raise AssertionError('unexpected non-d10 random draw')
        self.calls.append((low,high))
        if len(self.calls)>500:
            raise AssertionError('short native scenario consumed an unbounded dice script')
        return self.value


def native_source(*, pc_talents=(), npc_talents=(), pc_context=None, npc_context=None, rounds=1):
    initial=automatic_source(pc_count=1,enemy_count=1,rounds=rounds)
    member=initial.party[0]
    if pc_talents:
        member=replace(member,talents=pc_talents,oath_context=pc_context,
            talent_facts=oath_source().talent_facts if any(t.id is TalentId.HONOUR_BOUND for t in pc_talents)
                else None)
    npc=GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(GeneratedWeapon.DAGGER),ArmourLoadout(),
        defence=4,talents=npc_talents,oath_context=npc_context,
        talent_facts=oath_source().talent_facts if any(t.id is TalentId.HONOUR_BOUND for t in npc_talents)
            else None)
    return replace(initial,party=(member,),enemies=(npc.participant(initial.enemy_activation_order[0]),))


def lady_context(*, prebattle=False, good=True):
    return OathBattleContext('gm:lady',good,lady_prayer_before_battle_confirmed=prebattle)


def real_tests(result):
    seen=set()
    for step in result.steps:
        for proof in oath_step_evidence(step.proof):
            if type(proof) is TestResult and proof.trace.request_id not in seen:
                seen.add(proof.trace.request_id)
                yield proof


class OathNativeTests(unittest.TestCase):
    def assert_replays(self, source, result):
        state=initial_pc_melee_state(source)
        for step in result.steps:
            self.assertEqual(step.source,state)
            state=PcMeleeStep(state,step.proof).state
        self.assertEqual(state,result.state)

    def test_pc_and_generated_npc_each_pay_prayer_in_their_first_actual_turn(self):
        source=native_source(pc_talents=(lady(free=True),),npc_talents=(lady(free=True),),
            pc_context=lady_context(),npc_context=lady_context())
        rng=LiteralD10()
        result=run_pc_melee_scenario(source,rng)
        prayers=[step for step in result.steps if type(step.proof) is PcLadyPrayerProof]
        self.assertEqual([step.proof.result.blessing.actor_id for step in prayers],
            [source.pc_activation_order[0],source.enemy_activation_order[0]])
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(rng.calls,[])
        for step in prayers:
            prayer=step.proof.result
            self.assertTrue(prayer.slot.executed)
            self.assertTrue(actor_oath(step.state,prayer.blessing.actor_id).lady.available)
            self.assertEqual(prayer.source_request.slot_index,1)
        self.assertEqual(prayers[1].source.round_state.completed_turn_entity_ids,source.pc_activation_order)
        self.assert_replays(source,result)

    def test_prebattle_prayer_is_an_explicit_initial_source_not_an_extra_action(self):
        source=native_source(pc_talents=(lady(free=True),),npc_talents=(lady(free=True),),
            pc_context=lady_context(prebattle=True),npc_context=lady_context(prebattle=True))
        initial=initial_pc_melee_state(source)
        for row in initial.oaths:
            self.assertEqual(row.lady.prayers,('gm:lady:pre-battle-prayer',))
            self.assertTrue(row.lady.available)
        result=run_pc_melee_scenario(source,LiteralD10())
        self.assertFalse(any(type(step.proof) is PcLadyPrayerProof for step in result.steps))
        self.assertEqual(result.executed_actions,2)
        self.assert_replays(source,result)

    def test_pc_glorious_consumes_one_session_activation_and_no_fate(self):
        source=native_source(pc_talents=(honour(),),pc_context=context(),rounds=2)
        member=source.party[0]
        member=replace(member,fate=replace(member.fate,rating=0,session_spend_limit=0))
        source=replace(source,party=(member,))
        result=run_pc_melee_scenario(source,LiteralD10())
        actor=source.pc_activation_order[0]
        owner=actor_oath(result.state,actor)
        self.assertEqual(len(owner.honour_uses),1)
        self.assertFalse(owner.honour.available)
        actual=[test for test in real_tests(result)
            if HONOUR_BOUND_GLORIOUS_RULE_ID in test.trace.applied_rule_ids]
        self.assertEqual(len(actual),1)
        self.assertEqual(result.state.participant(actor).fate,member.fate)
        self.assert_replays(source,result)

    def test_generated_npc_can_activate_on_protection_before_its_own_prayer(self):
        source=native_source(npc_talents=(honour(),lady()),npc_context=context())
        result=run_pc_melee_scenario(source,LiteralD10())
        actor=source.enemy_activation_order[0]
        owner=actor_oath(result.state,actor)
        self.assertEqual(len(owner.honour_uses),1)
        prayers=[step for step in result.steps if type(step.proof) is PcLadyPrayerProof]
        self.assertEqual(len(prayers),1)
        self.assertEqual(prayers[0].proof.result.blessing.actor_id,actor)
        self.assertEqual(len(actor_oath(prayers[0].source,actor).honour_uses),1)
        self.assertFalse(hasattr(result.state.enemy(actor).state,'fate'))
        self.assert_replays(source,result)

    def test_spent_or_unfulfilled_or_broken_oath_cannot_gain_an_activation(self):
        for gm in (context(honour_bound_used_this_session=True),
                replace(context(),combat_tests_fulfil_oath_confirmed=False),
                replace(context(),in_good_standing_confirmed=False)):
            with self.subTest(context=gm):
                source=native_source(pc_talents=(honour(),),pc_context=gm)
                result=run_pc_melee_scenario(source,LiteralD10())
                row=actor_oath(result.state,source.pc_activation_order[0])
                self.assertEqual(row.honour_uses,())
                self.assertFalse(any(HONOUR_BOUND_GLORIOUS_RULE_ID in test.trace.applied_rule_ids
                    for test in real_tests(result)))

    def test_lady_bad_standing_does_not_silently_pray_on_any_turn(self):
        source=native_source(pc_talents=(lady(free=True),),pc_context=lady_context(good=False),rounds=2)
        result=run_pc_melee_scenario(source,LiteralD10())
        self.assertFalse(any(type(step.proof) is PcLadyPrayerProof for step in result.steps))
        row=actor_oath(result.state,source.pc_activation_order[0])
        self.assertTrue(row.lady.oath_barred)
        self.assertFalse(row.lady.available)
        self.assert_replays(source,result)

    def test_paid_pc_prayer_cancels_real_wound_with_ack_and_no_daily_or_fate_cost(self):
        initial=automatic_source(pc_count=1,enemy_count=2,rounds=1)
        actor=initial.pc_activation_order[0]
        member=replace(initial.party[0],talents=(lady(free=True),),oath_context=lady_context())
        weak=GeneratedNpc(3,1,3,3,4,4,initial_generated_weapons(GeneratedWeapon.DAGGER),
            ArmourLoadout(),defence=4)
        strong=replace(weak,strength=6)
        source=replace(initial,party=(member,),enemies=tuple(npc.participant(identifier)
            for npc,identifier in zip((weak,strong),initial.enemy_activation_order,strict=True)))
        result=run_pc_melee_scenario(source,LiteralD10(1))
        completions=[step for step in result.steps if type(step.proof) is PcWoundCompletionProof]
        self.assertEqual(len(completions),1)
        completion=completions[0].proof.completion
        self.assertIs(completion.outcome,CharacterWoundLifecycleOutcome.NEGATED)
        self.assertIsNone(completion.daily_registration)
        self.assertIsNone(completion.fate_burn)
        self.assertIsNone(completion.wound_effect)
        self.assertTrue(completions[0].source.participant(actor).injury.conditions.has(Condition.STAGGERED))
        final=result.state.participant(actor)
        self.assertEqual(final.injury.wounds,())
        self.assertTrue(final.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(final.daily_wounds.wound_count,0)
        self.assertEqual(final.fate,member.fate)
        row=actor_oath(result.state,actor)
        self.assertEqual(len(row.lady_uses),1)
        self.assertEqual(row.lady.negated_wound_id,completion.wound_result.request_id)
        self.assertFalse(row.lady.available)
        acknowledgements=[step.proof for step in result.steps if type(step.proof) is PcOathNegationAckProof]
        self.assertEqual(len(acknowledgements),1)
        self.assertEqual(acknowledgements[0].source.rule_id,completion.wound_result.negated_by_rule_id)
        self.assert_replays(source,result)

    def test_npc_prebattle_blessing_cancels_profile_wound_before_defeat_or_scarab_charge(self):
        original=magic_battle('scarab_knife',pc_strength=6,npc_toughness=3,
            pc_toughness=20,rounds=1,initial_charges=0)
        enemy=original.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(lady(free=True),),
            oath_context=lady_context(prebattle=True))
        source=replace(original,enemies=(npc.participant(enemy.state.actor_id),))
        result=run_pc_melee_scenario(source,LiteralD10(1))
        attacks=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.pc_activation_order[0]]
        self.assertEqual(len(attacks),1)
        wound=attacks[0].proof.execution.resolution.profile_wound
        self.assertIsNotNone(wound)
        self.assertEqual(wound.wounds_inflicted,0)
        self.assertIsNotNone(wound.negated_by_rule_id)
        self.assertFalse(wound.state.defeated)
        final=result.state.enemy(enemy.state.actor_id).state
        self.assertEqual(final.injury.wounds,0)
        self.assertFalse(final.injury.defeated)
        owner=actor_oath(result.state,enemy.state.actor_id)
        self.assertEqual(len(owner.lady_uses),1)
        self.assertEqual(owner.lady.negated_wound_id,wound.request_id)
        self.assertFalse(owner.lady.available)
        self.assertTrue(any(type(step.proof) is PcOathNegationAckProof for step in result.steps))
        self.assertFalse(any(type(step.proof) is PcScarabChargeProof for step in result.steps))
        self.assertEqual(result.state.party[0].weapon_inventory.active.charges,0)
        self.assert_replays(source,result)

    def test_pc_forbidden_shooting_uses_carried_melee_or_real_recover(self):
        for backup in (False,True):
            with self.subTest(backup=backup):
                original=magic_battle('pistol',rounds=1)
                member=original.party[0]
                equipment=member.combat_equipment
                if backup:
                    equipment=(*equipment,PcWeaponItem('backup',PcMeleeWeapon.SWORD,PcItemLocation.CARRIED,None))
                member=replace(member,talents=(honour(),),oath_context=replace(context(),
                    combat_tests_fulfil_oath_confirmed=False),combat_equipment=equipment)
                source=replace(original,party=(member,))
                result=run_pc_melee_scenario(source,LiteralD10())
                attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id==member.actor_id]
                self.assertFalse(any(proof.weapon_intent.attack_skill is Skill.SHOOTING for proof in attacks))
                if backup:
                    self.assertTrue(attacks)
                    self.assertTrue(all(proof.weapon_intent.attack_skill is Skill.MELEE for proof in attacks))
                    self.assertEqual(result.state.participant(member.actor_id).weapon_inventory.active.kind,WeaponKind.SWORD)
                else:
                    self.assertEqual(attacks,[])
                    self.assertEqual(result.executed_actions,2)
                self.assertEqual(actor_oath(result.state,member.actor_id).honour_uses,())
                self.assert_replays(source,result)

    def test_generated_npc_forbidden_shooting_uses_carried_melee_or_real_recover(self):
        for backup in (False,True):
            with self.subTest(backup=backup):
                original=magic_battle('pistol',npc_magic=True,rounds=1)
                enemy=original.enemies[0]
                npc=enemy.definition.generated_components
                weapons=npc.weapons
                if backup:
                    weapons=(*weapons,WeaponItemSource('backup',WeaponKind.SWORD,WeaponItemLocation.CARRIED,None))
                npc=replace(npc,talents=(honour(),),oath_context=replace(context(),
                    combat_tests_fulfil_oath_confirmed=False),weapons=weapons)
                source=replace(original,enemies=(npc.participant(enemy.state.actor_id),))
                result=run_pc_melee_scenario(source,LiteralD10())
                attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id==enemy.state.actor_id]
                self.assertFalse(any(proof.weapon_intent.attack_skill is Skill.SHOOTING for proof in attacks))
                if backup:
                    self.assertTrue(attacks)
                    self.assertTrue(all(proof.weapon_intent.attack_skill is Skill.MELEE for proof in attacks))
                    self.assertEqual(result.state.enemy(enemy.state.actor_id).state.weapon_inventory.active.kind,WeaponKind.SWORD)
                else:
                    self.assertEqual(attacks,[])
                    self.assertEqual(result.executed_actions,2)
                self.assertEqual(actor_oath(result.state,enemy.state.actor_id).honour_uses,())
                self.assert_replays(source,result)

    def test_actual_broken_loses_blessing_and_only_real_flight_breaks_the_confirmed_oath(self):
        for npc_target in (False,True):
            with self.subTest(npc_target=npc_target):
                original=magic_battle('staff',pc_ws=6 if npc_target else 1,
                    npc_ws=1 if npc_target else 6,rounds=2)
                gm=replace(context(lady_prayer_before_battle_confirmed=True,fleeing_breaks_oath=True),
                    combat_tests_fulfil_oath_confirmed=False)
                target=original.enemy_activation_order[0] if npc_target else original.pc_activation_order[0]
                member=original.party[0]
                npc=original.enemies[0].definition.generated_components
                if npc_target:
                    member=replace(member,mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN)
                    npc=replace(npc,talents=(honour(),lady()),oath_context=gm,
                        talent_facts=oath_source().talent_facts)
                else:
                    member=replace(member,talents=(honour(),lady()),oath_context=gm,
                        talent_facts=oath_source().talent_facts)
                    npc=replace(npc,mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN)
                source=replace(original,party=(member,),enemies=(npc.participant(original.enemy_activation_order[0]),),
                    facts=replace(original.facts,unmounted=False))
                result=run_pc_melee_scenario(source,LiteralD10(3))
                broken=next(step for step in result.steps if type(step.proof) is PcAfterGiveGroundProof
                    and step.proof.result.state.conditions.has(Condition.BROKEN))
                after_broken=actor_oath(broken.state,target)
                self.assertFalse(after_broken.lady.available)
                self.assertFalse(after_broken.honour.oath_barred)  # The observed flight is a separate event.
                flights=[step for step in result.steps if type(step.proof) in (PcBrokenMoveProof,PcBrokenRunProof)
                    and step.proof.actor_id==target]
                if npc_target:
                    self.assertTrue(flights)
                    fled=flights[0]
                    self.assertGreater(result.steps.index(fled),result.steps.index(broken))
                    after_flight=actor_oath(fled.state,target)
                    self.assertTrue(after_flight.honour.oath_barred)
                    self.assertTrue(after_flight.lady.oath_barred)
                    self.assertFalse(after_flight.lady.available)
                    self.assertEqual(after_flight.honour_uses,())
                else:
                    # This target's defensive Give Ground already reached a safe
                    # zone; it does not subsequently flee while Broken.
                    self.assertEqual(flights,[])
                    self.assertFalse(actor_oath(result.state,target).honour.oath_barred)
                self.assert_replays(source,result)


if __name__=='__main__':
    unittest.main()
