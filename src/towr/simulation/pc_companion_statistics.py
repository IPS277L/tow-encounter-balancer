"""Source-ordered observations of real mount bodies, distinct from riders.

The caller admits complete native replay before extracting observations. These
totals grant no turn, Attack, Help, movement, wound or additional action budget.
"""
from dataclasses import dataclass, replace

from towr.domain.pc_companion_models import PcMountCompanionState, mount_companion_actor_id
from towr.domain.pc_mount_companion_owner import initial_pc_companions


_COUNT_FIELDS = ('retentions','remounts','eligible_turns','started_turns','waits',
    'recover_actions','movement_actions','departures','landings','wounds_at_end','defeats')


@dataclass(frozen=True, slots=True)
class PcCompanionCount:
    actor_id: str
    rider_id: str
    retentions: int = 0
    remounts: int = 0
    eligible_turns: int = 0
    started_turns: int = 0
    waits: int = 0
    recover_actions: int = 0
    movement_actions: int = 0
    departures: int = 0
    landings: int = 0
    wounds_at_end: int = 0
    defeats: int = 0

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('companion count requires its exact body actor identifier')
        if type(self.rider_id) is not str or not self.rider_id.strip():
            raise TypeError('companion count requires its exact rider identifier')
        if self.actor_id != mount_companion_actor_id(self.rider_id):
            raise ValueError('companion count must retain the actual rider-bound body identity')
        for field in _COUNT_FIELDS:
            value = getattr(self,field)
            if type(value) is not int:
                raise TypeError('companion '+field+' requires an exact integer')
            if value < 0:
                raise ValueError('companion '+field+' cannot be negative')


def companion_count_sources(scenario) -> tuple[PcMountCompanionState,...]:
    """Canonical all-initial-mount rows in PC then original NPC source order."""
    return initial_pc_companions(scenario)


def _source_rows(counts,scenario):
    sources = companion_count_sources(scenario)
    if not sources:
        if counts is not None:
            raise ValueError('companion counts require actual initial mount sources')
        return sources
    if type(counts) is not tuple or any(type(row) is not PcCompanionCount for row in counts):
        raise TypeError('companion counts require exact immutable typed rows, including zeros')
    for row in counts:
        replace(row)
    expected = tuple((row.snapshot.state.actor_id,row.rider_id) for row in sources)
    if tuple((row.actor_id,row.rider_id) for row in counts) != expected:
        raise ValueError('companion counts must preserve every canonical body/rider in source order, including zeros')
    return sources


def validate_companion_counts(counts,scenario,*,trials,started_rounds):
    """Validate per-trial or summed observations without adding permissions."""
    for name,value in (('trials',trials),('started rounds',started_rounds)):
        if type(value) is not int:
            raise TypeError('companion '+name+' requires an exact integer')
        if value < 0:
            raise ValueError('companion '+name+' cannot be negative')
    sources = _source_rows(counts,scenario)
    for row,source in zip(counts or (),sources,strict=True):
        if row.started_turns > row.eligible_turns or row.eligible_turns > started_rounds:
            raise ValueError('companion started turns exceed its actual eligible round clocks')
        if row.waits+row.recover_actions+row.movement_actions > row.started_turns:
            raise ValueError('passive companion observations exceed its actual started one-action turns')
        if row.remounts > row.retentions:
            raise ValueError('companion remounts require actual preceding retentions')
        if row.departures > trials or row.defeats > trials:
            raise ValueError('a companion can depart or be defeated at most once per trial')
        if row.wounds_at_end > source.snapshot.definition.wound_limit*trials:
            raise ValueError('companion final wounds exceed its own profile HP across trials')
        if trials == 0 and any(getattr(row,field) for field in _COUNT_FIELDS):
            raise ValueError('zero trials cannot contain companion observations')


def sum_companion_counts(count_groups,scenario):
    """Sum already extracted rows; final aggregate validation owns trial bounds."""
    if type(count_groups) is not tuple:
        raise TypeError('companion summation requires an exact ordered tuple of observation groups')
    sources = companion_count_sources(scenario)
    totals = {source.snapshot.state.actor_id:dict.fromkeys(_COUNT_FIELDS,0) for source in sources}
    for counts in count_groups:
        _source_rows(counts,scenario)
        for row in counts or ():
            for field in _COUNT_FIELDS:
                totals[row.actor_id][field] += getattr(row,field)
    return tuple(PcCompanionCount(source.snapshot.state.actor_id,source.rider_id,
        **totals[source.snapshot.state.actor_id]) for source in sources) if sources else None


