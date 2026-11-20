"""Actual K1 shot, prepared companion observations; no native replay claimed."""
from copy import copy
from dataclasses import dataclass, replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_blunderbuss_reaction_sources import prepared_shot, Ones
from tests.unit.test_pc_companion_actor_queries import companion
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_battlefield_models import with_actor_placement
from towr.domain.pc_blunderbuss_models import (
    PcBlunderbussTargetProof, PcBlunderbussProfileProof, PcBlunderbussMinionDefeatProof, PcNearbyDecisions,
    pc_blunderbuss_snapshot, next_pc_blunderbuss_target, pc_blunderbuss_pending_npc_target,
    pc_blunderbuss_profile_decision, project_pc_battlefield_nearby,
)
from towr.domain.pc_mount_models import CombatMount, PcMountedState
from towr.domain.pc_melee_result_models import initial_pc_melee_state, build_pc_melee_attack, PcAttackProof
from towr.domain.pc_npc_ranged_models import complete_pc_npc_ranged_shot
from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
from towr.domain.injury_models import MinionStaggerDefeatOutcome
from towr.domain.condition_models import EffectClassification
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    CombatSide, CombatTurnStartRequest, CombatActionSlotRequest, CombatActionDeclaration,
    CombatActionKind, ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.test_resolution import RerollAllFailures
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


@dataclass(frozen=True)
class PreparedNearbyState:
    """Only local wave projection is exercised, not native source admission."""
    base: object
    companions: tuple
    mounts: tuple
    battlefield: object
    round_state: object
    history: tuple = ()
    pending: tuple = ()
    pending_actor_id: str | None = None
    pending_wound: object = None

    def __getattr__(self, name):
        return getattr(self.base, name)


def with_companions(base, *, mounted=False, retained=1, brute=False, conditions=ConditionState()):
    rows = (companion('pc1', CombatSide.PLAYERS_AND_ALLIES, retained=retained,
                brute=brute, conditions=conditions),
        companion('minion2', CombatSide.OPPOSITION, retained=retained, brute=brute, conditions=conditions))
    primary = 'pc1'
    battlefield = base.battlefield
    zone = battlefield.spatial.placement_for(primary).zone_id
    placements = (*battlefield.spatial.placements, *(SpatialEntityPlacement(row.snapshot.state.actor_id,
        row.snapshot.state.side.value, zone) for row in rows))
    close = (*battlefield.close_pairs, *((primary, row.snapshot.state.actor_id) for row in rows))
    battlefield = replace(battlefield, spatial=replace(battlefield.spatial, placements=placements), close_pairs=close)
    return PreparedNearbyState(base, rows, tuple(PcMountedState(row.rider_id, CombatMount.HORSE, mounted)
        for row in rows), battlefield, base.round_state)


class CompanionBlunderbussTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.shot = prepared_shot()

    def opened(self, **options):
        view = with_companions(self.base, **options)
        snapshot = pc_blunderbuss_snapshot(view, self.shot)
        shot = replace(self.shot, nearby_snapshot=snapshot)
        return replace(view, history=(shot,), pending=(snapshot.request.source,)), snapshot

    def test_snapshot_keeps_actual_sides_and_profiles_without_converting_allies_into_pcs(self):
        view, snapshot = self.opened(brute=True)
        self.assertEqual(snapshot.cluster.target_ids, ('pc1:mount', 'pc2', 'minion2:mount'))
        self.assertEqual(tuple(target.target_id for target in snapshot.request.targets), snapshot.cluster.target_ids)
        for target in snapshot.request.targets:
            with self.subTest(actor=target.target_id):
                if target.target_id.endswith(':mount'):
                    self.assertIs(target.impact.target_policy, TargetInjuryPolicy.BRUTE)
                    self.assertEqual(target.impact.target_state, pc_actor_injury(view, target.target_id))
                    self.assertEqual(target.impact.wound_dice_modifiers, ())
        self.assertIs(view.companions[0].snapshot.state.side, CombatSide.PLAYERS_AND_ALLIES)
        self.assertIs(view.companions[1].snapshot.state.side, CombatSide.OPPOSITION)

    def test_mounted_or_unretained_bodies_are_not_secondary_targets(self):
        for options in (dict(mounted=True), dict(retained=None)):
            with self.subTest(options=options):
                _, snapshot = self.opened(**options)
                self.assertEqual(snapshot.cluster.target_ids, ('pc2',))

    def test_close_links_and_live_body_control_secondary_targets_not_the_side_or_zone_alone(self):
        view = with_companions(self.base)
        ally, enemy = view.companions
        defeated = replace(ally, snapshot=replace(ally.snapshot, state=replace(ally.snapshot.state,
            injury=replace(ally.snapshot.state.injury, wounds=1, defeated=True))))
        defenceless = replace(enemy, snapshot=replace(enemy.snapshot, state=replace(enemy.snapshot.state,
            injury=replace(enemy.snapshot.state.injury,
                conditions=enemy.snapshot.state.injury.conditions.with_condition(Condition.DEFENCELESS)))))
        view = replace(view, companions=(defeated, defenceless))
        self.assertEqual(pc_blunderbuss_snapshot(view, self.shot).cluster.target_ids, ('pc2', 'minion2:mount'))
        zone = view.battlefield.spatial.placement_for('minion2:mount').zone_id
        view = replace(view, battlefield=with_actor_placement(view.battlefield, 'minion2:mount', zone))
        self.assertEqual(pc_blunderbuss_snapshot(view, self.shot).cluster.target_ids, ('pc2',))

    def test_local_wave_updates_the_allied_companion_bank_and_keeps_rider_fate(self):
        view, snapshot = self.opened()
        request = next_pc_blunderbuss_target(view)
        self.assertEqual(request.target_id, 'pc1:mount')
        rng = ScriptedD10([])
        result = resolve_stagger_impact(request, rng, decisions=PcNearbyDecisions())
        rng.assert_exhausted()
        proof = PcBlunderbussTargetProof(self.shot.request.kernel_request.id, request, result)
        after = project_pc_battlefield_nearby(view, proof)
        self.assertTrue(pc_actor_injury(after, 'pc1:mount').conditions.has(Condition.STAGGERED))
        self.assertFalse(pc_actor_injury(view, 'pc1:mount').conditions.has(Condition.STAGGERED))
        self.assertEqual(after.enemies, view.enemies)
        self.assertEqual(after.party, view.party)
        self.assertEqual(after.participant('pc1').fate, view.participant('pc1').fate)
        self.assertFalse(hasattr(after.companions[0].snapshot.state, 'fate'))
        self.assertEqual(next_pc_blunderbuss_target(after).target_id, 'pc2')
        with self.assertRaises(ValueError):
            project_pc_battlefield_nearby(after, proof)

    def test_repeated_stagger_defeats_profile_body_without_disposition_or_nonexistent_turn(self):
        conditions = ConditionState().with_condition(Condition.STAGGERED).with_condition(Condition.PRONE)
        # Wound bands need the real mount source, beyond authored geometry
        # observations. Detachment itself remains an explicit prepared fact.
        from towr.domain.pc_mount_companion_owner import initial_pc_companions
        source=replace(self.base.source,party=(replace(self.base.source.party[0],mount=CombatMount.HORSE),
            *self.base.source.party[1:]),facts=replace(self.base.source.facts,unmounted=False))
        base=copy(self.base); object.__setattr__(base,'source',source)
        view=with_companions(base,conditions=conditions)
        body=initial_pc_companions(source)[0]
        body=replace(body,retained_since_round=1,snapshot=replace(body.snapshot,state=replace(body.snapshot.state,
            injury=replace(body.snapshot.state.injury,conditions=conditions))))
        view=replace(view,companions=(body,view.companions[1]))
        snapshot=pc_blunderbuss_snapshot(view,self.shot)
        shot=replace(self.shot,nearby_snapshot=snapshot)
        view=replace(view,history=(shot,),pending=(snapshot.request.source,))
        request = next_pc_blunderbuss_target(view)
        result = resolve_stagger_impact(request, ScriptedD10([]), decisions=PcNearbyDecisions())
        proof = PcBlunderbussTargetProof(self.shot.request.kernel_request.id, request, result)
        after = project_pc_battlefield_nearby(view, proof)
        target = pc_blunderbuss_pending_npc_target(after)
        self.assertIs(target, proof)
        self.assertTrue(pc_actor_injury(after, 'pc1:mount').defeated)
        self.assertIsNone(pc_blunderbuss_profile_decision(after, target))
        acknowledgement = PcBlunderbussProfileProof(proof.resolution_id, request.target_id,
            result.profile_wound.state_change, None)
        completed = project_pc_battlefield_nearby(after, acknowledgement)
        self.assertEqual(completed.round_state, view.round_state)
        self.assertEqual(completed.pending, ())
        self.assertEqual(completed.party, view.party)
        self.assertEqual(completed.enemies, view.enemies)

    def test_changed_companion_injury_cannot_replace_the_frozen_hit_source(self):
        view, _ = self.opened(brute=True)
        row = view.companions[0]
        changed = replace(row, snapshot=replace(row.snapshot, state=replace(row.snapshot.state,
            injury=replace(row.snapshot.state.injury, wounds=1))))
        forged = replace(view, companions=(changed, view.companions[1]))
        with self.assertRaises(ValueError):
            next_pc_blunderbuss_target(forged)

    def test_actual_skeletal_source_destroys_on_repeated_stagger_without_a_wound_or_fleeing(self):
        # Prepare a genuine shot from a source that really owns a Skeletal
        # Steed. Only the detach/conditions observation is prepared below.
        source = replace(self.base.source, party=(replace(self.base.source.party[0],
            mount=CombatMount.SKELETAL_STEED), *self.base.source.party[1:]),
            facts=replace(self.base.source.facts, unmounted=False))
        base = initial_pc_melee_state(source)
        clock = replace(base.round_state, completed_turn_entity_ids=source.pc_activation_order)
        clock = start_combat_turn(CombatTurnStartRequest('skeletal:start', clock, 'minion1')).state
        clock = reserve_combat_action_slot(CombatActionSlotRequest('skeletal:slot', clock, 'minion1',
            CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)).state
        base = replace(base, round_state=clock)
        intent = build_pc_attack_weapon_intent(base)
        request, protection = build_pc_melee_attack(base, weapon_intent=intent)
        execution = execute_attack_action(request, Ones(), decisions=RerollAllFailures())
        shot = PcAttackProof(request, prepare_protection(protection), execution, None,
            npc_ranged_shot=complete_pc_npc_ranged_shot(base, request, request, execution), weapon_intent=intent)
        row, = base.companions
        row = replace(row, retained_since_round=1, snapshot=replace(row.snapshot,
            state=replace(row.snapshot.state, injury=replace(row.snapshot.state.injury,
                conditions=row.snapshot.state.injury.conditions.with_condition(Condition.STAGGERED)))))
        actor = row.snapshot.state.actor_id
        zone = base.battlefield.spatial.placement_for(row.rider_id).zone_id
        battlefield = replace(base.battlefield, spatial=replace(base.battlefield.spatial,
            placements=(*base.battlefield.spatial.placements,
                SpatialEntityPlacement(actor, row.snapshot.state.side.value, zone))),
            close_pairs=(*base.battlefield.close_pairs, (actor, row.rider_id)))
        view = PreparedNearbyState(base, (row,), (replace(base.mounts[0], mounted=False),),
            battlefield, base.round_state)
        snapshot = pc_blunderbuss_snapshot(view, shot)
        shot = replace(shot, nearby_snapshot=snapshot)
        view = replace(view, history=(shot,), pending=(snapshot.request.source,))
        impact = next_pc_blunderbuss_target(view)
        self.assertEqual(impact.target_id, actor)
        self.assertIs(impact.minion_stagger_defeat.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual(tuple(immunity.classification for immunity in impact.target_effect_immunities),
            (EffectClassification.PSYCHOLOGICAL,))
        self.assertFalse(impact.can_target_leave_zone)
        result = resolve_stagger_impact(impact, ScriptedD10([]), decisions=PcNearbyDecisions())
        self.assertIsNone(result.profile_wound)
        self.assertEqual(result.state.wounds, 0)
        self.assertTrue(result.state.defeated)
        self.assertIs(result.state.defeat_cause.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        target = PcBlunderbussTargetProof(request.kernel_request.id, impact, result)
        after = project_pc_battlefield_nearby(view, target)
        self.assertIs(pc_blunderbuss_pending_npc_target(after), target)
        cause = result.minion_stagger_defeat.cause
        acknowledgement = PcBlunderbussMinionDefeatProof(request.kernel_request.id, actor, cause)
        with self.assertRaises(ValueError):
            replace(acknowledgement, source=replace(cause, outcome=MinionStaggerDefeatOutcome.FLED))
        with self.assertRaises(ValueError):
            project_pc_battlefield_nearby(after,
                replace(acknowledgement, source=replace(cause, source_id='foreign:source')))
        completed = project_pc_battlefield_nearby(after, acknowledgement)
        self.assertEqual(completed.pending, ())
        self.assertEqual(completed.round_state, view.round_state)
        self.assertEqual(completed.party, view.party)
        self.assertEqual(completed.enemies, view.enemies)
        with self.assertRaises(ValueError):
            project_pc_battlefield_nearby(completed, acknowledgement)


if __name__ == '__main__':
    unittest.main()
