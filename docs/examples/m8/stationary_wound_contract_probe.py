"""ADR-0049 original contract evidence and preserved None admission boundary.

Copy with leg_spasm_stand.py and magic_scenario.py. PG1.4 Rules pp115-116,
118-119,122-123; Magic pp156-157; Wounds Table p190. GM1.1 Champions p92.
Primitive-only results below are never substituted into a full battle owner.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from leg_spasm_stand import wounded_case
from magic_scenario import authored_scenario, ScriptedDice
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import (
    CowardlyFlightCastingFacts, CowardlyFlightCastingRequest, CowardlyFlightCastingTarget,
)
from towr.domain.injury_models import (
    CharacterWoundRequest, CharacterWoundType, WoundConditionEffect,
    WoundEffectDuration, WoundEntryId, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.test_models import InlineProfile
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleRollRequest, CharacterWoundLifecycleCompletionRequest,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_leg_spasm_resolution import (
    stand_npc_roster_leg_spasm, apply_npc_roster_leg_spasm_stand,
)
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle, complete_character_wound_lifecycle,
)


def main():
    global_rng = getstate()
    hit = (1, 2, 3, 10, 10, 10)
    scenario, wounded = wounded_case((*hit, 9), WoundEntryId.LEG_SPASM, opted=False)
    stand = stand_npc_roster_leg_spasm(NpcRosterLegSpasmStandRequest(
        'contract49:stand', wounded, 'wizard', False, True))
    owner = apply_npc_roster_leg_spasm_stand(wounded, stand)
    before = deepcopy(owner)
    injury = owner.roster.participant('wizard').state.injury
    assert not injury.conditions.has(Condition.PRONE)
    assert injury.active_wound_effects == (WoundRestrictionEffect(
        1, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN, WoundEffectDuration.UNTIL_TREATED),)
    assert diagnose_npc_magic_unsupported(scenario, owner, 'contract49:stop').reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    print('ACTUAL WOUND 9: 7 d10; bound stand complete; terrain retained; None runner still stops')

    facts = CowardlyFlightCastingFacts(
        caster_can_cast=True, knows_battle_magic=True, spell_memorised=True,
        caster_unarmoured=True, no_bulky_items=True, no_casting_opposition=True,
        no_mixing_winds=True, no_other_test_modifiers=True, no_potency_modifiers=True,
        no_effect_immunities=True, all_zone_enemies_included=True, target_zone_within_long_range=True)
    raw = CowardlyFlightCastingRequest(
        'contract49:k1-cast', owner.wizard.caster, 'wizard', owner.casting_round_state,
        1, owner.wizard.magic_state, owner.casting_spatial_state, 'arena',
        (CowardlyFlightCastingTarget('enemy', InlineProfile(3, 3),
            owner.roster.participant('enemy').state.injury, True),), facts,
        scenario.policy_for('wizard').casting_policy)
    try:
        NpcRosterCastingRequest(owner, raw)
    except ValueError as error:
        assert 'unsupported Wound effects' in str(error), str(error)
    else:
        raise AssertionError('existing bound Casting unexpectedly admits retained terrain')
    print('BOUND CASTING GAP: retained terrain rejected before RNG; original owner unchanged')
    dice = ScriptedDice((10, 10, 10))
    primitive = execute_cowardly_flight_casting(raw, dice)
    assert dice.calls == 3 and primitive.source is raw
    assert primitive.round_state.active_turn.action_slots[0].executed
    assert owner == before
    print('K1 CASTING ONLY: 3 d10; action executed in primitive result; no future owner transition fabricated')

    # Existing K1 can produce the exact mixed effects, but no bound attack/clock
    # witness exists for this independent demonstration. Never project it to owner.
    dice = ScriptedDice((1, 5))
    roll = roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest(
        'contract49:k1-wound6', 'wizard', CharacterWoundRequest(
            'contract49:k1-wound6:roll', injury, CharacterWoundType.CHAMPION)), dice)
    mixed = complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest(
        'contract49:k1-wound6:complete', roll, roll.wound_result.state,
        owner.champion_attack.daily_wounds, 'contract49:k1-wound6:daily',
        consumed_roll_ids=owner.champion_attack.consumed_wound_roll_ids))
    assert dice.calls == 2
    assert tuple(w.table_total for w in mixed.state.wounds) == (9, 6)
    conditions = tuple(e for e in mixed.state.active_wound_effects if isinstance(e, WoundConditionEffect))
    restrictions = tuple(e for e in mixed.state.active_wound_effects if isinstance(e, WoundRestrictionEffect))
    assert conditions == (WoundConditionEffect(2, Condition.DRAINED, WoundEffectDuration.END_OF_NEXT_TURN),)
    assert restrictions == injury.active_wound_effects and owner == before
    print('K1 MIXED EFFECTS ONLY: 2 d10; terrain plus timed Drained; no root attack/expiry witness created')

    # Independent actual Wound6 control: the existing runner carries the complete
    # attack witness and expires Drained at the end of the next Wizard turn.
    control_source = authored_scenario()
    control_before = deepcopy(control_source)
    values = (10,) * 9 + (*hit, 6) + (10,) * 3 + hit
    dice = ScriptedDice(values)
    control = run_npc_magic_scenario(control_source, dice)
    assert dice.calls == len(values) == 25 and control.unsupported is None
    ends = tuple(step.result for step in control.steps
                 if isinstance(step.result, NpcWoundTurnEndResult) and step.result.source.expiries)
    assert len(ends) == 1
    end = ends[0]
    expiry = end.source.expiries[0]
    assert expiry.deadline_round_number == end.source.state.round_state.round_number == 2
    assert expiry.effect in end.source.state.roster.participant('wizard').state.injury.active_wound_effects
    final = end.state.roster.participant('wizard').state.injury
    assert not final.conditions.has(Condition.DRAINED) and final.wounds == end.source.state.roster.participant('wizard').state.injury.wounds
    assert end.state.wound_turn_end_receipts[-1].expired_attack_ids == (expiry.attack_id,)
    assert not end.state.wound_expiries and control_source == control_before
    print('ACTUAL WOUND 6 CONTROL: 25 d10; full attack witness; deadline round 2; Drained expires; wound/history retained')
    assert owner == before and getstate() == global_rng
    print('37 scripted d10; immutable sources/global RNG; None path closed; mixed chain checked separately')


if __name__ == '__main__':
    main()
