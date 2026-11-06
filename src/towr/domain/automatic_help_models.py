"""Source-bound no-Test Help with one uncapped die or one free success."""
from __future__ import annotations

from dataclasses import dataclass,fields,is_dataclass,replace
from enum import Enum

from towr.domain.condition_models import Condition,ConditionState
from towr.domain.test_models import (
    DiceModifier,InlineProfile,TestProfile,Skill,TestRequest,QualityModifier,SuccessModifier,RerollLock,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,ActionSlotGrant,CombatActionDeclaration,CombatActionKind,
    CombatActionSlot,CombatRoundState,CombatSide,CombatTurnParticipant,CombatTurnState,
)


AUTOMATIC_HELP_ACTION_RULE_ID='RULE-COMBAT-004:automatic-help-action'


class AutomaticHelpEffectKind(str,Enum):
    BONUS_DIE_BEYOND_CAP='bonus_die_beyond_cap'
    FREE_SUCCESS='free_success'


def _exact(value,cls,label):
    if type(value) is not cls:
        raise TypeError(f'{label} must retain its exact {cls.__name__} type')


def _identifier(value,label):
    _exact(value,str,label)
    if not value.strip():
        raise ValueError(f'{label} must be nonempty')


def _same(actual,expected,label):
    _exact(actual,type(expected),label)
    if actual!=expected:
        raise ValueError(label)
    if is_dataclass(expected):
        for item in fields(expected):
            _same(getattr(actual,item.name),getattr(expected,item.name),label)
    elif type(expected) is tuple:
        for left,right in zip(actual,expected,strict=True):
            _same(left,right,label)


def _readmit_clock(state):
    _exact(state,CombatRoundState,'automatic Help clock')
    for name in ('participants','side_order','completed_turn_entity_ids','excluded_turn_entity_ids'):
        _exact(getattr(state,name),tuple,name)
    for participant in state.participants:
        _exact(participant,CombatTurnParticipant,'clock participant')
        _identifier(participant.entity_id,'clock actor ID')
        _exact(participant.side,CombatSide,'clock participant side')
        replace(participant)
    for side in state.side_order:
        _exact(side,CombatSide,'clock side order')
    for actor in (*state.completed_turn_entity_ids,*state.excluded_turn_entity_ids):
        _identifier(actor,'clock completed/excluded actor')
    if state.active_turn is not None:
        turn=state.active_turn
        _exact(turn,CombatTurnState,'active turn')
        _identifier(turn.actor_id,'active actor')
        _exact(turn.side,CombatSide,'active side')
        _exact(turn.action_slots,tuple,'action slots')
        for slot in turn.action_slots:
            _exact(slot,CombatActionSlot,'action slot')
            _exact(slot.grant,ActionSlotGrant,'action slot grant')
            _exact(slot.declaration,CombatActionDeclaration,'action declaration')
            _exact(slot.declaration.kind,CombatActionKind,'action kind')
            replace(slot.declaration)
            if slot.grant_rule_id is not None:
                _identifier(slot.grant_rule_id,'action grant Rule ID')
            if slot.execution is not None:
                receipt=slot.execution
                _exact(receipt,ActionExecutionReceipt,'action receipt')
                for name in ('id','executor_rule_id','source_request_id','result_request_id','actor_id'):
                    _identifier(getattr(receipt,name),name)
                _same(receipt.declaration,slot.declaration,'execution declaration differs from reserved slot')
                replace(receipt)
            replace(slot)
        replace(turn)
    replace(state)


def _readmit_test(test):
    _exact(test,TestRequest,'automatic Help target Test')
    _identifier(test.id,'target Test ID')
    if type(test.profile) not in (InlineProfile,TestProfile):
        raise TypeError('automatic Help target requires an exact numeric Test profile')
    replace(test.profile)
    for name,cls in (('dice_modifiers',DiceModifier),('quality_modifiers',QualityModifier),
            ('success_modifiers',SuccessModifier),('reroll_locks',RerollLock)):
        values=getattr(test,name)
        _exact(values,tuple,name)
        for value in values:
            _exact(value,cls,name)
            _identifier(value.rule_id,'Test modifier source')
            if cls is DiceModifier:
                _exact(value.bypasses_pool_cap,bool,'bypass eligibility')
            elif cls is QualityModifier and value.source_id is not None:
                _identifier(value.source_id,'quality modifier source')
            replace(value)
    replace(test)


