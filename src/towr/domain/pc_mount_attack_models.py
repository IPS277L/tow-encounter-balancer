"""Source-bound mount Abilities for a rider's ordinary paid Attack (PG124)."""
from __future__ import annotations
from towr.domain.injury_models import injury_wound_count

from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, replace
from towr.domain.pc_musician_effect_models import musician_defends_ties
from enum import Enum

from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_mount_models import CombatMount, PcMountedState, pc_mounted_attack_effects
from towr.domain.protection_models import (
    HalflingStealthProtectionPermission, ProtectionPreparationRequest,
    ProtectionTestOption, _expected_protection,
)
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, InlineProfile, QualityModifier, Skill, TestQuality, TestRequest
from towr.domain.turn_models import CombatActionKind, CombatRoundState, ManoeuvreKind


class PcMountAttackAbility(str, Enum):
    HOOVES = 'hooves'
    WICKED_CLAWS = 'wicked_claws'


class PcMountedAttackMode(str, Enum):
    RIDER = 'rider'
    MOUNT = 'mount'


def pc_mount_attack_profile(mount: CombatMount):
    if type(mount) is not CombatMount:
        raise TypeError('mount Attack requires its exact actual mount type')
    return ((PcMountAttackAbility.WICKED_CLAWS, InlineProfile(4, 4, 8), DamageProfile(5))
        if mount is CombatMount.DEMIGRYPH else
        (PcMountAttackAbility.HOOVES, InlineProfile(3, 3, 6), DamageProfile(3)))


def available_pc_attack_mount(state, actor):
    """A composite live rider can use only their current actual ridden mount."""
    if actor not in (*state.source.pc_activation_order, *state.source.npc_activation_order):
        raise ValueError('mount Attack actor must belong to the complete encounter')
    from towr.domain.pc_oath_models import oath_allows_attack
    if not oath_allows_attack(state,actor,Skill.MELEE):
        return None
    mount = next((item for item in state.mounts if item.actor_id == actor and item.mounted), None)
    if mount is None:
        return None
    from towr.domain.pc_actor_models import pc_actor_injury
    injury = pc_actor_injury(state,actor)
    unavailable = injury_is_defeated(injury)
    if unavailable or any(injury.conditions.has(condition) for condition in (Condition.PRONE, Condition.DEFENCELESS)):
        return None
    body,_ = _mounted_body(state,actor)
    return None if injury_is_defeated(body.snapshot.state.injury) or any(body.snapshot.state.injury.conditions.has(condition)
        for condition in (Condition.PRONE,Condition.DEFENCELESS)) else mount


def _mounted_body(state, actor):
    """Readmit the current animal's complete source; never manufacture a fresh body."""
    from towr.domain.pc_actor_models import pc_companion
    from towr.domain.pc_companion_models import mount_companion_actor_id
    from towr.domain.pc_companion_effect_models import companion_profile
    body=pc_companion(state,mount_companion_actor_id(actor))
    if body is None:
        raise ValueError('mounted natural Attack lost its actual independent animal body')
    profile=companion_profile(state,body.snapshot.state.actor_id)
    if body.retained_since_round is not None:
        raise ValueError('a separately retained animal cannot simultaneously make its rider\'s mount Attack')
    return body,profile


def pc_mount_primary_needed(state, actor):
    """Position for the actual mount when the rider has no usable weapon grip."""
    if available_pc_attack_mount(state, actor) is None:
        return False
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
        from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
        use=pc_attack_weapon_use(state,actor)
        if use is not None:
            return False
        return (state.source.participant(actor).policy is PcMeleePolicy.AUTOMATIC_COMBAT
            and usable_weapon_hand(state.participant(actor)) is None and pc_preferred_weapon_hand(state, actor) is None)
    from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
    return not state.enemy(actor).state.wields_weapon and npc_attack_weapon_use(state,actor) is None


