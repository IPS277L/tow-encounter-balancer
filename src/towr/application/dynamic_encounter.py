"""Budgeted adaptive generation of new NPC configurations, then Monte Carlo.

The simulator is injected. Neither NPC identity nor a supplied enemy reserve
defines the search space. Existing JSON families are unchanged.
"""
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from hashlib import sha256
from math import exp, isfinite, log, sqrt
from random import Random

from towr.application.ranged_simulation_models import SimulationExecutionMode,SimulationExecutionOptions
from towr.domain.generated_npc_models import (GeneratedNpc,GeneratedWeapon,GeneratedAbility,
    GeneratedTalent,generated_talent_requirements_met,GeneratedRangedFacts,GENERATED_RANGED_WEAPONS,
    generated_weapon_allows_shield,generated_weapon_grips,GENERATED_VARIABLE_GRIP_WEAPONS,
    GENERATED_TWO_HANDED_RANGED_WEAPONS,GENERATED_CLOSE_WEAPONS)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponId,ranged_weapon_combat_profile
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_mount_models import CombatMount
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeFacts, PcMeleeParticipant, PcMeleeScenario, PC_RANGED_WEAPONS
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


@dataclass(frozen=True, slots=True)
class NumericCompositionSample:
    """Generated numeric sources and their actual freedom/change counts."""
    composition: tuple[GeneratedNpc, ...]
    bias: float
    variable_fields: int
    changed_members: int


