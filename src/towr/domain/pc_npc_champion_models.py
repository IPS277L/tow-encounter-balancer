"""NPC Character-injury owner, GM1.1 VII92, without PC Fate resources.

The NPC snapshot owns health/inventory. This bank contains only the extra
table-Wound metadata; the composed body is a view for shared anatomical rules.
"""
from __future__ import annotations
from dataclasses import dataclass,field,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState,WoundRestriction,WoundRestrictionEffect,WoundConditionEffect,WoundEffectDuration
from towr.domain.pc_heavy_wound_models import PcBodyFact,usable_hands
from towr.domain.pc_melee_models import PcWeaponHand,PcTwoHandedGrip
from towr.domain.pc_shield_models import PcShieldState,PcShieldLocation
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill,TestRequest,QualityModifier,TestQuality
from towr.domain.tool_inventory_models import ToolInventoryState
from towr.domain.weapon_inventory_models import WeaponInventoryState,WeaponItemLocation,WeaponGrip

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcTimedWound
    from towr.domain.pc_npc_shield_models import PcNpcShieldState
    from towr.domain.pc_battlefield_models import PcBattlefieldState
    from towr.domain.injury_models import WoundConsequenceRequest
    from towr.domain.recover_models import RecoverActionExecutionRequest,RecoverActionExecutionResult


def is_npc_champion(state,actor):
    return actor in state.source.npc_activation_order and state.source.enemy(actor).definition.injury_policy is TargetInjuryPolicy.CHAMPION


@dataclass(frozen=True,slots=True)
class NpcChampionMetadata:
    actor_id:str
    daily_wounds:DailyWoundState
    timed_wounds:tuple[PcTimedWound,...]=()
    body_facts:tuple[PcBodyFact,...]=()

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Champion metadata needs its actual NPC actor')
        if type(self.daily_wounds) is not DailyWoundState or self.daily_wounds.target_id!=self.actor_id:
            raise TypeError('Champion daily Wounds belong to this actor')
        replace(self.daily_wounds)
        if type(self.timed_wounds) is not tuple or type(self.body_facts) is not tuple:
            raise TypeError('Champion body and expiry metadata retain ordered tuples')
        from towr.domain.pc_melee_result_models import PcTimedWound
        for value,kind in (*( (t,PcTimedWound) for t in self.timed_wounds),
                           *( (f,PcBodyFact) for f in self.body_facts)):
            if type(value) is not kind: raise TypeError('Champion metadata needs exact typed body/expiry sources')
            replace(value)
        if len(set(self.body_facts))!=len(self.body_facts) or len({t.effect for t in self.timed_wounds})!=len(self.timed_wounds):
            raise ValueError('Champion metadata cannot repeat an anatomical or timed effect')


@dataclass(frozen=True,slots=True)
class NpcChampionBody:
    actor_id:str
    injury:CharacterInjuryState
    weapon_inventory:WeaponInventoryState
    daily_wounds:DailyWoundState
    timed_wounds:tuple[PcTimedWound,...]=()
    body_facts:tuple[PcBodyFact,...]=()
    shield:PcShieldState|None=None
    tool_inventory:ToolInventoryState=field(default_factory=ToolInventoryState)

    def __post_init__(self):
        if type(self.injury) is not CharacterInjuryState or type(self.weapon_inventory) is not WeaponInventoryState:
            raise TypeError('Champion body view keeps actual character health and physical inventory')
        replace(self.injury); replace(self.weapon_inventory); replace(self.tool_inventory)
        NpcChampionMetadata(self.actor_id,self.daily_wounds,self.timed_wounds,self.body_facts)
        from towr.domain.pc_heavy_wound_models import validate_body_fact_sources
        validate_body_fact_sources(self.injury,self.body_facts)
        if any(t.effect not in self.injury.active_wound_effects for t in self.timed_wounds):
            raise ValueError('Champion timed sources require an actual active Wound effect')
        if self.shield is not None: replace(self.shield)

    @property
    def weapon_hand(self):
        from towr.domain.pc_weapon_inventory import pc_hand
        item=self.weapon_inventory.active
        return pc_hand(item.grip) if item is not None and item.location is WeaponItemLocation.HELD else None


