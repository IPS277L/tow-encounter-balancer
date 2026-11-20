"""Own companion targets at Bash preparation boundaries, without battle rolls.

All immutable actors are admitted original sources. Detached body/HP views are
explicit preparation data, not native retention, target geometry or Bash grants.
"""
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support.magic_weapon_battles import magic_battle
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_npc_snapshot, pc_actor_npc_update
from towr.domain.pc_bash_advice import bash_follow_up_value, bash_weapon_available
from towr.domain.pc_bash_weapon_models import select_bash_weapon
from towr.domain.pc_companion_effect_models import companion_test_request
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.pc_melee_result_models import PcMeleeState, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill
from towr.domain.weapon_effect_preparation import weapon_damage_preparation


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy


def prepared(*, barding=False):
    source = magic_battle('sword', npc_magic=True, pc_weapon='sword', pc_strength=5)
    talent = paid_talent(TalentId.BASH_ATTACK)
    member = replace(source.party[0], mount=CombatMount.HORSE, talents=(talent,),
        armour=ArmourLoadout(barding=barding))
    generated = replace(source.enemies[0].definition.generated_components,
        strength=5, mount=CombatMount.HORSE, talents=(talent,),
        armour=ArmourLoadout(barding=barding))
    source = replace(source, party=(member,),
        enemies=(generated.participant(source.enemy_activation_order[0]),),
        facts=replace(source.facts, unmounted=False))
    initial = initial_pc_melee_state(source)
    state = Preparation(**{name: getattr(initial, name) for name in initial.__dataclass_fields__})
    # These explicit body views test preparation only. Native detachment receipts,
    # movement, active target selection and immediate grants remain separate owners.
    state.mounts = tuple(replace(row, mounted=False) for row in initial.mounts)
    state.companions = tuple(replace(row, retained_since_round=1) for row in initial.companions)
    state.exited_npc_ids = ()
    return state


def matchup(state, npc=False):
    pc, enemy = state.source.pc_activation_order[0], state.source.enemy_activation_order[0]
    return (enemy, pc+':mount') if npc else (pc, enemy+':mount')


def with_body(state, target, **changes):
    following = copy(state)
    snapshot = pc_actor_npc_snapshot(state, target)
    for name, value in pc_actor_npc_update(state, target,
            snapshot=replace(snapshot, state=replace(snapshot.state, **changes))).items():
        setattr(following, name, value)
    return following


