"""Independent explicit C19 sources; never infer or repair a submitted oath."""
from towr.application.generated_oath_sources import GeneratedOathSource
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.talent_catalog import TalentId, TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent, OathChoice, TalentAcquisition, TalentAcquisitionPhase, TalentFunding,
    TalentLoreFact, TalentOwnerFacts,
)
from towr.domain.test_models import Skill


def honour(oath='protect-allies'):
    return AcquiredTalent(TalentId.HONOUR_BOUND, (TalentAcquisition(
        TalentAcquisitionPhase.ADVANCEMENT, TalentFunding.XP, OathChoice(oath)),))


def lady(*, free=False):
    return AcquiredTalent(TalentId.BLESSINGS_OF_THE_LADY, (TalentAcquisition(
        TalentAcquisitionPhase.CREATION if free else TalentAcquisitionPhase.ADVANCEMENT,
        TalentFunding.FREE if free else TalentFunding.XP),))


def context(**kwargs):
    return OathBattleContext('gm:scene', True, 'protect-allies', True,
        forbidden_attack_skills=(Skill.SHOOTING,), **kwargs)


def source(*, full=True):
    return GeneratedOathSource((honour(), lady()) if full else (honour(),), context(),
        TalentOwnerFacts(origin=TalentOrigin.BRETONNIAN_HUMAN,
            lores=(TalentLoreFact('high_society'),)) if full else TalentOwnerFacts())


def with_native_outcome_owner(scenario, *, actor=None, fate=1, lucky=False, gm_context=None):
    """Declare a fresh PC test source with one oath and finite session funding."""
    from dataclasses import replace
    from tests.support.talent_sources import free_talent
    from towr.domain.fate_models import FateSessionState
    from towr.domain.pc_melee_models import PcFatePolicy
    actor=scenario.pc_activation_order[0] if actor is None else actor
    member=scenario.participant(actor)
    owned=tuple(talent for talent in member.talents if talent.id not in
        (TalentId.HONOUR_BOUND,TalentId.LUCKY))
    owned=(*owned,honour(),*((free_talent(TalentId.LUCKY),) if lucky else ()))
    gm_context=(replace(context(unmitigated_success_scope_confirmed=True),forbidden_attack_skills=())
        if gm_context is None else gm_context)
    resource=FateSessionState(member.fate.session_id,actor,fate,fate,has_lucky=lucky)
    member=replace(member,talents=owned,oath_context=gm_context,fate=resource,
        fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=None,near_miss_policy=None)
    return replace(scenario,party=tuple(member if row.actor_id==actor else row for row in scenario.party))
