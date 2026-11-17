# Процессное исполнение динамического генератора

Дата: 2026-11-17. Согласованная граница: [ADR-0129](../decisions/ADR-0129-dynamic-process-execution.md). Машина Windows/Python3.12,16логических CPU. Замеры относятся к этой машине и текущему supported set.

## Методика

Backend сравнивается на точных сохранённых входах [предыдущего полного замера](dynamic-full-auto-plan-2026-11-17.md). Меняется только `execution` с sequential на process/4; seed42, партия, диапазоны, цели и весь план прежние. Один pool живёт от начала до конца поиска; `search_seconds` включает startup/shutdown и aggregate, encoding замерен отдельно. Кандидаты адаптируются последовательно. В deep comparison отчёта нормализуется только `source_request.execution`; остальные поля, составы, ranking, seeds, summaries и executable replays должны совпасть полностью.

Команда повторного воспроизведения с сохранёнными экспортами:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/process-fixed-plans/mixed.request.json .cache/process-fixed-plans/mixed-magic.request.json --output .cache/dynamic-process-fixed-2026-11-17.json
```

Локальные raw artifacts содержат полный source_request, hashes исходников/harness, фактические batches и результаты. Существующий sequential baseline повторно не вычислялся. Полные планы и результаты ниже переносимы через исходный отчёт и входы developer harness; `.cache` не является поставляемым API.

## Предварительная калибровка

На фиксированных финальных составах старого поиска запущено12trials, с новым холодным pool для каждого измерения. Все типизированные результаты полностью совпали с sequential.

| Партия | Sequential | Process2 | Process3 | Process4 | Process8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Смешанная2PC,6NPC |34.348s|26.230s|16.880s|12.795s|10.345s|
| С магом (Wizard),3PC,10NPC |76.835s|55.141s|36.845s|28.563s|21.101s|

Четыре процесса дали около2.69×, восемь —3.32–3.64×: масштабирование нелинейно. Пользователь выбрал автоматический предел4. Для UI взяты более осторожные credits1.25/1.9/2.5для2/3/4workers и3s на единственный pool. Для большего числа workers дополнительный credit не вводится. Это общая модель ETA и автоматического бюджета, ручные планы сохраняются.

## Полные неизменные планы

| Партия | Trials | Sequential search | Process4 search | Ускорение | Полный отчёт |
| --- | ---: | ---: | ---: | ---: | --- |
| Смешанная2PC |194|706.593s|260.515s|2.71×|совпал после нормализации execution|
| С магом (Wizard),3PC |174|962.455s|349.482s|2.75×|совпал после нормализации execution|

Process encoding занял0.700/0.438s. С учётом encoding ожидание сократилось с11.79до4.35мин и с16.05до5.83мин. Оба отчёта полностью совпали после нормализации единственного execution-поля; в368trials нет новых unsupported/исходов. Статистическая точность этих поисков осталась прежней: количество trials не менялось. Ускорение backend само по себе не добавляет независимых наблюдений.

## Увеличенный автоматический план

Точный JavaScript планировщика исполнен в headless Edge с прежними party facts/seed42, NPC1–10, целью50%/5раундов и cap15, но с process/4. Новый план для mixed-magic:18×12screening +2×110validation =436trials; раньше10×8 +2×47 =174. Для mixed он формирует20×12 +2×122 =484; второй увеличенный полный поиск не повторяется ради матрицы. Расчётная точка бюджета —750s, широкий ETA для обоих планов301–1493s.

Измеряется один полный сложный mixed-magic план:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/process-auto-plans/mixed-magic.request.json --output .cache/dynamic-process-auto-2026-11-17.json
```

Вход/manifest: `.cache/process-auto-plans/`; raw result и run.log рядом с output. Source не меняется во время исполнения. Этот поиск проверяет стоимость нового автоплана, а не parity на старом количестве trials: меняются screening, proposals и составы финалистов. Между-seed устойчивость и гарантия глобального оптимума из одного такого запуска не следуют.

### Результат

Завершены436/436trials,18составов/18proposals, proposal cap не достигнут. Screening counts: `[6,7,7,3,10,7,7,6,10,9,10,9,10,9,5,3,10,9]`. Search895.418s, encoding1.093s: вместе896.511s =14.94мин. Это на19.5%выше центрального ориентира750s, в широком ETA301–1493s и в пользовательском диапазоне10–15мин. Диагностические повторы unsupported отдельно заняли8.781s; UI их не исполняет, в search/trials они не включены.

| Финалист | NPC | Validation | Wilson95 | Средние started rounds | Unsupported | Выбор |
| --- | ---: | --- | --- | ---: | ---: | --- |
| `validate:0` |10|75/110 (68.18%)|58.99–76.15%|5.900|0|единственный допустимый|
| `validate:1` |10|67/110 (60.91%)|51.57–69.51%|6.091|2|исключён|

Во всём поиске0round-limit,3unsupported; failures исполнения нет. Выборка финалиста выросла47→110, интервал допустимого состава уже прежнего. Однако расстояние до цели50%ухудшилось:18.18п.п. вместо3.19п.п. старого174-trial плана; ошибка длительности0.900вместо0.787. **На этом запуске больше вычислений не улучшило качество подбора.** Между режимами при одинаковом плане parity подтверждена отдельно; здесь результат изменился из-за другого автоплана и обнаруженных остановок.

Все три остановки подтверждены диагностическим replay:

