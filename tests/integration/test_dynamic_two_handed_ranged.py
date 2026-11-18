"""All PG95 two-handed Shooting weapons cross JSON, execution and native replay.

Every roll is literally3: Shooting2 fails, while Dexterity6 and Awareness4
succeed. Strong Protection makes optional repeater fire useful without replacing
the automatic tactic. These are nine short deterministic fights, not Monte Carlo.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.attack_models import DamageImpactSpec
from towr.domain.pc_aim_models import PcAimProof, PcAimConsumptionProof
from towr.domain.pc_battlefield_models import battlefield_range
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeOutcome
from towr.domain.pc_npc_aim_models import PcNpcAimProof, PcNpcAimConsumptionProof
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.ranged_weapon_attack_preparation_models import (
    ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID, OUTSIDE_OPTIMUM_RANGE_RULE_ID,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange as Range
from towr.domain.reload_models import FreeReloadWeaponState
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


# Independent literal PG95 table: weapon, Damage, optimum min/max, ignores
# armour, required Exacting successes after an ordinary or optional-bonus shot.
WEAPONS = (
    ('shortbow', 3, Range.SHORT, Range.MEDIUM, False, None),
    ('warbow', 3, Range.MEDIUM, Range.LONG, False, None),
    ('longbow', 4, Range.MEDIUM, Range.LONG, False, None),
    ('crossbow', 4, Range.SHORT, Range.LONG, False, 2),
    ('handgun', 5, Range.MEDIUM, Range.LONG, True, 3),
    ('blunderbuss', 4, Range.SHORT, Range.SHORT, False, 3),
    ('hochland_long_rifle', 6, Range.MEDIUM, Range.EXTREME, True, 4),
    ('repeater_crossbow', 4, Range.SHORT, Range.MEDIUM, False, 3),
    ('repeater_handgun', 5, Range.SHORT, Range.LONG, True, 5),
)
FREE_BOWS = frozenset(('shortbow', 'warbow', 'longbow'))
FIREARMS = frozenset(('handgun', 'blunderbuss', 'hochland_long_rifle', 'repeater_handgun'))


class AllThrees:
    def __init__(self, value=3):
        self.calls = 0
        self.value = value

    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('these battles use only d10')
        self.calls += 1
        return self.value


def dynamic_document(weapon):
    raw = json.loads(Path('docs/examples/dynamic/equipment.request.json').read_text('utf-8'))
    raw['request_id'] = 'all-2h-ranged:' + weapon
    member = raw['party'][0]
    raw['party'] = [member]
    member['characteristics'] = dict(weapon_skill=2, ballistic_skill=2, strength=3,
        toughness=10, initiative=10, agility=10)
    member['skills'] = dict(melee=2, defence=2, athletics=6, endurance=6,
        shooting=2, dexterity=6, awareness=4)
    member['equipment'] = dict(weapons=[dict(id='ranged:owned', weapon=weapon,
        location='both_hands',**({} if weapon in FREE_BOWS else dict(initially_loaded=True)))], armour=[])
    member['talents'] = []
    member['consumables'] = []
    member['resources'] = dict(fate=0)
    member['ranged'] = dict(ammunition_supply_confirmed=True,
        has_blackpowder_lore=True if weapon in FIREARMS else None,
        has_blackpowder_kit=True if weapon in FIREARMS else None)
    raw['search_space'] = dict(weapon_count=[1], initial_loaded=[True],weapon_skill=[2], strength=[3], toughness=[10], agility=[10],
        melee=[2], defence=[2], athletics=[6], weapon=[weapon], armour=[None],
        shield=[None], abilities=[[]], allowed_talents=[], ballistic_skill=[2], shooting=[2],
        initiative=[10], dexterity=[6], awareness=[4], mount=[None])
    raw['npc_count'] = dict(minimum=1, maximum=1)
    raw['targets'] = dict(win_rate=dict(numerator=1, denominator=2),
        started_rounds=dict(numerator=5, denominator=1))
    raw['search'] = dict(master_seed='42', max_candidates=1, exploration_trials=1,
        finalist_trials=1, top_k=1, max_total_trials=2)
    raw['max_rounds'] = 7
    raw['execution'] = dict(mode='sequential')
    raw['scene'].update(range='medium', two_handed_max_range='long')
    return raw


def native_document(scenario):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='all-2h:replay',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(scenario),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


def receipt_for(proof):
    if type(proof) is PcAttackProof:
        return proof.execution.state.active_turn.action_slots[proof.execution.slot_index - 1].execution
    if type(proof) in (PcAimProof, PcNpcAimProof, PcRangedReloadProof, PcNpcRangedReloadProof):
        return proof.result.slot.execution
    return None


class DynamicTwoHandedRangedTests(unittest.TestCase):
    def test_all_nine_weapons_execute_for_both_sides_and_replay_current_json(self):
        for weapon, damage, minimum, maximum, ignores_armour, reload_target in WEAPONS:
            with self.subTest(weapon=weapon):
                raw = dynamic_document(weapon)
                original = deepcopy(raw)
                command = parse_dynamic_encounter_request(json.dumps(raw))
                self.assertEqual(json.loads(command.source_json), raw)
                npc = command.request.space.sample(Random(42))
                scenario = command.request.scenario((npc,), 'battle:' + weapon)
                pc_ranged = scenario.party[0].pc.ranged
                self.assertEqual(scenario.party[0].combat_equipment[0].initially_loaded,
                    None if weapon in FREE_BOWS else True)
                self.assertTrue(pc_ranged.ammunition_supply_confirmed)
                self.assertEqual(pc_ranged.has_blackpowder_lore, True if weapon in FIREARMS else None)
                self.assertEqual(npc.ranged.has_blackpowder_kit, True if weapon in FIREARMS else None)
                source_copy = deepcopy(scenario)
                encoded = native_document(scenario)
                parsed = parse_pc_melee_simulation_request(json.dumps(encoded)).request.scenario
                self.assertEqual(parsed, scenario)
                self.assertEqual(encoded['scenario']['enemies'][0]['definition']
                    ['generated_components']['weapon'], weapon)
                rng = AllThrees()
                result = run_pc_melee_scenario(parsed, rng)
                self.assertGreater(rng.calls, 0)
                self.assertEqual(raw, original)
                self.assertEqual(scenario, source_copy)
                self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
                self.assertIsNone(result.unsupported)
                self.assertEqual(result.started_rounds, 7)
                # The result constructor replays every complete typed step from
                # the initial source, including one-use shot and Aim owners.
                self.assertEqual(replace(result), result)
                self.assertEqual(native_document(result.source), encoded)
                actors = ('pc', 'generated-npc:1')
                actions = tuple(receipt_for(step.proof) for step in result.steps
                    if receipt_for(step.proof) is not None)
                self.assertEqual(len({action.id for action in actions}), len(actions))
                self.assertEqual(len({(action.actor_id, action.round_number, action.slot_index)
                    for action in actions}), len(actions))
                for step in result.steps:
                    self.assertIsNot(battlefield_range(step.state.battlefield, *actors), Range.CLOSE)
                for actor in actors:
                    shots = tuple((index, step.proof) for index, step in enumerate(result.steps)
                        if type(step.proof) is PcAttackProof and step.proof.request.actor_id == actor)
                    reloads = tuple((index, step.proof) for index, step in enumerate(result.steps)
                        if type(step.proof) in (PcRangedReloadProof, PcNpcRangedReloadProof)
                        and step.proof.request.actor_id == actor)
                    aims = tuple((index, step.proof) for index, step in enumerate(result.steps)
                        if type(step.proof) in (PcAimProof, PcNpcAimProof)
                        and step.proof.request.actor_id == actor)
                    self.assertGreaterEqual(len(shots), 2, actor)
                    for shot_index, attack in shots:
                        shot = attack.ranged_shot if actor == 'pc' else attack.npc_ranged_shot
                        self.assertIsNotNone(shot)
                        profile = shot.preparation.profile
                        self.assertEqual((profile.damage_value, profile.optimum_range_min,
                            profile.optimum_range_max, profile.ignores_armour),
                            (damage, minimum, maximum, ignores_armour))
                        self.assertIs(profile.hands, RangedWeaponHands.TWO_HANDED)
                        source = shot.preparation.source_request
                        self.assertEqual(source.attack.actor_id, actor)
                        self.assertFalse(source.has_enemy_in_close_range)
                        actual = source.target_range
                        self.assertIsNot(actual, Range.CLOSE)
                        self.assertEqual(actual, battlefield_range(result.steps[shot_index].source.battlefield,
                            actor, attack.request.target_id))
                        impact = attack.request.kernel_request.attack.impact_spec
                        self.assertIs(type(impact), DamageImpactSpec)
                        self.assertEqual((impact.damage.base, impact.ignores_armour),
                            (damage, ignores_armour))
                        self.assertIs(attack.protection.source_request.attack_skill, Skill.SHOOTING)
                        self.assertEqual(attack.execution.resolution.attack.attacker_test.successes, 0)
                        self.assertLessEqual(attack.execution.resolution.attack.attacker_test.trace.threshold, 2)
                        outside = not (tuple(Range).index(minimum) <= tuple(Range).index(actual)
                            <= tuple(Range).index(maximum))
                        modifiers = attack.request.kernel_request.attack.attacker_test.dice_modifiers
                        self.assertEqual(tuple(m.amount for m in modifiers
                            if m.rule_id == OUTSIDE_OPTIMUM_RANGE_RULE_ID), (-1,) if outside else ())
                    if reload_target is None:
                        self.assertEqual(len(shots), 7)
                        self.assertFalse(reloads)
                        self.assertTrue(all(type((attack.ranged_shot if actor == 'pc'
                            else attack.npc_ranged_shot).preparation.source_request.weapon_state)
                            is FreeReloadWeaponState for _, attack in shots))
                    else:
                        self.assertTrue(reloads, (weapon, actor))
                        for _, reload in reloads:
                            self.assertEqual(reload.request.weapon_state.required_successes, reload_target)
                            self.assertEqual(reload.result.state.required_successes, reload_target)
                            self.assertFalse(reload.result.previous_state.loaded)
                            self.assertTrue(reload.result.state.loaded)
                            self.assertGreaterEqual(reload.result.exacting.test_result.successes, reload_target)
                        for previous, following in zip(shots, shots[1:]):
                            # A real completed Reload lies between each pair of
                            # bonus/every-shot cycles; no loaded flag is patched.
                            if weapon.startswith('repeater_'):
                                shot = previous[1].ranged_shot if actor == 'pc' else previous[1].npc_ranged_shot
                                if not shot.preparation.source_request.uses_optional_reload_bonus:
                                    continue
                            self.assertTrue(any(previous[0] < index < following[0]
                                and proof.result.state.loaded for index, proof in reloads))
                    if weapon == 'hochland_long_rifle':
                        self.assertGreaterEqual(len(aims), len(shots))
                        used = []
                        for shot_index, attack in shots:
                            shot = attack.ranged_shot if actor == 'pc' else attack.npc_ranged_shot
                            follow_up = shot.preparation.aim_follow_up
                            self.assertIsNotNone(follow_up)
                            self.assertIs(follow_up.outcome, AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
                            aim = follow_up.source_request.aim
                            self.assertTrue(any(index < shot_index and proof.result == aim for index, proof in aims))
                            used.append(aim.request_id)
                            consumption = result.steps[shot_index + 1].proof
                            self.assertIn(type(consumption), (PcAimConsumptionProof, PcNpcAimConsumptionProof))
                            self.assertEqual(consumption.follow_up, follow_up)
                        self.assertEqual(len(used), len(set(used)))
                    else:
                        self.assertFalse(aims)
                self.assertEqual(result.state.participant('pc').fate.spends, ())

    def test_crossbow_short_shots_apply_armoured_damage_bonus_once_for_each_side(self):
        raw = dynamic_document('crossbow')
        raw['scene']['range'] = 'short'
        raw['party'][0]['equipment']['armour'] = [dict(
            id='armour:owned', kind='light_armour', location='worn')]
        raw['search_space']['armour'] = ['light_armour']
        raw['max_rounds'] = 1
        raw['targets']['started_rounds'] = dict(numerator=1, denominator=1)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        npc = command.request.space.sample(Random(42))
        scenario = command.request.scenario((npc,), 'crossbow:armour')
        native = parse_pc_melee_simulation_request(json.dumps(native_document(scenario))).request.scenario
        result = run_pc_melee_scenario(native, AllThrees())
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        shots = tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertEqual(tuple(shot.request.actor_id for shot in shots), ('pc', 'generated-npc:1'))
        for attack in shots:
            shot = attack.ranged_shot or attack.npc_ranged_shot
            self.assertIs(shot.preparation.source_request.target_range, Range.SHORT)
            impact = attack.request.kernel_request.attack.impact_spec
            self.assertTrue(impact.resilience.is_armoured)
            self.assertEqual(impact.damage.base, 4)
            self.assertEqual(tuple((modifier.rule_id, modifier.amount) for modifier in impact.damage_modifiers),
                ((ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID, 1),))
            self.assertFalse(any(modifier.rule_id == OUTSIDE_OPTIMUM_RANGE_RULE_ID
                for modifier in attack.request.kernel_request.attack.attacker_test.dice_modifiers))

    def test_zero_success_hochland_aim_still_allows_the_real_shot_for_each_side(self):
        raw = dynamic_document('hochland_long_rifle')
        raw['max_rounds'] = 2
        raw['targets']['started_rounds'] = dict(numerator=2, denominator=1)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        npc = command.request.space.sample(Random(42))
        scenario = command.request.scenario((npc,), 'hochland:zero-aim')
        # Literal5 fails Awareness4 and Shooting2 but succeeds Protection6.
        result = run_pc_melee_scenario(scenario, AllThrees(5))
        self.assertIs(result.outcome, PcMeleeOutcome.ROUND_LIMIT)
        aims = tuple(step.proof for step in result.steps
            if type(step.proof) in (PcAimProof, PcNpcAimProof))
        shots = tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertEqual(len(aims), 2)
        self.assertEqual(tuple(shot.request.actor_id for shot in shots), ('pc', 'generated-npc:1'))
        for proof in aims:
            self.assertEqual(proof.result.awareness_test_result.successes, 0)
            self.assertEqual(proof.result.bonus.bonus_dice, 0)
        for attack in shots:
            shot = attack.ranged_shot or attack.npc_ranged_shot
            follow_up = shot.preparation.aim_follow_up
            self.assertIs(follow_up.outcome, AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
            self.assertEqual(follow_up.source_request.aim.bonus.bonus_dice, 0)
        self.assertEqual(replace(result), result)

    def test_native_json_rejects_derived_profile_and_conditional_source_forgeries(self):
        for weapon in ('crossbow', 'handgun', 'hochland_long_rifle'):
            raw = dynamic_document(weapon)
            command = parse_dynamic_encounter_request(json.dumps(raw))
            npc = command.request.space.sample(Random(42))
            encoded = native_document(command.request.scenario((npc,), 'closed:' + weapon))
            for change in ('damage', 'awareness', 'mount'):
                forged = deepcopy(encoded)
                definition = forged['scenario']['enemies'][0]['definition']
                if change == 'damage':
                    definition['attack']['damage']['base'] += 1
                elif change == 'awareness':
                    definition['generated_components']['ranged']['awareness'] = None
                else:
                    definition['generated_components']['mount'] = 'horse'
                with self.subTest(weapon=weapon, change=change), self.assertRaises(PcMeleeInputError):
                    parse_pc_melee_simulation_request(json.dumps(forged))


if __name__ == '__main__':
    unittest.main()