@dataclass(frozen=True, slots=True)
class PcMountedAttackIntent:
    actor_id: str
    source_round: CombatRoundState
    source_mount: PcMountedState
    target_id: str
    mode: PcMountedAttackMode

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id, self.target_id)):
            raise TypeError('mounted Attack requires exact actor and target identifiers')
        if (type(self.source_round) is not CombatRoundState or type(self.source_mount) is not PcMountedState
                or type(self.mode) is not PcMountedAttackMode):
            raise TypeError('mounted Attack intent requires its exact clock, mount and Ability')
        replace(self.source_round); replace(self.source_mount)
        turn = self.source_round.active_turn
        if (self.actor_id == self.target_id or turn is None or turn.actor_id != self.actor_id
                or self.source_mount.actor_id != self.actor_id or not self.source_mount.mounted):
            raise ValueError('mounted Attack intent changed its actual rider, mount or natural Ability')
        if turn.action_slots:
            slot = turn.action_slots[-1]
            if slot.executed or not (slot.declaration.kind is CombatActionKind.ATTACK
                    or slot.declaration.kind is CombatActionKind.MANOEUVRE
                    and slot.declaration.manoeuvre is ManoeuvreKind.CHARGE):
                raise ValueError('mounted primary Attack requires its own unused Attack or actual Charge slot')

    @property
    def ability(self):
        return pc_mount_attack_profile(self.source_mount.mount)[0] if self.mode is PcMountedAttackMode.MOUNT else None

    @property
    def weapon_instance_id(self):
        if self.mode is not PcMountedAttackMode.MOUNT:
            raise ValueError('a rider-mode choice does not invent a natural mount weapon')
        return self.actor_id + ':mount:' + self.source_mount.mount.value + ':' + self.ability.value

    @property
    def slot_index(self):
        return len(self.source_round.active_turn.action_slots) or 1


def build_pc_mounted_attack_intent(state, actor, target, *, mode=PcMountedAttackMode.MOUNT):
    mount = available_pc_attack_mount(state, actor)
    if mount is None:
        raise ValueError('no current ridden mount can make this primary Attack')
    from towr.domain.pc_short_opening_models import pc_enemy_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    from towr.domain.pc_actor_models import pc_opponent_ids
    targets = pc_opponent_ids(state,actor)
    if (target not in targets or pc_enemy_range(state, actor, target) is not RangedWeaponRange.CLOSE
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):
        raise ValueError('mount Attack requires its actual live Close enemy after all pending work')
    return PcMountedAttackIntent(actor, state.round_state, mount, target, mode)


def pc_mounted_attack_test(state, actor, target, identifier, *, extra_qualities=(), is_charge=False):
    mount = available_pc_attack_mount(state, actor)
    if mount is None:
        raise ValueError('mount Test requires the actual available mount Ability')
    if type(extra_qualities) is not tuple or any(type(item) is not QualityModifier for item in extra_qualities):
        raise TypeError('mount Test qualities require their exact typed source tuple')
    if type(is_charge) is not bool:
        raise TypeError('mount Test requires its actual Charge context')
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_allows_outnumbering
    from towr.domain.pc_npc_ability_models import pc_npc_allows_enemy_higher_ground
    from towr.domain.pc_battlefield_manoeuvre_models import pc_charge_attack_modifiers
    from towr.domain.pc_actor_models import pc_actor_injury,pc_actor_npc_snapshot
    from towr.domain.pc_companion_effect_models import companion_test_request
    body,_ = _mounted_body(state,actor)
    injury=body.snapshot.state.injury
    actual=companion_test_request(state,body.snapshot.state.actor_id,identifier,Skill.MELEE)
    target_injury=pc_actor_injury(state,target)
    modifiers = [*actual.dice_modifiers,*(pc_charge_attack_modifiers(state,actor,target) if is_charge else ())]
    if state.source.facts.outnumbering_bonus_approved and pc_battlefield_allows_outnumbering(state, actor):
        modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering', 1))
    if target_injury.conditions.has(Condition.PRONE) and (target in state.source.pc_activation_order
            or pc_npc_allows_enemy_higher_ground(pc_actor_npc_snapshot(state,target).definition)):
        modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground', 1))
    if injury.conditions.has(Condition.DRAINED):
        modifiers = [item for item in modifiers if item.amount <= 0]
    qualities = (*actual.quality_modifiers,*extra_qualities)
    from towr.domain.pc_oath_models import honour_quality_modifiers, filter_honour_test, prepare_pc_honour_test
    if not injury.conditions.has(Condition.DRAINED):
        qualities = (*qualities, *honour_quality_modifiers(state, actor))
    # No rider ratings, weapon Traits, Agilulf overrides, hand Critical or
    # already-consumed rider Attack Help are a mount's printed Abilities.
    test = filter_honour_test(TestRequest(identifier, actual.profile, tuple(modifiers), qualities))
    return prepare_pc_honour_test(state, actor, test) if actor in state.source.pc_activation_order else test


