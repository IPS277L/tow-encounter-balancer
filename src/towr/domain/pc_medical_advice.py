"""Bounded clinical advice, never an alternative medical rule or execution.

One defeated Minion is one utility unit, as in existing combat advice. Compare
the foregone ordinary action with changes to at most two actual future patient
turns, plus one unit for avoiding death during those own end phases. Incoming
enemy actions, later new injuries and postoperative healing are not predicted.
Printed Recall distributions are conservative: optional Fate is not promised
for either medical Test; the ordinary-action selector keeps its existing Fate
policy. Every branch is a read-only forecast, without Tests, proofs or RNG draws.
"""
from dataclasses import dataclass,replace,is_dataclass
from math import isfinite

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (CharacterInjuryState,WoundConditionEffect,WoundRestrictionEffect,
    WoundRestriction,WoundEffectDuration,injury_is_defeated)
from towr.domain.pc_medical_tactics import MedicalActionChoice,MedicalActionKind,medical_actions
from towr.domain.turn_models import CombatActionKind
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation


@dataclass(frozen=True,slots=True)
class MedicalAdvice:
    choice:MedicalActionChoice
    utility:float
    ordinary_utility:float

    def __post_init__(self):
        if type(self.choice) is not MedicalActionChoice:raise TypeError('medical advice needs an attainable typed choice')
        for value in (self.utility,self.ordinary_utility):
            if type(value) is not float or not isfinite(value):raise TypeError('medical advice needs finite utilities')


@dataclass(frozen=True,slots=True)
class _NpcOrdinary:
    action:CombatActionKind
    view:object
    weapon_use:object|None=None


class MedicalAdviceView:
    """Uncommitted body/inventory facts for existing finite tactical queries."""
    medical_advice_disabled=True

    def __init__(self,base,**changes):self._base=base;self._changes=changes
    def __getattr__(self,name):return self._changes[name] if name in self._changes else getattr(self._base,name)
    def participant(self,actor):return next(row for row in self.party if row.actor_id==actor)
    def enemy(self,actor):return next(row for row in self.enemies if row.state.actor_id==actor)
    @property
    def live_party(self):return tuple(row for row in self.party if not row.injury.dead)
    @property
    def live_enemies(self):
        hostile=set(self.source.enemy_activation_order)
        return tuple(row for row in self.enemies if row.state.actor_id in hostile
            and not injury_is_defeated(row.state.injury) and row.state.actor_id not in self.exited_npc_ids)


def _body(state,actor):
    from towr.domain.pc_medical_models import medical_effective_body
    return medical_effective_body(state,actor)


def _with_body(state,actor,body):
    if actor in state.source.pc_activation_order:
        return MedicalAdviceView(state,party=tuple(body if row.actor_id==actor else row for row in state.party))
    enemy=state.enemy(actor)
    inventory=body.weapon_inventory
    from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
    updated=replace(enemy,state=replace(enemy.state,injury=body.injury,weapon_inventory=inventory,
        tool_inventory=body.tool_inventory,wields_weapon=any(item.location is WeaponItemLocation.HELD for item in inventory.items),
        holds_shield=inventory.shield_hand is not None,available_attack_ids=npc_inventory_attack_ids(enemy.definition,inventory)))
    changes=dict(enemies=tuple(updated if row.state.actor_id==actor else row for row in state.enemies))
    if type(body.injury) is CharacterInjuryState:
        changes['npc_champions']=tuple(replace(row,body_facts=body.body_facts,
            timed_wounds=tuple(t for t in body.timed_wounds if t.effect in body.injury.active_wound_effects))
            if row.actor_id==actor else row for row in state.npc_champions)
    view=MedicalAdviceView(state,**changes)
    from towr.domain.pc_npc_resilience_models import npc_current_resilience
    resilience=npc_current_resilience(view,actor)
    return MedicalAdviceView(view,enemies=tuple(replace(row,state=replace(row.state,current_resilience=resilience))
        if row.state.actor_id==actor else row for row in view.enemies))


