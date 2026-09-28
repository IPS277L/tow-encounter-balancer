"""Execute an admitted command using the standard v1 RNG and explicit backend."""
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.application.ranged_simulation_models import RangedSimulationCommand, SimulationExecutionMode
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation


def execute_ranged_simulation(command: RangedSimulationCommand) -> NpcRangedSimulationResult:
    """Return a complete source-bound result, or raise a typed execution error.

    Process execution requires an importable, guarded caller entry point.
    There is no retry, backend fallback, or custom RNG option at this boundary.
    """
    if not isinstance(command, RangedSimulationCommand):
        raise TypeError("execution requires a typed ranged simulation command")
    try:
        if command.execution.mode is SimulationExecutionMode.SEQUENTIAL:
            result = run_npc_ranged_simulation(command.request)
        else:
            result = run_npc_ranged_simulation_parallel(
                command.request, workers=command.execution.workers,
                batch_size=command.execution.batch_size,
            )
        if not isinstance(result, NpcRangedSimulationResult):
            raise TypeError("runner must return a typed ranged simulation result")
        if result.source_request != command.request:
            raise ValueError("runner result must belong to the command request")
        return result
    except Exception as error:
        raise RangedSimulationExecutionError(command.request.scenario.initial.current.id) from error
