"""Actual PC/generated-NPC oath owners; ADR-0141 C18/C19, PG74/77.

The normal native projection authenticates each underlying Test/Wound first.
This owner then consumes only real receipts from that step, never advice.
"""
from dataclasses import dataclass, fields, is_dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.lady_blessing_models import (
    LadyBlessingState, LadyOathDecision, OathDecisionKind, record_lady_prayer,
    record_lady_wound_negation, record_lady_broken_gain, record_lady_oath_decision,
)
from towr.domain.oath_context_models import OathBattleContext, validate_oath_context
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_lady_negation_models import LADY_NEGATION_RULE_ID
from towr.domain.talent_lady_prayer_models import (
    LadyPrayerActionRequest, LadyPrayerActionResult, execute_lady_prayer, lady_prayer_declaration,
)
from towr.domain.talent_models import AcquiredTalent
from towr.domain.test_models import QualityModifier, QualityModifierSource, TestQuality, TestRequest, TestResult
from towr.domain.turn_models import CombatActionKind, CombatTurnStartResult


@dataclass(frozen=True, slots=True)
class PcOathActor:
    actor_id: str
    context: OathBattleContext
    honour: object | None
    lady: LadyBlessingState | None
    honour_uses: tuple = ()
    lady_uses: tuple = ()

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('native oath owner needs its actual actor')
        if type(self.context) is not OathBattleContext:
            raise TypeError('native oath owner needs its exact GM source')
        replace(self.context)
        if type(self.honour_uses) is not tuple or type(self.lady_uses) is not tuple:
            raise TypeError('native oath receipts retain their immutable order')
        if self.honour is not None:
            from towr.domain.honour_bound_models import HonourBoundState
            if type(self.honour) is not HonourBoundState or self.honour.actor_id != self.actor_id:
                raise TypeError('native Honour Bound cannot replace its actual actor')
            replace(self.honour)
        if self.lady is not None:
            if type(self.lady) is not LadyBlessingState or self.lady.actor_id != self.actor_id:
                raise TypeError('native Lady blessing cannot replace its actual actor')
            replace(self.lady)


@dataclass(frozen=True, slots=True)
class PcLadyPrayerProof:
    result: LadyPrayerActionResult

    def __post_init__(self):
        if type(self.result) is not LadyPrayerActionResult:
            raise TypeError('native prayer needs its actual paid action result')
        replace(self.result)


@dataclass(frozen=True, slots=True)
class PcOathNegationAckProof:
    source: object

    def __post_init__(self):
        from towr.domain.resolution_models import ConsumeWoundNegationRequest
        if type(self.source) is not ConsumeWoundNegationRequest:
            raise TypeError('Lady acknowledgement needs its actual pending resource consumption')
        replace(self.source)


def oath_context_for(source, actor):
    if actor in source.pc_activation_order:
        return getattr(source.participant(actor), 'oath_context', None)
    enemy = next((enemy for enemy in source.npc_sources if enemy.state.actor_id == actor), None)
    if enemy is None:
        return None
    return getattr(enemy.definition.generated_components, 'oath_context', None)


def initial_pc_oaths(source):
    from towr.domain.talent_actor_models import npc_definition_acquired_talents
    rows = []
    for actor in (*source.pc_activation_order, *source.npc_activation_order):
        context = oath_context_for(source, actor)
        if context is None:
            continue
        if actor in source.pc_activation_order:
            member = source.participant(actor)
            talents, session = member.talents, member.fate.session_id
        else:
            definition = next(enemy.definition for enemy in source.npc_sources if enemy.state.actor_id == actor)
            talents = npc_definition_acquired_talents(definition)
            session = source.party[0].fate.session_id
        validate_oath_context(talents, context)
        honour = lady = None
        for talent in talents:
            if talent.id is TalentId.HONOUR_BOUND:
                from towr.domain.honour_bound_models import initial_honour_bound_state
                honour = initial_honour_bound_state(actor, talent, session, context)
            elif talent.id is TalentId.BLESSINGS_OF_THE_LADY:
                lady = LadyBlessingState(actor, talent, source.id)
                if not context.in_good_standing_confirmed:
                    lady = record_lady_oath_decision(lady, LadyOathDecision(
                        context.gm_confirmation_id + ':initial-breach', actor, OathDecisionKind.BREACH))
                elif context.lady_prayer_before_battle_confirmed:
                    lady = record_lady_prayer(lady, context.gm_confirmation_id + ':pre-battle-prayer')
        rows.append(PcOathActor(actor, context, honour, lady))
    return tuple(rows)


