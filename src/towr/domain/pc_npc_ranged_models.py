"""Source-bound NPC ranged weapons and real Exacting actions inside the PC owner."""
from __future__ import annotations

from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import DamageImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.pc_npc_ranged_source_models import (
    PC_NPC_RANGED_DEFINITION_IDS, pc_npc_ranged_profile,
)
from towr.domain.npc_roster_models import NpcParticipantSnapshot
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest, ReloadableRangedAttackExecutionResult, _spent_weapon_state,
    RangedWeaponAttackExecutionResult,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest, RangedWeaponAttackPreparationResult,
    _applied_rule_ids, _execution_for, _profile_prepared_attack, _aim_follow_up_for, _within_optimum,
    OUTSIDE_OPTIMUM_RANGE_RULE_ID,SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
    ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID,BLUNDERBUSS_NEARBY_STAGGER_RULE_ID,WOUNDS_TABLE_BONUS_RULE_ID,
)
from towr.domain.ranged_weapon_profiles import (RangedWeaponId,RangedWeaponRange, RangedWeaponHands,ranged_weapon_combat_profile,
    ranged_weapon_reload_profile,RangedReloadTrigger,REPEATER_SHOOTING_BONUS_RULE_ID)
from towr.domain.reload_models import (
    FreeReloadWeaponState, RangedWeaponReloadState, ReloadableWeaponState,
    ReloadActionExecutionRequest, ReloadActionExecutionResult,
    create_initial_ranged_weapon_reload_state, reload_approach_id,ranged_weapon_is_loaded,
)
from towr.domain.test_models import DiceModifier, Skill, TestRequest
from towr.domain.pc_short_opening_models import pc_enemy_range,pc_has_close_enemy
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation, WeaponItemSource, WeaponUnitState,
    initial_weapon_inventory, weapon_reload_cycle_id, weapon_reload_target, weapon_unit_id,
)

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


@dataclass(frozen=True, slots=True)
class PcNpcRangedShotProof:
    preparation: RangedWeaponAttackPreparationResult
    execution: ReloadableRangedAttackExecutionResult | RangedWeaponAttackExecutionResult


@dataclass(frozen=True, slots=True)
class PcNpcRangedReloadProof:
    request: ReloadActionExecutionRequest
    result: ReloadActionExecutionResult


def initial_pc_npc_weapon_inventories(source) -> tuple[NpcParticipantSnapshot, ...]:
    """Admit physical items from complete components or canonical Shooting only.

    Opaque authored and natural profiles retain their profile-owned availability;
    numeric Damage and a weapon-like name do not prove a physical item source.
    Every generated item retains its own immutable origin and resource state.
    """
    result = []
    for enemy in source.npc_sources:
        actor = enemy.state.actor_id
        components = enemy.definition.generated_components
        policy = next((value for value in source.npc_ranged_policies if value.actor_id == actor), None)
        if components is not None:
            from towr.domain.generated_npc_models import validate_generated_definition,generated_initial_weapon_inventory
            validate_generated_definition(enemy.definition)
            if components.ranged is not None and policy is None:
                raise ValueError('generated NPC Shooting requires its actual initial resource policy')
            inventory=generated_initial_weapon_inventory(components,actor)
        elif policy is not None or enemy.definition.id in PC_NPC_RANGED_DEFINITION_IDS:
            # This helper checks the entire admitted canonical loadout. It is
            # deliberately not an inferred registry of ordinary NPC weapons.
            ranged = pc_npc_ranged_profile(enemy.definition)
            if policy is None:
                raise ValueError('canonical NPC Shooting requires its actual initial resource policy')
            item=policy.initial_weapon
            if type(item) is not WeaponItemSource or item.kind.value!=ranged.weapon_id.value:
                raise ValueError('canonical firearm requires its complete physical item source')
            inventory=initial_weapon_inventory(actor,(item,),active_item_id=weapon_unit_id(actor,item.id,0),
                shield_hand=WeaponGrip.RIGHT if enemy.state.holds_shield else None)
        else:
            if enemy.state.weapon_inventory is not None:
                raise ValueError('an opaque NPC source cannot claim an inferred weapon inventory')
            result.append(enemy)
            continue
        if enemy.state.weapon_inventory is not None and enemy.state.weapon_inventory != inventory:
            raise ValueError('initial NPC inventory differs from its complete physical source')
        injury=enemy.state.injury
        from towr.domain.weapon_inventory_models import carrying_burden_rule_ids
        if components is not None and carrying_burden_rule_ids(inventory,components.strength):
            injury=replace(injury,conditions=injury.conditions.with_condition(Condition.BURDENED))
        result.append(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,injury=injury)))
    return tuple(result)


