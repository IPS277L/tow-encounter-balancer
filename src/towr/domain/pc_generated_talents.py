"""Source-bound Wild Attack price and Defensive Stance pending replacement.

PG1.4 III74/81, V119/123. These transitions are neither actions nor Tests.
The selected stance trades a genuinely available new Staggered application.
"""
from __future__ import annotations

from towr.domain.pc_demigryph_models import pc_kernel_attack_types

from dataclasses import dataclass,field,replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import TalentId
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import QualityModifier,TestQuality,Skill
from towr.domain.turn_models import CombatActionKind

if TYPE_CHECKING:
    from towr.domain.npc_roster_models import NpcDefinition
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.pc_mount_attack_models import PcMountedAttackIntent
    from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
    from towr.domain.weapon_use_models import WeaponUse

WILD_ATTACK_RULE_ID = 'RULE-TALENT-002:wild-attack'
DEFENSIVE_STANCE_RULE_ID = 'RULE-TALENT-002:defensive-stance'


def _identifier(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise TypeError('Talent proof needs exact nonempty actor/action identifiers')


@dataclass(frozen=True,slots=True)
class PcWildAttackProof:
    actor_id: str
    action_id: str
    intent: PcTacticalChoice | None = field(default=None,kw_only=True)
    mount_intent: PcMountedAttackIntent | None = field(default=None,kw_only=True)
    attack_weapon_intent: PcAttackWeaponIntent | None = field(default=None,kw_only=True)
    help_weapon_use: WeaponUse | None = field(default=None,kw_only=True)

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _identifier(self.action_id)
        if self.attack_weapon_intent is not None:
            from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
            if (type(self.attack_weapon_intent) is not PcAttackWeaponIntent
                    or self.attack_weapon_intent.actor_id != self.actor_id
                    or self.attack_weapon_intent.action_id != self.action_id):
                raise TypeError('Wild Attack requires its exact pre-price weapon intent')
            replace(self.attack_weapon_intent)
        if self.help_weapon_use is not None:
            from towr.domain.weapon_use_models import WeaponUse
            if type(self.help_weapon_use) is not WeaponUse or self.help_weapon_use.actor_id != self.actor_id:
                raise TypeError('Wild Help requires its exact pre-price weapon use')
            replace(self.help_weapon_use)
        if self.attack_weapon_intent is not None and self.help_weapon_use is not None:
            raise ValueError('Wild price commits Attack or Help, never both')
        if self.mount_intent is not None:
            from towr.domain.pc_mount_attack_models import PcMountedAttackIntent
            if type(self.mount_intent) is not PcMountedAttackIntent or self.mount_intent.actor_id!=self.actor_id:
                raise TypeError('Wild Attack mount mode requires its exact committed source')
            replace(self.mount_intent)
        if self.intent is not None:
            from towr.domain.pc_tactical_models import PcTacticalChoice
            from towr.domain.pc_melee_models import PcHelpTarget
            if (type(self.intent) is not PcTacticalChoice or self.intent.actor_id != self.actor_id
                    or self.intent.wild_attack is not True or self.intent.potion is not None
                    or self.intent.action not in (CombatActionKind.ATTACK,CombatActionKind.HELP)):
                raise ValueError('Wild Attack must commit one actual Attack/Melee Help choice')
            _identifier(self.intent.target_id)
            if (self.intent.action is CombatActionKind.HELP and (self.intent.help_policy is None
                    or self.intent.help_policy.target is not PcHelpTarget.ATTACK
                    or self.intent.help_policy.skill is not Skill.MELEE)):
                raise ValueError('Wild Help must commit its actual Melee beneficiary policy')


@dataclass(frozen=True,slots=True)
class PcDefensiveStanceProof:
    actor_id: str
    attacker_id: str
    source: AttackerStaggerRequest

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _identifier(self.attacker_id)
        if type(self.source) is not AttackerStaggerRequest:
            raise TypeError('Defensive Stance must replace its actual pending miss Staggered')
        _identifier(self.source.attack_id)
        replace(self.source)


def has_generated_talent(definition: NpcDefinition,talent: TalentId) -> bool:
    components = definition.generated_components
    from towr.domain.talent_models import has_talent
    return components is not None and has_talent(components.talents,talent)


def wild_attack_available(definition: NpcDefinition,conditions: ConditionState) -> bool:
    return (has_generated_talent(definition,TalentId.WILD_ATTACK)
        and not conditions.has(Condition.STAGGERED) and not conditions.has(Condition.DRAINED))


def actor_has_combat_talent(state: PcMeleeState,actor_id: str,talent: TalentId) -> bool:
    from towr.domain.talent_actor_models import actor_has_talent
    return actor_has_talent(state,actor_id,talent)


def actor_conditions(state: PcMeleeState,actor_id: str) -> ConditionState:
    if actor_id in state.source.pc_activation_order:
        return state.participant(actor_id).injury.conditions
    if actor_id in state.source.enemy_activation_order:
        return state.enemy(actor_id).state.injury.conditions
    from towr.domain.pc_actor_models import pc_actor_injury
    return pc_actor_injury(state,actor_id).conditions


def actor_stagger_removable(state: PcMeleeState,actor_id: str) -> bool:
    if not actor_conditions(state,actor_id).has(Condition.STAGGERED):
        return False
    if actor_id in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        member=state.participant(actor_id)
        return not member.injury.dead and not has_ongoing_condition(member.injury,Condition.STAGGERED)
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    return not pc_actor_npc_snapshot(state,actor_id).state.injury.defeated


def pending_wild_attack(state: PcMeleeState) -> PcWildAttackProof | None:
    """Recover the one price awaiting its actual next Melee Test in this turn."""
    from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof,pc_melee_action_id
    turn = state.round_state.active_turn
    if turn is None:
        return None
    if not actor_has_combat_talent(state,turn.actor_id,TalentId.WILD_ATTACK):
        return None
    from towr.domain.pc_bash_attack_models import pending_bash_decision
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    bash = pending_bash_decision(state)
    action_id = (bash.grant.id if bash is not None and bash.grant.actor_id == turn.actor_id
        else pc_melee_action_id(state,turn.actor_id))
    for proof in reversed(state.history):
        if (type(proof) is PcImmediateStrikeProof and proof.request.actor_id == turn.actor_id
                and proof.request.id == action_id):
            return None
        if (type(proof) is PcAttackProof and proof.request.actor_id == turn.actor_id
                and proof.request.id == action_id+':execute'):
            return None
        if (type(proof) is PcHelpProof and proof.request.actor_id == turn.actor_id
                and proof.request.id == action_id+':help:execute'):
            return None
        if (type(proof) is PcWildAttackProof and proof.actor_id == turn.actor_id
                and proof.action_id == action_id):
            return proof
    return None


def expected_wild_attack(state: PcMeleeState) -> PcWildAttackProof | None:
    from towr.domain.pc_bash_wild_attack import expected_bash_wild_attack
    bash = expected_bash_wild_attack(state)
    if bash is not None:
        return bash
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    turn = state.round_state.active_turn
    if (turn is None
            or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind not in (CombatActionKind.ATTACK,CombatActionKind.HELP)):
        return None
    if turn.actor_id in state.source.pc_activation_order:
        member=state.participant(turn.actor_id)
        conditions=member.injury.conditions
        if (member.injury.dead or not state.live_enemies
                or not actor_has_combat_talent(state,turn.actor_id,TalentId.WILD_ATTACK)
                or conditions.has(Condition.STAGGERED) or conditions.has(Condition.DRAINED)):
            return None
        from towr.domain.pc_tactical_models import select_pc_tactic
        intent=select_pc_tactic(state,turn.actor_id)
        if not intent.wild_attack:
            return None
        from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
        from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
        return PcWildAttackProof(turn.actor_id,pc_melee_action_id(state,turn.actor_id),intent=intent,
            attack_weapon_intent=build_pc_attack_weapon_intent(state) if intent.action is CombatActionKind.ATTACK else None,
            help_weapon_use=pc_attack_weapon_use(state,turn.actor_id) if intent.action is CombatActionKind.HELP else None)
    if turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK or not state.live_party:
        return None
    enemy = state.enemy(turn.actor_id)
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    if (enemy.state.injury.defeated or pc_selected_npc_attack_profile(state,turn.actor_id).skill is not Skill.MELEE
            or not wild_attack_available(enemy.definition,enemy.state.injury.conditions)):
        return None
    from towr.domain.pc_mount_attack_models import (pc_uses_mount_attack,available_pc_attack_mount,
        build_pc_mounted_attack_intent,PcMountedAttackMode)
    if pc_uses_mount_attack(state,turn.actor_id):
        return None
    intent=None
    if available_pc_attack_mount(state,turn.actor_id) is not None:
        from towr.domain.pc_short_opening_models import pc_enemy_range
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        target=next(actor for actor in state.source.enemy_target_priority if not state.participant(actor).injury.dead)
        if pc_enemy_range(state,turn.actor_id,target) is RangedWeaponRange.CLOSE:
            intent=build_pc_mounted_attack_intent(state,turn.actor_id,target,mode=PcMountedAttackMode.RIDER)
    from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
    return PcWildAttackProof(turn.actor_id,pc_melee_action_id(state,turn.actor_id),mount_intent=intent,
        attack_weapon_intent=build_pc_attack_weapon_intent(state))


def generated_attack_quality(state: PcMeleeState,actor_id: str) -> tuple[QualityModifier,...]:
    source = pending_wild_attack(state)
    return ((QualityModifier(WILD_ATTACK_RULE_ID,TestQuality.GLORIOUS),)
        if source is not None and source.actor_id == actor_id
        and not actor_conditions(state,actor_id).has(Condition.DRAINED) else ())


def expected_defensive_stance(state: PcMeleeState) -> PcDefensiveStanceProof | None:
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof,pc_kernel_resolution
    if (state.pending_wound is not None or not state.pending
            or type(state.pending[0]) is not AttackerStaggerRequest):
        return None
    pending = state.pending[0]
    attack = next((proof for proof in reversed(state.history)
        if type(proof) in pc_kernel_attack_types()
        and proof.request.kernel_request.attack.id == pending.attack_id),None)
    if attack is None:
        return None
    defender=attack.request.target_id
    request = attack.protection.source_request
    result = pc_kernel_resolution(attack).attack
    from towr.domain.pc_companion_attack_models import kernel_condition_actor
    condition_actor=kernel_condition_actor(state,attack)
    from towr.domain.attack_models import defender_won_attack_opposition
    if (not actor_has_combat_talent(state,defender,TalentId.DEFENSIVE_STANCE)
            or not actor_stagger_removable(state,defender)
            or request.attack_skill is not Skill.MELEE or request.selected_skill is not Skill.DEFENCE
            or result.outcome is not AttackOutcome.MISS or result.defender_test is None
            or not defender_won_attack_opposition(attack.request.kernel_request.attack,result)
            or attack.request.kernel_request.attack.attacker_is_staggered
            or actor_conditions(state,condition_actor).has(Condition.STAGGERED)):
        return None
    return PcDefensiveStanceProof(defender,attack.request.actor_id,pending)
