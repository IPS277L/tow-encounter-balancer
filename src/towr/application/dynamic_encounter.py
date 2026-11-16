"""Budgeted adaptive generation of new NPC configurations, then Monte Carlo.

The simulator is injected. Neither NPC identity nor a supplied enemy reserve
defines the search space. Existing JSON families are unchanged.
"""
from dataclasses import dataclass, fields, replace
from enum import Enum
from hashlib import sha256
from math import isfinite, log, sqrt
from random import Random

from towr.domain.generated_npc_models import (GeneratedNpc,GeneratedWeapon,GeneratedAbility,
    GeneratedTalent,generated_talent_requirements_met,GeneratedRangedFacts,GENERATED_RANGED_WEAPONS)
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
    defence: tuple[int, ...] = (3, 4, 5)
    weapon: tuple[GeneratedWeapon, ...] = tuple(GeneratedWeapon)
    light_armour: tuple[bool, ...] = (False, True)
    shield: tuple[bool, ...] = (False, True)
    abilities: tuple[tuple[GeneratedAbility, ...], ...] = ((),)
    allowed_talents: tuple[GeneratedTalent,...] = tuple(GeneratedTalent)
    ballistic_skill: tuple[int, ...] = (2, 3, 4)
    shooting: tuple[int, ...] = (3, 4, 5)
    initiative: tuple[int, ...] = (2, 3, 4)
    dexterity: tuple[int, ...] = (3, 4, 5)

    def __post_init__(self):
        if (type(self.allowed_talents) is not tuple
                or any(type(t) is not GeneratedTalent for t in self.allowed_talents)
                or len(set(self.allowed_talents)) != len(self.allowed_talents)):
            raise ValueError('allowed_talents requires unique supported Talents; empty disables generation')
        for name in (*self._ordinary_names(), *self._ranged_names()):
            choices = getattr(self,name)
            if type(choices) is not tuple or not choices or len(set(choices)) != len(choices):
                raise ValueError(f'{name} requires nonempty distinct tuple choices')
            for value in choices:
                if name in ('weapon_skill','strength','toughness','agility','ballistic_skill','initiative'):
                    if type(value) is not int or value < 1:
                        raise ValueError(f'{name} choices must be positive integers')
                elif name in ('melee','athletics','defence','shooting','dexterity'):
                    if type(value) is not int or not 2 <= value <= 6:
                        raise ValueError(f'{name} choices must be integers in 2..6')
                elif name == 'weapon' and type(value) is not GeneratedWeapon:
                    raise ValueError('weapon choices must be supported typed weapons')
                elif name in ('light_armour','shield') and type(value) is not bool:
                    raise ValueError('equipment choices must be exact booleans')
                elif name == 'abilities':
                    if (type(value) is not tuple or any(type(a) is not GeneratedAbility for a in value)
                            or len(set(value)) != len(value)):
                        raise ValueError('ability groups must be unique supported typed tuples')
        if any(weapon in GENERATED_RANGED_WEAPONS for weapon in self.weapon) and False not in self.shield:
            raise ValueError('ranged weapon choices need an admissible no-Shield loadout')
        if True in self.shield and all(weapon in GENERATED_RANGED_WEAPONS for weapon in self.weapon):
            raise ValueError('Shield choice has no admissible melee weapon')

    @staticmethod
    def _ranged_names():
        return ('ballistic_skill','shooting','initiative','dexterity')

    @staticmethod
    def _ordinary_names():
        return ('weapon_skill','strength','toughness','agility','melee','athletics','defence',
            'weapon','light_armour','shield','abilities')

    def _build(self, facts, talents=(), ranged_values=None):
        ranged=None
        if facts['weapon'] in GENERATED_RANGED_WEAPONS:
            values=ranged_values or {name:getattr(self,name)[0] for name in self._ranged_names()}
            blackpowder=facts['weapon'] is not GeneratedWeapon.REPEATER_HANDBOW
            ranged=GeneratedRangedFacts(**values,initially_loaded=True,ammunition_supply_confirmed=True,
                has_blackpowder_lore=True if blackpowder else None,
                has_blackpowder_kit=True if blackpowder else None)
        return GeneratedNpc(**facts,talents=talents,ranged=ranged)

    def sample(self, rng: Random) -> GeneratedNpc:
        # Select a legal equipment branch before its conditional source facts.
        # No Shield is drawn then discarded, and melee sources draw no unused
        # ranged characteristics or skills.
        weapon=rng.choice(self.weapon)
        facts={name:rng.choice(getattr(self,name)) for name in self._ordinary_names()
            if name not in ('weapon','shield')}
        facts['weapon']=weapon
        facts['shield']=rng.choice(tuple(value for value in self.shield
            if weapon not in GENERATED_RANGED_WEAPONS or value is False))
        ranged_values=({name:rng.choice(getattr(self,name)) for name in self._ranged_names()}
            if weapon in GENERATED_RANGED_WEAPONS else None)
        talents=tuple(t for t in self.allowed_talents if generated_talent_requirements_met(t,
            weapon_skill=facts['weapon_skill'],strength=facts['strength']) and rng.randrange(2))
        return self._build(facts,talents,ranged_values)

    def mutate(self, npc: GeneratedNpc, rng: Random) -> GeneratedNpc:
        if type(npc) is not GeneratedNpc or not self.contains(npc):
            raise ValueError('mutation requires an admitted member of this component space')
        replace(npc)
        facts={name:getattr(npc,name) for name in self._ordinary_names()}
        ranged_values=({name:getattr(npc.ranged,name) for name in self._ranged_names()}
            if npc.ranged is not None else None)
        variable=[]
        for name in self._ordinary_names():
            values=[]
            for value in getattr(self,name):
                if value == getattr(npc,name):
                    continue
                try:
                    candidate=self._build(facts | {name:value},npc.talents,ranged_values)
                except ValueError:
                    continue
                values.append(candidate)
            if values:
                variable.append((name,tuple(values)))
        if npc.ranged is not None:
            for name in self._ranged_names():
                values=tuple(replace(npc,ranged=replace(npc.ranged,**{name:value}))
                    for value in getattr(self,name) if value != getattr(npc.ranged,name))
                if values:
                    variable.append((name,values))
        talent_options=[]
        for talent in self.allowed_talents:
            selected=tuple(t for t in self.allowed_talents if (t in npc.talents) != (t is talent))
            if all(generated_talent_requirements_met(t,weapon_skill=npc.weapon_skill,
                    strength=npc.strength) for t in selected):
                talent_options.append(replace(npc,talents=selected))
        if talent_options:
            variable.append(('talents',tuple(talent_options)))
        if not variable:
            return npc
        _,values=rng.choice(variable)
        return rng.choice(values)

    def contains(self,npc: GeneratedNpc) -> bool:
        if type(npc) is not GeneratedNpc:
            return False
        try:
            replace(npc)
        except (ValueError,TypeError):
            return False
        return (all(getattr(npc,name) in getattr(self,name) for name in self._ordinary_names())
            and (npc.ranged is None or all(getattr(npc.ranged,name) in getattr(self,name)
                for name in self._ranged_names()))
            and set(npc.talents) <= set(self.allowed_talents))


