"""Typed immediate weapon strikes, separate from ordinary action execution.

The first permission is Bash Attack. Its parent slot witnesses the triggering
action; it is neither reserved nor executed again by the immediate strike.
"""
from __future__ import annotations

from dataclasses import dataclass,field,replace
from typing import TYPE_CHECKING

from towr.domain.pc_bash_weapon_models import BashWeaponSelection
from towr.domain.talent_bash_attack_models import BashAttackGrant,BASH_ATTACK_RULE_ID
from towr.domain.talent_armour_bane_models import ArmourBaneApplication
from towr.domain.protection_models import ProtectionPreparationResult
from towr.domain.resolution_models import KernelAttackRequest,ResolutionResult
from towr.domain.turn_models import CombatRoundState
from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
from towr.domain.pc_magic_weapon_models import PcMagicWeaponAttackReceipt
from towr.domain.help_models import HelpBonusApplicationResult
from towr.domain.automatic_help_models import AutomaticHelpBonusApplicationResult
from towr.domain.test_models import Skill

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline
    from towr.domain.fate_models import FateGloriousSpendResult


IMMEDIATE_ATTACK_RULE_ID='RULE-COMBAT-004:immediate-attack-execution'


@dataclass(frozen=True,slots=True)
class PcBashDecisionProof:
    source_index:int
    grant:BashAttackGrant
    selection:BashWeaponSelection|None

    def __post_init__(self):
        if type(self.source_index) is not int or self.source_index<0:
            raise TypeError('Bash decision requires its actual triggering journal index')
        if type(self.grant) is not BashAttackGrant:
            raise TypeError('Bash decision requires its complete actual permission')
        replace(self.grant)
        if self.selection is not None:
            if type(self.selection) is not BashWeaponSelection:
                raise TypeError('Bash decision requires its exact physical selection')
            replace(self.selection)
            if self.selection.use.actor_id!=self.grant.actor_id:
                raise ValueError('Bash selected another actor implements')
            identity=lambda inventory:tuple((item.id,item.source,item.initial_actor_id,item.source_item_id,item.unit_index)
                for item in inventory.items)
            if identity(self.selection.use.inventory)!=identity(self.grant.weapon_use.inventory):
                raise ValueError('Bash readiness cannot invent, replace or erase initial physical units')


@dataclass(frozen=True,slots=True)
class PcImmediateStrikeRequest:
    decision:PcBashDecisionProof
    source_round:CombatRoundState
    kernel_request:KernelAttackRequest
    weapon_intent:PcAttackWeaponIntent

    def __post_init__(self):
        if (type(self.decision) is not PcBashDecisionProof or type(self.source_round) is not CombatRoundState
                or type(self.kernel_request) is not KernelAttackRequest
                or type(self.weapon_intent) is not PcAttackWeaponIntent):
            raise TypeError('immediate strike requires its exact permission, clock, K1 and weapon intent')
        for value in (self.decision,self.source_round,self.kernel_request,self.weapon_intent):replace(value)
        choice=self.decision.selection
        if choice is None:
            raise ValueError('a declined Bash permission cannot execute an immediate strike')
        if self.source_round!=self.grant.source_execution.state:
            raise ValueError('Bash must use its completed parent clock without another action')
        if (self.weapon_intent.action_id!=self.id or self.weapon_intent.actor_id!=self.actor_id
                or self.weapon_intent.target_id!=self.target_id
                or self.weapon_intent.attack_skill is not Skill.MELEE or self.weapon_intent.mount_attack
                or self.weapon_intent.attack_use!=choice.use
                or self.kernel_request.target_id!=self.target_id
                or self.kernel_request.id!=self.id+':kernel'):
            raise ValueError('immediate strike changed its granted target or committed Melee implements')

    @property
    def grant(self):return self.decision.grant
    @property
    def id(self):return self.grant.id
    @property
    def actor_id(self):return self.grant.actor_id
    @property
    def target_id(self):return self.grant.target_id
    @property
    def state(self):return self.source_round
    @property
    def slot_index(self):
        """Existing parent slot for follow-up provenance; never a fresh slot."""
        return self.grant.source_execution.slot_index


@dataclass(frozen=True,slots=True)
class PcImmediateStrikeExecutionResult:
    source_request:PcImmediateStrikeRequest
    resolution:ResolutionResult

    def __post_init__(self):
        if type(self.source_request) is not PcImmediateStrikeRequest or type(self.resolution) is not ResolutionResult:
            raise TypeError('immediate execution requires its actual typed source and K1 result')
        if self.resolution.request_id!=self.source_request.kernel_request.id:
            raise ValueError('immediate K1 result belongs to another strike')

    @property
    def request_id(self):return self.source_request.id
    @property
    def actor_id(self):return self.source_request.actor_id
    @property
    def target_id(self):return self.source_request.target_id
    @property
    def previous_state(self):return self.source_request.source_round
    @property
    def state(self):return self.source_request.source_round
    @property
    def applied_rule_ids(self):return (BASH_ATTACK_RULE_ID,IMMEDIATE_ATTACK_RULE_ID)


@dataclass(frozen=True,slots=True)
class PcImmediateStrikeProof:
    request:PcImmediateStrikeRequest
    protection:ProtectionPreparationResult
    resolution:ResolutionResult
    fate_decline:PcFateDecline|None=None
    glorious:FateGloriousSpendResult|None=None
    help_applications:tuple[HelpBonusApplicationResult,...]=()
    npc_help_applications:tuple[AutomaticHelpBonusApplicationResult,...]=()
    magic_weapon:PcMagicWeaponAttackReceipt|None=field(default=None,kw_only=True)
    armour_bane:ArmourBaneApplication|None=field(default=None,kw_only=True)

    def __post_init__(self):
        if (type(self.request) is not PcImmediateStrikeRequest
                or type(self.protection) is not ProtectionPreparationResult
                or type(self.resolution) is not ResolutionResult):
            raise TypeError('immediate strike proof requires its exact physical/K1 sources')
        for value in (self.request,self.protection,self.resolution):replace(value)
        PcImmediateStrikeExecutionResult(self.request,self.resolution)

    @property
    def weapon_intent(self):return self.request.weapon_intent
    @property
    def execution(self):return PcImmediateStrikeExecutionResult(self.request,self.resolution)
    @property
    def mount_attack(self):return None
    @property
    def npc_glorious_source(self):return None