def _ordinary(state,actor):
    """Existing Attack/Help/Recover units, with medical recursion disabled."""
    injury=_body(state,actor).injury
    if injury_is_defeated(injury) or injury.conditions.has(Condition.DEFENCELESS):return 0.,None
    state=_cleanup_tools(state,actor)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_tactical_models import _select_pc_tactic_without_music
        choice=_select_pc_tactic_without_music(state,actor)
        return max(0.,float(choice.utility)),choice
    from towr.domain.pc_npc_weapon_inventory import _utility,npc_attack_weapon_use
    from towr.domain.pc_npc_normal_help_models import npc_normal_help_choice,npc_help_weapon_use
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    recover=(1. if injury.conditions.has(Condition.PRONE) and not has_ongoing_condition(injury,Condition.PRONE) else 0.)
    best=(recover,_NpcOrdinary(CombatActionKind.RECOVER,state))
    for candidate in _npc_equipment_views(state,actor):
        attack=max(0.,float(_utility(candidate,actor)))
        if attack>best[0]:best=attack,_NpcOrdinary(CombatActionKind.ATTACK,candidate,npc_attack_weapon_use(candidate,actor))
        help_choice=npc_normal_help_choice(candidate,actor)
        if help_choice is not None and help_choice.utility>best[0]:
            best=float(help_choice.utility),_NpcOrdinary(CombatActionKind.HELP,candidate,
                npc_help_weapon_use(candidate,actor,help_choice.policy.skill))
    return best


def _npc_equipment_views(state,actor):
    """Actual finite Equip plans, including stowed medical tools, without receipts."""
    state=_cleanup_tools(state,actor)
    body=_body(state,actor)
    yield state
    from towr.domain.pc_npc_weapon_inventory import _plan
    from towr.domain.weapon_catalog import weapon_profile
    from towr.domain.ranged_weapon_profiles import RangedWeaponHands
    for item in body.weapon_inventory.items:
        if item.location not in (WeaponItemLocation.HELD,WeaponItemLocation.CARRIED):continue
        profile=weapon_profile(item.kind)
        grips=((WeaponGrip.BOTH,WeaponGrip.LEFT,WeaponGrip.RIGHT) if profile.variable_grip else
            (WeaponGrip.BOTH,) if profile.hands is RangedWeaponHands.TWO_HANDED else (WeaponGrip.LEFT,WeaponGrip.RIGHT))
        for grip in grips:
            try:plan=_plan(state,actor,item,grip)
            except ValueError:continue
            if plan is None:continue
            touched=set()
            for before,after in zip(body.weapon_inventory.items,plan.after.items,strict=True):
                if (before.location,before.grip)==(after.location,after.grip):continue
                for unit in (before,after):
                    if unit.location is WeaponItemLocation.HELD:
                        touched.update((WeaponGrip.LEFT,WeaponGrip.RIGHT) if unit.grip is WeaponGrip.BOTH else (unit.grip,))
            injury=_incidental_injury(body,touched)
            changes=dict(weapon_inventory=plan.after,injury=injury)
            if is_dataclass(body):changed=replace(body,**changes)
            else:
                from types import SimpleNamespace
                changed=SimpleNamespace(**(vars(body)|changes))
            yield _with_body(state,actor,changed)


def _incidental_injury(body,hands):
    injury=body.injury
    if type(injury) is CharacterInjuryState and hands:
        from towr.domain.pc_heavy_wound_models import critical_for_action,critical_for_hand
        from towr.domain.pc_melee_models import PcWeaponHand
        injury=critical_for_action(body,None)
        for hand in hands:injury=critical_for_hand(replace(body,injury=injury),PcWeaponHand(hand.value))
    return injury


def _cleanup_tools(state,actor):
    body=_body(state,actor)
    tools=replace(body.tool_inventory,items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        if item.location is WeaponItemLocation.HELD else item for item in body.tool_inventory.items))
    if tools!=body.tool_inventory:
        touched={hand for item in body.tool_inventory.items if item.location is WeaponItemLocation.HELD
            for hand in item.occupied_hands}
        changes=dict(tool_inventory=tools,injury=_incidental_injury(body,touched))
        if is_dataclass(body):body=replace(body,**changes)
        else:
            from types import SimpleNamespace
            body=SimpleNamespace(**(vars(body)|changes))
        state=_with_body(state,actor,body)
    return state


