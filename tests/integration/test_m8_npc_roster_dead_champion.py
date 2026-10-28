"""Actual bound Attack -> pure exclusion -> existing turn consumers."""
from copy import deepcopy
from random import getstate
import unittest

from tests.helpers import SequenceRandom
from tests.integration.test_m8_npc_roster_minion_defeat import shoot
from tests.integration.test_m8_npc_roster_turn import activate, advance, cast, end
from tests.unit.test_m8_npc_magic_scenario import scenario, OPPOSITION
from tests.unit.test_m8_npc_roster_minion_attack import parts
from tests.unit.test_m8_npc_roster_turn import CAST
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_roster_champion_attack_models import (
    NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult,
)
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionRequest as Request
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_dead_champion_resolution import (
    exclude_npc_roster_dead_champion as exclude,
    apply_npc_roster_dead_champion_exclusion as apply,
)
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def fresh_lethal_attack():
    """Three actual rounds from a fresh authored owner; no runner extension."""
    state = scenario(wizard_side=OPPOSITION).initial_runtime_state
    for number, dice in enumerate(((1,), (1, 1), (10, 10, 5)), 1):
        state = activate(state, 'enemy')
        prepared, execution = parts(state, 'enemy', 'wizard', f'incoming:{number}')
        source = NpcRosterChampionAttackRequest(state,
            NpcChampionAttackRequest(state.champion_attack, prepared, execution))
        result = NpcRosterChampionAttackResult(source, execute_npc_champion_attack(
            source.attack, SequenceRandom((1, 2, 3, 10, 10, 10, *dice))))
        state = apply_npc_roster_champion_attack_result(state, result)
        if number == 3:
            return result
        state = end(state, 'enemy')
        state = cast(activate(state, 'wizard', CAST), (10, 10, 10))
        state = end(state, 'wizard')
        state = shoot(activate(state, 'ally'), 'ally', 'enemy', f'ally:miss:{number}', (10,) * 6)
        state = advance(end(state, 'ally'))


class DeadChampionExclusionIntegrationTests(unittest.TestCase):
    def test_real_fresh_attack_chain_keeps_daily_and_both_attack_ledgers(self):
        attack = fresh_lethal_attack(); old = attack.state
        before = deepcopy(attack); global_rng = getstate()
        result = exclude(Request('death:round3', old, attack))
        final = apply(old, result)
        injury = final.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.table_total for w in injury.wounds), (1, 2, 25))
        self.assertTrue(injury.dead)
        self.assertEqual(final.champion_attack.daily_wounds.wound_count, 3)
        self.assertEqual(len(final.champion_attack.consumed_wound_roll_ids), 3)
        self.assertEqual(final.champion_attack.consumed_execution_ids,
                         ('incoming:1', 'incoming:2', 'incoming:3'))
        self.assertEqual(final.minion_attack.consumed_execution_ids, ('ally:miss:1', 'ally:miss:2'))
        self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
        self.assertEqual(final.wound_turn_end_receipts, old.wound_turn_end_receipts)
        self.assertIs(final.wizard, old.wizard)
        self.assertEqual(attack, before)
        self.assertEqual(getstate(), global_rng)

    def test_attacker_end_and_surviving_ally_finish_the_round_before_advance(self):
        attack = fresh_lethal_attack(); old = attack.state
        final = apply(old, exclude(Request('death:round3', old, attack)))
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('end:lethal-attacker', final, 'enemy')).state
        self.assertEqual(ended.round_state.completed_turn_entity_ids, ('enemy',))
        self.assertEqual(ended.round_state.excluded_turn_entity_ids, ('wizard',))
        self.assertFalse(ended.round_state.round_complete)
        ally = activate(ended, 'ally')
        self.assertEqual(ally.round_state.active_turn.actor_id, 'ally')
        finished = shoot(ally, 'ally', 'enemy', 'ally:miss:3', (10,) * 6)
        finished = end(finished, 'ally')
        self.assertTrue(finished.round_state.round_complete)
        following = advance(finished)
        self.assertEqual(following.round_state.round_number, 4)
        self.assertEqual(following.round_state.excluded_turn_entity_ids, ('wizard',))
        self.assertEqual(following.round_state.completed_turn_entity_ids, ())
        self.assertEqual(following.roster, finished.roster)
        self.assertEqual(following.spatial_state.placements, old.spatial_state.placements)
        self.assertEqual(following.champion_attack.consumed_wound_roll_ids,
                         old.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(following.champion_attack.daily_wounds, old.champion_attack.daily_wounds)

    def test_exclusion_preserves_spatial_archives_and_live_casting_projection(self):
        attack = fresh_lethal_attack(); old = attack.state
        final = apply(old, exclude(Request('death:archive', old, attack)))
        self.assertEqual(final.roster, old.roster)
        self.assertEqual(final.round_state.participants, old.round_state.participants)
        self.assertEqual(final.spatial_state, old.spatial_state)
        self.assertEqual(final.spatial_state.placement_for('wizard'), old.spatial_state.placement_for('wizard'))
        self.assertEqual(tuple(p.entity_id for p in final.casting_round_state.participants), ('ally', 'enemy'))
        self.assertEqual(tuple(p.entity_id for p in final.casting_spatial_state.placements), ('ally', 'enemy'))
        self.assertEqual(final.minion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)

    def test_consumer_requires_immediate_post_attack_not_attacker_end_state(self):
        attack = fresh_lethal_attack(); old = attack.state
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('end:without-exclusion', old, 'enemy')).state
        with self.assertRaises(ValueError): Request('too-late', ended, attack)
        result = exclude(Request('immediate', old, attack))
        with self.assertRaises(ValueError): apply(ended, result)


if __name__ == '__main__':
    unittest.main()
