from dataclasses import dataclass

from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest


@dataclass(frozen=True, slots=True)
class MixedSimulationCommand:
    request: NpcMixedSimulationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, NpcMixedSimulationRequest):
            raise TypeError("command requires a typed simulation request")
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError("command requires typed execution options")
        if not isinstance(self.definition_order, (tuple, list)):
            raise TypeError("definition order requires an ordered sequence")
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError("definition order requires non-empty IDs")
        definitions = {p.definition.id for p in self.request.scenario.initial.current.state.roster.participants}
        if len(set(order)) != len(order) or set(order) != definitions:
            raise ValueError("definition order must contain every used definition exactly once")
        object.__setattr__(self, "definition_order", order)
