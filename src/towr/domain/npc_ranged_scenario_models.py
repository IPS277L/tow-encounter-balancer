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
class NpcRangedScenarioFacts:
    """Caller assertions for every enemy pair throughout the stationary scenario.

    No inference of awareness, ammunition, omitted Abilities or battlefield
    modifiers is possible from a numeric NPC profile or a Zone graph alone.
    """

    target_range: RangedWeaponRange
    has_enemy_in_close_range: bool
    targets_aware: bool
    clear_line_of_sight: bool
    stationary: bool
    unmodified_tests: bool
    no_additional_rules: bool
    ammunition_sufficient: bool
    requires_reload_action: bool

    def __post_init__(self) -> None:
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError("scenario range must be typed")
        if self.target_range is not RangedWeaponRange.MEDIUM:
            raise ValueError("ranged scenario requires Medium Range")
        expected = (
            ("has_enemy_in_close_range", False), ("targets_aware", True),
            ("clear_line_of_sight", True),
            ("stationary", True), ("unmodified_tests", True),
            ("no_additional_rules", True), ("ammunition_sufficient", True),
            ("requires_reload_action", False),
        )
        for name, required in expected:
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"scenario {name} must be an explicit boolean")
            if value is not required:
                raise ValueError(f"unsupported ranged scenario fact: {name}")


@dataclass(frozen=True, slots=True)
class NpcRangedActorPolicy:
    """Ordered enemy targets and preapproved decisions for this attacker."""

    actor_id: str
    target_actor_ids: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("scenario policy requires an actor ID")
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
class NpcRangedScenario:
    """Preflight boundary for a fresh, bounded numeric Minion firefight.

    Construction validates input only: no runner, decisions, effects or RNG are
    executed. initial.max_rounds is the whole scenario budget, not a fresh
    allowance for each resume. Terminal orchestration is a separate concern.
    """

    initial: NpcRoundsRequest
    facts: NpcRangedScenarioFacts
    actor_policies: tuple[NpcRangedActorPolicy, ...]
    repeated_stagger_choice: StaggerChoice
    perspective_side: CombatSide
    objective: NpcDefeatObjective

    def __post_init__(self) -> None:
        if not isinstance(self.initial, NpcRoundsRequest):
            raise TypeError("scenario requires typed initial rounds input")
        if not isinstance(self.facts, NpcRangedScenarioFacts):
            raise TypeError("scenario requires explicit typed facts")
        if not isinstance(self.perspective_side, CombatSide):
            raise TypeError("scenario perspective must be a CombatSide")
        if not isinstance(self.objective, NpcDefeatObjective):
            raise TypeError("scenario requires an explicit defeat objective")
        if not isinstance(self.repeated_stagger_choice, StaggerChoice):
            raise TypeError("scenario repeated Staggered choice must be typed")
        if self.repeated_stagger_choice is not StaggerChoice.SUFFER_WOUND:
            raise ValueError("ranged scenario supports only SUFFER_WOUND for repeated Staggered")

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
        if (spatial.gave_ground_entity_ids or spatial.free_move_used_entity_ids
                or spatial.difficult_terrain_tested_entity_ids):
            raise ValueError("scenario requires unused initial spatial state")
        if {item.entity_id for item in spatial.placements} != actor_ids:
            raise ValueError("scenario spatial placements must match the roster exactly")

        for participant in roster.participants:
            definition, state = participant.definition, participant.state
            if definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("ranged scenario supports Minions only")
            if state.injury.wounds or state.injury.defeated or state.injury.conditions.conditions:
                raise ValueError("scenario requires initially healthy Minions without Conditions")
            if len(definition.attacks) != 1:
                raise ValueError("scenario requires exactly one numeric Shooting profile")
            attack = definition.attacks[0]
            if (attack.skill is not Skill.SHOOTING
                    or attack.range_min is not RangedWeaponRange.MEDIUM
                    or attack.range_max is not RangedWeaponRange.LONG
                    or attack.hands is not RangedWeaponHands.TWO_HANDED
                    or attack.damage.success_multiplier != 1
                    or attack.ignores_armour or attack.secondary_effects
                    or attack.test_profile.pool_cap is not None):
                raise ValueError("unsupported scenario Shooting profile or effects")
            if state.available_attack_ids != (attack.id,):
                raise ValueError("scenario Shooting profile must be available")
            if (not state.wields_weapon or state.holds_shield
                    or state.current_resilience != definition.resilience):
                raise ValueError("unsupported scenario equipment or modified Resilience")
            if (len(definition.protection) != 1
                    or definition.protection[0].skill is not Skill.ATHLETICS
                    or definition.protection[0].test_profile.pool_cap is not None):
                raise ValueError("scenario requires one unmodified Athletics Protection profile")

        policies = tuple(self.actor_policies)
        if not all(isinstance(item, NpcRangedActorPolicy) for item in policies):
            raise TypeError("scenario actor policies must be typed")
        if len(policies) != len(actor_ids) or {item.actor_id for item in policies} != actor_ids:
            raise ValueError("scenario requires exactly one policy per actor")
        for policy in policies:
            side = roster.participant(policy.actor_id).state.side
            enemies = {item.state.actor_id for item in roster.participants if item.state.side is not side}
            if set(policy.target_actor_ids) != enemies:
                raise ValueError("scenario target priorities must contain every enemy exactly once")
            zone = spatial.placement_for(policy.actor_id).zone_id
            for target_id in policy.target_actor_ids:
                target_zone = spatial.placement_for(target_id).zone_id
                if not spatial.graph.are_adjacent(zone, target_zone):
                    raise ValueError("scenario Medium Range requires adjacent enemy Zones")
        enemies = {item.state.actor_id for item in roster.participants
                   if item.state.side is not self.perspective_side}
        if set(self.objective.target_actor_ids) != enemies:
            raise ValueError("scenario objective must name all and only the opposing side")
        object.__setattr__(self, "actor_policies", policies)

    def policy_for(self, actor_id: str) -> NpcRangedActorPolicy:
        for policy in self.actor_policies:
            if policy.actor_id == actor_id:
                return policy
        raise ValueError("unknown scenario actor")
