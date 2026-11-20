"""Local Skin Wolf wave projections over explicit retained-body observations.

The canonical Skin Wolf and battlefield mount source are deliberately combined
at a prepared boundary. This is not public family admission or a claimed
Dismount/native prefix. K1 resolves the actual standard action and each impact.
"""
from dataclasses import dataclass, replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain.condition_models import Condition
from towr.domain.injury_models import MinionStaggerDefeatOutcome
from towr.domain.magic_models import WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_snapshot
from towr.domain.pc_battlefield_models import _close_key, with_actor_placement
from towr.domain.pc_melee_models import PcMeleeScenario
from towr.domain.pc_melee_result_models import PcMeleeState, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof, PcWarpedFormTargetProof, PcWarpedFormProfileProof,
    PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof, WarpedFormDecisions,
    expected_pc_warped_form_activation, next_warped_form_target,
)
from towr.domain._pc_warped_form_projection import project_warped_form_step
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnState,
)
from towr.domain.undead_minion_models import UNDEAD_MINION_RULE_ID
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.turn_resolution import reserve_combat_action_slot


CASTER = 'skin_wolf1'
BODIES = ('pc1:mount', 'minion1:mount')


class PreparedSource(SimpleNamespace):
    participant = PcMeleeScenario.participant
    enemy = PcMeleeScenario.enemy


@dataclass(frozen=True)
class PreparedWave:
    base: object
    source: object
    party: tuple
    enemies: tuple
    companions: tuple
    mounts: tuple
    battlefield: object
    round_state: object
    history: tuple = ()
    pending: tuple = ()
    pending_wound: object = None
    pending_actor_id: str | None = None
    npc_distractions: tuple = ()
    weighted_nets: tuple = ()

    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies
    exited_npc_ids = PcMeleeState.exited_npc_ids

    def __getattr__(self, name):
        return getattr(self.base, name)


