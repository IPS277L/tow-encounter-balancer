"""Observations of actual music receipts, distinct from tactics and permissions.

The native caller admits complete replay before extraction. These counters do
not create a Test, inspiration, action, Fate spend or additional participant.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import has_talent
from towr.domain.talent_actor_models import npc_definition_acquired_talents


_FIELDS=('actions','pickups','inspired_allies','signals','protected_ties')


@dataclass(frozen=True,slots=True)
class PcMusicianCount:
    actor_id: str
    actions: int = 0
    pickups: int = 0
    inspired_allies: int = 0
    signals: int = 0
    protected_ties: int = 0

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('music count requires its exact musician actor identifier')
        for name in _FIELDS:
            value=getattr(self,name)
            if type(value) is not int:
                raise TypeError('music '+name+' requires an exact integer')
            if value<0:
                raise ValueError('music '+name+' cannot be negative')


def musician_count_actors(scenario):
    """Every actual owner in PC then original NPC source order, including zeros."""
    return (tuple(member.actor_id for member in scenario.party
            if has_talent(member.talents,TalentId.BATTLEFIELD_MUSICIAN))
        +tuple(enemy.state.actor_id for enemy in scenario.enemies
            if has_talent(npc_definition_acquired_talents(enemy.definition),TalentId.BATTLEFIELD_MUSICIAN)))


def _rows(counts,scenario):
    actors=musician_count_actors(scenario)
    if not actors:
        if counts is not None:
            raise ValueError('music observations require actual musician Talent sources')
        return actors
    if type(counts) is not tuple or any(type(row) is not PcMusicianCount for row in counts):
        raise TypeError('music observations require every exact typed row, including zeros')
    for row in counts:
        replace(row)
    if tuple(row.actor_id for row in counts)!=actors:
        raise ValueError('music observations must preserve every actual musician in source order')
    return actors


def validate_musician_counts(counts,scenario,*,trials,started_rounds,actions):
    for name,value in (('trials',trials),('started rounds',started_rounds),('actions',actions)):
        if type(value) is not int:
            raise TypeError('music '+name+' requires an exact integer')
        if value<0:
            raise ValueError('music '+name+' cannot be negative')
    _rows(counts,scenario)
    if sum(row.actions+row.pickups for row in counts or ())>actions:
        raise ValueError('music paid actions and pickups exceed actual executed actions')
    party={member.actor_id for member in scenario.party}
    opposition={enemy.state.actor_id for enemy in scenario.enemies}
    party_bodies=sum(member.mount is not None for member in scenario.party)
    npc_bodies=sum(enemy.definition.generated_components is not None
        and enemy.definition.generated_components.mount is not None for enemy in scenario.enemies)
    for row in counts or ():
        # At most two paid ordinary slots for a PC, one for an NPC. The
        # stricter shared budget checks require actual second-action receipts.
        budget=started_rounds*(2 if row.actor_id in party else 1)
        if row.actions+row.pickups>budget or row.signals>started_rounds:
            raise ValueError('music observations exceed this actor\'s actual turn/action ceilings')
        listeners=(len(party)+party_bodies-1 if row.actor_id in party else len(opposition)+npc_bodies-1)
        if row.inspired_allies>row.actions*listeners:
            raise ValueError('music beneficiaries exceed distinct actual allied source bodies per action')
        if row.protected_ties and not row.inspired_allies:
            raise ValueError('protected music ties require an actual earlier inspired ally')
        # Current native kernel families permit an ordinary strike, a paired
        # mount strike and an immediate strike per paid source. This is only
        # a conservative observation bound, not a new tabletop source limit.
        if row.protected_ties>3*actions:
            raise ValueError('protected music ties exceed current actual kernel attack opportunities')
        if not trials and any(getattr(row,name) for name in _FIELDS):
            raise ValueError('zero trials cannot contain music observations')


def sum_musician_counts(groups,scenario):
    if type(groups) is not tuple:
        raise TypeError('music summation requires an exact tuple of observation groups')
    actors=musician_count_actors(scenario)
    totals={actor:dict.fromkeys(_FIELDS,0) for actor in actors}
    for counts in groups:
        _rows(counts,scenario)
        for row in counts or ():
            for name in _FIELDS:
                totals[row.actor_id][name]+=getattr(row,name)
    return tuple(PcMusicianCount(actor,**totals[actor]) for actor in actors) if actors else None


def musician_observations(result):
    """Extract source-bound receipts once after caller replay, without RNG."""
    from towr.domain.pc_musician_effect_models import (
        PcMusicianActionProof,PcMusicianSignalProof,active_music_sources,pc_attack_tie_break,
    )
    from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types,pc_kernel_resolution
    from towr.domain.attack_models import defender_won_attack_opposition
    actors=musician_count_actors(result.source)
    if not actors:
        return None
    if type(result.steps) is not tuple:
        raise TypeError('music observations require the actual immutable native journal')
    totals={actor:dict.fromkeys(_FIELDS,0) for actor in actors}
    seen=set()

    def add(field,actor,identifier,amount=1):
        if actor not in totals:
            raise ValueError('music receipt belongs to an actor outside the complete musician source')
        key=(field,actor,identifier)
        if key in seen:
            raise ValueError('music observation duplicated one actual native source receipt')
        seen.add(key)
        totals[actor][field]+=amount

    for step in result.steps:
        proof=step.proof
        if type(proof) is PcMusicianActionProof:
            replace(proof)
            source=proof.result.source_request
            actor=source.source.actor_id
            add('actions',actor,source.id)
            add('inspired_allies',actor,source.id,len(proof.result.beneficiary_ids))
        elif type(proof) is PcMusicianRecoverProof:
            replace(proof)
            add('pickups',proof.equipment.actor_id,proof.result.request_id)
        elif type(proof) is PcMusicianSignalProof:
            replace(proof)
            receipt=proof.result.receipt
            add('signals',receipt.source.actor_id,receipt.source_turn)
        elif type(proof) in pc_kernel_attack_types():
            kernel=proof.request.kernel_request
            attack=pc_kernel_resolution(proof).attack
            if (attack.defender_test is None or attack.attacker_test.successes<=0
                    or attack.attacker_test.successes!=attack.defender_test.successes
                    or not defender_won_attack_opposition(kernel.attack,attack)):
                continue
            expected=pc_attack_tie_break(step.source,proof.request.actor_id,kernel.target_id)
            if expected is None or kernel.attack.tie_break!=expected:
                continue
            credited={source.source_request.source.actor_id for source in active_music_sources(step.source)
                if kernel.target_id in source.beneficiary_ids}
            for actor in credited:
                add('protected_ties',actor,kernel.id)
    return tuple(PcMusicianCount(actor,**totals[actor]) for actor in actors)
