"""Current application commands for the separate PC melee JSON1 boundary."""
from dataclasses import dataclass, replace

from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest, validate_pc_melee_balance_request
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest


def _envelope(request_id: str, execution: SimulationExecutionOptions, schema_version: str) -> None:
    if type(request_id) is not str or not request_id.strip():
        raise ValueError('command request_id must be a nonblank string')
    if type(schema_version) is not str or schema_version != '1':
        raise ValueError('PC melee supports only the current JSON1')
    if type(execution) is not SimulationExecutionOptions:
        raise TypeError('command requires explicit typed execution options')
    replace(execution)


@dataclass(frozen=True, slots=True)
class PcMeleeSimulationCommand:
    request_id: str
    request: PcMeleeSimulationRequest
    execution: SimulationExecutionOptions
    schema_version: str = '1'

    def __post_init__(self) -> None:
        _envelope(self.request_id, self.execution, self.schema_version)
        if type(self.request) is not PcMeleeSimulationRequest:
            raise TypeError('simulation command requires a PcMeleeSimulationRequest')
        replace(self.request)


@dataclass(frozen=True, slots=True)
class PcMeleeBalanceCommand:
    request_id: str
    request: PcMeleeBalanceRequest
    execution: SimulationExecutionOptions
    schema_version: str = '1'

    def __post_init__(self) -> None:
        _envelope(self.request_id, self.execution, self.schema_version)
        validate_pc_melee_balance_request(self.request)


class PcMeleeCommandExecutionError(RuntimeError):
    """Safe command context; private causes stay in the Python exception chain."""

    def __init__(self, request_id: str, family: str, phase: str, *,
                 candidate_id: str | None = None, candidate_index: int | None = None) -> None:
        if type(request_id) is not str or not request_id.strip():
            raise ValueError('execution failure requires its trusted request_id')
        if type(family) is not str or family not in ('simulation', 'balance'):
            raise ValueError('unknown PC command family')
        allowed = ('simulation',) if family == 'simulation' else ('generation', 'evaluation')
        if type(phase) is not str or phase not in allowed:
            raise ValueError('failure phase contradicts command family')
        if (candidate_id is None) != (candidate_index is None):
            raise ValueError('candidate error context requires both ID and index')
        if candidate_id is not None:
            if family != 'balance' or type(candidate_id) is not str or not candidate_id.strip():
                raise ValueError('candidate context requires a balance candidate ID')
            if type(candidate_index) is not int or candidate_index < 0:
                raise ValueError('candidate index must be a nonnegative integer')
        self.request_id = request_id
        self.schema_version = '1'
        self.family = family
        self.phase = phase
        self.candidate_id = candidate_id
        self.candidate_index = candidate_index
        self.code = f'{phase}_failed'
        super().__init__(f'PC melee {family} {phase} failed')
