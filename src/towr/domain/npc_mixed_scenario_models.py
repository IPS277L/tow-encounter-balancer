"""Pure admission for the stationary mixed Minion scenario (ADR-0028)."""
from __future__ import annotations

from dataclasses import dataclass

from towr.domain.condition_models import StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


@dataclass(frozen=True, slots=True)
class NpcMixedPairRange:
    """An explicit symmetric enemy distance, not inferred from Zone placement."""

    first_actor_id: str
    second_actor_id: str
    target_range: RangedWeaponRange

    def __post_init__(self) -> None:
        _identifier(self.first_actor_id, "first actor")
        _identifier(self.second_actor_id, "second actor")
        if self.first_actor_id == self.second_actor_id:
            raise ValueError("mixed range requires two different actors")
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError("mixed range must be typed")
        if self.target_range not in (RangedWeaponRange.CLOSE, RangedWeaponRange.MEDIUM):
            raise ValueError("mixed scenario supports only Close and Medium pairs")


@dataclass(frozen=True, slots=True)
class NpcMixedScenarioFacts:
    """Caller assertions throughout the budget, including all occupied Zones.

    Ordinary Melee outnumbering is the sole permitted test modifier.
    Ammunition/reload assertions concern every Shooting actor.
    """

    targets_aware: bool
    clear_line_of_sight: bool
    stationary: bool
    all_zone_combatants_included: bool
    unmounted_combatants_only: bool
    no_higher_ground: bool
    no_additional_rules: bool
    no_other_test_modifiers: bool
    ammunition_sufficient: bool
    requires_reload_action: bool

    def __post_init__(self) -> None:
        for name in (
            "targets_aware", "clear_line_of_sight", "stationary", "all_zone_combatants_included",
            "unmounted_combatants_only", "no_higher_ground", "no_additional_rules",
            "no_other_test_modifiers", "ammunition_sufficient", "requires_reload_action",
        ):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"scenario {name} must be an explicit boolean")
            if value is not (name != "requires_reload_action"):
                raise ValueError(f"unsupported mixed scenario fact: {name}")


@dataclass(frozen=True, slots=True)
class NpcMixedActorPolicy:
    """All enemy priorities/GM decisions, and this actor's explicit escape fact."""

    actor_id: str
    target_actor_ids: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]
    outnumbering_bonus_approved: bool
    can_leave_zone: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "policy actor")
        for name in ("outnumbering_bonus_approved", "can_leave_zone"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"policy {name} requires an explicit boolean")
        if not isinstance(self.defeat_decisions, (tuple, list)):
            raise TypeError("defeat decisions require an ordered sequence")
        targets = NpcDefeatObjective(self.target_actor_ids).target_actor_ids
        decisions = tuple(self.defeat_decisions)
        if not all(isinstance(item, MinionDefeatDecision) for item in decisions):
            raise TypeError("scenario defeat decisions must be typed")
        if tuple(item.target_id for item in decisions) != targets:
            raise ValueError("scenario requires one defeat decision per target in priority order")
        if any(item.attacker_id != self.actor_id for item in decisions):
            raise ValueError("scenario defeat decision belongs to another attacker")
        if any(not item.gm_approved for item in decisions):
            raise ValueError("scenario defeat decisions require explicit GM approval")
        object.__setattr__(self, "target_actor_ids", targets)
        object.__setattr__(self, "defeat_decisions", decisions)