def _action_price(state,actor,kind,hand=None):
    body=_body(state,actor)
    if type(body.injury) is not CharacterInjuryState:return state
    from towr.domain.pc_heavy_wound_models import critical_for_action
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    stands=(kind is CombatActionKind.RECOVER and body.injury.conditions.has(Condition.PRONE)
        and not has_ongoing_condition(body.injury,Condition.PRONE))
    injury=critical_for_action(body,kind,used_hand=hand,removes_prone=stands)
    return _with_body(state,actor,replace(body,injury=injury))


def _ordinary_price(state,actor,choice):
    state=_cleanup_tools(state,actor)
    if type(choice) is _NpcOrdinary:
        from towr.domain.pc_weapon_intent_models import weapon_use_hand
        return _action_price(choice.view,actor,choice.action,weapon_use_hand(choice.weapon_use))
    if choice is not None:kind=choice.action
    else:kind=CombatActionKind.ATTACK
    hand=None
    if kind is CombatActionKind.ATTACK:
        if actor in state.source.pc_activation_order:
            from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
            use=pc_attack_weapon_use(state,actor)
        else:
            from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
            use=npc_attack_weapon_use(state,actor)
        if use is not None:
            from towr.domain.pc_weapon_intent_models import weapon_use_hand
            hand=weapon_use_hand(use)
    return _action_price(state,actor,kind,hand)


def _prepare(state,actor,choice):
    """Mirror only actual hand conflicts; no ground item or receipt is created."""
    body=_body(state,actor)
    from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands,critical_for_action
    from towr.domain.pc_melee_models import PcWeaponHand
    hands=(tuple(WeaponGrip(side.value) for side in usable_hands(body)) if type(body.injury) is CharacterInjuryState
        else (WeaponGrip.LEFT,WeaponGrip.RIGHT))
    injured=({WeaponGrip(side.value) for side in injured_hands(body)} if type(body.injury) is CharacterInjuryState else set())
    def held(grip):return (WeaponGrip.LEFT,WeaponGrip.RIGHT) if grip is WeaponGrip.BOTH else (grip,)
    inventory=body.weapon_inventory
    def cost(hand):return (hand in injured,hand is inventory.shield_hand,
        sum(hand in held(item.grip) for item in inventory.items if item.location is WeaponItemLocation.HELD),hand is WeaponGrip.RIGHT)
    if not hands:return None,None
    hand=min(hands,key=cost)
    conflicts=tuple(item for item in inventory.items if item.location is WeaponItemLocation.HELD and hand in held(item.grip))
    if any(binding.attacker_id==actor and binding.weapon_id in {item.id for item in conflicts}
            for binding in state.briarroot_bindings):return None,None
    tools=replace(body.tool_inventory,items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        if item.location is WeaponItemLocation.HELD and item.id!=choice.kit_id and hand in item.occupied_hands else item
        for item in body.tool_inventory.items))
    if choice.pickup_tool:
        tools=replace(tools,items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None,dropped_zone_id=None)
            if item.id==choice.kit_id and item.location is WeaponItemLocation.DROPPED else item for item in tools.items))
    released=hand is inventory.shield_hand
    changed=replace(inventory,items=tuple(replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        if item in conflicts else item for item in inventory.items),shield_hand=None if released else inventory.shield_hand)
    injury=body.injury
    if type(injury) is CharacterInjuryState:
        if changed!=inventory or tools!=body.tool_inventory:
            injury=critical_for_action(body,None,used_hand=PcWeaponHand(hand.value))
        injury=critical_for_action(replace(body,injury=injury),CombatActionKind.RECOVER,used_hand=PcWeaponHand(hand.value))
    changes=dict(weapon_inventory=changed,tool_inventory=tools,injury=injury)
    # A forecast releases protection only; physical drop positions belong to execution.
    if released and actor in state.source.pc_activation_order:changes['shield']=None
    if is_dataclass(body):changed_body=replace(body,**changes)
    else:
        from types import SimpleNamespace
        changed_body=SimpleNamespace(**(vars(body)|changes))
    prepared=_with_body(state,actor,changed_body)
    return prepared,hand


