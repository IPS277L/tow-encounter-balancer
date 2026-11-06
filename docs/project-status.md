# Текущий статус проекта

Дата обновления: 2026-11-06.

## Текущий этап

**M47 завершена: Flagellant/Flails и Hooks and Chains, Feel No Pain и собственный Recover.** Пользователь выбрал полный [ADR-0092](decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md). Каталог49→51. [Правило](rules/npc-profile-catalog.md#flagellant-feel-no-pain-m47), [factory/JSON/CLI-примеры](examples/m47/README.md).

Оба loadouts — Normal Brute2/T3Res3 без брони/щита, Athletics3d3/caps6. Flails Close3d4Damage6/2H получает−2d Melee при Staggered; Hooks and Chains Close3d4Damage3/1H — без штрафа. PC weapon Traits/повторные penalties не добавляются. Direct Broken immunity Unbreakable сохраняет остальные Conditions и не превращается в psychological immunity.

Required `npc_flagellant_policies` содержит unique canonical opposition actor, exact feel_no_pain enum и recover_when_wounded bool, без default. `wound_at_zero` заменяет первое Staggered от incoming weak physical hit или своего miss одной Wound только при0; при1 добровольная замена не выбирается. Direct Wound не удваивается, repeated Staggered сохраняет прежнюю SUFFER_WOUND price/W2defeat. `[]` отказывается от обоих новых choices; Flails penalty/Unbreakable сохраняются. Подбор фильтрует записи исключённых NPC без переназначения.

Incoming replacement задаёт explicit `FirstStaggerWoundSpec` до Test: raw HIT/Damage/impact прежние, результат содержит один настоящий profile-Wound/ACK и Rule ID. Own miss имеет отдельный typed actor/source/profile-Wound witness, связывает рану с настоящим miss самого actor. Полный результат readmits exact types при replay; найденный при review cached-alias пропуск исправлен и покрыт регрессией.

Живой actor с1Wound и выбранным recovery тратит обычное действие на standard self Recover: реальные slot/receipt/TurnEnd, снятие своих Staggered/Prone и heal1→0, без RNG/PC Fate/второй Attack/revival. Каждое получение/лечение сохраняется в history, включая повторные циклы. Named helper атакует сам, когда его beneficiary будет Recover. Compact record/summary содержит отдельные NPC Recover counts/trial count/total; NPC Recover входит в total actions, PC costs отдельные.

152старыхJSON documents M9–M46 мигрированы только required policy arrays/нулевыми NPC Recover полями, остальные значения и49прежнихentries/definitions/snapshots/metadata сохранены. Current PC JSON1 остаётся1. Обратные defaults/старые версии не добавляются.

## Последняя проверка

Из-за новых Stagger/Wound, owner/Recover и record/summary seams выполнен расширенный адресный checkpoint109модулей/1044tests: **1038успехов и6environment errors Windows Pipe WinError5 в sandbox**,0gameplay/assertion failures,70.032s. Фактическая команда при `PYTHONPATH=src`: `.venv/Scripts/python.exe .cache/m47_checkpoint.py`. Выбраны PC unit M9–M47, K1 Test/Kernel/Stagger/secondary/Conditions/Recover, M6/M7 runners/M8Minion и ближайшие PC simulation/balance/exit/Help/extra/JSON integrations. Локальные selector/module list/log не входят в репозиторий.

Только6упавших process cases затем повторены вне sandbox с новым M47 process parity: **7tests OK за17.364s**. Проверены party losses, exit, Help, balance spawn, uneven batches/worker exception и полные Flagellant policy/Recover counts records+summary. Команда: `Get-Content .cache/m47_process_retry_names.txt` в task-specific PowerShell array, затем `.venv/Scripts/python.exe -m unittest @m47RetryNames -v`. Windows Pipe граница прежняя; backend механизм не менялся. Это составная адресная проверка, не единый зелёный full run; успешные1038tests не повторялись.

Все49новыхtests прошли:12K1,9catalog,19native,8JSON/statistics/search,1process. Независимое review после исправления exact miss-witness проверки новых дефектов не нашло. Переносимая адресная команда нового поведения:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_k1_first_stagger_wound tests.unit.test_m47_pc_flagellant_catalog tests.unit.test_m47_pc_flagellant_execution tests.integration.test_m47_pc_flagellant_json tests.integration.test_m47_pc_flagellant_process -v
```

Literal scripts проверяют incoming weak hit/own miss и правильного actor, accepted/declined/W1 choices, direct Wound без второй/repeated Wound/W2disposition, Flails−2/Drained, real Recover benefits/receipts/cycles/no RNG/no revive, Help fallback, Broken-only immunity, skip/replay/source/alias guards. Scripted compact observations доказывают точные Recover costs отдельно от PC benefits; schema/full echoes/4count compositions и invalid source/counter types проверены.

Оба requests M47 исполнены настоящим sequential CLI. Simulation seed42/6trials/budget5rounds, один PC Staff против1Flails+1Hooks:0objective/2party defeated/4limit/0unsupported,83actions,28started/26completed rounds. PC погиб в2trials; во всех6trials был NPC Recover,26actions всего (Flails19/Hooks7). Balance1–2Flails+0–1Hooks,4состава по2trials:20/30/30/21actions и7/11/11/5NPC Recover, unsupported везде0. Полная таблица в примере; малые выборки не задают истинные вероятности/оптимум, ROUND_LIMIT остаётся отдельным исходом.

Финальная проверка `.venv/Scripts/python.exe .cache/m47_verify.py` прошла:78current request/result pairs M9–M47/full source echoes, сохранение остальных значений152старыхJSON documents после удаления только policy/Recover fields и всех49прежнихcatalog entries/definitions/snapshots/metadata. Проверены40изменённыхMarkdown файлов/2069локальныхссылок, UTF-8/whitespace и `git -c core.safecrlf=false diff --check`. .cache helpers/logs локальные и не входят в репозиторий.

Полный regression проекта, wheel и полная backend/console матрица не запускались. Новый Kernel branch включается только explicit spec; обычные paths проверены K1 и соседними families. Доставка/backend механизм не менялись, новая схема остаётся в прежнем JSON discovery. Успешные игровые проверки после документальных правок не повторяются.

## Ограничения

M47 recovery только standard self Flagellant с1Wound; общего NPC Recover/лечения при profile Wound других существ нет. Feel No Pain policy покрывает incoming physical hit/own miss, не все будущие producers Staggered. Новый Broken producer/общая миграция Condition provenance не добавлены. Fixed Close/noMove/noExternal/all-included arena и прежние PC Wounds1–23/lethal24+/Critical/Defenceless/backup/Fate/Help/Recover/NPC exit сохраняются.

Skin Wolf/его end-turn Warped Form и регенерация ещё не подключены; Blood Rage policy M46 Bestigor-only. Miner/Brewguard Distracted, Bear extra Attack и Thief Stealth остаются своими source-bound случаями. Dragon Ogre не добавлен до уточнения [shield/Resilience7/8](open-questions-details.md#dragon-ogre-shield-resilience). Net/inventory/campaign/save-resume, Greatsword Defence bonus и невозможная повторная анатомия сохраняют отдельные вопросы/точные stops; costs/losses при stop/limit относятся к исполненному prefix.

## Следующий шаг

**Подготовить M48 — Skin Wolf / Claws and Fangs с Blood Rage и Warped Form (GM187).** Полная карточка ранее адресно прочитана. Описать явные choices перед Attack и в end phase, heal неогненной Wound при отсутствии Staggered и Staggered для допустимых Close creatures. Согласовать target snapshot/порядок/self inclusion, source Wound/heal history и обязательные PC/NPC последствия, включая Feel No Pain/повторный Staggered/Fate. В нынешнем physical melee source нет огневого урона; это premise bounded-среза, не универсальный default. Новый end-turn heal не подменять Flagellant Recover; расширение Bestigor-only Rage policy и новая тактика требуют конкретного ADR/согласования. M48/scope ещё не выбраны. [Очередь](roadmap.md), [вопросы](open-questions.md).

Незакоммиченные изменения M31–M46 сохранены; текущая рабочая копия охватывает M31–M47. Commit/push выполняет пользователь.
