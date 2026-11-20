"""Real K1 Casting/effects over explicitly prepared retained mount bodies.

These observations do not claim a native Dismount prefix or expand the public
Miscast target planner. No controller or Test result is patched.
"""
from dataclasses import dataclass, replace
import unittest

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain.condition_models import Condition
from towr.domain.injury_models import MinionStaggerDefeatOutcome, ProfileWoundResult
from towr.domain.magic_models import MiscastTableEntryId
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, _close_key, with_actor_placement
from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind
from towr.domain.pc_magic_models import (
    PcMagicPending, build_pc_casting_request, guarded_casting_test, complete_pc_casting,
    project_pc_magic_step, build_magic_effect, spell_choice, _spell_target_ids,
)
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_melee_result_models import (
    PcMeleeState, PcFateDecline, initial_pc_melee_state, pc_melee_action_declaration,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.resolution_models import StaggerImpactResult
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionKind, CombatActionSlotRequest, CombatTurnStartRequest,
)
from towr.rules.test_resolution import resolve_test, RerollAllFailures
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


@dataclass(frozen=True)
class PreparedMagic:
    base: object
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
    magic_pending: object = None
    magic_modifiers: tuple = ()
    magic_notes: tuple = ()

    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies
    exited_npc_ids = PcMeleeState.exited_npc_ids

    def __getattr__(self, name):
        return getattr(self.base, name)


def prepared(*, spell=PcSpellId.LIGHTNING_BLAST, kind=CombatMount.DEMIGRYPH,
        barding=(False,), staggered=False):
    original = mount_source(kind)
    wizard = magic_scenario(reason=2, willpower=5, spells=(spell,)).party[0]
    template = original.party[0]
    npc = original.enemies[0].definition.generated_components
    enemies = tuple(replace(npc, armour=replace(npc.armour, barding=armoured)).participant(f'minion{index+1}')
        for index, armoured in enumerate(barding))
    ids = tuple(enemy.state.actor_id for enemy in enemies)
    member = replace(template, wizard=wizard.wizard, talents=wizard.talents,
        pc=replace(template.pc, weapon_skill=1, melee=1), target_priority=ids,
        defeat_decisions=tuple(replace(template.defeat_decisions[0], target_id=target) for target in ids))
    source = replace(original, party=(member,), enemies=enemies, enemy_activation_order=ids,
        battlefield=PcBattlefieldSpec(R.EXTREME, R.LONG),
        facts=replace(original.facts, all_opponents_close=False, daylight_confirmed=True))
    actual = initial_pc_melee_state(source)
    rows = []
    for row in actual.companions:
        injury = row.snapshot.state.injury
        if staggered and row.rider_id in ids:
            injury = replace(injury, conditions=injury.conditions.with_condition(Condition.STAGGERED))
        rows.append(replace(row, retained_since_round=1,
            snapshot=replace(row.snapshot, state=replace(row.snapshot.state, injury=injury))))
    zone = actual.battlefield.spatial.placement_for('pc1').zone_id
    battlefield = replace(actual.battlefield,
        spatial=replace(actual.battlefield.spatial,
            placements=(*actual.battlefield.spatial.placements,
                *(SpatialEntityPlacement(row.snapshot.state.actor_id, row.snapshot.state.side.value, zone)
                    for row in rows))),
        close_pairs=(*actual.battlefield.close_pairs,
            *(_close_key('pc1', row.snapshot.state.actor_id) for row in rows)))
    clock = replace(actual.round_state, round_number=2)
    clock = start_combat_turn(CombatTurnStartRequest('prepared:start', clock, 'pc1')).state
    state = PreparedMagic(actual, actual.party, actual.enemies, tuple(rows),
        tuple(replace(row, mounted=False) for row in actual.mounts), battlefield, clock)
    declaration = pc_melee_action_declaration(state)
    if declaration.kind is not CombatActionKind.IMPROVISE:
        raise AssertionError('the actual Wizard must select Casting at this prepared boundary')
    clock = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve', clock, 'pc1',
        declaration, ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=clock)