def _treated_view(state,actor,sequence,*,suppress=False):
    body=_body(state,actor);injury=body.injury
    durations=(WoundEffectDuration.UNTIL_TREATED,WoundEffectDuration.UNTIL_HEALED) if suppress else (WoundEffectDuration.UNTIL_TREATED,)
    removed=tuple(effect for effect in injury.active_wound_effects if effect.wound_sequence==sequence and effect.duration in durations)
    from towr.domain.pc_medical_models import medical_condition_snapshots
    conditions=injury.conditions
    for snapshot in medical_condition_snapshots(state,actor,injury,removed):
        if not snapshot.has_other_active_source:conditions=conditions.without_condition(snapshot.condition)
    remaining=tuple(effect for effect in injury.active_wound_effects if effect not in removed)
    wounds=tuple(replace(wound,treated=True) if wound.sequence==sequence else wound for wound in injury.wounds)
    from towr.domain.pc_heavy_wound_models import PcBodyFactKind
    facts=tuple(fact for fact in body.body_facts if not (suppress and fact.wound_sequence==sequence
        and fact.kind in (PcBodyFactKind.UNUSABLE_ARM,PcBodyFactKind.CLUTCH_STOMACH)))
    changed=replace(body,injury=replace(injury,wounds=wounds,conditions=conditions,active_wound_effects=remaining),
        body_facts=facts,timed_wounds=tuple(t for t in body.timed_wounds if t.effect in remaining))
    if actor in state.source.pc_activation_order and changed.shield is not None:
        from towr.domain.pc_shield_models import PcShieldLocation
        from towr.domain.pc_heavy_wound_models import usable_hands
        if (changed.shield.location is PcShieldLocation.UNAVAILABLE
                and changed.weapon_inventory.shield_hand is not None and changed.shield.hand in usable_hands(changed)):
            changed=replace(changed,shield=replace(changed.shield,location=PcShieldLocation.HELD))
    return _with_body(state,actor,changed)


def _success(state,actor,skill,identifier,*,target=None):
    from towr.domain.pc_medical_models import medical_test
    from towr.domain.pc_tactical_models import _distribution
    return 1.-_distribution(medical_test(state,actor,identifier,skill,target=target))[0]


def _after_medical_test(state,actor,request):
    """Advance one-use forecast modifiers without fabricating an executed Test."""
    from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
    used={modifier.rule_id for modifier in request.dice_modifiers}
    modifiers=tuple(modifier for modifier in state.magic_modifiers
        if not (modifier.target_id==actor and modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY
            and modifier.source_id in used))
    state=MedicalAdviceView(state,magic_modifiers=modifiers)
    if any(modifier.rule_id=='RULE-HEALTH-005:crushed-rib-next-test'
            for modifier in request.quality_modifiers):
        body=_body(state,actor)
        if type(body.injury) is CharacterInjuryState:
            injury=replace(body.injury,active_wound_effects=tuple(effect for effect in body.injury.active_wound_effects
                if not (type(effect) is WoundRestrictionEffect and effect.restriction is WoundRestriction.NEXT_TEST_IS_GRIM)))
            state=_with_body(state,actor,replace(body,injury=injury))
    return state


def _end_success(state,actor):
    from towr.domain.test_models import Skill
    from towr.domain.pc_tactical_models import _distribution
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        request=_pc_test(state,actor,'medical-advice:endurance',Skill.ENDURANCE)
    else:
        from towr.domain.pc_npc_champion_models import npc_champion_test
        request=npc_champion_test(state,actor,'medical-advice:endurance',Skill.ENDURANCE)
    return 1.-_distribution(request)[0]


