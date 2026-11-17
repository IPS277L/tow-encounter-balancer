# ADR-0133: направление числовой компонентной мутации

Дата: 2026-11-17. Статус: эксперимент завершён без выигрыша, candidate не принят; исходный application/tests восстановлены побайтно. Формула и условия ниже записаны до изменения кода и candidate измерений.

## Гипотеза и точное поведение

[ADR-0132](ADR-0132-two-member-component-mutation.md) отклонил увеличение числа случайно мутируемых NPC. Проверяется другой один фактор: выбор нового значения уже выбранного числового поля у прежнего одного NPC с учётом наблюдавшейся сложности его полного родительского состава. Это эвристика поиска, не правило монотонной силы и не причинный вывод о Стойкости (Toughness).

Выбор elite/parent, NPC и изменяемого поля остаётся прежним. Если у выбранного родителя есть unsupported либо win rate точно совпадает с target, направление0 и весь прежний путь мутации сохраняется. Иначе направление+1 при win rate игроков выше цели,−1при ниже. Сигнал берётся именно от выбранного component-parent, не от другого count-parent или общей средней всех поисков. Неизвестные исходы не становятся поражениями.

`NpcSearchSpace.mutate` принимает keyword-only `numeric_direction` с точным int−1/0/+1, default0. Обычные поля/пулы допустимых мутаций строятся прежним способом и выбираются прежним `rng.choice(variable)`. Для выбранной характеристики/навыка при ненулевом направлении из уже допустимых candidates остаётся ближайшее числовое значение в нужную сторону, независимо от порядка allowed tuple; затем исполняется прежний `rng.choice(values)`. Поля: WS/S/T/Agility/Melee/Defence/Athletics, а у ranged NPC также BS/Shooting/I/Dexterity.

Если ни одного допустимого значения в нужную сторону нет, сохраняется **прежний случайный выбор** из этого же поля. Не вводятся скрытый выбор другого поля, no-op, увеличение envelope или удаление Talent ради направления. Поэтому на границе возможно движение против сигнала; это явный exploratory fallback. Нечисловые weapon/armour/shield/abilities/talents сохраняют прежние значения выбора и RNG-путь. Direction0 тоже сохраняет прежний путь полностью. При ненулевом направлении числового поля последующий RNG-path может измениться из-за размера values.

Мутация остаётся одного NPC/одного поля через существующий builder с prerequisites. Count±1/расписание ветвей,30%restarts, score win→rounds, C/E/V, stage seeds, admission/kernel и текущий JSON/UI не меняются. C1 и пространства без изменяемых числовых полей сохраняют полные прежние результаты. Singleton не исключён из направленной мутации: это намеренное отличие от проверки масштаба ADR-0132. Нового публичного JSON поля/версии нет.

## Проверки и условия до candidate

Детерминированно проверить оба направления для характеристик/навыков/ranged source, ближайшее значение в несортированном allowed tuple, boundary/невозможный prerequisite fallback, сохранение Talent/остальных компонентов, signal0при unsupported/точном target, default0/RNG и отклонение bool/float/неразрешённых directions. Integration должна подтвердить использование сигнала реального родителя и прежние source/count/validation/budget/cancel/progress guards. Ближайшие JSON/real process checks — по изменённому пути; full regression/wheel без нового риска не нужны.

До правки сохранить точный application/integration snapshot со всеми прежними незакоммиченными изменениями в `.cache/adr133/`. Четыре actual full JSON controls C1 и nonnumeric-only на42/202должны совпасть с reference. Проверить собственный diff и заморозить source/harness на всю серию.

Первый gate — те же шесть полных inputs42/202 из [серии устойчивости](../benchmarks/dynamic-stability-2026-11-17.md),112trials каждый (6×8+2×32), process4. Сохранённый reference не пересчитывается. Показать все пары и интервалы выбранных составов, duration, фактическую стоимость и все unknown. Условия прежнего сравнения ADR-0132 сохраняются:

- Шесть рекомендаций и полный112-trial бюджет каждой строки, без execution failure/proposal cap; unsupported в каждой строке≤reference0.
- Macro absolute win error ниже reference; минимум две строки улучшаются≥1/32; ухудшение любой строки≤2/32.
- Хотя бы одна исходная застрявшая202строка (melee/mixed-magic) выходит из100%и становится ближе50%. Они не считаются независимыми подтверждениями.
- Суммарные search+encoding≤1.5×reference717.143s. Это ограниченный engineering go/no-go, не статистическое доказательство универсальности; более трудные бои могут стоить дороже.

При отрицательном gate завершить все шесть строк, сохранить результаты и восстановить только собственный snapshot. Направление/nearest/fallback/допуски после просмотра результатов не менять.505/full candidate после отрицательного первого gate не запускать.

Только при успешном первом gate — mixed505/112, тот же заранее подготовленный неиспользованный source `.cache/adr132/mixed-505.request.json`. Reference исполняется из точного snapshot, candidate — из замороженного проверенного source; прогоны последовательны, формула не меняется. Требуются рекомендация, unsupported≤reference, отсутствие proposal cap/ошибки, win error≤reference+1/32, стоимость≤1.5×reference.