def cast(state):
    request = build_pc_casting_request(state)
    rng = ScriptedD10((1, 1))
    test = resolve_test(guarded_casting_test(request.casting_request), rng, decisions=RerollAllFailures())
    rng.assert_exhausted()
    decline = PcFateDecline('pc1', request.casting_request.test.id, 'test',
        state.source.participant('pc1').fate_policy)
    proof = complete_pc_casting(state, test, decline, None)
    return project_pc_magic_step(state, proof), proof


def effect(state):
    rng = ScriptedD10(())
    proof = build_magic_effect(state, rng)
    rng.assert_exhausted()
    return project_pc_magic_step(state, proof), proof


class CompanionMagicTests(unittest.TestCase):
    def test_target_priority_preserves_originals_then_only_live_opposing_bodies(self):
        state = prepared(barding=(False, False))
        self.assertEqual(_spell_target_ids(state, 'pc1'),
            ('minion1', 'minion2', 'minion1:mount', 'minion2:mount'))
        self.assertNotIn('pc1:mount', _spell_target_ids(state, 'pc1'))
        for mode in ('mounted', 'inactive', 'dead'):
            with self.subTest(mode=mode):
                body = next(row for row in state.companions if row.rider_id == 'minion1')
                changed = state
                if mode == 'mounted':
                    changed = replace(state, mounts=tuple(replace(row, mounted=True)
                        if row.actor_id == 'minion1' else row for row in state.mounts))
                else:
                    if mode == 'inactive':
                        body = replace(body, retained_since_round=None)
                    else:
                        body = replace(body, snapshot=replace(body.snapshot, state=replace(body.snapshot.state,
                            injury=replace(body.snapshot.state.injury, wounds=3, defeated=True))))
                    changed = replace(state, companions=tuple(body if row.rider_id == 'minion1' else row
                        for row in state.companions))
                self.assertEqual(_spell_target_ids(changed, 'pc1'), ('minion1', 'minion2', 'minion2:mount'))
        zone = state.battlefield.spatial.placement_for('pc1').zone_id
        tied = replace(state, battlefield=with_actor_placement(state.battlefield, 'minion1', zone))
        self.assertEqual(spell_choice(tied, 'pc1', 2)[1], ('minion1',))

    def test_real_lightning_cast_uses_own_brute_wound_band_and_exact_before_receipt(self):
        before = prepared()
        state, cast_proof = cast(before)
        self.assertEqual(cast_proof.targets.selected_target_id, 'minion1:mount')
        self.assertEqual(state.magic_pending.tasks[0].value, 6)
        self.assertEqual(state.magic_pending.tasks[0].id, cast_proof.targets.follow_ups[0].resolution_id)
        after, proof = effect(state)
        self.assertIs(type(proof.result), ProfileWoundResult)
        self.assertEqual((proof.result.state_change.previous_wounds, proof.result.state_change.current_wounds), (0, 1))
        self.assertIsNone(proof.decision)
        self.assertEqual(proof.previous_injury, pc_actor_injury(state, 'minion1:mount'))
        self.assertEqual(pc_actor_injury(after, 'minion1:mount').wounds, 1)
        self.assertFalse(pc_actor_injury(after, 'minion1:mount').defeated)
        self.assertTrue(pc_actor_injury(after, 'minion1:mount').conditions.has(Condition.DRAINED))
        self.assertFalse(proof.result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(after.party, state.party)
        self.assertEqual(after.enemies, state.enemies)
        self.assertEqual(after.round_state, state.round_state)
        self.assertEqual(after.participant('pc1').fate, before.participant('pc1').fate)
        self.assertFalse(hasattr(after.companions[-1].snapshot.state, 'fate'))
        with self.assertRaises(ValueError):
            project_pc_magic_step(state, replace(proof, previous_injury=None))
        with self.assertRaises(ValueError):
            project_pc_magic_step(after, proof)

    def test_real_fire_breath_freezes_distinct_zone_targets_and_own_barding_damage(self):
        state, cast_proof = cast(prepared(spell=PcSpellId.FIRE_BREATH,
            kind=CombatMount.HORSE, barding=(False, True)))
        self.assertEqual(tuple(task.target_id for task in state.magic_pending.tasks), ('minion1:mount', 'minion2:mount'))
        self.assertEqual(tuple(task.value for task in state.magic_pending.tasks), (4, 3))
        self.assertEqual(len(cast_proof.targets.follow_ups), 2)
        first, proof = effect(state)
        self.assertTrue(pc_actor_injury(first, 'minion1:mount').defeated)
        self.assertEqual(pc_actor_injury(first, 'minion1:mount').wounds, 1)
        self.assertIsNone(proof.decision)
        self.assertEqual(first.round_state, state.round_state)
        # Later geometry cannot retarget the already committed spell tasks.
        zone = first.battlefield.spatial.placement_for('minion2').zone_id
        moved = replace(first, battlefield=with_actor_placement(first.battlefield, 'minion2:mount', zone))
        second, proof = effect(moved)
        self.assertIs(type(proof.result), StaggerImpactResult)
        self.assertEqual(proof.task.target_id, 'minion2:mount')
        self.assertTrue(pc_actor_injury(second, 'minion2:mount').conditions.has(Condition.STAGGERED))
        self.assertFalse(pc_actor_injury(second, 'minion2:mount').defeated)
        self.assertEqual(second.party, state.party)
        self.assertEqual(second.enemies, state.enemies)

    def test_real_fire_breath_repeated_stagger_uses_skeletal_destroyed_without_wound(self):
        state, _ = cast(prepared(spell=PcSpellId.FIRE_BREATH,
            kind=CombatMount.SKELETAL_STEED, barding=(True,), staggered=True))
        after, proof = effect(state)
        self.assertIs(type(proof.result), StaggerImpactResult)
        self.assertIsNone(proof.result.profile_wound)
        self.assertEqual(proof.result.minion_stagger_defeat.cause.rule_id, 'BOOK-GM-GUIDE:1.1:p168:undead-minion')
        self.assertIs(proof.result.minion_stagger_defeat.cause.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual(pc_actor_injury(after, 'minion1:mount').wounds, 0)
        self.assertTrue(pc_actor_injury(after, 'minion1:mount').defeated)
        self.assertIsNone(proof.decision)
        self.assertEqual(after.round_state, state.round_state)

    def test_committed_physical_condition_task_updates_body_only_and_body_cannot_cast(self):
        state = prepared(kind=CombatMount.SKELETAL_STEED)
        task = PcMagicTask('prepared:wind', PcMagicTaskKind.PRONE, 'minion1:mount',
            note=MiscastTableEntryId.UNNATURAL_WIND)
        state = replace(state, magic_pending=PcMagicPending('pc1', 'prepared:miscast', (task,)))
        after, proof = effect(state)
        self.assertFalse(proof.result.blocked)  # Physical forced Prone is not psychological.
        self.assertTrue(pc_actor_injury(after, 'minion1:mount').conditions.has(Condition.PRONE))
        self.assertEqual(after.party, state.party)
        self.assertEqual(after.enemies, state.enemies)
        self.assertEqual(after.magic_modifiers[-1].target_id, 'minion1:mount')
        # An explicit local bad caller cannot cast with a passive profile actor.
        from types import SimpleNamespace
        invalid_clock = SimpleNamespace(active_turn=SimpleNamespace(actor_id='minion1:mount'))
        with self.assertRaises(ValueError):
            build_pc_casting_request(replace(state, round_state=invalid_clock))


if __name__ == '__main__':
    unittest.main()
