from dataclasses import dataclass
from math import prod

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.ranged_staged_evaluation_models import (
    RangedBalanceStage, RangedStagedEvaluationRequest, _planned_trials, _validate_stages,
)
from towr.domain.npc_ranged_scenario_models import NpcRangedScenario, NpcRangedScenarioFacts
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest


@dataclass(frozen=True, slots=True)
class RangedCompositionGroup:
    group_id: str
    actor_ids: tuple[str, ...]
    minimum_count: int
    maximum_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.group_id, str) or not self.group_id.strip():
            raise ValueError("composition group requires a non-empty ID")
        actors = tuple(self.actor_ids)
        if not actors or not all(isinstance(actor, str) and actor.strip() for actor in actors):
            raise ValueError("composition group requires non-empty actor IDs")
        if len(set(actors)) != len(actors):
            raise ValueError("composition group actor IDs must be unique")
        if (type(self.minimum_count) is not int or type(self.maximum_count) is not int
                or not 0 <= self.minimum_count <= self.maximum_count <= len(actors)):
            raise ValueError("composition counts must be integers within the supplied reserve")
        object.__setattr__(self, "actor_ids", actors)


@dataclass(frozen=True, slots=True)
class RangedCandidateGenerationRequest:
    template_scenario: NpcRangedScenario
    groups: tuple[RangedCompositionGroup, ...]
    facts: NpcRangedScenarioFacts
    candidate_id_prefix: str
    max_candidates: int
    master_seed: int
    stages: tuple[RangedBalanceStage, ...]
    max_total_trials: int
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.template_scenario, NpcRangedScenario):
            raise TypeError("generation requires an admitted template scenario")
        if not isinstance(self.facts, NpcRangedScenarioFacts):
            raise TypeError("generation requires explicit facts for every composition")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("generation requires a typed objective window")
        if not isinstance(self.candidate_id_prefix, str) or not self.candidate_id_prefix.strip():
            raise ValueError("generation requires a non-empty candidate ID prefix")
        for name, value in (("max_candidates", self.max_candidates), ("max_total_trials", self.max_total_trials)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        groups, stages = tuple(self.groups), tuple(self.stages)
        if not groups:
            raise ValueError("generation requires at least one composition group")
        if not all(isinstance(group, RangedCompositionGroup) for group in groups):
            raise TypeError("generation requires typed composition groups")
        if len({group.group_id for group in groups}) != len(groups):
            raise ValueError("composition group IDs must be unique")
        actors = tuple(actor for group in groups for actor in group.actor_ids)
        template = self.template_scenario
        participants = {p.state.actor_id: p for p in template.initial.current.state.roster.participants}
        enemies = {actor for actor, p in participants.items() if p.state.side is not template.perspective_side}
        if len(set(actors)) != len(actors) or set(actors) != enemies:
            raise ValueError("composition groups must partition exactly the opposing reserve")
        for group in groups:
            definition = participants[group.actor_ids[0]].definition
            if any(participants[actor].definition != definition for actor in group.actor_ids):
                raise ValueError("each composition group must share one exact NPC definition")
        _validate_stages(stages)
        # Reuse seed admission without fabricating candidates or materializing a family.
        NpcRangedSimulationRequest(template, self.master_seed, stages[0].trials_per_candidate)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "stages", stages)
        if not 1 <= self.candidate_count <= self.max_candidates:
            raise ValueError("composition count is empty or exceeds max_candidates")
        if self.planned_trials > self.max_total_trials:
            raise ValueError("generated evaluation exceeds max_total_trials")

    @property
    def candidate_count(self) -> int:
        count = prod(group.maximum_count - group.minimum_count + 1 for group in self.groups)
        return count - int(all(group.minimum_count == 0 for group in self.groups))

    @property
    def planned_trials(self) -> int:
        return _planned_trials(self.candidate_count, self.stages)


@dataclass(frozen=True, slots=True)
class RangedCandidateGenerationResult:
    source_request: RangedCandidateGenerationRequest
    evaluation_request: RangedStagedEvaluationRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RangedCandidateGenerationRequest):
            raise TypeError("generation result requires its typed source")
        if not isinstance(self.evaluation_request, RangedStagedEvaluationRequest):
            raise TypeError("generation result requires a typed staged evaluation request")
        source, evaluation = self.source_request, self.evaluation_request
        if (evaluation.master_seed != source.master_seed or evaluation.stages != source.stages
                or evaluation.max_total_trials != source.max_total_trials or evaluation.window != source.window
                or len(evaluation.candidates) != source.candidate_count):
            raise ValueError("generated evaluation has foreign parameters or an incomplete candidate list")
        # Local import keeps pure source models usable without an import cycle.
        from towr.application.ranged_candidate_generation import _count_vectors, _project_candidate

        for counts, candidate in zip(_count_vectors(source), evaluation.candidates):
            if candidate != _project_candidate(source, counts):
                raise ValueError("generated candidate differs from its exact source projection")
