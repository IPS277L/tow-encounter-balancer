"""Actual editor DOM: explicit GM facts survive edits without starting a search."""
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from towr.adapters._local_ui_page import PAGE


BROWSER=os.environ.get('TOWR_UI_BROWSER') or shutil.which('chromium') or shutil.which('google-chrome')
if not BROWSER:
    edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    BROWSER=str(edge) if edge.is_file() else None


CHECK=r'''
<script>
(async()=>{
 const assert=(value,name)=>{if(!value)throw Error(name);},copy=value=>JSON.parse(JSON.stringify(value));
 const field=path=>document.querySelector('[data-path="'+path+'"]');
 const change=(path,value)=>{const input=field(path);assert(input,'field '+path);if(input.type==='checkbox')input.checked=value;else input.value=value;input.dispatchEvent(new Event('change'));};
 const load=value=>{byId('request').value=pretty(value);syncForm();};
 try{
  for(let i=0;i<100&&!byId('request').value;i++)await new Promise(resolve=>setTimeout(resolve,1));
  assert(byId('request').value,'source loaded');byId('auto-search').checked=false;
  const original=read(),draft=copy(original);
  draft.party[0].talents=[{id:'honour_bound',acquisitions:[{phase:'advancement',funding:'xp',choice:{oath_id:'protect-allies'},devotion_confirmed:null}]}];
  draft.party[0].oath_context={gm_confirmation_id:'gm:actual',in_good_standing_confirmed:true,oath_id:'protect-allies',combat_tests_fulfil_oath_confirmed:false,forbidden_attack_skills:['shooting'],fleeing_breaks_oath:true,lady_prayer_before_battle_confirmed:false,honour_bound_used_this_session:true};
  load(draft);const before=JSON.stringify(read());byId('request-json-tab').click();byId('request-visual-tab').click();
  assert(JSON.stringify(read())===before,'view/render does not approve or repair GM facts');
  assert(field('party/0/oath_context/honour_bound_used_this_session').checked,'real session expenditure preserved');
  assert(!field('party/0/oath_context/unmitigated_success_scope_confirmed').checked,'omitted scope does not grant Unmitigated Success');
  change('party/0/oath_context/combat_tests_fulfil_oath_confirmed',true);
  assert(read().party[0].oath_context.combat_tests_fulfil_oath_confirmed===true,'explicit fulfilment edit');
  assert(read().party[0].oath_context.unmitigated_success_scope_confirmed!==true,'fulfilment confirmation does not imply outcome scope');
  change('party/0/oath_context/unmitigated_success_scope_confirmed',true);
  assert(read().party[0].oath_context.unmitigated_success_scope_confirmed===true,'scope is a separate deliberate GM fact');
  change('party/0/talents/0/acquisitions/0/choice/oath_id','new-oath');
  assert(read().party[0].oath_context.oath_id==='new-oath','intentional OathChoice edit stays matched');
  change('party/0/oath_context/in_good_standing_confirmed',false);
  assert(read().party[0].oath_context.in_good_standing_confirmed===false,'false is retained, not repaired');
  const npc=copy(original);npc.search_space=planningSearchSpace({...npc,search_space:null});npc.search_space.allowed_oath_sources=[];load(npc);
  const add=document.querySelector('[data-role="add-oath-source"]');assert(add,'NPC source add');add.click();
  let source=read().search_space.allowed_oath_sources[0];
  assert(source.context.in_good_standing_confirmed===false&&source.context.gm_confirmation_id==='','new source invents no GM approval');
  assert(!source.talent_facts.origin&&!(source.talent_facts.lores||[]).length,'new source invents no Origin/Lore');
  change('search_space/allowed_oath_sources/0/oath_id','defend-land');
  change('search_space/allowed_oath_sources/0/context/gm_confirmation_id','gm:npc');
  change('search_space/allowed_oath_sources/0/context/in_good_standing_confirmed',true);
  change('search_space/allowed_oath_sources/0/talents','both');
  source=read().search_space.allowed_oath_sources[0];
  assert(source.talents.some(t=>t.id==='blessings_of_the_lady'),'Lady selected explicitly');
  assert(!source.talent_facts.origin&&!(source.talent_facts.lores||[]).length,'adding Lady does not manufacture paid Requirements');
  change('search_space/allowed_oath_sources/0/talent_facts/origin','bretonnian_human');
  change('search_space/allowed_oath_sources/0/talent_facts/high_society',true);
  change('search_space/allowed_oath_sources/0/context/forbidden_attack_skills/shooting',true);
  source=read().search_space.allowed_oath_sources[0];
  assert(source.context.oath_id==='defend-land'&&source.talents[0].acquisitions[0].choice.oath_id==='defend-land','same source oath identity');
  assert(source.talent_facts.lores.some(l=>l.id==='high_society'&&l.magic===false),'explicit ordinary High Society Lore');
  assert(source.context.forbidden_attack_skills.includes('shooting'),'explicit prohibited action');
  assert(source.context.unmitigated_success_scope_confirmed===false,'NPC source has no automatic outcome permission');
  change('search_space/allowed_oath_sources/0/context/unmitigated_success_scope_confirmed',true);source=read().search_space.allowed_oath_sources[0];
  const hint=oathContextHint(source.context);assert(hint.includes('gm:npc')&&hint.includes('defend-land')&&hint.includes('Исходные GM-факты')&&hint.includes('Shooting'),'result Talent tooltip shows the actual initial GM context');
  const encoded=JSON.stringify(read());byId('request-json-tab').click();byId('request-visual-tab').click();assert(JSON.stringify(read())===encoded,'complete NPC source survives representation changes');
  document.body.setAttribute('data-oath-check','passed');
 }catch(error){document.body.setAttribute('data-oath-check','failed:'+error.message);}
})();
</script>
'''


