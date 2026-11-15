"""DOM views over the current request/result JSON; no game rules."""

VISUAL_STYLE = r'''
.view-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.view-switch{display:flex;gap:4px}.view-switch button{height:32px;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;font-size:13px}
.view-switch button[aria-pressed="true"]{color:#235ba8;border-color:#235ba8;background:#edf4ff}
.view-switch button[aria-pressed="true"]:hover:not(:disabled){background:#dfeafe;border-color:#1c4c8c}
.view-switch button[aria-pressed="true"]:active:not(:disabled){background:#d0e1fb}
.visual-view{min-height:560px}.visual-card{border:1px solid #dfe4eb;border-radius:6px;padding:14px;margin:12px 0;background:#fafbfc}
.visual-card h3{font-size:15px;margin:0 0 12px}.visual-card h4{font-size:14px;margin:12px 0 8px}
.visual-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.visual-fields.character-identity{grid-template-columns:minmax(0,2fr) minmax(90px,1fr);align-items:end}
.visual-fields.character-stats{grid-template-columns:repeat(auto-fit,minmax(min(100%,136px),1fr));align-items:end}
.character-stats label{display:grid;grid-template-rows:auto 36px;align-content:start;font-size:12px;line-height:1.3}
.visual-fields.character-stats input{width:100%;max-width:100%;height:36px;text-align:left}
.visual-fields input,.visual-fields select{width:100%;min-width:0}
select{font:inherit;padding:8px 36px 8px 10px;border:1px solid #bfc7d2;border-radius:4px;background-color:white;color:#20242c;appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='m2 4 4 4 4-4' fill='none' stroke='%235d6977' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;background-size:12px 12px}
@media(forced-colors:active){select{appearance:auto;background-image:none;padding-right:8px}}
.visual-card details{margin-top:12px}.visual-card summary{cursor:pointer;color:#46566c;font-size:13px}
.visual-card details .visual-card{background:white}.toggle-field{flex-direction:row;align-items:center;gap:8px}
.toggle-field input{width:auto}.visual-note{font-size:13px;color:#667085;line-height:1.5;margin:8px 0}
.automatic-npc-toggle{margin:14px 0}
.stale-notice{padding:10px 12px;background:#fff8e8;border:1px solid #e9d6a7;border-radius:5px;color:#78531c;font-size:13px;margin:12px 0}
.result-metrics{display:flex;flex-wrap:wrap;gap:10px 22px;margin:10px 0;font-size:13px}.result-metrics strong{display:block;font-size:19px;color:#20242c}
.badge{display:inline-block;padding:3px 7px;border-radius:4px;background:#e6f2e9;color:#236137;font-size:12px}
.npc-stats{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;margin:8px 0}
.npc-stats span{color:#5c6470}.npc-stats b{color:#20242c}.result-card .visual-card{background:white}
.visual-empty{color:#667085;padding:16px 0}.visual-card button{font-size:13px}
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
// Characteristic abbreviations follow PG14. Skill short labels are UI notation.
const skillTerms={melee:{name:'Ближний бой',original:'Melee',short:'Mel'},defence:{name:'Защита',original:'Defence',short:'Def'},athletics:{name:'Атлетика',original:'Athletics',short:'Ath'},endurance:{name:'Выносливость',original:'Endurance',short:'End'}};
const termLabels=(terms,style)=>Object.fromEntries(Object.entries(terms).map(([key,term])=>[key,term.name+' ('+term[style]+')']));
const characteristicNames=termLabels(characteristicTerms,'short'),characteristicFullNames=termLabels(characteristicTerms,'original');
const statLabels={...characteristicNames,...termLabels(skillTerms,'short'),armour_bonus:'Бонус брони (Armour Bonus)'};
const statFullNames={...characteristicFullNames,...termLabels(skillTerms,'original')};
const weaponNames={staff:'Посох (Staff)',sword:'Меч (Sword)',dagger:'Кинжал (Dagger)',axe:'Топор (Axe)',warhammer:'Боевой молот (Warhammer)',
 morning_star:'Моргенштерн (Morning Star)',pickaxe:'Клевец (Pickaxe)',flail:'Цеп (Flail)',billhook:'Гвизарма (Billhook)',halberd:'Алебарда (Halberd)',glaive:'Глефа (Glaive)',greataxe:'Двуручный топор (Greataxe)',greathammer:'Двуручный молот (Greathammer)'};
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
 input.dataset.path=path.join('/');input.addEventListener('change',()=>{try{if(onChange){onChange(input.value);return;}editRequest(path,input.type==='checkbox'?input.checked:typeof value==='number'?integer(input.value):input.value);}catch(error){visualEditError=error.message;message(error.message,'error');}});
 label.append(input);parent.append(label);return input;
}
function renderRequestVisual(data){
 visualEditError=null;
 if(requestView!=='visual')return;
 const root=byId('request-visual');root.replaceChildren();
 for(const [index,member] of (data.party||[]).entries()){
  const person=card('Игрок '+(index+1)+' · '+member.actor_id);person.classList.add('player-card');
  const identity=node('div',undefined,'visual-fields character-identity');inputField(identity,'Имя / ID',['party',index,'actor_id'],member.actor_id);
  inputField(identity,'Судьба (Fate)',['party',index,'resources','fate'],member.resources?.fate);person.append(identity);
  for(const [section,title] of [['characteristics','Характеристики (Characteristics)'],['skills','Навыки (Skills)']]){
   person.append(node('h4',title));const grid=node('div',undefined,'visual-fields character-stats');
   for(const [key,value] of Object.entries(member[section]||{}))inputField(grid,statLabels[key]||key,['party',index,section,key],value);
   person.append(grid);
  }
  renderInventory(person,member,index);
  renderTalentTags(person,member,index);
  const remove=actionButton('remove','Удалить игрока '+member.actor_id,true);remove.dataset.action='remove-player';remove.disabled=busy||(data.party||[]).length<=1;remove.onclick=()=>editRequest(['party'],read().party.filter((_,i)=>i!==index));person.querySelector('h3').classList.add('character-heading');person.querySelector('h3').append(remove);root.append(person);
 }
 const add=actionButton('add','Добавить игрока');add.dataset.action='add-player';add.disabled=busy;add.onclick=()=>{
  const data=read(),members=data.party||[];let id='pc:'+(members.length+1),suffix=members.length+1;while(members.some(m=>m.actor_id===id))id='pc:'+(++suffix);
  const member=JSON.parse(JSON.stringify(members[0]||{characteristics:{weapon_skill:3,strength:3,toughness:3,agility:3},skills:{melee:4,defence:4,athletics:4,endurance:4},equipment:{weapons:[{id:'weapon:1',weapon:'staff',location:'right_hand'}],armour:[]},consumables:[],talents:[],resources:{fate:2}}));member.actor_id=id;editRequest(['party'],[...members,member]);
 };root.append(add);
 const scene=card('Сцена'),sceneGrid=node('div',undefined,'visual-fields');
 for(const [key,title,choices] of [['range','Начальная дистанция',{close:'Ближняя дистанция (Close Range)'}],['ambush','Засада (Ambush)',{none:'Нет — засады пока не поддержаны'}],['terrain','Местность (Terrain)',{open:'Открытая, без модификаторов'}]])inputField(sceneGrid,title,['scene',key],data.scene?.[key],choices);
 scene.append(sceneGrid);scene.append(node('p','Начало новой сессии: персонажи здоровы, Судьба (Fate) и талант Удачливый (Lucky) доступны полностью. Решения и расход ресурсов рассчитываются в каждом бою.','visual-note'));root.append(scene);
 const advanced=node('details',undefined,'visual-card');advanced.open=!!data.search_space;advanced.append(node('summary','Ограничения генерации NPC — необязательно'));
 const automatic=node('label','Автоматические диапазоны по партии','toggle-field automatic-npc-toggle'),automaticInput=node('input');automaticInput.type='checkbox';automaticInput.checked=!data.search_space;automaticInput.dataset.path='automatic-npc-space';
 automaticInput.onchange=()=>editRequest(['search_space'],automaticInput.checked?null:planningSearchSpace({...read(),search_space:null}));automatic.prepend(automaticInput);advanced.append(automatic);
 if(!data.search_space){advanced.append(node('p','Генератор сам задаёт диапазоны характеристик и навыков вокруг партии. Составы проверяются по вашим целям боя.','visual-note'));root.append(advanced);return;}
 const space=card('Возможные параметры противников');space.append(node('p','Разрешённые значения через запятую. Генератор выбирает из них новые сочетания.','visual-note'));
 const grid=node('div',undefined,'visual-fields');
 for(const key of ['weapon_skill','strength','toughness','agility','melee','athletics'])if(Array.isArray(data.search_space?.[key])){
  const label=node('label',statLabels[key]),input=node('input');label.title=statFullNames[key]||statLabels[key];input.title=label.title;input.type='text';input.value=data.search_space[key].join(', ');input.dataset.path='search_space/'+key;
  input.addEventListener('change',()=>{try{const values=input.value.trim().split(/[,;\s]+/).map(integer);if(new Set(values).size!==values.length)throw Error('Значения не должны повторяться.');editRequest(['search_space',key],values);}catch(error){visualEditError=error.message;message(error.message,'error');}});label.append(input);grid.append(label);
 }
 space.append(grid);
 const choices=node('div',undefined,'visual-fields');
 for(const [key,options] of [['weapon',{staff:weaponNames.staff,dagger:weaponNames.dagger}],['light_armour',{'false':'Без брони','true':'Лёгкая броня (Light Armour)'}]]){
  const group=node('div');group.append(node('h4',key==='weapon'?'Оружие (Weapons)':'Броня (Armour)'));
  for(const [raw,name] of Object.entries(options)){
   const value=key==='light_armour'?raw==='true':raw,label=node('label',name,'toggle-field'),input=node('input');input.type='checkbox';input.checked=(data.search_space?.[key]||[]).includes(value);input.dataset.path='search_space/'+key+'/'+raw;
   input.addEventListener('change',()=>{const values=[...(read().search_space?.[key]||[])];editRequest(['search_space',key],input.checked?[...values,value]:values.filter(v=>v!==value));});label.prepend(input);group.append(label);
  }choices.append(group);
 }
 const ability=node('div');ability.append(node('h4','Способности (Abilities)'));
 const select=node('select');select.setAttribute('aria-label','Допустимые способности NPC');select.dataset.path='search_space/abilities';
 const abilityOptions=[['Без способностей',[[]]],['Без способностей или Истощение (Drained) при попадании',[[],['drained_on_hit']]],['Только Истощение (Drained) при попадании',[['drained_on_hit']]]];
 const current=JSON.stringify(data.search_space?.abilities);for(const [name,value] of abilityOptions){const option=node('option',name);option.value=JSON.stringify(value);select.append(option);}
 if(!abilityOptions.some(([,value])=>JSON.stringify(value)===current)){const option=node('option','Пользовательский набор · см. JSON');option.value=current||'[]';select.append(option);}select.value=current;
 select.onchange=()=>editRequest(['search_space','abilities'],JSON.parse(select.value));ability.append(select);choices.append(ability);space.append(choices);advanced.append(space);root.append(advanced);

}
function setRequestView(view){
 const previous=requestView;
 if(view==='visual'){try{syncForm();const data=read();requestView=view;renderRequestVisual(data);}catch(error){requestView=previous;message('Сначала исправьте JSON: '+error.message,'error');return;}}
 else{requestView=view;visualEditError=null;}
 byId('request').classList.toggle('hidden',view!=='json');byId('visual-request-controls').classList.toggle('hidden',view!=='visual');
 for(const mode of ['visual','json'])byId('request-'+mode+'-tab').setAttribute('aria-pressed',String(mode===view));
 updateFileActions();
}
function setResultView(view){resultView=view;byId('result').classList.toggle('hidden',view!=='json');byId('result-visual').classList.toggle('hidden',view!=='visual');for(const mode of ['visual','json'])byId('result-'+mode+'-tab').setAttribute('aria-pressed',String(mode===view));updateFileActions();}
function updateFileActions(){
 byId('format').classList.toggle('hidden',requestView!=='json');
 byId('download').disabled=busy||!lastResult;
}
function renderResultVisual(result){
 const root=byId('result-visual');root.replaceChildren();
 if(!result){root.append(node('p','Результат появится после расчёта.','visual-empty'));return;}
 if(result.error){root.append(node('p',[result.error.path,result.error.message].filter(Boolean).join(': '),'visual-note'));return;}
 root.append(node('p','Seed расчёта: '+result.source_request.search.master_seed,'visual-note'));
 const percent=n=>Number.isFinite(n)?(n*100).toFixed(1)+'%':'—';
 const selected=new Set(result.selected||[]);
 function candidateView(candidate,number){
  const id=candidate.replay?.scenario?.id,box=card('Состав '+number);box.classList.add('result-card');box.dataset.candidateId=id;
  if(selected.has(id))box.append(node('span','Рекомендован после проверки','badge'));
  const metrics=node('div',undefined,'result-metrics');for(const [title,value] of [['Победы игроков',percent(candidate.win_rate)],['Средние раунды',Number(candidate.mean_started_rounds).toFixed(2)],['Симуляций',candidate.trials]]){const item=node('div',title);item.append(node('strong',value));metrics.append(item);}box.append(metrics);
  if(candidate.win_interval_95)box.append(node('p','Интервал оценки побед (95%): '+candidate.win_interval_95.map(percent).join(' — '),'visual-note'));
  for(const [index,npc] of (candidate.npcs||[]).entries()){
   const creature=card('Противник '+(index+1)),stats=node('div',undefined,'npc-stats');
   for(const key of ['weapon_skill','strength','toughness','agility','melee','athletics']){const item=node('span',statLabels[key]+': ');item.title=statFullNames[key]||statLabels[key];item.append(node('b',npc[key]));stats.append(item);}creature.append(stats);
   creature.append(node('p',(weaponNames[npc.weapon]||npc.weapon)+' · '+(npc.light_armour?'Лёгкая броня (Light Armour)':'Без брони')+((npc.abilities||[]).length?' · '+npc.abilities.map(a=>a==='drained_on_hit'?'Истощение при попадании (Drained)':a).join(', '):''),'visual-note'));box.append(creature);
  }
  const outcomes=candidate.outcomes||{};box.append(node('p','Победы: '+outcomes.objective_achieved+' · Поражения: '+outcomes.party_defeated+' · Лимит раундов: '+outcomes.round_limit+' · Неподдержанные ситуации: '+outcomes.unsupported_path,'visual-note'));
  const use=node('button','Взять за основу запроса');use.type='button';use.disabled=busy;use.title='Число NPC фиксируется; их значения становятся допустимыми для поиска. Возможны новые сочетания.';use.onclick=()=>useComposition(candidate);box.append(use);
  const replay=node('button','Скачать бой');replay.type='button';replay.style.marginLeft='8px';replay.onclick=()=>download(pretty(candidate.replay),'encounter-replay.json');box.append(replay);return box;
 }
 const finals=result.validations||[];
 root.append(node('p','Проверенные финалисты · '+finals.length,'visual-note'));
 if(!finals.length)root.append(node('p','В этом запуске нет проверенных финалистов. См. исследованные составы ниже.','visual-note'));
 finals.forEach((candidate,index)=>root.append(candidateView(candidate,index+1)));
 const explored=node('details',undefined,'visual-card');explored.append(node('summary','Исследованные составы · '+(result.explored||[]).length));(result.explored||[]).forEach((candidate,index)=>explored.append(candidateView(candidate,index+1)));root.append(explored);
}
function useComposition(candidate){
 if(busy)return;
 try{const data=read(),npcs=candidate.npcs;if(!npcs?.length)throw Error('Состав не содержит NPC.');
  data.npc_count={minimum:npcs.length,maximum:npcs.length};const next={...(data.search_space||{})};
  for(const key of ['weapon_skill','strength','toughness','agility','melee','athletics','weapon','light_armour'])next[key]=[...new Set(npcs.map(n=>n[key]))];
  next.abilities=[...new Map(npcs.map(n=>[JSON.stringify(n.abilities),n.abilities])).values()];data.search_space=next;
  byId('request').value=pretty(data);setRequestView('visual');syncForm();message('Состав перенесён в запрос. Возможны новые сочетания его параметров. Для расчёта нажмите «Запустить генератор».');
 }catch(error){message(error.message,'error');}
}
for(const mode of ['visual','json']){byId('request-'+mode+'-tab').onclick=()=>setRequestView(mode);byId('result-'+mode+'-tab').onclick=()=>setResultView(mode);}
renderResultVisual(null);
'''

from towr.adapters._local_ui_inventory import INVENTORY_STYLE, INVENTORY_SCRIPT

VISUAL_STYLE += INVENTORY_STYLE
VISUAL_SCRIPT += INVENTORY_SCRIPT
