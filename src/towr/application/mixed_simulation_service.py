"""Execute an admitted Mixed command with the standard RNG and explicit backend."""
from towr.application.mixed_simulation_errors import MixedSimulationExecutionError
from towr.application.mixed_simulation_models import MixedSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


def execute_mixed_simulation(command: MixedSimulationCommand) -> NpcMixedSimulationSummary:
    """Return a source-bound aggregate, or raise a typed execution error.

    The runner still materializes complete trial records before summarization.
    Process execution requires an importable, guarded caller entry point.
    There is no retry, backend fallback, or custom RNG option at this boundary.
    """
    if not isinstance(command, MixedSimulationCommand):
        raise TypeError("execution requires a typed mixed simulation command")
    try:
        if command.execution.mode is SimulationExecutionMode.SEQUENTIAL:
            result = run_npc_mixed_simulation(command.request)
        else:
            result = run_npc_mixed_simulation_parallel(
                command.request, workers=command.execution.workers,
                batch_size=command.execution.batch_size,
            )
        if not isinstance(result, NpcMixedSimulationResult):
            raise TypeError("runner must return a typed mixed simulation result")
        if result.source_request != command.request:
            raise ValueError("runner result must belong to the command request")
        summary = summarize_npc_mixed_simulation(result)
        if not isinstance(summary, NpcMixedSimulationSummary):
            raise TypeError("summary must be a typed mixed simulation summary")
        if summary.source_request != command.request:
            raise ValueError("summary must belong to the command request")
        return summary
    except Exception as error:
        raise MixedSimulationExecutionError(command.request.scenario.initial.current.id) from error
