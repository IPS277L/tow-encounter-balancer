"""Actual editor DOM checks; the page never starts a combat or search."""
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from towr.adapters._local_ui_page import PAGE


BROWSER = os.environ.get('TOWR_UI_BROWSER') or shutil.which('chromium') or shutil.which('google-chrome')
if not BROWSER:
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    BROWSER = str(edge) if edge.is_file() else None


CHECK = r'''
<script>
(async()=>{
 const assert=(value,name)=>{if(!value)throw Error(name);};
 const copy=value=>JSON.parse(JSON.stringify(value));
 const field=path=>document.querySelector('[data-path="'+path+'"]');
 const change=(path,value)=>{const input=field(path);assert(input,'field '+path);if(input.type==='checkbox')input.checked=value;else input.value=value;input.dispatchEvent(new Event('change'));};
 const load=data=>{byId('request').value=pretty(data);syncForm();};
 try{
  for(let i=0;i<100&&!byId('request').value;i++)await new Promise(resolve=>setTimeout(resolve,1));
  assert(byId('request').value,'initial source loaded');
  byId('auto-search').checked=false;
  const original=read();
  for(const value of [null,{audible_confirmed:false,blocked_zone_pairs:[['zone:0','zone:1']]}]){
   const draft=copy(original);draft.scene.music_acoustics=value;load(draft);const before=JSON.stringify(read());
   byId('request-json-tab').click();byId('request-visual-tab').click();
   assert(JSON.stringify(read())===before,'render/view switch preserves null/false acoustic facts');
  }
  const draft=copy(original);draft.scene.music_acoustics={audible_confirmed:false,blocked_zone_pairs:[['zone:0','zone:1']]};
  draft.party[0].equipment.tools=[{id:'tool:1',kind:'musicians_gear',hands_required:1,location:'carried'}];
  draft.party[0].characteristics.fellowship=5;draft.party[0].skills.leadership=4;
  draft.party[0].talent_facts={lores:[{id:'anatomy',magic:false}]};load(draft);
  const sourceBefore=JSON.stringify(read());
  automaticSearchPlan(read());estimatedSearchTime(read());
  assert(JSON.stringify(read())===sourceBefore,'planning preserves acoustic and instrument source facts');
  assert(!field('party/0/characteristics/fellowship').disabled&&!field('party/0/skills/leadership').disabled,'real gear enables common Fellowship/Leadership fields');
  assert(field('party/0/characteristics/fellowship').title.includes('Fellowship'),'Characteristic retains original in accessible title');
  change('party/0/characteristics/fellowship','15');change('party/0/skills/leadership','6');
  assert(read().party[0].characteristics.fellowship===15&&read().party[0].skills.leadership===6,'common numeric fields preserve exact ratings without a Fellowship cap');
  assert(!read().party[0].talent_facts.equipment,'gear does not grant historical acquisition equipment');
  change('party/0/talent_facts/lores/music',true);
  assert(read().party[0].talent_facts.lores.some(lore=>lore.id==='music'&&lore.magic===false),'Music Lore is an explicit ordinary Lore');
  assert(read().party[0].talent_facts.lores.some(lore=>lore.id==='anatomy'),'other acquired Lore remains');
  change('party/0/equipment/tools/0/hands_required','2');
  change('party/0/equipment/tools/0/location','both_hands');
  assert(read().party[0].equipment.weapons[0].location==='left_hand','tool edit never silently frees a weapon hand');
  change('party/0/equipment/tools/0/location','carried');
  change('party/0/equipment/tools/0/instrument_name','The old drum');
  assert(read().party[0].equipment.tools[0].instrument_name==='The old drum','instrument label retained');
  document.querySelector('[data-action="add-tools"]').click();
  assert(read().party[0].equipment.tools.length===2&&read().party[0].equipment.tools[1].id==='tool:2','add instrument preserves unique cross-inventory ID');
  document.querySelector('[data-action="remove-item"][data-path="party/0/equipment/tools/1"]').click();
  assert(read().party[0].equipment.tools.length===1&&read().party[0].equipment.tools[0].id==='tool:1','remove affects one physical tool');
  change('scene/music_acoustics/audible_confirmed',true);
  assert(read().scene.music_acoustics.audible_confirmed===true&&JSON.stringify(read().scene.music_acoustics.blocked_zone_pairs)==='[["zone:0","zone:1"]]','GM checkbox preserves acoustic barriers');
  assert(field('scene/music_acoustics/blocked_zone_pairs/0/0').title.includes('zone:0'),'barrier editor describes relative actual Zone keys');
  const beforeTalent=read(),free={id:'battlefield_musician',acquisitions:[{phase:'creation',funding:'free',choice:null,devotion_confirmed:null}]};
  beforeTalent.party[0].talents=[free];load(beforeTalent);
  assert(!field('party/0/talent_facts/equipment/musicians_gear'),'free purchase has no invented historical gear requirement');
  const paid=read();paid.party[0].talents[0].acquisitions[0].funding='xp';load(paid);
  assert(field('party/0/talent_facts/equipment/musicians_gear'),'paid acquisition offers historical prerequisite fact');
  const physicalBefore=JSON.stringify(read().party[0].equipment.tools);
  change('party/0/talent_facts/equipment/musicians_gear',true);
  assert(JSON.stringify(read().party[0].equipment.tools)===physicalBefore,'historical prerequisite checkbox creates no physical tool');
  const unknown=read();unknown.scene.music_acoustics=null;load(unknown);
  assert(read().scene.music_acoustics===null&&!field('scene/music_acoustics/audible_confirmed'),'unknown hearing does not become false or true while rendering');
  const automatic=planningSearchSpace({...read(),search_space:null});
  assert(JSON.stringify(automatic.leadership)==='[5,6]'&&JSON.stringify(automatic.musician_instrument_hands)==='[1,2]','automatic ranges use actual Leadership and explicit default permitted instrument hands');
  const manual=read();manual.search_space=copy(automatic);manual.search_space.allowed_talents=['battlefield_musician'];delete manual.search_space.leadership;delete manual.search_space.musician_instrument_hands;load(manual);
  const sourceBeforeControls=JSON.stringify(read());
  assert(field('search_space/leadership')&&field('search_space/musician_instrument_hands/1')&&field('search_space/musician_instrument_hands/2'),'manual Musician source exposes Leadership and actual GM hand choices');
  byId('request-json-tab').click();byId('request-visual-tab').click();
  assert(JSON.stringify(read())===sourceBeforeControls,'rendered defaults do not materialize facts or instruments');
  change('search_space/leadership','2, 6');change('search_space/musician_instrument_hands/1',false);
  assert(JSON.stringify(read().search_space.leadership)==='[2,6]'&&JSON.stringify(read().search_space.musician_instrument_hands)==='[2]','manual generator hand choices stay numeric and Leadership stays a distinct Skill range');
  document.body.dataset.musicianCheck='passed';
 }catch(error){document.body.dataset.musicianError=error.stack;document.body.append(document.createTextNode(error.stack));}
})();
</script>
'''


