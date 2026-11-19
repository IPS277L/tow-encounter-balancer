"""Physical Attack/Protection choices committed before prices and dice.

Only the choices are frozen. Test modifiers still use the current Conditions
after paying a price; a price never licenses selecting different implements.
"""
from dataclasses import dataclass, replace, field

from towr.domain.npc_roster_models import NpcProtectionProfile
from towr.domain.test_models import Skill
from towr.domain.weapon_use_models import WeaponUse, WeaponProtectionUse
from towr.domain.weapon_quality_preparation import WeaponAttackQualityContext
from towr.domain.brawn_impact_models import BrawnAttackEffect


@dataclass(frozen=True, slots=True)
class PcAttackWeaponIntent:
    action_id: str
    actor_id: str
    target_id: str
    attack_skill: Skill
    attack_use: WeaponUse | None
    protection_skill: Skill | None
    protection_use: WeaponProtectionUse | None
    npc_protection: NpcProtectionProfile | None = None
    mount_attack: bool = False
    magic_context: WeaponAttackQualityContext | None = field(default=None,kw_only=True)
    dragon_fire: bool = field(default=False,kw_only=True)
    brawn_effect: BrawnAttackEffect = field(default=BrawnAttackEffect.STAGGER,kw_only=True)

    def __post_init__(self):
        if any(type(value) is not str or not value.strip()
                for value in (self.action_id, self.actor_id, self.target_id)):
            raise TypeError('weapon intent needs exact action/actor/target identifiers')
        if self.actor_id == self.target_id:
            raise ValueError('Attack cannot target its own actor')
        if type(self.attack_skill) is not Skill or type(self.mount_attack) is not bool:
            raise TypeError('weapon intent requires an exact Skill and mount choice')
        if self.protection_skill is not None and type(self.protection_skill) is not Skill:
            raise TypeError('Protection choice requires its exact Skill')
        for use, expected, actor in ((self.attack_use, WeaponUse, self.actor_id),
                (self.protection_use, WeaponProtectionUse, self.target_id)):
            if use is not None:
                if type(use) is not expected or use.actor_id != actor:
                    raise TypeError('weapon intent changed its exact actor-owned use')
                replace(use)
        if self.attack_use is not None and (self.mount_attack or self.attack_use.skill is not self.attack_skill):
            raise ValueError('a rider weapon cannot supply a mount or another Skill')
        if self.protection_use is not None and self.protection_use.skill is not self.protection_skill:
            raise ValueError('Protection implements belong to a different Test')
        if self.npc_protection is not None:
            if type(self.npc_protection) is not NpcProtectionProfile:
                raise TypeError('NPC Protection requires its complete typed profile')
            replace(self.npc_protection)
            if self.protection_skill is not None and self.npc_protection.skill is not self.protection_skill:
                raise ValueError('NPC Protection profile changed its selected Skill')
        from towr.domain.weapon_catalog import MAGIC_WEAPON_KINDS, WeaponKind
        magical = self.attack_use is not None and any(
            self.attack_use.inventory.item(item).kind in MAGIC_WEAPON_KINDS
            for item in self.attack_use.item_ids)
        if magical != (self.magic_context is not None):
            raise ValueError('Magic Weapon intent requires its actual context')
        if self.magic_context is not None:
            if type(self.magic_context) is not WeaponAttackQualityContext:
                raise TypeError('Magic Weapon context must retain its exact type')
            replace(self.magic_context)
        if type(self.dragon_fire) is not bool or (self.dragon_fire and (
                self.attack_use is None or self.attack_use.kind is not WeaponKind.DRAGON_BOW
                or self.attack_use.primary.dragon_arrow_used)):
            raise ValueError('fire-arrow intent requires this unused Dragon Bow')
        if type(self.brawn_effect) is not BrawnAttackEffect:
            raise TypeError('Brawn intent requires its exact selected alternative')
        if self.brawn_effect is not BrawnAttackEffect.STAGGER and (
                self.attack_use is None or self.attack_use.kind is not WeaponKind.UNARMED
                or self.attack_use.skill is not Skill.BRAWN or self.attack_use.item_ids):
            raise ValueError('Brawn displacement requires the real itemless Unarmed intent')


def pc_attack_selection(state):
    """The existing target/mount policy, shared by commitment and execution."""
    from towr.domain.pc_melee_result_models import current_pc_charge
    from towr.domain.pc_mount_attack_models import pc_uses_mount_attack, pc_best_mount_attack
    from towr.domain.pc_melee_models import PcMeleePolicy
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    turn = state.round_state.active_turn
    actor = turn.actor_id
    charge = current_pc_charge(state, actor)
    mounted = pc_uses_mount_attack(state, actor)
    pc_attacks = actor in state.source.pc_activation_order
    grant = ((turn.action_slots[-1].enduring_strength or turn.action_slots[-1].crown_of_antlers
        or turn.action_slots[-1].duellist_blades)
        if turn.action_slots else None)
    if grant is not None and turn.action_slots[-1].duellist_blades is not None:
        return actor,grant.target_id,False
    if mounted:
        if pc_attacks:
            from towr.domain.pc_tactical_models import select_pc_tactic
            target = select_pc_tactic(state, actor).target_id
        else:
            target = pc_best_mount_attack(state, actor)[1]
    elif pc_attacks:
        target = next(a for a in state.source.participant(actor).target_priority
            if not state.enemy(a).state.injury.defeated and a not in state.exited_npc_ids)
        if charge is None and state.source.participant(actor).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            from towr.domain.pc_tactical_models import select_pc_tactic
            target = select_pc_tactic(state, actor).target_id
    else:
        target = (grant.target_id if grant is not None else next(a for a in state.source.enemy_target_priority
            if not state.participant(a).injury.dead))
        if state.battlefield is not None and grant is None and charge is None:
            target = next((a for a in state.source.enemy_target_priority
                if not state.participant(a).injury.dead and pc_battlefield_attack_available(state, actor, a)), target)
    return actor, charge.target_id if charge is not None else target, mounted


