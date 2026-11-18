"""Real paid K1 Reload actions for common inventory/resource tests."""
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import ConditionState
from towr.domain.reload_models import ReloadActionExecutionRequest, reload_approach_id
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest, ImproviseKind,
)
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


def execute_scripted_weapon_reload(weapon, values=(1, 10), *, actor='pc', round_number=1):
    """Execute one supplied script; never fabricate contributions or expected state."""
    clock = CombatRoundState(round_number, (
        CombatTurnParticipant(actor, CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy', CombatSide.OPPOSITION)))
    clock = start_combat_turn(CombatTurnStartRequest(f'real:{round_number}:start', clock, actor)).state
    declaration = CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SKILL, improvise_approach_id=reload_approach_id(weapon.weapon_instance_id))
    clock = reserve_combat_action_slot(CombatActionSlotRequest(f'real:{round_number}:reserve',
        clock, actor, declaration, ActionSlotGrant.STANDARD)).state
    request = ReloadActionExecutionRequest(f'real:{round_number}:reload', clock, actor,
        ConditionState(), 1, weapon, TestRequest(f'real:{round_number}:dexterity', TestProfile(len(values), 5)))
    rng = ScriptedD10(values)
    result = execute_reload_action(request, rng)
    rng.assert_exhausted()
    return result
