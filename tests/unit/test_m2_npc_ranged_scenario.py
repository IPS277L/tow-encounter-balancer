from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.unit.test_m2_npc_roster import definition, participant
from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_ranged_scenario_models import (
    NpcRangedActorPolicy, NpcRangedScenario, NpcRangedScenarioFacts,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import GiveGroundRequest, TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


def scenario(*, sizes=(2, 2), reverse=False, disposition=NpcDefeatDisposition.KNOCKED_OUT):
    # Numeric ranged excerpt: GM Guide 1.1, Allies and Antagonists / Brigand p97.
    # Explicitly excludes the melee attack and any additional applicable rules.
    profile = definition()
    profile = replace(profile, attacks=(profile.attacks[1],))
    sides = tuple(CombatSide)
    roster = NpcRoster(tuple(participant(f"actor:{side_index}:{index}", profile=profile, side=side)
                            for side_index, (side, size) in enumerate(zip(sides, sizes))
                            for index in range(size)))
    combat = CombatRoundState(1, roster.turn_participants, sides[::-1] if reverse else sides)
    current = NpcRoundRequest("scenario:archers", NpcRosterAttackState(roster), combat,
                              tuple(p.entity_id for p in combat.participants), ())
    spatial = SpatialBattleState(
        ZoneGraph(("zone:0", "zone:1"), (ZoneConnection("zone:0", "zone:1"),)),
        tuple(SpatialEntityPlacement(p.state.actor_id, p.state.side.value,
                                    "zone:0" if p.state.side is sides[0] else "zone:1")
              for p in roster.participants),
    )
    policies = tuple(NpcRangedActorPolicy(
        actor.state.actor_id,
        tuple(p.state.actor_id for p in roster.participants if p.state.side is not actor.state.side),
        tuple(MinionDefeatDecision(actor.state.actor_id, p.state.actor_id, disposition, True)
              for p in roster.participants if p.state.side is not actor.state.side),
    ) for actor in roster.participants)
    return NpcRangedScenario(
        NpcRoundsRequest(current, spatial, 3),
        NpcRangedScenarioFacts(
            target_range=Range.MEDIUM, has_enemy_in_close_range=False, targets_aware=True,
            clear_line_of_sight=True, stationary=True, unmodified_tests=True,
            no_additional_rules=True, ammunition_sufficient=True, requires_reload_action=False,
        ),
        policies, StaggerChoice.SUFFER_WOUND, sides[0],
        NpcDefeatObjective(tuple(p.state.actor_id for p in roster.participants if p.state.side is sides[1])),
    )


def with_roster(source, roster):
    current = replace(source.initial.current, state=replace(source.initial.current.state, roster=roster))
    return replace(source.initial, current=current)


def with_actor(source, *, definition_changes=None, state_changes=None):
    roster = source.initial.current.state.roster
    actor = roster.participants[0]
    profile = replace(actor.definition, id="changed", **(definition_changes or {}))
    actor = replace(actor, definition=profile,
                    state=replace(actor.state, definition_id=profile.id, **(state_changes or {})))
    return with_roster(source, NpcRoster((actor, *roster.participants[1:])))


class M2NpcRangedScenarioTests(unittest.TestCase):
    def test_accepts_multiple_actors_orders_and_explicit_dispositions_without_changing_sources(self):
        for sizes in ((1, 1), (2, 2), (3, 2)):
            for reverse in (False, True):
                for disposition in NpcDefeatDisposition:
                    with self.subTest(sizes=sizes, reverse=reverse, disposition=disposition):
                        source = scenario(sizes=sizes, reverse=reverse, disposition=disposition)
                        before = deepcopy(source)
                        validated = replace(source)
                        self.assertIs(validated.initial, source.initial)
                        self.assertEqual(source, before)
                        self.assertEqual(source.initial.max_rounds, 3)
                        for policy in source.actor_policies:
                            self.assertIs(source.policy_for(policy.actor_id), policy)
                            self.assertTrue(all(d.disposition is disposition for d in policy.defeat_decisions))
                        other = CombatSide.OPPOSITION
                        objective = NpcDefeatObjective(tuple(p.state.actor_id for p in
                            source.initial.current.state.roster.participants if p.state.side is not other))
                        self.assertEqual(replace(source, perspective_side=other, objective=objective).objective,
                                         objective)

    def test_normalizes_lists_and_preserves_supplied_priority_order(self):
        source = scenario()
        original = source.actor_policies[0]
        targets = list(original.target_actor_ids[::-1])
        decisions = list(original.defeat_decisions[::-1])
        policy = replace(original, target_actor_ids=targets, defeat_decisions=decisions)
        policies = [policy, *source.actor_policies[1:]]
        updated = replace(source, actor_policies=policies)
        targets.clear()
        decisions.clear()
        policies.clear()
        self.assertEqual(updated.actor_policies[0].target_actor_ids, original.target_actor_ids[::-1])
        with self.assertRaises(FrozenInstanceError):
            updated.facts = source.facts
        with self.assertRaises(FrozenInstanceError):
            policy.actor_id = "changed"
        with self.assertRaises(ValueError):
            updated.policy_for("absent")

    def test_rejects_every_initial_condition_including_ablaze_and_staggered(self):
        source = scenario()
        for condition in Condition:
            for index in range(4):
                with self.subTest(condition=condition, actor=index):
                    roster = source.initial.current.state.roster
                    actors = list(roster.participants)
                    actor = actors[index]
                    actors[index] = replace(actor, state=replace(actor.state,
                        injury=ProfileInjuryState(0, 1, ConditionState({condition}))))
                    with self.assertRaisesRegex(ValueError, "without Conditions"):
                        replace(source, initial=with_roster(source, NpcRoster(actors)))

    def test_rejects_defeated_and_unavailable_or_inconsistent_equipment(self):
        source = scenario()
        for changes in (
            {"injury": ProfileInjuryState(1, 1, defeated=True)},
            {"available_attack_ids": ()}, {"wields_weapon": False}, {"holds_shield": True},
            {"current_resilience": ResilienceProfile(9)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, initial=with_actor(source, state_changes=changes))

    def test_rejects_unsupported_profiles_effects_and_protection(self):
        source = scenario()
        profile = source.initial.current.state.roster.participants[0].definition
        attack = profile.attacks[0]
        attacks = (
            replace(attack, skill=Skill.MELEE, range_min=Range.CLOSE),
            replace(attack, range_min=Range.SHORT), replace(attack, range_max=Range.MEDIUM),
            replace(attack, hands=Hands.ONE_HANDED), replace(attack, ignores_armour=True),
            replace(attack, damage=DamageProfile(3, 2)),
            replace(attack, test_profile=InlineProfile(3, 3, 4)),
            replace(attack, secondary_effects=(ConditionOnHitSpec(condition=Condition.ABLAZE, rule_id="test:ablaze"),)),
        )
        for attack in attacks:
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, "Shooting profile"):
                replace(source, initial=with_actor(source, definition_changes={"attacks": (attack,)}))
        for protection in ((), (replace(profile.protection[0], skill=Skill.DEFENCE),),
                           (replace(profile.protection[0], test_profile=InlineProfile(3, 2, 4)),)):
            with self.subTest(protection=protection), self.assertRaisesRegex(ValueError, "Protection"):
                replace(source, initial=with_actor(source, definition_changes={"protection": protection}))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            replace(source, initial=with_actor(source, definition_changes={"attacks": definition().attacks}))

    def test_rejects_non_minions_and_roster_entries_outside_the_round(self):
        source = scenario()
        roster = source.initial.current.state.roster
        for policy in (TargetInjuryPolicy.BRUTE, TargetInjuryPolicy.CHAMPION):
            profile = replace(definition(), id="other", injury_policy=policy,
                              wound_limit=2 if policy is TargetInjuryPolicy.BRUTE else None)
            extra = participant("extra", profile=profile)
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "exactly the round"):
                replace(source, initial=with_roster(source, NpcRoster((*roster.participants, extra))))
            # The nested round boundary already refuses an in-round non-Minion.
            actor = roster.participants[0]
            swapped = participant(actor.state.actor_id, profile=profile, side=actor.state.side)
            with self.assertRaisesRegex(ValueError, "Minion"):
                replace(source, initial=with_roster(source, NpcRoster((swapped, *roster.participants[1:]))))

    def test_rejects_pending_histories_used_rounds_and_spatial_usage(self):
        source = scenario()
        current, spatial = source.initial.current, source.initial.spatial_state
        currents = (
            replace(current, pending_follow_ups=(GiveGroundRequest("pending"),)),
            replace(current, state=replace(current.state, consumed_execution_ids=("previous",))),
            replace(current, round_state=replace(current.round_state,
                                                completed_turn_entity_ids=(current.actor_order[0],))),
        )
        for current in currents:
            with self.subTest(current=current), self.assertRaisesRegex(ValueError, "fresh first round"):
                replace(source, initial=replace(source.initial, current=current))
        with self.assertRaisesRegex(ValueError, "fresh first round"):
            replace(source, initial=replace(source.initial,
                current=replace(source.initial.current,
                                round_state=replace(source.initial.current.round_state, round_number=2)),
                spatial_state=replace(spatial, round_number=2)))
        for name in ("gave_ground_entity_ids", "free_move_used_entity_ids", "difficult_terrain_tested_entity_ids"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unused initial spatial"):
                replace(source, initial=replace(source.initial, spatial_state=replace(spatial,
                    **{name: (source.initial.current.actor_order[0],)})))

    def test_rejects_inconsistent_spatial_facts_and_extra_or_missing_placements(self):
        source = scenario()
        spatial = source.initial.spatial_state
        cases = (
            replace(spatial, placements=spatial.placements[:-1]),
            replace(spatial, placements=(*spatial.placements, SpatialEntityPlacement("extra", "other", "zone:0"))),
            replace(spatial, placements=(replace(spatial.placements[0], zone_id="zone:1"), *spatial.placements[1:])),
            replace(spatial, placements=(replace(spatial.placements[0], side_id="wrong"), *spatial.placements[1:])),
            replace(spatial, graph=ZoneGraph(spatial.graph.zone_ids)),
        )
        for spatial in cases:
            with self.subTest(spatial=spatial), self.assertRaises(ValueError):
                replace(source, initial=replace(source.initial, spatial_state=spatial))

    def test_requires_every_actor_and_all_enemy_targets_with_explicit_gm_decisions(self):
        source = scenario()
        first = source.actor_policies[0]
        for decisions in (first.defeat_decisions[:-1], first.defeat_decisions[::-1],
                          (replace(first.defeat_decisions[0], gm_approved=False), *first.defeat_decisions[1:]),
                          (replace(first.defeat_decisions[0], attacker_id="foreign"), *first.defeat_decisions[1:])):
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                replace(first, defeat_decisions=decisions)
        for targets in ((first.target_actor_ids[0],), ("unknown",), ("actor:0:1",)):
            policy = replace(first, target_actor_ids=targets, defeat_decisions=tuple(
                MinionDefeatDecision(first.actor_id, target, NpcDefeatDisposition.KILLED, True) for target in targets))
            with self.subTest(targets=targets), self.assertRaisesRegex(ValueError, "every enemy"):
                replace(source, actor_policies=(policy, *source.actor_policies[1:]))
        for policies in (source.actor_policies[:-1], (first, *source.actor_policies[:-1])):
            with self.assertRaisesRegex(ValueError, "one policy per actor"):
                replace(source, actor_policies=policies)

    def test_rejects_partial_friendly_or_unknown_objectives_and_other_stagger_choices(self):
        source = scenario()
        for targets in (("actor:1:0",), ("actor:0:0", "actor:0:1"), ("unknown",)):
            with self.subTest(targets=targets), self.assertRaisesRegex(ValueError, "all and only"):
                replace(source, objective=NpcDefeatObjective(targets))
        for choice in (StaggerChoice.FALL_PRONE, StaggerChoice.GIVE_GROUND):
            with self.assertRaisesRegex(ValueError, "SUFFER_WOUND"):
                replace(source, repeated_stagger_choice=choice)

    def test_rejects_unsupported_external_facts_and_implicit_boolean_values(self):
        source = scenario()
        for name in ("has_enemy_in_close_range", "targets_aware", "clear_line_of_sight", "stationary",
                     "unmodified_tests", "no_additional_rules", "ammunition_sufficient", "requires_reload_action"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, name):
                    replace(source.facts, **{name: not getattr(source.facts, name)})
                for value in (0, 1, None, "true"):
                    with self.assertRaises(TypeError):
                        replace(source.facts, **{name: value})
        for band in (Range.CLOSE, Range.SHORT, Range.LONG, Range.EXTREME):
            with self.assertRaisesRegex(ValueError, "Medium"):
                replace(source.facts, target_range=band)

    def test_requires_typed_contracts_and_positive_integer_budget(self):
        source = scenario()
        for name, value in (("initial", None), ("facts", None), ("actor_policies", (None,)),
                            ("perspective_side", "opposition"), ("objective", ("actor:1:0",)),
                            ("repeated_stagger_choice", "suffer_wound")):
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(source, **{name: value})
        for limit in (0, -1, True, False, 1.5, "2", None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                replace(source, initial=replace(source.initial, max_rounds=limit))
        with self.assertRaises(TypeError):
            replace(source.actor_policies[0], defeat_decisions=(None,))
        with self.assertRaises(TypeError):
            replace(source.facts, target_range="medium")
