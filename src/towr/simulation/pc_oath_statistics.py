"""Actual Oath receipts after native replay, separate from tactical advice.

PC and original NPC source order is retained, including zero rows. A confirmed
pre-battle prayer grants no extra action observation; Fate prices come from
actual spend receipts, preserving Lucky's free first spend.
"""
from dataclasses import dataclass, replace

from towr.domain.fate_models import FateSpendFunding
from towr.domain.honour_bound_models import HonourBoundGloriousResult, HonourBoundUnmitigatedResult
from towr.domain.injury_models import CharacterWoundResult, ProfileWoundResult
from towr.domain.pc_oath_models import PcLadyPrayerProof, lady_wound_rule, oath_context_for
from towr.domain.talent_actor_models import npc_definition_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import has_talent


_FIELDS = ('prayers','wound_negations','glorious_activations','unmitigated_activations',
    'fate_spends','fate_session_cost')


@dataclass(frozen=True,slots=True)
class PcOathCount:
    actor_id: str
    prayers: int = 0
    wound_negations: int = 0
    glorious_activations: int = 0
    unmitigated_activations: int = 0
    fate_spends: int = 0
    fate_session_cost: int = 0

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Oath observations require an exact actor identifier')
        for name in _FIELDS:
            value = getattr(self,name)
            if type(value) is not int:
                raise TypeError('Oath '+name+' requires an exact integer')
            if value < 0:
                raise ValueError('Oath '+name+' cannot be negative')


def _sources(scenario):
    return (tuple((member.actor_id,member.talents) for member in scenario.party)
        +tuple((enemy.state.actor_id,npc_definition_acquired_talents(enemy.definition))
            for enemy in scenario.enemies))


def oath_count_actors(scenario):
    return tuple(actor for actor,talents in _sources(scenario)
        if any(has_talent(talents,talent) for talent in (TalentId.HONOUR_BOUND,TalentId.BLESSINGS_OF_THE_LADY)))


def _rows(counts,scenario):
    actors = oath_count_actors(scenario)
    if not actors:
        if counts is not None:
            raise ValueError('Oath observations require actual Honour Bound or Lady owners')
        return actors
    if type(counts) is not tuple or any(type(row) is not PcOathCount for row in counts):
        raise TypeError('Oath observations require every exact typed row, including zeros')
    for row in counts:
        replace(row)
    if tuple(row.actor_id for row in counts) != actors:
        raise ValueError('Oath rows must preserve all actual PC then NPC source owners in order')
    return actors


def validate_oath_counts(counts,scenario,*,trials,started_rounds,actions):
    for name,value in (('trials',trials),('started rounds',started_rounds),('actions',actions)):
        if type(value) is not int:
            raise TypeError('Oath '+name+' requires an exact integer')
        if value < 0:
            raise ValueError('Oath '+name+' cannot be negative')
    _rows(counts,scenario)
    if sum(row.prayers for row in counts or ()) > actions:
        raise ValueError('ordinary prayers exceed actual executed actions')
    talents = dict(_sources(scenario))
    party = {member.actor_id:member for member in scenario.party}
    for row in counts or ():
        owned = talents[row.actor_id]
        honour, lady = has_talent(owned,TalentId.HONOUR_BOUND),has_talent(owned,TalentId.BLESSINGS_OF_THE_LADY)
        context = oath_context_for(scenario,row.actor_id)
        uses = row.glorious_activations + row.unmitigated_activations
        if uses > trials or context is not None and context.honour_bound_used_this_session and uses:
            raise ValueError('Honour Bound activations exceed the actual unused once-session resource')
        if (not honour and (uses or row.fate_spends or row.fate_session_cost)
                or not lady and (row.prayers or row.wound_negations)):
            raise ValueError('Oath observations cannot grant a missing Talent effect')
        if row.prayers > min(trials,started_rounds) or row.wound_negations > trials:
            raise ValueError('Lady observations exceed the actual first-own-turn or once-battle resource')
        if (context is not None and context.lady_prayer_before_battle_confirmed and row.prayers
                or context is not None and not context.in_good_standing_confirmed
                    and (row.prayers or uses or row.wound_negations)):
            raise ValueError('Oath observations contradict their explicit initial GM source')
        if row.fate_spends != row.unmitigated_activations or row.fate_session_cost > row.fate_spends:
            raise ValueError('Unmitigated observations require exactly their actual Fate spend and funding')
        if row.actor_id not in party:
            if row.unmitigated_activations or row.fate_spends or row.fate_session_cost:
                raise ValueError('NPC Oath observations cannot invent player Fate')
        else:
            fate = party[row.actor_id].fate
            free = trials*int(fate.lucky_free_spend_available)
            if (row.fate_session_cost > trials*fate.remaining_spends
                    or row.fate_session_cost < row.fate_spends-free):
                raise ValueError('Oath Fate observations exceed the actual initial pool and Lucky source')
        if not trials and any(getattr(row,name) for name in _FIELDS):
            raise ValueError('zero trials cannot contain Oath observations')


