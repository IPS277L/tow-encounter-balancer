"""ADR-0050 automatic Leg Spasm/Wound6 continuation; copy with magic_scenario.py.

PG1.4 Rules pp115-116,119,122-123; Wounds Table p190. GM1.1 p92.
Wizard4 and all other numeric profiles/facts are authored, not named book NPCs.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from random import getstate

from magic_scenario import authored_scenario, ScriptedDice
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import (
    NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy, NpcMagicStationaryWoundPolicy,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome, NpcMagicUnsupportedReason
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


@dataclass(frozen=True, slots=True)
class ScriptedFactory:
    seeds: tuple[int, ...]
    scripts: tuple[tuple[int, ...], ...]

    def __call__(self, seed):
        return ScriptedDice(self.scripts[self.seeds.index(seed)])


def authored_input(*, stationary=True, miscast=False):
    source = authored_scenario(wizard_side=CombatSide.OPPOSITION)
    initial = replace(source.initial, wizard=replace(source.initial.wizard,
        caster=replace(source.initial.wizard.caster, wizard_level=4)))
    return replace(source, initial=initial,
        stationary_wound_continuation=(NpcMagicStationaryWoundPolicy.LEG_SPASM_STAND_AND_CONTINUE
                                      if stationary else None),
        miscast_continuation=(NpcMagicMiscastContinuationPolicy(
            NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
            NpcRosterMiscastFacts(True, True, True, True, True),
            NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE) if miscast else None))


def main():
    global_rng = getstate()
    hit = (1, 2, 3, 10, 10, 10)
    values = (*hit, 9, *((10,) * 9), *hit, 1, 5, *((10,) * 24))
    assert len(values) == 48
    positive = None
    for miscast in (False, True):
        source = authored_input(miscast=miscast)
        before = deepcopy(source)
        dice = ScriptedDice(values)
        result = run_npc_magic_scenario(source, dice)
        assert dice.calls == 48 and source == before and result.source is source
        assert result.outcome is NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
        assert (result.executed_actions, result.started_rounds, result.completed_rounds) == (9, 3, 3)
        stands = tuple(s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
        assert len(stands) == 1 and len(result.steps) == 30
        stand = stands[0]
        assert stand.after.spatial_state.placements == stand.before.spatial_state.placements
        assert stand.after.consumed_execution_ids == stand.before.consumed_execution_ids
        assert stand.after.spatial_state.free_move_used_entity_ids == ('wizard',)
        casts = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult))
        assert len(casts) == 3 and all(c.source.stationary_wounds is not None for c in casts)
        attacks = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterChampionAttackResult))
        assert len(attacks) == 3
        assert all(a.source.attack.execution.kernel_request.can_target_leave_zone is False for a in attacks[1:])
        final = result.current
        injury = final.roster.participant('wizard').state.injury
        assert tuple(w.table_total for w in injury.wounds) == (9, 6)
        assert not injury.conditions.has(Condition.PRONE) and not injury.conditions.has(Condition.DRAINED)
        assert len(injury.active_wound_effects) == 1 and not final.wound_expiries
        assert len(final.champion_attack.daily_wounds.receipts) == 2
        assert len(final.champion_attack.consumed_wound_roll_ids) == 2
        assert len(tuple(e for r in final.wound_turn_end_receipts for e in r.expired_sources)) == 1
        assert final.roster == final.champion_attack.roster == final.minion_attack.roster
        if positive is None:
            positive = result
        else:
            assert result.steps == positive.steps and result.current == positive.current
        print(f'AUTOMATIC stationary=on miscast={"on" if miscast else "None"}: 48 d10; round limit; 9 actions; 3 rounds; 1 stand')
    print('WOUND 9/6: terrain and both wounds/daily/roll histories retained; Drained expires with its exact witness')
    print('SHOOTING: normal Protection; effective Give Ground=False; no Prone penalty after stand')
    for miscast in (False, True):
        source = authored_input(stationary=False, miscast=miscast)
        before = deepcopy(source)
        dice = ScriptedDice((*hit, 9))
        result = run_npc_magic_scenario(source, dice)
        assert dice.calls == 7 and source == before
        assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
        assert result.current == next(s.before for s in positive.steps
                                      if isinstance(s.result, NpcRosterLegSpasmStandResult))
        print(f'LEGACY stationary=None miscast={"on" if miscast else "None"}: 7 d10; same actor-injury stop')
    request = NpcMagicSimulationRequest(authored_input(), 42, 2)
    before = deepcopy(request)
    factory = ScriptedFactory(tuple(request.seed_for(i) for i in range(2)), (values, (*hit, 10)))
    sequential = run_npc_magic_simulation(request, rng_factory=factory)
    spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1, rng_factory=factory)
    assert sequential == spawned and request == before
    assert sequential.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
    assert summarize_npc_magic_simulation(sequential) == summarize_npc_magic_simulation(spawned)
    assert all(r.source_scenario is request.scenario for r in spawned.trials)
    assert summarize_npc_magic_simulation(spawned).trials == 2
    print('NATIVE sequential/spawn: identical records/summary/full source; round limit + unsupported; denominator 2')
    assert getstate() == global_rng
    print('220 scripted d10 across runner and both backends; immutable sources/global RNG; native API only')


if __name__ == '__main__':
    main()
