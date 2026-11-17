# ADR-0134: распределение предложений и наблюдаемость операторов

Дата: 2026-11-17. Статус: наблюдаемость реализована с сохранением прежней стратегии; новое расписание проверено и отклонено. План записан до candidate измерений.

## Основание и независимая диагностическая часть

[ADR-0133](ADR-0133-directed-numeric-component-mutation.md) не изменил первые рекомендации. Cached decision replay короткой серии показал9component-вызовов, а в одном поиске0; в старом полномC18плане их6. Это измерение ограниченной экспозиции, не доказательство дефекта распределения. Следующая гипотеза меняет **выбор операции**, сохраняя прежние resize±1, single-NPC random mutation, score, C/E/V и kernel. Числовая policy ADR-0133 снята и не является вторым фактором.

Сначала существующее создание одного предложения извлекается в private `_propose(request, explored, rng, operation)`. Его frozen результат содержит requested/applied operation и composition. Private selector сначала полностью сохраняет старые random70%/30% и count/component parity; прежний порядок RNG-вызовов внутри ветвей сохраняется, включая выбор elite перед count-parent. На этом исходнике подтверждаются полные actual JSON controls и cached decision/source parity прежних шести поисков/полногоUI202. Это отдельная диагностическая основа без изменения поведения поиска.

Существующий developer harness наблюдает один вызов `_propose` на попытку: requested/applied, count, duplicate; агрегаты сверяются с proposal_attempts/числом explored. Обёртка возвращает тот же объект, не расходует RNG и не добавляет игровых фактов. Это только developer artifact, не новый public JSON/UI/progress callback. Диагностический helper/наблюдаемость могут остаться после отрицательного candidate при доказанной parity; откат нового расписания выполняется к этому проверенному baseline, сохраняя старую стратегию ADR-0128 и все прежние изменения пользователя.

## Одна изменяемая стратегия

Первый состав — прежний random restart. После него используется повторяющийся цикл запросов:

`count, component, restart, count, component, restart, count, component, restart, count`.

Это4count/3component/3restart на каждые10последующих **попыток**, а не30%-вероятность каждого отдельного шага. На границе цикла возможны два count подряд; каждый меняет количество максимум на1. Для шести уникальных предложений без дубликатов, включая первое, requested counts2/component2/restart2; дляC18—7/5/6. При дубликате цикл продвигается по номеру попытки, а не числу принятых составов: недоступная мутация не блокирует будущий restart. Global30×C cap остаётся прежним.

Count использует прежний `_directed_count_parent`; при min=max/границе/точном target/нет supported parent фактическая операция — component. Неверное движение не навязывается. Component меняет один NPC/одно допустимое поле старым mutate; restart заново выбирает count и компоненты во всём разрешённом пространстве. Метаданные различают запрос и применённую операцию. При фиксированном count это7component/3restart на полный цикл, без несуществующего resize. Неизменяемое пространство может исчерпать уникальные составы и достичь прежнего cap.

Выбор random elite/индекса/поля и порядок оставшихся NPC, requirements/admission, cancellation, stage seeds, independent validation и итоговый score сохраняются. Proposal RNG-path после первого состава намеренно меняется из-за снятия случайного выбора операции. C1 сохраняет прежний результат и RNG; общая parity fixed count не обещается, поскольку расписание меняется и для него. Нет нового wire version, hardcoded NPC или правила монотонной сложности.

## Дешёвый gate до боёв

1. Legacy extraction: четыре полных actual JSON C1/nonnumeric42/202равны исходным; trace/untraced результат одинаков; recorded decision replay повторяет все источники/оценки прежних шести поисков и полногоUI202без новых боёв. Исторические source/harness hashes и новые hashes записываются отдельно, поскольку helper/инструментирование изменяют текст файлов, сохраняя игровое поведение.
2. Pure schedule: точный цикл/префиксыC1/C6/C18, отсутствие RNG-дискретизации операции, продвижение при duplicate, source/order±1 при count, границы/exact target/unsupported/fixed count fallback.
3. На100seeds0–99с явно условными feedback1/0/target/unknown проверитьC6/C18: bounds, admissible components, полный уникальный бюджет при широком изменяемом пространстве и минимум два component-вызова/хотя бы один принятый component. Это проверка достижимости ветвей без симуляции, не оценка побед. Отдельно неизменяемое пространство/duplicates/cap и отмена.
4. Адресные настоящие integration/JSON/real-process checks; C1actual results42/202равны baseline. Full regression/wheel без нового риска не нужны.

