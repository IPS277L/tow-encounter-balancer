from __future__ import annotations

from enum import Enum


class OpposedOutcome(str, Enum):
    ATTACKER_WINS = "attacker_wins"
    DEFENDER_WINS = "defender_wins"
    DOUBLE_ZERO = "double_zero"


def resolve_opposed(attacker_successes: int, defender_successes: int) -> OpposedOutcome:
    if attacker_successes < 0 or defender_successes < 0:
        raise ValueError("success counts must not be negative")
    if attacker_successes == 0 and defender_successes == 0:
        return OpposedOutcome.DOUBLE_ZERO
    if attacker_successes >= defender_successes:
        return OpposedOutcome.ATTACKER_WINS
    return OpposedOutcome.DEFENDER_WINS