def actor_oath(state, actor):
    return next((row for row in getattr(state, 'oaths', ()) if row.actor_id == actor), None)


def lady_wound_rule(actor):
    return LADY_NEGATION_RULE_ID + ':' + str(len(actor)) + ':' + actor


def pc_oath_wound_options(state, actor):
    from towr.domain.injury_models import WoundNegationOption
    row = actor_oath(state, actor)
    return (WoundNegationOption(lady_wound_rule(actor)),) if row and row.lady and row.lady.available else ()


def oath_allows_attack(state, actor, skill):
    row = actor_oath(state, actor)
    return row is None or skill not in row.context.forbidden_attack_skills


def oath_allows_pc_choice(state, actor, choice):
    if choice.action is not CombatActionKind.ATTACK or actor_oath(state, actor) is None:
        return True
    from towr.domain.test_models import Skill
    from towr.domain.weapon_catalog import weapon_profile
    if choice.mount_attack:
        from towr.domain.pc_mount_attack_models import available_pc_attack_mount
        mount = available_pc_attack_mount(state, actor)
        return mount is not None and oath_allows_attack(state, actor, Skill.MELEE)
    inventory = state.participant(actor).weapon_inventory
    item = inventory.active if choice.weapon_item_id is None else inventory.item(choice.weapon_item_id)
    skill = Skill.BRAWN if choice.unarmed_attack or item is None else weapon_profile(item.kind).skill
    return oath_allows_attack(state, actor, skill)


def npc_oath_attack_blocked(state, actor):
    row = actor_oath(state, actor)
    if row is None:
        return False
    from towr.domain.test_models import Skill
    from towr.domain.weapon_catalog import weapon_profile
    inventory = state.enemy(actor).state.weapon_inventory
    skill = Skill.BRAWN if inventory is None or inventory.active is None else weapon_profile(inventory.active.kind).skill
    return not oath_allows_attack(state, actor, skill)


class LadyWoundDecisions:
    """Select only an option already supplied by the actual native owner."""
    def __init__(self, base):
        self.base = base

    def __getattr__(self, name):
        return getattr(self.base, name)

    def _choice(self, options):
        choices = tuple(option.rule_id for option in options
            if option.rule_id.startswith(LADY_NEGATION_RULE_ID + ':'))
        if len(choices) > 1:
            raise ValueError('one actual actor cannot supply multiple Lady resources')
        return choices[0] if choices else None

    def choose_wound_negation(self, *, request, table_roll, options):
        chosen = self._choice(options)
        return chosen if chosen is not None else self.base.choose_wound_negation(
            request=request, table_roll=table_roll, options=options)

    def choose_profile_wound_negation(self, *, request, options):
        chosen = self._choice(options)
        if chosen is not None:
            return chosen
        return self.base.choose_profile_wound_negation(request=request, options=options)


def lady_prayer_selected(state):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return False
    turn = state.round_state.active_turn
    if turn is None or turn.action_slots and turn.action_slots[-1].executed:
        return False
    row = actor_oath(state, turn.actor_id)
    if row is None or row.lady is None or row.lady.prayers or row.lady.oath_barred:
        return False
    from towr.domain.pc_actor_models import pc_actor_injury
    injury = pc_actor_injury(state, turn.actor_id)
    if any(injury.conditions.has(value) for value in (Condition.BROKEN, Condition.DEFENCELESS)):
        return False
    starts = tuple(proof for proof in state.history if type(proof) is CombatTurnStartResult)
    return sum(proof.turn.actor_id == turn.actor_id for proof in starts) == 1


def build_pc_lady_prayer(state):
    if not lady_prayer_selected(state):
        raise ValueError('native Lady prayer is not the selected first-own-turn action')
    from towr.domain.pc_actor_models import pc_actor_injury
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = state.round_state.active_turn.actor_id
    return LadyPrayerActionRequest(pc_melee_action_id(state, actor) + ':lady-prayer',
        actor_oath(state, actor).lady, state.round_state,
        tuple(proof for proof in state.history if type(proof) is CombatTurnStartResult),
        pc_actor_injury(state, actor).conditions, len(state.round_state.active_turn.action_slots))


