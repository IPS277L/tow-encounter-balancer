"""Source-bound Wild Attack price and Defensive Stance pending replacement.

PG1.4 III74/81, V119/123. These transitions are neither actions nor Tests.
The selected stance trades a genuinely available new Staggered application.
"""
from __future__ import annotations

from dataclasses import dataclass,field,replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedTalent
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import QualityModifier,TestQuality,Skill
from towr.domain.turn_models import CombatActionKind

if TYPE_CHECKING:
    from towr.domain.npc_roster_models import NpcDefinition
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_tactical_models import PcTacticalChoice

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

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _identifier(self.action_id)
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


def has_generated_talent(definition: NpcDefinition,talent: GeneratedTalent) -> bool:
    components = definition.generated_components
    return components is not None and talent in components.talents


def wild_attack_available(definition: NpcDefinition,conditions: ConditionState) -> bool:
    return (has_generated_talent(definition,GeneratedTalent.WILD_ATTACK)
        and not conditions.has(Condition.STAGGERED) and not conditions.has(Condition.DRAINED))


def actor_has_combat_talent(state: PcMeleeState,actor_id: str,talent: GeneratedTalent) -> bool:
    if actor_id in state.source.pc_activation_order:
        return any(fact.talent is talent for fact in state.source.participant(actor_id).combat_talents)
    return has_generated_talent(state.enemy(actor_id).definition,talent)


def actor_conditions(state: PcMeleeState,actor_id: str) -> ConditionState:
    return (state.participant(actor_id).injury.conditions if actor_id in state.source.pc_activation_order
        else state.enemy(actor_id).state.injury.conditions)


def actor_stagger_removable(state: PcMeleeState,actor_id: str) -> bool:
    if not actor_conditions(state,actor_id).has(Condition.STAGGERED):
        return False
    if actor_id in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import has_ongoing_condition
        member=state.participant(actor_id)
        return not member.injury.dead and not has_ongoing_condition(member.injury,Condition.STAGGERED)
    return not state.enemy(actor_id).state.injury.defeated


def pending_wild_attack(state: PcMeleeState) -> PcWildAttackProof | None:
    """Recover the one price awaiting its actual next Melee Test in this turn."""
    from towr.domain.pc_melee_result_models import PcAttackProof,PcHelpProof,pc_melee_action_id
    turn = state.round_state.active_turn
    if turn is None:
        return None
    if not actor_has_combat_talent(state,turn.actor_id,GeneratedTalent.WILD_ATTACK):
        return None
    action_id = pc_melee_action_id(state,turn.actor_id)
    for proof in reversed(state.history):
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
                or not actor_has_combat_talent(state,turn.actor_id,GeneratedTalent.WILD_ATTACK)
                or conditions.has(Condition.STAGGERED) or conditions.has(Condition.DRAINED)):
            return None
        from towr.domain.pc_tactical_models import select_pc_tactic
        intent=select_pc_tactic(state,turn.actor_id)
        return (PcWildAttackProof(turn.actor_id,pc_melee_action_id(state,turn.actor_id),intent=intent)
            if intent.wild_attack else None)
    if turn.action_slots[-1].declaration.kind is not CombatActionKind.ATTACK or not state.live_party:
        return None
    enemy = state.enemy(turn.actor_id)
    if (enemy.state.injury.defeated or enemy.definition.attacks[0].skill is not Skill.MELEE
            or not wild_attack_available(enemy.definition,enemy.state.injury.conditions)):
        return None
    return PcWildAttackProof(turn.actor_id,pc_melee_action_id(state,turn.actor_id))


def generated_attack_quality(state: PcMeleeState,actor_id: str) -> tuple[QualityModifier,...]:
    source = pending_wild_attack(state)
    return ((QualityModifier(WILD_ATTACK_RULE_ID,TestQuality.GLORIOUS),)
        if source is not None and source.actor_id == actor_id
        and not actor_conditions(state,actor_id).has(Condition.DRAINED) else ())


def expected_defensive_stance(state: PcMeleeState) -> PcDefensiveStanceProof | None:
    from towr.domain.pc_melee_result_models import PcAttackProof
    if (state.pending_wound is not None or not state.pending
            or type(state.pending[0]) is not AttackerStaggerRequest):
        return None
    pending = state.pending[0]
    attack = next((proof for proof in reversed(state.history)
        if type(proof) is PcAttackProof
        and proof.request.kernel_request.attack.id == pending.attack_id),None)
    if attack is None:
        return None
    defender=attack.request.target_id
    request = attack.protection.source_request
    result = attack.execution.resolution.attack
    if (not actor_has_combat_talent(state,defender,GeneratedTalent.DEFENSIVE_STANCE)
            or not actor_stagger_removable(state,defender)
            or request.attack_skill is not Skill.MELEE or request.selected_skill is not Skill.DEFENCE
            or result.outcome is not AttackOutcome.MISS or result.defender_test is None
            or result.defender_test.successes <= result.attacker_test.successes
            or attack.request.kernel_request.attack.attacker_is_staggered
            or actor_conditions(state,attack.request.actor_id).has(Condition.STAGGERED)):
        return None
    return PcDefensiveStanceProof(defender,attack.request.actor_id,pending)
