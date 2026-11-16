"""Acquired PC combat Talent facts, including PG73 creation-free provenance."""
from dataclasses import dataclass,replace
from enum import Enum

from towr.domain.generated_npc_models import GeneratedTalent,generated_talent_requirements_met


class TalentAcquisition(str,Enum):
    EARNED='earned'
    CREATION_FREE='creation_free'


@dataclass(frozen=True,slots=True)
class PcCombatTalent:
    talent: GeneratedTalent
    acquisition: TalentAcquisition = TalentAcquisition.EARNED

    def __post_init__(self):
        if type(self.talent) is not GeneratedTalent or self.talent not in (
                GeneratedTalent.DEFENSIVE_STANCE,GeneratedTalent.WILD_ATTACK):
            raise ValueError('PC combat source supports Defensive Stance/Wild Attack only')
        if type(self.acquisition) is not TalentAcquisition:
            raise TypeError('Talent acquisition requires its typed earned/creation_free fact')


def validate_pc_combat_talents(talents,pc) -> None:
    if type(talents) is not tuple or any(type(value) is not PcCombatTalent for value in talents):
        raise TypeError('PC combat Talents require an ordered typed tuple')
    for value in talents:
        replace(value)
        if (value.acquisition is not TalentAcquisition.CREATION_FREE
                and not generated_talent_requirements_met(value.talent,weapon_skill=pc.weapon_skill,
                    strength=pc.strength)):
            raise ValueError('PC Talent Requirements need WS3/S4 or explicit free Character Creation')
    if len({value.talent for value in talents}) != len(talents):
        raise ValueError('PC combat Talents are single acquisitions, not repeatable ranks')