def initial_npc_champions(source):
    return tuple(NpcChampionMetadata(enemy.state.actor_id,DailyWoundState(source.day_id,enemy.state.actor_id))
        for enemy in source.npc_sources if enemy.definition.injury_policy is TargetInjuryPolicy.CHAMPION)


@dataclass(frozen=True,slots=True)
class PcNpcChampionRecoverProof:
    request:RecoverActionExecutionRequest
    result:RecoverActionExecutionResult
    previous_injury:CharacterInjuryState
    injury:CharacterInjuryState

    @property
    def actor_id(self): return self.request.actor_id

    def __post_init__(self):
        from towr.domain.recover_models import RecoverActionExecutionRequest,RecoverActionExecutionResult
        if (type(self.request) is not RecoverActionExecutionRequest or type(self.result) is not RecoverActionExecutionResult
                or type(self.previous_injury) is not CharacterInjuryState or type(self.injury) is not CharacterInjuryState):
            raise TypeError('Champion Recover requires actual action and Character injury witnesses')
        replace(self.request);replace(self.result);replace(self.previous_injury);replace(self.injury)


def npc_champion_body(state,actor):
    if not is_npc_champion(state,actor): raise ValueError('actor is not an admitted NPC Champion')
    enemy=state.enemy(actor)
    row=next((row for row in state.npc_champions if row.actor_id==actor),None)
    if row is None: raise ValueError('NPC Champion lost its separate table-Wound metadata')
    inventory=enemy.state.weapon_inventory
    shield=None
    if inventory.shield_hand is not None:
        shield=PcShieldState(PcShieldLocation.HELD,PcWeaponHand(inventory.shield_hand.value))
    body=NpcChampionBody(actor,enemy.state.injury,inventory,row.daily_wounds,row.timed_wounds,row.body_facts,
        shield,enemy.state.tool_inventory)
    if shield is not None and shield.hand not in usable_hands(body):
        body=replace(body,shield=PcShieldState(PcShieldLocation.UNAVAILABLE,shield.hand))
    return body


@dataclass(frozen=True,slots=True)
class NpcChampionShieldDrop:
    actor_id:str
    source:WoundConsequenceRequest
    previous:PcNpcShieldState
    state:PcNpcShieldState
    previous_battlefield:PcBattlefieldState|None
    battlefield:PcBattlefieldState|None

    def __post_init__(self):
        from towr.domain.pc_npc_shield_models import PcNpcShieldState,NpcShieldLocation,_shield_transition,_add_marker
        from towr.domain.injury_models import WoundConsequenceRequest
        if type(self.source) is not WoundConsequenceRequest or type(self.previous) is not PcNpcShieldState or type(self.state) is not PcNpcShieldState:
            raise TypeError('Champion Shield loss retains actual Wound and physical item sources')
        replace(self.source);replace(self.previous);replace(self.state)
        if self.previous.actor_id!=self.actor_id or self.state.location is not NpcShieldLocation.DROPPED:
            raise ValueError('Champion Shield loss changed actual owner or physical outcome')
        _shield_transition(self.previous,self.state,picked_up=False)
        if self.battlefield!=_add_marker(self.previous_battlefield,self.state):
            raise ValueError('Champion Shield loss changed its actual ground marker')


class _UpdatedView:
    def __init__(self,before,updates): self._before=before;self._updates=updates
    def __getattr__(self,name): return self._updates[name] if name in self._updates else getattr(self._before,name)
    def enemy(self,actor): return next(e for e in self.enemies if e.state.actor_id==actor)