def npc_ranged_weapon_from_unit(item: WeaponUnitState) -> RangedWeaponReloadState | None:
    """A K1 view of one item; free weapons have no duplicate persistent state."""
    if type(item) is not WeaponUnitState:
        raise TypeError('NPC ranged resources require the actual typed physical unit')
    replace(item)
    if weapon_profile(item.kind).group is not WeaponGroup.SHOOTING:
        return None
    if item.reload is not None:
        return item.reload
    weapon = create_initial_ranged_weapon_reload_state(item.id,RangedWeaponId(item.kind.value))
    if type(weapon) is not FreeReloadWeaponState:
        raise ValueError('an Exacting weapon cannot lose its persistent K1 state')
    return weapon


def pc_npc_ranged_weapon(state: PcMeleeState, actor: str,
        item_id: str | None = None) -> RangedWeaponReloadState | None:
    inventory = state.enemy(actor).state.weapon_inventory
    if inventory is None:
        if item_id is not None:
            raise ValueError('NPC has no admitted physical weapon inventory')
        return None
    item = inventory.active if item_id is None else inventory.item(item_id)
    return None if item is None else npc_ranged_weapon_from_unit(item)


def pc_active_npc_ranged_profile(state,actor):
    enemy=state.enemy(actor)
    inventory=enemy.state.weapon_inventory
    item=None if inventory is None else inventory.active
    return pc_npc_ranged_profile(enemy.definition,None if item is None else item.kind)


def npc_ranged_is_loaded(weapon: RangedWeaponReloadState) -> bool:
    """Free-with-Attack bows have no persistent loaded flag or Exacting cycle."""
    return ranged_weapon_is_loaded(weapon)


def npc_ranged_inventory_update(state: PcMeleeState, actor: str,
        weapon: RangedWeaponReloadState) -> tuple[NpcParticipantSnapshot, ...]:
    return npc_ranged_inventory_update_enemies(state.enemies,actor,weapon)


def npc_ranged_inventory_update_enemies(enemies: tuple[NpcParticipantSnapshot, ...], actor: str,
        weapon: RangedWeaponReloadState) -> tuple[NpcParticipantSnapshot, ...]:
    """Retain full K1 state on exactly the source-bound unit, including 0 work."""
    if type(weapon) not in (FreeReloadWeaponState,ReloadableWeaponState):
        raise TypeError('NPC ranged update requires its exact K1 weapon state')
    replace(weapon)
    enemy = next((value for value in enemies if value.state.actor_id == actor),None)
    if enemy is None:
        raise ValueError('NPC ranged update requires its actual existing actor')
    inventory = enemy.state.weapon_inventory
    if inventory is None:
        raise ValueError('NPC ranged update requires its physical weapon inventory')
    item = inventory.item(weapon.weapon_instance_id)
    previous = npc_ranged_weapon_from_unit(item)
    if previous is None or previous.weapon_id is not weapon.weapon_id:
        raise ValueError('NPC ranged update belongs to another physical weapon')
    if type(previous) is FreeReloadWeaponState:
        if weapon != previous:
            raise ValueError('a free-reload item cannot acquire Exacting progress')
        following = inventory
    else:
        following = inventory.with_item(replace(item,reload=weapon))
    updated = replace(enemy,state=replace(enemy.state,weapon_inventory=following))
    return tuple(updated if value.state.actor_id == actor else value for value in enemies)


