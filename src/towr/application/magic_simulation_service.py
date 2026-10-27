"""Execute an admitted magic command using its explicit standard RNG backend."""
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode
from towr.simulation.npc_magic_models import NpcMagicSimulationResult
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def execute_magic_simulation(command: MagicSimulationCommand) -> NpcMagicSimulationSummary:
    """Return the exact source-bound aggregate or a typed execution failure.

    Runners materialize the complete trial records before summarization. Process
    execution requires an importable, guarded caller. No custom RNG, retry or
    backend fallback is added at this boundary.
    """
    if not isinstance(command, MagicSimulationCommand):
        raise TypeError("execution requires a typed magic simulation command")
    try:
        if command.execution.mode is SimulationExecutionMode.SEQUENTIAL:
            result = run_npc_magic_simulation(command.request)
        else:
            result = run_npc_magic_simulation_parallel(
                command.request, workers=command.execution.workers,
                batch_size=command.execution.batch_size,
            )
        if not isinstance(result, NpcMagicSimulationResult):
            raise TypeError("runner must return a typed magic simulation result")
        if result.source_request != command.request:
            raise ValueError("runner result must belong to the full command request")
        summary = summarize_npc_magic_simulation(result)
        if not isinstance(summary, NpcMagicSimulationSummary):
            raise TypeError("summary must be a typed magic simulation summary")
        if summary.source_request != command.request:
            raise ValueError("summary must belong to the full command request")
        return summary
    except Exception as error:
        raise MagicSimulationExecutionError(command.request_id) from error