class CompanionBashPreparationTests(unittest.TestCase):
    def test_each_original_actor_selects_its_own_melee_against_opposing_profile_body(self):
        for npc in (False, True):
            state = prepared()
            actor, target = matchup(state, npc)
            original = state.enemy(actor).state if npc else state.participant(actor)
            with self.subTest(npc=npc):
                selected = select_bash_weapon(state, actor, target)
                self.assertIsNotNone(selected)
                self.assertEqual(selected.use.actor_id, actor)
                self.assertIs(selected.use.skill, Skill.MELEE)
                self.assertIs(selected.use.inventory, original.weapon_inventory)
                self.assertIsNone(selected.equip)
                self.assertIsNotNone(bash_weapon_available(state, actor, target))
                self.assertEqual(state.history, ())

    def test_same_side_unknown_or_passive_companion_attackers_get_no_permission(self):
        state = prepared()
        pc, enemy = state.source.pc_activation_order[0], state.source.enemy_activation_order[0]
        for actor, target in ((pc, pc+':mount'), (enemy, enemy+':mount'),
                (pc, 'foreign:mount'), (enemy+':mount', pc), (pc+':mount', enemy)):
            with self.subTest(actor=actor, target=target), self.assertRaises(ValueError):
                select_bash_weapon(state, actor, target)
        # Owning a passive animal does not copy its rider's Bash Talent.
        self.assertIsNone(bash_weapon_available(state, pc+':mount', enemy))

    def test_defeated_body_is_not_a_future_attack_and_first_stagger_guard_stays(self):
        for npc in (False, True):
            state = prepared()
            actor, target = matchup(state, npc)
            body = pc_actor_npc_snapshot(state, target).state.injury
            defeated = replace(body, wounds=body.wound_limit, defeated=True)
            following = with_body(state, target, injury=defeated)
            with self.subTest(npc=npc):
                self.assertIsNone(select_bash_weapon(following, actor, target))
                self.assertEqual(bash_follow_up_value(following, actor, target, (0., 1.), (1.,)), 0.)
                for condition in (Condition.STAGGERED, Condition.DEFENCELESS):
                    changed = with_body(state, target,
                        injury=replace(body, conditions=body.conditions.with_condition(condition)))
                    self.assertIsNone(bash_weapon_available(changed, actor, target))

    def test_known_bank_only_or_still_mounted_body_is_not_a_bash_target(self):
        for npc in (False, True):
            state = prepared()
            actor, target = matchup(state, npc)
            body = next(row for row in state.companions if row.snapshot.state.actor_id == target)
            inactive = copy(state)
            inactive.companions = tuple(replace(row, retained_since_round=None)
                if row is body else row for row in state.companions)
            mounted = copy(state)
            mounted.mounts = tuple(replace(row, mounted=True)
                if row.actor_id == body.rider_id else row for row in state.mounts)
            with self.subTest(npc=npc):
                for unavailable in (inactive, mounted):
                    self.assertIsNone(select_bash_weapon(unavailable, actor, target))
                    self.assertEqual(bash_follow_up_value(unavailable, actor, target, (0., 1.), (1.,)), 0.)
                # Detachment this very round is already targetable, even though
                # the body will not receive its own ordinary turn until later.
                self.assertEqual(state.round_state.round_number, body.retained_since_round)
                self.assertIsNotNone(select_bash_weapon(state, actor, target))

    def test_advice_uses_own_body_protection_and_resilience_for_both_sides_without_pc_fate(self):
        for npc in (False, True):
            state = prepared(barding=True)
            actor, target = matchup(state, npc)
            expected = companion_test_request(state, target, 'tactics:bash:protection', Skill.ATHLETICS)
            with self.subTest(npc=npc), \
                    patch('towr.domain.pc_generated_equipment.npc_protection_test', wraps=npc_protection_test) as protection, \
                    patch('towr.domain.weapon_effect_preparation.weapon_damage_preparation', wraps=weapon_damage_preparation) as damage, \
                    patch('towr.domain.pc_shield_models.pc_shield_resilience', side_effect=AssertionError('body is not PC')), \
                    patch('towr.domain.pc_melee_result_models._pc_test', side_effect=AssertionError('body is not PC')):
                value = bash_follow_up_value(state, actor, target, (0., 1.), (1.,))
                self.assertGreater(value, 0.)
                snapshot = pc_actor_npc_snapshot(state, target)
                self.assertEqual(damage.call_args.args[2], snapshot.state.current_resilience)
                protection.assert_called_once_with(state, target, actor, 'tactics:bash:protection',
                    attack_skill=Skill.MELEE)
                _, actual = npc_protection_test(state, target, actor, 'tactics:bash:protection')
                self.assertEqual(actual, expected)
                # The current actual creature's Resilience, including its own
                # Barding, is used rather than the rider's high Toughness20.
                stronger = with_body(state, target,
                    current_resilience=replace(snapshot.state.current_resilience, toughness=20))
                self.assertLess(select_bash_weapon(stronger, actor, target).utility,
                    select_bash_weapon(state, actor, target).utility)
                bash_follow_up_value(stronger, actor, target, (0., 1.), (1.,))
                self.assertEqual(damage.call_args.args[2],
                    pc_actor_npc_snapshot(stronger, target).state.current_resilience)
                self.assertEqual(state.history, ())
                self.assertEqual(state.party, prepared(barding=True).party)

    def test_body_barding_and_drained_modifiers_are_its_own_actual_test_source(self):
        bare, barded = prepared(), prepared(barding=True)
        for npc in (False, True):
            actor, target = matchup(barded, npc)
            _, ordinary = npc_protection_test(bare, target, actor, 'prepared:bare')
            _, armoured = npc_protection_test(barded, target, actor, 'prepared:barded')
            self.assertEqual(ordinary.dice_modifiers, ())
            self.assertEqual(tuple(mod.amount for mod in armoured.dice_modifiers), (-1,))
            body = pc_actor_npc_snapshot(barded, target).state.injury
            drained = with_body(barded, target,
                injury=replace(body, conditions=body.conditions.with_condition(Condition.DRAINED)))
            _, actual = npc_protection_test(drained, target, actor, 'prepared:drained')
            self.assertEqual(tuple(mod.amount for mod in actual.dice_modifiers), (-1,))


if __name__ == '__main__':
    unittest.main()
