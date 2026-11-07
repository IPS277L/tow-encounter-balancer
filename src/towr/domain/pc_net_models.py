"""Finite Net stock, explicit free draws and independent Burdened causes."""
from dataclasses import dataclass, replace

from towr.domain.attack_models import AttackOutcome, ConditionImpactSpec, MissConsequence
from towr.domain.condition_models import Condition, ConditionApplicationResult
from towr.domain.resolution_models import AttackerStaggerRequest, ConditionImpactResult, ResolutionResult
from towr.domain.turn_models import CombatActionKind

from towr.domain.pc_npc_net_policy_models import NET_DEFINITION_ID, NET_RULE_ID


@dataclass(frozen=True, slots=True)
class PcNpcNetDrawProof:
    actor_id: str
    action_id: str
    attack_id: str

    def __post_init__(self):
        if any(type(value) is not str or not value.strip()
                for value in (self.actor_id,self.action_id,self.attack_id)):
            raise TypeError('Net draw requires exact nonempty source IDs')
        if self.attack_id not in ('jagged_spear','weighted_net'):
            raise ValueError('Net draw must select its carried Net or Spear')


@dataclass(frozen=True, slots=True)
class PcNetConditionSource:
    attack_id: str
    attacker_id: str
    target_id: str
    application_id: str
    rule_id: str
    condition: Condition = Condition.BURDENED

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in
                (self.attack_id,self.attacker_id,self.target_id,self.application_id,self.rule_id)):
            raise TypeError('Net cause requires exact nonempty source IDs')
        if (self.attacker_id==self.target_id or self.rule_id!=NET_RULE_ID
                or type(self.condition) is not Condition or self.condition is not Condition.BURDENED):
            raise ValueError('Net cause must retain its own Burdened source')


def is_net_impact(impact):
    return type(impact) is ConditionImpactSpec and impact.rule_id==NET_RULE_ID


def expected_net_resolution(kernel, attack):
    if (not is_net_impact(kernel.attack.impact_spec)
            or kernel.attack.impact_spec.condition is not Condition.BURDENED
            or kernel.target_state.conditions.has(Condition.DEFENCELESS)):
        raise ValueError('bounded Net requires its Burdened impact and non-Defenceless PC')
    target = kernel.target_state
    applications = ()
    replacement = None
    followups = ()
    if attack.outcome is AttackOutcome.HIT:
        conditions = target.conditions.with_condition(Condition.BURDENED)
        application = ConditionApplicationResult(kernel.id+':condition-impact',conditions,
            Condition.BURDENED,target.conditions.has(Condition.BURDENED),False,NET_RULE_ID,None,(NET_RULE_ID,))
        applications = (application,)
        replacement = ConditionImpactResult(application)
        target = replace(target,conditions=conditions)
    elif attack.miss_consequence is MissConsequence.STAGGER_ATTACKER:
        followups = (AttackerStaggerRequest(kernel.attack.id),)
    return ResolutionResult(kernel.id,attack,replacement,target,None,None,None,None,None,
        followups,condition_applications=applications)


def net_condition_sources_from_attack(request, result):
    if not is_net_impact(request.kernel_request.attack.impact_spec):
        return ()
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    canonical = expected_net_resolution(request.kernel_request,result.attack)
    if result!=canonical:
        raise ValueError('Net result changed its primary Condition or invented Damage/Wound')
    validate_pc_melee_source_types(result,canonical)
    if result.attack.outcome is not AttackOutcome.HIT:
        return ()
    return (PcNetConditionSource(request.id,request.actor_id,request.target_id,
        result.condition_applications[0].request_id,NET_RULE_ID),)


def net_stock_and_held(state, actor):
    """Derive only finite stock/equipment; full owner replay certifies each proof."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    policy = next(p for p in state.source.npc_net_policies if p.actor_id==actor)
    remaining, held = policy.initial_count, 'weighted_net'
    for proof in state.history:
        if type(proof) is PcNpcNetDrawProof and proof.actor_id==actor:
            replace(proof)
            if proof.attack_id==held or proof.attack_id=='weighted_net' and not remaining:
                raise ValueError('Net free draw repeated current equipment or restored spent stock')
            held = proof.attack_id
        elif (type(proof) is PcAttackProof and proof.request.actor_id==actor
                and is_net_impact(proof.request.kernel_request.attack.impact_spec)):
            if remaining!=1 or held!='weighted_net':
                raise ValueError('Net throw lacks its one held unspent Net')
            remaining,held = 0,None
    return remaining,held


def selected_pc_npc_net_attack(state, actor):
    if state.source.enemy(actor).definition.id!=NET_DEFINITION_ID:
        return None
    from towr.domain.pc_npc_net_policy_models import PcNpcNetMode
    policy = next(p for p in state.source.npc_net_policies if p.actor_id==actor)
    remaining,_ = net_stock_and_held(state,actor)
    target = next((state.participant(a) for a in state.source.enemy_target_priority
        if not state.participant(a).injury.dead),None)
    return ('weighted_net' if remaining and policy.mode is PcNpcNetMode.THROW_ONCE_THEN_SPEAR
        and target is not None and not any(target.injury.conditions.has(c)
            for c in (Condition.BURDENED,Condition.DEFENCELESS)) else 'jagged_spear')


def expected_pc_npc_net_draw(state):
    if not state.source.npc_net_policies or state.pending or state.pending_wound is not None:
        return None
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.enemy_activation_order
            or state.source.enemy(turn.actor_id).definition.id!=NET_DEFINITION_ID):
        return None
    if not turn.action_slots or turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK:
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    _,held = net_stock_and_held(state,turn.actor_id)
    selected = ('jagged_spear' if turn.action_slots[-1].executed
        else selected_pc_npc_net_attack(state,turn.actor_id))
    if selected==held:
        return None
    return PcNpcNetDrawProof(turn.actor_id,
        pc_melee_action_id(state,turn.actor_id)+':net:draw:'+selected,selected)


def expected_pc_npc_net_equipment(state, actor):
    old = state.source.enemy(actor).state
    remaining,held = net_stock_and_held(state,actor)
    return replace(old,available_attack_ids=('jagged_spear','weighted_net') if remaining else ('jagged_spear',),
        wields_weapon=held is not None)


def spend_pc_npc_net(state, enemies, request):
    if not is_net_impact(request.kernel_request.attack.impact_spec):
        return enemies
    actor = request.actor_id
    if state.source.enemy(actor).definition.id!=NET_DEFINITION_ID:
        raise ValueError('Net stock belongs to its full canonical loadout')
    remaining,held = net_stock_and_held(state,actor)
    if remaining!=1 or held!='weighted_net':
        raise ValueError('Net Attack cannot consume unavailable equipment')
    return tuple(replace(e,state=replace(e.state,available_attack_ids=('jagged_spear',),wields_weapon=False))
        if e.state.actor_id==actor else e for e in enemies)
