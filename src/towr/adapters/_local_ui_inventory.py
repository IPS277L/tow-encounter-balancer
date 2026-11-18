"""Inventory rows and talent tags over request facts; no combat execution."""

INVENTORY_STYLE = r'''
.inventory-row{--item-control-height:36px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) var(--item-control-height);gap:10px;align-items:end;margin:10px 0}
.inventory-row.consumable{grid-template-columns:minmax(0,1fr) var(--consumable-count-width,88px) 36px;margin:0}
.inventory-row input,.inventory-row select{width:100%;min-width:0;height:var(--item-control-height)}
.inventory-row.has-charge{grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto var(--item-control-height)}
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
@media(max-width:480px){.inventory-row,.inventory-row.has-charge{grid-template-columns:minmax(0,1fr) var(--item-control-height)}.inventory-row>label:first-child,.inventory-row.has-charge>label:nth-child(2){grid-column:1/-1}.consumable-item{--consumable-count-width:70px}.inventory-row.consumable>label:first-child{grid-column:auto}}
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
const talentNames={lucky:'Удачливый (Lucky)',wizard:'Маг (Wizard)',defensive_stance:'Оборонительная стойка (Defensive Stance)',wild_attack:'Дикая атака (Wild Attack)','mighty blow':'Могучий удар (Mighty Blow)'};
const pcCombatTalentIds=['defensive_stance','wild_attack'],supportedPlayerTalents=['lucky','wizard',...pcCombatTalentIds];
const pcCombatTalentHints={defensive_stance:'Боевое мастерство (WS) 3+. Успешная Защита (Defence) может снять собственное Пошатывание (Staggered) вместо доступного нового Staggered атакующему. Постоянная причина состояния сохраняется.',wild_attack:'Сила (S) 4+. Автоматический выбор для атаки или Помощи (Help) в Ближнем бою (Melee): получить Пошатывание (Staggered) до проверки ради Блистательного (Glorious) Test. Не используется при Staggered или Истощении (Drained).'};
const talentLabel=value=>talentNames[value.toLowerCase()]||value;
const heldLocations={carried:'Убрано / за спиной',left_hand:'В левой руке',right_hand:'В правой руке',both_hands:'В обеих руках'};
const twoHandedInventoryWeapons=new Set(['pickaxe','flail','billhook','halberd','glaive','greataxe','greatsword','greathammer','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','blunderbuss','hochland_long_rifle','weighted_net']);
function actionButton(kind,title,iconOnly=false){
 const button=node('button',undefined,kind==='add'?'action-add':'action-remove');button.type='button';button.title=title;button.setAttribute('aria-label',title);
 if(kind==='add'){button.textContent='Добавить';return button;}
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS('http://www.w3.org/2000/svg','path');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');
 path.setAttribute('d','M6 6l12 12M6 18 18 6');svg.append(path);button.append(svg);if(!iconOnly)button.append(node('span',title));return button;
}
function inventoryId(member,prefix){const ids=new Set([...(member.equipment?.weapons||[]),...(member.equipment?.armour||[]),...(member.consumables||[])].map(i=>i.id));let n=1;while(ids.has(prefix+':'+n))n++;return prefix+':'+n;}
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
  inventoryRemove(row,['party',index,'equipment','weapons'],i,'оружие '+(i+1));parent.append(row);
 }
 inventoryAdd(parent,'Добавить оружие',['party',index,'equipment','weapons'],m=>({id:inventoryId(m,'weapon'),weapon:'sword',location:'carried'}));
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
 if(!active.length)warnings.push('На начало боя нужно хотя бы одно оружие (Weapon) в руках.');
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
function setPlayerWeapon(index,itemIndex,key,value){const member=read().party[index],item=member.equipment.weapons[itemIndex];item[key]=value;if(key==='weapon'){if(pcExactingWeapons.has(value)){if(typeof item.initially_loaded!=='boolean')item.initially_loaded=true;}else delete item.initially_loaded;}syncPlayerRangedPreparation(member);editRequest(['party',index],member);}
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
function renderTalentTags(parent,member,index){
 parent.append(node('h4','Таланты (Talents)'));const tags=node('div',undefined,'talent-tags');
 for(const [i,talent] of (member.talents||[]).entries()){
  const supported=supportedPlayerTalents.includes(talent),tag=node('span',talentLabel(talent),'talent-tag'+(supported?'':' pending'));
  attachTagTooltip(tag,talent==='lucky'?'Первая трата Судьбы (Fate) за сессию бесплатна':talent==='wizard'?'Уровень мага (Wizard Level) и известные заклинания (Spells) задаются ниже':pcCombatTalentHints[talent]||'Ещё не поддержан симуляцией');
  const remove=actionButton('remove','Удалить талант '+talentLabel(talent),true);remove.onclick=()=>setPlayerTalents(index,read().party[index].talents.filter((_,j)=>j!==i));tag.append(remove);tags.append(tag);
 }parent.append(tags);
 const entry=node('div',undefined,'talent-entry'),picker=node('div',undefined,'talent-picker'),input=node('input');input.type='text';input.placeholder='Выберите или введите талант…';input.setAttribute('aria-label','Добавить талант персонажу '+(index+1));input.dataset.role='talent-entry';input.dataset.member=String(index);input.autocomplete='off';
 const options=node('div',undefined,'talent-suggestions hidden');options.id='talent-options-'+index;options.setAttribute('role','listbox');options.setAttribute('aria-label','Подсказки талантов');
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',options.id);input.setAttribute('aria-expanded','false');
 let selectedIndex=-1;
 const close=()=>{options.classList.add('hidden');input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');selectedIndex=-1;};
 const commit=raw=>{
  const value=raw.trim();if(!value)return;const talent=supportedPlayerTalents.includes(value.toLowerCase())?value.toLowerCase():value,values=read().party[index].talents||[];
  if(values.some(t=>t.toLowerCase()===talent.toLowerCase())){message('Этот талант уже добавлен.','error');close();return;}
  close();setPlayerTalents(index,[...values,talent]);document.querySelector('[data-role="talent-entry"][data-member="'+index+'"]').focus();
 };
 const suggest=()=>{
  options.replaceChildren();selectedIndex=-1;input.removeAttribute('aria-activedescendant');
  const query=input.value.trim(),values=read().party[index].talents||[],duplicate=value=>values.some(t=>t.toLowerCase()===value.toLowerCase()),choices=[];
  if(!duplicate('lucky') && ['lucky','удача','удачливый','удачливый (lucky)'].some(name=>name.includes(query.toLowerCase())))choices.push({value:'lucky',label:talentLabel('lucky'),hint:'Первая трата Судьбы (Fate) за сессию бесплатна.'});
  if(!duplicate('wizard') && ['wizard','маг','маг (wizard)'].some(name=>name.includes(query.toLowerCase())))choices.push({value:'wizard',label:talentLabel('wizard'),hint:'Сотворение (Casting) запомненных заклинаний (Memorised Spells) школы Elementalism.'});
  for(const value of pcCombatTalentIds)if(!duplicate(value) && [value,talentLabel(value),value.replaceAll('_',' ')].some(name=>name.toLowerCase().includes(query.toLowerCase())))choices.push({value,label:talentLabel(value),hint:pcCombatTalentHints[value]});
  if(query && !duplicate(query) && !choices.length)choices.push({value:query,label:'Добавить «'+talentLabel(query)+'»',hint:'Эффект этого таланта пока не подключён к симуляции.'});
  if(!choices.length){close();return;}
  for(const [i,choice] of choices.entries()){
   const option=node('button',choice.label,'talent-option');option.type='button';option.id=options.id+'-'+i;option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.tabIndex=-1;
   option.append(node('small',choice.hint));option.onmousedown=event=>event.preventDefault();option.onclick=()=>commit(choice.value);options.append(option);
  }options.classList.remove('hidden');input.setAttribute('aria-expanded','true');
 };
 input.onfocus=suggest;input.oninput=suggest;
 input.onblur=()=>setTimeout(()=>{if(!picker.contains(document.activeElement))close();},0);
 input.onkeydown=event=>{
  if(event.key==='Escape'){close();return;}
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){
   event.preventDefault();if(options.classList.contains('hidden'))suggest();const rows=[...options.querySelectorAll('[role="option"]')];if(!rows.length)return;
   selectedIndex=event.key==='ArrowDown'?(selectedIndex+1)%rows.length:(selectedIndex<0?rows.length-1:(selectedIndex+rows.length-1)%rows.length);
   rows.forEach((row,i)=>row.setAttribute('aria-selected',String(i===selectedIndex)));input.setAttribute('aria-activedescendant',rows[selectedIndex].id);return;
  }
  if(event.key==='Enter'){event.preventDefault();const rows=options.querySelectorAll('[role="option"]'),selected=rows[selectedIndex]||(input.value.trim()?rows[0]:null);if(selected&&!options.classList.contains('hidden'))selected.click();else commit(input.value);}
 };picker.append(input,options);entry.append(picker);parent.append(entry);
 for(const talent of pcCombatTalentIds.filter(t=>(member.talents||[]).includes(t))){
  const row=node('label',talentLabel(talent)+' — бесплатно при создании (Character Creation)','toggle-field talent-provenance'),checkbox=node('input');checkbox.type='checkbox';checkbox.checked=member.talent_acquisition?.[talent]==='creation_free';checkbox.dataset.path='party/'+index+'/talent_acquisition/'+talent;checkbox.setAttribute('aria-label','Бесплатно при создании: '+talentLabel(talent));row.title='Факт бесплатного получения при создании персонажа отменяет требования (Requirements) таланта; не является тактикой.';
  checkbox.onchange=()=>setPlayerTalentAcquisition(index,talent,checkbox.checked);row.prepend(checkbox);parent.append(row);
  const required=talent==='defensive_stance'?Number(member.characteristics?.weapon_skill)>=3:Number(member.characteristics?.strength)>=4;
  if(!required && !checkbox.checked)parent.append(node('p',talentLabel(talent)+': не выполнены требования (Requirements). Если талант получен бесплатно при создании, укажите этот факт; он не включается автоматически.','inventory-warning'));
 }
 parent.append(node('p','Подключены Удачливый (Lucky), Маг (Wizard), Оборонительная стойка (Defensive Stance) и Дикая атака (Wild Attack). Другие таланты (Talents) сохраняются как теги; до реализации их эффектов расчёт с ними недоступен.','visual-note'));
}
function setPlayerTalents(index,talents){
 const member=read().party[index],oldTalents=member.talents||[],previous=oldTalents.includes('wizard');member.talents=talents;
 if(member.talent_acquisition && typeof member.talent_acquisition==='object' && !Array.isArray(member.talent_acquisition)){for(const talent of pcCombatTalentIds)if(oldTalents.includes(talent)&&!talents.includes(talent))delete member.talent_acquisition[talent];if(!Object.keys(member.talent_acquisition).length)delete member.talent_acquisition;}
 if(talents.includes('wizard')){
  if(!member.magic)member.magic={origin:'human',wizard_level:1,lores:['elementalism'],memorised_spells:['lightning_blast'],arcane_paraphernalia:true};
  if(!Object.hasOwn(member.characteristics,'reason'))member.characteristics.reason=3;
  if(!Object.hasOwn(member.skills,'willpower'))member.skills.willpower=3;
 }else if(previous){delete member.magic;delete member.characteristics.reason;delete member.skills.willpower;}
 editRequest(['party',index],member);
}
function setPlayerTalentAcquisition(index,talent,free){
 const member=read().party[index],facts=member.talent_acquisition && typeof member.talent_acquisition==='object' && !Array.isArray(member.talent_acquisition)?{...member.talent_acquisition}:{};
 if(free)facts[talent]='creation_free';else delete facts[talent];
 if(Object.keys(facts).length)member.talent_acquisition=facts;else delete member.talent_acquisition;
 editRequest(['party',index],member);
}
function renderPlayerMagic(parent,member,index){
 if(!member.magic)return;
 const magic=member.magic,path=['party',index,'magic'];parent.append(node('h4','Магия (Magic)'));
 const fields=node('div',undefined,'visual-fields');
 const level=inputField(fields,'Уровень мага (Wizard Level)',[...path,'wizard_level'],magic.wizard_level);level.min='1';level.max='4';
 inputField(fields,'Происхождение (Origin)',[...path,'origin'],magic.origin,{human:'Человек (Human)',dwarf:'Гном (Dwarf)',halfling:'Полурослик (Halfling)',high_elf:'Высший эльф (High Elf)',wood_elf:'Лесной эльф (Wood Elf)',ogre:'Огр (Ogre)'});
 inputField(fields,'Магические принадлежности (Arcane Paraphernalia)',[...path,'arcane_paraphernalia'],magic.arcane_paraphernalia);parent.append(fields);
 parent.append(node('p','Школа магии (Magic Lore): Стихийная магия (Elementalism). Разум (Reason) и Сила воли (Willpower) редактируются в характеристиках и навыках выше.','visual-note'));
 const spells=node('div',undefined,'magic-spells');spells.setAttribute('role','group');spells.setAttribute('aria-label','Запомненные заклинания (Memorised Spells)');
 for(const [id,title] of Object.entries({lightning_blast:'Удар молнии (Lightning Blast)',fire_breath:'Огненное дыхание (Fire Breath)'})){
  const label=node('label'),box=node('input');box.type='checkbox';box.checked=(magic.memorised_spells||[]).includes(id);box.dataset.spell=id;box.dataset.member=String(index);
  box.onchange=()=>{const selected=read().party[index].magic.memorised_spells;editRequest([...path,'memorised_spells'],box.checked?[...selected,id]:selected.filter(value=>value!==id));};label.append(box,node('span',title));spells.append(label);
 }parent.append(spells);
 parent.append(node('p','Каждый бросок сотворения (Casting) занимает действие. Броня (Armour) и щит (Shield) делают проверку мрачной (Grim); Мантия из итильмара (Mantle of Ithilmar) сама этого штрафа не даёт. Принадлежности не добавляют отдельный бонусный куб.','visual-note'));
 if(['dwarf','halfling'].includes(magic.origin))parent.append(node('p','Талант Маг (Wizard) недоступен этому происхождению (Origin).','inventory-warning'));
 if(!magic.arcane_paraphernalia)parent.append(node('p','Для расчёта нужны магические принадлежности (Arcane Paraphernalia); импровизированный комплект пока не поддержан.','inventory-warning'));
 if(!(magic.memorised_spells||[]).length)parent.append(node('p','Выберите хотя бы одно запомненное заклинание (Memorised Spell).','inventory-warning'));
}
'''
