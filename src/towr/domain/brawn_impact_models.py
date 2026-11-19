"""PG1.4 III69: selected alternatives to an Unarmed Staggered impact.

The K1 Test proves success; placement and mount/vehicle consequences belong to
the encounter owner. Dragging a rider from the saddle does not itself invent
Prone: PG124 names those as distinct causes of forced dismount.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


BRAWN_DISPLACEMENT_RULE_ID = 'RULE-SKILL-004:brawn-displacement'


class BrawnAttackEffect(str, Enum):
    STAGGER = 'stagger'
    SHOVE = 'shove'
    DISMOUNT = 'dismount'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label + ' requires an exact nonempty identifier')


@dataclass(frozen=True, slots=True)
class BrawnDisplacementImpactSpec:
    """One alternative committed by the actual Brawn actor before the Test."""
    kind: BrawnAttackEffect
    actor_id: str
    rule_id: str = BRAWN_DISPLACEMENT_RULE_ID

    def __post_init__(self):
        if type(self.kind) is not BrawnAttackEffect:
            raise TypeError('Brawn displacement requires its exact selected alternative')
        if self.kind is BrawnAttackEffect.STAGGER:
            raise ValueError('ordinary Unarmed Staggered uses its existing Condition impact')
        _identifier(self.actor_id, 'Brawn actor')
        if type(self.rule_id) is not str or self.rule_id != BRAWN_DISPLACEMENT_RULE_ID:
            raise ValueError('Brawn displacement requires its canonical PG69 source rule')


def prepare_brawn_displacement_impact(use, kind):
    """Only the real itemless Unarmed WeaponUse can supply these alternatives."""
    from towr.domain.weapon_catalog import WeaponKind
    from towr.domain.weapon_use_models import WeaponUse
    from towr.domain.test_models import Skill
    if type(use) is not WeaponUse:
        raise TypeError('Brawn displacement requires the actual frozen Unarmed use')
    replace(use)
    if (use.kind is not WeaponKind.UNARMED or use.primary is not None
            or use.item_ids or use.skill is not Skill.BRAWN):
        raise ValueError('a held Brawn weapon or another Skill does not grant unarmed displacement')
    return BrawnDisplacementImpactSpec(kind, use.actor_id)


@dataclass(frozen=True, slots=True)
class BrawnDisplacementRequest:
    """Pending physical consequence, bound to the one genuinely successful Test."""
    resolution_id: str
    attack_id: str
    source: BrawnDisplacementImpactSpec
    target_id: str

    def __post_init__(self):
        for name in ('resolution_id', 'attack_id', 'target_id'):
            _identifier(getattr(self, name), name)
        if type(self.source) is not BrawnDisplacementImpactSpec:
            raise TypeError('Brawn consequence requires the exact committed impact source')
        replace(self.source)
        if self.source.actor_id == self.target_id:
            raise ValueError('an Unarmed Attack cannot displace its own actor')

    @property
    def actor_id(self):
        return self.source.actor_id

    @property
    def kind(self):
        return self.source.kind

    @property
    def rule_id(self):
        return self.source.rule_id


@dataclass(frozen=True, slots=True)
class BrawnDisplacementImpactResult:
    """No damage or condition is substituted for the pending actual placement."""
    request: BrawnDisplacementRequest

    def __post_init__(self):
        if type(self.request) is not BrawnDisplacementRequest:
            raise TypeError('Brawn displacement result requires its exact pending consequence')
        replace(self.request)

    @property
    def applied_rule_ids(self):
        return (self.request.rule_id,)

    @property
    def source_rule_id(self):
        return self.request.rule_id

