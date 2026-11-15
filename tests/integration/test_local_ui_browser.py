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
  const foldedSource=byId('request').value;byId('search-settings').querySelector('summary').click();
  check(!byId('search-settings').open && byId('request').value===foldedSource,'collapse preserves request');
  byId('search-settings').querySelector('summary').click();
  check(byId('request').classList.contains('hidden') && byId('request-visual').children.length>0,'default visual request');
  let stat=document.querySelector('[data-path="party/0/pc/strength"]');stat.value=String(original.party[0].pc.strength+1);stat.dispatchEvent(new Event('change'));
  check(read().party[0].pc.strength===original.party[0].pc.strength+1,'editable PC card');
  check(JSON.stringify(read().party[0].fate)===JSON.stringify(original.party[0].fate),'preserved Fate metadata');
  byId('request-json-tab').click();check(!byId('request').classList.contains('hidden'),'JSON request tab');
  const edited=read();edited.party[0].pc.toughness+=1;byId('request').value=pretty(edited);byId('request').dispatchEvent(new Event('input'));
  byId('request-visual-tab').click();check(document.querySelector('[data-path="party/0/pc/toughness"]').value===String(edited.party[0].pc.toughness),'JSON edit visible in card');
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
  const running=run();check(byId('request').readOnly && byId('run').disabled && byId('run').classList.contains('hidden') && !byId('cancel').classList.contains('hidden'),'cancel replaces launch while busy');await running;
  const result=JSON.parse(byId('result').textContent);
  check(result.total_trials===3 && result.explored.length===2,'real generation');
  check(result.source_request.search.master_seed==='9007199254740993','full source echo');
  check(!byId('download').disabled && !byId('request').readOnly,'completed state');
  check(document.querySelector('#result-visual .result-card') && generated===1,'visual result with one explicit run');
  const beforeInvalid=byId('request').value;stat=document.querySelector('[data-path="search_space/strength"]');stat.value='bad';stat.dispatchEvent(new Event('change'));await run();
  check(generated===1 && byId('request').value===beforeInvalid,'invalid card value blocks run without corrupting JSON');
  byId('request-json-tab').click();byId('request-visual-tab').click();
  const originalResult=canonical(result);byId('result-json-tab').click();check(!byId('result').classList.contains('hidden'),'JSON result tab');byId('result-visual-tab').click();
  stat=document.querySelector('[data-path="party/0/pc/strength"]');stat.value=String(read().party[0].pc.strength+1);stat.dispatchEvent(new Event('change'));
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
