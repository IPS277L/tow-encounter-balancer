"""Own canonical mount-NPC profiles and Tests, distinct from rider effects.

These queries prepare real source-bound Tests. They do not activate a mount,
spend a turn, resolve RNG or grant the creature its rider's resources/equipment.
"""
from dataclasses import replace

from towr.domain.armour_models import BARDING_AGILITY_RULE_ID
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_snapshot, pc_companion
from towr.domain.pc_mount_companion_sources import MountCompanionProfile, mount_companion_profile
from towr.domain.pc_mount_models import PcMountedState, initial_pc_mounts
from towr.domain.test_models import DiceModifier, InlineProfile, QualityModifier, Skill, TestQuality, TestRequest


def companion_profile_wound_injury(state, actor, change):
    """Apply the creature's own printed wound band to its actual profile ACK."""
    from towr.domain.injury_models import ProfileStateChangeRequest, ProfileNpcType
    if type(change) is not ProfileStateChangeRequest:
        raise TypeError('companion wound band requires its exact actual profile change')
    replace(change)
    profile = companion_profile(state, actor)
    injury = pc_actor_injury(state, actor)
    if (change.npc_type is not ProfileNpcType(profile.definition.injury_policy.value)
            or change.current_wounds != injury.wounds or change.defeated != injury.defeated):
        raise ValueError('companion wound band changed its actual body, HP or profile policy')
    return companion_wound_band_injury(profile, injury)


def companion_wound_band_injury(profile, injury):
    """Own printed band; the calling receipt validates the actual HP change."""
    from towr.domain.injury_models import ProfileInjuryState
    from towr.domain.pc_mount_companion_sources import MountCompanionWoundBand
    if type(profile) is not MountCompanionProfile or type(injury) is not ProfileInjuryState:
        raise TypeError('mount wound band requires its exact own profile and injury')
    replace(profile); replace(injury)
    if (profile.wound_band is MountCompanionWoundBand.DRAINED_1_2 and not injury.defeated
            and 1 <= injury.wounds <= 2):
        return replace(injury, conditions=injury.conditions.with_condition(Condition.DRAINED))
    return injury


def companion_profile(state, actor: str) -> MountCompanionProfile:
    """Bind the complete immutable NPC body to its one original mount source."""
    companion = pc_companion(state, actor)
    if companion is None:
        raise ValueError('own mount profile requires an actual companion actor')
    snapshot = pc_actor_npc_snapshot(state, actor)
    from towr.domain.pc_mount_companion_owner import initial_pc_companions
    expected = next((row for row in initial_pc_companions(state.source)
        if row.snapshot.state.actor_id == actor), None)
    if expected is None or companion.rider_id != expected.rider_id:
        raise ValueError('companion profile is not attached to its actual initial mount source')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    validate_pc_melee_source_types(snapshot.definition, expected.snapshot.definition)
    if snapshot.definition != expected.snapshot.definition or snapshot.state.side is not expected.snapshot.state.side:
        raise ValueError('companion profile changed its physical definition or source side')
    original = next(mount for mount in initial_pc_mounts(state.source) if mount.actor_id == companion.rider_id)
    if type(state.mounts) is not tuple or any(type(mount) is not PcMountedState for mount in state.mounts):
        raise TypeError('companion profile requires the exact actual mount state bank')
    current = tuple(mount for mount in state.mounts if mount.actor_id == companion.rider_id)
    if len(current) != 1:
        raise ValueError('companion profile requires its one actual mount state')
    replace(current[0])
    if current[0].mount is not original.mount:
        raise ValueError('companion profile changed its actual mount kind')
    rider = (state.source.participant(companion.rider_id)
        if companion.rider_id in state.source.pc_activation_order
        else state.source.enemy(companion.rider_id).definition.generated_components)
    armour = rider.armour
    barding = armour is not None and armour.barding
    return mount_companion_profile(original.mount, barding=barding)


def companion_test_request(state, actor: str, test_id: str, skill: Skill) -> TestRequest:
    """A creature's printed Characteristic/Skill plus its own actual effects."""
    if type(test_id) is not str or not test_id.strip():
        raise TypeError('companion Test requires its exact nonempty identifier')
    if type(skill) is not Skill:
        raise TypeError('companion Test requires its exact typed Skill')
    profile = companion_profile(state, actor)
    characteristic = profile.characteristic_for_skill(skill)
    if characteristic < 1:
        raise ValueError('this mount has no usable Characteristic for the requested Test')
    request_profile = InlineProfile(characteristic, profile.skill_rating(skill), 2*characteristic)
    # The physical animal wears Barding itself. Rider-only control/opposition
    # exemptions do not turn into an exemption for the animal's own Athletics.
    equipment = ((DiceModifier(BARDING_AGILITY_RULE_ID, -1),)
        if profile.barding and skill in (Skill.ATHLETICS, Skill.STEALTH) else ())
    from towr.domain.pc_magic_models import PcMagicModifier, magic_test_modifiers
    if type(state.magic_modifiers) is not tuple or any(type(row) is not PcMagicModifier
            for row in state.magic_modifiers):
        raise TypeError('companion Tests require the exact actual magic modifier bank')
    for modifier in state.magic_modifiers:
        replace(modifier)
    dice, qualities = magic_test_modifiers(state, actor, skill)
    modifiers = (*equipment, *dice)
    injury = pc_actor_injury(state, actor)
    if injury.conditions.has(Condition.DRAINED):
        modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
    if injury.conditions.has(Condition.BLINDED) and skill not in (Skill.ENDURANCE, Skill.WILLPOWER):
        qualities = (*qualities, QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    return TestRequest(test_id, request_profile, modifiers, qualities)
