"""Execute an admitted Melee command with the standard RNG and explicit backend."""
from towr.application.melee_simulation_errors import MeleeSimulationExecutionError
from towr.application.melee_simulation_models import MeleeSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode
from towr.simulation.npc_melee_models import NpcMeleeSimulationResult
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def execute_melee_simulation(command: MeleeSimulationCommand) -> NpcMeleeSimulationSummary:
    """Return a source-bound aggregate, or raise a typed execution error.

    The runner still materializes complete trial records before summarization.
    Process execution requires an importable, guarded caller entry point.
    There is no retry, backend fallback, or custom RNG option at this boundary.
    """
    if not isinstance(command, MeleeSimulationCommand):
        raise TypeError("execution requires a typed melee simulation command")
    try:
        if command.execution.mode is SimulationExecutionMode.SEQUENTIAL:
            result = run_npc_melee_simulation(command.request)
        else:
            result = run_npc_melee_simulation_parallel(
                command.request, workers=command.execution.workers,
                batch_size=command.execution.batch_size,
            )
        if not isinstance(result, NpcMeleeSimulationResult):
            raise TypeError("runner must return a typed melee simulation result")
        if result.source_request != command.request:
            raise ValueError("runner result must belong to the command request")
        summary = summarize_npc_melee_simulation(result)
        if not isinstance(summary, NpcMeleeSimulationSummary):
            raise TypeError("summary must be a typed melee simulation summary")
        if summary.source_request != command.request:
            raise ValueError("summary must belong to the command request")
        return summary
    except Exception as error:
        raise MeleeSimulationExecutionError(command.request.scenario.initial.current.id) from error
