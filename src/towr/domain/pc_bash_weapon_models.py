"""Physical Melee selection for an already earned Bash strike (PG73).

This is bounded preparation, not an Attack, an incidental receipt, or a Bash
grant. The battle owner must execute a proposed Shield release/equip and then
derive the selection again from the resulting real state. No combat state is
replaced to forecast an inventory arrangement.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from towr.domain.attack_models import (
    DamageImpactSpec, effective_damage_modifiers, effective_ignores_armour,
)
from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill, TestProfile, TestRequest, _expected_initial_roll_parameters
from towr.domain.weapon_catalog import weapon_profile
from towr.domain.weapon_effect_preparation import weapon_damage_preparation, weapon_test_modifiers
from towr.domain.weapon_equip_models import WeaponEquipTransition, plan_weapon_equip
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation
from towr.domain.weapon_use_models import WeaponUse, build_weapon_use


@dataclass(frozen=True, slots=True)
class BashWeaponSelection:
    use: WeaponUse
    equip: WeaponEquipTransition | None
    release_shield: bool
    utility: float

    def __post_init__(self):
        if type(self.use) is not WeaponUse:
            raise TypeError('Bash selection requires its exact physical WeaponUse')
        replace(self.use)
        if self.use.primary is None or self.use.skill is not Skill.MELEE:
            raise ValueError('Bash strike requires an actual Melee weapon, not Unarmed/Brawn')
        if self.equip is not None:
            if type(self.equip) is not WeaponEquipTransition:
                raise TypeError('Bash equip requires its exact typed transition')
            replace(self.equip)
            if (self.equip.actor_id != self.use.actor_id or self.equip.after != self.use.inventory
                    or self.equip.after.active_item_id != self.use.primary_item_id
                    or not self.equip.changes_equipment):
                raise ValueError('Bash equip must witness its actual changed hand arrangement')
        if type(self.release_shield) is not bool:
            raise TypeError('Bash Shield release requires an exact bool')
        if self.release_shield and (self.equip is None or self.equip.before.shield_hand is not None
                or self.use.primary_grip is not WeaponGrip.BOTH):
            raise ValueError('Bash Shield release precedes the actual two-handed equip')
        if type(self.utility) is not float or not isfinite(self.utility):
            raise TypeError('Bash selection utility requires a finite exact float')


def _hands(grip):
    return (WeaponGrip.LEFT, WeaponGrip.RIGHT) if grip is WeaponGrip.BOTH else (grip,)


def _npc_equip_used(state, actor):
    # Match the existing NPC incidental owner: the actual current turn, rather
    # than an invented actor-wide or whole-roster allowance.
    from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
    from towr.domain.turn_models import CombatTurnStartResult
    for proof in reversed(state.history):
        if type(proof) is CombatTurnStartResult:
            break
        if type(proof) is PcNpcWeaponEquipProof and proof.actor_id == actor:
            return True
    return False


def _candidate_uses(actor, inventory, primary, usable):
    try:
        yield build_weapon_use(actor, inventory, primary, usable_hands=usable)
    except ValueError:
        return
    for item in inventory.items:
        if item.id == primary or item.location is not WeaponItemLocation.HELD:
            continue
        try:
            yield build_weapon_use(actor, inventory, primary, (item.id,), usable)
        except ValueError:
            continue


def select_bash_weapon(state, actor_id: str, target_id: str) -> BashWeaponSelection | None:
    """Choose a real held/carried Melee unit without spending its permissions.

    Utility ranks the current capped Melee pool and weapon Damage pressure;
    it is a deterministic local heuristic, not a simulated win probability.
    Charge-only dice/Damage are deliberately absent, even in a mounted turn.
    """
    for actor in (actor_id, target_id):
        if type(actor) is not str or not actor.strip():
            raise TypeError('Bash selection requires exact nonempty actor identifiers')
    pcs, npcs = state.source.pc_activation_order, state.source.enemy_activation_order
    # Retained creatures are real opposing targets, not new Bash attackers.
    # Their passive policy cannot acquire a weapon, Talent or immediate grant.
    if actor_id not in (*pcs, *npcs):
        raise ValueError('Bash attacker must be an actual original combat actor')
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot, pc_actor_side
    if pc_actor_side(state, actor_id) is pc_actor_side(state, target_id):
        raise ValueError('Bash strike requires an opposing target')
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.pc_shield_models import pc_shield_resilience
    if actor_id in pcs:
        from towr.domain.pc_heavy_wound_models import injured_hands
        from towr.domain.pc_potion_models import pc_effective_definition
        from towr.domain.pc_weapon_inventory import _usable_pc_grips, pc_weapon_swap_used
        member = state.participant(actor_id)
        if member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS):
            return None
        source = state.source.participant(actor_id)
        pc = pc_effective_definition(state, actor_id)
        inventory, conditions, talents = member.weapon_inventory, member.injury.conditions, source.talents
        usable = _usable_pc_grips(member)
        injured = {WeaponGrip(hand.value) for hand in injured_hands(member)}
        strength, profile = pc.strength, pc.melee_profile
        spent = pc_weapon_swap_used(state, actor_id)
    else:
        from towr.domain.generated_npc_models import generated_npc_combat_ratings
        enemy = state.enemy(actor_id)
        source = enemy.definition.generated_components
        if source is None or enemy.state.injury.defeated or actor_id in state.exited_npc_ids:
            return None
        if enemy.state.injury.conditions.has(Condition.DEFENCELESS):
            return None
        inventory, conditions, talents = enemy.state.weapon_inventory, enemy.state.injury.conditions, source.talents
        usable, injured = (WeaponGrip.LEFT, WeaponGrip.RIGHT), set()
        ws, melee, _ = generated_npc_combat_ratings(source)
        strength, profile = source.strength, TestProfile(ws, melee)
        spent = _npc_equip_used(state, actor_id)
    if target_id in pcs:
        victim = state.participant(target_id)
        if victim.injury.dead:
            return None
        target_conditions, resilience = victim.injury.conditions, pc_shield_resilience(state, target_id)
    else:
        victim = pc_actor_npc_snapshot(state, target_id)
        if victim.state.injury.defeated or target_id in state.exited_npc_ids:
            return None
        if target_id not in npcs:
            from towr.domain.pc_actor_models import pc_active_actor_ids
            if target_id not in pc_active_actor_ids(state):
                return None
        target_conditions, resilience = victim.state.injury.conditions, victim.state.current_resilience
    if inventory is None or not usable:
        return None
    actor_mounted, target_mounted = pc_is_mounted(state, actor_id), pc_is_mounted(state, target_id)

    def score(use, equip, release):
        modifiers = weapon_test_modifiers(use, conditions, target_conditions=target_conditions,
            actor_mounted=actor_mounted, target_mounted=target_mounted, charging=False, talents=talents).modifiers
        if conditions.has(Condition.DRAINED):
            modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
        parameters = _expected_initial_roll_parameters(TestRequest('bash:weapon:estimate', profile, modifiers))
        successes = parameters[5] * parameters[6] / 10
        prepared = weapon_damage_preparation(use, strength, resilience,
            actor_mounted=actor_mounted, charging=False)
        pressure = 0.0
        if prepared.damage is not None:
            impact = DamageImpactSpec(prepared.damage, resilience,
                ignores_armour=prepared.ignores_armour, damage_modifiers=prepared.modifiers,
                magical_source=prepared.magical_source)
            protection = resilience.toughness if effective_ignores_armour(impact) else resilience.total
            pressure = max(0.0, prepared.damage.base + sum(mod.amount for mod in
                effective_damage_modifiers(impact)) + successes - protection)
        stowed = (0 if equip is None else sum(previous.location is WeaponItemLocation.HELD
            and following.location is not WeaponItemLocation.HELD
            for previous, following in zip(equip.before.items, equip.after.items, strict=True)))
        return float(successes + .25 * pressure - len(injured.intersection(use.used_hands))
            - .02 * (equip is not None) - .01 * stowed - .15 * release)

    best = None

    def consider(actual, primary, equip=None, release=False):
        nonlocal best
        for use in _candidate_uses(actor_id, actual, primary, usable):
            candidate = BashWeaponSelection(use, equip, release, score(use, equip, release))
            # Source and hand order break exact ties, with held arrangements
            # considered before any real equipment change.
            if best is None or candidate.utility > best.utility + 1e-12:
                best = candidate

    available = tuple(item for item in inventory.items
        if item.location in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED)
        and weapon_profile(item.kind).skill is Skill.MELEE)
    for item in available:
        if item.location is WeaponItemLocation.HELD:
            consider(inventory, item.id)
    if spent:
        return best
    from towr.domain.pc_briarroot_models import BriarrootWeaponKind
    bound = {binding.weapon_id for binding in state.briarroot_bindings
        if binding.attacker_id == actor_id and binding.kind is BriarrootWeaponKind.HELD}
    for item in available:
        printed = weapon_profile(item.kind)
        grips = ((WeaponGrip.BOTH, WeaponGrip.LEFT, WeaponGrip.RIGHT) if printed.variable_grip else
            (WeaponGrip.BOTH,) if printed.hands is RangedWeaponHands.TWO_HANDED else
            (WeaponGrip.LEFT, WeaponGrip.RIGHT))
        for grip in grips:
            if item.location is WeaponItemLocation.HELD and item.grip is grip:
                continue
            occupied = _hands(grip)
            if any(hand not in usable for hand in occupied):
                continue
            release = inventory.shield_hand in occupied
            if release and grip is not WeaponGrip.BOTH:
                continue
            before = replace(inventory, shield_hand=None) if release else inventory
            held = ((item.id, grip), *((other.id, other.grip) for other in before.items
                if other.id != item.id and other.location is WeaponItemLocation.HELD
                and not set(_hands(other.grip)).intersection(occupied)
                and all(hand in usable for hand in _hands(other.grip))))
            try:
                equip = plan_weapon_equip(actor_id, state.round_state.round_number, before,
                    held_items=held, active_item_id=item.id, usable_hands=usable)
            except ValueError:
                continue
            if any(equip.after.item(identifier).location is not WeaponItemLocation.HELD for identifier in bound):
                continue
            consider(equip.after, item.id, equip, release)
    return best