def _sample_numeric_value(values: tuple[int, ...], rng: Random, bias: float) -> int:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    if bias == 0:
        return rng.choice(ordered)
    weights = tuple(exp(log(9)*bias*i/(len(ordered)-1)) for i in range(len(ordered)))
    ticket = rng.random()*sum(weights)
    for value, weight in zip(ordered, weights):
        if ticket < weight:
            return value
        ticket -= weight
    return ordered[-1]


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
    weapon: tuple[GeneratedWeapon, ...] = GENERATED_CLOSE_WEAPONS
    light_armour: tuple[bool, ...] = (False, True)
    shield: tuple[bool, ...] = (False, True)
    abilities: tuple[tuple[GeneratedAbility, ...], ...] = ((),)
    allowed_talents: tuple[GeneratedTalent,...] = tuple(GeneratedTalent)
    ballistic_skill: tuple[int, ...] = (2, 3, 4)
    shooting: tuple[int, ...] = (3, 4, 5)
    initiative: tuple[int, ...] = (2, 3, 4)
    dexterity: tuple[int, ...] = (3, 4, 5)
    awareness: tuple[int, ...] = (3, 4, 5)
    weapon_grip: tuple[RangedWeaponHands, ...] = (
        RangedWeaponHands.ONE_HANDED, RangedWeaponHands.TWO_HANDED)
    mount: tuple[CombatMount | None, ...] = (None,)
    throwing: tuple[int, ...] = (3,4,5)
    brawn: tuple[int, ...] = (3,4,5)

    def __post_init__(self):
        if (type(self.weapon_grip) is not tuple or not self.weapon_grip
                or any(type(grip) is not RangedWeaponHands for grip in self.weapon_grip)
                or len(set(self.weapon_grip)) != len(self.weapon_grip)):
            raise ValueError('weapon_grip requires nonempty distinct typed hand choices')
        if (type(self.allowed_talents) is not tuple
                or any(type(t) is not GeneratedTalent for t in self.allowed_talents)
                or len(set(self.allowed_talents)) != len(self.allowed_talents)):
            raise ValueError('allowed_talents requires unique supported Talents; empty disables generation')
        for name in (*self._ordinary_names(), *self._ranged_names(), 'awareness','throwing'):
            choices = getattr(self,name)
            if type(choices) is not tuple or not choices or len(set(choices)) != len(choices):
                raise ValueError(f'{name} requires nonempty distinct tuple choices')
            for value in choices:
                if name in ('weapon_skill','strength','toughness','agility','ballistic_skill','initiative'):
                    if type(value) is not int or value < 1:
                        raise ValueError(f'{name} choices must be positive integers')
                elif name in ('melee','athletics','defence','shooting','dexterity','awareness','throwing','brawn'):
                    if type(value) is not int or not 2 <= value <= 6:
                        raise ValueError(f'{name} choices must be integers in 2..6')
                elif name == 'weapon' and type(value) is not GeneratedWeapon:
                    raise ValueError('weapon choices must be supported typed weapons')
                elif name in ('light_armour','shield') and type(value) is not bool:
                    raise ValueError('equipment choices must be exact booleans')
                elif name == 'mount' and value is not None and type(value) is not CombatMount:
                    raise ValueError('mount choices require supported typed components or None')
                elif name == 'abilities':
                    if (type(value) is not tuple or any(type(a) is not GeneratedAbility for a in value)
                            or len(set(value)) != len(value)):
                        raise ValueError('ability groups must be unique supported typed tuples')
        equipment_branches = tuple((weapon,grip) for weapon in self.weapon
            for grip in self._weapon_grips(weapon))
        if any(not generated_weapon_allows_shield(weapon,grip)
                for weapon,grip in equipment_branches) and False not in self.shield:
            raise ValueError('weapon choices need an admissible no-Shield loadout')
        if True in self.shield and not any(generated_weapon_allows_shield(weapon,grip)
                for weapon,grip in equipment_branches):
            raise ValueError('Shield choice has no admissible one-handed melee weapon')
        if GeneratedWeapon.WEIGHTED_NET in self.weapon and () not in self.abilities:
            raise ValueError('Net proposal needs an admitted empty Damage-secondary group')
        if all(weapon is GeneratedWeapon.WEIGHTED_NET for weapon in self.weapon) and any(self.abilities):
            raise ValueError('Damage-secondary choices have no admissible non-Net weapon')

    @staticmethod
    def _ranged_names(weapon=None):
        names = ('ballistic_skill','shooting','initiative','dexterity')
        return names + (('awareness',) if weapon in GENERATED_TWO_HANDED_RANGED_WEAPONS else ())

    @staticmethod
    def _ordinary_names():
        return ('weapon_skill','strength','toughness','agility','melee','athletics','defence',
            'weapon','light_armour','shield','abilities','mount','brawn')

    def _weapon_grips(self, weapon):
        # This conditional dimension is inactive for fixed melee/ranged items.
        return (self.weapon_grip if weapon in GENERATED_VARIABLE_GRIP_WEAPONS
            else generated_weapon_grips(weapon))

    def _build(self, facts, talents=(), ranged_values=None, *, weapon_grip=None,throwing=None,ballistic_skill=None):
        ranged=None
        if facts['weapon'] in GENERATED_RANGED_WEAPONS:
            names = self._ranged_names(facts['weapon'])
            values = {name:(ranged_values[name] if ranged_values is not None
                and name in ranged_values else getattr(self,name)[0]) for name in names}
            if ballistic_skill is not None:
                values['ballistic_skill'] = ballistic_skill
            blackpowder=ranged_weapon_combat_profile(
                RangedWeaponId(facts['weapon'].value)).requires_blackpowder_lore
            ranged=GeneratedRangedFacts(**values,initially_loaded=True,ammunition_supply_confirmed=True,
                has_blackpowder_lore=True if blackpowder else None,
                has_blackpowder_kit=True if blackpowder else None)
        throwing = (self.throwing[0] if throwing is None else throwing
            ) if facts['weapon'] is GeneratedWeapon.WEIGHTED_NET else None
        ballistic_skill = ((ballistic_skill if ballistic_skill is not None else
            ranged_values['ballistic_skill'] if ranged_values is not None else self.ballistic_skill[0])
            if facts['weapon'] is GeneratedWeapon.WEIGHTED_NET else None)
        return GeneratedNpc(**facts,talents=talents,ranged=ranged,weapon_grip=weapon_grip,
            throwing=throwing,ballistic_skill=ballistic_skill)

    def sample(self, rng: Random) -> GeneratedNpc:
        # Select a legal equipment branch before its conditional source facts.
        # No Shield is drawn then discarded, and melee sources draw no unused
        # ranged characteristics or skills.
        weapon=rng.choice(self.weapon)
        weapon_grip = rng.choice(self.weapon_grip) if weapon in GENERATED_VARIABLE_GRIP_WEAPONS else None
        facts={name:rng.choice(getattr(self,name)) for name in self._ordinary_names()
            if name not in ('weapon','shield','mount','abilities')}
        # A disabled singleton axis spends no additional RNG in pedestrian scenes.
        facts['mount'] = self.mount[0] if len(self.mount) == 1 else rng.choice(self.mount)
        facts['weapon']=weapon
        facts['abilities'] = rng.choice(((),) if weapon is GeneratedWeapon.WEIGHTED_NET else self.abilities)
        facts['shield']=rng.choice(tuple(value for value in self.shield
            if generated_weapon_allows_shield(weapon,weapon_grip) or value is False))
        ranged_values=({name:rng.choice(getattr(self,name)) for name in self._ranged_names(weapon)}
            if weapon in GENERATED_RANGED_WEAPONS else None)
        talents=tuple(t for t in self.allowed_talents if generated_talent_requirements_met(t,
            weapon_skill=facts['weapon_skill'],strength=facts['strength']) and rng.randrange(2))
        throwing = rng.choice(self.throwing) if weapon is GeneratedWeapon.WEIGHTED_NET else None
        ballistic = rng.choice(self.ballistic_skill) if weapon is GeneratedWeapon.WEIGHTED_NET else None
        return self._build(facts,talents,ranged_values,weapon_grip=weapon_grip,
            throwing=throwing,ballistic_skill=ballistic)

    def mutate(self, npc: GeneratedNpc, rng: Random) -> GeneratedNpc:
        if type(npc) is not GeneratedNpc or not self.contains(npc):
            raise ValueError('mutation requires an admitted member of this component space')
        replace(npc)
        facts={name:getattr(npc,name) for name in self._ordinary_names()}
        ranged_values=({name:getattr(npc.ranged,name) for name in self._ranged_names(npc.weapon)}
            if npc.ranged is not None else None)
        variable=[]
        for name in self._ordinary_names():
            if name == 'brawn' and npc.brawn is None:
                continue  # An explicitly absent optional capability is not invented by mutation.
            values=[]
            for value in getattr(self,name):
                if value == getattr(npc,name):
                    continue
                grips = self._weapon_grips(value) if name == 'weapon' else (npc.weapon_grip,)
                for grip in grips:
                    try:
                        candidate=self._build(facts | {name:value},npc.talents,ranged_values,
                            weapon_grip=grip,throwing=npc.throwing,ballistic_skill=npc.ballistic_skill)
                    except ValueError:
                        continue
                    values.append(candidate)
            if values:
                variable.append((name,tuple(values)))
        if npc.weapon in GENERATED_VARIABLE_GRIP_WEAPONS:
            grip_options = []
            for grip in self.weapon_grip:
                if grip is npc.weapon_grip:
                    continue
                try:
                    grip_options.append(replace(npc,weapon_grip=grip))
                except ValueError:
                    continue
            if grip_options:
                variable.append(('weapon_grip',tuple(grip_options)))
        if npc.ranged is not None:
            for name in self._ranged_names(npc.weapon):
                values=tuple(replace(npc,ranged=replace(npc.ranged,**{name:value}))
                    for value in getattr(self,name) if value != getattr(npc.ranged,name))
                if values:
                    variable.append((name,values))
        if npc.weapon is GeneratedWeapon.WEIGHTED_NET:
            for name in ('throwing','ballistic_skill'):
                options = tuple(replace(npc,**{name:value}) for value in getattr(self,name)
                    if value != getattr(npc,name))
                if options:
                    variable.append((name,options))
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
        return (all(getattr(npc,name) in getattr(self,name) or name == 'brawn' and npc.brawn is None
                for name in self._ordinary_names())
            and (npc.weapon is not GeneratedWeapon.WEIGHTED_NET or npc.throwing in self.throwing
                and npc.ballistic_skill in self.ballistic_skill)
            and (npc.weapon not in GENERATED_VARIABLE_GRIP_WEAPONS or npc.weapon_grip in self.weapon_grip)
            and (npc.ranged is None or all(getattr(npc.ranged,name) in getattr(self,name)
                for name in self._ranged_names(npc.weapon)))
            and (npc.ranged is None or npc.weapon in GENERATED_TWO_HANDED_RANGED_WEAPONS
                or npc.ranged.awareness is None)
            and set(npc.talents) <= set(self.allowed_talents))

    def resample_numeric(self, composition: tuple[GeneratedNpc, ...], rng: Random, *,
            bias: float = 0.) -> NumericCompositionSample:
        """Preserve gear/Talents while sampling admitted numeric values for a cohort."""
        if type(bias) not in (int, float) or not -1 <= bias <= 1 or not isfinite(bias):
            raise ValueError('numeric sampling bias must be finite in -1..1, excluding bool')
        if (type(composition) is not tuple or not composition
                or any(not self.contains(member) for member in composition)):
            raise ValueError('numeric sampling requires a nonempty admitted composition tuple')
        members = []
        variable_fields = 0
        ordinary = ('weapon_skill','strength','toughness','agility','melee','athletics','defence')
        for member in composition:
            current = member
            names = (ordinary + (('brawn',) if member.brawn is not None else ())
                + (('ballistic_skill','throwing') if member.weapon is GeneratedWeapon.WEIGHTED_NET else ())
                + (self._ranged_names(member.weapon) if member.ranged is not None else ()))
            for name in names:
                candidates = {}
                for value in getattr(self, name):
                    try:
                        candidate = (replace(current, ranged=replace(current.ranged, **{name:value}))
                            if current.ranged is not None and name in self._ranged_names(member.weapon)
                            else replace(current, **{name:value}))
                    except ValueError:
                        continue
                    candidates[value] = candidate
                if len(candidates) > 1:
                    variable_fields += 1
                selected = _sample_numeric_value(tuple(candidates), rng, float(bias))
                current = candidates[selected]
            members.append(current)
        result = tuple(members)
        return NumericCompositionSample(result, float(bias), variable_fields,
            sum(a != b for a, b in zip(composition, result)))