def build_pc_attack_weapon_intent(state):
    from towr.domain.pc_generated_talents import pending_wild_attack
    paid = pending_wild_attack(state)
    if paid is not None and paid.attack_weapon_intent is not None:
        return paid.attack_weapon_intent
    from towr.domain.pc_bestigor_models import pending_blood_rage
    rage = pending_blood_rage(state)
    if rage is not None:
        return rage.weapon_intent
    actor, target, mounted = pc_attack_selection(state)
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    slot = len(state.round_state.active_turn.action_slots) or 1
    action_id = pc_melee_action_id(state, actor) + (':attack2' if slot == 2 else '')
    return build_pc_explicit_attack_weapon_intent(state, actor, target, action_id, mount_attack=mounted)


def build_pc_explicit_attack_weapon_intent(state, actor, target, action_id, *, mount_attack=False):
    """Prepare one already chosen attack, also used by natural follow-ups."""
    from towr.domain.pc_melee_result_models import pc_attack_skill, pc_selected_npc_attack_profile
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use, pc_protection_weapon_use
    from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use, npc_protection_weapon_use
    from towr.domain.condition_models import Condition
    from towr.domain.pc_short_opening_models import pc_enemy_range
    from towr.domain.pc_melee_models import PcMeleePolicy
    mounted = mount_attack
    pc_attacks = actor in state.source.pc_activation_order
    skill = (Skill.MELEE if mounted else pc_attack_skill(state, actor) if pc_attacks
        else pc_selected_npc_attack_profile(state, actor).skill)
    use = (None if mounted else pc_attack_weapon_use(state, actor, target) if pc_attacks
        else npc_attack_weapon_use(state, actor, target)
        if state.enemy(actor).definition.generated_components is not None else None)
    profile = None
    if pc_attacks:
        from towr.domain.pc_generated_equipment import npc_protection_test
        policy = (next((p for p in (state.source.npc_close_shooting_protection_policies or ())
            if p.actor_id == target), None) if skill is Skill.SHOOTING
            and pc_enemy_range(state, actor, target).value == 'close' else None)
        if policy is not None:
            from towr.domain.pc_npc_close_shooting_models import pc_close_shooting_protection_profile
            profile = pc_close_shooting_protection_profile(state.enemy(target).definition, policy.skill)
        profile, _ = npc_protection_test(state, target, actor, action_id+':protection', profile, attack_skill=skill)
        protection_skill = profile.skill
        protection_use = (npc_protection_weapon_use(state, target, protection_skill, skill)
            if state.enemy(target).definition.generated_components is not None else None)
        injury = state.enemy(target).state.injury
    else:
        from towr.domain.pc_melee_result_models import pc_protection_skill
        member = state.participant(target)
        if skill is Skill.BRAWN and state.source.participant(target).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            from towr.domain.pc_generated_ranged_advice import pc_brawn_protection
            protection_skill,_=pc_brawn_protection(state,target,action_id+':protection')
        elif skill in (Skill.SHOOTING, Skill.THROWING) and state.source.participant(target).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            from towr.domain.pc_generated_ranged_advice import pc_shooting_protection
            protection_skill, _ = pc_shooting_protection(state, target, actor, action_id+':protection',attack_skill=skill)
        else:
            protection_skill = pc_protection_skill(member, skill,
                state.source.participant(target).close_shooting_protection_skill
                if pc_enemy_range(state, actor, target).value == 'close' else None)
        protection_use = pc_protection_weapon_use(member, protection_skill, skill)
        injury = member.injury
    if injury.conditions.has(Condition.DEFENCELESS):
        protection_skill, protection_use = None, None
    from towr.domain.pc_magic_weapon_models import magic_weapon_intent_facts
    context, dragon_fire = magic_weapon_intent_facts(state,actor,target,use)
    from towr.domain.pc_brawn_displacement_models import selected_brawn_effect
    brawn=selected_brawn_effect(state,actor,target,use)
    return PcAttackWeaponIntent(action_id, actor, target, skill, use,
        protection_skill, protection_use, profile, mounted,
        magic_context=context,dragon_fire=dragon_fire,brawn_effect=brawn)


def weapon_use_hand(use):
    """Actual used PC hands, including Shield and additional implements."""
    from towr.domain.pc_weapon_inventory import pc_hand
    from towr.domain.weapon_inventory_models import WeaponGrip
    hands = () if use is None else use.used_hands
    return pc_hand(WeaponGrip.BOTH) if len(hands) == 2 else pc_hand(hands[0]) if hands else None
