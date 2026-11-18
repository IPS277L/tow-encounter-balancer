from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.unit.test_m6_npc_melee_scenario import scenario, with_actor
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest
from towr.domain.npc_melee_scenario_result_models import melee_scenario_candidates
from towr.domain.npc_roster_models import NpcRoster, NpcProtectionProfile
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.domain.test_models import DiceModifier, InlineProfile, Skill
from towr.domain.turn_models import CombatTurnState
from towr.engine.npc_melee_scenario_runner import run_npc_melee_scenario


def context(source):
    current = source.initial.current
    actor = current.state.roster.participants[0]
    combat = replace(current.round_state, active_turn=CombatTurnState(actor.state.actor_id, actor.state.side))
    return NpcAttackSelectionRequest("candidate:probe", current.state, combat, actor.state.actor_id, 1, (), ())


class M6NpcMeleeCandidateTests(unittest.TestCase):
    def test_current_majority_equality_minority_and_explicit_gm_withholding(self):
        for sizes in ((3, 2), (2, 2), (1, 2)):
            for approved in (True, False):
                with self.subTest(sizes=sizes, approved=approved):
                    source = scenario(sizes=sizes, approved=approved)
                    supplied = context(source)
                    result = melee_scenario_candidates(source, supplied, source.initial.spatial_state)
                    expected = ((DiceModifier("RULE-COMBAT-009:outnumbering", 1),)
                                if sizes[0] > sizes[1] and approved else ())
                    self.assertEqual(tuple(c.target_id for c in result), source.actor_policies[0].target_actor_ids)
                    self.assertTrue(all(c.dice_modifiers == expected for c in result))
                    self.assertTrue(all(not option.test.dice_modifiers for c in result for option in c.protection_options))
                    self.assertFalse(supplied.candidates)

    def test_staggered_and_completed_allies_count_but_defenceless_and_defeated_do_not(self):
        source = scenario(sizes=(2, 1))
        supplied = context(source)
        ally = supplied.state.roster.participants[1]
        for condition, defeated, bonus in ((Condition.STAGGERED, False, True),
                                            (Condition.DEFENCELESS, False, False), (None, True, False)):
            # Synthetic current contexts test the counting rule; admission still
            # rejects all initial Conditions. Defenceless is not a supported tactic.
            injury = ProfileInjuryState(1 if defeated else 0, 1,
                ConditionState({condition}) if condition else ConditionState(), defeated=defeated)
            changed = replace(ally, state=replace(ally.state, injury=injury))
            roster = NpcRoster((supplied.state.roster.participants[0], changed, *supplied.state.roster.participants[2:]))
            updated = replace(supplied, state=replace(supplied.state, roster=roster),
                round_state=replace(supplied.round_state, completed_turn_entity_ids=(ally.state.actor_id,)))
            result = melee_scenario_candidates(source, updated, source.initial.spatial_state)
            self.assertEqual(bool(result[0].dice_modifiers), bonus)

    def test_defeated_enemy_is_omitted_and_changes_count_before_turn_exclusion(self):
        source = scenario()
        supplied = context(source)
        roster = supplied.state.roster
        enemy = roster.participants[2]
        defeated = replace(enemy, state=replace(enemy.state, injury=ProfileInjuryState(1, 1, defeated=True)))
        updated = replace(supplied, state=replace(supplied.state,
            roster=NpcRoster((*roster.participants[:2], defeated, roster.participants[3]))))
        before = melee_scenario_candidates(source, updated, source.initial.spatial_state)
        excluded = replace(updated, round_state=replace(updated.round_state, excluded_turn_entity_ids=(enemy.state.actor_id,)))
        after = melee_scenario_candidates(source, excluded, source.initial.spatial_state)
        self.assertEqual(before, after)
        self.assertEqual(tuple(c.target_id for c in before), ("actor:1:1",))
        self.assertEqual(before[0].dice_modifiers, (DiceModifier("RULE-COMBAT-009:outnumbering", 1),))

    def test_supplied_defence_and_can_leave_zone_are_preserved(self):
        source = scenario(sizes=(1, 1))
        enemy = source.initial.current.state.roster.participants[1]
        profile = replace(enemy.definition, id="test:defender", source_rule_id="test:defender",
                          protection=(NpcProtectionProfile("test:defence", Skill.DEFENCE, InlineProfile(4, 3)),))
        enemy = replace(enemy, definition=profile, state=replace(enemy.state, definition_id=profile.id))
        roster = NpcRoster((source.initial.current.state.roster.participants[0], enemy))
        source = replace(source, initial=replace(source.initial, current=replace(source.initial.current,
            state=replace(source.initial.current.state, roster=roster))))
        for can_leave in (True, False):
            source = replace(source, facts=replace(source.facts, can_leave_zone=can_leave))
            candidate, = melee_scenario_candidates(source, context(source), source.initial.spatial_state)
            self.assertIs(candidate.protection_skill, Skill.DEFENCE)
            self.assertEqual(candidate.protection_options[0].test.profile, InlineProfile(4, 3))
            self.assertEqual(candidate.can_target_leave_zone, can_leave)

    def test_bonus_respects_normal_pool_cap_and_is_traced_once(self):
        source = scenario(sizes=(2, 1))
        profile = source.initial.current.state.roster.participants[0].definition
        source = replace(source, initial=with_actor(source, definition_changes={
            "source_rule_id": "test:one-die-pool", "attacks": (replace(profile.attacks[0],
                source_rule_id="test:one-die-attack", test_profile=InlineProfile(1, 3)),),
        }))
        source = replace(source, initial=replace(source.initial, max_rounds=1))
        result = run_npc_melee_scenario(source, Mock(randint=Mock(return_value=10)))
        first = next(action for call in result.runner_report.source_steps if isinstance(call, NpcRoundsResult)
                     for action in call.rounds[0].steps if isinstance(action, NpcRosterAttackExecutionResult))
        trace = first.execution.resolution.attack.attacker_test.trace
        # PG 1.4 Rules / Test Modifiers p107: twice the base Characteristic.
        self.assertEqual((trace.base_dice, trace.regular_dice_delta, trace.rolled_dice), (1, 1, 2))
        self.assertEqual((trace.pool_cap, trace.cap_bypassing_dice), (2, 0))
        self.assertEqual(trace.applied_rule_ids.count("RULE-COMBAT-009:outnumbering"), 1)

    def test_stale_spatial_snapshot_and_untyped_arguments_are_rejected(self):
        source = scenario()
        supplied = context(source)
        spatial = source.initial.spatial_state
        for changed in (replace(spatial, round_number=2),
                        replace(spatial, free_move_used_entity_ids=("actor:0:0",)),
                        replace(spatial, placements=(replace(spatial.placements[0], zone_id="exit"), *spatial.placements[1:]))):
            with self.assertRaisesRegex(ValueError, "stationary spatial"):
                melee_scenario_candidates(source, supplied, changed)
        for args in ((None, supplied, spatial), (source, None, spatial), (source, supplied, None)):
            with self.assertRaises(TypeError):
                melee_scenario_candidates(*args)
