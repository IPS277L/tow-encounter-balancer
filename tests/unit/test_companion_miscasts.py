"""Real Casting/Miscast receipts over explicit prepared body observations.

Prepared detachment and geometry do not claim a native dismount history.
The existing PG159 planner retains its supported/unsupported entry boundary.
"""
from dataclasses import replace
from unittest import TestCase, main

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_companion_magic import prepared, effect
from towr.domain.condition_models import Condition
from towr.domain.magic_models import MiscastTableEntryId as Entry
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_battlefield_models import with_actor_placement
from towr.domain.pc_magic_models import (
    PcMiscastRollProof, _miscast_tasks_for_state, build_pc_casting_request, complete_pc_casting,
    guarded_casting_test, pc_magic_unsupported, project_pc_magic_step,
)
from towr.domain.pc_melee_result_models import PcFateDecline, initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.rules.miscast_resolution import resolve_miscast_roll
from towr.rules.test_resolution import resolve_test, RerollAllFailures


def actual_miscast(state, roll):
    member=state.source.party[0]
    source=replace(state.source,party=(replace(member,wizard=replace(member.wizard,reason=len(roll))),))
    initial=initial_pc_melee_state(source)
    state=replace(state,base=initial,party=initial.party)
    request=build_pc_casting_request(state)
    rng=ScriptedD10([9]*len(roll))
    test=resolve_test(guarded_casting_test(request.casting_request),rng,decisions=RerollAllFailures())
    rng.assert_exhausted()
    decline=PcFateDecline('pc1',request.casting_request.test.id,'test',source.party[0].fate_policy)
    casting=complete_pc_casting(state,test,decline,None)
    before=project_pc_magic_step(state,casting)
    request=before.magic_pending.miscast_request
    rng=ScriptedD10(roll)
    result=resolve_miscast_roll(request,before.participant('pc1').magic,rng)
    rng.assert_exhausted()
    proof=PcMiscastRollProof(request,result)
    return before,project_pc_magic_step(before,proof),proof


class CompanionMiscastTests(TestCase):
    def test_real_wind_roll_hits_both_body_sides_once_with_their_own_conditions(self):
        before,after,proof=actual_miscast(prepared(kind=CombatMount.SKELETAL_STEED),(7,7,7))
        self.assertIs(proof.result.entry.id,Entry.UNNATURAL_WIND)
        self.assertEqual(tuple(task.target_id for task in after.magic_pending.tasks),
            ('pc1','pc1:mount','minion1:mount'))
        self.assertNotIn('minion1',tuple(task.target_id for task in after.magic_pending.tasks))
        while after.magic_pending.tasks:
            previous=after
            after,application=effect(after)
            if application.task.target_id.endswith(':mount'):
                self.assertEqual(after.party,previous.party)
                self.assertEqual(after.enemies,previous.enemies)
                self.assertTrue(pc_actor_injury(after,application.task.target_id).conditions.has(Condition.PRONE))
                self.assertEqual(pc_actor_injury(after,application.task.target_id).wounds,0)
        self.assertEqual(after.round_state,before.round_state)
        with self.assertRaises(ValueError): project_pc_magic_step(after,proof)

    def test_range_is_actual_short_distance_and_far_bodies_are_not_silently_hit(self):
        state=prepared(barding=(False,False))
        far=state.battlefield.spatial.placement_for('minion1').zone_id
        state=replace(state,battlefield=with_actor_placement(state.battlefield,'minion2:mount',far))
        for entry in (Entry.HIDEOUS_STENCH,Entry.UNNATURAL_WIND,Entry.EAR_DAMAGE):
            with self.subTest(entry=entry):
                tasks=_miscast_tasks_for_state(state,entry,'actual:scope','pc1')
                targets=tuple(task.target_id for task in tasks)
                self.assertIn('pc1:mount',targets)
                self.assertIn('minion1:mount',targets)
                self.assertNotIn('minion2:mount',targets)
                self.assertNotIn('minion1',targets)
                self.assertNotIn('minion2',targets)

    def test_inactive_mounted_and_defeated_bodies_are_not_separate_subjects(self):
        for mode in ('mounted','inactive','defeated'):
            state=prepared()
            body=next(row for row in state.companions if row.rider_id=='minion1')
            if mode=='mounted':
                state=replace(state,mounts=tuple(replace(row,mounted=True) if row.actor_id=='minion1'
                    else row for row in state.mounts))
                body=replace(body,retained_since_round=None)
            elif mode=='inactive': body=replace(body,retained_since_round=None)
            else:
                injury=replace(body.snapshot.state.injury,wounds=3,defeated=True)
                body=replace(body,snapshot=replace(body.snapshot,state=replace(body.snapshot.state,injury=injury)))
            state=replace(state,companions=tuple(body if row.rider_id=='minion1' else row for row in state.companions))
            with self.subTest(mode=mode):
                targets=tuple(task.target_id for task in _miscast_tasks_for_state(state,Entry.EAR_DAMAGE,'scope','pc1'))
                self.assertNotIn('minion1:mount',targets)

    def test_dead_caster_support_check_can_finish_its_existing_supported_phase(self):
        _,state,_=actual_miscast(prepared(),(10,10,10,10))
        after,proof=effect(state)
        self.assertTrue(after.participant('pc1').injury.dead)
        self.assertFalse(after.magic_pending.tasks)
        self.assertIsNone(pc_magic_unsupported(after))

    def test_existing_gm_dependent_miscast_keeps_its_typed_stop(self):
        _,state,proof=actual_miscast(prepared(),(9,8,8,8))
        self.assertIs(proof.result.entry.id,Entry.ZONE_HAZARD)
        stop=pc_magic_unsupported(state)
        self.assertIsNotNone(stop)
        self.assertEqual(stop.entry_id,Entry.ZONE_HAZARD.value)


if __name__=='__main__': main()
