"""Battle-owned facts and effects of GM82–84 Magic Weapons.

An implement's name never supplies an invented duel, unused charge or action.
The Attack intent freezes the actual context before prices and dice.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.weapon_catalog import MAGIC_WEAPON_KINDS, WeaponKind
from towr.domain.weapon_quality_preparation import (
    WeaponAttackQualityContext, prepare_weapon_attack_quality,
)
from towr.domain.weapon_magic_lifecycle import WeaponMagicAttackTransition,WeaponScarabWoundCharge
from towr.domain.weapon_resource_models import WeaponShotResourceTransition

if TYPE_CHECKING:
    from towr.domain.pc_battlefield_models import PcBattlefieldState
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootDroppedWeapon


def actor_inventory(state, actor):
    if actor in state.source.pc_activation_order:
        return state.participant(actor).weapon_inventory
    if actor in state.source.npc_activation_order:
        return state.enemy(actor).state.weapon_inventory
    from towr.domain.pc_actor_models import pc_actor_inventory
    return pc_actor_inventory(state, actor)


def actor_injury(state, actor):
    if actor in state.source.pc_activation_order:
        return state.participant(actor).injury
    if actor in state.source.npc_activation_order:
        return state.enemy(actor).state.injury
    from towr.domain.pc_actor_models import pc_actor_injury
    return pc_actor_injury(state, actor)


def magic_contributor_value(state,use,target):
    """Small deterministic advice for optional real secondary implements."""
    kinds={use.inventory.item(item).kind for item in use.item_ids}
    value=0.0
    scarabs=sum(use.inventory.item(item).kind is WeaponKind.SCARAB_KNIFE for item in use.item_ids)
    value+=.05*scarabs
    if scarabs and not actor_injury(state,target).conditions.has(Condition.DRAINED):
        value+=.35
    if WeaponKind.SWORD_OF_JUSTICE in kinds and target in state.source.pc_activation_order:
        value+=.1
    inventory=actor_inventory(state,target)
    if WeaponKind.MORNING_STAR_OF_FRACASSE in kinds and inventory is not None:
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        if any(item.kind in MAGIC_WEAPON_KINDS and item.location is WeaponItemLocation.HELD
                for item in inventory.items):
            value+=.2
    return value


def single_combat_active(state, actor, target):
    from towr.domain.pc_single_combat_models import single_combat_active as observe
    return observe(state,actor,target)


def magic_weapon_intent_facts(state, actor, target, use):
    if use is None or not any(use.inventory.item(item).kind in MAGIC_WEAPON_KINDS
            for item in use.item_ids):
        return None, False
    injury, victim = actor_injury(state, actor), actor_injury(state, target)
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    from towr.domain.resolution_models import TargetInjuryPolicy
    target_is_pc_or_champion = (target in state.source.pc_activation_order
        or pc_actor_npc_snapshot(state,target).definition.injury_policy is TargetInjuryPolicy.CHAMPION)
    turn = state.round_state.active_turn
    action_index = None
    if use.kind is WeaponKind.DUELLIST_BLADES and turn is not None:
        # The plan is fixed before the first Test. Its second slot is proved by
        # the separate ability owner, never by this quality modifier.
        from towr.domain.pc_duellist_models import duellist_action_index
        action_index = duellist_action_index(state, use)
    context = WeaponAttackQualityContext(
        target_visible=_weapon_target_visible(state,actor,target,use.skill),
        target_prone=victim.conditions.has(Condition.PRONE),
        target_given_ground_this_round=(state.battlefield is not None
            and target in state.battlefield.spatial.gave_ground_entity_ids),
        single_combat=single_combat_active(state, actor, target),
        target_is_pc_or_champion=target_is_pc_or_champion,
        drained=injury.conditions.has(Condition.DRAINED),
        headsman_execution=(any(use.inventory.item(item).kind is WeaponKind.HEADSMANS_AXE
            for item in use.item_ids) and victim.conditions.has(Condition.PRONE)),
        duellist_action_index=action_index,
    )
    return context, (use.kind is WeaponKind.DRAGON_BOW
        and not use.primary.dragon_arrow_used and not victim.conditions.has(Condition.ABLAZE))


def _weapon_target_visible(state,actor,target,skill):
    from towr.domain.pc_scene_feature_models import scene_attack_visibility
    return scene_attack_visibility(state,actor,target,skill).visible


def magic_weapon_attack_test(intent, test):
    if intent.magic_context is None:
        return test
    return prepare_weapon_attack_quality(intent.attack_use,test,intent.magic_context).test


def condition_dragon_ranged_attack(state, actor, request):
    """Dragon's printed exception also follows K1's final range/Aim modifiers."""
    inventory = actor_inventory(state,actor)
    if inventory is None or inventory.active is None or inventory.active.kind is not WeaponKind.DRAGON_BOW:
        return request
    from towr.domain.test_models import TestQuality
    kernel = request.kernel_request
    test = kernel.attack.attacker_test
    test = replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers if m.amount > 0),
        quality_modifiers=tuple(m for m in test.quality_modifiers if m.quality is not TestQuality.GRIM))
    return replace(request,kernel_request=replace(kernel,attack=replace(kernel.attack,attacker_test=test)))


@dataclass(frozen=True, slots=True)
class PcMagicWeaponAttackReceipt:
    action_id: str
    actor_id: str
    target_id: str
    transition: WeaponMagicAttackTransition
    shot: WeaponShotResourceTransition | None
    scarab_charge: WeaponScarabWoundCharge | None
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None
    drops: tuple[tuple[PcBriarrootDroppedWeapon | None,PcBriarrootDroppedWeapon],...]

    @property
    def after_inventory(self):
        if self.scarab_charge is not None:
            return self.scarab_charge.after_inventory
        if self.shot is not None:
            return self.shot.after_inventory
        return self.transition.actor_inventory


def prepare_magic_weapon_attack(state,request,execution,intent):
    use=intent.attack_use
    if intent.magic_context is None:
        return None
    from towr.domain.weapon_magic_lifecycle import prepare_weapon_magic_attack,prepare_scarab_wound_charge
    from towr.domain.attack_models import AttackOutcome
    from towr.domain.weapon_inventory_models import WeaponItemLocation
    target_inventory=actor_inventory(state,intent.target_id)
    disarmed=None
    if (any(use.inventory.item(item).kind is WeaponKind.MORNING_STAR_OF_FRACASSE for item in use.item_ids)
            and execution.resolution.attack.outcome is AttackOutcome.HIT and target_inventory is not None):
        eligible=[item for item in target_inventory.items
            if item.location is WeaponItemLocation.HELD and item.kind in MAGIC_WEAPON_KINDS]
        # Threat order is explicit and deterministic, without another Test.
        from towr.domain.weapon_catalog import weapon_profile
        disarmed=next((item.id for item in sorted(eligible,key=lambda item:(
            -(weapon_profile(item.kind).damage_value or 0),item.id))),None)
    transition=prepare_weapon_magic_attack(use,execution.resolution.attack.outcome,
        higher_ground=intent.magic_context.effective_higher_ground,target_inventory=target_inventory,
        disarmed_item_id=disarmed)
    shot=None
    if intent.dragon_fire:
        from towr.domain.weapon_resource_models import prepare_weapon_shot_resources
        shot=prepare_weapon_shot_resources(use,dragon_fire=True)
    following=transition.actor_inventory if shot is None else shot.after_inventory
    charge=None
    if (any(use.inventory.item(item).kind is WeaponKind.SCARAB_KNIFE for item in use.item_ids)
            and execution.resolution.profile_wound is not None):
        from towr.domain.injury_models import ProfileWoundRequest,ProfileNpcType,ProfileDecapitationCause
        from towr.domain.pc_actor_models import pc_actor_npc_snapshot
        from towr.domain.pc_hit_condition_models import pc_pre_stagger_target
        injury,_=pc_pre_stagger_target(request.kernel_request,execution.resolution.attack.outcome)
        source=ProfileWoundRequest(request.kernel_request.id+':wound',
            ProfileNpcType(pc_actor_npc_snapshot(state,intent.target_id).definition.injury_policy.value),injury,
            additional_wounds=request.kernel_request.additional_profile_wounds,
            negation_options=request.kernel_request.wound_negation_options,
            decapitation_cause=(ProfileDecapitationCause(request.kernel_request.id+':wound',intent.target_id)
                if request.kernel_request.fixed_character_wound is not None else None))
        charge=prepare_scarab_wound_charge(use,following,execution.resolution.profile_wound,profile_request=source)
    from towr.domain.pc_briarroot_weapon_models import _bank,_ground,_add_marker,PcBriarrootDroppedWeapon
    drops=[]
    battlefield=state.battlefield
    for actor,before,after in ((intent.actor_id,use.inventory,transition.actor_inventory),
            (intent.target_id,target_inventory,transition.after_target_inventory)):
        if before is None or after is None:
            continue
        for old,item in zip(before.items,after.items,strict=True):
            if old.location is not WeaponItemLocation.HELD or item.location not in (
                    WeaponItemLocation.DROPPED,WeaponItemLocation.STUCK):
                continue
            previous=next((row for row in _bank(state) if (row.owner_id,row.weapon_id)==(actor,item.id)),None)
            dropped=PcBriarrootDroppedWeapon(actor,item.id,_ground(state,actor),
                () if actor in state.source.pc_activation_order else state.enemy(actor).state.available_attack_ids)
            battlefield=_add_marker(battlefield,dropped)
            drops.append((previous,dropped))
    return PcMagicWeaponAttackReceipt(request.id,intent.actor_id,intent.target_id,transition,
        shot,charge,state.battlefield,battlefield,tuple(drops))


def magic_weapon_attack_updates(state,request,execution,intent,receipt,updates):
    expected=prepare_magic_weapon_attack(state,request,execution,intent)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if receipt!=expected:
        raise ValueError('Magic Weapon consequence lost its real Attack/item/finite resource source')
    validate_pc_melee_source_types(receipt,expected)
    if expected is None:
        return updates
    updates=replace_actor_inventory(state,intent.actor_id,expected.after_inventory,updates)
    if expected.transition.after_target_inventory is not None:
        updates=replace_actor_inventory(state,intent.target_id,expected.transition.after_target_inventory,updates)
    if expected.drops:
        from towr.domain.pc_briarroot_weapon_models import _bank,_set_item
        bank=_bank(state)
        for previous,item in expected.drops:
            bank=_set_item(bank,item)
        updates.update(briarroot_dropped_weapons=bank,battlefield=expected.state)
    return updates


def replace_actor_inventory(state,actor,inventory,updates):
    updates=dict(updates)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_weapon_inventory import replace_pc_member
        updates['party']=tuple(replace_pc_member(member,weapon_inventory=inventory)
            if member.actor_id==actor else member for member in updates.get('party',state.party))
    else:
        from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        updates['enemies']=tuple(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,
            wields_weapon=any(item.location is WeaponItemLocation.HELD for item in inventory.items),
            holds_shield=inventory.shield_hand is not None,
            available_attack_ids=npc_inventory_attack_ids(enemy.definition,inventory)))
            if enemy.state.actor_id==actor else enemy for enemy in updates.get('enemies',state.enemies))
    return updates


@dataclass(frozen=True,slots=True)
class PcScarabChargeProof:
    action_id: str
    actor_id: str
    transition: WeaponScarabWoundCharge


def expected_scarab_charge(state):
    from towr.domain.pc_melee_result_models import PcAttackProof,PcWoundCompletionProof
    from towr.domain.weapon_magic_lifecycle import prepare_scarab_wound_charge
    spent={proof.action_id for proof in state.history if type(proof) is PcScarabChargeProof}
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    for attack in state.history:
        if type(attack) not in (PcAttackProof,PcImmediateStrikeProof) or attack.request.id in spent:
            continue
        use=attack.weapon_intent.attack_use
        if use is None or not any(use.inventory.item(item).kind is WeaponKind.SCARAB_KNIFE for item in use.item_ids):
            continue
        pending=attack.execution.resolution.pending_character_wound
        if pending is None:
            continue
        completion=next((proof.completion for proof in state.history
            if type(proof) is PcWoundCompletionProof
            and proof.completion.source_request.roll==pending),None)
        if completion is None:
            continue
        actor=attack.request.actor_id
        transition=prepare_scarab_wound_charge(use,actor_inventory(state,actor),completion)
        return PcScarabChargeProof(attack.request.id,actor,transition)
    return None


def project_scarab_charge(state,proof):
    expected=expected_scarab_charge(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if expected is None or proof!=expected:
        raise ValueError('Scarab charge lacks its actual accepted/cancelled Wound continuation')
    validate_pc_melee_source_types(proof,expected)
    return replace_actor_inventory(state,proof.actor_id,proof.transition.after_inventory,{})


def magic_resource_history_step(inventory,proof,actor):
    """Re-admit charges/Dragon use without treating location as a second bank."""
    receipt=getattr(proof,'magic_weapon',None)
    before=after=None
    if receipt is not None and receipt.actor_id==actor:
        before,after=receipt.transition.use.inventory,receipt.after_inventory
    elif type(proof) is PcScarabChargeProof and proof.actor_id==actor:
        before,after=proof.transition.previous_inventory,proof.transition.after_inventory
    else:
        from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
        if type(proof) is PcScarabHealingProof and proof.request.actor_id==actor:
            before,after=proof.resources.use.inventory,proof.resources.after_inventory
    if before is None:
        return inventory
    for expected,previous,current in zip(inventory.items,before.items,after.items,strict=True):
        if (expected.id,expected.source,expected.charges,expected.dragon_arrow_used)!=(
                previous.id,previous.source,previous.charges,previous.dragon_arrow_used):
            raise ValueError('Magic Weapon resource receipt is detached from its real prefix')
        inventory=inventory.with_item(replace(expected,charges=current.charges,
            dragon_arrow_used=current.dragon_arrow_used))
    return inventory


def pc_profile_wound_decision(state,attack):
    from towr.domain.injury_models import ProfileDecapitationCause
    from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
    from towr.domain.pc_demigryph_models import pc_kernel_resolution
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot,pc_actor_side
    target=attack.request.target_id
    pc_actor_npc_snapshot(state,target)
    pc_actor_side(state,attack.request.actor_id)
    result=pc_kernel_resolution(attack)
    cause=getattr(result.target_state,'defeat_cause',None)
    if type(cause) is ProfileDecapitationCause:
        replace(cause)
        if (cause.target_id!=target or cause.source_id!=attack.request.kernel_request.id+':wound'
                or attack.request.kernel_request.fixed_character_wound is None
                or result.profile_wound is None or result.profile_wound.state.defeat_cause!=cause):
            raise ValueError('mandatory NPC Decapitation lacks its actual fixed-Wound Attack source')
        return MinionDefeatDecision(attack.request.actor_id,target,
            NpcDefeatDisposition.KILLED,True)
    if target not in state.source.npc_activation_order:
        return None
    if attack.request.actor_id in state.source.npc_activation_order:
        decision=next((row for row in state.source.npc_defeat_decisions
            if row.attacker_id==attack.request.actor_id and row.target_id==target),None)
        if decision is None:raise ValueError('NPC defeat requires its explicit source GM disposition')
        return decision
    return state.source.participant(attack.request.actor_id).defeat_decision(target)


def pc_hammer_retrieval_selected(state):
    from towr.domain.pc_hammer_recover_models import hammer_retrieval_option
    turn=state.round_state.active_turn
    if turn is None:
        return False
    actor=turn.actor_id
    item=hammer_retrieval_option(state,actor)
    if item is None:
        return False
    if actor not in state.source.pc_activation_order:
        return True
    from towr.domain.pc_melee_models import PcMeleePolicy
    if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
        return True
    from towr.domain.pc_tactical_models import select_pc_tactic
    return select_pc_tactic(state).hammer_item_id==item
