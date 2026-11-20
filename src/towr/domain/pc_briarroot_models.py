"""Source-bound Briarroot Shield reactions and independent binding causes.

GM1.1 VI85; PG1.4 V123. The accepted lifecycle removes these vines when
their weapon is abandoned, their shield leaves, or a Brawn Recover frees one
selected binding. Other Burdened causes remain. No helper rolls combat again.
"""
from __future__ import annotations

from towr.domain.pc_demigryph_models import pc_kernel_attack_types

from dataclasses import dataclass,field,replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.armour_models import ShieldKind,BRIARROOT_RULE_ID
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition
from towr.domain.recover_models import (
    RecoverActionExecutionRequest,RecoverActionExecutionResult,RecoverConditionRemovalChoice,
    RecoverConditionRemovalResult,RecoverConditionTarget,RecoverMode,_expected_recover_execution,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionKind

if TYPE_CHECKING:
    from towr.domain.fate_models import FateGloriousSpendResult
    from towr.domain.pc_melee_result_models import PcAttackProof,PcFateDecline
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof


class BriarrootReleaseReason(str,Enum):
    WEAPON_RELEASED='weapon_released'
    BEARER_LEFT_CLOSE='bearer_left_close'
    SHIELD_RELEASED='shield_released'
    ACTOR_UNAVAILABLE='actor_unavailable'
    NATURAL_SOURCE_DEPARTED='natural_source_departed'


class BriarrootWeaponKind(str,Enum):
    HELD='held'
    NATURAL='natural'
    MOUNT_NATURAL='mount_natural'


def _id(value,label):
    if type(value) is not str or not value.strip():
        raise TypeError(f'{label} requires an exact nonempty identifier')


@dataclass(frozen=True,slots=True)
class PcBriarrootBinding:
    id: str
    bearer_id: str
    attacker_id: str
    weapon_id: str
    attack_id: str
    attack_history_index: int
    kind: BriarrootWeaponKind = field(default=BriarrootWeaponKind.HELD,kw_only=True)

    def __post_init__(self):
        for name in ('id','bearer_id','attacker_id','weapon_id','attack_id'):
            _id(getattr(self,name),name)
        if self.bearer_id == self.attacker_id:
            raise ValueError('Briarroot cannot bind its own shield-bearer')
        if type(self.attack_history_index) is not int or self.attack_history_index < 0:
            raise ValueError('Briarroot requires its actual nonnegative Attack history position')
        if type(self.kind) is not BriarrootWeaponKind:
            raise TypeError('Briarroot weapon source requires its exact typed kind')


def _bank(bank):
    if type(bank) is not tuple or any(type(item) is not PcBriarrootBinding for item in bank):
        raise TypeError('Briarroot bindings require an exact typed tuple')
    for item in bank:
        replace(item)
    if (len({item.id for item in bank}) != len(bank)
            or len({(item.bearer_id,item.attacker_id,item.weapon_id) for item in bank}) != len(bank)):
        raise ValueError('a shield cannot bind the same held weapon twice')


def _successful_defence(proof):
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof,pc_kernel_resolution
    if type(proof) not in pc_kernel_attack_types():
        return False
    protection=proof.protection.source_request
    attack=pc_kernel_resolution(proof).attack
    from towr.domain.attack_models import defender_won_attack_opposition
    return (protection.attack_skill is Skill.MELEE
        and protection.selected_skill is Skill.DEFENCE
        and protection.defender_holds_shield is True
        and attack.outcome is AttackOutcome.MISS
        and attack.defender_test is not None
        and defender_won_attack_opposition(proof.request.kernel_request.attack,attack))


@dataclass(frozen=True,slots=True)
class PcBriarrootProof:
    id: str
    history_index: int
    previous: tuple[PcBriarrootBinding,...]
    bindings: tuple[PcBriarrootBinding,...]
    attack_history_index: int | None = None
    attack: PcAttackProof | PcDemigryphStrikeProof | None = field(default=None,repr=False)
    removed: tuple[tuple[str,BriarrootReleaseReason],...] = ()

    def __post_init__(self):
        _id(self.id,'Briarroot proof')
        if type(self.history_index) is not int or self.history_index < 0:
            raise ValueError('Briarroot proof needs its actual history position')
        _bank(self.previous); _bank(self.bindings)
        if self.previous == self.bindings:
            raise ValueError('Briarroot proof must record an actual binding transition')
        if type(self.removed) is not tuple:
            raise TypeError('Briarroot release reasons require an ordered tuple')
        for item in self.removed:
            if type(item) is not tuple or len(item) != 2:
                raise TypeError('Briarroot release reason requires its binding and exact reason')
            _id(item[0],'released binding')
            if type(item[1]) is not BriarrootReleaseReason:
                raise TypeError('Briarroot release reason must be typed')
        removed=tuple(item for item in self.previous if item not in self.bindings)
        if tuple(item.id for item in removed) != tuple(item[0] for item in self.removed):
            raise ValueError('Briarroot proof must account for each removed binding in source order')
        added=tuple(item for item in self.bindings if item not in self.previous)
        retained=tuple(item for item in self.previous if item not in removed)
        if self.bindings != (*retained,*added):
            raise ValueError('Briarroot cannot reorder retained independent bindings')
        if self.attack is None:
            if added or self.attack_history_index is not None:
                raise ValueError('a new binding requires its actual defended Attack')
        else:
            if (type(self.attack_history_index) is not int
                    or not 0 <= self.attack_history_index < self.history_index
                    or not _successful_defence(self.attack) or len(added) != 1):
                raise ValueError('Briarroot activation requires one actual successful opposed Defence')
            binding,=added
            if (binding.attacker_id,binding.bearer_id,binding.attack_id,binding.attack_history_index) != (
                    self.attack.request.actor_id,self.attack.request.target_id,
                    self.attack.request.id,self.attack_history_index):
                raise ValueError('Briarroot binding changed its actual source Attack')

    @property
    def applied_rule_ids(self):
        return (BRIARROOT_RULE_ID,)


@dataclass(frozen=True,slots=True)
class PcBriarrootReleaseProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    binding_id: str
    previous: tuple[PcBriarrootBinding,...]
    bindings: tuple[PcBriarrootBinding,...]
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None

    def __post_init__(self):
        _id(self.binding_id,'selected Briarroot binding')
        _bank(self.previous); _bank(self.bindings)
        if type(self.request) is not RecoverActionExecutionRequest or type(self.result) is not RecoverActionExecutionResult:
            raise TypeError('Briarroot release requires its exact Recover request and result')
        replace(self.request); replace(self.result)
        binding=next((item for item in self.previous if item.id == self.binding_id),None)
        if (binding is None or self.request.mode is not RecoverMode.REMOVE_CONDITION
                or type(self.request.choice) is not RecoverConditionRemovalChoice
                or self.request.choice.condition is not Condition.BURDENED
                or self.request.choice.test_skill is not Skill.BRAWN
                or self.request.choice.target.entity_id != binding.attacker_id
                or type(self.result.resolution) is not RecoverConditionRemovalResult):
            raise ValueError('Briarroot release must select one actual bound weapon and Brawn Recover')
        expected=tuple(item for item in self.previous if item.id != binding.id) if self.result.resolution.removed else self.previous
        if self.bindings != expected:
            raise ValueError('one successful Brawn Recover releases exactly one selected Briarroot binding')


def _actors(state):
    return (*state.source.pc_activation_order,*state.source.npc_activation_order,
        *(row.snapshot.state.actor_id for row in state.companions if row.retained_since_round is not None))


def _known(state,actor):
    _id(actor,'Briarroot actor')
    if actor in (*state.source.pc_activation_order, *state.source.npc_activation_order):
        return
    if actor not in _actors(state):
        raise ValueError('Briarroot actor must belong to the complete encounter source')


def _alive(state,actor):
    from towr.domain.injury_models import injury_is_defeated
    injury = _injury(state, actor)
    return not injury_is_defeated(injury) and actor not in state.exited_npc_ids


def _injury(state,actor):
    from towr.domain.pc_actor_models import pc_actor_injury
    return pc_actor_injury(state, actor)


def _close(state,first,second):
    if state.battlefield is None:
        return state.source.facts.all_opponents_close
    from towr.domain.pc_battlefield_models import battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    return battlefield_range(state.battlefield,first,second) is RangedWeaponRange.CLOSE


def _holds_briarroot(state,actor):
    if not _source_briarroot(state,actor):
        return False
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_shield_models import pc_has_working_shield
        return pc_has_working_shield(state.participant(actor))
    return state.enemy(actor).state.holds_shield


def _source_briarroot(state,actor):
    from towr.domain.pc_armour_models import actor_armour
    armour=actor_armour(state,actor)
    return armour is not None and armour.shield is ShieldKind.BRIARROOT


def _held_weapon_id(state,actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_backup_weapon_models import pc_active_weapon_item_id
        member=state.participant(actor)
        if member.weapon_hand is None:
            return None
        if member.weapon_inventory is not None and member.weapon_inventory.active.location.value != 'held':
            return None
        return pc_active_weapon_item_id(state,actor)
    enemy=state.enemy(actor)
    if not enemy.state.wields_weapon:
        return None
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    profile=pc_selected_npc_attack_profile(state,actor)
    if profile.hands is None:
        return None
    if enemy.state.weapon_inventory is not None:
        selected=enemy.state.weapon_inventory.active
        return None if selected is None else selected.id
    return actor+':weapon:'+profile.id


def _release_reason(state,binding):
    if not _alive(state,binding.attacker_id) or not _alive(state,binding.bearer_id):
        return BriarrootReleaseReason.ACTOR_UNAVAILABLE
    if _weapon_released(state,binding):
        return (BriarrootReleaseReason.NATURAL_SOURCE_DEPARTED
            if binding.kind is BriarrootWeaponKind.MOUNT_NATURAL else BriarrootReleaseReason.WEAPON_RELEASED)
    if not _holds_briarroot(state,binding.bearer_id):
        return BriarrootReleaseReason.SHIELD_RELEASED
    if not _close(state,binding.attacker_id,binding.bearer_id):
        return BriarrootReleaseReason.BEARER_LEFT_CLOSE
    return None


def _weapon_released(state,binding):
    if binding.kind is BriarrootWeaponKind.NATURAL:
        return False
    if binding.kind is BriarrootWeaponKind.MOUNT_NATURAL:
        from towr.domain.pc_mount_models import pc_is_mounted
        return not pc_is_mounted(state,binding.attacker_id)
    actor=binding.attacker_id
    inventory=(state.participant(actor).weapon_inventory if actor in state.source.pc_activation_order
        else state.enemy(actor).state.weapon_inventory)
    if inventory is not None:
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        item=next((item for item in inventory.items if item.id==binding.weapon_id),None)
        if item is None:
            raise ValueError('Briarroot lost its actual weapon instance')
        if item.location is WeaponItemLocation.DROPPED:return True
        if item.location is not WeaponItemLocation.HELD:
            raise ValueError('a Briarroot-bound weapon cannot be stowed/deployed without actual release or drop')
        return False
    held=_held_weapon_id(state,actor)
    if held is None:
        # Legacy one-weapon owners and generated NPCs have no stow transition;
        # their source-bound hand-loss/weapon-drop owners clear this held fact.
        return True
    if held!=binding.weapon_id:
        raise ValueError('a Briarroot-bound weapon cannot disappear through an implicit weapon swap')
    return False


def _attack_weapon(state,proof):
    use=proof.weapon_intent.attack_use
    if use is not None and use.primary_item_id is not None:
        return use.primary_item_id,BriarrootWeaponKind.HELD
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    actor=proof.request.actor_id
    if type(proof) is PcDemigryphStrikeProof:
        return proof.request.weapon_instance_id,BriarrootWeaponKind.MOUNT_NATURAL
    if proof.mount_attack is not None:
        from towr.domain.pc_mount_attack_models import PcMountedAttackMode
        if proof.mount_attack.mode is PcMountedAttackMode.MOUNT:
            return proof.mount_attack.weapon_instance_id,BriarrootWeaponKind.MOUNT_NATURAL
    if actor in state.source.npc_activation_order:
        from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
        profile=pc_selected_npc_attack_profile(state,actor)
        if profile.hands is None:
            return actor+':natural:'+profile.id,BriarrootWeaponKind.NATURAL
    return _held_weapon_id(state,actor),BriarrootWeaponKind.HELD


def _binding_has_source(state,binding,proof):
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    if type(proof) is PcDemigryphStrikeProof:
        return (binding.kind is BriarrootWeaponKind.MOUNT_NATURAL
            and binding.weapon_id==proof.request.weapon_instance_id)
    if proof.mount_attack is not None:
        from towr.domain.pc_mount_attack_models import PcMountedAttackMode
        if proof.mount_attack.mode is PcMountedAttackMode.MOUNT:
            return (binding.kind is BriarrootWeaponKind.MOUNT_NATURAL
                and binding.weapon_id==proof.mount_attack.weapon_instance_id)
    actor=binding.attacker_id
    if actor in state.source.pc_activation_order:
        source=state.source.participant(actor)
        from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
        identifiers=tuple(item.id for item in initial_pc_weapon_inventory(source).items)
        return binding.kind is BriarrootWeaponKind.HELD and binding.weapon_id in identifiers
    source=next(enemy for enemy in state.source.npc_sources if enemy.state.actor_id==actor)
    if binding.kind is BriarrootWeaponKind.HELD:
        inventory=state.enemy(actor).state.weapon_inventory
        identifiers=(tuple(item.id for item in inventory.items) if inventory is not None else
            tuple(actor+':weapon:'+profile.id for profile in source.definition.attacks if profile.hands is not None))
        return binding.weapon_id in identifiers
    if binding.kind is BriarrootWeaponKind.NATURAL:
        return binding.weapon_id in tuple(actor+':natural:'+profile.id for profile in source.definition.attacks
            if profile.hands is None and profile.skill is Skill.MELEE)
    return False


def _current_attack(state):
    """Only an unconsumed Attack in this actual action can create a reaction."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof
    turn=state.round_state.active_turn
    if turn is None or not turn.action_slots:
        return None,None
    consumed={proof.attack_history_index for proof in state.history
        if type(proof) is PcBriarrootProof and proof.attack is not None}
    for index in range(len(state.history)-1,-1,-1):
        proof=state.history[index]
        if type(proof) not in pc_kernel_attack_types():
            continue
        if (index in consumed or proof.request.actor_id != turn.actor_id
                or proof.request.slot_index != len(turn.action_slots)):
            return None,None
        return index,proof
    return None,None


def expected_briarroot_update(state):
    previous=state.briarroot_bindings
    _bank(previous)
    if not previous and not any(_source_briarroot(state,actor) for actor in _actors(state)):
        return None
    removals=tuple((binding.id,reason) for binding in previous
        if (reason:=_release_reason(state,binding)) is not None)
    removed={binding_id for binding_id,_ in removals}
    bindings=tuple(binding for binding in previous if binding.id not in removed)
    index,attack=_current_attack(state)
    witness=None
    if attack is not None and _successful_defence(attack):
        actor,bearer=attack.request.actor_id,attack.request.target_id
        weapon,kind=_attack_weapon(state,attack)
        if (weapon is not None and _alive(state,actor) and _alive(state,bearer)
                and _holds_briarroot(state,bearer) and _close(state,actor,bearer)
                and not any((binding.bearer_id,binding.attacker_id,binding.weapon_id)==(bearer,actor,weapon)
                    for binding in bindings)):
            binding=PcBriarrootBinding(state.source.id+':briarroot:attack:'+str(index),
                bearer,actor,weapon,attack.request.id,index,kind=kind)
            bindings=(*bindings,binding)
            witness=attack
    if bindings == previous:
        return None
    history_index=len(state.history)
    return PcBriarrootProof(state.source.id+':briarroot:'+str(history_index),history_index,
        previous,bindings,index if witness is not None else None,witness,removals)


def external_briarroot_conditions(state,actor,*,bank=None):
    _known(state,actor)
    bank=state.briarroot_bindings if bank is None else bank
    _bank(bank)
    return frozenset((Condition.BURDENED,)) if any(binding.attacker_id==actor for binding in bank) else frozenset()


def bound_weapon_ids(state,actor):
    _known(state,actor)
    return tuple(dict.fromkeys(binding.weapon_id for binding in state.briarroot_bindings
        if binding.attacker_id==actor))


def can_leave_close_with_weapon(state,actor,bearer):
    _known(state,actor); _known(state,bearer)
    return not any(binding.attacker_id==actor and binding.bearer_id==bearer
        and not _weapon_released(state,binding) for binding in state.briarroot_bindings)


def briarroot_allows_give_ground(state,actor):
    """A repeated Stagger cannot offer escape while any actual weapon is caught."""
    _known(state,actor)
    return all(can_leave_close_with_weapon(state,actor,binding.bearer_id)
        for binding in state.briarroot_bindings if binding.attacker_id==actor)


def briarroot_movement_keeps_close(state,actor,after_battlefield):
    """Check an actual proposed placement without manufacturing a trial state.

    The shield-bearer may move away. The bound attacker keeps each tether until
    a genuine release/drop, including when the caught weapon is natural.
    """
    _known(state,actor)
    from towr.domain.pc_battlefield_models import PcBattlefieldState,battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    if type(after_battlefield) is not PcBattlefieldState:
        raise TypeError('Briarroot movement requires the exact proposed battlefield')
    return all(_weapon_released(state,binding)
        or battlefield_range(after_battlefield,actor,binding.bearer_id) is RangedWeaponRange.CLOSE
        for binding in state.briarroot_bindings if binding.attacker_id==actor)


def _independent_burden(state,actor):
    from towr.domain.pc_armour_models import external_armour_conditions
    from towr.domain.pc_inventory_conditions import external_inventory_conditions
    from towr.domain.pc_magic_models import external_magic_conditions
    from towr.domain.pc_weighted_net_models import weighted_net_condition_sources
    if (Condition.BURDENED in (external_armour_conditions(state,actor) | external_inventory_conditions(state,actor))
            or Condition.BURDENED in external_magic_conditions(state,actor)
            or weighted_net_condition_sources(state,actor)):
        return True
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        return has_ongoing_condition(_injury(state,actor),Condition.BURDENED)
    source=next(enemy for enemy in state.source.npc_sources if enemy.state.actor_id==actor)
    return source.definition.generated_components is None and source.state.injury.conditions.has(Condition.BURDENED)


def _burden_injury(state,actor,bank,injury=None):
    injury=_injury(state,actor) if injury is None else injury
    active=Condition.BURDENED in external_briarroot_conditions(state,actor,bank=bank)
    conditions=(injury.conditions.with_condition(Condition.BURDENED)
        if active or _independent_burden(state,actor) else injury.conditions.without_condition(Condition.BURDENED))
    return replace(injury,conditions=conditions)


def _bank_updates(state,bank,actors):
    injuries={actor:_burden_injury(state,actor,bank) for actor in actors}
    return dict(briarroot_bindings=bank,
        party=tuple(replace(member,injury=injuries[member.actor_id]) if member.actor_id in injuries
            else member for member in state.party),
        enemies=tuple(replace(enemy,state=replace(enemy.state,injury=injuries[enemy.state.actor_id]))
            if enemy.state.actor_id in injuries else enemy for enemy in state.enemies))


def apply_briarroot_update(state,proof):
    if type(proof) is not PcBriarrootProof:
        raise TypeError('Briarroot update requires its exact typed receipt')
    replace(proof)
    expected=expected_briarroot_update(state)
    if expected is None or proof != expected:
        raise ValueError('Briarroot update differs from the actual source/equipment/history prefix')
    actors={binding.attacker_id for binding in (*proof.previous,*proof.bindings)}
    return _bank_updates(state,proof.bindings,actors)


def build_briarroot_release(state,binding_id):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_weighted_net_models import _recover_actor,_brawn_test,_has_close_enemy
    actor,slot=_recover_actor(state)
    binding=next((item for item in state.briarroot_bindings if item.id==binding_id),None)
    if binding is None:
        raise ValueError('Briarroot release requires one actual binding')
    target=binding.attacker_id
    allied=(actor in state.source.pc_activation_order)==(target in state.source.pc_activation_order)
    if not allied or actor!=target and not _close(state,actor,target):
        raise ValueError('Briarroot Recover must free self or an actual Close ally')
    action=pc_melee_action_id(state,actor)+':briarroot:release:'+binding_id
    choice=RecoverConditionRemovalChoice(RecoverConditionTarget(target,_injury(state,target).conditions,
        None if actor==target else True),Condition.BURDENED,_brawn_test(state,actor,action+':brawn'),Skill.BRAWN,True)
    return RecoverActionExecutionRequest(action,state.round_state,actor,_injury(state,actor).conditions,
        _has_close_enemy(state,actor),slot,RecoverMode.REMOVE_CONDITION,choice)


def briarroot_recovery_options(state,actor):
    """Available source-bound targets before reserving an alternative Recover."""
    _known(state,actor)
    if (not _alive(state,actor) or _injury(state,actor).conditions.has(Condition.DEFENCELESS)):
        return ()
    if actor in state.source.pc_activation_order:
        if state.source.participant(actor).pc.brawn is None:
            return ()
    else:
        components=state.enemy(actor).definition.generated_components
        if components is None or components.brawn is None:
            return ()
    allied=lambda target:(actor in state.source.pc_activation_order)==(target in state.source.pc_activation_order)
    return tuple(binding.id for binding in state.briarroot_bindings
        if allied(binding.attacker_id) and (actor==binding.attacker_id or _close(state,actor,binding.attacker_id)))


def apply_briarroot_release(state,proof):
    from towr.domain.pc_melee_result_models import pc_after_test,_test_result
    from towr.domain.pc_heavy_wound_models import critical_for_action
    from towr.domain.pc_fate_test_models import validate_pc_test_fate
    from towr.rules.recover_resolution import _complete_condition_removal_after_test
    if type(proof) is not PcBriarrootReleaseProof:
        raise TypeError('Briarroot Recover requires its exact typed receipt')
    replace(proof)
    request=build_briarroot_release(state,proof.binding_id)
    if proof.request!=request or proof.previous!=state.briarroot_bindings:
        raise ValueError('Briarroot Recover changed its source request/bank')
    actor=request.actor_id
    actual=proof.result.resolution.test_result
    fate=None
    if actor in state.source.pc_activation_order:
        test,fate=validate_pc_test_fate(state,actor,Skill.BRAWN,request.choice.test,actual,
            proof.fate_decline,proof.glorious)
    else:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC Briarroot Recover cannot invent PC Fate')
        _test_result(request.choice.test,actual)
        test=request.choice.test
    choice=replace(request.choice,test=test)
    expected=_expected_recover_execution(replace(request,choice=choice),
        _complete_condition_removal_after_test(choice,actual))
    if proof.result!=expected:
        raise ValueError('Briarroot Recover differs from its actual completed Brawn Test')
    target=request.choice.target.entity_id
    updates=_bank_updates(state,proof.bindings,{target})
    updates['round_state']=expected.round_state
    if actor in state.source.pc_activation_order:
        member=next(member for member in updates['party'] if member.actor_id==actor)
        injury=critical_for_action(member,CombatActionKind.RECOVER)
        injury=pc_after_test(state,actor,injury)
        updates['party']=tuple(replace(member,injury=injury,fate=member.fate if fate is None else fate)
            if member.actor_id==actor else member for member in updates['party'])
    return updates


def validate_briarroot_bindings(state):
    """Fold actual receipts, without rerunning the battle or its choices."""
    _bank(state.briarroot_bindings)
    bank=()
    consumed=set()
    for index,proof in enumerate(state.history):
        if type(proof) is PcBriarrootReleaseProof:
            replace(proof)
            if proof.previous!=bank:
                raise ValueError('Briarroot Recover lost its actual binding prefix')
            bank=proof.bindings
        elif type(proof) is PcBriarrootProof:
            replace(proof)
            if (proof.history_index!=index or proof.id!=state.source.id+':briarroot:'+str(index)
                    or proof.previous!=bank):
                raise ValueError('Briarroot receipt lost its exact source/history prefix')
            if proof.attack is not None:
                origin=proof.attack_history_index
                if origin in consumed or state.history[origin]!=proof.attack:
                    raise ValueError('Briarroot reaction must preserve its one actual defended Attack')
                if not _source_briarroot(state,proof.attack.request.target_id):
                    raise ValueError('Briarroot reaction requires the actual shield item in its complete source')
                added=next(binding for binding in proof.bindings if binding not in proof.previous)
                if not _binding_has_source(state,added,proof.attack):
                    raise ValueError('Briarroot binding changed its actual held/natural weapon source')
                consumed.add(origin)
            bank=proof.bindings
        for binding in bank:
            _known(state,binding.attacker_id); _known(state,binding.bearer_id)
            if binding.id!=state.source.id+':briarroot:attack:'+str(binding.attack_history_index):
                raise ValueError('Briarroot binding changed its actual source identifier')
    if state.briarroot_bindings!=bank:
        raise ValueError('Briarroot bank differs from its complete receipt history')
    for binding in bank:
        if not _injury(state,binding.attacker_id).conditions.has(Condition.BURDENED):
            raise ValueError('an active Briarroot source cannot lose its Burdened flag')