def validate_pc_npc_ranged_weapons(state: PcMeleeState) -> None:
    initial = initial_pc_npc_weapon_inventories(state.source)
    if tuple(enemy.state.actor_id for enemy in state.enemies) != tuple(enemy.state.actor_id for enemy in initial):
        raise ValueError('NPC physical inventories changed source actor membership')
    from towr.domain.pc_melee_result_models import PcAttackProof, validate_pc_melee_source_types
    for enemy, original in zip(state.enemies,initial,strict=True):
        actual, expected = enemy.state.weapon_inventory, original.state.weapon_inventory
        if expected is None:
            if actual is not None:
                raise ValueError('NPC acquired an inventory without a physical source')
            continue
        if type(actual) is not WeaponInventoryState:
            raise TypeError('NPC physical source requires its exact common inventory')
        replace(actual)
        if tuple(item.id for item in actual.items) != tuple(item.id for item in expected.items):
            raise ValueError('NPC inventory changed its finite source membership')
        actor = original.state.actor_id
        for proof in state.history:
            from towr.domain.pc_magic_weapon_models import magic_resource_history_step
            expected=magic_resource_history_step(expected,proof,actor)
            if type(proof) is PcAttackProof and proof.npc_ranged_shot is not None:
                shot = proof.npc_ranged_shot.execution
                if shot.source_request.attack.actor_id != actor:
                    continue
                previous, current = shot.previous_weapon_state,shot.weapon_state
            elif type(proof) is PcNpcRangedReloadProof and proof.request.actor_id == actor:
                previous,current = proof.result.previous_state,proof.result.state
            else:
                continue
            item = expected.item(previous.weapon_instance_id)
            expected_weapon = npc_ranged_weapon_from_unit(item)
            if previous != expected_weapon:
                raise ValueError('NPC ranged weapon progress detached from its actual history')
            validate_pc_melee_source_types(previous,expected_weapon)
            if type(previous) is FreeReloadWeaponState:
                if current != previous:
                    raise ValueError('free NPC shot changed its stateless weapon resource')
                validate_pc_melee_source_types(current,previous)
            else:
                expected = expected.with_item(replace(item,reload=current))
        for actual_item, expected_item in zip(actual.items,expected.items,strict=True):
            # Location, grip and selection are replayed by the physical owner;
            # this owner authenticates origin and full Shooting resources only.
            canonical = replace(expected_item,location=actual_item.location,grip=actual_item.grip)
            if actual_item != canonical:
                raise ValueError('NPC weapon changed source, instance or actual K1 resource history')
            validate_pc_melee_source_types(actual_item,canonical)


def npc_ranged_hands_available(state,actor,*,reload=False):
    """Actual held ranged grip, and a usable free other hand for Reload."""
    enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    item=None if inventory is None else inventory.active
    if item is None or item.location is not WeaponItemLocation.HELD:return False
    from towr.domain.pc_npc_weapon_inventory import _usable_npc_grips
    from towr.domain.weapon_use_models import build_weapon_use
    usable=_usable_npc_grips(state,enemy)
    try:build_weapon_use(actor,inventory,item.id,usable_hands=usable)
    except ValueError:return False
    return not reload or (len(usable)==2 and inventory.shield_hand is None
        and not any(other.id!=item.id and other.location is WeaponItemLocation.HELD for other in inventory.items))


