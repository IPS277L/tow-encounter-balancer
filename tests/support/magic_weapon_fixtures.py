"""Independent current-format Magic Weapon inputs; no expected outcomes."""
import json
from pathlib import Path

from towr.adapters._pc_melee_scenario_json import scenario_document


MAGIC=('dragon_bow','duellist_blades','grotarggs_hammer','headsmans_axe',
    'morning_star_of_fracasse','scarab_knife','trickster_blade','unwavering_spear','sword_of_justice')
TWO_HANDED={'dragon_bow','duellist_blades','grotarggs_hammer','headsmans_axe','unwavering_spear'}


def request(kind='scarab_knife'):
    raw=json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    raw['party']=raw['party'][:1]
    member=raw['party'][0]
    member['skills']['brawn']=4
    item=dict(id='actual:'+kind,weapon=kind,location='both_hands' if kind in TWO_HANDED else 'left_hand')
    if kind=='scarab_knife':item['initial_charges']=4
    if kind=='ogre_pistol':item.update(initially_loaded=False,gm_fit_confirmed=True)
    member['equipment']={'weapons':[item],'armour':[]}
    if kind in ('dragon_bow','ogre_pistol'):
        member['characteristics'].update(ballistic_skill=4,initiative=3)
        member['skills'].update(shooting=5,awareness=4)
        if kind=='ogre_pistol':member['skills']['dexterity']=3
        member['ranged']=dict(ammunition_supply_confirmed=True,
            has_blackpowder_lore=True if kind=='ogre_pistol' else None,
            has_blackpowder_kit=True if kind=='ogre_pistol' else None)
    raw['search_space'].update(weapon=[kind],weapon_count=[1],armour=[None],shield=[None],
        allowed_talents=[],brawn=[4],endurance=[4],scarab_initial_charges=[2])
    if kind=='ogre_pistol':raw['search_space']['ogre_fit_confirmed']=True
    raw['scene'].update(range='medium',two_handed_max_range='long')
    return raw


def native(scenario):
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='magic-weapons:source',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


