from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol


@dataclass(frozen=True, slots=True)
class BattleEvent:
    type: str
    round: int
    actor_id: str | None = None
    target_id: str | None = None
    data: Mapping[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: BattleEvent) -> None: ...


class NullEventSink:
    def emit(self, event: BattleEvent) -> None:
        del event


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[BattleEvent] = []

    def emit(self, event: BattleEvent) -> None:
        self.events.append(event)