def honour_quality_modifiers(state, actor):
    row = actor_oath(state, actor)
    if row is None or row.honour is None or not row.honour.available:
        return ()
    if not row.context.combat_tests_fulfil_oath_confirmed:
        return ()
    from towr.domain.pc_actor_models import pc_actor_injury
    if pc_actor_injury(state, actor).conditions.has(Condition.DRAINED):
        return ()
    from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
    marker = 'honour:' + str(len(actor)) + ':' + actor + ':' + str(len(state.history))
    return (QualityModifier(HONOUR_BOUND_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
        QualityModifierSource.TALENT, marker),)


def pc_can_honour_unmitigated(state, actor):
    row = actor_oath(state, actor)
    if (row is None or row.honour is None or not row.honour.available
            or not row.context.combat_tests_fulfil_oath_confirmed
            or not row.context.unmitigated_success_scope_confirmed
            or actor not in state.source.pc_activation_order):
        return False
    from towr.domain.pc_melee_models import PcFatePolicy
    return (state.source.participant(actor).fate_policy is PcFatePolicy.CONFIGURED
        and state.participant(actor).fate.can_spend)


def pc_honour_outcome_id(state, actor, test_id):
    return 'honour-outcome:' + str(len(actor)) + ':' + actor + ':' + str(len(state.history)) + ':' + test_id


def attack_has_area_followups(attack):
    from towr.domain.weapon_impact_preparation import is_oil_impact, is_blast_impact
    from towr.domain.attack_models import NearbyTargetsStaggerSpec
    return (is_oil_impact(attack.impact_spec) or is_blast_impact(attack.impact_spec)
        or any(type(effect) is NearbyTargetsStaggerSpec for effect in attack.secondary_effects))


def choose_pc_honour_outcome(state, actor, request, result, *, area_attack=False):
    """Bounded tactic: fund a failed real Test, never reroll or edit its dice."""
    from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
    if (not pc_can_honour_unmitigated(state, actor) or result.successes
            or area_attack
            or any(value.rule_id == HONOUR_BOUND_GLORIOUS_RULE_ID for value in request.quality_modifiers)):
        return result
    maximum = max(0, result.trace.rolled_dice + result.trace.success_delta)
    if maximum <= 0:
        return result
    from towr.domain.honour_bound_models import (
        HonourBoundUnmitigatedRequest, activate_honour_bound_unmitigated, grant_honour_bound_outcome,
    )
    row = actor_oath(state, actor)
    activation = activate_honour_bound_unmitigated(HonourBoundUnmitigatedRequest(
        pc_honour_outcome_id(state, actor, request.id), row.honour, row.context,
        state.participant(actor).fate, request,
        row.context.gm_confirmation_id + ':maximum-legal-outcome', final_result=result))
    return grant_honour_bound_outcome(activation)


def prepare_pc_honour_test(state, actor, test, *, rule_of_nine=False, area_weapon=False):
    """Compare the two legal modes using exact current-pool distributions.

    Values are expected successes as a fraction of the current legal maximum.
    A paid Fate use costs 1/4 outcome unit, reduced when more session uses remain;
    Lucky's actually available first use costs zero. This is a bounded tactic,
    not a tabletop rule or a prediction of another participant's future dice.
    """
    if not pc_can_honour_unmitigated(state, actor) or area_weapon:
        return test
    from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
    if not any(value.rule_id == HONOUR_BOUND_GLORIOUS_RULE_ID for value in test.quality_modifiers):
        return test
    ordinary = replace(test, quality_modifiers=tuple(value for value in test.quality_modifiers
        if value.rule_id != HONOUR_BOUND_GLORIOUS_RULE_ID))
    comparison = ordinary
    glorious = test
    # Casting's locked 9 is part of the known prepared Test, even though its
    # physical guard is added by the Casting executor after _pc_test returns.
    if rule_of_nine:
        from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock
        lock = rule_of_nine_reroll_lock()
        comparison = replace(ordinary, reroll_locks=(*ordinary.reroll_locks, lock))
        glorious = replace(test, reroll_locks=(*test.reroll_locks, lock))
    from towr.domain.pc_tactical_models import _distribution
    raw, improved = _distribution(comparison), _distribution(glorious)
    maximum = max(1, len(raw)-1)
    glorious_gain = (sum(index*chance for index,chance in enumerate(improved))
        - sum(index*chance for index,chance in enumerate(raw)))/maximum
    fate = state.participant(actor).fate
    cost = 0 if fate.lucky_free_spend_available else 1
    outcome_gain = raw[0]*(1 - .25*cost/max(1, fate.remaining_spends))
    return ordinary if outcome_gain > glorious_gain+1e-12 else test