def prepared(*, kind=CombatMount.HORSE, staggered=False, initial_wounds=0):
    original = mount_source(kind)
    base = initial_pc_melee_state(original)
    wolf = create_pc_book_npc(PcBookNpcProfile.SKIN_WOLF, CASTER)
    close = ('minion1', 'pc1')
    policy = PcWarpedFormPolicy(CASTER, close,
        (MinionDefeatDecision(CASTER, 'minion1', NpcDefeatDisposition.KILLED, True),))
    source_values = {name: getattr(original, name) for name in original.__dataclass_fields__}
    source_values.update(enemies=(*original.enemies, wolf),
        enemy_activation_order=(*original.enemy_activation_order, CASTER), npc_warped_form_policies=(policy,))
    source = PreparedSource(**source_values)
    wolf = replace(wolf, state=replace(wolf.state, injury=replace(wolf.state.injury, wounds=1)))
    companions = []
    for row in base.companions:
        injury = row.snapshot.state.injury
        conditions = injury.conditions.with_condition(Condition.STAGGERED) if staggered else injury.conditions
        if kind is CombatMount.DEMIGRYPH and initial_wounds:
            conditions = conditions.with_condition(Condition.DRAINED)
        injury = replace(injury, wounds=initial_wounds, conditions=conditions)
        companions.append(replace(row, retained_since_round=2,
            snapshot=replace(row.snapshot, state=replace(row.snapshot.state, injury=injury))))
    zone = base.battlefield.spatial.placement_for('minion1').zone_id
    placements = (*base.battlefield.spatial.placements,
        SpatialEntityPlacement(CASTER, CombatSide.OPPOSITION.value, zone),
        *(SpatialEntityPlacement(row.snapshot.state.actor_id, row.snapshot.state.side.value, zone)
            for row in companions))
    links = (*base.battlefield.close_pairs,
        *(_close_key(CASTER, actor) for actor in (*close, *BODIES)),
        *(_close_key(row.rider_id, row.snapshot.state.actor_id) for row in companions))
    battlefield = replace(base.battlefield,
        spatial=replace(base.battlefield.spatial, placements=placements), close_pairs=links)
    # The Skin Wolf has really spent one K1 standard Recover slot in this
    # prepared turn; Warped Form itself must neither spend nor reserve one.
    clock = CombatRoundState(2,
        (CombatTurnParticipant('pc1', CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant('minion1', CombatSide.OPPOSITION),
            CombatTurnParticipant(CASTER, CombatSide.OPPOSITION)),
        completed_turn_entity_ids=('pc1', 'minion1'),
        active_turn=CombatTurnState(CASTER, CombatSide.OPPOSITION))
    reserved = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve', clock, CASTER,
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state
    request = RecoverActionExecutionRequest('prepared:recover', reserved, CASTER,
        wolf.state.injury.conditions, True, 1, RecoverMode.STANDARD,
        RecoverStandardChoice(WizardMagicState()))
    rng = ScriptedD10(())
    clock = execute_recover_action(request, rng).round_state
    rng.assert_exhausted()
    return PreparedWave(base, source, base.party, (*base.enemies, wolf), tuple(companions),
        tuple(replace(row, mounted=False) for row in base.mounts), battlefield, clock)


def impact(state):
    request = next_warped_form_target(state)
    if request is None:
        raise AssertionError('expected an actual wave target')
    rng = ScriptedD10(())
    result = resolve_stagger_impact(request, rng, decisions=WarpedFormDecisions())
    rng.assert_exhausted()
    proof = PcWarpedFormTargetProof(request.id.split(':target:')[0], request, result)
    return project_warped_form_step(state, proof), proof


def opened(**options):
    state = prepared(**options)
    activation = expected_pc_warped_form_activation(state)
    state = project_warped_form_step(state, activation)
    # Original source targets retain their order and ordinary rules.
    for actor in ('minion1', 'pc1'):
        if next_warped_form_target(state).target_id != actor:
            raise AssertionError('original wave order changed')
        state, _ = impact(state)
    return state


class CompanionWarpedFormTests(unittest.TestCase):
    def test_snapshot_appends_actual_close_bodies_after_original_order_without_turns_or_fate(self):
        state = prepared(kind=CombatMount.DEMIGRYPH)
        activation = expected_pc_warped_form_activation(state)
        self.assertEqual(activation.target_ids, ('minion1', 'pc1', *BODIES))
        self.assertEqual(state.source.npc_warped_form_policies[0].close_actor_ids, ('minion1', 'pc1'))
        after = project_warped_form_step(state, activation)
        self.assertEqual(after.round_state, state.round_state)
        self.assertEqual(after.party, state.party)
        self.assertEqual(after.companions, state.companions)
        self.assertEqual(after.participant('pc1').fate, state.participant('pc1').fate)
        self.assertFalse(any(hasattr(row.snapshot.state, 'fate') for row in state.companions))
        self.assertEqual(tuple(row.entity_id for row in state.round_state.participants), ('pc1', 'minion1', CASTER))
        with self.assertRaises(ValueError):
            project_warped_form_step(state, replace(activation, target_ids=tuple(reversed(activation.target_ids))))
        with self.assertRaises(ValueError):
            project_warped_form_step(after, activation)

    def test_mounted_inactive_dead_and_same_zone_without_close_are_excluded(self):
        for mode in ('mounted', 'inactive', 'dead', 'short'):
            with self.subTest(mode=mode):
                state = prepared()
                first, second = state.companions
                if mode == 'mounted':
                    state = replace(state, mounts=(replace(state.mounts[0], mounted=True), state.mounts[1]))
                elif mode == 'inactive':
                    state = replace(state, companions=(replace(first, retained_since_round=None), second))
                elif mode == 'dead':
                    snapshot = replace(first.snapshot, state=replace(first.snapshot.state,
                        injury=replace(first.snapshot.state.injury, wounds=1, defeated=True)))
                    state = replace(state, companions=(replace(first, snapshot=snapshot), second))
                else:
                    state = replace(state, battlefield=replace(state.battlefield,
                        close_pairs=tuple(pair for pair in state.battlefield.close_pairs
                            if pair != _close_key(CASTER, BODIES[0]))))
                self.assertEqual(expected_pc_warped_form_activation(state).target_ids,
                    ('minion1', 'pc1', BODIES[1]))

    def test_body_stagger_updates_only_its_own_bank_and_keeps_frozen_target_order(self):
        state = opened(kind=CombatMount.DEMIGRYPH)
        request = next_warped_form_target(state)
        self.assertEqual(request.target_id, BODIES[0])
        self.assertIs(request.target_policy, TargetInjuryPolicy.BRUTE)
        self.assertEqual(request.target_state, pc_actor_injury(state, BODIES[0]))
        self.assertEqual(request.wound_dice_modifiers, ())
        self.assertIsNone(request.first_stagger_wound)
        after, proof = impact(state)
        self.assertEqual(after.party, state.party)
        self.assertEqual(after.enemies, state.enemies)
        self.assertEqual(after.round_state, state.round_state)
        self.assertTrue(pc_actor_injury(after, BODIES[0]).conditions.has(Condition.STAGGERED))
        self.assertFalse(pc_actor_injury(state, BODIES[0]).conditions.has(Condition.STAGGERED))
        self.assertEqual(next_warped_form_target(after).target_id, BODIES[1])
        with self.assertRaises(ValueError):
            project_warped_form_step(after, proof)
        zone = after.battlefield.spatial.placement_for(BODIES[1]).zone_id
        moved_view = replace(after, battlefield=with_actor_placement(after.battlefield, BODIES[1], zone))
        self.assertEqual(next_warped_form_target(moved_view).target_id, BODIES[1])

    def test_demigryph_w1_and_w2_ack_use_own_drained_band_and_no_gm_disposition(self):
        for initial_wounds in (0, 1):
            with self.subTest(initial_wounds=initial_wounds):
                state = opened(kind=CombatMount.DEMIGRYPH, staggered=True, initial_wounds=initial_wounds)
                after, target = impact(state)
                self.assertEqual(pc_actor_injury(after, BODIES[0]).wounds, initial_wounds + 1)
                self.assertEqual(after.pending_actor_id, BODIES[0])
                self.assertIsNone(next_warped_form_target(after))
                source = target.result.profile_wound.state_change
                ack = PcWarpedFormProfileProof(target.activation_id, BODIES[0], source, None)
                settled = project_warped_form_step(after, ack)
                self.assertTrue(pc_actor_injury(settled, BODIES[0]).conditions.has(Condition.DRAINED))
                self.assertEqual(settled.pending, ())
                self.assertEqual(settled.party, after.party)
                self.assertEqual(settled.enemies, after.enemies)
                self.assertEqual(settled.round_state, after.round_state)
                with self.assertRaises(ValueError):
                    project_warped_form_step(settled, ack)

    def test_ordinary_body_defeat_has_no_roster_disposition_or_invented_turn(self):
        state = opened(staggered=True)
        after, target = impact(state)
        self.assertTrue(target.result.profile_wound.state.defeated)
        self.assertEqual(target.result.profile_wound.state.wounds, 1)
        source = target.result.profile_wound.state_change
        ack = PcWarpedFormProfileProof(target.activation_id, BODIES[0], source, None)
        invented = MinionDefeatDecision(CASTER, BODIES[0], NpcDefeatDisposition.KILLED, True)
        with self.assertRaises(ValueError):
            project_warped_form_step(after, replace(ack, decision=invented))
        settled = project_warped_form_step(after, ack)
        self.assertEqual(settled.round_state, after.round_state)
        self.assertEqual(settled.pending, ())
        self.assertEqual(settled.source.npc_warped_form_policies, state.source.npc_warped_form_policies)
        self.assertTrue(pc_actor_injury(settled, BODIES[0]).defeated)

    def test_skeletal_repeated_stagger_is_source_bound_destroyed_with_zero_wounds(self):
        state = opened(kind=CombatMount.SKELETAL_STEED, staggered=True)
        request = next_warped_form_target(state)
        self.assertEqual(request.minion_stagger_defeat.rule_id, UNDEAD_MINION_RULE_ID)
        self.assertIs(request.minion_stagger_defeat.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        after, target = impact(state)
        self.assertIsNone(target.result.profile_wound)
        self.assertIsNone(target.result.character_wound)
        self.assertEqual(pc_actor_injury(after, BODIES[0]).wounds, 0)
        self.assertTrue(pc_actor_injury(after, BODIES[0]).defeated)
        ack = PcWarpedFormMinionDefeatProof(target.activation_id, BODIES[0])
        settled = project_warped_form_step(after, ack)
        self.assertEqual(settled.pending, ())
        self.assertEqual(settled.round_state, after.round_state)
        self.assertEqual(pc_actor_npc_snapshot(settled, BODIES[0]).state.available_attack_ids, ())
        self.assertEqual(pc_actor_injury(settled, BODIES[0]).wounds, 0)
        with self.assertRaises(ValueError):
            project_warped_form_step(settled, ack)
        after, target = impact(settled)
        settled = project_warped_form_step(after,
            PcWarpedFormMinionDefeatProof(target.activation_id, BODIES[1]))
        ended = project_warped_form_step(settled, PcWarpedFormEndProof(target.activation_id))
        self.assertEqual(ended.round_state, state.round_state)
        self.assertEqual(tuple(row.snapshot.state.injury.wounds for row in ended.companions), (0, 0))
        with self.assertRaises(ValueError):
            project_warped_form_step(ended, PcWarpedFormEndProof(target.activation_id))


if __name__ == '__main__':
    unittest.main()