@dataclass(frozen=True, slots=True)
class NpcMixedScenario:
    """Fresh fixed-role Melee/Shooting Minions; validates without execution/RNG.

    Admission guarantees initial targets, not that the Attack-only policy can
    finish every future state. Close-target exhaustion is a later explicit stop.
    """

    initial: NpcRoundsRequest
    facts: NpcMixedScenarioFacts
    pair_ranges: tuple[NpcMixedPairRange, ...]
    actor_policies: tuple[NpcMixedActorPolicy, ...]
    repeated_stagger_choice: StaggerChoice
    perspective_side: CombatSide
    objective: NpcDefeatObjective

    def __post_init__(self) -> None:
        if not isinstance(self.initial, NpcRoundsRequest):
            raise TypeError("scenario requires typed initial rounds input")
        if not isinstance(self.facts, NpcMixedScenarioFacts):
            raise TypeError("scenario requires explicit mixed facts")
        if not isinstance(self.perspective_side, CombatSide):
            raise TypeError("scenario perspective must be a CombatSide")
        if not isinstance(self.objective, NpcDefeatObjective):
            raise TypeError("scenario requires an explicit defeat objective")
        if not isinstance(self.repeated_stagger_choice, StaggerChoice):
            raise TypeError("scenario repeated Staggered choice must be typed")
        if self.repeated_stagger_choice is not StaggerChoice.SUFFER_WOUND:
            raise ValueError("mixed scenario supports only SUFFER_WOUND for repeated Staggered")

        current, spatial = self.initial.current, self.initial.spatial_state
        roster, combat = current.state.roster, current.round_state
        if (combat != CombatRoundState(1, combat.participants, combat.side_order)
                or current.state != NpcRosterAttackState(roster)
                or current.pending_follow_ups or current.weapons):
            raise ValueError("scenario requires a fresh first round without histories, pending or weapons")
        actors = {p.state.actor_id: p for p in roster.participants}
        if set(actors) != {p.entity_id for p in combat.participants}:
            raise ValueError("scenario roster must contain exactly the round participants")
        if not all(isinstance(side, CombatSide) for side in combat.side_order):
            raise TypeError("scenario side order must contain CombatSide values")
        if combat.side_order != (CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION):
            raise ValueError("mixed scenario requires the ordinary initial side order")
        if (spatial.gave_ground_entity_ids or spatial.free_move_used_entity_ids
                or spatial.difficult_terrain_tested_entity_ids):
            raise ValueError("scenario requires unused initial spatial state")
        if {p.entity_id for p in spatial.placements} != set(actors):
            raise ValueError("scenario spatial placements must match the roster exactly")

        roles = set()
        for participant in roster.participants:
            definition, state = participant.definition, participant.state
            if definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("mixed scenario supports Minions only")
            if state.injury.wounds or state.injury.defeated or state.injury.conditions.conditions:
                raise ValueError("scenario requires initially healthy Minions without Conditions")
            if len(definition.attacks) != 1:
                raise ValueError("scenario requires exactly one numeric Attack profile")
            attack = definition.attacks[0]
            if (attack.damage.success_multiplier != 1 or attack.ignores_armour or attack.secondary_effects
                    or attack.test_profile.pool_cap is not None):
                raise ValueError("unsupported mixed Attack profile or effects")
            if attack.skill is Skill.MELEE:
                if (attack.range_min is not RangedWeaponRange.CLOSE
                        or attack.range_max is not RangedWeaponRange.CLOSE):
                    raise ValueError("mixed Melee requires Close range")
            elif attack.skill is Skill.SHOOTING:
                if (attack.range_min is not RangedWeaponRange.MEDIUM
                        or attack.range_max is not RangedWeaponRange.LONG
                        or attack.hands is not RangedWeaponHands.TWO_HANDED):
                    raise ValueError("mixed Shooting requires Medium-Long Optimum and two hands")
            else:
                raise ValueError("mixed scenario supports only Melee/Shooting profiles")
            roles.add(attack.skill)
            if state.available_attack_ids != (attack.id,):
                raise ValueError("scenario Attack profile must be available")
            if (not state.wields_weapon or state.holds_shield
                    or state.current_resilience != definition.resilience):
                raise ValueError("unsupported scenario equipment or modified Resilience")
            if (len(definition.protection) != 1 or definition.protection[0].skill is not Skill.ATHLETICS
                    or definition.protection[0].test_profile.pool_cap is not None):
                raise ValueError("mixed scenario requires one unmodified Athletics Protection profile")
        if roles != {Skill.MELEE, Skill.SHOOTING}:
            raise ValueError("mixed scenario requires both Melee and Shooting actors")

        if not isinstance(self.pair_ranges, (tuple, list)):
            raise TypeError("scenario pair ranges require an ordered sequence")
        pairs = tuple(self.pair_ranges)
        distances = {}
        for pair in pairs:
            if not isinstance(pair, NpcMixedPairRange):
                raise TypeError("scenario pair ranges must be typed")
            first, second = pair.first_actor_id, pair.second_actor_id
            if first not in actors or second not in actors:
                raise ValueError("scenario pair names an unknown actor")
            if actors[first].state.side is actors[second].state.side:
                raise ValueError("scenario range pairs must be enemies")
            key = frozenset((first, second))
            if key in distances:
                raise ValueError("duplicate or reversed scenario pair")
            distances[key] = pair.target_range
            first_zone = spatial.placement_for(first).zone_id
            second_zone = spatial.placement_for(second).zone_id
            if pair.target_range is RangedWeaponRange.CLOSE:
                if first_zone != second_zone:
                    raise ValueError("mixed Close pair requires the same Zone")
            elif second_zone not in spatial.graph.adjacent_zone_ids(first_zone):
                raise ValueError("mixed Medium pair requires adjacent Zones")
        expected_pairs = {frozenset((a, b)) for a, first in actors.items() for b, second in actors.items()
                          if first.state.side is not second.state.side}
        if set(distances) != expected_pairs:
            raise ValueError("scenario requires every enemy pair exactly once")

        if not isinstance(self.actor_policies, (tuple, list)):
            raise TypeError("scenario actor policies require an ordered sequence")
        policies = tuple(self.actor_policies)
        if not all(isinstance(item, NpcMixedActorPolicy) for item in policies):
            raise TypeError("scenario actor policies must be typed")
        if len(policies) != len(actors) or {p.actor_id for p in policies} != set(actors):
            raise ValueError("scenario requires exactly one policy per actor")
        for policy in policies:
            actor = actors[policy.actor_id]
            enemies = {key for key, p in actors.items() if p.state.side is not actor.state.side}
            if set(policy.target_actor_ids) != enemies:
                raise ValueError("scenario target priorities must contain every enemy exactly once")
            zone = spatial.placement_for(policy.actor_id).zone_id
            if policy.can_leave_zone and not spatial.graph.adjacent_zone_ids(zone):
                raise ValueError("can_leave_zone requires an adjacent Zone")
            ranges = {distances[frozenset((policy.actor_id, enemy))] for enemy in enemies}
            if actor.definition.attacks[0].skill is Skill.SHOOTING:
                # PG1.4 Equipment / Ranged Weapons p94: ANY Close enemy blocks a bow.
                if RangedWeaponRange.CLOSE in ranges:
                    raise ValueError("mixed Shooting actor must have no enemy in Close")
                required = RangedWeaponRange.MEDIUM
            else:
                required = RangedWeaponRange.CLOSE
            if required not in ranges:
                raise ValueError("every mixed actor requires an initially available target")
        enemies = {key for key, p in actors.items() if p.state.side is not self.perspective_side}
        if set(self.objective.target_actor_ids) != enemies:
            raise ValueError("scenario objective must name all and only the opposing side")
        object.__setattr__(self, "pair_ranges", pairs)
        object.__setattr__(self, "actor_policies", policies)

    def policy_for(self, actor_id: str) -> NpcMixedActorPolicy:
        _identifier(actor_id, "policy actor")
        for policy in self.actor_policies:
            if policy.actor_id == actor_id:
                return policy
        raise ValueError("unknown scenario actor")

    def range_for(self, first_actor_id: str, second_actor_id: str) -> RangedWeaponRange:
        """Look up a supplied enemy pair in either direction, without inference."""
        _identifier(first_actor_id, "first actor")
        _identifier(second_actor_id, "second actor")
        key = frozenset((first_actor_id, second_actor_id))
        for pair in self.pair_ranges:
            if frozenset((pair.first_actor_id, pair.second_actor_id)) == key:
                return pair.target_range
        raise ValueError("unknown scenario enemy pair")


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} ID must be a string")
    if not value.strip():
        raise ValueError(f"{label} ID must not be empty")