def filter_honour_test(test):
    """The automatic tactic keeps its session use if another source is Glorious."""
    from towr.domain.honour_bound_models import HONOUR_BOUND_GLORIOUS_RULE_ID
    if (any(value.rule_id == HONOUR_BOUND_GLORIOUS_RULE_ID for value in test.quality_modifiers)
            and any(value.quality is TestQuality.GLORIOUS and value.rule_id != HONOUR_BOUND_GLORIOUS_RULE_ID
                for value in test.quality_modifiers)):
        return replace(test, quality_modifiers=tuple(value for value in test.quality_modifiers
            if value.rule_id != HONOUR_BOUND_GLORIOUS_RULE_ID))
    return test


_EVIDENCE_PATHS = frozenset(('request', 'source_request', 'kernel_request', 'resolution', 'execution',
    'result', 'attack', 'attacker_test', 'defender_test', 'test', 'test_result', 'test_request',
    'help_test', 'help_test_result', 'leadership_test', 'awareness_test', 'awareness_test_result',
    'athletics_test', 'athletics_test_result', 'casting', 'exacting', 'critical', 'completion',
    'wound_result', 'character_wound', 'profile_wound', 'pending_character_wound', 'targets', 'impact',
    'casting_request', 'avoidance_test', 'dexterity_test', 'recall_test', 'recall_test_result', 'source_test', 'choice', 'condition_removal'))


def oath_step_evidence(proof):
    """Only actual Test/Wound result paths, never arbitrary source-state graphs."""
    from towr.domain.injury_models import CharacterWoundResult, ProfileWoundResult
    found, visited = [], set()
    def visit(value):
        if id(value) in visited:
            return
        visited.add(id(value))
        if type(value) in (TestRequest, TestResult, CharacterWoundResult, ProfileWoundResult):
            found.append(value)
        elif is_dataclass(value):
            for attribute in fields(value):
                if attribute.name in _EVIDENCE_PATHS:
                    visit(getattr(value, attribute.name))
        elif type(value) is tuple:
            for item in value:
                visit(item)
    visit(proof)
    return tuple(found)


def native_test_actor(state, proof, test_id):
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types, pc_kernel_resolution
    if type(proof) in pc_kernel_attack_types():
        attack = pc_kernel_resolution(proof).attack
        if attack.attacker_test.trace.request_id == test_id:
            return proof.request.actor_id
        if attack.defender_test is not None and attack.defender_test.trace.request_id == test_id:
            return proof.request.target_id
        return None
    for source in (getattr(proof, 'request', None),
            getattr(getattr(proof, 'result', None), 'source_request', None)):
        actor = getattr(source, 'actor_id', None) or getattr(source,'surgeon_id',None)
        if actor is not None:
            return actor
    if state.pending_actor_id is not None:
        return state.pending_actor_id
    turn = state.round_state.active_turn
    return turn.actor_id if turn is not None else None


def oath_test_request(proof, request):
    from towr.domain.pc_magic_models import PcCastingProof, guarded_casting_test
    if type(proof) is PcCastingProof and request.id == proof.request.casting_request.test.id:
        return guarded_casting_test(proof.request.casting_request)
    return request


def validate_oath_proof_access(state, proof):
    for result in oath_step_evidence(proof):
        if type(result) is not TestResult or result.honour_bound is None:
            continue
        actor = native_test_actor(state, proof, result.trace.request_id)
        grant = result.honour_bound
        if actor is None or grant.activation.state.actor_id != actor or actor not in state.source.pc_activation_order:
            raise ValueError('exceptional outcome cannot pay for another actor\'s actual Test')
        row = actor_oath(state, actor)
        if row is None or row.honour is None or not row.context.unmitigated_success_scope_confirmed:
            raise ValueError('exceptional outcome requires the actual owner\'s agreed GM scope')
        from towr.domain.pc_demigryph_models import pc_kernel_attack_types, pc_kernel_resolution
        if (type(proof) in pc_kernel_attack_types()
                and result.trace.request_id == pc_kernel_resolution(proof).attack.attacker_test.trace.request_id):
            attack = proof.request.kernel_request.attack
            if attack_has_area_followups(attack):
                raise ValueError('automatic Unmitigated Success cannot fund unbounded area Wounds')


