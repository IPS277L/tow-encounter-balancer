"""Fresh authored Champion-Wizard scenario admission (ADR-0037).

PG1.4 Equipment / Ranged Weapons p94; Rules pp112,114-115,119,122;
Battle Magic / Curse p162. GM1.1 Allies and Antagonists pp91-92.
No runner, RNG, request generation, tactical selection or current-turn admission.
"""
from dataclasses import dataclass, fields

from towr.domain.condition_models import StaggerChoice
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingPolicy
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.magic_models import COWARDLY_FLIGHT_SPELL_DEFINITION, FormalSpellDefinition, WizardMagicState
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scene_models import (
    NpcMagicPairRange, NpcMagicSceneFrame, NpcMagicSceneKey,
    _identifier, _ids, _ordered, validate_magic_scene_frame,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide


@dataclass(frozen=True, slots=True)
class NpcMagicScenarioFacts:
    authored_wizard_profile: bool
    targets_aware: bool
    clear_line_of_sight: bool
    all_combatants_included: bool
    unmounted_combatants_only: bool
    no_additional_rules: bool
    no_other_test_modifiers: bool
    no_cover_or_concealment: bool
    no_terrain_or_obstacles: bool
    no_external_scene_changes: bool
    no_external_condition_sources: bool
    ammunition_sufficient: bool
    requires_reload_action: bool
    knows_battle_magic: bool
    spell_memorised: bool
    no_bulky_items: bool
    no_casting_opposition: bool
    no_mixing_winds: bool
    no_potency_modifiers: bool
    no_effect_immunities: bool

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, bool):
                raise TypeError(f'scenario {item.name} must be an explicit boolean')
            if value is not (item.name != 'requires_reload_action'):
                raise ValueError(f'unsupported magic scenario fact: {item.name}')


@dataclass(frozen=True, slots=True)
class NpcMagicActorPolicy:
    actor_id: str
    willpower_profile: InlineProfile
    speed: MovementSpeed
    target_actor_ids: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]
    attack_id: str | None
    casting_policy: CowardlyFlightCastingPolicy | None
    zone_priorities: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        if not isinstance(self.willpower_profile, InlineProfile):
            raise TypeError('actor Willpower must be an InlineProfile')
        if self.willpower_profile.pool_cap is not None:
            raise ValueError('actor Willpower excludes custom pool caps')
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError('actor Speed must be a MovementSpeed')
        object.__setattr__(self, 'target_actor_ids', _ids(self.target_actor_ids))
        object.__setattr__(self, 'zone_priorities', _ids(self.zone_priorities))
        object.__setattr__(self, 'defeat_decisions', _ordered(
            self.defeat_decisions, MinionDefeatDecision, 'defeat decisions'))
        if self.casting_policy is not None:
            if not isinstance(self.casting_policy, CowardlyFlightCastingPolicy):
                raise TypeError('Casting policy must be typed')
            if (self.attack_id is not None or self.target_actor_ids or self.defeat_decisions
                    or not self.zone_priorities):
                raise ValueError('Wizard policy has only Casting and Zone priorities')
        else:
            _identifier(self.attack_id)
            if self.zone_priorities or not self.target_actor_ids:
                raise ValueError('Minion policy requires Shooting targets and no Casting Zones')