def _held_npc_ranged(state: PcMeleeState, actor: str, *, loaded: bool) -> RangedWeaponReloadState:
    if actor not in state.source.npc_activation_order:
        raise ValueError('NPC ranged weapon requires an opposition actor')
    enemy = state.enemy(actor)
    from towr.domain.pc_medical_models import effective_medical_injury
    injury=effective_medical_injury(state,actor)
    profile = pc_active_npc_ranged_profile(state,actor)
    weapon = pc_npc_ranged_weapon(state,actor)
    inventory = enemy.state.weapon_inventory
    item = inventory.active if inventory is not None else None
    combat_profile = ranged_weapon_combat_profile(profile.weapon_id)
    if (not npc_ranged_hands_available(state,actor,reload=not loaded) or weapon is None or npc_ranged_is_loaded(weapon) is not loaded or weapon.weapon_id is not profile.weapon_id
            or item is None or item.location is not WeaponItemLocation.HELD
            or weapon.weapon_instance_id != item.id
            or not enemy.state.wields_weapon or (not loaded and enemy.state.holds_shield)
            or not loaded and any(other.id!=item.id and other.location is WeaponItemLocation.HELD
                for other in inventory.items)
            or loaded and combat_profile.optimum_range_min is not RangedWeaponRange.CLOSE
                and pc_has_close_enemy(state,actor)
            or injury_is_defeated(enemy.state.injury) or actor in state.exited_npc_ids
            or any(injury.conditions.has(condition) for condition in (Condition.BROKEN,Condition.DEFENCELESS))):
        raise ValueError('NPC ranged weapon action requires its actual held weapon and usable actor')
    return weapon


def pc_npc_ranged_profile_modifiers(state: PcMeleeState, actor: str,
        target: str) -> tuple[DiceModifier,...]:
    """Printed range modifiers before the committed repeater choice and dice."""
    weapon = _held_npc_ranged(state,actor,loaded=True)
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    distance = pc_enemy_range(state,actor,target)
    modifiers = []
    if not _within_optimum(profile,distance,
            strength=pc_active_npc_ranged_profile(state,actor).strength):
        modifiers.append(DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID,-1))
    if distance is RangedWeaponRange.SHORT and profile.short_range_shooting_bonus_dice:
        modifiers.append(DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
            profile.short_range_shooting_bonus_dice))
    return tuple(modifiers)


def pc_conditioned_npc_ranged_attack(state: PcMeleeState, actor: str,
        preparation: RangedWeaponAttackPreparationResult) -> AttackActionExecutionRequest:
    """The same real Conditions filter follows K1 traits and actual Aim."""
    attack = preparation.execution.attack
    from towr.domain.pc_magic_weapon_models import condition_dragon_ranged_attack
    attack = condition_dragon_ranged_attack(state,actor,attack)
    if not state.enemy(actor).state.injury.conditions.has(Condition.DRAINED):
        return attack
    kernel = attack.kernel_request
    test = kernel.attack.attacker_test
    return replace(attack,kernel_request=replace(kernel,attack=replace(kernel.attack,
        attacker_test=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers if m.amount <= 0)))))


