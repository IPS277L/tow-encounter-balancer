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
.stale-notice{padding:10px 12px;background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:5px;color:var(--warning-text);font-size:13px;margin:12px 0}
.result-metrics{display:flex;flex-wrap:wrap;gap:10px 22px;margin:10px 0;font-size:13px}.result-metrics strong{display:block;font-size:19px;color:var(--text)}
.badge{display:inline-block;padding:3px 7px;border-radius:4px;background:var(--success-bg);color:var(--success-text);font-size:12px}
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
const generatedTalentNames={magic_resistance:'Сопротивление магии (Magic Resistance)',defensive_stance:'Оборонительная стойка (Defensive Stance)',wild_attack:'Дикая атака (Wild Attack)'};
const generatedTalentHints={magic_resistance:'Сила (Potency) затрагивающего заклинания уменьшается на 1; при 0 эффекта нет. Требований нет.',defensive_stance:'Боевое мастерство (WS) 3+. При успешной Защите (Defence) NPC снимает собственный Staggered, отказавшись от доступного нового Staggered атакующему.',wild_attack:'Сила (S) 4+. Перед проверкой Ближнего боя (Melee) NPC получает Staggered и делает её Glorious. Не применяется к Стрельбе (Shooting), при Staggered или Drained.'};
const weaponNames={staff:'Посох (Staff)',sword:'Меч (Sword)',dagger:'Кинжал (Dagger)',axe:'Топор (Axe)',warhammer:'Боевой молот (Warhammer)',
 morning_star:'Моргенштерн (Morning Star)',pickaxe:'Клевец (Pickaxe)',flail:'Цеп (Flail)',billhook:'Гвизарма (Billhook)',halberd:'Алебарда (Halberd)',glaive:'Глефа (Glaive)',greataxe:'Двуручный топор (Greataxe)',greathammer:'Двуручный молот (Greathammer)'};
