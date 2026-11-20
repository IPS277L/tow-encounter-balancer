"""Free-strike aggregate source boundaries; no Monte Carlo accuracy assertions."""
from copy import copy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario, make_pc_melee_scenario
from tests.support.talent_sources import free_talent, paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.talent_catalog import TalentId
from towr.simulation.pc_immediate_attack_statistics import (
    PcImmediateAttackCount, immediate_attack_count_actors, validate_immediate_attack_counts,
)


def owner_source(*, pc_indices=(0,), npc_indices=(0,), free=False):
    """A genuine admitted source; only run once the runtime Bash cap is ready."""
    source = make_pc_melee_party_scenario(pc_count=2, enemy_count=2, max_rounds=3)
    acquired = free_talent(TalentId.BASH_ATTACK) if free else paid_talent(TalentId.BASH_ATTACK)
    party = tuple(replace(member, pc=replace(member.pc, strength=5, brawn=4),
        talents=(acquired,) if index in pc_indices else ()) for index, member in enumerate(source.party))
    enemies = tuple(GeneratedNpc(3, 5, 3, 3, 4, 4,
        initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(), defence=4, brawn=4,
        talents=(acquired,) if index in npc_indices else ()).participant(enemy.state.actor_id)
        for index, enemy in enumerate(source.enemies))
    return replace(source, party=party, enemies=enemies)


def prepared_observations(*, trials=2, owners=True, scenario=None):
    """Honest aggregate fixtures, not claimed native journals or MC samples."""
    from towr.domain.pc_melee_result_models import PcMeleeOutcome
    from towr.simulation.pc_melee_models import (
        PcAllyRecoverActionCount, PcGloriousSpendCount, PcHelpActionCount,
        PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord,
        PcNearMissBurnCount, PcNpcExitCount, PcNpcExtraAttackCount, PcNpcHelpActionCount,
        PcNpcRecoverActionCount, PcNpcWarpedFormCount,
    )
    if scenario is None:
        scenario = owner_source(pc_indices=(0,), npc_indices=(0,)) if owners else (
            make_pc_melee_party_scenario(pc_count=2, enemy_count=2))
    scenario = replace(scenario, max_rounds=1)
    request = PcMeleeSimulationRequest(scenario, 42, trials)
    pc_ids = scenario.pc_activation_order
    npc_ids = scenario.enemy_activation_order
    actors = immediate_attack_count_actors(scenario)
    immediate = tuple(PcImmediateAttackCount(actor, 1) for actor in actors) if actors else None
    records = tuple(PcMeleeTrialRecord(scenario, index, request.seed_for(index), PcMeleeOutcome.ROUND_LIMIT,
        executed_actions=len(pc_ids)+len(npc_ids), started_rounds=1, completed_rounds=1, defeated_pc_ids=(),
        near_miss_burn_counts=tuple(PcNearMissBurnCount(actor, 0) for actor in pc_ids),
        glorious_spend_counts=tuple(PcGloriousSpendCount(actor, 0) for actor in pc_ids),
        help_action_counts=tuple(PcHelpActionCount(actor, 0) for actor in pc_ids),
        ally_recover_action_counts=tuple(PcAllyRecoverActionCount(actor, 0) for actor in pc_ids),
        npc_exit_counts=tuple(PcNpcExitCount(actor, 0) for actor in npc_ids),
        npc_help_action_counts=tuple(PcNpcHelpActionCount(actor, 0) for actor in npc_ids),
        npc_extra_attack_counts=tuple(PcNpcExtraAttackCount(actor, 0) for actor in npc_ids),
        npc_recover_action_counts=tuple(PcNpcRecoverActionCount(actor, 0) for actor in npc_ids),
        npc_warped_form_counts=tuple(PcNpcWarpedFormCount(actor, 0) for actor in npc_ids),
        immediate_attack_counts=immediate) for index in range(trials))
    return PcMeleeSimulationResult(request, records)