@unittest.skipUnless(BROWSER,'installed Edge/Chromium required for actual editor checks')
class OathUiSourceTests(unittest.TestCase):
    def test_actual_editor_preserves_and_edits_explicit_pc_and_npc_oath_sources(self):
        initial=json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
        initial['party']=initial['party'][:1]
        stub='<script>window.fetch=async url=>{if(url!=="/api/request")throw Error("Unexpected request: "+url);return new Response('
        stub+=json.dumps(json.dumps(initial))+',{status:200,headers:{"X-TOWR-UI-Mode":"manual"}});};</script>'
        page_source=PAGE.replace('<!doctype html>','<!doctype html>'+stub,1)+CHECK
        cache=Path('.cache').resolve();cache.mkdir(exist_ok=True)
        self.assertTrue(cache.is_relative_to(Path.cwd().resolve()))
        with tempfile.TemporaryDirectory(prefix='oath-editor-',dir=cache) as temporary:
            folder=Path(temporary);page=folder/'editor.html';page.write_text(page_source,encoding='utf-8')
            arguments=['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--dump-dom','--virtual-time-budget=2000','--user-data-dir='+str(folder/'profile'),page.as_uri()]
            if os.name=='nt':
                quote=lambda value:"'"+value.replace("'","''")+"'"
                output,errors=folder/'dom.txt',folder/'errors.txt'
                command=(f'$p=Start-Process -FilePath {quote(BROWSER)} '
                    f'-ArgumentList {quote(subprocess.list2cmdline(arguments))} -WindowStyle Hidden -Wait -PassThru '
                    f'-RedirectStandardOutput {quote(str(output))} -RedirectStandardError {quote(str(errors))}; exit $p.ExitCode')
                result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,timeout=30)
                dom=output.read_text(encoding='utf-8')
            else:
                result=subprocess.run([BROWSER,*arguments],capture_output=True,timeout=30)
                dom=result.stdout.decode('utf-8',errors='replace')
            self.assertEqual(result.returncode,0,result.stderr[-1000:])
            self.assertIn('data-oath-check="passed"',dom,html.unescape(dom[-3500:]))