Если дешевый gate не пройден, дорогую серию не запускать: исправить реализацию согласованного расписания/отражения метрик либо сохранить отрицательное решение. Не выбирать другой цикл по известным боевым результатам.

## Условия сравнения до candidate

При успешном дешёвом gate — все шесть прежних полных112-trial inputs42/202, process4. Reference игровые результаты из сохранённой серии e470не пересчитываются: extraction parity проверяется выше, различие source/harness hashes явно сохраняется. Инструментирование имеет небольшую стоимость; не выдавать отличия wall time за лабораторное ускорение. Все пары/интервалы/раунды/unknown и бюджет видимы.

Первый gate сохраняет критерии ADR-0132/0133:

- Шесть первых рекомендаций,112trials на поиск, без execution failure/proposal cap; unsupported каждого поиска≤reference0.
- Macro absolute win error ниже reference; минимум две строки улучшаются≥1/32; ухудшение любой строки≤2/32.
- Хотя бы одна исходная застрявшая202строка (melee/mixed-magic) выходит из100%и становится ближе50%; они не считаются независимыми подтверждениями.
- Суммарные search+encoding≤1.5×reference717.143s.

Это engineering go/no-go, не доказательство превосходства на всех партиях. При отрицательном gate завершить все шесть строк, сохранить результаты и откатить только новое расписание к проверенному instrumented baseline; не подбирать частоты/цикл под данные.505/full candidate не запускать.

Только при положительном gate — frozen baseline/candidate mixed505/112 на прежнем неиспользованном source. Требуются рекомендация, unsupported≤baseline, cap/error0, win error≤baseline+1/32, стоимость≤1.5×baseline. Baseline содержит diagnostic extraction и прежний random selector; формула candidate не меняется. Прогоны последовательны.

Только после обоих gates — прежний full UI mixed-magic202/436: поддержанная рекомендация, point win error≤10п.п., search+encoding≤900s, unsupported≤reference2. Новая причина определяется парой `(reason,entry_id)`; известный набор — `pc_magic_miscast_unresolved` с `zone_hazard`, `random_transport`, `fascinating_rift`, `spell_recast`. Другие причины/ошибки gate не проходят. Duration вторична и видима; unknown не становятся поражениями и исключают конкретный состав. Один successful full seed не доказывает общей устойчивости.

Числа/решение сохраняются здесь, текущий этап/следующий шаг — в статусе. Локальные source snapshots/results/trace в `.cache/adr134/` требуют отдельного переноса между компьютерами. Commit/push выполняет пользователь.

## Фактическая подготовка

Original игровой source `e470ada2e692b2f7758943c22fa521cf9aaf60bd39101822f574aa4e6ff95016`; проверенный instrumented baseline со старым selector — `e7b98831ffef2c1174f89b39c6be22ae65efa01806da5ffc467b73c817375467`; candidate — `a593d5a76d59d3cf3e5ac91c92626890cce526cce86ac5d38011e0ebeca75836`. Все три application snapshots сохранены в `.cache/adr134/`, как и относящиеся tests/harness snapshots. Между baseline/candidate меняются только цикл и selector; направление/радиус не добавлены.