def automatic_npc_search_space(party: tuple[PcMeleeParticipant, ...]) -> NpcSearchSpace:
    """A bounded search envelope around the party, not a book NPC stat limit.

    The battle targets rank sampled compositions; they do not prescribe a
    monotonic stat multiplier. No authored abilities are granted implicitly.
    """
    if not party:
        raise ValueError('automatic NPC space needs a party')
    choices = {}
    for name in ('weapon_skill', 'strength', 'toughness', 'agility', 'melee', 'defence', 'athletics'):
        values = [getattr(p.pc, name) for p in party]
        floor, ceiling = (2, 6) if name in ('melee', 'defence', 'athletics') else (1, 10)
        low = max(floor, min(ceiling, min(values) - 1))
        high = max(low, min(ceiling, max(values) + 1))
        choices[name] = tuple(range(low, high + 1))
    # Include useful resistance near a mage's ordinary Lightning potency;
    # the physical-only envelope otherwise misses these candidate profiles.
    from towr.domain.pc_magic_source_models import PcSpellId
    toughness = set(choices['toughness'])
    for member in party:
        if member.wizard is not None and PcSpellId.LIGHTNING_BLAST in member.wizard.memorised_spells:
            pivot = min(10,4+(member.wizard.reason*member.wizard.willpower+9)//10)
            toughness.update((max(1,pivot-1),pivot))
    choices['toughness'] = tuple(sorted(toughness))
    # Melee-only parties have no BS/I/Shooting/Dexterity facts. Use the
    # explicit starting envelope rather than pretending their WS/Ag are those
    # characteristics. Where an admitted PC source supplies ranged facts,
    # centre each corresponding range around those actual values.
    for name in ('ballistic_skill','shooting','initiative','dexterity'):
        values=[getattr(member.pc.ranged,name) for member in party
            if member.pc.ranged is not None and getattr(member.pc.ranged,name) is not None]
        if values:
            floor,ceiling=(2,6) if name in ('shooting','dexterity') else (1,10)
            low=max(floor,min(ceiling,min(values)-1))
            high=max(low,min(ceiling,max(values)+1))
            choices[name]=tuple(range(low,high+1))
    return NpcSearchSpace(**choices)


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
        if any(p.pc.weapon in PC_RANGED_WEAPONS and p.pc.weapon.value not in
                ('pistol','repeater_pistol','repeater_handbow') for p in self.party):
            raise ValueError('dynamic slice requires melee or supported Close ranged PCs')
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
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
        return PcMeleeScenario(candidate_id, party, self.day_id,
            tuple(n.participant(a) for n, a in zip(composition, actors)), self.facts,
            tuple(p.actor_id for p in party), actors, tuple(p.actor_id for p in party), self.max_rounds,
            None, (), npc_extra_attack_actor_ids=(), npc_grudge_policies=(), npc_blood_rage_actor_ids=(),
            npc_flagellant_policies=(), npc_warped_form_policies=(),
            npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
                for npc,actor in zip(composition,actors) if npc.ranged is not None))


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


