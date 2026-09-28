from dataclasses import dataclass
from enum import Enum

from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest


class SimulationExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PROCESS = "process"


@dataclass(frozen=True, slots=True)
class SimulationExecutionOptions:
    mode: SimulationExecutionMode
    workers: int | None = None
    batch_size: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, SimulationExecutionMode):
            raise TypeError("execution mode must be typed")
        if self.mode is SimulationExecutionMode.SEQUENTIAL:
            if self.workers is not None or self.batch_size is not None:
                raise ValueError("sequential execution has no workers/batch_size")
        else:
            if type(self.workers) is not int or not 1 <= self.workers <= 61:
                raise ValueError("process workers must be an integer in [1, 61]")
            if type(self.batch_size) is not int or self.batch_size < 1:
                raise ValueError("process batch_size must be a positive integer")


@dataclass(frozen=True, slots=True)
class RangedSimulationCommand:
    request: NpcRangedSimulationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, NpcRangedSimulationRequest):
            raise TypeError("command requires a typed simulation request")
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError("command requires typed execution options")
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError("definition order requires non-empty IDs")
        definitions = {p.definition.id for p in self.request.scenario.initial.current.state.roster.participants}
        if len(set(order)) != len(order) or set(order) != definitions:
            raise ValueError("definition order must contain every used definition exactly once")
        object.__setattr__(self, "definition_order", order)
