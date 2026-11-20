"""Actual Aim sources independent of Shooting/Reload preparation."""
from dataclasses import replace
from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID, AimFollowUpRequest
from towr.domain.condition_models import Condition
from towr.domain.test_models import Skill


def other_aim_action_receipt(proof):
    """Additional real Recover owners, never incidental equipment changes."""
    from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
    from towr.domain.pc_hammer_recover_models import PcHammerRetrievalProof
    from towr.domain.pc_extinguish_models import PcExtinguishProof
    from towr.domain.pc_briarroot_models import PcBriarrootReleaseProof
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponPickupProof
    from towr.domain.pc_npc_shield_models import PcNpcShieldRecoverProof
    from towr.domain.pc_npc_champion_models import PcNpcChampionRecoverProof
    from towr.domain.pc_medical_models import PcMedicalTreatmentProof,PcMedicalSurgeryProof
    from towr.domain.pc_medical_equipment_models import PcMedicalToolRecoverProof
    if type(proof) is PcMedicalTreatmentProof:
        return proof.execution.slot.execution
    if type(proof) in (PcScarabHealingProof, PcHammerRetrievalProof, PcExtinguishProof,
            PcBriarrootReleaseProof, PcBriarrootWeaponPickupProof, PcNpcShieldRecoverProof,
            PcNpcChampionRecoverProof,PcMedicalSurgeryProof,PcMedicalToolRecoverProof):
        return proof.result.slot.execution
    return None


def actor_awareness_profile(state, actor):
    if actor in state.source.pc_activation_order:
        owner = state.source.participant(actor).pc
    elif actor in state.source.npc_activation_order:
        owner = state.source.enemy(actor).definition.generated_components
    else:
        from towr.domain.pc_actor_models import pc_actor_npc_snapshot
        owner = pc_actor_npc_snapshot(state, actor).definition.generated_components
    return None if owner is None or owner.awareness is None else owner.awareness_profile


def actor_aim_weapon_use(state, actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
        use = pc_attack_weapon_use(state, actor)
    else:
        from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
        use = npc_attack_weapon_use(state, actor)
    return use if use is not None and use.skill in (Skill.SHOOTING, Skill.THROWING) else None


def actor_can_aim(state, actor):
    from towr.domain.pc_generated_talents import actor_conditions
    from towr.domain.pc_short_opening_models import pc_has_close_enemy
    from towr.domain.weapon_catalog import weapon_profile
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    use = actor_aim_weapon_use(state, actor)
    if (use is None or actor_awareness_profile(state, actor) is None
            or any(actor_conditions(state, actor).has(condition)
                for condition in (Condition.DEFENCELESS, Condition.BROKEN))):
        return False
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import restriction_sources
        from towr.domain.injury_models import WoundRestriction
        if restriction_sources(state.participant(actor).injury, WoundRestriction.CANNOT_AIM):
            return False
    return not (use.skill is Skill.SHOOTING and pc_has_close_enemy(state, actor)
        and weapon_profile(use.kind).optimum_range_min is not RangedWeaponRange.CLOSE)


def actual_aim_follow_up(aim, proof, receipt):
    """K1 preflight must reproduce the actual next Attack and its single bonus."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.turn_models import CombatActionKind
    from towr.rules.aim_resolution import resolve_aim_follow_up
    attack = proof.request if type(proof) is PcAttackProof and receipt.declaration.kind is CombatActionKind.ATTACK else None
    skill = None if attack is None else proof.weapon_intent.attack_skill
    before = attack
    if attack is not None:
        test = attack.kernel_request.attack.attacker_test
        before = replace(attack, kernel_request=replace(attack.kernel_request, attack=replace(
            attack.kernel_request.attack, attacker_test=replace(test, dice_modifiers=tuple(
                value for value in test.dice_modifiers if value.rule_id != AIM_FOLLOW_UP_RULE_ID)))))
    follow = resolve_aim_follow_up(AimFollowUpRequest(aim.request_id+':consume:'+receipt.id,
        aim, receipt.actor_id, receipt.id, receipt.declaration, skill, before))
    if follow.attack != attack:
        # The parent Attack projector has already authenticated all current
        # Conditions. Its Drained owner can suppress positive modifiers after
        # the K1 Aim grant; this bookkeeping receipt never authorizes a roll.
        prepared = follow.attack
        if prepared is None:
            raise ValueError('Aim consumption changed the actual next action')
        test = prepared.kernel_request.attack.attacker_test
        suppressed = replace(prepared, kernel_request=replace(prepared.kernel_request,
            attack=replace(prepared.kernel_request.attack, attacker_test=replace(test,
                dice_modifiers=tuple(value for value in test.dice_modifiers if value.amount <= 0)))))
        if suppressed != attack:
            raise ValueError('Aim consumption changed the actual next Attack or its single bonus')
    return follow
