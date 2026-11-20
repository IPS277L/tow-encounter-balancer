"""Finite automatic music choices and committed physical preparation.

Read-only proposals never enter the native journal. A real selected intention
is recorded before an instrument's hand use can change a wounded actor.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_is_pc, pc_actor_injury
from towr.domain.pc_tool_models import actor_tools
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import CombatActionKind
from towr.domain.test_models import Skill
from towr.domain.weapon_inventory_models import WeaponItemLocation


@dataclass(frozen=True, slots=True)
class MusicEquipmentView:
    base: object
    proof: object

    def __getattr__(self, name):
        if name == 'party' and self.proof.actor_id in self.base.source.pc_activation_order:
            return tuple(self.proof.state if member.actor_id == self.proof.actor_id else member for member in self.base.party)
        if name == 'enemies' and self.proof.actor_id in self.base.source.npc_activation_order:
            return tuple(self.proof.state if member.state.actor_id == self.proof.actor_id else member for member in self.base.enemies)
        if name == 'battlefield':
            return self.proof.battlefield
        if name == 'npc_shields' and self.proof.npc_shield is not None:
            return tuple(self.proof.npc_shield if item.actor_id == self.proof.actor_id else item for item in self.base.npc_shields)
        return getattr(self.base, name)

    def participant(self, actor):
        return next(member for member in self.party if member.actor_id == actor)

    def enemy(self, actor):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id == actor)


def music_cleanup_view(state, actor):
    if not any(item.location is WeaponItemLocation.HELD for item in actor_tools(state, actor).items):
        return state
    from towr.domain.pc_musician_equipment_models import plan_musician_equipment
    proposal = plan_musician_equipment(state, actor, None)
    return state if proposal is None else MusicEquipmentView(state, proposal)


@dataclass(frozen=True, slots=True)
class MusicOption:
    actor_id: str
    item_id: str
    utility: float
    pickup: bool


@dataclass(frozen=True, slots=True)
class PcMusicianIntentProof:
    actor_id: str
    action_id: str
    choice: object

    def __post_init__(self):
        from towr.domain.pc_tactical_models import PcTacticalChoice
        if (type(self.actor_id) is not str or not self.actor_id.strip()
                or type(self.action_id) is not str or not self.action_id.strip()):
            raise TypeError('music intent requires its actual actor and action identifiers')
        if (type(self.choice) is not PcTacticalChoice or self.choice.actor_id != self.actor_id
                or self.choice.music_item_id is None
                or self.choice.action not in (CombatActionKind.IMPROVISE, CombatActionKind.RECOVER)):
            raise ValueError('music intent must retain its one selected action and physical instrument')


def committed_musician_intent(state, actor=None):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_musician_effect_models import PcMusicianActionProof
    turn = state.round_state.active_turn
    if turn is None or actor is not None and actor != turn.actor_id:
        return None
    actor = turn.actor_id
    action_id = pc_melee_action_id(state, actor)
    for proof in reversed(state.history):
        if type(proof) is PcMusicianActionProof and proof.result.source_request.actor_id == actor:
            return None
        if type(proof) is PcMusicianIntentProof and proof.actor_id == actor and proof.action_id == action_id:
            return proof
    return None


def best_music_option(state, actor):
    from towr.domain.pc_battlefield_musician_models import (
        musician_description, musician_music_lore, held_musician_source,
        musician_listeners, musician_listener_risk, musician_leadership_test,
    )
    from towr.domain.pc_musician_equipment_models import plan_musician_equipment
    from towr.domain.pc_tactical_models import _distribution
    from towr.domain.pc_talent_advice import pc_test_distribution
    if (not any(talent.id is TalentId.BATTLEFIELD_MUSICIAN for talent in actor_acquired_talents(state, actor))
            or state.source.music_acoustics is None or not state.source.music_acoustics.audible_confirmed
            or musician_music_lore(state, actor) is None):
        return None
    description, _ = musician_description(state, actor)
    if description is None or description.fellowship is None or description.leadership is None:
        return None
    injury = pc_actor_injury(state, actor)
    if injury.conditions.has(Condition.DEFENCELESS) or injury.conditions.has(Condition.BROKEN):
        return None
    best = None
    for item in actor_tools(state, actor).items:
        pickup = item.location is WeaponItemLocation.DROPPED
        proposal = plan_musician_equipment(state, actor, item.id, pickup=pickup)
        view = state if proposal is None else MusicEquipmentView(state, proposal)
        if held_musician_source(view, actor, item.id) is None:
            continue
        values = sorted((musician_listener_risk(view, actor, listener.actor_id)
            for listener in musician_listeners(view, actor)
            if listener.can_hear and not listener.conditions.has(Condition.DEAFENED)
                and listener.range_band.value in ('close', 'short', 'medium')), reverse=True)
        if not values:
            continue
        request = musician_leadership_test(view, actor, 'tactics:music:leadership')
        probabilities = (pc_test_distribution(view, actor, Skill.LEADERSHIP, request, include_policy=True)
            if pc_actor_is_pc(state, actor) else _distribution(request))
        utility = sum(chance*sum(values[:successes]) for successes, chance in enumerate(probabilities))
        if pickup:
            # This action recovers the real dropped tool; inspiration needs a
            # later paid action. Do not credit today's benefit twice.
            utility *= .5 if state.round_state.round_number < state.source.max_rounds else 0.
        if proposal is not None:
            after = proposal.state.injury if pc_actor_is_pc(state, actor) else proposal.state.state.injury
            if after.conditions.has(Condition.CRITICALLY_INJURED) and not injury.conditions.has(Condition.CRITICALLY_INJURED):
                utility = max(0., utility-.5)
        option = MusicOption(actor, item.id, utility, pickup)
        if best is None or option.utility > best.utility+1e-12:
            best = option
    return best if best is not None and best.utility > 1e-12 else None


def music_tactical_choice(option):
    from towr.domain.pc_tactical_models import PcTacticalChoice
    return PcTacticalChoice(option.actor_id,
        CombatActionKind.RECOVER if option.pickup else CombatActionKind.IMPROVISE,
        option.actor_id, None, option.utility,
        'recover_actual_instrument' if option.pickup else 'inspire_allies_against_incoming_attacks',
        music_item_id=option.item_id, music_pickup=option.pickup)


def npc_music_choice(state, actor):
    from towr.domain.pc_oath_models import lady_prayer_selected
    if lady_prayer_selected(state):
        return None
    intent = committed_musician_intent(state, actor)
    if intent is not None:
        return intent.choice
    option = best_music_option(state, actor)
    if option is None:
        return None
    view = music_cleanup_view(state, actor)
    from towr.domain.pc_npc_weapon_inventory import _utility, expected_npc_weapon_equip, _view
    baseline = _utility(view, actor)
    equip = expected_npc_weapon_equip(view)
    if equip is not None:
        baseline = max(baseline, _utility(_view(view, actor, equip.transition.after), actor))
    return music_tactical_choice(option) if option.utility > baseline+1e-12 else None


def current_music_choice(state):
    turn = state.round_state.active_turn
    if turn is None:
        return None
    intent = committed_musician_intent(state)
    if intent is not None:
        return intent.choice
    if turn.actor_id in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(turn.actor_id).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            return None
        from towr.domain.pc_tactical_models import select_pc_tactic
        choice = select_pc_tactic(state, turn.actor_id)
        return choice if choice.music_item_id is not None else None
    if turn.actor_id in state.source.npc_activation_order:
        return npc_music_choice(state, turn.actor_id)
    return None


def expected_musician_intent(state):
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots or state.pending or state.pending_wound is not None
            or state.magic_pending is not None or committed_musician_intent(state) is not None):
        return None
    choice = current_music_choice(state)
    if choice is None:
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    return PcMusicianIntentProof(turn.actor_id, pc_melee_action_id(state, turn.actor_id), choice)
