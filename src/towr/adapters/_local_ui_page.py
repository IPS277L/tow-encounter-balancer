"""Self-contained local page; shipped as ordinary Python package code."""

PAGE = r'''<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOWR — генератор боёв</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:#20242c;font:15px system-ui,sans-serif}
main{max-width:1400px;margin:28px auto;padding:0 22px}h1{font-size:26px;margin:0 0 8px}h2{font-size:17px;margin:0}
p{color:#5c6470;line-height:1.5}.panel{background:white;border:1px solid #d9dee5;border-radius:8px;padding:18px;margin:18px 0}
.control-groups{display:grid;grid-template-columns:minmax(260px,1fr) minmax(0,2fr);gap:16px;margin-top:16px}
.control-group{min-width:0;padding:14px 16px 16px;border:1px solid #dfe4eb;border-radius:6px;background:#fafbfc}
.control-group legend{padding:0 6px;font-size:14px;font-weight:600;color:#404957}
.control-group.search{grid-column:1/-1}.composition .fields{grid-template-columns:repeat(2,minmax(0,1fr))}
.fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}label{display:flex;flex-direction:column;gap:5px;color:#404957;font-size:13px}
.field{display:flex;flex-direction:column;gap:5px}
.field-hint{font-size:12px;line-height:1.4;color:#667085;font-weight:400}
input,button,textarea{font:inherit}input{min-width:0;padding:8px;border:1px solid #bfc7d2;border-radius:4px}
button{padding:8px 12px;border:1px solid #bfc7d2;border-radius:5px;background:white;cursor:pointer;color:#20242c}
button.primary{background:#235ba8;color:white;border-color:#235ba8}button:disabled{opacity:.5;cursor:default}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.columns .panel{min-width:0;margin-top:0}textarea,pre{width:100%;height:560px;margin:0;padding:12px;border:1px solid #c9d0da;border-radius:4px;tab-size:2;background:#fafbfc;color:#20242c;font:13px/1.5 Consolas,monospace}
textarea{resize:vertical}pre{overflow:auto;white-space:pre}#status{min-height:24px;white-space:pre-wrap}#status.error{color:#b02222}#status.success{color:#1d683c}
small{color:#5c6470}.hidden{display:none}fieldset{border:0;padding:0;margin:0}a{color:#235ba8}
:focus-visible{outline:2px solid #235ba8;outline-offset:2px}@media(max-width:850px){.columns{grid-template-columns:1fr}.control-groups{grid-template-columns:1fr}.fields{grid-template-columns:repeat(2,minmax(0,1fr))}textarea,pre{height:420px}}
@media(max-width:480px){.fields,.composition .fields{grid-template-columns:1fr}}
</style>
<main>
<h1>TOWR — генератор боёв</h1>
<p>Настройте поиск, отредактируйте JSON и запустите расчёт. Партия, характеристики, навыки и снаряжение задаются в JSON.</p>
<section class="panel" aria-labelledby="settings-title">
<h2 id="settings-title">Параметры поиска</h2>
<fieldset id="controls"><div class="control-groups">
<fieldset class="control-group composition"><legend>Состав противников</legend>
<div class="fields">
<div class="field"><label>Минимум NPC<input id="minimum" type="number" min="1" step="1" aria-describedby="minimum-hint"></label><small id="minimum-hint" class="field-hint">Нижняя граница числа противников в составе.</small></div>
<div class="field"><label>Максимум NPC<input id="maximum" type="number" min="1" step="1" aria-describedby="maximum-hint"></label><small id="maximum-hint" class="field-hint">Верхняя граница. Равен минимуму — число врагов фиксировано.</small></div>
</div>
</fieldset>
<fieldset class="control-group "><legend>Цели боя</legend>
<div class="fields">
<div class="field"><label>Победа игроков, %<input id="win" type="number" min="0" max="100" step="any" aria-describedby="win-hint"></label><small id="win-hint" class="field-hint">Желаемая доля побед партии. Ниже процент — сложнее бой.</small></div>
<div class="field"><label>Целевая длительность, раунды<input id="rounds" type="number" min="1" step="any" aria-describedby="rounds-hint"></label><small id="rounds-hint" class="field-hint">Желаемая средняя длительность боя.</small></div>
<div class="field"><label>Предел раундов<input id="maxRounds" type="number" min="1" step="1" aria-describedby="maxRounds-hint"></label><small id="maxRounds-hint" class="field-hint">После этого раунда бой останавливается. Лимит не считается победой.</small></div>
</div>
</fieldset>
<fieldset class="control-group search"><legend>Поиск и точность</legend>
<div class="fields">
<div class="field"><label>Кандидатов<input id="candidates" type="number" min="1" step="1" aria-describedby="candidates-hint"></label><small id="candidates-hint" class="field-hint">Максимальное число разных составов для поиска.</small></div>
<div class="field"><label>Симуляций на кандидата<input id="exploration" type="number" min="1" step="1" aria-describedby="exploration-hint"></label><small id="exploration-hint" class="field-hint">Пробных боёв на состав. Больше — точнее оценка.</small></div>
<div class="field"><label>Seed<input id="seed" type="text" inputmode="numeric" aria-describedby="seed-hint"></label><small id="seed-hint" class="field-hint">Тот же seed и те же входные данные повторяют расчёт.</small></div>
<div class="field"><label>Финалистов<input id="top" type="number" min="1" step="1" aria-describedby="top-hint"></label><small id="top-hint" class="field-hint">Максимум лучших составов для повторной проверки.</small></div>
<div class="field"><label>Симуляций на финалиста<input id="finalTrials" type="number" min="1" step="1" aria-describedby="finalTrials-hint"></label><small id="finalTrials-hint" class="field-hint">Новые бои для независимой оценки финалистов.</small></div>
<div class="field"><label>Бюджет симуляций<input id="budget" type="number" min="1" step="1" aria-describedby="budget-hint"></label><small id="budget-hint" class="field-hint">Общий предел числа симуляций на весь поиск.</small></div>
</div>
<div class="toolbar"><button id="calculate" type="button">Рассчитать бюджет</button><small id="cost"></small></div>
</fieldset>
</div></fieldset>
</section>
<div class="toolbar">
<button id="run" class="primary" type="button">Запустить генератор</button>
<button id="load" type="button">Загрузить JSON</button><input id="file" class="hidden" type="file" accept=".json,application/json" aria-label="Файл запроса">
<button id="save" type="button">Скачать запрос</button><button id="format" type="button">Форматировать JSON</button>
</div>
<p id="status" role="status" aria-live="polite">Загрузка…</p>
<div class="columns">
<section class="panel"><h2><label for="request" style="font:inherit">Запрос · редактируемый JSON</label></h2><p><small>Форма и JSON связаны. Неизвестные поля и недопустимые значения проверяются при запуске.</small></p>
<textarea id="request" spellcheck="false" aria-label="JSON запроса"></textarea></section>
<section class="panel"><h2>Результат</h2><div class="toolbar"><button id="download" type="button" disabled>Скачать результат</button><small id="summary"></small></div>
<pre id="result" tabindex="0" aria-label="JSON результата">Результат появится после расчёта.</pre></section>
</div>
</main>
<script>
'use strict';
const byId = id => document.getElementById(id);
const paths = {minimum:['npc_count','minimum'],maximum:['npc_count','maximum'],
 maxRounds:['max_rounds'],seed:['search','master_seed'],candidates:['search','max_candidates'],
 exploration:['search','exploration_trials'],top:['search','top_k'],finalTrials:['search','finalist_trials'],budget:['search','max_total_trials']};
let lastResult=null, busy=false;
function message(text,kind=''){byId('status').textContent=text;byId('status').className=kind;}
function pretty(value){return JSON.stringify(value,null,2)+'\n';}
function read(){const value=JSON.parse(byId('request').value);if(!value || typeof value!=='object' || Array.isArray(value))throw Error('Запрос должен быть JSON-объектом.');return value;}
function get(value,path){return path.reduce((v,k)=>v?.[k],value);}
function put(value,path,next){let owner=value;for(const k of path.slice(0,-1)){if(!owner[k] || typeof owner[k]!=='object' || Array.isArray(owner[k]))throw Error('В JSON отсутствует раздел '+k);owner=owner[k];}owner[path.at(-1)]=next;}
function integer(text){const n=Number(text);if(!text.trim() || !Number.isSafeInteger(n))throw Error('Введите целое число.');return n;}
function fraction(text,scale=1){
 if(!/^\d+(\.\d{1,6})?$/.test(text))throw Error('Введите положительное число, не более 6 знаков после точки.');
 const [whole,decimal='']=text.split('.');let n=Number(whole+decimal),d=10**decimal.length*scale;
 if(!Number.isSafeInteger(n)||!Number.isSafeInteger(d))throw Error('Слишком большое число.');
 let a=n,b=d;while(b){const r=a%b;a=b;b=r;}return {numerator:n/a,denominator:d/a};
}
function syncForm(){
 const data=read();
 for(const [id,path] of Object.entries(paths))byId(id).value=get(data,path)??'';
 const win=data.targets?.win_rate, rounds=data.targets?.started_rounds;
 byId('win').value=win?Number((100*win.numerator/win.denominator).toFixed(6)):'';
 byId('rounds').value=rounds?Number((rounds.numerator/rounds.denominator).toFixed(6)):'';
 const search=data.search;
 byId('cost').textContent=search?'План: до '+(search.max_candidates*search.exploration_trials+search.top_k*search.finalist_trials)+' симуляций.':'';
}
function changed(id){
 try{const data=read();
  if(id==='win')put(data,['targets','win_rate'],fraction(byId(id).value,100));
  else if(id==='rounds')put(data,['targets','started_rounds'],fraction(byId(id).value));
  else put(data,paths[id],id==='seed'?byId(id).value:integer(byId(id).value));
  byId('request').value=pretty(data);syncForm();message('Запрос изменён. Результат расчёта относится к предыдущему запуску.');
 }catch(error){message(error.message,'error');}
}
function download(text,name){const url=URL.createObjectURL(new Blob([text],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function setBusy(value){busy=value;byId('controls').disabled=value;byId('request').readOnly=value;for(const id of ['run','load','save','format','file'])byId(id).disabled=value;}
async function run(){
 if(busy)return;
 try{read();}catch(error){message(error.message,'error');return;}
 setBusy(true);lastResult=null;byId('download').disabled=true;byId('summary').textContent='';byId('result').textContent='Выполняется расчёт…';
 const started=Date.now();message('Выполняется расчёт…');const timer=setInterval(()=>message('Выполняется расчёт · '+Math.floor((Date.now()-started)/1000)+' с'),1000);
 try{
  const response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:byId('request').value});
  const result=await response.json();byId('result').textContent=pretty(result);
  if(!response.ok){throw Error([result.error?.path,result.error?.message||'Не удалось выполнить расчёт.'].filter(Boolean).join(': '));}
  lastResult=result;byId('download').disabled=false;
  byId('summary').textContent='Кандидатов: '+result.explored.length+' · Выбрано: '+result.selected.length+' · Симуляций: '+result.total_trials;
  message('Готово · '+((Date.now()-started)/1000).toFixed(1)+' с. Результат содержит полные составы и запросы для повторного запуска.','success');
 }catch(error){message(error.message,'error');if(byId('result').textContent==='Выполняется расчёт…')byId('result').textContent='Результат не получен.';}
 finally{clearInterval(timer);setBusy(false);}
}
for(const id of [...Object.keys(paths),'win','rounds'])byId(id).addEventListener('change',()=>changed(id));
byId('request').addEventListener('input',()=>{try{syncForm();message('JSON изменён. Нажмите «Запустить генератор» для нового расчёта.');}catch(error){message('JSON: '+error.message,'error');}});
byId('format').onclick=()=>{try{byId('request').value=pretty(read());syncForm();message('JSON отформатирован.');}catch(error){message(error.message,'error');}};
byId('calculate').onclick=()=>{try{const data=read(),s=data.search;put(data,['search','max_total_trials'],s.max_candidates*s.exploration_trials+s.top_k*s.finalist_trials);byId('request').value=pretty(data);syncForm();message('Бюджет рассчитан.');}catch(error){message(error.message,'error');}};
byId('save').onclick=()=>{try{read();download(byId('request').value,'encounter-request.json');}catch(error){message(error.message,'error');}};
byId('download').onclick=()=>{if(lastResult)download(pretty(lastResult),'encounter-result.json');};
byId('load').onclick=()=>byId('file').click();
byId('file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{const raw=(await file.text()).replace(/^\uFEFF/,'');const data=JSON.parse(raw);if(!data||typeof data!=='object'||Array.isArray(data))throw Error('Запрос должен быть JSON-объектом.');byId('request').value=raw;syncForm();message('Загружен '+file.name+'.');}catch(error){message(error.message,'error');}finally{event.target.value='';}};
byId('run').onclick=run;
fetch('/api/request').then(response=>{if(!response.ok)throw Error('Не удалось загрузить начальный запрос.');return response.text();}).then(raw=>{const data=JSON.parse(raw.replace(/^\uFEFF/,''));byId('request').value=pretty(data);syncForm();message(data.kind==='dynamic_encounter_search'?'Готово к запуску. Можно изменить форму или JSON.':'Загрузите JSON запроса, чтобы заполнить форму.');}).catch(error=>message(error.message+' Загрузите JSON запроса.','error'));
</script>
</html>'''
