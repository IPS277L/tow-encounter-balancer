# M70: Hochland, настоящий Aim и Fate Second Action

Три PC начинают на Short против четырёх authored numeric Melee Minions. NPC действуют по прежней тактике: подходят в Close, затем атакуют. [Правило](../../rules/equipment.md#pc-hochland-m70), [Fate](../../rules/fate.md#pc-second-action-m70), [контракт](../../decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md).

| PC | Primary | Как получает выстрел до подхода NPC |
|---|---|---|
| pc1 | Hochland | standard Aim → Second Action за1session Fate → Shoot |
| pc2 | Hochland, Fate0/Lucky | standard Aim → первый бесплатный Lucky spend → Shoot |
| pc3 | Sling | обычный выстрел, Aim/Second Action counters=0 |

У всех carried Sword/right backup. Hochland/BOTH без shield: Damage6/ignores armour, Short−1d, mandatory Aim, Reload4. Shared Wounds Table+1d не применяется к numeric Minions и не превращается в Damage. Два настоящих действия и ресурс записываются отдельно; Aim с0success тоже разрешает попытку второго действия. У третьего PC одноручный Sling и прежний free-reload путь.

Hochland ranged содержит10обязательных полей:

```json
"weapon": "hochland_long_rifle",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "awareness": 4,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

Per-participant policy в обоих Hochland loadouts:

```json
"fate_policy": "configured",
"aim_second_action_policy": {
  "minimum_remaining_session_spends": 0
}
```

Awareness использует Initiative; source Skill не выводится из Dexterity. Optional Awareness Glorious в первом срезе отклоняется, Shooting Glorious задаётся по прежним критериям и расходует остаток ресурса после Second Action. Policy отсутствует — Second Action не выбирается. При отсутствии funding или несоблюдении резерва PC выполняет обычный Aim без free Shoot, затем действует по прежнему Close→backup. Lucky разрешён только Hoc-source; неоплаченная первая трата также работает для выбранного Glorious, если Second Action не использован.

Aim одноразовый и привязан к actual actor/target/action receipt. Следующий собственный ranged Attack той же цели применяет его, другой action/Recover/melee теряет его. Incoming Protection/end phase не потребляют Aim. Штатный TurnEnd не может пропустить выбранный доступный Second Action; рана8/CANNOT_AIM запрещает новый Aim до RNG. Mandatory/hand/Critical/Defenceless/terminal guards сохраняются. Retained empty4 после Shoot не вызывает Reload у active melee backup.

В summary только Aim-capable source появляется block aim: action_counts/total_action_count и second_action_spend_counts/total_second_action_spend_count. Rows содержат всех PC, включая pc3 с нулями. Counts отражают события трат, в том числе Lucky-free, а не оплаченные session points. Glorious counts остаются отдельными и считают только GLORIOUS_TEST. В сценах без Hochland этого block нет, текущая wire version остаётся1.

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m70/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m70/pc-melee-balance.request.json
```

Actual CLI simulation seed42/4trials/6round budget:4objective/48actions/10started/6completed rounds, без потерь PC. Aim actions8/Second Action events8, rows4/4/0;4session-paid events у pc1 и4Lucky-free у pc2 в независимых trials. Count search3–4Minions:2candidate×2trials, по2objective,14/20actions, в каждом4Aim/4Second events и rows2/2/0. Это демонстрационные выборки, не точные вероятности или оптимальность стратегии.

[Simulation request](pc-melee-simulation.request.json), [result](pc-melee-simulation.result.json); [balance request](pc-melee-balance.request.json), [result](pc-melee-balance.result.json). Прежние244JSON M9–M69/NPC59/shared14 сохраняются. Нет setup turn до обнаружения, новых Zone/PC movement или безопасного fresh Aim→Shoot→Reload4→новый Aim→Shoot цикла.
