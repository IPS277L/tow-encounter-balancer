"""Select explicit RNG backends; expose aggregates and source-bound reports."""
from dataclasses import replace

from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceExecutionError, PcMeleeBalanceResult,
)
from towr.application.pc_melee_commands import (
    PcMeleeBalanceCommand, PcMeleeCommandExecutionError, PcMeleeSimulationCommand,
)
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest, PcMeleeSimulationResult
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def _simulate(request: PcMeleeSimulationRequest, execution: SimulationExecutionOptions) -> PcMeleeSimulationSummary:
    replace(request)
    replace(execution)
    if execution.mode is SimulationExecutionMode.SEQUENTIAL:
        result = run_pc_melee_simulation(request)
    else:
        result = run_pc_melee_simulation_parallel(request, workers=execution.workers,
            batch_size=execution.batch_size)
    if type(result) is not PcMeleeSimulationResult:
        raise TypeError('PC simulation must return a typed result')
    replace(result)
    if result.source_request != request:
        raise ValueError('PC simulation returned another complete source request')
    return summarize_pc_melee_simulation(result)


def execute_pc_melee_simulation(command: PcMeleeSimulationCommand) -> PcMeleeSimulationSummary:
    if type(command) is not PcMeleeSimulationCommand:
        raise TypeError('execution requires a PC simulation command')
    try:
        replace(command)
        return _simulate(command.request, command.execution)
    except Exception as error:
        raise PcMeleeCommandExecutionError(command.request_id, 'simulation', 'simulation') from error


def execute_pc_melee_balance(command: PcMeleeBalanceCommand) -> PcMeleeBalanceResult:
    if type(command) is not PcMeleeBalanceCommand:
        raise TypeError('execution requires a PC balance command')
    try:
        replace(command)
    except Exception as error:
        raise PcMeleeCommandExecutionError(command.request_id, 'balance', 'generation') from error
    try:
        return evaluate_pc_melee_balance(command.request,
            lambda request: _simulate(request, command.execution))
    except PcMeleeBalanceExecutionError as error:
        raise PcMeleeCommandExecutionError(command.request_id, 'balance', error.phase.value,
            candidate_id=error.candidate_id, candidate_index=error.candidate_index) from error
    except Exception as error:
        raise PcMeleeCommandExecutionError(command.request_id, 'balance', 'evaluation') from error
