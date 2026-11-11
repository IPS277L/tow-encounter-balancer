"""Budgeted adaptive generation of new NPC configurations, then Monte Carlo.

The simulator is injected. Neither NPC identity nor a supplied enemy reserve
defines the search space. Existing JSON families are unchanged.
"""
from dataclasses import dataclass, fields, replace
from hashlib import sha256
from math import isfinite, log, sqrt
from random import Random

from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, GeneratedAbility
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeFacts, PcMeleeParticipant, PcMeleeScenario, PC_RANGED_WEAPONS
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


@dataclass(frozen=True, slots=True)
class NpcSearchSpace:
    """Finite allowed values; no Cartesian grid is materialized."""
    weapon_skill: tuple[int, ...] = (2, 3, 4)
    strength: tuple[int, ...] = (2, 3, 4)
    toughness: tuple[int, ...] = (2, 3, 4)
    agility: tuple[int, ...] = (2, 3, 4)
    melee: tuple[int, ...] = (3, 4, 5)
    athletics: tuple[int, ...] = (3, 4, 5)
    weapon: tuple[GeneratedWeapon, ...] = (GeneratedWeapon.STAFF, GeneratedWeapon.DAGGER)
    light_armour: tuple[bool, ...] = (False, True)
    abilities: tuple[tuple[GeneratedAbility, ...], ...] = ((),)

    def __post_init__(self):
        baseline = {}
        for field in fields(self):
            choices = getattr(self, field.name)
            if type(choices) is not tuple or not choices or len(set(choices)) != len(choices):
                raise ValueError(f'{field.name} requires nonempty distinct tuple choices')
            baseline[field.name] = choices[0]
        # Linear validation of every option, not enumeration of combinations.
        for field in fields(self):
            for value in getattr(self, field.name):
                GeneratedNpc(**(baseline | {field.name: value}))

    def sample(self, rng: Random) -> GeneratedNpc:
        return GeneratedNpc(**{f.name: rng.choice(getattr(self, f.name)) for f in fields(self)})

    def mutate(self, npc: GeneratedNpc, rng: Random) -> GeneratedNpc:
        variable = [f.name for f in fields(self) if len(getattr(self, f.name)) > 1]
        if not variable:
            return npc
        name = rng.choice(variable)
        return replace(npc, **{name: rng.choice(tuple(v for v in getattr(self, name) if v != getattr(npc, name)))})


