"""Actual PC ability Attacks; source possession alone never adds action budget."""
from dataclasses import dataclass, replace

from towr.domain.pc_combat_equipment_models import pc_initial_weapon_kinds
from towr.domain.weapon_catalog import WeaponKind


def pc_extra_attack_actors(scenario) -> tuple[str, ...]:
    """Eligible source owners, including a real carried Duellist Blades unit."""
    return tuple(member.actor_id for member in scenario.party
        if WeaponKind.DUELLIST_BLADES in pc_initial_weapon_kinds(member))


@dataclass(frozen=True, slots=True)
class PcExtraAttackCount:
    actor_id: str
    count: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC extra Attack requires its exact source actor ID')
        if type(self.count) is not int:
            raise TypeError('PC extra Attack count must be an exact integer')
        if self.count < 0:
            raise ValueError('PC extra Attack count cannot be negative')


def validate_pc_extra_attack_counts(counts, scenario, *, trials, extra_trials,
        actions, started_rounds):
    eligible = pc_extra_attack_actors(scenario)
    if not eligible:
        if counts is not None or extra_trials is not None:
            raise ValueError('PC extra Attack counters require an actual source ability')
        return
    if type(counts) is not tuple or any(type(row) is not PcExtraAttackCount for row in counts):
        raise TypeError('PC extra Attack counts require an exact typed tuple')
    for row in counts:
        replace(row)
    if tuple(row.actor_id for row in counts) != tuple(member.actor_id for member in scenario.party):
        raise ValueError('PC extra Attack counts must cover the ordered full source party')
    total = sum(row.count for row in counts)
    if extra_trials is None:
        extra_trials = int(total > 0)
    if type(extra_trials) is not int:
        raise TypeError('PC extra Attack trial count must be an exact integer')
    if (not 0 <= extra_trials <= trials or extra_trials > total
            or 2 * total > actions or (total > 0) != (extra_trials > 0)):
        raise ValueError('PC extra Attacks contradict observed trials and actual primary actions')
    budget = min(started_rounds-(trials-extra_trials), extra_trials*scenario.max_rounds)
    for row in counts:
        if row.count > budget or (row.count and row.actor_id not in eligible):
            raise ValueError('PC extra Attack exceeds its actual source and containing-round budget')