def project_oath_aftermath(before, after, proof):
    if not before.oaths:
        return after
    from towr.domain.injury_models import CharacterWoundResult, ProfileWoundResult
    from towr.domain.pc_actor_models import pc_actor_injury
    from towr.domain.honour_bound_models import (
        HonourBoundGloriousRequest, activate_honour_bound_glorious,
        record_honour_bound_oath_decision, HONOUR_BOUND_GLORIOUS_RULE_ID,
    )
    evidence = oath_step_evidence(proof)
    tests = {value.trace.request_id: value for value in evidence if type(value) is TestResult}
    requests = {value.id: value for value in evidence if type(value) is TestRequest}
    rows = []
    fate_updates = {}
    for row in before.oaths:
        honour, lady = row.honour, row.lady
        uses, negations = row.honour_uses, row.lady_uses
        marker = honour_quality_modifiers(before, row.actor_id)
        for identifier, actual in tests.items():
            request = requests.get(identifier)
            if request is not None:
                request = oath_test_request(proof, request)
            grant = actual.honour_bound
            if grant is not None and grant.activation.state.actor_id == row.actor_id:
                from towr.domain.honour_bound_models import (
                    HonourBoundUnmitigatedRequest, activate_honour_bound_unmitigated,
                )
                from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
                previous = next((use for use in uses
                    if use.source_request.id == grant.activation.source_request.id), None)
                if previous is not None:
                    if previous != grant.activation:
                        raise ValueError('a repeated outcome witness changed its already paid source')
                    continue
                if request is None or not pc_can_honour_unmitigated(before, row.actor_id):
                    raise ValueError('native Unmitigated Success needs an actual lawful unused PC source')
                selected = choose_pc_honour_outcome(before, row.actor_id, request, grant.raw_test)
                if selected.honour_bound is None:
                    raise ValueError('recorded outcome differs from the automatic failed-Test decision')
                expected = selected.honour_bound.activation
                if grant.activation != expected or grant.raw_test.trace != actual.trace:
                    raise ValueError('native Unmitigated Success changed its actual Test, scope or Fate price')
                validate_pc_melee_source_types(grant.activation, expected)
                honour, uses = expected.state, (*uses, expected)
                fate_updates[row.actor_id] = expected.fate_state
            if request is None or not marker or marker[0] not in request.quality_modifiers:
                continue
            if HONOUR_BOUND_GLORIOUS_RULE_ID not in actual.trace.applied_rule_ids:
                raise ValueError('actual Honour Bound Test lost its prepared Talent source')
            ordinary = replace(request, quality_modifiers=tuple(value for value in request.quality_modifiers
                if value != marker[0]))
            activation = activate_honour_bound_glorious(HonourBoundGloriousRequest(
                marker[0].source_id, honour, row.context, ordinary))
            # Its generic canonical marker is rebound to this native history prefix.
            if replace(activation.test.quality_modifiers[-1], source_id=marker[0].source_id) != marker[0]:
                raise ValueError('native Honour Bound changed its generic prepared effect')
            honour, uses = activation.state, (*uses, activation)
        if lady is not None:
            for result in evidence:
                if type(result) not in (CharacterWoundResult, ProfileWoundResult):
                    continue
                if getattr(result, 'negated_by_rule_id', None) != lady_wound_rule(row.actor_id):
                    continue
                if lady.negated_wound_id == result.request_id:
                    if not negations or negations[-1] != result:
                        raise ValueError('repeated Lady result replaced its actual consumed Wound')
                    continue
                lady = record_lady_wound_negation(lady, result.request_id)
                negations = (*negations, result)
            old, new = pc_actor_injury(before, row.actor_id), pc_actor_injury(after, row.actor_id)
            if not old.conditions.has(Condition.BROKEN) and new.conditions.has(Condition.BROKEN):
                lady = record_lady_broken_gain(lady, row.actor_id, old.conditions, new.conditions)
        # Actual fleeing, not a mere defensive displacement, is the observed breach.
        if row.context.fleeing_breaks_oath and type(proof).__name__ in ('PcBrokenRunProof', 'PcBrokenMoveProof', 'PcNpcExitProof'):
            actor = (getattr(proof, 'actor_id', None)
                or getattr(getattr(proof, 'request', None), 'actor_id', None)
                or getattr(getattr(proof, 'request', None), 'entity_id', None))
            if actor == row.actor_id:
                decision = LadyOathDecision('oath-flee:' + str(len(before.history)), actor, OathDecisionKind.BREACH)
                if honour is not None:
                    honour = record_honour_bound_oath_decision(honour, decision)
                if lady is not None:
                    lady = record_lady_oath_decision(lady, decision)
        rows.append(replace(row, honour=honour, lady=lady, honour_uses=uses, lady_uses=negations))
    if fate_updates:
        from towr.domain.pc_weapon_inventory import replace_pc_member
        party = tuple(replace_pc_member(member, fate=fate_updates[member.actor_id])
            if member.actor_id in fate_updates else member for member in after.party)
        return replace(after, party=party, oaths=tuple(rows))
    return replace(after, oaths=tuple(rows))