def automatic_npc_search_space(party: tuple[PcMeleeParticipant, ...], *,
        battlefield: PcBattlefieldSpec | None = None) -> NpcSearchSpace:
    """A bounded search envelope around the party, not a book NPC stat limit.

    The battle targets rank sampled compositions; they do not prescribe a
    monotonic stat multiplier. No authored abilities are granted implicitly.
    """
    if not party:
        raise ValueError('automatic NPC space needs a party')
    if battlefield is not None:
        if type(battlefield) is not PcBattlefieldSpec:
            raise TypeError('automatic NPC space requires an exact battlefield spec or None')
        replace(battlefield)
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
    for name in ('throwing','brawn'):
        values = [getattr(member.pc,name) for member in party if getattr(member.pc,name) is not None]
        if values:
            low,high = max(2,min(6,min(values)-1)),max(2,min(6,max(values)+1))
            choices[name] = tuple(range(low,high+1))
    # Melee-only parties have no BS/I/Shooting/Dexterity facts. Use the
    # explicit starting envelope rather than pretending their WS/Ag are those
    # characteristics. Where an admitted PC source supplies ranged facts,
    # centre each corresponding range around those actual values.
    for name in ('ballistic_skill','shooting','initiative','dexterity','awareness'):
        values=[getattr(member.pc.ranged,name) for member in party
            if member.pc.ranged is not None and getattr(member.pc.ranged,name) is not None]
        if name == 'ballistic_skill':
            values.extend(member.pc.ballistic_skill for member in party
                if member.pc.ballistic_skill is not None)
        if values:
            floor,ceiling=(2,6) if name in ('shooting','dexterity','awareness') else (1,10)
            low=max(floor,min(ceiling,min(values)-1))
            high=max(low,min(ceiling,max(values)+1))
            choices[name]=tuple(range(low,high+1))
    choices['weapon'] = tuple(GeneratedWeapon) if battlefield is not None else GENERATED_CLOSE_WEAPONS
    choices['mount'] = (None, CombatMount.HORSE) if battlefield is not None else (None,)
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
    battlefield: PcBattlefieldSpec | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.party) is not tuple or not self.party or any(type(p) is not PcMeleeParticipant for p in self.party):
            raise TypeError('party must be a nonempty tuple of typed PC participants')
        if len({p.actor_id for p in self.party}) != len(self.party):
            raise ValueError('party actor IDs must be unique')
        if type(self.facts) is not PcMeleeFacts or type(self.space) is not NpcSearchSpace:
            raise TypeError('generation requires typed facts and search space')
        replace(self.facts)
        replace(self.space)
        if self.battlefield is None:
            if any(mount is not None for mount in self.space.mount) or any(
                    member.mount is not None for member in self.party):
                raise ValueError('mounted dynamic encounters require an explicit battlefield')
            if not self.facts.all_opponents_close or self.facts.can_leave_zone:
                raise ValueError('stationary dynamic request requires the all-Close arena')
            if any(weapon in GENERATED_TWO_HANDED_RANGED_WEAPONS for weapon in self.space.weapon):
                raise ValueError('two-handed generated Shooting requires an explicit battlefield')
            if any(p.pc.weapon in PC_RANGED_WEAPONS and p.pc.weapon.value not in
                    ('pistol','repeater_pistol','repeater_handbow') for p in self.party):
                raise ValueError('stationary dynamic request requires supported Close ranged PCs')
        else:
            if type(self.battlefield) is not PcBattlefieldSpec:
                raise TypeError('dynamic battlefield must be an exact PcBattlefieldSpec or None')
            replace(self.battlefield)
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
        actual_facts = replace(self.facts, unmounted=not any(
            member.mount is not None for member in party)
            and not any(npc.mount is not None for npc in composition))
        return PcMeleeScenario(candidate_id, party, self.day_id,
            tuple(n.participant(a) for n, a in zip(composition, actors)), actual_facts,
            tuple(p.actor_id for p in party), actors, tuple(p.actor_id for p in party), self.max_rounds,
            None, (), npc_extra_attack_actor_ids=(), npc_grudge_policies=(), npc_blood_rage_actor_ids=(),
            npc_flagellant_policies=(), npc_warped_form_policies=(),
            npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
                for npc,actor in zip(composition,actors) if npc.ranged is not None),
            battlefield=self.battlefield)


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

    @property
    def target_match_found(self):
        return any(assess_dynamic_candidate(self.source,c).status is DynamicTargetStatus.WITHIN_TARGETS
            for c in self.finalists)


