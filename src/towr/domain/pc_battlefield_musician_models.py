"""Native music: actual tools, audience, prepared Leadership and effect receipts."""
from towr.domain.injury_models import injury_wound_count
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import (
    pc_actor_is_pc, pc_actor_injury, pc_actor_side, pc_active_actor_ids,
    pc_actor_npc_snapshot, pc_opponent_ids,
)
from towr.domain.pc_musician_effect_models import (
    PcMusicianActionProof, PcMusicianSignalProof, musician_defends_ties,
)
from towr.domain.pc_tool_models import actor_tools, actor_tool_zone
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_battlefield_musician_models import (
    BattlefieldMusicianSource, BattlefieldMusicianListener,
    BattlefieldMusicianActionRequest, BattlefieldMusicianSignalRequest,
    BattlefieldMusicianSignalKind,
)
from towr.domain.test_models import Skill, TestRequest, TestQuality, QualityModifier
from towr.domain.tool_inventory_models import ToolKind, build_tool_use
from towr.domain.turn_models import CombatTurnParticipant
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation


@dataclass(frozen=True, slots=True)
class PcMusicianRecoverProof:
    result: object
    equipment: object

    def __post_init__(self):
        from towr.domain.recover_models import RecoverActionExecutionResult
        from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
        if type(self.result) is not RecoverActionExecutionResult or type(self.equipment) is not PcMusicianEquipmentProof:
            raise TypeError('tool pickup requires its actual paid Recover and physical equipment receipt')
        replace(self.result)
        replace(self.equipment)
        if not self.equipment.pickup:
            raise ValueError('paid music pickup must retrieve an actually dropped instrument')


def musician_description(state, actor):
    if actor in state.source.pc_activation_order:
        source = state.source.participant(actor)
        return source.pc, source.talent_facts
    if actor in state.source.npc_activation_order:
        source = state.enemy(actor).definition
        return source.generated_components, source.talent_facts
    return None, None


def musician_music_lore(state, actor):
    description, facts = musician_description(state, actor)
    if description is None or facts is None:
        return None
    return next((lore for lore in facts.lores if lore.id == 'music' and not lore.magic), None)


def musician_usable_hands(state, actor):
    if pc_actor_is_pc(state, actor):
        from towr.domain.pc_heavy_wound_models import usable_hands, injured_hands
        member = state.participant(actor)
        hands = usable_hands(member)
        injured = injured_hands(member)
        return tuple(WeaponGrip(hand.value) for hand in sorted(hands, key=lambda hand: hand in injured))
    return WeaponGrip.LEFT, WeaponGrip.RIGHT


def held_musician_source(state, actor, item_id=None):
    talent = next((talent for talent in actor_acquired_talents(state, actor)
        if talent.id is TalentId.BATTLEFIELD_MUSICIAN), None)
    description, _ = musician_description(state, actor)
    lore = musician_music_lore(state, actor)
    if talent is None or description is None or lore is None:
        return None
    if description.fellowship is None or description.leadership is None:
        return None
    tools = actor_tools(state, actor)
    for item in tools.items:
        if (item.kind is not ToolKind.MUSICIANS_GEAR or item.location is not WeaponItemLocation.HELD
                or item_id is not None and item.id != item_id):
            continue
        try:
            use = build_tool_use(actor, tools, item.id, usable_hands=musician_usable_hands(state, actor))
        except ValueError:
            continue
        return BattlefieldMusicianSource(actor, talent, use, lore,
            description.fellowship, description.leadership)
    return None


def _music_heard(state, actor, listener):
    acoustics = state.source.music_acoustics
    if acoustics is None:
        return False
    if state.battlefield is None:
        return acoustics.audible_confirmed
    arena = state.source.facts.zone_id + ':'
    first, second = actor_tool_zone(state, actor), actor_tool_zone(state, listener)
    if not first.startswith(arena) or not second.startswith(arena):
        raise ValueError('music audience escaped its actual arena namespace')
    return acoustics.can_hear(first[len(arena):], second[len(arena):])


