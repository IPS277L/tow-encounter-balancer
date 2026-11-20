"""Typed ordinary-action grants from actual Talent execution sources."""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.reload_models import RELOAD_RULE_ID, ReloadActionExecutionResult
from towr.domain.condition_models import Condition
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.turn_models import CombatActionKind


RAPID_RELOAD_RULE_ID = 'RULE-TALENT-002:rapid-reload'


@dataclass(frozen=True, slots=True)
class RapidReloadGrant:
    """One immediate Aim/Attack, tied to one successful physical Reload."""

    actor_id: str
    round_number: int
    slot_request_id: str
    source_reload: ReloadActionExecutionResult
    owned_talent: AcquiredTalent
    target_id: str
    action_kind: CombatActionKind
    ranged_bonus: bool = False

    def __post_init__(self):
        for value in (self.actor_id, self.slot_request_id, self.target_id):
            if type(value) is not str or not value.strip():
                raise TypeError('Rapid Reload requires exact actor, slot and target identifiers')
        if type(self.round_number) is not int or self.round_number < 1:
            raise ValueError('Rapid Reload requires an exact positive round')
        if type(self.source_reload) is not ReloadActionExecutionResult:
            raise TypeError('Rapid Reload requires the full actual Reload execution')
        source = replace(self.source_reload)
        if type(self.owned_talent) is not AcquiredTalent:
            raise TypeError('Rapid Reload requires its actual acquired Talent source')
        replace(self.owned_talent)
        if self.owned_talent.id is not TalentId.RAPID_RELOAD:
            raise ValueError('another Talent cannot authorize Rapid Reload')
        if (source.rule_id != RELOAD_RULE_ID or source.source_request.actor_id != self.actor_id
                or source.round_state.round_number != self.round_number
                or source.source_request.slot_index != 1
                or not source.exacting.test_result.succeeded):
            raise ValueError('Rapid Reload requires this actor and round successful first Reload Test')
        if source.source_request.actor_conditions.has(Condition.STAGGERED):
            raise ValueError('Staggered forbids Rapid Reload')
        if type(self.action_kind) is not CombatActionKind or self.action_kind not in (
                CombatActionKind.AIM, CombatActionKind.ATTACK):
            raise ValueError('Rapid Reload grants only Aim or Attack')
        if self.target_id == self.actor_id:
            raise ValueError('Rapid Reload requires an opposing target')
        if type(self.ranged_bonus) is not bool:
            raise TypeError('Rapid Reload retains an exact repeater mode')
        if self.action_kind is CombatActionKind.AIM and self.ranged_bonus:
            raise ValueError('Aim cannot spend a repeater Attack bonus')
        if self.ranged_bonus:
            from towr.domain.ranged_weapon_profiles import ranged_weapon_reload_profile,RangedReloadTrigger
            if (ranged_weapon_reload_profile(source.state.weapon_id).trigger
                    is not RangedReloadTrigger.AFTER_OPTIONAL_BONUS
                    or source.source_request.actor_conditions.has(Condition.DRAINED)):
                raise ValueError('Rapid Reload repeater mode requires its actual available weapon bonus')
        if self.action_kind is CombatActionKind.ATTACK and not source.state.loaded:
            raise ValueError('Rapid Reload Attack requires the actual weapon to be loaded')

    @property
    def weapon_instance_id(self):
        return self.source_reload.state.weapon_instance_id

    @property
    def first_execution(self):
        return self.source_reload.slot.execution
