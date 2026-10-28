"""Source-bound handoff between the two narrow ADR-0036 action owners."""
from dataclasses import dataclass, replace

from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest, NpcChampionAttackResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry
from towr.domain.injury_models import WoundEntryId


@dataclass(frozen=True, slots=True)
class NpcRosterChampionAttackRequest:
    """Bind magic/spatial and attack ownership before any Attack RNG."""

    state: NpcRosterCastingState
    attack: NpcChampionAttackRequest

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState) or not isinstance(self.attack, NpcChampionAttackRequest):
            raise TypeError('handoff requires typed Casting state and Champion attack request')
        if self.state.pending_miscast_continuation is not None:
            raise ValueError('prepared Miscast blocks Champion attack dispatch')
        if self.state.pending_minion_attack is not None:
            raise ValueError('pending Minion attack blocks Champion attack dispatch')
        if self.state.pending_miscast is not None:
            raise ValueError('pending Miscast blocks Champion attack dispatch')
        if self.state.pending_interruption is not None:
            raise ValueError('pending interruption Miscast blocks Champion attack dispatch')
        if self.state.pending_movement is not None:
            raise ValueError('pending movement blocks Champion attack dispatch')
        if self.state.champion_attack is None or self.state.champion_attack != self.attack.state:
            raise ValueError('Champion attack must match the current bound owner')
        if self.attack.execution.id in self.state.consumed_execution_ids:
            raise ValueError('action execution has already been consumed')


@dataclass(frozen=True, slots=True)
class NpcRosterChampionAttackResult:
    source: NpcRosterChampionAttackRequest
    attack: NpcChampionAttackResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterChampionAttackRequest) or not isinstance(self.attack, NpcChampionAttackResult):
            raise TypeError('handoff requires typed source and Champion attack result')
        if self.attack.source != self.source.attack:
            raise ValueError('Champion attack result differs from the bound source')

    @property
    def state(self) -> NpcRosterCastingState:
        previous, updated = self.source.state, self.attack.state
        expiries = previous.wound_expiries
        completion = self.attack.completion
        if (completion is not None and completion.wound_effect is not None
                and completion.wound_effect.request.entry_id is WoundEntryId.STOMACH_BLOW):
            expiries = (*expiries, NpcStomachBlowExpiry(self.attack))
        return replace(previous, roster=updated.roster, round_state=updated.round_state,
                       minion_attack=(None if previous.minion_attack is None else
                                      replace(previous.minion_attack, roster=updated.roster)),
                       champion_attack=updated, consumed_execution_ids=(
                           *previous.consumed_execution_ids, self.attack.execution.request_id),
                       wound_expiries=expiries)
