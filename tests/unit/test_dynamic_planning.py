"""Actual browser execution of the deterministic workload and planning policy."""
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from towr.adapters._local_ui_planning import PLANNING_SCRIPT
from towr.adapters._local_ui_visual import VISUAL_SCRIPT


BROWSER=os.environ.get('TOWR_UI_BROWSER') or shutil.which('chromium') or shutil.which('google-chrome')
if not BROWSER:
    edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    BROWSER=str(edge) if edge.is_file() else None


CHECK=r'''
const copy=value=>JSON.parse(JSON.stringify(value));
const canonical=value=>JSON.stringify(value);
const assert=(condition,name)=>{if(!condition)throw Error(name);};
const budget=plan=>plan.max_candidates*plan.exploration_trials+plan.top_k*plan.finalist_trials;
const standard=copy(inputs.melee);standard.npc_count={minimum:1,maximum:10};standard.max_rounds=15;
standard.targets={win_rate:{numerator:1,denominator:2},started_rounds:{numerator:5,denominator:1}};
standard.search.max_total_trials=100;
const original=canonical(standard),baseTime=estimatedSearchTime(standard),basePlan=automaticSearchPlan(standard);
assert(baseTime.low>0&&baseTime.high>=baseTime.low,'positive ordered time interval');
assert(canonical(standard)===original,'estimation and planning do not mutate the input');
assert(basePlan.max_candidates>=8&&basePlan.max_candidates<=64,'ordinary capacity explores a useful range of candidates');
assert(basePlan.exploration_trials>=8&&basePlan.top_k<=basePlan.max_candidates,'screening and finalists are bounded');
assert(Number.isSafeInteger(budget(basePlan))&&budget(basePlan)<=searchCostModel.maxTrials,'automatic trial budget stays bounded');
const moreTrials=copy(standard);moreTrials.search.max_total_trials*=2;
assert(estimatedSearchTime(moreTrials).low>baseTime.low&&estimatedSearchTime(moreTrials).high>baseTime.high,'more trials increase both time bounds');
const ranged=copy(standard);ranged.party[0]=copy(inputs.mixed.party[0]);
assert(estimatedSearchTime(ranged).high>baseTime.high,'PC ranged equipment contributes to cost');
assert(budget(automaticSearchPlan(ranged))<budget(basePlan),'costlier ranged party receives fewer automatic trials');
const costly=copy(ranged);costly.npc_count={minimum:10,maximum:10};costly.max_rounds=30;costly.targets.started_rounds.numerator=15;
const costlyCapacity=Math.max(searchCostModel.minTrials,Math.min(searchCostModel.maxTrials,Math.floor(searchCostModel.targetSeconds/simulationCostEstimate(costly).seconds)));
const costlyPlan=automaticSearchPlan(costly);
assert(costlyCapacity<192&&costlyPlan.exploration_trials===8,'limited capacity preserves breadth with eight screening trials');
assert(costlyPlan.finalist_trials>0&&budget(costlyPlan)<=costlyCapacity,'fallback retains independent validation within the same capacity');
const noShield=copy(ranged);noShield.party[0].equipment.armour=[];
assert(estimatedSearchTime(ranged).high>estimatedSearchTime(noShield).high,'actual Shield kind contributes to cost independently');
const noBackup=copy(noShield);noBackup.party[0].equipment.weapons=noBackup.party[0].equipment.weapons.filter(item=>item.location!=='carried');
assert(estimatedSearchTime(noShield).high>estimatedSearchTime(noBackup).high,'carried melee backup contributes independently');
const highRangedDice=copy(ranged);highRangedDice.party[0].characteristics.ballistic_skill=8;highRangedDice.party[0].characteristics.initiative=8;
assert(estimatedSearchTime(highRangedDice).high>estimatedSearchTime(ranged).high,'actual BS and Initiative contribute to cost');
const mage=copy(ranged);mage.party.push(copy(inputs.mage.party[0]));
assert(estimatedSearchTime(mage).high>estimatedSearchTime(ranged).high,'caster and extra actor contribute to cost');
const oneSpell=copy(mage);oneSpell.party.at(-1).magic.memorised_spells=oneSpell.party.at(-1).magic.memorised_spells.slice(0,1);
assert(estimatedSearchTime(mage).high>estimatedSearchTime(oneSpell).high,'spell choices contribute independently');
const talented=copy(standard);talented.party[0].talents=['defensive_stance'];
assert(estimatedSearchTime(talented).high>baseTime.high,'PC combat talents contribute to cost');
const many=copy(standard);many.npc_count.maximum=20;
assert(estimatedSearchTime(many).high>baseTime.high,'more NPCs increase cost at the same trial count');
const longer=copy(standard);longer.max_rounds=30;longer.targets.started_rounds.numerator=10;
assert(estimatedSearchTime(longer).high>baseTime.high&&budget(automaticSearchPlan(longer))<budget(basePlan),'longer encounters increase cost and reduce trial capacity');
const meleeNpc=copy(standard);meleeNpc.search_space=planningSearchSpace(standard);meleeNpc.search_space.weapon=['staff'];meleeNpc.search_space.allowed_talents=[];
const rangedNpc=copy(meleeNpc);rangedNpc.search_space.weapon=['pistol'];
assert(estimatedSearchTime(rangedNpc).high>estimatedSearchTime(meleeNpc).high,'NPC ranged component contributes to cost');
const npcTalent=copy(meleeNpc);npcTalent.search_space.allowed_talents=['wild_attack'];
assert(estimatedSearchTime(npcTalent).high>estimatedSearchTime(meleeNpc).high,'permitted NPC talents contribute to cost');
const finite=copy(meleeNpc);finite.npc_count={minimum:1,maximum:1};
for(const key of Object.keys(finite.search_space))finite.search_space[key]=finite.search_space[key].slice(0,1);
assert(automaticSearchPlan(finite).max_candidates===1,'finite source space caps candidates');
const extreme=copy(standard);extreme.targets.win_rate={numerator:99,denominator:100};
assert(basePlan.finalist_trials>automaticSearchPlan(extreme).finalist_trials,'central win target reserves more independent precision');
const reseeded=copy(standard);reseeded.search.master_seed='101';
assert(canonical(automaticSearchPlan(reseeded))===canonical(basePlan),'seed does not change deterministic workload allocation');
assert(canonical(executionCostEstimate(standard))===canonical({...simulationCostEstimate(standard),startupSeconds:0}),'sequential workload estimate remains unchanged');
let previousTime=baseTime.high,previousBudget=budget(basePlan);
for(const workers of [2,3,4]){
 const parallel=copy(standard);parallel.execution={mode:'process',workers};
 const before=canonical(parallel),time=estimatedSearchTime(parallel),plan=automaticSearchPlan(parallel),cost=executionCostEstimate(parallel);
 assert(time.low>0&&time.high>=time.low&&time.high<previousTime,'measured process throughput reduces ordered ETA at '+workers+' workers');
 assert(budget(plan)>previousBudget&&budget(plan)<=searchCostModel.maxTrials,'process throughput increases bounded useful trial allocation at '+workers+' workers');
 assert(cost.startupSeconds+budget(plan)*cost.seconds<=searchCostModel.targetSeconds,'process automatic plan fits same wall target including one pool startup');
 assert(canonical(parallel)===before,'process planning and ETA preserve full source');
 previousTime=time.high;previousBudget=budget(plan);
}
const four=copy(standard);four.execution={mode:'process',workers:4};
const manyWorkers=copy(four);manyWorkers.execution.workers=61;
assert(canonical(estimatedSearchTime(manyWorkers))===canonical(estimatedSearchTime(four))&&canonical(automaticSearchPlan(manyWorkers))===canonical(automaticSearchPlan(four)),'unmeasured worker counts receive no fabricated additional speedup');
const oneWorker=copy(four);oneWorker.execution.workers=1;
assert(estimatedSearchTime(oneWorker).high===baseTime.high+searchCostModel.processStartupSeconds,'one process retains sequential throughput plus pool startup');
for(const execution of [null,{},[],{mode:'other'},{mode:'sequential',workers:2},{mode:'process'},{mode:'process',workers:true},{mode:'process',workers:0},{mode:'process',workers:62},{mode:'process',workers:2.5},{mode:'process',workers:4,batch_size:1}]){
 const invalid=copy(standard);invalid.execution=execution;
 assert(estimatedSearchTime(invalid)===null,'invalid execution receives no invented ETA');
 let rejected=false;try{automaticSearchPlan(invalid);}catch(_){rejected=true;}
 assert(rejected,'invalid execution cannot produce an automatic precision plan');
}
const manual=copy(standard);manual.search={master_seed:'987',max_candidates:3,exploration_trials:2,top_k:2,finalist_trials:7,max_total_trials:999};
manual.execution={mode:'process',workers:4};
controls['auto-search'].checked=false;applySearchPlan(manual);
assert(canonical(manual.search)===canonical({master_seed:'987',max_candidates:3,exploration_trials:2,top_k:2,finalist_trials:7,max_total_trials:20}),'manual settings and seed survive; budget is derived');
assert(canonical(manual.execution)===canonical({mode:'process',workers:4}),'manual precision preserves explicit process execution');
controls['auto-search'].checked=true;const automatic=copy(standard);applySearchPlan(automatic);
assert(automatic.search.master_seed===standard.search.master_seed&&automatic.search.max_total_trials===budget(automatic.search),'automatic application preserves seed and exact budget');
const automaticProcess=copy(four);applySearchPlan(automaticProcess);
assert(canonical(automaticProcess.execution)===canonical(four.execution)&&automaticProcess.search.master_seed===four.search.master_seed,'automatic precision preserves process mode and seed');
assert(estimatedSearchTime({})===null,'invalid inputs have no invented estimate');
document.body.dataset.planningCheck='passed';
document.body.textContent=JSON.stringify({basePlan,baseTime,rangedPlan:automaticSearchPlan(ranged),rangedTime:estimatedSearchTime(ranged),mageTime:estimatedSearchTime(mage)});
'''


