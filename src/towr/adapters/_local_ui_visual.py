"""DOM views over the current request/result JSON; no game rules."""

VISUAL_STYLE = r'''
.view-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.view-switch{display:flex;gap:4px}.view-switch button{height:32px;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;font-size:13px}
.view-switch button[aria-pressed="true"]{color:var(--accent);border-color:var(--accent);background:var(--hover)}
.view-switch button[aria-pressed="true"]:hover:not(:disabled){background:var(--active);border-color:var(--accent-strong)}
.view-switch button[aria-pressed="true"]:active:not(:disabled){background:var(--selected-active)}
.visual-view{display:flow-root;min-height:560px}.visual-view.hidden{display:none}.visual-card{border:1px solid var(--border);border-radius:6px;padding:14px;margin:12px 0;background:var(--surface-soft)}
.visual-card h3{font-size:15px;margin:0 0 12px}.visual-card h4{font-size:14px;margin:12px 0 8px}
.visual-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.visual-fields.character-identity{grid-template-columns:minmax(0,2fr) minmax(90px,1fr);align-items:end}
.visual-fields.character-stats{grid-template-columns:repeat(auto-fit,minmax(min(100%,136px),1fr));align-items:end}
.visual-fields.character-stats.skill-stats{grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr))}
.character-stats label{display:grid;grid-template-rows:auto 36px;align-content:start;font-size:12px;line-height:1.3}
.visual-fields.character-stats input{width:100%;max-width:100%;height:36px;text-align:left}
.character-stats input.stat-placeholder{color:var(--quiet);background:transparent;border-style:dashed;opacity:1;cursor:not-allowed}
.visual-fields input,.visual-fields select{width:100%;min-width:0}
select{font:inherit;padding:8px 36px 8px 10px;border:1px solid var(--input-border);border-radius:4px;background-color:var(--surface);color:var(--text);appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='m2 4 4 4 4-4' fill='none' stroke='%235d6977' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;background-size:12px 12px}
@media(forced-colors:active){select{appearance:auto;background-image:none;padding-right:8px}}
.visual-card details{margin-top:12px}.visual-card summary{cursor:pointer;color:var(--label);font-size:13px}
.visual-card details .visual-card{background:var(--surface)}.toggle-field{flex-direction:row;align-items:center;gap:8px}
.toggle-field input{width:auto}.visual-note{font-size:13px;color:var(--hint);line-height:1.5;margin:8px 0}
.automatic-npc-toggle{margin:14px 0}
.scene-blocking{grid-column:1/-1}.scene-blocking .visual-note{margin:4px 0 0}
.stale-notice{padding:10px 12px;background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:5px;color:var(--warning-text);font-size:13px;margin:12px 0}
.result-metrics{display:flex;flex-wrap:wrap;gap:10px 22px;margin:10px 0;font-size:13px}.result-metrics strong{display:block;font-size:19px;color:var(--text)}
.badge{display:inline-block;padding:3px 7px;border-radius:4px;background:var(--success-bg);color:var(--success-text);font-size:12px}
.badge.outside-badge{background:var(--warning-bg);color:var(--warning-text)}
.badge.unsupported-badge{background:var(--warning-bg);color:var(--error)}
.result-card{margin-top:18px}.result-card+.result-card{padding-top:18px;border-top:1px solid var(--border)}
#result-visual>.result-card:first-child{margin-top:0}#result-card-heading{padding:10px 0}
#request-visual>.visual-card:first-child,#result-visual>.result-card:first-child>.result-statistics{margin-top:0}
#result-card-heading.heading-spacer{visibility:hidden}
.result-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.result-heading h3{font-size:15px;margin:0}
.result-statistics .badge{margin-bottom:4px}
.npc-stat-table{width:100%;border-collapse:collapse;font-size:13px}
.npc-stat-tables{display:grid;gap:16px;margin:12px 0}
.npc-stat-table caption{text-align:left;font-size:14px;font-weight:600;margin-bottom:6px}
.npc-stat-table th,.npc-stat-table td{padding:6px 0;border-bottom:1px solid var(--divider)}
.npc-stat-table{table-layout:fixed}.npc-stat-table col.stat-value{width:32px}
.npc-stat-table th{text-align:left;font-size:12px;font-weight:400;color:var(--label);overflow-wrap:anywhere}.npc-stat-table td{text-align:right;font-variant-numeric:tabular-nums}
.npc-stat-table th:nth-child(3){padding-left:16px}.npc-stat-table td.unavailable{color:var(--quiet)}
.npc-loadout{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 14px;margin:14px 0 0;font-size:13px;line-height:1.5}
.npc-loadout dt{color:var(--label)}.npc-loadout dd{margin:0;overflow-wrap:anywhere}
.item-tags{display:flex;flex-wrap:wrap;gap:6px}.item-tag,.talent-tag{display:inline-flex;align-items:center;max-width:100%;min-height:26px;padding:3px 9px;border:1px solid var(--tag-border);border-radius:14px;background:var(--hover);color:var(--accent);font-size:12px;line-height:18px;cursor:help}
.item-tag.empty{background:transparent;border-style:dashed;border-color:var(--border);color:var(--quiet)}
@media(max-width:480px){.npc-loadout{grid-template-columns:1fr;gap:4px}.npc-loadout dd{margin-bottom:6px}}
.visual-empty{color:var(--hint);padding:16px 0}.visual-card button{font-size:13px}
@media(max-width:1100px){.visual-fields{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.visual-fields{grid-template-columns:1fr}}
'''

