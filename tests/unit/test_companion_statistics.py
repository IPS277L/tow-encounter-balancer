"""Prepared source/clock observations; no Monte Carlo or native battle reruns.

The fixtures retain real K1/owner receipts. Prepared clock boundaries do not
claim whole encounter replay, which remains the extraction caller's gate.
"""
from copy import copy, deepcopy
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.unit import test_pc_mount_retention as retention_fixtures
from tests.unit import test_companion_broken_movement as broken_fixtures
from tests.unit import test_companion_landing as landing_fixtures
from tests.unit import test_companion_departure as departure_fixtures
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain import talent_actor_models
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
from towr.domain.pc_back_in_saddle_models import expected_back_in_saddle_move
from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof, battlefield_recovered_injury
from towr.domain.pc_broken_battlefield_models import expected_pc_broken_battlefield_step, project_pc_broken_battlefield
from towr.domain.pc_companion_departure_models import expected_companion_departure, project_companion_departure
from towr.domain.pc_companion_landing_models import expected_companion_landing, project_companion_landing
from towr.domain.pc_companion_turn_models import expected_companion_wait, build_companion_recover
from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
from towr.domain.pc_melee_result_models import PcMeleeStep, initial_pc_melee_state, pc_melee_action_id, pc_melee_round_participants
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnStartRequest, ManoeuvreKind,
)
from towr.rules.turn_resolution import advance_combat_round, reserve_combat_action_slot, start_combat_turn
from towr.simulation.pc_companion_statistics import (
    PcCompanionCount, companion_count_sources, companion_observations,
    sum_companion_counts, validate_companion_counts,
)


def result_view(state):
    initial_clock = initial_pc_melee_state(state.source).round_state
    steps = tuple(SimpleNamespace(proof=proof,source=SimpleNamespace(round_state=initial_clock))
        for proof in state.history)
    return SimpleNamespace(source=state.source,steps=steps,state=state,
        started_rounds=state.round_state.round_number)


def add_round_advance(view):
    previous = replace(view.round_state,active_turn=None,
        completed_turn_entity_ids=tuple(row.entity_id for row in view.round_state.participants),
        excluded_turn_entity_ids=())
    proof = advance_combat_round(CombatRoundAdvanceRequest('prepared:advance',previous,
        pc_melee_round_participants(view)))
    view.history = (*view.history,proof)
    view.round_state = proof.state
    return proof


