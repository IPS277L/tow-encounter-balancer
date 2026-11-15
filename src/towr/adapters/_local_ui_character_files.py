"""Granular profile files and NPC composition drafts; never edits report metrics."""

CHARACTER_FILES_STYLE = r'''
.character-file-actions{flex-shrink:0}.player-card .character-file-actions .icon-button,.player-actions .icon-button{width:36px;height:36px}
.character-heading,.npc-heading{flex-wrap:wrap}
.player-actions{display:flex;align-items:center;gap:8px}.npc-heading{display:flex;justify-content:space-between;align-items:center;gap:10px}
.badge.draft-badge{background:var(--warning-bg);color:var(--warning-text)}
'''

CHARACTER_FILES_SCRIPT = r'''
let characterFileEpoch=0;const characterFileVersions=new Map(),npcDrafts=new Map();
const characterUploadPath='M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5',characterDownloadPath='M12 4v12m-5-5 5 5 5-5M4 15v5h16v-5';
function invalidateCharacterImports(){characterFileEpoch++;characterFileVersions.clear();}
function resetCharacterFiles(){invalidateCharacterImports();npcDrafts.clear();updateNpcDraftNotice();}
function updateNpcDraftNotice(){
 byId('result-draft-notice').classList.toggle('hidden',npcDrafts.size===0);
 const title=npcDrafts.size?'Скачать исходный отчёт (без черновиков NPC)':'Скачать результат';byId('download').title=title;byId('download').setAttribute('aria-label',title);
}
function draftNpcs(candidate,report){const draft=report===lastResult?npcDrafts.get(candidate.replay.scenario.id):null;return draft&&draft.original===canonical(candidate.npcs)?draft.npcs:candidate.npcs;}
async function validateCharacterText(kind,document){
 const response=await fetch('/api/character',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,document})});const result=await response.json();if(!response.ok)throw Error(result.error?.message||'Не удалось загрузить персонажа.');return result.character;
}
function characterFileControls({kind,key,current,apply,downloadable=true}){
 const actions=node('div',undefined,'file-actions character-file-actions');actions.setAttribute('role','group');actions.setAttribute('aria-label',kind==='player'?'Файл игрока':'Файл противника');
 const file=node('input');file.type='file';file.accept='.json,application/json';file.className='hidden';file.dataset.characterFile=key;file.dataset.characterControl='';file.setAttribute('aria-label',kind==='player'?'JSON игрока':'JSON противника');file.disabled=busy;
 const load=resultIconButton('load-'+kind,kind==='player'?'Загрузить игрока':'Загрузить противника',characterUploadPath);load.dataset.characterControl='';load.disabled=busy;load.onclick=()=>file.click();actions.append(load,file);
 function operation(){const epoch=characterFileEpoch,version=(characterFileVersions.get(key)||0)+1;characterFileVersions.set(key,version);return ()=>!busy&&epoch===characterFileEpoch&&characterFileVersions.get(key)===version;}
 file.onchange=async event=>{
  const selected=event.target.files[0];if(!selected||busy)return;const active=operation();
  try{if(selected.size>2*1024*1024)throw Error('Файл персонажа больше 2 МиБ.');const before=canonical(current()),text=await selected.text();if(!active())return;const character=await validateCharacterText(kind,text);if(!active())return;if(canonical(current())!==before)throw Error('Карточка изменилась во время загрузки. Выберите файл ещё раз.');apply(character);message('');}
  catch(error){if(active())message(error.message,'error');}finally{event.target.value='';}
 };
 if(downloadable){const save=resultIconButton('save-'+kind,kind==='player'?'Скачать игрока':'Скачать противника',characterDownloadPath);save.dataset.characterControl='';save.disabled=busy;save.onclick=async()=>{if(busy)return;const active=operation();try{const character=current(),before=canonical(character);await validateCharacterText(kind,pretty(character));if(active()&&canonical(current())===before)download(pretty(character),'encounter-'+kind+'.json');}catch(error){if(active())message(error.message,'error');}};actions.append(save);}
 return actions;
}
function playerFileControls(index){return characterFileControls({kind:'player',key:'player:'+index,current:()=>read().party[index],apply:character=>{
 const data=read();if(data.party.some((member,i)=>i!==index&&member.actor_id===character.actor_id))throw Error('Игрок с ID «'+character.actor_id+'» уже есть в партии.');data.party[index]=character;editRequest(['party'],data.party);
}});}
function addPlayerFileControls(){return characterFileControls({kind:'player',key:'player:add',current:()=>read().party.map(member=>member.actor_id),downloadable:false,apply:character=>{
 const data=read();if(data.party.some(member=>member.actor_id===character.actor_id))throw Error('Игрок с ID «'+character.actor_id+'» уже есть в партии. Загрузите файл в его карточку для замены.');editRequest(['party'],[...data.party,character]);
}});}
function npcFileControls(candidate,index,report){const id=candidate.replay.scenario.id;return characterFileControls({kind:'npc',key:'npc:'+id+':'+index,current:()=>draftNpcs(candidate,report)[index],apply:character=>{
 if(report!==lastResult)throw Error('Результат уже изменился. Выберите файл ещё раз.');const npcs=JSON.parse(JSON.stringify(draftNpcs(candidate,report)));npcs[index]=character;
 if(canonical(npcs)===canonical(candidate.npcs))npcDrafts.delete(id);else npcDrafts.set(id,{original:canonical(candidate.npcs),npcs});updateNpcDraftNotice();renderResultVisual(lastResult);updateFileActions();
}});}
function resetNpcDraft(candidate){invalidateCharacterImports();npcDrafts.delete(candidate.replay.scenario.id);updateNpcDraftNotice();renderResultVisual(lastResult);updateFileActions();}
'''