def _score(request, candidate):
    return (bool(candidate.summary.outcome_counts.unsupported_path),
        abs(candidate.win_rate-request.target_win_rate),
        abs(candidate.mean_started_rounds-request.target_rounds))


def validate_dynamic_encounter_result(result: DynamicEncounterResult) -> None:
    """Check the complete source, stage seeds, selection and accounting without trials."""
    if type(result) is not DynamicEncounterResult or type(result.source) is not DynamicEncounterRequest:
        raise TypeError('expected a typed dynamic result and source')
    request = replace(result.source)
    if type(result.explored) is not tuple or not 1 <= len(result.explored) <= request.max_candidates:
        raise ValueError('explored candidates exceed the source bounds')
    compositions = tuple(c.composition for c in result.explored)
    if len(set(compositions)) != len(compositions):
        raise ValueError('exploration contains duplicate compositions')

    def check(candidate, stage, index, trials):
        if type(candidate) is not GeneratedCandidate:
            raise TypeError('observations must be typed generated candidates')
        replace(candidate)
        if not request.minimum_npcs <= len(candidate.composition) <= request.maximum_npcs:
            raise ValueError('candidate count is outside the search space')
        for npc in candidate.composition:
            if not request.space.contains(npc):
                raise ValueError('candidate component is outside the search space')
        expected = PcMeleeSimulationRequest(request.scenario(candidate.composition, f'dynamic:{stage}:{index}'),
            _seed(request.master_seed, stage, index), trials)
        if candidate.summary.source_request != expected:
            raise ValueError('candidate source/seed/stage differs from generation source')

    for i, candidate in enumerate(result.explored):
        check(candidate, 'explore', i, request.exploration_trials)
    eligible = [c for c in sorted(result.explored, key=lambda c: _score(request, c))
        if not c.summary.outcome_counts.unsupported_path][:request.top_k]
    if type(result.validations) is not tuple or len(result.validations) != len(eligible):
        raise ValueError('validation must cover the selected exploration finalists')
    indices = {c.composition: i for i, c in enumerate(eligible)}
    if set(c.composition for c in result.validations) != set(indices):
        raise ValueError('validation compositions differ from exploration finalists')
    for candidate in result.validations:
        check(candidate, 'validate', indices[candidate.composition], request.finalist_trials)
    ranked = tuple(sorted(result.validations, key=lambda c: (_score(request, c), indices[c.composition])))
    if result.validations != ranked:
        raise ValueError('validation ranking is inconsistent')
    expected_total = len(result.explored)*request.exploration_trials + len(result.validations)*request.finalist_trials
    if type(result.total_trials) is not int or result.total_trials != expected_total or expected_total > request.max_total_trials:
        raise ValueError('trial accounting differs from executed observations/budget')
    limit = request.max_candidates*30
    if type(result.proposal_attempts) is not int or not len(result.explored) <= result.proposal_attempts <= limit:
        raise ValueError('proposal accounting is outside the budget')
    expected_limit = result.proposal_attempts == limit and len(result.explored) < request.max_candidates
    if type(result.proposal_limit_reached) is not bool or result.proposal_limit_reached != expected_limit:
        raise ValueError('proposal limit flag is inconsistent')