@dataclass(frozen=True, slots=True)
class NpcMagicScenario:
    id: str
    initial: NpcRosterCastingState
    facts: NpcMagicScenarioFacts
    activation_order: tuple[str, ...]
    actors: tuple[NpcMagicActorPolicy, ...]
    scene_frames: tuple[NpcMagicSceneFrame, ...]
    perspective_side: CombatSide
    objective: NpcDefeatObjective
    max_rounds: int
    repeated_stagger_choice: StaggerChoice
    spell: FormalSpellDefinition

    def __post_init__(self) -> None:
        _identifier(self.id)
        for value, kind in ((self.initial, NpcRosterCastingState), (self.facts, NpcMagicScenarioFacts),
                            (self.perspective_side, CombatSide), (self.objective, NpcDefeatObjective),
                            (self.repeated_stagger_choice, StaggerChoice), (self.spell, FormalSpellDefinition)):
            if not isinstance(value, kind):
                raise TypeError(f'magic scenario requires {kind.__name__}')
        if not isinstance(self.max_rounds, int) or isinstance(self.max_rounds, bool):
            raise TypeError('max_rounds must be an integer')
        if self.max_rounds < 1:
            raise ValueError('max_rounds must be positive')
        if self.repeated_stagger_choice is not StaggerChoice.SUFFER_WOUND:
            raise ValueError('scenario requires explicit SUFFER_WOUND repeated Staggered policy')
        if self.spell != COWARDLY_FLIGHT_SPELL_DEFINITION:
            raise ValueError('scenario supports only the canonical Battle Magic Curse definition')
        state = self.initial
        roster, combat, spatial = state.roster, state.round_state, state.spatial_state
        champion = state.champion_attack
        if champion is None:
            raise ValueError('initial scenario requires its Champion attack/daily owner')
        if not all(isinstance(s, CombatSide) for s in combat.side_order):
            raise TypeError('round side order must contain CombatSide values')
        fresh_combat = CombatRoundState(1, roster.turn_participants)
        fresh_spatial = SpatialBattleState(spatial.graph, spatial.placements)
        fresh_champion = NpcChampionAttackState(roster, fresh_combat,
            DailyWoundState(champion.daily_wounds.day_id, state.wizard.actor_id))
        if (state.wizard.magic_state != WizardMagicState()
                or state != NpcRosterCastingState(roster, state.wizard, fresh_combat, fresh_spatial,
                                                 champion_attack=fresh_champion)):
            raise ValueError('scenario requires fresh round/spatial/magic/daily/history without pending')
        ids = tuple(p.state.actor_id for p in roster.participants)
        wizard = roster.participant(state.wizard.actor_id)
        if (not any(p.state.side is wizard.state.side and p is not wizard for p in roster.participants)
                or not any(p.state.side is not wizard.state.side for p in roster.participants)):
            raise ValueError('Wizard requires an allied and an opposing Minion')
        for participant in roster.participants:
            definition, actor = participant.definition, participant.state
            is_wizard = actor.actor_id == state.wizard.actor_id
            healthy = CharacterInjuryState() if is_wizard else ProfileInjuryState(0, 1)
            if actor.injury != healthy:
                raise ValueError('scenario actors must initially be healthy without Conditions')
            if actor.current_resilience != definition.resilience or actor.holds_shield:
                raise ValueError('scenario requires unchanged Resilience and no shields')
            if (len(definition.protection) != 1 or definition.protection[0].skill is not Skill.ATHLETICS
                    or definition.protection[0].test_profile.pool_cap is not None):
                raise ValueError('scenario requires one normal Athletics Protection profile per actor')
            if is_wizard:
                if definition.attacks or actor.available_attack_ids or actor.wields_weapon or actor.current_resilience.is_armoured:
                    raise ValueError('authored Wizard must have no weapon attacks, armour or bulky equipment')
            else:
                if (definition.injury_policy is not TargetInjuryPolicy.MINION or len(definition.attacks) != 1
                        or not actor.wields_weapon):
                    raise ValueError('scenario requires armed numeric Shooting Minions')
                attack = definition.attacks[0]
                ordinary_ranges = (RangedWeaponRange.SHORT, RangedWeaponRange.MEDIUM, RangedWeaponRange.LONG)
                if (attack.skill is not Skill.SHOOTING or attack.range_min not in ordinary_ranges
                        or attack.range_max not in ordinary_ranges or attack.test_profile.pool_cap is not None
                        or attack.ignores_armour or attack.secondary_effects or attack.damage.success_multiplier != 1
                        or actor.available_attack_ids != (attack.id,)):
                    raise ValueError('unsupported numeric Shooting profile, availability or effects')
        order = _ids(self.activation_order)
        if set(order) != set(ids):
            raise ValueError('activation order must contain all actors exactly once')
        actors = _ordered(self.actors, NpcMagicActorPolicy, 'actor policies')
        if tuple(p.actor_id for p in actors) != ids:
            raise ValueError('actor policies must match the complete ordered roster')
        for policy in actors:
            actor = roster.participant(policy.actor_id)
            if policy.actor_id == state.wizard.actor_id:
                if (policy.casting_policy is not CowardlyFlightCastingPolicy.CAST_WHEN_READY
                        or set(policy.zone_priorities) != set(spatial.graph.zone_ids)
                        or policy.willpower_profile != state.wizard.caster.casting_profile):
                    raise ValueError('Wizard requires canonical Casting, complete Zones and current Willpower')
            else:
                enemies = {p.state.actor_id for p in roster.participants if p.state.side is not actor.state.side}
                if policy.casting_policy is not None or policy.attack_id != actor.definition.attacks[0].id:
                    raise ValueError('Minion policy must select its sole numeric attack')
                if set(policy.target_actor_ids) != enemies:
                    raise ValueError('target priorities must contain all hostile actors, including the Wizard')
                targets = tuple(t for t in policy.target_actor_ids if t != state.wizard.actor_id)
                if (tuple(d.target_id for d in policy.defeat_decisions) != targets
                        or any(d.attacker_id != policy.actor_id or not d.gm_approved for d in policy.defeat_decisions)):
                    raise ValueError('Minion-target defeat decisions must match priority/attacker with GM approval')
        opponents = {p.state.actor_id for p in roster.participants if p.state.side is not self.perspective_side}
        if set(self.objective.target_actor_ids) != opponents:
            raise ValueError('objective must name all and only the opposing perspective side')
        scene_frames = _ordered(self.scene_frames, NpcMagicSceneFrame, 'scene frames')
        keys = tuple(frame.key for frame in scene_frames)
        if len(set(keys)) != len(keys):
            raise ValueError('scene frame keys must be unique')
        initial_key = NpcMagicSceneKey(spatial.placements, ids)
        if initial_key not in keys:
            raise ValueError('scenario requires its exact initial scene frame')
        for frame in scene_frames:
            validate_magic_scene_frame(frame, state, {p.actor_id: p.speed for p in actors})
        frame = scene_frames[keys.index(initial_key)]
        for policy in actors:
            actor = roster.participant(policy.actor_id)
            if policy.actor_id == state.wizard.actor_id:
                enemy_zones = {spatial.placement_for(p.state.actor_id).zone_id for p in roster.participants
                               if p.state.side is not wizard.state.side}
                if not any(z.zone_id in enemy_zones and z.target_range is not RangedWeaponRange.EXTREME
                           for z in frame.zone_ranges):
                    raise ValueError('Wizard requires an initial enemy Zone within Long')
            else:
                pairs = tuple(p for p in frame.pair_ranges if policy.actor_id in (p.first_actor_id, p.second_actor_id))
                if any(p.target_range is RangedWeaponRange.CLOSE for p in pairs):
                    raise ValueError('initial Shooting actor must have no hostile actor in Close')
                attack = actor.definition.attacks[0]
                def available(pair: NpcMagicPairRange) -> bool:
                    approval = (pair.first_range_approved_by_gm if pair.first_actor_id == policy.actor_id
                                else pair.second_range_approved_by_gm)
                    return pair.target_range is not RangedWeaponRange.EXTREME and (
                        attack.hands is RangedWeaponHands.ONE_HANDED
                        or tuple(RangedWeaponRange).index(pair.target_range) <= tuple(RangedWeaponRange).index(attack.range_max)
                        or approval)
                if not any(available(p) for p in pairs):
                    raise ValueError('every Minion requires an initially available Shooting target')
        object.__setattr__(self, 'activation_order', order)
        object.__setattr__(self, 'actors', actors)
        object.__setattr__(self, 'scene_frames', scene_frames)

    @property
    def initial_frame(self) -> NpcMagicSceneFrame:
        key = NpcMagicSceneKey(self.initial.spatial_state.placements,
                              tuple(p.state.actor_id for p in self.initial.roster.participants))
        return next(frame for frame in self.scene_frames if frame.key == key)

    def frame_for(self, key: NpcMagicSceneKey) -> NpcMagicSceneFrame | None:
        if not isinstance(key, NpcMagicSceneKey):
            raise TypeError('frame lookup requires a typed scene key')
        return next((frame for frame in self.scene_frames if frame.key == key), None)

    def policy_for(self, actor_id: str) -> NpcMagicActorPolicy:
        _identifier(actor_id)
        for actor in self.actors:
            if actor.actor_id == actor_id:
                return actor
        raise ValueError('unknown scenario policy actor')
