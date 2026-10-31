"""Magic reserve admission and source-bound inputs (ADR-0042/0047).

Request admission is arithmetic; result validation checks each full projection.
Neither model runs a battle or infers tactical facts.
"""
from dataclasses import dataclass
from math import prod

from towr.balance.magic_staged_evaluation_models import (
    MagicBalanceStage, MagicStagedEvaluationRequest, _planned_trials, _validate_stages,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import (
    NpcMagicMiscastContinuationPolicy, NpcMagicScenario, NpcMagicScenarioFacts,
)
from towr.domain.npc_magic_scene_models import NpcMagicSceneFrame
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("magic composition IDs must be strings")
    if not value.strip():
        raise ValueError("magic composition IDs must not be blank")


@dataclass(frozen=True, slots=True)
class MagicCompositionGroup:
    group_id: str
    actor_ids: tuple[str, ...]
    minimum_count: int
    maximum_count: int

    def __post_init__(self) -> None:
        _identifier(self.group_id)
        if not isinstance(self.actor_ids, (tuple, list)):
            raise TypeError("magic composition actor IDs require an ordered tuple or list")
        actors = tuple(self.actor_ids)
        if not actors:
            raise ValueError("magic composition group requires actor IDs")
        for actor in actors:
            _identifier(actor)
        if len(set(actors)) != len(actors):
            raise ValueError("magic composition actor IDs must be unique")
        if type(self.minimum_count) is not int or type(self.maximum_count) is not int:
            raise TypeError("magic composition counts must be integers")
        if not 0 <= self.minimum_count <= self.maximum_count <= len(actors):
            raise ValueError("magic composition counts must fit the supplied reserve")
        object.__setattr__(self, "actor_ids", actors)


@dataclass(frozen=True, slots=True)
class MagicCandidateGenerationRequest:
    """Admit a whole reserve and budget without validating individual subsets.

    Separate facts/frames and unchanged template policies apply to every
    projected composition/state. Construction must later admit each subset.
    The Wizard remains fixed even when opposite the perspective side.
    Miscast opt-in needs a separate, equal whole-family assertion; omitted
    reserve actors are absent, not external creatures within Short Range.
    """

    template_scenario: NpcMagicScenario
    groups: tuple[MagicCompositionGroup, ...]
    facts: NpcMagicScenarioFacts
    scene_frames: tuple[NpcMagicSceneFrame, ...]
    candidate_id_prefix: str
    max_candidates: int
    master_seed: int
    stages: tuple[MagicBalanceStage, ...]
    max_total_trials: int
    window: ObjectiveRateWindow
    miscast_continuation: NpcMagicMiscastContinuationPolicy | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.template_scenario, NpcMagicScenario):
            raise TypeError("generation requires an admitted magic template scenario")
        if (self.miscast_continuation is not None
                and not isinstance(self.miscast_continuation, NpcMagicMiscastContinuationPolicy)):
            raise TypeError("magic generation requires a typed Miscast continuation policy or None")
        if self.miscast_continuation != self.template_scenario.miscast_continuation:
            raise ValueError("magic generation Miscast continuation requires an explicit family policy equal to the template")
        if not isinstance(self.facts, NpcMagicScenarioFacts):
            raise TypeError("generation requires explicit magic facts for every composition")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("generation requires a typed objective window")
        _identifier(self.candidate_id_prefix)
        for name in ("max_candidates", "max_total_trials"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
            if value < 1:
                raise ValueError(f"{name} must be positive")
        for name in ("groups", "scene_frames", "stages"):
            if not isinstance(getattr(self, name), (tuple, list)):
                raise TypeError(f"magic generation {name} requires an ordered tuple or list")
        groups, frames, stages = tuple(self.groups), tuple(self.scene_frames), tuple(self.stages)
        if not groups:
            raise ValueError("magic generation requires at least one composition group")
        if not all(isinstance(group, MagicCompositionGroup) for group in groups):
            raise TypeError("generation requires typed magic composition groups")
        if len({group.group_id for group in groups}) != len(groups):
            raise ValueError("magic composition group IDs must be unique")
        template = self.template_scenario
        participants = {p.state.actor_id: p for p in template.initial.roster.participants}
        wizard_id = template.initial.wizard.actor_id
        reserve = {actor for actor, participant in participants.items()
                   if actor != wizard_id and participant.state.side is not template.perspective_side}
        actors = tuple(actor for group in groups for actor in group.actor_ids)
        if len(set(actors)) != len(actors) or set(actors) != reserve:
            raise ValueError("magic groups must partition exactly the opposing Minion reserve, excluding the Wizard")
        for group in groups:
            definition = participants[group.actor_ids[0]].definition
            if any(participants[actor].definition != definition for actor in group.actor_ids):
                raise ValueError("each magic composition group must share one exact NPC definition")
        if not all(isinstance(frame, NpcMagicSceneFrame) for frame in frames):
            raise TypeError("generation requires typed magic family scene frames")
        if frames != template.scene_frames:
            raise ValueError("family scene frames must retain the exact ordered template frames")
        _validate_stages(stages)
        NpcMagicSimulationRequest(template, self.master_seed, stages[0].trials_per_candidate)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "scene_frames", frames)
        object.__setattr__(self, "stages", stages)
        if not 1 <= self.candidate_count <= self.max_candidates:
            raise ValueError("magic composition count is empty or exceeds max_candidates")
        if self.planned_trials > self.max_total_trials:
            raise ValueError("generated magic evaluation exceeds max_total_trials")

    @property
    def candidate_count(self) -> int:
        count = prod(group.maximum_count - group.minimum_count + 1 for group in self.groups)
        # With either perspective, zero removes a mandatory Wizard Minion ally
        # or opponent. The fixed Wizard never makes that vector admissible.
        return count - int(all(group.minimum_count == 0 for group in self.groups))

    @property
    def planned_trials(self) -> int:
        return _planned_trials(self.candidate_count, self.stages)


@dataclass(frozen=True, slots=True)
class MagicCandidateGenerationResult:
    source_request: MagicCandidateGenerationRequest
    evaluation_request: MagicStagedEvaluationRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MagicCandidateGenerationRequest):
            raise TypeError("generation result requires its typed magic source")
        if not isinstance(self.evaluation_request, MagicStagedEvaluationRequest):
            raise TypeError("generation result requires a typed magic staged request")
        source, evaluation = self.source_request, self.evaluation_request
        if (evaluation.master_seed != source.master_seed or evaluation.stages != source.stages
                or evaluation.max_total_trials != source.max_total_trials or evaluation.window != source.window
                or len(evaluation.candidates) != source.candidate_count):
            raise ValueError("generated magic evaluation has foreign parameters or an incomplete candidate list")
        # Resolve the models/construction cycle locally. Rebuild one expected
        # projection at a time without retaining a second complete family.
        from towr.application.magic_candidate_generation import _count_vectors, _project_candidate

        for counts, candidate in zip(_count_vectors(source), evaluation.candidates):
            if candidate != _project_candidate(source, counts):
                raise ValueError("generated magic candidate differs from its exact source projection")