const generatedWeaponNames={...weaponNames,pistol:'Пистолет (Pistol)',repeater_pistol:'Многозарядный пистолет (Repeater Pistol)',repeater_handbow:'Многозарядный ручной арбалет (Repeater Handbow)'};
const playerWeaponNames={...generatedWeaponNames},pcCloseRangedWeapons=new Set(['pistol','repeater_pistol','repeater_handbow']);
function playerInitialRangedWeapon(member){const active=(member.equipment?.weapons||[]).filter(item=>item.location!=='carried');return active.length===1&&pcCloseRangedWeapons.has(active[0].weapon)?active[0]:null;}
function node(tag,text,classes){const element=document.createElement(tag);if(text!==undefined)element.textContent=String(text);if(classes)element.className=classes;return element;}
function card(title){const element=node('section',undefined,'visual-card');element.append(node('h3',title));return element;}
function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
function markResultStale(){
 let stale=false;if(lastResult){try{stale=canonical(read())!==canonical(lastResult.source_request);}catch(_){stale=true;}}
 byId('result-stale').classList.toggle('hidden',!stale);
}
function editRequest(path,value){
 if(busy)return;
 try{const data=read();put(data,path,value);byId('request').value=pretty(data);syncForm();message('Запрос изменён. Новый расчёт — по кнопке «Запустить генератор».');}
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
 const values=member[section]||{},terms=section==='characteristics'?characteristicTerms:skillTerms,supported=section==='characteristics'?['weapon_skill','strength','toughness','agility']:['melee','defence','endurance','athletics'];
 if(member.magic && (member.talents||[]).includes('wizard'))supported.push(section==='characteristics'?'reason':'willpower');
 const rangedStat=(section==='characteristics'?['ballistic_skill','initiative']:['shooting','dexterity']).includes(key);
 if(playerInitialRangedWeapon(member))supported.push(...(section==='characteristics'?['ballistic_skill','initiative']:['shooting','dexterity']));
 if(Object.hasOwn(terms,key)&&!supported.includes(key)){
  const label=node('label',statLabels[key]),input=node('input');input.type='text';input.value=values[key]??'—';input.disabled=true;input.className='stat-placeholder';input.dataset.stat=key;input.title=statFullNames[key]+(rangedStat?' · Не используется с начальным оружием; сохранённое значение остаётся в персонаже':' · Пока не подключено к симуляции');input.setAttribute('aria-label',input.title);label.append(input);parent.append(label);
 }else if(rangedStat){const path=['party',index,section,key],input=inputField(parent,statLabels[key],path,values[key]??'',null,raw=>editRequest(path,integer(raw)));input.type='number';input.step='1';input.min='1';if(section==='skills')input.max='10';input.required=true;input.placeholder='Обязательно';}
 else inputField(parent,statLabels[key]||key,['party',index,section,key],values[key]);
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
  const data=read(),members=data.party||[];let id='pc:'+(members.length+1),suffix=members.length+1;while(members.some(m=>m.actor_id===id))id='pc:'+(++suffix);
  const member=JSON.parse(JSON.stringify(members[0]||{characteristics:{weapon_skill:3,strength:3,toughness:3,agility:3},skills:{melee:4,defence:4,athletics:4,endurance:4},equipment:{weapons:[{id:'weapon:1',weapon:'staff',location:'right_hand'}],armour:[]},consumables:[],talents:[],resources:{fate:2}}));member.actor_id=id;editRequest(['party'],[...members,member]);
 };const playerActions=node('div',undefined,'player-actions');playerActions.append(add,addPlayerFileControls());root.append(playerActions);
 const scene=card('Сцена'),sceneGrid=node('div',undefined,'visual-fields');
 for(const [key,title,choices] of [['range','Начальная дистанция',{close:'Ближняя дистанция (Close Range)'}],['ambush','Засада (Ambush)',{none:'Нет — засады пока не поддержаны'}],['terrain','Местность (Terrain)',{open:'Открытая, без модификаторов'}]])inputField(sceneGrid,title,['scene',key],data.scene?.[key],choices);
 scene.append(sceneGrid);scene.append(node('p','Начало новой сессии: персонажи здоровы, Судьба (Fate) и талант Удачливый (Lucky) доступны полностью. Решения и расход ресурсов рассчитываются в каждом бою.','visual-note'));root.append(scene);
 const advanced=node('details',undefined,'visual-card');advanced.open=!!data.search_space;advanced.append(node('summary','Ограничения генерации NPC — необязательно'));
 const automatic=node('label','Автоматические диапазоны по партии','toggle-field automatic-npc-toggle'),automaticInput=node('input');automaticInput.type='checkbox';automaticInput.checked=!data.search_space;automaticInput.dataset.path='automatic-npc-space';
 automaticInput.onchange=()=>editRequest(['search_space'],automaticInput.checked?null:planningSearchSpace({...read(),search_space:null}));automatic.prepend(automaticInput);advanced.append(automatic);
 if(!data.search_space){advanced.append(node('p','Генератор сам задаёт диапазоны характеристик и навыков вокруг партии. Составы проверяются по вашим целям боя.','visual-note'));root.append(advanced);return;}
 const space=card('Возможные параметры противников');space.append(node('p','Разрешённые значения через запятую. Генератор выбирает из них новые сочетания.','visual-note'));
 const grid=node('div',undefined,'visual-fields');
 for(const key of ['weapon_skill','ballistic_skill','strength','toughness','initiative','agility','melee','defence','shooting','dexterity','athletics'])if(Array.isArray(data.search_space?.[key])){
  const label=node('label',statLabels[key]),input=node('input');label.title=statFullNames[key]||statLabels[key];input.title=label.title;input.type='text';input.value=data.search_space[key].join(', ');input.dataset.path='search_space/'+key;
  input.addEventListener('change',()=>{try{const values=input.value.trim().split(/[,;\s]+/).map(integer);if(new Set(values).size!==values.length)throw Error('Значения не должны повторяться.');editRequest(['search_space',key],values);}catch(error){visualEditError=error.message;message(error.message,'error');}});label.append(input);grid.append(label);
 }
 space.append(grid);
 const choices=node('div',undefined,'visual-fields');
 for(const [key,options] of [['weapon',Object.fromEntries(['staff','dagger','axe','sword','warhammer','morning_star','pistol','repeater_pistol','repeater_handbow'].map(key=>[key,generatedWeaponNames[key]]))],['light_armour',{'false':'Без брони','true':'Лёгкая броня (Light Armour)'}],['shield',{'false':'Без щита','true':'Щит (Shield)'}]]){
  const group=node('div');group.append(node('h4',key==='weapon'?'Оружие (Weapons)':key==='shield'?'Щит (Shield)':'Броня (Armour)'));
  for(const [raw,name] of Object.entries(options)){
   const value=key==='light_armour'||key==='shield'?raw==='true':raw,label=node('label',name,'toggle-field'),input=node('input');input.type='checkbox';input.checked=(data.search_space?.[key]||[]).includes(value);input.dataset.path='search_space/'+key+'/'+raw;
   input.addEventListener('change',()=>{const values=[...(read().search_space?.[key]||[])];editRequest(['search_space',key],input.checked?[...values,value]:values.filter(v=>v!==value));});label.prepend(input);group.append(label);
  }choices.append(group);
 }
 const ability=node('div');ability.append(node('h4','Способности (Abilities)'));
 const select=node('select');select.setAttribute('aria-label','Допустимые способности NPC');select.dataset.path='search_space/abilities';
 const abilityOptions=[['Без способностей',[[]]],['Без способностей или Истощение (Drained) при попадании',[[],['drained_on_hit']]],['Только Истощение (Drained) при попадании',[['drained_on_hit']]]];
 const current=JSON.stringify(data.search_space?.abilities);for(const [name,value] of abilityOptions){const option=node('option',name);option.value=JSON.stringify(value);select.append(option);}
 if(!abilityOptions.some(([,value])=>JSON.stringify(value)===current)){const option=node('option','Пользовательский набор · см. JSON');option.value=current||'[]';select.append(option);}select.value=current;
 select.onchange=()=>editRequest(['search_space','abilities'],JSON.parse(select.value));ability.append(select);choices.append(ability);
 const talents=node('div');talents.append(node('h4','Разрешённые таланты (Talents)'));
 for(const [value,name] of Object.entries(generatedTalentNames)){
  const label=node('label',name,'toggle-field'),input=node('input');input.type='checkbox';input.checked=(data.search_space?.allowed_talents||[]).includes(value);input.dataset.path='search_space/allowed_talents/'+value;label.title=generatedTalentHints[value];
  input.onchange=()=>{const values=read().search_space.allowed_talents;editRequest(['search_space','allowed_talents'],input.checked?[...values,value]:values.filter(t=>t!==value));};label.prepend(input);talents.append(label);
 }
 talents.append(node('p','Генератор выбирает допустимые сочетания с учётом требований. Снимите все флажки для составов без талантов.','visual-note'));choices.append(talents);space.append(choices);advanced.append(space);root.append(advanced);

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
function renderResultVisual(result,root=byId('result-visual')){
 hideTagTooltip();
 if(root===byId('result-visual')){byId('result-card-heading').replaceChildren();byId('result-card-heading').classList.add('hidden');}
 root.replaceChildren();
 if(!result){root.append(node('p','Результат появится после расчёта.','visual-empty'));return;}
 if(result.error){root.append(node('p',[result.error.path,result.error.message].filter(Boolean).join(': '),'visual-note'));return;}
 const percent=n=>Number.isFinite(n)?(n*100).toFixed(1)+'%':'—';
 const selected=new Set(result.selected||[]);
 function candidateView(candidate,number){
  const id=candidate.replay?.scenario?.id,box=node('section',undefined,'result-card'),npcs=draftNpcs(candidate,result),dirty=npcs!==candidate.npcs;box.dataset.candidateId=id;
  const heading=node('div',undefined,'result-heading'),actions=node('div',undefined,'file-actions');actions.setAttribute('role','group');actions.setAttribute('aria-label','Действия с составом '+number);heading.append(node('h3','Состав '+number),actions);box.append(heading);
  if(dirty){const reset=resultIconButton('reset-npc-draft','Сбросить черновик состава','M3 11a9 9 0 1 1 2 7M3 4v7h7');reset.dataset.characterControl='';reset.disabled=busy;reset.onclick=()=>resetNpcDraft(candidate);actions.append(reset);}
  const replay=resultIconButton('download-replay','Скачать бой','M12 4v12m-5-5 5 5 5-5M4 15v5h16v-5');replay.disabled=dirty;if(dirty)replay.title='Бой черновика пока не пересчитывается; сбросьте изменения для скачивания исходного боя.';replay.onclick=()=>{if(!dirty)download(pretty(candidate.replay),'encounter-replay.json');};actions.append(replay);
  const statistics=card(dirty?'Статистика исходного состава':'Статистика');statistics.classList.add('result-statistics');
  if(dirty)statistics.append(node('span','Черновик · оценки неактуальны','badge draft-badge'));
  else if(selected.has(id))statistics.append(node('span','Рекомендован после проверки','badge'));
  const metrics=node('div',undefined,'result-metrics');for(const [title,value] of [['Победы игроков',percent(candidate.win_rate)],['Средние раунды',Number(candidate.mean_started_rounds).toFixed(2)],['Симуляций',candidate.trials]]){const item=node('div',title);item.append(node('strong',value));metrics.append(item);}statistics.append(metrics);
  if(candidate.win_interval_95)statistics.append(node('p','Интервал оценки побед (95%): '+candidate.win_interval_95.map(percent).join(' — '),'visual-note'));
  if(candidate.potion_use_counts)statistics.append(node('p','Использовано зелий (Potions), в среднем за бой: '+(candidate.potion_use_counts.reduce((sum,item)=>sum+item.count,0)/candidate.trials).toFixed(2),'visual-note'));
  if(candidate.magic_counts){const mean=key=>(candidate.magic_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Магия (Magic), в среднем за бой: сотворения (Casting) '+mean('casting_actions')+' · заклинания (Spells) '+mean('spell_casts')+' · ошибки (Miscasts) '+mean('miscasts')+' · неподдержанные Miscasts '+mean('unsupported_miscasts'),'visual-note'));}
  if(candidate.pc_ranged_counts){const mean=key=>(candidate.pc_ranged_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Игроки: выстрелы (Shots) '+mean('shots')+' · Помощь стрелку (Shooting Help) '+mean('shooting_help_tests')+' · Перезарядка (Reload) '+mean('reload_actions')+' · Смена оружия (Weapon Swap) '+mean('weapon_swaps')+' — в среднем за бой','visual-note'));}
  if(candidate.npc_ranged_counts){const mean=key=>(candidate.npc_ranged_counts.reduce((sum,item)=>sum+item[key],0)/candidate.trials).toFixed(2);statistics.append(node('p','Стрельба NPC (Shooting), в среднем за бой: выстрелы '+mean('shots')+' · залпы '+mean('bonus_shots')+' · действия перезарядки (Reload) '+mean('reload_actions'),'visual-note'));}
  const outcomes=candidate.outcomes||{};statistics.append(node('p','Победы: '+outcomes.objective_achieved+' · Поражения: '+outcomes.party_defeated+' · Лимит раундов: '+outcomes.round_limit+' · Неподдержанные ситуации: '+outcomes.unsupported_path,'visual-note'));box.append(statistics);
  for(const [index,npc] of (npcs||[]).entries()){
   const creature=card('Противник '+(index+1));creature.classList.add('npc-card');creature.querySelector('h3').classList.add('npc-heading');creature.querySelector('h3').append(npcFileControls(candidate,index,result));const tables=node('div',undefined,'npc-stat-tables');tables.append(npcStatTable('Характеристики (Characteristics)',Object.keys(characteristicTerms),{...npc,...(npc.ranged||{})}),npcStatTable('Навыки (Skills)',Object.keys(skillTerms),{...npc,...(npc.ranged||{})}));creature.append(tables);
   const loadout=node('dl',undefined,'npc-loadout'),weapon=generatedWeaponNames[npc.weapon]||npc.weapon;
   const weaponHint={pistol:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)5, игнорирует броню; Перезарядка (Reload)3 успеха.',repeater_pistol:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)5, игнорирует броню. Возможный залп +2d открывает Перезарядку (Reload)3 успеха; режим выбирается автоматически.',repeater_handbow:'Одноручное, оптимальная дальность (Optimum Range) Close–Short; Урон (Damage)4. Возможный залп +1d открывает Перезарядку (Reload)3 успеха; режим выбирается автоматически.',dagger:'Одноручное, Close Range; Damage = Strength − 1. +1d к Stealth для сокрытия.',staff:'Одноручное, Close Range; Damage = Strength. +1d к Athletics при пересечении Difficult Terrain.',axe:'Одноручное, Close Range; Damage = Strength. +1 Damage против бронированной (armoured) цели.',sword:'Одноручное, Close Range; Damage = Strength. +1d к Защите (Defence), пока владелец не Ошеломлён (Staggered).',warhammer:'Одноручное, Close Range; Damage = Strength. +1d к Ближнему бою (Melee) против Ошеломлённой (Staggered) цели.',morning_star:'Одноручное, Close Range; Damage = Strength + 1. −1d к Ближнему бою (Melee), пока владелец Ошеломлён (Staggered); нельзя применять dual wield.'}[npc.weapon]||weapon;
   const armourTags=[];if(npc.light_armour)armourTags.push([armourNames.light_armour,'+1 Resilience поверх Toughness.']);if(npc.shield)armourTags.push([armourNames.shield,'Щит (Shield) занимает вторую руку; +1 Resilience отдельно от брони. Разрешает Defence против Shooting.']);
   const groups=[['Оружие (Weapons)',[[weapon,weaponHint]],'Оружие не задано'],['Броня (Armour)',armourTags,'Броня не надета'],['Расходники (Consumables)',[],'Генератор пока не выдаёт расходники'],['Таланты (Talents)',(npc.talents||[]).map(t=>[generatedTalentNames[t]||t,generatedTalentHints[t]||t]),'Таланты не выбраны']];
   if((npc.abilities||[]).length)groups.push(['Способности (Abilities)',npc.abilities.map(a=>[a==='drained_on_hit'?'Истощение при попадании (Drained)':a,a==='drained_on_hit'?'При попадании цель получает Истощение (Drained). Отдельно разрешённая способность, не книжный талант.':a]),'Способности не заданы']);
   for(const [title,items,emptyHint] of groups){const values=node('dd');values.append(resultItemTags(items,emptyHint));loadout.append(node('dt',title),values);}creature.append(loadout);box.append(creature);
  }
  return box;
 }
 const finals=result.validations||[];
 if(!finals.length)root.append(node('p','В этом запуске нет проверенных финалистов. См. исследованные составы ниже.','visual-note'));
 finals.forEach((candidate,index)=>root.append(candidateView(candidate,index+1)));
 const explored=node('details',undefined,'visual-card');explored.append(node('summary','Исследованные составы'));(result.explored||[]).forEach((candidate,index)=>explored.append(candidateView(candidate,index+1)));root.append(explored);
 if(root===byId('result-visual'))syncResultCardHeading();
}
for(const mode of ['visual','json']){byId('request-'+mode+'-tab').onclick=()=>setRequestView(mode);byId('result-'+mode+'-tab').onclick=()=>setResultView(mode);}
renderResultVisual(null);
'''

from towr.adapters._local_ui_inventory import INVENTORY_STYLE, INVENTORY_SCRIPT

VISUAL_STYLE += INVENTORY_STYLE
VISUAL_SCRIPT += INVENTORY_SCRIPT