def _turns(state,actor,doctor,*,delay=0):
    remaining=max(0,state.source.max_rounds-state.round_state.round_number)
    unavailable=(*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    later=actor!=doctor and actor not in unavailable
    return min(2,max(0,remaining+int(later)-delay))


def _future_value(state,actor,turns,*,current_end=False):
    body=_body(state,actor)
    if injury_is_defeated(body.injury):return 0.
    value,choice=_ordinary(state,actor)
    priced=_ordinary_price(state,actor,choice)
    critical=_body(priced,actor).injury.conditions.has(Condition.CRITICALLY_INJURED)
    ready=0. if body.injury.conditions.has(Condition.DEFENCELESS) else 1.
    helpless=1.-ready;dead=0.;score=0.
    chance=_end_success(priced,actor) if critical and type(body.injury) is CharacterInjuryState else 1.
    def end(ready,helpless,dead,p):return ready*p,helpless*p+ready*(1.-p),dead+helpless*(1.-p)
    if current_end:
        current=(_end_success(state,actor) if body.injury.conditions.has(Condition.CRITICALLY_INJURED)
            and type(body.injury) is CharacterInjuryState else 1.)
        ready,helpless,dead=end(ready,helpless,dead,current)
    for _ in range(turns):
        score+=ready*value
        ready,helpless,dead=end(ready,helpless,dead,chance)
    return score+(1.-dead)


def choose_compared_medical_action(state,actor):
    """Select medicine only when its bounded expected benefit beats ordinary work."""
    if getattr(state,'medical_advice_disabled',False):return None
    choices=tuple(choice for choice in medical_actions(state,actor) if choice.kind is MedicalActionKind.TREATMENT)
    if not choices:return None
    view=MedicalAdviceView(state)
    ordinary,ordinary_choice=_ordinary(view,actor)
    baseline=_ordinary_price(view,actor,ordinary_choice)
    from towr.domain.pc_medical_models import medical_facts
    from towr.domain.pc_medical_models import medical_test
    from towr.domain.pc_tactical_models import _distribution
    from towr.domain.talent_actor_models import actor_has_talent
    from towr.domain.talent_catalog import TalentId
    from towr.domain.test_models import Skill
    best=None
    for choice in choices:
        if choice.pickup_tool and state.round_state.round_number>=state.source.max_rounds:continue
        prepared,hand=_prepare(view,actor,choice)
        if prepared is None:continue
        facts=medical_facts(prepared,actor)
        treatment=1. if facts.anatomy_lore else _success(prepared,actor,Skill.RECALL,'medical-advice:treatment',target=choice.target_id)
        if not facts.anatomy_lore:
            request=medical_test(prepared,actor,'medical-advice:treatment',Skill.RECALL,target=choice.target_id)
            prepared=_after_medical_test(prepared,actor,request)
        treated=_treated_view(prepared,choice.target_id,choice.wound_sequence)
        can_suppress=actor_has_talent(prepared,actor,TalentId.COMBAT_SURGEON) and any(
            effect.wound_sequence==choice.wound_sequence and effect.duration is WoundEffectDuration.UNTIL_HEALED
            for effect in _body(treated,choice.target_id).injury.active_wound_effects)
        suppressed=_treated_view(prepared,choice.target_id,choice.wound_sequence,suppress=True)
        suppression=0.
        if can_suppress:
            request=medical_test(treated,actor,'medical-advice:surgeon',Skill.RECALL,target=choice.target_id)
            suppression=1.-_distribution(request)[0]
            treated=_after_medical_test(treated,actor,request)
            suppressed=_after_medical_test(suppressed,actor,request)
        targets=(actor,) if choice.target_id==actor else (actor,choice.target_id)
        delay=int(choice.pickup_tool)
        def future(selected):return sum(_future_value(selected,target,_turns(state,target,actor,delay=delay),
            current_end=target==actor and not choice.pickup_tool) for target in targets)
        value=(1.-treatment)*future(prepared)+treatment*((1.-suppression)*future(treated)+suppression*future(suppressed))-future(baseline)
        if choice.pickup_tool:
            # Pickup precedes a later treatment. It cannot prevent this turn's
            # Critical end Test; losing readiness prevents that later action.
            own=_body(prepared,actor).injury
            continuation=(_end_success(prepared,actor) if type(own) is CharacterInjuryState
                and own.conditions.has(Condition.CRITICALLY_INJURED) else 1.)
            value=continuation*value/2.
        if value>ordinary+1e-12 and (best is None or value>best.utility+1e-12):
            best=MedicalAdvice(choice,float(value),float(ordinary))
    return best