def prepare_pc_mounted_attack(state, actor, target, identifier, *, extra_qualities=(), is_charge=False,
        weapon_intent=None):
    """Shared real K1 source for a primary mount Attack or Demigryph follow-up."""
    from towr.domain.pc_oath_models import oath_allows_attack
    if not oath_allows_attack(state,actor,Skill.MELEE):
        raise ValueError('mounted Melee Attack violates the actual GM-confirmed oath')
    mount = available_pc_attack_mount(state, actor)
    if mount is None:
        raise ValueError('mount Attack requires its current actual available source')
    from towr.domain.pc_actor_models import pc_opponent_ids
    if target not in pc_opponent_ids(state,actor):
        raise ValueError('mount Attack requires its actual live opposing target')
    if weapon_intent is not None:
        from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
        if type(weapon_intent) is not PcAttackWeaponIntent:
            raise TypeError('mount Attack requires its exact frozen weapon intent')
        replace(weapon_intent)
        if (weapon_intent.action_id != identifier or weapon_intent.actor_id != actor
                or weapon_intent.target_id != target or not weapon_intent.mount_attack
                or weapon_intent.attack_skill is not Skill.MELEE or weapon_intent.attack_use is not None):
            raise ValueError('mount Attack changed its actual committed natural source')
    attacker = pc_mounted_attack_test(state, actor, target, identifier+':attack',
        extra_qualities=extra_qualities, is_charge=is_charge)
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot,pc_companion
    target_is_pc = target in state.source.pc_activation_order
    immunities=()
    if not target_is_pc:
        from towr.domain.pc_generated_equipment import npc_protection_test
        from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
        from towr.domain.pc_flagellant_models import pc_flagellant_first_stagger_spec
        enemy = pc_actor_npc_snapshot(state,target)
        if weapon_intent is None:
            profile, defender = npc_protection_test(state, target, actor, identifier+':protection', attack_skill=Skill.MELEE)
            skill = profile.skill
        elif weapon_intent.protection_skill is None:
            if not enemy.state.injury.conditions.has(Condition.DEFENCELESS):
                raise ValueError('a living capable defender cannot lose its committed Protection')
            skill, defender = None, None
        else:
            profile, defender = npc_protection_test(state, target, actor, identifier+':protection',
                weapon_intent.npc_protection, attack_skill=Skill.MELEE,
                weapon_use=weapon_intent.protection_use)
            skill = weapon_intent.protection_skill
            if profile.skill is not skill:
                raise ValueError('mount target changed its frozen Protection profile')
        target_injury, resilience = enemy.state.injury, enemy.state.current_resilience
        armed, shield = enemy.state.wields_weapon, enemy.state.holds_shield
        policy = enemy.definition.injury_policy
        if pc_companion(state,target) is not None:
            from towr.domain.pc_undead_minion_models import pc_undead_minion_source
            from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec,undead_minion_effect_immunities
            undead=pc_undead_minion_source(state,target)
            minion_defeat=undead_minion_stagger_defeat_spec(undead,target)
            immunities=undead_minion_effect_immunities(undead,target)
            first_stagger=None
        else:
            minion_defeat, first_stagger = pc_npc_stagger_defeat_spec(enemy.definition), pc_flagellant_first_stagger_spec(state, target)
        permission = HalflingStealthProtectionPermission(target, enemy.definition) if skill is Skill.STEALTH else None
    else:
        from towr.domain.pc_melee_result_models import _pc_test, pc_protection_skill, pc_after_test
        from towr.domain.pc_heavy_wound_models import critical_for_hand, usable_weapon_hand
        from towr.domain.pc_shield_models import pc_has_working_shield, pc_protection_hand, pc_shield_resilience
        from towr.domain.pc_help_models import build_pc_test_help
        member = state.participant(target)
        skill = (pc_protection_skill(member, Skill.MELEE) if weapon_intent is None
            else weapon_intent.protection_skill)
        if skill is None:
            if not member.injury.conditions.has(Condition.DEFENCELESS):
                raise ValueError('a living capable defender cannot lose its committed Protection')
            defender = None
        else:
            options = {} if weapon_intent is None else {'weapon_use': weapon_intent.protection_use}
            defender = _pc_test(state, target, identifier+':protection', skill, oppose_attack=True,
                incoming_attack_skill=Skill.MELEE, **options)
        if not member.injury.conditions.has(Condition.DEFENCELESS):
            defender, _ = build_pc_test_help(state, target, skill, defender)
        from towr.domain.pc_weapon_intent_models import weapon_use_hand
        hand = (pc_protection_hand(member, Skill.MELEE, skill) if weapon_intent is None
            else weapon_use_hand(weapon_intent.protection_use))
        target_injury = (member.injury if member.injury.conditions.has(Condition.DEFENCELESS)
            else pc_after_test(state, target, critical_for_hand(member, hand)))
        resilience = pc_shield_resilience(state, target)
        from towr.domain.pc_weapon_inventory import pc_protection_weapon_use
        defence_use=pc_protection_weapon_use(member,Skill.DEFENCE,Skill.MELEE)
        armed, shield = defence_use is not None and bool(defence_use.item_ids), pc_has_working_shield(member)
        policy, minion_defeat, first_stagger, permission = TargetInjuryPolicy.PLAYER, None, None, None
    body,_ = _mounted_body(state,actor)
    actor_injury = body.snapshot.state.injury
    from towr.domain.pc_musician_effect_models import pc_attack_tie_break
    attack = AttackRequest(identifier+':attack-request', attacker, None,
        DamageImpactSpec(pc_mount_attack_profile(mount.mount)[2], resilience), True,
        actor_injury.conditions.has(Condition.STAGGERED),
        tie_break=pc_attack_tie_break(state,actor,target),
        secondary_effects=pc_mounted_attack_effects(state, actor, target, is_charge=is_charge, attack_skill=Skill.MELEE))
    defenceless = target_injury.conditions.has(Condition.DEFENCELESS)
    protection = ProtectionPreparationRequest(identifier+':prepare-protection', target, attack,
        Skill.MELEE, True, defenceless, armed, shield, None if defenceless else skill,
        () if defenceless else (ProtectionTestOption(target, skill, defender),), halfling_stealth_permission=permission)
    from towr.domain.pc_briarroot_models import briarroot_allows_give_ground
    from towr.domain.pc_give_ground_models import pc_give_ground_context
    ground=pc_give_ground_context(state,target,actor)
    from towr.domain.pc_oath_models import pc_oath_wound_options
    kernel = KernelAttackRequest(identifier+':kernel', target, _expected_protection(protection)[0],
        policy, target_injury, ground.can_leave and briarroot_allows_give_ground(state,target),
        ground.given_this_round, physical_attack=True,
        minion_stagger_defeat=minion_defeat, first_stagger_wound=first_stagger,
        target_effect_immunities=immunities, wound_negation_options=pc_oath_wound_options(state,target))
    return kernel, protection


