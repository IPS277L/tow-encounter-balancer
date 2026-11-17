# ADR-0132: компонентная мутация двух участников состава

Дата: 2026-11-17. Статус: эксперимент завершён и отклонён; исходный application/tests восстановлены побайтно. Условия ниже зафиксированы до изменения кода и измерения candidate.

## Основание и граница

[Повтор двух фиксированных составов](../benchmarks/dynamic-plateau-escape-2026-11-17.md#результат-контроля404) сохранил разрыв сложности при одинаковых10NPC. Он не выделяет эффект одной характеристики и не подтверждает новую поисковую стратегию. Следующая гипотеза меняет только масштаб существующего компонентного предложения: два разных участника вместо одного. Более крупная мутация может выйти из локальной области, но может и разрушить полезный состав; сравнение определяет решение.

В прежней component-ветке сначала выполняются прежние `randrange(n)` и `space.mutate` для первого NPC. При n>1 затем выполняется `randrange(n-1)`; индекс не меньше первого увеличивается на1. Второй NPC мутирует через тот же `space.mutate`. Это выбор двух различных позиций без замены; порядок списка/численность и остальные участники сохраняются. Для n=1 нет второго RNG-вызова и сохраняется прежний полный путь. Для C1, где адаптивного предложения нет, исполнение прежнее. При fixed count>1 масштаб компонентной мутации намеренно меняется.

Каждая мутация использует существующие prerequisites/валидацию. Если пространство не допускает изменения выбранного участника, не вводятся принудительная замена, скрытый третий выбор или новое послабление; прежний seen/proposal cap обрабатывает дубликаты. Ровно два разных **выбранных** участника не обещают два фактически изменённых профиля. RNG передаётся явно.

Count±1/parent,30%random restarts, расписание ветвей, elite selection, win→rounds score, C/E/V, seeds стадий, kernel, JSON/UI и правила не меняются. При n>1 последующий proposal RNG-path закономерно изменится; одинаковый master seed не означает одинаковые составы разных алгоритмов.

## Проверки до измерений

- Детерминированно проверить distinct indices/обе стороны отображения индекса, неизменные count/порядок/остальных участников, прежний первый результат мутации, singleton RNG parity и неизменяемое пространство.
- Реальные generated sources должны сохранять admission; integration — два изменённых участника в component-ветке, прежний resize, independent validation/source/accounting/duplicates/cancel/progress. Нужны ближайшие JSON/process-проверки; full regression/wheel без нового риска не требуются.
- Сравнить полные реально исполненные текущие JSON results с исходным алгоритмом для singleton и C1 на42/202. Snapshot исходного application/tests сохраняется в `.cache/adr132/`; откат затрагивает только этот эксперимент, сохраняя прежний dirty tree.

## Условия решения до candidate измерений

Первый gate — все шесть прежних inputs42/202 из [серии устойчивости](../benchmarks/dynamic-stability-2026-11-17.md), без изменения запросов: каждый6×8+2×32=112trials, process4. Reference уже сохранён, повторять его не нужно. Показать все пары, duration, unknown, proposal cap и фактическое время. Это ограниченный engineering go/no-go, не доказательство статистического превосходства.

Для перехода дальше нужны одновременно:

1. Шесть рекомендаций, полный112-trial бюджет каждого поиска, без execution failures/proposal cap; unsupported в каждом поиске не больше исходного0.
2. Средняя абсолютная ошибка доли побед относительно50% ниже reference; минимум две строки улучшаются хотя бы на1/32. Ухудшение отдельной строки не больше2/32 (6.25п.п.); это заранее принятый практический допуск, не доверительный интервал.
3. Хотя бы одна из исходных застрявших202строк (melee/mixed-magic) выходит из100%и становится ближе50%. Два таких случая не считаются независимыми подтверждениями.
4. Суммарные search+encoding не больше1.5×reference717.143s. У более трудных боёв может быть большая стоимость; она показывается, но бюджет ресурсов остаётся условием внедрения.

При отрицательном gate закончить шестистрочное сравнение, сохранить отрицательный результат и восстановить исходный application; не подбирать число участников/порог под результаты и не запускать последующие дорогие контроли.

Только после положительного первого gate — mixed505/112 с теми же facts/plan/process4. Seed505 выбран до candidate; reference снимается из точного сохранённого исходника, candidate — из замороженного проверяемого исходника. Оба запуска последовательны; никаких правок во время измерения. Для продолжения нужны рекомендация, отсутствие новых unsupported/proposal cap, win error не больше reference+1/32 и стоимость≤1.5×reference. Порядок получения reference после первого gate не даёт права менять формулу.

Только после обоих gates — полный прежний UI mixed-magic202/436 при неизменном запросе. Для внедрения: поддержанная рекомендация, point win error≤10п.п., search+encoding≤900s, unsupported≤reference2 и отсутствие новых причин остановок/ошибок исполнения. Для этого gate причина задаётся парой `(reason, entry_id)`; разрешённый уже наблюдавшийся набор зафиксирован до candidate: `pc_magic_miscast_unresolved` с `zone_hazard`, `random_transport`, `fascinating_rift` или `spell_recast`. Это объединение прежних контролей, не только двух entries reference202; остальные причины gate не проходят. Duration вторична и показывается. Известные unknown остаются видимыми и исключают конкретный состав по прежней политике. Один successful full seed не доказывает универсальной устойчивости.

При любом отрицательном gate эксперимент не становится default. Raw результаты — в локальной `.cache/adr132/`, решение/актуальный следующий шаг — в этом ADR и статусе. Новая эвристика не добавляет книжных statblocks, общий threat scalar или house rule.

## Фактическая подготовка

Candidate ограничен новым helper и заменой прежних двух строк component-ветки; это подтверждено diff против точного snapshot со всеми прежними незакоммиченными изменениями. Reference source hash `e470ada2e692b2f7758943c22fa521cf9aaf60bd39101822f574aa4e6ff95016`, candidate `9b8433d6e1bca64655d3a4a3335791810564612bb8d715624a01ffe5468346c2`. Во время серии исходники заморожены. Все шесть запросов предварительно допущены и полностью совпали с reference sources; developer harness тот же. Вход `mixed-505.request.json` подготовлен/допущен до просмотра полной серии, ещё не исполнен.

- `tests.unit.test_component_mutation_proposals tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:34OK/14.255s.
- Текущий JSON integration module:18проверок успешно; первый составной вызов завершился ошибкой19-го selector из-за неверного имени smoke-класса в команде, не игрового сбоя. Исправленный selector `tests.integration.test_dynamic_process_json.DynamicProcessJsonSmokeTests.test_spawn_matches_sequential_result_and_preserves_source_echo` вместе с `tests.integration.test_dynamic_process_execution.DynamicProcessExecutionTests.test_real_spawn_pool_is_reused_and_matches_both_sequential_sources`:2OK/4.649s. Успешный дорогой JSON module повторно не запускался.
- Четыре full current JSON result singleton/C1на42/202совпали с reference целиком; artifacts `invariant-reference.json`/`invariant-candidate.json`, script `invariant_checks.py` в `.cache/adr132/`.
- Независимое read-only ревью до candidate подтвердило план, после правки — distinct indices, прежний первый draw/mutate, singleton RNG и сохранение guards. Дополнительных тяжёлых прогонов ревьюер не запускал.

Серия запускается одной командой, без параллельных тяжёлых задач:

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/dynamic-stability-2026-11-17/melee-42.request.json .cache/dynamic-stability-2026-11-17/melee-202.request.json .cache/dynamic-stability-2026-11-17/mixed-42.request.json .cache/dynamic-stability-2026-11-17/mixed-202.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-42.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-202.request.json --output .cache/adr132/candidate-short.json
```

Реальный spawn исполнялся вне sandbox из-за известного Windows pipe ограничения. Прогресс/полные результаты сохранены после каждого поиска; `.cache/adr132/compare_short.py` проверяет текущие schema/source/accounting и вычисляет gates только после всех шести строк. Промежуточный успех не стал основанием принятия нового default.

## Все пары и решение

Серия завершена:672trials, шесть рекомендаций, без execution failures/proposal cap. Во всех строках один и тот же полный source request/112-trial план у reference/candidate; рекомендации оцениваются32новыми validation trials. Это сравнение двух алгоритмов поиска, порождающих разные составы, а не парный тест одной композиции. Время — search+encoding, без отдельных диагностических replay; одинаковые trials могут иметь разную стоимость из-за разных боёв.

| Вход | Seed | Победы reference→candidate | Started rounds reference→candidate | Время reference→candidate |
| --- | ---: | --- | --- | --- |
| Melee, restricted |42|59.375→59.375%|7.688→7.688|105.893→109.183s|
| Melee, restricted |202|100→100%|4.281→4.281|31.125→32.608s|
| Mixed, auto |42|62.5→59.375%|6.250→5.969|145.380→135.617s|
| Mixed, auto |202|59.375→90.625%|8.500→6.063|150.188→105.993s|
| Mixed-magic, auto |42|71.875→100%|6.094→3.781|194.597→140.408s|
| Mixed-magic, auto |202|100→100%|3.531→4.625|89.959→130.644s|

Macro mean absolute win error25.521→34.896п.п. (хуже на9.375п.п.). Одна строка улучшилась на1/32; две ухудшились более чем на допустимые2/32: mixed202на31.25п.п. ошибки и mixed-magic42на28.125п.п. Обе исходные застрявшие202строки остались100%. У mixed-magic202screening достиг9NPCвместо6, но count coverage не превратился в нужную сложность.

Есть и положительный локальный результат: mixed42получил59.375%побед/5.969раунда — оба описательных point-ориентира win±10п.п./duration±1. Это один короткий результат с32-trial оценкой, не гарантия вероятности или общего улучшения. Gate не менялся ради него; одинаковые проценты в первых двух строках не объявляются равенством полных search reports.

Всего9round-limits, как у reference; они не считаются победой. Один unsupported против reference0: mixed-magic42, `dynamic:explore:5`, trial1, seed`85827077352730258687242700352296609763471172998764169443268227887654559945368`, `pc_magic_miscast_unresolved`, entry`zone_hazard`, total34. Native replay подтвердил typed stop; sample сохранён в artifact. Этот9NPCscreening дал7побед/1unknown/0поражений и исключён; unknown не подменён поражением. Все выбранные рекомендации имеют0unsupported.

| Первый gate | Итог |
| --- | --- |
| Рекомендации,112trials в каждой строке, execution/proposal guards |Пройден|
| Unsupported≤reference в каждом поиске |Не пройден:1против0|
| Macro error ниже |Не пройден|
| Минимум две строки улучшились≥1/32 |Не пройден:только одна|
| Регресс каждой строки≤2/32 |Не пройден:две нарушают|
| Хотя бы одна застрявшая202приблизилась к50% |Не пройден|
| Стоимость≤1.5×reference |Пройден|

Search+encoding654.454s (10.91мин) против717.143s (11.95мин). Это стоимость исполненных разных боёв; меньшая длительность серии не подтверждает ускорение алгоритма при одинаковой нагрузке и не компенсирует ухудшение подбора. Итого gate=false. Reference/candidate505и полный candidateUI202не запускались; подготовленный505остаётся неиспользованным. Пороги, число мутируемых NPC и seed после данных не подбирались.

## Возврат и проверка

До возврата подтверждены текущие candidate source/harness hashes; все шесть result прошли текущие schema, полный source echo и accounting outcomes/trials. После возврата application побайтно совпал с `.cache/adr132/dynamic_encounter.reference.py`, integration tests — с `test_dynamic_encounter.reference.py`; source hash снова `e470ada2e692b2f7758943c22fa521cf9aaf60bd39101822f574aa4e6ff95016`. Все прежние незакоммиченные изменения сохранены. Candidate source/tests остались только как локальные `*.candidate.py`; собственный новый unit module удалён из исполняемого набора, helper/ветка не оставлены в runtime.

После возврата `tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:28OK/9.896s, `.cache/adr132/restored-validation.log`. JSON/process checks уже выполнены до серии, восстановлен точный ранее проверенный source; повторный дорогой JSON/full/wheel не нужен. Восстановление проверяет исполняемый поиск, не превращая предыдущий составной запуск с ошибкой selector в единый зелёный full run.

Полные measurements — `.cache/adr132/candidate-short.json`, сравнение/все gates — `short-comparison.json`, лог — `candidate-short.run.log`; эта локальная `.cache` не переносится через Git автоматически. Для точного повтора raw inputs/results/snapshots нужно перенести отдельно. Постоянный итог сохраняет этот ADR.

Отклонена конкретная гипотеза масштаба случайной компонентной мутации. Данные не доказывают бесполезность компонентного поиска и не выделяют причинный эффект одной характеристики: изменились составы и последующий RNG-path. Гипотеза направления числового изменения затем проверена отдельно по [ADR-0133](ADR-0133-directed-numeric-component-mutation.md), без изменения радиуса/численности; candidate не принят, выявлена малая фактическая экспозиция оператора. Актуальный следующий шаг закреплён в [статусе](../project-status.md#следующий-шаг). Увеличение радиуса до3или новый коэффициент под известные seeds из этих результатов не следуют.
