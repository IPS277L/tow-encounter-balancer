"""Optional real-browser check; uses an installed Edge/Chromium, no driver."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from towr.adapters._local_ui_page import PAGE
from towr.adapters.local_ui import LocalUiServer


BROWSER = os.environ.get('TOWR_UI_BROWSER') or shutil.which('chromium') or shutil.which('google-chrome')
if not BROWSER:
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    BROWSER = str(edge) if edge.is_file() else None

CHECK = r'''<script>
(async()=>{
 function check(value,message){if(!value)throw Error(message);}
 try{
  while(!byId('request').value)await new Promise(resolve=>setTimeout(resolve,50));
  const original=read();check(original.kind==='dynamic_encounter_search','initial request');
  const layout=()=>[document.documentElement.clientWidth,...[document.querySelector('main'),...document.querySelectorAll('.columns>.panel')].flatMap(element=>{const rect=element.getBoundingClientRect();return [rect.left,rect.width];})];
  const originalLayout=JSON.stringify(layout());byId('request-json-tab').click();byId('result-json-tab').click();check(JSON.stringify(layout())===originalLayout,'JSON view preserves main and panel horizontal positions');byId('request-visual-tab').click();byId('result-visual-tab').click();check(JSON.stringify(layout())===originalLayout,'card view preserves viewport gutter and panel widths');
  // Evaluate the actual hover declarations through an equivalent forced-state
  // class, preserving specificity; dispatching mouse events does not set :hover.
  const hoverProbe=document.createElement('style');hoverProbe.textContent=[...document.styleSheets].flatMap(sheet=>[...sheet.cssRules]).filter(rule=>rule.selectorText?.includes(':hover')).map(rule=>rule.cssText.replaceAll(':hover','.ui-test-hover')).join('\n');document.head.append(hoverProbe);
  const buttonPaint=button=>{const style=getComputedStyle(button);return [style.backgroundColor,style.borderColor,style.color].join('|');};
  const hoverChanges=button=>{const before=buttonPaint(button);button.classList.add('ui-test-hover');const changed=buttonPaint(button)!==before;button.classList.remove('ui-test-hover');return changed;};
  for(const id of ['load','save','format','request-visual-tab','request-json-tab','result-visual-tab','result-json-tab','run'])check(hoverChanges(byId(id)),'hover styling for '+id);
  for(const id of ['load','save','format','request-visual-tab','request-json-tab','result-visual-tab','result-json-tab']){const button=byId(id);button.classList.add('ui-test-hover');check(getComputedStyle(button).color==='rgb(35, 91, 168)','blue hover feedback for '+id);button.classList.remove('ui-test-hover');}
  check(!hoverChanges(byId('download')),'disabled download does not gain hover styling');
  check(!byId('budget') && !byId('calculate'),'budget is derived text only');
  check(byId('auto-search').checked && byId('candidates').disabled,'automatic planning initially enabled');
  const standard=JSON.parse(JSON.stringify(original));standard.npc_count={minimum:1,maximum:10};standard.targets={win_rate:{numerator:1,denominator:2},started_rounds:{numerator:5,denominator:1}};standard.max_rounds=15;
  check(canonical(automaticSearchPlan(standard))===canonical({max_candidates:24,exploration_trials:12,top_k:2,finalist_trials:256}),'baseline automatic plan');
  const estimate=estimatedSearchTime(standard);check(estimate.low>0 && estimate.high>=estimate.low,'valid time interval');
  const larger=JSON.parse(JSON.stringify(standard));larger.search.max_total_trials*=2;
  check(estimatedSearchTime(larger).high>estimate.high,'more trials increase estimated time');
  const heavier=JSON.parse(JSON.stringify(standard));heavier.npc_count.maximum=20;
  check(estimatedSearchTime(heavier).high>estimate.high,'larger composition increases estimated time at same budget');
  check(estimatedSearchTime({})===null,'invalid inputs have no invented time');
  const timeText=formatSearchTime(estimatedSearchTime(read()));check(byId('cost').textContent.includes(timeText) && byId('settings-preview').textContent.includes(timeText),'same estimate in plan and header');
  check(!byId('run').classList.contains('hidden') && byId('cancel').classList.contains('hidden'),'only launch shown when idle');
  check([...byId('run').parentElement.querySelectorAll('button')].map(b=>b.id).join(',')==='run,cancel','global toolbar only generates/cancels');
  check(byId('load').closest('.panel')===byId('request').closest('.panel') && byId('download').closest('.panel')===byId('result').closest('.panel'),'file controls in matching panels');
  check(byId('format').classList.contains('hidden') && !byId('load-result') && !byId('format-result') && !byId('result-file'),'format icons hidden in cards');
  const typed=pretty(standard);byId('request').value=typed;byId('request').setSelectionRange(5,5);byId('request').dispatchEvent(new Event('input'));
  check(byId('request').value===typed && byId('request').selectionStart===5,'JSON typing preserves text and cursor');
  byId('request').value=pretty(original);syncForm();
  const single=JSON.parse(JSON.stringify(original));single.npc_count={minimum:1,maximum:1};for(const key of Object.keys(single.search_space))single.search_space[key]=single.search_space[key].slice(0,1);
  check(automaticSearchPlan(single).max_candidates===1,'finite space caps candidates');
  const rare=JSON.parse(JSON.stringify(original));rare.targets.win_rate={numerator:99,denominator:100};
  check(automaticSearchPlan(original).finalist_trials>automaticSearchPlan(rare).finalist_trials,'precision responds to target');
  const longer=JSON.parse(JSON.stringify(original));longer.targets.started_rounds={numerator:15,denominator:1};longer.max_rounds=30;
  check(canonical(automaticSearchPlan(original))!==canonical(automaticSearchPlan(longer)),'planning responds to workload');
  check(read().search.max_total_trials===read().search.max_candidates*read().search.exploration_trials+read().search.top_k*read().search.finalist_trials,'automatic budget formula');
  byId('auto-search').checked=false;byId('auto-search').dispatchEvent(new Event('change'));
  check(!byId('candidates').disabled,'manual planning override');
  check(!byId('fresh-seed') && !byId('seed').disabled,'seed is directly editable without reseeding switch');
  check(!byId('search-settings').open,'search settings initially collapsed');
  byId('search-settings').querySelector('summary').click();check(byId('search-settings').open,'expand search settings');
  const autoPlanLabel=byId('auto-search').parentElement;check(autoPlanLabel.nextElementSibling.getBoundingClientRect().top-autoPlanLabel.getBoundingClientRect().bottom>=12,'automatic plan checkbox is separated from candidate fields');
  const foldedSource=byId('request').value;byId('search-settings').querySelector('summary').click();
  check(!byId('search-settings').open && byId('request').value===foldedSource,'collapse preserves request');
  byId('search-settings').querySelector('summary').click();
  check(byId('request').classList.contains('hidden') && byId('request-visual').children.length>0,'default visual request');
  let stat=document.querySelector('[data-path="party/0/characteristics/strength"]');stat.value=String(original.party[0].characteristics.strength+1);stat.dispatchEvent(new Event('change'));
  check(read().party[0].characteristics.strength===original.party[0].characteristics.strength+1,'editable PC card');
  check(JSON.stringify(read().party[0].resources)===JSON.stringify(original.party[0].resources),'preserved resource facts');
  check([...byId('request-visual').querySelectorAll('h4')].some(h=>h.textContent==='Характеристики (Characteristics)') && [...byId('request-visual').querySelectorAll('h4')].some(h=>h.textContent==='Навыки (Skills)'),'separate character and skill groups');
  const statInputs=[...document.querySelectorAll('#request-visual .character-stats input')];check(statInputs.length>=8 && statInputs.every(input=>Math.abs(input.getBoundingClientRect().width-input.parentElement.getBoundingClientRect().width)<1 && input.getBoundingClientRect().height===36),'character and skill editors fill their grid columns');
  const statRow=statInputs.slice(0,4).map(input=>input.getBoundingClientRect());check(statRow.every((rect,i)=>Math.abs(rect.top-statRow[0].top)<1 && (i===0||rect.left>statRow[i-1].right)),'four full-width stat fields stay aligned in one row');
  const singleLineLabels=parent=>[...parent.querySelectorAll('.character-stats label')].every(label=>{const range=document.createRange();range.selectNodeContents(label.firstChild);return range.getClientRects().length===1 && range.getBoundingClientRect().width<=label.getBoundingClientRect().width+1;});
  check(singleLineLabels(byId('request-visual')),'all Characteristic and Skill names fit on one line');
  const narrowPlayer=document.querySelector('.player-card');narrowPlayer.style.width='260px';check(singleLineLabels(narrowPlayer),'stat grid adapts to narrow cards without clipping labels');narrowPlayer.style.width='';
  check(document.querySelector('[data-path="party/0/characteristics/strength"]').parentElement.textContent.includes('(S)') && document.querySelector('[data-path="party/0/skills/defence"]').parentElement.textContent.includes('(Def)'),'character and skill labels use original abbreviations');
  check([characteristicNames,weaponNames,armourNames,consumableNames].every(names=>Object.values(names).every(name=>/\([^)]+\)$/.test(name))),'book term choices include original names or established abbreviations');
  check(characteristicNames.weapon_skill.endsWith('(WS)') && characteristicNames.ballistic_skill.endsWith('(BS)'),'established original abbreviations are used');
  check(characteristicNames.strength.endsWith('(S)') && characteristicNames.agility.endsWith('(Ag)') && characteristicNames.reason.endsWith('(Re)') && characteristicNames.fellowship.endsWith('(Fel)') && statLabels.melee.endsWith('(Mel)') && statLabels.endurance.endsWith('(End)'),'all current Characteristics and Skills use short labels');
  check(document.querySelector('[data-path="party/0/characteristics/strength"]').title.includes('(Strength)') && document.querySelector('[data-path="party/0/skills/defence"]').getAttribute('aria-label').includes('(Defence)'),'full originals remain in tooltips and accessible labels');
  const playerCards=[...byId('request-visual').querySelectorAll('.player-card')],partyBefore=canonical(read().party);
  check(playerCards.length===read().party.length && playerCards.every(card=>card.parentElement===byId('request-visual')) && !byId('request-visual').textContent.includes('Партия игроков'),'players render directly without party wrapper');
  document.querySelector('[data-action="add-player"]').click();check(read().party.length===playerCards.length+1,'add player action works');
  const newActor=read().party.at(-1).actor_id;check(read().party.filter(p=>p.actor_id===newActor).length===1,'added player has a unique actor ID');
  document.querySelectorAll('.player-card [data-action="remove-player"]')[playerCards.length].click();check(canonical(read().party)===partyBefore,'removing added player preserves existing players');
  const identityName=document.querySelector('[data-path="party/0/actor_id"]'),identityFate=document.querySelector('[data-path="party/0/resources/fate"]');
  check(identityName.parentElement.parentElement===identityFate.parentElement.parentElement && identityFate.getBoundingClientRect().left>identityName.getBoundingClientRect().right && Math.abs(identityFate.getBoundingClientRect().top-identityName.getBoundingClientRect().top)<1,'Fate sits to the right of name on the same row');
  check(document.querySelectorAll('[data-path="party/0/resources/fate"]').length===1,'Fate has a single editor');
  const weaponControl=document.querySelector('[data-path="party/0/equipment/weapons/0/weapon"]'),removeWeapon=document.querySelector('[data-path="party/0/equipment/weapons/0"]');
  const selectStyle=getComputedStyle(weaponControl);check(selectStyle.appearance==='none' && Number.parseFloat(selectStyle.paddingRight)>=32 && selectStyle.backgroundPosition.includes('12px'),'select arrow has an explicit inset and text clearance');
  check(weaponControl.selectedOptions[0].textContent.includes('(Sword)') && weaponControl.title.includes('(Sword)'),'item label and tooltip preserve original term');
  check(Math.abs(weaponControl.getBoundingClientRect().height-removeWeapon.getBoundingClientRect().height)<1 && Math.abs(removeWeapon.getBoundingClientRect().width-removeWeapon.getBoundingClientRect().height)<1,'item delete button matches input height and stays square');
  check(!document.querySelector('[data-path="party/0/policy"]') && !document.querySelector('[data-path="party/0/fate"]'),'no internal controller or ledger inputs');
  document.querySelector('[data-action="add-weapons"]').click();
  let location=document.querySelector('[data-path="party/0/equipment/weapons/1/location"]');location.value='right_hand';location.dispatchEvent(new Event('change'));
  document.querySelector('[data-action="add-weapons"]').click();
  let weapon=document.querySelector('[data-path="party/0/equipment/weapons/2/weapon"]');weapon.value='glaive';weapon.dispatchEvent(new Event('change'));
  check(read().party[0].equipment.weapons.length===3 && read().party[0].equipment.weapons[2].location==='carried','two held weapons and a carried glaive are stored separately');
  check(byId('request-visual').textContent.includes('бой двумя оружиями'),'unsupported dual wield is visible before calculation');
  document.querySelector('[data-path="party/0/equipment/weapons/2"]').click();document.querySelector('[data-path="party/0/equipment/weapons/1"]').click();
  document.querySelector('[data-action="add-armour"]').click();document.querySelector('[data-action="add-armour"]').click();
  let kind=document.querySelector('[data-path="party/0/equipment/armour/1/kind"]');kind.value='helmet';kind.dispatchEvent(new Event('change'));
  document.querySelector('[data-action="add-armour"]').click();kind=document.querySelector('[data-path="party/0/equipment/armour/2/kind"]');kind.value='shield';kind.dispatchEvent(new Event('change'));
  location=document.querySelector('[data-path="party/0/equipment/armour/2/location"]');location.value='right_hand';location.dispatchEvent(new Event('change'));
  check(read().party[0].equipment.armour.map(a=>a.kind).join(',')==='light_armour,helmet,shield','body helmet and shield are independent items');
  byId('request-json-tab').click();byId('request-visual-tab').click();check(read().party[0].equipment.armour.length===3,'inventory survives view switching');
  for(const i of [2,1,0])document.querySelector('[data-path="party/0/equipment/armour/'+i+'"]').click();
  let talent=document.querySelector('[data-role="talent-entry"][data-member="0"]');talent.focus();
  const suggestions=document.getElementById(talent.getAttribute('aria-controls')),suggestion=suggestions.querySelector('[role="option"]');
  check(!talent.hasAttribute('list') && !document.querySelector('datalist') && talent.getAttribute('aria-expanded')==='true','custom talent dropdown opens');
  check(suggestions.getBoundingClientRect().top>=talent.getBoundingClientRect().bottom && suggestions.getBoundingClientRect().width>=talent.getBoundingClientRect().width-1 && Number.parseFloat(getComputedStyle(suggestion).fontSize)>=13,'readable talent menu anchored below input');
  talent.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));check(talent.getAttribute('aria-expanded')==='false','Escape closes suggestions');
  talent.value='missing';talent.dispatchEvent(new Event('input'));check(suggestions.textContent.includes('Добавить «missing»'),'custom talent can be added from dropdown');
  talent.value='';talent.dispatchEvent(new Event('input'));suggestions.querySelector('[role="option"]').click();
  check(!document.querySelector('[data-action="add-talent"]') && read().party[0].talents.join(',')==='lucky','dropdown click adds talent without a separate button');
  check(read().party[0].talents.join(',')==='lucky' && document.querySelector('.talent-tag'),'talent becomes a tag');
  const tagList=document.querySelector('.talent-tags');check(tagList.getBoundingClientRect().top-tagList.previousElementSibling.getBoundingClientRect().bottom>=12 && tagList.nextElementSibling.getBoundingClientRect().top-tagList.getBoundingClientRect().bottom>=14,'talent tags have breathing room above and below');
  const addButtons=[...document.querySelectorAll('#request-visual .action-add')],deleteButtons=[...document.querySelectorAll('#request-visual .action-remove')];
  check(addButtons.length>=4 && addButtons.every(b=>Math.abs(b.getBoundingClientRect().width-88)<1 && Math.abs(b.getBoundingClientRect().height-36)<1 && b.textContent==='Добавить' && !b.querySelector('svg') && b.getAttribute('aria-label').startsWith('Добавить ')),'add actions match control height and retain compact text-only appearance');
  check(deleteButtons.every(b=>{const size=b.closest('.talent-tag')?24:36;return Math.abs(b.getBoundingClientRect().width-size)<1 && Math.abs(b.getBoundingClientRect().height-size)<1 && b.getAttribute('aria-label') && b.querySelector('path').getAttribute('d')==='M6 6l12 12M6 18 18 6';}),'cross delete actions keep standard size with compact talent exception');
  check(document.querySelector('.talent-tag .action-remove svg').getBoundingClientRect().width===12,'talent cross icon is compact');
  const luminance=rgb=>rgb.match(/[\d.]+/g).slice(0,3).map(v=>{const n=Number(v)/255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
  const background=element=>{for(let owner=element;owner;owner=owner.parentElement){const color=getComputedStyle(owner).backgroundColor;if(color!=='rgba(0, 0, 0, 0)' && color!=='transparent')return color;}return 'rgb(255, 255, 255)';};
  for(const button of [addButtons[0],deleteButtons[0]]){const style=getComputedStyle(button),a=luminance(style.color),b=luminance(background(button));check((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,'action colors have readable contrast');}
  check(getComputedStyle(addButtons[0]).color==='rgb(88, 101, 117)' && getComputedStyle(deleteButtons[0]).color==='rgb(88, 101, 117)','add and delete share neutral colors');
  check(hoverChanges(addButtons[0]) && hoverChanges(deleteButtons[0]),'add and delete retain hover feedback');
  for(const [button,color] of [[addButtons[0],'rgb(70, 102, 82)'],[deleteButtons[0],'rgb(150, 89, 89)']]){button.classList.add('ui-test-hover');const style=getComputedStyle(button);check(style.color===color,'green add and red delete hover');const a=luminance(style.color),b=luminance(background(button));check((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,'colored hover remains readable');button.classList.remove('ui-test-hover');}
  check(addButtons.every(button=>getComputedStyle(button).borderStyle==='solid' && getComputedStyle(button).borderColor==='rgb(204, 212, 223)' && getComputedStyle(button).backgroundColor==='rgb(255, 255, 255)'),'compact add buttons have a visible light border and white surface');
  talent=document.querySelector('[data-role="talent-entry"][data-member="0"]');talent.value='lucky';talent.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));check(read().party[0].talents.length===1,'duplicate tag prevented');
  talent.value='Mighty Blow';talent.dispatchEvent(new Event('input'));document.querySelector('#talent-options-0 [role="option"]').click();check(document.querySelector('.talent-tag.pending'),'unsupported talent stays visible in draft');
  document.querySelector('[aria-label="Удалить талант Могучий удар (Mighty Blow)"]').click();document.querySelector('[aria-label="Удалить талант Удачливый (Lucky)"]').click();check(read().party[0].talents.length===0,'talent tags removable');
  talent=document.querySelector('[data-role="talent-entry"][data-member="0"]');talent.focus();talent.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown'}));talent.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));check(read().party[0].talents.join(',')==='lucky','keyboard selection adds immediately');document.querySelector('[aria-label="Удалить талант Удачливый (Lucky)"]').click();
  talent=document.querySelector('[data-role="talent-entry"][data-member="0"]');talent.value='luck';talent.dispatchEvent(new Event('input'));talent.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));check(read().party[0].talents.join(',')==='lucky','Enter selects matching talent instead of creating a partial tag');document.querySelector('[aria-label="Удалить талант Удачливый (Lucky)"]').click();
  document.querySelector('[data-action="add-consumables"]').click();
  kind=document.querySelector('[data-path="party/0/consumables/0/kind"]');kind.value='enhancement_potion';kind.dispatchEvent(new Event('change'));
  let attribute=document.querySelector('[data-path="party/0/consumables/0/characteristic"]');attribute.value='agility';attribute.dispatchEvent(new Event('change'));
  let quantity=document.querySelector('[data-path="party/0/consumables/0/quantity"]');quantity.value='2';quantity.dispatchEvent(new Event('change'));
  const potionControls=['kind','quantity'].map(key=>document.querySelector('[data-path="party/0/consumables/0/'+key+'"]').getBoundingClientRect());potionControls.push(document.querySelector('[data-path="party/0/consumables/0"]').getBoundingClientRect());
  check(potionControls.every(r=>Math.abs(r.top-potionControls[0].top)<1 && Math.abs(r.height-potionControls[0].height)<1),'consumable header aligns type quantity and delete');
  const effect=document.querySelector('[data-path="party/0/consumables/0/characteristic"]');check(effect.closest('.consumable-details') && effect.getBoundingClientRect().top>potionControls[0].bottom,'effect parameters stay in the same lightweight item');
  check(Math.abs(effect.getBoundingClientRect().left-potionControls[0].left)<1 && Math.abs(effect.getBoundingClientRect().width-potionControls[0].width)<1,'potion Characteristic editor spans the same grid column as item');
  check(effect.selectedOptions[0].textContent.includes('(Ag)') && effect.title.includes('(Agility)'),'potion choices share original Characteristic names');
  check(read().party[0].consumables[0].quantity===2 && read().party[0].consumables[0].characteristic==='agility','potion facts editable without simulation');
  document.querySelector('[data-action="add-consumables"]').click();quantity=document.querySelector('[data-path="party/0/consumables/1/quantity"]');quantity.value='3';quantity.dispatchEvent(new Event('change'));
  document.querySelector('[data-action="add-consumables"]').click();kind=document.querySelector('[data-path="party/0/consumables/2/kind"]');kind.value='enhancement_potion';kind.dispatchEvent(new Event('change'));
  attribute=document.querySelector('[data-path="party/0/consumables/2/characteristic"]');attribute.value='ballistic_skill';attribute.dispatchEvent(new Event('change'));
  const cards=[...document.querySelectorAll('#request-visual .consumable-item')],headers=cards.map(c=>c.querySelector('[data-path$="/quantity"]').getBoundingClientRect());
  check(cards.length===3 && cards.every(c=>!c.querySelector('h5') && getComputedStyle(c).borderTopWidth==='0px') && headers.every(r=>Math.abs(r.left-headers[0].left)<1 && Math.abs(r.width-headers[0].width)<1),'mixed potions keep quantity aligned without nested headings or boxes');
  const potionSnapshot=canonical(read().party[0].consumables);byId('request-json-tab').click();byId('request-visual-tab').click();check(canonical(read().party[0].consumables)===potionSnapshot,'mixed quantities and effects survive JSON switch');
  document.querySelector('[data-path="party/0/consumables/1"]').click();check(read().party[0].consumables[0].quantity===2 && read().party[0].consumables[1].characteristic==='ballistic_skill','removing one consumable preserves other cards');
  document.querySelector('[data-path="party/0/consumables/1"]').click();document.querySelector('[data-path="party/0/consumables/0"]').click();
  const autoSpace=document.querySelector('[data-path="automatic-npc-space"]'),autoSpaceLabel=autoSpace.parentElement;check(autoSpaceLabel.getBoundingClientRect().top-autoSpaceLabel.previousElementSibling.getBoundingClientRect().bottom>=12,'automatic NPC ranges checkbox is separated from section heading');autoSpace.checked=true;autoSpace.dispatchEvent(new Event('change'));
  check(read().search_space===null && !document.querySelector('[data-path="search_space/strength"]'),'automatic space hides manual ranges');
  const automaticSource=read();check(planningSearchSpace(automaticSource).strength.includes(automaticSource.party[0].characteristics.strength),'planning envelope follows party');
  const manualSpace=document.querySelector('[data-path="automatic-npc-space"]');manualSpace.checked=false;manualSpace.dispatchEvent(new Event('change'));
  check(read().search_space.strength.length>0,'optional manual constraints can be enabled');
  byId('request-json-tab').click();check(!byId('request').classList.contains('hidden'),'JSON request tab');
  const edited=read();edited.party[0].characteristics.toughness+=1;byId('request').value=pretty(edited);byId('request').dispatchEvent(new Event('input'));
  byId('request-visual-tab').click();check(document.querySelector('[data-path="party/0/characteristics/toughness"]').value===String(edited.party[0].characteristics.toughness),'JSON edit visible in card');
  stat=document.querySelector('[data-path="search_space/strength"]');stat.value='2, 4';stat.dispatchEvent(new Event('change'));
  check(JSON.stringify(read().search_space.strength)==='[2,4]','editable search space');
  const beforeToggle=canonical(read());byId('request-json-tab').click();byId('request-visual-tab').click();check(canonical(read())===beforeToggle,'lossless mode switch');
  check(byId('win').value==='60','JSON to form');
  byId('seed').value='9007199254740993';byId('seed').dispatchEvent(new Event('change'));
  check(read().search.master_seed==='9007199254740993','seed precision');
  byId('win').value='37.5';byId('win').dispatchEvent(new Event('change'));
  check(JSON.stringify(read().targets.win_rate)==='{"numerator":3,"denominator":8}','percentage fraction');
  check(JSON.stringify(read().party)===JSON.stringify(edited.party),'unrelated party preserved');
  byId('rounds').value='1.5';byId('rounds').dispatchEvent(new Event('change'));
  check(read().targets.started_rounds.numerator===3 && read().targets.started_rounds.denominator===2,'round fraction');
  const data=read();data.search.max_candidates=2;data.search.exploration_trials=1;
  data.search.top_k=1;data.search.finalist_trials=1;
  byId('request').value=pretty(data);byId('request').dispatchEvent(new Event('input'));
  check(byId('candidates').value==='2','edited JSON to form');
  byId('request').dispatchEvent(new Event('blur'));check(read().search.max_total_trials===3,'automatic budget even in manual mode');
  byId('request-json-tab').click();check(!byId('format').classList.contains('hidden'),'request formatter only in JSON');byId('format').click();JSON.parse(byId('request').value);byId('request-visual-tab').click();
  let generated=0;const realFetch=window.fetch;window.fetch=(url,...args)=>{if(url==='/api/generate')generated++;return realFetch(url,...args);};
  const running=run();check(byId('request').readOnly && byId('run').disabled && byId('run').classList.contains('hidden') && !byId('cancel').classList.contains('hidden'),'cancel replaces launch while busy');check(hoverChanges(byId('cancel')),'active cancel button has hover feedback');await running;
  const result=JSON.parse(byId('result').textContent);
  check(result.total_trials===3 && result.explored.length===2,'real generation');
  check(result.source_request.search.master_seed==='9007199254740993','full source echo');
  check(!byId('download').disabled && !byId('request').readOnly,'completed state');
  check(hoverChanges(byId('download')),'enabled download has hover feedback');
  const exportNames=[],anchorClick=HTMLAnchorElement.prototype.click,sourceBeforeExport=canonical(read());
  try{HTMLAnchorElement.prototype.click=function(){exportNames.push(this.download);};byId('save').click();byId('save').click();byId('download').click();[...document.querySelectorAll('#result-visual .result-card button')].find(button=>button.textContent==='Скачать бой').click();}finally{HTMLAnchorElement.prototype.click=anchorClick;}
  check(exportNames.length===4 && new Set(exportNames).size===4 && exportNames.every(name=>/^encounter-(request|result|replay)_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z_[0-9a-f]{8}\.json$/.test(name)),'request result and replay exports receive unique dated filenames');
  check(canonical(read())===sourceBeforeExport,'export filename uniqueness does not change source or seed');
  check(document.querySelector('#result-visual .result-card') && generated===1,'visual result with one explicit run');
  const beforeInvalid=byId('request').value;stat=document.querySelector('[data-path="search_space/strength"]');stat.value='bad';stat.dispatchEvent(new Event('change'));await run();
  check(generated===1 && byId('request').value===beforeInvalid,'invalid card value blocks run without corrupting JSON');
  byId('request-json-tab').click();byId('request-visual-tab').click();
  const originalResult=canonical(result);byId('result-json-tab').click();check(!byId('result').classList.contains('hidden'),'JSON result tab');byId('result-visual-tab').click();
  stat=document.querySelector('[data-path="party/0/characteristics/strength"]');stat.value=String(read().party[0].characteristics.strength+1);stat.dispatchEvent(new Event('change'));
  check(!byId('result-stale').classList.contains('hidden'),'stale notice after visual edit');
  check(generated===1 && canonical(JSON.parse(byId('result').textContent))===originalResult,'no automatic generation or metric edits');
  const changedSource=read();byId('request').value=pretty(result.source_request);syncForm();
  check(byId('result-stale').classList.contains('hidden') && generated===1,'restoring source clears stale without run');
  byId('request').value=pretty(changedSource);syncForm();
  document.querySelector('#result-visual .result-card button').click();
  check(read().npc_count.minimum===result.validations[0].npcs.length && generated===1,'copy composition without run');
  await run();check(generated===2 && byId('result-stale').classList.contains('hidden'),'explicit rerun clears stale notice');
  const repeated=canonical(JSON.parse(byId('result').textContent));await run();
  check(generated===3 && canonical(JSON.parse(byId('result').textContent))===repeated,'same seed and request reproduce result without reseeding');
  const liveFetch=window.fetch;let completeGeneration,token;
  window.fetch=(url,options)=>{
   if(url==='/api/generate'){token=options.headers['X-TOWR-Run-ID'];return new Promise(resolve=>{completeGeneration=resolve;});}
   if(url==='/api/cancel'){check(options.headers['X-TOWR-Run-ID']===token,'cancel is bound to active run');return Promise.resolve(new Response('{"cancel_requested":true}',{status:202}));}
   return liveFetch(url,options);
  };
  const cancelledRun=run();check(!byId('cancel').disabled && busy,'cancel enabled while running');await cancelGeneration();
  check(cancelling && byId('cancel').disabled,'waiting for server cancellation');
  completeGeneration(new Response('{"kind":"dynamic_encounter_cancelled"}',{status:200}));await cancelledRun;
  check(!busy && !byId('run').disabled && byId('cancel').disabled && byId('download').disabled && !byId('run').classList.contains('hidden') && byId('cancel').classList.contains('hidden'),'cancel unlocks UI and restores launch without partial result');
  check(byId('result').textContent.includes('отменена'),'cancellation shown in both views');
  window.fetch=liveFetch;await run();check(canonical(JSON.parse(byId('result').textContent))===repeated,'restart after cancel preserves seed and result');
  const savedRequest=byId('request').value,reportBeforeLoad=canonical(lastResult),runsBeforeLoad=generated;
  await byId('file').onchange({target:{files:[new File([savedRequest],'saved-request.json')],value:''}});
  check(canonical(read())===canonical(JSON.parse(savedRequest)) && canonical(lastResult)===reportBeforeLoad && generated===runsBeforeLoad,'request file import preserves report and does not generate');
  byId('request-json-tab').click();
  byId('request').value='{';await run();check(byId('status').className==='error','invalid JSON');
  byId('request-visual-tab').click();check(requestView==='json' && byId('request').value==='{','invalid JSON not overwritten by toggle');
  document.body.setAttribute('data-ui-check','passed');
 }catch(error){document.body.setAttribute('data-ui-check','failed');document.body.append(document.createTextNode('UI CHECK: '+error.stack));}
})();
</script>'''


@unittest.skipUnless(BROWSER, 'installed Edge/Chromium required')
class LocalUiBrowserTests(unittest.TestCase):
    def test_form_json_and_actual_generation_in_browser(self):
        initial = Path('docs/examples/dynamic/search.request.json').read_bytes()
        with patch('towr.adapters.local_ui.PAGE', PAGE.replace('</html>', CHECK + '</html>')):
            with LocalUiServer(0, initial) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with tempfile.TemporaryDirectory(prefix='towr-ui-browser-') as folder:
                        arguments = ['--headless=new', '--disable-gpu',
                            '--no-first-run', '--no-default-browser-check', '--dump-dom',
                            '--window-size=1400,1100',
                            '--virtual-time-budget=15000', '--timeout=30000',
                            '--user-data-dir=' + str(Path(folder)/'profile'), f'http://127.0.0.1:{server.server_port}/']
                        if os.name == 'nt':
                            # Edge's Windows launcher exits before its browser
                            # child. Start-Process -Wait waits for the process tree.
                            quote = lambda value: "'" + value.replace("'", "''") + "'"
                            output, errors = Path(folder)/'dom.txt', Path(folder)/'errors.txt'
                            script = (f'$p = Start-Process -FilePath {quote(BROWSER)} '
                                f'-ArgumentList {quote(subprocess.list2cmdline(arguments))} '
                                f'-WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput {quote(str(output))} '
                                f'-RedirectStandardError {quote(str(errors))}; exit $p.ExitCode')
                            result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                                capture_output=True, timeout=45)
                            dom = output.read_text(encoding='utf-8')
                        else:
                            result = subprocess.run([BROWSER, *arguments], capture_output=True, timeout=45)
                            dom = result.stdout.decode('utf-8', errors='replace')
                        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                        self.assertTrue('data-ui-check="passed"' in dom, dom[-2200:])
                finally:
                    server.shutdown()
                    thread.join(5)


if __name__ == '__main__':
    unittest.main()