def validate_oath_fate_budget(counts,scenario,glorious_counts,aim,*,trials):
    """Oath, ordinary Glorious and Second Action share the real session pool."""
    ordinary={row.actor_id:row.count for row in glorious_counts}
    seconds={row.actor_id:row.count for row in aim.second_action_spend_counts} if aim is not None else {}
    party={member.actor_id:member for member in scenario.party}
    for row in counts or ():
        if not row.fate_spends:
            continue
        fate=party[row.actor_id].fate
        other=ordinary.get(row.actor_id,0)+seconds.get(row.actor_id,0)
        free=trials*int(fate.lucky_free_spend_available)
        oath_free=row.fate_spends-row.fate_session_cost
        # Each actual free first spend belongs to one use, not each Talent.
        minimum_other_cost=max(0,other-(free-oath_free))
        if row.fate_session_cost+minimum_other_cost>trials*fate.remaining_spends:
            raise ValueError('Oath and other Fate spends exceed the same actual session pool and Lucky source')


def sum_oath_counts(groups,scenario):
    if type(groups) is not tuple:
        raise TypeError('Oath summation requires an exact tuple of observation groups')
    actors = oath_count_actors(scenario)
    totals = {actor:dict.fromkeys(_FIELDS,0) for actor in actors}
    for counts in groups:
        _rows(counts,scenario)
        for row in counts or ():
            for name in _FIELDS:
                totals[row.actor_id][name] += getattr(row,name)
    return tuple(PcOathCount(actor,**totals[actor]) for actor in actors) if actors else None


def oath_observations(result):
    """Read only actual paid actions and completed resource ledgers after replay."""
    actors = oath_count_actors(result.source)
    if not actors:
        return None
    allies={ally.state.actor_id for ally in result.source.npc_allies}
    if type(result.steps) is not tuple or tuple(row.actor_id for row in result.state.oaths if row.actor_id not in allies) != actors:
        raise ValueError('Oath observations require the actual complete immutable owner journal')
    totals = {actor:dict.fromkeys(_FIELDS,0) for actor in actors}
    seen = set()
    for step in result.steps:
        proof = step.proof
        if type(proof) is PcLadyPrayerProof:
            replace(proof)
            source = proof.result.source_request
            actor = source.blessing.actor_id
            if actor in allies:continue
            key = (actor,source.id)
            if actor not in totals or key in seen:
                raise ValueError('ordinary prayer observation replaced or duplicated an actual owner receipt')
            seen.add(key)
            totals[actor]['prayers'] += 1
    for row in result.state.oaths:
        replace(row)
        if row.actor_id in allies:continue
        counted = totals[row.actor_id]
        use_ids = set()
        for activation in row.honour_uses:
            if type(activation) not in (HonourBoundGloriousResult,HonourBoundUnmitigatedResult):
                raise TypeError('Honour Bound observations require actual typed activation receipts')
            replace(activation)
            source = activation.source_request
            if source.id in use_ids or activation.state.actor_id != row.actor_id:
                raise ValueError('Honour Bound observation duplicated or changed its actual activation owner')
            use_ids.add(source.id)
            if type(activation) is HonourBoundGloriousResult:
                counted['glorious_activations'] += 1
            else:
                spend = activation.spend
                if (row.actor_id not in result.source.pc_activation_order
                        or spend not in result.state.participant(row.actor_id).fate.spends):
                    raise ValueError('Unmitigated observation has no actual spent player Fate receipt')
                counted['unmitigated_activations'] += 1
                counted['fate_spends'] += 1
                counted['fate_session_cost'] += int(spend.funding is FateSpendFunding.SESSION_POOL)
        wound_ids = set()
        for wound in row.lady_uses:
            if type(wound) not in (CharacterWoundResult,ProfileWoundResult):
                raise TypeError('Lady observation requires an actually consumed typed Wound result')
            if (wound.request_id in wound_ids or wound.negated_by_rule_id != lady_wound_rule(row.actor_id)
                    or type(wound) is ProfileWoundResult and wound.wounds_negated != 1
                    or type(wound) is CharacterWoundResult and wound.wound_accepted):
                raise ValueError('Lady observation duplicated or replaced its actual negated Wound')
            wound_ids.add(wound.request_id)
            counted['wound_negations'] += 1
        if row.lady is not None and bool(row.lady.negated_wound_id is not None) != bool(wound_ids):
            raise ValueError('Lady observation differs from the actual exhausted resource')
    counts = tuple(PcOathCount(actor,**totals[actor]) for actor in actors)
    validate_oath_counts(counts,result.source,trials=1,started_rounds=result.started_rounds,
        actions=result.executed_actions)
    return counts
