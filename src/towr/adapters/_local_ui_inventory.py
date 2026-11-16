"""Inventory rows and talent tags over request facts; no combat execution."""

INVENTORY_STYLE = r'''
.inventory-row{--item-control-height:36px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) var(--item-control-height);gap:10px;align-items:end;margin:10px 0}
.inventory-row.consumable{grid-template-columns:minmax(0,1fr) var(--consumable-count-width,88px) 36px;margin:0}
.inventory-row input,.inventory-row select{width:100%;min-width:0;height:var(--item-control-height)}
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
@media(max-width:480px){.inventory-row{grid-template-columns:minmax(0,1fr) var(--item-control-height)}.inventory-row>label:first-child{grid-column:1/-1}.consumable-item{--consumable-count-width:70px}.inventory-row.consumable>label:first-child{grid-column:auto}}
'''

INVENTORY_SCRIPT = r'''
const armourNames={light_armour:'Лёгкая броня (Light Armour)',heavy_armour:'Тяжёлая броня (Heavy Armour)',helmet:'Обычный шлем (Helmet)',shield:'Щит (Shield)'};
const consumableNames={healing_potion:'Зелье лечения (Healing Potion)',enhancement_potion:'Зелье усиления (Enhancement Potion)'};
const enhancementNames=characteristicNames;
const talentNames={lucky:'Удачливый (Lucky)',wizard:'Маг (Wizard)','mighty blow':'Могучий удар (Mighty Blow)'};
const talentLabel=value=>talentNames[value.toLowerCase()]||value;
const heldLocations={carried:'Убрано / за спиной',left_hand:'В левой руке',right_hand:'В правой руке',both_hands:'В обеих руках'};
const twoHandedInventoryWeapons=new Set(['pickaxe','flail','billhook','halberd','glaive','greataxe','greathammer']);
function actionButton(kind,title,iconOnly=false){
 const button=node('button',undefined,kind==='add'?'action-add':'action-remove');button.type='button';button.title=title;button.setAttribute('aria-label',title);
 if(kind==='add'){button.textContent='Добавить';return button;}
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS('http://www.w3.org/2000/svg','path');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');
 path.setAttribute('d','M6 6l12 12M6 18 18 6');svg.append(path);button.append(svg);if(!iconOnly)button.append(node('span',title));return button;
}
function inventoryId(member,prefix){const ids=new Set([...(member.equipment?.weapons||[]),...(member.equipment?.armour||[]),...(member.consumables||[])].map(i=>i.id));let n=1;while(ids.has(prefix+':'+n))n++;return prefix+':'+n;}
function inventoryRemove(row,path,index,title){const remove=actionButton('remove','Удалить '+title,true);remove.classList.add('inventory-remove');remove.dataset.action='remove-item';remove.dataset.path=[...path,index].join('/');remove.onclick=()=>editRequest(path,get(read(),path).filter((_,i)=>i!==index));row.append(remove);}
function inventoryAdd(parent,title,path,make){const button=actionButton('add',title);button.classList.add('inventory-add');button.dataset.action='add-'+path.at(-1);button.onclick=()=>{const data=read(),member=data.party[path[1]];editRequest(path,[...(get(data,path)||[]),make(member)]);};parent.append(button);}
function renderInventory(parent,member,index){
 const gear=member.equipment||{};
 parent.append(node('h4','Оружие (Weapons)'));
 parent.append(node('p','Каждая строка — отдельный предмет. Положение указывает, что активно на начало боя.','visual-note'));
 for(const [i,item] of (gear.weapons||[]).entries()){
  const row=node('div',undefined,'inventory-row'),path=['party',index,'equipment','weapons',i];
  inputField(row,'Оружие '+(i+1),[...path,'weapon'],item.weapon,weaponNames);
  inputField(row,'На начало боя',[...path,'location'],item.location,heldLocations);
  inventoryRemove(row,['party',index,'equipment','weapons'],i,'оружие '+(i+1));parent.append(row);
 }
 inventoryAdd(parent,'Добавить оружие',['party',index,'equipment','weapons'],m=>({id:inventoryId(m,'weapon'),weapon:'sword',location:'carried'}));
 parent.append(node('h4','Броня (Armour) и защитное снаряжение'));
 for(const [i,item] of (gear.armour||[]).entries()){
  const row=node('div',undefined,'inventory-row'),path=['party',index,'equipment','armour',i];
  inputField(row,'Предмет '+(i+1),[...path,'kind'],item.kind,armourNames,value=>{
   const next={...get(read(),path),kind:value,location:value==='shield'?'carried':'worn'};editRequest(path,next);
  });
  const locations=item.kind==='shield'?{carried:'Убрано',left_hand:'В левой руке',right_hand:'В правой руке'}:{worn:'Надето',carried:'Убрано'};
  inputField(row,'На начало боя',[...path,'location'],item.location,locations);
  inventoryRemove(row,['party',index,'equipment','armour'],i,'защитный предмет '+(i+1));parent.append(row);
 }
 inventoryAdd(parent,'Добавить защиту',['party',index,'equipment','armour'],m=>({id:inventoryId(m,'armour'),kind:'light_armour',location:'worn'}));
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
 const warnings=[],active=(gear.weapons||[]).filter(w=>w.location!=='carried'),spares=(gear.weapons||[]).filter(w=>w.location==='carried');
 if(active.length!==1)warnings.push('Симуляция пока требует одно активное оружие; бой двумя оружиями ещё не реализован.');
 if(spares.length && !(spares.length===1 && active.length===1 && twoHandedInventoryWeapons.has(active[0].weapon) && !twoHandedInventoryWeapons.has(spares[0].weapon)))warnings.push('Смена этого набора запасного оружия пока не реализована.');
 if((gear.armour||[]).some(a=>a.kind==='heavy_armour'||a.location==='carried'))warnings.push('Тяжёлая или запасная броня/щит пока не подключены к симуляции.');
 if((member.consumables||[]).some(item=>item.kind==='enhancement_potion'&&!['weapon_skill','strength','toughness','agility'].includes(item.characteristic)))warnings.push('Усиление (Enhancement Potion) пока поддерживает WS, Strength, Toughness и Agility.');
 if(warnings.length)parent.append(node('p',warnings.join(' ')+' Инвентарь можно редактировать и сохранять; неподдержанные возможности блокируют расчёт.','inventory-warning'));
}
function renderTalentTags(parent,member,index){
 parent.append(node('h4','Таланты (Talents)'));const tags=node('div',undefined,'talent-tags');
 for(const [i,talent] of (member.talents||[]).entries()){
  const supported=['lucky','wizard'].includes(talent),tag=node('span',talentLabel(talent),'talent-tag'+(supported?'':' pending'));
  attachTagTooltip(tag,talent==='lucky'?'Первая трата Судьбы (Fate) за сессию бесплатна':talent==='wizard'?'Уровень мага (Wizard Level) и известные заклинания (Spells) задаются ниже':'Ещё не поддержан симуляцией');
  const remove=actionButton('remove','Удалить талант '+talentLabel(talent),true);remove.onclick=()=>setPlayerTalents(index,read().party[index].talents.filter((_,j)=>j!==i));tag.append(remove);tags.append(tag);
 }parent.append(tags);
 const entry=node('div',undefined,'talent-entry'),picker=node('div',undefined,'talent-picker'),input=node('input');input.type='text';input.placeholder='Выберите или введите талант…';input.setAttribute('aria-label','Добавить талант персонажу '+(index+1));input.dataset.role='talent-entry';input.dataset.member=String(index);input.autocomplete='off';
 const options=node('div',undefined,'talent-suggestions hidden');options.id='talent-options-'+index;options.setAttribute('role','listbox');options.setAttribute('aria-label','Подсказки талантов');
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',options.id);input.setAttribute('aria-expanded','false');
 let selectedIndex=-1;
 const close=()=>{options.classList.add('hidden');input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');selectedIndex=-1;};
 const commit=raw=>{
  const value=raw.trim();if(!value)return;const talent=['lucky','wizard'].includes(value.toLowerCase())?value.toLowerCase():value,values=read().party[index].talents||[];
  if(values.some(t=>t.toLowerCase()===talent.toLowerCase())){message('Этот талант уже добавлен.','error');close();return;}
  close();setPlayerTalents(index,[...values,talent]);document.querySelector('[data-role="talent-entry"][data-member="'+index+'"]').focus();
 };
 const suggest=()=>{
  options.replaceChildren();selectedIndex=-1;input.removeAttribute('aria-activedescendant');
  const query=input.value.trim(),values=read().party[index].talents||[],duplicate=value=>values.some(t=>t.toLowerCase()===value.toLowerCase()),choices=[];
  if(!duplicate('lucky') && ['lucky','удача','удачливый','удачливый (lucky)'].some(name=>name.includes(query.toLowerCase())))choices.push({value:'lucky',label:talentLabel('lucky'),hint:'Первая трата Судьбы (Fate) за сессию бесплатна.'});
  if(!duplicate('wizard') && ['wizard','маг','маг (wizard)'].some(name=>name.includes(query.toLowerCase())))choices.push({value:'wizard',label:talentLabel('wizard'),hint:'Сотворение (Casting) запомненных заклинаний (Memorised Spells) школы Elementalism.'});
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
 parent.append(node('p','В расчёт подключены Удачливый (Lucky) и Маг (Wizard). Другие таланты (Talents) можно сохранить тегами; до реализации их эффектов расчёт с ними будет недоступен.','visual-note'));
}
function setPlayerTalents(index,talents){
 const member=read().party[index],previous=(member.talents||[]).includes('wizard');member.talents=talents;
 if(talents.includes('wizard')){
  if(!member.magic)member.magic={origin:'human',wizard_level:1,lores:['elementalism'],memorised_spells:['lightning_blast'],arcane_paraphernalia:true};
  if(!Object.hasOwn(member.characteristics,'reason'))member.characteristics.reason=3;
  if(!Object.hasOwn(member.skills,'willpower'))member.skills.willpower=3;
 }else if(previous){delete member.magic;delete member.characteristics.reason;delete member.skills.willpower;}
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
 parent.append(node('p','Каждый бросок сотворения (Casting) занимает действие. Броня (Armour) и щит (Shield) делают проверку мрачной (Grim); принадлежности не добавляют отдельный бонусный куб.','visual-note'));
 if(['dwarf','halfling'].includes(magic.origin))parent.append(node('p','Талант Маг (Wizard) недоступен этому происхождению (Origin).','inventory-warning'));
 if(!magic.arcane_paraphernalia)parent.append(node('p','Для расчёта нужны магические принадлежности (Arcane Paraphernalia); импровизированный комплект пока не поддержан.','inventory-warning'));
 if(!(magic.memorised_spells||[]).length)parent.append(node('p','Выберите хотя бы одно запомненное заклинание (Memorised Spell).','inventory-warning'));
}
'''