- Foundation:50адресных проверок,46успешных/4Windows TEMP PermissionError в sandbox,13.731s. Повторены только эти4вне sandbox:4OK/2.011s; успешные проверки не повторялись. Логи `foundation-validation.log`/`foundation-temp-validation.log`; это составной адресный результат, не единый зелёный full run.
- Четыре actual full JSON C1/nonnumeric42/202совпали original→baseline. `replay_reference.py` потребил68сохранённых observations шести коротких поисков и полногоUI202без новых боёв: полные допущенные source/stage/seed, порядки финалистов, attempts/бюджет совпали. Private recorded summary view содержит только реально записанные score-поля, не восстанавливает отсутствующие counters и не кодируется как native result. Артефакт `reference-decision-parity.json` хранит разные recorded/code source hashes и telemetry старого алгоритма.
- Candidate: `tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:40OK/13.456s. Включены800условных C6/C18планов без боёв:100seeds×2бюджета×4feedback. Bounds/admissibility, полный уникальный бюджет при широком пространстве, минимум2component-вызова и1принятый component подтверждены. Actual C1JSON42/202совпали с baseline; nonnumeric parity candidate не обещается.
- `tests.unit.test_dynamic_benchmark tests.integration.test_dynamic_encounter_json tests.integration.test_dynamic_process_json.DynamicProcessJsonSmokeTests.test_spawn_matches_sequential_result_and_preserves_source_echo tests.integration.test_dynamic_process_execution.DynamicProcessExecutionTests.test_real_spawn_pool_is_reused_and_matches_both_sequential_sources -q`:34OK/27.401s вне sandbox, `candidate-json-process-validation.log`.
- Root проверил diff инструментирования, независимое read-only ревью подтвердило scheduler/границы/attempt advancement и rollback к instrumented baseline. Дорогих параллельных прогонов не было.

Текущая серия выполняется одной командой, без overrides:

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/dynamic-stability-2026-11-17/melee-42.request.json .cache/dynamic-stability-2026-11-17/melee-202.request.json .cache/dynamic-stability-2026-11-17/mixed-42.request.json .cache/dynamic-stability-2026-11-17/mixed-202.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-42.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-202.request.json --output .cache/adr134/candidate-short.json
```

Result/log сохраняются после каждого поиска; `compare_short.py` сверяет текущие schema/source/accounting и telemetry, затем считает заранее заданные gates после всех шести строк. Исторический reference harness отличается инструментированием; его hash не объявляется равным новому. Полные C1/native trace и recorded decision parity выше отделяют изменение наблюдаемости от изменения стратегии. Во время серии source/harness заморожены.

## Результат равнобюджетного сравнения

Серия завершена:672trials, все шесть текущих result прошли schema/full source echo/accounting и сверку proposal telemetry. Бюджет каждого112, execution failures/proposal cap0. Сумма разных наблюдений:538побед игроков,123поражения,9round-limits и2unknown; это не оценка одной общей вероятности победы. Время ниже search+encoding; reference — сохранённые actual прогоны старого sourcee470, а не новый игровой прогон instrumented baseline.

| Вход | Seed | Победы первой рекомендации reference→candidate | Started rounds reference→candidate | Время reference→candidate |
| --- | ---: | --- | --- | --- |
| Melee, restricted |42|59.375→34.375%|7.688→7.031|105.893→91.700s|
| Melee, restricted |202|100→100%|4.281→5.188|31.125→38.067s|
| Mixed, auto |42|62.5→31.25%|6.250→6.656|145.380→150.068s|
| Mixed, auto |202|59.375→78.125%|8.500→8.313|150.188→115.224s|
| Mixed-magic, auto |42|71.875→нет допустимой рекомендации|6.094→—|194.597→178.317s|
| Mixed-magic, auto |202|100→100%|3.531→4.219|89.959→128.430s|

У рекомендаций32validation trials; интервалы побед/раундов обеих сторон сохранены в `short-comparison.json`. Три поддержанные строки стали дальше от50%, две остались100%. Улучшений поддержанных первых рекомендаций нет. Mixed202превысил допустимую регрессию win error:9.375→28.125п.п., рост18.75п.п. при допуске6.25. Macro candidate error всей шестистрочной серии **не определяется**: одна строка не имеет рекомендации. Она не исключается условно из среднего и не заменяется оценкой неподдержанного финалиста; reference macro25.521п.п. остаётся отдельным фактом.

В mixed-magic42оба финалиста исключены по прежней политике. Каждый имеет31победу/0поражений/1unknown из32; это разные составы, не62/64оценка одной композиции:

