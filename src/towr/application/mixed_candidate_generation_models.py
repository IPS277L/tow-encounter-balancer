from dataclasses import dataclass
from math import prod

from towr.balance.mixed_staged_evaluation_models import (
    MixedBalanceStage, MixedStagedEvaluationRequest, _planned_trials, _validate_stages,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_mixed_scenario_models import NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest


@dataclass(frozen=True, slots=True)
class MixedCompositionGroup:
    group_id: str
    actor_ids: tuple[str, ...]
    minimum_count: int
    maximum_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.group_id, str) or not self.group_id.strip():
            raise ValueError("composition group requires a non-empty ID")
        if not isinstance(self.actor_ids, (tuple, list)):
            raise TypeError("composition actor IDs require an ordered sequence")
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
class MixedCandidateGenerationRequest:
    """Arithmetic preflight for an explicit reserve, without materialization.

    Facts, pair ranges and fixed template policies apply to the entire family.
    Admission of each subset remains the responsibility of construction.
    """

    template_scenario: NpcMixedScenario
    groups: tuple[MixedCompositionGroup, ...]
    facts: NpcMixedScenarioFacts
    pair_ranges: tuple[NpcMixedPairRange, ...]
    candidate_id_prefix: str
    max_candidates: int
    master_seed: int
    stages: tuple[MixedBalanceStage, ...]
    max_total_trials: int
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.template_scenario, NpcMixedScenario):
            raise TypeError("generation requires an admitted mixed template scenario")
        if not isinstance(self.facts, NpcMixedScenarioFacts):
            raise TypeError("generation requires explicit mixed facts for every composition")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("generation requires a typed objective window")
        if not isinstance(self.candidate_id_prefix, str) or not self.candidate_id_prefix.strip():
            raise ValueError("generation requires a non-empty candidate ID prefix")
        for name, value in (("max_candidates", self.max_candidates), ("max_total_trials", self.max_total_trials)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("groups", "pair_ranges", "stages"):
            if not isinstance(getattr(self, name), (tuple, list)):
                raise TypeError(f"generation {name} requires an ordered sequence")
        groups, pairs, stages = tuple(self.groups), tuple(self.pair_ranges), tuple(self.stages)
        if not groups:
            raise ValueError("generation requires at least one composition group")
        if not all(isinstance(group, MixedCompositionGroup) for group in groups):
            raise TypeError("generation requires typed mixed composition groups")
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
        if not all(isinstance(pair, NpcMixedPairRange) for pair in pairs):
            raise TypeError("generation requires typed mixed family pairs")
        if pairs != template.pair_ranges:
            raise ValueError("family pairs must retain the exact ordered template pair ranges")
        # Scenario admission already checks each policy's escape path. The same
        # graph, placements, policies and distances apply to every composition.
        _validate_stages(stages)
        NpcMixedSimulationRequest(template, self.master_seed, stages[0].trials_per_candidate)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "pair_ranges", pairs)
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
class MixedCandidateGenerationResult:
    source_request: MixedCandidateGenerationRequest
    evaluation_request: MixedStagedEvaluationRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MixedCandidateGenerationRequest):
            raise TypeError("generation result requires its typed mixed source")
        if not isinstance(self.evaluation_request, MixedStagedEvaluationRequest):
            raise TypeError("generation result requires a typed mixed staged evaluation request")
        source, evaluation = self.source_request, self.evaluation_request
        if (evaluation.master_seed != source.master_seed or evaluation.stages != source.stages
                or evaluation.max_total_trials != source.max_total_trials or evaluation.window != source.window
                or len(evaluation.candidates) != source.candidate_count):
            raise ValueError("generated evaluation has foreign parameters or an incomplete candidate list")
        # Local import avoids a models/construction cycle. Validate one expected
        # projection at a time, without retaining a second copy of the family.
        from towr.application.mixed_candidate_generation import _count_vectors, _project_candidate

        for counts, candidate in zip(_count_vectors(source), evaluation.candidates):
            if candidate != _project_candidate(source, counts):
                raise ValueError("generated candidate differs from its exact source projection")
