"""Explicit scene GM facts for vows, PG1.4 III74/77 and ADR-0141 C19.

Facts describe this battle, not a tactical script or inferred oath semantics.
Ownership, session expenditure and actual consequences have separate owners.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent, has_talent
from towr.domain.test_models import Skill


@dataclass(frozen=True, slots=True)
class OathBattleContext:
    gm_confirmation_id: str
    in_good_standing_confirmed: bool
    oath_id: str | None = None
    combat_tests_fulfil_oath_confirmed: bool = False
    forbidden_attack_skills: tuple[Skill, ...] = ()
    fleeing_breaks_oath: bool = False
    lady_prayer_before_battle_confirmed: bool = False
    honour_bound_used_this_session: bool = False
    unmitigated_success_scope_confirmed: bool = False

    def __post_init__(self):
        for value in (self.gm_confirmation_id, *((self.oath_id,) if self.oath_id is not None else ())):
            if type(value) is not str or not value.strip():
                raise TypeError('Oath context needs exact nonempty GM and oath identifiers')
        for name in ('in_good_standing_confirmed', 'combat_tests_fulfil_oath_confirmed',
                'fleeing_breaks_oath', 'lady_prayer_before_battle_confirmed', 'honour_bound_used_this_session',
                'unmitigated_success_scope_confirmed'):
            if type(getattr(self, name)) is not bool:
                raise TypeError('Oath scene confirmations require exact booleans')
        if (type(self.forbidden_attack_skills) is not tuple
                or any(type(skill) is not Skill or skill not in (Skill.MELEE, Skill.BRAWN,
                    Skill.SHOOTING, Skill.THROWING) for skill in self.forbidden_attack_skills)
                or len(set(self.forbidden_attack_skills)) != len(self.forbidden_attack_skills)):
            raise ValueError('Oath restrictions require distinct actual Attack Skills')
        if self.lady_prayer_before_battle_confirmed and not self.in_good_standing_confirmed:
            raise ValueError('a barred oath cannot confirm a currently active pre-battle blessing')


def validate_oath_context(talents: tuple[AcquiredTalent, ...], context: OathBattleContext | None):
    honour = has_talent(talents, TalentId.HONOUR_BOUND)
    lady = has_talent(talents, TalentId.BLESSINGS_OF_THE_LADY)
    if context is None:
        if honour or lady:
            raise ValueError('Honour Bound and Lady require their actual GM scene context')
        return
    if type(context) is not OathBattleContext:
        raise TypeError('Oath context must retain its exact typed source')
    replace(context)
    if not (honour or lady):
        raise ValueError('Oath context cannot grant a missing Talent')
    if honour:
        owned = next(talent for talent in talents if talent.id is TalentId.HONOUR_BOUND)
        if context.oath_id != owned.acquisitions[0].choice.oath_id:
            raise ValueError('GM oath context must match the actual acquired OathChoice')
    elif (context.oath_id is not None or context.honour_bound_used_this_session
            or context.unmitigated_success_scope_confirmed):
        raise ValueError('Lady alone cannot invent Honour Bound ownership, expenditure or Unmitigated scope')
    if context.lady_prayer_before_battle_confirmed and not lady:
        raise ValueError('pre-battle Lady prayer requires its actually acquired Talent')