VISUAL_SCRIPT = r'''
let requestView='visual', resultView='visual', visualEditError=null;
const characteristicTerms={
 weapon_skill:{name:'Боевое мастерство',original:'Weapon Skill',short:'WS'},ballistic_skill:{name:'Меткость',original:'Ballistic Skill',short:'BS'},
 strength:{name:'Сила',original:'Strength',short:'S'},toughness:{name:'Стойкость',original:'Toughness',short:'T'},
 initiative:{name:'Инициатива',original:'Initiative',short:'I'},agility:{name:'Ловкость',original:'Agility',short:'Ag'},
 reason:{name:'Разум',original:'Reason',short:'Re'},fellowship:{name:'Обаяние',original:'Fellowship',short:'Fel'}};
// PG14/68: official Characteristic abbreviations; Skills use full originals.
const skillTerms={
 melee:{name:'Ближний бой',original:'Melee'},defence:{name:'Защита',original:'Defence'},
 shooting:{name:'Стрельба',original:'Shooting'},throwing:{name:'Метание',original:'Throwing'},
 brawn:{name:'Грубая сила',original:'Brawn'},toil:{name:'Тяжёлый труд',original:'Toil'},
 survival:{name:'Выживание',original:'Survival'},endurance:{name:'Выносливость',original:'Endurance'},
 awareness:{name:'Внимательность',original:'Awareness'},dexterity:{name:'Ловкость рук',original:'Dexterity'},
 athletics:{name:'Атлетика',original:'Athletics'},stealth:{name:'Скрытность',original:'Stealth'},
 willpower:{name:'Сила воли',original:'Willpower'},recall:{name:'Память',original:'Recall'},
 leadership:{name:'Лидерство',original:'Leadership'},charm:{name:'Обаяние',original:'Charm'}};
const termLabels=(terms,style)=>Object.fromEntries(Object.entries(terms).map(([key,term])=>[key,term.name+' ('+term[style]+')']));
const characteristicNames=termLabels(characteristicTerms,'short'),characteristicFullNames=termLabels(characteristicTerms,'original');
const statLabels={...characteristicNames,...termLabels(skillTerms,'original'),armour_bonus:'Бонус брони (Armour Bonus)'};
const statFullNames={...characteristicFullNames,...termLabels(skillTerms,'original')};
const weaponNames={staff:'Посох (Staff)',sword:'Меч (Sword)',dagger:'Кинжал (Dagger)',axe:'Топор (Axe)',warhammer:'Боевой молот (Warhammer)',
 knuckledusters:'Кастеты (Knuckledusters)',cavalry_spear:'Кавалерийное копьё (Cavalry Spear)',lance:'Пика (Lance)',
 morning_star:'Моргенштерн (Morning Star)',foot_spear:'Пешее копьё (Foot Spear)',polearm:'Древковое оружие (Polearm)',pickaxe:'Клевец (Pickaxe)',flail:'Цеп (Flail)',billhook:'Гвизарма (Billhook)',halberd:'Алебарда (Halberd)',glaive:'Глефа (Glaive)',greataxe:'Двуручный топор (Greataxe)',greatsword:'Двуручный меч (Greatsword)',greathammer:'Двуручный молот (Greathammer)',weighted_net:'Утяжелённая сеть (Weighted Net)'};
const generatedWeaponNames={...weaponNames,dragon_bow:'Лук дракона (Dragon Bow)',duellist_blades:'Клинки дуэлянта (Duellist Blades)',grotarggs_hammer:'Молот Гротаргга (Grotargg’s Hammer)',headsmans_axe:'Топор палача (Headsman’s Axe)',morning_star_of_fracasse:'Моргенштерн Фракасса (Morning Star of Fracasse)',scarab_knife:'Нож скарабея (Scarab Knife)',sword_of_justice:'Меч правосудия (Sword of Justice)',trickster_blade:'Клинок обманщика (Trickster Blade)',unwavering_spear:'Непоколебимое копьё (Unwavering Spear)',ogre_pistol:'Огрский пистолет (Ogre Pistol)',rock:'Камень (Rock)',throwing_spear:'Метательное копьё (Throwing Spear)',throwing_axe:'Метательный топор (Throwing Axe)',throwing_knives:'Метательные ножи (Throwing Knives)',oil_flask:'Масляная склянка (Oil Flask)',blasting_charge:'Подрывной заряд (Blasting Charge)',sling:'Праща (Sling)',pistol:'Пистолет (Pistol)',repeater_pistol:'Многозарядный пистолет (Repeater Pistol)',repeater_handbow:'Многозарядный ручной арбалет (Repeater Handbow)',shortbow:'Короткий лук (Shortbow)',warbow:'Боевой лук (Warbow)',longbow:'Длинный лук (Longbow)',crossbow:'Арбалет (Crossbow)',repeater_crossbow:'Многозарядный арбалет (Repeater Crossbow)',handgun:'Ружьё (Handgun)',repeater_handgun:'Многозарядное ружьё (Repeater Handgun)',blunderbuss:'Мушкетон (Blunderbuss)',hochland_long_rifle:'Хохландская длинная винтовка (Hochland Long Rifle)'};
const playerWeaponNames={...generatedWeaponNames,sling:'Праща (Sling)'},pcCloseRangedWeapons=new Set(['pistol','repeater_pistol','repeater_handbow','ogre_pistol']);
const pcRangedWeapons=new Set([...pcCloseRangedWeapons,'shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','blunderbuss','hochland_long_rifle','sling','dragon_bow']);
const pcFreeReloadWeapons=new Set(['shortbow','warbow','longbow','sling','dragon_bow']),pcFirearms=new Set(['pistol','repeater_pistol','handgun','repeater_handgun','blunderbuss','hochland_long_rifle','ogre_pistol']);
const pcExactingWeapons=new Set([...pcRangedWeapons].filter(weapon=>!pcFreeReloadWeapons.has(weapon)));
const pcRepeaterWeapons=new Set(['repeater_pistol','repeater_handbow','repeater_crossbow','repeater_handgun']);
const pcThrowingWeapons=new Set(['weighted_net','rock','throwing_spear','throwing_axe','throwing_knives','oil_flask','blasting_charge']);
const pcFiniteThrowingWeapons=new Set([...pcThrowingWeapons].filter(kind=>kind!=='throwing_knives'));
function playerThrowingWeapons(member){return (member.equipment?.weapons||[]).filter(item=>pcThrowingWeapons.has(item.weapon));}
function playerBrawnRequired(member){const weapons=member.equipment?.weapons||[];return !weapons.some(item=>item.location!=='carried')||weapons.some(item=>['knuckledusters','grotarggs_hammer'].includes(item.weapon));}
function playerRangedRequirements(member){
 const weapons=(member.equipment?.weapons||[]).filter(item=>pcRangedWeapons.has(item.weapon));
 if(!weapons.length)return null;
 return {weapons,exacting:weapons.some(item=>pcExactingWeapons.has(item.weapon)),firearm:weapons.some(item=>pcFirearms.has(item.weapon)),repeater:weapons.some(item=>pcRepeaterWeapons.has(item.weapon)),requiresAim:weapons.some(item=>item.weapon==='hochland_long_rifle')};
}
const twoHandedWeaponHints={
 dragon_bow:'Магический Урон (Damage)6; Optimum Medium–Extreme, две руки. Без отрицательных кубов и Мрачного (Grim); невидимую цель атаковать нельзя. Одна огненная стрела за бой.',
 scarab_knife:'Магический Урон (Damage) S+1; попадание даёт Истощение (Drained), причинённая Рана (Wound) — заряд. Три заряда лечат одну собственную рану через Восстановление (Recover).',
 ogre_pistol:'Урон (Damage)5, игнорирует броню (Armour); Optimum Close–Medium, maximum Long, Перезарядка (Reload)3. Требует подтверждения GM о пригодности владельцу.',
 rock:'Метание (Throwing), нужна одна пригодная рука. Попадание даёт Пошатнувшийся (Staggered) вместо Урона (Damage); повторное Staggered может дать Рану (Wound). Optimum Short–Medium; при Силе (S)≥4 верхняя граница увеличена. Предмет падает у исходной позиции цели и может быть подобран.',
 throwing_spear:'Одноручное Метание (Throwing); Урон (Damage) = Сила (Strength). Optimum Close–Medium, при S≥4 верхняя граница увеличена. Конечный подбираемый предмет.',
 throwing_axe:'Одноручное Метание (Throwing); Урон (Damage) = Сила (Strength) +1, ещё +1 против бронированной цели. Optimum Short, при S≥4 верхняя граница увеличена. Конечный подбираемый предмет.',
 throwing_knives:'Одноручное Метание (Throwing); Урон (Damage) = Сила (Strength). Optimum Short, при S≥4 верхняя граница увеличена. Один комплект содержит достаточно ножей на весь бой.',
 oil_flask:'Одноручное Метание (Throwing); Optimum Short–Medium. При попадании Горит (Ablaze) получает цель и все существа рядом (Close). Расходуется при броске; не подбирается.',
 blasting_charge:'Одноручное Метание (Throwing); Optimum Short–Medium. Попадание создаёт Опасность (Hazard)3 для всех в зоне (Zone) цели; промах — в зоне атакующего. Сопротивление Выносливостью (Endurance). Расходуется при броске.',
 sling:'Одноручная Стрельба (Shooting); Урон (Damage) = Сила (Strength). Optimum Medium, maximum Long; нельзя стрелять рядом с Close enemy. Зарядка бесплатна как часть Attack, без отдельного Reload.',
 foot_spear:'Дальность (Range) Close–Short. Урон (Damage) = Сила (Strength), +1 при двуручном хвате. +1d к Защите (Defence) против настоящего Натиска (Charge).',
 polearm:'Дальность (Range) Close–Short. Урон (Damage) = Сила (Strength), +2 при двуручном хвате.',
 shortbow:'Двуручное. Урон (Damage)3; оптимальная дальность (Optimum Range) Short–Medium. Свободная перезарядка (Free Reload); нельзя стрелять рядом с противником (Close enemy).',
 warbow:'Двуручное. Урон (Damage)3; оптимальная дальность (Optimum Range) Medium–Long. Свободная перезарядка (Free Reload); нельзя стрелять рядом с противником (Close enemy).',
 longbow:'Двуручное. Урон (Damage)4; оптимальная дальность (Optimum Range) Medium–Long. Свободная перезарядка (Free Reload); нельзя стрелять рядом с противником (Close enemy).',
 crossbow:'Двуручное. Урон (Damage)4, +1 против бронированной цели. Оптимальная дальность (Optimum Range) Short–Long; Перезарядка (Reload)2 успеха.',
 repeater_crossbow:'Двуручное. Урон (Damage)4; оптимальная дальность (Optimum Range) Short–Medium. Дополнительный залп +2d открывает Перезарядку (Reload)3 успеха.',
 handgun:'Двуручное. Урон (Damage)5, игнорирует броню. Оптимальная дальность (Optimum Range) Medium–Long, −1d на Short; Перезарядка (Reload)3 успеха.',
 repeater_handgun:'Двуручное. Урон (Damage)5, игнорирует броню. Оптимальная дальность (Optimum Range) Short–Long; дополнительный залп +3d открывает Перезарядку (Reload)5 успехов.',
 blunderbuss:'Двуручное. Урон (Damage)4; оптимальная дальность (Optimum Range) Short, максимум Medium. Попадание накладывает Ошеломление (Staggered) на остальные близкие цели. Перезарядка (Reload)3 успеха.',
 hochland_long_rifle:'Двуручное. Урон (Damage)6, игнорирует броню; +2 к проверке Раны (Wound). Оптимальная дальность (Optimum Range) Medium–Extreme. Обязательно Прицеливание (Aim); Перезарядка (Reload)4 успеха.',
 weighted_net:'Двуручное Метание (Throwing), использует Меткость (BS). Урона и раны не наносит: попадание даёт Перегруженность (Burdened). Оптимум Close–Short, при Силе (S)≥4 — Close–Medium. Конечный предмет; освобождение одной сети — отдельный Recover/Brawn, затем возможен подбор.'
};
function node(tag,text,classes){const element=document.createElement(tag);if(text!==undefined)element.textContent=String(text);if(classes)element.className=classes;return element;}
function card(title){const element=node('section',undefined,'visual-card');element.append(node('h3',title));return element;}
function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
function markResultStale(){
 let stale=false;if(lastResult){try{stale=canonical(read())!==canonical(lastResult.source_request);}catch(_){stale=true;}}
 byId('result-stale').classList.toggle('hidden',!stale);
}
function editRequest(path,value){
 if(busy)return;
 try{const before=read(),data=path.length?before:value;const oldId=path[0]==='party'&&path[2]==='actor_id'?data.party[path[1]].actor_id:null;if(path.length)put(data,path,value);if(path[0]==='party'&&data.player_side_activation_order){if(oldId)data.player_side_activation_order=data.player_side_activation_order.map(id=>id===oldId?value:id);const ids=[...data.party.map(m=>m.actor_id),...(data.npc_allies||[]).map(m=>m.actor_id)];data.player_side_activation_order=[...data.player_side_activation_order.filter(id=>ids.includes(id)),...ids.filter(id=>!data.player_side_activation_order.includes(id))];}byId('request').value=pretty(data);syncForm();message('Запрос изменён. Новый расчёт — по кнопке «Запустить генератор».');}
 catch(error){message(error.message,'error');}
}
function inputField(parent,title,path,value,choices=null,onChange=null){
 const label=node('label',title);let input;
 if(choices){input=node('select');for(const [key,name] of Object.entries(choices)){const option=node('option',name);option.value=key;input.append(option);}if(!(value in choices)){const option=node('option',String(value));option.value=value;input.append(option);}input.value=value;input.title=characteristicFullNames[value]||choices[value]||String(value);}
 else{input=node('input');input.type=typeof value==='boolean'?'checkbox':typeof value==='number'?'number':'text';if(input.type==='checkbox'){input.checked=value;label.classList.add('toggle-field');}else input.value=value??'';if(input.type==='number')input.step='1';}
 const fullName=statFullNames[path.at(-1)];if(fullName){label.title=fullName;input.title=fullName;input.setAttribute('aria-label',fullName);}
 input.dataset.path=path.join('/');input.addEventListener('change',()=>{try{if(onChange){onChange(input.type==='checkbox'?input.checked:input.value);return;}editRequest(path,input.type==='checkbox'?input.checked:typeof value==='number'?integer(input.value):input.value);}catch(error){visualEditError=error.message;message(error.message,'error');}});
 label.append(input);parent.append(label);return input;
}
function playerStatInput(parent,member,index,section,key){
 const values=member[section]||{},terms=section==='characteristics'?characteristicTerms:skillTerms,supported=section==='characteristics'?['weapon_skill','strength','toughness','agility','initiative','reason']:['melee','defence','endurance','athletics','brawn','awareness','recall','dexterity'];
 if(section==='skills'&&member.magic && playerHasTalent(member,'wizard'))supported.push('willpower');
 if(playerMusicRelevant(member)||Object.hasOwn(values,section==='characteristics'?'fellowship':'leadership'))supported.push(section==='characteristics'?'fellowship':'leadership');
 const rangedStat=(section==='characteristics'?['ballistic_skill']:['shooting','throwing','brawn']).includes(key);
 const ranged=playerRangedRequirements(member);
 if(ranged)supported.push(...(section==='characteristics'?['ballistic_skill']:['shooting',...(ranged.exacting?['dexterity']:[])]));
 if(playerThrowingWeapons(member).length)supported.push(section==='characteristics'?'ballistic_skill':'throwing');
 if(Object.hasOwn(terms,key)&&!supported.includes(key)){
  const label=node('label',statLabels[key]),input=node('input');input.type='text';input.value=values[key]??'—';input.disabled=true;input.className='stat-placeholder';input.dataset.stat=key;input.title=statFullNames[key]+(rangedStat?' · Не используется с этим снаряжением; сохранённое значение остаётся в персонаже':' · Пока не подключено к симуляции');input.setAttribute('aria-label',input.title);label.append(input);parent.append(label);
 }else if(key==='fellowship'||key==='leadership'){const path=['party',index,section,key],input=inputField(parent,statLabels[key],path,values[key]??'',null,value=>editRequest(path,value===''?undefined:integer(value)));input.type='number';input.step='1';input.min='1';if(section==='skills')input.max='10';input.placeholder='Не задано';}
 else if(rangedStat||['initiative','awareness','reason','recall','dexterity'].includes(key)){const doctor=playerHasTalent(member,'combat_surgeon'),optional=key==='brawn'&&!playerBrawnRequired(member)||key==='awareness'&&!ranged?.requiresAim||key==='initiative'&&!ranged?.exacting&&!ranged?.requiresAim&&!member.skills?.awareness&&!member.skills?.dexterity||key==='reason'&&!member.magic&&!member.skills?.recall&&!doctor||key==='recall'&&!doctor||key==='dexterity'&&!ranged?.exacting&&!doctor;const path=['party',index,section,key],input=inputField(parent,statLabels[key],path,values[key]??'',null,raw=>editRequest(path,optional&&raw===''?undefined:integer(raw)));input.type='number';input.step='1';input.min='1';if(section==='skills')input.max='10';input.required=!optional;input.placeholder=optional?({brawn:'Безоружная атака / освобождение',reason:'Для Recall',recall:'Для обработки ран',dexterity:'Для Reload / операции',initiative:'Для Aim / Dexterity'}[key]||'Для Aim'):'Обязательно';}
 else inputField(parent,statLabels[key]||key,['party',index,section,key],values[key]);
}
function appendNpcAlly(npc){
 const data=read(),allies=data.npc_allies||[],ids=new Set([...data.party.map(m=>m.actor_id),...allies.map(m=>m.actor_id)]);let ordinal=allies.length+1;while(ids.has('npc-ally:'+ordinal))ordinal++;const actor_id='npc-ally:'+ordinal;
 data.npc_allies=[...allies,{actor_id,npc}];if(data.player_side_activation_order)data.player_side_activation_order.push(actor_id);editRequest([],data);
}
function defaultNpcAlly(){return {weapon_skill:3,strength:3,toughness:3,agility:3,melee:4,athletics:3,defence:3,endurance:null,abilities:[],talents:[],ranged:null,mount:null,throwing:null,brawn:null,ballistic_skill:null,reason:null,recall:null,dexterity:null,injury_policy:'minion',rider_kind:null,agilulf_code_confirmed:null,armour:{body:[],benefit:null,helmet:null,shield:null,barding:false},weapons:[{id:'item:1',weapon:'staff',location:'held',hand:'left'}]};}
function renderNpcAllies(parent,data){
 const allies=data.npc_allies||[],section=node('details',undefined,'visual-card');section.open=allies.length>0;section.append(node('summary','Союзные NPC (Allied NPCs) — необязательно'));section.append(node('p','Фиксированные участники на стороне игроков. Генератор меняет только противников; Судьба (Fate) союзным NPC не выдаётся.','visual-note'));
 for(const [index,ally] of allies.entries()){
  const npc=ally.npc,person=card('Союзник '+(index+1)+' · '+ally.actor_id);person.classList.add('npc-card');const path=['npc_allies',index,'npc'];
  const heading=person.querySelector('h3');heading.classList.add('character-heading');const actions=npcAllyFileControls(index),remove=actionButton('remove','Удалить союзного NPC '+ally.actor_id,true);remove.disabled=busy;remove.onclick=()=>{const current=read();current.npc_allies=current.npc_allies.filter((_,i)=>i!==index);if(current.player_side_activation_order)current.player_side_activation_order=current.player_side_activation_order.filter(id=>id!==ally.actor_id);editRequest([],current);};actions.append(remove);heading.append(actions);
  const identity=node('div',undefined,'visual-fields character-identity');inputField(identity,'Имя / ID',['npc_allies',index,'actor_id'],ally.actor_id,null,value=>{const current=read();if([...current.party,...current.npc_allies.filter((_,i)=>i!==index)].some(m=>m.actor_id===value))throw Error('Этот ID уже занят.');const old=current.npc_allies[index].actor_id;current.npc_allies[index].actor_id=value;if(current.player_side_activation_order)current.player_side_activation_order=current.player_side_activation_order.map(id=>id===old?value:id);editRequest([],current);});inputField(identity,'Ранения (Wounds)',[...path,'injury_policy'],npc.injury_policy||'minion',{minion:'Приспешник (Minion)',champion:'Чемпион (Champion)'});person.append(identity);
  for(const [keys,title] of [[Object.keys(characteristicTerms),'Характеристики (Characteristics)'],[Object.keys(skillTerms),'Навыки (Skills)']]){
   person.append(node('h4',title));const grid=node('div',undefined,'visual-fields character-stats'+(title.startsWith('Навыки')?' skill-stats':''));
   const supported=new Set(['weapon_skill','ballistic_skill','strength','toughness','initiative','agility','reason','fellowship','melee','defence','athletics','endurance','throwing','brawn','shooting','dexterity','recall','awareness','leadership']);
   for(const key of keys){const nested=npc.ranged&&['ballistic_skill','shooting'].includes(key),value=(nested?npc.ranged:npc)[key],statPath=nested?[...path,'ranged',key]:[...path,key];
    if(!supported.has(key)||(key==='shooting'&&!npc.ranged)){const label=node('label',statLabels[key]),input=node('input');input.value='—';input.disabled=true;input.className='stat-placeholder';input.title=statFullNames[key];label.append(input);grid.append(label);continue;}
    const required=['weapon_skill','strength','toughness','agility','melee','athletics'].includes(key)||key==='endurance'&&npc.injury_policy==='champion';const input=inputField(grid,statLabels[key],statPath,value??'',null,raw=>editRequest(statPath,raw===''?null:integer(raw)));input.type='number';input.min='1';if(Object.hasOwn(skillTerms,key)){input.min='2';input.max='6';}input.required=required;input.placeholder=required?'Обязательно':'Не задано';
   }person.append(grid);
  }
  person.append(node('h4','Снаряжение и таланты (Equipment and Talents)'));const tags=[];for(const item of npc.weapons||[])tags.push([generatedWeaponNames[item.weapon]||item.weapon,(item.location==='held'?'В руках (Held)':'При себе (Carried)')+' · '+(item.hand||'')]);for(const kind of [...(npc.armour?.body||[]),npc.armour?.helmet,npc.armour?.shield,npc.armour?.barding?'barding':null].filter(Boolean))tags.push([armourNames[kind]||kind,armourHints[kind]||kind]);for(const item of npc.tools||[])tags.push([item.kind==='physickers_kit'?'Набор лекаря (Physicker’s Kit)':'Инструменты музыканта (Musician’s Gear)',item.location+' · '+item.hands_required+' рук']);for(const talent of npc.talents||[])tags.push([talentLabel(talent.id),talentHint(talent.id)]);person.append(resultItemTags(tags,'Предметы и таланты не заданы'));
  renderMedicalPreparation(person,[...path,'medical'],npc.medical||null,value=>editRequest([...path,'medical'],value));
  const details=node('details');details.append(node('summary','Полный источник NPC (JSON)'));const editor=node('textarea');editor.value=pretty(npc);editor.rows=9;editor.style.width='100%';editor.setAttribute('aria-label','Полный источник союзного NPC');editor.disabled=busy;const apply=node('button','Применить JSON');apply.type='button';apply.disabled=busy;apply.onclick=async()=>{try{const snapshot=canonical(read().npc_allies[index].npc),parsed=await validateCharacterText('npc',editor.value);if(canonical(read().npc_allies[index].npc)!==snapshot)throw Error('Карточка изменилась; откройте редактор заново.');editRequest(path,parsed);}catch(error){message(error.message,'error');}};details.append(editor,apply);person.append(details);section.append(person);
 }
 const actions=node('div',undefined,'player-actions'),add=actionButton('add','Добавить союзного NPC');add.disabled=busy;add.onclick=()=>appendNpcAlly(defaultNpcAlly());actions.append(add,addNpcAllyFileControls());section.append(actions);
 if(allies.length){const order=node('details');order.append(node('summary','Порядок ходов стороны игроков (Activation Order)'));const label=node('label','Задать явный порядок','toggle-field'),toggle=node('input');toggle.type='checkbox';toggle.checked=!!data.player_side_activation_order;toggle.onchange=()=>editRequest(['player_side_activation_order'],toggle.checked?[...read().party.map(m=>m.actor_id),...(read().npc_allies||[]).map(m=>m.actor_id)]:null);label.prepend(toggle);order.append(label);if(data.player_side_activation_order){const input=inputField(order,'ID участников по порядку, через запятую',['player_side_activation_order'],data.player_side_activation_order.join(', '),null,value=>editRequest(['player_side_activation_order'],value.split(',').map(s=>s.trim()).filter(Boolean)));input.title='Каждый игрок и союзный NPC ровно один раз.';}else order.append(node('p','По умолчанию игроки, затем союзные NPC в порядке карточек.','visual-note'));section.append(order);}
 parent.append(section);
}
function renderRequestVisual(data){
 visualEditError=null;
 if(requestView!=='visual')return;
 hideTagTooltip();
 const root=byId('request-visual');root.replaceChildren();
 for(const [index,member] of (data.party||[]).entries()){
  const person=card('Игрок '+(index+1)+' · '+member.actor_id);person.classList.add('player-card');
  const identity=node('div',undefined,'visual-fields character-identity');inputField(identity,'Имя / ID',['party',index,'actor_id'],member.actor_id);
  inputField(identity,'Судьба (Fate)',['party',index,'resources','fate'],member.resources?.fate);person.append(identity);
  for(const [section,title] of [['characteristics','Характеристики (Characteristics)'],['skills','Навыки (Skills)']]){
   person.append(node('h4',title));const stats=node('div',undefined,'visual-fields character-stats'+(section==='skills'?' skill-stats':'')),terms=section==='characteristics'?characteristicTerms:skillTerms;
   for(const key of [...Object.keys(terms),...Object.keys(member[section]||{}).filter(key=>!Object.hasOwn(terms,key))])playerStatInput(stats,member,index,section,key);person.append(stats);
  }
  renderInventory(person,member,index);
  renderPlayerRangedPreparation(person,member,index);
  renderTalentTags(person,member,index);
  renderPlayerMagic(person,member,index);
  const remove=actionButton('remove','Удалить игрока '+member.actor_id,true);remove.dataset.action='remove-player';remove.disabled=busy||(data.party||[]).length<=1;remove.onclick=()=>editRequest(['party'],read().party.filter((_,i)=>i!==index));const actions=playerFileControls(index);actions.append(remove);person.querySelector('h3').classList.add('character-heading');person.querySelector('h3').append(actions);root.append(person);
 }
 const add=actionButton('add','Добавить игрока');add.dataset.action='add-player';add.disabled=busy;add.onclick=()=>{
  const data=read(),members=data.party||[];let id='pc:'+(members.length+1),suffix=members.length+1;while([...members,...(data.npc_allies||[])].some(m=>m.actor_id===id))id='pc:'+(++suffix);
  const member=JSON.parse(JSON.stringify(members[0]||{characteristics:{weapon_skill:3,strength:3,toughness:3,agility:3},skills:{melee:4,defence:4,athletics:4,endurance:4,brawn:4},equipment:{weapons:[{id:'weapon:1',weapon:'staff',location:'right_hand'}],armour:[]},consumables:[],talents:[],resources:{fate:2}}));member.actor_id=id;editRequest(['party'],[...members,member]);
 };const playerActions=node('div',undefined,'player-actions');playerActions.append(add,addPlayerFileControls());root.append(playerActions);
 renderNpcAllies(root,data);
 const scene=card('Сцена'),sceneGrid=node('div',undefined,'visual-fields');
 const ranges={close:'Ближняя (Close)',short:'Короткая (Short)',medium:'Средняя (Medium)',long:'Дальняя (Long)',extreme:'Предельная (Extreme)'};
 for(const [key,title,choices] of [['range','Начальная дистанция (Range)',ranges],['two_handed_max_range','Предел стрельбы 2H (Maximum Range)',Object.fromEntries(Object.entries(ranges).filter(([key])=>key!=='close'))],['ambush','Засада (Ambush)',{none:'Нет — засады пока не поддержаны'}],['terrain','Местность (Terrain)',{open:'Открытая по умолчанию'}]])inputField(sceneGrid,title,['scene',key],data.scene?.[key],choices);
 inputField(sceneGrid,'Воздушное пространство (Airspace)',['scene','airspace'],data.scene?.airspace?'open':'none',{none:'Только наземные зоны',open:'Открытое небо'},value=>editRequest(['scene','airspace'],value==='open'?{open_sky_confirmed:true,fall_hazard_rating:2}:null));
 if(data.scene?.airspace)inputField(sceneGrid,'Опасность падения (Hazard Rating)',['scene','airspace','fall_hazard_rating'],data.scene.airspace.fall_hazard_rating).min='1';
 const blocking=node('div',undefined,'scene-blocking'),blockingInput=inputField(blocking,'Враги перекрывают проходы',['scene','enemy_zone_blocking'],data.scene?.enemy_zone_blocking??false);
 const blockingHint=node('p','Решение ведущего (GM): враги в Ближней дистанции (Close Range) перекрывают узкие выходы из исходной Зоны (Zone) и проходы через промежуточные Зоны (Zones).','visual-note');blockingHint.id='scene-enemy-zone-blocking-hint';blockingInput.setAttribute('aria-describedby',blockingHint.id);blocking.append(blockingHint);sceneGrid.append(blocking);
 const companions=node('div',undefined,'scene-blocking'),companionsInput=inputField(companions,'Спешенные животные (Mounts) — участники боя',['scene','dismounted_mounts_are_combatants'],data.scene?.dismounted_mounts_are_combatants??false);
 const companionsHint=node('p','Решение ведущего (GM): учитывать оставшихся без всадника животных (Mounts) как участников боя. По умолчанию они не участвуют; тактика ожидания и восстановления (Recover) сохраняется.','visual-note');companionsHint.id='scene-dismounted-mount-combatants-hint';companionsInput.setAttribute('aria-describedby',companionsHint.id);companions.append(companionsHint);sceneGrid.append(companions);
 const acoustics=node('div',undefined,'scene-blocking'),music=data.scene?.music_acoustics;
 inputField(acoustics,'Слышимость музыки (Battlefield Musician)',['scene','music_acoustics'],music==null?'none':'configured',{none:'Факт не задан',configured:'Задать условия слышимости'},value=>editRequest(['scene','music_acoustics'],value==='none'?null:{audible_confirmed:true,blocked_zone_pairs:[]}));
 if(music!=null){
  inputField(acoustics,'Музыка слышна (Battlefield Musician)',['scene','music_acoustics','audible_confirmed'],music.audible_confirmed);
  for(const [i,pair] of (music.blocked_zone_pairs||[]).entries()){
   const row=node('div',undefined,'talent-owner-row');
   for(let side=0;side<2;side++){const input=inputField(row,'Зона (Zone) '+(side+1),['scene','music_acoustics','blocked_zone_pairs',i,side],pair[side]);input.title='Относительный ID зоны: zone:0, zone:1 или air:0. Зона должна существовать в этой сцене.';}
   const remove=actionButton('remove','Удалить акустическую преграду',true);remove.onclick=()=>editRequest(['scene','music_acoustics','blocked_zone_pairs'],read().scene.music_acoustics.blocked_zone_pairs.filter((_,j)=>j!==i));row.append(remove);acoustics.append(row);
  }
  const add=actionButton('add','Добавить акустическую преграду');add.onclick=()=>editRequest(['scene','music_acoustics','blocked_zone_pairs'],[...(read().scene.music_acoustics.blocked_zone_pairs||[]),['zone:0','zone:1']]);acoustics.append(add);
 }
 acoustics.append(node('p','Явное решение ведущего (GM) о слышимости по сцене; указанные пары Зон (Zones) исключаются. Средняя дистанция (Medium Range) ограничивает вдохновение, а слышимость сигналов задаётся отдельно от дальности.','visual-note'));sceneGrid.append(acoustics);
 renderSurgeryRiskPolicy(sceneGrid,data.scene||{});
 scene.append(sceneGrid);scene.append(node('p','Начало новой сессии: персонажи здоровы, Судьба (Fate) и талант Удачливый (Lucky) доступны полностью. Решения и расход ресурсов рассчитываются в каждом бою.','visual-note'));root.append(scene);
 const advanced=node('details',undefined,'visual-card');advanced.open=!!data.search_space;advanced.append(node('summary','Ограничения генерации NPC — необязательно'));
 const automatic=node('label','Автоматические диапазоны по партии','toggle-field automatic-npc-toggle'),automaticInput=node('input');automaticInput.type='checkbox';automaticInput.checked=!data.search_space;automaticInput.dataset.path='automatic-npc-space';
 automaticInput.onchange=()=>editRequest(['search_space'],automaticInput.checked?null:planningSearchSpace({...read(),search_space:null}));automatic.prepend(automaticInput);advanced.append(automatic);
 if(!data.search_space){advanced.append(node('p','Генератор сам задаёт диапазоны характеристик и навыков вокруг партии. Составы проверяются по вашим целям боя.','visual-note'));root.append(advanced);return;}
 const space=card('Возможные параметры противников');space.append(node('p','Разрешённые значения через запятую. Генератор выбирает из них новые сочетания.','visual-note'));
 const grid=node('div',undefined,'visual-fields');
 const musicAllowed=(data.search_space?.allowed_talents||[]).includes('battlefield_musician');
 const medicalAllowed=!!data.search_space?.allowed_medical_sources?.length;
 const rangeDefaults={...(medicalAllowed?{reason:[3,4,5],recall:[3,4,5],initiative:[2,3,4],dexterity:[3,4,5]}:{}),...(musicAllowed?{fellowship:[2,3,4],leadership:[3,4,5]}:{}),...((data.search_space?.allowed_talents||[]).includes('careful_aim')?{reason:[3,4,5]}:{})};
 for(const key of ['weapon_skill','ballistic_skill','strength','toughness','initiative','agility','reason','fellowship','melee','defence','shooting','throwing','brawn','dexterity','recall','awareness','athletics','endurance','leadership','weapon_count'])if(Array.isArray(data.search_space?.[key]||rangeDefaults[key])){
  const label=node('label',key==='weapon_count'?'Количество оружия (Weapons)':statLabels[key]),input=node('input');label.title=key==='weapon_count'?'Допустимое число отдельных предметов у каждого противника; 0 — безоружный бой (Unarmed)':statFullNames[key]||statLabels[key];input.title=label.title;input.type='text';input.dataset.path='search_space/'+key;
  input.value=(data.search_space[key]||rangeDefaults[key]).join(', ');
  input.addEventListener('change',()=>{try{const values=input.value.trim().split(/[,;\s]+/).map(integer);if(new Set(values).size!==values.length)throw Error('Значения не должны повторяться.');editRequest(['search_space',key],values);}catch(error){visualEditError=error.message;message(error.message,'error');}});label.append(input);grid.append(label);
 }
 space.append(grid);
 const choices=node('div',undefined,'visual-fields');
 const bodyChoices=Object.fromEntries(bodyArmourIds.map(key=>[key,armourNames[key]]));
 const choiceDefaults={injury_policy:['minion'],secondary_armour:[null],helmet:[null],barding:[false],initial_loaded:[true],weapon_grip:['1h','2h'],mount:[null],rider_kind:['human','elf','other'],musician_instrument_hands:[1,2]};
 const choiceTitles={injury_policy:'Тип ранений NPC (NPC Wounds)',weapon:'Оружие (Weapons)',armour:'Броня (Armour)',secondary_armour:'Дополнительный комплект (Layered Armour)',helmet:'Шлем (Helmet)',shield:'Щит (Shield)',barding:'Конская броня (Barding)',initial_loaded:'Начальный заряд (Loaded)',weapon_grip:'Хват копья / древкового оружия (Grip)',mount:'Ездовое животное (Mount)',rider_kind:'Происхождение всадника (Rider)',musician_instrument_hands:'Хват инструментов (Musician’s Gear)'};
 for(const [key,options] of [['injury_policy',{minion:'Миньон (Minion)',champion:'Чемпион (Champion)'}],['weapon',Object.fromEntries(generatedWeaponIds.map(key=>[key,generatedWeaponNames[key]]))],['armour',{none:'Без брони',...bodyChoices}],['secondary_armour',{none:'Без второго комплекта',...bodyChoices}],['helmet',{none:'Без шлема',helmet:armourNames.helmet,helm_of_the_hunt:armourNames.helm_of_the_hunt}],['shield',{none:'Без щита',shield:armourNames.shield,briarroot_shield:armourNames.briarroot_shield}],['barding',{'false':'Без конской брони','true':armourNames.barding}],['initial_loaded',{'false':'Не заряжено (Unloaded)','true':'Заряжено (Loaded)'}],['weapon_grip',{'1h':'Одна рука (1H)','2h':'Две руки (2H)'}],['mount',combatMountNames],['rider_kind',{human:riderKindNames.human,elf:riderKindNames.elf,other:riderKindNames.other}],['musician_instrument_hands',{'1':'Одна рука (1H)','2':'Две руки (2H)'}]]){
  if(key==='musician_instrument_hands'&&!musicAllowed&&!Array.isArray(data.search_space?.[key]))continue;
  const group=node('div');group.append(node('h4',choiceTitles[key]));
  for(const [raw,name] of Object.entries(options)){
   const value=key==='musician_instrument_hands'?Number(raw):['barding','initial_loaded'].includes(key)?raw==='true':raw==='none'?null:raw,label=node('label',name,'toggle-field'),input=node('input');input.type='checkbox';input.checked=(data.search_space?.[key]||choiceDefaults[key]||[]).includes(value);input.dataset.path='search_space/'+key+'/'+raw;if(armourHints[raw])label.title=armourHints[raw];
   input.addEventListener('change',()=>{const current=read().search_space,values=[...(current[key]||choiceDefaults[key]||[])];current[key]=input.checked?[...values,value]:values.filter(v=>v!==value);if(['armour','secondary_armour'].includes(key)&&!['armour','secondary_armour'].some(axis=>(current[axis]||[]).includes('armour_of_agilulf')))current.agilulf_code_confirmed=null;if(key==='weapon'&&!current.weapon.includes('ogre_pistol'))current.ogre_fit_confirmed=null;editRequest(['search_space'],current);});label.prepend(input);group.append(label);
  }choices.append(group);
 }
 if(['armour','secondary_armour'].some(key=>(data.search_space?.[key]||[]).includes('armour_of_agilulf')))inputField(choices,'GM подтвердил рыцарский кодекс для Доспеха Агилульфа (Armour of Agilulf)',['search_space','agilulf_code_confirmed'],data.search_space.agilulf_code_confirmed===true,null,value=>editRequest(['search_space','agilulf_code_confirmed'],value?true:null));
 if((data.search_space?.weapon||[]).includes('ogre_pistol'))inputField(choices,'GM подтвердил пригодность Огрского пистолета (Ogre Pistol)',['search_space','ogre_fit_confirmed'],data.search_space.ogre_fit_confirmed===true,null,value=>editRequest(['search_space','ogre_fit_confirmed'],value?true:null));
 if((data.search_space?.weapon||[]).includes('scarab_knife')){const label=node('label','Начальные заряды Ножа скарабея (Scarab Knife)'),input=node('input');input.type='text';input.dataset.path='search_space/scarab_initial_charges';input.value=(data.search_space.scarab_initial_charges||[0]).join(', ');input.onchange=()=>{try{const values=input.value.trim().split(/[,;\s]+/).map(integer);if(values.some(v=>v<0)||new Set(values).size!==values.length)throw Error('Заряды должны быть различными неотрицательными целыми числами.');editRequest(['search_space','scarab_initial_charges'],values);}catch(error){message(error.message,'error');}};label.append(input);choices.append(label);}
 const ability=node('div');ability.append(node('h4','Способности (Abilities)'));
 const select=node('select');select.setAttribute('aria-label','Допустимые способности NPC');select.dataset.path='search_space/abilities';
 const abilityOptions=[['Без способностей',[[]]],['Без способностей или Истощение (Drained) при попадании',[[],['drained_on_hit']]],['Только Истощение (Drained) при попадании',[['drained_on_hit']]]];
 const current=JSON.stringify(data.search_space?.abilities);for(const [name,value] of abilityOptions){const option=node('option',name);option.value=JSON.stringify(value);select.append(option);}
 if(!abilityOptions.some(([,value])=>JSON.stringify(value)===current)){const option=node('option','Пользовательский набор · см. JSON');option.value=current||'[]';select.append(option);}select.value=current;
 select.onchange=()=>editRequest(['search_space','abilities'],JSON.parse(select.value));ability.append(select);choices.append(ability);
 const talents=node('div');talents.append(node('h4','Разрешённые таланты (Talents)'));
 for(const value of generatedExecutableTalentIds){
  const label=node('label',talentLabel(value),'toggle-field'),input=node('input');input.type='checkbox';input.checked=(data.search_space?.allowed_talents||[]).includes(value);input.dataset.path='search_space/allowed_talents/'+value;label.title=talentHint(value);
  input.onchange=()=>{const source=read().search_space,values=source.allowed_talents,next=input.checked?[...values,value]:values.filter(t=>t!==value),fact={allies_in_arms:'fellowship',careful_aim:'reason'}[value];if(input.checked&&fact&&!Array.isArray(source[fact]))editRequest(['search_space'],{...source,allowed_talents:next,[fact]:planningSearchSpace({...read(),search_space:null})[fact]});else editRequest(['search_space','allowed_talents'],next);};label.prepend(input);talents.append(label);
 }
 talents.append(node('p','Генератор выбирает допустимые сочетания с учётом требований. Снимите все флажки для составов без талантов.','visual-note'));choices.append(talents);renderGeneratedOathSources(choices,data.search_space||{});renderGeneratedMedicalSources(choices,data.search_space||{});space.append(choices);advanced.append(space);root.append(advanced);

}
function setRequestView(view){
 hideTagTooltip();
 const previous=requestView;
 if(view==='visual'){try{syncForm();const data=read();requestView=view;renderRequestVisual(data);}catch(error){requestView=previous;message('Сначала исправьте JSON: '+error.message,'error');return;}}
 else{requestView=view;visualEditError=null;}
 byId('request').classList.toggle('hidden',view!=='json');byId('visual-request-controls').classList.toggle('hidden',view!=='visual');
 for(const mode of ['visual','json'])byId('request-'+mode+'-tab').setAttribute('aria-pressed',String(mode===view));
 updateFileActions();
}
function setResultView(view){hideTagTooltip();resultView=view;byId('result').classList.toggle('hidden',view!=='json');byId('result-visual').classList.toggle('hidden',view!=='visual');for(const mode of ['visual','json'])byId('result-'+mode+'-tab').setAttribute('aria-pressed',String(mode===view));updateFileActions();}
function updateFileActions(){
 updateResultHeadingVisibility();
 byId('format').classList.toggle('hidden',requestView!=='json');
 byId('format-result').classList.toggle('hidden',resultView!=='json');byId('format-result').disabled=busy||!lastResult;
 byId('load-result').disabled=busy;byId('result-file').disabled=busy;
 byId('download').disabled=busy||!lastResult;
 for(const control of document.querySelectorAll('[data-character-control]'))control.disabled=busy;
}
function updateResultHeadingVisibility(){
 const slot=byId('result-card-heading'),invisible=resultView!=='visual';slot.classList.toggle('hidden',!slot.hasChildNodes());slot.classList.toggle('heading-spacer',invisible);slot.setAttribute('aria-hidden',String(invisible));slot.inert=invisible;
}
function syncResultCardHeading(){
 const slot=byId('result-card-heading');slot.replaceChildren();const heading=byId('result-visual').querySelector(':scope>.result-card>.result-heading');if(heading)slot.append(heading);updateResultHeadingVisibility();
}
function resultIconButton(action,title,path){
 const button=node('button',undefined,'icon-button');button.type='button';button.title=title;button.setAttribute('aria-label',title);button.dataset.action=action;
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),shape=document.createElementNS('http://www.w3.org/2000/svg','path');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');shape.setAttribute('d',path);svg.append(shape);button.append(svg);return button;
}
function npcStatTable(title,keys,npc){
 const table=node('table',undefined,'npc-stat-table');table.append(node('caption',title));const columns=node('colgroup');for(let i=0;i<2;i++)columns.append(node('col'),node('col',undefined,'stat-value'));table.append(columns);const body=node('tbody');
 for(let i=0;i<keys.length;i+=2){const row=node('tr');for(const key of keys.slice(i,i+2)){const label=node('th',statLabels[key]),value=node('td',npc[key]??'—');label.id=tableStatId();value.setAttribute('headers',label.id);label.title=statFullNames[key];value.dataset.stat=key;value.classList.toggle('unavailable',npc[key]==null);if(npc[key]==null)value.title='Значение пока не задано';row.append(label,value);}body.append(row);}table.append(body);return table;
}
let statCellSequence=0;
function tableStatId(){return 'npc-stat-'+(++statCellSequence);}
function resultItemTags(items,emptyHint){
 const tags=node('div',undefined,'item-tags');for(const [label,hint] of items.length?items:[['—',emptyHint]]){const tag=node('span',label,'item-tag'+(items.length?'':' empty'));attachTagTooltip(tag,hint);tags.append(tag);}return tags;
}
function validateTargetMetadata(result){
 const fail=()=>{throw Error('JSON результата должен содержать согласованную оценку совместных целей текущего формата.');};
 const exactKeys=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===keys.slice().sort().join(',');
 const criteria=result.target_criteria;
 if(!exactKeys(criteria,['basis','win_rate_tolerance','started_rounds_tolerance'])||criteria.basis!=='point_estimates'||criteria.win_rate_tolerance!==.1||criteria.started_rounds_tolerance!==1||typeof result.target_match_found!=='boolean')fail();
 const fraction=value=>value&&typeof value.numerator==='number'&&Number.isFinite(value.numerator)&&typeof value.denominator==='number'&&Number.isFinite(value.denominator)&&value.denominator>0?value.numerator/value.denominator:NaN;
 const targets=result.source_request?.targets,winTarget=fraction(targets?.win_rate),roundTarget=fraction(targets?.started_rounds);
 if(!Number.isFinite(winTarget)||winTarget<0||winTarget>1||!Number.isFinite(roundTarget)||roundTarget<1||!Number.isSafeInteger(result.source_request.max_rounds)||result.source_request.max_rounds<1||roundTarget>result.source_request.max_rounds||!Array.isArray(result.explored)||!Array.isArray(result.validations)||!Array.isArray(result.selected))fail();
 const same=(left,right)=>Math.abs(left-right)<=1e-10*Math.max(1,Math.abs(left),Math.abs(right));
 const normalized=value=>Math.abs(value-1)<=1e-12?1:Math.round(value*1e12)/1e12;
 for(const candidate of [...result.explored,...result.validations]){
  const assessment=candidate?.target_assessment;
  if(!exactKeys(assessment,['status','win_rate_in_range','started_rounds_in_range','win_rate_deviation','started_rounds_deviation','normalized_max_deviation','normalized_total_deviation'])||typeof assessment.win_rate_in_range!=='boolean'||typeof assessment.started_rounds_in_range!=='boolean'||!Number.isFinite(candidate.win_rate)||candidate.win_rate<0||candidate.win_rate>1||!Number.isFinite(candidate.mean_started_rounds)||candidate.mean_started_rounds<1||candidate.mean_started_rounds>result.source_request.max_rounds||!Number.isSafeInteger(candidate.trials)||candidate.trials<1||!candidate.outcomes||['objective_achieved','party_defeated','round_limit','unsupported_path'].some(key=>!Number.isSafeInteger(candidate.outcomes[key])||candidate.outcomes[key]<0)||!same(candidate.win_rate,candidate.outcomes.objective_achieved/candidate.trials)||['objective_achieved','party_defeated','round_limit','unsupported_path'].reduce((sum,key)=>sum+candidate.outcomes[key],0)!==candidate.trials)fail();
  for(const key of ['win_rate_deviation','started_rounds_deviation','normalized_max_deviation','normalized_total_deviation'])if(typeof assessment[key]!=='number'||!Number.isFinite(assessment[key])||assessment[key]<0)fail();
  const winDeviation=Math.abs(candidate.win_rate-winTarget),roundDeviation=Math.abs(candidate.mean_started_rounds-roundTarget);
  const winNormalized=normalized(winDeviation/criteria.win_rate_tolerance),roundNormalized=normalized(roundDeviation/criteria.started_rounds_tolerance);
  const winInRange=winNormalized<=1,roundInRange=roundNormalized<=1,status=candidate.outcomes.unsupported_path?'unsupported':winInRange&&roundInRange?'within_targets':'outside_targets';
  if(assessment.status!==status||assessment.win_rate_in_range!==winInRange||assessment.started_rounds_in_range!==roundInRange||!same(assessment.win_rate_deviation,winDeviation)||!same(assessment.started_rounds_deviation,roundDeviation)||!same(assessment.normalized_max_deviation,Math.max(winNormalized,roundNormalized))||!same(assessment.normalized_total_deviation,winNormalized+roundNormalized))fail();
 }
 const supported=result.validations.filter(candidate=>candidate.target_assessment.status!=='unsupported').map(candidate=>candidate.replay?.scenario?.id);
 if(result.target_match_found!==result.validations.some(candidate=>candidate.target_assessment.status==='within_targets')||supported.some(id=>typeof id!=='string')||JSON.stringify(result.selected)!==JSON.stringify(supported))fail();
 const score=candidate=>[Number(candidate.target_assessment.status==='unsupported'),candidate.target_assessment.normalized_max_deviation,candidate.target_assessment.normalized_total_deviation];
 for(let index=1;index<result.validations.length;index++){
  const previous=score(result.validations[index-1]),next=score(result.validations[index]);
  for(let axis=0;axis<previous.length;axis++){if(previous[axis]<next[axis])break;if(previous[axis]>next[axis])fail();}
 }
}
function targetAssessmentBadge(candidate,validated){
 const status=candidate.target_assessment.status;
 const label=status==='unsupported'?'Неподдержанные исходы':status==='within_targets'?(validated?'Обе цели в допуске · по выборке':'Предварительно обе цели в допуске'):(validated?'Лучший найденный · вне допусков':'Предварительно вне допусков');
 const badge=node('span',label,'badge'+(status==='outside_targets'?' outside-badge':status==='unsupported'?' unsupported-badge':''));badge.dataset.targetStatus=status;
 attachTagTooltip(badge,'Совместные допуски: победы ±10 п.п. и средняя длительность ±1 раунд. Сравниваются точечные оценки выборки; это не подтверждение попадания всего доверительного интервала в допуски.');
 return badge;
}
function renderResultVisual(result,root=byId('result-visual')){
 hideTagTooltip();
 if(root===byId('result-visual')){byId('result-card-heading').replaceChildren();byId('result-card-heading').classList.add('hidden');}
 root.replaceChildren();
 if(!result){root.append(node('p','Результат появится после расчёта.','visual-empty'));return;}
 if(result.error){root.append(node('p',[result.error.path,result.error.message].filter(Boolean).join(': '),'visual-note'));return;}
 validateTargetMetadata(result);
 const percent=n=>Number.isFinite(n)?(n*100).toFixed(1)+'%':'—';
 function candidateView(candidate,number,validated=false){
  const id=candidate.replay?.scenario?.id,box=node('section',undefined,'result-card'),npcs=draftNpcs(candidate,result),dirty=npcs!==candidate.npcs;box.dataset.candidateId=id;
  const heading=node('div',undefined,'result-heading'),actions=node('div',undefined,'file-actions');actions.setAttribute('role','group');actions.setAttribute('aria-label','Действия с составом '+number);heading.append(node('h3','Состав '+number),actions);box.append(heading);
  if(dirty){const reset=resultIconButton('reset-npc-draft','Сбросить черновик состава','M3 11a9 9 0 1 1 2 7M3 4v7h7');reset.dataset.characterControl='';reset.disabled=busy;reset.onclick=()=>resetNpcDraft(candidate);actions.append(reset);}
  const replay=resultIconButton('download-replay','Скачать бой','M12 4v12m-5-5 5 5 5-5M4 15v5h16v-5');replay.disabled=dirty;if(dirty)replay.title='Бой черновика пока не пересчитывается; сбросьте изменения для скачивания исходного боя.';replay.onclick=()=>{if(!dirty)download(pretty(candidate.replay),'encounter-replay.json');};actions.append(replay);
  const statistics=card(dirty?'Статистика исходного состава':'Статистика');statistics.classList.add('result-statistics');
  if(dirty)statistics.append(node('span','Черновик · оценки неактуальны','badge draft-badge'));
  else statistics.append(targetAssessmentBadge(candidate,validated));
  const metrics=node('div',undefined,'result-metrics');for(const [title,value] of [['Победы игроков',percent(candidate.win_rate)],['Средние раунды',Number(candidate.mean_started_rounds).toFixed(2)],['Симуляций',candidate.trials]]){const item=node('div',title);item.append(node('strong',value));metrics.append(item);}statistics.append(metrics);
  if(candidate.win_interval_95)statistics.append(node('p','Интервал оценки побед (95%): '+candidate.win_interval_95.map(percent).join(' — '),'visual-note'));
  const assessment=candidate.target_assessment;
  const targetNote=node('p',(dirty?'Исходные оценки':assessment.status==='unsupported'?'Оценки с неподдержанными исходами':'По оценкам выборки')+': победы '+(assessment.win_rate_in_range?'в допуске':'вне допуска')+' ±10 п.п. · раунды '+(assessment.started_rounds_in_range?'в допуске':'вне допуска')+' ±1.','visual-note target-assessment-note');
  targetNote.dataset.targetBasis=result.target_criteria.basis;statistics.append(targetNote);
  if(candidate.potion_use_counts)statistics.append(node('p','Использовано зелий (Potions), в среднем за бой: '+(candidate.potion_use_counts.reduce((sum,item)=>sum+item.count,0)/candidate.trials).toFixed(2),'visual-note'));
  if(candidate.magic_counts){const mean=key=>(candidate.magic_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Магия (Magic), в среднем за бой: сотворения (Casting) '+mean('casting_actions')+' · заклинания (Spells) '+mean('spell_casts')+' · ошибки (Miscasts) '+mean('miscasts')+' · неподдержанные Miscasts '+mean('unsupported_miscasts'),'visual-note'));}
  if(candidate.pc_ranged_counts){const mean=key=>(candidate.pc_ranged_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Игроки: выстрелы (Shots) '+mean('shots')+' · Помощь стрелку (Shooting Help) '+mean('shooting_help_tests')+' · Перезарядка (Reload) '+mean('reload_actions')+' · Смена оружия (Weapon Swap) '+mean('weapon_swaps')+' — в среднем за бой','visual-note'));}
  if(candidate.npc_ranged_counts){const mean=key=>(candidate.npc_ranged_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Стрельба NPC (Shooting), в среднем за бой: выстрелы '+mean('shots')+' · залпы '+mean('bonus_shots')+' · действия перезарядки (Reload) '+mean('reload_actions'),'visual-note'));}
  if(candidate.npc_ally_counts?.length)statistics.append(node('p','Союзные NPC, в среднем за бой: '+candidate.npc_ally_counts.map(row=>row.actor_id+' — действий '+(row.actions/candidate.trials).toFixed(2)+', атак '+(row.attacks/candidate.trials).toFixed(2)+', восстановлений (Recover) '+(row.recover_actions/candidate.trials).toFixed(2)).join(' · '),'visual-note'));
  const outcomes=candidate.outcomes||{};statistics.append(node('p','Победы: '+outcomes.objective_achieved+' · Поражения: '+outcomes.party_defeated+' · Лимит раундов: '+outcomes.round_limit+' · Неподдержанные ситуации: '+outcomes.unsupported_path,'visual-note'));box.append(statistics);
  for(const [index,npc] of (npcs||[]).entries()){
   const creature=card('Противник '+(index+1));creature.classList.add('npc-card');creature.querySelector('h3').classList.add('npc-heading');creature.querySelector('h3').append(npcFileControls(candidate,index,result));const tables=node('div',undefined,'npc-stat-tables');tables.append(npcStatTable('Характеристики (Characteristics)',Object.keys(characteristicTerms),{...(npc.talent_facts||{}),...npc,...(npc.ranged||{})}),npcStatTable('Навыки (Skills)',Object.keys(skillTerms),{...(npc.talent_facts||{}),...npc,...(npc.ranged||{})}));creature.append(tables);
   const loadout=node('dl',undefined,'npc-loadout');
   const weaponTags=(npc.weapons||[]).map(item=>{const weapon=generatedWeaponNames[item.weapon]||item.weapon;
   const weaponHint=twoHandedWeaponHints[item.weapon]||{pistol:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)5, игнорирует броню; Перезарядка (Reload)3 успеха.',repeater_pistol:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)5, игнорирует броню. Возможный залп +2d открывает Перезарядку (Reload)3 успеха; режим выбирается автоматически.',repeater_handbow:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)4. Возможный залп +1d открывает Перезарядку (Reload)3 успеха; режим выбирается автоматически.',knuckledusters:'Одноручное (1H), атака Грубой силой (Brawn); Damage = Strength − 1. Не даёт Защиту (Defence). +1d к Скрытности (Stealth) для сокрытия.',cavalry_spear:'Одноручное (1H), дальность Close–Short; Damage = Strength. +1d к Ближнему бою (Melee) при верховом Натиске (Charge).',lance:'Одноручное (1H), Close Range; Damage = Strength + 1. Верховой Натиск (Charge) даёт +1d к Melee и +1 Damage; нельзя применять Dual Wield.',dagger:'Одноручное, Close Range; Damage = Strength − 1. +1d к Stealth для сокрытия.',staff:'Одноручное, Close Range; Damage = Strength. +1d к Athletics при пересечении Difficult Terrain.',axe:'Одноручное, Close Range; Damage = Strength. +1 Damage против бронированной (armoured) цели.',sword:'Одноручное, Close Range; Damage = Strength. +1d к Защите (Defence), пока владелец не Ошеломлён (Staggered).',warhammer:'Одноручное, Close Range; Damage = Strength. +1d к Ближнему бою (Melee) против Ошеломлённой (Staggered) цели.',morning_star:'Одноручное, Close Range; Damage = Strength + 1. −1d к Ближнему бою (Melee), пока владелец Ошеломлён (Staggered); нельзя применять dual wield.',pickaxe:'Двуручное (2H), Close Range; Damage = Strength + 1. +1d к Труду (Toil) при добыче ресурсов.',flail:'Двуручное (2H), Close Range; Damage = Strength + 3. −2d к Ближнему бою (Melee) при Staggered.',billhook:'Двуручное (2H), Close Range; Damage = Strength + 2. +1d к Ближнему бою (Melee) против верховой цели (mounted enemy).',halberd:'Двуручное (2H), Close Range; Damage = Strength + 2. +1 Damage против бронированной (armoured) цели.',glaive:'Двуручное (2H), Close Range; Damage = Strength + 2. +1d к Защите (Defence) при отсутствии Staggered.',greataxe:'Двуручное (2H), Close Range; Damage = Strength + 3. −1d к Ближнему бою (Melee); +1 Damage против бронированной (armoured) цели.',greatsword:'Двуручное (2H), Close Range; Damage = Strength + 3. −1d к Ближнему бою (Melee); +1d к Защите (Defence) при отсутствии Staggered.',greathammer:'Двуручное (2H), Close Range; Damage = Strength + 3. −1d к Ближнему бою (Melee); +1d против Staggered enemy.'}[item.weapon]||weapon;const pose=item.location==='carried'?'При себе (Carried)':item.hand==='both'?'В обеих руках (Both Hands)':item.hand==='right'?'В правой руке (Right Hand)':'В левой руке (Left Hand)';return [weapon+(item.quantity>1?' × '+item.quantity:''),weaponHint+' '+pose+'.'+(typeof item.initially_loaded==='boolean'?(item.initially_loaded?' Заряжено (Loaded).':' Не заряжено (Unloaded).'):'')];});
   if(!(npc.weapons||[]).some(item=>item.location==='held')&&Number.isInteger(npc.brawn))weaponTags.unshift(['Безоружный бой (Unarmed)','Режим атаки Грубой силой (Brawn), не предмет. Успех накладывает Ошеломлён (Staggered); отдельного Damage нет.']);
   const armourTags=[],protection=npc.armour;
   for(const kind of protection?.body||[])armourTags.push([armourNames[kind]||kind,(armourHints[kind]||kind)+(protection.benefit!==kind?' Преимущества этого комплекта не выбраны; его штрафы сохраняются.':'')]);
   for(const kind of [protection?.helmet,protection?.shield,protection?.barding?'barding':null])if(kind)armourTags.push([armourNames[kind]||kind,armourHints[kind]||kind]);
   const toolTags=(npc.tools||[]).map(item=>[item.instrument_name||'Инструменты музыканта (Musician’s Gear)',item.hands_required+' рук · '+(heldLocations[item.location]||item.location)]);
   const groups=[['Оружие (Weapons)',weaponTags,'Оружие не задано'],['Инструменты (Trade Tools)',toolTags,'Инструменты не заданы'],['Броня (Armour)',armourTags,'Броня не надета'],['Расходники (Consumables)',[],'Генератор пока не выдаёт расходники'],['Таланты (Talents)',(npc.talents||[]).map(t=>[talentLabel(t.id),talentHint(t.id)+(['honour_bound','blessings_of_the_lady'].includes(t.id)&&npc.oath_context?' '+oathContextHint(npc.oath_context):'')]),'Таланты не выбраны']];
   if(npc.mount)groups.push(['Ездовое животное (Mount)',[[combatMountNames[npc.mount]||npc.mount,'Собственный источник эффектов маунта; броня всадника и Конская броня (Barding) учитываются отдельно. При спешивании маунт покидает поле.']],'Пешком']);
   if((npc.abilities||[]).length)groups.push(['Способности (Abilities)',npc.abilities.map(a=>[a==='drained_on_hit'?'Истощение при попадании (Drained)':a,a==='drained_on_hit'?'При попадании цель получает Истощение (Drained). Отдельно разрешённая способность, не книжный талант.':a]),'Способности не заданы']);
   for(const [title,items,emptyHint] of groups){const values=node('dd');values.append(resultItemTags(items,emptyHint));loadout.append(node('dt',title),values);}creature.append(loadout);box.append(creature);
  }
  return box;
 }
 const finals=result.validations||[];
 if(!finals.length)root.append(node('p','В этом запуске нет проверенных финалистов. См. исследованные составы ниже.','visual-note'));
 finals.forEach((candidate,index)=>root.append(candidateView(candidate,index+1,true)));
 const explored=node('details',undefined,'visual-card');explored.append(node('summary','Исследованные составы'));(result.explored||[]).forEach((candidate,index)=>explored.append(candidateView(candidate,index+1)));root.append(explored);
 if(root===byId('result-visual'))syncResultCardHeading();
}
for(const mode of ['visual','json']){byId('request-'+mode+'-tab').onclick=()=>setRequestView(mode);byId('result-'+mode+'-tab').onclick=()=>setResultView(mode);}
renderResultVisual(null);
'''

from towr.adapters._local_ui_inventory import INVENTORY_STYLE, INVENTORY_SCRIPT

VISUAL_STYLE += INVENTORY_STYLE
VISUAL_SCRIPT += INVENTORY_SCRIPT