def prepare_pc_npc_ranged_shot(state: PcMeleeState, request: AttackActionExecutionRequest):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = request.actor_id
    weapon = _held_npc_ranged(state,actor,loaded=True)
    profile = pc_active_npc_ranged_profile(state,actor)
    policy = next(policy for policy in state.source.npc_ranged_policies if policy.actor_id == actor)
    reload_profile=ranged_weapon_reload_profile(weapon.weapon_id)
    test=request.kernel_request.attack.attacker_test
    selected=any(m.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID for m in test.dice_modifiers)
    if state.enemy(actor).definition.generated_components is not None:
        from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus,pc_shooting_protection
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.pc_melee_result_models import pc_protection_skill
        ordinary=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers
            if m.rule_id!=REPEATER_SHOOTING_BONUS_RULE_ID))
        target=request.target_id
        defender=request.kernel_request.attack.defender_test
        if target in state.source.pc_activation_order:
            source=state.source.participant(target)
            defender_skill=(pc_shooting_protection(state,target,actor,defender.id)[0]
                if defender is not None and source.policy is PcMeleePolicy.AUTOMATIC_COMBAT else
                pc_protection_skill(state.participant(target),Skill.SHOOTING,source.close_shooting_protection_skill))
        else:
            from towr.domain.pc_actor_models import pc_actor_npc_snapshot
            pc_actor_npc_snapshot(state,target)
            defender_skill=None
            if defender is not None:
                from towr.domain.pc_generated_equipment import npc_protection_test
                from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
                protection_profile,prepared=npc_protection_test(state,target,actor,defender.id,attack_skill=Skill.SHOOTING)
                if prepared!=defender:
                    raise ValueError('NPC shot changed the companion\'s committed Protection Test')
                validate_pc_melee_source_types(defender,prepared)
                defender_skill=protection_profile.skill
        if selected != npc_repeater_bonus(state,actor,ordinary,
                defender,target,defender_skill=defender_skill):
            raise ValueError('NPC Repeater mode differs from its committed automatic choice')
    cycle=(weapon_reload_cycle_id(weapon.weapon_instance_id,len(weapon.reload_cycle_ids)+1)
        if reload_profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT or selected else None)
    from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID
    from towr.domain.pc_npc_aim_models import current_npc_aim
    combat_profile = ranged_weapon_combat_profile(weapon.weapon_id)
    distance = pc_enemy_range(state,actor,request.target_id)
    ranks = tuple(RangedWeaponRange)
    beyond_optimum = (combat_profile.has_gm_defined_maximum_range
        and ranks.index(distance) > ranks.index(combat_profile.optimum_range_max))
    approved = False
    if combat_profile.hands is RangedWeaponHands.TWO_HANDED:
        battlefield = state.source.battlefield
        if battlefield is None:
            raise ValueError('two-handed NPC Shooting requires the actual battlefield GM maximum')
        if ranks.index(distance) > ranks.index(battlefield.two_handed_max_range):
            raise ValueError('NPC shot exceeds the explicit scene two-handed maximum')
        approved = distance is RangedWeaponRange.EXTREME or beyond_optimum
    # Reconstruct the unprepared source. The owning Attack contains precisely
    # these traits; K1 proves each one independently and exactly once.
    kernel = request.kernel_request
    impact = kernel.attack.impact_spec
    if type(impact) is not DamageImpactSpec:
        raise TypeError('NPC ranged preparation requires an exact Damage impact')
    unprepared = replace(request,kernel_request=replace(kernel,attack=replace(kernel.attack,
        attacker_test=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers
            if m.rule_id not in (OUTSIDE_OPTIMUM_RANGE_RULE_ID,SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
                AIM_FOLLOW_UP_RULE_ID))),
        impact_spec=replace(impact,damage_modifiers=tuple(m for m in impact.damage_modifiers
            if m.rule_id != ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID)),
        secondary_effects=tuple(effect for effect in kernel.attack.secondary_effects
            if effect.rule_id != BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)),
        wound_dice_modifiers=tuple(m for m in kernel.wound_dice_modifiers
            if m.rule_id != WOUNDS_TABLE_BONUS_RULE_ID)))
    preparation = RangedWeaponAttackPreparationRequest(
        id=pc_melee_action_id(state,actor)+':ranged:prepare',weapon_state=weapon,attack=unprepared,
        target_range=distance,attacker_strength=profile.strength,
        has_blackpowder_lore=policy.has_blackpowder_lore is True,
        has_enemy_in_close_range=pc_has_close_enemy(state,actor),
        next_reload_cycle_id=cycle,
        uses_optional_reload_bonus=selected,aim=current_npc_aim(state,actor),
        range_approved_by_gm=approved)
    attack = _profile_prepared_attack(preparation)
    follow_up = _aim_follow_up_for(preparation,attack)
    return RangedWeaponAttackPreparationResult(preparation.id,preparation.rule_id,preparation,
        combat_profile,attack,follow_up,
        _execution_for(preparation,follow_up.attack if follow_up is not None else attack),
        _applied_rule_ids(preparation,combat_profile,follow_up))