WIN_RATE_TOLERANCE = .1
STARTED_ROUNDS_TOLERANCE = 1.


class DynamicTargetStatus(str, Enum):
    WITHIN_TARGETS = 'within_targets'
    OUTSIDE_TARGETS = 'outside_targets'
    UNSUPPORTED = 'unsupported'


@dataclass(frozen=True, slots=True)
class DynamicTargetAssessment:
    """Point estimates under the current trial/tactics budget, not certification."""
    status: DynamicTargetStatus
    win_rate_in_range: bool
    started_rounds_in_range: bool
    win_rate_deviation: float
    started_rounds_deviation: float
    normalized_max_deviation: float
    normalized_total_deviation: float


def assess_dynamic_targets(target_win_rate, target_rounds, win_rate, mean_started_rounds,
        unsupported_path) -> DynamicTargetAssessment:
    values = (target_win_rate,target_rounds,win_rate,mean_started_rounds)
    if (any(type(v) not in (int,float) or not isfinite(v) for v in values)
            or not 0 <= target_win_rate <= 1 or not 0 <= win_rate <= 1
            or target_rounds < 1 or mean_started_rounds < 1
            or type(unsupported_path) is not int or unsupported_path < 0):
        raise ValueError('joint target assessment requires finite admitted aggregates')
    win_error = abs(win_rate-target_win_rate)
    rounds_error = abs(mean_started_rounds-target_rounds)
    # One numerical convention for both inclusion and ranking. Rounding only
    # removes floating arithmetic noise at 1e-12 of a tolerance unit.
    def normalized(error,tolerance):
        value = error/tolerance
        return 1. if abs(value-1) <= 1e-12 else round(value,12)
    win_distance = normalized(win_error,WIN_RATE_TOLERANCE)
    round_distance = normalized(rounds_error,STARTED_ROUNDS_TOLERANCE)
    win_match,round_match = win_distance <= 1,round_distance <= 1
    status = (DynamicTargetStatus.UNSUPPORTED if unsupported_path else
        DynamicTargetStatus.WITHIN_TARGETS if win_match and round_match else
        DynamicTargetStatus.OUTSIDE_TARGETS)
    return DynamicTargetAssessment(status,win_match,round_match,win_error,rounds_error,
        max(win_distance,round_distance),win_distance+round_distance)


