"""Pure source-preserving PC scenario codec, without execution or RNG."""
from dataclasses import asdict
from enum import Enum
from functools import partial

from towr.adapters._json_common import build_value
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.attack_models import ConditionImpactSpec, ConditionOnHitSpec, DamageProfile, ResilienceProfile, ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition, EffectClassification
from towr.domain.fate_models import (
    FateBurnKind, FateBurnRecord, FateRefreshRecord, FateSessionState,
    FateSpendFunding, FateSpendKind, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
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
from towr.domain.pc_npc_pistol_source_models import (
    PC_NPC_PISTOL_DEFINITION_IDS, PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcNearMissPolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcAllyRecoverPolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleeParticipant, PcMeleePolicy, PcMeleeScenario,
    PcMeleeWeapon, PcRandomSidePolicy, PcHeavyWoundPolicy, PcWeaponHand, PcTwoHandedGrip, PcBackupWeaponPolicy, PcAdjacentNpcExitPolicy, validate_pc_melee_scenario_admission,
    PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy,
    PC_RANGED_WEAPONS, PC_FREE_RELOAD_WEAPONS, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
    PcShortRangeOpening, PcBlunderbussNearby, PcAimSecondActionPolicy,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


_NPC_PISTOL_FIELDS = ('initially_loaded', 'has_blackpowder_lore',
    'has_blackpowder_kit', 'ammunition_supply_confirmed', 'reload_hand_policy')


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {name: _plain(child) for name, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(child) for child in value]
    return value


def parse_facts(data: dict) -> PcMeleeFacts:
    return PcMeleeFacts(**data)


def facts_document(facts: PcMeleeFacts) -> dict:
    return asdict(facts)


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
    pc_raw = dict(data["pc"])
    pc_raw["weapon"] = PcMeleeWeapon(pc_raw["weapon"])
    if 'pistol' in pc_raw:
        raise error_type(Code.INVALID_INPUT, 'PC pistol profile key was replaced by ranged',
            path=path_prefix + '/pc/pistol')
    if 'ranged' in pc_raw:
        weapon = pc_raw['weapon']
        raw = pc_raw['ranged']
        fields = {'ballistic_skill', 'shooting', 'ammunition_supply_confirmed'}
        if weapon not in PC_FREE_RELOAD_WEAPONS:
            fields.update(('initiative', 'dexterity', 'initially_loaded', 'reload_hand_policy'))
        if weapon in (PcMeleeWeapon.PISTOL, PcMeleeWeapon.REPEATER_PISTOL,
                PcMeleeWeapon.HANDGUN, PcMeleeWeapon.REPEATER_HANDGUN, PcMeleeWeapon.BLUNDERBUSS, PcMeleeWeapon.HOCHLAND_LONG_RIFLE):
            fields.update(('has_blackpowder_lore', 'has_blackpowder_kit'))
        if weapon in (PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL,
                PcMeleeWeapon.REPEATER_CROSSBOW, PcMeleeWeapon.REPEATER_HANDGUN):
            fields.add('repeater_bonus_policy')
        if weapon is PcMeleeWeapon.HOCHLAND_LONG_RIFLE:
            fields.add('awareness')
        if weapon not in PC_RANGED_WEAPONS or type(raw) is not dict or set(raw) != fields:
            raise error_type(Code.INVALID_INPUT, 'ranged requires its complete closed weapon-specific profile',
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
                protection_skill=(None if data["help_policy"]["protection_skill"] is None else
                    Skill(data["help_policy"]["protection_skill"])))))
    ally_recover_policy = (None if data["ally_recover_policy"] is None else
        build(path_prefix + "/ally_recover_policy",PcAllyRecoverPolicy,**data["ally_recover_policy"]))
    backup_weapon_policy = (None if data["backup_weapon_policy"] is None else
        build(path_prefix + "/backup_weapon_policy", PcBackupWeaponPolicy,
            **dict(data["backup_weapon_policy"],
                weapon=PcMeleeWeapon(data["backup_weapon_policy"]["weapon"]),
                preferred_hand=PcWeaponHand(data["backup_weapon_policy"]["preferred_hand"]))))
    return build(path_prefix, PcMeleeParticipant, data["actor_id"], pc, fate,
        PcMeleePolicy(data["policy"]), PcFatePolicy(data["fate_policy"]),
        PcRandomSidePolicy(data["random_side_policy"]), PcHeavyWoundPolicy(data["heavy_wound_policy"]),
        (PcTwoHandedGrip.BOTH if data["initial_weapon_hand"] == "both"
            else PcWeaponHand(data["initial_weapon_hand"])),
        tuple(data["target_priority"]),
        tuple(build(f"{path_prefix}/defeat_decisions/{index}", MinionDefeatDecision,
            **dict(record, disposition=NpcDefeatDisposition(record["disposition"])))
            for index, record in enumerate(data["defeat_decisions"])),
        near_miss_policy=near_miss,glorious_policy=glorious,help_policy=help_policy,
        aim_second_action_policy=aim_second_action_policy,
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


def _parse_npc_attack(data, *, skill, path_prefix, error_type, pistol=False):
    if pistol:
        required = {'id','source_rule_id','skill','test_profile','damage','range_min',
            'range_max','hands','secondary_effects','ignores_armour'}
        if (set(data) != required or type(data['skill']) is not str or data['skill'] != 'shooting'
                or type(data['range_min']) is not str or data['range_min'] != 'close'
                or data['ignores_armour'] is not True):
            raise error_type(Code.INVALID_INPUT,'NPC Pistol requires its complete closed Shooting profile',path=path_prefix)
    elif any(name in data for name in ('range_min', 'ignores_armour')) or (
            'skill' in data and skill is Skill.MELEE):
        raise error_type(Code.INVALID_INPUT,'explicit Shooting fields belong only to canonical NPC Pistol',path=path_prefix)
    return build_value(error_type,path_prefix,NpcAttackProfile,
        data['id'],data['source_rule_id'],skill,
        InlineProfile(**data['test_profile']),DamageProfile(**data['damage']),
        RangedWeaponRange.CLOSE,RangedWeaponRange(data['range_max']),
        None if data['hands'] is None else RangedWeaponHands(data['hands']),
        ignores_armour=pistol,
        secondary_effects=tuple(_parse_attack_effect(effect,
            path_prefix=f'{path_prefix}/secondary_effects/{index}',error_type=error_type)
            for index,effect in enumerate(data['secondary_effects'])))


def _npc_attack_document(attack):
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


def _parse_scenario(data, *, path_prefix, error_type):
    build = partial(build_value, error_type)
    party = tuple(_parse_participant(member, path_prefix=f"{path_prefix}/party/{index}", error_type=error_type)
                  for index, member in enumerate(data["party"]))
    enemies = []
    net_policies = []
    pistol_policies = []
    for index, enemy in enumerate(data["enemies"]):
        path = f"{path_prefix}/enemies/{index}"
        definition_raw = enemy["definition"]
        attack_raw = definition_raw["attack"]
        protection_raw = definition_raw["protection"]
        pistol = definition_raw['id'] in PC_NPC_PISTOL_DEFINITION_IDS
        if ('pistol' in enemy) != pistol:
            raise error_type(Code.INVALID_INPUT,'pistol source is required only for canonical NPC Pistol',path=path+'/pistol')
        if pistol:
            raw = enemy['pistol']
            if type(raw) is not dict or set(raw) != set(_NPC_PISTOL_FIELDS):
                raise error_type(Code.INVALID_INPUT,'NPC Pistol requires its complete closed source facts',path=path+'/pistol')
            pistol_policies.append(build(path+'/pistol',PcNpcPistolPolicy,
                enemy['actor_id'],raw['initially_loaded'],raw['has_blackpowder_lore'],
                raw['has_blackpowder_kit'],raw['ammunition_supply_confirmed'],
                PcNpcPistolReloadHandPolicy(raw['reload_hand_policy'])))
        attack = _parse_npc_attack(attack_raw,skill=Skill.SHOOTING if pistol else Skill.MELEE,
            path_prefix=path+'/definition/attack',error_type=error_type,pistol=pistol)
        has_trample = 'trample_attack' in definition_raw
        if has_trample != (definition_raw['id']=='pc-book-npc:great_stag'):
            raise error_type(Code.INVALID_INPUT,'trample_attack is required only for canonical Great Stag',
                path=path+'/definition/trample_attack')
        attacks = (attack,)
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
        definition = build(path + "/definition", NpcDefinition,
            definition_raw["id"], definition_raw["source_rule_id"],
            TargetInjuryPolicy(definition_raw["injury_policy"]), definition_raw["wound_limit"],
            resilience, attacks, (NpcProtectionProfile(protection_raw["source_rule_id"],
                Skill(protection_raw["skill"]), InlineProfile(**protection_raw["test_profile"])),))
        state = build(path, NpcParticipantState, enemy["actor_id"], definition.id,
            CombatSide.OPPOSITION, ProfileInjuryState(0, definition.wound_limit), tuple(profile.id for profile in attacks),
            resilience, attack.hands is not None, enemy["holds_shield"])
        enemies.append(NpcParticipantSnapshot(definition, state))
    return build(path_prefix, PcMeleeScenario, data["id"], party,
        data["day_id"], tuple(enemies), build(path_prefix + "/facts", PcMeleeFacts, **data["facts"]),
        tuple(data["pc_activation_order"]), tuple(data["enemy_activation_order"]),
        tuple(data["enemy_target_priority"]), data["max_rounds"],
        None if data['npc_broken_exit_policy'] is None else build(path_prefix+'/npc_broken_exit_policy',
            PcAdjacentNpcExitPolicy,**data['npc_broken_exit_policy']),
        tuple(build(f'{path_prefix}/npc_help_policies/{index}',PcNpcHelpPolicy,**policy)
            for index,policy in enumerate(data['npc_help_policies'])),
        npc_extra_attack_actor_ids=tuple(data['npc_extra_attack_actor_ids']),
        short_range_opening=_parse_short_range_opening(data,path_prefix=path_prefix,error_type=error_type),
        blunderbuss_nearby=_parse_blunderbuss_nearby(data,path_prefix=path_prefix,error_type=error_type),
        npc_close_shooting_protection_policies=_parse_close_shooting_policies(data,
            path_prefix=path_prefix,error_type=error_type),
        npc_net_policies=tuple(net_policies),
        npc_pistol_policies=tuple(pistol_policies),
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
    for member in party:
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
            "resilience": {"toughness":definition.resilience.toughness,"bonus":definition.resilience.bonus},
            "attack": _npc_attack_document(attack),
            "protection": {"source_rule_id": protection.source_rule_id,
                "skill": protection.skill.value,"test_profile": asdict(protection.test_profile)}}})
        if definition.resilience.armoured is not None:
            enemies[-1]['definition']['resilience']['armoured'] = definition.resilience.armoured
        if definition.id==NET_DEFINITION_ID:
            enemies[-1]['definition']['net_attack'] = _net_attack_document(definition.attacks[1])
            policy = next(policy for policy in scenario.npc_net_policies if policy.actor_id==enemy.state.actor_id)
            enemies[-1]['net_policy'] = {'initial_count':policy.initial_count,'mode':policy.mode.value}
        elif definition.id in PC_NPC_PISTOL_DEFINITION_IDS:
            policy = next(policy for policy in scenario.npc_pistol_policies if policy.actor_id==enemy.state.actor_id)
            enemies[-1]['pistol'] = _plain({name:getattr(policy,name) for name in _NPC_PISTOL_FIELDS})
        elif len(definition.attacks)==2:
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
    if scenario.npc_close_shooting_protection_policies is not None:
        document['npc_close_shooting_protection_policies'] = _plain([
            asdict(policy) for policy in scenario.npc_close_shooting_protection_policies])
    if scenario.short_range_opening is not None:
        document['short_range_opening'] = asdict(scenario.short_range_opening)
    if scenario.blunderbuss_nearby is not None:
        document['blunderbuss_nearby'] = {
            'initial_npc_clustered_confirmed':scenario.blunderbuss_nearby.initial_npc_clustered_confirmed,
            'target_priority':list(scenario.blunderbuss_nearby.target_priority)}
    return document
