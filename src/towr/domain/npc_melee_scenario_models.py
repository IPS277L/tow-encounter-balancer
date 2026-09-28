from __future__ import annotations

from dataclasses import dataclass

from towr.domain.condition_models import StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


@dataclass(frozen=True, slots=True)
class NpcMeleeScenarioFacts:
    """Explicit assertions for all enemy pairs throughout one stationary melee.

    A shared Zone does not establish Close, awareness, paths, or absent Abilities.
    no_other_test_modifiers excludes everything except ordinary outnumbering.
    """

    zone_id: str
    all_opponents_in_close_range: bool
    targets_aware: bool
    clear_line_of_sight: bool
    stationary: bool
    all_zone_combatants_included: bool
    unmounted_combatants_only: bool
    no_higher_ground: bool
    no_additional_rules: bool
    no_other_test_modifiers: bool
    can_leave_zone: bool

    def __post_init__(self) -> None:
        _identifier(self.zone_id, "scenario Zone")
        for name in (
            "all_opponents_in_close_range", "targets_aware", "clear_line_of_sight",
            "stationary", "all_zone_combatants_included", "unmounted_combatants_only",
            "no_higher_ground", "no_additional_rules", "no_other_test_modifiers", "can_leave_zone",
        ):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"scenario {name} must be an explicit boolean")
            if name != "can_leave_zone" and not value:
                raise ValueError(f"unsupported melee scenario fact: {name}")


@dataclass(frozen=True, slots=True)
class NpcMeleeActorPolicy:
    """Ordered enemy targets and preapproved decisions for this attacker."""

    actor_id: str
    target_actor_ids: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]
    outnumbering_bonus_approved: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "scenario actor")
        if not isinstance(self.outnumbering_bonus_approved, bool):
            raise TypeError("outnumbering bonus requires an explicit GM boolean")
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
class NpcMeleeScenario:
    """Preflight boundary for a fresh, bounded numeric Minion melee.

    Construction validates input only: no runner, decisions, effects or RNG are
    executed. initial.max_rounds is the whole scenario budget, not a fresh
    allowance for each resume. Terminal orchestration is a separate concern.
    """

    initial: NpcRoundsRequest
    facts: NpcMeleeScenarioFacts
    actor_policies: tuple[NpcMeleeActorPolicy, ...]
    repeated_stagger_choice: StaggerChoice
    perspective_side: CombatSide
    objective: NpcDefeatObjective

    def __post_init__(self) -> None:
        if not isinstance(self.initial, NpcRoundsRequest):
            raise TypeError("scenario requires typed initial rounds input")
        if not isinstance(self.facts, NpcMeleeScenarioFacts):
            raise TypeError("scenario requires explicit typed facts")
        if not isinstance(self.perspective_side, CombatSide):
            raise TypeError("scenario perspective must be a CombatSide")
        if not isinstance(self.objective, NpcDefeatObjective):
            raise TypeError("scenario requires an explicit defeat objective")
        if not isinstance(self.repeated_stagger_choice, StaggerChoice):
            raise TypeError("scenario repeated Staggered choice must be typed")
        if self.repeated_stagger_choice is not StaggerChoice.SUFFER_WOUND:
            raise ValueError("melee scenario supports only SUFFER_WOUND for repeated Staggered")

        current = self.initial.current
        roster = current.state.roster
        combat = current.round_state
        spatial = self.initial.spatial_state
        if (combat != CombatRoundState(1, combat.participants, combat.side_order)
                or current.state != NpcRosterAttackState(roster)
                or current.pending_follow_ups or current.weapons):
            raise ValueError("scenario requires a fresh first round without histories, pending or weapons")
        actor_ids = {item.state.actor_id for item in roster.participants}
        if actor_ids != {item.entity_id for item in combat.participants}:
            raise ValueError("scenario roster must contain exactly the round participants")
        # CombatRoundState historically accepts string-valued Enum equivalents;
        # the scenario boundary requires actual typed sides throughout.
        if not all(isinstance(side, CombatSide) for side in combat.side_order):
            raise TypeError("scenario side order must contain CombatSide values")
        if combat.side_order != (CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION):
            raise ValueError("melee scenario requires the ordinary initial side order")
        if (spatial.gave_ground_entity_ids or spatial.free_move_used_entity_ids
                or spatial.difficult_terrain_tested_entity_ids):
            raise ValueError("scenario requires unused initial spatial state")
        if {item.entity_id for item in spatial.placements} != actor_ids:
            raise ValueError("scenario spatial placements must match the roster exactly")

        if any(item.zone_id != self.facts.zone_id for item in spatial.placements):
            raise ValueError("melee scenario requires every participant in the declared Zone")
        if self.facts.can_leave_zone and not spatial.graph.adjacent_zone_ids(self.facts.zone_id):
            raise ValueError("can_leave_zone requires an adjacent Zone")

        for participant in roster.participants:
            definition, state = participant.definition, participant.state
            if definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("melee scenario supports Minions only")
            if state.injury.wounds or state.injury.defeated or state.injury.conditions.conditions:
                raise ValueError("scenario requires initially healthy Minions without Conditions")
            if len(definition.attacks) != 1:
                raise ValueError("scenario requires exactly one numeric Close Melee profile")
            attack = definition.attacks[0]
            if (attack.skill is not Skill.MELEE
                    or attack.range_min is not RangedWeaponRange.CLOSE
                    or attack.range_max is not RangedWeaponRange.CLOSE
                    or attack.damage.success_multiplier != 1
                    or attack.ignores_armour or attack.secondary_effects
                    or attack.test_profile.pool_cap is not None):
                raise ValueError("unsupported scenario Melee profile or effects")
            if state.available_attack_ids != (attack.id,):
                raise ValueError("scenario Melee profile must be available")
            if (not state.wields_weapon or state.holds_shield
                    or state.current_resilience != definition.resilience):
                raise ValueError("unsupported scenario equipment or modified Resilience")
            if (len(definition.protection) != 1
                    or definition.protection[0].skill not in (Skill.ATHLETICS, Skill.DEFENCE)
                    or definition.protection[0].test_profile.pool_cap is not None):
                raise ValueError("scenario requires one unmodified Athletics or Defence Protection profile")

        if not isinstance(self.actor_policies, (tuple, list)):
            raise TypeError("scenario actor policies require an ordered sequence")
        policies = tuple(self.actor_policies)
        if not all(isinstance(item, NpcMeleeActorPolicy) for item in policies):
            raise TypeError("scenario actor policies must be typed")
        if len(policies) != len(actor_ids) or {item.actor_id for item in policies} != actor_ids:
            raise ValueError("scenario requires exactly one policy per actor")
        for policy in policies:
            side = roster.participant(policy.actor_id).state.side
            enemies = {item.state.actor_id for item in roster.participants if item.state.side is not side}
            if set(policy.target_actor_ids) != enemies:
                raise ValueError("scenario target priorities must contain every enemy exactly once")
        enemies = {item.state.actor_id for item in roster.participants
                   if item.state.side is not self.perspective_side}
        if set(self.objective.target_actor_ids) != enemies:
            raise ValueError("scenario objective must name all and only the opposing side")
        object.__setattr__(self, "actor_policies", policies)

    def policy_for(self, actor_id: str) -> NpcMeleeActorPolicy:
        for policy in self.actor_policies:
            if policy.actor_id == actor_id:
                return policy
        raise ValueError("unknown scenario actor")


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} ID must be a string")
    if not value.strip():
        raise ValueError(f"{label} ID must not be empty")