def assess_dynamic_candidate(request, candidate) -> DynamicTargetAssessment:
    return assess_dynamic_targets(request.target_win_rate,request.target_rounds,
        candidate.win_rate,candidate.mean_started_rounds,candidate.summary.outcome_counts.unsupported_path)


def _seed(master: int, stage: str, index: int) -> int:
    return int.from_bytes(sha256(f'towr:dynamic:v1:{master}:{stage}:{index}'.encode()).digest()[:8], 'big')


def _score(request, candidate):
    assessment = assess_dynamic_candidate(request,candidate)
    return (assessment.status is DynamicTargetStatus.UNSUPPORTED,
        assessment.normalized_max_deviation,assessment.normalized_total_deviation)


def _directed_count_parent(request, explored):
    """Advance an observed win-rate plateau without pruning any count range.

    This only chooses a proposal parent. Final ranking uses the joint-target
    score; independent trials must check whether the proposed resize helped.
    """
    eligible = [c for c in explored if not c.summary.outcome_counts.unsupported_path]
    if not eligible:
        return None
    best = min(eligible, key=lambda c: _score(request, c))
    if best.win_rate == request.target_win_rate:
        return None
    plateau = [c for c in eligible if c.win_rate == best.win_rate]
    if best.win_rate > request.target_win_rate:
        parent = max(plateau, key=lambda c: len(c.composition))
        return parent if len(parent.composition) < request.maximum_npcs else None
    parent = min(plateau, key=lambda c: len(c.composition))
    return parent if len(parent.composition) > request.minimum_npcs else None