@dataclass(frozen=True,slots=True)
class AutomaticHelpActionRequest:
    id:str
    round_state:CombatRoundState
    actor_id:str
    actor_conditions:ConditionState
    beneficiary_id:str
    beneficiary_test_id:str
    slot_index:int
    beneficiary_skill:Skill
    source_rule_id:str
    effect_kind:AutomaticHelpEffectKind
    rule_id:str=AUTOMATIC_HELP_ACTION_RULE_ID

    def __post_init__(self):
        for name in ('id','actor_id','beneficiary_id','beneficiary_test_id','source_rule_id','rule_id'):
            _identifier(getattr(self,name),name)
        if self.rule_id!=AUTOMATIC_HELP_ACTION_RULE_ID:
            raise ValueError('automatic Help requires its canonical action rule')
        _readmit_clock(self.round_state)
        _exact(self.beneficiary_skill,Skill,'beneficiary Skill')
        _exact(self.effect_kind,AutomaticHelpEffectKind,'automatic Help effect kind')
        _exact(self.slot_index,int,'slot index')
        if self.slot_index not in (1,2):
            raise ValueError('automatic Help slot index must be1 or2')
        _exact(self.actor_conditions,ConditionState,'helper Conditions')
        _exact(self.actor_conditions.conditions,frozenset,'helper Condition flags')
        for condition in self.actor_conditions.conditions:
            _exact(condition,Condition,'helper Condition')
        replace(self.actor_conditions)
        if any(self.actor_conditions.has(c) for c in (Condition.DEAFENED,Condition.DEFENCELESS)):
            raise ValueError('Deafened or Defenceless actors cannot Help')
        turn=self.round_state.active_turn
        if turn is None or turn.actor_id!=self.actor_id:
            raise ValueError('automatic Help requires the actual active actor')
        if self.actor_id==self.beneficiary_id:
            raise ValueError('automatic Help requires another actor')
        if self.round_state.participant_for(self.actor_id).side is not self.round_state.participant_for(self.beneficiary_id).side:
            raise ValueError('automatic Help beneficiary must be an ally')
        if self.slot_index>len(turn.action_slots):
            raise ValueError('automatic Help requires a reserved slot')
        if any(not slot.executed for slot in turn.action_slots[:self.slot_index-1]):
            raise ValueError('earlier action slots must complete first')
        slot=turn.action_slots[self.slot_index-1]
        if slot.declaration.kind is not CombatActionKind.HELP or slot.executed:
            raise ValueError('automatic Help requires one unexecuted Help slot')


@dataclass(frozen=True,slots=True)
class AutomaticHelpBonusSnapshot:
    id:str
    source_request_id:str
    helper_id:str
    beneficiary_id:str
    beneficiary_test_id:str
    beneficiary_skill:Skill
    rule_id:str
    effect_kind:AutomaticHelpEffectKind

    def __post_init__(self):
        for name in ('id','source_request_id','helper_id','beneficiary_id','beneficiary_test_id','rule_id'):
            _identifier(getattr(self,name),name)
        _exact(self.beneficiary_skill,Skill,'bonus beneficiary Skill')
        _exact(self.effect_kind,AutomaticHelpEffectKind,'automatic Help bonus kind')
        if self.helper_id==self.beneficiary_id:
            raise ValueError('automatic Help requires another actor')
        if self.id!=self.source_request_id+':bonus':
            raise ValueError('automatic Help bonus ID lacks its actual source action')

    @property
    def bonus_dice(self)->int:
        _exact(self.effect_kind,AutomaticHelpEffectKind,'automatic Help bonus kind')
        return int(self.effect_kind is AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP)

    @property
    def bonus_successes(self)->int:
        _exact(self.effect_kind,AutomaticHelpEffectKind,'automatic Help bonus kind')
        return int(self.effect_kind is AutomaticHelpEffectKind.FREE_SUCCESS)

    @property
    def bypasses_pool_cap(self)->bool:
        _exact(self.effect_kind,AutomaticHelpEffectKind,'automatic Help bonus kind')
        return self.effect_kind is AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP


def _action_components(request):
    _exact(request,AutomaticHelpActionRequest,'automatic Help source')
    replace(request)
    turn=request.round_state.active_turn
    slot=turn.action_slots[request.slot_index-1]
    bonus=AutomaticHelpBonusSnapshot(request.id+':bonus',request.id,request.actor_id,
        request.beneficiary_id,request.beneficiary_test_id,request.beneficiary_skill,request.source_rule_id,
        request.effect_kind)
    executed=replace(slot,execution=ActionExecutionReceipt(request.id,request.rule_id,request.id,
        bonus.id,request.actor_id,request.round_state.round_number,slot.index,slot.declaration))
    state=replace(request.round_state,active_turn=replace(turn,action_slots=tuple(
        executed if item.index==request.slot_index else item for item in turn.action_slots)))
    return state,executed,bonus,(request.rule_id,request.source_rule_id)


@dataclass(frozen=True,slots=True)
class AutomaticHelpActionResult:
    request_id:str
    source_request:AutomaticHelpActionRequest
    previous_round_state:CombatRoundState
    round_state:CombatRoundState
    slot:CombatActionSlot
    bonus:AutomaticHelpBonusSnapshot
    applied_rule_ids:tuple[str,...]

    def __post_init__(self):
        state,slot,bonus,rules=_action_components(self.source_request)
        _readmit_clock(self.previous_round_state)
        _readmit_clock(self.round_state)
        _same((self.request_id,self.previous_round_state,self.round_state,self.slot,self.bonus,self.applied_rule_ids),
            (self.source_request.id,self.source_request.round_state,state,slot,bonus,rules),
            'automatic Help result changed its actual action/source/slot/bonus')


def expected_automatic_help_action(request:AutomaticHelpActionRequest)->AutomaticHelpActionResult:
    state,slot,bonus,rules=_action_components(request)
    return AutomaticHelpActionResult(request.id,request,request.round_state,state,slot,bonus,rules)


@dataclass(frozen=True,slots=True)
class AutomaticHelpBonusApplicationRequest:
    id:str
    help:AutomaticHelpActionResult
    beneficiary_id:str
    beneficiary_skill:Skill
    test:TestRequest

    def __post_init__(self):
        _identifier(self.id,'automatic Help application ID')
        _identifier(self.beneficiary_id,'automatic Help application beneficiary')
        _exact(self.help,AutomaticHelpActionResult,'automatic Help application source')
        replace(self.help)
        _exact(self.beneficiary_skill,Skill,'application beneficiary Skill')
        _readmit_test(self.test)
        bonus=self.help.bonus
        if (self.beneficiary_id!=bonus.beneficiary_id or self.beneficiary_skill is not bonus.beneficiary_skill
                or self.test.id!=bonus.beneficiary_test_id):
            raise ValueError('automatic Help application must use the exact intended actor/Skill/Test')


def _expected_automatic_help_application(request:AutomaticHelpBonusApplicationRequest):
    _exact(request,AutomaticHelpBonusApplicationRequest,'automatic Help application')
    replace(request)
    if request.help.bonus.effect_kind is AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP:
        modifier=DiceModifier(request.help.bonus.rule_id,1,True)
        return replace(request.test,dice_modifiers=(*request.test.dice_modifiers,modifier)),modifier
    modifier=SuccessModifier(request.help.bonus.rule_id,1)
    return replace(request.test,success_modifiers=(*request.test.success_modifiers,modifier)),modifier


@dataclass(frozen=True,slots=True)
class AutomaticHelpBonusApplicationResult:
    request_id:str
    source_request:AutomaticHelpBonusApplicationRequest
    test:TestRequest
    modifier:DiceModifier|SuccessModifier
    applied_rule_ids:tuple[str,...]

    def __post_init__(self):
        test,modifier=_expected_automatic_help_application(self.source_request)
        _readmit_test(self.test)
        _same((self.request_id,self.test,self.modifier,self.applied_rule_ids),
            (self.source_request.id,test,modifier,(self.source_request.help.source_request.rule_id,
                self.source_request.help.bonus.rule_id)),
            'automatic Help application changed its bound source or typed modifier')