class DynamicEncounterCancelled(Exception):
    """Explicit interruption; no partial encounter report is returned."""


class DynamicProgressPhase(str, Enum):
    GENERATING = 'generating'
    SIMULATING = 'simulating'
    CANDIDATE_COMPLETE = 'candidate_complete'
    SELECTING = 'selecting'
    COMPLETE = 'complete'


@dataclass(frozen=True, slots=True)
class DynamicEncounterProgress:
    """Transient observations, not a partial result or a battle journal."""
    phase: DynamicProgressPhase
    stage: str | None
    candidate_number: int
    candidate_count: int
    npc_count: int
    completed_trials: int
    trial_count: int
    total_completed_trials: int
    trial_budget: int
    wins: int
    unsupported_trials: int

    def __post_init__(self):
        if type(self.phase) is not DynamicProgressPhase or self.stage not in (None, 'explore', 'validate'):
            raise ValueError('invalid progress phase/stage')
        for field in fields(self):
            if field.name in ('phase', 'stage'):
                continue
            if type(getattr(self, field.name)) is not int or getattr(self, field.name) < 0:
                raise ValueError('progress counters must be nonnegative integers')
        if (self.completed_trials > self.trial_count
                or self.wins + self.unsupported_trials > self.completed_trials
                or not self.completed_trials <= self.total_completed_trials <= self.trial_budget
                or self.candidate_number > self.candidate_count):
            raise ValueError('inconsistent progress counters')

    @property
    def win_rate(self):
        return self.wins / self.completed_trials if self.completed_trials else None


