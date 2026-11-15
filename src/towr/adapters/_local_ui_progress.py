"""Small live progress view; no battle log, source edits or simulation logic."""

PROGRESS_STYLE = r'''
.generation-progress{background:white;border:1px solid #d9dee5;border-radius:6px;padding:12px 16px;margin:0 0 16px}
.generation-progress p{font-size:13px;margin:5px 0}.generation-progress progress{display:block;width:100%;height:9px;margin:10px 0;accent-color:#235ba8}
.generation-progress .progress-phase{font-weight:600;color:#404957}.generation-progress .progress-last{color:#667085;font-size:12px}
'''

PROGRESS_MARKUP = r'''
<section id="generation-progress" class="generation-progress hidden" aria-label="Ход генерации">
<p id="progress-phase" class="progress-phase" role="status" aria-live="polite"></p>
<progress id="progress-bar" max="1" aria-label="Завершённые симуляции"></progress>
<p id="progress-count"></p>
<p id="progress-observation"></p>
<p id="progress-last" class="progress-last hidden"></p>
</section>
'''

PROGRESS_SCRIPT = r'''
let progressRunId=null, progressTimer=null, progressAbort=null, progressSequence=-1;
function progressAssessment(p){
 if(!p||!p.completed_trials)return '';
 const rate=(100*p.wins/p.completed_trials).toFixed(1).replace('.',',');
 return 'Победы игроков: '+p.wins+'/'+p.completed_trials+' ('+rate+'%)'+(p.unsupported_trials?' · неподдержанные исходы: '+p.unsupported_trials:'');
}
function renderGenerationProgress(data){
 if(!busy||data.run_id!==activeRunId||data.run_id!==progressRunId||data.sequence<progressSequence)return;
 progressSequence=data.sequence;const p=data.current;
 if(!p)return;
 const position=p.candidate_number+' из '+p.candidate_count;
 const phases={generating:'Создаём состав '+position,simulating:(p.stage==='validate'?'Независимая проверка: финалист ':'Предварительная оценка: состав ')+position+(p.npc_count?' · '+p.npc_count+' NPC':''),candidate_complete:(p.stage==='validate'?'Проверен финалист ':'Оценён состав ')+position,selecting:'Выбираем финалистов для независимой проверки',complete:'Симуляции завершены. Подготавливаем результат'};
 const phase=cancelling||data.state==='cancelling'?'Останавливаем генерацию…':phases[p.phase]||'Выполняется расчёт…';
 if(byId('progress-phase').textContent!==phase)byId('progress-phase').textContent=phase;
 byId('progress-bar').max=p.trial_budget;byId('progress-bar').value=p.total_completed_trials;
 byId('progress-count').textContent='Всего завершено '+p.total_completed_trials+' симуляций · план до '+p.trial_budget;
 byId('progress-observation').textContent=p.trial_count?'Симуляции состава: '+p.completed_trials+'/'+p.trial_count+(p.completed_trials?' · '+progressAssessment(p)+' · предварительно':''):'';
 const last=data.last_candidate,same=last&&last.stage===p.stage&&last.candidate_number===p.candidate_number;
 byId('progress-last').classList.toggle('hidden',!last||same);
 byId('progress-last').textContent=last?'Последняя оценка · '+(last.stage==='validate'?'финалист ':'состав ')+last.candidate_number+': '+progressAssessment(last):'';
}
async function pollGenerationProgress(runId){
 if(!busy||activeRunId!==runId||progressRunId!==runId)return;
 const controller=new AbortController();progressAbort=controller;
 try{
  const response=await fetch('/api/progress',{headers:{'X-TOWR-Run-ID':runId},signal:controller.signal});
  if(response.ok){const data=await response.json();if(data.kind==='dynamic_encounter_progress')renderGenerationProgress(data);}
 }catch(_){/* A missed status poll must not interrupt the generation request. */}
 finally{
  if(progressAbort===controller)progressAbort=null;
  if(busy&&activeRunId===runId&&progressRunId===runId)progressTimer=setTimeout(()=>pollGenerationProgress(runId),1000);
 }
}
function startGenerationProgress(runId){
 if(progressTimer!==null)clearTimeout(progressTimer);if(progressAbort)progressAbort.abort();
 progressRunId=runId;progressSequence=-1;byId('generation-progress').classList.remove('hidden');
 byId('progress-phase').textContent='Проверяем запрос и готовим поиск…';byId('progress-bar').max=1;byId('progress-bar').removeAttribute('value');
 byId('progress-count').textContent='Ожидаем начала симуляций';byId('progress-observation').textContent='';byId('progress-last').textContent='';byId('progress-last').classList.add('hidden');
 progressTimer=setTimeout(()=>pollGenerationProgress(runId),0);
}
function finishGenerationProgress(runId,outcome,result=null){
 if(progressRunId!==runId)return;
 progressRunId=null;if(progressTimer!==null)clearTimeout(progressTimer);progressTimer=null;if(progressAbort)progressAbort.abort();progressAbort=null;
 byId('progress-phase').textContent=outcome==='complete'?'Готово. Проверено финалистов: '+result.validations.length:outcome==='cancelled'?'Генерация отменена':'Расчёт остановлен из-за ошибки';
 byId('progress-last').textContent='';byId('progress-last').classList.add('hidden');byId('progress-observation').textContent='';
 if(outcome==='complete'){
  byId('progress-bar').max=Math.max(1,result.total_trials);byId('progress-bar').value=result.total_trials;
  byId('progress-count').textContent='Завершено '+result.total_trials+' симуляций · план был до '+result.source_request.search.max_total_trials;
  const selected=result.validations.find(candidate=>candidate.replay?.scenario?.id===result.selected[0]);
  byId('progress-observation').textContent=selected?'Рекомендованный состав · '+progressAssessment({completed_trials:selected.trials,wins:selected.outcomes.objective_achieved,unsupported_trials:0})+' · независимая проверка':'Подходящий состав не найден. Подробности — в результате.';
 }else if(!byId('progress-bar').hasAttribute('value')){byId('progress-bar').value=0;byId('progress-count').textContent='Завершённые симуляции не получены';}
 else byId('progress-count').textContent='Последнее обновление: '+byId('progress-bar').value+' завершённых симуляций';
}
'''
