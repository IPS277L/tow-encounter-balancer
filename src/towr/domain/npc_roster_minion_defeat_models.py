"""One full-owner defeat acknowledgement/exclusion (ADR-0037).

GM1.1 Allies and Antagonists / Minions p91; PG1.4 Rules / Combat p112.
Disposition is a supplied attacker/GM decision, not an equipment/death engine.
"""
from dataclasses import dataclass, replace

from towr.domain.minion_defeat_models import (
    MinionDefeatDecision, acknowledged_minion_defeat_state, validate_minion_defeat_context,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_round_exclusion_models import excluded_minion_round, validate_minion_exclusion_context


@dataclass(frozen=True, slots=True)
class NpcRosterMinionDefeatRequest:
    id: str
    state: NpcRosterCastingState
    decision: MinionDefeatDecision

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError('defeat phase ID must be a string')
        if not self.id.strip():
            raise ValueError('defeat phase ID must not be blank')
        if not isinstance(self.state, NpcRosterCastingState) or not isinstance(self.decision, MinionDefeatDecision):
            raise TypeError('bound defeat requires typed full state and decision')
        old = self.state
        attack = old.pending_minion_attack
        if attack is None or old.minion_attack is None:
            raise ValueError('bound defeat requires the current full pending Minion attack')
        if (old.pending_miscast is not None or old.pending_movement is not None or old.pending_interruption is not None
                or old.champion_attack is not None and old.champion_attack.pending is not None):
            raise ValueError('another mandatory pending continuation blocks defeat completion')
        follow_up = validate_minion_defeat_context(old.minion_attack, old.round_state, attack,
                                                  self.decision, attack.pending_follow_ups)
        # This ordinary single-target slice does not erase a different required
        # consequence or invent a new representation for partially handled work.
        if attack.pending_follow_ups != (follow_up,):
            raise ValueError('other Minion attack follow-ups require a separate consumer')
        target = self.decision.target_id
        if target in old.round_state.excluded_turn_entity_ids:
            raise ValueError('pending defeat target is already excluded')
        if target not in old.round_state.completed_turn_entity_ids:
            validate_minion_exclusion_context(old.minion_attack, old.round_state, target)


@dataclass(frozen=True, slots=True)
class NpcRosterMinionDefeatResult:
    source: NpcRosterMinionDefeatRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterMinionDefeatRequest):
            raise TypeError('bound defeat result requires its complete typed source')

    @property
    def excludes_target(self) -> bool:
        return self.source.decision.target_id not in self.source.state.round_state.completed_turn_entity_ids

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        attack_id = old.pending_minion_attack.execution.request_id
        minion = acknowledged_minion_defeat_state(old.minion_attack, attack_id)
        combat = (excluded_minion_round(old.round_state, self.source.decision.target_id)
                  if self.excludes_target else old.round_state)
        champion = old.champion_attack
        if champion is not None:
            champion = replace(champion, round_state=combat)
        return replace(old, minion_attack=minion, champion_attack=champion,
                       round_state=combat, pending_minion_attack=None)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return (('RULE-NPC-002', 'RULE-COMBAT-001:rounds-sides-turns') if self.excludes_target
                else ('RULE-NPC-002',))
