# ADR-0089: Dwarf Miner и явный grudge relationship

Дата: 2026-11-06. Статус: **полный контракт принят пользователем и реализован в M43**. Выбраны явные пары Miner→PC и прежний порядок выбора целей.

## Источники и механика

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Dwarf Miner105: Normal Minion, T4/Res6 armoured, Mining Pickaxe Close4d/3 Damage4,2H; Defence4d/3, alternate Athletics1d/3. Blasting Charge — отдельная ranged/Hazard атака, здесь unselected. Printed Test pools/Damage уже готовы; PC Pickaxe Traits/повторный weapon penalty не добавляются. Shield отсутствует, ordinary caps8/8; explicit pool_cap остаётся null.

Grudges to Settle: встреча с врагом, на которого есть grudge, накладывает Distracted; Miner получает+1d Melee против этого врага. BOOK-PLAYER-GUIDE1.4, гл.V Distracted123:−1d на Tests, включая Opposed, вне focus; другой Distracted заменяет прежний. Новый focus для этого источника — явно указанный grudge enemy, а не attacker первой раны. Как Minion, Miner после первой Wound defeated и не использует Brewguard W1 trigger.

Down in the Dark: игнорирование underground Difficult Terrain и запрет врагам получать bonus dice от higher ground против Miner. Вторую часть исполнять при подготовке входящего PC Melee, в том числе при Prone Miner. Terrain/movement не исполняются в fixed Close/noMove/noTerrain сцене.

В существующем PC source нет race/ancestry/past-insult данных; принадлежность к party или target priority не доказывает grudge. Связь задаёт caller как факт ведущего, без RNG или выдуманной общей racial policy.

## Принятый контракт

В native `PcMeleeScenario` и текущий PC JSON1 добавить обязательный `npc_grudge_policies`: exact tuple/list записей `PcNpcGrudgePolicy(actor_id, focus_actor_id)`.

```json
"npc_grudge_policies": [
  {"actor_id": "miner1", "focus_actor_id": "pc2"}
]
```

Разрешён canonical `DWARF_MINER_PICKAXE = dwarf_miner_pickaxe`, source `BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe`; actor должен быть opposition Miner, focus — включённый PC. Один Miner имеет не более одной пары; несколько Miners могут иметь одного focus. Self/unknown/wrong-side/other-profile IDs, дубликаты actor, равные неверные типы и пропущенное поле отвергаются до RNG. Несколько одновременных grudge enemies одного Miner этим срезом не моделируются.

`[]` явно утверждает отсутствие подтверждённых grudge relationships в данной сцене. Miner без записи не получает grudge Condition/bonus; остальные его свойства, включая Down in the Dark, сохраняются. Связь не выбирается автоматически из имени/расы/priority. Caller сохраняет исходный порядок списка в source echo; порядок применения encounter effects определяется source roster.

**Тактика прежняя:** Miner продолжает Attack по текущему `enemy_target_priority`. Grudge не перемещает focus на первое место и не включает преследование/Recover. Caller может сам задать нужный приоритет во входе, как прежде.

Count search удаляет пару при исключении её Miner, без переназначения; party остаётся фиксированной. Каждая projected composition начинает свежую встречу; между trials нет переноса Condition/history.

Wire version остаётся PC JSON1, новые costs/summary metrics не нужны. Все136прежнихJSON documents M9–M42 обновить обязательным `npc_grudge_policies: []` во входах и полных echoes, сохранив все остальные значения. Native builders задают required поле явно; defaults/compatibility ветви не добавляются.

## Встреча, focus и lifetime

Перед первым combat turn owner исполняет по одному typed encounter proof для выбранных Miners, в порядке source roster. Proof связывает полный source scenario/relationship и canonical Miner; исходные NPC snapshots остаются fresh/healthy без caller-injected Conditions. Наложение не расходует action, TurnStart/TurnEnd или RNG. Его нельзя отложить до первой атаки, пропустить или выполнить повторно.

Miner Distracted хранится отдельным source kind в owner-local bank M42. Brewguard first-Wound cause/receipt не переиспользуется. Generic ConditionState и Troll/Foul Stench/spell consumers не получают скрытую новую семантику.

