"""Explicit GM surgery risk, PG1.4 V122 and accepted ADR-0141 C24.

The book names risks, not their probabilities. A scene supplies every weight;
the receipt does not fabricate a Wounds Table result or another action.
"""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.combat_surgeon_surgery_models import CombatSurgeonBattleSurgeryActionResult
from towr.domain.injury_models import CharacterInjuryState, DecisionOwner, WoundRecord
from towr.domain.surgery_models import DowntimeSurgeryResult
from towr.domain.talent_test_source import validate_completed_talent_test

SURGERY_FAILURE_RESOLUTION_RULE_ID = 'RULE-HEALTH-010:surgery-failure-gm-resolution'


class SurgeryFailureOutcome(str, Enum):
    NO_COMPLICATION = 'no_complication'
    PERMANENT_DISFIGUREMENT = 'permanent_disfigurement'
    DEATH = 'death'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('surgery risk requires exact nonempty source identifiers')


@dataclass(frozen=True, slots=True)
class SurgeryRiskPolicy:
    id: str
    no_complication: int
    permanent_disfigurement: int
    death: int
    disfigurement_description: str | None = None
    owner: DecisionOwner = DecisionOwner.GM

    def __post_init__(self):
        _identifier(self.id)
        if self.owner is not DecisionOwner.GM:
            raise ValueError('only an explicit GM scene policy supplies surgical risks')
        for weight in (self.no_complication,self.permanent_disfigurement,self.death):
            if type(weight) is not int or weight < 0:
                raise TypeError('GM surgery weights must be nonnegative exact integers')
        if not self.total:
            raise ValueError('GM surgery policy needs at least one possible outcome')
        if self.permanent_disfigurement:
            _identifier(self.disfigurement_description)
        elif self.disfigurement_description is not None:
            raise ValueError('an unavailable disfigurement outcome has no narrative effect')

    @property
    def total(self):
        return self.no_complication+self.permanent_disfigurement+self.death

    def outcome_for(self,draw):
        if type(draw) is not int or not 1 <= draw <= self.total:
            raise ValueError('surgery draw must belong to its actual GM weights')
        if draw <= self.no_complication:
            return SurgeryFailureOutcome.NO_COMPLICATION
        if draw <= self.no_complication+self.permanent_disfigurement:
            return SurgeryFailureOutcome.PERMANENT_DISFIGUREMENT
        return SurgeryFailureOutcome.DEATH


@dataclass(frozen=True, slots=True)
class SurgeryFailureResolutionRequest:
    id: str
    surgery: CombatSurgeonBattleSurgeryActionResult | DowntimeSurgeryResult
    policy: SurgeryRiskPolicy
    injury_state: CharacterInjuryState
    consumed_risk_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _identifier(self.id)
        if type(self.surgery) not in (CombatSurgeonBattleSurgeryActionResult,DowntimeSurgeryResult):
            raise TypeError('surgery risk requires its actual completed surgical Test/action')
        replace(self.surgery.source_request)
        if type(self.surgery) is CombatSurgeonBattleSurgeryActionResult:
            replace(self.surgery.exacting.source_request)
            replace(self.surgery.exacting)
            test=self.surgery.exacting.test_result
        else:
            test=self.surgery.test_result
        validate_completed_talent_test(self.surgery.source_request.dexterity_test,test)
        replace(self.surgery)
        risk=self.surgery.failure_risk
        if risk is None:
            raise ValueError('successful surgery has no failed-Test risk to resolve')
        replace(risk)
        if type(risk.wound_sequence) is not int or type(self.surgery.source_request.wound_sequence) is not int:
            raise TypeError('surgical risk must preserve the exact operated Wound number')
        if type(self.policy) is not SurgeryRiskPolicy:
            raise TypeError('surgery risk needs its complete explicit GM policy')
        replace(self.policy)
        if type(self.injury_state) is not CharacterInjuryState:
            raise TypeError('surgery risk retains a real Character patient')
        replace(self.injury_state)
        if self.injury_state != self.surgery.state or self.injury_state.dead:
            raise ValueError('surgery risk must settle against its actual living patient before continuing')
        if type(self.consumed_risk_ids) is not tuple:
            raise TypeError('surgery risk ledger requires an exact ordered tuple')
        for value in self.consumed_risk_ids: _identifier(value)
        if len(set(self.consumed_risk_ids)) != len(self.consumed_risk_ids) or risk.id in self.consumed_risk_ids:
            raise ValueError('the same failed surgical Test cannot cause two risk outcomes')


@dataclass(frozen=True, slots=True)
class SurgeryDisfigurement:
    risk_id: str
    target_id: str
    wound: WoundRecord
    description: str

    def __post_init__(self):
        for value in (self.risk_id,self.target_id,self.description): _identifier(value)
        if type(self.wound) is not WoundRecord:
            raise TypeError('permanent surgical disfigurement retains its actual operated Wound')
        replace(self.wound)


@dataclass(frozen=True, slots=True)
class SurgeryFailureResolutionResult:
    source_request: SurgeryFailureResolutionRequest
    draw: int
    outcome: SurgeryFailureOutcome
    state: CharacterInjuryState
    disfigurement: SurgeryDisfigurement | None
    consumed_risk_ids: tuple[str, ...]
    rule_id: str = SURGERY_FAILURE_RESOLUTION_RULE_ID

    def __post_init__(self):
        if type(self.source_request) is not SurgeryFailureResolutionRequest:
            raise TypeError('surgery risk result must retain its exact request')
        replace(self.source_request)
        expected=_expected_surgery_failure(self.source_request,self.draw)
        actual=(self.outcome,self.state,self.disfigurement,self.consumed_risk_ids)
        if actual != expected or type(self.outcome) is not SurgeryFailureOutcome:
            raise ValueError('surgery outcome changed its GM policy, patient or single-use ledger')
        if self.rule_id != SURGERY_FAILURE_RESOLUTION_RULE_ID:
            raise ValueError('surgery risk result requires its actual resolution rule')
        if type(self.state) is not CharacterInjuryState or type(self.state.dead) is not bool:
            raise TypeError('surgical outcome preserves its exact Character state and death flag')
        if type(self.consumed_risk_ids) is not tuple or type(self.rule_id) is not str:
            raise TypeError('surgical outcome must retain its exact ledger and rule identifier')
        if self.disfigurement is not None:
            if type(self.disfigurement) is not SurgeryDisfigurement:
                raise TypeError('surgical disfigurement requires its actual persistent fact')
            replace(self.disfigurement)


def _expected_surgery_failure(request,draw):
    outcome=request.policy.outcome_for(draw)
    risk=request.surgery.failure_risk
    state=replace(request.injury_state,dead=True) if outcome is SurgeryFailureOutcome.DEATH else request.injury_state
    disfigurement=None
    if outcome is SurgeryFailureOutcome.PERMANENT_DISFIGUREMENT:
        wound=request.injury_state.wounds[risk.wound_sequence-1]
        disfigurement=SurgeryDisfigurement(risk.id,risk.target_id,wound,request.policy.disfigurement_description)
    return outcome,state,disfigurement,(*request.consumed_risk_ids,risk.id)