def npc_champion_updates(state,actor,*,body=None,injury=None,daily_wounds=None,timed_wounds=None,body_facts=None,
        tool_inventory=None,npc_shield_drop=None):
    before=npc_champion_body(state,actor)
    if body is not None:
        if type(body) is not NpcChampionBody or body.actor_id!=actor:
            raise TypeError('Champion update requires the same exact body view')
        if any(value is not None for value in (injury,daily_wounds,timed_wounds,body_facts,tool_inventory)):
            raise ValueError('Champion update selects either its full body or explicit changed fields')
    else:
        body=replace(before,**{k:v for k,v in dict(injury=injury,daily_wounds=daily_wounds,
            timed_wounds=timed_wounds,body_facts=body_facts,tool_inventory=tool_inventory).items() if v is not None})
    row=NpcChampionMetadata(actor,body.daily_wounds,body.timed_wounds,body.body_facts)
    enemy=state.enemy(actor)
    inventory=body.weapon_inventory
    from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
    enemy=replace(enemy,state=replace(enemy.state,injury=body.injury,weapon_inventory=inventory,
        tool_inventory=body.tool_inventory,wields_weapon=any(i.location is WeaponItemLocation.HELD for i in inventory.items),
        holds_shield=inventory.shield_hand is not None,available_attack_ids=npc_inventory_attack_ids(enemy.definition,inventory)))
    updates=dict(enemies=tuple(enemy if e.state.actor_id==actor else e for e in state.enemies),
        npc_champions=tuple(row if r.actor_id==actor else r for r in state.npc_champions))
    if npc_shield_drop is not None:
        replace(npc_shield_drop)
        if npc_shield_drop.actor_id!=actor: raise ValueError('Champion cannot drop another NPC Shield')
        updates['npc_shields']=tuple(npc_shield_drop.state if s.actor_id==actor else s for s in state.npc_shields)
        updates['battlefield']=npc_shield_drop.battlefield
    from towr.domain.pc_npc_resilience_models import npc_current_resilience
    resilience=npc_current_resilience(_UpdatedView(state,updates),actor)
    updates['enemies']=tuple(replace(e,state=replace(e.state,current_resilience=resilience))
        if e.state.actor_id==actor else e for e in updates['enemies'])
    return updates


def npc_champion_test_modifiers(state,actor,skill):
    if not is_npc_champion(state,actor): return (),()
    from towr.domain.pc_medical_models import medical_effective_body
    body=medical_effective_body(state,actor)
    qualities=[]
    if skill not in (Skill.ENDURANCE,Skill.WILLPOWER) and body.injury.conditions.has(Condition.BLINDED):
        qualities.append(QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM))
    if any(isinstance(e,WoundRestrictionEffect) and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM
            for e in body.injury.active_wound_effects):
        from towr.domain.crushed_rib_test_models import CRUSHED_RIB_TEST_RULE_ID
        qualities.append(QualityModifier(CRUSHED_RIB_TEST_RULE_ID,TestQuality.GRIM))
    return (),tuple(qualities)


def npc_champion_test(state,actor,test_id,skill):
    source=state.enemy(actor).definition.generated_components
    if source is None or not is_npc_champion(state,actor): raise ValueError('Champion Test requires actual generated source')
    profile={Skill.ENDURANCE:lambda:source.endurance_profile,Skill.RECALL:lambda:source.recall_profile,
        Skill.DEXTERITY:lambda:source.dexterity_profile}
    if skill in profile: selected=profile[skill]()
    else: raise ValueError('this Champion body Test requires Endurance, Recall or Dexterity')
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    from towr.domain.pc_oath_models import filter_honour_test
    md,mq=magic_test_modifiers(state,actor,skill)
    extra,qualities=npc_champion_test_modifiers(state,actor,skill)
    dice=(*md,*actor_armour_test_modifiers(state,actor,skill),*extra)
    if state.enemy(actor).state.injury.conditions.has(Condition.DRAINED): dice=tuple(m for m in dice if m.amount<=0)
    return filter_honour_test(TestRequest(test_id,selected,dice,(*mq,*qualities)))


def npc_champion_after_test(state,actor,injury=None):
    injury=npc_champion_body(state,actor).injury if injury is None else injury
    return replace(injury,active_wound_effects=tuple(e for e in injury.active_wound_effects
        if not isinstance(e,WoundRestrictionEffect) or e.restriction is not WoundRestriction.NEXT_TEST_IS_GRIM))


def npc_champion_wound_completion(state):
    from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionRequest
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    actor=state.pending_actor_id; pending=state.pending_wound
    if pending is None or not is_npc_champion(state,actor): raise ValueError('no actual Champion Wound awaits completion')
    body=npc_champion_body(state,actor)
    consumed=tuple(p.completion.source_request.roll.request_id for p in state.history
        if type(p) is PcWoundCompletionProof and p.completion.source_request.roll.source_request.target_id==actor)
    return CharacterWoundLifecycleCompletionRequest(pending.request_id+':complete',pending,body.injury,body.daily_wounds,
        daily_registration_id=pending.request_id+':daily' if pending.wound_result.wound_accepted else None,
        consumed_roll_ids=consumed)


