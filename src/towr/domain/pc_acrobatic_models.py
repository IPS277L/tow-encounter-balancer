"""Bind Acrobatic movement/falling effects to the actual initial owner."""
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId


def actor_acrobatic_source(state,actor):
    from towr.domain.talent_acrobatic_models import AcrobaticSource
    talent=next((entry for entry in actor_acquired_talents(state,actor)
        if entry.id is TalentId.ACROBATIC),None)
    return None if talent is None else AcrobaticSource(actor,talent)
