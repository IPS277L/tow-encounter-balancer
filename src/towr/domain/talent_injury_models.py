"""Hardy Wounds Table preparation, PG1.4 III76, without profile conversion.

The actual injury resolver applies the minimum of one die. Ownership does not
grant a Minion, Brute or Monstrosity a character's Wounds Table.
"""
from dataclasses import replace

from towr.domain.injury_models import CharacterWoundRequest,WoundDiceModifier
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent,has_talent


HARDY_RULE_ID='RULE-TALENT-002:hardy'


def hardy_wound_dice_modifiers(talents:tuple[AcquiredTalent,...])->tuple[WoundDiceModifier,...]:
    return (WoundDiceModifier(HARDY_RULE_ID,-1),) if has_talent(talents,TalentId.HARDY) else ()


def prepare_hardy_wound(request:CharacterWoundRequest,
        talents:tuple[AcquiredTalent,...])->CharacterWoundRequest:
    """Add one owned Hardy source to a real character-table request.

    An existing Hardy marker is rejected, including on a source without the
    Talent. Calling preparation twice must not silently stack or legitimise it.
    Explicit fixed entries roll no table dice and retain their exact request.
    """
    if type(request) is not CharacterWoundRequest:
        raise TypeError('Hardy requires its actual character Wounds Table request')
    replace(request)
    if (type(request.dice_modifiers) is not tuple
            or any(type(modifier) is not WoundDiceModifier for modifier in request.dice_modifiers)):
        raise TypeError('Hardy preserves exact typed Wounds Table modifiers')
    for modifier in request.dice_modifiers:
        replace(modifier)
        if modifier.rule_id==HARDY_RULE_ID:
            raise ValueError('Hardy source is already present or was supplied without its owner')
    modifiers=hardy_wound_dice_modifiers(talents)
    if not modifiers or request.fixed_entry is not None:
        return request
    return replace(request,dice_modifiers=(*request.dice_modifiers,*modifiers))
