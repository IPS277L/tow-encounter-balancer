"""Source-bound Cleaving Blow waves, PG1.4 III74 and ADR-0141 C22.

Each accepted weapon Wound has its own receipt. Immediate weapon Traits
inherit the weapon; this talent's Staggered waves do not inherit it.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.injury_models import ProfileStateChangeRequest, MinionStaggerDefeatCause
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.resolution_models import StaggerImpactRequest, StaggerImpactResult, TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.weapon_use_models import WeaponUse
from towr.domain.weapon_inventory_models import WeaponGrip

CLEAVING_BLOW_RULE_ID = 'RULE-TALENT-002:cleaving-blow'


def _ids(*values):
    if any(type(v) is not str or not v.strip() for v in values):
        raise TypeError('Cleaving Blow requires exact nonempty source identifiers')


@dataclass(frozen=True, slots=True)
class CleavingBlowTrigger:
    attack_index: int
    source_index: int
    wound_id: str
    wound_ordinal: int
    actor_id: str
    wounded_target_id: str
    weapon_use: WeaponUse
    talent: AcquiredTalent

    def __post_init__(self):
        _ids(self.wound_id, self.actor_id, self.wounded_target_id)
        if any(type(v) is not int or v < 0 for v in
                (self.attack_index, self.source_index, self.wound_ordinal)):
            raise TypeError('Cleaving Blow retains exact Wound journal positions')
        if self.source_index < self.attack_index:
            raise ValueError('a weapon Wound cannot precede its Attack')
        if type(self.weapon_use) is not WeaponUse or type(self.talent) is not AcquiredTalent:
            raise TypeError('Cleaving Blow retains its actual acquired talent and physical weapon')
        replace(self.weapon_use); replace(self.talent)
        if (self.talent.id is not TalentId.CLEAVING_BLOW or self.weapon_use.actor_id != self.actor_id
                or self.weapon_use.primary_grip is not WeaponGrip.BOTH):
            raise ValueError('Cleaving Blow requires this owner and one actual two-handed weapon')

    @property
    def wave_id(self):
        return self.wound_id + ':cleaving:' + str(self.wound_ordinal)


@dataclass(frozen=True, slots=True)
class PcCleavingStartProof:
    trigger: CleavingBlowTrigger
    target_ids: tuple[str, ...]

    def __post_init__(self):
        if type(self.trigger) is not CleavingBlowTrigger:
            raise TypeError('Cleaving wave requires its exact actual Wound trigger')
        replace(self.trigger)
        if type(self.target_ids) is not tuple or len(set(self.target_ids)) != len(self.target_ids):
            raise TypeError('Cleaving wave freezes distinct ordered actual enemies')
        _ids(*self.target_ids)
        if any(actor in self.target_ids for actor in (self.trigger.actor_id,self.trigger.wounded_target_id)):
            raise ValueError('Cleaving wave excludes its owner and the enemy already wounded')

    @property
    def wave_id(self): return self.trigger.wave_id


@dataclass(frozen=True, slots=True)
class PcCleavingTargetProof:
    wave_id: str
    request: StaggerImpactRequest
    result: StaggerImpactResult

    def __post_init__(self):
        _ids(self.wave_id)
        if type(self.request) is not StaggerImpactRequest or type(self.result) is not StaggerImpactResult:
            raise TypeError('Cleaving target requires its exact Stagger impact and result')
        replace(self.request); replace(self.result)


@dataclass(frozen=True, slots=True)
class PcCleavingProfileProof:
    wave_id: str
    target_id: str
    source: ProfileStateChangeRequest
    decision: MinionDefeatDecision | None

    def __post_init__(self):
        _ids(self.wave_id,self.target_id)
        if type(self.source) is not ProfileStateChangeRequest:
            raise TypeError('Cleaving profile acknowledgement requires its actual Wound change')
        replace(self.source)
        if self.decision is not None:
            if type(self.decision) is not MinionDefeatDecision:
                raise TypeError('Cleaving defeat requires its actual GM disposition')
            replace(self.decision)


@dataclass(frozen=True, slots=True)
class PcCleavingMinionDefeatProof:
    wave_id: str
    target_id: str
    source: MinionStaggerDefeatCause
    weighted_net_drops: tuple = field(default=(),kw_only=True)

    def __post_init__(self):
        _ids(self.wave_id,self.target_id)
        if type(self.source) is not MinionStaggerDefeatCause or self.source.target_id != self.target_id:
            raise TypeError('Cleaving non-Wound defeat requires its exact target and cause')
        replace(self.source)


@dataclass(frozen=True, slots=True)
class PcCleavingEndProof:
    wave_id: str

    def __post_init__(self): _ids(self.wave_id)


CLEAVING_PROOFS = (PcCleavingStartProof,PcCleavingTargetProof,PcCleavingProfileProof,
    PcCleavingMinionDefeatProof,PcCleavingEndProof)


def cleaving_wound_triggers(state):
    """Read only explicit weapon result paths, never arbitrary Wounds in state.

    Character Wounds wait for their actual Near Miss completion. Profile
    Wounds count only inflicted points, including the remaining point after
    a partial negation. Own-wave receipts deliberately have no weapon source.
    """
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types,pc_kernel_resolution
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    from towr.domain.pc_blunderbuss_models import PcBlunderbussTargetProof,PcBlunderbussNearbyProof
    from towr.domain.talent_actor_models import actor_acquired_talents
    from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
    attacks = {p.request.kernel_request.id:(i,p) for i,p in enumerate(state.history)
        if type(p) in pc_kernel_attack_types()}
    completed = {p.completion.source_request.roll.request_id:(i,p.completion)
        for i,p in enumerate(state.history) if type(p) is PcWoundCompletionProof}
    found=[]

    def add(attack_entry, result, target, producer_index):
        attack_index,attack=attack_entry
        use=attack.weapon_intent.attack_use
        if use is None or use.primary_grip is not WeaponGrip.BOTH:
            return
        talent=next((t for t in actor_acquired_talents(state,attack.request.actor_id)
            if t.id is TalentId.CLEAVING_BLOW),None)
        if talent is None:
            return
        profile=result.profile_wound
        pending=result.pending_character_wound
        if profile is not None:
            wound_id,count=profile.request_id,profile.wounds_inflicted
        elif pending is not None:
            actual=completed.get(pending.request_id)
            if actual is None:
                return
            producer_index,completion=actual
            if completion.source_request.roll != pending:
                raise ValueError('Cleaving Wound completion replaced the actual weapon roll')
            wound_id=pending.request_id
            count=int(completion.outcome is CharacterWoundLifecycleOutcome.ACCEPTED)
        else:
            return
        for ordinal in range(count):
            found.append(CleavingBlowTrigger(attack_index,producer_index,wound_id,ordinal,
                attack.request.actor_id,target,use,talent))

    for i,proof in enumerate(state.history):
        if type(proof) in pc_kernel_attack_types():
            add((i,proof),pc_kernel_resolution(proof),proof.request.target_id,i)
        elif type(proof) is PcBlunderbussTargetProof:
            entry=attacks.get(proof.resolution_id)
            if entry is None:
                raise ValueError('secondary weapon Wound lost its actual Attack')
            add(entry,proof.result,proof.request.target_id,i)
        elif type(proof) is PcBlunderbussNearbyProof:
            entry=attacks.get(proof.request.source.resolution_id)
            if entry is None:
                raise ValueError('secondary weapon Wound lost its actual Attack')
            for target in proof.result.targets:
                add(entry,target.impact,target.target_id,i)
    return tuple(sorted(found,key=lambda t:t.source_index))


def current_cleaving_wave(state):
    for proof in reversed(state.history):
        if type(proof) is PcCleavingEndProof: return None
        if type(proof) is PcCleavingStartProof: return proof
    return None


def cleaving_target_ids(state,trigger):
    from towr.domain.pc_actor_models import pc_opponent_ids
    from towr.domain.pc_battlefield_models import battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    live=pc_opponent_ids(state,trigger.actor_id)
    priority=(state.source.enemy_target_priority if trigger.actor_id in state.source.npc_activation_order
        else tuple(enemy.state.actor_id for enemy in state.source.npc_sources))
    order=tuple(dict.fromkeys((*priority,*live)))
    def close(actor):
        if state.battlefield is None:
            if not state.source.facts.all_opponents_close:
                raise ValueError('Cleaving Blow requires actual owner-centred Close geometry')
            return True
        return battlefield_range(state.battlefield,trigger.actor_id,actor) is RangedWeaponRange.CLOSE
    return tuple(actor for actor in order if actor in live and actor != trigger.wounded_target_id and close(actor))


def expected_cleaving_start(state):
    # Source was admitted once. The absent-talent fast path must not rebuild
    # every NPC definition on every ordinary engine/projection transition.
    if not (any(t.id is TalentId.CLEAVING_BLOW for member in state.source.party for t in member.talents)
            or any(t.id is TalentId.CLEAVING_BLOW for enemy in state.source.npc_sources
                for t in enemy.definition.talents)):
        return None
    if state.pending or state.pending_wound is not None or current_cleaving_wave(state) is not None:
        return None
    from towr.domain.pc_blunderbuss_models import current_pc_blunderbuss_wave
    from towr.domain.pc_warped_form_models import current_warped_form
    from towr.domain.pc_weapon_area_models import current_weapon_area
    if (current_pc_blunderbuss_wave(state) is not None or current_warped_form(state) is not None
            or current_weapon_area(state) is not None or state.magic_pending is not None):
        return None
    spent={p.wave_id for p in state.history if type(p) is PcCleavingStartProof}
    trigger=next((t for t in cleaving_wound_triggers(state) if t.wave_id not in spent),None)
    return None if trigger is None else PcCleavingStartProof(trigger,cleaving_target_ids(state,trigger))


def cleaving_target_receipt(state):
    wave=current_cleaving_wave(state)
    return None if wave is None else next((p for p in reversed(state.history)
        if type(p) is PcCleavingTargetProof and p.wave_id==wave.wave_id),None)


def cleaving_pending_npc_target(state):
    receipt=cleaving_target_receipt(state)
    if (receipt is None or not state.pending or state.pending_wound is not None
            or state.pending_actor_id != receipt.request.target_id
            or receipt.request.target_id in state.source.pc_activation_order):
        return None
    from towr.domain.pc_blunderbuss_models import _nearby_pending_suffix
    return receipt if _nearby_pending_suffix(receipt.result.follow_ups,state.pending) else None


def next_cleaving_target(state):
    wave=current_cleaving_wave(state)
    if wave is None or state.pending or state.pending_wound is not None:
        return None
    done=tuple(p.request.target_id for p in state.history if type(p) is PcCleavingTargetProof
        and p.wave_id==wave.wave_id)
    if done != wave.target_ids[:len(done)]:
        raise ValueError('Cleaving targets changed their actual committed order')
    if len(done)==len(wave.target_ids): return None
    actor=wave.target_ids[len(done)]
    from towr.domain.pc_actor_models import pc_actor_injury,pc_actor_npc_snapshot,pc_companion
    from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
    from towr.domain.pc_flagellant_models import pc_flagellant_first_stagger_spec
    from towr.domain.pc_undead_minion_models import pc_undead_minion_source
    from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec,undead_minion_effect_immunities
    from towr.domain.talent_injury_models import hardy_wound_dice_modifiers
    from towr.domain.talent_actor_models import actor_acquired_talents
    from towr.domain.pc_oath_models import pc_oath_wound_options
    pc=actor in state.source.pc_activation_order
    policy=TargetInjuryPolicy.PLAYER if pc else pc_actor_npc_snapshot(state,actor).definition.injury_policy
    undead=pc_undead_minion_source(state,actor)
    defeat=(undead_minion_stagger_defeat_spec(undead,actor) if undead is not None else
        None if pc else pc_npc_stagger_defeat_spec(pc_actor_npc_snapshot(state,actor).definition))
    from towr.domain.pc_give_ground_models import pc_give_ground_context
    ground=pc_give_ground_context(state,actor,wave.trigger.actor_id)
    # The scenario's ordinary repeated-Stagger strategy chooses a Wound.
    # Retain the real alternatives in the K1 source rather than forbidding them.
    return StaggerImpactRequest(wave.wave_id+':target:'+actor,actor,policy,pc_actor_injury(state,actor),
        ground.can_leave,ground.given_this_round,minion_stagger_defeat=defeat,
        first_stagger_wound=None if pc or pc_companion(state,actor) is not None else pc_flagellant_first_stagger_spec(state,actor),
        wound_dice_modifiers=hardy_wound_dice_modifiers(actor_acquired_talents(state,actor))
            if policy in (TargetInjuryPolicy.PLAYER,TargetInjuryPolicy.CHAMPION) else (),
        wound_negation_options=pc_oath_wound_options(state,actor),
        target_effect_immunities=undead_minion_effect_immunities(undead,actor))


def cleaving_profile_decision(state,target):
    from towr.domain.pc_actor_models import pc_companion
    wave=current_cleaving_wave(state)
    if not target.result.profile_wound.state_change.defeated or pc_companion(state,target.request.target_id) is not None:
        return None
    actor=wave.trigger.actor_id
    if actor in state.source.pc_activation_order:
        return state.source.participant(actor).defeat_decision(target.request.target_id)
    return None


def cleaving_wave_receipt(history,ack):
    """Bind an acknowledgement to the unique open wave and last real target."""
    if type(ack) not in (PcCleavingProfileProof,PcCleavingMinionDefeatProof):
        raise TypeError('Cleaving acknowledgement requires its exact typed profile or defeat proof')
    replace(ack)
    wave=target=None
    acknowledged=False
    for proof in history:
        if type(proof) is PcCleavingStartProof:
            wave=proof; target=None; acknowledged=False
        elif type(proof) is PcCleavingTargetProof:
            target=proof; acknowledged=False
        elif type(proof) in (PcCleavingProfileProof,PcCleavingMinionDefeatProof):
            acknowledged=True
        elif type(proof) is PcCleavingEndProof:
            wave=target=None
    if (wave is None or target is None or acknowledged or ack.wave_id != wave.wave_id
            or target.wave_id != wave.wave_id or target.request.target_id != ack.target_id
            or ack.target_id not in wave.target_ids):
        raise ValueError('Cleaving acknowledgement lost its actual wave and target')
    replace(wave); replace(target)
    actual=(target.result.profile_wound.state_change if type(ack) is PcCleavingProfileProof
        and target.result.profile_wound is not None else target.result.minion_stagger_defeat.cause
        if type(ack) is PcCleavingMinionDefeatProof and target.result.minion_stagger_defeat is not None else None)
    if actual is None or ack.source != actual:
        raise ValueError('Cleaving acknowledgement replaced the actual injury result')
    return wave,target


def validate_cleaving_history(state):
    if not any(type(p) in CLEAVING_PROOFS for p in state.history): return
    available={t.wave_id:t for t in cleaving_wound_triggers(state)}
    spent=set(); wave=None; targets=[]
    for proof in state.history:
        if type(proof) not in CLEAVING_PROOFS: continue
        replace(proof)
        if type(proof) is PcCleavingStartProof:
            if wave is not None or proof.wave_id in spent or available.get(proof.wave_id) != proof.trigger:
                raise ValueError('Cleaving wave lost its real weapon Wound or repeated its trigger')
            wave=proof; spent.add(proof.wave_id); targets=[]
        elif wave is None or proof.wave_id != wave.wave_id:
            raise ValueError('Cleaving continuation has no unique actual open wave')
        elif type(proof) is PcCleavingTargetProof:
            targets.append(proof.request.target_id)
            if tuple(targets) != wave.target_ids[:len(targets)] or len(targets)>len(wave.target_ids):
                raise ValueError('Cleaving targets were omitted, reordered or repeated')
        elif type(proof) is PcCleavingEndProof:
            if tuple(targets)!=wave.target_ids:
                raise ValueError('Cleaving completion omitted actual targets')
            wave=None