def validate_npc_champions(state):
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    expected=tuple(e.state.actor_id for e in state.source.npc_sources if e.definition.injury_policy is TargetInjuryPolicy.CHAMPION)
    if type(state.npc_champions) is not tuple or tuple(r.actor_id for r in state.npc_champions)!=expected:
        raise ValueError('Champion metadata bank must match the complete source order')
    for row in state.npc_champions:
        if type(row) is not NpcChampionMetadata: raise TypeError('Champion metadata bank needs exact typed rows')
        replace(row)
        if row.daily_wounds.day_id!=state.source.day_id: raise ValueError('Champion day source changed')
        receipts=tuple(p.completion.daily_registration.receipt for p in state.history
            if type(p) is PcWoundCompletionProof and p.completion.daily_registration is not None
            and p.completion.source_request.roll.source_request.target_id==row.actor_id)
        if row.daily_wounds.receipts!=receipts or row.daily_wounds.closed_by_infection_id is not None:
            raise ValueError('Champion daily Wounds must retain every actual combat registration')
        npc_champion_body(state,row.actor_id)


def npc_champion_pending_owner(state):
    actor=state.pending_actor_id
    if not is_npc_champion(state,actor): return None
    if state.pending_wound is not None:
        return actor if state.pending_wound.source_request.target_id==actor else None
    return actor if state.pending else None


def complete_npc_champion_equipment_proof(state,proof):
    from towr.domain.pc_melee_result_models import PcBodyConsequenceProof,PcHandDropProof
    if type(proof) not in (PcBodyConsequenceProof,PcHandDropProof): return proof
    if not is_npc_champion(state,state.pending_actor_id):
        if proof.npc_shield_drop is not None: raise ValueError('a PC cannot attach an NPC Champion Shield loss')
        return proof
    body=npc_champion_body(state,state.pending_actor_id)
    from towr.domain._pc_heavy_wound_projection import body_consequence
    argument=PcBodyConsequenceProof(proof.source,proof.die,proof.hand) if type(proof) is PcHandDropProof else proof
    changed=body_consequence(body,argument)
    receipt=None
    if body.shield is not None and changed.shield is not None and changed.shield.location is PcShieldLocation.DROPPED:
        from towr.domain.pc_npc_shield_models import NpcShieldLocation,_drop_position,_add_marker
        previous=next(s for s in state.npc_shields if s.actor_id==body.actor_id)
        dropped=replace(previous,location=NpcShieldLocation.DROPPED,ground=_drop_position(state,body.actor_id))
        receipt=NpcChampionShieldDrop(body.actor_id,proof.source,previous,dropped,state.battlefield,
            _add_marker(state.battlefield,dropped))
    if proof.npc_shield_drop is not None and proof.npc_shield_drop!=receipt:
        raise ValueError('Champion Shield loss changed its actual anatomical source')
    return replace(proof,npc_shield_drop=receipt)


def npc_champion_recover_request(state):
    from towr.domain.recover_models import RecoverActionExecutionRequest,RecoverMode,RecoverStandardChoice,RecoverConditionTarget
    from towr.domain.magic_models import WizardMagicState
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_actor_models import pc_opponent_ids
    actor=state.round_state.active_turn.actor_id
    body=npc_champion_body(state,actor)
    def target(condition):
        return (RecoverConditionTarget(actor,body.injury.conditions,None)
            if body.injury.conditions.has(condition) and not has_ongoing_condition(body.injury,condition) else None)
    from towr.domain.pc_battlefield_models import battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    close=state.source.facts.all_opponents_close if state.battlefield is None else any(
        battlefield_range(state.battlefield,actor,enemy) is RangedWeaponRange.CLOSE for enemy in pc_opponent_ids(state,actor))
    return RecoverActionExecutionRequest(pc_melee_action_id(state,actor)+':champion:recover',state.round_state,
        actor,body.injury.conditions,close,1,RecoverMode.STANDARD,
        RecoverStandardChoice(WizardMagicState(),staggered_target=target(Condition.STAGGERED),prone_target=target(Condition.PRONE)))