Только после обоих gates — прежний full UI mixed-magic202/436. Для внедрения: поддержанная рекомендация, point win error≤10п.п., search+encoding≤900s, unsupported≤reference2. Новая причина определяется парой `(reason,entry_id)`; разрешённый уже наблюдавшийся набор — `pc_magic_miscast_unresolved` с `zone_hazard`, `random_transport`, `fascinating_rift` или `spell_recast`. Остальные причины/ошибки gate не проходят. Duration вторична и видима; unknown исключают конкретный состав по прежней политике. Один full seed не доказывает общего качества.

При любом отрицательном gate candidate не становится default. Постоянное решение/все пары остаются в этом ADR, текущий этап/следующий шаг — в статусе. Локальные artifacts `.cache/adr133/` нужно переносить отдельно для точного повтора на другом компьютере.

## Подготовка и исполнение

Reference source hash `e470ada2e692b2f7758943c22fa521cf9aaf60bd39101822f574aa4e6ff95016`, candidate `0cdaa91488840eb05e967ec9cd266eb31e036e58a6fa86ec6f17b5d4b845bc98`. Diff ограничен numeric_direction в существующем mutate, чистым helper сигнала и передачей выбранного component-parent; прочие source файлы не менялись. Точные application/integration snapshots и новые tests сохранены в `.cache/adr133/`. Исходники во время измерений заморожены.

- `tests.unit.test_directed_numeric_mutation tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:38OK/10.590s, `preflight-validation.log`.
- `tests.integration.test_dynamic_encounter_json tests.integration.test_dynamic_process_json.DynamicProcessJsonSmokeTests.test_spawn_matches_sequential_result_and_preserves_source_echo tests.integration.test_dynamic_process_execution.DynamicProcessExecutionTests.test_real_spawn_pool_is_reused_and_matches_both_sequential_sources -q`:20OK/21.959s, `json-process-validation.log`.
- Четыре полных actual JSON C1/nonnumeric42/202совпали целиком; artifacts `invariant-reference.json`/`invariant-candidate.json`, script `invariant_checks.py`. Это не сравнение изменяемого singleton, которого invariant-план не обещает.

Серия использует прежние точные inputs, без overrides:

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/dynamic-stability-2026-11-17/melee-42.request.json .cache/dynamic-stability-2026-11-17/melee-202.request.json .cache/dynamic-stability-2026-11-17/mixed-42.request.json .cache/dynamic-stability-2026-11-17/mixed-202.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-42.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-202.request.json --output .cache/adr133/candidate-short.json
```

Один process4поиск за раз, реальный spawn вне sandbox из-за известного ограничения Windows pipes. Промежуточные measurements сохраняются после каждого поиска; `compare_short.py` проверяет schema/source/accounting и вычисляет первый gate после всех шести строк. Не запускать параллельно тяжёлые проверки и не выдавать промежуточный результат за принятие default.

Независимое read-only ревью перед серией подтвердило семантику числовых Skills, предварительную фильтрацию prerequisites и заявленный fallback, направление от выбранного parent и неизменность остальных ветвей. Ревьюер не запускал симуляций или тестов.

## Результаты всех шести поисков

Завершены672trials, все шесть текущих result прошли schema/source echo/accounting; source/harness hashes совпали с зафиксированными. У каждого поиска112trials, рекомендация есть, proposal cap/ошибок исполнения нет. Unsupported0, round-limits9как у reference; лимиты не считаются победами.

Все шесть **первых рекомендаций** совпали с reference полными candidate records, включая NPC, native source и оценки. Таблица относится именно к первым рекомендациям каждого поиска; у обоих вариантов32validation trials на состав:

| Вход | Seed | Победы reference=candidate | Wilson95%, оба | Started rounds, оба | Время reference→candidate |
| --- | ---: | --- | --- | ---: | --- |
| Melee, restricted |42|19/32 (59.375%)|42.26–74.48%|7.688|105.893→99.393s|
| Melee, restricted |202|32/32 (100%)|89.28–100%|4.281|31.125→29.621s|
| Mixed, auto |42|20/32 (62.5%)|45.25–77.07%|6.250|145.380→129.061s|
| Mixed, auto |202|19/32 (59.375%)|42.26–74.48%|8.500|150.188→125.931s|
| Mixed-magic, auto |42|23/32 (71.875%)|54.63–84.44%|6.094|194.597→158.856s|
| Mixed-magic, auto |202|32/32 (100%)|89.28–100%|3.531|89.959→82.814s|

Macro absolute win error остался25.521п.п.; улучшившихся строк0, обе застрявшие202строки остались100%. Ни одна первая рекомендация не попала одновременно в описательные win±10п.п./duration±1. Интервалы начатых раундов также сохранены в `short-comparison.json`; они включают censored prefix и не являются гарантией длительности завершённого боя.