def musician_listeners(state, actor, *, priority=None):
    from towr.domain.pc_battlefield_models import battlefield_range
    allies = tuple(ally for ally in pc_active_actor_ids(state, pc_actor_side(state, actor)) if ally != actor)
    if priority is not None:
        if set(priority) != set(allies) or len(priority) != len(allies):
            raise ValueError('music priority must preserve all actual distinct allied listeners')
        allies = priority
    result = []
    for ally in allies:
        injury = pc_actor_injury(state, ally)
        distance = (RangedWeaponRange.CLOSE if state.battlefield is None
            else battlefield_range(state.battlefield, actor, ally))
        result.append(BattlefieldMusicianListener(ally, pc_actor_side(state, ally), True,
            injury.conditions, distance, _music_heard(state, actor, ally)))
    return tuple(result)


def _audience_participants(state, listeners):
    clock_ids = {participant.entity_id for participant in state.round_state.participants}
    return tuple(CombatTurnParticipant(listener.actor_id, listener.side)
        for listener in listeners if listener.actor_id not in clock_ids)


def musician_leadership_test(state, actor, identifier):
    if pc_actor_is_pc(state, actor):
        from towr.domain.pc_melee_result_models import _pc_test
        return _pc_test(state, actor, identifier, Skill.LEADERSHIP, weapon_use=None)
    description, _ = musician_description(state, actor)
    if description is None:
        raise ValueError('music needs the actual generated Leadership profile')
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    modifiers, qualities = magic_test_modifiers(state, actor, Skill.LEADERSHIP)
    modifiers = (*modifiers, *pc_npc_distraction_test_modifiers(state, actor, None),
        *actor_armour_test_modifiers(state, actor, Skill.LEADERSHIP))
    conditions = pc_actor_injury(state, actor).conditions
    if conditions.has(Condition.BLINDED):
        qualities = (*qualities, QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    if conditions.has(Condition.DRAINED):
        modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
        qualities = tuple(modifier for modifier in qualities if modifier.quality is not TestQuality.GLORIOUS)
    return TestRequest(identifier, description.leadership_profile, modifiers, qualities)


def musician_listener_risk(state, musician, ally):
    """Immediate prepared-Test reduction; no future dice or hidden combat state.

    The estimate uses current ready attacks and current protection. It values
    only the changed positive ties; already inspired/Defenceless allies add no
    duplicated value. It is a bounded tactic, not an extra tabletop rule.
    """
    from towr.domain.pc_tactical_models import _distribution, _impact_value
    from towr.domain.pc_melee_result_models import _pc_test, pc_protection_skill
    from towr.domain.pc_generated_equipment import npc_protection_test
    from towr.domain.attack_models import DamageImpactSpec
    injury = pc_actor_injury(state, ally)
    if musician_defends_ties(state, ally) or injury.conditions.has(Condition.DEFENCELESS):
        return 0.0
    total = 0.0
    for enemy_id in pc_opponent_ids(state, ally):
        from towr.domain.pc_short_opening_models import pc_enemy_range
        distance = pc_enemy_range(state, enemy_id, ally)
        if pc_actor_is_pc(state, enemy_id):
            from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
            use = pc_attack_weapon_use(state, enemy_id, ally)
            if use is None:
                continue
            if use.skill in (Skill.MELEE, Skill.BRAWN) and distance is not RangedWeaponRange.CLOSE:
                continue
            attack = _pc_test(state, enemy_id, 'tactics:music:attack', use.skill, weapon_use=use)
            skill = use.skill
            damage = state.source.participant(enemy_id).pc.strength
        else:
            enemy = pc_actor_npc_snapshot(state, enemy_id)
            from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
            profile = pc_selected_npc_attack_profile(state, enemy_id)
            skill = profile.skill
            if skill in (Skill.MELEE, Skill.BRAWN) and distance is not RangedWeaponRange.CLOSE:
                continue
            from towr.domain.pc_npc_ability_models import pc_npc_attack_modifiers
            attack = TestRequest('tactics:music:attack', profile.test_profile,
                pc_npc_attack_modifiers(enemy.definition, enemy.state.injury.conditions,
                    target_conditions=injury.conditions, attacker_wounds=injury_wound_count(enemy.state.injury)))
            damage = profile.damage.base if profile.damage is not None else 0
        if pc_actor_is_pc(state, ally):
            from towr.domain.pc_shield_models import pc_shield_resilience
            member = state.participant(ally)
            protection_skill = pc_protection_skill(member, skill)
            protection = _pc_test(state, ally, 'tactics:music:protection', protection_skill,
                oppose_attack=True, incoming_attack_skill=skill)
            resilience = pc_shield_resilience(state, ally).total
        else:
            _, protection = npc_protection_test(state, ally, enemy_id, 'tactics:music:protection', attack_skill=skill)
            resilience = pc_actor_npc_snapshot(state, ally).state.current_resilience.total
        if protection is None:
            continue
        a, d = _distribution(attack), _distribution(protection)
        staggered = injury.conditions.has(Condition.STAGGERED)
        before = _impact_value(a, d, damage, resilience, 1, staggered)
        after = _impact_value(a, d, damage, resilience, 1, staggered, defender_wins_ties=True)
        total += max(0.0, before-after)
    return total


def musician_listener_priority(state, actor):
    listeners = musician_listeners(state, actor)
    scored = [(listener.actor_id, musician_listener_risk(state, actor, listener.actor_id)) for listener in listeners]
    return tuple(actor_id for actor_id, _ in sorted(scored, key=lambda value: -value[1]))


def build_pc_musician_action(state, *, item_id=None):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    turn = state.round_state.active_turn
    actor = turn.actor_id
    source = held_musician_source(state, actor, item_id)
    if source is None:
        raise ValueError('Leadership action has no actual usable music source')
    identifier = pc_melee_action_id(state, actor)+':music'+('' if len(turn.action_slots)==1 else ':action2')
    listeners = musician_listeners(state, actor, priority=musician_listener_priority(state, actor))
    return BattlefieldMusicianActionRequest(identifier, state.round_state, source,
        pc_actor_injury(state, actor).conditions, len(turn.action_slots),
        musician_leadership_test(state, actor, identifier+':leadership'), listeners,
        audience_participants=_audience_participants(state, listeners))


def project_pc_musician_action(state, proof):
    from towr.rules.battlefield_musician_resolution import complete_battlefield_musician_action
    from towr.domain.pc_melee_result_models import _test_result, _party_update, pc_after_test
    expected = build_pc_musician_action(state, item_id=proof.result.source_request.source.tool_use.item_id)
    actor = expected.actor_id
    updates = {}
    if pc_actor_is_pc(state, actor):
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        from towr.domain.pc_heavy_wound_models import critical_for_action
        from towr.domain.pc_weapon_inventory import pc_hand
        from towr.domain.turn_models import CombatActionKind
        effective, fate = validate_pc_test_fate(state, actor, Skill.LEADERSHIP, expected.leadership_test,
            proof.result.test_result, proof.decline, proof.glorious)
        member = state.participant(actor)
        injury = member.injury
        for hand in expected.source.tool_use.used_hands:
            injury = critical_for_action(replace(member, injury=injury), CombatActionKind.IMPROVISE,
                used_hand=pc_hand(hand))
        updates['party'] = _party_update(state, actor, injury=pc_after_test(state, actor, injury), fate=fate)
        expected = replace(expected, leadership_test=effective)
    else:
        if proof.decline is not None or proof.glorious is not None:
            raise ValueError('NPC music cannot own or spend PC Fate')
        _test_result(expected.leadership_test, proof.result.test_result)
    canonical = complete_battlefield_musician_action(expected, proof.result.test_result)
    if proof.result != canonical:
        raise ValueError('native music changed its actual tool, final Test, audience, clock or source')
    updates['round_state'] = canonical.round_state
    return updates


def build_pc_musician_signal(state, kind=BattlefieldMusicianSignalKind.PRESENCE):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = state.round_state.active_turn.actor_id
    if pc_actor_injury(state,actor).conditions.has(Condition.DEFENCELESS):
        return None
    if state.source.music_acoustics is None or not state.source.music_acoustics.audible_confirmed:
        return None
    if kind is BattlefieldMusicianSignalKind.PRESENCE:
        from towr.domain.pc_musician_tactics import committed_musician_intent
        intent=committed_musician_intent(state,actor)
        if intent is None or intent.choice.music_pickup:
            return None
    elif not pc_actor_injury(state,actor).conditions.has(Condition.BROKEN):
        return None
    source = held_musician_source(state, actor)
    if source is None:
        return None
    previous = tuple(proof.result.receipt for proof in state.history if type(proof) is PcMusicianSignalProof)
    if any(receipt.source_turn == (actor, state.round_state.round_number) for receipt in previous):
        return None
    listeners = musician_listeners(state, actor)
    return BattlefieldMusicianSignalRequest(pc_melee_action_id(state, actor)+':music:signal',
        state.round_state, source, pc_actor_injury(state, actor).conditions, kind, listeners,
        previous_receipts=previous, audience_participants=_audience_participants(state, listeners))


def build_pc_musician_recover(state):
    from towr.domain.pc_musician_tactics import committed_musician_intent
    from towr.domain.pc_melee_result_models import pc_melee_action_id,build_pc_melee_recover
    from towr.domain.recover_models import (
        RecoverActionExecutionRequest,RecoverMode,RecoverStandardChoice,
        RecoverConditionTarget,RecoverObjectInteractionFollowUp,
    )
    from towr.domain.magic_models import WizardMagicState
    from towr.domain.pc_short_opening_models import pc_has_close_enemy
    intent = committed_musician_intent(state)
    if intent is None or not intent.choice.music_pickup:
        raise ValueError('no actual music-tool pickup was committed')
    actor, item = intent.actor_id, intent.choice.music_item_id
    identifier = pc_melee_action_id(state, actor)
    interaction = RecoverObjectInteractionFollowUp(identifier+':pickup-tool',actor,item,True)
    if pc_actor_is_pc(state, actor):
        request = build_pc_melee_recover(state)
        return replace(request,choice=replace(request.choice,object_interaction=interaction),healing_potion=None)
    injury = pc_actor_injury(state, actor)
    def target(condition):
        return RecoverConditionTarget(actor,injury.conditions,None) if injury.conditions.has(condition) else None
    choice = RecoverStandardChoice(WizardMagicState(),staggered_target=target(Condition.STAGGERED),
        prone_target=target(Condition.PRONE),object_interaction=interaction)
    return RecoverActionExecutionRequest(identifier+':music:recover',state.round_state,actor,
        injury.conditions,pc_has_close_enemy(state,actor),1,RecoverMode.STANDARD,choice)


def project_pc_musician_recover(state, proof):
    from towr.domain.pc_ally_recover_models import expected_pc_standard_recover,pc_after_standard_recover
    from towr.domain.pc_musician_equipment_models import project_musician_equipment
    from towr.domain.pc_battlefield_movement_models import battlefield_recovered_injury
    request = build_pc_musician_recover(state)
    canonical = expected_pc_standard_recover(request)
    if proof.result != canonical:
        raise ValueError('music pickup changed its paid standard Recover, benefits or clock')
    updates = project_musician_equipment(state,proof.equipment,request.choice.object_interaction.object_id,pickup=True)
    actor = request.actor_id
    if pc_actor_is_pc(state,actor):
        updates['party'] = pc_after_standard_recover(state,request,canonical)
    else:
        after = proof.equipment.state
        injury = battlefield_recovered_injury(after.state.injury,canonical)
        updates['enemies'] = tuple(replace(after,state=replace(after.state,injury=injury))
            if enemy.state.actor_id == actor else enemy for enemy in state.enemies)
    updates['round_state'] = canonical.round_state
    return updates