def planning_document():
    folder=Path('docs/examples/dynamic')
    inputs={name:json.loads((folder/file).read_text('utf-8')) for name,file in (
        ('melee','search.request.json'),('mixed','pc-ranged.request.json'),('mage','elemental-mage.request.json'))}
    # Reuse the actual editor's active-item predicate; no simulated equipment parser.
    ranged_set=re.search(r'pcCloseRangedWeapons=new Set\(\[[^\n]+?\]\)',VISUAL_SCRIPT).group()
    ranged_function=re.search(r'function playerInitialRangedWeapon\(member\)\{[^\n]+\}',VISUAL_SCRIPT).group()
    dependencies="const controls={};const byId=id=>controls[id]||(controls[id]={checked:false});let busy=false;const syncForm=()=>{},message=()=>{};"
    program=dependencies+'const '+ranged_set+';'+ranged_function+PLANNING_SCRIPT
    program+='const inputs='+json.dumps(inputs)+';try{'+CHECK+"}catch(error){document.body.dataset.planningError=error.stack;document.body.textContent=error.stack;}"
    return '<!doctype html><html><body><script>'+program+'</script></body></html>'


@unittest.skipUnless(BROWSER,'installed Edge/Chromium required for actual JS policy checks')
class DynamicPlanningTests(unittest.TestCase):
    def test_workload_precision_manual_override_and_seed_in_actual_javascript(self):
        with tempfile.TemporaryDirectory(prefix='towr-planning-') as temporary:
            folder=Path(temporary)
            page=folder/'planning.html';page.write_text(planning_document(),encoding='utf-8')
            arguments=['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--dump-dom','--virtual-time-budget=1000','--user-data-dir='+str(folder/'profile'),page.as_uri()]
            if os.name=='nt':
                quote=lambda value:"'"+value.replace("'","''")+"'"
                output,errors=folder/'dom.txt',folder/'errors.txt'
                command=(f'$p=Start-Process -FilePath {quote(BROWSER)} '
                    f'-ArgumentList {quote(subprocess.list2cmdline(arguments))} -WindowStyle Hidden -Wait -PassThru '
                    f'-RedirectStandardOutput {quote(str(output))} -RedirectStandardError {quote(str(errors))}; exit $p.ExitCode')
                result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,timeout=25)
                dom=output.read_text('utf-8')
            else:
                result=subprocess.run([BROWSER,*arguments],capture_output=True,timeout=25)
                dom=result.stdout.decode('utf-8',errors='replace')
            self.assertEqual(result.returncode,0,result.stderr[-1500:])
            self.assertIn('data-planning-check="passed"',dom,html.unescape(dom[-2500:]))


if __name__=='__main__':
    unittest.main()