def honour_fate_after_proof(state, actor, fate, proof):
    """Fold a consumed exceptional result at its real place in the Fate prefix.

    The ordinary projector constructs a temporary state before this owner has
    consumed the outcome. Only an activation present in its bound use bank is
    charged; validate_native_oath_resources rejects such a temporary prefix as
    an externally supplied transition source.
    """
    row = actor_oath(state, actor)
    if row is None or not row.honour_uses:
        return fate
    from towr.domain.honour_bound_models import HonourBoundUnmitigatedResult
    paid = {use.source_request.id: use for use in row.honour_uses
        if type(use) is HonourBoundUnmitigatedResult}
    if not paid:
        return fate
    for result in oath_step_evidence(proof):
        if type(result) is not TestResult or result.honour_bound is None:
            continue
        activation = result.honour_bound.activation
        if activation.source_request.id not in paid:
            continue
        if activation != paid[activation.source_request.id]:
            raise ValueError('Fate outcome history changed its consumed full source')
        if activation.spend.id in {spend.id for spend in fate.spends}:
            continue
        if activation.source_request.fate_state != fate:
            raise ValueError('Honour Bound Fate spend must extend the actual session prefix')
        fate = activation.fate_state
    return fate


def validate_native_oath_resources(state):
    from towr.domain.pc_oath_history_models import fold_native_oaths
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    expected = fold_native_oaths(state.source,state.history)
    if state.oaths != expected:
        raise ValueError('native Oath bank must preserve its complete actual source and receipt history')
    validate_pc_melee_source_types(state.oaths,expected)


def project_pc_oath_step(state, proof):
    from towr.domain.pc_melee_result_models import _ready, validate_pc_melee_source_types
    if type(proof) is PcOathNegationAckProof:
        expected = expected_oath_negation_ack(state)
        if expected != proof:
            raise ValueError('Lady acknowledgement changed its actual next consumed Wound source')
        pending = state.pending[1:]
        return replace(state, pending=pending,
            pending_actor_id=state.pending_actor_id if pending or state.pending_wound else None,
            history=(*state.history, proof))
    if type(proof) is not PcLadyPrayerProof:
        raise TypeError('native oath action requires its exact accepted proof')
    _ready(state)
    expected = execute_lady_prayer(build_pc_lady_prayer(state))
    if proof.result != expected:
        raise ValueError('native Lady prayer changed its actual actor, first-turn prefix or action')
    validate_pc_melee_source_types(proof.result, expected)
    actor = expected.blessing.actor_id
    rows = tuple(replace(row, lady=expected.blessing) if row.actor_id == actor else row for row in state.oaths)
    return replace(state, oaths=rows, round_state=expected.round_state, history=(*state.history, proof))


def expected_oath_negation_ack(state):
    from towr.domain.resolution_models import ConsumeWoundNegationRequest
    if not state.pending or type(state.pending[0]) is not ConsumeWoundNegationRequest:
        return None
    source = state.pending[0]
    row = next((row for row in state.oaths if source.rule_id == lady_wound_rule(row.actor_id)), None)
    if (row is None or row.lady is None or row.lady.negated_wound_id is None
            or not row.lady_uses or not row.lady.negated_wound_id.startswith(source.resolution_id)):
        raise ValueError('pending Lady resource consumption lacks its actual bound Wound receipt')
    return PcOathNegationAckProof(source)