| Финалист | NPC | Mean started rounds | Typed stop, index, total |
| --- | ---: | ---: | --- |
| `validate:0` |9|4.40625|`pc_magic_miscast_unresolved`, `spell_recast`, trial5, total23|
| `validate:1` |8|4.09375|`pc_magic_miscast_unresolved`, `daemon_rift`, trial13, total37|

Обе остановки повторены нативно с исходными seeds, сохранёнными в raw artifact. `daemon_rift` — ещё одна наблюдавшаяся entry текущей неподключённой PC Miscast-границы; игровые правила не менялись. Unknown не подменены поражением и не стали допустимыми рекомендациями.9round-limits всей серии также не считаются победой.

## Что показали счётчики

У candidate36attempts/36принятых составов,0duplicates; у reference37attempts/36принятых,1duplicate. В каждой candidate строке requested2count/2component/2restart. Один requested count в mixed42перешёл в component при недоступном resize; итого applied11count/13component/12restart.

| Вход/seed | Applied component reference→candidate |
| --- | --- |
| Melee42 |2→2|
| Melee202 |0→2|
| Mixed42 |1→3|
| Mixed202 |2→2|
| Mixed-magic42 |2→2|
| Mixed-magic202 |2→2|
| Всего |9→13|

Механическое покрытие component выросло, но в этой серии не дало лучшего подбора. Нельзя объявлять любой другой schedule бесполезным или выводить причинный эффект одного параметра: после смены selector меняется proposal RNG-path и полные составы. Дешёвый gate проверял достижимость ветвей, а не гарантировал качество.

Первый дорогой gate=false:5/6рекомендаций, unsupported2против0, нет двух улучшений/выхода202из100%, mixed202нарушил per-cell допуск. Бюджет/cap/стоимость пройдены. Search+encoding701.806s (11.70мин) против исторического717.143s (11.95мин); diagnostic replays7.272s учитываются отдельно. Разница времени описательная и не подтверждает ускорения на одинаковой нагрузке.505/full candidate не запускались, цикл/допуски после данных не подбирались.

## Сохранённая функция и откат эксперимента

Private proposal helper и developer telemetry остаются: их legacy parity проверена actual JSON, native traced/untraced и68cached observations без новых боёв. Старый recorded source hash — e470…, старый harness —5851933500bd33c12a2e38c7f88d34e789a849f5d302e05b3d9ffa68e9b698cb; новый baseline source —e7b988…, candidate source —a593d5…, новый harness —a952e3dedc0f374a011f9927d40bd0aaf66f1d8fbc0dfc40ff8203ff5fe3d7cd. Это разные виды hashes; источник игровых reference-результатов не переименован в новый instrumented run.

Application, proposal tests и integration tests побайтно возвращены к `.cache/adr134/*.baseline.py`; source снова `e7b98831ffef2c1174f89b39c6be22ae65efa01806da5ffc467b73c817375467`. Helper использует прежний random selector ADR-0128, cycle отсутствует. Все прежние пользовательские изменения сохранены; новые tool metrics не попадают в public JSON/UI.

После возврата `tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:36OK/10.461s (`restored-validation.log`). Успешные дорогие JSON/process checks не повторялись после точного возврата проверенного baseline; full/wheel не запускались. Candidate snapshots/results/logs/telemetry сохранены в локальной `.cache/adr134/`; source/schema/accounting и все hashes повторно сверены, документационные ссылки проверены.

Следующее направление — проектирование генерации **целого состава** через управляемое распределение разрешённых числовых значений, с сохранением индивидуального разброса, ограничений снаряжения (Equipment)/талантов (Talents) и native builder. Сначала зафиксировать одну модель proposal distribution и дешёвую проверку фактического изменения нескольких NPC; затем отдельный заранее заданный native контроль влияния на сложность до новой серии поиска. Это ещё не реализовано и не формула книжной силы; новое распределение не должно одновременно менять score, budget, operator schedule или kernel. Чередование ещё одного цикла/коэффициента под известные seeds не обосновано.