@dataclass(frozen=True, slots=True)
class DynamicEncounterRequest:
    party: tuple[PcMeleeParticipant, ...]
    facts: PcMeleeFacts
    day_id: str
    space: NpcSearchSpace
    minimum_npcs: int
    maximum_npcs: int
    target_win_rate: float
    target_rounds: float
    master_seed: int
    max_candidates: int
    exploration_trials: int
    finalist_trials: int
    top_k: int
    max_total_trials: int
    max_rounds: int
    defeat_disposition: NpcDefeatDisposition

    def __post_init__(self):
        if type(self.party) is not tuple or not self.party or any(type(p) is not PcMeleeParticipant for p in self.party):
            raise TypeError('party must be a nonempty tuple of typed PC participants')
        if len({p.actor_id for p in self.party}) != len(self.party):
            raise ValueError('party actor IDs must be unique')
        if type(self.facts) is not PcMeleeFacts or type(self.space) is not NpcSearchSpace:
            raise TypeError('generation requires typed facts and search space')
        replace(self.facts)
        replace(self.space)
        if not self.facts.all_opponents_close or self.facts.can_leave_zone:
            raise ValueError('initial dynamic slice requires the stationary all-Close arena')
        if any(p.pc.weapon in PC_RANGED_WEAPONS for p in self.party):
            raise ValueError('initial dynamic slice requires melee PCs')
        if type(self.day_id) is not str or not self.day_id.strip():
            raise ValueError('day ID is required')
        if type(self.defeat_disposition) is not NpcDefeatDisposition:
            raise TypeError('an explicit GM defeat disposition is required')
        for name in ('minimum_npcs', 'maximum_npcs', 'max_candidates', 'exploration_trials',
                'finalist_trials', 'top_k', 'max_total_trials', 'max_rounds'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        if self.minimum_npcs > self.maximum_npcs or self.top_k > self.max_candidates:
            raise ValueError('count bounds/top_k are inconsistent')
        if type(self.master_seed) is not int or not 0 <= self.master_seed < 2**64:
            raise ValueError('master seed must fit uint64')
        for name in ('target_win_rate', 'target_rounds'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError('targets must be finite numbers')
        if not 0 <= self.target_win_rate <= 1 or not 1 <= self.target_rounds <= self.max_rounds:
            raise ValueError('targets are outside encounter bounds')
        if self.max_candidates*self.exploration_trials + self.top_k*self.finalist_trials > self.max_total_trials:
            raise ValueError('search and independent validation exceed the trial budget')
        # Validate the actual execution bridge before spending any simulation budget.
        self.scenario(tuple(self.space.sample(Random(0)) for _ in range(self.maximum_npcs)), 'preflight')

    def scenario(self, composition: tuple[GeneratedNpc, ...], candidate_id: str) -> PcMeleeScenario:
        actors = tuple(f'generated-npc:{i+1}' for i in range(len(composition)))
        if set(actors) & {p.actor_id for p in self.party}:
            raise ValueError('generated actor IDs collide with party IDs')
        party = tuple(replace(p, target_priority=actors,
            defeat_decisions=tuple(MinionDefeatDecision(p.actor_id, a, self.defeat_disposition, True) for a in actors))
            for p in self.party)
        return PcMeleeScenario(candidate_id, party, self.day_id,
            tuple(n.participant(a) for n, a in zip(composition, actors)), self.facts,
            tuple(p.actor_id for p in party), actors, tuple(p.actor_id for p in party), self.max_rounds,
            None, (), npc_extra_attack_actor_ids=(), npc_grudge_policies=(), npc_blood_rage_actor_ids=(),
            npc_flagellant_policies=(), npc_warped_form_policies=())


@dataclass(frozen=True, slots=True)
class GeneratedCandidate:
    composition: tuple[GeneratedNpc, ...]
    summary: PcMeleeSimulationSummary

    def __post_init__(self):
        if type(self.composition) is not tuple or not self.composition or any(type(n) is not GeneratedNpc for n in self.composition):
            raise TypeError('candidate requires a nonempty typed composition')
        if type(self.summary) is not PcMeleeSimulationSummary:
            raise TypeError('candidate requires its typed aggregate')
        replace(self.summary)
        enemies = self.summary.source_request.scenario.enemies
        if len(enemies) != len(self.composition) or any(
                npc.participant(enemy.state.actor_id) != enemy for npc, enemy in zip(self.composition, enemies)):
            raise ValueError('candidate components do not match the complete executable source')

    @property
    def win_rate(self):
        return self.summary.outcome_counts.objective_achieved / self.summary.trials

    @property
    def mean_started_rounds(self):
        return self.summary.total_started_round_count / self.summary.trials

    @property
    def win_interval_95(self):
        """Wilson interval; conditional on this fixed candidate and tactics."""
        n, p, z = self.summary.trials, self.win_rate, 1.959963984540054
        denominator = 1 + z*z/n
        center = (p + z*z/(2*n))/denominator
        half = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
        return max(0., center-half), min(1., center+half)

    @property
    def rounds_interval_95(self):
        """Conservative Hoeffding bound for started rounds, including censored trials."""
        maximum = self.summary.source_request.scenario.max_rounds
        half = (maximum-1)*sqrt(log(40)/(2*self.summary.trials))
        return max(1., self.mean_started_rounds-half), min(float(maximum), self.mean_started_rounds+half)


@dataclass(frozen=True, slots=True)
class DynamicEncounterResult:
    source: DynamicEncounterRequest
    explored: tuple[GeneratedCandidate, ...]
    validations: tuple[GeneratedCandidate, ...]
    total_trials: int
    proposal_attempts: int
    proposal_limit_reached: bool

    @property
    def finalists(self):
        return tuple(c for c in self.validations if not c.summary.outcome_counts.unsupported_path)


def _seed(master: int, stage: str, index: int) -> int:
    return int.from_bytes(sha256(f'towr:dynamic:v1:{master}:{stage}:{index}'.encode()).digest()[:8], 'big')


def search_dynamic_encounter(request: DynamicEncounterRequest, simulator=None) -> DynamicEncounterResult:
    """Explore random restarts and local mutations, then independently validate.

    Ranking: no unsupported observations, distance to win target, distance to
    duration target, proposal order. The result makes no global-optimum claim.
    """
    if type(request) is not DynamicEncounterRequest:
        raise TypeError('expected a DynamicEncounterRequest')
    replace(request)
    if simulator is None:
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        simulator = lambda source: summarize_pc_melee_simulation(run_pc_melee_simulation(source))
    if not callable(simulator):
        raise TypeError('simulator must be callable')
    rng = Random(_seed(request.master_seed, 'proposals', 0))
    explored, seen = [], set()

    def score(candidate):
        return (bool(candidate.summary.outcome_counts.unsupported_path),
            abs(candidate.win_rate-request.target_win_rate),
            abs(candidate.mean_started_rounds-request.target_rounds))

    def evaluate(composition, stage, index):
        scenario = request.scenario(composition, f'dynamic:{stage}:{index}')
        trials = request.exploration_trials if stage == 'explore' else request.finalist_trials
        source = PcMeleeSimulationRequest(scenario, _seed(request.master_seed, stage, index), trials)
        summary = simulator(source)
        if type(summary) is not PcMeleeSimulationSummary:
            raise TypeError('simulator must return a typed aggregate')
        replace(summary)
        if summary.source_request != source:
            raise ValueError('simulator returned another candidate/seed/trial source')
        return GeneratedCandidate(composition, summary)

    attempts, limit = 0, request.max_candidates*30
    while len(explored) < request.max_candidates and attempts < limit:
        attempts += 1
        if explored and rng.random() < .7:
            elite = sorted(explored, key=score)[:max(1, request.top_k)]
            composition = list(rng.choice(elite).composition)
            if request.minimum_npcs != request.maximum_npcs and rng.random() < .25:
                if len(composition) < request.maximum_npcs and (len(composition) == request.minimum_npcs or rng.random() < .5):
                    composition.append(request.space.sample(rng))
                else:
                    composition.pop(rng.randrange(len(composition)))
            else:
                index = rng.randrange(len(composition))
                composition[index] = request.space.mutate(composition[index], rng)
            composition = tuple(composition)
        else:
            composition = tuple(request.space.sample(rng) for _ in range(rng.randint(request.minimum_npcs, request.maximum_npcs)))
        if composition in seen:
            continue
        seen.add(composition)
        explored.append(evaluate(composition, 'explore', len(explored)))
    eligible = [c for c in sorted(explored, key=score) if not c.summary.outcome_counts.unsupported_path]
    validated = [evaluate(c.composition, 'validate', i) for i, c in enumerate(eligible[:request.top_k])]
    # Failed validation remains visible in explored/validation observations, never a selected recommendation.
    finalists = tuple(sorted(validated, key=score))
    total = len(explored)*request.exploration_trials + len(validated)*request.finalist_trials
    return DynamicEncounterResult(request, tuple(explored), finalists, total, attempts,
        attempts == limit and len(explored) < request.max_candidates)