Melee по grudge focus: обычный+1d, без штрафа Distracted. Melee по другому PC:−1d Distracted, без grudge бонуса. Protection против focus: без штрафа, но **без+1d**, поскольку выбранный Skill — Defence. Protection против другого PC:−1d. Positive ordinary bonus проходит cap/Drained, negative penalty сохраняется; named Help остаётся своим отдельным источником.

Grudge relationship и текущий Distracted — разные факты: Melee bonus определяется отношением к фактической цели, не одним флагом Condition. Поэтому будущее снятие/замена Distracted не должно автоматически уничтожать grudge bonus. В M43 Recover/Willpower/внешней замены нет.

Confirmed death focus снимает Distracted по PG123 через post-Wound/Fate expiry; raw lethal roll/Near Miss не подтверждают смерть, живой Defenceless сохраняет focus. Смерть не переназначает grudge другому PC. Remaining NPC actions используют прежний priority без старого penalty; encounter effect не накладывается каждый новый раунд. Потеря видимости, выход/повторная встреча и произвольное обновление grudge исключены fixed scene.

## Отклонённая меньшая альтернатива

Рассматривалось отложить variable grudge и добавить только ограниченный Miner loadout для сцены с явно подтверждённым отсутствием grudge. Нового source поля/миграции тогда не было бы, Grudges to Settle не срабатывал бы из-за ложного premise, а не отключался вопреки книге. Пользователь выбрал полный контракт выше; `[]` остаётся его явным no-grudge случаем.

## Проверенная граница

1. Exact catalog/source/2H/noShield/Res6/Defence versus alternate Athletics, full active/inactive Abilities; без PC Traits/повторного штрафа и без изменения42старыхentries.
2. Required exact policies/closed schema/native types; duplicate/wrong actor/focus/other book/authored и cached aliases до RNG. Full source echoes и subset filtering без переназначения.
3. Initial encounter proof до TurnStart/Test, ровно один source на выбранного Miner; `[]` даёт явное отсутствие grudge. Several actors/source order, source/replay guards и отсутствие action/RNG costs.
4. Actual focus versus другой PC в обеих Test ролях: Melee+1/−1, Protection0/−1. Проверить ordinary cap/Drained/Help и прежний target priority. Down in the Dark удаляет только enemy higher-ground bonus против Miner, сохраняя остальные modifiers и старых NPC.
5. Confirmed lethal/Critical focus death, Near Miss/Defenceless, no reapply в новом раунде, одновременные Brewguard и Miner причины без смешения происхождения.
6. Native → trials/summary → count search → current JSON1/schema → CLI-примеры. Миграция136старыхJSON сохраняет прочие наблюдения. Адресный PC checkpoint по влиянию на общий owner/preparation; full project/wheel/backend matrix только при отдельном основании.

Согласование получено от пользователя; оно требовалось по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь вводится обязательная публичная source policy для grudge relationships; имя/родословная врага не подменяются предположением модели.

Реализация: [policy/admission](../../src/towr/domain/pc_npc_grudge_policy_models.py), [encounter proof и relationship bonus](../../src/towr/domain/pc_npc_grudge_models.py), [общий source bank/expiry](../../src/towr/domain/pc_npc_distraction_models.py), [owner](../../src/towr/domain/pc_melee_result_models.py), [schema](../../src/towr/adapters/schemas/pc-melee-common.schema.json). Проверки: [catalog](../../tests/unit/test_m43_pc_miner_catalog.py), [native encounter/focus/lifetime](../../tests/unit/test_m43_pc_miner_grudge_execution.py), [JSON/trials/search](../../tests/integration/test_m43_pc_miner_grudge_json.py), [representative process parity](../../tests/integration/test_m43_pc_miner_process.py), [CLI-примеры](../examples/m43/README.md). Единый PC checkpoint75модулей/694tests OK за37.671s; отдельно process1test OK за1.798s. Все30новыхtests прошли. Фактические команды/ограничения/следующий шаг — в [статусе](../project-status.md).