def complete_pc_npc_ranged_shot(state,base_request,effective_request,execution: AttackActionExecutionResult):
    preparation = prepare_pc_npc_ranged_shot(state,base_request)
    if pc_conditioned_npc_ranged_attack(state,base_request.actor_id,preparation) != base_request:
        raise ValueError('NPC ranged Attack differs from its conditioned canonical profile')
    source = preparation.execution
    if type(source.weapon_state) is FreeReloadWeaponState:
        request = replace(source,attack=effective_request)
        result = RangedWeaponAttackExecutionResult(request.id,request.rule_id,request,execution,
            source.weapon_state,source.weapon_state,
            tuple(dict.fromkeys((request.rule_id,*execution.applied_rule_ids))))
        return PcNpcRangedShotProof(preparation,result)
    request = ReloadableRangedAttackExecutionRequest(source.id,source.attack_skill,effective_request,
        source.weapon_state,source.next_reload_cycle_id,source.uses_optional_reload_bonus,source.rule_id)
    result = ReloadableRangedAttackExecutionResult(request.id,request.rule_id,request,execution,
        request.weapon_state,_spent_weapon_state(request),
        tuple(dict.fromkeys((request.rule_id,*execution.applied_rule_ids))))
    return PcNpcRangedShotProof(preparation,result)


def npc_ranged_reload_declaration(state: PcMeleeState, actor: str):
    weapon = _held_npc_ranged(state,actor,loaded=False)
    if type(weapon) is not ReloadableWeaponState:
        raise ValueError('Free-with-Attack bows do not open a separate Reload action')
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(weapon.weapon_instance_id))


def build_pc_npc_ranged_reload(state: PcMeleeState) -> ReloadActionExecutionRequest:
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    if state.round_state.active_turn is None or state.pending or state.pending_wound is not None:
        raise ValueError('NPC Reload requires its actual own turn after mandatory work')
    actor = state.round_state.active_turn.actor_id
    weapon = _held_npc_ranged(state,actor,loaded=False)
    if type(weapon) is not ReloadableWeaponState:
        raise ValueError('Free-with-Attack bows do not open a separate Reload action')
    enemy = state.enemy(actor)
    action = pc_melee_action_id(state,actor)
    if enemy.state.tool_inventory.occupied_hands:
        raise ValueError('NPC Reload requires its instrument to be stowed before using both hands')
    from towr.domain.pc_medical_models import effective_medical_injury
    return ReloadActionExecutionRequest(action+':reload:execute',state.round_state,actor,
        effective_medical_injury(state,actor).conditions,1,weapon,
        npc_ranged_reload_test(state,actor,action+':reload:dexterity'))


def npc_ranged_reload_test(state: PcMeleeState,actor_id: str,test_id: str) -> TestRequest:
    """One prepared Dexterity Test for execution and finite forecast, no RNG."""
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers
    enemy=state.enemy(actor_id)
    profile=pc_active_npc_ranged_profile(state,actor_id)
    if ranged_weapon_reload_profile(profile.weapon_id).trigger is RangedReloadTrigger.FREE_WITH_ATTACK:
        raise ValueError('Free-with-Attack bows have no Exacting Dexterity Test')
    modifiers=pc_npc_distraction_test_modifiers(state,actor_id,None)
    magic_dice,qualities=magic_test_modifiers(state,actor_id,Skill.DEXTERITY)
    from towr.domain.pc_npc_champion_models import npc_champion_test_modifiers
    from towr.domain.pc_medical_models import effective_medical_injury
    from towr.domain.test_models import TestQuality
    body_dice,body_quality=npc_champion_test_modifiers(state,actor_id,Skill.DEXTERITY)
    modifiers=(*modifiers,*magic_dice,*body_dice)
    qualities=tuple(dict.fromkeys((*qualities,*body_quality)))
    if effective_medical_injury(state,actor_id).conditions.has(Condition.DRAINED):
        modifiers=tuple(m for m in modifiers if m.amount<=0)
        qualities=tuple(q for q in qualities if q.quality is not TestQuality.GLORIOUS)
    from towr.domain.pc_oath_models import filter_honour_test
    return filter_honour_test(TestRequest(test_id,profile.dexterity_profile,modifiers,qualities))
