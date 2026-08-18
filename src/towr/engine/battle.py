from __future__ import annotations

from dataclasses import dataclass

from towr.controllers.focused import FocusMostWounded
from towr.controllers.protocols import TargetSelector
from towr.domain.combatants import CombatantDefinition, CombatantState, Side
from towr.domain.encounters import EncounterDefinition
from towr.domain.results import BattleOutcome, BattleResult, CombatantResult
from towr.engine.events import BattleEvent, EventSink, NullEventSink, RecordingEventSink
from towr.engine.resolution import AttackResolver
from towr.rules.dice import RandomSource
from towr.rules.ruleset import RULES_VERSION


@dataclass(frozen=True, slots=True)
class BattleConfig:
    max_rounds: int
    record_events: bool = False

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be positive")


class BattleEngine:
    def __init__(
        self,
        *,
        rng: RandomSource,
        config: BattleConfig,
        target_selector: TargetSelector | None = None,
    ) -> None:
        self._rng = rng
        self._config = config
        self._target_selector = target_selector or FocusMostWounded()

    def run(self, encounter: EncounterDefinition) -> BattleResult:
        self._validate_first_slice(encounter)
        players = [CombatantState(definition=item) for item in encounter.players]
        monsters = [CombatantState(definition=item) for item in encounter.monsters]
        sink: EventSink
        recorder: RecordingEventSink | None = None
        if self._config.record_events:
            recorder = RecordingEventSink()
            sink = recorder
        else:
            sink = NullEventSink()
        resolver = AttackResolver(rng=self._rng, events=sink)

        for round_number in range(1, self._config.max_rounds + 1):
            sink.emit(BattleEvent(type="round_started", round=round_number))
            self._run_side(round_number, players, monsters, resolver, sink)
            outcome = self._outcome(players, monsters)
            if outcome is not None:
                return self._result(outcome, round_number, players, monsters, recorder)

            self._run_side(round_number, monsters, players, resolver, sink)
            outcome = self._outcome(players, monsters)
            if outcome is not None:
                return self._result(outcome, round_number, players, monsters, recorder)

            sink.emit(BattleEvent(type="round_ended", round=round_number))

        return self._result(
            BattleOutcome.ROUND_LIMIT,
            self._config.max_rounds,
            players,
            monsters,
            recorder,
        )

    def _run_side(
        self,
        round_number: int,
        actors: list[CombatantState],
        opponents: list[CombatantState],
        resolver: AttackResolver,
        sink: EventSink,
    ) -> None:
        for actor in actors:
            if not actor.is_alive:
                continue
            for action in actor.definition.actions:
                if not actor.is_alive or not any(item.is_alive for item in opponents):
                    return
                target = self._target_selector.select(actor, opponents)
                sink.emit(
                    BattleEvent(
                        type="action_started",
                        round=round_number,
                        actor_id=actor.definition.id,
                        target_id=target.definition.id,
                        data={"action_id": action.id},
                    )
                )
                resolver.resolve(
                    round_number=round_number,
                    attacker=actor,
                    defender=target,
                    action=action,
                )

    @staticmethod
    def _outcome(
        players: list[CombatantState],
        monsters: list[CombatantState],
    ) -> BattleOutcome | None:
        players_alive = any(item.is_alive for item in players)
        monsters_alive = any(item.is_alive for item in monsters)
        if not players_alive and not monsters_alive:
            return BattleOutcome.DRAW
        if not monsters_alive:
            return BattleOutcome.PLAYER_VICTORY
        if not players_alive:
            return BattleOutcome.MONSTER_VICTORY
        return None

    @staticmethod
    def _result(
        outcome: BattleOutcome,
        rounds: int,
        players: list[CombatantState],
        monsters: list[CombatantState],
        recorder: RecordingEventSink | None,
    ) -> BattleResult:
        states = (*players, *monsters)
        return BattleResult(
            outcome=outcome,
            rounds=rounds,
            combatants=tuple(
                CombatantResult(
                    id=state.definition.id,
                    wounds=state.wounds,
                    stagger=state.stagger,
                    survived=state.is_alive,
                )
                for state in states
            ),
            rules_version=RULES_VERSION,
            events=tuple(recorder.events) if recorder is not None else (),
        )

    @staticmethod
    def _validate_first_slice(encounter: EncounterDefinition) -> None:
        if len(encounter.players) != 1 or len(encounter.monsters) != 1:
            raise NotImplementedError("the first vertical slice supports only 1 vs 1")
        for combatant in (*encounter.players, *encounter.monsters):
            BattleEngine._validate_actions(combatant)

    @staticmethod
    def _validate_actions(combatant: CombatantDefinition) -> None:
        if any(action.target_count != 1 for action in combatant.actions):
            raise NotImplementedError("multi-target actions are not part of the first slice")