def npc_champion_aftermath(state,after,proof):
    """Apply anatomical prices of real NPC action/Test receipts, never advice."""
    from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof,PcNpcHelpProof
    from towr.domain.pc_npc_aim_models import PcNpcAimProof
    from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    from towr.domain.turn_models import CombatActionKind
    from towr.domain.pc_heavy_wound_models import critical_for_action,critical_for_hand
    from towr.domain.pc_weapon_intent_models import weapon_use_hand
    action=hand=None
    request=getattr(proof,'request',None)
    actor=getattr(request,'actor_id',None)
    if type(proof) in (PcAttackProof,PcImmediateStrikeProof):
        actor=proof.request.actor_id; action=CombatActionKind.ATTACK
        hand=weapon_use_hand(proof.weapon_intent.attack_use)
    elif type(proof) in (PcHelpProof,PcNpcHelpProof): action=CombatActionKind.HELP
    elif type(proof) is PcNpcAimProof:
        action=CombatActionKind.AIM
        from towr.domain.pc_aim_source_models import actor_aim_weapon_use
        hand=weapon_use_hand(actor_aim_weapon_use(state,actor))
    elif type(proof) is PcNpcRangedReloadProof:
        action=CombatActionKind.IMPROVISE;hand=PcTwoHandedGrip.BOTH
    if action is None or not is_npc_champion(state,actor): return after
    from towr.domain.pc_medical_models import medical_effective_body
    from towr.domain.pc_heavy_wound_models import merge_effective_critical_consequences
    body=medical_effective_body(after,actor)
    injury=merge_effective_critical_consequences(npc_champion_body(after,actor).injury,
        critical_for_action(body,action,used_hand=hand))
    from towr.domain.pc_oath_models import oath_step_evidence
    from towr.domain.test_models import TestResult
    if any(type(value) is TestResult for value in oath_step_evidence(proof)):
        injury=npc_champion_after_test(after,actor,injury)
    return replace(after,**npc_champion_updates(after,actor,injury=injury))


