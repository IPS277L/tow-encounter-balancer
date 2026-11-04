"""Explicit d10 scripts for the first actual PC Wound and follow-up tests."""
from tests.support.pc_melee_fixtures import make_pc_melee_scenario


class ScriptedD10:
    def __init__(self, values):
        self.values = tuple(values)
        self.index = 0

    def randint(self, low, high):
        assert (low,high) == (1,10)
        assert self.index < len(self.values), f'unexpected d10 at index {self.index}'
        value = self.values[self.index]
        self.index += 1
        return value

    def assert_exhausted(self):
        assert self.index == len(self.values), (self.index,len(self.values))


def first_wound_script(total, *, endurance_success=False, hand=1):
    # PC misses (3d10 vs2), enemy hits (2d10 vs3), then one Wounds die.
    values = [10,10,10,1,1, 1,1,10,10,10, total]
    if total in (4,5,7):
        values.extend([1,10,10] if endurance_success else [10,10,10])
    if total == 8 or total == 4 and not endurance_success:
        values.append(hand)
    return values


def run_first_wound(total, *, endurance_success=False, hand=1):
    from towr.engine.pc_melee_runner import run_pc_melee_scenario
    source = make_pc_melee_scenario(max_rounds=1)
    rng = ScriptedD10(first_wound_script(total,endurance_success=endurance_success,hand=hand))
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def blind_expiry_script():
    return first_wound_script(7) + [1,1,10,10,10,1,1, 10,10,1,1,1]


def party_casualty_source():
    from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
    return make_pc_melee_party_scenario(pc_count=2, enemy_count=4, max_rounds=2)


def party_casualty_script():
    # Both PCs miss. Three Minions Wound pc1 (totals1,2,30), then the
    # fourth retargets pc2 and misses. pc2 kills a Minion next round;
    # the remaining three miss. All literal rolls, no computed expectations.
    return ([10,10,10,1,1] * 2
        + [1,1,1,10,10,10,1]
        + [1,1,1,10,10,10,1,1]
        + [1,1,1,10,10,10,10,10,10]
        + [10,10,10,1,1,1]
        + [1,1,1,10,10]
        + [10,10,10,1,1,1] * 3)


def unavailable_arm_source():
    return make_pc_melee_scenario(enemy_count=4,max_rounds=1)


def unavailable_arm_script():
    return ([10,10,10,1,1]
        + [1,1,1,10,10,10,1]
        + [1,1,1,10,10,10,10,10,1]
        + [1,1,1,7,7,6]
        + [1,1,1,5,5,5,5])
