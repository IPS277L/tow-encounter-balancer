from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom, combatant
from towr.domain.actions import AttackAction, StatRollSource
from towr.domain.combatants import Side
from towr.domain.encounters import EncounterDefinition
from towr.domain.results import BattleOutcome
from towr.domain.stats import DicePool
from towr.engine.battle import BattleConfig, BattleEngine


class BattleEngineTests(unittest.TestCase):
    def test_player_can_win_before_monster_acts(self) -> None:
        player = combatant(
            "player",
            Side.PLAYERS,
            ws=DicePool(2, 10),
            resilience=5,
        )
        monster = combatant(
            "monster",
            Side.MONSTERS,
            defense=DicePool(2, 1),
            resilience=1,
            wound_limit=1,
        )
        result = BattleEngine(
            rng=SequenceRandom([1, 1, 10, 10]),
            config=BattleConfig(max_rounds=10, record_events=True),
        ).run(EncounterDefinition(players=(player,), monsters=(monster,)))

        self.assertIs(result.outcome, BattleOutcome.PLAYER_VICTORY)
        self.assertEqual(result.rounds, 1)
        action_actors = [
            event.actor_id for event in result.events if event.type == "action_started"
        ]
        self.assertEqual(action_actors, ["player"])

    def test_double_zero_can_defeat_both_sides(self) -> None:
        profile = DicePool(2, 1)
        player = combatant(
            "player",
            Side.PLAYERS,
            ws=profile,
            defense=profile,
            wound_limit=1,
        )
        monster = combatant(
            "monster",
            Side.MONSTERS,
            ws=profile,
            defense=profile,
            wound_limit=1,
        )
        result = BattleEngine(
            rng=SequenceRandom([10] * 8),
            config=BattleConfig(max_rounds=10),
        ).run(EncounterDefinition(players=(player,), monsters=(monster,)))

        self.assertIs(result.outcome, BattleOutcome.DRAW)
        self.assertTrue(all(not item.survived for item in result.combatants))

    def test_miss_stagger_does_not_accumulate_until_round_limit(self) -> None:
        weak = DicePool(2, 1)
        player = combatant("player", Side.PLAYERS, ws=weak, defense=weak)
        monster = combatant("monster", Side.MONSTERS, ws=weak, defense=weak)
        one_phase = [10, 10, 1, 10]
        result = BattleEngine(
            rng=SequenceRandom(one_phase * 4),
            config=BattleConfig(max_rounds=2),
        ).run(EncounterDefinition(players=(player,), monsters=(monster,)))

        self.assertIs(result.outcome, BattleOutcome.ROUND_LIMIT)
        self.assertEqual(result.rounds, 2)
        self.assertEqual([item.stagger for item in result.combatants], [1, 1])
        self.assertEqual([item.wounds for item in result.combatants], [0, 0])

    def test_multiple_actions_resolve_in_configuration_order(self) -> None:
        actions = (
            AttackAction("first", StatRollSource("WS"), weapon=0),
            AttackAction("second", StatRollSource("WS"), weapon=0),
        )
        player = combatant(
            "player",
            Side.PLAYERS,
            ws=DicePool(2, 10),
            actions=actions,
        )
        monster = combatant(
            "monster",
            Side.MONSTERS,
            defense=DicePool(2, 1),
            resilience=10,
            wound_limit=1,
        )
        result = BattleEngine(
            rng=SequenceRandom([1, 1, 10, 10] * 2),
            config=BattleConfig(max_rounds=10, record_events=True),
        ).run(EncounterDefinition(players=(player,), monsters=(monster,)))

        action_ids = [
            event.data["action_id"]
            for event in result.events
            if event.type == "action_started"
        ]
        self.assertEqual(action_ids, ["first", "second"])
        self.assertIs(result.outcome, BattleOutcome.PLAYER_VICTORY)

    def test_first_slice_rejects_multi_target_action_explicitly(self) -> None:
        action = AttackAction("area", StatRollSource("WS"), weapon=0, target_count=2)
        player = combatant("player", Side.PLAYERS, actions=(action,))
        monster = combatant("monster", Side.MONSTERS)
        engine = BattleEngine(
            rng=SequenceRandom([]),
            config=BattleConfig(max_rounds=1),
        )

        with self.assertRaises(NotImplementedError):
            engine.run(EncounterDefinition(players=(player,), monsters=(monster,)))


if __name__ == "__main__":
    unittest.main()