def search_dynamic_encounter(request: DynamicEncounterRequest, simulator=None, *,
        cancel_requested=None, on_progress=None) -> DynamicEncounterResult:
    """Explore random restarts and local mutations, then independently validate.

    Ranking: no unsupported observations, distance to win target, distance to
    duration target, proposal order. The result makes no global-optimum claim.
    """
    if type(request) is not DynamicEncounterRequest:
        raise TypeError('expected a DynamicEncounterRequest')
    replace(request)
    if cancel_requested is not None and not callable(cancel_requested):
        raise TypeError('cancel_requested must be callable')
    if on_progress is not None and not callable(on_progress):
        raise TypeError('on_progress must be callable')

    def checkpoint():
        if cancel_requested is not None and cancel_requested():
            raise DynamicEncounterCancelled('dynamic encounter search cancelled')

    completed_total = 0

    def emit(phase, stage=None, number=0, count=0, npc_count=0, completed=0, trials=0, wins=0, unsupported=0):
        checkpoint()
        if on_progress is not None:
            on_progress(DynamicEncounterProgress(phase, stage, number, count, npc_count,
                completed, trials, completed_total + completed, request.max_total_trials, wins, unsupported))
        checkpoint()

    checkpoint()
    default_simulator = simulator is None
    if default_simulator:
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        from towr.domain.pc_melee_result_models import PcMeleeOutcome
        class InterruptibleRandom(Random):
            def randint(self, start, end):
                checkpoint()
                return super().randint(start, end)

        rng_factory = Random if cancel_requested is None else InterruptibleRandom
    elif not callable(simulator):
        raise TypeError('simulator must be callable')
    rng = Random(_seed(request.master_seed, 'proposals', 0))
    explored, seen = [], set()

    def score(candidate):
        return _score(request, candidate)

    def evaluate(composition, stage, index, candidate_count):
        nonlocal completed_total
        checkpoint()
        scenario = request.scenario(composition, f'dynamic:{stage}:{index}')
        trials = request.exploration_trials if stage == 'explore' else request.finalist_trials
        source = PcMeleeSimulationRequest(scenario, _seed(request.master_seed, stage, index), trials)
        emit(DynamicProgressPhase.SIMULATING, stage, index+1, candidate_count, len(composition), trials=trials)
        completed, wins, unsupported = 0, 0, 0

        def observed(record):
            nonlocal completed, wins, unsupported
            completed += 1
            wins += int(record.outcome is PcMeleeOutcome.OBJECTIVE_ACHIEVED)
            unsupported += int(record.outcome is PcMeleeOutcome.UNSUPPORTED_PATH)
            emit(DynamicProgressPhase.SIMULATING, stage, index+1, candidate_count,
                len(composition), completed, trials, wins, unsupported)

        if default_simulator:
            summary = summarize_pc_melee_simulation(run_pc_melee_simulation(source,
                rng_factory=rng_factory, on_trial_complete=observed if on_progress is not None else None))
        else:
            summary = simulator(source)
        checkpoint()
        if type(summary) is not PcMeleeSimulationSummary:
            raise TypeError('simulator must return a typed aggregate')
        replace(summary)
        if summary.source_request != source:
            raise ValueError('simulator returned another candidate/seed/trial source')
        candidate = GeneratedCandidate(composition, summary)
        emit(DynamicProgressPhase.CANDIDATE_COMPLETE, stage, index+1, candidate_count,
            len(composition), trials, trials, summary.outcome_counts.objective_achieved,
            summary.outcome_counts.unsupported_path)
        completed_total += trials
        return candidate

    attempts, limit = 0, request.max_candidates*30
    announced_candidate = -1
    while len(explored) < request.max_candidates and attempts < limit:
        checkpoint()
        if announced_candidate != len(explored):
            announced_candidate = len(explored)
            emit(DynamicProgressPhase.GENERATING, 'explore', len(explored)+1, request.max_candidates)
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
        explored.append(evaluate(composition, 'explore', len(explored), request.max_candidates))
    emit(DynamicProgressPhase.SELECTING)
    eligible = [c for c in sorted(explored, key=score) if not c.summary.outcome_counts.unsupported_path]
    chosen = eligible[:request.top_k]
    validated = [evaluate(c.composition, 'validate', i, len(chosen)) for i, c in enumerate(chosen)]
    # Failed validation remains visible in explored/validation observations, never a selected recommendation.
    finalists = tuple(sorted(validated, key=score))
    total = len(explored)*request.exploration_trials + len(validated)*request.finalist_trials
    checkpoint()
    result = DynamicEncounterResult(request, tuple(explored), finalists, total, attempts,
        attempts == limit and len(explored) < request.max_candidates)
    emit(DynamicProgressPhase.COMPLETE)
    return result
