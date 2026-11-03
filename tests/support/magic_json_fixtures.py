"""Fresh authored Magic JSON fixtures and explicit Miscast variants."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Literal


MAGIC_JSON_EXAMPLES = Path(__file__).resolve().parents[2] / 'docs/examples/m8/json'


def load_magic_fixture(
    family: Literal['simulation', 'balance'],
    kind: Literal['request', 'result', 'error'] = 'request',
) -> dict:
    """Read a fresh document so mutations cannot leak to another test."""
    return json.loads((MAGIC_JSON_EXAMPLES / f'magic-{family}.{kind}.json').read_text(encoding='utf-8'))


def miscast_policy_document() -> dict:
    """Build one independent authored policy, including its mutable facts."""
    return {
        'choice': 'decline_cast_before_miscast',
        'facts': {
            'all_combatants_in_roster': True,
            'no_external_short_range_creatures': True,
            'unmounted_combatants_only': True,
            'no_effect_immunities': True,
            'no_cross_zone_close': True,
        },
        'prone_policy': 'self_stand_when_safe',
    }


def simulation_document(*, miscast: bool = False) -> dict:
    data = load_magic_fixture('simulation')
    data['scenario']['miscast_continuation'] = miscast_policy_document() if miscast else None
    return data


def balance_document(*, miscast: bool = False, source: dict | None = None) -> dict:
    """Set two independent matching assertions, preserving all other input."""
    data = load_magic_fixture('balance') if source is None else deepcopy(source)
    data['reserve']['scenario']['miscast_continuation'] = miscast_policy_document() if miscast else None
    data['generation']['miscast_continuation'] = miscast_policy_document() if miscast else None
    return data
