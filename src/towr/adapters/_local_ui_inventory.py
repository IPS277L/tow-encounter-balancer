"""Inventory rows and talent tags over request facts; no combat execution."""
import json

from towr.domain.talent_catalog import TALENT_DEFINITIONS


_TALENT_TRANSLATIONS = dict(zip(
    (entry.id.value for entry in TALENT_DEFINITIONS),
    ('Ускоренное восстановление', 'Акробат', 'Братья по оружию', 'Пробой брони',
     'Таранный удар', 'Снова в седле', 'Боевой музыкант', 'Благословения Леди',
     'Тщательное прицеливание', 'Рассекающий удар', 'Боевой хирург', 'Глубокое построение',
     'Оборонительная стойка', 'Рассеиватель', 'Исключительный слух', 'Вера', 'Фамильяр',
     'Притворное бегство', 'Сражаться как один', 'Устрашающий', 'Золотой голос',
     'Обет Грааля', 'Крепкий', 'Ненависть', 'Держать строй', 'Связанный честью',
     'Пристальное изучение', 'Перехватчик', 'Железный желудок', 'Зоркий',
     'Молниеносные рефлексы', 'Длиннобородый', 'Удачливый', 'Сопротивление магии',
     'Могучий удар', 'Обитатель ночи', 'Эрудит', 'Обет поиска', 'Быстрое переодевание',
     'Быстрый бросок', 'Быстрая перезарядка', 'Сопротивление порче', 'Решительный',
     'Ответный выпад', 'Тайная родословная', 'Малый рост', 'Заклинатель змей',
     'Видящий духов', 'Стоять и стрелять', 'Держаться в стороне', 'Провокатор',
     'Жажда знаний', 'Прикосновение Ветров', 'Несломленный', 'Доблесть веков',
     'Авангард', 'Поручиться за них', 'Дикая атака', 'Маг'), strict=True))


def _talent_metadata():
    from towr.domain.talent_actor_models import PC_EXECUTABLE_TALENTS,GENERATED_TALENT_POOL
    result = {}
    for entry in TALENT_DEFINITIONS:
        requirements = entry.requirements
        result[entry.id.value] = dict(name=entry.name,
            label=_TALENT_TRANSLATIONS[entry.id.value] + ' (' + entry.name + ')',
            page=entry.page, xp=entry.xp_cost, maximum=entry.maximum_purchases,
            progression=entry.progression.value,
            selection=entry.selection.value if entry.selection is not None else None,
            creation_only=entry.creation_only,
            pc_executable=entry.id in PC_EXECUTABLE_TALENTS,
            generated_order=(GENERATED_TALENT_POOL.index(entry.id)
                if entry.id in GENERATED_TALENT_POOL else None),
            characteristics={name: getattr(requirements, name) for name in
                ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                 'initiative', 'agility', 'reason', 'fellowship') if getattr(requirements, name)},
            origins=[value.value for value in requirements.origins],
            excluded_origins=[value.value for value in requirements.excluded_origins],
            lores=[value.value for value in requirements.lores],
            talents=[value.value for value in requirements.talents],
            equipment=[value.value for value in requirements.equipment],
            status=requirements.minimum_status.value if requirements.minimum_status is not None else None)
    return result

INVENTORY_STYLE = r'''
.inventory-row{--item-control-height:36px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) var(--item-control-height);gap:10px;align-items:end;margin:10px 0}
.inventory-row.consumable{grid-template-columns:minmax(0,1fr) var(--consumable-count-width,88px) 36px;margin:0}
.inventory-row input,.inventory-row select{width:100%;min-width:0;height:var(--item-control-height)}
.inventory-row.has-charge{grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto var(--item-control-height)}
.inventory-row.has-quantity{grid-template-columns:minmax(0,1fr) minmax(0,1fr) 76px var(--item-control-height)}
.inventory-row.tool-row{grid-template-columns:minmax(0,1fr) 80px minmax(0,1fr) var(--item-control-height)}
.tool-name{display:block;margin:0 0 12px}.tool-name input{width:100%}
@media(max-width:480px){.inventory-row.tool-row{grid-template-columns:minmax(0,1fr) var(--item-control-height)}.inventory-row.tool-row>label:first-child{grid-column:1/-1}}
.inventory-row>.toggle-field{height:var(--item-control-height);display:flex;align-items:center;gap:6px;white-space:nowrap}
.inventory-row>.toggle-field input{width:auto;height:auto}
.visual-view .action-add,.visual-card .action-remove{height:36px;display:inline-flex;align-items:center;justify-content:center;gap:8px;font-size:13px;border-radius:5px;flex-shrink:0}
.visual-view .action-add{width:88px;height:36px;max-width:100%;padding:0 8px;background:var(--surface);color:var(--action-text);border:1px solid var(--button-border)}
.visual-view .action-add:hover:not(:disabled){background:var(--add-hover);color:var(--add-text);border-color:var(--add-border)}
.visual-view .action-add:active:not(:disabled){background:var(--add-active);color:var(--add-active-text);border-color:var(--add-active-border)}
.visual-card .action-remove{width:36px;padding:0;background:var(--surface);color:var(--action-text);border:1px solid var(--button-border)}
.visual-card .action-remove:hover:not(:disabled){background:var(--remove-hover);color:var(--remove-text);border-color:var(--remove-border)}
.visual-card .action-remove:active:not(:disabled){background:var(--remove-active);color:var(--remove-active-text);border-color:var(--remove-active-border)}
.action-remove svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;pointer-events:none;flex-shrink:0}
.character-heading{display:flex;justify-content:space-between;align-items:center;gap:10px}
.inventory-add{margin:4px 0 8px}.talent-tags{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 16px}.talent-tags:empty{display:none}
.talent-tag{gap:5px;padding:0 3px 0 9px;overflow-wrap:anywhere}
.talent-provenance{margin:0 0 10px;line-height:1.5}
.talent-source{margin:10px 0}.talent-source summary{font-size:13px}.talent-source-grid{margin:10px 0;grid-template-columns:repeat(2,minmax(0,1fr))}.talent-owner-facts{margin:12px 0}.talent-acquisition{padding:5px 0;border-bottom:1px solid var(--divider)}.talent-acquisition:last-child{border:0}.talent-source .visual-note{font-size:12px}.talent-choice{grid-column:1/-1}.talent-owner-row{display:flex;gap:8px;align-items:end;margin:8px 0}.talent-owner-row>label:first-child{flex:1;min-width:0}.talent-owner-row input{width:100%}.talent-owner-row .toggle-field input{width:auto}
.talent-tag.pending{background:var(--warning-bg);border-color:var(--warning-border)}
.visual-card .talent-tag .action-remove{width:24px;height:24px;background:transparent;border-color:transparent;border-radius:12px}
.talent-tag .action-remove svg{width:12px;height:12px}
.talent-entry{display:flex;flex-wrap:wrap;gap:8px;align-items:start;margin-bottom:12px}.talent-picker{position:relative;min-width:120px;flex:1}.talent-picker input{width:100%;min-width:0;height:36px}
.consumable-item{--consumable-count-width:88px;padding:12px 0;border-bottom:1px solid var(--divider)}
.consumable-details{display:grid;grid-template-columns:minmax(0,1fr) var(--consumable-count-width) 36px;gap:10px;align-items:end;margin-top:8px}
.consumable-details label{min-width:0}.consumable-details select{width:100%;min-width:0;height:36px}
.consumable-details .visual-note{grid-column:2/-1;font-size:12px;margin:0 0 8px}.consumable-item .consumable-summary{font-size:12px;margin:6px 0 0}
.talent-suggestions{position:absolute;top:calc(100% + 5px);left:0;right:0;z-index:30;background:var(--surface);border:1px solid var(--input-border);border-radius:5px;box-shadow:0 5px 14px var(--shadow);max-height:180px;overflow:auto}
.talent-suggestions.hidden{display:none}.talent-suggestions .talent-option{display:block;width:100%;text-align:left;border:0;border-radius:0;padding:10px 12px;font-size:14px;white-space:normal}
.talent-suggestions .talent-option:hover:not(:disabled),.talent-option[aria-selected="true"]{background:var(--hover)}.talent-option small{display:block;margin-top:3px;font-size:12px;line-height:1.4}
.inventory-warning{color:var(--warning-text);background:var(--warning-bg);border-radius:4px;padding:8px 10px;font-size:13px;line-height:1.5}
.magic-spells{display:flex;flex-wrap:wrap;gap:10px 20px;margin:10px 0}.magic-spells label{display:flex;align-items:center;gap:8px}.magic-spells input{width:auto}
@media(max-width:480px){.inventory-row,.inventory-row.has-charge,.inventory-row.has-quantity{grid-template-columns:minmax(0,1fr) var(--item-control-height)}.inventory-row>label:first-child,.inventory-row.has-charge>label:nth-child(2),.inventory-row.has-quantity>label:nth-child(2){grid-column:1/-1}.consumable-item{--consumable-count-width:70px}.inventory-row.consumable>label:first-child{grid-column:auto}}
'''

