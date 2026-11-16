"""Bounded UI planning policy; it never executes battles or changes game rules."""

PLANNING_SCRIPT = r'''
let planningError=null;
const precisionIds=['candidates','exploration','top','finalTrials'];
function planningSearchSpace(data){
 // Client estimate for planning/manual initialization. Execution derives its
 // authoritative automatic envelope on the server from the admitted party.
 if(data.search_space)return data.search_space;
 const space={weapon:['staff','dagger'],light_armour:[false,true],abilities:[[]]};
 for(const key of ['weapon_skill','strength','toughness','agility','melee','athletics']){
  const skill=['melee','athletics'].includes(key),floor=skill?2:1,ceiling=skill?6:10;
  const values=data.party.map(m=>Number((skill?m.skills:m.characteristics)?.[key]));
  if(!values.length||values.some(v=>!Number.isSafeInteger(v)))throw Error('Проверьте характеристики и навыки партии.');
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
function estimatedSearchTime(data){
 try{
  const space=planningSearchSpace(data);
  const min=data.npc_count?.minimum,max=data.npc_count?.maximum,cap=data.max_rounds;
  const rounds=data.targets?.started_rounds?.numerator/data.targets?.started_rounds?.denominator;
  const total=data.search?.max_total_trials;
  if(!Number.isSafeInteger(min)||min<1||!Number.isSafeInteger(max)||max<min||!Number.isSafeInteger(cap)||cap<1||!Number.isFinite(rounds)||rounds<1||rounds>cap||!Number.isSafeInteger(total)||total<1||!data.party?.length)return null;
  const mean=values=>values.reduce((sum,value)=>sum+Number(value),0)/values.length;
  const count=(min+max)/2;
  // Local 4-trial measurements: 1/5/10 ordinary Staff NPCs, two PCs.
  const perTrial=count<=5 ? .027+(count-1)*(1.081-.027)/4 : 1.081+(count-5)*(2.266-1.081)/5;
  const dice=mean(space.weapon_skill)+mean(space.agility)+mean(data.party.map(m=>Number(m.characteristics.weapon_skill)+Number(m.characteristics.agility)));
  const abilities=1+.15*Math.max(...space.abilities.map(group=>group.length));
  const work=((count+data.party.length)/(count+2))*(rounds/5)*Math.pow(cap/15,.25)*Math.sqrt(dice/12)*abilities;
  const seconds=total*perTrial*work;
  if(!Number.isFinite(seconds)||seconds<=0)return null;
  return {low:Math.max(1,Math.ceil(seconds*.6)),high:Math.max(1,Math.ceil(seconds*1.6))};
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
 for(const key of ['weapon_skill','strength','toughness','agility','melee','athletics','weapon','light_armour','abilities']){
  const values=space[key];if(!Array.isArray(values)||!values.length)throw Error('Задайте допустимые значения: '+key);
  profiles=Math.min(1e12,profiles*values.length);bits+=Math.log2(values.length);
 }
 const mean=values=>values.reduce((sum,value)=>sum+Number(value),0)/values.length;
 const npcDice=mean(space.weapon_skill)+mean(space.agility);
 const partyDice=mean(data.party.map(m=>Number(m.characteristics?.weapon_skill)+Number(m.characteristics?.agility)));
 if(!Number.isFinite(npcDice+partyDice)||npcDice+partyDice<=0)throw Error('Проверьте характеристики участников.');
 const abilityCost=1+.15*Math.max(...space.abilities.map(group=>Array.isArray(group)?group.length:0));
 const load=Math.max(.5,((data.party.length+(min+max)/2)/7.5)*(rounds/5)*Math.pow(cap/15,.25)*Math.sqrt((npcDice+partyDice)/12)*abilityCost);
 const capacity=Math.max(256,Math.min(1600,16*Math.floor(800/load/16)));
 const variance=4*p*(1-p),exploration=8+4*Math.round(variance);
 const desired=Math.min(64,4*Math.ceil((8+bits+2*Math.log2(max-min+1)+Math.log2(max))/4));
 const affordable=Math.max(1,4*Math.floor(capacity*.4/exploration/4));
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
