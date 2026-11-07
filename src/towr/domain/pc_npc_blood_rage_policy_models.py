"""Caller-owned voluntary Blood Rage for the canonical Bestigor and Skin Wolf."""
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition


BESTIGOR_DEFINITION_ID = 'pc-book-npc:bestigor_massive_axe'
SKIN_WOLF_DEFINITION_ID = 'pc-book-npc:skin_wolf'
SKIN_WOLF_BLOOD_RAGE_RULE_ID = 'RULE-PROFILE-MONSTER-011:blood-rage'
BLOOD_RAGE_RULE_ID = 'RULE-PROFILE-BEASTMEN-003:blood-rage'
BESTIGOR_WOUND_GLORIOUS_RULE_ID = 'RULE-PROFILE-BEASTMEN-003:first-wound-next-attack-glorious'


def validate_pc_npc_blood_rage_policy(source) -> None:
    actors = source.npc_blood_rage_actor_ids
    if type(actors) is not tuple:
        raise TypeError('Blood Rage requires an exact ordered tuple of actor IDs')
    for actor in actors:
        if type(actor) is not str or not actor.strip():
            raise TypeError('Blood Rage actor IDs must be exact nonempty strings')
        if actor not in source.enemy_activation_order:
            raise ValueError('Blood Rage actor must belong to the source opposition')
        definition = source.enemy(actor).definition
        validate_pc_book_npc_definition(definition)
        if definition.id not in (BESTIGOR_DEFINITION_ID,SKIN_WOLF_DEFINITION_ID):
            raise ValueError('Blood Rage requires a canonical Bestigor or Skin Wolf')
    if len(set(actors)) != len(actors):
        raise ValueError('Blood Rage actor IDs must be unique')
