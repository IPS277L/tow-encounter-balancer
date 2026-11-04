"""Bounded PC reserve search with complete source/aggregate result chains."""
from dataclasses import dataclass, replace
from enum import Enum
from itertools import product
from math import prod

from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_models import PcMeleeFacts, PcMeleeScenario, validate_pc_melee_scenario_admission
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def _identifier(value: str, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f'{name} must be a string')
    if not value.strip():
        raise ValueError(f'{name} must not be blank')


def _integer(value: int, name: str, *, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError(f'{name} must be an integer')
    if value < minimum:
        raise ValueError(f'{name} must be at least {minimum}')


def _ordered(value, name: str) -> tuple:
    if type(value) not in (tuple, list):
        raise TypeError(f'{name} requires an ordered tuple or list')
    return tuple(value)


@dataclass(frozen=True, slots=True)
class PcMeleeCompositionGroup:
    group_id: str
    actor_ids: tuple[str, ...]
    minimum_count: int
    maximum_count: int

    def __post_init__(self) -> None:
        _identifier(self.group_id, 'group ID')
        actors = _ordered(self.actor_ids, 'group actors')
        for actor in actors:
            _identifier(actor, 'group actor ID')
        if not actors or len(set(actors)) != len(actors):
            raise ValueError('group actors must be nonempty and unique')
        _integer(self.minimum_count, 'minimum count')
        _integer(self.maximum_count, 'maximum count')
        if not self.minimum_count <= self.maximum_count <= len(actors):
            raise ValueError('group bounds must fit its actor reserve')
        object.__setattr__(self, 'actor_ids', actors)


@dataclass(frozen=True, slots=True)
class PcMeleeBalanceRequest:
    template: PcMeleeScenario
    groups: tuple[PcMeleeCompositionGroup, ...]
    facts: PcMeleeFacts
    master_seed: int
    trials_per_candidate: int
    max_candidates: int
    max_total_trials: int
    window: ObjectiveRateWindow
    top_k: int

    def __post_init__(self) -> None:
        validate_pc_melee_scenario_admission(self.template)
        if type(self.facts) is not PcMeleeFacts:
            raise TypeError('generation requires explicit PC family facts')
        replace(self.facts)
        if self.facts != self.template.facts:
            raise ValueError('family facts must match the complete template facts')
        if type(self.window) is not ObjectiveRateWindow:
            raise TypeError('balance requires an explicit objective window')
        replace(self.window)
        _integer(self.master_seed, 'master seed')
        _integer(self.trials_per_candidate, 'trials per candidate', minimum=1)
        if self.master_seed >= 1 << 64 or self.trials_per_candidate >= 1 << 64:
            raise ValueError('seed and trials per candidate must fit uint64')
        for name in ('max_candidates', 'max_total_trials', 'top_k'):
            _integer(getattr(self, name), name, minimum=1)
        groups = _ordered(self.groups, 'composition groups')
        if not groups:
            raise ValueError('balance requires at least one composition group')
        for group in groups:
            if type(group) is not PcMeleeCompositionGroup:
                raise TypeError('groups must contain PcMeleeCompositionGroup values')
            if type(group.actor_ids) is not tuple:
                raise TypeError('transported group actors must be canonical tuples')
            replace(group)
        if len({group.group_id for group in groups}) != len(groups):
            raise ValueError('composition group IDs must be unique')
        actors = tuple(actor for group in groups for actor in group.actor_ids)
        reserve = {enemy.state.actor_id: enemy for enemy in self.template.enemies}
        if len(set(actors)) != len(actors) or set(actors) != set(reserve):
            raise ValueError('groups must exactly partition all enemy profile NPCs')
        for group in groups:
            definition = reserve[group.actor_ids[0]].definition
            if any(reserve[actor].definition != definition for actor in group.actor_ids):
                raise ValueError('one composition group requires equal complete profile NPC definitions')
        object.__setattr__(self, 'groups', groups)
        if self.candidate_count == 0:
            raise ValueError('all-zero counts cannot form a PC encounter')
        if self.candidate_count > self.max_candidates:
            raise ValueError('composition grid exceeds max_candidates')
        if self.planned_trials > self.max_total_trials:
            raise ValueError('composition grid exceeds max_total_trials')

    @property
    def candidate_count(self) -> int:
        return prod(group.maximum_count-group.minimum_count+1 for group in self.groups)-int(
            all(group.minimum_count == 0 for group in self.groups))

    @property
    def planned_trials(self) -> int:
        return self.candidate_count*self.trials_per_candidate


def validate_pc_melee_balance_request(request: PcMeleeBalanceRequest) -> None:
    if type(request) is not PcMeleeBalanceRequest:
        raise TypeError('balance requires a PcMeleeBalanceRequest')
    if type(request.groups) is not tuple:
        raise TypeError('transported composition groups must be a canonical tuple')
    replace(request)


def pc_melee_count_vectors(request: PcMeleeBalanceRequest):
    """Call only after arithmetic admission; no subsets are built by preflight."""
    return (counts for counts in product(*(range(group.minimum_count, group.maximum_count+1)
             for group in request.groups)) if any(counts))


def pc_melee_candidate_id(request: PcMeleeBalanceRequest, counts: tuple[int, ...]) -> str:
    return request.template.id+':counts:'+','.join(map(str, counts))


def project_pc_melee_candidate(request: PcMeleeBalanceRequest, counts: tuple[int, ...]) -> PcMeleeSimulationRequest:
    """Exact ordered prefix projection; no tactical facts or policies are repaired."""
    validate_pc_melee_balance_request(request)
    if type(counts) is not tuple or len(counts) != len(request.groups):
        raise TypeError('count vector must be a tuple with one count per group')
    for group, count in zip(request.groups, counts):
        _integer(count, 'candidate count')
        if not group.minimum_count <= count <= group.maximum_count:
            raise ValueError('candidate count is outside its group bounds')
    if not any(counts):
        raise ValueError('a candidate must retain an enemy profile NPC')
    keep = {actor for group, count in zip(request.groups, counts) for actor in group.actor_ids[:count]}
    template = request.template
    scenario = replace(template, id=pc_melee_candidate_id(request, counts), facts=request.facts,
        enemies=tuple(enemy for enemy in template.enemies if enemy.state.actor_id in keep),
        enemy_activation_order=tuple(actor for actor in template.enemy_activation_order if actor in keep),
        party=tuple(replace(member,
            target_priority=tuple(actor for actor in member.target_priority if actor in keep),
            defeat_decisions=tuple(decision for decision in member.defeat_decisions if decision.target_id in keep))
            for member in template.party))
    return PcMeleeSimulationRequest(scenario, request.master_seed, request.trials_per_candidate)


@dataclass(frozen=True, slots=True)
class PcMeleeCandidateResult:
    candidate_id: str
    counts: tuple[int, ...]
    source_request: PcMeleeSimulationRequest
    summary: PcMeleeSimulationSummary
    assessment: PcMeleeCandidateAssessment

    def __post_init__(self) -> None:
        _identifier(self.candidate_id, 'candidate ID')
        counts = _ordered(self.counts, 'candidate counts')
        if not counts or not any(counts):
            raise ValueError('candidate count vector must be nonempty and nonzero')
        for count in counts:
            _integer(count, 'candidate count')
        for value, cls in ((self.source_request, PcMeleeSimulationRequest),
                           (self.summary, PcMeleeSimulationSummary),
                           (self.assessment, PcMeleeCandidateAssessment)):
            if type(value) is not cls:
                raise TypeError(f'candidate result requires {cls.__name__}')
            replace(value)
        if (self.summary.source_request != self.source_request
                or self.assessment.source_request != self.source_request
                or self.assessment.summary != self.summary):
            raise ValueError('candidate aggregate/assessment belongs to another complete request')
        if self.candidate_id != self.source_request.scenario.id:
            raise ValueError('candidate ID differs from its source scenario')
        object.__setattr__(self, 'counts', counts)


def select_pc_melee_candidate_ids(candidates: tuple[PcMeleeCandidateResult, ...], top_k: int) -> tuple[str, ...]:
    eligible = (candidate for candidate in candidates if candidate.assessment.window_match is True)
    ranked = sorted(eligible, key=lambda candidate: abs(
        candidate.assessment.objective_achieved_rate-candidate.assessment.window.target))
    return tuple(candidate.candidate_id for candidate in ranked[:top_k])


@dataclass(frozen=True, slots=True)
class PcMeleeBalanceResult:
    source_request: PcMeleeBalanceRequest
    candidates: tuple[PcMeleeCandidateResult, ...]
    selected_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_pc_melee_balance_request(self.source_request)
        candidates = _ordered(self.candidates, 'candidate results')
        if len(candidates) != self.source_request.candidate_count:
            raise ValueError('balance report must contain the complete candidate grid')
        for candidate, counts in zip(candidates, pc_melee_count_vectors(self.source_request)):
            if type(candidate) is not PcMeleeCandidateResult:
                raise TypeError('balance report candidates must be typed')
            if type(candidate.counts) is not tuple:
                raise TypeError('transported candidate counts must be a canonical tuple')
            replace(candidate)
            expected = project_pc_melee_candidate(self.source_request, counts)
            if (candidate.candidate_id != expected.scenario.id or candidate.counts != counts
                    or candidate.source_request != expected
                    or candidate.assessment.window != self.source_request.window):
                raise ValueError('balance candidate differs from the exact source projection')
        selected = _ordered(self.selected_candidate_ids, 'selected candidates')
        for candidate_id in selected:
            _identifier(candidate_id, 'selected candidate ID')
        if selected != select_pc_melee_candidate_ids(candidates, self.source_request.top_k):
            raise ValueError('selected candidates contradict the complete assessments/ranking')
        object.__setattr__(self, 'candidates', candidates)
        object.__setattr__(self, 'selected_candidate_ids', selected)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def planned_trials(self) -> int:
        return self.source_request.planned_trials

    @property
    def total_trials(self) -> int:
        return sum(candidate.summary.trials for candidate in self.candidates)


class PcMeleeBalancePhase(str, Enum):
    GENERATION = 'generation'
    EVALUATION = 'evaluation'


def validate_pc_melee_balance_result(result: PcMeleeBalanceResult) -> None:
    """Re-admit the original cached result before serialization or other reuse."""
    if type(result) is not PcMeleeBalanceResult:
        raise TypeError('balance result must be a PcMeleeBalanceResult')
    if type(result.candidates) is not tuple or type(result.selected_candidate_ids) is not tuple:
        raise TypeError('transported balance collections must be canonical tuples')
    replace(result)


class PcMeleeBalanceExecutionError(RuntimeError):
    def __init__(self, phase: PcMeleeBalancePhase, candidate_id: str | None = None,
                 candidate_index: int | None = None) -> None:
        if type(phase) is not PcMeleeBalancePhase:
            raise TypeError('balance failure phase must be typed')
        if (candidate_id is None) != (candidate_index is None):
            raise ValueError('candidate failure context must include both ID and index')
        if candidate_id is not None:
            _identifier(candidate_id, 'failure candidate ID')
            _integer(candidate_index, 'failure candidate index')
        self.phase = phase
        self.candidate_id = candidate_id
        self.candidate_index = candidate_index
        super().__init__(f'PC melee balance {phase.value} failed')
