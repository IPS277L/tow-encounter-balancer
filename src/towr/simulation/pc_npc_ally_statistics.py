"""Fixed NPC ally observations, separate from hostile NPC and PC Fate totals."""
from dataclasses import dataclass,replace

from towr.domain.injury_models import CharacterInjuryState,injury_is_defeated,injury_wound_count
from towr.domain.turn_models import CombatActionKind


_FIELDS=('actions','attacks','recover_actions','defeated','wounds')


@dataclass(frozen=True,slots=True)
class PcNpcAllyCount:
    actor_id:str
    actions:int
    attacks:int
    recover_actions:int
    defeated:int
    wounds:int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC ally observations require an exact actor identifier')
        for name in _FIELDS:
            value=getattr(self,name)
            if type(value) is not int or value<0:
                raise TypeError('NPC ally observations require exact nonnegative integer counts')
        if self.recover_actions>self.actions:
            raise ValueError('NPC ally Recover observations exceed actual actions')


def validate_npc_ally_counts(counts,scenario,*,trials,started_rounds,actions):
    allies=scenario.npc_allies
    if not allies:
        if counts is not None:raise ValueError('NPC ally counts require actual fixed allied sources')
        return
    if type(counts) is not tuple or any(type(row) is not PcNpcAllyCount for row in counts):
        raise TypeError('NPC allies require exact immutable typed observations')
    if tuple(row.actor_id for row in counts)!=tuple(ally.state.actor_id for ally in allies):
        raise ValueError('NPC ally observations must preserve every source actor in order')
    from towr.domain.pc_mount_models import CombatMount
    from towr.domain.talent_actor_models import npc_definition_acquired_talents
    from towr.domain.talent_models import has_talent
    from towr.domain.talent_catalog import TalentId
    for source,row in zip(allies,counts,strict=True):
        replace(row)
        if row.actions>2*started_rounds or row.defeated>trials:
            raise ValueError('NPC ally observations exceed their actual round/trial budget')
        components=source.definition.generated_components
        mounted=(components is not None and components.mount is CombatMount.DEMIGRYPH)
        bash=has_talent(npc_definition_acquired_talents(source.definition),TalentId.BASH_ATTACK)
        # A paired mount strike belongs to each real Attack action, including
        # a legal second action; it is not limited to one per round.
        free_budget=int(mounted)*row.actions+int(bash)*started_rounds
        if row.attacks+row.recover_actions>row.actions+free_budget:
            raise ValueError('NPC ally attacks require actual action or free-strike capacity')
        if type(source.state.injury) is not CharacterInjuryState and row.wounds>source.state.injury.wound_limit*trials:
            raise ValueError('NPC ally profile Wounds exceed its actual finite health')
    if sum(row.actions for row in counts)>actions:
        raise ValueError('NPC ally actions exceed total executed actions')


def observe_npc_allies(result):
    """Read actual newly executed slots and typed free-strike proofs after replay."""
    actors=tuple(ally.state.actor_id for ally in result.source.npc_allies)
    if not actors:return None
    totals={actor:dict.fromkeys(_FIELDS,0) for actor in actors}
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    seen=set()
    for step in result.steps:
        before=step.source.round_state.active_turn;after=step.state.round_state.active_turn
        if after is not None and after.actor_id in totals:
            previous=({slot.execution.id for slot in before.action_slots if slot.execution is not None}
                if before is not None and before.actor_id==after.actor_id else set())
            for slot in after.action_slots:
                receipt=slot.execution
                if receipt is None or receipt.id in previous:continue
                key=(after.actor_id,receipt.id)
                if key in seen:raise ValueError('NPC ally action receipt cannot be counted twice')
                seen.add(key)
                row=totals[after.actor_id];row['actions']+=1
                row['attacks']+=int(slot.declaration.kind is CombatActionKind.ATTACK)
                row['recover_actions']+=int(slot.declaration.kind is CombatActionKind.RECOVER)
        if type(step.proof) in (PcImmediateStrikeProof,PcDemigryphStrikeProof):
            request=step.proof.request;actor=request.actor_id
            if actor not in totals:continue
            key=(actor,request.id)
            if key in seen:raise ValueError('NPC ally free strike cannot be counted twice')
            seen.add(key);totals[actor]['attacks']+=1
    for actor in actors:
        injury=result.state.enemy(actor).state.injury
        totals[actor]['defeated']=int(injury_is_defeated(injury))
        totals[actor]['wounds']=injury_wound_count(injury)
    return tuple(PcNpcAllyCount(actor,**totals[actor]) for actor in actors)


def sum_npc_ally_counts(records,scenario):
    if not scenario.npc_allies:return None
    return tuple(PcNpcAllyCount(ally.state.actor_id,**{name:sum(getattr(record.npc_ally_counts[index],name)
        for record in records) for name in _FIELDS}) for index,ally in enumerate(scenario.npc_allies))
