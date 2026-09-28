from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_roster import participant
from tests.unit.test_m6_npc_melee_scenario import definition
from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_mixed_scenario_models import (
    NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_round_weapon_models import NpcRoundWeaponState
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range, RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.resolution_models import GiveGroundRequest, NearbyTargetsStaggerRequest, TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide, CombatTurnState


def bow_definition():
    # GM1.1 Allies and Antagonists / Brigand p97: numeric Shooting only.
    melee = definition()
    return replace(melee, id='bow', source_rule_id='BOOK-GM-GUIDE:1.1:p97:brigand',
                   resilience=ResilienceProfile(3, 1),
                   attacks=(replace(melee.attacks[0], id='warbow', source_rule_id='test:warbow',
                       skill=Skill.SHOOTING, damage=DamageProfile(3), range_min=Range.MEDIUM,
                       range_max=Range.LONG, hands=Hands.TWO_HANDED),),
                   protection=(replace(melee.protection[0], test_profile=InlineProfile(3, 2)),))


def scenario(*, sizes=(3, 2), enemy_bow=False, approved=True,
             disposition=NpcDefeatDisposition.KNOCKED_OUT):
    melee, bow = definition(), bow_definition()
    actors = []
    placements = []
    for side_index, (side, size) in enumerate(zip(CombatSide, sizes)):
        for index in range(size):
            is_bow = index == 0 and (side_index == 0 or enemy_bow)
            actor = participant(f'{side_index}:{index}', profile=bow if is_bow else melee, side=side)
            actors.append(actor)
            placements.append(SpatialEntityPlacement(actor.state.actor_id, side.value,
                              f'rear:{side_index}' if is_bow else 'arena'))
    roster = NpcRoster(actors)
    current = NpcRoundRequest('mixed', NpcRosterAttackState(roster),
                              CombatRoundState(1, roster.turn_participants),
                              tuple(p.state.actor_id for p in actors), ())
    spatial = SpatialBattleState(ZoneGraph(('arena', 'rear:0', 'rear:1', 'empty'), (
        ZoneConnection('arena', 'rear:0'), ZoneConnection('arena', 'rear:1'),
        ZoneConnection('rear:0', 'rear:1'),
    )), placements)
    # Authored fixture: every melee pair is explicitly within arm's reach.
    pairs = tuple(NpcMixedPairRange(a.state.actor_id, b.state.actor_id,
                  Range.CLOSE if a.definition is melee and b.definition is melee else Range.MEDIUM)
                  for a in actors if a.state.side is CombatSide.PLAYERS_AND_ALLIES
                  for b in actors if b.state.side is CombatSide.OPPOSITION)
    policies = tuple(NpcMixedActorPolicy(
        a.state.actor_id, tuple(b.state.actor_id for b in actors if b.state.side is not a.state.side),
        tuple(MinionDefeatDecision(a.state.actor_id, b.state.actor_id, disposition, True)
              for b in actors if b.state.side is not a.state.side), approved, False,
    ) for a in actors)
    return NpcMixedScenario(NpcRoundsRequest(current, spatial, 3),
        NpcMixedScenarioFacts(True, True, True, True, True, True, True, True, True, False),
        pairs, policies, StaggerChoice.SUFFER_WOUND, CombatSide.PLAYERS_AND_ALLIES,
        NpcDefeatObjective(tuple(p.state.actor_id for p in actors if p.state.side is CombatSide.OPPOSITION)))


def with_roster(source, roster):
    current = replace(source.initial.current, state=replace(source.initial.current.state, roster=roster))
    return replace(source.initial, current=current)


def with_actor(source, index=0, *, definition_changes=None, state_changes=None):
    actors = list(source.initial.current.state.roster.participants)
    actor = actors[index]
    profile = replace(actor.definition, id='changed:' + str(index), **(definition_changes or {}))
    actors[index] = replace(actor, definition=profile,
                            state=replace(actor.state, definition_id=profile.id, **(state_changes or {})))
    return with_roster(source, NpcRoster(actors))


class M7NpcMixedScenarioTests(unittest.TestCase):
    def test_valid_sizes_roles_dispositions_and_both_perspectives(self):
        for sizes, enemy_bow in (((2, 1), False), ((3, 2), False), ((2, 2), True)):
            for disposition in NpcDefeatDisposition:
                for approved in (True, False):
                    with self.subTest(sizes=sizes, disposition=disposition, approved=approved):
                        source = scenario(sizes=sizes, enemy_bow=enemy_bow,
                                          disposition=disposition, approved=approved)
                        before = deepcopy(source)
                        self.assertEqual(replace(source), before)
                        for policy in source.actor_policies:
                            self.assertIs(source.policy_for(policy.actor_id), policy)
                            self.assertIs(policy.outnumbering_bonus_approved, approved)
                            self.assertTrue(all(d.disposition is disposition for d in policy.defeat_decisions))
                        other = CombatSide.OPPOSITION
                        objective = NpcDefeatObjective(tuple(p.state.actor_id for p in
                            source.initial.current.state.roster.participants if p.state.side is not other))
                        self.assertEqual(replace(source, perspective_side=other, objective=objective).objective, objective)
                        self.assertEqual(source, before)

    def test_pair_direction_and_all_supplied_orders_are_preserved(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        pairs = tuple(replace(p, first_actor_id=p.second_actor_id, second_actor_id=p.first_actor_id)
                      for p in source.pair_ranges[::-1])
        policies = tuple(replace(p, target_actor_ids=p.target_actor_ids[::-1],
                                  defeat_decisions=p.defeat_decisions[::-1]) for p in source.actor_policies[::-1])
        current, spatial = source.initial.current, source.initial.spatial_state
        changed = replace(source, pair_ranges=pairs, actor_policies=policies,
            initial=replace(source.initial, current=replace(current, actor_order=current.actor_order[::-1]),
                            spatial_state=replace(spatial, placements=spatial.placements[::-1])))
        self.assertEqual(changed.pair_ranges, pairs)
        self.assertEqual(changed.actor_policies, policies)
        self.assertEqual(changed.initial.current.actor_order, current.actor_order[::-1])
        self.assertEqual(changed.initial.spatial_state.placements, spatial.placements[::-1])
        for pair in pairs:
            self.assertIs(changed.range_for(pair.first_actor_id, pair.second_actor_id), pair.target_range)
            self.assertIs(changed.range_for(pair.second_actor_id, pair.first_actor_id), pair.target_range)
        # Enemy archer at Medium may precede the available Close enemy in a melee policy.
        policy = source.policy_for('0:1')
        self.assertIs(source.range_for(policy.actor_id, policy.target_actor_ids[0]), Range.MEDIUM)

    def test_list_inputs_are_copied_and_all_models_are_frozen_slotted(self):
        source = scenario()
        policy = source.actor_policies[0]
        targets, decisions = list(policy.target_actor_ids), list(policy.defeat_decisions)
        copied = replace(policy, target_actor_ids=targets, defeat_decisions=decisions)
        pairs, policies = list(source.pair_ranges), [copied, *source.actor_policies[1:]]
        changed = replace(source, pair_ranges=pairs, actor_policies=policies)
        targets.clear(); decisions.clear(); pairs.clear(); policies.clear()
        self.assertEqual(changed, source)
        for item in (changed, changed.facts, copied, changed.pair_ranges[0]):
            self.assertFalse(hasattr(item, '__dict__'))
            name = fields(item)[0].name
            with self.assertRaises(FrozenInstanceError):
                setattr(item, name, getattr(item, name))

    def test_explicit_fact_booleans_have_no_defaults_or_coercion(self):
        facts = scenario().facts
        with self.assertRaises(TypeError):
            NpcMixedScenarioFacts()
        for field in fields(facts):
            for value in (None, 0, 1, 'true'):
                with self.subTest(field=field.name, value=value), self.assertRaises(TypeError):
                    replace(facts, **{field.name: value})
            with self.assertRaises(ValueError):
                replace(facts, **{field.name: not getattr(facts, field.name)})

    def test_pair_ids_range_types_and_self_pair(self):
        pair = scenario().pair_ranges[0]
        for name in ('first_actor_id', 'second_actor_id'):
            for value in ('', ' ', None, 1):
                with self.assertRaises(ValueError if isinstance(value, str) else TypeError):
                    replace(pair, **{name: value})
        with self.assertRaises(ValueError):
            replace(pair, second_actor_id=pair.first_actor_id)
        for value in ('medium', None, 1):
            with self.assertRaises(TypeError):
                replace(pair, target_range=value)
        for value in (Range.SHORT, Range.LONG, Range.EXTREME):
            with self.assertRaises(ValueError):
                replace(pair, target_range=value)
        self.assertEqual(replace(pair, first_actor_id=' spaced ').first_actor_id, ' spaced ')

    def test_missing_duplicate_reversed_friendly_and_unknown_pairs(self):
        source = scenario()
        first = source.pair_ranges[0]
        cases = ((), source.pair_ranges[:-1], (*source.pair_ranges, first),
                 (*source.pair_ranges, replace(first, first_actor_id=first.second_actor_id,
                                              second_actor_id=first.first_actor_id)),
                 (replace(first, second_actor_id='0:1'), *source.pair_ranges[1:]),
                 (replace(first, second_actor_id='unknown'), *source.pair_ranges[1:]))
        for pairs in cases:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                replace(source, pair_ranges=pairs)
        for a, b in (('0:0', '0:1'), ('0:0', '0:0'), ('0:0', 'unknown')):
            with self.assertRaises(ValueError):
                source.range_for(a, b)
        with self.assertRaises(TypeError):
            source.range_for(None, '0:0')
        with self.assertRaises(ValueError):
            source.policy_for('unknown')

    def test_pair_geometry_requires_explicit_consistent_close_and_medium(self):
        source = scenario()
        # Both directions of inconsistency are rejected; the graph cannot overwrite a fact.
        for index in (0, 2):
            pair = source.pair_ranges[index]
            changed = replace(pair, target_range=Range.CLOSE if pair.target_range is Range.MEDIUM else Range.MEDIUM)
            pairs = list(source.pair_ranges); pairs[index] = changed
            with self.assertRaisesRegex(ValueError, 'Zone'):
                replace(source, pair_ranges=pairs)
        spatial = source.initial.spatial_state
        disconnected = replace(spatial, graph=ZoneGraph(spatial.graph.zone_ids))
        with self.assertRaisesRegex(ValueError, 'adjacent Zones'):
            replace(source, initial=replace(source.initial, spatial_state=disconnected))

    def test_shooter_rejects_any_close_enemy_even_when_first_target_is_medium(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        spatial = source.initial.spatial_state
        # Move only allied bow to arena, explicitly change its E-melee pair to Close.
        placements = tuple(replace(p, zone_id='arena') if p.entity_id == '0:0' else p for p in spatial.placements)
        pairs = tuple(replace(p, target_range=Range.CLOSE) if (p.first_actor_id,p.second_actor_id)==('0:0','1:1')
                      else p for p in source.pair_ranges)
        self.assertEqual(source.policy_for('0:0').target_actor_ids[0], '1:0')
        with self.assertRaisesRegex(ValueError, 'no enemy in Close'):
            replace(source, pair_ranges=pairs, initial=replace(source.initial,
                spatial_state=replace(spatial, placements=placements)))

    def test_melee_requires_initially_reachable_target(self):
        source = scenario()
        spatial = source.initial.spatial_state
        placements = tuple(replace(p, zone_id='rear:0') if p.entity_id=='0:1' else p for p in spatial.placements)
        pairs = tuple(replace(p, target_range=Range.MEDIUM) if p.first_actor_id=='0:1' else p for p in source.pair_ranges)
        with self.assertRaisesRegex(ValueError, 'initially available target'):
            replace(source, pair_ranges=pairs, initial=replace(source.initial,
                spatial_state=replace(spatial, placements=placements)))

    def test_both_attack_roles_are_required(self):
        source = scenario()
        for profile in (definition(), bow_definition()):
            actors = tuple(participant(p.state.actor_id, profile=profile, side=p.state.side)
                           for p in source.initial.current.state.roster.participants)
            with self.assertRaisesRegex(ValueError, 'both Melee and Shooting'):
                replace(source, initial=with_roster(source, NpcRoster(actors)))

    def test_all_initial_conditions_and_wounds_are_rejected_for_both_roles(self):
        source = scenario()
        for index in (0, 1):
            for condition in Condition:
                with self.subTest(index=index, condition=condition), self.assertRaisesRegex(ValueError, 'without Conditions'):
                    replace(source, initial=with_actor(source, index, state_changes={
                        'injury': ProfileInjuryState(0, 1, ConditionState({condition}))}))
            with self.assertRaises(ValueError):
                replace(source, initial=with_actor(source, index, state_changes={
                    'injury': ProfileInjuryState(1, 1, defeated=True)}))

    def test_profiles_reject_extra_attacks_effects_damage_caps_and_ranges(self):
        source = scenario()
        for index in (0, 1):
            profile = source.initial.current.state.roster.participants[index].definition
            attack = profile.attacks[0]
            changes = [dict(ignores_armour=True), dict(damage=DamageProfile(2, 2)),
                       dict(test_profile=InlineProfile(3, 3, 4)),
                       dict(secondary_effects=(ConditionOnHitSpec(rule_id='test:ablaze', condition=Condition.ABLAZE),))]
            changes += ([dict(range_min=Range.SHORT), dict(range_max=Range.MEDIUM), dict(hands=Hands.ONE_HANDED)]
                        if index==0 else [dict(range_max=Range.SHORT)])
            for change in changes:
                with self.subTest(index=index, change=change), self.assertRaises(ValueError):
                    replace(source, initial=with_actor(source,index,definition_changes={'attacks':(replace(attack,**change),)}))
            for attacks, available in (((),()), ((attack,replace(attack,id='extra')),(attack.id,))):
                with self.assertRaisesRegex(ValueError, 'exactly one'):
                    replace(source,initial=with_actor(source,index,definition_changes={'attacks':attacks},
                                                      state_changes={'available_attack_ids':available}))

    def test_only_one_athletics_protection_is_admitted(self):
        source = scenario()
        for index in (0, 1):
            profile = source.initial.current.state.roster.participants[index].definition.protection[0]
            for protection in ((), (replace(profile, skill=Skill.DEFENCE),), (replace(profile,skill=Skill.MELEE),),
                               (profile,replace(profile,skill=Skill.DEFENCE)),
                               (replace(profile,test_profile=InlineProfile(3,3,4)),)):
                with self.assertRaisesRegex(ValueError, 'Athletics Protection'):
                    replace(source,initial=with_actor(source,index,definition_changes={'protection':protection}))

    def test_equipment_availability_and_resilience_are_not_repaired(self):
        source = scenario()
        for index in (0, 1):
            for change in ({'wields_weapon':False}, {'holds_shield':True}, {'available_attack_ids':()},
                           {'current_resilience':ResilienceProfile(9)}):
                with self.assertRaises(ValueError):
                    replace(source, initial=with_actor(source,index,state_changes=change))

    def test_supplied_melee_two_hands_zero_damage_and_numeric_resilience(self):
        source = scenario()
        attack = source.initial.current.state.roster.participants[1].definition.attacks[0]
        changed = replace(source,initial=with_actor(source,1,definition_changes={
            'attacks':(replace(attack,hands=Hands.TWO_HANDED,damage=DamageProfile(0)),),
            'resilience':ResilienceProfile(0)},state_changes={'current_resilience':ResilienceProfile(0)}))
        self.assertIs(changed.initial.current.state.roster.participants[1].definition.attacks[0].hands,Hands.TWO_HANDED)

    def test_policy_booleans_targets_and_gm_decisions_are_explicit(self):
        source = scenario()
        policy = source.actor_policies[0]
        for name in ('outnumbering_bonus_approved','can_leave_zone'):
            for value in (None,0,1,'false'):
                with self.assertRaises(TypeError): replace(policy,**{name:value})
        for name,value in (('actor_id',''),('actor_id',' '),('target_actor_ids',()),
                           ('target_actor_ids',(policy.target_actor_ids[0],)*2),
                           ('defeat_decisions',policy.defeat_decisions[:-1]),
                           ('defeat_decisions',policy.defeat_decisions[::-1]),
                           ('defeat_decisions',(replace(policy.defeat_decisions[0],gm_approved=False),*policy.defeat_decisions[1:])),
                           ('defeat_decisions',(replace(policy.defeat_decisions[0],attacker_id='other'),*policy.defeat_decisions[1:]))):
            with self.subTest(name=name,value=value), self.assertRaises(ValueError):replace(policy,**{name:value})
        for value in (None,1):
            with self.assertRaises(TypeError):replace(policy,actor_id=value)

    def test_all_actor_policies_and_all_enemies_required_including_unreachable(self):
        source = scenario(sizes=(2,2),enemy_bow=True)
        for policies in ((),source.actor_policies[:-1],(*source.actor_policies,source.actor_policies[0])):
            with self.assertRaises(ValueError):replace(source,actor_policies=policies)
        p=source.policy_for('0:1')
        incomplete=replace(p,target_actor_ids=p.target_actor_ids[1:],defeat_decisions=p.defeat_decisions[1:])
        with self.assertRaisesRegex(ValueError,'every enemy'):
            replace(source,actor_policies=tuple(incomplete if x.actor_id==p.actor_id else x for x in source.actor_policies))
        wrong=replace(p,actor_id='unknown',defeat_decisions=tuple(replace(d,attacker_id='unknown') for d in p.defeat_decisions))
        with self.assertRaises(ValueError):replace(source,actor_policies=(wrong,*source.actor_policies[1:]))

    def test_escape_and_gm_withholding_are_preserved_per_actor(self):
        source=scenario()
        policies=tuple(replace(p,can_leave_zone=i%2==0,outnumbering_bonus_approved=i%2!=0)
                       for i,p in enumerate(source.actor_policies))
        changed=replace(source,actor_policies=policies)
        self.assertEqual(changed.actor_policies,policies)
        self.assertFalse(source.actor_policies[0].can_leave_zone)
        self.assertTrue(changed.actor_policies[0].can_leave_zone)

    def test_ordinary_side_order_budgets_types_objective_and_stagger_choice(self):
        source=scenario()
        current=source.initial.current
        for order,error in ((tuple(reversed(tuple(CombatSide))),ValueError),(tuple(s.value for s in CombatSide),TypeError)):
            with self.assertRaises(error):replace(source,initial=replace(source.initial,
                current=replace(current,round_state=replace(current.round_state,side_order=order))))
        for limit in (0,-1,True,1.5,'2',None):
            with self.assertRaises(ValueError):replace(source.initial,max_rounds=limit)
        for name,value in (('initial',None),('facts',None),('perspective_side','opposition'),
                           ('objective',None),('repeated_stagger_choice','suffer_wound')):
            with self.assertRaises(TypeError):replace(source,**{name:value})
        for choice in StaggerChoice:
            if choice is not StaggerChoice.SUFFER_WOUND:
                with self.assertRaises(ValueError):replace(source,repeated_stagger_choice=choice)
        for ids in (('1:0',),('0:0','1:0','1:1'),('unknown',)):
            with self.assertRaises(ValueError):replace(source,objective=NpcDefeatObjective(ids))

    def test_unordered_or_untyped_pair_and_policy_collections(self):
        source=scenario()
        for name,values in (('pair_ranges',source.pair_ranges),('actor_policies',source.actor_policies)):
            for value in (set(values),{},None,'input',(None,)):
                with self.assertRaises(TypeError):replace(source,**{name:value})
        p=source.actor_policies[0]
        for name,values in (('target_actor_ids',p.target_actor_ids),('defeat_decisions',p.defeat_decisions)):
            for value in (set(values),{},None,'input',(None,)):
                with self.assertRaises(TypeError):replace(p,**{name:value})

    def test_used_round_pending_and_histories_are_rejected(self):
        source=scenario();current=source.initial.current;spatial=source.initial.spatial_state
        for updated in (
            replace(current,pending_follow_ups=(GiveGroundRequest('pending'),)),
            replace(current,state=replace(current.state,consumed_execution_ids=('previous',))),
            replace(current,state=replace(current.state,consumed_nearby_stagger_sources=(NearbyTargetsStaggerRequest('old','attack'),))),
            replace(current,round_state=replace(current.round_state,completed_turn_entity_ids=('0:0',))),
            replace(current,round_state=replace(current.round_state,active_turn=CombatTurnState('0:0',CombatSide.PLAYERS_AND_ALLIES))),
        ):
            with self.assertRaisesRegex(ValueError,'fresh first round'):replace(source,initial=replace(source.initial,current=updated))
        with self.assertRaisesRegex(ValueError,'fresh first round'):
            replace(source,initial=replace(source.initial,current=replace(current,
                round_state=replace(current.round_state,round_number=2)),spatial_state=replace(spatial,round_number=2)))
        for name in ('gave_ground_entity_ids','free_move_used_entity_ids','difficult_terrain_tested_entity_ids'):
            with self.assertRaisesRegex(ValueError,'unused initial spatial'):
                replace(source,initial=replace(source.initial,spatial_state=replace(spatial,**{name:('0:0',)})))

    def test_roster_round_and_spatial_members_must_match(self):
        source=scenario();spatial=source.initial.spatial_state
        roster=source.initial.current.state.roster
        extra=participant('extra',profile=definition())
        with self.assertRaisesRegex(ValueError,'exactly the round'):
            replace(source,initial=with_roster(source,NpcRoster((*roster.participants,extra))))
        for placements in (spatial.placements[:-1],(*spatial.placements,SpatialEntityPlacement('extra','other','arena')),
                           (replace(spatial.placements[0],side_id='wrong'),*spatial.placements[1:])):
            with self.assertRaises(ValueError):replace(source,initial=replace(source.initial,
                spatial_state=replace(spatial,placements=placements)))

    def test_weapon_bindings_cannot_enter_a_fresh_mixed_scenario(self):
        source = scenario()
        current = source.initial.current
        weapon = create_initial_ranged_weapon_reload_state('gun', RangedWeaponId.BLUNDERBUSS)
        bound = replace(current, weapons=(NpcRoundWeaponState('0:0', 'warbow', weapon),))
        with self.assertRaisesRegex(ValueError, 'fresh first round'):
            replace(source, initial=replace(source.initial, current=bound))

    def test_nested_round_rejects_non_minions_without_erasing_profile(self):
        source=scenario();roster=source.initial.current.state.roster
        for injury_policy in (TargetInjuryPolicy.BRUTE,TargetInjuryPolicy.CHAMPION):
            profile=replace(definition(),id='other',injury_policy=injury_policy,
                            wound_limit=2 if injury_policy is TargetInjuryPolicy.BRUTE else None)
            actor=participant('0:0',profile=profile,side=CombatSide.PLAYERS_AND_ALLIES)
            with self.assertRaisesRegex(ValueError,'Minion'):
                replace(source,initial=with_roster(source,NpcRoster((actor,*roster.participants[1:]))))

    def test_admission_does_not_execute_rng_or_round_and_leaves_source_unchanged(self):
        source=scenario();before=deepcopy(source)
        with patch('random.Random',side_effect=AssertionError('RNG')), \
             patch('towr.engine.npc_round_coordinator.run_npc_round',side_effect=AssertionError('round')):
            self.assertEqual(replace(source),before)
            with self.assertRaises(ValueError):replace(source,pair_ranges=())
        self.assertEqual(source,before)
