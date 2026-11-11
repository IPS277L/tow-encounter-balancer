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
  check(byId('win').value==='60','JSON to form');
  byId('seed').value='9007199254740993';byId('seed').dispatchEvent(new Event('change'));
  check(read().search.master_seed==='9007199254740993','seed precision');
  byId('win').value='37.5';byId('win').dispatchEvent(new Event('change'));
  check(JSON.stringify(read().targets.win_rate)==='{"numerator":3,"denominator":8}','percentage fraction');
  check(JSON.stringify(read().party)===JSON.stringify(original.party),'unrelated party preserved');
  byId('rounds').value='1.5';byId('rounds').dispatchEvent(new Event('change'));
  check(read().targets.started_rounds.numerator===3 && read().targets.started_rounds.denominator===2,'round fraction');
  const data=read();data.search.max_candidates=2;data.search.exploration_trials=1;
  data.search.top_k=1;data.search.finalist_trials=1;
  byId('request').value=pretty(data);byId('request').dispatchEvent(new Event('input'));
  check(byId('candidates').value==='2','edited JSON to form');
  byId('calculate').click();check(read().search.max_total_trials===3,'budget calculation');
  byId('format').click();JSON.parse(byId('request').value);
  const running=run();check(byId('request').readOnly && byId('run').disabled,'busy state');await running;
  const result=JSON.parse(byId('result').textContent);
  check(result.total_trials===3 && result.explored.length===2,'real generation');
  check(result.source_request.search.master_seed==='9007199254740993','full source echo');
  check(!byId('download').disabled && !byId('request').readOnly,'completed state');
  byId('request').value='{';await run();check(byId('status').className==='error','invalid JSON');
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
                        self.assertIn('data-ui-check="passed"', dom, dom[-3000:])
                finally:
                    server.shutdown()
                    thread.join(5)


if __name__ == '__main__':
    unittest.main()
