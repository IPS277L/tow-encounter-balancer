"""Aggregate-only PC encounter data for the balance boundary."""
from towr.simulation.pc_npc_ally_statistics import PcNpcAllyCount,validate_npc_ally_counts
from towr.simulation.pc_ranged_statistics import PcRangedCount,validate_pc_ranged_counts

from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount,validate_npc_ranged_counts
from towr.simulation.pc_extra_attack_statistics import (
    PcExtraAttackCount,pc_extra_attack_actors,validate_pc_extra_attack_counts,
)
from towr.simulation.pc_rapid_reload_statistics import (
    PcRapidReloadCount, validate_rapid_reload_counts, validate_npc_aim_counts,
)
from towr.simulation.pc_immediate_attack_statistics import (
    PcImmediateAttackCount, validate_immediate_attack_counts,
)
from towr.simulation.pc_companion_statistics import PcCompanionCount, validate_companion_counts
from towr.simulation.pc_musician_statistics import PcMusicianCount, validate_musician_counts
from towr.simulation.pc_oath_statistics import PcOathCount, validate_oath_counts, validate_oath_fate_budget

from dataclasses import dataclass, field, replace

from towr.simulation.pc_melee_models import (
    PcMeleeOutcomeCounts, PcMeleeSimulationRequest, PcNearMissBurnCount,
    validate_near_miss_counts, PcGloriousSpendCount, validate_glorious_counts,
    PcHelpActionCount, validate_help_counts, PcAllyRecoverActionCount, validate_ally_recover_counts,
    validate_automatic_action_budget,validate_npc_action_budget, PcPotionUseCount, validate_potion_use_counts,
    PcMagicCount, validate_magic_counts,
    PcNpcExitCount, validate_npc_exit_counts, PcNpcHelpActionCount, validate_npc_help_counts,
    PcNpcExtraAttackCount, validate_npc_extra_attack_counts,
    PcNpcRecoverActionCount, validate_npc_recover_counts,
    PcNpcWarpedFormCount, validate_npc_warped_form_counts, warped_form_target_budget,
    PcAimCount, PcAimCounts, validate_aim_counts,
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
    npc_exit_trial_count: int
    npc_exit_counts: tuple[PcNpcExitCount, ...]
    objective_with_npc_exit_count: int
    npc_help_action_trial_count: int
    npc_help_action_counts: tuple[PcNpcHelpActionCount, ...]
    npc_extra_attack_trial_count: int
    npc_extra_attack_counts: tuple[PcNpcExtraAttackCount, ...]
    npc_recover_action_trial_count: int
    npc_recover_action_counts: tuple[PcNpcRecoverActionCount, ...]
    npc_warped_form_trial_count: int
    npc_warped_form_counts: tuple[PcNpcWarpedFormCount, ...]
    aim: PcAimCounts | None = field(default=None, kw_only=True)
    potion_use_counts: tuple[PcPotionUseCount, ...] | None = field(default=None, kw_only=True)
    magic_counts: tuple[PcMagicCount, ...] | None = field(default=None, kw_only=True)
    npc_ranged_counts: tuple[PcNpcRangedCount, ...] | None = field(default=None,kw_only=True)
    pc_ranged_counts: tuple[PcRangedCount,...] | None = field(default=None,kw_only=True)
    pc_extra_attack_counts: tuple[PcExtraAttackCount,...] | None = field(default=None,kw_only=True)
    pc_extra_attack_trial_count: int | None = field(default=None,kw_only=True)
    rapid_reload_counts: tuple[PcRapidReloadCount,...] | None = field(default=None,kw_only=True)
    npc_aim_counts: tuple[PcAimCount,...] | None = field(default=None,kw_only=True)
    immediate_attack_counts: tuple[PcImmediateAttackCount,...] | None = field(default=None,kw_only=True)
    companion_counts: tuple[PcCompanionCount,...] | None = field(default=None,kw_only=True)
    music_counts: tuple[PcMusicianCount,...] | None = field(default=None,kw_only=True)
    oath_counts: tuple[PcOathCount,...] | None = field(default=None,kw_only=True)
    npc_ally_counts: tuple[PcNpcAllyCount,...] | None = field(default=None,kw_only=True)

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
        if type(self.npc_extra_attack_trial_count) is not int:
            raise TypeError('NPC extra Attack trial count must be an integer')
        validate_npc_extra_attack_counts(self.npc_extra_attack_counts,self.source_request.scenario,
            trials=self.trials,extra_trials=self.npc_extra_attack_trial_count,
            actions=self.total_action_count,started_rounds=started)
        validate_aim_counts(self.aim,self.source_request.scenario,trials=self.trials,
            actions=self.total_action_count,started_rounds=started,glorious_counts=self.glorious_spend_counts)
        seconds = self.aim.total_second_action_spend_count if self.aim is not None else 0
        if pc_extra_attack_actors(self.source_request.scenario) and type(self.pc_extra_attack_trial_count) is not int:
            raise TypeError('PC extra Attack trial count must retain its exact observed integer')
        validate_pc_extra_attack_counts(self.pc_extra_attack_counts,self.source_request.scenario,
            trials=self.trials,extra_trials=self.pc_extra_attack_trial_count,
            actions=self.total_action_count,started_rounds=started)
        pc_extras=sum(row.count for row in self.pc_extra_attack_counts or ())
        validate_npc_aim_counts(self.npc_aim_counts,self.source_request.scenario,trials=self.trials,
            actions=self.total_action_count,started_rounds=started)
        validate_rapid_reload_counts(self.rapid_reload_counts,self.source_request.scenario,trials=self.trials,
            actions=self.total_action_count,started_rounds=started,
            pc_ranged_counts=self.pc_ranged_counts,npc_ranged_counts=self.npc_ranged_counts,
            aim_counts=self.aim,npc_aim_counts=self.npc_aim_counts,
            pc_extra_counts=self.pc_extra_attack_counts,npc_extra_counts=self.npc_extra_attack_counts)
        rapid=sum(row.count for row in self.rapid_reload_counts or ())
        validate_immediate_attack_counts(self.immediate_attack_counts,self.source_request.scenario,
            actions=self.total_action_count,started_rounds=started)
        validate_companion_counts(self.companion_counts,self.source_request.scenario,trials=self.trials,started_rounds=started)
        validate_musician_counts(self.music_counts,self.source_request.scenario,trials=self.trials,
            started_rounds=started,actions=self.total_action_count)
        validate_oath_counts(self.oath_counts,self.source_request.scenario,trials=self.trials,
            started_rounds=started,actions=self.total_action_count)
        companion_actions=sum(row.recover_actions+row.movement_actions for row in self.companion_counts or ())
        validate_npc_ally_counts(self.npc_ally_counts,self.source_request.scenario,trials=self.trials,
            started_rounds=started,actions=self.total_action_count)
        allied_actions=sum(row.actions for row in self.npc_ally_counts or ())
        terminal = counts.objective_achieved+counts.party_defeated
        members = len(self.source_request.scenario.party)
        if not max(completed, terminal+limited*budget) <= self.total_action_count <= (
                members+len(self.source_request.scenario.enemies))*started+self.total_npc_extra_attack_count+allied_actions+pc_extras+seconds+rapid+companion_actions:
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
        validate_npc_warped_form_counts(self.npc_warped_form_counts,self.source_request.scenario,
            trials=self.trials,activation_trials=self.npc_warped_form_trial_count,
            actions=self.total_action_count,started_rounds=started)
        pc_injury_budget=self.total_action_count+warped_form_target_budget(
            self.source_request.scenario,self.npc_warped_form_counts,pc_targets=True)
        npc_injury_budget=self.total_action_count+warped_form_target_budget(
            self.source_request.scenario,self.npc_warped_form_counts,pc_targets=False)
        if deaths > pc_injury_budget:
            raise ValueError('individual deaths contradict action/terminal bounds')
        if type(self.near_miss_burn_trial_count) is not int:
            raise TypeError('Near Miss trial count must be an integer')
        validate_near_miss_counts(self.near_miss_burn_counts, self.source_request.scenario,
            trials=self.trials, burn_trials=self.near_miss_burn_trial_count,
            actions=pc_injury_budget)
        if type(self.glorious_spend_trial_count) is not int:
            raise TypeError('Glorious trial count must be an integer')
        validate_glorious_counts(self.glorious_spend_counts,self.source_request.scenario,
            trials=self.trials,spend_trials=self.glorious_spend_trial_count)
        validate_oath_fate_budget(self.oath_counts,self.source_request.scenario,self.glorious_spend_counts,
            self.aim,trials=self.trials)
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
        validate_potion_use_counts(self.potion_use_counts,self.source_request.scenario,trials=self.trials,
            actions=self.total_action_count,started_rounds=self.total_started_round_count)
        validate_pc_ranged_counts(self.pc_ranged_counts,self.source_request.scenario,
            actions=self.total_action_count,started_rounds=self.total_started_round_count,help_counts=self.help_action_counts,
            rapid_reload_counts=self.rapid_reload_counts)
        validate_npc_ranged_counts(self.npc_ranged_counts,self.source_request.scenario,
            actions=self.total_action_count,started_rounds=self.total_started_round_count,
            rapid_reload_counts=self.rapid_reload_counts)
        validate_magic_counts(self.magic_counts,self.source_request.scenario,trials=self.trials,
            actions=self.total_action_count,started_rounds=self.total_started_round_count,
            unsupported_trials=counts.unsupported_path)
        validate_automatic_action_budget(self.help_action_counts,self.ally_recover_action_counts,
            self.source_request.scenario,started_rounds=self.total_started_round_count,
            potion_counts=self.potion_use_counts,magic_counts=self.magic_counts,
            pc_extra_counts=self.pc_extra_attack_counts,aim_counts=self.aim,rapid_reload_counts=self.rapid_reload_counts,
            pc_ranged_counts=self.pc_ranged_counts,music_counts=self.music_counts,oath_counts=self.oath_counts)
        if type(self.npc_help_action_trial_count) is not int:
            raise TypeError('NPC Help trial count must be an integer')
        validate_npc_help_counts(self.npc_help_action_counts,self.source_request.scenario,trials=self.trials,
            help_trials=self.npc_help_action_trial_count,actions=self.total_action_count,
            started_rounds=self.total_started_round_count)
        if type(self.npc_recover_action_trial_count) is not int:
            raise TypeError('NPC Recover trial count must be an integer')
        validate_npc_recover_counts(self.npc_recover_action_counts,self.source_request.scenario,
            trials=self.trials,recover_trials=self.npc_recover_action_trial_count,
            actions=self.total_action_count,started_rounds=self.total_started_round_count,
            warped_form_counts=self.npc_warped_form_counts)
        validate_npc_action_budget(self.npc_extra_attack_counts,self.npc_help_action_counts,
            self.npc_recover_action_counts,started_rounds=self.total_started_round_count,
            ranged_counts=self.npc_ranged_counts,rapid_reload_counts=self.rapid_reload_counts,npc_aim_counts=self.npc_aim_counts,
            music_counts=self.music_counts,oath_counts=self.oath_counts)
        if sum(item.count for item in (*self.help_action_counts,*self.ally_recover_action_counts,
                *self.npc_help_action_counts,*self.npc_recover_action_counts,*(self.potion_use_counts or ())))+2*(self.total_npc_extra_attack_count+pc_extras)+(self.aim.total_action_count if self.aim is not None else 0)+sum(row.count for row in self.npc_aim_counts or ())+self.total_casting_action_count+sum(row.shots+row.reload_actions for row in self.npc_ranged_counts or ())+sum(row.shots+row.reload_actions for row in self.pc_ranged_counts or ())+sum(row.actions+row.pickups for row in self.music_counts or ())+sum(row.prayers for row in self.oath_counts or ())>self.total_action_count:
            raise ValueError('Help, ally Recover and primary/extra Attacks cannot consume the same action')
        validate_npc_exit_counts(self.npc_exit_counts,self.source_request.scenario,
            trials=self.trials,exit_trials=self.npc_exit_trial_count)
        if self.total_npc_exit_count>npc_injury_budget:
            raise ValueError('NPC exits exceed actual source injury opportunities')
        if type(self.objective_with_npc_exit_count) is not int:
            raise TypeError('objective with NPC exit count must be an integer')
        if not max(0,counts.objective_achieved+self.npc_exit_trial_count-self.trials)<=self.objective_with_npc_exit_count<=min(
                counts.objective_achieved,self.npc_exit_trial_count):
            raise ValueError('joint objective/exit count contradicts the marginal trial counts')

    @property
    def total_casting_action_count(self) -> int:
        return sum(row.casting_actions for row in self.magic_counts or ())

    @property
    def total_immediate_attack_count(self) -> int:
        return sum(row.count for row in self.immediate_attack_counts or ())

    @property
    def total_spell_cast_count(self) -> int:
        return sum(row.spell_casts for row in self.magic_counts or ())

    @property
    def total_miscast_count(self) -> int:
        return sum(row.miscasts for row in self.magic_counts or ())

    @property
    def total_unsupported_miscast_count(self) -> int:
        return sum(row.unsupported_miscasts for row in self.magic_counts or ())

    @property
    def total_potion_use_count(self) -> int:
        return sum(item.count for item in self.potion_use_counts or ())

    @property
    def total_npc_exit_count(self) -> int:
        return sum(item.count for item in self.npc_exit_counts)


    @property
    def total_npc_help_action_count(self) -> int:
        return sum(item.count for item in self.npc_help_action_counts)


    @property
    def total_npc_recover_action_count(self) -> int:
        return sum(item.count for item in self.npc_recover_action_counts)

    @property
    def total_npc_warped_form_count(self) -> int:
        return sum(item.count for item in self.npc_warped_form_counts)

    @property
    def total_npc_extra_attack_count(self) -> int:
        return sum(item.count for item in self.npc_extra_attack_counts)

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
