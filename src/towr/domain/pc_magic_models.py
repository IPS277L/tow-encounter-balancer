"""Bounded PC Casting, direct spell effects and mandatory Miscast journal phases."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.magic_models import (WizardMagicState, CastingTestRequest, CastingTestResult,
    CastingChoice, CastingDecisionRequest, CastingSpellSelection, MiscastPreparationRequest,
    MiscastRollRequest, MiscastRollResult, SpellCastRequest, IdentifiedSpellTarget,
    SpellTargetPreflightRequest, SpellCastExecutionResult,SpellPotencyModifier,SpellPotencyRequest)
from towr.domain.action_execution_models import (CastingAttemptExecutionRequest, CastingAttemptExecutionResult,
    CastingActionPostTestRequest, CastingActionPostTestResult, CastingActionMiscastPreparationRequest,
    CastingActionMiscastPreparationResult, SkippedCastingTestAfterActionRequest,SkippedCastingTestAfterActionResult)
from towr.domain.magic_models import MiscastPoolResolutionResult,MiscastPreparationResult,MiscastTableEntryId
from towr.domain.resolution_models import StaggerImpactResult
from towr.domain.injury_models import ProfileInjuryState, ProfileWoundResult
from towr.domain.condition_models import ConditionApplicationResult
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleRollResult,FixedCharacterWoundLifecycleCompletionResult
from towr.domain.pc_magic_source_models import (PcSpellId, pc_spell_definition, pc_spell_damage,
    ELEMENTALISM_LORE_ID)
from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind, pc_miscast_tasks
from towr.domain.test_models import TestResult, DiceModifier, QualityModifier, TestQuality, Skill
from towr.domain.turn_models import CombatActionKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState, PcFateDecline
    from towr.domain.fate_models import FateGloriousSpendResult
    from towr.domain.npc_roster_models import NpcParticipantSnapshot


@dataclass(frozen=True, slots=True)
class PcMagicPending:
    caster_id: str
    source_id: str
    tasks: tuple[PcMagicTask, ...] = ()
    miscast_request: MiscastRollRequest | None = None
    miscast_roll: MiscastRollResult | None = None

    def __post_init__(self):
        if any(type(value) is not str or not value for value in (self.caster_id,self.source_id)):
            raise ValueError('pending magic requires its actor and origin')
        if type(self.tasks) is not tuple or any(type(task) is not PcMagicTask for task in self.tasks):
            raise TypeError('pending magic requires exact ordered tasks')
        for task in self.tasks:
            replace(task)
        if len({task.id for task in self.tasks}) != len(self.tasks):
            raise ValueError('a magic task cannot repeat')
        for value, cls in ((self.miscast_request,MiscastRollRequest),(self.miscast_roll,MiscastRollResult)):
            if value is not None:
                if type(value) is not cls:
                    raise TypeError('pending Miscast must retain its typed source')
                replace(value)
        if self.miscast_request is not None and self.miscast_roll is not None:
            raise ValueError('an actual Miscast cannot await another roll')


@dataclass(frozen=True, slots=True)
class PcMagicModifier:
    source_id: str
    target_id: str
    kind: PcMagicTaskKind

    def __post_init__(self):
        if any(type(value) is not str or not value for value in (self.source_id,self.target_id)):
            raise ValueError('magic modifier requires actor/source IDs')
        if type(self.kind) is not PcMagicTaskKind or self.kind not in (PcMagicTaskKind.PRONE,
                PcMagicTaskKind.BLINDED,PcMagicTaskKind.NEXT_TEST_PENALTY,
                PcMagicTaskKind.FELLOWSHIP_GRIM,PcMagicTaskKind.AWARENESS_GRIM):
            raise ValueError('unknown supported magic modifier')

    @property
    def condition(self):
        return {PcMagicTaskKind.PRONE: Condition.PRONE,
            PcMagicTaskKind.BLINDED: Condition.BLINDED}.get(self.kind)


@dataclass(frozen=True, slots=True)
class PcCastingProof:
    request: CastingAttemptExecutionRequest
    execution: CastingAttemptExecutionResult
    post_test: CastingActionPostTestResult
    preparation: CastingActionMiscastPreparationResult | None
    spell_id: PcSpellId | None
    targets: SpellCastExecutionResult | None
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None

    @property
    def actor_id(self):
        return self.request.actor_id


@dataclass(frozen=True, slots=True)
class PcMagicInterruptionProof:
    actor_id: str
    source_action_id: str
    result: SkippedCastingTestAfterActionResult | MiscastPoolResolutionResult
    preparation: MiscastPreparationResult | None


@dataclass(frozen=True, slots=True)
class PcMiscastRollProof:
    request: MiscastRollRequest
    result: MiscastRollResult

    @property
    def actor_id(self):
        return self.request.target_id


@dataclass(frozen=True, slots=True)
class PcMagicEffectProof:
    task: PcMagicTask
    result: (StaggerImpactResult | ProfileWoundResult | ConditionApplicationResult
        | CharacterWoundLifecycleRollResult | FixedCharacterWoundLifecycleCompletionResult | None) = None
    decision: MinionDefeatDecision | None = None
    previous_injury: ProfileInjuryState | None = field(default=None, kw_only=True)

    def __post_init__(self):
        if self.previous_injury is not None:
            if type(self.previous_injury) is not ProfileInjuryState:
                raise TypeError('companion magic effect retains its exact own profile before snapshot')
            replace(self.previous_injury)


@dataclass(frozen=True, slots=True)
class PcMagicCleanupProof:
    source_id: str


@dataclass(frozen=True, slots=True)
class PcMagicUnsupported:
    actor_id: str
    source_id: str
    entry_id: str
    total: int
    reason: str = 'pc_magic_miscast_unresolved'

    def __post_init__(self):
        if (any(type(value) is not str or not value for value in
                (self.actor_id, self.source_id, self.entry_id)) or type(self.total) is not int or self.total < 1
                or self.reason != 'pc_magic_miscast_unresolved'):
            raise ValueError('magic unsupported must retain its actual roll and entry')


MAGIC_PROOFS = (PcCastingProof, PcMagicInterruptionProof, PcMiscastRollProof,
    PcMagicEffectProof, PcMagicCleanupProof)


def magic_hand(state, actor):
    from towr.domain.pc_potion_models import pc_potion_hand
    return pc_potion_hand(state.participant(actor))


def magic_test_modifiers(state, actor, skill):
    dice, qualities = [], []
    from towr.domain.pc_oath_models import honour_quality_modifiers
    qualities.extend(honour_quality_modifiers(state, actor))
    for modifier in state.magic_modifiers:
        if modifier.target_id != actor:
            continue
        if modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY:
            dice.append(DiceModifier(modifier.source_id, -1))
        elif modifier.kind is PcMagicTaskKind.FELLOWSHIP_GRIM and skill in (Skill.CHARM, Skill.LEADERSHIP):
            qualities.append(QualityModifier(modifier.source_id, TestQuality.GRIM))
        elif modifier.kind is PcMagicTaskKind.AWARENESS_GRIM and skill is Skill.AWARENESS:
            qualities.append(QualityModifier(modifier.source_id, TestQuality.GRIM))
    return tuple(dice), tuple(qualities)


def external_magic_conditions(state, actor):
    return frozenset(modifier.condition for modifier in state.magic_modifiers
        if modifier.target_id == actor and modifier.condition is not None)


def consume_magic_modifiers(modifiers, proof):
    """Consume only modifiers proven by an actual Test or standard Recover."""
    from towr.domain.recover_models import RecoverStandardResult
    used, removed, visited = set(), set(), set()
    paths = {'execution','resolution','result','casting','test','test_result','attack',
        'attacker_test','defender_test','critical','completion','wound_effect','exacting','awareness_test_result','athletics_test_result',
        'help_test_result'}
    def visit(value):
        if id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, TestResult):
            used.update(value.trace.applied_rule_ids)
        elif isinstance(value, RecoverStandardResult):
            removed.update((change.entity_id,condition) for change in value.condition_changes
                for condition in change.removed_conditions)
        elif is_dataclass(value):
            for field in fields(value):
                if field.name in paths:
                    visit(getattr(value,field.name))
    visit(proof)
    return tuple(modifier for modifier in modifiers
        if not (modifier.kind is PcMagicTaskKind.NEXT_TEST_PENALTY and modifier.source_id in used)
        and (modifier.target_id,modifier.condition) not in removed)


def guarded_casting_test(request):
    from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock
    return replace(request.test, reroll_locks=(*request.test.reroll_locks,rule_of_nine_reroll_lock()))


def build_pc_casting_request(state):
    from towr.domain.pc_melee_result_models import _pc_test, pc_melee_action_id
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order:
        raise ValueError('Casting requires an actual PC Wizard, not a passive profile body')
    wizard = state.source.participant(actor).wizard
    member = state.participant(actor)
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if actor_bound_to_chivalric_combat(state,actor):
        raise ValueError('Agilulf chivalric combat cannot replace hand-to-hand combat with an offensive spell')
    if wizard is None or member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS) or magic_hand(state,actor) is None:
        raise ValueError('Casting requires a living able Wizard and a usable hand')
    action_id = pc_melee_action_id(state,actor)
    request = CastingTestRequest(action_id+':casting',actor,ELEMENTALISM_LORE_ID,
        _pc_test(state,actor,action_id+':willpower',Skill.WILLPOWER,casting=True),member.magic)
    return CastingAttemptExecutionRequest(action_id+':casting:execute',state.round_state,actor,1,request)


def _spell_target_ids(state, actor):
    """Original priorities precede actual opposing retained profile bodies."""
    from towr.domain.pc_actor_models import pc_opponent_ids, pc_companion
    opponents = pc_opponent_ids(state, actor)
    priority = state.source.participant(actor).target_priority
    return (*tuple(target for target in priority if target in opponents),
        *tuple(target for target in opponents if pc_companion(state, target) is not None))


def spell_choice(state, actor, potency, *, maximum_targets=None):
    """Choose spell and distinct current targets using printed direct Damage."""
    if potency < 1:
        return None, (), 0.0
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    live = [pc_actor_npc_snapshot(state, target) for target in _spell_target_ids(state, actor)]
    best = (None, (), 0.0)
    for spell in state.source.participant(actor).wizard.memorised_spells:
        quota = potency if spell is PcSpellId.FIRE_BREATH else 1
        if maximum_targets is not None:
            quota = min(quota, maximum_targets)
        definition = pc_spell_definition(spell)
        values = []
        for enemy in live:
            if state.battlefield is not None:
                from towr.domain.pc_battlefield_models import battlefield_range
                from towr.domain.ranged_weapon_profiles import RangedWeaponRange
                if tuple(RangedWeaponRange).index(battlefield_range(state.battlefield,actor,enemy.state.actor_id)) > tuple(RangedWeaponRange).index(RangedWeaponRange(definition.range.value)):
                    continue
            modifiers = generated_spell_potency_modifiers(enemy)
            effective_potency = potency
            if modifiers:
                from towr.rules.spell_potency_resolution import resolve_spell_potency
                effective_potency = resolve_spell_potency(SpellPotencyRequest(
                    'pc-magic:advice:'+enemy.state.actor_id,definition.rule_id,
                    enemy.state.actor_id,potency,modifiers)).effective_potency
            resilience = enemy.state.current_resilience
            value = (0.0 if effective_potency == 0 else
                1.0 if (pc_spell_damage(spell,effective_potency,resilience.is_armoured) > resilience.total
                    or enemy.state.injury.conditions.has(Condition.STAGGERED)) else 0.5)
            values.append((enemy.state.actor_id,value))
        values.sort(key=lambda item:-item[1])
        if spell is PcSpellId.FIRE_BREATH and state.battlefield is not None:
            spatial=state.battlefield.spatial
            zones=tuple(dict.fromkeys(spatial.placement_for(target).zone_id for target,_ in values))
            groups=tuple(tuple(item for item in values if spatial.placement_for(item[0]).zone_id == zone)[:quota]
                for zone in zones)
            selected=max(groups,key=lambda group:sum(value for _,value in group),default=())
        else:
            selected = values[:quota]
        utility = sum(value for _,value in selected)
        if utility > best[2]+1e-12:
            best = spell, tuple(target for target,_ in selected), utility
    return best


def generated_spell_potency_modifiers(enemy: NpcParticipantSnapshot) -> tuple[SpellPotencyModifier,...]:
    """A passive acquired Talent affects cast spells, including when Drained.

    This contributes to each actual target's K1 Potency request. It is not a
    blanket immunity to magic or a modifier for raw Miscast consequences.
    """
    from towr.domain.generated_npc_models import TalentId
    from towr.rules.stone_troll import magic_resistance_spell_potency_modifier
    components = enemy.definition.generated_components
    from towr.domain.talent_models import has_talent
    if components is not None and has_talent(components.talents,TalentId.MAGIC_RESISTANCE):
        return (magic_resistance_spell_potency_modifier(),)
    return ()


def complete_pc_casting(state, test, decline, glorious):
    from towr.rules.casting_test_resolution import _complete_casting_test
    from towr.rules.casting_action_execution import (_complete_casting_attempt_after_test,
        resolve_casting_action_post_test, prepare_casting_action_miscast)
    from towr.rules.spell_target_preflight import resolve_spell_target_preflight
    from towr.rules.spell_cast_execution import resolve_spell_cast_targets
    request = build_pc_casting_request(state)
    wizard = state.source.participant(request.actor_id).wizard
    casting = _complete_casting_test(request.casting_request,test)
    execution = _complete_casting_attempt_after_test(request,casting)
    post_pool = replace(casting.state,miscast_dice=casting.state.miscast_dice+casting.miscast_dice_added)
    spell, targets, _ = spell_choice(state,request.actor_id,casting.latest_roll_successes,
        maximum_targets=1 if test.honour_bound is not None else None)
    if post_pool.casting_successes < 2:
        spell, targets = None, ()
    selection = (CastingSpellSelection(pc_spell_definition(spell).rule_id,ELEMENTALISM_LORE_ID,2)
        if spell is not None else None)
    decision = None if post_pool.miscast_dice > wizard.wizard_level else CastingDecisionRequest(
        request.id+':decision',request.actor_id,post_pool,wizard.wizard_level,
        CastingChoice.CAST if selection is not None else CastingChoice.WAIT,selection)
    post = resolve_casting_action_post_test(CastingActionPostTestRequest(request.id+':post',execution,
        wizard.wizard_level,decision))
    preparation = None
    if post_pool.miscast_dice > wizard.wizard_level:
        preparation = prepare_casting_action_miscast(CastingActionMiscastPreparationRequest(
            request.id+':miscast',post, MiscastPreparationRequest(request.id+':prepare',
                post.miscast_pool.roll_request,post.state,selection)))
    casts = preparation.preparation.follow_ups if preparation is not None else post.decision.follow_ups
    source = next((value for value in casts if isinstance(value,SpellCastRequest)),None)
    resolved = None
    if source is not None:
        definition = pc_spell_definition(spell)
        from towr.domain.pc_actor_models import pc_actor_npc_snapshot
        affected = tuple(IdentifiedSpellTarget(target,
            generated_spell_potency_modifiers(pc_actor_npc_snapshot(state, target))) for target in targets)
        subject = ((state.battlefield.spatial.placement_for(targets[0]).zone_id
            if state.battlefield is not None else state.source.facts.zone_id)
            if spell is PcSpellId.FIRE_BREATH else targets[0])
        preflight = resolve_spell_target_preflight(SpellTargetPreflightRequest(request.id+':preflight',source,
            definition,subject,definition.target_kind,True,affected))
        resolved = resolve_spell_cast_targets(preflight.execution_request)
    return PcCastingProof(request,execution,post,preparation,spell if source is not None else None,
        resolved,decline,glorious)


def casting_pending(proof, state):
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    spell_source = (proof.preparation.preparation.follow_ups if proof.preparation is not None
        else proof.post_test.decision.follow_ups)
    tasks = ()
    if proof.targets is not None:
        tasks = tuple(PcMagicTask(effect.resolution_id,PcMagicTaskKind.DAMAGE,effect.target_id,
            pc_spell_damage(proof.spell_id,effect.potency,
                pc_actor_npc_snapshot(state,effect.target_id).state.current_resilience.is_armoured))
            for effect in proof.targets.follow_ups)
    roll = next((value for value in spell_source if isinstance(value,MiscastRollRequest)),None)
    return PcMagicPending(proof.actor_id,proof.request.id,tasks,roll) if tasks or roll is not None else None


def expected_magic_interruption(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.magic_models import MiscastPoolIncreaseRequest,MiscastPoolIncreaseSourceKind,MiscastPoolResolutionRequest
    from towr.rules.casting_interruption_resolution import resolve_skipped_casting_test_after_action
    from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase
    from towr.rules.miscast_resolution import prepare_miscast
    turn = state.round_state.active_turn
    if turn is None or state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    if turn.actor_id not in state.source.pc_activation_order:
        return None
    wizard = state.source.participant(turn.actor_id).wizard
    member = state.participant(turn.actor_id)
    if wizard is None or member.magic.casting_lore_id is None or member.injury.dead:
        return None
    receipt = turn.action_slots[-1].execution if turn.action_slots else None
    if turn.action_slots and (receipt is None or turn.action_slots[-1].declaration.improvise_approach_id == ELEMENTALISM_LORE_ID):
        return None
    if receipt is None and not member.injury.conditions.has(Condition.DEFENCELESS):
        return None
    source_id = receipt.id if receipt is not None else pc_melee_action_id(state,turn.actor_id)+':incapacitated'
    consumed = tuple(p.source_action_id for p in state.history if type(p) is PcMagicInterruptionProof)
    if source_id in consumed:
        return None
    from towr.domain.pc_demigryph_models import build_pc_demigryph_strike
    if build_pc_demigryph_strike(state) is not None:
        return None  # The same Attack action still has its committed mount strike.
    identifier = source_id+':skipped-casting'
    if receipt is not None:
        result = resolve_skipped_casting_test_after_action(SkippedCastingTestAfterActionRequest(
            identifier,turn.actor_id,receipt,member.magic,wizard.wizard_level,consumed))
        pool = result.miscast_pool
    else:
        source = MiscastPoolIncreaseRequest(identifier+':increase',turn.actor_id,1,
            MiscastPoolIncreaseSourceKind.ACTION,source_id,'RULE-MAGIC-004:skipped-casting-test')
        result = pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest(
            identifier,source,member.magic,wizard.wizard_level))
    prepared = (prepare_miscast(MiscastPreparationRequest(identifier+':prepare',pool.roll_request,pool.state))
        if pool.roll_request is not None else None)
    return PcMagicInterruptionProof(turn.actor_id,source_id,result,prepared)


def _miscast_tasks_for_state(state, entry, source_id, caster_id, *, support_check=False):
    """Snapshot actual subjects by role and the printed PG159 range.

    A retained allied animal is a profile NPC, not a PC injury/Fate owner.
    Mounted pairs stay one target. Original roster order is kept, followed by
    source-ordered retained bodies, at the moment of the actual Miscast roll.
    """
    from towr.domain.pc_actor_models import pc_active_actor_ids
    from towr.domain.pc_battlefield_models import battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    live=frozenset(pc_active_actor_ids(state))
    party=tuple(actor for actor in state.source.pc_activation_order
        if actor in live or support_check and actor==caster_id)
    npcs=(*tuple(actor for actor in state.source.enemy_activation_order if actor in live),
        *tuple(row.snapshot.state.actor_id for row in state.companions
            if row.snapshot.state.actor_id in live))
    ranges={MiscastTableEntryId.SENSE_OF_LOSS:RangedWeaponRange.MEDIUM,
        MiscastTableEntryId.NAUSEATING_WAVE:RangedWeaponRange.SHORT,
        MiscastTableEntryId.FOOD_SPOILED:RangedWeaponRange.LONG,
        MiscastTableEntryId.ARCANE_SPILL:RangedWeaponRange.SHORT,
        MiscastTableEntryId.HIDEOUS_STENCH:RangedWeaponRange.SHORT,
        MiscastTableEntryId.UNNATURAL_WIND:RangedWeaponRange.SHORT,
        MiscastTableEntryId.EAR_DAMAGE:RangedWeaponRange.SHORT}
    maximum=ranges.get(entry)
    if maximum is not None and state.battlefield is not None:
        bands=tuple(RangedWeaponRange)
        def in_range(actor):
            return actor==caster_id or bands.index(battlefield_range(state.battlefield,caster_id,actor))<=bands.index(maximum)
        party=tuple(actor for actor in party if in_range(actor))
        npcs=tuple(actor for actor in npcs if in_range(actor))
    return pc_miscast_tasks(entry,source_id,caster_id,party,npcs)


def pc_magic_unsupported(state):
    pending = state.magic_pending
    if pending is None or pending.miscast_roll is None or pending.tasks or state.pending or state.pending_wound is not None:
        return None
    roll = pending.miscast_roll
    if _miscast_tasks_for_state(state,roll.entry.id,roll.request_id+':effect',pending.caster_id,
            support_check=True) is None:
        return PcMagicUnsupported(pending.caster_id,roll.request_id,roll.entry.id.value,roll.total)
    return None


class _ReplayD10:
    def __init__(self, values):
        self.values, self.index = tuple(values), 0
    def randint(self, lower, upper):
        if self.index == len(self.values):
            raise ValueError('magic proof omitted required random dice')
        value = self.values[self.index]
        self.index += 1
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError('magic proof contains a malformed random die')
        return value
    def exhausted(self):
        if self.index != len(self.values):
            raise ValueError('magic proof added unrelated random dice')


def build_magic_effect(state, rng):
    """Resolve exactly one committed task using existing typed rule owners."""
    from towr.domain.injury_models import (CharacterWoundRequest, FixedCharacterWoundRequest,
        ProfileWoundRequest,ProfileNpcType,WoundEntryId,FixedWoundSelection)
    from towr.domain.wound_lifecycle_models import (CharacterWoundLifecycleRollRequest,
        FixedCharacterWoundLifecycleRequest, FixedCharacterWoundLifecycleCompletionRequest)
    from towr.rules.wound_lifecycle_resolution import (roll_character_wound_lifecycle,
        begin_fixed_character_wound_lifecycle,complete_fixed_character_wound_lifecycle)
    from towr.domain.condition_models import ConditionApplicationRequest
    from towr.rules.condition_effect_resolution import resolve_condition_application
    from towr.domain.resolution_models import StaggerImpactRequest,TargetInjuryPolicy
    from towr.rules.stagger_impact_resolution import resolve_stagger_impact
    from towr.rules.injury_resolution import resolve_profile_wound
    from towr.domain.pc_warped_form_models import WarpedFormDecisions
    from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_snapshot, pc_companion
    from towr.domain.pc_oath_models import pc_oath_wound_options, LadyWoundDecisions
    task = state.magic_pending.tasks[0]
    options = pc_oath_wound_options(state,task.target_id)
    decisions = LadyWoundDecisions(WarpedFormDecisions())
    is_pc = task.target_id in state.source.pc_activation_order
    injury = pc_actor_injury(state, task.target_id)
    companion = pc_companion(state, task.target_id)
    previous = injury if companion is not None else None
    if (injury.dead if is_pc else injury.defeated) and task.kind is not PcMagicTaskKind.NOTE:
        return PcMagicEffectProof(task, previous_injury=previous)
    result = decision = None
    if task.kind in (PcMagicTaskKind.DAMAGE,PcMagicTaskKind.FIXED_EARS) and not is_pc:
        enemy = pc_actor_npc_snapshot(state, task.target_id)
        if task.kind is PcMagicTaskKind.FIXED_EARS or task.value > enemy.state.current_resilience.total:
            result = resolve_profile_wound(ProfileWoundRequest(task.id+':wound',
                ProfileNpcType(enemy.definition.injury_policy.value),injury,negation_options=options),
                decisions=decisions)
        else:
            from towr.domain.pc_undead_minion_models import pc_undead_minion_source
            from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec
            undead = undead_minion_stagger_defeat_spec(pc_undead_minion_source(state,task.target_id),task.target_id)
            request = StaggerImpactRequest(task.id,task.target_id,enemy.definition.injury_policy,
                injury,False,False,minion_stagger_defeat=undead,wound_negation_options=options)
            result = resolve_stagger_impact(request,rng,decisions=decisions)
        if result.state.defeated and companion is None:
            decision = next(d for d in state.source.participant(state.magic_pending.caster_id).defeat_decisions
                if d.target_id == task.target_id)
    elif task.kind is PcMagicTaskKind.STAGGER:
        from towr.domain.talent_injury_models import hardy_wound_dice_modifiers
        if is_pc:
            request = StaggerImpactRequest(task.id,task.target_id,TargetInjuryPolicy.PLAYER,
                injury,False,False,wound_dice_modifiers=hardy_wound_dice_modifiers(
                    state.source.participant(task.target_id).talents),wound_negation_options=options)
        else:
            from towr.domain.pc_undead_minion_models import pc_undead_minion_source
            from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec
            enemy = pc_actor_npc_snapshot(state,task.target_id)
            request = StaggerImpactRequest(task.id,task.target_id,enemy.definition.injury_policy,
                injury,False,False,minion_stagger_defeat=undead_minion_stagger_defeat_spec(
                    pc_undead_minion_source(state,task.target_id),task.target_id),wound_negation_options=options)
        result = resolve_stagger_impact(request,rng,decisions=decisions)
    elif task.kind is PcMagicTaskKind.RANDOM_WOUND:
        from towr.domain.talent_injury_models import prepare_hardy_wound
        result = roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest(task.id,task.target_id,
            prepare_hardy_wound(CharacterWoundRequest(task.id+':wound',injury,negation_options=options),
                state.source.participant(task.target_id).talents)),rng,decisions=decisions)
    elif task.kind is PcMagicTaskKind.FIXED_EARS:
        if options:
            # Named-entry character lifecycle supplies the same actual fixed
            # Wound without dice. Negation precedes Deafened/daily registration.
            result = roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest(
                task.id,task.target_id,CharacterWoundRequest(task.id+':wound',injury,
                    negation_options=options,fixed_entry=FixedWoundSelection(
                        WoundEntryId.EARS_RINGING,11,'RULE-MISCAST-TABLE:ear_damage'))),
                rng,decisions=decisions)
            return PcMagicEffectProof(task,result,decision,previous_injury=previous)
        pending = begin_fixed_character_wound_lifecycle(FixedCharacterWoundLifecycleRequest(task.id,task.target_id,
            FixedCharacterWoundRequest(task.id+':wound',injury,WoundEntryId.EARS_RINGING,11,
                'RULE-MISCAST-TABLE:ear_damage')))
        consumed = tuple(p.result.source_request.pending.request_id for p in state.history
            if type(p) is PcMagicEffectProof and p.task.kind is PcMagicTaskKind.FIXED_EARS
                and p.task.target_id in state.source.pc_activation_order
                and type(p.result) is FixedCharacterWoundLifecycleCompletionResult)
        result = complete_fixed_character_wound_lifecycle(FixedCharacterWoundLifecycleCompletionRequest(
            task.id+':complete',pending,pending.wound_result.state,state.participant(task.target_id).daily_wounds,
            task.id+':daily',consumed))
    elif task.kind in (PcMagicTaskKind.PRONE,PcMagicTaskKind.BLINDED):
        from towr.domain.pc_undead_minion_models import pc_undead_minion_source
        from towr.domain.undead_minion_models import undead_minion_effect_immunities
        condition = Condition.PRONE if task.kind is PcMagicTaskKind.PRONE else Condition.BLINDED
        result = resolve_condition_application(ConditionApplicationRequest(task.id,injury.conditions,condition,
            'RULE-MISCAST-TABLE:'+task.note.value, immunities=undead_minion_effect_immunities(
                pc_undead_minion_source(state,task.target_id),task.target_id)))
    return PcMagicEffectProof(task,result,decision,previous_injury=previous)


def effect_replay_dice(proof):
    from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleRollResult
    from towr.domain.resolution_models import StaggerImpactResult
    if isinstance(proof.result, CharacterWoundLifecycleRollResult):
        return _ReplayD10(proof.result.wound_result.table_roll.values)
    if isinstance(proof.result, StaggerImpactResult) and proof.result.character_wound is not None:
        return _ReplayD10(proof.result.character_wound.table_roll.values)
    return _ReplayD10(())


def project_pc_magic_step(state, proof):
    from towr.domain.pc_melee_result_models import (_ready,_party_update,_enemy_update,
        pc_melee_selected_action,pc_after_test,validate_pc_melee_source_types)
    from towr.domain.pc_heavy_wound_models import critical_for_action
    from towr.domain.pc_fate_test_models import validate_pc_test_fate
    from towr.rules.miscast_resolution import resolve_miscast_roll
    from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update, pc_companion

    def same(actual, expected):
        if actual != expected:
            raise ValueError('magic proof changed its canonical current actor, effect, receipt or source')
        validate_pc_melee_source_types(actual,expected)

    def finish(**updates):
        updates.setdefault('magic_modifiers',consume_magic_modifiers(state.magic_modifiers,proof))
        return replace(state,history=(*state.history,proof),**updates)

    if state.pending or state.pending_wound is not None:
        raise ValueError('magic cannot skip an actual pending Wound consequence')
    if type(proof) is PcCastingProof:
        _ready(state)
        from towr.domain.pc_melee_result_models import pc_is_casting_action
        if not pc_is_casting_action(state):
            raise ValueError('Casting cannot replace the selected action')
        expected = build_pc_casting_request(state)
        same(proof.request,expected)
        test = proof.execution.casting.test
        _,fate = validate_pc_test_fate(state,proof.actor_id,Skill.WILLPOWER,
            guarded_casting_test(expected.casting_request),test,proof.fate_decline,proof.glorious)
        canonical = complete_pc_casting(state,test,proof.fate_decline,proof.glorious)
        same(proof,canonical)
        actor = proof.actor_id
        magic = proof.preparation.preparation.state if proof.preparation is not None else proof.post_test.state
        injury = pc_after_test(state,actor,critical_for_action(state.participant(actor),
            CombatActionKind.IMPROVISE,used_hand=magic_hand(state,actor)))
        return finish(round_state=proof.execution.state,party=_party_update(state,actor,injury=injury,fate=fate,magic=magic),
            magic_pending=casting_pending(proof,state))
    if type(proof) is PcMagicInterruptionProof:
        expected = expected_magic_interruption(state)
        if expected is None:
            raise ValueError('no actual non-Casting opportunity was skipped')
        same(proof,expected)
        magic = proof.preparation.state if proof.preparation is not None else proof.result.state
        roll = proof.preparation.follow_ups[-1] if proof.preparation is not None else None
        return finish(party=_party_update(state,proof.actor_id,magic=magic),magic_pending=(
            PcMagicPending(proof.actor_id,proof.source_action_id,(),roll) if roll is not None else None))
    pending = state.magic_pending
    if pending is None:
        raise ValueError('magic phase is detached from an actual Casting or interruption')
    if type(proof) is PcMiscastRollProof:
        if pending.tasks or pending.miscast_request is None:
            raise ValueError('spell targets must finish before the actual Miscast roll')
        same(proof.request,pending.miscast_request)
        dice = _ReplayD10(proof.result.roll_values)
        result = resolve_miscast_roll(pending.miscast_request,state.participant(pending.caster_id).magic,dice)
        dice.exhausted()
        same(proof.result,result)
        tasks = _miscast_tasks_for_state(state,result.entry.id,result.request_id+':effect',pending.caster_id)
        return finish(magic_pending=replace(pending,tasks=tasks or (),miscast_request=None,miscast_roll=result))
    if type(proof) is PcMagicEffectProof:
        if not pending.tasks:
            raise ValueError('magic effect has no committed next target')
        same(proof.task,pending.tasks[0])
        dice = effect_replay_dice(proof)
        canonical = build_magic_effect(state,dice)
        dice.exhausted()
        same(proof,canonical)
        task, result = proof.task, proof.result
        updates = dict(magic_pending=replace(pending,tasks=pending.tasks[1:]))
        is_pc = task.target_id in state.source.pc_activation_order
        injury = pc_actor_injury(state, task.target_id)
        active = not (injury.dead if is_pc else injury.defeated)
        if task.kind in (PcMagicTaskKind.DAMAGE,PcMagicTaskKind.FIXED_EARS) and not is_pc and active:
            changed = result.state
            if pc_companion(state, task.target_id) is not None:
                from towr.domain.pc_companion_effect_models import companion_profile, companion_wound_band_injury
                changed = companion_wound_band_injury(companion_profile(state, task.target_id), changed)
            updates.update(pc_actor_npc_update(state, task.target_id, injury=changed))
            combat = state.round_state
            if (result.state.defeated and task.target_id in tuple(row.entity_id for row in combat.participants)
                    and task.target_id not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids)):
                updates['round_state'] = replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,task.target_id))
        elif task.kind is PcMagicTaskKind.STAGGER and active:
            if is_pc:
                updates.update(party=_party_update(state,task.target_id,injury=result.state),pending=result.follow_ups,
                    pending_wound=result.pending_character_wound,
                    pending_actor_id=task.target_id if result.follow_ups or result.pending_character_wound is not None else None)
            else:
                changed = result.state
                if pc_companion(state,task.target_id) is not None:
                    from towr.domain.pc_companion_effect_models import companion_profile, companion_wound_band_injury
                    changed = companion_wound_band_injury(companion_profile(state,task.target_id),changed)
                updates.update(pc_actor_npc_update(state,task.target_id,injury=changed))
                combat=state.round_state
                if (changed.defeated and task.target_id in tuple(row.entity_id for row in combat.participants)
                        and task.target_id not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids)):
                    updates['round_state']=replace(combat,
                        active_turn=None if combat.active_turn is not None and combat.active_turn.actor_id==task.target_id
                            else combat.active_turn,
                        excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,task.target_id))
        elif task.kind is PcMagicTaskKind.RANDOM_WOUND and active:
            updates.update(party=_party_update(state,task.target_id,injury=result.wound_result.state),
                pending_wound=result,pending_actor_id=task.target_id)
        elif task.kind is PcMagicTaskKind.FIXED_EARS and active:
            if type(result) is CharacterWoundLifecycleRollResult:
                updates.update(party=_party_update(state,task.target_id,injury=result.wound_result.state),
                    pending_wound=result,pending_actor_id=task.target_id)
            else:
                updates.update(party=_party_update(state,task.target_id,injury=result.state,daily_wounds=result.daily_wounds),
                    pending=result.wound_effect.follow_ups,pending_actor_id=task.target_id if result.wound_effect.follow_ups else None)
        elif task.kind in (PcMagicTaskKind.PRONE,PcMagicTaskKind.BLINDED) and active:
            changed = replace(injury,conditions=result.state)
            updates.update(dict(party=_party_update(state,task.target_id,injury=changed)) if is_pc
                else pc_actor_npc_update(state,task.target_id,injury=changed))
            updates['magic_modifiers'] = (*state.magic_modifiers,PcMagicModifier(task.id,task.target_id,task.kind))
        elif task.kind is PcMagicTaskKind.DEATH and active:
            updates['party'] = _party_update(state,task.target_id,injury=replace(injury,dead=True))
        elif task.kind in (PcMagicTaskKind.NEXT_TEST_PENALTY,PcMagicTaskKind.FELLOWSHIP_GRIM,
                PcMagicTaskKind.AWARENESS_GRIM) and active:
            updates['magic_modifiers'] = (*state.magic_modifiers,PcMagicModifier(task.id,task.target_id,task.kind))
        elif task.kind is PcMagicTaskKind.NOTE:
            updates['magic_notes'] = (*state.magic_notes,task)
        return finish(**updates)
    if type(proof) is PcMagicCleanupProof:
        if pending.tasks or pending.miscast_request is not None or pc_magic_unsupported(state) is not None:
            raise ValueError('magic cannot clear its pool before all actual consequences')
        same(proof.source_id,pending.source_id)
        updates = dict(magic_pending=None)
        if pending.miscast_roll is not None:
            updates['party'] = _party_update(state,pending.caster_id,
                magic=replace(state.participant(pending.caster_id).magic,miscast_dice=0))
        return finish(**updates)
    raise TypeError('unknown PC magic proof')
