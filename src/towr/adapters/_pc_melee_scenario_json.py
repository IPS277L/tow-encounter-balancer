"""Pure source-preserving PC scenario codec, without execution or RNG."""
from dataclasses import asdict
from enum import Enum
from functools import partial
from towr.adapters._oath_json import parse_oath_context, oath_context_document

from towr.adapters._json_common import build_value, resilience_document
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.attack_models import ConditionImpactSpec, HazardImpactSpec, ConditionOnHitSpec, DamageProfile, ResilienceProfile, ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition, ConditionState, EffectClassification
from towr.domain.fate_models import (
    FateBurnKind, FateBurnRecord, FateRefreshRecord, FateSessionState,
    FateSpendFunding, FateSpendKind, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.potion_models import ConsumableItem, ConsumableKind
from towr.domain.pc_magic_source_models import PcWizardProfile, PcSpellId
from towr.adapters._talent_json import (
    parse_acquired_talents, acquired_talents_document,
    parse_talent_owner_facts, talent_owner_facts_document,
)
from towr.adapters._tool_json import parse_tool_item_sources, tool_item_sources_document
from towr.domain.tool_inventory_models import initial_tool_inventory
from towr.domain.battlefield_music_models import BattlefieldMusicAcoustics
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, GeneratedAbility, TalentId, GeneratedRangedFacts
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,PcFeelNoPainPolicy
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode,PcNpcNetPolicy,NET_DEFINITION_ID
from towr.domain.pc_npc_ranged_source_models import (
    PC_NPC_RANGED_DEFINITION_IDS, PcNpcRangedPolicy, PcNpcRangedReloadHandPolicy,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcNearMissPolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcAllyRecoverPolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleeParticipant, PcMeleePolicy, PcMeleeScenario,
    PcMeleeWeapon, PcRandomSidePolicy, PcHeavyWoundPolicy, PcWeaponHand, PcTwoHandedGrip, PcBackupWeaponPolicy, PcAdjacentNpcExitPolicy, validate_pc_melee_scenario_admission,
    PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy,
    PC_RANGED_WEAPONS, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
    PcShortRangeOpening, PcBlunderbussNearby, PcAimSecondActionPolicy,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation,WeaponGrip
from towr.domain.pc_battlefield_models import PcBattlefieldSpec,PcAirspaceSpec
from towr.domain.pc_companion_policy_models import DismountedMountPolicy
from towr.domain.pc_single_combat_models import PcSingleCombatPair
from towr.domain.pc_scene_feature_models import PcZoneFeatures,PcVisibilityFact
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.armour_models import ArmourLoadout, BodyArmour, HelmetKind, ShieldKind
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


_NPC_RANGED_FIELDS = ('has_blackpowder_lore',
    'has_blackpowder_kit', 'ammunition_supply_confirmed', 'reload_hand_policy')


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {name: _plain(child) for name, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(child) for child in value]
    return value


def parse_armour_loadout(raw, *, path_prefix, error_type):
    """Read the one closed item-source shape shared by native and dynamic JSON."""
    expected = {'body', 'benefit', 'helmet', 'shield', 'barding'}
    if type(raw) is not dict or set(raw) != expected or type(raw['body']) is not list:
        raise error_type(Code.INVALID_INPUT, 'armour requires its complete closed equipment source',
            path=path_prefix)
    try:
        return build_value(error_type, path_prefix, ArmourLoadout,
            tuple(BodyArmour(value) for value in raw['body']),
            None if raw['benefit'] is None else BodyArmour(raw['benefit']),
            None if raw['helmet'] is None else HelmetKind(raw['helmet']),
            None if raw['shield'] is None else ShieldKind(raw['shield']), raw['barding'])
    except error_type:
        raise
    except (ValueError, TypeError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix) from error


def parse_medical_preparation(raw, *, path, error_type):
    if raw is None:
        return None
    from towr.domain.medical_preparation_models import MedicalPreparationFacts
    from towr.domain.injury_models import WoundEntryId
    required={'anatomy_lore','treatment_supplies','surgery_supplies'}
    optional={'recovery_supports','self_treatment_modifier','makeshift_modifier'}
    if type(raw) is not dict or not required <= raw.keys() or raw.keys()-required-optional:
        raise error_type(Code.INVALID_INPUT,'medical preparation needs explicit knowledge and supplies',path=path)
    try:
        values=dict(raw,recovery_supports=tuple(WoundEntryId(value) for value in raw.get('recovery_supports',())))
    except (TypeError,ValueError) as error:
        raise error_type(Code.INVALID_INPUT,str(error),path=path+'/recovery_supports') from error
    return build_value(error_type,path,MedicalPreparationFacts,**values)


def parse_surgery_risk(raw, *, path, error_type):
    if raw is None:
        return None
    from towr.domain.surgery_failure_resolution_models import SurgeryRiskPolicy
    from towr.domain.injury_models import DecisionOwner
    required={'id','no_complication','permanent_disfigurement','death'}
    if type(raw) is not dict or not required <= raw.keys() or raw.keys()-required-{'disfigurement_description','owner'}:
        raise error_type(Code.INVALID_INPUT,'surgery risk needs an explicit complete GM weight policy',path=path)
    try:
        owner=DecisionOwner(raw.get('owner','gm'))
    except (TypeError,ValueError) as error:
        raise error_type(Code.INVALID_INPUT,str(error),path=path+'/owner') from error
    return build_value(error_type,path,SurgeryRiskPolicy,**dict(raw,owner=owner))


def parse_generated_medical_sources(raw, *, path, error_type):
    from towr.application.generated_medical_sources import GeneratedMedicalSource
    if type(raw) is not list:
        raise error_type(Code.INVALID_INPUT,'allowed medical sources must be an explicit list',path=path)
    sources=[]
    for index,item in enumerate(raw):
        current=path+'/'+str(index)
        if type(item) is not dict or set(item)!={'medical','tools'}:
            raise error_type(Code.INVALID_INPUT,'medical source requires its preparation and physical tools',path=current)
        sources.append(build_value(error_type,current,GeneratedMedicalSource,
            parse_medical_preparation(item['medical'],path=current+'/medical',error_type=error_type),
            parse_tool_item_sources(item['tools'],path_prefix=current+'/tools',error_type=error_type)))
    return tuple(sources)


def generated_medical_sources_document(sources):
    from towr.application.generated_medical_sources import GeneratedMedicalSource
    if type(sources) is not tuple or any(type(source) is not GeneratedMedicalSource for source in sources):
        raise TypeError('medical source documents retain their exact initial source tuple')
    return [dict(medical=_plain(asdict(source.medical)),tools=tool_item_sources_document(source.tools))
        for source in sources]


def parse_generated_components(raw, *, path_prefix, error_type):
    """Readmit the complete generated source without rebuilding or dropping facts."""
    return build_value(error_type, path_prefix, GeneratedNpc,
        **dict(raw, weapons=tuple(parse_weapon_item_source(item,
                path_prefix=f'{path_prefix}/weapons/{index}',error_type=error_type)
            for index,item in enumerate(raw['weapons'])),
            tools=parse_tool_item_sources(raw.get('tools', []),
                path_prefix=path_prefix+'/tools', error_type=error_type),
            armour=parse_armour_loadout(raw.get('armour'),
                path_prefix=path_prefix+'/armour', error_type=error_type),
            mount=None if raw.get('mount') is None else CombatMount(raw['mount']),
            rider_kind=None if raw.get('rider_kind') is None else RiderKind(raw['rider_kind']),
            ranged=None if raw.get('ranged') is None else build_value(error_type,
                path_prefix+'/ranged', GeneratedRangedFacts, **raw['ranged']),
            medical=parse_medical_preparation(raw.get('medical'),path=path_prefix+'/medical',error_type=error_type),
            injury_policy=TargetInjuryPolicy(raw.get('injury_policy','minion')),
            abilities=tuple(GeneratedAbility(value) for value in raw['abilities']),
            oath_context=parse_oath_context(raw.get('oath_context'), path=path_prefix+'/oath_context',error_type=error_type),
            talents=parse_acquired_talents(raw['talents'],path=path_prefix+'/talents',error_type=error_type),
            talent_facts=None if raw.get('talent_facts') is None else parse_talent_owner_facts(
                raw['talent_facts'],path=path_prefix+'/talent_facts',error_type=error_type)))


def parse_weapon_item_source(raw,*,path_prefix,error_type):
    required={'id','weapon','location','hand'}
    if type(raw) is not dict or not required <= raw.keys() or raw.keys()-required-{'initially_loaded','gm_fit_confirmed','initial_charges','quantity'}:
        raise error_type(Code.INVALID_INPUT,'weapon item needs its complete closed initial source',path=path_prefix)
    return build_value(error_type,path_prefix,WeaponItemSource,raw['id'],WeaponKind(raw['weapon']),
        WeaponItemLocation(raw['location']),None if raw['hand'] is None else WeaponGrip(raw['hand']),
        quantity=raw.get('quantity',1),initially_loaded=raw.get('initially_loaded'),
        initial_charges=raw.get('initial_charges',0),gm_fit_confirmed=raw.get('gm_fit_confirmed'))


def weapon_item_source_document(item):
    document=dict(id=item.id,weapon=item.kind.value,location=item.initial_location.value,
        hand=None if item.initial_grip is None else item.initial_grip.value)
    if item.initially_loaded is not None:
        document['initially_loaded']=item.initially_loaded
    if item.quantity!=1:
        document['quantity']=item.quantity
    if item.kind is WeaponKind.SCARAB_KNIFE:
        document['initial_charges']=item.initial_charges
    if item.gm_fit_confirmed is not None:
        document['gm_fit_confirmed']=item.gm_fit_confirmed
    return document


def generated_components_document(npc):
    document=_plain(asdict(npc))
    document['weapons']=[weapon_item_source_document(item) for item in npc.weapons]
    if npc.tools:
        document['tools'] = tool_item_sources_document(npc.tools)
    else:
        del document['tools']
    document['talents']=acquired_talents_document(npc.talents)
    if npc.oath_context is None:
        del document['oath_context']
    else:
        document['oath_context']=oath_context_document(npc.oath_context)
    if npc.talent_facts is None:
        del document['talent_facts']
    return document


def parse_npc_allies(raw, *, path_prefix, error_type):
    """Original same-side NPC actors use the standalone generated NPC source."""
    if type(raw) is not list:
        raise error_type(Code.INVALID_INPUT,'NPC allies require an ordered array.',path=path_prefix)
    allies=[]
    for index,row in enumerate(raw):
        path=f'{path_prefix}/{index}'
        if type(row) is not dict or set(row)!={'actor_id','npc'}:
            raise error_type(Code.INVALID_INPUT,'An NPC ally requires actor_id and its complete npc source.',path=path)
        npc=parse_generated_components(row['npc'],path_prefix=path+'/npc',error_type=error_type)
        allies.append(build_value(error_type,path,npc.participant,row['actor_id'],side=CombatSide.PLAYERS_AND_ALLIES))
    return tuple(allies)


def npc_allies_document(allies):
    return [dict(actor_id=ally.state.actor_id,npc=generated_components_document(ally.definition.generated_components))
        for ally in allies]


def parse_facts(data: dict) -> PcMeleeFacts:
    return PcMeleeFacts(**data)


def facts_document(facts: PcMeleeFacts) -> dict:
    document = asdict(facts)
    if document.get('daylight_confirmed') is None:
        document.pop('daylight_confirmed',None)
    return document


def _parse_close_shooting_policies(data, *, path_prefix, error_type):
    name = 'npc_close_shooting_protection_policies'
    if name not in data:
        return None
    path = path_prefix + '/' + name
    raw = data[name]
    if type(raw) is not list or not raw:
        raise error_type(Code.INVALID_INPUT, 'Close Shooting policies require a nonempty list', path=path)
    policies = []
    for index, value in enumerate(raw):
        item_path = path + '/' + str(index)
        if (type(value) is not dict or set(value) != {'actor_id','skill'}
                or type(value['skill']) is not str):
            raise error_type(Code.INVALID_INPUT, 'Close Shooting policy requires actor_id and skill', path=item_path)
        policies.append(build_value(error_type,item_path,PcNpcCloseShootingProtectionPolicy,
            value['actor_id'],Skill(value['skill'])))
    return tuple(policies)


def parse_scenario(data: dict, *, path_prefix: str, error_type: type[PcMeleeInputError]) -> PcMeleeScenario:
    try:
        return _parse_scenario(data, path_prefix=path_prefix, error_type=error_type)
    except PcMeleeInputError:
        raise
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix) from error


def _parse_short_range_opening(data, *, path_prefix, error_type):
    name = 'short_range_opening'
    if name not in data:
        return None
    raw = data[name]
    path = path_prefix + '/' + name
    if type(raw) is not dict or set(raw) != {'party_clustered_confirmed','npc_approach_clear_confirmed'}:
        raise error_type(Code.INVALID_INPUT, 'Short opening requires its complete closed confirmations', path=path)
    return build_value(error_type, path, PcShortRangeOpening, **raw)


def _parse_battlefield(data, *, path_prefix, error_type):
    raw = data.get('battlefield')
    if raw is None:
        return None
    path = path_prefix + '/battlefield'
    if (type(raw) is not dict or not {'initial_range','two_handed_max_range'} <= raw.keys()
            or set(raw)-{'initial_range','two_handed_max_range','airspace','zone_features','visibility','darkness','enemy_zone_blocking','dismounted_mount_policy','dismounted_mounts_are_combatants'}):
        raise error_type(Code.INVALID_INPUT, 'Battlefield requires its complete scene ranges', path=path)
    return build_value(error_type, path, PcBattlefieldSpec,
        RangedWeaponRange(raw['initial_range']), RangedWeaponRange(raw['two_handed_max_range']),
        airspace=parse_airspace(raw.get('airspace'),path=path+'/airspace',error_type=error_type),
        **parse_scene_features(raw,path=path,error_type=error_type))


def parse_music_acoustics(raw, *, path, error_type):
    if raw is None:
        return None
    if (type(raw) is not dict or set(raw) != {'audible_confirmed', 'blocked_zone_pairs'}
            or type(raw['blocked_zone_pairs']) is not list
            or any(type(pair) is not list for pair in raw['blocked_zone_pairs'])):
        raise error_type(Code.INVALID_INPUT, 'Music acoustics require complete GM hearing facts and Zone pairs', path=path)
    return build_value(error_type, path, BattlefieldMusicAcoustics, raw['audible_confirmed'],
        tuple(tuple(pair) for pair in raw['blocked_zone_pairs']))


def parse_scene_features(raw,*,path,error_type):
    return dict(zone_features=tuple(build_value(error_type,f'{path}/zone_features/{index}',
            PcZoneFeatures,**feature) for index,feature in enumerate(raw.get('zone_features',()))),
        visibility=tuple(build_value(error_type,f'{path}/visibility/{index}',PcVisibilityFact,**fact)
            for index,fact in enumerate(raw.get('visibility',()))),darkness=raw.get('darkness',False),
        enemy_zone_blocking=raw.get('enemy_zone_blocking',False),
        dismounted_mount_policy=DismountedMountPolicy(raw.get('dismounted_mount_policy','wait_and_recover')),
        dismounted_mounts_are_combatants=raw.get('dismounted_mounts_are_combatants',False))


def parse_airspace(raw,*,path,error_type):
    if raw is None:
        return None
    if type(raw) is not dict or set(raw)!={'open_sky_confirmed','fall_hazard_rating'}:
        raise error_type(Code.INVALID_INPUT,'Airspace requires explicit open sky and falling Hazard facts',path=path)
    return build_value(error_type,path,PcAirspaceSpec,**raw)


def _parse_blunderbuss_nearby(data, *, path_prefix, error_type):
    name = 'blunderbuss_nearby'
    if name not in data:
        return None
    raw = data[name]
    path = path_prefix + '/' + name
    if (type(raw) is not dict or set(raw) != {'initial_npc_clustered_confirmed','target_priority'}
            or type(raw['target_priority']) is not list):
        raise error_type(Code.INVALID_INPUT, 'Blunderbuss nearby requires its complete closed source', path=path)
    return build_value(error_type,path,PcBlunderbussNearby,
        raw['initial_npc_clustered_confirmed'],tuple(raw['target_priority']))


def _parse_combat_equipment(raw,*,path,error_type):
    if raw is None:
        return None
    return tuple(build_value(error_type,f'{path}/{index}',PcWeaponItem,
        item['id'],PcMeleeWeapon(item['weapon']),PcItemLocation(item['location']),
        None if item['hand'] is None else PcTwoHandedGrip.BOTH if item['hand']=='both'
        else PcWeaponHand(item['hand']),initially_loaded=item.get('initially_loaded'),quantity=item.get('quantity',1),
        initial_charges=item.get('initial_charges',0),gm_fit_confirmed=item.get('gm_fit_confirmed'))
        for index,item in enumerate(raw))


def _parse_participant(data, *, path_prefix, error_type):
    build = partial(build_value, error_type)
    close_shooting_protection_skill = None
    if 'close_shooting_protection_skill' in data:
        raw = data['close_shooting_protection_skill']
        if type(raw) is not str or raw not in ('melee', 'athletics'):
            raise error_type(Code.INVALID_INPUT, 'PC Close Shooting Protection requires Melee or Athletics',
                path=path_prefix + '/close_shooting_protection_skill')
        close_shooting_protection_skill = Skill(raw)
    backup = data['backup_weapon_policy']
    if backup is not None and (type(backup) is not dict or set(backup) != {'weapon','preferred_hand'}):
        raise error_type(Code.INVALID_INPUT,'backup requires its complete closed weapon and preferred hand',
            path=path_prefix + '/backup_weapon_policy')
    shield = None
    if 'shield' in data:
        raw = data['shield']
        if type(raw) is not dict or set(raw) != {'initial_hand', 'hand_conflict_policy', 'recovery_policy'}:
            raise error_type(Code.INVALID_INPUT, 'shield requires its complete closed loadout',
                path=path_prefix + '/shield')
        shield = build(path_prefix + '/shield', PcShieldLoadout,
            PcWeaponHand(raw['initial_hand']), PcShieldHandConflictPolicy(raw['hand_conflict_policy']),
            PcShieldRecoveryPolicy(raw['recovery_policy']))
    aim_second_action_policy = None
    if 'aim_second_action_policy' in data:
        raw = data['aim_second_action_policy']
        if type(raw) is not dict or set(raw) != {'minimum_remaining_session_spends'}:
            raise error_type(Code.INVALID_INPUT, 'Aim Second Action requires its complete closed policy',
                path=path_prefix + '/aim_second_action_policy')
        aim_second_action_policy = build(path_prefix + '/aim_second_action_policy', PcAimSecondActionPolicy, **raw)
    combat_equipment=_parse_combat_equipment(data.get('combat_equipment'),
        path=path_prefix+'/combat_equipment',error_type=error_type)
    requirements=weapon_ranged_requirements(tuple(item.weapon for item in combat_equipment or ()))
    pc_raw = dict(data["pc"])
    if 'medical' in pc_raw:
        pc_raw['medical']=parse_medical_preparation(pc_raw['medical'],path=path_prefix+'/pc/medical',error_type=error_type)
    pc_raw['tools'] = parse_tool_item_sources(pc_raw.get('tools', []),
        path_prefix=path_prefix+'/pc/tools', error_type=error_type)
    pc_raw["weapon"] = PcMeleeWeapon(pc_raw["weapon"])
    if 'pistol' in pc_raw:
        raise error_type(Code.INVALID_INPUT, 'PC pistol profile key was replaced by ranged',
            path=path_prefix + '/pc/pistol')
    if pc_raw['weapon'] in PC_RANGED_WEAPONS and combat_equipment is None:
        raise error_type(Code.INVALID_INPUT,'Shooting requires its complete physical weapon inventory',
            path=path_prefix+'/combat_equipment')
    if requirements is not None and 'ranged' not in pc_raw:
        raise error_type(Code.INVALID_INPUT,'Shooting inventory requires its complete actor ranged profile',
            path=path_prefix+'/pc/ranged')
    if 'ranged' in pc_raw:
        raw = pc_raw['ranged']
        if requirements is None or type(raw) is not dict:
            raise error_type(Code.INVALID_INPUT,'ranged requires an actual Shooting inventory',
                path=path_prefix+'/pc/ranged')
        fields = {'ballistic_skill', 'shooting', 'ammunition_supply_confirmed'}
        if requirements.exacting:
            fields.add('reload_hand_policy')
        if requirements.firearm:
            fields.update(('has_blackpowder_lore', 'has_blackpowder_kit'))
        if requirements.repeater:
            fields.add('repeater_bonus_policy')
        if set(raw) != fields:
            raise error_type(Code.INVALID_INPUT, 'ranged requires the complete closed profile for its whole inventory',
                path=path_prefix + '/pc/ranged')
        options = dict(raw)
        if 'reload_hand_policy' in raw:
            options['reload_hand_policy'] = PcRangedReloadHandPolicy(raw['reload_hand_policy'])
        if 'repeater_bonus_policy' in raw:
            options['repeater_bonus_policy'] = PcRepeaterBonusPolicy(raw['repeater_bonus_policy'])
        pc_raw['ranged'] = build(path_prefix + '/pc/ranged', PcRangedProfile, **options)
    pc = build(path_prefix + "/pc", PcMeleeDefinition, **pc_raw)
    fate_raw = dict(data["fate"])
    fate_raw["spends"] = tuple(build(f"{path_prefix}/fate/spends/{index}", FateSpendRecord,
        **dict(record, kind=FateSpendKind(record["kind"]), funding=FateSpendFunding(record["funding"])))
        for index, record in enumerate(fate_raw["spends"]))
    fate_raw["refreshes"] = tuple(build(f"{path_prefix}/fate/refreshes/{index}", FateRefreshRecord, **record)
        for index, record in enumerate(fate_raw["refreshes"]))
    fate_raw["burns"] = tuple(build(f"{path_prefix}/fate/burns/{index}", FateBurnRecord,
        **dict(record, kind=FateBurnKind(record["kind"]))) for index, record in enumerate(fate_raw["burns"]))
    fate_raw["resource_event_ids"] = tuple(fate_raw["resource_event_ids"])
    fate = build(path_prefix + "/fate", FateSessionState, **fate_raw)
    near_miss = (None if data["near_miss_policy"] is None else
        build(path_prefix + "/near_miss_policy", PcNearMissPolicy, **data["near_miss_policy"]))
    glorious = (None if data["glorious_policy"] is None else
        build(path_prefix + "/glorious_policy", PcGloriousPolicy,
            **dict(data["glorious_policy"],skills=tuple(Skill(value)
                for value in data["glorious_policy"]["skills"]))))
    help_policy = (None if data["help_policy"] is None else
        build(path_prefix + "/help_policy", PcHelpPolicy,
            **dict(data["help_policy"],target=PcHelpTarget(data["help_policy"]["target"]),
                skill=Skill(data["help_policy"]["skill"]))))
    ally_recover_policy = (None if data["ally_recover_policy"] is None else
        build(path_prefix + "/ally_recover_policy",PcAllyRecoverPolicy,**data["ally_recover_policy"]))
    backup_weapon_policy = (None if data["backup_weapon_policy"] is None else
        build(path_prefix + "/backup_weapon_policy", PcBackupWeaponPolicy,
            **dict(data["backup_weapon_policy"],
                weapon=PcMeleeWeapon(data["backup_weapon_policy"]["weapon"]),
                preferred_hand=PcWeaponHand(data["backup_weapon_policy"]["preferred_hand"]))))
    wizard = None
    if 'wizard' in data:
        raw = data['wizard']
        wizard = build(path_prefix + '/wizard', PcWizardProfile,
            **dict(raw, lores=tuple(raw['lores']), memorised_spells=tuple(PcSpellId(value)
                for value in raw['memorised_spells'])))
    return build(path_prefix, PcMeleeParticipant, data["actor_id"], pc, fate,
        PcMeleePolicy(data["policy"]), PcFatePolicy(data["fate_policy"]),
        PcRandomSidePolicy(data["random_side_policy"]), PcHeavyWoundPolicy(data["heavy_wound_policy"]),
        (None if data["initial_weapon_hand"] is None else PcTwoHandedGrip.BOTH
            if data["initial_weapon_hand"] == "both" else PcWeaponHand(data["initial_weapon_hand"])),
        tuple(data["target_priority"]),
        tuple(build(f"{path_prefix}/defeat_decisions/{index}", MinionDefeatDecision,
            **dict(record, disposition=NpcDefeatDisposition(record["disposition"])))
            for index, record in enumerate(data["defeat_decisions"])),
        near_miss_policy=near_miss,glorious_policy=glorious,help_policy=help_policy,
        aim_second_action_policy=aim_second_action_policy,
        wizard=wizard, armour_worn=data.get('armour_worn'),
        armour=None if 'armour' not in data else parse_armour_loadout(data['armour'],
            path_prefix=path_prefix+'/armour', error_type=error_type),
        rider_kind=None if data.get('rider_kind') is None else RiderKind(data['rider_kind']),
        agilulf_code_confirmed=data.get('agilulf_code_confirmed'),
        mount=None if data.get('mount') is None else CombatMount(data['mount']),
        combat_equipment=combat_equipment,
        talents=parse_acquired_talents(data.get('talents',[]),path=path_prefix+'/talents',error_type=error_type),
        oath_context=parse_oath_context(data.get('oath_context'),path=path_prefix+'/oath_context',error_type=error_type),
        talent_facts=None if data.get('talent_facts') is None else parse_talent_owner_facts(
            data['talent_facts'],path=path_prefix+'/talent_facts',error_type=error_type),
        consumables=tuple(build(f'{path_prefix}/consumables/{index}', ConsumableItem,
            **dict(item, kind=ConsumableKind(item['kind'])))
            for index,item in enumerate(data.get('consumables', []))),
        ally_recover_policy=ally_recover_policy,backup_weapon_policy=backup_weapon_policy,shield=shield,
        close_shooting_protection_skill=close_shooting_protection_skill)


def _parse_attack_effect(data, *, path_prefix, error_type):
    kind=data['kind']
    if type(kind) is not str:
        raise error_type(Code.INVALID_INPUT,'PC Melee attack effect kind must be an exact string',path=path_prefix+'/kind')
    raw=dict(data)
    del raw['kind']
    if kind=='prone_before_give_ground':
        if set(raw)!={'rule_id','affects_monstrosities'}:
            raise error_type(Code.INVALID_INPUT,'pre-Stagger Prone requires its closed complete source',path=path_prefix)
        return build_value(error_type,path_prefix,ProneBeforeGiveGroundSpec,**raw)
    if kind!='condition_on_hit':
        raise error_type(Code.INVALID_INPUT,'unsupported PC Melee attack effect kind',path=path_prefix+'/kind')
    raw['condition']=Condition(raw['condition'])
    raw['classification']=EffectClassification(raw['classification'])
    return build_value(error_type,path_prefix,ConditionOnHitSpec,**raw)


def _attack_effect_document(effect):
    if type(effect) is ProneBeforeGiveGroundSpec:
        return {'kind':'prone_before_give_ground','rule_id':effect.rule_id,
            'affects_monstrosities':effect.affects_monstrosities}
    if type(effect) is ConditionOnHitSpec:
        return {'kind':'condition_on_hit','condition':effect.condition.value,
            'rule_id':effect.rule_id,'classification':effect.classification.value}
    raise TypeError('unsupported PC Melee attack effect type')


def _parse_npc_attack(data, *, skill, path_prefix, error_type, shooting=False):
    if shooting:
        required = {'id','source_rule_id','skill','test_profile','damage','range_min',
            'range_max','hands','secondary_effects','ignores_armour'}
        if (set(data) != required or type(data['skill']) is not str or data['skill'] != 'shooting'
                or type(data['range_min']) is not str
                or type(data['ignores_armour']) is not bool):
            raise error_type(Code.INVALID_INPUT,'NPC ranged source requires its complete closed Shooting profile',path=path_prefix)
    elif any(name in data for name in ('range_min', 'ignores_armour')) or (
            'skill' in data and skill is Skill.MELEE):
        raise error_type(Code.INVALID_INPUT,'explicit Shooting fields belong only to a complete NPC ranged source',path=path_prefix)
    return build_value(error_type,path_prefix,NpcAttackProfile,
        data['id'],data['source_rule_id'],skill,
        InlineProfile(**data['test_profile']),DamageProfile(**data['damage']),
        RangedWeaponRange(data['range_min']) if shooting else RangedWeaponRange.CLOSE,RangedWeaponRange(data['range_max']),
        None if data['hands'] is None else RangedWeaponHands(data['hands']),
        ignores_armour=data['ignores_armour'] if shooting else False,
        secondary_effects=tuple(_parse_attack_effect(effect,
            path_prefix=f'{path_prefix}/secondary_effects/{index}',error_type=error_type)
            for index,effect in enumerate(data['secondary_effects'])))


def _npc_attack_document(attack):
    if attack.skill is Skill.BRAWN:
        document = {'id':attack.id,'source_rule_id':attack.source_rule_id,'skill':'brawn',
            'test_profile':asdict(attack.test_profile),'range_min':attack.range_min.value,
            'range_max':attack.range_max.value,'hands':None if attack.hands is None else attack.hands.value}
        if attack.condition_impact is not None:
            impact=attack.condition_impact
            document['impact']={'kind':'condition','condition':impact.condition.value,
                'rule_id':impact.rule_id,'classification':impact.classification.value}
        else:
            document.update(damage=asdict(attack.damage),secondary_effects=[
                _attack_effect_document(effect) for effect in attack.secondary_effects])
        return document
    if attack.skill is Skill.THROWING:
        return _throwing_attack_document(attack)
    document = {'id':attack.id,'source_rule_id':attack.source_rule_id,
        'test_profile':asdict(attack.test_profile),'damage':asdict(attack.damage),
        'range_max':attack.range_max.value,'hands':None if attack.hands is None else attack.hands.value,
        'secondary_effects':[_attack_effect_document(effect) for effect in attack.secondary_effects]}
    if attack.skill is Skill.SHOOTING:
        document.update(skill=attack.skill.value,range_min=attack.range_min.value,
            ignores_armour=attack.ignores_armour)
    return document


def _parse_net_attack(data, *, path_prefix, error_type):
    if set(data)!={'id','source_rule_id','skill','test_profile','range_min','range_max','hands','impact'}:
        raise error_type(Code.INVALID_INPUT,'Net requires its closed complete explicit profile',path=path_prefix)
    impact = data['impact']
    if set(impact)!={'kind','condition','rule_id','classification'} or impact['kind']!='condition':
        raise error_type(Code.INVALID_INPUT,'Net requires its complete primary Condition impact',path=path_prefix+'/impact')
    return build_value(error_type,path_prefix,NpcAttackProfile,
        data['id'],data['source_rule_id'],Skill(data['skill']),InlineProfile(**data['test_profile']),
        None,RangedWeaponRange(data['range_min']),RangedWeaponRange(data['range_max']),
        RangedWeaponHands(data['hands']),condition_impact=ConditionImpactSpec(
            Condition(impact['condition']),impact['rule_id'],EffectClassification(impact['classification'])))


def _net_attack_document(attack):
    impact = attack.condition_impact
    return {'id':attack.id,'source_rule_id':attack.source_rule_id,'skill':attack.skill.value,
        'test_profile':asdict(attack.test_profile),'range_min':attack.range_min.value,
        'range_max':attack.range_max.value,'hands':attack.hands.value,
        'impact':{'kind':'condition','condition':impact.condition.value,
            'rule_id':impact.rule_id,'classification':impact.classification.value}}


def _throwing_attack_document(attack):
    document = {'id':attack.id,'source_rule_id':attack.source_rule_id,'skill':'throwing',
        'test_profile':asdict(attack.test_profile),'range_min':attack.range_min.value,
        'range_max':attack.range_max.value,'hands':None if attack.hands is None else attack.hands.value}
    if attack.condition_impact is not None:
        document['impact']=dict(kind='condition',**_plain(asdict(attack.condition_impact)))
    elif attack.hazard_impact is not None:
        document['impact']=dict(kind='hazard',**_plain(asdict(attack.hazard_impact)))
    else:
        document.update(damage=asdict(attack.damage),secondary_effects=[
            _attack_effect_document(effect) for effect in attack.secondary_effects])
    return document


def _parse_throwing_attack(data, *, path_prefix, error_type):
    common={'id','source_rule_id','skill','test_profile','range_min','range_max','hands'}
    expected=common | ({'impact'} if 'impact' in data else {'damage','secondary_effects'})
    if set(data)!=expected or data['skill']!='throwing':
        raise error_type(Code.INVALID_INPUT,'Throwing requires its complete physical impact profile',path=path_prefix)
    condition=hazard=None
    if 'impact' in data:
        raw=data['impact']
        if raw.get('kind')=='condition' and set(raw)=={'kind','condition','rule_id','classification'}:
            condition=ConditionImpactSpec(Condition(raw['condition']),raw['rule_id'],EffectClassification(raw['classification']))
        elif (raw.get('kind')=='hazard' and set(raw)=={'kind','rating','avoidance_skill','rule_id','inflicts_wound',
                'failure_conditions','classification','repeated_condition_replacements'}
                and raw['repeated_condition_replacements']==[]):
            hazard=HazardImpactSpec(raw['rating'],Skill(raw['avoidance_skill']),raw['rule_id'],
                raw['inflicts_wound'],tuple(Condition(value) for value in raw['failure_conditions']),
                EffectClassification(raw['classification']))
        else:
            raise error_type(Code.INVALID_INPUT,'Throwing requires its complete Condition or Hazard source',path=path_prefix+'/impact')
    return build_value(error_type,path_prefix,NpcAttackProfile,data['id'],data['source_rule_id'],Skill.THROWING,
        InlineProfile(**data['test_profile']),None if 'impact' in data else DamageProfile(**data['damage']),
        RangedWeaponRange(data['range_min']),RangedWeaponRange(data['range_max']),
        None if data['hands'] is None else RangedWeaponHands(data['hands']),condition_impact=condition,hazard_impact=hazard,
        secondary_effects=tuple(_parse_attack_effect(effect,path_prefix=f'{path_prefix}/secondary_effects/{index}',
            error_type=error_type) for index,effect in enumerate(data.get('secondary_effects',()))))


def _parse_brawn_attack(data, *, path_prefix, error_type):
    common={'id','source_rule_id','skill','test_profile','range_min','range_max','hands'}
    expected=common | ({'impact'} if 'impact' in data else {'damage','secondary_effects'})
    if set(data)!=expected or data['skill']!='brawn':
        raise error_type(Code.INVALID_INPUT,'Brawn requires its complete physical or Unarmed profile',path=path_prefix)
    impact=None
    if 'impact' in data:
        raw=data['impact']
        if set(raw)!={'kind','condition','rule_id','classification'} or raw['kind']!='condition':
            raise error_type(Code.INVALID_INPUT,'Unarmed requires its complete primary Condition impact',path=path_prefix+'/impact')
        impact=ConditionImpactSpec(Condition(raw['condition']),raw['rule_id'],EffectClassification(raw['classification']))
    return build_value(error_type,path_prefix,NpcAttackProfile,data['id'],data['source_rule_id'],Skill.BRAWN,
        InlineProfile(**data['test_profile']),None if impact is not None else DamageProfile(**data['damage']),
        RangedWeaponRange(data['range_min']),RangedWeaponRange(data['range_max']),
        None if data['hands'] is None else RangedWeaponHands(data['hands']),condition_impact=impact,
        secondary_effects=tuple(_parse_attack_effect(effect,path_prefix=f'{path_prefix}/secondary_effects/{index}',
            error_type=error_type) for index,effect in enumerate(data.get('secondary_effects',()))))


def _parse_scenario(data, *, path_prefix, error_type):
    build = partial(build_value, error_type)
    party = tuple(_parse_participant(member, path_prefix=f"{path_prefix}/party/{index}", error_type=error_type)
                  for index, member in enumerate(data["party"]))
    enemies = []
    net_policies = []
    ranged_policies = []
    for index, enemy in enumerate(data["enemies"]):
        path = f"{path_prefix}/enemies/{index}"
        definition_raw = enemy["definition"]
        generated_source='generated_components' in definition_raw
        if generated_source:
            if 'attack' in definition_raw or not definition_raw.get('attacks'):
                raise error_type(Code.INVALID_INPUT,'generated NPC requires its complete attacks array',path=path+'/definition')
            raw_attacks=definition_raw['attacks']
        else:
            if 'attacks' in definition_raw:
                raise error_type(Code.INVALID_INPUT,'attacks array belongs only to generated equipment',path=path+'/definition/attacks')
            raw_attacks=(definition_raw['attack'],)
        attack_raw = raw_attacks[0]
        protection_raw = definition_raw["protection"]
        shooting = any(raw.get('skill') == 'shooting' for raw in raw_attacks)
        if ('ranged' in enemy) != shooting:
            raise error_type(Code.INVALID_INPUT,'ranged source is required exactly for NPC Shooting',path=path+'/ranged')
        if shooting:
            raw = enemy['ranged']
            if type(raw) is not dict or not set(_NPC_RANGED_FIELDS) <= raw.keys() or raw.keys()-set(_NPC_RANGED_FIELDS)-{'initial_weapon'}:
                raise error_type(Code.INVALID_INPUT,'NPC ranged requires its complete closed source facts',path=path+'/ranged')
            ranged_policies.append(build(path+'/ranged',PcNpcRangedPolicy,
                enemy['actor_id'],raw['has_blackpowder_lore'],
                raw['has_blackpowder_kit'],raw['ammunition_supply_confirmed'],
                None if raw['reload_hand_policy'] is None else PcNpcRangedReloadHandPolicy(raw['reload_hand_policy']),
                initial_weapon=None if raw.get('initial_weapon') is None else parse_weapon_item_source(
                    raw['initial_weapon'],path_prefix=path+'/ranged/initial_weapon',error_type=error_type)))
        attacks=tuple(_parse_brawn_attack(raw,path_prefix=path+f'/definition/attacks/{i}',error_type=error_type)
            if raw.get('skill')=='brawn' else _parse_throwing_attack(raw,path_prefix=path+f'/definition/attacks/{i}',error_type=error_type)
            if raw.get('skill')=='throwing' else _parse_npc_attack(raw,
                skill=Skill.SHOOTING if raw.get('skill')=='shooting' else Skill.MELEE,
                path_prefix=path+f'/definition/attacks/{i}' if generated_source else path+'/definition/attack',
                error_type=error_type,shooting=raw.get('skill')=='shooting') for i,raw in enumerate(raw_attacks))
        attack=attacks[0]
        has_trample = 'trample_attack' in definition_raw
        if has_trample != (definition_raw['id']=='pc-book-npc:great_stag'):
            raise error_type(Code.INVALID_INPUT,'trample_attack is required only for canonical Great Stag',
                path=path+'/definition/trample_attack')
        net_goblin = definition_raw['id']==NET_DEFINITION_ID
        if ('net_attack' in definition_raw)!=net_goblin or ('net_policy' in enemy)!=net_goblin:
            raise error_type(Code.INVALID_INPUT,'net_attack and net_policy are required only for canonical Net loadouts',path=path)
        has_armoured = 'armoured' in definition_raw['resilience']
        if (net_goblin and not has_armoured or definition_raw['id'].startswith('pc-book-npc:')
                and not net_goblin and has_armoured):
            raise error_type(Code.INVALID_INPUT,'canonical armoured metadata is required only for Net loadouts',
                path=path+'/definition/resilience')
        if has_armoured and type(definition_raw['resilience']['armoured']) is not bool:
            raise error_type(Code.INVALID_INPUT,'explicit armoured metadata must be an exact boolean',
                path=path+'/definition/resilience/armoured')
        if net_goblin:
            attacks = (*attacks,_parse_net_attack(definition_raw['net_attack'],
                path_prefix=path+'/definition/net_attack',error_type=error_type))
            raw_policy = enemy['net_policy']
            if set(raw_policy)!={'initial_count','mode'}:
                raise error_type(Code.INVALID_INPUT,'Net policy requires complete closed stock and mode',path=path+'/net_policy')
            net_policies.append(build(path+'/net_policy',PcNpcNetPolicy,enemy['actor_id'],
                raw_policy['initial_count'],PcNpcNetMode(raw_policy['mode'])))
        if has_trample:
            trample_raw = definition_raw['trample_attack']
            if set(trample_raw)!={'id','source_rule_id','skill','test_profile','damage','range_max','hands','secondary_effects'}:
                raise error_type(Code.INVALID_INPUT,'Trample requires its closed complete explicit profile',
                    path=path+'/definition/trample_attack')
            trample = _parse_npc_attack(trample_raw,skill=Skill(trample_raw['skill']),
                path_prefix=path+'/definition/trample_attack',error_type=error_type)
            attacks = (*attacks,trample)
        resilience = build(path + "/definition/resilience", ResilienceProfile, **definition_raw["resilience"])
        generated = None
        protection_profiles = (NpcProtectionProfile(protection_raw["source_rule_id"],
            Skill(protection_raw["skill"]), InlineProfile(**protection_raw["test_profile"])),)
        if 'generated_components' in definition_raw:
            raw = definition_raw['generated_components']
            generated = parse_generated_components(raw,
                path_prefix=path+'/definition/generated_components', error_type=error_type)
            alternate = definition_raw['alternate_protection']
            protection_profiles += (NpcProtectionProfile(alternate['source_rule_id'],
                Skill(alternate['skill']), InlineProfile(**alternate['test_profile'])),)
            if 'endurance_protection' in definition_raw:
                endurance=definition_raw['endurance_protection']
                protection_profiles += (NpcProtectionProfile(endurance['source_rule_id'],
                    Skill(endurance['skill']),InlineProfile(**endurance['test_profile'])),)
        definition = build(path + "/definition", NpcDefinition,
            definition_raw["id"], definition_raw["source_rule_id"],
            TargetInjuryPolicy(definition_raw["injury_policy"]), definition_raw["wound_limit"],
            resilience, attacks, protection_profiles, generated_components=generated,
            talents=parse_acquired_talents(definition_raw.get('talents', []),
                path=path+'/definition/talents', error_type=error_type),
            talent_facts=(None if definition_raw.get('talent_facts') is None else parse_talent_owner_facts(
                definition_raw['talent_facts'], path=path+'/definition/talent_facts', error_type=error_type)))
        from towr.domain.armour_models import armour_burden_sources
        initial_conditions=ConditionState(frozenset((Condition.BURDENED,))
            if generated is not None and armour_burden_sources(generated.armour,generated.strength)
            else frozenset())
        from towr.domain.injury_models import CharacterInjuryState
        initial_injury=(CharacterInjuryState(conditions=initial_conditions)
            if definition.injury_policy is TargetInjuryPolicy.CHAMPION else
            ProfileInjuryState(0, definition.wound_limit,initial_conditions))
        state = build(path, NpcParticipantState, enemy["actor_id"], definition.id,
            CombatSide.OPPOSITION, initial_injury, tuple(profile.id for profile in attacks),
            resilience, generated.participant(enemy['actor_id']).state.wields_weapon
                if generated is not None else attack.hands is not None, enemy["holds_shield"],
            tool_inventory=initial_tool_inventory(enemy['actor_id'], () if generated is None else generated.tools))
        enemies.append(NpcParticipantSnapshot(definition, state))
    allies=parse_npc_allies(data.get('npc_allies',[]),path_prefix=path_prefix+'/npc_allies',error_type=error_type)
    from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
    ranged_policies.extend(pc_npc_ranged_policy_for_generated(ally.definition.generated_components,ally.state.actor_id)
        for ally in allies if ally.definition.generated_components.ranged is not None)
    return build(path_prefix, PcMeleeScenario, data["id"], party,
        data["day_id"], tuple(enemies), build(path_prefix + "/facts", PcMeleeFacts, **data["facts"]),
        tuple(data["pc_activation_order"]), tuple(data["enemy_activation_order"]),
        tuple(data["enemy_target_priority"]), data["max_rounds"],
        None if data['npc_broken_exit_policy'] is None else build(path_prefix+'/npc_broken_exit_policy',
            PcAdjacentNpcExitPolicy,**data['npc_broken_exit_policy']),
        tuple(build(f'{path_prefix}/npc_help_policies/{index}',PcNpcHelpPolicy,**policy)
            for index,policy in enumerate(data['npc_help_policies'])),
        npc_extra_attack_actor_ids=tuple(data['npc_extra_attack_actor_ids']),
        npc_defeat_decisions=tuple(build(f'{path_prefix}/npc_defeat_decisions/{index}',
            MinionDefeatDecision,**dict(decision,disposition=NpcDefeatDisposition(decision['disposition'])))
            for index,decision in enumerate(data.get('npc_defeat_decisions',()))),
        npc_allies=allies,player_side_activation_order=(None if data.get('player_side_activation_order') is None
            else tuple(data['player_side_activation_order'])),
        short_range_opening=_parse_short_range_opening(data,path_prefix=path_prefix,error_type=error_type),
        battlefield=_parse_battlefield(data,path_prefix=path_prefix,error_type=error_type),
        music_acoustics=parse_music_acoustics(data.get('music_acoustics'),
            path=path_prefix+'/music_acoustics', error_type=error_type),
        surgery_risk=parse_surgery_risk(data.get('surgery_risk'),path=path_prefix+'/surgery_risk',error_type=error_type),
        single_combat_pairs=tuple(build(f'{path_prefix}/single_combat_pairs/{index}',
            PcSingleCombatPair,**pair) for index,pair in enumerate(data.get('single_combat_pairs',()))),
        blunderbuss_nearby=_parse_blunderbuss_nearby(data,path_prefix=path_prefix,error_type=error_type),
        npc_close_shooting_protection_policies=_parse_close_shooting_policies(data,
            path_prefix=path_prefix,error_type=error_type),
        npc_net_policies=tuple(net_policies),
        npc_ranged_policies=tuple(ranged_policies),
        npc_grudge_policies=tuple(build(f'{path_prefix}/npc_grudge_policies/{index}',PcNpcGrudgePolicy,**policy)
            for index,policy in enumerate(data['npc_grudge_policies'])),
        npc_blood_rage_actor_ids=tuple(data['npc_blood_rage_actor_ids']),
        npc_flagellant_policies=tuple(build(f'{path_prefix}/npc_flagellant_policies/{index}',
            PcFlagellantPolicy,policy['actor_id'],PcFeelNoPainPolicy(policy['feel_no_pain']),
            policy['recover_when_wounded']) for index,policy in enumerate(data['npc_flagellant_policies'])),
        npc_warped_form_policies=tuple(build(f'{path_prefix}/npc_warped_form_policies/{index}',
            PcWarpedFormPolicy,policy['actor_id'],tuple(policy['close_actor_ids']),
            tuple(build(f'{path_prefix}/npc_warped_form_policies/{index}/npc_defeat_decisions/{decision_index}',
                MinionDefeatDecision,**dict(decision,disposition=NpcDefeatDisposition(decision['disposition'])))
                for decision_index,decision in enumerate(policy['npc_defeat_decisions'])))
            for index,policy in enumerate(data['npc_warped_form_policies'])))


def scenario_document(scenario: PcMeleeScenario) -> dict:
    validate_pc_melee_scenario_admission(scenario)
    party = _plain([asdict(member) for member in scenario.party])
    for member, source in zip(party, scenario.party, strict=True):
        if source.pc.tools:
            member['pc']['tools'] = tool_item_sources_document(source.pc.tools)
        else:
            del member['pc']['tools']
        for name in ('armour','rider_kind','agilulf_code_confirmed'):
            if member[name] is None:
                del member[name]
        for name in ('throwing','brawn','ballistic_skill','fellowship','leadership'):
            if member['pc'][name] is None:
                del member['pc'][name]
        if member['mount'] is None:
            del member['mount']
        if member['combat_equipment'] is None:
            del member['combat_equipment']
        if not member['talents']:
            del member['talents']
        if member['talent_facts'] is None:
            del member['talent_facts']
        if source.oath_context is None:
            del member['oath_context']
        else:
            member['oath_context']=oath_context_document(source.oath_context)
        if member['armour_worn'] is None:
            del member['armour_worn']
        if member['wizard'] is None:
            del member['wizard']
        if not member['consumables']:
            del member['consumables']
        if member['aim_second_action_policy'] is None:
            del member['aim_second_action_policy']
        if member['close_shooting_protection_skill'] is None:
            del member['close_shooting_protection_skill']
        if member['shield'] is None:
            del member['shield']
        if member['pc']['ranged'] is None:
            del member['pc']['ranged']
        else:
            for name in tuple(member['pc']['ranged']):
                if member['pc']['ranged'][name] is None:
                    del member['pc']['ranged'][name]
    enemies = []
    for enemy in scenario.enemies:
        definition = enemy.definition
        attack, protection = definition.attacks[0], definition.protection[0]
        enemies.append({"actor_id": enemy.state.actor_id, "holds_shield": enemy.state.holds_shield, "definition": {
            "id": definition.id, "source_rule_id": definition.source_rule_id,
            "injury_policy": definition.injury_policy.value, "wound_limit": definition.wound_limit,
            "resilience": resilience_document(definition.resilience),
            "attack": _npc_attack_document(attack),
            "protection": {"source_rule_id": protection.source_rule_id,
                "skill": protection.skill.value,"test_profile": asdict(protection.test_profile)}}})
        owned_talents = acquired_talents_document(definition.talents)
        if owned_talents:
            enemies[-1]['definition']['talents'] = owned_talents
        if definition.talent_facts is not None:
            enemies[-1]['definition']['talent_facts'] = talent_owner_facts_document(definition.talent_facts)
        if definition.generated_components is not None:
            del enemies[-1]['definition']['attack']
            enemies[-1]['definition']['attacks']=[_npc_attack_document(profile) for profile in definition.attacks]
            enemies[-1]['definition']['generated_components'] = generated_components_document(definition.generated_components)
            alternate = definition.protection[1]
            enemies[-1]['definition']['alternate_protection'] = {
                'source_rule_id':alternate.source_rule_id,'skill':alternate.skill.value,
                'test_profile':asdict(alternate.test_profile)}
            if len(definition.protection)>2:
                endurance=definition.protection[2]
                enemies[-1]['definition']['endurance_protection']={
                    'source_rule_id':endurance.source_rule_id,'skill':endurance.skill.value,
                    'test_profile':asdict(endurance.test_profile)}
        if definition.id==NET_DEFINITION_ID:
            enemies[-1]['definition']['net_attack'] = _net_attack_document(definition.attacks[1])
            policy = next(policy for policy in scenario.npc_net_policies if policy.actor_id==enemy.state.actor_id)
            enemies[-1]['net_policy'] = {'initial_count':policy.initial_count,'mode':policy.mode.value}
        if any(profile.skill is Skill.SHOOTING for profile in definition.attacks):
            policy = next(policy for policy in scenario.npc_ranged_policies if policy.actor_id==enemy.state.actor_id)
            enemies[-1]['ranged'] = _plain({name:getattr(policy,name) for name in _NPC_RANGED_FIELDS})
            if policy.initial_weapon is not None:
                enemies[-1]['ranged']['initial_weapon']=weapon_item_source_document(policy.initial_weapon)
        elif definition.generated_components is None and len(definition.attacks)==2 and definition.id!=NET_DEFINITION_ID:
            trample = definition.attacks[1]
            enemies[-1]['definition']['trample_attack'] = dict(_npc_attack_document(trample),skill=trample.skill.value)
    document = {"id": scenario.id, "party": party,
        "day_id": scenario.day_id, "enemies": enemies,
        "facts": facts_document(scenario.facts),
        "pc_activation_order": list(scenario.pc_activation_order),
        "enemy_activation_order": list(scenario.enemy_activation_order),
        "enemy_target_priority": list(scenario.enemy_target_priority),
        "max_rounds": scenario.max_rounds,
        "npc_help_policies": [asdict(policy) for policy in scenario.npc_help_policies],
        "npc_extra_attack_actor_ids": list(scenario.npc_extra_attack_actor_ids),
        "npc_grudge_policies": [asdict(policy) for policy in scenario.npc_grudge_policies],
        "npc_blood_rage_actor_ids": list(scenario.npc_blood_rage_actor_ids),
        "npc_flagellant_policies": _plain([asdict(policy) for policy in scenario.npc_flagellant_policies]),
        "npc_warped_form_policies": _plain([asdict(policy) for policy in scenario.npc_warped_form_policies]),
        "npc_broken_exit_policy": None if scenario.npc_broken_exit_policy is None else asdict(scenario.npc_broken_exit_policy)}
    if scenario.npc_defeat_decisions:
        document['npc_defeat_decisions']=_plain([asdict(decision) for decision in scenario.npc_defeat_decisions])
    if scenario.npc_allies:
        document['npc_allies']=npc_allies_document(scenario.npc_allies)
    if scenario.player_side_activation_order is not None:
        document['player_side_activation_order']=list(scenario.player_side_activation_order)
    if scenario.npc_close_shooting_protection_policies is not None:
        document['npc_close_shooting_protection_policies'] = _plain([
            asdict(policy) for policy in scenario.npc_close_shooting_protection_policies])
    if scenario.single_combat_pairs:
        document['single_combat_pairs']=[asdict(pair) for pair in scenario.single_combat_pairs]
    if scenario.short_range_opening is not None:
        document['short_range_opening'] = asdict(scenario.short_range_opening)
    if scenario.battlefield is not None:
        document['battlefield'] = _plain(asdict(scenario.battlefield))
    if scenario.music_acoustics is not None:
        document['music_acoustics'] = _plain(asdict(scenario.music_acoustics))
    if scenario.surgery_risk is not None:
        document['surgery_risk'] = _plain(asdict(scenario.surgery_risk))
    if scenario.blunderbuss_nearby is not None:
        document['blunderbuss_nearby'] = {
            'initial_npc_clustered_confirmed':scenario.blunderbuss_nearby.initial_npc_clustered_confirmed,
            'target_priority':list(scenario.blunderbuss_nearby.target_priority)}
    return document