class ImmediateAttackCountRowTests(unittest.TestCase):
    def test_row_is_exact_immutable_nonnegative_and_pickle_safe(self):
        for count in (0, 1, 100):
            with self.subTest(count=count):
                row = PcImmediateAttackCount('actor', count)
                self.assertEqual(pickle.loads(pickle.dumps(row)), row)
                with self.assertRaises(FrozenInstanceError):
                    row.count = 1
        for actor in ('', '  ', None, 1, True):
            with self.subTest(actor=actor), self.assertRaises(TypeError):
                PcImmediateAttackCount(actor, 0)
        for count in (True, False, 1.0, '1', None):
            with self.subTest(count=count), self.assertRaises(TypeError):
                PcImmediateAttackCount('actor', count)
        with self.assertRaises(ValueError):
            PcImmediateAttackCount('actor', -1)

    def test_source_without_owners_requires_none_even_if_all_supplied_counts_are_zero(self):
        source = make_pc_melee_scenario(enemy_count=1)
        self.assertEqual(immediate_attack_count_actors(source), ())
        validate_immediate_attack_counts(None, source, started_rounds=1, actions=0)
        for counts in ((), [], (PcImmediateAttackCount('pc', 0),)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                validate_immediate_attack_counts(counts, source, started_rounds=1, actions=0)

    def test_round_and_action_budgets_require_exact_nonnegative_integers(self):
        source = make_pc_melee_scenario(enemy_count=1)
        for name in ('started_rounds', 'actions'):
            for value in (True, False, 1.0, None, -1):
                arguments = dict(started_rounds=1, actions=0)
                arguments[name] = value
                with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                    validate_immediate_attack_counts(None, source, **arguments)


class ImmediateAttackOwnerSourceTests(unittest.TestCase):
    def test_owners_are_actual_acquisitions_in_pc_then_npc_source_order(self):
        source = owner_source(pc_indices=(0, 1), npc_indices=(0, 1))
        actors = (*source.pc_activation_order, *source.enemy_activation_order)
        self.assertEqual(immediate_attack_count_actors(source), actors)
        rows = tuple(PcImmediateAttackCount(actor, 0) for actor in actors)
        validate_immediate_attack_counts(rows, source, started_rounds=1, actions=0)
        self.assertTrue(all(member.fate is not None for member in source.party))
        self.assertTrue(all(not hasattr(enemy.state, 'fate') for enemy in source.enemies))
        self.assertEqual(immediate_attack_count_actors(owner_source(pc_indices=(1,), npc_indices=(0,), free=True)),
            (source.party[1].actor_id, source.enemies[0].state.actor_id))

    def test_missing_foreign_duplicate_reordered_and_noncanonical_rows_are_rejected(self):
        source = owner_source()
        actors = immediate_attack_count_actors(source)
        rows = tuple(PcImmediateAttackCount(actor, 0) for actor in actors)
        invalid = (None, (), [], rows[:1], rows[::-1], rows * 2,
            (PcImmediateAttackCount('foreign', 0), *rows[1:]), tuple((row.actor_id, row.count) for row in rows))
        for counts in invalid:
            with self.subTest(counts=counts), self.assertRaises((TypeError, ValueError)):
                validate_immediate_attack_counts(counts, source, started_rounds=1, actions=0)
        malformed = copy(rows[0])
        object.__setattr__(malformed, 'count', True)
        with self.assertRaises(TypeError):
            validate_immediate_attack_counts((malformed, *rows[1:]), source, started_rounds=1, actions=1)

    def test_each_bash_needs_its_own_round_and_ordinary_source_action_without_counting_as_one(self):
        source = owner_source()
        pc, npc = immediate_attack_count_actors(source)
        rows = (PcImmediateAttackCount(pc, 1), PcImmediateAttackCount(npc, 1))
        # Two ordinary Brawn actions can grant two strikes: no fake third or
        # fourth action is required, and validating never changes the source.
        validate_immediate_attack_counts(rows, source, started_rounds=1, actions=2)
        with self.assertRaises(ValueError):
            validate_immediate_attack_counts(rows, source, started_rounds=1, actions=1)
        with self.assertRaises(ValueError):
            validate_immediate_attack_counts((PcImmediateAttackCount(pc, 2), rows[1]), source,
                started_rounds=1, actions=3)
        validate_immediate_attack_counts((PcImmediateAttackCount(pc, 3), PcImmediateAttackCount(npc, 2)), source,
            started_rounds=3, actions=5)

    def test_no_owner_can_borrow_a_count_from_another_source_or_an_unrelated_talent(self):
        source = owner_source(pc_indices=(0,), npc_indices=())
        actor, = immediate_attack_count_actors(source)
        rows = (PcImmediateAttackCount(actor, 1),)
        without = replace(source, party=tuple(replace(member, talents=()) for member in source.party))
        with self.assertRaises(ValueError):
            validate_immediate_attack_counts(rows, without, started_rounds=1, actions=1)
        other = replace(without, party=(replace(without.party[0],
            talents=(paid_talent(TalentId.MIGHTY_BLOW),)), without.party[1]))
        self.assertEqual(immediate_attack_count_actors(other), ())
        with self.assertRaises(ValueError):
            validate_immediate_attack_counts(rows, other, started_rounds=1, actions=1)

    def test_prepared_trial_and_summary_aggregate_without_changing_ordinary_actions(self):
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        result = prepared_observations()
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(result.total_action_count, 8)
        self.assertEqual(summary.total_action_count, 8)
        self.assertEqual(result.total_immediate_attack_count, 4)
        self.assertEqual(summary.total_immediate_attack_count, 4)
        self.assertEqual(summary.immediate_attack_counts,
            (PcImmediateAttackCount('pc1', 2), PcImmediateAttackCount('minion1', 2)))
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)

    def test_trial_summary_missing_foreign_oversized_or_cached_rows_are_rejected(self):
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        result = prepared_observations()
        record = result.records[0]
        summary = summarize_pc_melee_simulation(result)
        for document in (record, summary):
            rows = document.immediate_attack_counts
            invalid = (None, (), rows[::-1], rows * 2,
                (PcImmediateAttackCount('foreign', 0), *rows[1:]),
                (PcImmediateAttackCount(rows[0].actor_id, 3), *rows[1:]))
            for counts in invalid:
                with self.subTest(document=type(document), counts=counts), self.assertRaises((TypeError, ValueError)):
                    replace(document, immediate_attack_counts=counts)
            malformed = copy(rows[0])
            object.__setattr__(malformed, 'count', True)
            with self.assertRaises(TypeError):
                replace(document, immediate_attack_counts=(malformed, *rows[1:]))


if __name__ == '__main__':
    unittest.main()
