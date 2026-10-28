"""Exclude one dead Champion's still-owed turn after a completed Attack.

ADR-0044; PG1.4 Rules / Combat p112, Wounds Table pp190-191;
GM1.1 Allies and Antagonists / Champions p92. Death and Wound registration
are already complete: this phase only changes the current round exclusion.
"""
from dataclasses import dataclass, replace

from towr.domain.injury_models import WoundEntryId
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome


@dataclass(frozen=True, slots=True)
class NpcRosterDeadChampionExclusionRequest:
    id: str
    state: NpcRosterCastingState
    attack: NpcRosterChampionAttackResult

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError('dead Champion exclusion ID must be a string')
        if not self.id.strip():
            raise ValueError('dead Champion exclusion ID must not be blank')
        if not isinstance(self.state, NpcRosterCastingState) or not isinstance(self.attack, NpcRosterChampionAttackResult):
            raise TypeError('dead Champion exclusion requires typed full state and bound Attack result')
        old, attack = self.state, self.attack.attack
        if old.pending_miscast_continuation is not None:
            raise ValueError('prepared Miscast blocks dead Champion exclusion')
        if old != self.attack.state:
            raise ValueError('dead Champion exclusion requires the exact immediate post-Attack state')
        champion = old.champion_attack
        if (champion is None or champion.pending is not None or attack.pending_follow_ups
                or old.pending_minion_attack is not None or old.pending_miscast is not None
                or old.pending_movement is not None or old.pending_interruption is not None):
            raise ValueError('mandatory pending continuations block dead Champion exclusion')
        execution = attack.execution
        target_id = execution.target_id
        if target_id != old.wizard.actor_id:
            raise ValueError('dead Champion exclusion requires the bound Wizard target')
        actor, target = old.roster.participant(execution.actor_id), old.roster.participant(target_id)
        if (actor.definition.injury_policy is not TargetInjuryPolicy.MINION or actor.state.injury.defeated
                or target.definition.injury_policy is not TargetInjuryPolicy.CHAMPION
                or actor.state.side is target.state.side):
            raise ValueError('dead Champion exclusion requires the living enemy Minion attacker')
        completion, injury = attack.completion, target.state.injury
        if (completion is None or completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED
                or not completion.wound_result.table_roll.entry.lethal or not injury.dead
                or completion.wound_effect is None or completion.wound_effect.follow_ups
                or not injury.wounds or not injury.wounds[-1].effect_resolved):
            raise ValueError('dead Champion exclusion requires a completed accepted lethal Wound')
        if completion.wound_result.table_roll.entry.id not in (
                WoundEntryId.APPALLING_STRIKE, WoundEntryId.BISECTION,
                WoundEntryId.PIERCED_HEART, WoundEntryId.DECAPITATION):
            raise ValueError('dead Champion exclusion supports only the four lethal Wound entries')
        # These four K1 effects only resolve the newly registered Wound. The
        # general WoundEffectResult DTO alone does not validate that projection.
        rolled = completion.wound_result.state
        expected = replace(rolled, wounds=(*rolled.wounds[:-1], replace(rolled.wounds[-1], effect_resolved=True)))
        if injury != expected:
            raise ValueError('lethal Wound completion must only resolve the registered Wound effect')
        combat, turn = old.round_state, old.round_state.active_turn
        if turn is None or turn.actor_id != execution.actor_id or execution.state != combat:
            raise ValueError('dead Champion exclusion must precede the attacking actor turn end')
        if (execution.slot_index != 1 or turn.action_slots != (execution.slot,)
                or execution.slot.grant is not ActionSlotGrant.STANDARD or not execution.slot.executed
                or execution.slot.declaration != CombatActionDeclaration(CombatActionKind.ATTACK)):
            raise ValueError('dead Champion exclusion requires one completed standard Attack slot')
        if target_id in (*combat.completed_turn_entity_ids, *combat.excluded_turn_entity_ids):
            raise ValueError('dead Champion must still be awaiting its current-round turn')


@dataclass(frozen=True, slots=True)
class NpcRosterDeadChampionExclusionResult:
    source: NpcRosterDeadChampionExclusionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterDeadChampionExclusionRequest):
            raise TypeError('dead Champion exclusion result requires its complete typed source')

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        combat = replace(old.round_state, excluded_turn_entity_ids=(
            *old.round_state.excluded_turn_entity_ids, old.wizard.actor_id))
        return replace(old, round_state=combat, champion_attack=replace(old.champion_attack, round_state=combat))
