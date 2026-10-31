"""Exact mandatory Miscast journal adjacency (ADR-0046); no execution/RNG."""
from towr.domain.magic_models import MiscastTableEntryId
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_step_models import NpcMagicStep
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult, NpcRosterUnnaturalWindResult,
)


def validate_magic_miscast_predecessor(
    scenario: NpcMagicScenario, previous: NpcMagicStep | None, step: NpcMagicStep | None,
) -> None:
    """Bind origin traces, both phase links and the journal's supported tail."""
    if not isinstance(scenario, NpcMagicScenario):
        raise TypeError('Miscast journal requires a typed scenario')
    if any(value is not None and not isinstance(value, NpcMagicStep) for value in (previous, step)):
        raise TypeError('Miscast adjacency requires typed steps')
    phases = (NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult, NpcRosterUnnaturalWindResult)
    result = step.result if step is not None else None
    if scenario.miscast_continuation is None:
        if isinstance(result, phases) or previous is not None and isinstance(previous.result, phases):
            raise ValueError('Miscast journal phases require explicit scenario opt-in')
        return
    state = previous.after if previous is not None else scenario.initial_runtime_state
    expected = None
    if state.pending_miscast is not None or state.pending_interruption is not None:
        expected = NpcRosterMiscastPreparationResult
    elif isinstance(state.pending_miscast_continuation, NpcRosterMiscastPreparationResult):
        expected = NpcRosterMiscastRollResult
    elif (isinstance(state.pending_miscast_continuation, NpcRosterMiscastRollResult)
          and state.pending_miscast_continuation.roll.entry.id is MiscastTableEntryId.UNNATURAL_WIND):
        expected = NpcRosterUnnaturalWindResult
    if expected is not None:
        if not isinstance(result, expected):
            raise ValueError('opted journal cannot skip or stop before a mandatory Miscast phase')
        if previous is None or step.before != state:
            raise ValueError('Miscast phase requires its exact immediate full-owner predecessor')
    elif isinstance(result, phases):
        raise ValueError('Miscast phase has no matching immediate predecessor')
    if isinstance(result, NpcRosterMiscastPreparationResult):
        if previous is None or step.origin_witness != previous.result:
            raise ValueError('Miscast preparation requires the complete immediate origin witness')
    elif isinstance(result, (NpcRosterMiscastRollResult, NpcRosterUnnaturalWindResult)):
        if previous is None or result.source.state.pending_miscast_continuation != previous.result:
            raise ValueError('Miscast phase differs from the complete preceding phase result')
