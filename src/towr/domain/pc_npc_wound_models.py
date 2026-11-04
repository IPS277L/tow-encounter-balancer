"""The Official's first Wound and the unresolved movement at its actual Broken turn."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest
from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


OFFICIAL_DEFINITION_ID = 'pc-book-npc:empire_official_dagger'
OFFICIAL_BROKEN_RULE_ID = 'RULE-PROFILE-TALABEC-007:first-wound-broken'


def _first_wound(change: ProfileStateChangeRequest) -> bool:
    return (type(change) is ProfileStateChangeRequest and type(change.npc_type) is ProfileNpcType
        and change.npc_type is ProfileNpcType.BRUTE and type(change.previous_wounds) is int
        and change.previous_wounds==0 and type(change.current_wounds) is int and change.current_wounds==1
        and type(change.defeated) is bool and not change.defeated)


def _broken_source(actor_id: str, attack_id: str) -> str:
    return f'{OFFICIAL_BROKEN_RULE_ID}:{actor_id}:{attack_id}'


@dataclass(frozen=True, slots=True)
class PcNpcBrokenTurnUnsupported:
    actor_id: str
    source_id: str
    attack_id: str
    profile_change: ProfileStateChangeRequest
    reason: str = 'npc_broken_turn'

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.source_id,self.attack_id)):
            raise TypeError('Broken-turn stop requires its exact actor, source and Attack execution ID')
        if type(self.reason) is not str or self.reason!='npc_broken_turn':
            raise ValueError('Broken-turn stop requires its canonical reason')
        if not _first_wound(self.profile_change):
            raise ValueError('Broken-turn stop requires the actual undefeated Brute0-to-1 Wound change')
        if self.source_id!=_broken_source(self.actor_id,self.attack_id):
            raise ValueError('Broken-turn source must bind its rule, actor and actual Attack execution')


def official_profile_wound_state(definition: NpcDefinition, injury: ProfileInjuryState,
        change: ProfileStateChangeRequest) -> ProfileInjuryState:
    """Called only while acknowledging the actual mandatory profile-Wound receipt."""
    if definition.id!=OFFICIAL_DEFINITION_ID:
        return injury
    validate_pc_book_npc_definition(definition)
    if not _first_wound(change):
        return injury
    if injury.wounds!=1 or injury.defeated:
        raise ValueError('Official first-Wound effect requires its actual updated injury')
    return replace(injury,conditions=injury.conditions.with_condition(Condition.BROKEN))


def pc_npc_broken_turn_unsupported(state: PcMeleeState) -> PcNpcBrokenTurnUnsupported | None:
    """Keep the observed prefix; stop before a Broken Official's own unstarted turn."""
    combat = state.round_state
    if (state.pending or state.pending_wound is not None or combat.active_turn is not None
            or combat.round_complete or not state.live_party or not state.live_enemies):
        return None
    from towr.domain.pc_melee_result_models import PcAttackProof, PcProfileWoundProof, pc_melee_next_actor
    actor = pc_melee_next_actor(state)
    if actor not in state.source.enemy_activation_order:
        return None
    enemy = state.enemy(actor)
    if (enemy.definition.id!=OFFICIAL_DEFINITION_ID or enemy.state.injury.defeated
            or not enemy.state.injury.conditions.has(Condition.BROKEN)):
        return None
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.state.injury.wounds!=1:
        raise ValueError('live Broken Official must preserve its actual first Wound')
    attack = None
    cause = None
    for proof in state.history:
        if type(proof) is PcAttackProof:
            attack = proof
        elif (type(proof) is PcProfileWoundProof and attack is not None
                and attack.request.target_id==actor and _first_wound(proof.source)):
            if (proof.decision is not None or attack.execution.resolution.profile_wound is None
                    or proof.source!=attack.execution.resolution.profile_wound.state_change):
                raise ValueError('Broken-turn cause lacks its exact profile-Wound acknowledgement')
            if cause is not None:
                raise ValueError('Official first-Wound Broken cause cannot be acknowledged twice')
            cause = (attack.request.id,proof.source)
    if cause is None:
        raise ValueError('Broken-turn stop lacks its actual first-Wound Attack and acknowledgement')
    from towr.domain.pc_npc_exit_models import pc_npc_exit_supported
    if pc_npc_exit_supported(state,actor):
        return None
    attack_id,change = cause
    return PcNpcBrokenTurnUnsupported(actor,_broken_source(actor,attack_id),attack_id,change)