def project_npc_champion_step(state,proof):
    """The NPC's real Character lifecycle; all PC-only resource fields are null."""
    from towr.domain.pc_melee_result_models import (PcWoundCompletionProof,PcEnduranceProof,
        PcWoundChoiceProof,PcHandDropProof,PcBodyConsequenceProof,PcTurnEndProof,PcIncapacitatedTurnEndProof,
        PcTimedWound,validate_pc_melee_source_types,pc_melee_action_id)
    pending_actor=state.pending_actor_id
    turn=state.round_state.active_turn
    actor=pending_actor if pending_actor is not None else turn.actor_id if turn is not None else None
    if not is_npc_champion(state,actor): return None
    supported=(PcWoundCompletionProof,PcEnduranceProof,PcWoundChoiceProof,PcHandDropProof,PcBodyConsequenceProof)
    own_turn=turn is not None and turn.actor_id==actor
    if type(proof) not in supported and not (own_turn and type(proof) in (PcTurnEndProof,PcIncapacitatedTurnEndProof,PcNpcChampionRecoverProof)):
        return None
    body=npc_champion_body(state,actor)
    combat=state.round_state
    def same(actual,expected):
        if actual!=expected: raise ValueError('Champion consequence changed its actual source/result')
        validate_pc_melee_source_types(actual,expected)
    def finish(body=body,**changes):
        drops=getattr(proof,'tool_drops',())
        if drops: body=replace(body,tool_inventory=drops[-1].after)
        updates=npc_champion_updates(state,actor,body=body,npc_shield_drop=getattr(proof,'npc_shield_drop',None))
        updates.update(changes)
        if not updates.get('pending',state.pending) and updates.get('pending_wound',state.pending_wound) is None:
            updates['pending_actor_id']=None
        return replace(state,history=(*state.history,proof),**updates)
    def validate_no_fate():
        if getattr(proof,'fate_decline',None) is not None or getattr(proof,'glorious',None) is not None:
            raise ValueError('NPC Champion cannot spend, decline or burn PC Fate')
    if type(proof) is PcWoundCompletionProof:
        validate_no_fate()
        from towr.rules.wound_lifecycle_resolution import complete_character_wound_lifecycle
        expected=complete_character_wound_lifecycle(npc_champion_wound_completion(state))
        same(proof.completion,expected)
        injury=expected.state
        new_timed=tuple(PcTimedWound(e,expected.request_id,combat.round_number+int(actor in combat.completed_turn_entity_ids))
            for e in injury.active_wound_effects if type(e) is WoundConditionEffect
            and e.duration is WoundEffectDuration.END_OF_NEXT_TURN and e not in body.injury.active_wound_effects)
        clock=combat
        if injury.dead and (turn is None or turn.actor_id!=actor) and actor not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
            clock=replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,actor))
        more=() if expected.wound_effect is None else expected.wound_effect.follow_ups
        return finish(replace(body,injury=injury,daily_wounds=expected.daily_wounds,
            timed_wounds=(*body.timed_wounds,*new_timed)),pending_wound=None,pending=(*more,*state.pending),round_state=clock)
    if type(proof) is PcEnduranceProof:
        validate_no_fate()
        if state.pending_wound is not None or not state.pending: raise ValueError('Champion Endurance has no pending Wound source')
        same(proof.request,state.pending[0])
        test=npc_champion_test(state,actor,proof.request.test_id,Skill.ENDURANCE)
        same(proof.test_request,test)
        from towr.domain.talent_test_source import validate_completed_talent_test
        validate_completed_talent_test(test,proof.test)
        from towr.rules.wound_effect_resolution import resolve_wound_endurance_test
        result=resolve_wound_endurance_test(proof.request,npc_champion_after_test(state,actor),proof.test)
        same(proof.result,result)
        timed=tuple(PcTimedWound(e,proof.request.test_id,combat.round_number+int(actor in combat.completed_turn_entity_ids))
            for e in result.state.active_wound_effects if type(e) is WoundConditionEffect
            and e.duration is WoundEffectDuration.END_OF_NEXT_TURN and e not in body.injury.active_wound_effects)
        return finish(replace(body,injury=result.state,timed_wounds=(*body.timed_wounds,*timed)),pending=(*result.follow_ups,*state.pending[1:]))
    if type(proof) is PcWoundChoiceProof:
        if state.pending_wound is not None or not state.pending: raise ValueError('Champion wound choice has no pending source')
        from towr.rules.wound_effect_resolution import resolve_wound_choice
        from towr.domain.injury_models import WoundChoice
        from towr.domain._pc_heavy_wound_projection import clutch_candidates
        choice=WoundChoice.DROP_AND_CLUTCH_STOMACH if clutch_candidates(body) else WoundChoice.BECOME_DEFENCELESS
        result=resolve_wound_choice(state.pending[0],body.injury,choice)
        same(proof.result,result)
        return finish(replace(body,injury=result.state),pending=(*result.follow_ups,*state.pending[1:]))
    if type(proof) in (PcHandDropProof,PcBodyConsequenceProof):
        if state.pending_wound is not None or not state.pending: raise ValueError('Champion anatomy has no pending Wound consequence')
        same(proof.source,state.pending[0])
        completed=complete_npc_champion_equipment_proof(state,proof)
        same(proof,completed)
        from towr.domain._pc_heavy_wound_projection import body_consequence
        argument=PcBodyConsequenceProof(proof.source,proof.die,proof.hand) if type(proof) is PcHandDropProof else proof
        changed=body_consequence(body,argument)
        return finish(changed,pending=state.pending[1:])
    if type(proof) is PcNpcChampionRecoverProof:
        if state.pending or state.pending_wound is not None: raise ValueError('Champion Recover skipped a mandatory Wound')
        from towr.domain.pc_melee_result_models import pc_melee_selected_action
        from towr.domain.turn_models import CombatActionKind
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER: raise ValueError('Champion Recover is not its selected action')
        request=npc_champion_recover_request(state)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        result=expected_pc_standard_recover(request)
        from towr.domain.pc_battlefield_movement_models import battlefield_recovered_injury
        from towr.domain.pc_heavy_wound_models import critical_for_action
        injury=battlefield_recovered_injury(body.injury,result)
        injury=critical_for_action(replace(body,injury=injury),CombatActionKind.RECOVER,
            removes_prone=body.injury.conditions.has(Condition.PRONE) and not injury.conditions.has(Condition.PRONE))
        same((proof.request,proof.result,proof.previous_injury,proof.injury),(request,result,body.injury,injury))
        return finish(replace(body,injury=injury),round_state=result.round_state)
    return _project_npc_champion_turn_end(state,proof,body,finish,same)


