"""Small fresh dynamic battles for real magical inventory integration tests."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random

from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import weapon_reload_target
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


class Threes:
    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('the battle requested an unexpected die')
        return 3


def magic_battle(kind, *, npc_magic=False, count=1, players=1, rounds=1,
        distance='close', pc_weapon=None, pc_strength=3, pc_toughness=20,
        npc_toughness=20, pc_ws=4, npc_ws=3, initial_charges=0, fate=0):
    """Admit real Dynamic input, with no mount/Brawn/other ability fallback.

    Stats remain independent supplied facts. The high default Toughness avoids
    incidental Wounds while inspecting actual actions and on-hit properties.
    """
    raw = json.loads(Path('docs/examples/dynamic/brawn.request.json').read_text(encoding='utf-8'))
    selected = pc_weapon or ('staff' if npc_magic else kind)
    weapon = weapon_profile(WeaponKind(selected))
    member = raw['party'][0]
    member['characteristics'].update(weapon_skill=pc_ws, strength=pc_strength,
        toughness=pc_toughness, agility=3)
    member['skills'].update(melee=5, defence=5, athletics=4, endurance=5)
    member['skills'].pop('brawn', None)
    if weapon.kind is WeaponKind.GROTARGGS_HAMMER:
        member['skills']['brawn'] = 4
    member['equipment'] = dict(weapons=[], armour=[])
    item = dict(id='magic:test', weapon=selected,
        location='both_hands' if weapon.hands is RangedWeaponHands.TWO_HANDED else 'left_hand')
    if weapon_reload_target(weapon.kind) is not None:
        item['initially_loaded'] = True
    if weapon.kind is WeaponKind.SCARAB_KNIFE:
        item['initial_charges'] = initial_charges
    if weapon.kind is WeaponKind.OGRE_PISTOL:
        item['gm_fit_confirmed'] = True
    member['equipment']['weapons'].append(item)
    if weapon.group is WeaponGroup.SHOOTING:
        member['characteristics'].update(ballistic_skill=4, initiative=3)
        member['skills'].update(shooting=5, dexterity=5, awareness=4)
        from towr.domain.ranged_weapon_profiles import RangedWeaponId,ranged_weapon_combat_profile
        blackpowder = True if ranged_weapon_combat_profile(RangedWeaponId(weapon.kind.value)).requires_blackpowder_lore else None
        member['ranged'] = dict(ammunition_supply_confirmed=True,
            has_blackpowder_lore=blackpowder, has_blackpowder_kit=blackpowder)
    member['resources']['fate'] = fate
    raw['party'] = [member]
    for index in range(1, players):
        ally = deepcopy(member)
        ally['actor_id'] = f'ally:{index}'
        raw['party'].append(ally)
    raw['npc_count'] = dict(minimum=count, maximum=count)
    raw['max_rounds'] = rounds
    raw['targets']['started_rounds'] = dict(numerator=rounds, denominator=1)
    raw['scene']['range'] = distance
    raw['search_space'].update(weapon=[kind if npc_magic else 'staff'], weapon_count=[1],
        weapon_skill=[npc_ws], melee=[5], strength=[3], toughness=[npc_toughness],
        agility=[3], defence=[3], athletics=[3], endurance=[5], brawn=[4],
        ballistic_skill=[3], shooting=[5], initiative=[3], dexterity=[5], awareness=[4],
        throwing=[5], mount=[None], shield=[None], armour=[None], abilities=[[]])
    if npc_magic and kind == 'scarab_knife':
        raw['search_space']['scarab_initial_charges'] = [initial_charges]
    if npc_magic and kind == 'ogre_pistol':
        raw['search_space']['ogre_fit_confirmed'] = True
    command = parse_dynamic_encounter_request(json.dumps(raw))
    sources = tuple(replace(command.request.space.sample(Random(index+1)),
        brawn=4 if npc_magic and kind == 'grotarggs_hammer' else None)
        for index in range(count))
    return command.request.scenario(sources, 'magic-native:' + kind)


def native_document(source):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='magic:source',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


def run_native(testcase, source, rng=None):
    """Current JSON source roundtrip and full source-bound step replay, no RNG twice."""
    restored = parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario
    testcase.assertEqual(restored, source)
    result = run_pc_melee_scenario(restored, rng or Threes())
    testcase.assertIsNone(result.unsupported)
    current = initial_pc_melee_state(source)
    for step in result.steps:
        current = apply_pc_melee_step(current, step)
    testcase.assertEqual(current, result.state)
    return result


def pc_after_horse_charge_source(kind='headsmans_axe', *, knockout=True, count=1, rounds=1):
    """Healthy two-PC source: a real first Horse Charge can set up Prone.

    Both use the selected supported item; Grotargg receives the real Brawn4
    through ``magic_battle``. No injury or Conditions are injected. The high
    NPC Toughness keeps the first hit nonlethal, so its actual Staggered/Prone
    survive for the second PC's Test in the same phase.
    """
    from towr.domain.minion_defeat_models import NpcDefeatDisposition
    from towr.domain.pc_mount_models import CombatMount
    source = magic_battle(kind, players=2, rounds=rounds, count=count,
        distance='short', pc_ws=4, npc_ws=1)
    members = tuple(replace(member, defeat_decisions=tuple(replace(decision,
        disposition=NpcDefeatDisposition.KNOCKED_OUT) for decision in member.defeat_decisions))
        if knockout else member for member in source.party)
    return replace(source, party=(replace(members[0], mount=CombatMount.HORSE), members[1]),
        facts=replace(source.facts, unmounted=False))