class _ProposalOperation(str, Enum):
    COUNT = 'count'
    COMPONENT = 'component'
    RESTART = 'restart'


@dataclass(frozen=True, slots=True)
class _Proposal:
    requested: _ProposalOperation
    applied: _ProposalOperation
    composition: tuple[GeneratedNpc, ...]


def _select_proposal_operation(request: DynamicEncounterRequest, explored_count: int,
        attempt_number: int, rng: Random) -> _ProposalOperation:
    if explored_count and rng.random() < .7:
        return (_ProposalOperation.COUNT
            if request.minimum_npcs != request.maximum_npcs and explored_count % 2
            else _ProposalOperation.COMPONENT)
    return _ProposalOperation.RESTART


def _propose(request: DynamicEncounterRequest, explored: list[GeneratedCandidate],
        rng: Random, operation: _ProposalOperation) -> _Proposal:
    if type(operation) is not _ProposalOperation:
        raise TypeError('proposal operation must be typed')
    if operation is _ProposalOperation.RESTART:
        composition = tuple(request.space.sample(rng)
            for _ in range(rng.randint(request.minimum_npcs, request.maximum_npcs)))
        return _Proposal(operation, operation, composition)
    if not explored:
        raise ValueError('adaptive proposal requires observations')
    elite = sorted(explored, key=lambda candidate: _score(request, candidate))[:max(1, request.top_k)]
    composition = list(rng.choice(elite).composition)
    parent = (_directed_count_parent(request, explored)
        if operation is _ProposalOperation.COUNT and request.minimum_npcs != request.maximum_npcs else None)
    if parent is not None:
        composition = list(parent.composition)
        if parent.win_rate > request.target_win_rate:
            composition.append(request.space.sample(rng))
        else:
            composition.pop(rng.randrange(len(composition)))
        applied = _ProposalOperation.COUNT
    else:
        index = rng.randrange(len(composition))
        composition[index] = request.space.mutate(composition[index], rng)
        applied = _ProposalOperation.COMPONENT
    return _Proposal(operation, applied, tuple(composition))


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
        cancel_requested=None,on_progress=None,execution: SimulationExecutionOptions | None=None) -> DynamicEncounterResult:
    """Preserve ordered adaptive search while a process pool runs its trials."""
    if execution is not None:
        if not isinstance(execution,SimulationExecutionOptions):
            raise TypeError('execution requires typed simulation options')
        replace(execution)
        if simulator is not None:
            raise ValueError('custom simulator and execution options cannot be combined')
        if execution.mode is SimulationExecutionMode.PROCESS and execution.batch_size!=1:
            raise ValueError('dynamic process execution requires one-trial batches')
    if execution is not None and execution.mode is SimulationExecutionMode.PROCESS:
        from towr.simulation.pc_melee_process import PcMeleeProcessSession,PcMeleeSimulationCancelled
        try:
            with PcMeleeProcessSession(workers=execution.workers,batch_size=execution.batch_size,
                    cancel_requested=cancel_requested) as session:
                return _search_dynamic_encounter(request,cancel_requested=cancel_requested,
                    on_progress=on_progress,process_session=session)
        except PcMeleeSimulationCancelled as error:
            raise DynamicEncounterCancelled('dynamic encounter search cancelled') from error
    return _search_dynamic_encounter(request,simulator,cancel_requested=cancel_requested,
        on_progress=on_progress)


def _search_dynamic_encounter(request: DynamicEncounterRequest, simulator=None, *,
        cancel_requested=None,on_progress=None,process_session=None) -> DynamicEncounterResult:
    """Explore random restarts and local mutations, then independently validate.

    Ranking: no unsupported observations, worst normalized joint deviation,
    total normalized deviation, proposal order. Point matches are not certified.
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
        if process_session is None:
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
            if process_session is None:
                result=run_pc_melee_simulation(source,rng_factory=rng_factory,
                    on_trial_complete=observed if on_progress is not None else None)
            else:
                result=process_session.run(source,
                    on_trial_complete=observed if on_progress is not None else None)
            summary = summarize_pc_melee_simulation(result)
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
        operation = _select_proposal_operation(request, len(explored), attempts, rng)
        composition = _propose(request, explored, rng, operation).composition
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
