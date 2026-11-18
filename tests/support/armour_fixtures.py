"""Small fact builders for valid ordinary-armour fixtures, without rule arithmetic.

Malformed-source tests must alter the produced facts directly. These builders
do not repair a malformed source or calculate an expected combat result.
"""
from towr.domain.armour_models import ArmourLoadout, BodyArmour, ShieldKind


def light_loadout(*, light=False, shield=False):
    if type(light) is not bool or type(shield) is not bool:
        raise TypeError('valid fixture setup requires explicit bool choices')
    return ArmourLoadout((BodyArmour.LIGHT,) if light else (),
        BodyArmour.LIGHT if light else None,
        shield=ShieldKind.SHIELD if shield else None)


def armour_document(*, body=(), benefit=None, helmet=None, shield=None, barding=False):
    return dict(body=list(body), benefit=benefit, helmet=helmet, shield=shield, barding=barding)