@unittest.skipUnless(BROWSER, 'installed Edge/Chromium required for actual editor checks')
class MusicianUiSourceTests(unittest.TestCase):
    def test_actual_editor_preserves_sources_and_edits_real_tools_and_gm_facts(self):
        initial = json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
        initial['party'] = initial['party'][:1]
        stub = '<script>window.fetch=async url=>{if(url!=="/api/request")throw Error("Unexpected request: "+url);return new Response('
        stub += json.dumps(json.dumps(initial)) + ',{status:200,headers:{"X-TOWR-UI-Mode":"manual"}});};</script>'
        page_source = PAGE.replace('<!doctype html>', '<!doctype html>' + stub, 1) + CHECK
        with tempfile.TemporaryDirectory(prefix='towr-musician-editor-') as temporary:
            folder = Path(temporary)
            page = folder / 'editor.html'
            page.write_text(page_source, encoding='utf-8')
            arguments = ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                '--dump-dom', '--virtual-time-budget=2000', '--user-data-dir=' + str(folder / 'profile'), page.as_uri()]
            if os.name == 'nt':
                quote = lambda value: "'" + value.replace("'", "''") + "'"
                output, errors = folder / 'dom.txt', folder / 'errors.txt'
                command = (f'$p=Start-Process -FilePath {quote(BROWSER)} '
                    f'-ArgumentList {quote(subprocess.list2cmdline(arguments))} -WindowStyle Hidden -Wait -PassThru '
                    f'-RedirectStandardOutput {quote(str(output))} -RedirectStandardError {quote(str(errors))}; exit $p.ExitCode')
                result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                    capture_output=True, timeout=30)
                dom = output.read_text(encoding='utf-8')
            else:
                result = subprocess.run([BROWSER, *arguments], capture_output=True, timeout=30)
                dom = result.stdout.decode('utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('data-musician-check="passed"', dom, html.unescape(dom[-3500:]))


if __name__ == '__main__':
    unittest.main()