INVENTORY_SCRIPT = r'''
const armourNames={light_armour:'Лёгкая броня (Light Armour)',heavy_armour:'Тяжёлая броня (Heavy Armour)',full_plate_armour:'Полный латный доспех (Full Plate Armour)',armour_of_agilulf:'Доспех Агилульфа (Armour of Agilulf)',armour_of_meteoric_iron:'Доспех из метеоритного железа (Armour of Meteoric Iron)',mantle_of_ithilmar:'Мантия из итильмара (Mantle of Ithilmar)',helmet:'Обычный шлем (Helmet)',helm_of_the_hunt:'Шлем охоты (Helm of the Hunt)',shield:'Щит (Shield)',briarroot_shield:'Щит живых корней (Briarroot Shield)',barding:'Конская броня (Barding)'};
const bodyArmourIds=Object.freeze(['light_armour','heavy_armour','full_plate_armour','armour_of_agilulf','armour_of_meteoric_iron','mantle_of_ithilmar']);
const shieldArmourIds=new Set(['shield','briarroot_shield']);
const armourHints={light_armour:'Стойкость (Toughness) +1 к защищённости (Resilience).',heavy_armour:'Toughness +2 к Resilience; −1d к Ловкости (Agility), Обременён (Burdened) при Силе (Strength) ниже 3.',full_plate_armour:'Toughness +3 к Resilience; −1d к Ловкости (Agility), Обременён (Burdened) при Силе (Strength) ниже 4.',armour_of_agilulf:'Toughness +2 к Resilience; Боевое мастерство (WS), Ближний бой (Melee) и Защита (Defence) ровно 5. Требует соблюдения рыцарского кодекса.',armour_of_meteoric_iron:'Toughness +3 к Resilience; отменяет немагическое игнорирование брони и немагический бонус урона против бронированной цели.',mantle_of_ithilmar:'Toughness +3 к Resilience; +1d против опасностей среды (Environmental Hazards). Сама мантия не делает сотворение заклинаний (Casting) Мрачным (Grim).',helmet:'Часть защитного комплекта; не даёт дополнительного бонуса к защищённости (Resilience).',helm_of_the_hunt:'+1 Resilience; атака при Натиске (Charge) и преследование Блистательны (Glorious). Запрещает сжигание Судьбы (Fate) для Near Miss.',shield:'+1 Resilience при удержании пригодной рукой; Защита (Defence) против Стрельбы (Shooting) и Метания (Throwing).',briarroot_shield:'Обычная защита щита; выигранная Защита (Defence) против Ближнего боя (Melee) опутывает оружие врага и накладывает Обременён (Burdened).',barding:'+1 Resilience маунту и всаднику; −1d к Ловкости (Agility), пока всадник верхом. При спешивании бонусы всадника снимаются.'};
const combatMountNames={none:'Пешком',horse:'Лошадь (Horse)',bretonnian_warhorse:'Бретонская боевая лошадь (Bretonnian Warhorse)',elven_steed:'Эльфийская лошадь (Elven Steed)',skeletal_steed:'Скелетная лошадь (Skeletal Steed)',demigryph:'Демигриф (Demigryph)',pegasus:'Пегас (Pegasus)'};
const riderKindNames={none:'Укажите происхождение',human:'Человек (Human)',elf:'Эльф (Elf)',other:'Другое происхождение'};
const consumableNames={healing_potion:'Зелье лечения (Healing Potion)',enhancement_potion:'Зелье усиления (Enhancement Potion)'};
const enhancementNames=characteristicNames;
const talentMetadata=__TALENT_METADATA__;
const talentNames=Object.fromEntries(Object.entries(talentMetadata).map(([id,value])=>[id,value.label]));
const pcCombatTalentIds=['defensive_stance','wild_attack'],supportedPlayerTalents=Object.keys(talentMetadata).filter(id=>talentMetadata[id].pc_executable),generatedExecutableTalentIds=Object.keys(talentMetadata).filter(id=>talentMetadata[id].generated_order!==null).sort((a,b)=>talentMetadata[a].generated_order-talentMetadata[b].generated_order);
const pcCombatTalentHints={acrobatic:'Ловкость (Ag) 4+. Враги не перекрывают перемещение и Отступление (Give Ground); опасность падения (Hazard) уменьшается вдвое вниз до 0. Остальные препятствия и требования Полёта (Fly) сохраняются.',bash_attack:'Сила (S) 5+. Новое Пошатывание (Staggered) через Мощь (Brawn) разрешает немедленный удар реальным оружием Ближнего боя (Melee) по той же цели. Без нового обычного действия и без наследования Натиска (Charge).',allies_in_arms:'Обаяние (Fel) 4+. После окончательной проверки Помощи (Help) снимает одно доступное Пошатывание (Staggered) с помощника или союзника, даже при нуле успехов. Постоянная причина состояния сохраняется.',armour_bane:'Попадание подходящим оружием снижает Стойкость к урону (Resilience) на 1 после сравнения урона, минимум до Стойкости (Toughness). Потеря сохраняется до конца боя; отменённое свойство оружия не действует.',mighty_blow:'Игнорирует собственные штрафы двуручного оружия к Ближнему бою (Melee). Внешние штрафы сохраняются.',hardy:'На один куб меньше в таблице ран (Wounds Table), минимум один. Не меняет профильные раны NPC.',rapid_reload:'Успешная перезарядка (Reload) разрешает вторым действием прицелиться (Aim) или выстрелить (Attack). Нельзя после движения или при Пошатывании (Staggered); для выстрела нужен заряд.',defensive_stance:'Боевое мастерство (WS) 3+. Успешная Защита (Defence) может снять собственное Пошатывание (Staggered) вместо доступного нового Staggered атакующему. Постоянная причина состояния сохраняется.',wild_attack:'Сила (S) 4+. Автоматический выбор для атаки или Помощи (Help) в Ближнем бою (Melee): получить Пошатывание (Staggered) до проверки ради Блистательного (Glorious) Test. Не используется при Staggered или Истощении (Drained).'};
const talentLabel=value=>talentNames[value]||value;
const playerTalentIds=member=>(member.talents||[]).map(entry=>entry.id),playerHasTalent=(member,id)=>playerTalentIds(member).includes(id);
const playerMusicRelevant=member=>playerHasTalent(member,'battlefield_musician')||(member.equipment?.tools||[]).some(item=>item.kind==='musicians_gear');
const wizardUiAdditions=new Map();
const expandedTalentDetails=new Set();
function rememberTalentDetails(details,key){details.open=expandedTalentDetails.has(key);details.ontoggle=()=>{if(!details.isConnected)return;if(details.open)expandedTalentDetails.add(key);else expandedTalentDetails.delete(key);};}
const talentOriginNames={none:'Не указано',human:'Человек (Human)',empire_human:'Человек Империи (Empire Human)',bretonnian_human:'Бретонец (Bretonnian Human)',dwarf:'Гном (Dwarf)',high_elf:'Высший эльф (High Elf)',wood_elf:'Лесной эльф (Wood Elf)',halfling:'Полурослик (Halfling)',ogre:'Огр (Ogre)'};
const talentStatusNames={none:'Не указан',brass:'Медь (Brass)',silver:'Серебро (Silver)',gold:'Золото (Gold)'};
const talentEquipmentNames={musicians_gear:'Инструменты музыканта (Musician’s Gear)',grooming_kit:'Набор для ухода (Grooming Kit)'};
const deityNames={none:'Выберите божество (Deity)',ulric:'Ульрик (Ulric)',taal:'Таал (Taal)',rhya:'Рия (Rhya)',sigmar:'Сигмар (Sigmar)',manann:'Мананн (Manann)',morr:'Морр (Morr)',ranald:'Ранальд (Ranald)',verena:'Верена (Verena)',myrmidia:'Мирмидия (Myrmidia)',shallya:'Шаллия (Shallya)'};
const familiarEffectNames={none:'Выберите эффект (Familiar Effect)',armoured:'Бронированный (Armoured)',babbler:'Болтун (Babbler)',bookrest:'Подставка для книги (Bookrest)',chaos_sink:'Поглотитель Хаоса (Chaos Sink)',combatant:'Боец (Combatant)',flight:'Полёт (Flight)',linked:'Связанный (Linked)',poison_tongue:'Ядовитый язык (Poison Tongue)',skulker:'Скрытный (Skulker)'};
const talentChoiceFields={deity:{key:'deity',label:'Божество (Deity)',choices:deityNames},familiar_effect:{key:'effect',label:'Эффект фамильяра (Familiar Effect)',choices:familiarEffectNames},hated_group:{key:'group_id',label:'Группа ненависти (Hatred Group)'},oath:{key:'oath_id',label:'Клятва (Oath)'},secret_bloodline:{key:'bloodline_id',label:'Родословная (Bloodline)'},magic_lore:{key:'lore_id',label:'Магическое знание (Magic Lore)'}};
function talentHint(id){
 const metadata=talentMetadata[id];if(!metadata)return 'Неизвестный талант (Talent).';
 const requirements=Object.entries(metadata.characteristics).map(([key,value])=>(characteristicFullNames[key]||key)+' ≥'+value);
 if(metadata.origins.length)requirements.push(metadata.origins.map(value=>talentOriginNames[value]).join(' / '));
 if(metadata.excluded_origins.length)requirements.push('кроме '+metadata.excluded_origins.map(value=>talentOriginNames[value]).join(', '));
 requirements.push(...metadata.talents.map(talentLabel),...metadata.equipment.map(value=>talentEquipmentNames[value]),...metadata.lores.map(value=>({anatomy:'Анатомия (Anatomy Lore)',high_society:'Высшее общество (High Society Lore)',any_magic_lore:'Магическое знание (Magic Lore)'})[value]));
 if(metadata.status)requirements.push(talentStatusNames[metadata.status]+'+');
 if(metadata.creation_only)requirements.push('только создание (Character Creation)');
 return 'Player’s Guide1.4, '+metadata.page+' · базовая цена '+metadata.xp+' XP'+(requirements.length?' · '+requirements.join(', '):'')+'. '+(id==='lucky'?'Первая трата Судьбы (Fate) за сессию бесплатна.':id==='wizard'?'Уровень мага (Wizard Level) равен числу приобретений.':pcCombatTalentHints[id]||(id==='magic_resistance'?'Сила (Potency) затрагивающего заклинания уменьшается на1; при0 эффекта нет.':'Эффект пока не подключён к расчёту.'));
}
const heldLocations={carried:'Убрано / за спиной',left_hand:'В левой руке',right_hand:'В правой руке',both_hands:'В обеих руках'};
const twoHandedInventoryWeapons=new Set(['pickaxe','flail','billhook','halberd','glaive','greataxe','greatsword','greathammer','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','blunderbuss','hochland_long_rifle','weighted_net','dragon_bow','duellist_blades','grotarggs_hammer','headsmans_axe','unwavering_spear']);
function actionButton(kind,title,iconOnly=false){
 const button=node('button',undefined,kind==='add'?'action-add':'action-remove');button.type='button';button.title=title;button.setAttribute('aria-label',title);
 if(kind==='add'){button.textContent='Добавить';return button;}
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS('http://www.w3.org/2000/svg','path');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');
 path.setAttribute('d','M6 6l12 12M6 18 18 6');svg.append(path);button.append(svg);if(!iconOnly)button.append(node('span',title));return button;
}
function inventoryId(member,prefix){const ids=new Set([...(member.equipment?.weapons||[]),...(member.equipment?.armour||[]),...(member.equipment?.tools||[]),...(member.consumables||[])].map(i=>i.id));let n=1;while(ids.has(prefix+':'+n))n++;return prefix+':'+n;}
function syncPlayerArmourFacts(member){const body=(member.equipment?.armour||[]).filter(item=>item.location==='worn'&&bodyArmourIds.includes(item.kind));if(!body.some(item=>item.id===member.equipment.armour_benefit_id))delete member.equipment.armour_benefit_id;if(!body.some(item=>item.kind==='armour_of_agilulf'))delete member.agilulf_code_confirmed;}
function inventoryRemove(row,path,index,title){const remove=actionButton('remove','Удалить '+title,true);remove.classList.add('inventory-remove');remove.dataset.action='remove-item';remove.dataset.path=[...path,index].join('/');remove.onclick=()=>{const values=get(read(),path).filter((_,i)=>i!==index);if(path.at(-1)==='weapons'){const member=read().party[path[1]];member.equipment.weapons=values;syncPlayerRangedPreparation(member);editRequest(['party',path[1]],member);}else if(path.at(-1)==='armour'){const member=read().party[path[1]];member.equipment.armour=values;syncPlayerArmourFacts(member);editRequest(['party',path[1]],member);}else editRequest(path,values);};row.append(remove);}
function inventoryAdd(parent,title,path,make){const button=actionButton('add',title);button.classList.add('inventory-add');button.dataset.action='add-'+path.at(-1);button.onclick=()=>{const data=read(),member=data.party[path[1]];editRequest(path,[...(get(data,path)||[]),make(member)]);};parent.append(button);}
function renderInventory(parent,member,index){
 const gear=member.equipment||{};
 inputField(parent,'Ездовое животное (Mount)',['party',index,'mount'],member.mount||'none',combatMountNames,value=>{const current=read().party[index];current.mount=value==='none'?null:value;if(!['demigryph','pegasus'].includes(value))delete current.rider_kind;editRequest(['party',index],current);});
 if(['demigryph','pegasus'].includes(member.mount))inputField(parent,'Происхождение всадника (Rider)',['party',index,'rider_kind'],member.rider_kind||'none',riderKindNames,value=>editRequest(['party',index,'rider_kind'],value==='none'?null:value));
 parent.append(node('h4','Оружие (Weapons)'));
 parent.append(node('p','Каждая строка — отдельный предмет. Первое оружие в руках — основное на начало боя; остальные предметы сохраняют своё положение.','visual-note'));
 for(const [i,item] of (gear.weapons||[]).entries()){
  const row=node('div',undefined,'inventory-row'),path=['party',index,'equipment','weapons',i];
  inputField(row,'Оружие '+(i+1),[...path,'weapon'],item.weapon,playerWeaponNames,value=>setPlayerWeapon(index,i,'weapon',value));
  inputField(row,'На начало боя',[...path,'location'],item.location,heldLocations,value=>setPlayerWeapon(index,i,'location',value));
  if(pcExactingWeapons.has(item.weapon)){row.classList.add('has-charge');const loaded=inputField(row,'Заряжено (Loaded)',[...path,'initially_loaded'],item.initially_loaded===true,null,value=>setPlayerWeapon(index,i,'initially_loaded',value));loaded.title='Начальный заряд именно этого предмета. Незаряженное оружие требует Перезарядки (Reload).';}
  if(pcFiniteThrowingWeapons.has(item.weapon)){row.classList.add('has-quantity');const quantity=inputField(row,'Количество',[...path,'quantity'],item.quantity??1,null,value=>setPlayerWeapon(index,i,'quantity',integer(value)));quantity.min='1';quantity.title='Конечное число отдельных метательных предметов (Throwing Weapons). Каждый экземпляр сохраняет собственное положение.';}
  if(item.weapon==='scarab_knife'){row.classList.add('has-charge');const charges=inputField(row,'Начальные заряды (Charges)',[...path,'initial_charges'],item.initial_charges??0,null,value=>setPlayerWeapon(index,i,'initial_charges',integer(value)));charges.min='0';charges.title='Фактический запас этого Ножа скарабея (Scarab Knife) на начало боя. Не пополняется при смене оружия.';}
  inventoryRemove(row,['party',index,'equipment','weapons'],i,'оружие '+(i+1));parent.append(row);
  if(item.weapon==='ogre_pistol')inputField(parent,'GM подтвердил пригодность Огрского пистолета (Ogre Pistol)',['party',index,'equipment','weapons',i,'gm_fit_confirmed'],item.gm_fit_confirmed===true,null,value=>setPlayerWeapon(index,i,'gm_fit_confirmed',value?true:null));
 }
 inventoryAdd(parent,'Добавить оружие',['party',index,'equipment','weapons'],m=>({id:inventoryId(m,'weapon'),weapon:'sword',location:'carried'}));
 parent.append(node('h4','Инструменты (Trade Tools)'));
 for(const [i,item] of (gear.tools||[]).entries()){
  const row=node('div',undefined,'inventory-row tool-row'),path=['party',index,'equipment','tools',i];
  inputField(row,'Инструмент '+(i+1),[...path,'kind'],item.kind,{musicians_gear:'Инструменты музыканта (Musician’s Gear)'});
  inputField(row,'Рук',[...path,'hands_required'],String(item.hands_required),{'1':'1','2':'2'},value=>editRequest([...path,'hands_required'],integer(value)));
  const locations=Object.fromEntries(Object.entries(heldLocations).filter(([key])=>key==='carried'||(item.hands_required===2?key==='both_hands':key!=='both_hands')));
  inputField(row,'На начало боя',[...path,'location'],item.location,locations);
  inventoryRemove(row,['party',index,'equipment','tools'],i,'инструмент '+(i+1));parent.append(row);
  const name=node('div',undefined,'tool-name');inputField(name,'Название инструмента (необязательно)',[...path,'instrument_name'],item.instrument_name??'',null,value=>editRequest([...path,'instrument_name'],value===''?undefined:value));parent.append(name);
 }
 inventoryAdd(parent,'Добавить инструмент',['party',index,'equipment','tools'],m=>({id:inventoryId(m,'tool'),kind:'musicians_gear',hands_required:1,location:'carried'}));
 if(playerMusicRelevant(member)){
  const known=(member.talent_facts?.lores||[]).some(lore=>lore.id==='music'&&lore.magic===false);
  inputField(parent,'Знание музыки (Music Lore)',['party',index,'talent_facts','lores','music'],known,null,value=>editPlayerTalentFacts(index,facts=>{const lores=(facts.lores||[]).filter(lore=>lore.id!=='music');facts.lores=value?[...lores,{id:'music',magic:false}]:lores;if(!facts.lores.length)delete facts.lores;}));
  parent.append(node('p','Для игры нужны настоящее удерживаемое снаряжение музыканта (Musician’s Gear), пригодные руки и Знание музыки (Music Lore). Обаяние (Fel) и Лидерство (Leadership) редактируются в общих характеристиках и навыках.','visual-note'));
 }
 parent.append(node('h4','Броня (Armour) и защитное снаряжение'));
 for(const [i,item] of (gear.armour||[]).entries()){
  const row=node('div',undefined,'inventory-row'),path=['party',index,'equipment','armour',i];
  inputField(row,'Предмет '+(i+1),[...path,'kind'],item.kind,armourNames,value=>{
   const current=read().party[index];current.equipment.armour[i]={...current.equipment.armour[i],kind:value,location:shieldArmourIds.has(value)?'carried':'worn'};syncPlayerArmourFacts(current);editRequest(['party',index],current);
  });
  const locations=shieldArmourIds.has(item.kind)?{carried:'Убрано',left_hand:'В левой руке',right_hand:'В правой руке'}:{worn:item.kind==='barding'?'На маунте':'Надето',carried:'Убрано'};
  inputField(row,'На начало боя',[...path,'location'],item.location,locations,value=>{const current=read().party[index];current.equipment.armour[i].location=value;syncPlayerArmourFacts(current);editRequest(['party',index],current);});
  inventoryRemove(row,['party',index,'equipment','armour'],i,'защитный предмет '+(i+1));parent.append(row);
 }
 inventoryAdd(parent,'Добавить защиту',['party',index,'equipment','armour'],m=>({id:inventoryId(m,'armour'),kind:'light_armour',location:'worn'}));
 const wornBody=(gear.armour||[]).filter(item=>item.location==='worn'&&bodyArmourIds.includes(item.kind));
 if(wornBody.length>1){
  const sources=Object.fromEntries([['none','Выберите источник преимуществ'],...wornBody.map(item=>[item.id,armourNames[item.kind]+' · '+item.id])]);
  inputField(parent,'Преимущества комплекта (Armour Benefits)',['party',index,'equipment','armour_benefit_id'],gear.armour_benefit_id||'none',sources,value=>{const current=read().party[index];if(value==='none')delete current.equipment.armour_benefit_id;else current.equipment.armour_benefit_id=value;editRequest(['party',index],current);});
  parent.append(node('p','При сочетании обычной и магической брони действуют преимущества выбранного комплекта; штрафы обоих сохраняются.','visual-note'));
 }
 const wearingAgilulf=wornBody.some(item=>item.kind==='armour_of_agilulf');
 if(wearingAgilulf)inputField(parent,'GM подтвердил применимость рыцарского кодекса (Code Chivalric)',['party',index,'agilulf_code_confirmed'],member.agilulf_code_confirmed===true,null,value=>editRequest(['party',index,'agilulf_code_confirmed'],value?true:null));
 parent.append(node('p','Щит (Shield) занимает руку. Обычный шлем (Helmet) не добавляет отдельного бонуса поверх комплекта брони (Armour).','visual-note'));
 parent.append(node('h4','Расходники'));
 for(const [i,item] of (member.consumables||[]).entries()){
  const box=node('div',undefined,'consumable-item');box.dataset.itemId=item.id;box.setAttribute('role','group');box.setAttribute('aria-label',(consumableNames[item.kind]||item.kind)+' · '+(i+1));
  const row=node('div',undefined,'inventory-row consumable'),path=['party',index,'consumables',i];
  inputField(row,'Предмет',[...path,'kind'],item.kind,consumableNames,value=>editRequest(path,{...get(read(),path),kind:value,characteristic:value==='enhancement_potion'?'strength':null}));
  const count=inputField(row,'Количество',[...path,'quantity'],item.quantity);count.min='1';
  inventoryRemove(row,['party',index,'consumables'],i,'расходник '+(i+1));
  box.append(row);
  if(item.kind==='enhancement_potion'){
   const details=node('div',undefined,'consumable-details');inputField(details,'Характеристика (Characteristic)',[...path,'characteristic'],item.characteristic,enhancementNames);
   details.append(node('p','+1 до заката','visual-note'));box.append(details);
  }else if(item.kind==='healing_potion'){
   const summary=node('p','Лечит одну рану (Wound).','visual-note consumable-summary');summary.title='Лечит одну рану (Wound) и связанные с ней последствия.';box.append(summary);
  }
  parent.append(box);
 }
 inventoryAdd(parent,'Добавить расходник',['party',index,'consumables'],m=>({id:inventoryId(m,'consumable'),kind:'healing_potion',quantity:1,characteristic:null}));
 const warnings=[],active=(gear.weapons||[]).filter(w=>w.location!=='carried');
 if(!active.length)parent.append(node('p','На начало боя — безоружный бой (Unarmed): проверка Грубой силы (Brawn), без предмета и обязательного использования рук.','visual-note'));
 if(playerBrawnRequired(member)&&!Number.isSafeInteger(member.skills?.brawn))warnings.push('Для безоружного боя (Unarmed), кастетов (Knuckledusters) и Молота Гротаргга (Grotargg’s Hammer) укажите Грубую силу (Brawn).');
 if((gear.armour||[]).some(a=>a.kind==='barding'&&a.location==='worn')&&!member.mount)warnings.push('Конская броня (Barding) требует настоящего маунта (Mount).');
 if(wornBody.length>1&&!wornBody.some(item=>item.id===gear.armour_benefit_id))warnings.push('Выберите комплект, дающий преимущества брони (Armour Benefits).');
 if(wearingAgilulf&&member.agilulf_code_confirmed!==true)warnings.push('Для Доспеха Агилульфа (Armour of Agilulf) требуется подтверждение GM о рыцарском кодексе.');
 if(member.mount==='demigryph'&&member.rider_kind!=='human'||member.mount==='pegasus'&&!['human','elf'].includes(member.rider_kind))warnings.push('Происхождение всадника должно соответствовать требованиям маунта (Mount).');
 if((member.consumables||[]).some(item=>item.kind==='enhancement_potion'&&!['weapon_skill','strength','toughness','agility'].includes(item.characteristic)))warnings.push('Усиление (Enhancement Potion) пока поддерживает WS, Strength, Toughness и Agility.');
 if(warnings.length)parent.append(node('p',warnings.join(' ')+' Инвентарь можно редактировать и сохранять; неподдержанные возможности блокируют расчёт.','inventory-warning'));
}
function syncPlayerRangedPreparation(member){
 const requirements=playerRangedRequirements(member);if(!requirements){delete member.ranged;return;}
 const current=member.ranged&&typeof member.ranged==='object'&&!Array.isArray(member.ranged)?member.ranged:{};
 member.ranged={ammunition_supply_confirmed:current.ammunition_supply_confirmed??false,has_blackpowder_lore:requirements.firearm?(current.has_blackpowder_lore??false):null,has_blackpowder_kit:requirements.firearm?(current.has_blackpowder_kit??false):null};
}
function setPlayerWeapon(index,itemIndex,key,value){const member=read().party[index],item=member.equipment.weapons[itemIndex];item[key]=value;if(key==='weapon'){if(pcExactingWeapons.has(value)){if(typeof item.initially_loaded!=='boolean')item.initially_loaded=true;}else delete item.initially_loaded;if(!pcFiniteThrowingWeapons.has(value))delete item.quantity;if(value==='scarab_knife')item.initial_charges=item.initial_charges??0;else delete item.initial_charges;if(value!=='ogre_pistol')delete item.gm_fit_confirmed;}syncPlayerRangedPreparation(member);editRequest(['party',index],member);}
function renderPlayerRangedPreparation(parent,member,index){
 const requirements=playerRangedRequirements(member);if(!requirements)return;
 parent.append(node('h4','Подготовка к стрельбе (Ranged Preparation)'));
 const prep=member.ranged||{},grid=node('div',undefined,'visual-fields'),path=['party',index,'ranged'];
 for(const [key,title] of [['ammunition_supply_confirmed','Боезапас подготовлен (Ammunition)'],...(requirements.firearm?[['has_blackpowder_lore','Знание пороха (Lore: Blackpowder)'],['has_blackpowder_kit','Пороховой набор (Blackpowder Kit)']]:[])]){
  const input=inputField(grid,title,[...path,key],prep[key]===true,null,value=>{const current=read().party[index];syncPlayerRangedPreparation(current);current.ranged[key]=value;editRequest(['party',index],current);});input.title='Факт персонажа или подготовки сцены. Не добавляет бонусный куб.';
 }
 parent.append(grid);parent.append(node('p',requirements.exacting?'Перезарядка (Reload) использует Инициативу (I) и Ловкость рук (Dexterity). Начальный заряд задаётся отдельно у каждого предмета.':'Выстрел включает подготовку снаряда. Инициатива (I) и Внимательность (Awareness) нужны для Прицеливания (Aim).','visual-note'));
 if(!member.ranged || !prep.ammunition_supply_confirmed || (requirements.firearm&&(!prep.has_blackpowder_lore||!prep.has_blackpowder_kit)))parent.append(node('p','Для расчёта подтвердите боезапас и необходимые Lore/Kit для всего стрелкового снаряжения; неполный черновик можно сохранить.','inventory-warning'));
 if(requirements.weapons.some(item=>pcExactingWeapons.has(item.weapon)&&typeof item.initially_loaded!=='boolean'))parent.append(node('p','Укажите начальный заряд (Loaded) каждого оружия с Перезарядкой (Reload).','inventory-warning'));
}
function newTalentAcquisition(id,previous=null,purchase=0){
 const metadata=talentMetadata[id],field=talentChoiceFields[metadata.selection];
 return {phase:previous?.phase||'creation',funding:'xp',choice:field&&(purchase===0||metadata.progression==='familiar_effects')?{[field.key]:''}:null,devotion_confirmed:null};
}
function resizeTalentAcquisitions(member,talent,count){
 const metadata=talentMetadata[talent.id],maximum=metadata.progression==='familiar_effects'?9:metadata.maximum;
 if(!Number.isSafeInteger(count)||count<1||maximum!==null&&count>maximum)throw Error('Проверьте число приобретений таланта (Talent Purchases).');
 const values=talent.acquisitions.slice(0,count);
 while(values.length<count)values.push(newTalentAcquisition(talent.id,values.at(-1),values.length));
 talent.acquisitions=values;
 if(talent.id==='wizard'&&member.magic)member.magic.wizard_level=count;
}
function setPlayerTalentCount(index,id,count){const member=read().party[index],talent=member.talents.find(value=>value.id===id);if(!talent)throw Error('Талант (Talent) не выбран.');resizeTalentAcquisitions(member,talent,integer(count));editRequest(['party',index],member);}
function setPlayerTalentAcquisition(index,talentIndex,purchase,key,value){
 const member=read().party[index],talent=member.talents[talentIndex],acquisition=talent.acquisitions[purchase];
 talent.acquisitions[purchase]={...acquisition,[key]:value};syncPlayerOathContext(member);editRequest(['party',index],member);
}
function renderTalentAcquisitions(parent,member,index,talent,talentIndex){
 const metadata=talentMetadata[talent.id],details=node('details',undefined,'talent-source');details.dataset.talentId=talent.id;
 rememberTalentDetails(details,member.actor_id+':talent:'+talent.id);
 const field=talentChoiceFields[metadata.selection],missingChoice=field&&talent.acquisitions.some((value,i)=>(i===0||metadata.progression==='familiar_effects')&&!String(value.choice?.[field.key]||'').trim());
 details.append(node('summary',talentLabel(talent.id)+' · приобретений: '+talent.acquisitions.length+(missingChoice?' · требуется выбор':'')));
 if(metadata.progression!=='single'){
  const count=inputField(details,'Приобретения (Purchases)',['party',index,'talents',talentIndex,'purchase_count'],talent.acquisitions.length,null,value=>setPlayerTalentCount(index,talent.id,value));count.min='1';if(metadata.maximum!==null)count.max=String(metadata.maximum);if(metadata.progression==='familiar_effects')count.max='9';count.dataset.role='talent-purchases';count.dataset.talentId=talent.id;
 }
 for(const [purchase,acquisition] of talent.acquisitions.entries()){
  const row=node('div',undefined,'talent-acquisition'),fields=node('div',undefined,'visual-fields talent-source-grid'),path=['party',index,'talents',talentIndex,'acquisitions',purchase];
  if(talent.acquisitions.length>1)row.append(node('p','Приобретение '+(purchase+1),'visual-note'));
  const phases=metadata.creation_only?{creation:'Создание (Character Creation)'}:{creation:'Создание (Character Creation)',advancement:'Развитие (Advancement)'};
  inputField(fields,'Когда получен',[...path,'phase'],acquisition.phase,phases,value=>setPlayerTalentAcquisition(index,talentIndex,purchase,'phase',value));
  inputField(fields,'Оплата',[...path,'funding'],acquisition.funding,{xp:'За опыт (XP)',free:'Бесплатно (Free)'},value=>setPlayerTalentAcquisition(index,talentIndex,purchase,'funding',value));
  const choiceField=talentChoiceFields[metadata.selection],requiresChoice=choiceField&&(purchase===0||metadata.progression==='familiar_effects');
  if(requiresChoice){
   let choices=choiceField.choices;
   if(metadata.progression==='familiar_effects'){const others=new Set(talent.acquisitions.filter((_,i)=>i!==purchase).map(value=>value.choice?.effect));choices=Object.fromEntries(Object.entries(familiarEffectNames).filter(([id])=>id==='none'||id===acquisition.choice?.effect||!others.has(id)));}
   const value=acquisition.choice?.[choiceField.key]||'',input=inputField(fields,choiceField.label,[...path,'choice',choiceField.key],choices?(value||'none'):value,choices||null,value=>setPlayerTalentAcquisition(index,talentIndex,purchase,'choice',{[choiceField.key]:value==='none'?'':value}));input.parentElement.classList.add('talent-choice');
   if(!value)row.append(node('p','Укажите обязательный выбор таланта (Talent Choice). Пока это неполный черновик.','inventory-warning'));
  }
  if(talent.id==='faith'&&acquisition.phase==='advancement')inputField(fields,'Испытание преданности (Trial of Devotion) подтверждено',[...path,'devotion_confirmed'],acquisition.devotion_confirmed===true,null,value=>setPlayerTalentAcquisition(index,talentIndex,purchase,'devotion_confirmed',value));
  row.prepend(fields);
  if(acquisition.funding==='free'&&acquisition.phase!=='creation')row.append(node('p','Бесплатное получение (Free) допустимо только при создании персонажа (Character Creation).','inventory-warning'));
  const free=acquisition.phase==='creation'&&acquisition.funding==='free';
  const missing=Object.entries(metadata.characteristics).filter(([key,value])=>Number(member.characteristics?.[key]??member.talent_facts?.[key]??0)<value);
  if(!free&&missing.length)row.append(node('p','Не выполнены требования (Requirements): '+missing.map(([key,value])=>(characteristicNames[key]||key)+' ≥'+value).join(', ')+'. Бесплатное получение указывается только как реальный факт создания персонажа.','inventory-warning'));
  details.append(row);
 }
 details.append(node('p',talentHint(talent.id),'visual-note'));parent.append(details);
}
function editPlayerTalentFacts(index,apply){const member=read().party[index],facts={...(member.talent_facts||{})};apply(facts);if(Object.keys(facts).length)member.talent_facts=facts;else delete member.talent_facts;editRequest(['party',index],member);}
function renderTalentOwnerFacts(parent,member,index){
 if(!(member.talents||[]).length&&!member.talent_facts)return;
 const details=node('details',undefined,'talent-owner-facts'),facts=member.talent_facts||{},path=['party',index,'talent_facts'];details.append(node('summary','Факты требований (Talent Requirements)'));
 rememberTalentDetails(details,member.actor_id+':talent-facts');
 details.append(node('p','Дополнительные исходные факты персонажа. Базовые характеристики, известные заклинания и снаряжение сохраняются в своих разделах. Подтверждения указывайте только для действительно выполненных условий.','visual-note'));
 const grid=node('div',undefined,'visual-fields talent-source-grid');
 for(const [key,label,choices] of [['origin','Происхождение (Origin)',talentOriginNames],['status','Статус (Status)',talentStatusNames]])inputField(grid,label,[...path,key],facts[key]||'none',choices,value=>editPlayerTalentFacts(index,values=>{if(value==='none')delete values[key];else values[key]=value;}));
 for(const key of ['initiative','reason','fellowship'])if(!Object.hasOwn(member.characteristics||{},key)){const input=inputField(grid,characteristicNames[key],[...path,key],facts[key]??'',null,value=>editPlayerTalentFacts(index,values=>{if(value==='')delete values[key];else values[key]=integer(value);}));input.type='number';input.min='1';input.step='1';input.title=characteristicFullNames[key];input.setAttribute('aria-label',characteristicFullNames[key]);}
 details.append(grid,node('p','Знания (Lores)','visual-note'));
 for(const [position,lore] of (facts.lores||[]).entries()){
  const row=node('div',undefined,'talent-owner-row');
  inputField(row,'Знание (Lore)',[...path,'lores',position,'id'],lore.id,null,value=>editPlayerTalentFacts(index,values=>{values.lores=values.lores.map((item,i)=>i===position?{...item,id:value}:item);}));
  const check=inputField(row,'Магическое (Magic Lore)',[...path,'lores',position,'magic'],lore.magic===true,null,value=>editPlayerTalentFacts(index,values=>{values.lores=values.lores.map((item,i)=>i===position?{...item,magic:value}:item);}));check.parentElement.classList.add('toggle-field');
  const remove=actionButton('remove','Удалить знание (Lore)',true);remove.onclick=()=>editPlayerTalentFacts(index,values=>{values.lores=values.lores.filter((_,i)=>i!==position);if(!values.lores.length)delete values.lores;});row.append(remove);details.append(row);
 }
 const add=actionButton('add','Добавить знание (Lore)');add.onclick=()=>editPlayerTalentFacts(index,values=>{values.lores=[...(values.lores||[]),{id:'',magic:false}];});details.append(add);
 const confirmations=node('div',undefined,'visual-fields talent-source-grid');
 for(const [id,label] of Object.entries(talentEquipmentNames)){if(id==='musicians_gear'&&!(member.talents||[]).some(talent=>talent.id==='battlefield_musician'&&talent.acquisitions.some(acquisition=>acquisition.funding==='xp')))continue;const input=inputField(confirmations,id==='musicians_gear'?'Инструменты при приобретении таланта (Musician’s Gear)':label,[...path,'equipment',id],(facts.equipment||[]).includes(id),null,value=>editPlayerTalentFacts(index,values=>{const items=values.equipment||[];values.equipment=value?[...items.filter(item=>item!==id),id]:items.filter(item=>item!==id);if(!values.equipment.length)delete values.equipment;}));input.parentElement.classList.add('toggle-field');}
 for(const [key,label] of [['grail_quest_completed','Поиск Грааля (Grail Quest) завершён'],['can_cast_spells','Иное сотворение заклинаний (Spellcasting) подтверждено']]){const input=inputField(confirmations,label,[...path,key],facts[key]===true,null,value=>editPlayerTalentFacts(index,values=>{values[key]=value;}));input.parentElement.classList.add('toggle-field');}
 details.append(confirmations);parent.append(details);
}
function renderTalentTags(parent,member,index){
 parent.append(node('h4','Таланты (Talents)'));const tags=node('div',undefined,'talent-tags');
 if((member.talents||[]).some(entry=>!entry||typeof entry!=='object'||Array.isArray(entry)||!Object.hasOwn(talentMetadata,entry.id)||!Array.isArray(entry.acquisitions))){parent.append(node('p','Проверьте объекты приобретённых талантов (Talents) в JSON: нужны известный талант и список приобретений.','inventory-warning'));return;}
 for(const [i,talent] of (member.talents||[]).entries()){
  const supported=supportedPlayerTalents.includes(talent.id),tag=node('span',talentLabel(talent.id),'talent-tag'+(supported?'':' pending'));attachTagTooltip(tag,talentHint(talent.id));
  const remove=actionButton('remove','Удалить талант '+talentLabel(talent.id),true);remove.onclick=()=>setPlayerTalents(index,read().party[index].talents.filter((_,j)=>j!==i));tag.append(remove);tags.append(tag);
 }parent.append(tags);
 const entry=node('div',undefined,'talent-entry'),picker=node('div',undefined,'talent-picker'),input=node('input');input.type='text';input.placeholder='Найдите талант в книжном каталоге…';input.setAttribute('aria-label','Добавить талант персонажу '+(index+1));input.dataset.role='talent-entry';input.dataset.member=String(index);input.autocomplete='off';
 const options=node('div',undefined,'talent-suggestions hidden');options.id='talent-options-'+index;options.setAttribute('role','listbox');options.setAttribute('aria-label','Подсказки талантов');
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',options.id);input.setAttribute('aria-expanded','false');let selectedIndex=-1;
 const close=()=>{options.classList.add('hidden');input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');selectedIndex=-1;};
 const commit=id=>{
  if(!Object.hasOwn(talentMetadata,id)){message('Выберите талант (Talent) из книжного каталога.','error');return;}
  const values=read().party[index].talents||[];if(values.some(value=>value.id===id)){message('Этот талант уже добавлен.','error');close();return;}
  if(talentMetadata[id].selection)expandedTalentDetails.add(read().party[index].actor_id+':talent:'+id);
  close();setPlayerTalents(index,[...values,{id,acquisitions:[newTalentAcquisition(id)]}]);document.querySelector('[data-role="talent-entry"][data-member="'+index+'"]').focus();
 };
 const suggest=()=>{
  options.replaceChildren();selectedIndex=-1;input.removeAttribute('aria-activedescendant');const query=input.value.trim().toLowerCase(),owned=new Set(playerTalentIds(read().party[index]));
  const ids=[...supportedPlayerTalents,...Object.keys(talentMetadata).filter(id=>!supportedPlayerTalents.includes(id))],choices=ids.filter(id=>!owned.has(id)&&[id,talentMetadata[id].name,talentLabel(id)].some(name=>name.toLowerCase().includes(query)));
  if(!choices.length){close();return;}
  for(const [i,id] of choices.entries()){
   const option=node('button',talentLabel(id),'talent-option');option.type='button';option.id=options.id+'-'+i;option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.tabIndex=-1;
   option.append(node('small',talentHint(id)));option.onmousedown=event=>event.preventDefault();option.onclick=()=>commit(id);options.append(option);
  }options.classList.remove('hidden');input.setAttribute('aria-expanded','true');
 };
 input.onfocus=suggest;input.oninput=suggest;input.onblur=()=>setTimeout(()=>{if(!picker.contains(document.activeElement))close();},0);
 input.onkeydown=event=>{
  if(event.key==='Escape'){close();return;}
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){
   event.preventDefault();if(options.classList.contains('hidden'))suggest();const rows=[...options.querySelectorAll('[role="option"]')];if(!rows.length)return;
   selectedIndex=event.key==='ArrowDown'?(selectedIndex+1)%rows.length:(selectedIndex<0?rows.length-1:(selectedIndex+rows.length-1)%rows.length);rows.forEach((row,i)=>row.setAttribute('aria-selected',String(i===selectedIndex)));input.setAttribute('aria-activedescendant',rows[selectedIndex].id);return;
  }
  if(event.key==='Enter'){event.preventDefault();const rows=options.querySelectorAll('[role="option"]'),selected=rows[selectedIndex]||(input.value.trim()?rows[0]:null);if(selected&&!options.classList.contains('hidden'))selected.click();}
 };picker.append(input,options);entry.append(picker);parent.append(entry);
 for(const [talentIndex,talent] of (member.talents||[]).entries())renderTalentAcquisitions(parent,member,index,talent,talentIndex);
 renderTalentOwnerFacts(parent,member,index);
 renderPlayerOathContext(parent,member,index);
 const pending=(member.talents||[]).filter(talent=>!supportedPlayerTalents.includes(talent.id));
 if(pending.length)parent.append(node('p','Эффекты ещё не подключены к расчёту: '+pending.map(talent=>talentLabel(talent.id)).join(', ')+'. Источник можно редактировать и сохранять как черновик.','inventory-warning'));
}
function setPlayerTalents(index,talents){
 const member=read().party[index],previous=playerHasTalent(member,'wizard');member.talents=talents;const wizard=talents.find(value=>value.id==='wizard');
 if(wizard){
  if(!member.magic){member.magic={origin:'human',wizard_level:wizard.acquisitions.length,lores:['elementalism'],memorised_spells:['lightning_blast'],arcane_paraphernalia:true};const additions={};if(!Object.hasOwn(member.characteristics,'reason')){member.characteristics.reason=3;additions.reason=3;}if(!Object.hasOwn(member.skills,'willpower')){member.skills.willpower=3;additions.willpower=3;}wizardUiAdditions.set(member.actor_id,additions);}
  member.magic.wizard_level=wizard.acquisitions.length;
 }else if(previous){delete member.magic;const additions=wizardUiAdditions.get(member.actor_id)||{};if(additions.reason===member.characteristics.reason&&!talents.some(value=>talentMetadata[value.id].characteristics.reason))delete member.characteristics.reason;if(additions.willpower===member.skills.willpower)delete member.skills.willpower;wizardUiAdditions.delete(member.actor_id);}
 syncPlayerOathContext(member);editRequest(['party',index],member);
}
function oathContextHint(context){
 if(!context)return '';
 const yes=value=>value?'да':'нет',forbidden=(context.forbidden_attack_skills||[]).map(skill=>statFullNames[skill]||skill).join(', ')||'нет';
 return 'Исходные GM-факты сцены. '+(context.oath_id?'Обет (Oath): '+context.oath_id+'. ':'')+'Подтверждение GM: '+context.gm_confirmation_id+'. Обет соблюдён: '+yes(context.in_good_standing_confirmed)+'. Боевые проверки служат обету: '+yes(context.combat_tests_fulfil_oath_confirmed)+'. Исход Безоговорочного успеха (Unmitigated Success) подтверждён: '+yes(context.unmitigated_success_scope_confirmed)+'. Запрещённые атаки: '+forbidden+'. Бегство нарушает обет: '+yes(context.fleeing_breaks_oath)+'. Молитва перед боем (Lady Prayer): '+yes(context.lady_prayer_before_battle_confirmed)+'. Активация уже использована до боя в этой сессии (Session): '+yes(context.honour_bound_used_this_session)+'.';
}
function blankOathContext(oathId=null){return {gm_confirmation_id:'',in_good_standing_confirmed:false,oath_id:oathId,combat_tests_fulfil_oath_confirmed:false,forbidden_attack_skills:[],fleeing_breaks_oath:false,lady_prayer_before_battle_confirmed:false,honour_bound_used_this_session:false,unmitigated_success_scope_confirmed:false};}
function syncPlayerOathContext(member){
 const honour=(member.talents||[]).find(talent=>talent.id==='honour_bound'),lady=playerHasTalent(member,'blessings_of_the_lady');
 if(!honour&&!lady){delete member.oath_context;return;}
 if(!member.oath_context)member.oath_context=blankOathContext();
 member.oath_context.oath_id=honour?.acquisitions[0]?.choice?.oath_id||null;
 if(!honour){member.oath_context.unmitigated_success_scope_confirmed=false;member.oath_context.combat_tests_fulfil_oath_confirmed=false;member.oath_context.honour_bound_used_this_session=false;}
 if(!lady)member.oath_context.lady_prayer_before_battle_confirmed=false;
}
function renderOathContextFields(parent,context,path,change,{honour,lady}){
 const grid=node('div',undefined,'visual-fields talent-source-grid');
 inputField(grid,'Подтверждение GM',[...path,'gm_confirmation_id'],context.gm_confirmation_id||'',null,value=>change('gm_confirmation_id',value));
 for(const [key,title] of [['in_good_standing_confirmed','Обет соблюдён к началу сцены (Oath)'],...(honour?[['combat_tests_fulfil_oath_confirmed','Боевые проверки служат обету (Oath Tests)'],['unmitigated_success_scope_confirmed','GM подтвердил область Безоговорочного успеха (Unmitigated Success)'],['honour_bound_used_this_session','Активация уже использована в сессии (Session)']]:[]),...(lady?[['lady_prayer_before_battle_confirmed','Молитва действительно совершена перед боем (Lady Prayer)']]:[]),['fleeing_breaks_oath','Бегство нарушает обет (Oath)']]){
  const input=inputField(grid,title,[...path,key],context[key]===true,null,value=>change(key,value));input.parentElement.classList.add('toggle-field');
 }
 parent.append(grid);const restrictions=node('div',undefined,'visual-fields talent-source-grid');
 for(const [skill,title] of [['melee','Ближний бой (Melee)'],['brawn','Мощь (Brawn)'],['shooting','Стрельба (Shooting)'],['throwing','Метание (Throwing)']]){
  const input=inputField(restrictions,'Запрещены атаки: '+title,[...path,'forbidden_attack_skills',skill],(context.forbidden_attack_skills||[]).includes(skill),null,value=>change('forbidden_attack_skills',value?[...(context.forbidden_attack_skills||[]).filter(id=>id!==skill),skill]:(context.forbidden_attack_skills||[]).filter(id=>id!==skill)));input.parentElement.classList.add('toggle-field');
 }
 parent.append(restrictions);
 if(!String(context.gm_confirmation_id||'').trim())parent.append(node('p','Укажите источник подтверждения GM. Имя обета само по себе не определяет его исполнение или запреты.','inventory-warning'));
}
function renderPlayerOathContext(parent,member,index){
 const honour=playerHasTalent(member,'honour_bound'),lady=playerHasTalent(member,'blessings_of_the_lady');if(!honour&&!lady)return;
 const details=node('details',undefined,'talent-owner-facts');details.dataset.role='oath-context';details.append(node('summary','Обет и сцена (Oath)'));rememberTalentDetails(details,member.actor_id+':oath-context');
 const context=member.oath_context||blankOathContext(),path=['party',index,'oath_context'];
 renderOathContextFields(details,context,path,(key,value)=>{const current=read().party[index];syncPlayerOathContext(current);current.oath_context[key]=value;editRequest(['party',index],current);},{honour,lady});
 details.append(node('p','Подтверждаются исходные факты этой сцены. Молитву, применение таланта и расход Судьбы (Fate) выбирает симуляция.','visual-note'));parent.append(details);
}
function editGeneratedOathSource(index,change){const space=read().search_space,sources=space.allowed_oath_sources||[];change(sources[index]);editRequest(['search_space','allowed_oath_sources'],sources);}
function renderGeneratedOathSources(parent,space){
 const section=node('div');section.append(node('h4','Разрешённые обеты NPC (Oaths)'),node('p','Генератор может выбрать один из явно подтверждённых источников или NPC без обета. Требования не создаются автоматически.','visual-note'));
 for(const [index,source] of (space.allowed_oath_sources||[]).entries()){
  const details=node('details',undefined,'talent-owner-facts');rememberTalentDetails(details,'generated:oath:'+index);details.append(node('summary','Обет NPC '+(index+1)));
  const honour=(source.talents||[]).find(t=>t.id==='honour_bound'),lady=(source.talents||[]).find(t=>t.id==='blessings_of_the_lady'),grid=node('div',undefined,'visual-fields talent-source-grid');
  const mode=honour?(lady?'both':'honour'):'lady';
  inputField(grid,'Таланты (Talents)',['search_space','allowed_oath_sources',index,'talents'],mode,{honour:'Связанный честью (Honour Bound)',both:'Honour Bound + Blessings of the Lady',lady:'Благословения Леди (Blessings of the Lady)'},value=>editGeneratedOathSource(index,current=>{
   const existing=new Map(current.talents.map(t=>[t.id,t]));current.talents=[...(value!=='lady'?[existing.get('honour_bound')||{id:'honour_bound',acquisitions:[{phase:'advancement',funding:'xp',choice:{oath_id:''},devotion_confirmed:null}]}]:[]),...(value!=='honour'?[existing.get('blessings_of_the_lady')||{id:'blessings_of_the_lady',acquisitions:[{phase:'advancement',funding:'xp',choice:null,devotion_confirmed:null}]}]:[])];
   current.context.oath_id=current.talents.find(t=>t.id==='honour_bound')?.acquisitions[0]?.choice?.oath_id||null;
   if(value==='lady'){current.context.unmitigated_success_scope_confirmed=false;current.context.honour_bound_used_this_session=false;current.context.combat_tests_fulfil_oath_confirmed=false;}if(value==='honour')current.context.lady_prayer_before_battle_confirmed=false;
  }));
  if(honour)inputField(grid,'Обет (Oath)',['search_space','allowed_oath_sources',index,'oath_id'],honour.acquisitions[0]?.choice?.oath_id||'',null,value=>editGeneratedOathSource(index,current=>{current.talents.find(t=>t.id==='honour_bound').acquisitions[0].choice={oath_id:value};current.context.oath_id=value;}));
  inputField(grid,'Происхождение (Origin)',['search_space','allowed_oath_sources',index,'talent_facts','origin'],source.talent_facts?.origin||'none',talentOriginNames,value=>editGeneratedOathSource(index,current=>{current.talent_facts.origin=value==='none'?null:value;}));details.append(grid);
  for(const [talentIndex,talent] of (source.talents||[]).entries()){
   const fields=node('div',undefined,'visual-fields talent-source-grid'),acquisition=talent.acquisitions[0];fields.append(node('p',talentLabel(talent.id),'visual-note'));
   for(const [key,title,choices] of [['phase','Приобретение (Acquisition)',{creation:'Создание (Character Creation)',advancement:'Развитие (Advancement)'}],['funding','Оплата (Funding)',{xp:'За опыт (XP)',free:'Бесплатно (Free)'}]])inputField(fields,title,['search_space','allowed_oath_sources',index,'talents',talentIndex,'acquisitions',0,key],acquisition[key],choices,value=>editGeneratedOathSource(index,current=>{current.talents[talentIndex].acquisitions[0][key]=value;}));details.append(fields);
  }
  const lore=inputField(details,'Знание высшего общества (High Society Lore)',['search_space','allowed_oath_sources',index,'talent_facts','high_society'],(source.talent_facts?.lores||[]).some(l=>l.id==='high_society'&&!l.magic),null,value=>editGeneratedOathSource(index,current=>{const lores=current.talent_facts.lores||[];current.talent_facts.lores=value?[...lores.filter(l=>l.id!=='high_society'),{id:'high_society',magic:false}]:lores.filter(l=>l.id!=='high_society');}));lore.parentElement.classList.add('toggle-field');
  renderOathContextFields(details,source.context||blankOathContext(),['search_space','allowed_oath_sources',index,'context'],(key,value)=>editGeneratedOathSource(index,current=>{current.context[key]=value;}),{honour:!!honour,lady:!!lady});
  const remove=actionButton('remove','Удалить источник обета (Oath)',true);remove.onclick=()=>editRequest(['search_space','allowed_oath_sources'],(read().search_space.allowed_oath_sources||[]).filter((_,i)=>i!==index));details.append(remove);section.append(details);
 }
 const add=actionButton('add','Добавить источник обета (Oath)');add.dataset.role='add-oath-source';add.onclick=()=>editRequest(['search_space','allowed_oath_sources'],[...(read().search_space.allowed_oath_sources||[]),{talents:[{id:'honour_bound',acquisitions:[{phase:'advancement',funding:'xp',choice:{oath_id:''},devotion_confirmed:null}]}],context:blankOathContext(),talent_facts:{}}]);section.append(add);parent.append(section);
}
function renderPlayerMagic(parent,member,index){
 if(!member.magic)return;
 const magic=member.magic,path=['party',index,'magic'];parent.append(node('h4','Магия (Magic)'));
 const fields=node('div',undefined,'visual-fields');
 const level=inputField(fields,'Уровень мага (Wizard Level)',[...path,'wizard_level'],magic.wizard_level,null,value=>setPlayerTalentCount(index,'wizard',value));level.min='1';level.max='4';
 inputField(fields,'Происхождение (Origin)',[...path,'origin'],magic.origin,{human:'Человек (Human)',dwarf:'Гном (Dwarf)',halfling:'Полурослик (Halfling)',high_elf:'Высший эльф (High Elf)',wood_elf:'Лесной эльф (Wood Elf)',ogre:'Огр (Ogre)'});
 inputField(fields,'Магические принадлежности (Arcane Paraphernalia)',[...path,'arcane_paraphernalia'],magic.arcane_paraphernalia);parent.append(fields);
 parent.append(node('p','Школа магии (Magic Lore): Стихийная магия (Elementalism). Разум (Reason) и Сила воли (Willpower) редактируются в характеристиках и навыках выше.','visual-note'));
 const spells=node('div',undefined,'magic-spells');spells.setAttribute('role','group');spells.setAttribute('aria-label','Запомненные заклинания (Memorised Spells)');
 for(const [id,title] of Object.entries({lightning_blast:'Удар молнии (Lightning Blast)',fire_breath:'Огненное дыхание (Fire Breath)'})){
  const label=node('label'),box=node('input');box.type='checkbox';box.checked=(magic.memorised_spells||[]).includes(id);box.dataset.spell=id;box.dataset.member=String(index);
  box.onchange=()=>{const selected=read().party[index].magic.memorised_spells;editRequest([...path,'memorised_spells'],box.checked?[...selected,id]:selected.filter(value=>value!==id));};label.append(box,node('span',title));spells.append(label);
 }parent.append(spells);
 parent.append(node('p','Каждый бросок сотворения (Casting) занимает действие. Броня (Armour) и щит (Shield) делают проверку мрачной (Grim); Мантия из итильмара (Mantle of Ithilmar) сама этого штрафа не даёт. Принадлежности не добавляют отдельный бонусный куб.','visual-note'));
 const wizard=(member.talents||[]).find(value=>value.id==='wizard');
 if(wizard&&wizard.acquisitions.length!==magic.wizard_level)parent.append(node('p','Уровень мага (Wizard Level) не совпадает с числом приобретений таланта (Talent Purchases). Исправьте исходные факты; загрузка JSON не изменяет их автоматически.','inventory-warning'));
 if(['dwarf','halfling'].includes(magic.origin)&&wizard?.acquisitions.some(value=>value.funding==='xp'))parent.append(node('p','Для платного приобретения таланта Маг (Wizard) не выполнены требования происхождения (Origin).','inventory-warning'));
 if(!magic.arcane_paraphernalia)parent.append(node('p','Для расчёта нужны магические принадлежности (Arcane Paraphernalia); импровизированный комплект пока не поддержан.','inventory-warning'));
 if(!(magic.memorised_spells||[]).length)parent.append(node('p','Выберите хотя бы одно запомненное заклинание (Memorised Spell).','inventory-warning'));
}
'''

INVENTORY_SCRIPT = INVENTORY_SCRIPT.replace('__TALENT_METADATA__',
    json.dumps(_talent_metadata(), ensure_ascii=False, separators=(',', ':')))