Совпадение первых рекомендаций не означает равенства всех финалистов: совпали11из12validation candidate records. Второй финалист mixed-magic42 (`dynamic:validate:1`) изменил WSодного NPC2→3, сохранил100%побед, mean_started_rounds3.78125→4.0625. В первых четырёх поисках совпали полные JSON result reports. В двух магических поисках изменился один screening-состав в каждом: всего34из36screening compositions совпали по индексу. Источник проверки — `composition-comparison.json` и полные artifacts, не только одинаковые проценты.

Первый gate=false: macro не снизился, двух улучшений нет, ни одна застрявшая строка не вышла из100%. Проверки рекомендаций/бюджета/unsupported/cap/допуска регрессии/стоимости пройдены.625.676s (10.43мин) search+encoding против717.143s (11.95мин) — один последовательный замер, не доказательство ускорения эвристики: первые четыре поиска имеют одинаковую игровую нагрузку, но тоже различаются по времени. Reference/candidate505и full UI candidate не запускались; пороги, nearest/fallback и формула после данных не менялись.

## Дешёвая диагностика фактического применения

До возврата source выполнен `replay_proposals.py` в `.cache/adr133/`: повтор **решений поиска по сохранённым наблюдениям**, без новых боёв. Callback потребляет48фактически записанных observations (36screening+12validation), каждый раз проверяя полное равенство typed source с заранее допущенным native replay. Берутся только записанные outcomes и total started rounds, необходимые для прежнего score/ветвления. Engine runner заблокирован, выход не кодируется как simulation result.

Private `RecordedSummaryView` временно подменяет ожидаемый класс summary только в отдельном процессе инструмента. Он не восстанавливает отсутствующие counters, не является native aggregate и не заменяет его валидацию. Это диагностическое воспроизведение control flow, а не дополнительные Monte Carlo-наблюдения или игровые replay. Совпадение всех источников, использованных observations и порядка финалистов проверено. Source до/после тот же candidate; runtime файла не менялся.

| Вход/seed | Вызовы component mutate | Выбрано числовое поле | Допустимое направление было | Новое значение отличается от прежнего выбора |
| --- | ---: | ---: | ---: | ---: |
| Melee42 |2|1|1|0|
| Melee202 |0|0|0|0|
| Mixed42 |1|1|0|0|
| Mixed202 |2|1|0|0|
| Mixed-magic42 |2|2|2|1|
| Mixed-magic202 |2|2|1|1|
| Всего |9|7|4|2|

Сравнение с прежним direction0 использует отдельный shadow RNG с тем же текущим состоянием перед каждым вызовом. Во всех9вызовах локальные конечные RNG states совпали; это не доказательство равенства всего глобального proposal RNG-path двух алгоритмов. Артефакт `proposal-replay.json` хранит эти признаки, source/measurement hashes и executed_battles=0. Результат не расширяет672-trial выборку. Независимое read-only ревью подтвердило узкую интерпретацию этого инструмента.

Главное ограничение короткогоC6эксперимента — малая фактическая экспозиция нового оператора: он изменил значения лишь в двух component-вызовах, а в melee202component-ветка вообще не выполнялась. Это объясняет ограниченность проверки данной гипотезы; из отсутствия выигрыша нельзя заключить, что направленные мутации вообще бесполезны. Критерии внедрения всё равно не пройдены, поэтому candidate не оставлен в default.

Для отделения C6от рабочего плана дешёво проверен и **прежний baseline**, без candidate: сохранённый full UI mixed-magic202/436. На восстановленном sourcee470`replay_baseline_proposals.py` потребил20его записанных observations (18screening+2validation), без новых боёв. Число component-вызовов6, все выбрали числовое поле. Полные источники/порядок оценок проверены; total rounds восстановлен из mean×trials с обязательной точной обратной проверкой total/trials=записанный mean. Артефакт `baseline-full-proposal-replay.json` содержит source/measurement hashes и executed_battles=0. Это подсчёт операций старого полного плана, а не измерение качества candidate на нём и не доказательство дефекта расписания. Локальные сравнения baseline с собой не являются оценкой эффекта numeric_direction.

## Возврат и следующий шаг

Application/integration tests побайтно восстановлены из `.cache/adr133/*.reference.py`, source hash снова `e470ada2e692b2f7758943c22fa521cf9aaf60bd39101822f574aa4e6ff95016`. Прежние незакоммиченные изменения сохранены. Candidate source/tests оставлены только в локальных `*.candidate.py`; собственный unit module/helper/numeric_direction удалены из исполняемого набора.

После возврата `tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:28OK/10.158s, `restored-validation.log`. Дорогие JSON/process проверки уже выполнены, восстановлен точный проверенный reference; full/wheel не повторялись. Cached decision replay требует candidate source и сейчас намеренно не запускается на восстановленном runtime. Raw artifacts нужно переносить отдельно для точного повтора на другом компьютере.

Затем проверено расписание count/component/restart по [ADR-0134](ADR-0134-proposal-schedule-and-observability.md): покрытие операций выросло, боевой подбор не улучшился; расписание снято, новая наблюдаемость сохранена с legacy parity. Числовая мутация ADR-0133 не оставлена вторым фактором. Актуальная очередь закреплена в [статусе](../project-status.md#следующий-шаг); общий threat scalar и причинная модель одной характеристики из этих данных не следуют.