def _project_npc_champion_turn_end(state,proof,body,finish,same):
    from towr.domain.pc_melee_result_models import PcIncapacitatedTurnEndProof,PcCriticalProof,pc_melee_action_id
    from towr.domain.turn_models import CombatTurnEndResult
    from towr.domain.critical_injury_models import CriticalInjuryTestRequest,CriticalInjuryTestResult
    from towr.domain.talent_test_source import validate_completed_talent_test
    from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
    from towr.domain.pc_duellist_models import build_pc_duellist_second_action
    from towr.domain.pc_rapid_reload_models import build_pc_rapid_reload_second_action
    if any(builder(state) is not None for builder in (build_pc_npc_extra_attack_slot,
            build_pc_duellist_second_action,build_pc_rapid_reload_second_action)):
        raise ValueError('Champion must execute its available second action before TurnEnd')
    combat=state.round_state;turn=combat.active_turn;actor=body.actor_id
    if state.pending or state.pending_wound is not None: raise ValueError('Champion end cannot skip mandatory Wound work')
    incapable=type(proof) is PcIncapacitatedTurnEndProof
    if incapable:
        from towr.domain.pc_broken_battlefield_models import pc_broken_turn_blocked
        defenceless=body.injury.conditions.has(Condition.DEFENCELESS)
        if turn.action_slots or not (defenceless or pc_broken_turn_blocked(state)):
            raise ValueError('actionless Champion end requires actual incapacity')
        rules=('RULE-COMBAT-001:rounds-sides-turns','RULE-HEALTH-008:defenceless-turn' if defenceless else 'RULE-HEALTH-008:broken-blocked-turn')
    else:
        if not turn.action_slots or any(not s.executed for s in turn.action_slots): raise ValueError('Champion end skipped its actual action')
        rules=('RULE-COMBAT-001:rounds-sides-turns',)
    clock=replace(combat,active_turn=None,completed_turn_entity_ids=(*combat.completed_turn_entity_ids,actor))
    action_id=pc_melee_action_id(state,actor)
    same(proof.result,CombatTurnEndResult(action_id+':end',clock,turn,clock.next_side,clock.round_complete,rules))
    if getattr(proof,'fate_decline',None) is not None: raise ValueError('Champion turn end cannot invent Fate')
    injury=body.injury
    if not injury.dead and injury.conditions.has(Condition.CRITICALLY_INJURED):
        critical=proof.critical
        if type(critical) is not PcCriticalProof or critical.fate_decline is not None or critical.glorious is not None:
            raise ValueError('Champion Critical Test has no PC Fate window')
        test=npc_champion_test(state,actor,action_id+':critical:endurance',Skill.ENDURANCE)
        same(critical.test_request,test)
        validate_completed_talent_test(test,critical.result.test)
        source=CriticalInjuryTestRequest(action_id+':critical',actor,npc_champion_after_test(state,actor),test.id)
        expected=CriticalInjuryTestResult(source,critical.result.test,critical.result.state)
        same(critical.result,expected)
        injury=expected.state
    elif proof.critical is not None: raise ValueError('healthy/dead Champion cannot invent a Critical Test')
    expired=tuple(t.effect for t in body.timed_wounds if t.deadline_round==combat.round_number)
    if any(t.deadline_round<combat.round_number for t in body.timed_wounds): raise ValueError('Champion expiry metadata is stale')
    effects=tuple(e for e in injury.active_wound_effects if e not in expired)
    conditions=injury.conditions
    for effect in expired:
        from towr.domain.pc_magic_models import external_magic_conditions
        from towr.domain.pc_inventory_conditions import external_inventory_conditions
        from towr.domain.pc_briarroot_models import external_briarroot_conditions
        if (not any(type(other) is WoundConditionEffect and other.condition is effect.condition for other in effects)
                and effect.condition not in external_magic_conditions(state,actor)|external_inventory_conditions(state,actor)|external_briarroot_conditions(state,actor)):
            conditions=conditions.without_condition(effect.condition)
    return finish(replace(body,injury=replace(injury,conditions=conditions,active_wound_effects=effects),
        timed_wounds=tuple(t for t in body.timed_wounds if t.effect not in expired)),round_state=clock)