| Состав / trial index | Причина | Контекст |
| --- | --- | --- |
| `explore:16` /8 | `ranged_grip_unavailable` | PC Wound sequence4, table18, clutch stomach; загруженный пистолет выпал |
| `validate:1` /94 | `pc_magic_miscast_unresolved` | mage, Fascinating Rift, Miscast total38 |
| `validate:1` /100 | `ranged_grip_unavailable` | PC Wound sequence5, table16, unusable arm; загруженный пистолет выпал |

Последующая адресная диагностика подтвердила: в обоих grip-путях правая рука недоступна после16, левая занята clutch18, `usable_hands=()`, loaded=true; Sword остаётся carried. Фактический fallback — Attack, не Reload. Подстрока `:reload:` принадлежит ID состояния оружия, а не доказывает выбранное действие. Руки для draw/pickup/стрельбы действительно нет; ошибки доступной смены оружия не обнаружено. PG1.4 Appendix190–191 согласуется с исполнением. Позднее пользователь согласовал fallback на standard Recover по [ADR-0130](../decisions/ADR-0130-automatic-pc-recover-with-no-usable-hands.md); оба trials после изменения завершились реальным поражением партии. Все полные search-числа этого отчёта относятся к состоянию до ADR-0130 и не пересчитывались.

Диагностика воспроизвела исходные два trials без изменения source/seed (9.331s на оба); prepared regression для обоих порядков16→18/18→16 и положительного случая одной пригодной руки добавлена к `tests.unit.test_pc_ranged_advice`:21OK/0.116s. Production в рамках диагностики не менялся, полный поиск не повторялся. Локальные `.cache/grip-explore-16.pickle` и `.cache/grip-validate-1.pickle` — временные результаты анализа, не публичный save/resume формат.

Fascinating Rift сохраняет уже известную GM/spatial границу магии; эффект не превращён в no-op. Из-за любого observed unsupported состав исключается по действующему контракту, даже если его win point ближе к цели. Следующая работа опирается на эти реальные случаи и устойчивость поиска; ускорение не является доказательством улучшения его качества.

## Прогресс, отмена и диагностика

Unit scheduler проверяет ограничение in-flight, переиспользование pool, обратный порядок завершения, полную проверку batch до callbacks и cleanup при ошибке worker/observer. Реальные spawn-проверки сравнивают records, отменяют уже выполняющийся RNG и validation, проверяют завершение дочерних процессов до acknowledgement и успешный следующий запуск. Ошибки не превращаются в частичный успешный result или fallback.

Developer harness выполняет заявленный execution, переиспользует Session и считает уникальные доставленные индексы. Failure artifact сохраняет их явно. При process первый ещё не доставленный индекс не обязательно является индексом упавшего trial; точный контекст исключения worker содержится в `error_notes` с index/seed. Heartbeat отражает число принятых records, а не максимальный индекс.

## Адресная проверка

Выполнены отдельные группы; это не единый full regression. На Windows реальные spawn/Edge/tempfile запускались вне sandbox после ранее подтверждённых WinError5.

- Scheduler и dynamic JSON/process CLI:16OK/6.803s (`tests.unit.test_pc_process_session tests.integration.test_dynamic_process_json`).
- Реальные spawn/reuse, отмена внутри worker/validation и exception cleanup:4OK/9.979s (`tests.integration.test_dynamic_process_execution`).
- Execution API и developer harness, включая unordered accounting/failure source:12OK/3.314s (`tests.unit.test_dynamic_execution_options tests.unit.test_dynamic_benchmark`).
- Фактический JavaScript в Edge и CPU-aware defaults/explicit file preservation:4OK/2.393s (`tests.unit.test_dynamic_planning tests.unit.test_local_ui_execution_defaults`).
- Повторная лёгкая проверка execution API/defaults после интеграции:6OK/0.031s.
- После завершения всех замеров усилена только revalidation typed execution при encode: одинаковые по Python equality `4.0/4`, `True/1`, plain string/Enum не обходят guards. Текущие admission и реальные process JSON/CLI smoke повторены:9OK/6.541s (`tests.integration.test_dynamic_process_json`), лог `.cache/adr129-final-source-guards.log`. Нормальные запросы, backend и планировщик не менялись; дорогие замеры не повторялись.

Сквозная группа:55OK/61.004s; лог `.cache/adr129-addressed-validation.log`:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m unittest tests.integration.test_local_ui tests.integration.test_local_ui_browser tests.integration.test_dynamic_encounter_json tests.unit.test_dynamic_encounter_progress tests.integration.test_m9_pc_melee_simulation tests.integration.test_m12_pc_heavy_wounds tests.integration.test_m53_shield_process tests.integration.test_m55_pistol_shield_process tests.integration.test_dynamic_pc_ranged_json.DynamicPcRangedProcessTests tests.integration.test_dynamic_pc_magic.PcMagicProcessParityTests tests.integration.test_dynamic_potions.PotionProcessParityTests -q
```

Она охватывает реальную HTTP process-генерацию, progress, cancel→занятый job→cleanup→новый Run, browser, текущий JSON/CLI и репрезентативные native melee/heavy Wounds/Shield/Pistol/ranged/magic/potions. Старые проверки pool admission обновлены на фактического владельца `pc_melee_process`, без ослабления source/pickle guards. Полный regression и wheel не запускались: проверены затронутые process consumers, сборка/доставка не менялись.