class CompanionStatisticsTests(unittest.TestCase):
    def setUp(self):
        for name in ('PC_EXECUTABLE_TALENTS','NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models,name,
                getattr(talent_actor_models,name)|{TalentId.BACK_IN_THE_SADDLE}))

    def test_all_initial_mounts_require_source_ordered_zero_rows_even_without_retention(self):
        scenario = mount_source()
        sources = companion_count_sources(scenario)
        self.assertEqual(tuple((row.snapshot.state.actor_id,row.rider_id) for row in sources),
            (('pc1:mount','pc1'),('minion1:mount','minion1')))
        expected = (PcCompanionCount('pc1:mount','pc1'),PcCompanionCount('minion1:mount','minion1'))
        self.assertEqual(companion_observations(result_view(initial_pc_melee_state(scenario))),expected)
        validate_companion_counts(expected,scenario,trials=1,started_rounds=1)
        unmounted = replace(scenario,party=(replace(scenario.party[0],mount=None),),
            enemies=(replace(scenario.enemies[0].definition.generated_components,mount=None).participant('minion1'),),
            facts=replace(scenario.facts,unmounted=True))
        self.assertEqual(companion_count_sources(unmounted),())
        self.assertIsNone(companion_observations(result_view(initial_pc_melee_state(unmounted))))
        validate_companion_counts(None,unmounted,trials=1,started_rounds=1)
        with self.assertRaises(ValueError):
            validate_companion_counts((),unmounted,trials=1,started_rounds=1)

    def test_exact_types_missing_duplicate_foreign_and_reordered_rows_are_rejected(self):
        scenario = mount_source()
        rows = (PcCompanionCount('pc1:mount','pc1'),PcCompanionCount('minion1:mount','minion1'))
        for invalid in (None,(),list(rows),rows[::-1],rows+rows,rows[:1],
                (PcCompanionCount('foreign:mount','foreign'),rows[1])):
            with self.subTest(invalid=invalid),self.assertRaises((TypeError,ValueError)):
                validate_companion_counts(invalid,scenario,trials=1,started_rounds=1)
        for field in fields(PcCompanionCount):
            if field.name in ('actor_id','rider_id'):
                continue
            for value in (True,-1,'0'):
                with self.subTest(field=field.name,value=value),self.assertRaises((TypeError,ValueError)):
                    replace(rows[0],**{field.name:value})
        malformed = deepcopy(rows)
        object.__setattr__(malformed[0],'started_turns',True)
        with self.assertRaises(TypeError):
            validate_companion_counts(malformed,scenario,trials=1,started_rounds=1)
        with self.assertRaises(ValueError):
            PcCompanionCount('pc1','pc1')

    def test_trial_and_aggregate_bounds_follow_own_body_hp_and_actual_turn_counts(self):
        scenario = mount_source()
        first = PcCompanionCount('pc1:mount','pc1',retentions=1,remounts=1,
            eligible_turns=2,started_turns=2,waits=1,recover_actions=1,
            departures=1,wounds_at_end=1,defeats=1)
        rows = (first,PcCompanionCount('minion1:mount','minion1'))
        validate_companion_counts(rows,scenario,trials=1,started_rounds=2)
        for changes in (dict(started_turns=3),dict(eligible_turns=3),dict(movement_actions=1),
                dict(remounts=2),dict(departures=2),dict(wounds_at_end=2),dict(defeats=2)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_companion_counts((replace(first,**changes),rows[1]),scenario,trials=1,started_rounds=2)
        summed = sum_companion_counts((rows,rows),scenario)
        self.assertEqual(summed[0].defeats,2)
        self.assertEqual(summed[0].wounds_at_end,2)
        validate_companion_counts(summed,scenario,trials=2,started_rounds=4)
        with self.assertRaises(ValueError):
            validate_companion_counts(rows,scenario,trials=0,started_rounds=0)
        with self.assertRaises(TypeError):
            validate_companion_counts(rows,scenario,trials=True,started_rounds=2)

    def test_retention_round_and_remount_do_not_create_body_turns_or_actions(self):
        fixture = retention_fixtures.MountRetentionTests()
        state,_ = fixture.retained(distance=RangedWeaponRange.SHORT)
        rows = companion_observations(result_view(state))
        self.assertEqual(rows[0],PcCompanionCount('pc1:mount','pc1',retentions=1))
        start = start_combat_turn(CombatTurnStartRequest(pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1'))
        state = PcMeleeStep(state,start).state
        remount = expected_back_in_saddle_move(state)
        state = PcMeleeStep(state,remount).state
        rows = companion_observations(result_view(state))
        self.assertEqual(rows[0],PcCompanionCount('pc1:mount','pc1',retentions=1,remounts=1))
        self.assertEqual(rows[1],PcCompanionCount('minion1:mount','minion1'))

    def test_actual_next_round_wait_and_recover_are_counted_only_on_the_own_body(self):
        fixture = retention_fixtures.MountRetentionTests()
        for npc in (False,True):
            state,_ = fixture.retained(npc=npc)
            state = fixture.next_round_companion_turn(state,npc=npc)
            state = PcMeleeStep(state,expected_companion_wait(state)).state
            rows = companion_observations(result_view(state))
            index = int(npc)
            self.assertEqual((rows[index].eligible_turns,rows[index].started_turns,rows[index].waits),(1,1,1))
            self.assertEqual(rows[1-index].started_turns,0)
        state,_ = fixture.retained(kind=CombatMount.DEMIGRYPH)
        actor = 'pc1:mount'
        injury = pc_actor_injury(state,actor)
        injury = replace(injury,wounds=1,conditions=injury.conditions.with_condition(Condition.STAGGERED)
            .with_condition(Condition.PRONE).with_condition(Condition.DRAINED))
        state = replace(state,**pc_actor_npc_update(state,actor,injury=injury))
        state = fixture.next_round_companion_turn(state)
        reserve = reserve_combat_action_slot(CombatActionSlotRequest(pc_melee_action_id(state,actor)+':reserve',
            state.round_state,actor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD))
        state = PcMeleeStep(state,reserve).state
        request = build_companion_recover(state)
        result = expected_pc_standard_recover(request)
        recover = PcBattlefieldRecoverProof(request,result,injury,battlefield_recovered_injury(injury,result))
        state = PcMeleeStep(state,recover).state
        rows = companion_observations(result_view(state))
        self.assertEqual(rows[0],PcCompanionCount(actor,'pc1',retentions=1,eligible_turns=1,
            started_turns=1,recover_actions=1,wounds_at_end=1))

    def test_mandatory_broken_run_counts_a_paid_body_movement_without_recover_or_wait(self):
        state,actor = broken_fixtures.CompanionBrokenMovementTests().prepared()
        state.battlefield = replace(state.battlefield,spatial=replace(state.battlefield.spatial,
            free_move_used_entity_ids=(actor,)))
        reserve = reserve_combat_action_slot(CombatActionSlotRequest('prepared:body:run',state.round_state,actor,
            CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=ManoeuvreKind.RUN),ActionSlotGrant.STANDARD))
        state.round_state = reserve.state
        state.history = (*state.history,reserve)
        proof = expected_pc_broken_battlefield_step(state)
        state = broken_fixtures.apply_prepared(state,project_pc_broken_battlefield(state,proof),proof)
        rows = companion_observations(result_view(state))
        self.assertEqual(rows[0],PcCompanionCount(actor,'pc1',retentions=1,eligible_turns=1,
            started_turns=1,movement_actions=1))
        malformed = deepcopy(proof)
        object.__setattr__(malformed.result.slot,'execution',None)
        observed = result_view(state)
        observed.steps = (*observed.steps[:-1],SimpleNamespace(proof=malformed))
        with self.assertRaises(ValueError):
            companion_observations(observed)

    def test_mounted_landing_and_departure_do_not_invent_body_actions_or_turns(self):
        view,rider,body = landing_fixtures.context()
        landing_fixtures.hazard_w1(view,body)
        add_round_advance(view)
        landing_fixtures.started(view,rider)
        proof = expected_companion_landing(view)
        landing_fixtures.append(view,proof,**project_companion_landing(view,proof))
        rows = companion_observations(result_view(view))
        self.assertEqual(rows[0],PcCompanionCount(body,rider,landings=1,wounds_at_end=1))
        view = departure_fixtures.view(npc=True,mounted=True)
        add_round_advance(view)
        departure_fixtures.npc_attack_defeat(view)
        proof = expected_companion_departure(view)
        for name,value in project_companion_departure(view,proof).items():
            setattr(view,name,value)
        view.history = (*view.history,proof)
        rows = companion_observations(result_view(view))
        self.assertEqual(rows[1],PcCompanionCount('minion1:mount','minion1',departures=1))

    def test_missing_round_advance_duplicate_start_wait_and_erased_receipt_are_rejected(self):
        fixture = retention_fixtures.MountRetentionTests()
        state,_ = fixture.retained()
        state = fixture.next_round_companion_turn(state)
        start = state.history[-1]
        waiting = expected_companion_wait(state)
        state = PcMeleeStep(state,waiting).state
        for history in (state.history+(waiting,),state.history+(start,),state.history[1:],
                tuple(proof for proof in state.history if type(proof).__name__!='CombatRoundAdvanceResult')):
            malformed = copy(result_view(state))
            malformed.steps = tuple(SimpleNamespace(proof=proof,source=malformed.steps[0].source) for proof in history)
            with self.subTest(history=history),self.assertRaises((TypeError,ValueError)):
                companion_observations(malformed)

    def test_final_body_wounds_and_defeat_are_separate_from_original_rider_and_npc_totals(self):
        state,_ = retention_fixtures.MountRetentionTests().retained()
        # A complete typed final-body observation, not a manufactured native
        # Wound/ACK prefix. The extraction caller still owns whole replay.
        final = SimpleNamespace(**{name:getattr(state,name) for name in state.__dataclass_fields__})
        row = state.companions[0]
        injury = replace(row.snapshot.state.injury,wounds=1,defeated=True)
        final.companions = (replace(row,snapshot=replace(row.snapshot,state=replace(row.snapshot.state,injury=injury))),
            state.companions[1])
        rows = companion_observations(result_view(final))
        self.assertEqual(rows[0],PcCompanionCount('pc1:mount','pc1',retentions=1,wounds_at_end=1,defeats=1))
        self.assertEqual(rows[1],PcCompanionCount('minion1:mount','minion1'))
        self.assertFalse(state.participant('pc1').injury.dead)
        self.assertFalse(state.enemy('minion1').state.injury.defeated)

    def test_cached_passive_body_attack_or_help_cannot_be_hidden_as_a_zero_observation(self):
        from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof
        state,_ = retention_fixtures.MountRetentionTests().retained()
        for kind in (PcAttackProof,PcHelpProof):
            # Malformed cached input is deliberately negative: an existing
            # proof tag must not turn a passive body into an ordinary actor.
            proof = object.__new__(kind)
            object.__setattr__(proof,'request',SimpleNamespace(actor_id='pc1:mount'))
            result = result_view(state)
            result.steps = (*result.steps,SimpleNamespace(proof=proof))
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                companion_observations(result)


if __name__=='__main__':
    unittest.main()
