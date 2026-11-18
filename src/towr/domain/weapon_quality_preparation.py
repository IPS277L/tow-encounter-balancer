"""Magic Weapon Attack qualities from GM1.1 VI82–84 (ADR-0140).

Prepare before rolling or spending Fate. Context facts belong to the battle
owner: this module cannot invent a visible target, higher ground or a duel.
Physical activation costs and on-hit consequences are separate owners.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.test_models import QualityModifier, TestQuality, TestRequest
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_use_models import WeaponUse


DRAGON_BOW_RULE_ID = 'RULE-MAGIC-ITEM-003:dragon-bow-no-penalties'
DUELLIST_GRIM_RULE_ID = 'RULE-MAGIC-ITEM-003:duellist-first-grim'
DUELLIST_GLORIOUS_RULE_ID = 'RULE-MAGIC-ITEM-003:duellist-second-glorious'
GROTARGG_HIGHER_GROUND_RULE_ID = 'RULE-MAGIC-ITEM-003:grotargg-higher-ground'
HEADSMAN_EXECUTION_RULE_ID = 'RULE-MAGIC-ITEM-003:headsman-prone-execution'
UNWAVERING_GIVEN_GROUND_RULE_ID = 'RULE-MAGIC-ITEM-003:unwavering-given-ground-this-round'
JUSTICE_SINGLE_COMBAT_RULE_ID = 'RULE-MAGIC-ITEM-003:justice-single-combat'
_QUALITY_RULES = frozenset((DUELLIST_GRIM_RULE_ID, DUELLIST_GLORIOUS_RULE_ID,
    GROTARGG_HIGHER_GROUND_RULE_ID, HEADSMAN_EXECUTION_RULE_ID,
    UNWAVERING_GIVEN_GROUND_RULE_ID, JUSTICE_SINGLE_COMBAT_RULE_ID))


@dataclass(frozen=True, slots=True)
class WeaponAttackQualityContext:
    target_visible: bool = True
    higher_ground: bool = False
    target_prone: bool = False
    target_given_ground_this_round: bool = False
    single_combat: bool = False
    target_is_pc_or_champion: bool = False
    drained: bool = False
    headsman_execution: bool = False
    duellist_action_index: int | None = None

    def __post_init__(self):
        for name in ('target_visible', 'higher_ground', 'target_prone',
                'target_given_ground_this_round', 'single_combat',
                'target_is_pc_or_champion', 'drained', 'headsman_execution'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name + ' must retain its exact boolean source')
        if self.duellist_action_index is not None and (
                type(self.duellist_action_index) is not int
                or self.duellist_action_index not in (1, 2)):
            raise ValueError('Duellist quality requires actual action one or two')

    @property
    def effective_higher_ground(self) -> bool:
        # PG123 explicitly grants higher ground against a Prone creature.
        return self.higher_ground or self.target_prone


@dataclass(frozen=True, slots=True)
class WeaponQualityContribution:
    item_id: str
    modifier: QualityModifier

    def __post_init__(self):
        if type(self.item_id) is not str or not self.item_id.strip():
            raise TypeError('weapon quality needs its actual unit ID')
        if type(self.modifier) is not QualityModifier:
            raise TypeError('weapon quality requires its exact typed modifier')
        replace(self.modifier)


def _prepare(use, request, context):
    if type(use) is not WeaponUse or type(request) is not TestRequest:
        raise TypeError('weapon Attack qualities require typed use and Test source')
    if type(context) is not WeaponAttackQualityContext:
        raise TypeError('weapon Attack qualities require exact context facts')
    replace(use)
    replace(request)
    replace(context)
    if any(modifier.rule_id in _QUALITY_RULES for modifier in request.quality_modifiers):
        raise ValueError('weapon qualities cannot be prepared twice')
    kinds = tuple(use.inventory.item(item_id).kind for item_id in use.item_ids)
    if context.headsman_execution and (WeaponKind.HEADSMANS_AXE not in kinds or not context.target_prone):
        raise ValueError('execution intent requires the actual Axe and a Prone target')
    if context.duellist_action_index is not None and WeaponKind.DUELLIST_BLADES not in kinds:
        raise ValueError('another weapon cannot receive Duellist action qualities')

    contributions = []
    for item_id in use.item_ids:
        kind = use.inventory.item(item_id).kind
        rule = quality = None
        if kind is WeaponKind.DUELLIST_BLADES and context.duellist_action_index is not None:
            if context.duellist_action_index == 1:
                rule, quality = DUELLIST_GRIM_RULE_ID, TestQuality.GRIM
            else:
                rule, quality = DUELLIST_GLORIOUS_RULE_ID, TestQuality.GLORIOUS
        elif kind is WeaponKind.GROTARGGS_HAMMER and context.effective_higher_ground:
            rule, quality = GROTARGG_HIGHER_GROUND_RULE_ID, TestQuality.GLORIOUS
        elif kind is WeaponKind.HEADSMANS_AXE and context.headsman_execution:
            rule, quality = HEADSMAN_EXECUTION_RULE_ID, TestQuality.GRIM
        elif kind is WeaponKind.UNWAVERING_SPEAR and context.target_given_ground_this_round:
            rule, quality = UNWAVERING_GIVEN_GROUND_RULE_ID, TestQuality.GLORIOUS
        elif (kind is WeaponKind.SWORD_OF_JUSTICE and context.single_combat
                and context.target_is_pc_or_champion):
            rule, quality = JUSTICE_SINGLE_COMBAT_RULE_ID, TestQuality.GLORIOUS
        if quality is not None and not (context.drained and quality is TestQuality.GLORIOUS):
            contributions.append(WeaponQualityContribution(item_id, QualityModifier(rule, quality)))

    # Each actual source remains in contributions even if two items grant the
    # same non-stacking quality. Never duplicate or erase a Fate spend here.
    modifiers = tuple(dict.fromkeys(item.modifier for item in contributions))
    dice = request.dice_modifiers
    qualities = (*request.quality_modifiers, *modifiers)
    rules = tuple(dict.fromkeys(item.modifier.rule_id for item in contributions))
    if use.kind is WeaponKind.DRAGON_BOW:
        if not context.target_visible:
            raise ValueError('Dragon Bow cannot Attack an unseen target')
        dice = tuple(modifier for modifier in dice if modifier.amount > 0)
        qualities = tuple(modifier for modifier in qualities if modifier.quality is not TestQuality.GRIM)
        rules = (DRAGON_BOW_RULE_ID, *rules)
    return replace(request, dice_modifiers=dice, quality_modifiers=qualities), tuple(contributions), rules


@dataclass(frozen=True, slots=True)
class WeaponAttackQualityPreparation:
    use: WeaponUse
    source_test: TestRequest
    context: WeaponAttackQualityContext
    test: TestRequest
    contributions: tuple[WeaponQualityContribution, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self):
        expected = _prepare(self.use, self.source_test, self.context)
        if (self.test, self.contributions, self.applied_rule_ids) != expected:
            raise ValueError('weapon Attack quality changed its source or canonical effects')
        if type(self.test) is not TestRequest or type(self.contributions) is not tuple:
            raise TypeError('weapon Attack quality must retain exact prepared types')
        replace(self.test)
        for item in self.contributions:
            if type(item) is not WeaponQualityContribution:
                raise TypeError('weapon Attack quality lost a typed item contribution')
            replace(item)


def prepare_weapon_attack_quality(use: WeaponUse, request: TestRequest,
        context: WeaponAttackQualityContext) -> WeaponAttackQualityPreparation:
    test, contributions, rules = _prepare(use, request, context)
    return WeaponAttackQualityPreparation(use, request, context, test, contributions, rules)
