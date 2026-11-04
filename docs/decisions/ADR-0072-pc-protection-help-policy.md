# ADR-0072: Help для намеченного Protection Test

Дата: 2026-11-04. Статус: **M16 реализована и адресно проверена в указанной границе**.

## Решение и граница

После M15 пользователь поручил продолжить Help для защиты союзника. Сохраняются нынешние PC melee, numeric Minions/Brutes, одна Close Zone, общий PC-side→NPC-side clock и явные роли. Protection Help предназначается для одного будущего Test, а не создаёт общий защитный бонус на раунд.

Ненулевая `PcHelpPolicy` теперь требует три поля: `beneficiary_id`, `target` и `protection_skill`. При `target: melee_attack` skill равен null и действуют условия M15. При `target: first_incoming_protection` требуется Defence либо Athletics; helper Test использует тот же Skill, поэтому нового GM approval для смешанных Skills нет. Mode участника остаётся `help_ally_or_attack_or_recover_self`, у обычного PC `help_policy: null`.

Получатель остаётся другим обычным PC этой party, без Help chains. Для Protection он может стоять раньше помощника и уже завершить свой ход: NPC-side ещё впереди. Для Melee Attack остаётся требование более позднего хода. Self Recover помощника имеет прежний приоритет; нужна пригодная рука/оружие, отсутствие Deafened/Defenceless. Помощь физическая, не зависит от слуха получателя. Использование руки и тяжёлые ограничения продолжают создавать книжные последствия.

## Выбор конкретной защиты

В момент Help берётся первый живой и ещё не завершивший ход NPC из `enemy_activation_order`. Текущий первый живой PC в `enemy_target_priority` должен быть выбранным получателем; иначе Help не выбирается. Получатель жив, не Defenceless/Drained, и его текущий Protection Skill совпадает с настройкой: Defence с пригодным оружием, иначе Athletics. Его собственный Recover и уже завершённый ход помощь защите не запрещают.

Snapshot связывается с точным ID Protection Test этого NPC в текущем раунде. Не предсказываются будущие попадания, убийства или результаты Tests; не выбирается «самый опасный» NPC. Конкретный NPC ID не хранится в authored policy, поэтому enemy count projection сохраняет весь выбор helper/beneficiary и использует первый оставшийся NPC уже внутри candidate encounter.

Если помощь недоступна, сохраняется прежняя Attack/Recover. Это ограниченная детерминированная тактика, а не дополнительные книжные запреты или optimal AI.

## Источники

Адресно проверены локальные extracted Player’s Guide1.4, гл.V Rules / Helping With a Test108, Combat Help117, Attack Tests118, Deafened/Drained123; строки14/15 Wounds Table190 использованы для source-aware Critical/Defenceless проверки. Книга прямо допускает Help для защиты, даёт +1d за успех и позволяет другой relevant Skill по GM. Defence доступен suitably armed, иначе Athletics; Defenceless не Oppose. Новых нормативных Rule IDs/house rules и полного перечитывания книги нет.

## Исполнение и источники

M15 `PcHelpProof` и `PcAttackProof.help_applications` используются для обеих сторон Attack. Generic preparation связывает actual earlier Help, beneficiary ID, Test ID и Skill. Исходные Protection options содержат подтверждённый Help до фактического initial roll; только затем собственная Glorious policy получателя может добавить свой modifier. Helper Glorious выбирается по `request.help_skill`, включая обычные Sword/Drained правила для Defence Test. Новый RNG или отдельная Attack arithmetic не вводятся.

Несколько snapshots складываются обычными bonus dice под прежним cap; нулевой Help сохраняет receipt и расход действия. Drained блокирует positive bonus dice, не стирая происхождение. Полный source/prefix/type admission, exact K1 applications и однократность остаются обязательными. Mutable банка бонусов или нового состояния owner нет.

Совпадение одного Test ID недостаточно: NPC после смерти цели мог бы атаковать другого PC с тем же сформированным ID, поэтому обязательна также точная связь beneficiary и actual Skill. Snapshot не заставляет Protection выбрать старый навык. Если союзник поднял оружие и Athletics сменился на Defence, бонус остаётся unused. Если намеченный NPC погиб, помощь не переходит к следующему NPC или раунду. Если получатель стал Defenceless, incoming Attack не создаёт Protection Test, applications или Glorious window. Допустимый unused snapshot не блокирует terminal outcome.

## Текущий контракт и отчёты

PC JSON остаётся единственным форматом1. У ненулевой Help configuration оба новых поля обязательны, старый объект только с beneficiary не принимается. M15 requests/results мигрированы как `melee_attack`/null без смены gameplay и прежних counters; M9–M14 с `help_policy: null` не меняются. [M16 examples](../examples/m16/README.md) исполняют Protection Help.

Существующие per-PC `help_action_counts`, trial count и total считают оба вида фактической помощи; target виден в полном request. Новые почти одинаковые counters не вводятся. Учитываются failed/unused actions; это не число добавленных кубов. Fate costs, полный denominator, indexed independent trials, sequential/process parity и aggregate-only ranking сохраняются. Generation не переписывает Help policy при удалении NPC.

## Проверка

Нативно проверены Defence Help, получатель до/после помощника, zero/multiple/cap, собственные Sword/Glorious обоих PC, гибель намеченного NPC при живом другом, Wound4/drop→Recover/pickup→смена Athletics на Defence и Wound15→Critical failure→Defenceless без Protection. Положительная Athletics application и Drained preparation проверяются отдельно на чистой границе с фактическим предшествующим Help receipt; это не выдаётся за отдельный исполненный бой с данным исходом. Source/skill/type/replay forgeries, fixed-policy generation, native trials, process/search, codec/schema и реальные CLI закрывают сквозной путь.

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m16_check_subsystem.py` выполнила **393 tests OK/69.786s**,39модулей PC M9–M16 и ближайших Protection/Help/Turn/Test/Fate/Drained/Wound consumers;0failures/errors/skips. Log `.cache/m16-pc-subsystem.log`. Код и тесты заморожены до запуска, это единый зелёный адресный прогон, не полный regression проекта.

В составе11новых native/pure Protection Help tests,4model/generation tests,4integration с actual Windows spawn/count search/cache guards и46current codec/schema tests. Независимое source/timing review не нашло дефекта. Оба M16 requests реально исполнены CLI; production с первого рабочего прототипа до checkpoint не менялась. Сохранение14старых request/result пар и их gameplay/prior counters проверено отдельно. Общий K1, сборка/dependencies/resources/entry points не менялись; full/wheel и повтор успешной дорогой матрицы не требовались.

Локальный launcher/log находятся в `.cache`; в чистой копии адресные проверки функции можно повторить без них:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m16_pc_protection_help tests.unit.test_m16_pc_protection_help_models tests.integration.test_m16_pc_protection_help tests.unit.test_m15_pc_help tests.unit.test_k1_protection_preparation tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -v
```

Перечисленные модули входят в выполненный checkpoint; это не заявление об отдельном дополнительном прогоне.
