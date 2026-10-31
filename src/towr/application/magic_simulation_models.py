"""Pure application input for the separate magic JSON boundary (ADR-0043)."""
from dataclasses import dataclass

from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


@dataclass(frozen=True, slots=True)
class MagicSimulationCommand:
    request_id: str
    request: NpcMagicSimulationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str):
            raise TypeError("magic schema version must be a string")
        if self.schema_version not in ("1", "2"):
            raise ValueError("unsupported magic schema version")
        if not isinstance(self.request_id, str):
            raise TypeError("command request ID must be a string")
        if not self.request_id.strip():
            raise ValueError("command request ID must not be blank")
        if not isinstance(self.request, NpcMagicSimulationRequest):
            raise TypeError("command requires a typed magic simulation request")
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError("command requires typed execution options")
        if not isinstance(self.definition_order, (tuple, list)):
            raise TypeError("definition order requires an ordered tuple or list")
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError("definition order requires non-empty IDs")
        definitions = {p.definition.id for p in self.request.scenario.initial.roster.participants}
        if len(set(order)) != len(order) or set(order) != definitions:
            raise ValueError("definition order must contain every used definition exactly once")
        object.__setattr__(self, "definition_order", order)
