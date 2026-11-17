"""Developer-only sequential allocation laboratory; no game/JSON dependencies.

Truth belongs to the oracle and evaluator. The search receives IDs, declared
fixed costs and observations only. Confidence bounds invert a beta mixture
likelihood-ratio martingale; the allocation index itself is a research policy.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from math import ceil, isfinite, lgamma, log, log1p, sqrt
from random import Random
from typing import Callable


@lru_cache(maxsize=32768,typed=True)
def bernoulli_cs(n: int, successes: int, alpha: float) -> tuple[float, float]:
    """Time-uniform Jeffreys beta-mixture CS for a fixed Bernoulli stream."""
    if (type(n) is not int or type(successes) is not int or not 0 <= successes <= n
            or type(alpha) not in (int,float) or not isfinite(alpha) or not 0 < alpha < 1):
        raise ValueError('invalid Bernoulli count or error probability')
    if n == 0:
        return 0., 1.
    failures = n-successes
    constant = (lgamma(successes+.5)+lgamma(failures+.5)-lgamma(n+1)
        -2*lgamma(.5))
    threshold = log(1/alpha)

    def outside(p):
        if p == 0:
            return successes > 0
        if p == 1:
            return failures > 0
        return constant-successes*log(p)-failures*log(1-p) > threshold

    mean = successes/n
    lower = 0.
    if successes:
        a,b = 0.,mean
        for _ in range(48):
            middle = (a+b)/2
            if outside(middle): a = middle
            else: b = middle
        lower = a  # outward rounding
    upper = 1.
    if failures:
        a,b = mean,1.
        for _ in range(48):
            middle = (a+b)/2
            if outside(middle): b = middle
            else: a = middle
        upper = b
    return lower,upper


def target_loss_bounds(interval, target):
    lower,upper = interval
    return max(lower-target,target-upper,0.),max(abs(lower-target),abs(upper-target))


@lru_cache(maxsize=32768,typed=True)
def bernoulli_fixed(n: int, successes: int, tail_alpha: float) -> tuple[float,float]:
    """One-sided KL-Chernoff inversions, each with error <= tail_alpha.

    These are fixed-n bounds. Do not peek, extend or stop using these bounds.
    """
    if (type(n) is not int or type(successes) is not int or not 0 <= successes <= n
            or type(tail_alpha) not in (int,float) or not isfinite(tail_alpha) or not 0 < tail_alpha < 1):
        raise ValueError('invalid fixed-sample counts or tail probability')
    if n == 0:
        return 0.,1.
    mean = successes/n
    threshold = log(1/tail_alpha)
    constant = (successes*log(mean) if successes else 0.) + ((n-successes)*log1p(-mean) if successes < n else 0.)

    def outside(p):
        if p == 0: return successes > 0
        if p == 1: return successes < n
        return constant-successes*log(p)-(n-successes)*log1p(-p) > threshold

    lower,upper = 0.,1.
    if successes:
        a,b = 0.,mean
        for _ in range(48):
            middle = (a+b)/2
            if outside(middle): a = middle
            else: b = middle
        lower = a
    if successes < n:
        a,b = mean,1.
        for _ in range(48):
            middle = (a+b)/2
            if outside(middle): b = middle
            else: a = middle
        upper = b
    return lower,upper


def precision_sample_size(finalists, alpha, half_width):
    """Conservative width plan for fully observed samples, not test power."""
    if (type(finalists) is not int or finalists < 1 or type(alpha) not in (int,float)
            or not 0 < alpha < 1 or type(half_width) not in (int,float) or not 0 < half_width < 1):
        raise ValueError('invalid precision request')
    return ceil(log(2*finalists/alpha)/(2*half_width**2))


@dataclass(frozen=True)
class FixedConfirmation:
    finalist_ids: tuple[str,...]
    n_requested: int
    n_reserved: int
    n: int
    alpha: float
    requested_half_width: float
    nominal_half_width: float | None

    @property
    def budget_limited(self):
        return self.n < self.n_requested

    def interval(self, counts):
        if not self.finalist_ids or counts.n != self.n:
            raise ValueError('fixed confirmation requires its entire frozen sample')
        tail = self.alpha/(2*len(self.finalist_ids))
        return bernoulli_fixed(counts.n,counts.wins,tail)[0],bernoulli_fixed(counts.n,counts.wins+counts.unknown,tail)[1]


def precision_reserve(pool, plan, half_width):
    m = min(2,len(pool))
    requested = precision_sample_size(m,plan.alpha,half_width)
    unit = m*max(a.cost for a in pool)
    minimum_search = plan.initial_trials*sum(a.cost for a in pool)
    reserved_n = min(requested,(plan.work_budget-minimum_search)//unit)
    if reserved_n < 1:
        raise ValueError('insufficient budget for minimum search and independent confirmation')
    return reserved_n*unit,reserved_n


def freeze_confirmation(finalists, reserve, reserved_n, alpha, half_width):
    ids = tuple(a.id for a in finalists)
    if not ids:
        return FixedConfirmation((),0,reserved_n,0,alpha,half_width,None)
    requested = precision_sample_size(len(ids),alpha,half_width)
    n = min(requested,reserve//sum(a.cost for a in finalists))
    if n < 1:
        raise ValueError('confirmation reserve is inconsistent with finalists')
    return FixedConfirmation(ids,requested,reserved_n,n,alpha,half_width,
        sqrt(log(2*len(ids)/alpha)/(2*n)))


@dataclass(frozen=True)
class ArmSpec:
    id: str
    cost: int = 1

    def __post_init__(self):
        if type(self.id) is not str or not self.id or type(self.cost) is not int or self.cost < 1:
            raise ValueError('arms require IDs and positive declared fixed costs')


@dataclass(frozen=True)
class Trial:
    outcome: str
    rounds: int

    def __post_init__(self):
        if self.outcome not in ('win','loss','round_limit','unknown') or type(self.rounds) is not int or self.rounds < 1:
            raise ValueError('invalid laboratory observation')


@dataclass
class Counts:
    n: int = 0
    wins: int = 0
    unknown: int = 0
    round_limits: int = 0
    rounds: int = 0

    def add(self, trial):
        self.n += 1
        self.wins += trial.outcome == 'win'
        self.unknown += trial.outcome == 'unknown'
        self.round_limits += trial.outcome == 'round_limit'
        self.rounds += trial.rounds

    def interval(self, alpha):
        # Y=confirmed win <= latent win <= Z=win or unknown, even for
        # informative missingness. Never divide by n-unknown.
        return (bernoulli_cs(self.n,self.wins,alpha)[0],
            bernoulli_cs(self.n,self.wins+self.unknown,alpha)[1])


@dataclass(frozen=True)
class Plan:
    work_budget: int
    confirmation_trials: int = 32
    initial_trials: int = 4
    batch_size: int = 4
    alpha: float = .05

    def __post_init__(self):
        if any(type(getattr(self,n)) is not int or getattr(self,n) < 1
                for n in ('work_budget','confirmation_trials','initial_trials','batch_size')):
            raise ValueError('positive integer budgets required')
        if not 0 < self.alpha < 1:
            raise ValueError('alpha must be in (0,1)')


@dataclass(frozen=True)
class Look:
    arm_id: str
    stage: str
    n: int
    lower: float
    upper: float
    method: str = 'cs'


@dataclass
class Run:
    policy: str
    pool: tuple[ArmSpec,...]
    plan: Plan
    explored: dict[str,Counts] = field(default_factory=dict)
    confirmed: dict[str,Counts] = field(default_factory=dict)
    looks: list[Look] = field(default_factory=list)
    selected: str | None = None
    search_work: int = 0
    confirmation_work: int = 0
    reserved_work: int = 0
    final_plan: FixedConfirmation | None = None

    @property
    def spent_work(self):
        return self.search_work+self.confirmation_work


def empirical_score(counts, target, target_rounds):
    return abs(counts.wins/counts.n-target),abs(counts.rounds/counts.n-target_rounds)


def racing_next(pool, counts, target, alpha, remaining):
    """Optimistic target distance, then uncertainty per sqrt(declared cost).

    Recompute eligibility every time: a former leader may become unsupported.
    No permanently discarded arms and no optimal-allocation theorem is claimed.
    """
    eligible = [a for a in pool if counts[a.id].n and not counts[a.id].unknown]
    if not eligible:
        return None
    losses = {a.id:target_loss_bounds(counts[a.id].interval(alpha),target) for a in eligible}
    best_upper = min(losses[a.id][1] for a in eligible)
    active = [a for a in eligible if a.cost <= remaining and losses[a.id][0] <= best_upper]
    return min(active,key=lambda a:(losses[a.id][0],
        -(losses[a.id][1]-losses[a.id][0])/sqrt(a.cost),counts[a.id].n,a.id),default=None)


def run_search(pool: tuple[ArmSpec,...], draw: Callable[[str,str,int],Trial], plan: Plan,
        *, policy: str, target=.5, target_rounds=5., precision: float | None = None) -> Run:
    """Equal resource cap and fresh confirmation for both laboratory policies."""
    if policy not in ('uniform','racing') or not pool or len({a.id for a in pool}) != len(pool):
        raise ValueError('invalid policy or pool')
    if not 0 <= target <= 1 or not isfinite(target_rounds) or target_rounds < 1:
        raise ValueError('invalid laboratory targets')
    maximum_cost = max(a.cost for a in pool)
    reserve = min(2,len(pool))*plan.confirmation_trials*maximum_cost
    reserved_n = plan.confirmation_trials
    if precision is not None:
        reserve,reserved_n = precision_reserve(pool,plan,precision)
    search_budget = plan.work_budget-reserve
    cost_cycle = sum(a.cost for a in pool)
    if search_budget < cost_cycle:
        raise ValueError('budget cannot expose the pool and reserve confirmation')
    result = Run(policy,pool,plan,{a.id:Counts() for a in pool},reserved_work=reserve)
    # Fixed pool K, two stages and two bounding streams. Union bound also
    # protects the finalist selected after looking at both confirmations.
    alpha = plan.alpha/(4*len(pool))

    def observe(arm, stage, times):
        counts = (result.explored if stage == 'explore' else result.confirmed).setdefault(arm.id,Counts())
        for _ in range(times):
            trial = draw(arm.id,stage,counts.n)
            if type(trial) is not Trial:
                raise TypeError('laboratory oracle must return Trial')
            counts.add(trial)
        fixed = stage == 'confirm' and result.final_plan is not None
        lower,upper = result.final_plan.interval(counts) if fixed else counts.interval(alpha)
        result.looks.append(Look(arm.id,stage,counts.n,lower,upper,'fixed_kl' if fixed else 'cs'))
        if stage == 'explore': result.search_work += times*arm.cost
        else: result.confirmation_work += times*arm.cost

    quota = search_budget//cost_cycle
    initial = quota if policy == 'uniform' else min(plan.initial_trials,quota)
    for arm in pool:
        observe(arm,'explore',initial)
    remainder_cursor = 0
    while result.search_work < search_budget:
        remaining = search_budget-result.search_work
        if policy == 'uniform':
            # Only the integer remainder; deterministic public pool order.
            ordered = pool[remainder_cursor:]+pool[:remainder_cursor]
            arm = next((a for a in ordered if a.cost <= remaining),None)
            if arm is not None:
                remainder_cursor = (pool.index(arm)+1)%len(pool)
            times = 1
        else:
            arm = racing_next(pool,result.explored,target,alpha,remaining)
            times = min(plan.batch_size,remaining//arm.cost) if arm else 0
        if arm is None:
            break
        observe(arm,'explore',times)

    eligible = [a for a in pool if not result.explored[a.id].unknown]
    finalists = sorted(eligible,key=lambda a:empirical_score(result.explored[a.id],target,target_rounds))[:2]
    if precision is not None:
        # Freeze m, IDs, n and alpha BEFORE opening any confirmation tape.
        result.final_plan = freeze_confirmation(finalists,reserve,reserved_n,plan.alpha,precision)
    for arm in finalists:
        observe(arm,'confirm',result.final_plan.n if result.final_plan is not None else plan.confirmation_trials)
    supported = [a for a in finalists if not result.confirmed[a.id].unknown]
    if supported:
        result.selected = min(supported,key=lambda a:empirical_score(result.confirmed[a.id],target,target_rounds)).id
    assert result.spent_work <= plan.work_budget
    return result


@dataclass(frozen=True)
class ArmTruth:
    spec: ArmSpec
    win_probability: float
    terminal_mean_rounds: float = 5.
    unknown_if_win: float = 0.
    unknown_if_nonwin: float = 0.
    round_limit_probability: float = 0.

    def __post_init__(self):
        if (not 0 <= self.win_probability <= 1 or not 0 <= self.round_limit_probability <= 1-self.win_probability
                or not 0 <= self.unknown_if_win <= 1 or not 0 <= self.unknown_if_nonwin <= 1
                or not 1 <= self.terminal_mean_rounds <= 15):
            raise ValueError('invalid oracle truth')

    @property
    def unknown_probability(self):
        p = self.win_probability
        return p*self.unknown_if_win+(1-p)*self.unknown_if_nonwin

    @property
    def mean_rounds(self):
        q = self.round_limit_probability
        return (1-q)*self.terminal_mean_rounds+q*15


@dataclass(frozen=True)
class Fixture:
    name: str
    arms: tuple[ArmTruth,...]
    target: float = .5
    target_rounds: float = 5.
    win_tolerance: float = .1
    rounds_tolerance: float = 1.


def _seed(*parts):
    return int.from_bytes(sha256(':'.join(map(str,parts)).encode()).digest()[:16],'big')


class Oracle:
    """Paired indexed tapes; stage/candidate streams do not depend on call order."""
    def __init__(self, fixture: Fixture, seed: int):
        self.fixture = fixture
        self.seed = seed
        self._truth = {a.spec.id:a for a in fixture.arms}
        self._tapes = {}
        self._rngs = {}

    def draw(self, arm_id, stage, index):
        if stage not in ('explore','confirm') or type(index) is not int or index < 0:
            raise ValueError('invalid indexed trial')
        key = arm_id,stage
        tape = self._tapes.setdefault(key,[])
        if key not in self._rngs:
            self._rngs[key] = Random(_seed(self.fixture.name,self.seed,arm_id,stage))
        rng = self._rngs[key]
        truth = self._truth[arm_id]
        while len(tape) <= index:
            u = rng.random()
            win = u < truth.win_probability
            limited = truth.win_probability <= u < truth.win_probability+truth.round_limit_probability
            mean = truth.terminal_mean_rounds
            rounds = 15 if limited else int(mean)+int(rng.random() < mean-int(mean))
            unknown = rng.random() < (truth.unknown_if_win if win else truth.unknown_if_nonwin)
            outcome = 'unknown' if unknown else 'win' if win else 'round_limit' if limited else 'loss'
            tape.append(Trial(outcome,min(rounds,2) if unknown else rounds))
        return tape[index]

    def proposal_pool(self):
        result = [a.spec for a in self.fixture.arms]
        Random(_seed(self.fixture.name,self.seed,'proposals')).shuffle(result)
        return tuple(result)


def fixtures():
    """Known responses, not book profiles or proposed product defaults."""
    names = ('smooth','narrow','plateau','reversal','duration_conflict',
        'informative_unknown','variable_cost','unreachable')
    result = []
    for name in names:
        arms = []
        for i in range(32):
            x = i/31
            p,r,cost,uw,un,limit = .05+.9*x,5.,1,0.,0.,0.
            if name == 'narrow': p = .5 if i == 19 else .08 if i < 19 else .92
            elif name == 'plateau': p = .08 if i < 14 else .5 if i < 18 else .92
            elif name == 'reversal': p = (.05,.85,.5,.15,.95,.6,.1,.9)[i%8]
            elif name == 'duration_conflict':
                p,r = (.5,11.) if i%2 == 0 else (.55,5.)
            elif name == 'informative_unknown':
                p = .5 if i%4 == 0 else .57 if i%8 == 2 else .2 if i%2 else .8
                uw = .5 if i%4 == 0 else 0.
            elif name == 'variable_cost': cost = 4 if .3 < p < .7 else 1
            elif name == 'unreachable': p,limit = (.1 if i%2 else .9),.05
            arms.append(ArmTruth(ArmSpec(f'arm:{i:02}',cost),p,r,uw,un,limit))
        result.append(Fixture(name,tuple(arms)))
    return tuple(result)


def evaluate(fixture: Fixture, result: Run):
    """Truth is used only after execution, for diagnosis rather than decisions."""
    truth = {a.spec.id:a for a in fixture.arms}
    visited = [truth[k] for k,c in result.explored.items() if c.n]
    safe = [a for a in visited if a.unknown_probability == 0]

    def hit(a, joint=False):
        return (a.unknown_probability == 0 and abs(a.win_probability-fixture.target) <= fixture.win_tolerance+1e-12
            and (not joint or abs(a.mean_rounds-fixture.target_rounds) <= fixture.rounds_tolerance))

    chosen = truth.get(result.selected)
    best_error = min((abs(a.win_probability-fixture.target) for a in safe),default=None)
    selected_error = abs(chosen.win_probability-fixture.target) if chosen else None
    penalty = max(fixture.target,1-fixture.target)
    penalized_error = selected_error if chosen and chosen.unknown_probability == 0 else penalty
    counts = tuple(result.explored.values())+tuple(result.confirmed.values())
    alpha = result.plan.alpha/(4*len(result.pool))
    selected_counts = result.confirmed.get(result.selected)
    interval = ((result.final_plan.interval(selected_counts) if result.final_plan is not None
        else selected_counts.interval(alpha)) if selected_counts is not None else None)
    return dict(coverage_win=any(hit(a) for a in visited),coverage_joint=any(hit(a,True) for a in visited),
        final_win_hit=bool(chosen and hit(chosen)),final_joint_hit=bool(chosen and hit(chosen,True)),
        selected=result.selected,selected_error=selected_error,penalized_error=penalized_error,
        best_visited_error=best_error,
        selection_regret=(selected_error-best_error if chosen and chosen.unknown_probability == 0 and best_error is not None else None),
        penalized_regret=penalized_error-(best_error or 0.),
        unsupported_risk_selected=bool(chosen and chosen.unknown_probability),
        missing_recommendation=result.selected is None,
        win_band_certified=bool(interval and interval[0] >= fixture.target-fixture.win_tolerance
            and interval[1] <= fixture.target+fixture.win_tolerance),
        cs_covers_truth_at_all_recorded_looks=all(look.lower <= truth[look.arm_id].win_probability <= look.upper
            for look in result.looks if look.method == 'cs'),
        confirmation_covers_truth=all(look.lower <= truth[look.arm_id].win_probability <= look.upper
            for look in result.looks if look.stage == 'confirm'),
        selected_interval_width=interval[1]-interval[0] if interval else None,
        unknown_trials=sum(c.unknown for c in counts),round_limit_trials=sum(c.round_limits for c in counts),
        trials=sum(c.n for c in counts),search_work=result.search_work,
        confirmation_work=result.confirmation_work,unspent_work=result.plan.work_budget-result.spent_work,
        unused_confirmation_reserve=result.reserved_work-result.confirmation_work,
        explored_trials={k:c.n for k,c in result.explored.items()})