def companion_observations(result):
    """Extract concrete receipts after caller replay, without replay or RNG here."""
    from towr.domain.turn_models import (CombatRoundAdvanceResult,CombatTurnStartResult,CombatRoundState,CombatSide,
        CombatActionSlot,ActionExecutionReceipt,ActionSlotGrant,CombatActionKind,ManoeuvreKind)
    from towr.domain.pc_mount_retention_models import PcMountRetentionProof
    from towr.domain.pc_back_in_saddle_models import BACK_IN_SADDLE_REMOUNT_PROOFS
    from towr.domain.pc_companion_turn_models import PcCompanionWaitProof
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
    from towr.domain.pc_broken_battlefield_models import PcBrokenRunProof
    from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldRunProof
    from towr.domain.pc_companion_departure_models import PcCompanionDepartureProof
    from towr.domain.pc_companion_landing_models import PcCompanionLandingProof
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types
    from towr.domain.pc_melee_result_models import PcHelpProof,PcNpcHelpProof,validate_pc_melee_source_types
    sources = companion_count_sources(result.source)
    if not sources:
        return None
    if type(result.steps) is not tuple:
        raise TypeError('companion observations require the exact ordered journal steps')
    originals = (*result.source.pc_activation_order,*result.source.npc_activation_order)
    totals = {source.snapshot.state.actor_id:dict.fromkeys(_COUNT_FIELDS,0) for source in sources}
    by_actor = {source.snapshot.state.actor_id:source for source in sources}
    initial_clock = result.steps[0].source.round_state if result.steps else result.state.round_state
    if (type(initial_clock) is not CombatRoundState or type(initial_clock.round_number) is not int
            or initial_clock.round_number != 1
            or tuple(row.entity_id for row in initial_clock.participants) != originals):
        raise ValueError('companion observations require the actual original round-one clock')
    clocks = {1:initial_clock}
    started = set()
    finished = set()
    seen = set()

    def actor_row(actor):
        if actor not in totals:
            raise ValueError('companion receipt belongs to a body outside its complete initial source')
        return totals[actor]

    def add_once(field,actor,key):
        identity = (field,actor,key)
        if identity in seen:
            raise ValueError('companion observation duplicated one actual source receipt')
        seen.add(identity)
        actor_row(actor)[field] += 1

    def completed_body_turn(actor,round_number):
        key = (round_number,actor)
        if key not in started or key in finished:
            raise ValueError('companion wait/action lacks its one actual started turn')
        finished.add(key)

    def executed_body_action(proof,kind):
        slot = proof.result.slot
        if type(slot) is not CombatActionSlot:
            raise TypeError('companion action count requires its exact actually executed slot')
        replace(slot)
        execution = slot.execution
        if type(execution) is not ActionExecutionReceipt:
            raise ValueError('companion action count cannot use an unexecuted reservation')
        replace(execution)
        if (slot.index != 1 or slot.grant is not ActionSlotGrant.STANDARD or slot.declaration.kind is not kind
                or execution.actor_id != proof.actor_id or execution.source_request_id != proof.request.id
                or execution.round_number != proof.request.round_state.round_number
                or kind is CombatActionKind.MANOEUVRE and slot.declaration.manoeuvre is not ManoeuvreKind.RUN):
            raise ValueError('companion action observation changed its actual one standard Recover/Run source')

    for index,step in enumerate(result.steps):
        proof = step.proof
        if type(proof) is CombatRoundAdvanceResult:
            clock = proof.state
            if (type(clock) is not CombatRoundState or type(clock.round_number) is not int
                    or clock.round_number != len(clocks)+1):
                raise ValueError('companion eligible clocks must be actual consecutive once-only round advances')
            replace(clock)
            clocks[clock.round_number] = clock
        elif type(proof) is CombatTurnStartResult:
            actor = proof.turn.actor_id
            if actor not in totals:
                if actor not in originals:
                    raise ValueError('turn observation invented an actor outside the encounter source')
                continue
            replace(proof.turn); replace(proof.state)
            round_number = proof.state.round_number
            admitted = clocks.get(round_number)
            if (admitted is None or actor not in tuple(row.entity_id for row in admitted.participants)
                    or proof.turn.side is not by_actor[actor].snapshot.state.side
                    or proof.state.active_turn != proof.turn):
                raise ValueError('companion started turn lacks its actual admitted body clock and side')
            key = (round_number,actor)
            if key in started:
                raise ValueError('one companion turn cannot start twice in a round')
            started.add(key)
            totals[actor]['started_turns'] += 1
        elif type(proof) is PcMountRetentionProof:
            replace(proof)
            actor = proof.state.snapshot.state.actor_id
            if proof.history_index != index or proof.source.mount_id != actor:
                raise ValueError('companion retention observation lost its actual source/history position')
            add_once('retentions',actor,index)
        elif type(proof) in BACK_IN_SADDLE_REMOUNT_PROOFS:
            replace(proof)
            if proof.history_index != index:
                raise ValueError('companion remount observation changed its actual history position')
            add_once('remounts',proof.source.mount_id,index)
        elif type(proof) is PcCompanionWaitProof:
            replace(proof)
            actor = proof.result.completed_turn.actor_id
            completed_body_turn(actor,proof.result.state.round_number)
            if (proof.result.completed_turn.action_slots
                    or actor not in proof.result.state.completed_turn_entity_ids):
                raise ValueError('companion waiting cannot invent an action or omit its completed turn')
            totals[actor]['waits'] += 1
        elif type(proof) is PcBattlefieldRecoverProof and proof.actor_id in totals:
            replace(proof)
            actor = proof.actor_id
            executed_body_action(proof,CombatActionKind.RECOVER)
            completed_body_turn(actor,proof.request.round_state.round_number)
            totals[actor]['recover_actions'] += 1
        elif type(proof) in (PcBrokenRunProof,PcBattlefieldRunProof) and proof.actor_id in totals:
            replace(proof)
            actor = proof.actor_id
            executed_body_action(proof,CombatActionKind.MANOEUVRE)
            completed_body_turn(actor,proof.request.round_state.round_number)
            totals[actor]['movement_actions'] += 1
        elif type(proof) is PcCompanionDepartureProof:
            replace(proof)
            if proof.history_index != index:
                raise ValueError('companion departure observation changed its actual history position')
            add_once('departures',proof.actor_id,proof.actor_id)
        elif type(proof) is PcCompanionLandingProof:
            replace(proof)
            if proof.history_index != index:
                raise ValueError('companion landing observation changed its actual history position')
            add_once('landings',proof.body_id,(proof.wound_receipt_index,proof.turn_start_index))
        elif type(proof) in (*pc_kernel_attack_types(),PcHelpProof,PcNpcHelpProof) and proof.request.actor_id in totals:
            raise ValueError('the passive companion policy cannot observe an Attack or Help action')
    if tuple(clocks) != tuple(range(1,result.started_rounds+1)):
        raise ValueError('companion eligible observations lost an actual started-round clock')
    for clock in clocks.values():
        for participant in clock.participants:
            actor = participant.entity_id
            if actor in totals:
                if type(participant.side) is not CombatSide or participant.side is not by_actor[actor].snapshot.state.side:
                    raise ValueError('eligible companion clock changed its source side')
                totals[actor]['eligible_turns'] += 1
    final = result.state.companions
    if type(final) is not tuple or len(final) != len(sources):
        raise TypeError('companion observations require the complete exact final body bank')
    for body,source in zip(final,sources,strict=True):
        if type(body) is not PcMountCompanionState:
            raise TypeError('companion observation requires its exact final body row')
        replace(body)
        actor = source.snapshot.state.actor_id
        if (body.rider_id != source.rider_id or body.snapshot.state.actor_id != actor
                or body.snapshot.definition != source.snapshot.definition
                or body.snapshot.state.side is not source.snapshot.state.side):
            raise ValueError('companion observations changed canonical body membership, definition or side')
        validate_pc_melee_source_types(body.snapshot.definition,source.snapshot.definition)
        totals[actor]['wounds_at_end'] = body.snapshot.state.injury.wounds
        totals[actor]['defeats'] = int(body.snapshot.state.injury.defeated)
    rows = tuple(PcCompanionCount(source.snapshot.state.actor_id,source.rider_id,
        **totals[source.snapshot.state.actor_id]) for source in sources)
    validate_companion_counts(rows,result.source,trials=1,started_rounds=result.started_rounds)
    return rows