def pc_best_mount_attack(state, actor, *, grim=False):
    """Immediate public-fact utility; no future rolls, new RNG or action slot."""
    if type(grim) is not bool:
        raise TypeError('prospective mount Grim requires an exact bool')
    if available_pc_attack_mount(state, actor) is None:
        return 0.0, None
    from towr.domain.pc_short_opening_models import pc_enemy_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    from towr.domain.pc_tactical_models import _distribution, _impact_value
    from towr.domain.pc_talent_advice import pc_test_distribution
    is_pc = actor in state.source.pc_activation_order
    priority = state.source.participant(actor).target_priority if is_pc else state.source.enemy_target_priority
    from towr.domain.pc_actor_models import pc_opponent_ids
    targets=pc_opponent_ids(state,actor)
    priority=tuple(target for target in priority if target in targets)+tuple(target for target in targets if target not in priority)
    best = 0.0, None
    for target in priority:
        if target not in targets or pc_enemy_range(state, actor, target) is not RangedWeaponRange.CLOSE:
            continue
        qualities = (QualityModifier('tactics:mount-grim', TestQuality.GRIM),) if grim else ()
        kernel, _ = prepare_pc_mounted_attack(state, actor, target, 'tactics:mount:'+actor,
            extra_qualities=qualities)
        attack = kernel.attack
        defenceless = kernel.target_state.conditions.has(Condition.DEFENCELESS)
        distribution = (pc_test_distribution(state, actor, Skill.MELEE, attack.attacker_test)
            if is_pc else _distribution(attack.attacker_test))
        utility = _impact_value(distribution, (1.0,) if defenceless else _distribution(attack.defender_test),
            attack.impact_spec.damage.base, attack.impact_spec.resilience.total,
            attack.impact_spec.damage.success_multiplier, kernel.target_state.conditions.has(Condition.STAGGERED), defenceless,
            defender_wins_ties=musician_defends_ties(state,target))
        if best[1] is None or utility > best[0] + 1e-12:
            best = utility, target
    return best


