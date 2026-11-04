"""Aggregate-only PC encounter data for the balance boundary."""
from dataclasses import dataclass, replace

from towr.simulation.pc_melee_models import (
    PcMeleeOutcomeCounts, PcMeleeSimulationRequest, PcNearMissBurnCount,
    validate_near_miss_counts, PcGloriousSpendCount, validate_glorious_counts,
    PcHelpActionCount, validate_help_counts, PcAllyRecoverActionCount, validate_ally_recover_counts,
)


@dataclass(frozen=True, slots=True)
class PcMeleeDefeatCount:
    """Completed lethal lifecycles observed for one source PC, before any stop."""

    actor_id: str
    count: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC death count requires a nonempty actor ID')
        if type(self.count) is not int:
            raise TypeError('PC death count must be an integer')
        if self.count < 0:
            raise ValueError('PC death count must be nonnegative')


@dataclass(frozen=True, slots=True)
class PcMeleeSimulationSummary:
    source_request: PcMeleeSimulationRequest
    outcome_counts: PcMeleeOutcomeCounts
    total_action_count: int
    total_started_round_count: int
    total_completed_round_count: int
    any_pc_defeated_count: int
    pc_defeat_counts: tuple[PcMeleeDefeatCount, ...]
    near_miss_burn_trial_count: int
    near_miss_burn_counts: tuple[PcNearMissBurnCount, ...]
    glorious_spend_trial_count: int
    glorious_spend_counts: tuple[PcGloriousSpendCount, ...]
    help_action_trial_count: int
    help_action_counts: tuple[PcHelpActionCount, ...]
    ally_recover_action_trial_count: int
    ally_recover_action_counts: tuple[PcAllyRecoverActionCount, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, PcMeleeSimulationRequest):
            raise TypeError('summary requires its typed simulation request')
        replace(self.source_request)
        if not isinstance(self.outcome_counts, PcMeleeOutcomeCounts):
            raise TypeError('summary requires typed outcome counts')
        replace(self.outcome_counts)
        for name in ('total_action_count', 'total_started_round_count', 'total_completed_round_count'):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f'{name} must be an integer')
            if value < 0:
                raise ValueError(f'{name} must be nonnegative')
        counts = self.outcome_counts
        if sum(getattr(counts, name) for name in counts.__dataclass_fields__) != self.trials:
            raise ValueError('summary must account for every requested trial')
        limited = counts.round_limit
        budget = self.source_request.scenario.max_rounds
        started, completed = self.total_started_round_count, self.total_completed_round_count
        if not limited*budget + self.trials-limited <= started <= self.trials*budget:
            raise ValueError('started rounds contradict outcomes/budget')
        if not limited*budget <= completed <= started or started-completed > self.trials-limited:
            raise ValueError('completed rounds contradict started rounds')
        terminal = counts.objective_achieved+counts.party_defeated
        members = len(self.source_request.scenario.party)
        if not max(completed, terminal+limited*budget) <= self.total_action_count <= (members+len(self.source_request.scenario.enemies))*started:
            raise ValueError('actions contradict outcomes/rounds/actor count')
        if type(self.any_pc_defeated_count) is not int:
            raise TypeError('trials with a confirmed PC death must be an integer')
        any_death = self.any_pc_defeated_count
        if not counts.party_defeated <= any_death <= self.trials:
            raise ValueError('trials with PC deaths contradict party outcomes/denominator')
        if type(self.pc_defeat_counts) is not tuple:
            raise TypeError('per-PC death counts must be a canonical tuple')
        for item in self.pc_defeat_counts:
            if type(item) is not PcMeleeDefeatCount:
                raise TypeError('per-PC death counts require typed observations')
            replace(item)
            if not counts.party_defeated <= item.count <= any_death:
                raise ValueError('per-PC death counts contradict party/any-death counts')
        if tuple(item.actor_id for item in self.pc_defeat_counts) != tuple(
                member.actor_id for member in self.source_request.scenario.party):
            raise ValueError('per-PC death counts must cover the full source-ordered party')
        deaths = sum(item.count for item in self.pc_defeat_counts)
        if not any_death+counts.party_defeated*(members-1) <= deaths <= (
                any_death-counts.party_defeated)*(members-1)+counts.party_defeated*members:
            raise ValueError('any-death count contradicts individual observations')
        if deaths > self.total_action_count:
            raise ValueError('individual deaths contradict action/terminal bounds')
        if type(self.near_miss_burn_trial_count) is not int:
            raise TypeError('Near Miss trial count must be an integer')
        validate_near_miss_counts(self.near_miss_burn_counts, self.source_request.scenario,
            trials=self.trials, burn_trials=self.near_miss_burn_trial_count,
            actions=self.total_action_count)
        if type(self.glorious_spend_trial_count) is not int:
            raise TypeError('Glorious trial count must be an integer')
        validate_glorious_counts(self.glorious_spend_counts,self.source_request.scenario,
            trials=self.trials,spend_trials=self.glorious_spend_trial_count)
        if type(self.help_action_trial_count) is not int:
            raise TypeError('Help trial count must be an integer')
        validate_help_counts(self.help_action_counts,self.source_request.scenario,trials=self.trials,
            help_trials=self.help_action_trial_count,actions=self.total_action_count,
            started_rounds=self.total_started_round_count)
        if type(self.ally_recover_action_trial_count) is not int:
            raise TypeError('ally Recover trial count must be an integer')
        validate_ally_recover_counts(self.ally_recover_action_counts,self.source_request.scenario,
            trials=self.trials,recover_trials=self.ally_recover_action_trial_count,
            actions=self.total_action_count,started_rounds=self.total_started_round_count)
        if sum(item.count for item in (*self.help_action_counts,*self.ally_recover_action_counts))>self.total_action_count:
            raise ValueError('Help and ally Recover cannot consume the same action')

    @property
    def total_ally_recover_action_count(self) -> int:
        return sum(item.count for item in self.ally_recover_action_counts)

    @property
    def total_help_action_count(self) -> int:
        return sum(item.count for item in self.help_action_counts)

    @property
    def total_glorious_spend_count(self) -> int:
        return sum(item.count for item in self.glorious_spend_counts)

    @property
    def total_near_miss_burn_count(self) -> int:
        return sum(item.count for item in self.near_miss_burn_counts)

    @property
    def trials(self) -> int:
        return self.source_request.trials
