"""Source-bound Skin Wolf end phase; an ordered wave is not an Attack action."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState, ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.resolution_models import StaggerImpactRequest, StaggerImpactResult, TargetInjuryPolicy
from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
from towr.domain.pc_flagellant_models import pc_flagellant_first_stagger_spec

SKIN_WOLF_DEFINITION_ID = 'pc-book-npc:skin_wolf'
WARPED_FORM_RULE_ID = 'RULE-PROFILE-MONSTER-011:warped-form'


def _ids(*values):
    if any(type(value) is not str or not value.strip() for value in values):
        raise TypeError('Warped Form requires exact nonempty source IDs')


@dataclass(frozen=True, slots=True)
class PcWarpedFormActivationProof:
    activation_id: str
    actor_id: str
    previous_injury: ProfileInjuryState
    injury: ProfileInjuryState
    target_ids: tuple[str, ...]

    def __post_init__(self):
        _ids(self.activation_id, self.actor_id)
        if type(self.target_ids) is not tuple:
            raise TypeError('wave snapshot must be an exact ordered tuple')
        _ids(*self.target_ids)
        if len(set(self.target_ids)) != len(self.target_ids) or self.actor_id in self.target_ids:
            raise ValueError('wave snapshot cannot duplicate targets or include its caster')
        for injury in (self.previous_injury, self.injury):
            if type(injury) is not ProfileInjuryState:
                raise TypeError('Warped Form retains exact cost/heal injury states')
            replace(injury)


@dataclass(frozen=True, slots=True)
class PcWarpedFormTargetProof:
    activation_id: str
    request: StaggerImpactRequest
    result: StaggerImpactResult

    def __post_init__(self):
        _ids(self.activation_id)
        if type(self.request) is not StaggerImpactRequest or type(self.result) is not StaggerImpactResult:
            raise TypeError('wave target requires its exact Stagger impact receipt')
        replace(self.request)
        replace(self.result)


@dataclass(frozen=True, slots=True)
class PcWarpedFormProfileProof:
    activation_id: str
    target_id: str
    source: ProfileStateChangeRequest
    decision: MinionDefeatDecision | None

    def __post_init__(self):
        _ids(self.activation_id, self.target_id)
        if type(self.source) is not ProfileStateChangeRequest:
            raise TypeError('wave Wound ACK requires its exact profile change')
        replace(self.source)
        if self.decision is not None:
            if type(self.decision) is not MinionDefeatDecision:
                raise TypeError('wave defeat requires its exact GM disposition')
            replace(self.decision)


@dataclass(frozen=True, slots=True)
class PcWarpedFormMinionDefeatProof:
    activation_id: str
    target_id: str

    def __post_init__(self):
        _ids(self.activation_id, self.target_id)


@dataclass(frozen=True, slots=True)
class PcWarpedFormEndProof:
    activation_id: str

    def __post_init__(self):
        _ids(self.activation_id)


def current_warped_form(state):
    """The single open activation, retained independently of the action target."""
    for proof in reversed(state.history):
        if type(proof) is PcWarpedFormEndProof:
            return None
        if type(proof) is PcWarpedFormActivationProof:
            return proof
    return None


def expected_pc_warped_form_activation(state):
    turn = state.round_state.active_turn
    if (turn is None or state.pending or state.pending_wound is not None
            or not turn.action_slots or not all(slot.executed for slot in turn.action_slots)):
        return None
    policy = next((p for p in state.source.npc_warped_form_policies if p.actor_id == turn.actor_id), None)
    if policy is None:
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    activation_id = pc_melee_action_id(state, turn.actor_id) + ':warped-form'
    if any(type(p) is PcWarpedFormActivationProof and p.activation_id == activation_id for p in state.history):
        return None
    enemy = state.enemy(turn.actor_id)
    before = enemy.state.injury
    if (enemy.definition.id != SKIN_WOLF_DEFINITION_ID or before.defeated or before.wounds == 0
            or before.conditions.has(Condition.STAGGERED) or turn.actor_id in state.exited_npc_ids):
        return None
    # Admission permits fresh physical melee sources only: every Wound in this
    # scenario comes from physical weapons or their non-fire Stagger consequences.
    # Unknown initial Wounds, magic and external producers are excluded by source.
    after = replace(before, wounds=before.wounds-1,
        conditions=before.conditions.with_condition(Condition.STAGGERED))
    live = {m.actor_id for m in state.live_party} | {e.state.actor_id for e in state.live_enemies}
    return PcWarpedFormActivationProof(activation_id, turn.actor_id, before, after,
        tuple(actor for actor in policy.close_actor_ids if actor in live))


def next_warped_form_target(state):
    activation = current_warped_form(state)
    if activation is None or state.pending or state.pending_wound is not None:
        return None
    targets = tuple(p.request.target_id for p in state.history
        if type(p) is PcWarpedFormTargetProof and p.activation_id == activation.activation_id)
    if targets != activation.target_ids[:len(targets)]:
        raise ValueError('wave targets changed their committed snapshot order')
    if len(targets) == len(activation.target_ids):
        return None
    actor = activation.target_ids[len(targets)]
    if actor in state.source.pc_activation_order:
        injury = state.participant(actor).injury
        policy = TargetInjuryPolicy.PLAYER
        coward = first = None
    else:
        enemy = state.enemy(actor)
        injury = enemy.state.injury
        policy = enemy.definition.injury_policy
        coward = pc_npc_stagger_defeat_spec(enemy.definition)
        first = pc_flagellant_first_stagger_spec(state, actor)
    return StaggerImpactRequest(activation.activation_id+':target:'+actor, actor, policy, injury,
        state.source.facts.can_leave_zone, False, minion_stagger_defeat=coward, first_stagger_wound=first)


class WarpedFormDecisions:
    def choose_repeated_stagger(self, *, request, allowed_choices):
        if StaggerChoice.SUFFER_WOUND not in allowed_choices:
            raise ValueError('wave requires the admitted suffer-Wound strategy')
        return StaggerChoice.SUFFER_WOUND

    def choose_wound_negation(self, *, request, table_roll, options):
        if options:
            raise ValueError('external Wound negations are outside this source')
        return None


def canonical_warped_form_impact(request, recorded):
    """Re-execute the rule using only the actual recorded Wounds Table dice."""
    from towr.rules.stagger_impact_resolution import resolve_stagger_impact
    values = tuple(recorded.character_wound.table_roll.values) if recorded.character_wound is not None else ()
    class Dice:
        index = 0
        def randint(self, lower, upper):
            if self.index == len(values):
                raise ValueError('wave receipt omitted a required Wound die')
            value = values[self.index]
            self.index += 1
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('wave Wound dice require exact in-range integers')
            return value
    dice = Dice()
    result = resolve_stagger_impact(request, dice, decisions=WarpedFormDecisions())
    if dice.index != len(values):
        raise ValueError('wave receipt invented unused Wound dice')
    return result
