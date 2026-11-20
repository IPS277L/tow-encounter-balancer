"""Faith entitlement and lifetime Miracle expenditure, PG1.4 III75/VII138–139.

Owner acquisition facts must be validated before use. This module derives
entitlements from that complete ownership source; it does not infer current
Strictures observance, execute Prayers, grant Fate or invent Miracle effects.
Actual effects still need their GM-approved scope and a runtime owner.
"""
from dataclasses import dataclass,field,replace

from towr.domain.faith_catalog import PrayerId,deity_definition
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent,DeityId,has_talent,talent_purchases


def _identifier(value,label):
    if type(value) is not str or not value.strip():
        raise TypeError(label+' requires an exact nonempty identifier')


@dataclass(frozen=True,slots=True)
class FaithAccess:
    talents:tuple[AcquiredTalent,...]
    miracles_spent:int=0
    deity:DeityId|None=field(init=False)
    has_favour:bool=field(init=False)
    prayers:tuple[PrayerId,...]=field(init=False)
    miracle_capacity:int=field(init=False)
    available_miracles:int=field(init=False)

    def __post_init__(self):
        count=talent_purchases(self.talents,TalentId.FAITH)
        if type(self.miracles_spent) is not int or self.miracles_spent<0:
            raise TypeError('Miracles spent requires an exact nonnegative lifetime count')
        if count and (has_talent(self.talents,TalentId.WIZARD)
                or has_talent(self.talents,TalentId.TOUCHED_BY_THE_WINDS)):
            raise ValueError('Faith access cannot coexist with spellcasting Talents')
        deity=(next(value for value in self.talents if value.id is TalentId.FAITH)
            .acquisitions[0].choice.deity if count else None)
        capacity=max(0,count-2)
        if self.miracles_spent>capacity:
            raise ValueError('Miracles spent exceeds actual one-use acquisitions')
        object.__setattr__(self,'deity',deity)
        object.__setattr__(self,'has_favour',count>=1)
        object.__setattr__(self,'prayers',deity_definition(deity).prayer_ids if count>=2 else ())
        object.__setattr__(self,'miracle_capacity',capacity)
        object.__setattr__(self,'available_miracles',capacity-self.miracles_spent)


def faith_access(talents:tuple[AcquiredTalent,...],miracles_spent:int=0)->FaithAccess:
    return FaithAccess(talents,miracles_spent)


def _access(source):
    if type(source) is not FaithAccess:
        raise TypeError('Miracle resource source requires exact FaithAccess')
    if replace(source)!=source:
        raise ValueError('cached Faith access differs from its actual acquired source')


@dataclass(frozen=True,slots=True)
class MiracleUse:
    """One expenditure witness, not a generic resolver of divine intervention."""
    use_id:str
    actor_id:str
    battle_id:str
    action_id:str
    scope_id:str
    gm_scope_confirmed:bool
    source:FaithAccess

    def __post_init__(self):
        for name in ('use_id','actor_id','battle_id','action_id','scope_id'):
            _identifier(getattr(self,name),'Miracle '+name)
        if type(self.gm_scope_confirmed) is not bool:
            raise TypeError('Miracle scope confirmation requires an exact bool')
        if not self.gm_scope_confirmed:
            raise ValueError('a Miracle requires an explicitly confirmed particular GM scope')
        _access(self.source)
        if self.source.available_miracles<1:
            raise ValueError('no acquired Miracle use remains')

    @property
    def result_access(self)->FaithAccess:
        replace(self)
        return faith_access(self.source.talents,self.source.miracles_spent+1)


@dataclass(frozen=True,slots=True)
class FaithMiracleLedger:
    actor_id:str
    initial_access:FaithAccess
    uses:tuple[MiracleUse,...]=()
    access:FaithAccess=field(init=False)

    def __post_init__(self):
        _identifier(self.actor_id,'Faith ledger actor')
        _access(self.initial_access)
        if type(self.uses) is not tuple or any(type(value) is not MiracleUse for value in self.uses):
            raise TypeError('Miracle ledger requires a tuple of exact expenditure witnesses')
        used_ids=set()
        used_sources=set()
        current=self.initial_access
        for use in self.uses:
            replace(use)
            if use.actor_id!=self.actor_id:
                raise ValueError('Miracle expenditure belongs to another actor')
            source_key=(use.battle_id,use.action_id,use.scope_id)
            if use.use_id in used_ids or source_key in used_sources:
                raise ValueError('the same Miracle invocation cannot be charged under repeated or aliased identities')
            if use.source!=current:
                raise ValueError('Miracle expenditure changed the actual preceding resource source')
            used_ids.add(use.use_id)
            used_sources.add(source_key)
            current=use.result_access
        object.__setattr__(self,'access',current)


def use_faith_miracle(ledger:FaithMiracleLedger,*,use_id:str,battle_id:str,
        action_id:str,scope_id:str,gm_scope_confirmed:bool)->FaithMiracleLedger:
    """Append one explicit expenditure without changing acquisitions or effects.

    A battle/session boundary is not a resource refill. Current Strictures and
    execution of the agreed scope remain the effect owner's responsibility.
    """
    if type(ledger) is not FaithMiracleLedger:
        raise TypeError('Miracle expenditure requires its exact actor ledger')
    if replace(ledger)!=ledger:
        raise ValueError('cached Miracle ledger differs from its actual receipt history')
    receipt=MiracleUse(use_id,ledger.actor_id,battle_id,action_id,scope_id,gm_scope_confirmed,ledger.access)
    return replace(ledger,uses=(*ledger.uses,receipt))
