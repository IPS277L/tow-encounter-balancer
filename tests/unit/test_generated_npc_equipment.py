"""Component-bound NPC equipment, actual protection choices and literal battles."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.attack_models import DamageModifier
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_magic_models import PcMagicModifier
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcShieldHandConflictPolicy, PcShieldLoadout,
    PcShieldRecoveryPolicy, PcWeaponHand, validate_pc_melee_scenario_admission,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, build_pc_melee_attack,
    initial_pc_melee_state,
)
from towr.domain.pc_weapon_models import (
    AXE_ARMOUR_RULE_ID, MORNING_STAR_STAGGERED_RULE_ID, WARHAMMER_STAGGERED_RULE_ID,
)
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatActionKind
from towr.domain.pc_tactical_models import select_pc_tactic
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.test_resolution import resolve_test


def component(weapon=GeneratedWeapon.STAFF, *, weapon_skill=1, strength=3,
              toughness=20, agility=1, melee=4, defence=2, athletics=2,
              light_armour=False, shield=False):
    return GeneratedNpc(weapon_skill, strength, toughness, agility, melee, athletics,
        initial_generated_weapons(weapon), light_loadout(light=light_armour, shield=shield), defence=defence)


def source_for(npc, *, rounds=1):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=rounds)
    member = source.party[0]
    member = replace(member, policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        pc=replace(member.pc, weapon_skill=1, melee=1, defence=1, agility=1,
            athletics=1, strength=1, toughness=20))
    return replace(source, party=(member,), enemies=(npc.participant('minion1'),))


def enemy_conditions(state, *conditions):
    enemy = state.enemy('minion1')
    changed = replace(enemy, state=replace(enemy.state,
        injury=replace(enemy.state.injury, conditions=ConditionState(frozenset(conditions)))))
    return replace(state, enemies=(changed,))


def party_conditions(state, *conditions):
    member = state.participant('pc1')
    return replace(state, party=(replace(member,
        injury=replace(member.injury, conditions=ConditionState(frozenset(conditions)))),))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def attacks(result, actor):
    return tuple(step for step in result.steps
        if type(step.proof) is PcAttackProof and step.proof.request.actor_id == actor)


class GeneratedNpcEquipmentTests(unittest.TestCase):
    def test_lightning_uses_component_shield_as_armour_without_an_attack_test(self):
        from tests.support.pc_magic_scenarios import magic_scenario
        from towr.domain.pc_magic_source_models import PcSpellId
        from towr.domain.pc_magic_models import PcMagicEffectProof
        for shield in (False,True):
            source = magic_scenario(reason=2,willpower=10,level=4,enemies=1,
                spells=(PcSpellId.LIGHTNING_BLAST,))
            npc = component(toughness=5,shield=shield)
            source = replace(source,enemies=(npc.participant('minion1'),))
            with self.subTest(shield=shield):
                result = execute(source,[1,1])
                effects = [step.proof for step in result.steps if type(step.proof) is PcMagicEffectProof
                    and step.proof.task.kind is PcMagicTaskKind.DAMAGE]
                self.assertEqual([effect.task.value for effect in effects],[6+int(shield)])
                self.assertTrue(result.state.enemy('minion1').state.injury.defeated)
                self.assertFalse(any(type(step.proof) is PcAttackProof for step in result.steps))

    def test_fire_breath_uses_each_component_targets_actual_armour(self):
        from tests.support.pc_magic_scenarios import magic_scenario
        from towr.domain.pc_magic_source_models import PcSpellId
        from towr.domain.pc_magic_models import PcMagicEffectProof
        source = magic_scenario(reason=2,willpower=10,level=4,enemies=2,
            spells=(PcSpellId.FIRE_BREATH,))
        source = replace(source,enemies=(component(toughness=3,shield=True).participant('minion1'),
            component(toughness=3).participant('minion2')))
        result = execute(source,[1,1,10,10])
        impacts = [step.proof.task for step in result.steps if type(step.proof) is PcMagicEffectProof
            and step.proof.task.kind is PcMagicTaskKind.DAMAGE]
        self.assertEqual({task.target_id:task.value for task in impacts},{'minion1':3,'minion2':4})
        self.assertEqual(len(impacts),2)
        self.assertTrue(result.state.enemy('minion2').state.injury.defeated)
        self.assertFalse(result.state.enemy('minion1').state.injury.defeated)
        self.assertTrue(result.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))

    def test_derived_weapon_damage_resilience_hands_and_both_skill_profiles(self):
        expected_damage = {
            GeneratedWeapon.STAFF: 3, GeneratedWeapon.DAGGER: 2,
            GeneratedWeapon.AXE: 3, GeneratedWeapon.SWORD: 3,
            GeneratedWeapon.WARHAMMER: 3, GeneratedWeapon.MORNING_STAR: 4,
        }
        for weapon, damage in expected_damage.items():
            for light, shield in ((False,False), (True,False), (False,True), (True,True)):
                with self.subTest(weapon=weapon, light=light, shield=shield):
                    npc = component(weapon, weapon_skill=4, toughness=5, agility=2,
                        defence=6, athletics=3, light_armour=light, shield=shield)
                    enemy = npc.participant('arbitrary-label')
                    self.assertEqual(enemy.definition.generated_components, npc)
                    self.assertEqual(enemy.definition.attacks[0].damage.base, damage)
                    self.assertEqual(enemy.state.current_resilience.total, 5+int(light)+int(shield))
                    self.assertEqual(enemy.state.holds_shield, shield)
                    self.assertTrue(enemy.state.wields_weapon)
                    defence, athletics = enemy.definition.protection
                    self.assertEqual((defence.skill, defence.test_profile),
                        (Skill.DEFENCE, InlineProfile(4,6)))
                    self.assertEqual((athletics.skill, athletics.test_profile),
                        (Skill.ATHLETICS, InlineProfile(2,3)))
        self.assertEqual(component(GeneratedWeapon.DAGGER,strength=1).participant('d').definition.attacks[0].damage.base,0)

    def test_new_component_values_are_exact_and_cannot_be_mutated_through_readmission(self):
        npc = component()
        for field, value in (('defence',True), ('defence',1), ('defence',7)):
            with self.subTest(field=field, value=value), self.assertRaises((TypeError,ValueError)):
                replace(npc, **{field:value})
        for value in (1, 'true'):
            with self.subTest(shield=value), self.assertRaises((TypeError,ValueError)):
                replace(npc, armour=replace(npc.armour, shield=value))
        malformed = deepcopy(npc)
        object.__setattr__(malformed,'defence',True)
        with self.assertRaises((TypeError,ValueError)):
            malformed.participant('bad')

    def test_full_source_rejects_mismatched_components_derived_profiles_and_shield_state(self):
        source = source_for(component(GeneratedWeapon.SWORD,shield=True))
        for kind in ('component','attack','protection','resilience','shield','missing'):
            with self.subTest(kind=kind):
                forged = deepcopy(source)
                enemy = forged.enemies[0]
                definition = enemy.definition
                if kind == 'component':
                    object.__setattr__(definition,'generated_components',
                        replace(definition.generated_components,weapons=initial_generated_weapons(GeneratedWeapon.AXE)))
                elif kind == 'attack':
                    object.__setattr__(definition.attacks[0].damage,'base',30)
                elif kind == 'protection':
                    object.__setattr__(definition.protection[0].test_profile,'threshold',6)
                elif kind == 'resilience':
                    object.__setattr__(definition.resilience,'bonus',0)
                elif kind == 'shield':
                    object.__setattr__(enemy.state,'holds_shield',False)
                else:
                    object.__setattr__(definition,'generated_components',None)
                    object.__setattr__(definition,'protection',(definition.protection[1],))
                with self.assertRaises((TypeError,ValueError)):
                    validate_pc_melee_scenario_admission(forged)

    def test_defence_uses_ws_and_athletics_uses_agility_with_defence_tie_priority(self):
        source = source_for(component(weapon_skill=3,defence=4,agility=2,athletics=6))
        state = tactical_snapshot(source)
        profile, request = npc_protection_test(state,'minion1','pc1','choice:tie')
        self.assertIs(profile.skill,Skill.DEFENCE)  # 3 * .4 == 2 * .6
        self.assertEqual(request.profile,InlineProfile(3,4))
        faster = source_for(component(weapon_skill=1,defence=2,agility=3,athletics=6))
        profile, request = npc_protection_test(tactical_snapshot(faster),'minion1','pc1','choice:athletics')
        self.assertIs(profile.skill,Skill.ATHLETICS)
        self.assertEqual(request.profile,InlineProfile(3,6))

    def test_sword_changes_real_choice_after_stagger_or_drained_and_bonus_is_not_on_athletics(self):
        source = source_for(component(GeneratedWeapon.SWORD,weapon_skill=1,
            defence=5,agility=3,athletics=3))
        state = tactical_snapshot(source)
        profile, test = npc_protection_test(state,'minion1','pc1','choice:sword')
        self.assertIs(profile.skill,Skill.DEFENCE)  # 2 * .5 > 3 * .3
        self.assertEqual(tuple((m.rule_id,m.amount) for m in test.dice_modifiers),
            (('RULE-EQUIPMENT-003:sword-defence',1),))
        for condition in (Condition.STAGGERED,Condition.DRAINED):
            with self.subTest(condition=condition):
                profile, test = npc_protection_test(enemy_conditions(state,condition),
                    'minion1','pc1','choice:changed')
                self.assertIs(profile.skill,Skill.ATHLETICS)
                self.assertFalse(test.dice_modifiers)

    def test_next_test_penalty_is_included_in_choice_before_any_roll_or_consumption(self):
        state = tactical_snapshot(source_for(component(GeneratedWeapon.SWORD,
            weapon_skill=1,defence=5,agility=3,athletics=3)))
        penalty = PcMagicModifier('actual-stench-source','minion1',PcMagicTaskKind.NEXT_TEST_PENALTY)
        state = replace(state,magic_modifiers=(penalty,))
        profile, test = npc_protection_test(state,'minion1','pc1','choice:stench')
        self.assertIs(profile.skill,Skill.ATHLETICS)  # .6 versus .5 after -1d
        self.assertEqual(tuple(m.amount for m in test.dice_modifiers),(-1,))
        self.assertEqual(state.magic_modifiers,(penalty,))

    def test_defenceless_generated_target_has_no_protection_test_or_options(self):
        state = enemy_conditions(tactical_snapshot(source_for(component(GeneratedWeapon.SWORD))),
            Condition.DEFENCELESS)
        request, preparation = build_pc_melee_attack(state)
        self.assertIsNone(request.kernel_request.attack.defender_test)
        self.assertIsNone(preparation.selected_skill)
        self.assertEqual(preparation.options,())

    def test_native_sword_protects_with_a_real_extra_die_and_replay_is_single_use(self):
        source = source_for(component(GeneratedWeapon.SWORD))
        result = execute(source,[10,10,10,10,10])
        attack = attacks(result,'pc1')[0].proof.execution.resolution.attack
        self.assertEqual(attack.defender_test.trace.initial_values,(10,10))
        self.assertEqual(attack.defender_test.trace.rolled_dice,2)
        self.assertIn('RULE-EQUIPMENT-003:sword-defence',attack.defender_test.trace.applied_rule_ids)
        state = initial_pc_melee_state(source)
        for step in result.steps:
            state = apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(state,result.steps[-1])

    def test_native_axe_damage_uses_actual_body_armour_helmet_or_shield(self):
        for armour in ('none','body','helmet','shield'):
            with self.subTest(armour=armour):
                source = source_for(component(GeneratedWeapon.AXE))
                member = source.party[0]
                shield = (PcShieldLoadout(PcWeaponHand.RIGHT,
                    PcShieldHandConflictPolicy.WEAPON_FIRST,
                    PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if armour=='shield' else None)
                source = replace(source,party=(replace(member,
                    pc=replace(member.pc,armour_bonus=int(armour=='body')),
                    armour_worn=armour in ('body','helmet'),shield=shield),))
                result = execute(source,[1,10,1,10])
                step = attacks(result,'minion1')[0]
                attack = step.proof.execution.resolution.attack
                self.assertEqual(attack.damage,4 if armour=='none' else 5)
                self.assertEqual(attack.effective_resilience,20+int(armour in ('body','shield')))
                self.assertEqual(attack.impact_spec.damage_modifiers,
                    () if armour=='none' else (DamageModifier(AXE_ARMOUR_RULE_ID,1,armour_specific=True),))
                if armour=='helmet':
                    forged = deepcopy(step.proof)
                    object.__setattr__(forged.request.kernel_request.attack.impact_spec,
                        'damage_modifiers',())
                    with self.assertRaises(ValueError):
                        PcMeleeStep(step.source,forged)

    def test_native_warhammer_adds_target_bonus_after_the_pc_really_misses(self):
        result = execute(source_for(component(GeneratedWeapon.WARHAMMER)),[10]*5)
        step = attacks(result,'minion1')[0]
        self.assertTrue(step.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        attack = step.proof.execution.resolution.attack
        self.assertEqual(attack.attacker_test.trace.rolled_dice,2)
        self.assertEqual(tuple((m.rule_id,m.amount) for m in
            step.proof.request.kernel_request.attack.attacker_test.dice_modifiers),
            ((WARHAMMER_STAGGERED_RULE_ID,1),))
        fresh = party_conditions(step.source)
        self.assertEqual(build_pc_melee_attack(fresh)[0].kernel_request.attack.attacker_test.dice_modifiers,())
        drained = enemy_conditions(step.source,Condition.DRAINED)
        self.assertEqual(build_pc_melee_attack(drained)[0].kernel_request.attack.attacker_test.dice_modifiers,())

    def test_recover_advice_removes_the_warhammer_bonus_with_the_prospective_stagger(self):
        source = source_for(component(GeneratedWeapon.WARHAMMER))
        source = replace(source,party=(replace(source.party[0],policy=PcMeleePolicy.AUTOMATIC_COMBAT),))
        state = party_conditions(tactical_snapshot(source),Condition.STAGGERED)
        choice = select_pc_tactic(state)
        self.assertIs(choice.action,CombatActionKind.RECOVER)
        # Current hit pressure is 1-(.6*.6)=.64 with Warhammer's second die.
        # After Recover the target is fresh, the bonus is gone and one-die
        # hits only Stagger it: .4 * .5 = .2; the improvement is .44.
        self.assertAlmostEqual(choice.utility,.44)

    def test_native_morning_star_negative_die_survives_drained_and_uses_real_minimum_threshold(self):
        result = execute(source_for(component(GeneratedWeapon.MORNING_STAR),rounds=2),[10]*8)
        first, second = attacks(result,'minion1')
        self.assertFalse(first.proof.request.kernel_request.attack.attacker_test.dice_modifiers)
        test = second.proof.execution.resolution.attack.attacker_test
        self.assertEqual((test.trace.rolled_dice,test.trace.threshold),(1,1))
        self.assertEqual(test.trace.initial_values,(10,))
        self.assertEqual(second.proof.request.kernel_request.attack.impact_spec.damage.base,4)
        state = enemy_conditions(second.source,Condition.STAGGERED,Condition.DRAINED)
        prepared = build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        self.assertEqual(tuple((m.rule_id,m.amount) for m in prepared.dice_modifiers),
            ((MORNING_STAR_STAGGERED_RULE_ID,-1),))
        rng = ScriptedD10([1])
        actual = resolve_test(prepared,rng)
        rng.assert_exhausted()
        self.assertEqual((actual.successes,actual.trace.threshold),(1,1))

    def test_components_keep_their_mechanics_when_definition_identity_changes(self):
        source = source_for(component(GeneratedWeapon.SWORD,shield=True))
        original = source.enemies[0]
        renamed = replace(original,definition=replace(original.definition,id='custom:unlisted-guard'),
            state=replace(original.state,definition_id='custom:unlisted-guard'))
        changed = replace(source,enemies=(renamed,))
        first = execute(source,[10]*5)
        second = execute(changed,[10]*5)
        for actor in ('pc1','minion1'):
            original_attack = attacks(first,actor)[0].proof.execution.resolution.attack
            renamed_attack = attacks(second,actor)[0].proof.execution.resolution.attack
            self.assertEqual(original_attack,renamed_attack)
        self.assertIs(second.outcome,PcMeleeOutcome.ROUND_LIMIT)


if __name__ == '__main__':
    unittest.main()
