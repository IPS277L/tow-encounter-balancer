"""Finite ADR-0029 probe over public mixed runner, not a simulation API.

All records/aggregation here are illustrative. Production request/result/summary
validation lives in towr.simulation and is not exercised here. No tests/private builders.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from random import Random, getstate
from struct import pack

from mixed_scenario import ScriptedDice, build_scenario
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_mixed_scenario_models import NpcMixedScenario
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome, NpcMixedScenarioResult
from towr.domain.npc_rounds_models import NpcRoundsOutcome
from towr.engine.npc_mixed_scenario_runner import run_npc_mixed_scenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_melee_models import npc_melee_trial_seed
from towr.simulation.npc_ranged_models import npc_ranged_trial_seed


SCHEME = "towr:npc-mixed-trial:v1"
MASTER_SEED = 42
VECTORS = (
    (0, 0, "31b5bc60517dc8c6ec3ebca91c0319881480062cc5353cee054661e8b5acae5c"),
    (42, 7, "ecbb86faf8c674f5ecc8b5aea0a13fe836004fecafbbd4ec7cf59e50a9165ed7"),
    ((1 << 64) - 1, (1 << 64) - 1, "b55deeeb08ed8633fb362bb47dc3deff6d27b5fafc3e08d538c1c99486637f89"),
)


def proposed_seed(master_seed: int, index: int) -> int:
    # Fixed valid inputs in this probe. Public admission is not implemented here.
    payload = SCHEME.encode("ascii") + b"\0" + master_seed.to_bytes(8, "big") + index.to_bytes(8, "big")
    return int.from_bytes(sha256(payload).digest(), "big")


@dataclass(frozen=True, slots=True)
class Observation:
    index: int
    seed: int
    outcome: Outcome
    attacks: int
    visited_rounds: int


def observe(source: NpcMixedScenario, index: int, rng: RandomSource) -> Observation:
    result = run_npc_mixed_scenario(source, rng)
    assert isinstance(result, NpcMixedScenarioResult) and result.source_scenario == source
    report = result.runner_report
    assert not result.current.pending_follow_ups
    if result.outcome in (Outcome.OBJECTIVE_ACHIEVED, Outcome.SIDE_DEFEATED):
        assert report.outcome is NpcRoundsOutcome.PENDING_FOLLOW_UPS
        assert report.pending_follow_up_count == 1 and result.terminal_acknowledgement is not None
    if result.outcome is Outcome.UNSUPPORTED_PATH:
        assert report.blocked_reason is NpcAttackSelectionBlock.NO_CANDIDATE
        assert not result.current.round_state.active_turn.action_slots[0].executed
    assert 1 <= report.visited_round_count <= source.initial.max_rounds
    assert report.executed_attack_count <= len(source.initial.current.actor_order) * report.visited_round_count
    # The full result is released after this projection; no journal in the record.
    return Observation(index, proposed_seed(MASTER_SEED, index), result.outcome,
                       report.executed_attack_count, report.visited_round_count)


def main() -> None:
    for master, index, expected in VECTORS:
        digest = proposed_seed(master, index)
        assert f"{digest:064x}" == expected
        # Independently encode the same unsigned integers with struct.
        assert sha256(SCHEME.encode('ascii') + b'\0' + pack('>QQ', master, index)).hexdigest() == expected
        assert digest not in (npc_melee_trial_seed(master, index), npc_ranged_trial_seed(master, index))
    print(f"seed scheme: {SCHEME}; three golden vectors/struct encoding/family separation OK")

    source = build_scenario(two_archers=True)
    before, global_rng = deepcopy(source), getstate()
    wound, miss = (1, 2, 10, 10, 10, 10), (10,) * 6
    scripts = (miss + wound + miss + wound, miss * 2 + wound * 2, miss * 8, wound)
    expected = ((Outcome.OBJECTIVE_ACHIEVED, 4, 2), (Outcome.SIDE_DEFEATED, 4, 1),
                (Outcome.ROUND_LIMIT, 8, 2), (Outcome.UNSUPPORTED_PATH, 1, 1))
    streams = tuple(ScriptedDice(values) for values in scripts)
    records = tuple(observe(source, index, rng) for index, rng in enumerate(streams))
    assert len({id(rng) for rng in streams}) == 4
    for record, rng, values, (outcome, attacks, rounds) in zip(records, streams, scripts, expected):
        assert (record.outcome, record.attacks, record.visited_rounds) == (outcome, attacks, rounds)
        assert rng.calls == len(values)
        print(f"scripted {record.index}: {outcome.value}; attacks={attacks}; visited_rounds={rounds}; rng={rng.calls}")
    counts = Counter(record.outcome for record in records)
    assert tuple(counts[outcome] for outcome in Outcome) == (1, 1, 1, 1)
    total_attacks = sum(record.attacks for record in records)
    total_rounds = sum(record.visited_rounds for record in records)
    assert (total_attacks, total_rounds) == (17, 6)
    assert tuple(sorted(reversed(records), key=lambda record: record.index)) == records
    print("illustrative aggregate: outcomes=1/1/1/1; total_attacks=17; total_visited_rounds=6")
    print("scripted goal share=1/4 over ALL trials; unsupported=1/4 remains separate; not a balance estimate")

    def seeded(indices: range, *, advance_first_stream: bool = False) -> dict[int, Observation]:
        observed = {}
        for index in indices:
            rng = Random(proposed_seed(MASTER_SEED, index))
            if index == 0 and advance_first_stream:
                for _ in range(17):
                    rng.randint(1, 10)
            observed[index] = observe(source, index, rng)
        return observed

    baseline = seeded(range(4))
    assert baseline == seeded(range(4)) == seeded(range(3, -1, -1))
    expanded = seeded(range(6))
    assert baseline == {index: expanded[index] for index in range(4)}
    shifted = seeded(range(4), advance_first_stream=True)
    assert tuple(baseline[i] for i in range(1, 4)) == tuple(shifted[i] for i in range(1, 4))
    assert source == before and getstate() == global_rng
    print("22 seeded runs: replay/reverse/expanded prefix/extra draws in trial 0 preserve other indexed records")
    print("26 total runner calls; immutable initial/global RNG unchanged; terminal suffix and real no-target stop projected")
    print("Production mixed simulation request/result/summary and their guards are NOT implemented by this probe")


if __name__ == "__main__":
    main()
