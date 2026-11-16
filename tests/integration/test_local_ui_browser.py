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
 if(window.parent!==window)return;
 function check(value,message){if(!value)throw Error(message);}
 try{
  while(!byId('request').value)await new Promise(resolve=>setTimeout(resolve,50));
  const original=read();check(original.kind==='dynamic_encounter_search','initial request');
  const beforeWizard=canonical(read());
  let wizardEntry=document.querySelector('[data-role="talent-entry"][data-member="0"]');wizardEntry.value='wizard';wizardEntry.dispatchEvent(new Event('input'));document.querySelector('#talent-options-0 [role="option"]').click();
  check(read().party[0].talents.includes('wizard') && read().party[0].magic.wizard_level===1 && read().party[0].magic.memorised_spells.join(',')==='lightning_blast','Wizard tag creates explicit visible magic facts');
  const reason=document.querySelector('[data-path="party/0/characteristics/reason"]'),willpower=document.querySelector('[data-path="party/0/skills/willpower"]');check(reason && !reason.disabled && willpower && !willpower.disabled && reason.title.includes('(Reason)') && willpower.title.includes('(Willpower)'),'wizard activates real Reason and Willpower fields');
  let wizardLevel=document.querySelector('[data-path="party/0/magic/wizard_level"]');wizardLevel.value='4';wizardLevel.dispatchEvent(new Event('change'));
  let breath=document.querySelector('[data-spell="fire_breath"][data-member="0"]');breath.checked=true;breath.dispatchEvent(new Event('change'));check(read().party[0].magic.wizard_level===4 && read().party[0].magic.memorised_spells.length===2,'wizard rank and known spells are editable facts');
  let kit=document.querySelector('[data-path="party/0/magic/arcane_paraphernalia"]');kit.checked=false;kit.dispatchEvent(new Event('change'));check(!read().party[0].magic.arcane_paraphernalia && byId('request-visual').textContent.includes('импровизированный комплект пока не поддержан'),'missing magical kit remains an explicit unsupported draft');
  const wizardDraft=canonical(read());byId('request-json-tab').click();byId('request-visual-tab').click();check(canonical(read())===wizardDraft,'wizard facts survive JSON and card switching');
  document.querySelector('[aria-label="Удалить талант Маг (Wizard)"]').click();check(canonical(read())===beforeWizard && !document.querySelector('[data-path="party/0/characteristics/reason"]') && !document.querySelector('[data-path="party/0/skills/willpower"]'),'removing Wizard restores nonmagical input without hidden magic fields');
  check(document.documentElement.dataset.theme===(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'),'initial theme follows system preference');setTheme('light');
  check(byId('theme-toggle').closest('.page-heading') && byId('theme-toggle').getBoundingClientRect().left>document.querySelector('h1').getBoundingClientRect().right,'theme switch at the upper right');
  check(getComputedStyle(byId('status')).display==='none' && !byId('status').textContent,'no routine status below launch button');
  const layout=()=>[document.documentElement.clientWidth,...[document.querySelector('main'),...document.querySelectorAll('.columns>.panel')].flatMap(element=>{const rect=element.getBoundingClientRect();return [rect.left,rect.width];})];
  const originalLayout=JSON.stringify(layout());byId('request-json-tab').click();byId('result-json-tab').click();check(JSON.stringify(layout())===originalLayout,'JSON view preserves main and panel horizontal positions');
  const jsonAligned=()=>Math.abs(byId('request').getBoundingClientRect().top-byId('result').getBoundingClientRect().top)<1;check(jsonAligned(),'request and result JSON share the same top edge');byId('result-stale').classList.remove('hidden');check(jsonAligned(),'JSON alignment survives stale notice');byId('result-stale').classList.add('hidden');
  const columns=document.querySelector('.columns');columns.style.width='900px';check(jsonAligned(),'JSON alignment survives wrapped headings and hints');columns.style.width='';byId('request-visual-tab').click();byId('result-visual-tab').click();check(JSON.stringify(layout())===originalLayout,'card view preserves viewport gutter and panel widths');
  // Evaluate the actual hover declarations through an equivalent forced-state
  // class, preserving specificity; dispatching mouse events does not set :hover.
  const hoverProbe=document.createElement('style');hoverProbe.textContent=[...document.styleSheets].flatMap(sheet=>[...sheet.cssRules]).filter(rule=>rule.selectorText?.includes(':hover')).map(rule=>rule.cssText.replaceAll(':hover','.ui-test-hover')).join('\n');document.head.append(hoverProbe);
  const buttonPaint=button=>{const style=getComputedStyle(button);return [style.backgroundColor,style.borderColor,style.color].join('|');};
  const hoverChanges=button=>{const before=buttonPaint(button);button.classList.add('ui-test-hover');const changed=buttonPaint(button)!==before;button.classList.remove('ui-test-hover');return changed;};
  for(const id of ['load','load-result','save','format','request-visual-tab','request-json-tab','result-visual-tab','result-json-tab','run'])check(hoverChanges(byId(id)),'hover styling for '+id);
  for(const id of ['load','load-result','save','format','request-visual-tab','request-json-tab','result-visual-tab','result-json-tab']){const button=byId(id);button.classList.add('ui-test-hover');check(getComputedStyle(button).color==='rgb(35, 91, 168)','blue hover feedback for '+id);button.classList.remove('ui-test-hover');}
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
  check(byId('format').classList.contains('hidden') && byId('format-result').classList.contains('hidden') && byId('load-result') && byId('result-file') && byId('format-result').disabled,'formatters hidden in cards; result upload available before calculation');
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
  check([...byId('request-visual').querySelectorAll('h4')].some(h=>h.textContent==='Характеристики (Characteristics)') && [...byId('request-visual').querySelectorAll('h4')].some(h=>h.textContent==='Навыки (Skills)'),'separate character and skill sections restored');
  const allCharacteristics=['weapon_skill','ballistic_skill','strength','toughness','initiative','agility','reason','fellowship'],allSkills=['melee','defence','shooting','throwing','brawn','toil','survival','endurance','awareness','dexterity','athletics','stealth','willpower','recall','leadership','charm'];
  const statInputs=[...document.querySelectorAll('#request-visual .character-stats input')];check(statInputs.length===24*read().party.length && statInputs.every(input=>Math.abs(input.getBoundingClientRect().width-input.parentElement.getBoundingClientRect().width)<1 && input.getBoundingClientRect().height===36),'stat inputs fill their grid columns');
  const placeholders=statInputs.filter(input=>input.classList.contains('stat-placeholder'));check(placeholders.length===16*read().party.length && placeholders.every(input=>input.disabled && input.value==='—' && !input.hasAttribute('data-path')),'unsupported request stats are disabled placeholders without source bindings');
  check(Object.keys(read().party[0].characteristics).length===4 && Object.keys(read().party[0].skills).length===4,'placeholders do not add unsupported fields to request JSON');
  const singleLineLabels=parent=>[...parent.querySelectorAll('.character-stats label')].every(label=>{const range=document.createRange();range.selectNodeContents(label.firstChild);return range.getClientRects().length===1 && range.getBoundingClientRect().width<=label.getBoundingClientRect().width+1;});
  check(singleLineLabels(byId('request-visual')),'all Characteristic and Skill names fit on one line');
  const narrowPlayer=document.querySelector('.player-card');narrowPlayer.style.width='260px';check([...narrowPlayer.querySelectorAll('.character-stats input')].every(input=>input.getBoundingClientRect().right<=narrowPlayer.getBoundingClientRect().right),'book pairs fit narrow cards without horizontal overflow');narrowPlayer.style.width='';
  check(document.querySelector('[data-path="party/0/characteristics/strength"]').parentElement.textContent.includes('(S)') && document.querySelector('[data-path="party/0/skills/defence"]').parentElement.textContent.includes('(Defence)'),'only official Characteristic abbreviations; full Skill originals');
  check([characteristicNames,weaponNames,armourNames,consumableNames].every(names=>Object.values(names).every(name=>/\([^)]+\)$/.test(name))),'book term choices include original names or established abbreviations');
  check(characteristicNames.weapon_skill.endsWith('(WS)') && characteristicNames.ballistic_skill.endsWith('(BS)'),'established original abbreviations are used');
  check(characteristicNames.strength.endsWith('(S)') && characteristicNames.agility.endsWith('(Ag)') && characteristicNames.reason.endsWith('(Re)') && characteristicNames.fellowship.endsWith('(Fel)') && statLabels.melee.endsWith('(Melee)') && statLabels.endurance.endsWith('(Endurance)'),'official Characteristic abbreviations and unabridged Skills');
  const reversed=JSON.parse(JSON.stringify(read()));for(const section of ['characteristics','skills'])reversed.party[0][section]=Object.fromEntries(Object.entries(reversed.party[0][section]).reverse());byId('request').value=pretty(reversed);syncForm();
  check([...document.querySelectorAll('.player-card:first-child .character-stats input[data-path]')].map(input=>input.dataset.path.split('/').at(-1)).join(',')==='weapon_skill,strength,toughness,agility,melee,defence,endurance,athletics','separate fields retain book order despite reordered JSON keys');
  check([...document.querySelectorAll('.player-card:first-child .character-stats input')].map(input=>input.dataset.stat||input.dataset.path.split('/').at(-1)).join(',')===[...allCharacteristics,...allSkills].join(','),'all request placeholders follow book order');
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
  const talentTag=document.querySelector('.talent-tag');check(!talentTag.hasAttribute('title') && talentTag.dataset.tooltip.includes('Судьбы'),'talent tag uses custom hint');talentTag.focus({preventScroll:true});check(!byId('tag-tooltip').hidden && byId('tag-tooltip').textContent===talentTag.dataset.tooltip && talentTag.getAttribute('aria-describedby')==='tag-tooltip','keyboard focus opens an accessible tag tooltip');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));check(byId('tag-tooltip').hidden,'Escape dismisses tag tooltip');talentTag.blur();
  const tagAppearance=tag=>{const style=getComputedStyle(tag);return [tag.getBoundingClientRect().height,style.fontSize,style.lineHeight,style.borderRadius].join('|');},talentTagAppearance=tagAppearance(talentTag);check(talentTag.getBoundingClientRect().height===26,'removable talent tag uses compact result tag height');
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
  talent=document.querySelector('[data-role="talent-entry"][data-member="0"]');talent.value='lucky';talent.dispatchEvent(new Event('input'));talent.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));check(read().party[0].talents.length===1,'duplicate tag prevented');
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
  check(document.querySelector('[data-path="search_space/defence"]') && document.querySelectorAll('[data-path^="search_space/weapon/"]').length===6 && document.querySelectorAll('[data-path^="search_space/shield/"]').length===2,'generated equipment has Defence, six weapons and independent Shield choices');
  check(planningSearchSpace(automaticSource).weapon.join(',')==='staff,dagger,axe,sword,warhammer,morning_star' && planningSearchSpace(automaticSource).shield.join(',')==='false,true','client automatic envelope includes the complete equipment chunk');
  check(document.querySelectorAll('[data-path^="search_space/allowed_talents/"]').length===3 && planningSearchSpace(automaticSource).allowed_talents.join(',')==='magic_resistance,defensive_stance,wild_attack','generated talents are permitted components, not prewritten subsets');
  for(const talent of ['magic_resistance','defensive_stance','wild_attack']){const box=document.querySelector('[data-path="search_space/allowed_talents/'+talent+'"]');box.checked=false;box.dispatchEvent(new Event('change'));}check(read().search_space.allowed_talents.length===0 && automaticSearchPlan(read()).max_candidates>=1,'empty permitted talents is a valid search space');
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
  check([...document.querySelectorAll('#request-visual .stat-placeholder')].every(input=>input.disabled),'request placeholders remain disabled after generation unlocks editing');
  check(byId('progress-phase').textContent.includes('Готово') && Number(byId('progress-bar').value)===result.total_trials && progressRunId===null,'completed generation closes polling and shows actual total');
  check(hoverChanges(byId('download')),'enabled download has hover feedback');
  check(!byId('summary') && !byId('result-visual').textContent.includes('Seed расчёта:') && !byId('result-visual').textContent.includes('Проверенные финалисты'),'result omits global candidate seed and finalist summaries');
  const composition=document.querySelector('#result-visual>.result-card'),candidate=result.validations[0],blocks=[...composition.children];
  check(blocks[0].classList.contains('result-statistics') && blocks.slice(1).every(block=>block.classList.contains('npc-card')) && blocks.length===candidate.npcs.length+1,'statistics block followed by individual opponents');
  check(byId('result-card-heading').querySelector('h3').getBoundingClientRect().left===composition.querySelector('.result-statistics').getBoundingClientRect().left && byId('result-card-heading').querySelector('[data-action="download-replay"]').getBoundingClientRect().right===composition.querySelector('.result-statistics').getBoundingClientRect().right,'composition title and download align with outer block edges');
  const cardsAligned=()=>Math.abs(document.querySelector('#request-visual>.player-card').getBoundingClientRect().top-document.querySelector('#result-visual>.result-card>.result-statistics').getBoundingClientRect().top)<1;
  check(cardsAligned(),'player and result statistics card top borders align');byId('result-stale').classList.remove('hidden');check(cardsAligned(),'card alignment survives stale notice');byId('result-stale').classList.add('hidden');columns.style.width='900px';check(cardsAligned(),'card alignment survives wrapping');columns.style.width='';
  setRequestView('json');setResultView('json');check(jsonAligned() && getComputedStyle(byId('result-card-heading')).visibility==='hidden' && byId('result-card-heading').inert,'JSON alignment preserved; heading hidden and unfocusable while keeping its space');setRequestView('visual');setResultView('visual');check(cardsAligned() && getComputedStyle(byId('result-card-heading')).visibility==='visible','card alignment preserved after view toggles');
  for(const stale of [false,true]){byId('result-stale').classList.toggle('hidden',!stale);for(const width of ['', '900px']){columns.style.width=width;let expectedTop=null;for(const left of ['visual','json'])for(const right of ['visual','json']){setRequestView(left);setResultView(right);byId('result-stale').classList.toggle('hidden',!stale);const a=(left==='json'?byId('request'):document.querySelector('#request-visual>.player-card')).getBoundingClientRect().top,b=(right==='json'?byId('result'):document.querySelector('#result-visual>.result-card>.result-statistics')).getBoundingClientRect().top;check(Math.abs(a-b)<1,'cards and JSON align in every mixed view');if(expectedTop===null)expectedTop=a;check(Math.abs(a-expectedTop)<1,'view switches preserve content top even with stale notice');}}}columns.style.width='';byId('result-stale').classList.add('hidden');setRequestView('visual');setResultView('visual');
  check(typeof useComposition==='undefined' && !document.querySelector('[data-action="use-composition"]'),'composition copy feature removed');
  for(const [index,creature] of [...composition.querySelectorAll('.npc-card')].entries()){
   const tables=creature.querySelectorAll('table');check(tables.length===2 && tables[0].caption.textContent==='Характеристики (Characteristics)' && tables[1].caption.textContent==='Навыки (Skills)','separate result stat tables restored');
   for(const [tableIndex,keys] of [allCharacteristics,allSkills].entries()){const cells=[...tables[tableIndex].querySelectorAll('td')];check(cells.map(cell=>cell.dataset.stat).join(',')===keys.join(','),'all book fields remain in order');for(const [i,cell] of cells.entries()){const value=candidate.npcs[index][keys[i]];check(cell.textContent===String(value??'—') && cell.classList.contains('unavailable')===(value==null),'source values preserved and unavailable stats use a placeholder');check(document.getElementById(cell.getAttribute('headers'))?.tagName==='TH','stat value associated with its label');}}
   const labels=[...creature.querySelectorAll('dt')].map(label=>label.textContent);check(labels.includes('Оружие (Weapons)') && labels.includes('Броня (Armour)') && labels.includes('Расходники (Consumables)') && labels.includes('Таланты (Talents)'),'loadout and future consumable talent slots');
   check(creature.querySelectorAll('.npc-loadout dd>.item-tags').length>=4 && [...creature.querySelectorAll('.item-tag')].every(tag=>tag.dataset.tooltip && !tag.hasAttribute('title') && tag.tabIndex===0),'loadout tags use custom keyboard-accessible hints without native titles');
   check(creature.querySelector('.item-tag').dataset.tooltip.includes('Damage') && creature.querySelectorAll('.item-tag.empty').length>=2,'weapon tag explains its profile and placeholders have tags');
  }
  check(tagAppearance(composition.querySelector('.item-tag'))===talentTagAppearance && [...composition.querySelectorAll('.item-tag')].every(tag=>tag.getBoundingClientRect().height===26),'result and request talent tags share height typography and radius');
  window.scrollTo(0,0);await new Promise(resolve=>setTimeout(resolve,100));const hoveredTag=composition.querySelector('.item-tag');hoveredTag.dispatchEvent(new PointerEvent('pointerenter'));await new Promise(resolve=>setTimeout(resolve,150));check(!byId('tag-tooltip').hidden && byId('tag-tooltip').textContent===hoveredTag.dataset.tooltip,'custom hover tooltip appears promptly');
  const hintRect=byId('tag-tooltip').getBoundingClientRect();check(hintRect.left>=0 && hintRect.right<=innerWidth && hintRect.top>=0 && hintRect.bottom<=innerHeight,'tooltip stays inside viewport');hoveredTag.dispatchEvent(new PointerEvent('pointerleave',{relatedTarget:byId('tag-tooltip')}));byId('tag-tooltip').dispatchEvent(new PointerEvent('pointerenter'));await new Promise(resolve=>setTimeout(resolve,150));check(!byId('tag-tooltip').hidden,'tooltip remains available while pointer moves onto it');byId('tag-tooltip').dispatchEvent(new PointerEvent('pointerleave'));check(byId('tag-tooltip').hidden,'tooltip closes after leaving tag and hint');
  const replayButton=byId('result-card-heading').querySelector('[data-action="download-replay"]');check(byId('result-card-heading').querySelectorAll('button').length===1 && replayButton.textContent==='' && replayButton.querySelector('svg') && replayButton.getAttribute('aria-label') && replayButton.title,'only accessible replay icon remains');check(replayButton.getBoundingClientRect().height===byId('download').getBoundingClientRect().height && buttonPaint(replayButton)===buttonPaint(byId('download')) && hoverChanges(replayButton),'replay icon shares existing size styling and hover');
  const duplicate=JSON.parse(JSON.stringify(candidate));duplicate.npcs=[candidate.npcs[0],candidate.npcs[0]];renderResultVisual({...result,validations:[duplicate],explored:[]});check(document.querySelectorAll('#result-visual>.result-card>.npc-card').length===2,'identical opponents remain separate cards');renderResultVisual(result);
  const talentPreview=JSON.parse(JSON.stringify(result));talentPreview.validations=[{...talentPreview.validations[0],npcs:[{...candidate.npcs[0],weapon_skill:4,strength:4,talents:['magic_resistance','defensive_stance','wild_attack']}]}];talentPreview.explored=[];const talentRoot=node('div');renderResultVisual(talentPreview,talentRoot);for(const title of ['Magic Resistance','Defensive Stance','Wild Attack'])check([...talentRoot.querySelectorAll('.item-tag')].some(tag=>tag.textContent.includes(title) && tag.dataset.tooltip),'real NPC talent tags have descriptive custom tooltips');
  const equipmentPreview=JSON.parse(JSON.stringify(result));equipmentPreview.validations=[{...equipmentPreview.validations[0],npcs:['axe','sword','warhammer','morning_star'].map(weapon=>({...candidate.npcs[0],weapon,defence:6,shield:true,light_armour:true}))}];equipmentPreview.explored=[];const previewRoot=node('div');renderResultVisual(equipmentPreview,previewRoot);check(previewRoot.querySelectorAll('.npc-card').length===4 && [...previewRoot.querySelectorAll('.npc-card')].every(card=>card.querySelector('[data-stat="defence"]').textContent==='6' && [...card.querySelectorAll('.item-tag')].some(tag=>tag.textContent.includes('Shield') && tag.dataset.tooltip.includes('+1 Resilience'))),'generated Defence and Shield are real result fields and tags');for(const [index,word] of ['armoured','Defence','Staggered','−1d'].entries())check(previewRoot.querySelectorAll('.npc-card')[index].querySelector('.item-tag').dataset.tooltip.includes(word),'each new weapon has its actual Trait tooltip');
  const removedTag=document.querySelector('#result-visual .item-tag');removedTag.focus({preventScroll:true});renderResultVisual(result);check(byId('tag-tooltip').hidden,'rerender clears a tooltip whose tag was replaced');
  showTagTooltip(document.querySelector('#result-visual .item-tag'));setResultView('json');check(byId('tag-tooltip').hidden,'switching away from cards clears tag tooltip');setResultView('visual');
  document.querySelector('#result-visual .item-tag').dispatchEvent(new PointerEvent('pointerenter'));renderResultVisual(result);await new Promise(resolve=>setTimeout(resolve,150));check(byId('tag-tooltip').hidden,'replaced tags cannot show delayed stale tooltips');
  const themeSource=canonical(read()),themeReport=canonical(lastResult);byId('theme-toggle').click();
  check(document.documentElement.dataset.theme==='dark' && byId('theme-toggle').getAttribute('aria-pressed')==='true' && localStorage.getItem('towr-ui-theme')==='dark','theme switch persists dark preference');
  for(const selector of ['body','.panel','.visual-card','input','select','textarea','pre','.item-tag','.talent-suggestions']){const element=document.querySelector(selector);if(element)check(luminance(getComputedStyle(element).backgroundColor)<.15,'dark surface for '+selector);}
  for(const selector of ['body','input','.npc-stat-table th','.item-tag:not(.empty)','.badge','#run']){const element=document.querySelector(selector),style=getComputedStyle(element),a=luminance(style.color),b=luminance(background(element));check((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,'readable dark contrast for '+selector);}
  for(const selector of ['.action-add','.action-remove']){const button=document.querySelector(selector);button.classList.add('ui-test-hover');const style=getComputedStyle(button),a=luminance(style.color),b=luminance(background(button));check((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,'dark action hover contrast');button.classList.remove('ui-test-hover');}
  async function reopenedTheme(){const frame=document.createElement('iframe');frame.style.cssText='position:fixed;left:-10000px;width:400px;height:400px';frame.src='/';await new Promise(resolve=>{frame.onload=resolve;document.body.append(frame);});await new Promise(resolve=>setTimeout(resolve,100));const inside=frame.contentDocument,panels=[...inside.querySelectorAll('.columns>.panel')].map(panel=>panel.getBoundingClientRect());check(panels[0].left===panels[1].left && panels[1].top>=panels[0].bottom && panels.every(panel=>panel.right<=frame.contentWindow.innerWidth),'mobile viewport stacks panels without an implicit second column');const state={theme:inside.documentElement.dataset.theme,system:frame.contentWindow.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'};frame.remove();return state;}
  check((await reopenedTheme()).theme==='dark','saved theme restored on a new page');localStorage.removeItem('towr-ui-theme');const systemPage=await reopenedTheme();check(systemPage.theme===systemPage.system,'system theme used without saved preference');
  const store=Storage.prototype.setItem;try{Storage.prototype.setItem=function(){throw Error('storage unavailable');};byId('theme-toggle').click();check(document.documentElement.dataset.theme==='light','theme toggle works when storage is blocked');}finally{Storage.prototype.setItem=store;}
  check(canonical(read())===themeSource && canonical(lastResult)===themeReport && generated===1,'theme does not edit request report or launch generation');
  const exportNames=[],anchorClick=HTMLAnchorElement.prototype.click,sourceBeforeExport=canonical(read());
  try{HTMLAnchorElement.prototype.click=function(){exportNames.push(this.download);};byId('save').click();byId('save').click();byId('download').click();byId('result-card-heading').querySelector('[data-action="download-replay"]').click();}finally{HTMLAnchorElement.prototype.click=anchorClick;}
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
  await run();check(generated===2 && byId('result-stale').classList.contains('hidden'),'explicit rerun clears stale notice');
  const repeated=canonical(JSON.parse(byId('result').textContent));await run();
  check(generated===3 && canonical(JSON.parse(byId('result').textContent))===repeated,'same seed and request reproduce result without reseeding');
  const liveFetch=window.fetch;let completeGeneration,token,progressReply,failProgress=false;
  window.fetch=(url,options)=>{
   if(url==='/api/generate'){token=options.headers['X-TOWR-Run-ID'];return new Promise(resolve=>{completeGeneration=resolve;});}
   if(url==='/api/cancel'){check(options.headers['X-TOWR-Run-ID']===token,'cancel is bound to active run');return Promise.resolve(new Response('{"cancel_requested":true}',{status:202}));}
   if(url==='/api/progress'){check(options.headers['X-TOWR-Run-ID']===token,'progress is bound to active run');return failProgress?Promise.reject(Error('temporary status outage')):Promise.resolve(new Response(JSON.stringify(progressReply),{status:200}));}
   return liveFetch(url,options);
  };
  const cancelledRun=run();check(!byId('cancel').disabled && busy && !byId('generation-progress').classList.contains('hidden'),'cancel and progress enabled while running');
  const baseProgress={stage:'explore',candidate_number:1,candidate_count:2,npc_count:2,completed_trials:0,trial_count:0,total_completed_trials:0,trial_budget:3,wins:0,unsupported_trials:0};
  const nextProgress=async()=>{clearTimeout(progressTimer);progressTimer=null;await pollGenerationProgress(token);};
  progressReply={kind:'dynamic_encounter_progress',run_id:token,state:'running',sequence:1,current:{...baseProgress,phase:'generating'},last_candidate:null};await nextProgress();
  check(byId('progress-phase').textContent.includes('Создаём состав 1 из 2'),'generation phase is shown');
  progressReply={...progressReply,sequence:2,current:{...baseProgress,phase:'simulating',completed_trials:1,trial_count:1,total_completed_trials:1,wins:1}};await nextProgress();
  check(byId('progress-observation').textContent.includes('1/1') && byId('progress-observation').textContent.includes('100,0%') && byId('progress-observation').textContent.includes('предварительно') && Number(byId('progress-bar').value)===1,'completed trials and provisional win percentage are displayed');
  failProgress=true;await nextProgress();check(busy && Number(byId('progress-bar').value)===1,'missed progress request does not interrupt generation');failProgress=false;
  const completedCandidate={...progressReply.current,phase:'candidate_complete'};
  progressReply={...progressReply,sequence:3,current:{...baseProgress,phase:'generating',candidate_number:2,total_completed_trials:1},last_candidate:completedCandidate};await nextProgress();
  check(!byId('progress-last').classList.contains('hidden') && byId('progress-last').textContent.includes('100,0%'),'previous assessment survives next composition generation');
  progressReply={...progressReply,sequence:4,current:{...baseProgress,phase:'simulating',stage:'validate',candidate_number:1,candidate_count:1,trial_count:1,total_completed_trials:2}};await nextProgress();
  check(byId('progress-phase').textContent.includes('Независимая проверка') && byId('progress-observation').textContent.includes('0/1'),'independent validation resets per-candidate observations');
  const currentPhase=byId('progress-phase').textContent;renderGenerationProgress({...progressReply,sequence:2,current:{...baseProgress,phase:'generating'}});renderGenerationProgress({...progressReply,sequence:99,run_id:'stale-run'});check(byId('progress-phase').textContent===currentPhase,'stale sequence and foreign run cannot overwrite current progress');
  await cancelGeneration();
  check(cancelling && byId('cancel').disabled,'waiting for server cancellation');
  completeGeneration(new Response('{"kind":"dynamic_encounter_cancelled"}',{status:200}));await cancelledRun;
  check(!busy && !byId('run').disabled && byId('cancel').disabled && byId('download').disabled && !byId('run').classList.contains('hidden') && byId('cancel').classList.contains('hidden'),'cancel unlocks UI and restores launch without partial result');
  check(byId('result').textContent.includes('отменена'),'cancellation shown in both views');
  check(progressRunId===null && byId('progress-phase').textContent.includes('отменена'),'cancelled generation closes progress polling');renderGenerationProgress(progressReply);check(byId('progress-phase').textContent.includes('отменена'),'late progress cannot replace terminal cancellation');
  check(byId('progress-observation').textContent==='' && byId('progress-last').classList.contains('hidden'),'cancel clears provisional per-candidate observations');
  // Completion can arrive between polls: replace an old exploration prefix
  // with the actual validation assessment rather than leaving stale odds.
  busy=true;activeRunId='finish-between-polls';startGenerationProgress(activeRunId);renderGenerationProgress({...progressReply,run_id:activeRunId,sequence:1,current:{...baseProgress,phase:'simulating',completed_trials:1,trial_count:12,total_completed_trials:1,wins:1}});
  finishGenerationProgress(activeRunId,'complete',result);busy=false;activeRunId=null;
  check(!byId('progress-observation').textContent.includes('предварительно') && !byId('progress-observation').textContent.includes('1/12') && byId('progress-last').classList.contains('hidden') && Number(byId('progress-bar').max)===result.total_trials,'final result replaces stale partial observations and completes the bar');
  busy=true;activeRunId='finish-without-recommendation';startGenerationProgress(activeRunId);finishGenerationProgress(activeRunId,'complete',{...result,selected:[],validations:[]});busy=false;activeRunId=null;
  check(byId('progress-observation').textContent.includes('не найден'),'completion without eligible finalists does not invent a win estimate');
  window.fetch=liveFetch;await run();check(canonical(JSON.parse(byId('result').textContent))===repeated,'restart after cancel preserves seed and result');
  const savedRequest=byId('request').value,reportBeforeLoad=canonical(lastResult),runsBeforeLoad=generated;
  await byId('file').onchange({target:{files:[new File([savedRequest],'saved-request.json')],value:''}});
  check(canonical(read())===canonical(JSON.parse(savedRequest)) && canonical(lastResult)===reportBeforeLoad && generated===runsBeforeLoad,'request file import preserves report and does not generate');
  const compactReport=JSON.stringify(lastResult),sourceBeforeResultLoad=canonical(read());
  await byId('result-file').onchange({target:{files:[new File(['\uFEFF'+compactReport],'saved-result.json')],value:''}});
  check(byId('result').textContent===compactReport && canonical(lastResult)===reportBeforeLoad && canonical(read())===sourceBeforeResultLoad && generated===runsBeforeLoad,'result import renders saved report without editing source or generating');
  check(document.querySelector('#result-visual .npc-card') && byId('format-result').classList.contains('hidden') && !byId('download').disabled,'loaded result has cards and file controls');
  byId('result-json-tab').click();check(!byId('format-result').classList.contains('hidden') && !byId('format-result').disabled && hoverChanges(byId('format-result')),'result formatter available with hover in JSON only');byId('format-result').click();check(byId('result').textContent===pretty(lastResult) && canonical(lastResult)===reportBeforeLoad,'result formatting changes whitespace only');byId('result-visual-tab').click();check(byId('format-result').classList.contains('hidden'),'result formatter hides again in cards');
  const resultBeforeBadLoad=byId('result').textContent;
  for(const raw of ['{',savedRequest,JSON.stringify({...lastResult,validations:[{}]})]){await byId('result-file').onchange({target:{files:[new File([raw],'bad.json')],value:''}});check(byId('status').className==='error' && canonical(lastResult)===reportBeforeLoad && byId('result').textContent===resultBeforeBadLoad,'invalid result files preserve previous report');}
  const foreign=JSON.parse(compactReport);foreign.source_request.search.master_seed='42';await byId('result-file').onchange({target:{files:[new File([JSON.stringify(foreign)],'other-result.json')],value:''}});check(!byId('result-stale').classList.contains('hidden') && canonical(read())===sourceBeforeResultLoad && generated===runsBeforeLoad,'imported report from another request is marked stale without changing the request');await byId('result-file').onchange({target:{files:[new File([compactReport],'saved-result.json')],value:''}});check(byId('result-stale').classList.contains('hidden'),'matching report import clears stale notice');
  let finishFile;const pendingResultFile=byId('result-file').onchange({target:{files:[{text:()=>new Promise(resolve=>{finishFile=resolve;})}],value:''}});const afterImportRun=run();check(byId('load-result').disabled && byId('format-result').disabled && byId('result-file').disabled,'result file actions disabled during generation');await afterImportRun;finishFile(JSON.stringify({...JSON.parse(compactReport),request_id:'late-report'}));await pendingResultFile;check(canonical(lastResult)===reportBeforeLoad && generated===runsBeforeLoad+1,'late result file read cannot overwrite a newer generation');
  const profileSource=JSON.parse(JSON.stringify(read())),profileReport=canonical(lastResult),profileReportText=byId('result').textContent,profileRuns=generated,npcCandidate=lastResult.validations[0],npcKey='npc:'+npcCandidate.replay.scenario.id+':0',originalNpc=JSON.parse(JSON.stringify(npcCandidate.npcs[0]));
  const profileInput=key=>[...document.querySelectorAll('[data-character-file]')].find(input=>input.dataset.characterFile===key),loadProfile=async(key,text)=>profileInput(key).onchange({target:{files:[new File([text],'character.json')],value:''}});
  const profileExports=[],realDownload=download;download=(text,name)=>profileExports.push({text,name});
  try{
   await profileInput('player:0').parentElement.querySelector('[data-action="save-player"]').onclick();check(canonical(JSON.parse(profileExports.at(-1).text))===canonical(profileSource.party[0]) && profileExports.at(-1).name==='encounter-player.json','player export contains every source fact and no UI placeholders');
   await profileInput(npcKey).parentElement.querySelector('[data-action="save-npc"]').onclick();check(canonical(JSON.parse(profileExports.at(-1).text))===canonical(originalNpc) && profileExports.at(-1).name==='encounter-npc.json','NPC export contains the individual generated profile');
   const changedNpc={...originalNpc,strength:originalNpc.strength+1};await loadProfile(npcKey,JSON.stringify(changedNpc));
   check(document.querySelector('#result-visual>.result-card .npc-card [data-stat="strength"]').textContent===String(changedNpc.strength) && !byId('result-draft-notice').classList.contains('hidden'),'NPC import replaces one card in composition draft');
   check(canonical(lastResult)===profileReport && byId('result').textContent===profileReportText && canonical(read())===canonical(profileSource) && generated===profileRuns,'NPC draft does not modify report metrics JSON source or launch generation');
   check(document.querySelector('#result-visual>.result-card .draft-badge') && byId('result-card-heading').querySelector('[data-action="download-replay"]').disabled,'draft assessments are explicitly stale and original replay cannot masquerade as draft battle');
   await byId('result-file').onchange({target:{files:[new File(['{'],'bad-report.json')],value:''}});check(npcDrafts.size===1 && canonical(lastResult)===profileReport,'invalid full report import preserves open NPC draft');await byId('result-file').onchange({target:{files:[new File([profileReportText],'original-report.json')],value:''}});check(npcDrafts.size===0 && byId('result-draft-notice').classList.contains('hidden'),'new full report clears old NPC drafts');await loadProfile(npcKey,JSON.stringify(changedNpc));
   await profileInput(npcKey).parentElement.querySelector('[data-action="save-npc"]').onclick();check(canonical(JSON.parse(profileExports.at(-1).text))===canonical(changedNpc),'NPC download uses edited draft profile');setResultView('json');check(byId('result').textContent===profileReportText && !byId('result-draft-notice').classList.contains('hidden'),'JSON remains original with a visible draft explanation');setResultView('visual');
   await loadProfile(npcKey,JSON.stringify(originalNpc));check(npcDrafts.size===0 && byId('result-draft-notice').classList.contains('hidden') && !byId('result-card-heading').querySelector('[data-action="download-replay"]').disabled,'restoring original NPC clears stale draft and re-enables replay');
   await loadProfile(npcKey,JSON.stringify(changedNpc));byId('result-card-heading').querySelector('[data-action="reset-npc-draft"]').click();check(npcDrafts.size===0 && canonical(lastResult)===profileReport,'reset composition discards only its draft');
   const rich=JSON.parse(JSON.stringify(profileSource.party[0]));rich.actor_id='pc:imported';rich.equipment.weapons.push({id:'spare:granular',weapon:'glaive',location:'carried'});rich.equipment.armour.push({id:'heavy:granular',kind:'heavy_armour',location:'carried'});rich.consumables=[{id:'potion:granular',kind:'enhancement_potion',quantity:3,characteristic:'ballistic_skill'}];rich.talents=['lucky','Future talent'];
   await loadProfile('player:0','\uFEFF'+JSON.stringify(rich));check(canonical(read().party[0])===canonical(rich) && canonical(read().party.slice(1))===canonical(profileSource.party.slice(1)) && !byId('result-stale').classList.contains('hidden'),'player import preserves full unsupported inventory and marks report stale');
   await profileInput('player:0').parentElement.querySelector('[data-action="save-player"]').onclick();check(canonical(JSON.parse(profileExports.at(-1).text))===canonical(rich),'rich player file roundtrip retains gear consumables talents and Fate');
   for(const text of [JSON.stringify(originalNpc),'{',JSON.stringify({...rich,actor_id:profileSource.party[1].actor_id})]){await loadProfile('player:0',text);check(byId('status').className==='error' && canonical(read().party[0])===canonical(rich),'wrong invalid or duplicate-ID player files leave source intact');}
   await profileInput('player:0').onchange({target:{files:[{size:2*1024*1024+1,text:()=>{throw Error('oversize file must not be read');}}],value:''}});check(byId('status').textContent.includes('2 МиБ') && canonical(read().party[0])===canonical(rich),'oversized character file is rejected before reading');
   const newcomer={...rich,actor_id:'pc:added-from-file'};await loadProfile('player:add',JSON.stringify(newcomer));check(read().party.length===profileSource.party.length+1 && canonical(read().party.at(-1))===canonical(newcomer),'player file can add a new party member');await loadProfile('player:add',JSON.stringify(newcomer));check(read().party.length===profileSource.party.length+1 && byId('status').className==='error','duplicate party IDs cannot be imported twice');document.querySelectorAll('.player-card [data-action="remove-player"]')[profileSource.party.length].click();await loadProfile('player:0',JSON.stringify(profileSource.party[0]));check(canonical(read())===canonical(profileSource),'granular player replacement can restore the exact original request');
   let releasePlayer;const playerPending=profileInput('player:0').onchange({target:{files:[{text:()=>new Promise(resolve=>{releasePlayer=resolve;})}],value:''}});editRequest(['party',0,'resources','fate'],profileSource.party[0].resources.fate+1);releasePlayer(JSON.stringify(rich));await playerPending;check(read().party[0].resources.fate===profileSource.party[0].resources.fate+1 && read().party[0].actor_id===profileSource.party[0].actor_id,'late player file cannot replace an edited card');await loadProfile('player:0',JSON.stringify(profileSource.party[0]));
   await loadProfile(npcKey,JSON.stringify(profileSource.party[0]));check(byId('status').className==='error' && npcDrafts.size===0 && canonical(lastResult)===profileReport,'player file cannot replace an NPC');
   let releaseNpc;const npcPending=profileInput(npcKey).onchange({target:{files:[{text:()=>new Promise(resolve=>{releaseNpc=resolve;})}],value:''}});const profileRun=run();check([...document.querySelectorAll('[data-character-control]')].every(control=>control.disabled),'profile controls disabled while generator runs');await profileRun;releaseNpc(JSON.stringify(changedNpc));await npcPending;check(npcDrafts.size===0 && canonical(lastResult)===profileReport && canonical(read())===canonical(profileSource) && generated===profileRuns+1,'new run ignores late NPC file and preserves reproducible original report');
  }finally{download=realDownload;}
  byId('request-json-tab').click();
  byId('request').value='{';await run();check(byId('status').className==='error' && getComputedStyle(byId('status')).display!=='none' && byId('status').textContent,'invalid JSON error remains visible');
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
                            '--virtual-time-budget=30000', '--timeout=30000',
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
