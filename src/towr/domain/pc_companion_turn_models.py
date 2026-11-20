"""The chosen passive mount policy uses real turns, never extra attacks (PG124).

Only a source-admitted, retained mount gets these turns. Standard Recover
changes its own Conditions; waiting changes only the actual combat clock.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_companion, pc_companion_turn_eligible, pc_actor_injury, pc_opponent_ids
from towr.domain.pc_battlefield_models import battlefield_range
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverConditionTarget, RecoverMode, RecoverStandardChoice
from towr.domain.magic_models import WizardMagicState
from towr.domain.turn_models import CombatTurnEndResult


COMPANION_WAIT_RULE_ID = 'RULE-MOUNT-001:gm-wait-policy'


def _active_companion(state):
    turn = state.round_state.active_turn
    if turn is None or pc_companion(state, turn.actor_id) is None:
        return None
    if not pc_companion_turn_eligible(state, turn.actor_id):
        raise ValueError('companion cannot take a turn before its admitted next round')
    return turn.actor_id


def companion_recover_needed(state, actor):
    row = pc_companion(state, actor)
    if row is None or not pc_companion_turn_eligible(state, actor):
        return False
    conditions = row.snapshot.state.injury.conditions
    return not conditions.has(Condition.DEFENCELESS) and any(conditions.has(condition)
        for condition in (Condition.PRONE, Condition.STAGGERED))


def build_companion_recover(state):
    actor = _active_companion(state)
    if actor is None or not companion_recover_needed(state, actor):
        raise ValueError('no actual companion standard Recover is selected')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    conditions = pc_actor_injury(state, actor).conditions
    def target(condition):
        return RecoverConditionTarget(actor, conditions, None) if conditions.has(condition) else None
    close_enemy = any(battlefield_range(state.battlefield, actor, enemy) is RangedWeaponRange.CLOSE
        for enemy in pc_opponent_ids(state, actor))
    return RecoverActionExecutionRequest(pc_melee_action_id(state, actor) + ':companion:recover',
        state.round_state, actor, conditions, close_enemy, 1, RecoverMode.STANDARD,
        RecoverStandardChoice(WizardMagicState(), staggered_target=target(Condition.STAGGERED),
            prone_target=target(Condition.PRONE)))


@dataclass(frozen=True, slots=True)
class PcCompanionWaitProof:
    result: CombatTurnEndResult

    def __post_init__(self):
        if type(self.result) is not CombatTurnEndResult:
            raise TypeError('companion wait requires its exact actual turn receipt')
        replace(self.result)


def expected_companion_wait(state):
    actor = _active_companion(state)
    if actor is None or state.round_state.active_turn.action_slots or companion_recover_needed(state, actor):
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    clock = replace(state.round_state, active_turn=None,
        completed_turn_entity_ids=(*state.round_state.completed_turn_entity_ids, actor))
    return PcCompanionWaitProof(CombatTurnEndResult(pc_melee_action_id(state, actor) + ':end', clock,
        state.round_state.active_turn, clock.next_side, clock.round_complete,
        ('RULE-COMBAT-001:rounds-sides-turns', COMPANION_WAIT_RULE_ID)))


def project_companion_turn(state, proof):
    """Admit only the agreed passive policy against the complete current clock."""
    from towr.domain.pc_melee_result_models import pc_melee_action_id, validate_pc_melee_source_types
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof, battlefield_recovered_injury
    from towr.domain.pc_actor_models import pc_actor_npc_update
    from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
    from towr.domain.pc_melee_result_models import PcTurnEndProof
    from towr.domain.turn_models import CombatActionSlotResult, CombatActionSlotRequest, CombatActionDeclaration, CombatActionKind, ActionSlotGrant
    from towr.rules.turn_resolution import reserve_combat_action_slot, end_combat_turn
    from towr.domain.turn_models import CombatTurnEndRequest
    actor = _active_companion(state)
    if actor is None or state.pending or state.pending_wound is not None:
        raise ValueError('companion turn requires its actual actor and closed mandatory work')
    turn = state.round_state.active_turn
    updates = {}
    if type(proof) is PcCompanionWaitProof:
        expected = expected_companion_wait(state)
        clock = proof.result.state
    elif type(proof) is CombatActionSlotResult:
        if turn.action_slots or not companion_recover_needed(state, actor):
            raise ValueError('passive companion may reserve only one necessary Recover')
        expected = reserve_combat_action_slot(CombatActionSlotRequest(pc_melee_action_id(state, actor)+':reserve',
            state.round_state, actor, CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD))
        clock = expected.state
    elif type(proof) is PcBattlefieldRecoverProof:
        request = build_companion_recover(state)
        result = expected_pc_standard_recover(request)
        before = pc_actor_injury(state, actor)
        after = battlefield_recovered_injury(before, result)
        expected = PcBattlefieldRecoverProof(request, result, before, after)
        clock = result.round_state
        updates = pc_actor_npc_update(state, actor, injury=after)
    elif type(proof) is PcTurnEndProof:
        if not turn.action_slots or any(not slot.executed for slot in turn.action_slots):
            raise ValueError('companion end must finish its one real Recover')
        result = end_combat_turn(CombatTurnEndRequest(pc_melee_action_id(state, actor)+':end', state.round_state, actor))
        expected = PcTurnEndProof(result, None, None)
        clock = result.state
    else:
        raise ValueError('passive companion may only wait or perform self Recover')
    if expected is None or type(proof) is not type(expected) or proof != expected:
        raise ValueError('companion turn receipt changed its actual policy, source, benefit or clock')
    validate_pc_melee_source_types(proof, expected)
    return replace(state, history=(*state.history, proof), round_state=clock, **updates)
