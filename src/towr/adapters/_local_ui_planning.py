"""Bounded UI planning policy; it never executes battles or changes game rules."""

PLANNING_SCRIPT = r'''
let planningError=null;
const precisionIds=['candidates','exploration','top','finalTrials'];
const generatedWeaponIds=Object.freeze(['staff','dagger','foot_spear','polearm','axe','sword','warhammer','morning_star','pickaxe','flail','billhook','halberd','glaive','greataxe','greatsword','greathammer','pistol','repeater_pistol','repeater_handbow','shortbow','warbow','longbow','crossbow','handgun','blunderbuss','hochland_long_rifle','repeater_crossbow','repeater_handgun','weighted_net']);
function planningSearchSpace(data){
 // Client estimate for planning/manual initialization. Execution derives its
 // authoritative automatic envelope on the server from the admitted party.
 if(data.search_space)return data.search_space;
 const space={weapon:[...generatedWeaponIds],light_armour:[false,true],shield:[false,true],weapon_grip:['1h','2h'],mount:[null,'horse'],abilities:[[]],allowed_talents:['magic_resistance','defensive_stance','wild_attack']};
 for(const key of ['weapon_skill','strength','toughness','agility','melee','defence','athletics']){
  const skill=['melee','defence','athletics'].includes(key),floor=skill?2:1,ceiling=skill?6:10;
  const values=data.party.map(m=>Number((skill?m.skills:m.characteristics)?.[key]));
  if(!values.length||values.some(v=>!Number.isSafeInteger(v)))throw Error('Проверьте характеристики и навыки партии.');
  const low=Math.max(floor,Math.min(ceiling,Math.min(...values)-1));
  const high=Math.max(low,Math.min(ceiling,Math.max(...values)+1));
  space[key]=Array.from({length:high-low+1},(_,i)=>low+i);
 }
 for(const key of ['ballistic_skill','initiative','shooting','dexterity','awareness','throwing','brawn']){
  const skill=['shooting','dexterity','awareness','throwing','brawn'].includes(key),floor=skill?2:1,ceiling=skill?6:10;
  const values=data.party.map(m=>Number((skill?m.skills:m.characteristics)?.[key])).filter(Number.isSafeInteger);
  if(!values.length){space[key]=skill?[3,4,5]:[2,3,4];continue;}
  const low=Math.max(floor,Math.min(ceiling,Math.min(...values)-1));
  const high=Math.max(low,Math.min(ceiling,Math.max(...values)+1));
  space[key]=Array.from({length:high-low+1},(_,i)=>low+i);
 }
 for(const member of data.party){
  if(member.magic?.memorised_spells?.includes('lightning_blast')){
   const reason=Number(member.characteristics?.reason),willpower=Number(member.skills?.willpower);
   if(!Number.isSafeInteger(reason)||reason<1||!Number.isSafeInteger(willpower)||willpower<1)throw Error('Проверьте Разум (Reason) и Силу воли (Willpower).');
   const pivot=Math.min(10,4+Math.ceil(reason*willpower/10));
   space.toughness=[...new Set([...space.toughness,Math.max(1,pivot-1),pivot])].sort((a,b)=>a-b);
  }
 }
 return space;
}
// One explicit workload model serves both planning and the displayed estimate.
// Coefficients are local benchmark guidance, not a machine-speed guarantee.
const searchCostModel=Object.freeze({actorRoundSeconds:.018,actorExponent:1.5,
 npcRangedWeight:.30,pcRangedWeight:1.2,pcMagicWeight:.15,equipmentWeight:.10,
 npcTalentWeight:.025,pcTalentWeight:.05,abilityWeight:.10,capExponent:.25,
 lowFactor:.40,highFactor:2.0,targetSeconds:750,minTrials:16,maxTrials:4096,
 processStartupSeconds:3,processThroughput:Object.freeze([1,1.25,1.9,2.5])});
function simulationCostEstimate(data){
 const space=planningSearchSpace(data);
 const min=data.npc_count?.minimum,max=data.npc_count?.maximum,cap=data.max_rounds;
 const rounds=data.targets?.started_rounds?.numerator/data.targets?.started_rounds?.denominator;
 if(!Number.isSafeInteger(min)||min<1||!Number.isSafeInteger(max)||max<min||!Number.isSafeInteger(cap)||cap<1||!Number.isFinite(rounds)||rounds<1||rounds>cap||!Array.isArray(data.party)||!data.party.length)return null;
 const mean=values=>{if(!Array.isArray(values)||!values.length||values.some(value=>!Number.isFinite(value)||value<=0))throw Error('Проверьте характеристики участников.');return values.reduce((sum,value)=>sum+value,0)/values.length;};
 const count=(min+max)/2,actors=count+data.party.length;
 if(!Array.isArray(space.weapon)||!space.weapon.length||!Array.isArray(space.abilities)||!space.abilities.length||space.abilities.some(group=>!Array.isArray(group)))return null;
 const rangedWeapons=new Set(['pistol','repeater_pistol','repeater_handbow','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','blunderbuss','hochland_long_rifle']);
 const npcRanged=space.weapon.filter(weapon=>rangedWeapons.has(weapon)).length/space.weapon.length;
 const partyDice=mean(data.party.map(member=>Math.max(Number(member.characteristics?.weapon_skill)+Number(member.characteristics?.agility),
  playerInitialRangedWeapon(member)?Number(member.characteristics?.ballistic_skill)+Number(member.characteristics?.initiative):0,
  member.magic?.memorised_spells?.length?Number(member.characteristics?.reason)+Number(member.characteristics?.agility):0)));
 const npcMeleeDice=mean(space.weapon_skill)+mean(space.agility);
 const npcDice=(1-npcRanged)*npcMeleeDice+(npcRanged?npcRanged*(mean(space.ballistic_skill)+mean(space.initiative)):0);
 const pcRanged=data.party.filter(member=>playerInitialRangedWeapon(member)).length/data.party.length;
 const pcMagic=data.party.reduce((total,member)=>total+(member.magic?.memorised_spells?.length||0),0)/data.party.length;
 const equipment=data.party.reduce((total,member)=>total+Number(Boolean(playerInitialRangedWeapon(member))&&(member.equipment?.weapons?.length||0)>1)+Number((member.equipment?.armour||[]).some(item=>item.kind==='shield'&&['left_hand','right_hand'].includes(item.location))),0)/data.party.length;
 const pcTalents=data.party.reduce((total,member)=>total+(member.talents||[]).filter(talent=>['defensive_stance','wild_attack'].includes(talent)).length,0)/data.party.length;
 const npcTalents=Array.isArray(space.allowed_talents)?space.allowed_talents.length:0;
 const abilities=Math.max(...space.abilities.map(group=>group.length));
 const m=searchCostModel;
 const seconds=m.actorRoundSeconds*Math.pow(actors,m.actorExponent)*rounds*Math.pow(cap/15,m.capExponent)*Math.sqrt((npcDice+partyDice)/12)
  *(1+m.npcRangedWeight*npcRanged)*(1+m.pcRangedWeight*pcRanged)*(1+m.pcMagicWeight*pcMagic)
  *(1+m.equipmentWeight*equipment)*(1+m.npcTalentWeight*npcTalents+m.pcTalentWeight*pcTalents+m.abilityWeight*abilities);
 if(!Number.isFinite(seconds)||seconds<=0)return null;
 return {seconds,low:seconds*m.lowFactor,high:seconds*m.highFactor};
}
function executionCostEstimate(data){
 const cost=simulationCostEstimate(data),execution=data.execution;
 if(!cost||!execution||typeof execution!=='object'||Array.isArray(execution))return null;
 const keys=Object.keys(execution);
 if(execution.mode==='sequential'&&keys.length===1)return {...cost,startupSeconds:0};
 if(execution.mode!=='process'||keys.length!==2||!Object.hasOwn(execution,'workers')||!Number.isSafeInteger(execution.workers)||execution.workers<1||execution.workers>61)return null;
 // Conservative credits below measured throughput for 2/3/4 workers. Higher
 // counts receive no unmeasured scaling credit; one pool starts per search.
 const throughput=searchCostModel.processThroughput[Math.min(4,execution.workers)-1];
 return {seconds:cost.seconds/throughput,low:cost.low/throughput,high:cost.high/throughput,startupSeconds:searchCostModel.processStartupSeconds};
}
function estimatedSearchTime(data){
 try{
  const total=data.search?.max_total_trials,cost=executionCostEstimate(data);
  if(!cost||!Number.isSafeInteger(total)||total<1)return null;
  return {low:Math.max(1,Math.ceil(cost.startupSeconds+total*cost.low)),high:Math.max(1,Math.ceil(cost.startupSeconds+total*cost.high))};
 }catch(_){return null;}
}
function formatSearchTime(estimate){
 if(!estimate)return 'время: нет оценки';
 const range=(low,high,unit)=>'≈ '+low+(low===high?'':'–'+high)+' '+unit;
 if(estimate.high<60)return range(estimate.low,estimate.high,'с');
 if(estimate.high<3600)return range(Math.max(1,Math.round(estimate.low/60)),Math.max(1,Math.ceil(estimate.high/60)),'мин');
 return range((estimate.low/3600).toFixed(1),(estimate.high/3600).toFixed(1),'ч');
}
function automaticSearchPlan(data){
 const space=planningSearchSpace(data);
 const positive=value=>{if(!Number.isSafeInteger(value)||value<1)throw Error('Для автоплана нужны положительные целые численность и предел раундов.');return value;};
 const min=positive(data.npc_count?.minimum),max=positive(data.npc_count?.maximum),cap=positive(data.max_rounds);
 const p=data.targets?.win_rate?.numerator/data.targets?.win_rate?.denominator;
 const rounds=data.targets?.started_rounds?.numerator/data.targets?.started_rounds?.denominator;
 if(min>max||!Number.isFinite(p)||p<0||p>1||!Number.isFinite(rounds)||rounds<1||rounds>cap||!Array.isArray(data.party)||!data.party.length)throw Error('Проверьте состав и цели боя для автоплана.');
 let profiles=1,bits=0;
 for(const key of ['weapon_skill','strength','toughness','agility','melee','defence','athletics','weapon','light_armour','shield','abilities']){
  const values=space[key];if(!Array.isArray(values)||!values.length)throw Error('Задайте допустимые значения: '+key);
  profiles=Math.min(1e12,profiles*values.length);bits+=Math.log2(values.length);
 }
 if(space.weapon.some(weapon=>['pistol','repeater_pistol','repeater_handbow','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','blunderbuss','hochland_long_rifle'].includes(weapon))){
  for(const key of ['ballistic_skill','initiative','shooting','dexterity',...(space.weapon.some(weapon=>!['pistol','repeater_pistol','repeater_handbow'].includes(weapon))?['awareness']:[])]){const values=space[key]||(key==='awareness'?[3,4,5]:null);if(!Array.isArray(values)||!values.length)throw Error('Задайте допустимые значения: '+key);profiles=Math.min(1e12,profiles*values.length);bits+=Math.log2(values.length);}
 }
 if(!Array.isArray(space.allowed_talents)||new Set(space.allowed_talents).size!==space.allowed_talents.length||space.allowed_talents.some(t=>!['magic_resistance','defensive_stance','wild_attack'].includes(t)))throw Error('Проверьте разрешённые таланты (Talents) NPC.');
 // Upper bound only: Requirements filter the sampled subsets on the server.
 profiles=Math.min(1e12,profiles*Math.pow(2,space.allowed_talents.length));bits+=space.allowed_talents.length;
 const cost=executionCostEstimate(data);
 if(!cost)throw Error('Проверьте состав, цели боя и режим исполнения для оценки стоимости.');
 const capacity=Math.max(searchCostModel.minTrials,Math.min(searchCostModel.maxTrials,Math.floor((searchCostModel.targetSeconds-cost.startupSeconds)/cost.seconds)));
 const variance=4*p*(1-p),preferredExploration=8+4*Math.round(variance);
 const desired=Math.min(64,4*Math.ceil((8+bits+2*Math.log2(max-min+1)+Math.log2(max))/4));
 // More uncertainty reserves more independent validation, while 50–60% of
 // ordinary capacity stays available to propose different compositions.
 const explorationShare=.6-.1*variance;
 // Retain useful breadth when expensive encounters cannot afford eight
 // candidates at the preferred precision. Never reduce screening below 8.
 const exploration=preferredExploration>8&&capacity*explorationShare<Math.min(8,desired)*preferredExploration?8:preferredExploration;
 const affordable=Math.max(1,Math.floor(capacity*explorationShare/exploration));
 let candidates=Math.min(desired,affordable),available=0;
 // Saturating space bound: at most 64 iterations, even for a huge count range.
 for(let count=min;count<=max&&available<candidates;count++)available+=Math.min(candidates,Math.pow(profiles,count));
 candidates=Math.max(1,Math.min(candidates,available));
 const top=Math.min(2,candidates),wanted=16*Math.ceil((64+192*variance)/16);
 const finals=Math.max(1,Math.min(wanted,Math.floor((capacity-candidates*exploration)/top)));
 return {max_candidates:candidates,exploration_trials:exploration,top_k:top,finalist_trials:finals};
}
function applySearchPlan(data){
 planningError=null;if(data.kind!=='dynamic_encounter_search')return;
 try{
  if(!data.search||typeof data.search!=='object'||Array.isArray(data.search))throw Error('В запросе отсутствует раздел search.');
  if(byId('auto-search').checked)Object.assign(data.search,automaticSearchPlan(data));
  const s=data.search;
  for(const key of ['max_candidates','exploration_trials','top_k','finalist_trials'])if(!Number.isSafeInteger(s[key])||s[key]<1)throw Error('Параметры поиска должны быть положительными целыми.');
  if(s.top_k>s.max_candidates)throw Error('Финалистов не может быть больше, чем кандидатов.');
  const total=s.max_candidates*s.exploration_trials+s.top_k*s.finalist_trials;
  if(!Number.isSafeInteger(total))throw Error('План симуляций слишком велик.');
  s.max_total_trials=total;
 }catch(error){planningError=error.message;throw error;}
}
function updatePlanControls(){
 for(const id of precisionIds)byId(id).disabled=busy||byId('auto-search').checked;
 byId('seed').disabled=busy;
}
byId('auto-search').onchange=()=>{try{syncForm();message(byId('auto-search').checked?'План обновлён автоматически.':'Ручная настройка поиска. Общий бюджет всё равно вычисляется автоматически.');}catch(error){message(error.message,'error');}};
'''