def pc_npc_mount_primary_selected(state, actor):
    """Prefer the natural mount attack when a held weapon cannot act or is weaker."""
    mount_value, target = pc_best_mount_attack(state, actor)
    if target is None:
        return False
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    from towr.domain.reload_models import ranged_weapon_is_loaded
    enemy = state.enemy(actor)
    profile = pc_selected_npc_attack_profile(state, actor)
    if profile.damage is None:
        if enemy.definition.generated_components is not None:
            from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use,_utility
            if (npc_attack_weapon_use(state,actor,target) is not None
                    and pc_battlefield_attack_available(state,actor,target)):
                return mount_value>_utility(state,actor)+1e-12
        return True
    if (not enemy.state.wields_weapon and profile.hands is not None
            or not pc_battlefield_attack_available(state, actor, target)):
        return True
    weapon = pc_npc_ranged_weapon(state, actor)
    if weapon is not None and not ranged_weapon_is_loaded(weapon):
        return True
    from towr.domain.pc_tactical_models import _distribution, _impact_value
    from towr.domain.pc_npc_ability_models import pc_npc_attack_modifiers
    from towr.domain.pc_generated_equipment import generated_attack_modifiers, generated_damage_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.attack_models import effective_damage_modifiers, effective_ignores_armour
    kernel, _ = prepare_pc_mounted_attack(state, actor, target, 'tactics:mount-compare:'+actor)
    from towr.domain.pc_actor_models import pc_actor_injury
    target_injury = pc_actor_injury(state,target)
    from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
    npc_use=(npc_attack_weapon_use(state,actor,target) if enemy.definition.generated_components is not None else None)
    modifiers = (*pc_npc_attack_modifiers(enemy.definition, enemy.state.injury.conditions,
        target_conditions=target_injury.conditions, attacker_wounds=injury_wound_count(enemy.state.injury)),
        *generated_attack_modifiers(enemy.definition, enemy.state.injury.conditions, target_injury.conditions,weapon_use=npc_use),
        *pc_npc_distraction_test_modifiers(state, actor, target), *magic_test_modifiers(state, actor, profile.skill)[0])
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers = tuple(item for item in modifiers if item.amount <= 0)
    prepared = TestRequest('tactics:rider:'+actor, profile.test_profile, modifiers,
        magic_test_modifiers(state, actor, profile.skill)[1])
    impact = DamageImpactSpec(profile.damage, kernel.attack.impact_spec.resilience,
        ignores_armour=profile.ignores_armour,
        damage_modifiers=generated_damage_modifiers(enemy.definition, kernel.attack.impact_spec.resilience,weapon_use=npc_use))
    rider_value = _impact_value(_distribution(prepared), (1.0,) if target_injury.conditions.has(Condition.DEFENCELESS)
        else _distribution(kernel.attack.defender_test),
        profile.damage.base + sum(item.amount for item in effective_damage_modifiers(impact)),
        impact.resilience.toughness if effective_ignores_armour(impact) else impact.resilience.total,
        profile.damage.success_multiplier, target_injury.conditions.has(Condition.STAGGERED),
        target_injury.conditions.has(Condition.DEFENCELESS),
        defender_wins_ties=musician_defends_ties(state,target))
    if available_pc_attack_mount(state, actor).mount is CombatMount.DEMIGRYPH:
        rider_value += pc_best_mount_attack(state, actor, grim=True)[0]
    return mount_value > rider_value + 1e-12


def pc_uses_mount_attack(state, actor=None):
    turn = state.round_state.active_turn
    actor = actor or (None if turn is None else turn.actor_id)
    if actor is None or available_pc_attack_mount(state, actor) is None:
        return False
    from towr.domain.pc_generated_talents import pending_wild_attack
    paid=pending_wild_attack(state)
    if paid is not None and paid.actor_id==actor:
        if paid.mount_intent is not None:
            return paid.mount_intent.mode is PcMountedAttackMode.MOUNT
        if paid.intent is not None:
            return paid.intent.mount_attack
    from towr.domain.pc_demigryph_models import current_pc_demigryph_intent
    if current_pc_demigryph_intent(state) is not None:
        return False
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            return False
        from towr.domain.pc_tactical_models import select_pc_tactic
        return select_pc_tactic(state, actor).mount_attack
    return pc_npc_mount_primary_selected(state, actor)


